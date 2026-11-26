"""Lecture et choix du plan d'épreuves (F1, 25/11) : plan.toml → liste d'Epreuve, dans l'ordre.

Un plan invalide est refusé AVANT toute sim, avec un message qui dit quelle entrée et quel champ.
"""
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

PLAN = Path(__file__).with_name("plan.toml")
INTERNES = ("image", "demarrage", "rtf", "parle")   # codées dans le programme (spec §3)
SOCLE = ("image", "demarrage", "rtf")               # ajoutées seules à toute sélection
CLES_SIM = {"monde", "regie", "jeu", "tete", "neuve"}


class PlanInvalide(ValueError):
    pass


@dataclass(frozen=True)
class Epreuve:
    id: str
    type: str = "script"
    script: str | None = None
    attendu: int | None = None
    motif: str | None = None
    delai_s: int | None = None
    sim: dict | None = None
    corps_sur_arme: bool = False
    facultative: bool = False
    chemins: tuple = ()
    bloque: tuple = ()
    # Clé de partage de la sim : deux épreuves de même clé partagent la même sim (`neuve` à part).
    cle_sim: tuple = field(init=False, default=())

    def __post_init__(self):
        s = self.sim or {}
        object.__setattr__(self, "cle_sim", (s.get("monde", "chantiers"), s.get("regie"),
                                             bool(s.get("jeu")), bool(s.get("tete"))))


def _verifier(n: int, e: dict) -> Epreuve:
    def refus(msg):
        raise PlanInvalide("plan, épreuve n°{} ({}) : {}".format(n, e.get("id", "sans id"), msg))
    connus = {"id", "type", "script", "attendu", "motif", "delai_s", "sim", "corps_sur_arme",
              "facultative", "chemins", "bloque"}
    if set(e) - connus:
        refus("champ(s) inconnu(s) : " + ", ".join(sorted(set(e) - connus)))
    if not isinstance(e.get("id"), str) or not e["id"]:
        refus("« id » manquant")
    type_ = e.get("type", "script")
    if type_ not in ("script", "interne"):
        refus("type « {} » (script | interne)".format(type_))
    if type_ == "interne" and e["id"] not in INTERNES:
        refus("épreuve interne inconnue (internes : {})".format(", ".join(INTERNES)))
    obligatoires = ("script", "attendu", "motif", "delai_s", "sim") if type_ == "script" else ()
    for cle in obligatoires:
        if cle not in e:
            refus("champ obligatoire « {} » manquant".format(cle))
    for cle in ("attendu", "delai_s"):
        if cle in e and (not isinstance(e[cle], int) or e[cle] <= 0):
            refus("« {} » doit être un entier positif".format(cle))
    if "sim" in e and (not isinstance(e["sim"], dict) or set(e["sim"]) - CLES_SIM):
        refus("« sim » : clés permises {}".format(", ".join(sorted(CLES_SIM))))
    return Epreuve(**{**e, "chemins": tuple(e.get("chemins", ())), "bloque": tuple(e.get("bloque", ()))})


def lire(chemin=None) -> list:
    """Le plan, vérifié : ordre du fichier, ids uniques, `bloque` ne cite que des ids connus."""
    chemin = chemin or PLAN
    try:
        brut = tomllib.loads(Path(chemin).read_text(encoding="utf-8")).get("epreuve")
    except (OSError, tomllib.TOMLDecodeError) as erreur:
        raise PlanInvalide("plan illisible ({}) : {}".format(chemin, erreur)) from None
    if not isinstance(brut, list) or not brut:
        raise PlanInvalide("plan sans aucune [[epreuve]] ({})".format(chemin))
    plan = [_verifier(n, e) for n, e in enumerate(brut, 1)]
    ids = [e.id for e in plan]
    if len(set(ids)) != len(ids):
        raise PlanInvalide("plan : id en double ({})".format(", ".join(sorted({i for i in ids if ids.count(i) > 1}))))
    for e in plan:
        if set(e.bloque) - set(ids) - {"*"}:
            raise PlanInvalide("plan, {} : « bloque » cite un id inconnu".format(e.id))
    return plan


def choisir(plan: list, ids=None) -> list:
    """Sous-ensemble du plan, dans l'ordre du plan ; le socle (image, demarrage, rtf) est ajouté
    seul. Le démarrage et la sonde prennent la sim de la première épreuve choisie : une sélection
    « a1 » ne démarre qu'une sim, pas deux. Un id inconnu est refusé avec la liste des ids valides."""
    if ids is None:
        return list(plan)
    valides = [e.id for e in plan]
    inconnus = [i for i in ids if i not in valides]
    if inconnus:
        raise PlanInvalide("épreuve(s) inconnue(s) : {} ; ids valides : {}".format(
            ", ".join(inconnus), ", ".join(valides)))
    garde = [e for e in plan if e.id in ids or e.id in SOCLE]
    premiere = next((e for e in garde if e.id not in SOCLE), None)
    if premiere is None or premiere.sim is None:
        return garde
    sim = {k: v for k, v in premiere.sim.items() if k != "neuve"}
    return [replace(e, sim=sim) if e.id in ("demarrage", "rtf") else e for e in garde]
