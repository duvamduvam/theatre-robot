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
  A1), à deux GENRES (R3) : « console » (STOP console, Route OFF), levé par le GO
  console seul ; « voix » (mot d'arrêt), levé aussi par un go de tour humain ;
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
  AMORCÉE (regard ; à défaut de pose/objet, l'intention seule, 3 s) puis le stop
  n'est demandé que si la console n'a dit ni ignore ni va_la entre-temps ;
- UNE SEULE REPRISE (lot S1 ; remplace les trois minuteries 10 s / 6 s / 90 s) :
  après un arrêt décidé par Didier — lubie, « stop » d'origine « didier », pause
  « regarde ça », fin (réussie ou non) d'un geste de la bouche ou de son propre
  déplacement — il repart seul (« go » d'origine « didier ») après D s de
  SILENCE, D tiré AU MOMENT DE L'ARRÊT dans [reprise.min_s, reprise.max_s] par le
  générateur semé du sélecteur (journalisé « il repartira après … de silence »).
  Toute parole entendue (chat_transcript, rôle david) remet le silence à zéro
  sans retirer le tirage (règle du 02/11). Attend qu'aucun geste ne roule.
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
from theatre_contrats import objets as tableau_objets
from didier_jeu.phrases import n as num
from didier_jeu.offres import Offre, Offres
from didier_jeu.pistes import Pistes
from didier_jeu.pulsions import Pulsions
from didier_jeu.relais import (DAVID, DIDIER, GO, PAUSE, STOP, VERROU_CONSOLE, VERROU_VOIX, lire, marche,
                               reponse_bouche)
from didier_rehearsal.rehearsal_state import SEANCE_EN_COURS
from didier_jeu.repertoire import COMMANDES_REGISSEUR, commande
from didier_jeu.scores import ARRET_DIDIER, RIEN, Candidat, Contexte, classer

# Commandes de la console (spec §4), gravées avec la page scène.
CONSOLE_CMDS = ("va_la", "joue_avec", "ignore", "reviens", "plus_lent", "stop", "go")
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
    stop_envoye: bool = False         # lubie : le « stop » est parti
    etape: Optional[dict] = None      # chat_move de l'étape EN COURS (appariement des réponses)
    nom_ordre: Optional[str] = None   # `name` de l'ordre ACCEPTÉ (seule son issue finit l'étape)
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
        # Verrou d'arrêt de DAVID SEUL (lot S1), à deux GENRES (règle R3, 25/11) : None (pas de
        # verrou) | VERROU_CONSOLE (STOP de la console, Route OFF : levé par un GO console
        # SEUL) | VERROU_VOIX (mot d'arrêt : levé par un go de David en tour humain ou par un
        # GO console).
        self.verrou: Optional[str] = None
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
        la bouche ne décide aucun mouvement, §8 bis) — le chat le sait."""
        demande, origine = lire(valeur)
        if demande == STOP:
            self.relayer_stop(origine, "bouche", now)
            return
        if demande == PAUSE and origine is None:
            # Une pause contient un arrêt : d'origine inconnue, c'est un stop (lu « david »,
            # comme le stop d'origine inconnue — sens sûr).
            self.relayer_stop(DAVID, "bouche", now)
            return
        if demande == GO and origine is None:
            self._journal("refus", f"« go » d'origine inconnue ({valeur!r}) : ignoré", source="bouche")
            return
        if demande == GO:
            self.relayer_go(origine, "bouche", now)
            return
        if demande == PAUSE:
            self.pause_regard(origine, now)
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
        if self._hors_atteinte(demande, now):
            return
        self._ordre_bouche(demande, now)

    def _ordre_bouche(self, demande: dict, now: float) -> None:
        """Un geste demandé par David à la bouche (tour humain ou continuation de SA tâche) :
        un ORDRE (lot S1, étude assainissement règle 1). Il part TOUT DE SUITE, sans score ni
        hystérésis, et n'est refusé que sous le verrou de David ou sans superviseur (l'objet
        hors d'atteinte est déjà refusé par _hors_atteinte, la sécurité par le régisseur).
        L'action engagée cède (un ordre passe devant) ; un ordre macro de la console en
        attente aussi (le plus récent de David gagne). Fatigue et réfractaire « deplacement »
        sont COMPTÉS (ses propres envies attendront) et rendus si le régisseur refuse."""
        code = texte = None
        if self.verrou_david:
            code, texte = "arrete", "il est arrêté jusqu'au go de David"
        elif self.superviseur_absent():
            code, texte = "sans_superviseur", "personne ne surveille (page fermée)"
        if code is not None:
            self.sorties.append(("chat_move_reply", reponse_bouche(demande, "dropped", code)))
            self._journal("refus", f"David voulait {phrases.demande(demande)}, mais non : {texte}",
                          source="bouche", demande=demande, code=code)
            return
        c = Candidat("bouche", demande.get("objet") or demande.get("cmd"), None, None, {"demande": demande})
        self.ordre = None
        self._executer_ordre(c, now, f"David : {phrases.demande(demande)} → il y va tout de suite",
                             f"David demande : {phrases.demande(demande)}", source="bouche", demande=demande)

    def _executer_ordre(self, c: Candidat, now: float, pourquoi: str, annulation: str, **journal) -> None:
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
        self.route_state = etat
        e = self.en_cours
        if e is not None and etat == "goto":
            e.accuse = True

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
        route — traité comme un STOP de la console (règle R3) : verrou « console »,
        levé par un GO console seulement ; reprise désarmée, lubie en attente
        annulée (revue A1, bloquant 3). « boot » : rien."""
        if cause != "cmd":
            return
        e = self.en_cours
        if e is not None and e.candidat.action == "lubie" and not e.stop_envoye:
            self._annuler(now, "David a coupé la route")
        self._desarmer_reprise("David a coupé la route")
        self.ordre = None
        if self.verrou != VERROU_CONSOLE:
            self.verrou = VERROU_CONSOLE
            self._journal("verrou", "David a coupé la route → verrou de la console, levé par son GO",
                          genre=VERROU_CONSOLE)

    def sur_seance(self, etat, now: float) -> None:
        """rehearsal/state (latché, régisseur) : {"seance": "attente"|"en_cours"|"terminee", …}.
        Seule « en_cours » est une séance ; tout le reste (illisible compris) = hors séance
        (règle R2, sens sûr : pas d'initiative)."""
        en = isinstance(etat, dict) and etat.get("seance") == SEANCE_EN_COURS
        if en != self.en_seance:
            self.en_seance = en
            self._journal("seance", "séance lancée : il peut prendre des initiatives" if en else
                          "hors séance : aucune initiative de mouvement (ni lubie, ni approche)", en_seance=en)

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
        if e is None or not e.candidat.deplacement or e.etape is None or payload.get("demande") != e.etape:
            return
        effet = payload.get("effect")
        if effet == "accepted":
            e.accuse = True
            nom = payload.get("name")
            e.nom_ordre = nom if isinstance(nom, str) else None
            return
        raison = payload.get("reason")
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
        # R4 : un stop de Didier pendant un geste de David SUSPEND l'ordre (ré-émis à la reprise).
        suspendu = (e.candidat.detail["demande"] if origine == DIDIER and e is not None
                    and e.candidat.action == "bouche" and e.origine == DAVID else None)
        if e is not None and (e.candidat.deplacement or e.candidat.action == "lubie"):
            self._annuler(now, f"stop de {qui}")
        if origine == DAVID:
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
            self._armer_reprise(now, "il s'est arrêté de lui-même")
            if suspendu is not None and self.reprise is not None:
                self.reprise["ordre"] = suspendu
                self._journal("ordre_suspendu", f"ordre de David suspendu ({phrases.demande(suspendu)}) : "
                              "il le reprendra après le silence", demande=suspendu)
            self.pourquoi_courant = f"Didier « stop » : arrêté{reste or ', il repartira seul'}"
        self._publier_intention(now)

    def pause_regard(self, origine: str, now: float) -> None:
        """« Regarde ça » de la bouche (cf. docstring de module) : en marche, « stop » relayé
        tout de suite SANS verrou (ce n'est pas un ordre d'arrêt : il repartira seul), puis la
        reprise s'arme. Le stop part d'origine « didier » (révision R1 du 25/11) : c'est un arrêt
        que Didier relancera lui-même — d'origine « david », son propre « go » ne le lèverait pas
        au régisseur. Ce n'est pas un arrêt « de Didier » au sens du réfractaire de 120 s : la
        demande vient d'un humain, comme un geste de la bouche."""
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
        self._armer_reprise(now, "regard terminé")
        self.pourquoi_courant = "il s'arrête pour regarder ; il repartira seul"
        self._publier_intention(now)

    def relayer_go(self, origine: str, source: str, now: float) -> None:
        """« go » d'origine « david » (console, tour humain) : lève le verrou, repart tout de
        suite (sans score : sinon il mourait au réfractaire de 10 s), la reprise devient
        caduque. D'origine « didier » : ignoré et journalisé — la bouche n'en émet plus en S1,
        et ce que Didier a arrêté, seule SA reprise le relance."""
        if origine != DAVID:
            self._journal("refus", "« go » proposé par Didier : ignoré (seule sa reprise, après le "
                          "silence, le relance)", source=source, origine=origine)
            return
        if source != "console" and self.verrou == VERROU_CONSOLE:
            # R3 : ce que David a arrêté à la CONSOLE (ou par Route OFF), seul son GO console le
            # relance — un « en route » interprété par la bouche ne suffit pas.
            self._journal("refus", "« go » dit à Didier, mais David a arrêté à la console : seul un GO "
                          "console le relance", source=source, origine=origine)
            return
        self.verrou = None
        self.reprise = None
        self.sorties.append(("chat_move", marche(GO, DAVID)))
        self._journal("relais_go", f"David « go » ({source}) → il repart", source=source, origine=origine)
        self.pourquoi_courant = "David « go »"
        self._publier_intention(now)

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
        refus = self._refus_deplacement(now, ordre=True)
        if refus:
            self._journal("refus", f"{pourquoi} — impossible : {refus}", source="console", cmd=ordre["cmd"],
                          cible=ordre.get("cible"))
            return
        ordre["pourquoi"] = pourquoi
        self.ordre = ordre
        self._journal("console", pourquoi, cmd=ordre["cmd"], cible=ordre.get("cible"))

    def _ordre_console(self, now: float) -> None:
        """L'ordre de la console en attente part (R6) : avant l'arbre, devant toute initiative.
        Une piste visée doit encore être vue (et assez loin) : sinon refus dit, jamais deviné."""
        o, self.ordre = self.ordre, None
        if o is None:
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
                             o["pourquoi"], source="console", cmd=o["cmd"])

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
            self.sorties.append(("chat_move", marche(STOP, DIDIER)))
            regard = bool(e.candidat.detail.get("regard"))
            self._journal("arret_didier", f"lubie « {e.candidat.cible} » réclamée"
                          + (", regard tourné vers elle" if regard else " (sans regard : position inconnue)")
                          + f", pas de refus en {self.r.get('lubie.delai_refus_s'):g} s → il s'arrête",
                          cible=e.candidat.cible, kind="lubie", regard=regard)
            self._armer_reprise(now, f"lubie « {e.candidat.cible} »", cible=e.candidat.cible)
            self.pourquoi_courant = f"arrêté devant « {e.candidat.cible} »" + (
                f" ; repartir ? (après {phrases.s(self.reprise['delai'])} de silence)" if self.reprise else "")
            self._publier_intention(now)
        if e.candidat.deplacement and e.candidat.action != "repartir" and not e.accuse \
                and now - e.t_etape > self.r.get("durees_s.deplacement_accuse") + EPS:
            self._rendre_refractaires(e)
            if e.candidat.action == "bouche":
                # Le régisseur s'est tu (sa réponse aurait accusé ou fini) : le
                # chat doit le savoir, sinon Didier affirme le geste.
                self.sorties.append(("chat_move_reply", reponse_bouche(e.etape, "no_reply", None)))
            self._finir(now, "le régisseur n'a pas donné suite (voir son journal) : il n'a pas bougé")
            return
        if now >= e.fin_prevue - EPS:
            self._finir(now, "c'est fini")

    def _etape_suivante(self, e: Engagement, now: float) -> None:
        etape = e.etapes.pop(0)
        e.accuse, e.t_etape, e.etape, e.nom_ordre = False, now, etape, None
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
                       apres_geste: bool = False) -> None:
        """Didier vient de s'arrêter de lui-même (cf. docstring de module, UNE SEULE REPRISE) :
        il repartira seul après D s de SILENCE, D tiré MAINTENANT dans [reprise.min_s,
        reprise.max_s] par le générateur semé (self.hasard), au dixième de seconde. Un nouvel
        arrêt retire. Jamais sous le verrou de David (règle du 31/10). `apres_geste` : arrêt
        de fin de déplacement — si la route a repris entre-temps, rien à relancer."""
        if self.verrou_david:
            return
        if apres_geste and not self.en_seance:
            # R2 : l'arrêt de fin de geste n'est pas le sien — hors séance, David relance.
            self._journal("reprise_annulee", f"{pourquoi}, hors séance → il ne repartira pas de lui-même")
            return
        delai = round(self.hasard.uniform(self.r.get("reprise.min_s"), self.r.get("reprise.max_s")), 1)
        self.reprise = {"t": now, "silence_depuis": now, "delai": delai, "pourquoi": pourquoi,
                        "cible": cible, "apres_geste": apres_geste, "ordre": None}
        self._journal("reprise_armee", f"{pourquoi} → il repartira après {phrases.s(delai)} de silence",
                      cause=pourquoi, delai_s=delai, cible=cible)

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
        if self.superviseur_absent():
            return
        if now - rep["silence_depuis"] < rep["delai"] - EPS:
            return
        self.reprise = None
        if rep["ordre"] is not None:
            ordre = dict(rep["ordre"], origine=DAVID)
            self._journal("reprise", f"ordre de David suspendu, repris après {phrases.s(rep['delai'])} de silence "
                          f"({phrases.demande(ordre)})", cause=rep["pourquoi"], delai_s=rep["delai"], demande=ordre)
            self._ordre_bouche(ordre, now)
            return
        self.sorties.append(("chat_move", marche(GO, DIDIER)))
        self._journal("reprise", f"reprise : il repart de lui-même ({rep['pourquoi']}, après "
                      f"{phrases.s(rep['delai'])} de silence)", cause=rep["pourquoi"], delai_s=rep["delai"])
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
                                apres_geste=True)
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
