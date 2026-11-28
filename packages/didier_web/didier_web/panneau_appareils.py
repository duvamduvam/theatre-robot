"""Tuile « Appareils » de la page scène (lot L3a, 28/11) — logique 100 % PURE : le jugement.

Spec : docs/spec-L3-gabarit-sono.md, décisions 18 et 19. Une ligne par appareil du registre
(theatre_contrats.appareils.REGISTRE), rendue d'après l'enveloppe d'état SEULE : aucun code propre
à la sono ici ni dans la page. Le pont appelle `lignes(snapshot)` sur ses derniers topics (le
même instantané que le message `state`, âge recalculé) et joint le résultat au `state` ; la page
affiche, elle ne juge rien — sauf l'avance d'un audio, calculée par elle d'après `debut_ms`.

Règles (gravées par packages/didier_core/test/unit/test_panneau_appareils.py) :
1. présence : « vue » si un état lisible de moins de FRAIS_S (5 s) ; « muette » au-delà ;
   « jamais vue » si aucun état reçu ;
2. pilote : badge « simulé » ou « matériel » ;
3. version : sha court (7 caractères, « -dirty » gardé) ; « version différente du robot » si
   le sha diffère de `deploy_sha` (catalogue_node du robot), aucun des deux n'étant `dev` ;
4. organe audio : « silence » au repos, sinon le chemin et la durée ; organe relais : allumé ou
   éteint + nom ; santé ≠ ok : l'organe barré, « absent » ou « erreur » ;
5. refus : « refusé : <code> — <detail> » ;
6. chaque organe porte le topic d'ordre de son type (registre) : la page s'en sert pour Jouer,
   Stop et l'impulsion, sans connaître les noms de topics.

Interprétation écrite (L3a, la spec ne la tranche pas, sens le plus lisible) : un état REÇU
mais illisible (decoder_etat -> None) est montré « état illisible », pastille grise, sans organe
— jamais pris pour un état valide, jamais confondu avec « jamais vue ».

Aucun import ROS ni aiohttp (même règle que web_protocol.py).
"""

from __future__ import annotations

from typing import Any

from theatre_contrats import appareils

Json = dict[str, Any]

FRAIS_S = 5.0
DEPLOY_SHA_TOPIC = "deploy_sha"
SHA_COURT = 7

VUE, MUETTE, JAMAIS_VUE, ILLISIBLE = "vue", "muette", "jamais_vue", "illisible"
TEXTES_PRESENCE = {VUE: "", MUETTE: "muette", JAMAIS_VUE: "jamais vue", ILLISIBLE: "état illisible"}
TEXTES_PILOTE = {"sim": "simulé", "materiel": "matériel"}
TEXTE_VERSION_DIFFERENTE = "version différente du robot"


def sha_court(sha: str) -> str:
    """« 7caeecbc12…-dirty » -> « 7caeecb-dirty » ; « dev » reste « dev »."""
    sale = sha.endswith("-dirty")
    base = sha[:-len("-dirty")] if sale else sha
    return base[:SHA_COURT] + ("-dirty" if sale else "")


def _version(sha: str, deploy_sha: Any) -> Json:
    differente = (isinstance(deploy_sha, str) and deploy_sha != appareils.SHA_DEV
                  and sha != appareils.SHA_DEV and sha != deploy_sha)
    return {"sha": sha_court(sha), "differente": differente,
            "texte": TEXTE_VERSION_DIFFERENTE if differente else ""}


def _organe(o: Json, ordres: Json) -> Json:
    """Un organe de l'enveloppe, prêt à afficher."""
    sante = o["sante"]
    if o["type"] == appareils.AUDIO:
        actif = o["valeur"] != ""
        texte = o["valeur"] if actif else "silence"
    else:
        actif = o["valeur"] is True
        texte = o["nom"]
    return {"nom": o["nom"], "type": o["type"], "actif": actif, "texte": texte,
            "valeur": o["valeur"],
            "debut_ms": o.get("debut_ms"), "duree_ms": o.get("duree_ms"),
            "barre": sante != "ok", "sante_texte": "" if sante == "ok" else sante,
            "topic_ordre": ordres.get(o["type"])}


def ligne(appareil: str, info: Json | None, deploy_sha: Any = None) -> Json:
    """La ligne d'UN appareil ; `info` = {"msg", "age_s"} du pont, ou None si jamais reçu."""
    ordres = appareils.REGISTRE[appareil]["ordres"]
    base = {"appareil": appareil, "pilote": None, "pilote_texte": "", "version": None,
            "organes": [], "refus_texte": None}
    if info is None:
        return dict(base, presence=JAMAIS_VUE, presence_texte=TEXTES_PRESENCE[JAMAIS_VUE])
    etat = appareils.decoder_etat(info.get("msg"))
    if etat is None:
        return dict(base, presence=ILLISIBLE, presence_texte=TEXTES_PRESENCE[ILLISIBLE])
    age = info.get("age_s")
    presence = VUE if isinstance(age, (int, float)) and age < FRAIS_S else MUETTE
    refus = etat["refus"]
    return dict(base, presence=presence, presence_texte=TEXTES_PRESENCE[presence],
                pilote=etat["pilote"], pilote_texte=TEXTES_PILOTE[etat["pilote"]],
                version=_version(etat["sha"], deploy_sha),
                organes=[_organe(o, ordres) for o in etat["organes"]],
                refus_texte=None if refus is None else f"refusé : {refus['code']} — {refus['detail']}")


def lignes(topics: Json) -> list[Json]:
    """Une ligne par appareil du registre, dans son ordre, d'après l'instantané du pont
    ({topic: {"msg", "age_s"}})."""
    sha_robot = (topics.get(DEPLOY_SHA_TOPIC) or {}).get("msg")
    return [ligne(nom, topics.get(a["etat"]), sha_robot) for nom, a in appareils.REGISTRE.items()]
