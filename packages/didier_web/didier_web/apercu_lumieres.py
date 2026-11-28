"""Aperçu des BANDES LED pour la page scène (lot I0, 22/11) — ce que le ruban du robot afficherait.

Pourquoi : la page scène ENVOIE `robot_lights` mais n'en montrait rien ; David ne pouvait pas
juger un bug joué en sim (le lights_node ne tourne que sur le Pi : `Misc.is_raspberrypi()`).
Le pont écoute déjà `robot_lights` (topic de sa whitelist) : il nourrit ici un MODÈLE de ce que
le vrai `didier_core.actions.lights.Lights` ferait de chaque message reçu, et publie à 2 Hz,
dans son message `state`, la brique en cours (méthode, couleur, depuis quand). La page anime
la rangée de pixels selon la méthode (static/lumieres.js).

Ce modèle reprend le COMPORTEMENT OBSERVABLE du vrai code, relu le 22/11 :
- démarrage sur la lumière `default` ;
- "stop" -> la lumière de REPOS (au départ `default` ; toute entrée marquée `"default": true`
  jouée devient le repos, comme `default dark`) ;
- {"brightness": x} -> luminosité seule, l'animation continue ;
- un nom inconnu est ignoré (l'animation en cours continue) ;
- `msg.time` non nul remplace la durée de l'ENTRÉE (fin d'une entrée non bouclée -> repos), mais
  PAS le minutage des briques, qui suit la durée du JSON (Track.frames sur json_seq[DURATION]) ;
- briques : la brique i s'affiche jusqu'à t_i × durée (la première depuis 0) ; boucle si `loop`.
  Conséquence réelle, visible ici : `scan` et `transfer` commencent par `rainbow` à 0 % et
  passent aussitôt à leur pulsation (verte, rouge) — l'arc-en-ciel ne dure qu'un tick.

Ce n'est PAS le rendu Adafruit pixel par pixel (prévu au lot L2c, ruban virtuel) : la page
dessine chaque méthode d'après ses paramètres de lights_animations.py (chase 3 allumées / 6
éteintes, pas de 0,1 s, etc.), assez pour reconnaître une animation, sans prétendre au pixel.

Python PUR (stdlib) : horloge injectée (`now_ms`), testé sans ROS ni réseau
(packages/didier_core/test/unit/test_apercu_lumieres.py).
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from theatre_contrats.lumiere_visage import CorpsSuitVisage

Chemin = Union["os.PathLike[str]", str]
Rgb = Tuple[int, int, int]

REPOS = "default"
STOP = "stop"
CLE_LUMINOSITE = "brightness"

# Les bandes dessinées par la page : la zone « corps » du ruban (robot_config.py :
# LIGHTS_START_LED 513 -> LIGHTS_END_LED 673, une seule PixelSubset dans lights_node). Une bande
# de plus = une entrée ici, rien d'autre.
BANDES = ({"nom": "corps", "leds": 673 - 513},)

FICHIERS = ("robot_lights.json", "lights_base.json", "colors.json")


def _rgb(nom_couleur: object, couleurs: Dict[str, Any]) -> Optional[Rgb]:
    valeur = couleurs.get(nom_couleur) if isinstance(nom_couleur, str) else None
    if isinstance(valeur, list) and len(valeur) == 3 and all(isinstance(c, int) for c in valeur):
        return (valeur[0], valeur[1], valeur[2])
    return None


def resoudre_briques(lights_base: Dict[str, Any], couleurs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """{brique: {"methode", "rgb"}} : la couleur nommée résolue comme load_light_base() ; une
    brique sans couleur (rainbow…) ou à couleur inconnue a rgb None."""
    briques = {}
    for nom, brique in (lights_base or {}).items():
        if isinstance(brique, dict):
            briques[nom] = {"methode": brique.get("method"), "rgb": _rgb(brique.get("color"), couleurs)}
    return briques


def activations(entree: Dict[str, Any]) -> List[Tuple[float, str]]:
    """[(instant_ms, brique)] de Track.frames : la brique i s'active quand la i-1 finit."""
    duree = entree.get("duration") or 0
    briques = list((entree.get("sequences") or {}).items())
    if not briques:
        return []
    resultat = [(0.0, briques[0][0])]
    for i in range(1, len(briques)):
        resultat.append((float(briques[i - 1][1]) * duree, briques[i][0]))
    return resultat


class EtatLumieres:
    """Ce que le ruban du robot afficherait, d'après les messages `robot_lights` reçus."""

    def __init__(self, lumieres: Dict[str, Any], briques: Dict[str, Dict[str, Any]], now_ms: float) -> None:
        self.lumieres = lumieres or {}
        self.briques = briques
        self.repos = REPOS
        self.luminosite: Optional[float] = None    # None = celle du robot (réglage, non connue ici)
        self.nom: Optional[str] = None
        self._depart = now_ms
        self._duree_ms = 0.0
        self._boucle = False
        self._duree_json = 0.0
        self._activations: List[Tuple[float, str]] = []
        self._jouer(REPOS, 0, now_ms)

    def _jouer(self, nom: str, time_ms: float, now_ms: float) -> bool:
        entree = self.lumieres.get(nom)
        if not isinstance(entree, dict):
            return False
        self.nom = nom
        self._duree_json = float(entree.get("duration") or 0)
        self._duree_ms = float(time_ms) if time_ms else self._duree_json
        self._boucle = bool(entree.get("loop"))
        if "default" in entree:      # le vrai code teste la PRÉSENCE de la clé, pas sa valeur
            self.repos = nom
        self._activations = activations(entree)
        self._depart = now_ms
        return True

    def recevoir(self, valeur: object, time_ms: float, now_ms: float) -> None:
        """Un message `robot_lights` (payload décodé, champ time) arrivé à now_ms."""
        if valeur == STOP:
            self._jouer(self.repos, 0, now_ms)
            return
        if isinstance(valeur, dict):
            if CLE_LUMINOSITE in valeur:
                try:
                    self.luminosite = max(0.0, min(1.0, float(valeur[CLE_LUMINOSITE])))
                except (TypeError, ValueError):
                    pass
            return
        if isinstance(valeur, str):
            self._jouer(valeur, time_ms, now_ms)

    def instant(self, now_ms: float) -> Dict[str, Any]:
        """{"sequence", "brique", "methode", "rgb", "depuis_ms", "luminosite", "repos"} : la
        brique affichée à now_ms ; une entrée non bouclée échue retombe d'abord au repos."""
        if not self._boucle and now_ms - self._depart > self._duree_ms:
            self._jouer(self.repos, 0, self._depart + self._duree_ms)
        brique: Optional[str] = None
        debut = self._depart
        if self._activations:
            ecoule = now_ms - self._depart
            cycle = 0.0
            if self._boucle and self._duree_json > 0:
                cycle = (ecoule // self._duree_json) * self._duree_json
                ecoule -= cycle
            for instant_ms, nom in self._activations:
                if instant_ms <= ecoule:
                    brique, debut = nom, self._depart + cycle + instant_ms
        info = self.briques.get(brique) if brique else None
        return {
            "sequence": self.nom,
            "brique": brique,
            "methode": info["methode"] if info else None,
            "rgb": list(info["rgb"]) if info and info["rgb"] else None,
            "depuis_ms": int(max(0, now_ms - debut)),
            "luminosite": self.luminosite,
            "repos": self.repos,
        }


def signature(json_dir: Chemin) -> Tuple[Optional[Tuple[int, int]], ...]:
    """(mtime_ns, taille) des trois fichiers : changée = relire (retouche par l'éditeur)."""
    resultat: List[Optional[Tuple[int, int]]] = []
    for nom in FICHIERS:
        try:
            st = os.stat(os.path.join(str(json_dir), nom))
            resultat.append((st.st_mtime_ns, st.st_size))
        except OSError:
            resultat.append(None)
    return tuple(resultat)


def charger(json_dir: Chemin) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """(robot_lights, briques résolues) lus dans json_dir ; fichier absent ou illisible = vide
    (l'aperçu montre alors « inconnue », le pont ne tombe jamais pour lui)."""
    def lire(nom: str) -> Dict[str, Any]:
        try:
            with open(os.path.join(str(json_dir), nom), encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
    lumieres, base, couleurs = (lire(n) for n in FICHIERS)
    return lumieres, resoudre_briques(base, couleurs)


def charger_expressions(json_dir: Chemin) -> Dict[str, Any]:
    """expressions.json : seul le champ `corps` (et loop/duration) sert à l'aperçu."""
    try:
        with open(os.path.join(str(json_dir), "expressions.json"), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class Apercu:
    """L'aperçu tenu par le pont : relit les fichiers s'ils ont changé (sans perdre ce qui joue :
    le modèle reprend avec les nouvelles tables à la prochaine commande).

    Le corps suit aussi le visage (theatre_contrats.lumiere_visage, la même règle que
    lights_node) : le pont lui passe les messages `face`. Le retour seul du visage au repos à la
    fin d'une expression non bouclée est modélisé ici (le vrai Face le fait de lui-même)."""

    def __init__(self, json_dir: Chemin, now_ms: float) -> None:
        self.json_dir = json_dir
        self._signature = signature(json_dir)
        lumieres, briques = charger(json_dir)
        self.etat = EtatLumieres(lumieres, briques, now_ms)
        self.expressions = charger_expressions(json_dir)
        self.arbitre = CorpsSuitVisage(repos=REPOS)
        self._fin_visage: Optional[float] = None
        self.arbitre.visage(self._corps(REPOS))

    def _corps(self, expression: str) -> Optional[str]:
        entree = self.expressions.get(expression)
        return entree.get("corps") if isinstance(entree, dict) else None

    def _relire_si_modifie(self) -> None:
        sig = signature(self.json_dir)
        if sig != self._signature:
            self._signature = sig
            self.etat.lumieres, self.etat.briques = charger(self.json_dir)

    def recevoir(self, valeur: object, time_ms: float, now_ms: float) -> None:
        """Un message `robot_lights` : commande explicite du corps."""
        self._relire_si_modifie()
        self.arbitre.commande(valeur)
        self.etat.recevoir(valeur, time_ms, now_ms)

    def recevoir_visage(self, valeur: object, time_ms: float, now_ms: float) -> None:
        """Un message `face` : le visage change (ou revient au repos sur « stop »)."""
        nom = REPOS if valeur == STOP else valeur
        if not isinstance(nom, str):
            return
        self.expressions = charger_expressions(self.json_dir)  # relu : une retouche compte tout de suite
        if nom not in self.expressions:
            return  # expression inconnue : le vrai Face l'ignore aussi
        entree = self.expressions.get(nom, {})
        duree = float(time_ms) if time_ms else float(entree.get("duration") or 0)
        self._fin_visage = None if entree.get("loop") or nom == REPOS else now_ms + duree
        self._jouer_corps(self.arbitre.visage(self._corps(nom)), now_ms)

    def _jouer_corps(self, nom: Optional[str], now_ms: float) -> None:
        if nom:
            self.etat.recevoir(nom, 0, now_ms)

    def instant(self, now_ms: float) -> Dict[str, Any]:
        if self._fin_visage is not None and now_ms > self._fin_visage:
            self._fin_visage = None
            self._jouer_corps(self.arbitre.visage(self._corps(REPOS)), now_ms)
        if self.arbitre.explicite and self.etat.instant(now_ms)["sequence"] == self.etat.repos:
            self._jouer_corps(self.arbitre.fin_commande(), now_ms)
        return dict(self.etat.instant(now_ms), bandes=[dict(b) for b in BANDES])
