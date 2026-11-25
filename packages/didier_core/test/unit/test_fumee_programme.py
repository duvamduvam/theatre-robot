"""Lot F1 (25/11) — le programme de fumée `machines/sim/fumee/` (spec docs/spec-F1-programme-fumee.md §7).

Tout est hôte : aucun docker, aucune sim. Les appels système passent par UN objet (banc.Systeme),
remplacé ici par `Faux`, qui joue docker, git et le thermomètre et note chaque commande. Valeurs
attendues GRAVÉES, jamais recalculées par le code testé.
"""
import json
import re
import sys
from pathlib import Path

import pytest

SIM = Path(__file__).resolve().parents[4] / "machines" / "sim"
sys.path.insert(0, str(SIM))

from fumee import __main__ as programme  # noqa: E402
from fumee import epreuve, images, plan as plans, rapport  # noqa: E402
from fumee.banc import CONTENEURS  # noqa: E402

fp = rapport.fp
PLAN = plans.lire()
IDS = ["image", "demarrage", "rtf", "namespace", "catalogue", "parle", "edition", "machines", "audio",
       "corps_sur", "chantiers", "a1", "objets", "conversation"]


# --- Le faux système ---------------------------------------------------------------------

class FauxProc:
    pid = 0

    def __init__(self, rc, tours=2):
        self.rc, self.tours = rc, tours

    def poll(self):
        if self.tours <= 0:
            return self.rc
        self.tours -= 1
        return None


class Faux:
    """Docker, git et sensors joués : la sim « démarre » à `compose up`, les scripts rendent leur
    ligne finale gravée, `chaud(faux)` donne la température (None = pas de thermomètre)."""

    def __init__(self, en_ligne=True, chaud=None, comptes=None, etiquettes=None, sha="c0ffee" + "0" * 34):
        self.env = {"FUMEE_COEURS": "", "FUMEE_PROFIL": "0", "HOME": "/nulle-part"}
        self.cmds, self.lances, self.tues, self.t = [], [], [], 0.0
        self.en_ligne, self.chaud, self.sim_up, self.en_cours = en_ligne, chaud, False, None
        self.comptes = comptes or {}        # script -> liste de (texte, rc), une par lancement
        self.etiquettes = etiquettes or {}  # image -> étiquette didier.empreinte
        self.sha = sha

    def sortie(self, cmd, entree=None, cwd=None, env=None, delai=None):
        self.cmds.append(list(cmd))
        j = " ".join(cmd)
        if cmd[:2] == ["docker", "compose"]:
            if " up " in j + " ":
                self.sim_up = True
            if " down" in j:
                self.sim_up = False
            return 0, ""
        if cmd[:2] == ["docker", "ps"]:
            return 0, "\n".join(CONTENEURS) if self.sim_up else ""
        if "printenv ROS_DOMAIN_ID" in j:
            return 0, "43\n"
        if cmd[:2] == ["docker", "logs"]:
            return 0, "Summary: 5 packages finished [1min]\n"
        if cmd[:3] == ["docker", "image", "inspect"]:
            lue = self.etiquettes.get(cmd[-1])
            return (0, lue + "\n") if lue else (1, "No such image")
        if "python3 - rtf" in j:
            return 0, "RTF=0.950 messages=400\n"
        if "python3 - parle" in j:
            return 0, 'ETATS=["", "parle", ""]\nPARLE 3 OK\n'
        if "corps_sur_bringup.py" in j:
            return 0, "CORPS_SUR_BRINGUP arme rearmements=0 ok etat={}\n"
        if cmd[:1] == ["git"] and "rev-parse" in cmd:
            return 0, ("main" if "--abbrev-ref" in cmd else self.sha) + "\n"
        return 0, ""

    def lancer(self, cmd, journal):
        script = cmd[-1].rsplit("/", 1)[1]
        self.lances.append(script)
        texte, rc = (self.comptes.get(script) or [(None, 0)]).pop(0) if self.comptes.get(script) else (None, 0)
        if texte is None:   # par défaut : la ligne finale VERTE, à la valeur du plan
            ep = next(e for e in PLAN if e.script == script)
            texte = "{} : {} OK, 0 KO\n".format(ep.motif, ep.attendu)
        Path(journal).write_text(texte, encoding="utf-8")
        self.en_cours = script
        return FauxProc(rc)

    def tuer(self, proc):
        self.tues.append(self.en_cours)
        self.en_cours = None

    def temperature(self):
        return self.chaud(self) if self.chaud else None

    def joignable(self, hote):
        return self.en_ligne

    def dormir(self, secondes):
        self.t += secondes

    def horloge(self):
        return self.t

    def ups(self):
        return [c for c in self.cmds if c[:2] == ["docker", "compose"] and "up" in c]

    def builds(self):
        return [c for c in self.cmds if c[:2] == ["docker", "compose"] and "build" in c]


@pytest.fixture
def secrets(tmp_path, monkeypatch):
    """Les deux fichiers de la tête, factices (présence seule testée)."""
    a, o = tmp_path / "secrets.env", tmp_path / "vision-conf-secret"
    a.write_text("ANTHROPIC_API_KEY=factice-pour-le-test\n")
    o.write_text("openrouter_key=x\n")
    monkeypatch.setattr(epreuve, "SECRET_ANTHROPIC", a)
    monkeypatch.setattr(epreuve, "SECRET_OPENROUTER", o)


def contexte(tmp_path, sy, hors_ligne=False):
    arbre = tmp_path / "arbre"
    (arbre / "machines" / "sim").mkdir(parents=True, exist_ok=True)
    (arbre / "machines" / "sim" / "docker-compose.yml").write_text("services: {}\n")
    for d in ("tmp", "jdir", "etat"):
        (tmp_path / d).mkdir(exist_ok=True)
    return epreuve.Contexte(sy, arbre, SIM, tmp_path / "tmp", tmp_path / "jdir", "2026-11-25-2200",
                            tmp_path / "etat", hors_ligne=hors_ligne)


def statuts(resultats):
    return {r["id"]: r["statut"] for r in resultats}


def ligne(ep_id, ok, ko=0):
    ep = next(e for e in PLAN if e.id == ep_id)
    return "{} : {} OK, {} KO\n".format(ep.motif, ok, ko)


# --- 1. Lecture du plan ------------------------------------------------------------------

def test_plan_dans_l_ordre_de_fumee_sh_et_de_la_page():
    assert [e.id for e in PLAN] == IDS
    assert [i for i, _ in fp.EPREUVES] == IDS          # la page range les épreuves dans le même ordre
    assert [e.id for e in PLAN if e.type == "interne"] == ["image", "demarrage", "rtf", "parle"]
    assert [e.id for e in PLAN if "*" in e.bloque] == ["image", "demarrage", "rtf", "corps_sur"]
    assert [e.id for e in PLAN if e.corps_sur_arme] == ["edition", "chantiers", "a1", "objets", "conversation"]
    assert [e.id for e in PLAN if e.facultative] == ["conversation"]


@pytest.mark.parametrize("texte, message", [
    ('[[epreuve]]\nid = "x"\nscript = "a.sh"\nmotif = "A"\ndelai_s = 9\nsim = {}\n',
     "plan, épreuve n°1 (x) : champ obligatoire « attendu » manquant"),
    ('[[epreuve]]\nid = "x"\ntype = "interne"\n', "plan, épreuve n°1 (x) : épreuve interne inconnue "
     "(internes : image, demarrage, rtf, parle)"),
    ('[[epreuve]]\nid = "image"\ntype = "interne"\ncouleur = 1\n', "plan, épreuve n°1 (image) : champ(s) inconnu(s) : couleur"),
    ('[[epreuve]]\nid = "image"\ntype = "interne"\n[[epreuve]]\nid = "image"\ntype = "interne"\n',
     "plan : id en double (image)"),
    ('[[epreuve]]\nid = "image"\ntype = "interne"\nbloque = ["zz"]\n', "plan, image : « bloque » cite un id inconnu"),
    ('[[epreuve]]\nid = "x"\nscript = "a.sh"\nattendu = 0\nmotif = "A"\ndelai_s = 9\nsim = {}\n',
     "plan, épreuve n°1 (x) : « attendu » doit être un entier positif"),
    ("rien = 1\n", "plan sans aucune [[epreuve]]"),
])
def test_plan_invalide_refuse_avec_un_message_clair(tmp_path, texte, message):
    f = tmp_path / "plan.toml"
    f.write_text(texte)
    with pytest.raises(plans.PlanInvalide) as erreur:
        plans.lire(f)
    assert str(erreur.value).startswith(message)


def test_plan_toml_illisible_refuse(tmp_path):
    f = tmp_path / "plan.toml"
    f.write_text("[[epreuve]\n")
    with pytest.raises(plans.PlanInvalide, match="^plan illisible"):
        plans.lire(f)


def test_choisir_ajoute_le_socle_seul_et_partage_la_sim_de_la_premiere():
    choisis = plans.choisir(PLAN, ["objets", "a1"])
    assert [e.id for e in choisis] == ["image", "demarrage", "rtf", "a1", "objets"]   # ordre du plan
    assert choisis[1].sim == {"monde": "chantiers", "regie": "jeu-a1", "jeu": True}
    assert choisis[2].cle_sim == ("chantiers", "jeu-a1", True, False)
    assert [e.id for e in plans.choisir(PLAN, None)] == IDS


def test_choisir_refuse_un_id_inconnu_avec_la_liste_des_valides():
    with pytest.raises(plans.PlanInvalide) as erreur:
        plans.choisir(PLAN, ["a1", "a2"])
    assert str(erreur.value) == ("épreuve(s) inconnue(s) : a2 ; ids valides : image, demarrage, rtf, namespace, "
                                 "catalogue, parle, edition, machines, audio, corps_sur, chantiers, a1, objets, conversation")


# --- 2. Mêmes valeurs que fumee.sh tant que les deux existent --------------------------------

def test_valeurs_attendues_du_plan_egales_a_celles_de_fumee_sh():
    texte = (SIM / "fumee.sh").read_text(encoding="utf-8")
    sh = {m[0].lower(): int(m[1]) for m in re.findall(r"^ATTENDU_([A-Z0-9_]+)=([0-9]+)", texte, re.M)}
    du_plan = {e.id: e.attendu for e in PLAN if e.attendu is not None}
    assert du_plan == {"namespace": 5, "catalogue": 4, "parle": 3, "edition": 13, "machines": 5, "audio": 10,
                       "corps_sur": 25, "chantiers": 21, "a1": 14, "objets": 13, "conversation": 19}
    assert du_plan == sh
    # Script, motif et délai de chaque lancer_validation de fumee.sh.
    appels = re.findall(r"lancer_validation (\w+) (\S+) \"\$ATTENDU_\w+\" '([^']+)' ([0-9]+)", texte)
    assert len(appels) == 10
    for ident, script, motif, delai in appels:
        ep = next(e for e in PLAN if e.id == ident)
        assert (ep.script, ep.motif, ep.delai_s) == (script, motif, int(delai))


def test_chemins_images_egaux_a_ceux_de_fumee_sh():
    texte = (SIM / "fumee.sh").read_text(encoding="utf-8")
    bloc = re.search(r"^CHEMINS_IMAGES=\(([^)]*)\)", texte, re.M).group(1)
    assert sorted(images.CHEMINS_IMAGES) == sorted(bloc.split())
    assert images.CHEMINS_IMAGES == (
        "machines/sim", "machines/robot/docker", "machines/robot/packages-docker.txt",
        "machines/robot/requirements.txt", "machines/vision/docker", "machines/vision/packages-docker.txt",
        "machines/vision/requirements.txt", "legacy/dadou_control_ros/conf")


# --- 3. Verdict d'une épreuve -------------------------------------------------------------

A1 = next(e for e in PLAN if e.id == "a1")


@pytest.mark.parametrize("texte, rc, gardien, statut, ok, ko, detail", [
    ("=== A1 : 14 OK, 0 KO\n", 0, None, "vert", 14, 0, None),
    ("=== A1 : 13 OK, 1 KO\n", 1, None, "rouge", 13, 1, None),
    ("=== A1 : 15 OK, 0 KO\n", 0, None, "rouge", 15, 0, None),
    ("=== A1 : 14 OK, 0 KO\n", 2, None, "rouge", 14, 0, "compteur conforme mais code de retour 2"),
    ("trace\n", 124, None, "rouge", 0, 0, "aucun compteur lu en fin de script (code 124) : précondition, "
                                           "délai dépassé ou crash — voir le journal"),
    ("MESURE INVALIDE : capture_topics mort\n", 3, None, "invalide", 0, 0,
     "invalide : enregistreur des captures mort (MESURE INVALIDE, code 3) — défaut du banc, pas de Didier"),
    ("=== A1 : 3 OK, 0 KO\n", -15, "chaleur : paquet CPU à 86 °C pendant l'épreuve", "invalide", 0, 0,
     "invalide : chaleur : paquet CPU à 86 °C pendant l'épreuve"),
])
def test_verdict_d_une_epreuve(texte, rc, gardien, statut, ok, ko, detail):
    r = epreuve.verdict_script(texte, rc, A1, gardien)
    assert (r["statut"], r["ok"], r["ko"], r.get("detail")) == (statut, ok, ko, detail)
    assert r["journal"] == "a1.log" and r["attendu"] == 14


def test_image_absente_hors_ligne_invalide_sans_aucun_build(tmp_path):
    sy = Faux(en_ligne=False)
    r = images.phase(contexte(tmp_path, sy, hors_ligne=True))
    assert (r["statut"], r["detail"]) == ("invalide", "invalide : hors ligne, image(s) à reconstruire : "
                                                      "monde, robot, vision, telecommande")
    assert sy.builds() == []


# --- 4. Verdict d'une fumée -----------------------------------------------------------------

def _fumee(**autres):
    return [{"id": i, "statut": autres.get(i, "vert")} for i in IDS]


@pytest.mark.parametrize("epreuves, attendu", [
    (_fumee(), ("vert", None)),
    (_fumee(a1="rouge"), ("rouge", "a1")),
    (_fumee(a1="invalide"), ("invalide", None)),
    (_fumee(chantiers="invalide", objets="rouge"), ("rouge", "objets")),     # un rouge après une invalide l'emporte
    (_fumee(rtf="invalide", namespace="non_lance", conversation="non_lance"), ("invalide", None)),
    (_fumee()[:5], ("rouge", None)),                                        # interrompue : jamais verte
])
def test_verdict_d_une_fumee(epreuves, attendu):
    assert fp.verdict_global(epreuves) == attendu      # la page et « due ? »
    if len(epreuves) == len(IDS):                      # le programme, sur les épreuves jouées
        assert rapport.verdict(epreuves) == attendu


def test_une_selection_n_est_pas_une_fumee_interrompue():
    jouees = [{"id": i, "statut": "vert"} for i in ("image", "demarrage", "rtf", "a1")]
    assert rapport.verdict(jouees) == ("vert", None)
    assert fp.verdict_global(jouees) == ("rouge", None)   # d'où le verdict du programme


def test_facultative_non_lancee_laisse_la_fumee_verte():
    ep = _fumee()[:-1] + [{"id": "conversation", "statut": "non_lance", "facultative": True}]
    assert fp.verdict_global(ep) == ("vert", None)


def test_une_invalide_n_est_ni_derniere_verte_ni_un_rouge_pour_due():
    invalide = {"id": "i", "sha": "aaa", "sha_complet": "a" * 40, "verdict": "invalide",
                "fin": "2026-11-25T22:00:00+01:00", "essai": False}
    assert fp.dernier_vert([invalide]) is None
    # Aucun appel git pour une invalide : le dépôt peut ne pas exister.
    assert fp.rouges_sur_code("/nulle-part", [invalide], None, "a" * 40) == 0


def test_page_d_une_fumee_invalide_pastille_orange():
    res = {"id": "2026-11-25-2200", "debut": "2026-11-25T22:00:00+01:00", "verdict": "invalide",
           "epreuves": _fumee(a1="invalide")}
    page = fp.rendre_page(res)
    assert '<div class="bandeau b-invalide"><strong><span class="verdict invalide">invalide</span></strong> INVALIDE :' in page
    assert ".orange, .invalide { background:var(--orange); }" in page
    assert ".bandeau.b-invalide { border-left-color:var(--orange); }" in page


# --- 5. Rejeu --------------------------------------------------------------------------------

def _chaud_pendant(script, fois):
    """86 °C pendant les `fois` premiers lancements de `script`, 60 °C sinon."""
    return lambda sy: 86.0 if sy.en_cours == script and sy.lances.count(script) <= fois else 60.0


def test_invalide_par_la_chaleur_rejouee_seule_puis_verte(tmp_path):
    sy = Faux(chaud=_chaud_pendant("validate-jeu-a1.sh", 2))
    f = contexte(tmp_path, sy)
    r = epreuve.derouler(f, plans.choisir(PLAN, ["a1", "objets"]))
    assert statuts(r) == {"image": "vert", "demarrage": "vert", "rtf": "vert", "a1": "vert", "objets": "vert"}
    assert sy.lances == ["validate-jeu-a1.sh"] * 3 + ["validate-objets.sh"]   # a1 seule, rejouée deux fois
    assert sy.tues == ["validate-jeu-a1.sh"] * 2
    assert r[3]["detail"] == "vert — après 2 rejeu(x)"
    assert [n for n in f.notes if "rejouée seule" in n] == [
        "a1 invalide (invalide : chaleur : paquet CPU à 86 °C pendant l'épreuve) : rejouée seule (1/2)",
        "a1 invalide (invalide : chaleur : paquet CPU à 86 °C pendant l'épreuve) : rejouée seule (2/2)"]
    assert len(sy.ups()) == 4   # sim du démarrage (partagée par a1), puis une sim neuve par rejeu, puis objets


def test_deux_rejeux_au_plus_puis_invalide(tmp_path):
    sy = Faux(chaud=_chaud_pendant("validate-jeu-a1.sh", 99))
    r = epreuve.derouler(contexte(tmp_path, sy), plans.choisir(PLAN, ["a1"]))
    assert sy.lances == ["validate-jeu-a1.sh"] * 3
    assert r[-1]["statut"] == "invalide"
    assert r[-1]["detail"] == "invalide : chaleur : paquet CPU à 86 °C pendant l'épreuve — après 2 rejeu(x)"


def test_un_rouge_banc_sain_n_est_jamais_rejoue(tmp_path):
    sy = Faux(chaud=lambda sy: 60.0, comptes={"validate-jeu-a1.sh": [(ligne("a1", 13, 1), 1)]})
    r = epreuve.derouler(contexte(tmp_path, sy), plans.choisir(PLAN, ["a1"]))
    assert sy.lances == ["validate-jeu-a1.sh"]
    assert (r[-1]["statut"], r[-1]["ok"], r[-1]["ko"]) == ("rouge", 13, 1)


def test_88_degres_arrete_toute_la_fumee(tmp_path):
    sy = Faux(chaud=lambda sy: 88.5 if sy.en_cours == "validate-jeu-a1.sh" else 60.0)
    f = contexte(tmp_path, sy)
    r = epreuve.derouler(f, plans.choisir(PLAN, ["a1", "objets"]))
    assert statuts(r)["a1"] == "invalide" and statuts(r)["objets"] == "non_lance"
    assert "validate-objets.sh" not in sy.lances
    assert "chaleur : paquet CPU ≥ 88 °C, fumée arrêtée (jamais au-delà de 90 °C)" in f.notes


def test_temps_reel_trop_bas_deux_fois_invalide_et_bloque(tmp_path):
    sy = Faux()
    reponse = sy.sortie
    sy.sortie = lambda cmd, **k: (0, "RTF=0.700 messages=300\n") if "python3 - rtf" in " ".join(cmd) else reponse(cmd, **k)
    f = contexte(tmp_path, sy)
    r = epreuve.derouler(f, plans.choisir(PLAN, ["namespace"]))
    assert statuts(r) == {"image": "vert", "demarrage": "vert", "rtf": "invalide", "namespace": "non_lance"}
    assert r[2]["detail"] == "invalide : temps réel 0.700 < 0.8 deux fois, à 2 min d'écart (PC trop occupé)"
    assert sy.lances == []
    assert fp.verdict_global(r) == ("invalide", None)


# --- 6. Bloquants ------------------------------------------------------------------------------

def test_rouge_de_corps_sur_bloque_les_suivantes(tmp_path, secrets):
    sy = Faux(comptes={"validate-corps-sur.sh": [(ligne("corps_sur", 24, 1), 1)]})
    r = epreuve.derouler(contexte(tmp_path, sy), PLAN)
    s = statuts(r)
    assert s["corps_sur"] == "rouge"
    assert [s[i] for i in ("chantiers", "a1", "objets", "conversation")] == ["non_lance"] * 4
    assert r[-1]["detail"] == "non lancée : « corps_sur » n'est pas verte"
    assert sy.lances[-1] == "validate-corps-sur.sh"


def test_rouge_de_a1_n_empeche_pas_objets(tmp_path, secrets):
    sy = Faux(comptes={"validate-jeu-a1.sh": [(ligne("a1", 12, 2), 1)]})
    r = epreuve.derouler(contexte(tmp_path, sy), PLAN)
    s = statuts(r)
    assert (s["a1"], s["objets"], s["conversation"]) == ("rouge", "vert", "vert")
    assert sy.lances[-2:] == ["validate-objets.sh", "validate-conversation.sh"]
    assert fp.verdict_global(r) == ("rouge", "a1")


# --- 7. Regroupement des sims ---------------------------------------------------------------

def test_le_plan_actuel_donne_six_demarrages_de_sim(tmp_path, secrets):
    sy = Faux()
    f = contexte(tmp_path, sy)
    r = epreuve.derouler(f, PLAN)
    assert set(statuts(r).values()) == {"vert"}
    assert len(sy.ups()) == 6 and f.sim.demarrages == 6
    # Seule la dernière (conversation) porte la surcouche de la tête.
    assert ["docker-compose.tete.yml" in c for c in sy.ups()] == [False] * 5 + [True]
    assert sy.lances == ["validate-namespace.sh", "validate-catalogue.sh", "validate-data-edit.sh",
                         "validate-machines.sh", "validate-audio.sh", "validate-corps-sur.sh",
                         "validate-rehearsal-chantiers.sh", "validate-jeu-a1.sh", "validate-objets.sh",
                         "validate-conversation.sh"]
    regies = [c[-1] for c in sy.cmds if "rehearsal.launch.py" in " ".join(c)]
    assert [re.search(r"scenario:=\S+( jeu:=true)?", x).group(0) for x in regies] == [
        "scenario:=chantiers", "scenario:=jeu-a1 jeu:=true", "scenario:=jeu-a1 jeu:=true", "scenario:=jeu-a1 jeu:=true"]


# --- 8. Empreinte d'image -----------------------------------------------------------------------

def _arbre(tmp_path):
    a = tmp_path / "arbre"
    (a / "machines/sim/monde").mkdir(parents=True)
    (a / "machines/sim/docker-compose.yml").write_text("services: {}\n")
    (a / "machines/sim/monde/Dockerfile").write_text("FROM ros:jazzy\n")
    return a


def test_empreinte_stable_et_gravee(tmp_path):
    a = _arbre(tmp_path)
    assert images.empreinte(a, ("machines/sim",)) == \
        "8447a24c02f1bf041677b623d2327edb1913dbebbd5532e8356c41583ab6b6a7"
    (a / "machines/sim/__pycache__").mkdir()
    (a / "machines/sim/__pycache__/x.pyc").write_bytes(b"\0")
    (a / "packages").mkdir()
    (a / "packages/hors-liste.txt").write_text("rien\n")
    assert images.empreinte(a, ("machines/sim",)) == \
        "8447a24c02f1bf041677b623d2327edb1913dbebbd5532e8356c41583ab6b6a7"


def test_empreinte_change_si_un_fichier_change(tmp_path):
    a = _arbre(tmp_path)
    avant = images.empreinte(a, ("machines/sim",))
    (a / "machines/sim/monde/Dockerfile").write_text("FROM ros:jazzy-ros-base\n")
    assert images.empreinte(a, ("machines/sim",)) != avant
    (a / "machines/sim/monde/Dockerfile").write_text("FROM ros:jazzy\n")
    assert images.empreinte(a, ("machines/sim",)) == avant


def test_image_a_jour_reutilisee_sinon_seule_reconstruite_avec_etiquette(tmp_path):
    sy = Faux()
    f = contexte(tmp_path, sy)
    voulues = {s: images.empreinte(f.arbre, images.COMMUN + c) for s, c in images.PAR_IMAGE.items()}
    sy.etiquettes = {"didier-sim/{}:local".format(s): e for s, e in voulues.items() if s != "robot"}
    r = images.phase(f)
    assert (r["statut"], r["detail"]) == ("vert", "reconstruite(s) : robot")
    assert sy.builds()[0][-2:] == ["build", "robot"]
    assert '  robot:\n    build:\n      labels:\n        didier.empreinte: "' in (f.tmp / "docker-compose.empreinte.yml").read_text()
    sy.etiquettes["didier-sim/robot:local"] = voulues["robot"]
    assert images.phase(f)["detail"] == "les 4 images portent l'empreinte de cette révision : réutilisées"
    assert len(sy.builds()) == 1


# --- 9. Hors ligne -------------------------------------------------------------------------------

def test_hors_ligne_aucun_build_et_conversation_non_lancee(tmp_path, secrets):
    sy = Faux(en_ligne=False)
    f = contexte(tmp_path, sy, hors_ligne=True)
    sy.etiquettes = {"didier-sim/{}:local".format(s): images.empreinte(f.arbre, images.COMMUN + c)
                     for s, c in images.PAR_IMAGE.items()}
    r = epreuve.derouler(f, PLAN)
    assert sy.builds() == []
    assert r[-1] == {"id": "conversation", "statut": "non_lance", "facultative": True,
                     "detail": "non lancée (hors ligne)", "duree_s": 0}
    assert "validate-conversation.sh" not in sy.lances
    assert fp.verdict_global(r) == ("vert", None)
    assert len(sy.ups()) == 5


# --- --reprendre (ajout du 25/11, demandé par David) --------------------------------------------

PETIT_PLAN = "".join('[[epreuve]]\nid = "{}"\ntype = "interne"\n{}\n'.format(i, "" if i == "image" else
                     'sim = { monde = "chantiers" }\n') for i in ("image", "demarrage", "rtf")) + "".join(
    '[[epreuve]]\nid = "{}"\nscript = "{}"\nattendu = {}\nmotif = "{}"\ndelai_s = 60\nsim = {{ monde = "chantiers" }}\n'
    .format(e.id, e.script, e.attendu, e.motif) for e in PLAN if e.id in ("namespace", "catalogue", "edition", "machines", "audio"))


@pytest.fixture
def banc(tmp_path, monkeypatch):
    """main() de bout en bout sur des chemins à nous ; plan réduit à 5 épreuves script."""
    (tmp_path / "plan.toml").write_text(PETIT_PLAN)
    monkeypatch.setattr(plans, "PLAN", tmp_path / "plan.toml")
    (tmp_path / "arbre").mkdir()
    (tmp_path / "arbre" / ".git").write_text("gitdir: ailleurs\n")
    (tmp_path / "xauth").write_text("")
    sy = Faux()
    sy.env.update(FUMEE_DEPOT=str(tmp_path / "depot"), FUMEE_SORTIE=str(tmp_path / "pages"),
                  FUMEE_ETAT=str(tmp_path / "etat"), FUMEE_BRUT=str(tmp_path / "brut"),
                  FUMEE_ARBRE=str(tmp_path / "arbre"), FUMEE_SIM_OCCUPEE=str(tmp_path / "sim-occupee"),
                  DIDIER_SIM_JOURNAUX=str(tmp_path / "sim"), FUMEE_COMMIT="0", XAUTHORITY=str(tmp_path / "xauth"))
    return sy, tmp_path


def _ancienne(tmp_path, sha):
    d = tmp_path / "brut" / "2026-11-25-0100"
    d.mkdir(parents=True)
    ep = [{"id": i, "statut": "vert", "detail": "gardée"} for i in ("image", "demarrage", "rtf")] + [
        {"id": "namespace", "statut": "vert", "ok": 5, "attendu": 5, "ko": 0, "detail": "gardée"},
        {"id": "catalogue", "statut": "rouge", "ok": 3, "attendu": 4, "ko": 1},
        {"id": "edition", "statut": "vert", "ok": 13, "attendu": 13, "ko": 0, "detail": "gardée"},
        {"id": "machines", "statut": "invalide", "detail": "invalide : chaleur"},
        {"id": "audio", "statut": "vert", "ok": 10, "attendu": 10, "ko": 0, "detail": "gardée"}]
    (d / "resultat.json").write_text(json.dumps({"id": "2026-11-25-0100", "sha_complet": sha,
                                                 "fin": "2026-11-25T02:00:00+01:00", "epreuves": ep}))


def test_reprendre_garde_les_vertes_et_ne_rejoue_que_le_reste(banc):
    sy, tmp_path = banc
    _ancienne(tmp_path, sy.sha)
    assert programme.main(["--reprendre"], sy=sy) == 0
    assert sy.lances == ["validate-catalogue.sh", "validate-machines.sh"]
    nouveaux = [p for p in (tmp_path / "brut").glob("*/resultat.json") if p.parent.name != "2026-11-25-0100"]
    assert len(nouveaux) == 1
    res = json.loads(nouveaux[0].read_text())
    assert [e["id"] for e in res["epreuves"]] == ["image", "demarrage", "rtf", "namespace", "catalogue",
                                                  "edition", "machines", "audio"]
    assert [e.get("detail") == "gardée" for e in res["epreuves"]] == [False, False, False, True, False, True, False, True]
    assert res["verdict"] == "vert" and res["reprise_de"] == "2026-11-25-0100"
    assert res["essai"] is False                         # la fusion couvre tout le plan
    assert "reprise de la fumée 2026-11-25-0100 : 3 épreuves gardées" in res["notes"]


def test_reprendre_une_autre_revision_est_refuse(banc, capsys):
    sy, tmp_path = banc
    _ancienne(tmp_path, "f" * 40)
    assert programme.main(["--reprendre"], sy=sy) == 2
    assert "rien à reprendre pour ce sha (c0ffee0)" in capsys.readouterr().err
    assert sy.lances == [] and sy.ups() == []


def test_epreuve_inconnue_refusee_avant_toute_commande(banc, capsys):
    sy, _ = banc
    assert programme.main(["--epreuves", "namespace,zz"], sy=sy) == 2
    assert capsys.readouterr().err.strip() == ("fumée : épreuve(s) inconnue(s) : zz ; ids valides : image, "
                                               "demarrage, rtf, namespace, catalogue, edition, machines, audio")
    assert sy.cmds == []


def test_fumee_complete_de_bout_en_bout_ecrit_la_page_et_rend_le_verrou(banc):
    sy, tmp_path = banc
    assert programme.main(["--epreuves", "edition"], sy=sy) == 0
    assert sy.lances == ["validate-data-edit.sh"]
    ligne_h = json.loads((tmp_path / "pages" / "historique.jsonl").read_text().splitlines()[-1])
    assert list(ligne_h) == list(fp.CHAMPS_HISTORIQUE)
    assert ligne_h["epreuves"]["edition"] == "vert 13/13" and ligne_h["verdict"] == "vert"
    assert ligne_h["essai"] is True                      # partielle : jamais la « dernière verte »
    assert fp.dernier_vert(fp.lire_resultats(tmp_path / "pages")) is None
    assert not (tmp_path / "sim-occupee").exists()      # notre « fumee HH:MM », retiré à la fin
    assert sy.sim_up is False                            # sim arrêtée
