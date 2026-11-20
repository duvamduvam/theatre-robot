"""Texte RACCORD avec l'action (lot du 18/11) — contrôles DÉTERMINISTES du texte de Didier.

Séance du 18/11, 21:35 : David « il y a une lettre sur le banc, tu pourrais regarder » -> la bouche
demande « aller voir banc » -> refusé (le banc est à 20 m) -> Didier répond « Je vois bien une
enveloppe posée dessus » MALGRÉ la consigne « ne prétends JAMAIS l'avoir fait » -> le metteur en
scène enchaîne « cherche la lettre », « lit l'enveloppe » -> et le corps continue sa route. Une
consigne de prompt ne suffit pas : Haiku (réflexion coupée) l'a ignorée. Ce module porte les deux
contrôles que le CODE applique, sans LLM :

1. `pretention(texte)` : après un geste REFUSÉ, la réplique de Didier prétend-elle avoir vu, trouvé
   ou fait la chose (ou l'annonce-t-elle encore) ? -> l'extrait fautif, ou None. La conversation
   (ConversationEngine._controlled_reply) rejette alors la réplique AVANT qu'elle soit dite, la
   régénère au plus CONTROLE_ESSAIS_MAX fois avec CORRECTION, puis se rabat sur REPLI_REFUS.
2. `geste_impossible(direction)` : la direction du metteur en scène demande-t-elle à Didier un geste
   qu'AUCUN maillon ne déclenche (chercher, aller quelque part, lire, prendre, ouvrir…) ? -> le mot
   fautif, ou None. La réflexion (reflection.parse_reflection) jette alors la direction : un tour
   spontané ne bouge jamais Didier (B1), et le sélecteur de jeu ne lit dans le tableau de situation
   que ses mots-clés (approche, regarde, salue, bonjour, danse, bouge — reglages.yaml), qui
   restent permis.

POURQUOI des motifs fermés plutôt qu'un juge LLM : un second appel coûte une seconde de plus à
chaque réplique et peut lui-même se tromper ; ici le sens SÛR est connu. Un faux positif (« je
vois ce que tu veux dire » après un refus) ne coûte qu'une régénération, bornée ; un faux négatif
laisse passer une phrase que la consigne du prompt interdit déjà. Les motifs sont lus sur un texte
APLATI (minuscules, sans accents, apostrophes droites, espaces simples) : « Je l’aperçois » s'y lit
« je l'apercois ». Textes et motifs GRAVÉS dans test/unit/test_raccord.py. Python PUR, stdlib.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Essais de génération d'une réplique contrôlée (le premier compris) : au-delà, REPLI_REFUS. Deux :
# chaque essai est un appel LLM complet (~1 s au premier mot, mais ici rien n'est dit avant la fin
# du contrôle) — un troisième doublerait l'attente pour un modèle qui a déjà ignoré deux consignes.
CONTROLE_ESSAIS_MAX = 2

# Ajouté à la direction de l'essai suivant (texte EXACT gravé en test). `{extrait}` : ce que le
# contrôle a reconnu, pour que le modèle sache quoi ne plus dire.
CORRECTION = ("ATTENTION : ta réplique précédente disait « {extrait} » : c'est FAUX, elle n'a pas été "
              "dite. Le geste n'a pas eu lieu : tu n'as rien vu, rien trouvé, rien fait de plus, tu n'as "
              "pas bougé. Refais ta réplique sans prétendre avoir vu, trouvé, lu ni fait quoi que ce soit, "
              "et sans annoncer que tu y vas.")

# Repli SÛR quand aucun essai ne passe (ou que le LLM est en panne) : vrai quel que soit le geste
# refusé (aller voir, tour, pivot, avancée), sans clé de geste. Texte EXACT gravé en test.
REPLI_REFUS = "Non, je n'ai pas pu : je n'ai pas bougé d'ici."


def aplatir(texte) -> str:
    """Minuscules, sans accents, apostrophes typographiques ramenées à « ' », espaces simples.
    Non-chaîne -> "" (le texte vient d'un LLM)."""
    if not isinstance(texte, str):
        return ""
    t = texte.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    return " ".join(t.split())


# --------------------------------------------------------------- 1. prétention après un refus
# Chaque motif décrit UNE façon de prétendre (gravée par un exemple en test). Les négations ne
# s'y prennent pas : « je ne vois pas », « je n'ai pas vu » ne contiennent ni « je vois » ni « j'ai vu ».
MOTIFS_PRETENTION = (
    # Perception au présent : « je vois bien une enveloppe », « je la vois », « je l'aperçois ».
    r"\bje (?:le |la |les |l'|te |vous )?(?:vois|apercois|distingue|remarque|devine)\b",
    # Perception, découverte ou lecture au passé : « j'ai vu », « j'ai trouvé la lettre ».
    r"\bj'(?:ai|avais) (?:bien |deja |enfin )?(?:vu|apercu|repere|trouve|lu|remarque|regarde)\b",
    r"\bje l'ai (?:bien |deja |enfin )?(?:vue?|apercue?|reperee?|trouvee?|lue?)\b",
    # Présence affirmée : « il y a bien une lettre », « y a bien un truc blanc », « il y a même un
    # mot qui dépasse » (banc réel du 19/11), « elle est bien là » — pas « il n'y a même pas ».
    r"(?<!n')\by a (?:bien|effectivement|vraiment|meme)\b(?! pas)",
    r"\b(?:elle|il) est (?:bien )?(?:la|posee|pose)\b",
    # Arrivée : « j'y suis », « me voilà », « nous y voilà », « je suis devant ».
    r"\bj'y suis\b",
    r"\bme (?:voila|voici)\b",
    r"\b(?:nous|on) y (?:voila|sommes|est)\b",
    r"\bje suis (?:bien |enfin )?(?:arrivee?|allee?|devant|a cote|tout pres|juste la)\b",
    # Geste accompli : « j'ai fait le tour », « c'est fait », « j'ai ouvert l'enveloppe ».
    r"\bj'ai (?:bien |enfin )?(?:fait|fini|termine|ouvert|pris|ramasse|attrape)\b",
    r"\bc'est fait\b",
    # Geste en cours : « je cherche », « je lis », « j'ouvre », « je m'approche ».
    r"\bje (?:cherche|fouille|lis|prends|ramasse|decachette|deplie|m'approche|m'avance|arrive)\b",
    r"\bj'ouvre\b",
    # Annonce du geste refusé : « j'y vais », « je vais voir », « allons-y ».
    r"\bj'y (?:vais|cours|file|fonce)\b",
    r"\bje (?:vais|file|fonce|cours) (?:y aller|aller|voir|la-bas|chercher|lire|ouvrir|m'approcher"
    r"|faire le tour)\b",
    r"\ballons[- ]y\b",
)
_PRETENTION_RE = tuple(re.compile(m) for m in MOTIFS_PRETENTION)


def pretention(texte) -> Optional[str]:
    """Réplique (texte DIT, sans le JSON de fin) -> l'extrait qui prétend avoir vu ou fait la chose
    (ou l'annonce), tel qu'aplati ; None si rien. Le premier motif trouvé dans le texte gagne."""
    plat = aplatir(texte)
    trouves = [m for m in (r.search(plat) for r in _PRETENTION_RE) if m is not None]
    if not trouves:
        return None
    return min(trouves, key=lambda m: m.start()).group(0).strip()


# --------------------------------------------------------------- 2. geste du metteur en scène
# Gestes qu'une DIRECTION ne peut pas déclencher : formes verbales (impératif, 3e personne,
# infinitif) des gestes de corps ou de mains que ni le tour spontané (B1 : jamais de mouvement) ni
# le sélecteur de jeu (mots-clés de reglages.yaml) ne savent faire. « ça va » et « comment va » ne
# sont pas « aller » ; « le lit » n'est pas « lire ». Liste FERMÉE, gravée en test.
GESTES_IMPOSSIBLES = (
    r"\bcherch(?:e|es|ent|er|ant)\b",
    r"\bfouill(?:e|es|ent|er)\b",
    r"\bramass(?:e|es|ent|er)\b",
    r"\battrap(?:e|es|ent|er)\b",
    r"\bsaisi(?:s|t|ssent|r)\b",
    r"\bdecachet(?:te|tes|tent|er)\b",
    r"\bdepli(?:e|es|ent|er)\b",
    r"\bouvr(?:e|es|ent|ir)\b",
    r"(?<!le )(?<!un )(?<!son )(?<!du )\bli(?:s|t|re|sent)\b",
    r"\bprend(?:s|re)? (?:la |le |les |l'|une |un |cette |ce )(?:lettre|enveloppe|objet|papier|colis)\b",
    r"(?<!ca )(?<!comment )\bva(?:s)? (?:voir|vers|jusqu|chercher|au |a la |aux |la-bas)",
    r"\b(?:aller|allez|allons|aille|aillent) (?:voir|vers|jusqu|chercher|au |a la |aux |la-bas)",
    r"\brejoin(?:s|t|dre)\b",
    r"\bdeplac(?:e|es|ent|er)\b",
    r"\b(?:avanc|recul|march)(?:e|es|ent|er) (?:vers|jusqu)",
    r"\bf(?:ai(?:s|t|re)|ass(?:e|ent)) le tour\b",
)
_GESTES_RE = tuple(re.compile(m) for m in GESTES_IMPOSSIBLES)


def geste_impossible(direction) -> Optional[str]:
    """Direction du metteur en scène -> le geste impossible qu'elle demande (extrait aplati), ou
    None. Le premier trouvé dans le texte gagne."""
    plat = aplatir(direction)
    trouves = [m for m in (r.search(plat) for r in _GESTES_RE) if m is not None]
    if not trouves:
        return None
    return min(trouves, key=lambda m: m.start()).group(0).strip()
