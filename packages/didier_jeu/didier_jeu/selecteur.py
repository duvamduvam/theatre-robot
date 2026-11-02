"""Le SÉLECTEUR de jeu — logique PURE (aucun import ROS), testée sans ROS.

Spec : theatre-robot/docs/spec-A1-selecteur-de-jeu.md (§3 l'arbre et le score,
§8 les précisions du 02/11). Le node (jeu_node.py) appelle les `sur_*` à chaque
message, `tick(now)` à ~10 Hz, puis VIDE `sorties` et publie. Horloge
injectée (secondes, monotone) : aucun sleep dans les tests.

Sorties (tuples, dans l'ordre où elles doivent partir) :
  ("chat_move", payload)       -> jeu/chat_move (régisseur), json.dumps(payload)
  ("animation", nom)           -> animation (nom de séquence)
  ("look", {"angle_deg", "hold_ms"}) -> look (gaze_follower, « regarder » M2)
  ("intention", dict)          -> jeu/intention (latché)
  ("journal", type, payload)   -> fichier JSONL + jeu/journal ; payload porte
                                  TOUJOURS un `pourquoi` non vide (porte T6)

RÈGLES GRAVÉES (chiffres : config/reglages.yaml ; tests : test/test_selecteur.py) :
- « stop » (bouche ou console) : relayé À LA RÉCEPTION, sans score, et verrou
  de tout déplacement jusqu'au « go » (porte T5 : < 200 ms). Le verrou retient
  QUI l'a posé : un « go » de la console (David) lève tout ; un « go » de la
  bouche ne lève que le stop de la bouche — JAMAIS un stop de David ;
- deux décisions différentes jamais à moins de changement.min_s (porte T1) ;
- hystérésis : le meilleur doit dépasser le second de marge pendant duree_s ;
- engagement : une action engagée se finit, sauf offre >= seuil_rupture ;
- naissance de piste -> ligne de décision (choix OU maintien) en <= 1 s (T3) ;
- initiatives spontanées >= 8 s ; arrêts de Didier >= 120 s ; un arrêt est
  RÉCLAMÉ (intention) ET AMORCÉ (regard) puis demandé au régisseur seulement si
  la console n'a dit ni ignore ni va_la pendant lubie.delai_refus_s ;
- reprise : après un arrêt de DIDIER, « repartir ? » puis « go » de lui-même
  après reprise.delai_s, sauf stop/ignore de la console ; JAMAIS de « go »
  automatique après un stop de David ;
- fatigue > seuil : aucun déplacement ; « ignore » : rien vers la cible
  pendant console.ignore_s.
SÉCURITÉ : ce module ne produit AUCUN Twist ; ses seuls effets sur les roues
sont des DEMANDES au régisseur (jeu/chat_move), qui arbitre (spec-aller-voir §3).
"""
import math
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from didier_jeu import arbre
from didier_jeu.offres import Offre, Offres
from didier_jeu.pistes import Pistes
from didier_jeu.pulsions import Pulsions
from didier_jeu.relais import GO, STOP, Verrou
from didier_jeu.repertoire import COMMANDES_REGISSEUR, commande
from didier_jeu.scores import RIEN, Candidat, Contexte, classer

# Commandes de la console (spec §4), gravées avec la page scène.
CONSOLE_CMDS = ("va_la", "joue_avec", "ignore", "reviens", "plus_lent", "stop", "go")
# Angle sous lequel « se tourner vers » une piste est inutile avant d'avancer (°).
ANGLE_MIN_TOURNER_DEG = 5.0
# Tolérance des comparaisons d'échéances : 5,6 − 5,0 vaut 0,5999… en flottant,
# un délai de 0,6 s tomberait un tick trop tard (vu en test).
EPS = 1e-6


def normaliser(texte: str) -> str:
    """Minuscules, sans accents (mots-clés du metteur en scène)."""
    sans = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in sans if unicodedata.category(c) != "Mn")


def angle_vers(pose, cible_xy) -> float:
    """Angle RELATIF (°, + = gauche, REP 103) de la pose (x, y, cap rad) vers
    un point du monde, ramené dans [-180, 180]."""
    x, y, cap = pose
    absolu = math.atan2(cible_xy[1] - y, cible_xy[0] - x)
    rel = math.degrees(absolu - cap)
    return (rel + 180.0) % 360.0 - 180.0


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
    origine: str                      # "didier" | "console"
    etapes: List[dict] = field(default_factory=list)   # chat_move restants (approcher)
    accuse: bool = False              # route_state « goto » vu pour l'étape en cours
    t_etape: float = 0.0
    anim_vue: bool = False            # animation_state a montré NOTRE séquence
    stop_envoye: bool = False         # lubie : le « stop » est parti


class Selecteur:
    def __init__(self, reglages, pools: Dict[str, list], deplacements: Dict[str, dict]):
        self.r = reglages
        self.pools = pools
        self.deplacements = deplacements
        self.offres = Offres()
        self.pistes = Pistes(reglages.get("pistes.perte_s"), reglages.get("pistes.nouvelle_apres_s"),
                             reglages.get("pistes.confiance_min"))
        self.pulsions = Pulsions(reglages)
        self.sorties: List[tuple] = []
        self.objets: Dict[str, tuple] = {}     # nom -> (x, y) ; rehearsal/objects
        self.pose = None                       # (x, y, cap) ; SIM-ONLY (vérité terrain)
        self.route_state: Optional[str] = None
        self.animation_state = ""
        self.joues: Dict[str, float] = {}      # séquence -> dernier t joué (rotation)
        self.en_cours: Optional[Engagement] = None
        self.courante = (RIEN, None)           # (action, cible) affichée
        self.pourquoi_courant = "démarrage : rien ne se passe encore"
        self.t_derniere_decision: Optional[float] = None
        self.derniers: Dict[str, float] = {}   # catégorie réfractaire -> t
        self.derniere_spontanee: Optional[float] = None
        self.leader: Optional[str] = None
        self.leader_depuis = 0.0
        # Qui a posé le verrou d'arrêt (relais.Verrou, revue A1 du 02/11).
        self.verrou = Verrou()
        self.arret_didier: Optional[dict] = None   # {"t", "cible"} : reprise armée
        self.presence_t: Optional[float] = None
        self.ordre: Optional[dict] = None          # {"action", "cible", "t", "cmd"}
        self.ignores: Dict[str, float] = {}        # cible -> t de fin
        self.joue_avec: Optional[dict] = None      # {"cible", "fin"}
        self.plus_lent_fin: Optional[float] = None
        self.metteur: Optional[dict] = None        # {"action", "t", "source"}
        self.piste_regardee: Optional[str] = None
        self.reaction_due: Optional[dict] = None   # {"piste", "t"}
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
               "verrou": self.verrou_stop, "jauges": self.pulsions.jauges()}
        if self.arret_didier is not None:
            out["proposition"] = "repartir ?"
        return out

    def _publier_intention(self, now: float) -> None:
        self.sorties.append(("intention", self.intention(now)))

    def vider_sorties(self) -> List[tuple]:
        out, self.sorties = self.sorties, []
        return out

    # ================================================================ prédicats de l'arbre
    @property
    def verrou_stop(self) -> bool:
        return self.verrou.actif

    def verrouille(self) -> bool:
        return self.verrou_stop

    def superviseur_absent(self) -> bool:
        if self.r.get("superviseur.mode") != "exigeant":
            return False
        return self.presence_t is None or self._now - self.presence_t > self.r.get("superviseur.silence_max_s")

    def ordre_en_cours(self) -> bool:
        return self.ordre is not None

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
        self.reaction_due = {"piste": nee, "t": now}
        self._journal("naissance_piste", f"nouvelle piste {nee} (aucune piste depuis plus de "
                      f"{self.r.get('pistes.nouvelle_apres_s'):g} s)",
                      piste=nee, azimut=round(azimut, 2), hauteur=round(hauteur, 2))

    def sur_poi_event(self, payload, now: float) -> None:
        if not isinstance(payload, dict) or payload.get("event") != "enter" or not payload.get("poi"):
            return
        poi = str(payload["poi"])
        self.offres.naitre(Offre("objet", poi, self.r.get("offres.valeur.objet"), now, self.r.get("offres.ttl_s")))
        self.pulsions.sur_poi()
        self._journal("offre", f"poi_event enter {poi} : offre objet, lubie +{self.r.get('pulsions.lubie.par_poi'):g}",
                      kind="objet", piste=poi)

    def sur_chat_move_bouche(self, valeur, now: float) -> None:
        """La bouche (rehearsal/chat_move) : « stop » relayé sans arbitrage ;
        le reste devient une offre « bouche » que le score pondère."""
        if valeur == STOP:
            self.relayer_stop("bouche", now)
            return
        if valeur == GO and self.verrou_stop:
            self.relayer_go("bouche", now)   # refusé si David a posé le verrou
            return
        if valeur == GO or (isinstance(valeur, dict) and valeur.get("cmd") in COMMANDES_REGISSEUR):
            cible = (valeur.get("objet") or valeur.get("cmd")) if isinstance(valeur, dict) else GO
            self.offres.naitre(Offre("bouche", "bouche", self.r.get("offres.valeur.bouche"), now,
                                     self.r.get("offres.ttl_s"), payload={"demande": valeur, "cible": cible}))
            self._journal("offre", f"la bouche demande {valeur!r} : intention pondérée", kind="bouche",
                          demande=valeur)
            return
        self._journal("refus", f"bouche : demande invalide {valeur!r}", source="bouche")

    def sur_console(self, payload, now: float) -> None:
        if not isinstance(payload, dict):
            self._journal("refus", f"console : objet JSON attendu, reçu {payload!r}", source="console")
            return
        if payload.get("presence") is True:
            self.presence_t = now
        cmd = payload.get("cmd")
        if cmd is None:
            return
        if cmd not in CONSOLE_CMDS:
            self._journal("refus", f"console : commande inconnue {cmd!r}", source="console")
            return
        cible = payload.get("cible")
        cible = str(cible) if isinstance(cible, (str, int)) and str(cible) else None
        if cmd == STOP:
            self.relayer_stop("console", now)
        elif cmd == GO:
            self.relayer_go("console", now)
        elif cmd == "ignore":
            self._ignorer(cible, now)
        elif cmd == "plus_lent":
            self.plus_lent_fin = now + self.r.get("console.plus_lent_s")
            self._journal("console", f"plus lent : réfractaires × {self.r.get('console.plus_lent_facteur'):g} "
                          f"pendant {self.r.get('console.plus_lent_s'):g} s", cmd=cmd)
        elif cmd == "reviens":
            self.joue_avec = None
            self._ordre({"action": "repartir", "cible": None, "cmd": cmd}, now, "reviens : rejoindre la route")
        elif cmd == "joue_avec":
            piste = cible or self._piste_regardee(now)
            if piste is None:
                self._journal("refus", "joue avec lui : aucune piste regardée", source="console", cmd=cmd)
                return
            self.joue_avec = {"cible": piste, "fin": now + self.r.get("console.joue_avec_s")}
            self._journal("console", f"joue avec {piste} : biais console sur cette piste "
                          f"{self.r.get('console.joue_avec_s'):g} s", cmd=cmd, cible=piste)
        elif cmd == "va_la":
            self._va_la(cible, now)

    def sur_situation(self, texte, now: float, source="chat_situation") -> None:
        if not isinstance(texte, str) or not texte.strip():
            return
        mots = self.r.get("metteur_en_scene.mots_cles")
        norm = normaliser(texte)
        for mot, action in mots.items():
            if normaliser(mot) in norm:
                self.metteur = {"action": action, "t": now, "source": source, "mot": mot}
                return

    def sur_mission(self, etat, now: float) -> None:
        if isinstance(etat, dict) and isinstance(etat.get("indication"), str):
            self.sur_situation(etat["indication"], now, source="mission_state")

    def sur_objets(self, objets) -> None:
        if not isinstance(objets, list):
            return
        self.objets = {o["name"]: (float(o["x"]), float(o["y"])) for o in objets
                       if isinstance(o, dict) and isinstance(o.get("name"), str)
                       and isinstance(o.get("x"), (int, float)) and isinstance(o.get("y"), (int, float))}

    def sur_pose(self, x: float, y: float, cap: float) -> None:
        self.pose = (x, y, cap)

    def sur_route_state(self, etat, now: float) -> None:
        self.route_state = etat
        e = self.en_cours
        if e is not None and etat == "goto":
            e.accuse = True

    def sur_route_cause(self, cause, now: float) -> None:
        """route_state_cause (latché, régisseur) : « cmd » = David a coupé la
        route — traité comme un stop de David : reprise désarmée, lubie en
        attente annulée (revue A1, bloquant 3). « boot » : rien."""
        if cause != "cmd":
            return
        e = self.en_cours
        if e is not None and e.candidat.action == "lubie" and not e.stop_envoye:
            self._annuler(now, "David a coupé la route")
        if self.arret_didier is not None:
            self.arret_didier = None
            self._journal("reprise_annulee", "David a coupé la route → pas de reprise automatique")

    def sur_goto_result(self, payload, now: float) -> None:
        e = self.en_cours
        if e is None or not e.candidat.deplacement or e.candidat.action == "repartir":
            return
        resultat = payload.get("result") if isinstance(payload, dict) else None
        if resultat == "arrived" and e.etapes:
            self._etape_suivante(e, now)
            return
        if resultat == "arrived" and e.origine == "didier":
            # Arrêt décidé par Didier (il est allé quelque part de lui-même) :
            # la reprise s'arme, il proposera de repartir.
            self.arret_didier = {"t": now, "cible": e.candidat.cible}
        self._finir(now, f"route_goto_result {resultat} ({payload.get('reason') if isinstance(payload, dict) else ''})")

    def sur_animation_state(self, nom, now: float) -> None:
        self.animation_state = nom if isinstance(nom, str) else ""
        e = self.en_cours
        if e is None or e.candidat.action not in ("accueil", "spontanee"):
            return
        seq = e.candidat.detail.get("sequence")
        if self.animation_state == seq:
            e.anim_vue = True
        elif e.anim_vue:
            self._finir(now, f"séquence {seq} terminée (animation_state {self.animation_state!r})")

    # ================================================================ relais et ordres
    def relayer_stop(self, source: str, now: float) -> None:
        """« stop » : relayé TOUT DE SUITE, sans score ; verrou jusqu'au « go »."""
        self.sorties.append(("chat_move", STOP))
        self.verrou.poser(source)
        self.arret_didier = None    # arrêt de David : jamais de « go » automatique
        self.ordre = None
        self.leader = None
        if self.en_cours is not None and (self.en_cours.candidat.deplacement
                                          or self.en_cours.candidat.action == "lubie"):
            self._annuler(now, f"stop de {source}")
        self._journal("relais_stop", f"stop de {source} relayé sans arbitrage ; verrou jusqu'au go", source=source)
        self.pourquoi_courant = f"stop de {source} : arrêté jusqu'au go"
        self._publier_intention(now)

    def relayer_go(self, source: str, now: float) -> None:
        """« go » : la console (David) lève tout verrou ; la bouche ne lève que
        le sien — un stop de David ne se lève qu'à la console."""
        if not self.verrou.lever(source):
            self._journal("refus", "la bouche dit « go » mais c'est David qui a arrêté : "
                          "seul un go de la console le relance", source=source)
            return
        self.sorties.append(("chat_move", GO))
        self.arret_didier = None
        self._journal("relais_go", f"go de {source} relayé : verrou levé", source=source)
        self.pourquoi_courant = f"go de {source}"
        self._publier_intention(now)

    def _ignorer(self, cible: Optional[str], now: float) -> None:
        cible = cible or self.courante[1] or (self.en_cours.candidat.cible if self.en_cours else None)
        n = 0
        if cible is not None:
            self.ignores[cible] = now + self.r.get("console.ignore_s")
            n = self.offres.tuer_cible(cible)
        e = self.en_cours
        if e is not None and (cible is None or e.candidat.cible == cible):
            self._annuler(now, f"ignore {cible or ''}".strip())
        # Reprise armée : « ignore » (sans cible, ou sur la cible de l'arrêt) la coupe.
        if self.arret_didier is not None and cible in (None, self.arret_didier["cible"]):
            self.arret_didier = None
            self._journal("reprise_annulee", "ignore de la console : pas de go automatique", cible=cible)
        self._journal("console", f"ignore {cible} : {n} offre(s) tuée(s), rien vers elle "
                      f"{self.r.get('console.ignore_s'):g} s", cmd="ignore", cible=cible)

    def _va_la(self, cible: Optional[str], now: float) -> None:
        # Une lubie en attente de son délai de refus : va_la la refuse.
        if self.en_cours is not None and self.en_cours.candidat.action == "lubie" and not self.en_cours.stop_envoye:
            self._annuler(now, "va_la de la console pendant la lubie")
        if cible in self.objets:
            self._ordre({"action": "aller_voir", "cible": cible, "cmd": "va_la"}, now, f"va là : {cible}")
            return
        piste = self.pistes.courante(now)
        if piste is not None and cible == piste.id:
            # Une PISTE : se tourner vers elle puis avancer <= 1 m (§8.2), si
            # superviseur présent et fatigue sous le seuil — vérifié au choix.
            self._ordre({"action": "approcher", "cible": cible, "cmd": "va_la"}, now, f"va là : piste {cible}")
            return
        self._journal("refus", f"va là : cible inconnue {cible!r} (ni objet de rehearsal/objects, ni piste vue)",
                      source="console", cmd="va_la", cible=cible)

    def _ordre(self, ordre: dict, now: float, pourquoi: str) -> None:
        refus = self._refus_deplacement(now)
        if refus:
            self._journal("refus", f"{pourquoi} refusé : {refus}", source="console", cmd=ordre["cmd"],
                          cible=ordre.get("cible"))
            return
        ordre["t"] = now
        self.ordre = ordre
        self._journal("console", pourquoi, cmd=ordre["cmd"], cible=ordre.get("cible"))

    def _refus_deplacement(self, now: float) -> Optional[str]:
        if self.verrou_stop:
            return f"verrou d'arrêt ({', '.join(sorted(self.verrou.sources))}) jusqu'au go"
        if self.superviseur_absent():
            return "superviseur absent"
        if self.pulsions.deplacement_interdit():
            return f"fatigue {self.pulsions.fatigue:.2f} > {self.pulsions.fatigue_seuil:g}"
        return None

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
        if self.arret_didier is not None:
            self.pulsions.pression_route = min(1.0, (now - self.arret_didier["t"]) / self.r.get("reprise.delai_s"))
        else:
            self.pulsions.pression_route = 0.0
        self._expirer(now)
        self._suivre_engagement(now)
        self.arbre.tick_once()
        self._reaction(now)
        return self._decision_tick

    def _expirer(self, now: float) -> None:
        self.ignores = {c: fin for c, fin in self.ignores.items() if fin > now}
        if self.joue_avec is not None and now >= self.joue_avec["fin"]:
            self.joue_avec = None
        if self.plus_lent_fin is not None and now >= self.plus_lent_fin:
            self.plus_lent_fin = None
        if self.metteur is not None and now - self.metteur["t"] > self.r.get("metteur_en_scene.ttl_s"):
            self.metteur = None
        if self.ordre is not None and now - self.ordre["t"] > self.r.get("console.ordre_ttl_s"):
            self._journal("refus", f"ordre {self.ordre['cmd']} non exécuté en "
                          f"{self.r.get('console.ordre_ttl_s'):g} s : abandonné", source="console",
                          cmd=self.ordre["cmd"], cible=self.ordre.get("cible"))
            self.ordre = None

    def _suivre_engagement(self, now: float) -> None:
        e = self.en_cours
        if e is None:
            return
        action = e.candidat.action
        if action == "lubie" and not e.stop_envoye and now - e.t_debut >= self.r.get("lubie.delai_refus_s") - EPS:
            # Ni ignore ni va_la pendant le délai de refus (ils auraient annulé
            # la lubie) : Didier demande l'arrêt au régisseur.
            e.stop_envoye = True
            self.sorties.append(("chat_move", STOP))
            self.arret_didier = {"t": now, "cible": e.candidat.cible}
            self._journal("arret_didier", f"lubie {e.candidat.cible} non refusée en "
                          f"{self.r.get('lubie.delai_refus_s'):g} s : stop demandé au régisseur",
                          cible=e.candidat.cible)
            self.pourquoi_courant = f"arrêté pour {e.candidat.cible} ; repartir ? (go dans " \
                                    f"{self.r.get('reprise.delai_s'):g} s)"
            self._publier_intention(now)
        if e.candidat.deplacement and e.candidat.action != "repartir" and not e.accuse \
                and now - e.t_etape > self.r.get("durees_s.deplacement_accuse") + EPS:
            self._finir(now, f"pas de route_state goto en {self.r.get('durees_s.deplacement_accuse'):g} s : "
                        "demande refusée par le régisseur (voir son journal)")
            return
        if now >= e.fin_prevue - EPS:
            self._finir(now, f"échéance de {action}")

    def _etape_suivante(self, e: Engagement, now: float) -> None:
        etape = e.etapes.pop(0)
        e.accuse, e.t_etape = False, now
        self.sorties.append(("chat_move", etape))

    def _finir(self, now: float, pourquoi: str) -> None:
        fini = self.en_cours.candidat
        self.en_cours = None
        self.courante = (RIEN, None)
        self.pourquoi_courant = f"fin de {fini.action} : {pourquoi}"
        if self.arret_didier is not None:
            self.pourquoi_courant += " ; repartir ?"
        self._journal("fin", pourquoi, action=fini.action, cible=fini.cible)
        self._publier_intention(now)

    def _annuler(self, now: float, pourquoi: str) -> None:
        """Interruption imposée (stop, ignore, va_la) : PAS une décision (porte T1)."""
        fini = self.en_cours.candidat
        self.en_cours = None
        self.courante = (RIEN, None)
        self.pourquoi_courant = f"{fini.action} annulé : {pourquoi}"
        self._journal("annulation", pourquoi, action=fini.action, cible=fini.cible)
        self._publier_intention(now)

    def _reaction(self, now: float) -> None:
        """Porte T3 : une naissance de piste a sa ligne de décision en <= 1 s —
        un choix (taggé dans _decider) ou, faute de choix, un MAINTIEN."""
        due = self.reaction_due
        if due is None or now - due["t"] < self.r.get("reaction.maintien_apres_s") - EPS:
            return
        self.reaction_due = None
        action, cible = self.courante
        offre = next((o for o in self.offres.vivantes(now) if o.kind == "personne" and o.piste == due["piste"]), None)
        valeur = offre.valeur if offre else 0.0
        if self.en_cours is not None:
            raison = (f"garde {action}, engagé ; offre {valeur:.1f} < "
                      f"{self.r.get('engagement.seuil_rupture'):g}")
        elif due["piste"] in self.ignores:
            raison = f"garde {action} : {due['piste']} ignorée par la console"
        elif self.t_derniere_decision is not None and now - self.t_derniere_decision < self.r.get("changement.min_s"):
            raison = (f"garde {action} : dernier changement il y a {now - self.t_derniere_decision:.1f} s "
                      f"< {self.r.get('changement.min_s'):g} s")
        else:
            raison = f"garde {action} : aucun candidat ne domine (hystérésis)"
        self._journal("maintien", raison, action=action, cible=cible, reaction_a=due["piste"])

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
            cands.append(Candidat("approcher", piste.id, o, "curiosite", {"azimut": piste.azimut}))
        if self.pools.get("spontanee"):
            cands.append(Candidat("spontanee", None, None, "ennui"))
        if self.route_state == "on" and not self.verrou_stop and self.arret_didier is None:
            for o in vivantes:
                if o.kind == "objet":
                    cands.append(Candidat("lubie", o.piste, o, "lubie"))
        for o in vivantes:
            if o.kind == "bouche":
                cands.append(Candidat("bouche", o.payload["cible"], o, None, {"demande": o.payload["demande"]}))
        if self.ordre is not None and self.ordre["action"] in ("aller_voir", "repartir"):
            cands.append(Candidat(self.ordre["action"], self.ordre["cible"]))
        if self.arret_didier is not None and self.pulsions.pression_route >= 1.0:
            cands.append(Candidat("repartir", None, None, "pression_route"))
        return [c for c in cands if self._permis(c, deplacement_permis)]

    def _permis(self, c: Candidat, deplacement_permis: bool) -> bool:
        if c.action == RIEN:
            return True
        if c.cible is not None and c.cible in self.ignores:
            return False
        if c.deplacement and (not deplacement_permis or self._refus_deplacement(self._now)):
            return False
        if c.action in ("accueil", "spontanee") and self.animation_state:
            return False   # une séquence a déjà la main (arbitrage actionneurs)
        return True

    def _contexte(self, now: float) -> Contexte:
        console = None
        if self.ordre is not None:
            console = {"action": self.ordre["action"], "cible": self.ordre["cible"]}
        elif self.joue_avec is not None:
            console = {"action": None, "cible": self.joue_avec["cible"]}
        tempo = self.r.get("console.plus_lent_facteur") if self.plus_lent_fin is not None else 1.0
        return Contexte(now=now, jauges=self.pulsions.jauges(),
                        metteur=self.metteur["action"] if self.metteur else None, console=console,
                        derniers=dict(self.derniers), derniere_spontanee=self.derniere_spontanee, tempo=tempo)

    def choisir(self, branche: str, deplacement_permis: bool, interrompt: bool) -> None:
        now = self._now
        cands = self._candidats(now, deplacement_permis)
        if self.en_cours is not None and not interrompt:
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
        origine = "console" if s.considerations.get("console") else "didier"
        if self.en_cours is not None:
            self._annuler(now, f"interrompu par {c.action} ({branche})")
        sortie_ok = self._executer(c, now, origine)
        if not sortie_ok:
            return
        self.leader = None
        self.t_derniere_decision = now
        self.courante = (c.action, c.cible)
        self.pourquoi_courant = s.pourquoi
        if c.action != RIEN:
            self.pulsions.sur_action(c.deplacement)
            if c.categorie is not None:
                self.derniers[c.categorie] = now
            if s.spontanee:
                self.derniere_spontanee = now
            if c.offre is not None:
                self.offres.prendre(c.offre)
        if self.ordre is not None and c.action == self.ordre["action"]:
            self.ordre = None
        payload = {
            "action": c.action, "cible": c.cible, "branche": branche, "score": round(s.total, 3),
            "considerations": s.considerations, "spontanee": s.spontanee, "deplacement": c.deplacement,
            "top3": [{"action": x.candidat.action, "cible": x.candidat.cible, "score": round(x.total, 3)}
                     for x in scores[:3]],
            "offres": [o.resume(now) for o in self.offres.vivantes(now)],
            "pulsions": self.pulsions.jauges(),
        }
        if c.detail.get("sequence"):
            payload["sequence"] = c.detail["sequence"]
        if self.reaction_due is not None:
            payload["reaction_a"] = self.reaction_due["piste"]
            self.reaction_due = None
        self._journal("decision", s.pourquoi, **payload)
        self._decision_tick = Decision(c.action, c.cible, s.pourquoi)
        self._publier_intention(now)

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
            if self.pose is not None and c.cible in self.objets:
                angle = angle_vers(self.pose, self.objets[c.cible])
                hold = r.get("lubie.delai_refus_s") + r.get("durees_s.arret")
                self.sorties.append(("look", {"angle_deg": round(angle, 1), "hold_ms": int(hold * 1000)}))
            fin = now + r.get("lubie.delai_refus_s") + r.get("durees_s.arret")
            self.en_cours = Engagement(c, now, fin, origine)
            return True
        if c.action == "repartir":
            self.sorties.append(("chat_move", GO))
            self.arret_didier = None
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
            etapes = [commande(self.deplacements, "aller_voir", objet=c.cible)]
        elif c.action == "bouche":
            demande = c.detail["demande"]
            if demande == GO:
                self.sorties.append(("chat_move", GO))
                self.arret_didier = None
                self.en_cours = Engagement(c, now, now + r.get("durees_s.relais"), origine, accuse=True)
                return True
            etapes = [demande]
        else:
            return False
        e = Engagement(c, now, now + r.get("durees_s.deplacement_max") * len(etapes), origine, etapes=etapes)
        self.en_cours = e
        self._etape_suivante(e, now)
        return True

    def _prochaine_sequence(self, emploi: str):
        """Rotation déterministe : la séquence jouée il y a le plus longtemps
        (jamais jouée d'abord, dans l'ordre du répertoire)."""
        pool = self.pools[emploi]
        return min(pool, key=lambda s: (self.joues.get(s.nom, -1.0), pool.index(s)))
