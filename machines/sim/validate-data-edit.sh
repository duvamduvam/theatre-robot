#!/bin/bash
# L1d — preuve REJOUABLE de l'édition des données à travers le robot, en simulation (spec
# theatre-robot/docs/spec-L1-contrats-donnees.md, « L1d », décision 15, épreuves 1 à 12 ; la 13,
# porte sim, arrive avec L1d-2), DANS le conteneur sim (domaine 43) démarré avec
# DATA_EDIT=true ANIMATIONS=true FACE=true.
#   1. création d'une séquence -> ok, fichier présent, nom au catalogue en <= 5 s ;
#   2. retouche (neck à 0.37) -> ok, octets exacts, sauvegarde, 2 lignes au journal ;
#   3. jouée : animation_state porte le nom ET neck reçoit 0.37 (rechargement prouvé) ;
#   4. faces vers une expression inconnue -> contrat, fichier inchangé ;
#   5. noms ../x/y et tmp-l1d/../../x -> nom_invalide, rien créé hors cible ;
#   6. roues hors bornes (0.95, dernière image non nulle, {"speed": 100}) -> contrat ×3 ;
#   7. roues dans les bornes -> ok + roues_a_valider_en_sim ; jouée : cmd_vel non nul puis nul,
#      DURÉE NON NULLE ÉCRITE AU RAPPORT (constat « impulsion ou tenue », pas un critère) ;
#   8. base_sha256 faux -> conflit ;  9. 131 073 octets -> trop_gros ;
#  10. PNG 24x16 en bouche -> ok ; le même en œil -> contrat ; des octets non PNG -> contrat ;
#  11. expression qui montre cette image -> ok, au catalogue, face_sim l'affiche sans erreur ;
#  12. lumière chaînant deux briques -> ok, au catalogue ; brique inconnue -> contrat.
# Lance la chaîne roues (drive.launch.py) si elle manque, l'arrête en sortant.
# Restaure expressions.json, robot_lights.json (et validations-sim.json s'il existe), efface ce
# qu'il a créé (tmp-l1d/, image, sauvegardes, lignes du journal) : empreinte de json/ et
# medias/visuals/ identique avant et après, sinon code 1 même à 12/12.
# Sortie 0 = OK ; 1 = KO ; 2 = banc faux (hors sim, nœud absent, édition désactivée).
# Rien ici ne peut atteindre le vrai robot : refus hors domaine 43.
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
NS="/${ROBOT_NAME:-didier}"
export NS
[ "${ROS_DOMAIN_ID:-}" = 43 ] || { echo "REFUS : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, ce script ne tourne qu'en simulation (43)"; exit 2; }

LANCES=()
lance() { # lance <motif pgrep « déjà là »> <nom> <commande…> (même motif que validate-namespace.sh)
  local motif=$1 nom=$2; shift 2
  if pgrep -f "$motif" >/dev/null; then echo "  déjà présent : $nom"; return; fi
  setsid "$@" >"/tmp/validate-data-edit-$nom.log" 2>&1 &
  LANCES+=($!); echo "  lancé : $nom (pid $!, journal /tmp/validate-data-edit-$nom.log)"
}
arreter() {
  for pid in "${LANCES[@]}"; do kill -INT -- "-$pid" 2>/dev/null; done
  for i in $(seq 1 20); do
    vivant=0; for pid in "${LANCES[@]}"; do kill -0 "$pid" 2>/dev/null && vivant=1; done
    [ $vivant = 0 ] && return; sleep 0.5
  done
  for pid in "${LANCES[@]}"; do kill -KILL -- "-$pid" 2>/dev/null; done
}
trap arreter EXIT

echo "=== édition à travers le robot sous $NS/ $(date +%T) ==="
# Sans démon : une découverte courte rate des nœuds (vu le 12/11) -> jusqu'à 4 essais.
for essai in 1 2 3 4; do
  noeuds=$(ros2 node list --no-daemon --spin-time 5 2>/dev/null)
  manque=""
  # animations_node se nomme « animation_node » (ANIMATION + "_node") : nom historique.
  for n in data_edit_node animation_node face_sim_node catalogue_node; do
    grep -qx "$NS/$n" <<<"$noeuds" || manque="$manque $NS/$n"
  done
  [ -z "$manque" ] && break; sleep 2
done
[ -z "$manque" ] || { echo "PRÉCONDITION :$manque absent(s) (sim lancée avec DATA_EDIT=true ANIMATIONS=true FACE=true ?)"; exit 2; }
lance "/twist_deadman( |$)" drive ros2 launch didier_drive drive.launch.py use_sim_time:=true
sleep 5

python3 - <<'PY'
import base64, hashlib, json, os, shutil, struct, sys, time, zlib
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from theatre_interfaces.msg import StringTime

NS = os.environ["NS"]
DATA = "/home/ros2_ws/src/robot"
JSON = DATA + "/json"
SEQ = JSON + "/sequences"
TMP_DIR = SEQ + "/tmp-l1d"
BACKUP = JSON + "/backup"
JOURNAL = BACKUP + "/EDITIONS-EN-ATTENTE.jsonl"
LOG = "/home/ros2_ws/log/robot.log"
RESTAURES = [JSON + "/expressions.json", JSON + "/robot_lights.json", JSON + "/validations-sim.json"]
PREFIXE = "l1d-v{}".format(os.getpid())  # ids de cette passe : on n'efface que les nôtres
DELAI = 5

ok = ko = 0
def verdict(bon, texte):
    global ok, ko
    print("  {} {}".format("✅" if bon else "❌", texte), flush=True)
    if bon: ok += 1
    else: ko += 1

def empreinte_arbre():
    """sha de tout json/ (hors backup/) et medias/visuals/ : avant == après, sinon résidu."""
    h = hashlib.sha256()
    for racine in (JSON, DATA + "/medias/visuals"):
        for d, sous, fichiers in sorted(os.walk(racine)):
            sous[:] = sorted(s for s in sous if os.path.join(d, s) != BACKUP)
            for f in sorted(fichiers):
                p = os.path.join(d, f)
                # Droits compris : une retouche qui rendrait 644 un fichier suivi en 755 se verrait.
                h.update(p.encode() + b"\0" + oct(os.stat(p).st_mode).encode() + open(p, "rb").read())
    return h.hexdigest()

def lister(racine):
    return {os.path.join(d, x) for d, s, f in os.walk(racine) for x in s + f}

# ---- état initial, pour tout remettre en place
sauves = {p: (open(p, "rb").read(), os.stat(p).st_mode) for p in RESTAURES if os.path.exists(p)}
TMP_IMAGES = DATA + "/medias/.tmp"
tmp_images_existait = os.path.isdir(TMP_IMAGES)
journal_avant = open(JOURNAL, "rb").read() if os.path.exists(JOURNAL) else None
backup_avant = lister(BACKUP) if os.path.isdir(BACKUP) else set()
backup_existait = os.path.isdir(BACKUP)
empreinte_avant = empreinte_arbre()
offset_log = os.path.getsize(LOG) if os.path.exists(LOG) else 0
shutil.rmtree(TMP_DIR, ignore_errors=True)
os.makedirs(TMP_DIR)  # le topic ne crée jamais de dossier (dossier_absent) : fixture de l'essai

rclpy.init()
node = rclpy.create_node("validate_data_edit", namespace=NS)
latche = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
resultats, etats, cous, cmd = [], [], [], []
catalogue = {}
node.create_subscription(StringTime, "data_edit_result", lambda m: resultats.append(json.loads(m.msg)), 10)
node.create_subscription(StringTime, "catalogue", lambda m: catalogue.update(json.loads(m.msg)), latche)
node.create_subscription(StringTime, "animation_state", lambda m: etats.append(json.loads(m.msg)), latche)
node.create_subscription(StringTime, "neck", lambda m: cous.append(m.msg), 10)
node.create_subscription(Twist, "cmd_vel", lambda m: cmd.append((time.monotonic(), m.linear.x, m.angular.z)), 10)
pub_edit = node.create_publisher(StringTime, "data_edit", 10)
pub_anim = node.create_publisher(StringTime, "animation", 10)
pub_face = node.create_publisher(StringTime, "face", 10)

def tourner(secondes, condition=lambda: False):
    fin = time.monotonic() + secondes
    while time.monotonic() < fin:
        rclpy.spin_once(node, timeout_sec=0.05)
        if condition():
            return True
    return condition()

tourner(10, lambda: pub_edit.get_subscription_count() > 0 and catalogue)
compteur = [0]
def envoyer(kind, mode, name, content, brut=None, **autres):
    compteur[0] += 1
    id_ = "{}-{}".format(PREFIXE, compteur[0])
    if brut is None:
        d = {"id": id_, "kind": kind, "mode": mode, "name": name, "content": content}
        d.update(autres)
        brut = json.dumps(d)
    else:
        id_ = None
    vus = len(resultats)
    pub_edit.publish(StringTime(msg=brut, time=0, anim=False))
    tourner(DELAI, lambda: any(r.get("id") == id_ for r in resultats[vus:]))
    return next((r for r in resultats[vus:] if r.get("id") == id_), {"code": "pas de réponse", "detail": []})

def sha_fichier(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def au_catalogue(famille, nom):
    return tourner(DELAI, lambda: nom in catalogue.get(famille, []))

def octets_attendus(contenu):
    return (json.dumps(contenu, indent=4, ensure_ascii=False) + "\n").encode()

def png(largeur, hauteur):
    def bloc(t, c):
        return struct.pack(">I", len(c)) + t + c + struct.pack(">I", zlib.crc32(t + c) & 0xFFFFFFFF)
    lignes = b"".join(b"\x00" + b"\xff\x40\x00" * largeur for _ in range(hauteur))
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(lignes)) + bloc(b"IEND", b""))

RETOUCHE = SEQ + "/tmp-l1d/l1d-retouche.json"
try:
    # 1. création
    seq = {"keys": "l1d-retouche", "duration": 3000, "neck": [[0.1, 0.5]]}
    r = envoyer("sequence", "create", "tmp-l1d/l1d-retouche", seq)
    verdict(r["code"] == "ok" and os.path.isfile(RETOUCHE) and au_catalogue("animations", "l1d-retouche"),
            "1. création -> {} ; fichier présent ; au catalogue en <= {} s".format(r["code"], DELAI))

    # 2. retouche du cou à 0.37
    seq2 = {"keys": "l1d-retouche", "duration": 3000, "neck": [[0.1, 0.37]]}
    r = envoyer("sequence", "replace", "tmp-l1d/l1d-retouche", seq2, base_sha256=sha_fichier(RETOUCHE))
    lignes = [l for l in open(JOURNAL, encoding="utf-8") if PREFIXE in l] if os.path.exists(JOURNAL) else []
    sauvegarde = r.get("sauvegarde") or ""
    verdict(r["code"] == "ok" and open(RETOUCHE, "rb").read() == octets_attendus(seq2)
            and os.path.isfile(os.path.join(DATA, sauvegarde)) and len(lignes) == 2,
            "2. retouche -> {} ; octets exacts ; sauvegarde {} ; {} ligne(s) au journal".format(
                r["code"], sauvegarde or "absente", len(lignes)))

    # 3. jouée : le rechargement est prouvé par la valeur 0.37
    etats.clear(); cous.clear()
    pub_anim.publish(StringTime(msg=json.dumps("l1d-retouche"), time=0, anim=False))
    def vu_037():
        return any(isinstance(v, (int, float)) and abs(v - 0.37) < 1e-9 for v in map(json.loads, cous))
    tourner(5, lambda: "l1d-retouche" in etats and vu_037())
    vu_037 = vu_037()
    verdict("l1d-retouche" in etats and vu_037,
            "3. jouée : animation_state {} ; neck reçu {}".format(etats, cous[:4]))
    tourner(3, lambda: etats and etats[-1] == "")

    # 4. référence inconnue
    avant = open(RETOUCHE, "rb").read()
    r = envoyer("sequence", "replace", "tmp-l1d/l1d-retouche",
                {**seq2, "faces": [[0, "l1d-expression-inconnue"]]}, base_sha256=sha_fichier(RETOUCHE))
    verdict(r["code"] == "contrat" and open(RETOUCHE, "rb").read() == avant,
            "4. faces inconnue -> {} {} ; fichier inchangé".format(r["code"], r["detail"]))

    # 5. noms qui sortent de la cible
    avant_json = lister(JSON)
    codes = [envoyer("sequence", "create", n, seq)["code"] for n in ("../x/y", "tmp-l1d/../../x")]
    nouveaux = lister(JSON) - avant_json - {p for p in lister(JSON) if p.startswith(BACKUP)}
    verdict(codes == ["nom_invalide", "nom_invalide"] and not nouveaux,
            "5. ../x/y, tmp-l1d/../../x -> {} ; rien de créé{}".format(codes, " : " + str(nouveaux) if nouveaux else ""))

    # 6. roues hors bornes : messages GRAVÉS (theatre_contrats/test/test_donnees.py)
    attendus = [
        (([[0.1, [0.95, 0.95]], [0.5, [0, 0]]]), "wheels[0] : consigne roues [0.95, 0.95] au-delà de 0.89 (VITESSE_ROUES_MAX)"),
        (([[0.1, [0.2, 0.2]]]), "wheels : la dernière image doit valoir [0, 0] (arrêt final), reçu [0.1, [0.2, 0.2]]"),
        (([[0.1, {"speed": 100}], [0.5, [0, 0]]]),
         "wheels[0] : consigne roues [gauche, droite] (deux nombres) attendue, reçu {'speed': 100}"),
    ]
    rendus = [envoyer("sequence", "create", "tmp-l1d/l1d-roues-ko",
                      {"keys": "l1d-roues-ko", "duration": 4000, "wheels": w}) for w, _ in attendus]
    verdict(all(r["code"] == "contrat" and r["detail"] == [m] for r, (_, m) in zip(rendus, attendus))
            and not os.path.exists(SEQ + "/tmp-l1d/l1d-roues-ko.json"),
            "6. roues hors bornes -> {} ; aucun fichier".format([(r["code"], r["detail"]) for r in rendus]))

    # 7. roues dans les bornes, jouées : on MESURE la tenue de cmd_vel
    roues = {"keys": "l1d-roues", "duration": 4000, "wheels": [[0.1, [0.2, 0.2]], [0.5, [0, 0]]]}
    r = envoyer("sequence", "create", "tmp-l1d/l1d-roues", roues)
    cree = r["code"] == "ok" and "roues_a_valider_en_sim" in r.get("avertissements", [])
    tourner(1)
    cmd.clear(); etats.clear()
    t0 = time.monotonic()
    pub_anim.publish(StringTime(msg=json.dumps("l1d-roues"), time=0, anim=False))
    tourner(4.0 + 2.0)
    non_nuls = [t for t, x, z in cmd if abs(x) > 1e-6 or abs(z) > 1e-6]
    fin_jeu = t0 + 4.0
    apres = [(x, z) for t, x, z in cmd if t >= fin_jeu + 1.0]
    if non_nuls:
        premier = non_nuls[0]
        nul_suivant = next((t for t, x, z in cmd if t > premier and abs(x) < 1e-6 and abs(z) < 1e-6), None)
        tenue = (nul_suivant or non_nuls[-1]) - premier
        print("IMPULSION_ROUES non_nul_pendant={:.2f}s premier_non_nul_a={:.2f}s messages_non_nuls={} "
              "(attendu si tenue : (0.5-0.1)x4 s = 1.60 s)".format(tenue, premier - t0, len(non_nuls)), flush=True)
    else:
        print("IMPULSION_ROUES aucun cmd_vel non nul reçu", flush=True)
    verdict(cree and bool(non_nuls) and apres and all(abs(x) < 1e-6 and abs(z) < 1e-6 for x, z in apres[-5:]),
            "7. roues bornées -> {} {} ; cmd_vel non nul vu : {} ; nul 1 s après la fin : {}".format(
                r["code"], r.get("avertissements"), bool(non_nuls), bool(apres) and apres[-1] == (0.0, 0.0)))

    # 8. conflit
    r = envoyer("sequence", "replace", "tmp-l1d/l1d-retouche", seq2, base_sha256="0" * 64)
    verdict(r["code"] == "conflit", "8. base_sha256 faux -> {}".format(r["code"]))

    # 9. trop gros : 131 073 octets exactement, refusé avant tout décodage (id inconnu)
    base = json.dumps({"id": PREFIXE + "-gros", "kind": "sequence", "mode": "create",
                       "name": "tmp-l1d/l1d-gros", "content": seq})
    brut = base + " " * (131_073 - len(base.encode()))
    r = envoyer(None, None, None, None, brut=brut)
    verdict(len(brut.encode()) == 131_073 and r["code"] == "trop_gros",
            "9. {} octets -> {}".format(len(brut.encode()), r["code"]))

    # 10. images
    bouche = png(24, 16)
    r1 = envoyer("image", "create", "mouth/l1d-bouche", base64.b64encode(bouche).decode())
    r2 = envoyer("image", "create", "eye/l1d-oeil", base64.b64encode(bouche).decode())
    r3 = envoyer("image", "create", "mouth/l1d-texte", base64.b64encode(b"ceci n'est pas un PNG").decode())
    verdict(r1["code"] == "ok" and os.path.isfile(DATA + "/medias/visuals/mouth/l1d-bouche.png")
            and r2["code"] == "contrat" and r3["code"] == "contrat",
            "10. bouche 24x16 -> {} ; même PNG en œil -> {} {} ; non-PNG -> {} {}".format(
                r1["code"], r2["code"], r2["detail"], r3["code"], r3["detail"]))

    # 11. expression qui montre l'image, affichée par face_sim (rechargement du visage)
    expression = {"duration": 2000, "loop": False, "mouths": [[1, "l1d-bouche.png"]],
                  "left_eyes": [[1, "oeil-droit.png"]], "right_eyes": [[1, "oeil-droit.png"]]}
    r = envoyer("expression", "create", "l1d visage", expression)
    present = au_catalogue("faces", "l1d visage")
    pub_face.publish(StringTime(msg=json.dumps("l1d visage"), time=0, anim=False))
    tourner(2)
    with open(LOG, "rb") as f:  # offset en OCTETS (le journal porte des accents)
        f.seek(offset_log)
        journal_robot = f.read().decode("utf-8", errors="replace")
    lignes_face = [l for l in journal_robot.splitlines() if "face_sim_node" in l]
    affiche = any("update face sequences : l1d visage" in l for l in lignes_face)
    image_relue = any("image mouth/l1d-bouche rechargée" in l for l in lignes_face)
    erreurs_face = [l for l in lignes_face if "ERROR" in l or "CRITICAL" in l]
    verdict(r["code"] == "ok" and present and affiche and image_relue and not erreurs_face,
            "11. expression -> {} ; au catalogue : {} ; image relue : {} ; affichée par face_sim : {} ; "
            "erreurs : {}".format(r["code"], present, image_relue, affiche, erreurs_face[:2]))

    # 12. lumière chaînant deux briques existantes, puis une brique inconnue
    r1 = envoyer("lumiere", "create", "l1d lumiere", {"duration": 3000, "loop": False,
                                                       "sequences": {"love": 0.5, "oulala": 1}})
    present = au_catalogue("robot_lights", "l1d lumiere")
    r2 = envoyer("lumiere", "create", "l1d lumiere ko", {"duration": 3000, "loop": False,
                                                          "sequences": {"l1d-brique-inconnue": 1}})
    verdict(r1["code"] == "ok" and present and r2["code"] == "contrat",
            "12. lumière -> {} ; au catalogue : {} ; brique inconnue -> {} {}".format(
                r1["code"], present, r2["code"], r2["detail"]))
finally:
    # ---- remise en état : fichiers restaurés, créations effacées, journal rendu
    for p, (octets, mode) in sauves.items():
        with open(p, "wb") as f:
            f.write(octets)
        os.chmod(p, mode & 0o7777)
    if not tmp_images_existait:
        shutil.rmtree(TMP_IMAGES, ignore_errors=True)
    for p in RESTAURES:
        if p not in sauves and os.path.exists(p):
            os.remove(p)
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    for zone in ("mouth", "eye"):
        for f in os.listdir(DATA + "/medias/visuals/" + zone):
            if f.startswith("l1d-"):
                os.remove(DATA + "/medias/visuals/" + zone + "/" + f)
    if journal_avant is None:
        if os.path.exists(JOURNAL):
            os.remove(JOURNAL)
    else:
        with open(JOURNAL, "wb") as f:
            f.write(journal_avant)
    if os.path.isdir(BACKUP):
        for p in sorted(lister(BACKUP) - backup_avant, key=len, reverse=True):
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        if not backup_existait:
            shutil.rmtree(BACKUP, ignore_errors=True)
    node.destroy_node()
    rclpy.shutdown()

propre = empreinte_arbre() == empreinte_avant
print("  remise en état de json/ et medias/visuals/ : {}".format("identique" if propre else "DIFFÉRENTE (résidu)"))
print("=== validate-data-edit ({}) : {} OK, {} KO {} ===".format(NS, ok, ko, time.strftime("%H:%M:%S")))
sys.exit(0 if ko == 0 and propre else 1)
PY
