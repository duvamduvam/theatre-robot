"""Le SÉLECTEUR de jeu — logique PURE (aucun import ROS), testée sans ROS.

Spec : theatre-robot/docs/spec-A1-selecteur-de-jeu.md (§3 l'arbre et le score,
§8 les précisions du 02/11), RÉVISÉE par docs/spec-S1-ordres-propositions.md (lot S1,
25/11 : ordres et propositions, une seule reprise). Le node (jeu_node.py) appelle les `sur_*` à chaque
message, `tick(now)` à ~10 Hz, puis VIDE `sorties` et publie. Horloge
injectée (secondes, monotone) : aucun sleep dans les tests.

Sorties (tuples, dans l'ordre où elles doivent partir) :
  ("chat_move", payload)       -> jeu/chat_move (régisseur), json.dumps(payload) ;
                                  marche = {"cmd", "origine"} (relais.marche), geste =
                                  dict du contrat, `origine` comprise (lot S1)
  ("chat_move_reply", payload) -> rehearsal/chat_move_reply (chat_node) : une
                                  demande de geste de la bouche NON transmise
                                  (« dropped » + code) ou restée sans réponse
                                  du régisseur (« no_reply ») — 15/11
  ("animation", nom)           -> animation (nom de séquence)
  ("look", {"angle_deg", "hold_ms"}) -> look (gaze_follower, « regarder » M2)
  ("intention", dict)          -> jeu/intention (latché)
  ("journal", type, payload)   -> fichier JSONL + jeu/journal ; payload porte
                                  TOUJOURS un `pourquoi` non vide (porte T6)
  ("corps_etat", texte)        -> corps/etat (latché) : l'état du corps encodé par
                                  theatre_contrats.corps_etat (lot S2a, 27/11) ; produit
                                  par rafraichir_corps(now), que le node appelle avant
                                  chaque vidage

RÈGLES GRAVÉES (chiffres : config/reglages.yaml ; tests : test/test_selecteur.py,
test/test_ordres_propositions.py pour le lot S1) :
- ORIGINE (lot S1) : chaque demande de la bouche dit qui la porte (relais.lire) —
  « david » = un ORDRE (mot d'arrêt, geste né d'un tour humain ; la console est
  toujours David), « didier » = une PROPOSITION (le « marche: stop » du LLM) ;
- « stop » (toute origine) : relayé À LA RÉCEPTION, sans score (porte T5 :
  < 200 ms) — un arrêt n'est jamais refusé. D'origine « david » : VERROU de tout
  déplacement jusqu'au « go » de David, et jamais de reprise seule (31/10) ;
  d'origine « didier » : AUCUN verrou, la reprise s'arme ; pendant un geste de
  David, l'ordre est SUSPENDU et ré-émis à la reprise (R4). Le verrou n'a qu'une
  source, David (supprimé : le verrou à deux sources console/bouche de la revue
  A1), à trois GENRES (R3) : « console » (STOP console), levé par le GO console seul ;
  « route » (Route OFF), levé quand la route revient à « on » ; « voix » (mot d'arrêt),
  levé aussi par un go de tour humain. L'ordre suspendu (R4) n'est rejoué que s'il
  vise un objet, a moins de reprise.ordre_suspendu_max_s, passe les contrôles d'un
  ordre neuf, et qu'aucun nouvel ordre de David n'est venu (seconde relecture, 26/11) ;
- « go » : d'origine « david » (console, tour humain) il lève le verrou et part
  tout de suite ; d'origine « didier » il est ignoré et journalisé (seule la
  reprise relance ce que Didier a arrêté) ;
- un ORDRE n'est refusé que pour : verrou de David (« arrete »), superviseur absent
  (« sans_superviseur »), impossible (« pas_ici », « hors_atteinte » ; « inconnu » et
  sécurité : dits par le régisseur). Un geste de la bouche d'origine « david » part
  TOUT DE SUITE, sans score ; un ordre de la console part au tick suivant (R6, 26/11),
  devant toute initiative, sans score ni écart minimal ; engagé, le score ne
  l'interrompt pas. Fatigue et réfractaires ne s'appliquent plus à un ordre : ils bornent les
  initiatives de Didier. Les refus « qui donnent du jeu » (étude assainissement §8.1,
  réponse 2) ne sont PAS ici : ils reviendront avec le régisseur LLM (S4) ;
- deux décisions différentes jamais à moins de changement.min_s (porte T1) ;
- hystérésis : le meilleur doit dépasser le second de marge pendant duree_s ;
- engagement : une action engagée se finit, sauf offre >= seuil_rupture ;
- naissance d'une offre de personne OU d'objet -> ligne de décision (choix OU
  maintien) en <= 1 s (T3) ;
- initiatives spontanées >= 8 s ; arrêts de Didier >= 120 s — tout arrêt de
  route qu'il cause (lubie, approche de lui-même ; PAS une demande de geste de
  la bouche, qui vient d'un humain : décision de David du 15/11) ; un
  ordre de David n'en est jamais un ; une lubie est RÉCLAMÉE (intention) ET
  AMORCÉE (regard ; à défaut de pose/objet, l'intention seule, 3 s) puis son arrêt
  n'est demandé que si la console n'a dit ni ignore ni va_la entre-temps. Lot S2c
  (relecture adverse du 28/11) : cet arrêt EST un pivot du corps vers l'objet
  (`tourner_vers` d'origine « didier », une manœuvre ordinaire : Didier quitte la route,
  pivote, finit à l'arrêt face à l'objet) ; objet non situé dans le tableau, ou pivot
  refusé (« deja_face », « no_pose », …) ou laissé sans réponse par le régisseur au-delà
  de durees_s.deplacement_accuse : repli sur l'arrêt d'avant S2c, un « stop » « didier » ;
- UNE SEULE REPRISE (lot S1 ; remplace les trois minuteries 10 s / 6 s / 90 s) :
  après un arrêt décidé par Didier — lubie, « stop » d'origine « didier », pause
  « regarde ça », fin (réussie ou non) d'un geste de la bouche ou de son propre
  déplacement — il repart seul (« go » d'origine « didier ») après D s de
  SILENCE, D tiré AU MOMENT DE L'ARRÊT dans [reprise.min_s, reprise.max_s] par le
  générateur semé du sélecteur (journalisé « il repartira après … de silence »).
  Toute parole entendue (chat_transcript, rôle david) remet le silence à zéro
  sans retirer le tirage (règle du 02/11). Attend qu'aucun geste ne roule ; celle
  d'une lubie attend aussi la fin de son pivot (route_state « goto » : un « go »
  pendant une manœuvre est sans effet au régisseur, « deja_en_marche », et Didier
  resterait planté à son arrivée).
  Annulée par un stop de David, une Route OFF de David, un « ignore » de la
  console, un « go » de David. Arrêt posé par David : jamais de reprise seule ;
- HORS SÉANCE (rehearsal/state ≠ « en_cours », ou inconnu — R2) : aucune initiative
  de mouvement (ni lubie, ni approche de son initiative), ni reprise d'un arrêt qu'il
  n'a pas posé (la fin d'un geste de David) ;
- « regarde ça » = PAUSE de la bouche (lot « texte raccord », séance du 18/11
  21:35 : « il y a une lettre sur le banc, tu pourrais regarder » finissait en
  « aller voir » d'un banc à 20 m, refusé, et le corps continuait sa route) :
  Didier en marche -> « stop » d'origine « didier » relayé tout de suite, SANS verrou, puis la
  reprise ; déjà arrêté (verrou, reprise armée) ou pas en route : rien ne bouge,
  jamais de « go » qu'il n'aurait pas eu sans elle ;
- fatigue > seuil : aucun déplacement DE SON INITIATIVE ; « ignore » : rien vers la
  cible pendant console.ignore_s (un « va là » de David vers elle lève l'ignore) ;
- RÉPONSE À LA BOUCHE (15/11, séance : « fais le tour de l'éléphant », la
  demande morte en silence au bout de son TTL, Didier affirmait le tour) :
  toute demande de GESTE de la bouche finit par une issue — transmise au
  régisseur (qui répond lui-même au chat), ou NON transmise : ligne `refus`
  + réponse « dropped » au chat avec son code (arrete, sans_superviseur,
  pas_ici, hors_atteinte ; pas_retenu pour une proposition de geste d'origine
  « didier », qu'aucun producteur n'émet en S1) ; transmise mais régisseur muet
  au-delà de durees_s.deplacement_accuse : réponse « no_reply ». Un
  déplacement REFUSÉ ou sans suite n'a pas eu lieu : ses périodes
  réfractaires et sa fatigue sont RENDUES.
- ÉTAT DU CORPS (lot S2a, 27/11, spec-S2 §2) : le sélecteur est le SEUL écrivain de
  corps/etat. Il RASSEMBLE les faits (route, corps sûr, séance et arrêt vocal, verrou,
  reprise et sa cause, dernier geste, tableau des objets) ; la marche, l'unique cause et
  la phrase sont décidées par theatre_contrats.corps_etat (pur, gravé). Republié à chaque
  changement et au plus tard toutes les 2 s ; un changement de marche ou de cause est une
  ligne `corps_etat` du journal (son `pourquoi` = la phrase) ;
- RÉPONSE À TOUTE DEMANDE DE DAVID (lot S2a, spec-S2 §3) : go, stop, pause et gestes de la
  bouche d'origine « david » ont TOUS une réponse sur chat_move_reply — « accepted », ou
  « dropped » + raison (« arrete » avec le genre du verrou, « sans_superviseur », « pas_ici »,
  « hors_atteinte », « corps_sur »). Un stop n'est jamais refusé ni retardé : sa réponse part
  APRÈS lui. Celle d'un geste accepté part AVANT sa transmission au régisseur : elle précède
  toujours le verdict du régisseur (la bouche actuelle prend le `name` de la DERNIÈRE réponse
  acceptée — l'inverse le lui ferait perdre). Corps sûr VERROUILLÉ (ou pas encore armé) : go
  et gestes de David refusés « corps_sur », ni relayés ni transmis ;
- Supprimés au lot S1 : les mots-clés du metteur en scène (sur_situation, et
  l'indication de mission_state) — « fragiles, sans identifiant ni retour »
  (étude improvisation) ; jeu/proposition les remplacera (I3).
SÉCURITÉ : ce module ne produit AUCUN Twist ; ses seuls effets sur les roues
sont des DEMANDES au régisseur (jeu/chat_move), qui arbitre (spec-aller-voir §3).
"""
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from didier_jeu import arbre, phrases
from theatre_contrats import corps_etat
from theatre_contrats import objets as tableau_objets
from didier_jeu.phrases import n as num
from didier_jeu.offres import Offre, Offres
from didier_jeu.pistes import Pistes
from didier_jeu.pulsions import Pulsions
from didier_jeu.relais import (DAVID, DIDIER, GO, PAUSE, STOP, VERROU_CONSOLE, VERROU_ROUTE, VERROU_VOIX, lire,
                               marche, reponse_bouche)
from didier_rehearsal.rehearsal_state import SEANCE_EN_COURS
from didier_jeu.repertoire import COMMANDES_REGISSEUR, commande
from didier_jeu.scores import ARRET_DIDIER, RIEN, Candidat, Contexte, classer

# Commandes de la console (spec §4), gravées avec la page scène.
CONSOLE_CMDS = ("va_la", "joue_avec", "ignore", "reviens", "plus_lent", "stop", "go")
# Gestes de David qu'un stop de Didier suspend puis REJOUE (R4) : ceux qui visent un objet. Les
# gestes RELATIFS (avancer, tourner) ne se rejouent jamais : depuis une autre pose, ils
# mèneraient ailleurs (seconde relecture, 26/11).
GESTES_REJOUABLES = ("aller_voir", "tour_de")
# « reviens » pendant une manœuvre : attente maximale (s) que le régisseur ait confirmé
# l'annulation (route_state quitte « goto ») avant d'envoyer le « go ».
REVIENS_ATTENTE_MAX_S = 5.0
# Angle sous lequel « se tourner vers » une piste est inutile avant d'avancer (°).
ANGLE_MIN_TOURNER_DEG = 5.0
# Tolérance des comparaisons d'échéances : 5,6 − 5,0 vaut 0,5999… en flottant,
# un délai de 0,6 s tomberait un tick trop tard (vu en test).
EPS = 1e-6


@dataclass
class Decision:
    action: str
    cible: Optional[str]
    pourquoi: str


@dataclass
class Engagement:
    candidat: Candidat
    t_debut: float
    fin_prevue: float                 # échéance (s) ; l'action peut finir avant
    origine: str                      # DIDIER (initiative) | DAVID (ordre : console ou geste de la bouche)
    etapes: List[dict] = field(default_factory=list)   # chat_move restants (approcher)
    accuse: bool = False              # route_state « goto » vu pour l'étape en cours
    t_etape: float = 0.0
    anim_vue: bool = False            # animation_state a montré NOTRE séquence
    stop_envoye: bool = False         # lubie : son arrêt est demandé (pivot ou « stop »)
    # Lubie (S2c) : le pivot `tourner_vers` demandé comme arrêt, tant que le régisseur ne l'a
    # pas accepté (None ensuite, ou s'il n'y en a pas) ; refusé ou sans suite -> « stop ».
    pivot: Optional[dict] = None
    t_pivot: float = 0.0
    etape: Optional[dict] = None      # chat_move de l'étape EN COURS (appariement des réponses)
    nom_ordre: Optional[str] = None   # `name` de l'ordre ACCEPTÉ (seule son issue finit l'étape)
    # Instant de l'ordre de David D'ORIGINE (R4, 3e relecture) : l'âge d'un ordre suspendu se
    # compte depuis lui, jamais remis à zéro par une ré-émission ou une nouvelle suspension.
    t_ordre: Optional[float] = None
    # Réfractaires d'avant la décision (catégorie -> t | None) : rendus si le
    # régisseur refuse ou se tait (le déplacement n'a pas eu lieu).
    derniers_avant: Dict[str, Optional[float]] = field(default_factory=dict)


class Selecteur:
    def __init__(self, reglages, pools: Dict[str, list], deplacements: Dict[str, dict],
                 graine: Optional[int] = None):
        self.r = reglages
        # Générateur du sélecteur (lot S1) : il tire la durée de silence de chaque reprise.
        # SEMÉ par le node (graine journalisée au démarrage) : une séance se rejoue à
        # l'identique, et un test grave la durée tirée.
        self.graine = graine
        self.hasard = random.Random(graine)
        self.pools = pools
        self.deplacements = deplacements
        self.offres = Offres()
        self.pistes = Pistes(reglages.get("pistes.perte_s"), reglages.get("pistes.nouvelle_apres_s"),
                             reglages.get("pistes.confiance_min"))
        self.pulsions = Pulsions(reglages)
        self.sorties: List[tuple] = []
        # Tableau des objets (scene/objets, lot O1, 18/11) : le sélecteur le LIT (distance,
        # côté, azimut, atteignable), il n'en calcule rien — plus de pose ni de carte ici.
        # PÉRIMÉ après tableau_objets.PEREMPTION_S sans republication (revue O1, 19/11 : le
        # regard d'une lubie restait sur l'azimut d'un tableau figé) : lu via tableau(now).
        self.tableau_recu = None               # dernier Tableau reçu (peut être périmé)
        self._tableau_t: Optional[float] = None
        self.route_state: Optional[str] = None
        self.animation_state = ""
        self.joues: Dict[str, float] = {}      # séquence -> dernier t joué (rotation)
        self.en_cours: Optional[Engagement] = None
        self.courante = (RIEN, None)           # (action, cible) affichée
        self.pourquoi_courant = "il vient d'arriver : rien ne se passe encore"
        self.t_derniere_decision: Optional[float] = None
        self.derniers: Dict[str, float] = {}   # catégorie réfractaire -> t
        self.derniere_spontanee: Optional[float] = None
        self.leader: Optional[str] = None
        self.leader_depuis = 0.0
        # Verrou d'arrêt de DAVID SEUL (lot S1), à trois GENRES (R3, 25-26/11) : None (pas de
        # verrou) | VERROU_CONSOLE (STOP de la console : levé par un GO console SEUL) |
        # VERROU_ROUTE (Route OFF : levé quand la route revient à « on », ou par un GO console) |
        # VERROU_VOIX (mot d'arrêt : levé par un go de David en tour humain ou un GO console).
        self.verrou: Optional[str] = None
        self._route_vue_off = False                # Route OFF : l'état « off » a-t-il été vu ?
        self._dernier_ordre: Optional[tuple] = None  # (cmd, cible, t) : rebond des ordres console ACCEPTÉS
        # « reviens » a posé un arrêt d'origine « david » (son stop d'annulation) : tant que son go
        # n'est pas parti, il faudra le lever d'un go de David (3e relecture, m2).
        self._arret_reviens = False
        # Séance du régisseur (rehearsal/state, règle R2) : hors séance — ou état inconnu —
        # Didier ne prend AUCUNE initiative de mouvement (lubie, approche, reprise d'un arrêt
        # qu'il n'a pas posé).
        self.en_seance = False
        # LA reprise (lot S1) : {"t", "silence_depuis", "delai", "pourquoi", "cible",
        # "apres_geste", "ordre"} — Didier s'est arrêté de lui-même et repartira seul
        # (_reprise_due) ; `ordre` : le geste de David suspendu par son arrêt (règle R4), ré-émis
        # à la place du « go ».
        self.reprise: Optional[dict] = None
        self.presence_t: Optional[float] = None
        self.ordre: Optional[dict] = None          # {"action", "cible", "cmd"} : ordre de la console, part au tick (R6)
        self.ignores: Dict[str, float] = {}        # cible -> t de fin
        self.joue_avec: Optional[dict] = None      # {"cible", "fin"}
        self.plus_lent_fin: Optional[float] = None
        self.piste_regardee: Optional[str] = None
        self.reaction_due: List[dict] = []         # [{"cible", "kind", "t"}] : offres nées sans réponse
        # État du corps (lot S2a) : faits que seul le sélecteur rassemble. `corps_sur` : dernier
        # corps_sur/etat LISIBLE (None = jamais reçu) ; `seance_connue` : rehearsal/state lu
        # (sinon l'état du corps est INCONNU, jamais deviné) ; `arret_vocal` : son badge.
        self.corps_sur: Optional[corps_etat.CorpsSur] = None
        self.seance_connue = False
        self.arret_vocal = False
        # Le dernier geste (spec-S2 §2) : {"demande", "etat", "raison", "parcouru_m", "t"} — dit
        # pendant corps_etat.GESTE_MEMOIRE_S après son issue.
        self.geste_corps: Optional[dict] = None
        self._corps_cle: Optional[tuple] = None        # clé du dernier corps/etat publié
        self._corps_t: Optional[float] = None          # et son instant
        self._corps_marche_cause: Optional[tuple] = None   # dernière (marche, cause) journalisée
        self._t_prec: Optional[float] = None
        self._now = 0.0
        self._decision_tick: Optional[Decision] = None
        self.arbre = arbre.construire(self)

    # ================================================================ sorties
    def _journal(self, type_: str, pourquoi: str, **payload) -> None:
        payload["pourquoi"] = pourquoi
        self.sorties.append(("journal", type_, payload))

    def intention(self, now: float) -> dict:
        """État courant pour jeu/intention (republié par le node toutes les 0,5 s)."""
        action, cible = self.courante
        fin = self.en_cours.fin_prevue if self.en_cours else None
        out = {"action": action, "cible": cible, "pourquoi": self.pourquoi_courant,
               "t_ms": int(now * 1000), "fin_prevue_ms": int(fin * 1000) if fin else None,
               "reste_ms": int(max(0.0, fin - now) * 1000) if fin else None,
               "verrou": self.verrou_david, "jauges": self.pulsions.jauges()}
        if self.reprise is not None:
            out["proposition"] = "repartir ?"
        return out

    def _publier_intention(self, now: float) -> None:
        self.sorties.append(("intention", self.intention(now)))

    def vider_sorties(self) -> List[tuple]:
        out, self.sorties = self.sorties, []
        return out

    # ================================================================ prédicats de l'arbre
    @property
    def verrou_david(self) -> bool:
        return self.verrou is not None

    def verrouille(self) -> bool:
        return self.verrou_david

    def superviseur_absent(self) -> bool:
        if self.r.get("superviseur.mode") != "exigeant":
            return False
        return self.presence_t is None or self._now - self.presence_t > self.r.get("superviseur.silence_max_s")

    def engagee(self) -> bool:
        return self.en_cours is not None

    # ================================================================ entrées
    def sur_person_box(self, azimut: float, hauteur: float, confiance: float, now: float) -> None:
        nee = self.pistes.update(azimut, hauteur, confiance, now)
        if nee is None:
            return
        self.offres.naitre(Offre("personne", nee, self.r.get("offres.valeur.personne"), now,
                                 self.r.get("offres.ttl_s")))
        self.pulsions.sur_piste_nee()
        self.reaction_due.append({"cible": nee, "kind": "personne", "t": now})
        self._journal("naissance_piste", f"une nouvelle personne apparaît ({nee})",
                      piste=nee, azimut=round(azimut, 2), hauteur=round(hauteur, 2))

    def sur_poi_event(self, payload, now: float) -> None:
        if not isinstance(payload, dict) or payload.get("event") != "enter" or not payload.get("poi"):
            return
        poi = str(payload["poi"])
        self.offres.naitre(Offre("objet", poi, self.r.get("offres.valeur.objet"), now, self.r.get("offres.ttl_s")))
        self.pulsions.sur_poi()
        self.reaction_due.append({"cible": poi, "kind": "objet", "t": now})
        self._journal("offre", f"il passe près de « {poi} » (lubie +{num(self.r.get('pulsions.lubie.par_poi'))})",
                      kind="objet", piste=poi)

    def sur_chat_move_bouche(self, valeur, now: float) -> None:
        """La bouche (rehearsal/chat_move), lue par son ORIGINE (lot S1, relais.lire) :
        stop / go / pause relayés à la réception (relayer_stop, relayer_go, pause_regard) ;
        un geste d'origine « david » est un ORDRE, exécuté tout de suite (_ordre_bouche) ;
        une proposition de geste (« didier ») n'est pas retenue en S1 (aucun producteur :
        la bouche ne décide aucun mouvement, §8 bis) — le chat le sait.
        Lot S2a : toute demande lue « david » a sa réponse (`valeur` telle quelle : la bouche
        apparie par égalité) ; cf. docstring de module, RÉPONSE À TOUTE DEMANDE DE DAVID."""
        demande, origine = lire(valeur)
        if origine == DAVID:
            # Règle de la 3e relecture : TOUTE action de David efface l'ordre suspendu, acceptée
            # ou refusée — donc ici, avant le moindre refus (hors d'atteinte, verrou, superviseur).
            self._oublier_suspendu("David demande autre chose à Didier")
        if demande == STOP:
            self.relayer_stop(origine, "bouche", now)
            if origine == DAVID:
                self._repondre(valeur, "accepted")      # APRÈS le stop : il n'attend jamais
            return
        if demande == PAUSE and origine is None:
            # Une pause contient un arrêt : d'origine inconnue, c'est un stop (lu « david »,
            # comme le stop d'origine inconnue — sens sûr).
            self.relayer_stop(DAVID, "bouche", now)
            self._repondre(valeur, "accepted")
            return
        if demande == GO and origine is None:
            self._journal("refus", f"« go » d'origine inconnue ({valeur!r}) : ignoré", source="bouche")
            return
        if demande == GO:
            if origine == DAVID and self._corps_verrouille():
                self._refus_corps_sur(valeur, "« go »")
                return
            genre = self.relayer_go(origine, "bouche", now)
            if origine == DAVID:
                if genre is None:
                    self._repondre(valeur, "accepted")
                else:
                    self._repondre(valeur, "dropped", "arrete", verrou=genre)
            return
        if demande == PAUSE:
            self.pause_regard(origine, now)
            if origine == DAVID:
                # Toujours tenue : en marche il s'arrête pour regarder, déjà arrêté il regarde.
                self._repondre(valeur, "accepted")
            return
        if not isinstance(demande, dict) or demande.get("cmd") not in COMMANDES_REGISSEUR:
            self._journal("refus", f"demande de mouvement incompréhensible ({valeur!r})", source="bouche")
            return
        if origine != DAVID:
            # La réponse « dropped » va au chat : Didier ne doit jamais affirmer ce geste.
            self.sorties.append(("chat_move_reply", reponse_bouche(demande, "dropped", "pas_retenu")))
            self._journal("refus", f"proposition de geste ({phrases.demande(demande)}, origine {origine!r}) : "
                          "non retenue — la bouche ne décide aucun mouvement", source="bouche",
                          demande=demande, code="pas_retenu", origine=origine)
            return
        if self._corps_verrouille():
            self._refus_corps_sur(demande, phrases.demande(demande), geste=True, now=now)
            return
        if self._hors_atteinte(demande, now):
            return
        self._ordre_bouche(demande, now, repondre=True)

    def _repondre(self, demande, effet: str, code=None, **extra) -> None:
        """Réponse du sélecteur à une demande de la bouche (rehearsal/chat_move_reply)."""
        self.sorties.append(("chat_move_reply", reponse_bouche(demande, effet, code, **extra)))

    def _corps_verrouille(self) -> bool:
        """Le corps sûr est VERROUILLÉ ou pas encore armé : rien ne bougera (lot S2a). Jamais
        reçu : on ne refuse rien (ses règles s'appliquent quand même aux roues)."""
        return self.corps_sur is not None and self.corps_sur.verrouille

    def _refus_corps_sur(self, demande, quoi: str, geste: bool = False, now: float = 0.0) -> None:
        """Go ou geste de David sous le corps sûr verrouillé : ni relayé ni transmis, dit au chat."""
        self._repondre(demande, "dropped", "corps_sur")
        if geste:
            self._noter_geste(demande, corps_etat.GESTE_REFUSE, "corps_sur", 0.0, now)
        self._journal("refus", f"David voulait {quoi}, mais non : son corps est verrouillé par sécurité "
                      f"({self.corps_sur.etat}{' ' + self.corps_sur.cause if self.corps_sur.cause else ''})",
                      source="bouche", demande=demande, code="corps_sur")

    def _ordre_bouche(self, demande: dict, now: float, t_ordre: Optional[float] = None,
                      repondre: bool = False) -> None:
        """Un geste demandé par David à la bouche (tour humain ou continuation de SA tâche) :
        un ORDRE (lot S1, étude assainissement règle 1). Il part TOUT DE SUITE, sans score ni
        hystérésis, et n'est refusé que sous le verrou de David ou sans superviseur (l'objet
        hors d'atteinte est déjà refusé par _hors_atteinte, la sécurité par le régisseur).
        L'action engagée cède (un ordre passe devant) ; un ordre macro de la console en
        attente aussi (le plus récent de David gagne). Fatigue et réfractaire « deplacement »
        sont COMPTÉS (ses propres envies attendront) et rendus si le régisseur refuse.
        `repondre` (lot S2a) : la demande vient de la bouche à l'instant — « accepted » part AVANT
        la transmission (cf. docstring de module) ; une ré-émission R4 n'a personne à qui répondre."""
        code = texte = None
        if self.verrou_david:
            code, texte = "arrete", "il est arrêté jusqu'au go de David"
        elif self.superviseur_absent():
            code, texte = "sans_superviseur", "personne ne surveille (page fermée)"
        if code is not None:
            self._repondre(demande, "dropped", code, **({"verrou": self.verrou} if code == "arrete" else {}))
            self._noter_geste(demande, corps_etat.GESTE_REFUSE, code, 0.0, now)
            self._journal("refus", f"David voulait {phrases.demande(demande)}, mais non : {texte}",
                          source="bouche", demande=demande, code=code)
            return
        if repondre:
            self._repondre(demande, "accepted")
        c = Candidat("bouche", demande.get("objet") or demande.get("cmd"), None, None, {"demande": demande})
        self.ordre = None
        self._oublier_suspendu("David donne un nouvel ordre")
        self._executer_ordre(c, now, f"David : {phrases.demande(demande)} → il y va tout de suite",
                             f"David demande : {phrases.demande(demande)}", t_ordre=t_ordre, source="bouche",
                             demande=demande)

    def _executer_ordre(self, c: Candidat, now: float, pourquoi: str, annulation: str,
                        t_ordre: Optional[float] = None, **journal) -> None:
        """Un ORDRE de David part (geste de la bouche, ordre de la console au tick) : il passe
        devant toute initiative — l'action engagée cède — sans score, sans hystérésis ni écart
        minimal entre décisions (règle R6, fumée du 26/11 : « va_la p1 » mort de vieillesse
        derrière une expression spontanée). Fatigue et réfractaire « deplacement » sont COMPTÉS
        (ses propres envies attendront) et rendus si le régisseur refuse."""
        if self.en_cours is not None:
            self._annuler(now, annulation)
        self.leader = None
        avant = {cat: self.derniers.get(cat) for cat in c.categories}
        self._executer(c, now, DAVID)
        if c.deplacement:
            self.en_cours.t_ordre = now if t_ordre is None else t_ordre
            self.en_cours.derniers_avant = avant      # rendus si le régisseur refuse
            self.pulsions.sur_action(True)
            for cat in c.categories:
                self.derniers[cat] = now
        self.courante = (c.action, c.cible)
        self.pourquoi_courant = pourquoi
        self._journal("ordre", pourquoi, origine=DAVID, action=c.action, cible=c.cible, **journal)
        self._publier_intention(now)

    def _hors_atteinte(self, demande: dict, now: float) -> bool:
        """aller_voir / tour_de de la bouche vers un objet du tableau (désigné par son `id`) qui
        n'est pas `atteignable` : refusé tout de suite, distance et côté dits au chat (séance du
        15/11 21:29). La règle (≤ 10 m, position sûre) est calculée par l'écrivain du tableau,
        à un seul endroit (lot O1) : ici on LIT le drapeau. Objet absent du tableau : la régie
        juge (« unknown »). Remplace le refus « > 10 m » du 15/11 (geste.distance_max_chat_m)."""
        if demande.get("cmd") not in ("aller_voir", "tour_de"):
            return False
        o = self.tableau(now).par_id(demande.get("id"))
        if o is None or o.atteignable:
            return False
        code = "hors_atteinte" if o.ici else "pas_ici"
        self.sorties.append(("chat_move_reply", reponse_bouche(demande, "dropped", code, distance_m=o.distance_m,
                                                               cote=o.cote)))
        self._noter_geste(demande, corps_etat.GESTE_REFUSE, code, 0.0, now)
        ou = tableau_objets.ou_dit(o) or "on ne sait pas où"
        self._journal("refus", f"il voulait {phrases.demande(demande)}, mais non : « {o.nom} » est {ou}, "
                      f"hors d'atteinte", source="bouche", demande=demande, code=code, id=o.id)
        return True

    def sur_console(self, payload, now: float) -> None:
        if not isinstance(payload, dict):
            self._journal("refus", f"ordre de la console illisible ({payload!r})", source="console")
            return
        if payload.get("presence") is True:
            self.presence_t = now
        cmd = payload.get("cmd")
        if cmd is None:
            return
        if cmd not in CONSOLE_CMDS:
            self._journal("refus", f"ordre de la console inconnu ({cmd!r})", source="console")
            return
        cible = payload.get("cible")
        cible = str(cible) if isinstance(cible, (str, int)) and str(cible) else None
        self._oublier_suspendu("David donne un nouvel ordre")   # n'importe lequel (seconde relecture)
        if cmd == STOP:
            self.relayer_stop(DAVID, "console", now)
        elif cmd == GO:
            self.relayer_go(DAVID, "console", now)
        elif cmd == "ignore":
            self._ignorer(cible, now)
        elif cmd == "plus_lent":
            self.plus_lent_fin = now + self.r.get("console.plus_lent_s")
            self._journal("console", f"David : plus lent → il agit {self.r.get('console.plus_lent_facteur'):g} fois "
                          f"moins souvent pendant {self.r.get('console.plus_lent_s'):g} s", cmd=cmd)
        elif cmd == "reviens":
            self.joue_avec = None
            self._ordre({"action": "repartir", "cible": None, "cmd": cmd}, now, "David : reviens → rejoindre la route")
        elif cmd == "joue_avec":
            piste = cible or self._piste_regardee(now)
            if piste is None:
                self._journal("refus", "David : joue avec lui — mais il ne voit personne", source="console", cmd=cmd)
                return
            self.joue_avec = {"cible": piste, "fin": now + self.r.get("console.joue_avec_s")}
            self._journal("console", f"David : joue avec {piste} → il s'occupe d'elle pendant "
                          f"{self.r.get('console.joue_avec_s'):g} s", cmd=cmd, cible=piste)
        elif cmd == "va_la":
            self._va_la(cible, now)

    def sur_tableau(self, tableau, now: float) -> None:
        """scene/objets décodé (theatre_contrats.objets.Tableau), reçu à `now`."""
        if self._tableau_t is None and self.tableau_recu is not None:
            self._journal("tableau", f"tableau des objets revenu ({len(tableau.objets)} objet(s))")
        self.tableau_recu = tableau
        self._tableau_t = now

    def tableau(self, now: float):
        """Le tableau des objets À LIRE à `now` : le dernier reçu s'il a moins de
        tableau_objets.PEREMPTION_S (même valeur que la bouche, la réflexion et la régie), sinon
        le tableau VIDE — aucun objet, aucun azimut : pas de regard ni de « va là » sur une
        donnée figée. Le passage au périmé est journalisé une fois."""
        if self._tableau_t is not None and now - self._tableau_t > tableau_objets.PEREMPTION_S:
            self._tableau_t = None
            self._journal("tableau", f"tableau des objets muet depuis plus de "
                          f"{tableau_objets.PEREMPTION_S:g} s : objets oubliés")
        return self.tableau_recu if self._tableau_t is not None else tableau_objets.VIDE

    def sur_route_state(self, etat, now: float) -> None:
        if etat == "on" and self.route_state != "on":
            # La route repart (Route ON de David, ou relance) : l'ordre suspendu tombe. (Le « off »
            # qui suit l'annulation d'une manœuvre par un stop de Didier n'est PAS une action de
            # David — l'effacer là rendrait R4 inopérant ; la Route OFF de David arrive par sa
            # cause, sur_route_cause.)
            self._oublier_suspendu("la route repart")
        self.route_state = etat
        e = self.en_cours
        if e is not None and etat == "goto":
            e.accuse = True
            e.pivot = None             # le pivot d'une lubie roule : accusé, comme un déplacement
        if self.verrou == VERROU_ROUTE:
            # La route revient à « on » APRÈS avoir été vue « off » (route_driver publie la cause
            # avant l'état : l'ancien « on » latché ne lève rien) : David l'a relancée.
            if etat == "off":
                self._route_vue_off = True
            elif etat == "on" and self._route_vue_off:
                self.verrou = None
                self._journal("verrou", "David a remis la route → verrou de la route levé", genre=VERROU_ROUTE)

    def sur_parole(self, texte, now: float) -> None:
        """Une parole ENTENDUE (chat_transcript, rôle david : ce que Didier a
        compris, de David ou du public). Arrêté par lui-même, Didier attend D s
        de SILENCE : le compteur repart de zéro (David, 02/11), le tirage reste."""
        if self.reprise is None:
            return
        self.reprise["silence_depuis"] = now
        self._journal("parole", f"on lui parle → il attend encore {phrases.s(self.reprise['delai'])} de "
                      "silence avant de repartir", texte=str(texte)[:80])

    def sur_route_cause(self, cause, now: float) -> None:
        """route_state_cause (latché, régisseur) : « cmd » = David a coupé la
        route — verrou « route » (R3, seconde relecture du 26/11 : route_driver publie
        la cause à chaque `off` et RIEN au `on`, un verrou « console » restait donc
        posé après OFF/ON), levé quand la route revient à « on » ; un STOP console
        posé avant garde le sien. Reprise désarmée, lubie en attente annulée (revue
        A1, bloquant 3). « boot » : rien."""
        if cause != "cmd":
            return
        # (L'ordre suspendu tombe avec la reprise, désarmée ci-dessous : Route OFF = action de David.)
        e = self.en_cours
        if e is not None and e.candidat.action == "lubie" and not e.stop_envoye:
            self._annuler(now, "David a coupé la route")
        self._desarmer_reprise("David a coupé la route")
        self.ordre = None
        if self.verrou is None:
            # Jamais au-dessus d'un verrou déjà posé (voix ou console) : il reste le sien
            # (3e relecture, m3).
            self.verrou = VERROU_ROUTE
            self._route_vue_off = self.route_state == "off"
            self._journal("verrou", "David a coupé la route → verrou de la route, levé quand il la remet",
                          genre=VERROU_ROUTE)

    def sur_seance(self, etat, now: float) -> None:
        """rehearsal/state (latché, régisseur) : {"seance": "attente"|"en_cours"|"terminee", …}.
        Seule « en_cours » est une séance ; tout le reste (illisible compris) = hors séance
        (règle R2, sens sûr : pas d'initiative). Lot S2a : `arret_vocal` (badge du régisseur)
        est retenu pour l'état du corps ; illisible -> état du corps INCONNU."""
        en = isinstance(etat, dict) and etat.get("seance") == SEANCE_EN_COURS
        self.seance_connue = isinstance(etat, dict) and isinstance(etat.get("seance"), str)
        self.arret_vocal = isinstance(etat, dict) and etat.get("arret_vocal") is True
        if en != self.en_seance:
            if not en:
                self._oublier_suspendu("la séance est finie")
            self.en_seance = en
            self._journal("seance", "séance lancée : il peut prendre des initiatives" if en else
                          "hors séance : aucune initiative de mouvement (ni lubie, ni approche)", en_seance=en)

    def sur_corps_sur(self, payload, now: float) -> None:
        """corps_sur/etat (latché, nœud corps_sur, publié à chaque changement) : retenu pour
        l'état du corps et le refus « corps_sur » (lot S2a). Illisible : le précédent est gardé."""
        lu = corps_etat.lire_corps_sur(payload)
        if lu is None:
            self._journal("corps_sur", f"état du corps sûr illisible ({str(payload)[:80]!r}) : le précédent est gardé")
            return
        self.corps_sur = lu

    def sur_goto_result(self, payload, now: float) -> None:
        e = self.en_cours
        if e is None or not e.candidat.deplacement or e.candidat.action == "repartir":
            return
        nom = payload.get("name") if isinstance(payload, dict) else None
        if e.nom_ordre is not None and nom != e.nom_ordre:
            # Issue d'un ordre ANTÉRIEUR (séance du 15/11 21:21) : pas la nôtre.
            self._journal("issue_ignoree", f"issue de « {nom} » ignorée : il attend celle de « {e.nom_ordre} »",
                          nom=nom, attendu=e.nom_ordre)
            return
        resultat = payload.get("result") if isinstance(payload, dict) else None
        if resultat == "arrived" and e.etapes:
            self._etape_suivante(e, now)
            return
        # La reprise après le déplacement (le sien ou un geste de la bouche) s'arme dans _finir.
        raison = payload.get("reason") if isinstance(payload, dict) else None
        parcouru = tableau_objets.nombre_fini(payload.get("travelled")) if isinstance(payload, dict) else None
        if resultat == "arrived":
            self._issue_geste(corps_etat.GESTE_ARRIVE, None, parcouru, now)
        else:
            # Corps sûr verrouillé pendant le geste : c'est LUI la raison (spec-S2 §2, exemple 5).
            self._issue_geste(corps_etat.GESTE_ABANDONNE, "corps_sur" if self._corps_verrouille()
                              else (raison or resultat), parcouru, now)
        self._finir(now, "il est arrivé" if resultat == "arrived" else f"il a renoncé ({raison or resultat})")

    def sur_move_reply(self, payload, now: float) -> None:
        """Réponse du RÉGISSEUR à un geste (rehearsal/chat_move_reply, source
        « director » ; nos propres réponses, source « jeu », reviennent aussi
        sur ce topic : ignorées). Appariée à l'étape EN COURS (égalité de la
        demande) : acceptée -> accusée (pas de faux « sans suite ») ; refusée
        -> l'engagement finit tout de suite, réfractaires et fatigue rendus."""
        if not isinstance(payload, dict) or payload.get("source") != "director":
            return
        e = self.en_cours
        if e is not None and e.pivot is not None and payload.get("demande") == e.pivot:
            # Le pivot qui sert d'arrêt à la lubie (S2c) : accepté, il roule ; sinon repli.
            effet = payload.get("effect")
            if effet == "accepted":
                e.pivot = None
            else:
                self._arret_lubie_sans_pivot(e, f"pivot refusé par le régisseur ({effet})", now)
            return
        if e is None or not e.candidat.deplacement or e.etape is None or payload.get("demande") != e.etape:
            return
        effet = payload.get("effect")
        if effet == "accepted":
            e.accuse = True
            nom = payload.get("name")
            e.nom_ordre = nom if isinstance(nom, str) else None
            return
        raison = payload.get("reason")
        self._issue_geste(corps_etat.GESTE_REFUSE, effet if isinstance(effet, str) else None, 0.0, now)
        self._rendre_refractaires(e)
        self._finir(now, f"le régisseur refuse ({effet}{' : ' + raison if raison else ''}) : "
                         "il n'a pas bougé")

    def sur_animation_state(self, nom, now: float) -> None:
        self.animation_state = nom if isinstance(nom, str) else ""
        e = self.en_cours
        if e is None or e.candidat.action not in ("accueil", "spontanee"):
            return
        seq = e.candidat.detail.get("sequence")
        if self.animation_state == seq:
            e.anim_vue = True
        elif e.anim_vue:
            self._finir(now, f"séquence « {seq} » terminée")

    # ================================================================ relais et ordres
    def relayer_stop(self, origine: str, source: str, now: float) -> None:
        """« stop » : relayé TOUT DE SUITE (premier effet, avant tout journal), sans score,
        quelle que soit son origine — un arrêt n'est jamais refusé. Le déplacement engagé et
        l'ordre en attente tombent (sens sûr : rien ne repart derrière un arrêt). Origine
        « david » : verrou jusqu'à SON go, reprise désarmée (jamais de « go » automatique
        après un stop de David, 31/10). Origine « didier » (proposition, §8.1 réponse 1) :
        aucun verrou, la reprise s'arme (sauf sous le verrou de David)."""
        self.sorties.append(("chat_move", marche(STOP, origine)))
        qui = phrases.qui(origine)
        self.ordre = None
        self.leader = None
        e = self.en_cours
        # R4 : un stop de Didier pendant un ORDRE de David engagé (geste de la bouche ou de la
        # console) le SUSPEND ; un second stop de Didier garde l'ordre déjà suspendu.
        garde = self.reprise.get("ordre") if (origine == DIDIER and self.reprise is not None) else None
        suspendu = None
        if (origine == DIDIER and e is not None and e.origine == DAVID and e.candidat.deplacement
                and e.etape is not None):
            if e.etape.get("cmd") in GESTES_REJOUABLES:
                suspendu = {"demande": e.etape, "t": e.t_ordre if e.t_ordre is not None else now}
            else:
                self._journal("ordre_suspendu", f"geste relatif non repris ({phrases.demande(e.etape)}) : il ne "
                              "mènerait plus au même endroit", demande=e.etape)
        if e is not None and (e.candidat.deplacement or e.candidat.action == "lubie"):
            self._annuler(now, f"stop de {qui}")
        if origine == DAVID:
            self._arret_reviens = False        # l'arrêt est désormais le sien
            # Genre (R3) : la console est la plus forte, un mot d'arrêt ne la rabaisse jamais.
            self.verrou = VERROU_CONSOLE if source == "console" else (self.verrou or VERROU_VOIX)
            self._desarmer_reprise("stop de David")
            self._journal("relais_stop", f"David « stop » ({source}) → il s'arrête tout de suite, jusqu'au go "
                          "de David", source=source, origine=origine)
            self.pourquoi_courant = "David « stop » : arrêté jusqu'à son go"
        else:
            reste = " ; David a déjà posé le verrou : il attend son go" if self.verrou_david else ""
            self._journal("relais_stop", f"Didier « stop » → il s'arrête tout de suite, sans verrou{reste}",
                          source=source, origine=origine)
            self._armer_reprise(now, "il s'est arrêté de lui-même", genre=corps_etat.DIDIER_STOP)
            if self.reprise is not None and (suspendu or garde) is not None:
                self.reprise["ordre"] = suspendu or garde
                if suspendu is not None:
                    self._journal("ordre_suspendu", f"ordre de David suspendu ({phrases.demande(suspendu['demande'])}) "
                                  ": il le reprendra après le silence", demande=suspendu["demande"])
            self.pourquoi_courant = f"Didier « stop » : arrêté{reste or ', il repartira seul'}"
        self._publier_intention(now)

    def pause_regard(self, origine: str, now: float) -> None:
        """« Regarde ça » de la bouche (cf. docstring de module) : en marche, « stop » relayé
        tout de suite SANS verrou (ce n'est pas un ordre d'arrêt : il repartira seul), puis la
        reprise s'arme. Le stop part d'origine « didier » (révision R1 du 25/11) : c'est un arrêt
        que Didier relancera lui-même — d'origine « david », son propre « go » ne le lèverait pas
        au régisseur. Ce n'est pas un arrêt « de Didier » au sens du réfractaire de 120 s : la
        demande vient d'un humain, comme un geste de la bouche.
        Dans les trois cas il REGARDE, et c'est le corps qui le fait (fumée du 28/11, D4 rouge :
        le seul `look` venait de la bouche, 3,1 s plus tard, au gré du LLM) : `look` publié ici,
        dans le même tick que le stop (_regard_de_pause). Un `look` de la bouche peut suivre :
        gaze_follower prend le dernier."""
        self._regard_de_pause()
        if self.verrou_david or self.reprise is not None:
            self._journal("pause_regard", "« regarde » : il est déjà arrêté → il regarde sans repartir "
                          "de lui-même", arrete=True)
            return
        if self.route_state not in ("on", "goto"):
            self._journal("pause_regard", f"« regarde » : il n'est pas en route ({self.route_state or 'inconnu'})"
                          " → il regarde sur place", arrete=True)
            return
        self.sorties.append(("chat_move", marche(STOP, DIDIER)))
        self.ordre = None
        e = self.en_cours
        if e is not None and (e.candidat.deplacement or e.candidat.action == "lubie"):
            self._annuler(now, "« regarde » : il s'arrête pour regarder")
        self._journal("pause_regard", "« regarde » → il s'arrête et regarde, il repartira seul", arrete=False,
                      origine=origine)
        self._armer_reprise(now, "regard terminé", genre=corps_etat.DIDIER_PAUSE)
        self.pourquoi_courant = "il s'arrête pour regarder ; il repartira seul"
        self._publier_intention(now)

    def _regard_de_pause(self) -> None:
        """Le regard d'un « regarde ça » : devant (angle 0 — la pause ne nomme aucun objet),
        tenu durees_s.regarder, comme le « regarder » d'une piste (_executer)."""
        hold = self.r.get("durees_s.regarder")
        self.sorties.append(("look", {"angle_deg": 0.0, "hold_ms": int(hold * 1000)}))

    def relayer_go(self, origine: str, source: str, now: float) -> Optional[str]:
        """« go » d'origine « david » (console, tour humain) : lève le verrou, repart tout de
        suite (sans score : sinon il mourait au réfractaire de 10 s), la reprise devient
        caduque. D'origine « didier » : ignoré et journalisé — la bouche n'en émet plus en S1,
        et ce que Didier a arrêté, seule SA reprise le relance.
        -> le genre du verrou qui le REFUSE (lot S2a : la réponse « arrete » le dit), sinon None."""
        if origine != DAVID:
            self._journal("refus", "« go » proposé par Didier : ignoré (seule sa reprise, après le "
                          "silence, le relance)", source=source, origine=origine)
            return None
        if source != "console" and self.verrou == VERROU_CONSOLE:
            # R3 : ce que David a arrêté à la CONSOLE, seul son GO console le relance — un « en
            # route » interprété par la bouche ne suffit pas.
            self._journal("refus", "« go » dit à Didier, mais David a arrêté à la console : seul un GO "
                          "console le relance", source=source, origine=origine)
            return VERROU_CONSOLE
        if source != "console" and self.verrou == VERROU_ROUTE:
            self._journal("refus", "« go » dit à Didier, mais David a coupé la route : elle se relance par la "
                          "route (ou le GO console)", source=source, origine=origine)
            return VERROU_ROUTE
        self.verrou = None
        self.reprise = None
        self._arret_reviens = False
        self.sorties.append(("chat_move", marche(GO, DAVID)))
        self._journal("relais_go", f"David « go » ({source}) → il repart", source=source, origine=origine)
        self.pourquoi_courant = "David « go »"
        self._publier_intention(now)
        return None

    def _ignorer(self, cible: Optional[str], now: float) -> None:
        cible = cible or self.courante[1] or (self.en_cours.candidat.cible if self.en_cours else None)
        if cible is not None:
            self.ignores[cible] = now + self.r.get("console.ignore_s")
            self.offres.tuer_cible(cible)
        e = self.en_cours
        if e is not None and (cible is None or e.candidat.cible == cible):
            self._annuler(now, f"David dit d'ignorer {cible or 'ça'}")
        # Reprise armée : « ignore » (sans cible, ou sur la cible de l'arrêt) la coupe.
        if self.reprise is not None and cible in (None, self.reprise["cible"]):
            self._desarmer_reprise("David dit d'ignorer")
        self._journal("console", f"David : ignorer {cible or 'ça'} pendant {self.r.get('console.ignore_s'):g} s",
                      cmd="ignore", cible=cible)

    def _va_la(self, cible: Optional[str], now: float) -> None:
        # Une lubie en attente de son délai de refus : va_la la refuse.
        if self.en_cours is not None and self.en_cours.candidat.action == "lubie" and not self.en_cours.stop_envoye:
            self._annuler(now, "David l'envoie ailleurs")
        objet = self.tableau(now).resoudre(cible).objet if cible is not None else None
        if objet is not None:
            # Un ordre de DAVID : pas soumis à « atteignable » (il voit ce qu'il désigne) ; la
            # régie garde ses bornes (40 m, route coupée). Cible = le NOM du tableau. Son
            # « ignore » d'avant sur cet objet tombe : son ordre le plus récent gagne (S1).
            self.ignores.pop(objet.nom, None)
            self._ordre({"action": "aller_voir", "cible": objet.nom, "cmd": "va_la"}, now,
                        f"David : va voir « {objet.nom} »")
            return
        piste = self.pistes.courante(now)
        if piste is not None and cible == piste.id:
            # Une PISTE : se tourner vers elle puis avancer <= 1 m (§8.2), si
            # superviseur présent et fatigue sous le seuil — vérifié au choix —
            # et JAMAIS trop près (approche.hauteur_max, David 02/11).
            if not self._assez_loin(piste):
                self._journal("refus", f"David : va vers {cible} — déjà trop près (hauteur "
                              f"{num(piste.hauteur)} ≥ {num(self.r.get('approche.hauteur_max'))})",
                              source="console", cmd="va_la", cible=cible)
                return
            self.ignores.pop(cible, None)
            self._ordre({"action": "approcher", "cible": cible, "cmd": "va_la"}, now, f"David : va vers {cible}")
            return
        self._journal("refus", f"David : va là « {cible} » — inconnu (ni objet connu, ni personne vue)",
                      source="console", cmd="va_la", cible=cible)

    def _ordre(self, ordre: dict, now: float, pourquoi: str) -> None:
        """Ordre macro de la console (va là, reviens) : refusé tout de suite s'il ne peut pas
        partir, sinon il PART AU PROCHAIN TICK (_ordre_console), sans score (règle R6)."""
        cle = (ordre["cmd"], ordre.get("cible"))
        if self._dernier_ordre is not None and self._dernier_ordre[:2] == cle \
                and now - self._dernier_ordre[2] < self.r.get("console.rebond_s") - EPS:
            self._journal("console", f"{pourquoi} — reçu deux fois en moins de "
                          f"{self.r.get('console.rebond_s'):g} s : le doublon est ignoré", cmd=ordre["cmd"],
                          cible=ordre.get("cible"), doublon=True)
            return
        refus = self._refus_deplacement(now, ordre=True)
        if refus:
            self._journal("refus", f"{pourquoi} — impossible : {refus}", source="console", cmd=ordre["cmd"],
                          cible=ordre.get("cible"))
            return
        self._dernier_ordre = cle + (now,)        # seuls les ordres ACCEPTÉS comptent (m4)
        ordre["pourquoi"] = pourquoi
        ordre["t"] = now
        self.ordre = ordre
        self._journal("console", pourquoi, cmd=ordre["cmd"], cible=ordre.get("cible"))

    def _ordre_console(self, now: float) -> None:
        """L'ordre de la console en attente part (R6) : avant l'arbre, devant toute initiative.
        Une piste visée doit encore être vue (et assez loin) : sinon refus dit, jamais deviné."""
        o, self.ordre = self.ordre, None
        if o is None:
            self._lever_arret_reviens(now)
            return
        if o["action"] == "repartir" and self._reviens_annule_la_manoeuvre(o, now):
            return
        refus = self._refus_deplacement(now, ordre=True)
        piste = self.pistes.courante(now)
        if refus is None and o["action"] == "approcher":
            if piste is None or piste.id != o["cible"]:
                refus = f"il ne voit plus {o['cible']}"
            elif not self._assez_loin(piste):
                refus = f"déjà trop près de {o['cible']}"
        if refus:
            self._journal("refus", f"{o['pourquoi']} — impossible : {refus}", source="console", cmd=o["cmd"],
                          cible=o["cible"])
            return
        detail = {"azimut": piste.azimut} if o["action"] == "approcher" else {}
        self._executer_ordre(Candidat(o["action"], o["cible"], None, None, detail), now, o["pourquoi"],
                             o["pourquoi"], t_ordre=o["t"], source="console", cmd=o["cmd"])

    def _reviens_annule_la_manoeuvre(self, o: dict, now: float) -> bool:
        """« reviens » pendant une manœuvre (geste en cours, route « goto ») : la reprendre au
        régisseur exige de l'ANNULER d'abord — son seul moyen est le « stop », qui publie
        « cancel » sur route_goto ; le « go » ne relance la route qu'une fois l'état sorti de
        « goto » (GotoPolicy.rejoin_allowed). Le sélecteur envoie donc « stop » (origine david :
        c'est l'ordre de David, le go de David le lèvera) puis garde l'ordre jusqu'à ce que la
        route quitte « goto » (au plus REVIENS_ATTENTE_MAX_S). -> True si l'ordre attend."""
        if "annule_t" not in o:
            e = self.en_cours
            if e is None or not e.candidat.deplacement or e.candidat.action == "repartir":
                return False
            # Un geste DEMANDÉ s'annule toujours, même si la route n'est pas encore « goto »
            # (le régisseur l'a peut-être accepté sans que l'état ait suivi : 3e relecture, m1).
            self.sorties.append(("chat_move", marche(STOP, DAVID)))
            self._arret_reviens = True
            self._annuler(now, "David : reviens → la manœuvre en cours est annulée")
            o["annule_t"] = now
        if self.route_state == "goto" and now - o["annule_t"] < REVIENS_ATTENTE_MAX_S - EPS:
            self.ordre = o
            return True
        return False

    def _lever_arret_reviens(self, now: float) -> None:
        """Le go du « reviens » n'est pas parti (son ordre est tombé : stop de Didier, regard,
        Route OFF, autre ordre…) : Didier ne doit jamais rester sous un arrêt « david » que
        David n'a pas donné (3e relecture, m2). Une reprise armée s'en charge (elle partira en
        « david », _reprise_due) ; sinon, dès que plus rien ne l'empêche — aucun déplacement en
        cours, ni verrou ni superviseur absent —, un go de David le lève."""
        if not self._arret_reviens or self.reprise is not None or self.verrou_david or self.superviseur_absent():
            return
        if self.en_cours is not None and self.en_cours.candidat.deplacement:
            return
        self._arret_reviens = False
        self.sorties.append(("chat_move", marche(GO, DAVID)))
        self._journal("reprise", "l'arrêt posé pour « reviens » est levé : rien ne le retient plus", origine=DAVID)
        self.pourquoi_courant = "David : reviens"
        self._publier_intention(now)

    def _refus_deplacement(self, now: float, ordre: bool = False) -> Optional[str]:
        """Pourquoi un déplacement ne peut pas partir (None = il peut). `ordre` : un ordre de
        David (lot S1) — la fatigue ne borne que les initiatives de Didier."""
        if self.verrou_david:
            return "il est arrêté jusqu'au go de David"
        if self.superviseur_absent():
            return "personne ne surveille (page fermée)"
        if not ordre and self.pulsions.deplacement_interdit():
            return f"il est fatigué ({num(self.pulsions.fatigue)} > {num(self.pulsions.fatigue_seuil)})"
        return None

    def _assez_loin(self, piste) -> bool:
        """Garde de distance de toute approche : hauteur de boîte < hauteur_max."""
        return piste.hauteur < self.r.get("approche.hauteur_max")

    def _piste_regardee(self, now: float) -> Optional[str]:
        p = self.pistes.courante(now)
        if p is None:
            return None
        return self.piste_regardee if self.piste_regardee == p.id else p.id

    # ================================================================ état du corps (lot S2a, 27/11)
    def _noter_geste(self, demande, etat: str, raison: Optional[str], parcouru_m: Optional[float],
                     now: float) -> None:
        """Le dernier geste (spec-S2 §2) devient `demande` : en cours, ou refusé avant de partir."""
        self.geste_corps = {"demande": demande, "etat": etat, "raison": raison, "parcouru_m": parcouru_m, "t": now}

    def _issue_geste(self, etat: str, raison: Optional[str], parcouru_m: Optional[float], now: float) -> None:
        """Issue du geste EN COURS (arrivé, abandonné, refusé par le régisseur) ; la première dite
        gagne (une annulation suivie de l'issue « cancelled » du même ordre ne la réécrit pas)."""
        g = self.geste_corps
        if g is not None and g["etat"] == corps_etat.GESTE_EN_COURS:
            g.update(etat=etat, raison=raison, parcouru_m=None if parcouru_m is None else round(parcouru_m, 1), t=now)

    def etat_corps(self, now: float) -> corps_etat.EtatCorps:
        """Les FAITS du sélecteur, tels quels, donnés à la règle unique (corps_etat.etablir)."""
        e, rep, g = self.en_cours, self.reprise, self.geste_corps
        geste = None
        if g is not None and (g["etat"] == corps_etat.GESTE_EN_COURS
                              or now - g["t"] <= corps_etat.GESTE_MEMOIRE_S + EPS):
            geste = corps_etat.Geste(g["demande"], g["etat"], g["raison"], g["parcouru_m"])
        return corps_etat.etablir(corps_etat.Faits(
            route_state=self.route_state, corps_sur=self.corps_sur, seance_connue=self.seance_connue,
            en_seance=self.en_seance, arret_vocal=self.arret_vocal, verrou=self.verrou,
            reprise=rep["genre"] if rep is not None else None,
            reprise_cible=rep["cible"] if rep is not None else None,
            repart_dans_s=rep["delai"] - (now - rep["silence_depuis"]) if rep is not None else None,
            geste_en_cours=e is not None and e.candidat.deplacement and e.candidat.action != "repartir",
            geste=geste, ici=corps_etat.ici_depuis(self.tableau(now))))

    def rafraichir_corps(self, now: float) -> None:
        """Republie corps/etat s'il a CHANGÉ (corps_etat.cle) ou s'il date de PERIODE_MAX_S ; un
        changement de marche ou de cause est une ligne `corps_etat` du journal — c'est elle qui
        dit « il a décidé » ou « David a arrêté ». Appelé par le node avant chaque vidage : après
        un stop, l'état part dans le même lot de sorties que lui, derrière lui."""
        etat = self.etat_corps(now)
        cle = corps_etat.cle(etat)
        if cle == self._corps_cle and self._corps_t is not None \
                and now - self._corps_t < corps_etat.PERIODE_MAX_S - EPS:
            return
        if (etat.marche, etat.cause) != self._corps_marche_cause:
            self._corps_marche_cause = (etat.marche, etat.cause)
            self._journal("corps_etat", etat.phrase, marche=etat.marche, cause=etat.cause,
                          qui_relance=etat.qui_relance)
        self._corps_cle, self._corps_t = cle, now
        self.sorties.append(("corps_etat", corps_etat.encoder(etat, int(now * 1000))))

    # ================================================================ tick
    def tick(self, now: float) -> Optional[Decision]:
        self._now = now
        self._decision_tick = None
        dt = 0.0 if self._t_prec is None else max(0.0, now - self._t_prec)
        self._t_prec = now
        vivantes = self.offres.vivantes(now)
        self.pulsions.avancer(dt, calme=not vivantes and self.en_cours is None)
        if self.reprise is not None:
            # Jauge AFFICHÉE (intention, journal) : la reprise ne passe plus par le score.
            silence = now - self.reprise["silence_depuis"]
            self.pulsions.pression_route = min(1.0, silence / self.reprise["delai"])
        else:
            self.pulsions.pression_route = 0.0
        self._expirer(now)
        self.tableau(now)          # péremption du tableau journalisée à l'heure, pas à la 1re lecture
        self._suivre_engagement(now)
        self._ordre_console(now)
        self._reprise_due(now)
        self.arbre.tick_once()
        self._reaction(now)
        return self._decision_tick

    def _expirer(self, now: float) -> None:
        self.ignores = {c: fin for c, fin in self.ignores.items() if fin > now}
        if self.joue_avec is not None and now >= self.joue_avec["fin"]:
            self.joue_avec = None
        if self.plus_lent_fin is not None and now >= self.plus_lent_fin:
            self.plus_lent_fin = None

    def _suivre_engagement(self, now: float) -> None:
        e = self.en_cours
        if e is None:
            return
        action = e.candidat.action
        if action == "lubie" and not e.stop_envoye and now - e.t_debut >= self.r.get("lubie.delai_refus_s") - EPS:
            # Ni ignore ni va_la pendant le délai de refus (ils auraient annulé
            # la lubie) : Didier demande l'arrêt au régisseur.
            e.stop_envoye = True
            # Lot S2c (séance du 26/11, « il n'a pas cadré le banc ») : il s'arrêtait DEVANT
            # l'objet de sa lubie mais lui parlait de profil — seule sa TÊTE était tournée
            # (`look`), et la caméra est fixée au BUSTE. Son arrêt est désormais un pivot du
            # CORPS vers l'objet (`tourner_vers`, l'angle est calculé par la régie, jamais
            # deviné ici) : une manœuvre ordinaire, qui quitte la route et finit à l'arrêt.
            # Jamais « stop » PUIS pivot (relecture adverse du 28/11) : sous l'arrêt, le pivot
            # restait retenu (facteur 0) et partait au « go » de la reprise — Didier planté.
            # Le pivot DÉPLACE le corps : mêmes gardes qu'un déplacement de son initiative
            # (2e relecture adverse du 28/11 : superviseur absent, fatigue). Refusé -> « stop ».
            refus = self._refus_deplacement(now)
            e.pivot = None if refus else self._pivot_vers(e.candidat.cible, now)
            if e.pivot is None:
                self.sorties.append(("chat_move", marche(STOP, DIDIER)))
                if refus:
                    self._journal("lubie_sans_pivot", f"lubie « {e.candidat.cible} » : pas de pivot, {refus} → "
                                  "il s'arrête sans se tourner", cible=e.candidat.cible, raison=refus)
            else:
                e.t_pivot = now
                self.sorties.append(("chat_move", e.pivot))
            regard = bool(e.candidat.detail.get("regard"))
            self._journal("arret_didier", f"lubie « {e.candidat.cible} » réclamée"
                          + (", regard tourné vers elle" if regard else " (sans regard : position inconnue)")
                          + f", pas de refus en {self.r.get('lubie.delai_refus_s'):g} s → il s'arrête",
                          cible=e.candidat.cible, kind="lubie", regard=regard, pivot=e.pivot is not None)
            self._armer_reprise(now, f"lubie « {e.candidat.cible} »", cible=e.candidat.cible,
                                genre=corps_etat.DIDIER_LUBIE)
            self.pourquoi_courant = f"arrêté devant « {e.candidat.cible} »" + (
                f" ; repartir ? (après {phrases.s(self.reprise['delai'])} de silence)" if self.reprise else "")
            self._publier_intention(now)
        if e.pivot is not None and now - e.t_pivot > self.r.get("durees_s.deplacement_accuse") + EPS:
            self._arret_lubie_sans_pivot(e, "le régisseur n'a pas répondu au pivot", now)
        if e.candidat.deplacement and e.candidat.action != "repartir" and not e.accuse \
                and now - e.t_etape > self.r.get("durees_s.deplacement_accuse") + EPS:
            self._rendre_refractaires(e)
            if e.candidat.action == "bouche":
                # Le régisseur s'est tu (sa réponse aurait accusé ou fini) : le
                # chat doit le savoir, sinon Didier affirme le geste.
                self.sorties.append(("chat_move_reply", reponse_bouche(e.etape, "no_reply", None)))
            self._issue_geste(corps_etat.GESTE_REFUSE, "sans_suite", 0.0, now)
            self._finir(now, "le régisseur n'a pas donné suite (voir son journal) : il n'a pas bougé")
            return
        # Une lubie dont le pivot attend sa réponse ne finit pas : son repli sur « stop »
        # (refus, silence du régisseur) mourrait avec elle, et Didier ne s'arrêterait pas.
        if now >= e.fin_prevue - EPS and e.pivot is None:
            self._finir(now, "c'est fini")

    def _etape_suivante(self, e: Engagement, now: float) -> None:
        etape = e.etapes.pop(0)
        e.accuse, e.t_etape, e.etape, e.nom_ordre = False, now, etape, None
        self._noter_geste(etape, corps_etat.GESTE_EN_COURS, None, None, now)
        self.sorties.append(("chat_move", etape))

    def _rendre_refractaires(self, e: Engagement) -> None:
        """Le déplacement n'a pas eu lieu (refus, régisseur muet) : ses périodes
        réfractaires reprennent leur valeur d'avant la décision, et la fatigue
        comptée est rendue. Une seule fois par engagement."""
        if not e.derniers_avant:
            return
        for cat, t in e.derniers_avant.items():
            if t is None:
                self.derniers.pop(cat, None)
            else:
                self.derniers[cat] = t
        e.derniers_avant = {}
        self.pulsions.sur_deplacement_refuse()

    # ================================================================ la reprise (une seule, lot S1)
    def _armer_reprise(self, now: float, pourquoi: str, cible: Optional[str] = None,
                       apres_geste: bool = False, *, genre: str) -> None:
        """Didier vient de s'arrêter de lui-même (cf. docstring de module, UNE SEULE REPRISE) :
        il repartira seul après D s de SILENCE, D tiré MAINTENANT dans [reprise.min_s,
        reprise.max_s] par le générateur semé (self.hasard), au dixième de seconde. Un nouvel
        arrêt retire. Jamais sous le verrou de David (règle du 31/10). `apres_geste` : arrêt
        de fin de déplacement — si la route a repris entre-temps, rien à relancer. `genre` : la
        cause de l'arrêt dans l'état du corps (corps_etat.REPRISES, lot S2a)."""
        if self.verrou_david:
            return
        if apres_geste and not self.en_seance:
            # R2 : l'arrêt de fin de geste n'est pas le sien — hors séance, David relance. La
            # reprise précédente et son ordre suspendu tombent aussi (rien de périmé ne repart).
            self.reprise = None
            self._journal("reprise_annulee", f"{pourquoi}, hors séance → il ne repartira pas de lui-même")
            return
        delai = round(self.hasard.uniform(self.r.get("reprise.min_s"), self.r.get("reprise.max_s")), 1)
        self.reprise = {"t": now, "silence_depuis": now, "delai": delai, "pourquoi": pourquoi,
                        "cible": cible, "apres_geste": apres_geste, "ordre": None, "genre": genre}
        self._journal("reprise_armee", f"{pourquoi} → il repartira après {phrases.s(delai)} de silence",
                      cause=pourquoi, delai_s=delai, cible=cible)

    def _oublier_suspendu(self, pourquoi: str) -> None:
        """Tout NOUVEL ordre de David efface l'ordre suspendu (seconde relecture, 26/11) : son
        ordre le plus récent gagne, l'ancien ne doit jamais repartir derrière lui."""
        if self.reprise is not None and self.reprise.get("ordre") is not None:
            demande = self.reprise["ordre"]["demande"]
            self.reprise["ordre"] = None
            self._journal("ordre_suspendu", f"ordre de David suspendu oublié ({phrases.demande(demande)}) : "
                          f"{pourquoi}", demande=demande)

    def _reprendre_suspendu(self, rep: dict, now: float) -> bool:
        """R4 : ré-émet l'ordre suspendu s'il a moins de reprise.ordre_suspendu_max_s et passe
        les contrôles d'un ordre neuf (objet atteignable, verrou, superviseur). -> True s'il
        est reparti ; sinon la reprise fait un simple « go »."""
        o = rep["ordre"]
        ordre = dict(o["demande"], origine=DAVID)
        if now - o["t"] > self.r.get("reprise.ordre_suspendu_max_s") + EPS:
            self._journal("ordre_suspendu", f"ordre de David abandonné : trop ancien ({phrases.demande(ordre)}, "
                          f"donné il y a plus de {self.r.get('reprise.ordre_suspendu_max_s'):g} s)", demande=ordre)
            return False
        if self._hors_atteinte(ordre, now):
            return False
        self._journal("reprise", f"ordre de David suspendu, repris après {phrases.s(rep['delai'])} de silence "
                      f"({phrases.demande(ordre)})", cause=rep["pourquoi"], delai_s=rep["delai"], demande=ordre)
        self._ordre_bouche(ordre, now, t_ordre=o["t"])
        return True

    def _desarmer_reprise(self, pourquoi: str) -> None:
        if self.reprise is not None:
            self.reprise = None
            self._journal("reprise_annulee", f"{pourquoi} → il ne repartira pas de lui-même")

    def _reprise_due(self, now: float) -> None:
        """« go » d'origine « didier » quand le silence a duré D s, qu'aucun déplacement ne
        roule (un geste en cours : elle l'attend) et que le superviseur est là — ou, si son
        arrêt avait suspendu un geste de David (R4), ce geste ré-émis à la place."""
        rep = self.reprise
        if rep is None:
            return
        if rep["apres_geste"] and self.route_state in ("on", "goto"):
            self.reprise = None        # la route a repris sans lui : rien à relancer
            return
        if rep["apres_geste"] and not self.en_seance:
            self._desarmer_reprise("la séance s'est arrêtée")      # R2
            return
        if self.en_cours is not None and self.en_cours.candidat.deplacement:
            return
        if rep["genre"] == corps_etat.DIDIER_LUBIE and self.route_state == "goto":
            # Le pivot de la lubie roule (S2c) : un « go » maintenant serait « deja_en_marche »
            # au régisseur, et Didier resterait planté à son arrivée. On attend son issue
            # (arrived / off) : le « go » part alors en reprise (« rejoin » au régisseur).
            return
        if self.superviseur_absent():
            return
        if now - rep["silence_depuis"] < rep["delai"] - EPS:
            return
        self.reprise = None
        if rep["ordre"] is not None and self._reprendre_suspendu(rep, now):
            return
        # Sous l'arrêt « david » d'un « reviens » dont le go n'est pas parti, seul un go de David
        # le lève au régisseur (R1) : la reprise part alors en « david » (3e relecture, m2).
        origine = DAVID if self._arret_reviens else DIDIER
        self._arret_reviens = False
        self.sorties.append(("chat_move", marche(GO, origine)))
        self._journal("reprise", f"reprise : il repart de lui-même ({rep['pourquoi']}, après "
                      f"{phrases.s(rep['delai'])} de silence)", cause=rep["pourquoi"], delai_s=rep["delai"],
                      origine=origine)
        self.pourquoi_courant = f"il repart de lui-même ({rep['pourquoi']})"
        self._publier_intention(now)

    def _finir(self, now: float, pourquoi: str) -> None:
        e = self.en_cours
        fini = e.candidat
        if fini.deplacement and fini.action != "repartir" and (fini.action == "bouche" or e.origine == DIDIER) \
                and self.route_state != "on":
            # Geste de la bouche (15/11) ou déplacement de son initiative, fini OU échoué
            # hors de sa route : il la reprendra seul. Refusé sans l'avoir quittée (« on ») :
            # rien n'a changé, une reprise déjà armée (lubie, stop de Didier) reste.
            self._armer_reprise(now, "geste terminé" if pourquoi == "il est arrivé" else "geste échoué",
                                apres_geste=True, genre=corps_etat.GESTE_FINI)
        # Fin sans issue dite (échéance du geste) : abandonné. Une issue déjà notée reste.
        self._issue_geste(corps_etat.GESTE_ABANDONNE, "timeout", None, now)
        self.en_cours = None
        self.courante = (RIEN, None)
        self.pourquoi_courant = f"{phrases.action(fini.action, fini.cible, fini.detail)} : {pourquoi}"
        if self.reprise is not None:
            self.pourquoi_courant += " ; repartir ?"
        self._journal("fin", f"{phrases.action(fini.action, fini.cible, fini.detail)} : {pourquoi}",
                      action=fini.action, cible=fini.cible)
        self._publier_intention(now)

    def _annuler(self, now: float, pourquoi: str) -> None:
        """Interruption imposée (stop, ignore, va_la) : PAS une décision (porte T1)."""
        fini = self.en_cours.candidat
        self._issue_geste(corps_etat.GESTE_ABANDONNE, "annule", None, now)
        self.en_cours = None
        self.courante = (RIEN, None)
        phrase = f"{pourquoi} → il arrête de {phrases.action(fini.action, fini.cible, fini.detail)}"
        self.pourquoi_courant = phrase
        self._journal("annulation", phrase, action=fini.action, cible=fini.cible)
        self._publier_intention(now)

    def _reaction(self, now: float) -> None:
        """Porte T3 : toute offre née (personne ou objet) a sa ligne de décision
        en <= 1 s — un choix (taggé dans _decider) ou, faute de choix, un
        MAINTIEN qui dit pourquoi il ne réagit pas."""
        dus = [d for d in self.reaction_due if now - d["t"] >= self.r.get("reaction.maintien_apres_s") - EPS]
        if not dus:
            return
        self.reaction_due = [d for d in self.reaction_due if d not in dus]
        action, cible = self.courante
        fait = phrases.action(action, cible)
        for due in dus:
            offre = next((o for o in self.offres.vivantes(now) if o.piste == due["cible"]), None)
            valeur = offre.valeur if offre else 0.0
            if self.en_cours is not None:
                raison = (f"il continue ({fait}) : la nouvelle offre ({num(valeur)}) ne suffit pas à "
                          f"l'interrompre (il faut {num(self.r.get('engagement.seuil_rupture'))})")
            elif due["cible"] in self.ignores:
                raison = f"il continue ({fait}) : David a dit d'ignorer {due['cible']}"
            elif self.t_derniere_decision is not None and now - self.t_derniere_decision < self.r.get("changement.min_s"):
                raison = (f"il continue ({fait}) : il vient de changer d'action il y a "
                          f"{phrases.s(now - self.t_derniere_decision)} (< {self.r.get('changement.min_s'):g} s)")
            elif due["kind"] == "objet" and self.route_state != "on":
                raison = f"il continue ({fait}) : « {due['cible']} », mais il n'est pas en route"
            elif due["kind"] == "objet" and (self.reprise is not None or self.verrou_david):
                raison = f"il continue ({fait}) : « {due['cible']} », mais il est déjà arrêté"
            elif due["kind"] == "objet" and now - self.derniers.get(ARRET_DIDIER, -1e9) < \
                    self.r.get("refractaire_s.arret_didier"):
                raison = (f"il continue ({fait}) : « {due['cible']} », mais il s'est déjà arrêté il y a moins de "
                          f"{self.r.get('refractaire_s.arret_didier'):g} s")
            else:
                raison = f"il continue ({fait}) : rien ne l'attire assez pour changer"
            self._journal("maintien", raison, action=action, cible=cible, reaction_a=[due["cible"]])

    # ================================================================ choix (feuilles de l'arbre)
    def _candidats(self, now: float, deplacement_permis: bool) -> List[Candidat]:
        cands = [Candidat(RIEN)]
        vivantes = self.offres.vivantes(now)
        piste = self.pistes.courante(now)
        if piste is not None:
            o = next((x for x in vivantes if x.kind == "personne" and x.piste == piste.id), None)
            cands.append(Candidat("regarder", piste.id, o, "curiosite", {"azimut": piste.azimut}))
            if o is not None and self.pools.get("accueil"):
                cands.append(Candidat("accueil", piste.id, o, "curiosite"))
            if self._assez_loin(piste):
                cands.append(Candidat("approcher", piste.id, o, "curiosite", {"azimut": piste.azimut}))
        if self.pools.get("spontanee"):
            cands.append(Candidat("spontanee", None, None, "ennui"))
        if self.en_seance and self.route_state == "on" and not self.verrou_david and self.reprise is None:
            for o in vivantes:
                if o.kind == "objet":
                    cands.append(Candidat("lubie", o.piste, o, "lubie"))
        # (Aucun ORDRE ne passe par le score — gestes de la bouche, ordres de la console : R6 ; la
        # reprise non plus : _reprise_due.)
        return [c for c in cands if self._permis(c, deplacement_permis)]

    def _permis(self, c: Candidat, deplacement_permis: bool) -> bool:
        if c.action == RIEN:
            return True
        if c.cible is not None and c.cible in self.ignores:
            return False
        if c.deplacement and (not deplacement_permis or self._refus_deplacement(self._now)):
            return False
        if c.action == "approcher" and not self.en_seance and not (
                self.joue_avec is not None and self.joue_avec["cible"] == c.cible):
            return False   # R2 : hors séance, pas d'approche de son initiative (« joue avec » : David)
        if c.action in ("accueil", "spontanee") and self.animation_state:
            return False   # une séquence a déjà la main (arbitrage actionneurs)
        return True

    def _contexte(self, now: float) -> Contexte:
        console = None
        if self.joue_avec is not None:
            console = {"action": None, "cible": self.joue_avec["cible"], "cmd": "joue avec"}
        tempo = self.r.get("console.plus_lent_facteur") if self.plus_lent_fin is not None else 1.0
        return Contexte(now=now, jauges=self.pulsions.jauges(), console=console,
                        derniers=dict(self.derniers), derniere_spontanee=self.derniere_spontanee, tempo=tempo)

    def choisir(self, branche: str, deplacement_permis: bool) -> None:
        now = self._now
        cands = self._candidats(now, deplacement_permis)
        if self.en_cours is not None and self.en_cours.origine == DAVID:
            # Un ORDRE de David engagé (ou « joue avec ») : le score ne l'interrompt jamais
            # (lot S1) ; seul un autre ordre passe devant (_executer_ordre).
            self.leader = None
            return
        if self.en_cours is not None:
            # Engagée : seules les offres de valeur >= seuil de rupture concourent.
            seuil = self.r.get("engagement.seuil_rupture")
            cands = [c for c in cands if c.offre is not None and c.offre.valeur >= seuil]
            if not cands:
                self.leader = None
                return
        scores = classer(cands, self._contexte(now), self.r)
        meilleur = scores[0]
        second = scores[1].total if len(scores) > 1 else 0.0
        if meilleur.candidat.cle() == f"{self.courante[0]}:{self.courante[1] or ''}" or meilleur.total <= 0.0:
            self.leader = None
            return
        if meilleur.candidat.action == RIEN and self.en_cours is not None:
            # « Rien » n'interrompt jamais une action engagée : elle se finit.
            self.leader = None
            return
        if meilleur.total < second * (1.0 + self.r.get("hysteresis.marge")):
            self.leader = None
            return
        if self.leader != meilleur.candidat.cle():
            self.leader, self.leader_depuis = meilleur.candidat.cle(), now
            return
        if now - self.leader_depuis < self.r.get("hysteresis.duree_s") - EPS:
            return
        if self.t_derniere_decision is not None and now - self.t_derniere_decision < self.r.get("changement.min_s") - EPS:
            return
        self._decider(meilleur, scores, branche, now)

    def _decider(self, s, scores, branche: str, now: float) -> None:
        c = s.candidat
        origine = DAVID if s.considerations.get("console") else DIDIER
        # PHOTOGRAPHIE avant toute mutation (revue A1, point 6) : pulsions et
        # offres de la ligne sont celles qui ont fait le `pourquoi` (calculé
        # au même instant), pas l'état d'après (ennui remis à 0, offre prise).
        jauges = self.pulsions.jauges()
        offres = [o.resume(now) for o in self.offres.vivantes(now)]
        if self.en_cours is not None:
            self._annuler(now, f"plus pressant : {phrases.action(c.action, c.cible, c.detail)}")
        sortie_ok = self._executer(c, now, origine)
        if not sortie_ok:
            return
        self.leader = None
        self.t_derniere_decision = now
        self.courante = (c.action, c.cible)
        pourquoi = s.pourquoi
        if c.detail.get("sequence"):
            pourquoi += f" « {c.detail['sequence']} »"
        self.pourquoi_courant = pourquoi
        if c.action != RIEN:
            if c.deplacement and self.en_cours is not None:
                # Photographie AVANT de compter : rendue si le régisseur refuse.
                self.en_cours.derniers_avant = {cat: self.derniers.get(cat) for cat in c.categories}
            self.pulsions.sur_action(c.deplacement)
            for cat in c.categories:
                if cat != ARRET_DIDIER:
                    self.derniers[cat] = now
                elif origine == DIDIER:
                    self._noter_arret_didier(c, now)
            if s.spontanee:
                self.derniere_spontanee = now
            if c.offre is not None:
                self.offres.prendre(c.offre)
        payload = {
            "action": c.action, "cible": c.cible, "branche": branche, "score": round(s.total, 3),
            "considerations": s.considerations, "spontanee": s.spontanee, "deplacement": c.deplacement,
            "top3": [{"action": x.candidat.action, "cible": x.candidat.cible, "score": round(x.total, 3)}
                     for x in scores[:3]],
            "offres": offres,
            "pulsions": jauges,
        }
        if c.detail.get("sequence"):
            payload["sequence"] = c.detail["sequence"]
        if self.reaction_due:
            payload["reaction_a"] = [d["cible"] for d in self.reaction_due]
            self.reaction_due = []
        self._journal("decision", pourquoi, **payload)
        self._decision_tick = Decision(c.action, c.cible, pourquoi)
        self._publier_intention(now)

    def _pivot_vers(self, cible, now: float) -> Optional[dict]:
        """Le `tourner_vers` d'origine « didier » qui tourne le CORPS vers un objet nommé (lot
        S2c), à publier tel quel ; le régisseur calcule l'angle depuis sa pose.

        L'`id` du tableau est JOINT, comme pour « aller voir » : depuis le lot O1 (18/11) la
        régie ne résout plus aucun nom, elle ne connaît que l'id (`_target`). Sans objet
        résolu -> None : on ne se tourne pas vers ce qu'on ne situe pas, et un geste sans id
        serait de toute façon refusé « unknown »."""
        if cible is None:
            return None
        objet = self.tableau(now).resoudre(cible).objet
        if objet is None:
            return None
        return dict(commande(self.deplacements, "tourner_vers", objet=cible, id=objet.id), origine=DIDIER)

    def _arret_lubie_sans_pivot(self, e: Engagement, pourquoi: str, now: float) -> None:
        """Le pivot de la lubie n'a pas lieu (refusé : « deja_face », « no_pose », … ; ou sans
        réponse) : Didier roule encore, il s'arrête comme avant S2c, par un « stop » « didier ».
        La reprise, déjà armée, reste celle de la lubie."""
        e.pivot = None
        self.sorties.append(("chat_move", marche(STOP, DIDIER)))
        self._journal("lubie_sans_pivot", f"lubie « {e.candidat.cible} » : {pourquoi} → il s'arrête sans se "
                      "tourner", cible=e.candidat.cible, raison=pourquoi)

    def _noter_arret_didier(self, c: Candidat, now: float) -> None:
        """Un arrêt de route causé par Didier (revue A1, point 11). Lubie : l'arrêt
        tombera après le délai de refus (le stop est noté là, ligne arret_didier) ;
        approche : il quitte sa route MAINTENANT. (Un geste de la bouche est un ordre de
        David, jamais un arrêt de Didier : décision du 15/11, lot S1.)"""
        if c.action == "lubie":
            self.derniers[ARRET_DIDIER] = now + self.r.get("lubie.delai_refus_s")
            return
        self.derniers[ARRET_DIDIER] = now
        self._journal("arret_didier", f"il quitte sa route pour {phrases.action(c.action, c.cible, c.detail)}",
                      cible=c.cible, kind=c.action)

    def _executer(self, c: Candidat, now: float, origine: str) -> bool:
        """Effets d'une action choisie ; False si elle ne peut pas partir."""
        r = self.r
        if c.action == RIEN:
            return True
        if c.action == "regarder":
            angle = -c.detail["azimut"] * r.get("regard.demi_champ_deg")
            hold = r.get("durees_s.regarder")
            self.sorties.append(("look", {"angle_deg": round(angle, 1), "hold_ms": int(hold * 1000)}))
            self.piste_regardee = c.cible
            self.en_cours = Engagement(c, now, now + hold, origine)
            return True
        if c.action in ("accueil", "spontanee"):
            seq = self._prochaine_sequence(c.action)
            c.detail["sequence"] = seq.nom
            self.joues[seq.nom] = now
            self.sorties.append(("animation", seq.nom))
            duree = (seq.duree_s or r.get("durees_s.expression_defaut")) + r.get("durees_s.expression_marge")
            self.en_cours = Engagement(c, now, now + duree, origine)
            return True
        if c.action == "lubie":
            # RÉCLAMÉ (intention publiée par _decider) ET AMORCÉ (regard vers l'objet).
            objet = self.tableau(now).resoudre(c.cible).objet
            if objet is not None and objet.azimut_deg is not None:
                angle = objet.azimut_deg
                hold = r.get("lubie.delai_refus_s") + r.get("durees_s.arret")
                self.sorties.append(("look", {"angle_deg": round(angle, 1), "hold_ms": int(hold * 1000)}))
                c.detail["regard"] = True
            fin = now + r.get("lubie.delai_refus_s") + r.get("durees_s.arret")
            self.en_cours = Engagement(c, now, fin, origine)
            return True
        if c.action == "repartir":
            self.sorties.append(("chat_move", marche(GO, origine)))
            if origine == DAVID:
                self._arret_reviens = False   # le go du « reviens » est parti
            self.reprise = None        # il repart : la reprise est caduque
            self.en_cours = Engagement(c, now, now + r.get("durees_s.relais"), origine, accuse=True)
            return True
        # Déplacements via le régisseur (étapes = chat_move successifs).
        if c.action == "approcher":
            etapes = []
            angle = -c.detail["azimut"] * r.get("regard.demi_champ_deg")
            if abs(angle) >= ANGLE_MIN_TOURNER_DEG:
                etapes.append(commande(self.deplacements, "se_tourner_vers", angle_deg=round(angle, 1)))
            etapes.append(commande(self.deplacements, "approcher"))
        elif c.action == "aller_voir":
            objet = self.tableau(now).resoudre(c.cible).objet
            etapes = [commande(self.deplacements, "aller_voir", objet=c.cible,
                               **({"id": objet.id} if objet is not None else {}))]
        elif c.action == "bouche":
            etapes = [c.detail["demande"]]   # TELLE QUELLE (origine comprise) : le chat apparie la réponse
        else:
            return False
        if c.action != "bouche":
            # Lot S1 : la demande au régisseur porte l'origine de qui la fait.
            etapes = [dict(etape, origine=origine) for etape in etapes]
        # Une reprise déjà armée ATTEND la fin du geste (_reprise_due) ; sa fin la ré-arme.
        e = Engagement(c, now, now + r.get("durees_s.deplacement_max") * len(etapes), origine, etapes=etapes)
        self.en_cours = e
        self._etape_suivante(e, now)
        return True

    def _prochaine_sequence(self, emploi: str):
        """Rotation déterministe : la séquence jouée il y a le plus longtemps
        (jamais jouée d'abord, dans l'ordre du répertoire)."""
        pool = self.pools[emploi]
        return min(pool, key=lambda s: (self.joues.get(s.nom, -1.0), pool.index(s)))
