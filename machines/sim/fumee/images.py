"""Images de la sim (F1, 25/11, spec §5) : une image n'est reconstruite que si les fichiers qui la
composent ont changé. Empreinte = sha256 de ces fichiers, posée en étiquette `didier.empreinte` au
build (surcouche compose écrite dans le dossier temporaire, le compose du dépôt reste intact).
Fini « aucune fumée verte de référence, on reconstruit tout ».
"""
import hashlib
import re
import shlex
from pathlib import Path

# Même liste que CHEMINS_IMAGES de fumee.sh (gravé par test), répartie par image : chaque image a
# ses chemins, plus le compose qui les décrit toutes.
PAR_IMAGE = {
    "monde": ("machines/sim",),
    "robot": ("machines/robot/docker", "machines/robot/packages-docker.txt", "machines/robot/requirements.txt"),
    "vision": ("machines/vision/docker", "machines/vision/packages-docker.txt", "machines/vision/requirements.txt"),
    "telecommande": ("legacy/dadou_control_ros/conf",),
}
COMMUN = ("machines/sim/docker-compose.yml",)
CHEMINS_IMAGES = tuple(c for chemins in PAR_IMAGE.values() for c in chemins)
ETIQUETTE = "didier.empreinte"
# Échec du build venu du RÉSEAU (registre ou DNS), pas du Dockerfile (vécu le 18/11) : fumee.sh.
PANNE_RESEAU = re.compile(r"lookup [^ ]+ on [^ ]+: .*(i/o timeout|no such host|server misbehaving)|dial tcp: .*"
                          r"(i/o timeout|connection refused|network is unreachable)|TLS handshake timeout|temporary "
                          r"failure in name resolution|failed to do request: (Head|Get) \"https://[^\"]*(docker\.io|"
                          r"docker\.com)", re.IGNORECASE)


def empreinte(arbre: Path, chemins) -> str:
    """sha256 des chemins (relatifs) ET des contenus, dans un ordre stable ; caches Python exclus."""
    h = hashlib.sha256()
    for chemin in sorted(chemins):
        p = arbre / chemin
        fichiers = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p] if p.is_file() else []
        for x in fichiers:
            if "__pycache__" in x.parts or x.suffix == ".pyc":
                continue
            h.update(str(x.relative_to(arbre)).encode() + b"\0" + hashlib.sha256(x.read_bytes()).digest())
    return h.hexdigest()


def phase(f, ident="image") -> dict:
    """Épreuve « image » : réutilisées, reconstruites (en ligne), ou invalide hors ligne."""
    voulues = {s: empreinte(f.arbre, COMMUN + c) for s, c in PAR_IMAGE.items()}
    a_faire = []
    for service, voulue in voulues.items():
        rc, lue = f.sy.sortie(["docker", "image", "inspect", "-f",
                               '{{ index .Config.Labels "%s" }}' % ETIQUETTE, "didier-sim/%s:local" % service])
        if rc != 0 or lue.strip() != voulue:
            a_faire.append(service)
    r = {"id": ident, "journal": "image.log"}
    if not a_faire:
        return {**r, "statut": "vert", "detail": "les 4 images portent l'empreinte de cette révision : réutilisées"}
    if f.hors_ligne:
        # Une image d'une autre révision ne teste pas celle-ci : absente comme manquante.
        return {**r, "statut": "invalide", "detail": "invalide : hors ligne, image(s) à reconstruire : " + ", ".join(a_faire)}
    surcouche = f.tmp / "docker-compose.empreinte.yml"
    surcouche.write_text("services:\n" + "".join('  {}:\n    build:\n      labels:\n        {}: "{}"\n'.format(
        s, ETIQUETTE, voulues[s]) for s in a_faire), encoding="utf-8")
    cmd = ["docker", "compose", "-f", "docker-compose.yml", "-f", str(surcouche), "build",
           *shlex.split(f.sy.env.get("FUMEE_BUILD_ARGS", "")), *a_faire]
    texte = ""
    for essai in (1, 2):   # une coupure DNS de quelques secondes ne doit pas compter
        rc, sortie = f.sy.sortie(cmd, cwd=f.arbre / "machines" / "sim")
        texte += "=== essai {}\n{}\n".format(essai, sortie)
        if rc == 0 or not PANNE_RESEAU.search(sortie) or essai == 2:
            break
        f.pause(int(f.sy.env.get("FUMEE_ATTENTE_RESEAU", "60")))
    (f.tmp / "image.log").write_text(texte, encoding="utf-8")
    if rc == 0:
        f.image_reconstruite = True
        return {**r, "statut": "vert", "detail": "reconstruite(s) : " + ", ".join(a_faire)}
    if PANNE_RESEAU.search(sortie):
        return {**r, "statut": "invalide", "detail": "invalide : panne réseau, registre Docker injoignable pendant "
                                                     "la reconstruction — défaut de l'environnement, pas de Didier"}
    return {**r, "statut": "rouge", "detail": "la reconstruction a échoué (" + ", ".join(a_faire) + ")"}
