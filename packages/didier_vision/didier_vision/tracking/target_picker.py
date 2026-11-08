"""Choix de la cible à suivre + conversion bbox -> azimut/élévation normalisés.

QUOI : logique PURE (aucun import cv2/mediapipe, aucun import de
       didier_vision.tracking.detector) — testable en CI sans dépendance lourde,
       cf. test/unit/test_target_picker.py qui doit rester vert
       même sur une machine sans mediapipe installé. Les détections passées
       en entrée sont de simples objets avec les attributs x1/y1/x2/y2/score
       (duck-typing : didier_vision.tracking.detector.Detection convient, mais
       n'importe quel objet compatible aussi — c'est volontaire, ça évite
       tout couplage entre ce module et le backend de détection).
POURQUOI séparé de detector.py : c'est la seule partie du pipeline qui doit
       être vérifiable par des tests unitaires rapides et déterministes (pas
       de caméra, pas de modèle .tflite) — le contrat ARCHITECTURE.md
       (/vision/person, x=azimut, y=élévation, z=confiance) est entièrement
       défini ici, indépendamment du choix de backend de détection.

Contrat de sortie (ARCHITECTURE.md) :
  x = azimut normalisé [-1..1], 0 = face caméra, +1 = bord DROIT de l'image
      VU DE LA CAMÉRA (donc PAS mirroré pour un observateur qui ferait face
      à la caméra : le pixel de colonne max de l'image correspond à +1).
      Documenté explicitement ici car le robot (gaze_follower côté
      dadou_robot_ros) en aura besoin pour le sens de rotation du cou — un
      mirroring introduit par erreur ferait tourner la tête du mauvais côté.
  y = élévation normalisée [-1..1], +1 = haut de l'image.
  z = confiance [0..1] de la détection retenue (score brut du backend, PAS
      lissé — seuls azimut/élévation/hauteur sont lissés par EMA, cf. plus bas).

Extension 2026-07-11 (suivi roues, person_follower côté dadou_robot_ros) :
  height = hauteur de la boîte / hauteur de l'image, [0..1], lissée par EMA.
      C'est le PROXY DE DISTANCE d'une caméra monoculaire : une personne
      debout proche remplit l'image (height élevé), loin elle est petite.
      La HAUTEUR plutôt que l'aire : l'aire varie avec la pose (bras écartés),
      la hauteur d'une personne debout ne varie qu'avec la distance.
      Publiée sur le topic /vision/person_box (le topic /vision/person
      historique reste inchangé — contrat gelé consommé par gaze_follower).
"""
from __future__ import annotations

from typing import NamedTuple, Optional


class Target(NamedTuple):
    """Cible retenue pour UNE frame — azimut/élévation/hauteur lissés EMA,
    confiance brute. NamedTuple : les consommateurs nomment les champs
    (result.azimuth) plutôt que de compter les positions."""
    azimuth: float
    elevation: float
    confidence: float
    height: float


def _azimuth(x1: float, x2: float, image_width: float) -> float:
    """Centre de boîte -> azimut [-1..1]. x pixel 0 (bord gauche de l'image
    telle que vue par la caméra) -> -1 ; x pixel image_width (bord droit) -> +1.
    Pas de mirroring : cf. docstring du module, c'est un choix de contrat
    documenté, pas un oubli."""
    if image_width <= 0:
        return 0.0
    cx = (x1 + x2) / 2.0
    azimuth = 2.0 * (cx / image_width) - 1.0
    return max(-1.0, min(1.0, azimuth))


def _elevation(y1: float, y2: float, image_height: float) -> float:
    """Centre de boîte -> élévation [-1..1]. y pixel 0 (haut de l'image) -> +1
    (les coordonnées image croissent vers le bas, l'élévation croît vers le haut :
    inversion volontaire)."""
    if image_height <= 0:
        return 0.0
    cy = (y1 + y2) / 2.0
    elevation = 1.0 - 2.0 * (cy / image_height)
    return max(-1.0, min(1.0, elevation))


def _height_ratio(y1: float, y2: float, image_height: float) -> float:
    """Hauteur de boîte / hauteur d'image, borné [0..1] — le proxy de distance
    (cf. docstring de module). Borné pour les boîtes aberrantes (y2 < y1 ou
    dépassant l'image), comme _area_ratio."""
    if image_height <= 0:
        return 0.0
    return max(0.0, min(1.0, (y2 - y1) / image_height))


def _area_ratio(x1: float, y1: float, x2: float, y2: float,
                 image_width: float, image_height: float) -> float:
    """Aire de la boîte / aire de l'image, dans [0..1] (borné en cas de boîte
    aberrante). Sert à pondérer le choix de cible : une personne proche de la
    caméra (donc une grosse boîte) ou centrale prime sur une silhouette
    lointaine ou en bord de cadre — plus pertinent pour un robot de théâtre
    qui doit suivre l'acteur/la personne qui LUI FAIT FACE, pas n'importe qui
    qui traverse au fond de la scène."""
    image_area = float(image_width * image_height)
    if image_area <= 0:
        return 0.0
    box_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return max(0.0, min(1.0, box_area / image_area))


class TargetPicker:
    """Sélectionne une personne à suivre parmi les détections d'une frame,
    lisse azimut/élévation par EMA, et réinitialise son état quand la cible
    est perdue.

    Paramètres :
      ema_alpha : poids de la NOUVELLE mesure dans le lissage exponentiel
          (ema = alpha*brut + (1-alpha)*ema_précédent). ~0.4 par défaut :
          assez réactif pour suivre un déplacement réel, assez lissé pour
          que le cou du robot ne vibre pas au bruit de détection frame à
          frame (bbox qui gigote de quelques pixels d'une frame à l'autre).
      adherence_radius : distance MAXIMALE en azimut brut (unité normalisée
          [-1..1], donc 0.3 ~ 30% de la largeur d'image) entre une détection
          et le dernier azimut retenu pour bénéficier du bonus d'adhérence.
      adherence_bonus : multiplicateur de score appliqué à une détection
          proche de la cible précédente. POURQUOI l'adhérence : avec du
          public devant la caméra, plusieurs personnes peuvent avoir des
          boîtes de score/aire comparables d'une frame à l'autre ; sans
          préférence pour la continuité, la cible choisie sauterait d'une
          personne à l'autre à chaque frame (choix instable, cou qui
          "saccade" d'une personne à l'autre au lieu de suivre calmement
          celle déjà engagée).
      designated_radius : distance MAXIMALE en azimut brut entre une
          détection et le dernier azimut de la cible DÉSIGNÉE (cf. designate()
          ci-dessous) pour être considérée comme étant toujours elle. Rôle
          analogue à adherence_radius, mais pour le régime désigné : ici
          c'est le SEUL critère (pas de pondération par score/aire), la
          cible est une identité verrouillée, pas la "meilleure" boîte.
    """

    def __init__(self, ema_alpha: float = 0.4, adherence_radius: float = 0.3,
                 adherence_bonus: float = 1.5, designated_radius: float = 0.3):
        self._ema_alpha = ema_alpha
        self._adherence_radius = adherence_radius
        self._adherence_bonus = adherence_bonus
        self._designated_radius = designated_radius
        # Drapeaux de désignation par bouton (2026-09-14, cf. étude
        # identification-acteur) : INITIALISÉS ICI, PAS dans _reset_state().
        # C'est volontaire et c'est LE piège de cette fonctionnalité : si
        # _reset_state() les effaçait, une simple frame sans détection (David
        # masqué un instant) ferait perdre la désignation — cf. update() et
        # le commentaire détaillé sur ce point précis.
        self._designated = False
        self._designation_pending = False
        self._reset_state()

    def _reset_state(self) -> None:
        """Remet à zéro le LISSAGE seul (EMA + dernier azimut brut) — ne
        touche JAMAIS à _designated/_designation_pending (cf. __init__ et
        designate()/release() : ce sont les SEULS points qui les modifient)."""
        self._ema_azimuth: Optional[float] = None
        self._ema_elevation: Optional[float] = None
        self._ema_height: Optional[float] = None
        # Azimut BRUT (pas lissé) de la dernière cible retenue : sert de
        # référence à l'adhérence (et, en régime désigné, à la fenêtre de
        # ré-acquisition designated_radius), comparé à l'azimut BRUT des
        # nouvelles détections (comparer du brut à du brut, pas du brut à du
        # lissé).
        self._last_raw_azimuth: Optional[float] = None

    def reset(self) -> None:
        """Repart de zéro : appelé explicitement en cas de perte de la cible
        (SANS désignation active — cf. update(), qui gère différemment la
        frame vide quand une désignation est en cours, précisément pour
        garder _last_raw_azimuth intact et permettre la ré-acquisition).
        POURQUOI un reset et pas juste "arrêter de publier" : si on gardait
        le vieux lissage EMA, la PROCHAINE personne détectée hériterait d'un
        état lissé qui n'a rien à voir avec elle (fantôme de la personne
        précédente) — reset garantit que la nouvelle personne repart d'une
        mesure brute, pas d'un mélange avec le passé.
        Ne touche PAS aux drapeaux de désignation (cf. _reset_state), mais
        efface bien _last_raw_azimuth : un appelant qui veut PRÉSERVER ce
        repère (cas de la frame vide sous désignation) ne doit PAS passer
        par cette méthode — cf. update()."""
        self._reset_state()

    def designate(self) -> None:
        """Arme une désignation (appui bouton du gant, cf. person_tracker_node) :
        la PROCHAINE frame comportant au moins une détection choisira la
        personne la plus CENTRÉE (cf. update(), régime a), sans égard au
        score/à l'aire ni à l'adhérence historique.
        Remet à zéro le lissage EMA pour la MÊME raison que reset() : la
        personne désignée ne doit pas hériter du fantôme EMA de la cible
        précédente. MAIS le drapeau _designation_pending posé juste après
        DOIT SURVIVRE à cette remise à zéro — _reset_state() ne le touche
        pas exprès (cf. sa docstring) : si l'ordre était inversé côté
        _reset_state, l'armement serait effacé avant même d'avoir pu
        s'appliquer à la prochaine frame."""
        self._reset_state()
        self._designation_pending = True

    def release(self) -> None:
        """Annule la désignation et revient au comportement historique
        (area_ratio * score + adhérence, régime c de update()). Ne touche
        PAS au lissage EMA : la personne actuellement suivie ne doit pas
        "sauter" visuellement au moment du relâchement du bouton, seul le
        CRITÈRE de sélection change à la prochaine frame."""
        self._designated = False
        self._designation_pending = False

    def update(self, detections: list, image_width: float,
               image_height: float) -> Optional[Target]:
        """Traite les détections d'UNE frame. Retourne un Target (azimut,
        élévation, hauteur lissés + confiance brute), ou None si aucune
        détection retenue (silence = personne perdue, cf. contrat
        ARCHITECTURE.md — c'est à l'appelant [le node] de ne rien publier
        dans ce cas, ce module se contente de renvoyer None).

        Trois régimes, dans cet ordre :
          (a) désignation en attente (designate() vient d'être appelé, pas
              encore de frame avec du monde depuis) : la détection la plus
              CENTRÉE gagne — c'est le seul critère que l'opérateur contrôle
              en se plaçant face au robot avant d'appuyer.
          (b) cible déjà désignée : seule compte la proximité en azimut brut
              avec la dernière position connue de CETTE personne (fenêtre
              designated_radius) — score/aire/adhérence n'entrent plus en jeu.
          (c) aucune désignation : comportement historique, inchangé.
        """
        if not detections:
            # PIÈGE (cf. étude identification-acteur §désignation) : un
            # self.reset() INCONDITIONNEL ici effacerait _last_raw_azimuth
            # (cf. _reset_state) — hors ce dernier est le SEUL repère qui
            # permet au régime (b) de reconnaître David à son retour. Si on
            # l'efface au premier hoquet de détection, la désignation "survit"
            # au sens des drapeaux (_designated reste True) mais devient
            # inutile en pratique : plus aucune référence à comparer, la
            # PROCHAINE personne détectée — n'importe qui — serait acceptée
            # comme si elle avait un azimut "proche de None".
            # Donc : désignation active -> on remet seulement le LISSAGE EMA
            # à zéro (pas de fantôme de mesure lissée à la ré-acquisition),
            # en conservant _last_raw_azimuth intact. Pas de désignation ->
            # comportement historique inchangé (reset() complet).
            # Dans les deux cas, _designated/_designation_pending ne sont
            # JAMAIS effacés ici (cf. _reset_state, designate(), release()) :
            # une désignation survit ainsi à une ou plusieurs frames sans
            # détection (David masqué un instant, ou sorti du champ puis
            # revenu). Pas d'expiration voulue : si David part 2 minutes, le
            # robot reste désigné et se tait (aucune publication) jusqu'à son
            # retour PRÈS DU MÊME AZIMUT — pour reprendre ailleurs, il
            # ré-appuie (release()/designate()), pas de minuteur caché.
            if self._designated or self._designation_pending:
                self._ema_azimuth = None
                self._ema_elevation = None
                self._ema_height = None
            else:
                self.reset()
            return None

        def _components(det):
            """Azimut/élévation/score/hauteur bruts d'UNE détection — factorisé
            pour ne pas dupliquer les 3 conversions dans les 3 régimes."""
            azimuth = _azimuth(det.x1, det.x2, image_width)
            elevation = _elevation(det.y1, det.y2, image_height)
            height = _height_ratio(det.y1, det.y2, image_height)
            return azimuth, elevation, det.score, height

        if self._designation_pending:
            # (a) Désignation en attente : la détection la plus CENTRÉE
            # gagne, quels que soient son score/son aire (cf. docstring
            # ci-dessus — POURQUOI : c'est le seul signal que l'opérateur
            # maîtrise directement).
            azimuth, elevation, confidence, height = min(
                (_components(det) for det in detections),
                key=lambda components: abs(components[0]),
            )
            self._designation_pending = False
            self._designated = True

        elif self._designated:
            # (b) Cible déjà désignée : on cherche, parmi les détections de
            # cette frame, celle dont l'azimut BRUT est le plus proche de
            # _last_raw_azimuth (l'identité de la personne, pas la qualité de
            # sa boîte) — et on l'accepte seulement si l'écart reste dans la
            # fenêtre designated_radius.
            candidate = None
            candidate_gap = None
            for det in detections:
                azimuth_candidate = _azimuth(det.x1, det.x2, image_width)
                gap = abs(azimuth_candidate - self._last_raw_azimuth)
                if gap <= self._designated_radius and (
                        candidate_gap is None or gap < candidate_gap):
                    candidate = det
                    candidate_gap = gap
            if candidate is None:
                # Personne dans la fenêtre cette frame (angle mort, dos
                # tourné, badaud passé devant...) : silence, PAS perte de la
                # désignation. _designated et _last_raw_azimuth restent EN
                # L'ÉTAT (on ne les touche pas ici) pour permettre la
                # ré-acquisition dès que David repasse près de cet azimut —
                # cf. contrat du régime (b) dans la docstring de la méthode.
                return None
            azimuth, elevation, confidence, height = _components(candidate)

        else:
            # (c) Comportement historique, STRICTEMENT inchangé.
            best_weight = None
            best = None  # (azimuth_brut, elevation_brut, score, height_brut)
            for det in detections:
                azimuth = _azimuth(det.x1, det.x2, image_width)
                elevation = _elevation(det.y1, det.y2, image_height)
                height = _height_ratio(det.y1, det.y2, image_height)
                area_ratio = _area_ratio(det.x1, det.y1, det.x2, det.y2,
                                          image_width, image_height)
                weight = area_ratio * det.score
                if (self._last_raw_azimuth is not None
                        and abs(azimuth - self._last_raw_azimuth) <= self._adherence_radius):
                    weight *= self._adherence_bonus
                if best_weight is None or weight > best_weight:
                    best_weight = weight
                    best = (azimuth, elevation, det.score, height)

            azimuth, elevation, confidence, height = best

        # EMA (commun aux trois régimes) : pas de valeur précédente (premier
        # calcul après un reset) -> on part directement de la mesure brute,
        # ne PAS lisser artificiellement vers 0 (une personne qui apparaît
        # sur le bord de l'image ne doit pas sembler démarrer du centre).
        self._ema_azimuth = (
            azimuth if self._ema_azimuth is None
            else self._ema_alpha * azimuth + (1.0 - self._ema_alpha) * self._ema_azimuth
        )
        self._ema_elevation = (
            elevation if self._ema_elevation is None
            else self._ema_alpha * elevation + (1.0 - self._ema_alpha) * self._ema_elevation
        )
        # Même lissage pour la hauteur : c'est elle qui commandera la vitesse
        # linéaire du suivi roues — le bruit frame à frame de la bbox ne doit
        # pas se transformer en à-coups d'avance/recul.
        self._ema_height = (
            height if self._ema_height is None
            else self._ema_alpha * height + (1.0 - self._ema_alpha) * self._ema_height
        )
        self._last_raw_azimuth = azimuth

        return Target(self._ema_azimuth, self._ema_elevation, confidence, self._ema_height)
