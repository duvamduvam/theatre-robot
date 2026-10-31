# Spec — « Aller voir » : le corps fait ce que la conversation dit (lot M1)

*Écrite le 2026-10-31, après « je lui dis va voir les anneaux et il refuse ».
Décisions de David : `etude-interaction.md` §10.4 et §10.5 bis. Premier cas de
la couche d'intentions de mouvement ; « tour de », « contourner », allure
viendront ensuite sur le même contrat.*

**SIM-ONLY.** Le cheminement lit `/ground_truth/odom` (vérité terrain Gazebo) ;
`robot_rehearsal` n'est jamais dans `robot_bringup`. Rien ici ne touche le vrai
robot ni la chaîne roues aval (mux, deadman, wheels).

## 1. Ce que voit David

« Va voir les anneaux » → Didier dit qu'il y va → il roule jusqu'à ~1,5 m de
l'objet (demi-tour s'il l'a dépassé), **pivote face à lui**, s'arrête, le
commente. « Stop » à tout instant l'arrête. Pour reprendre la route :
« go »/« on repart » (ou curseur, Route ON) — il rejoint son itinéraire.

## 2. Contrat (gravé des deux côtés)

### 2.1 Vocabulaire d'objets — `rehearsal/objects` (régisseur → chat_node)

StringTime, **latché** (TRANSIENT_LOCAL depth 1), publié au démarrage du
régisseur : JSON liste `[{"name": "anneaux", "desc": "bagues géantes"}, …]`,
construit depuis l'itinéraire (`config/chantiers.yaml`). Nouveau champ YAML
par POI : `desc` (≤ 6 mots, ce qu'on VOIT) et `alias` (liste de mots que
David peut dire). Absent → `desc` = nom, `alias` = [].

chat_node (vision), seulement si le mouvement à la voix est branché : ajoute
au prompt de marche la liste « Objets que tu peux aller voir : anneaux
(bagues géantes), flaque (…), … » — remplacée à chaque nouveau message, la
session LLM n'est PAS réinitialisée.

### 2.2 Intention — `rehearsal/chat_move` (chat_node → régisseur), étendu

Le payload actuel reste valide (`"go"` / `"stop"`, JSON chaîne). Ajout :
JSON objet `{"cmd": "aller_voir", "objet": "<texte>"}`. Côté bouche : clé de
fin de réplique `"aller_voir": "<nom de la liste>"` (même règles que
`marche` : normalisée, jamais en tour spontané — un tour spontané ne met
jamais Didier en mouvement, revue B1 du 23/10). Si la réplique porte à la
fois `marche` et `aller_voir`, `aller_voir` gagne sauf si `marche` vaut
`stop` (le stop gagne toujours).

### 2.3 Ordre de manœuvre — `route_goto` (régisseur → route_driver)

StringTime JSON : `{"name": "anneaux", "x": 78.42, "y": 4.19, "standoff": 1.5}`
ou `"cancel"`. Le route_driver est le SEUL à produire le Twist (créneau
`cmd_vel_follow`, prio 20) ; le régisseur ne fait qu'ordonner.

### 2.4 État — `route_state` étendu

Valeurs : `on` / `off` (inchangées) + `goto` (manœuvre en cours) +
`arrived` (arrêté face à l'objet). La page affiche « va voir : anneaux » /
« devant : anneaux ».

## 3. Arbitrage (régisseur)

- Objet résolu par correspondance normalisée (minuscules, sans accents, sans
  article) sur `name` + `alias`. Inconnu → refus journalisé `aller_voir
  {"effect": "unknown"}`, rien ne bouge.
- **Jamais contre un `off` de David** : si `route_state_cause` = `cmd` (David
  a coupé la route), refus `{"effect": "route_off_by_david"}`.
- Distance max 40 m depuis la pose courante, sinon refus `too_far`.
- Accepté hors séance comme en séance : c'est David qui le demande (décision
  §10.2 : « David arrête et relance quand il veut »).
- Un arrêt vocal en cours est levé par l'acceptation (même vitesse retenue
  rendue que le « go », jamais au-dessus du fader ni d'une panne batterie).

## 4. Manœuvre (route_driver, logique PURE dans `robot_rehearsal/goto.py`)

Machine à états, un `tick(pose, now)` → Twist borné, testée sans ROS :

1. **ALIGN** : pivot sur place vers le point d'arrêt P = cible − standoff le
   long de l'axe (pose → cible). `|ω| ≤ 0,6 rad/s`, `v = 0`.
2. **DRIVE** : avance vers P, cap corrigé (P), `v ≤` vitesse du fader ×
   `ABS_MAX_LIN`, rampe d'accélération identique au suivi de route.
3. **FACE** : pivot face à la cible, `|ω| ≤ 0,6`.
4. **ARRIVED** : zéro franc, puis silence (le mux retombe, le deadman fait
   le reste). Reste arrêté jusqu'à un go / Route ON / goto suivant.

Sûreté (tests gravés + mutation) :
- `route off`, `stop`, `cancel` → zéro franc IMMÉDIAT, manœuvre abandonnée.
- Odométrie périmée (même seuil que le suivi) → zéro.
- Délai max 60 s et distance parcourue max 1,5 × distance initiale → abandon,
  zéro, journal `goto_abort`.
- Jamais `ABS_MAX_LIN` / `ABS_MAX_ANG` dépassés (bornes de contracts.py).
- Reprise (go) : le suivi d'itinéraire repart vers le **waypoint le plus
  proche devant** la pose courante (pas vers l'ancien index s'il est
  derrière).

## 5. Hors lot (noté)

Pas d'évitement d'obstacle (ligne droite ; les objets Gazebo bloquent
physiquement — acceptable en sim, interdit au réel). « Tour de »,
« contourner », allure : lots suivants, même contrat (§2.2 `cmd`). Relance
autonome 90 s (§10.5) : lot à part.

## 6. Vérification

Tests purs (goto.py, résolution d'objet, arbitrage, prompt) ; puis en sim :
« va voir les anneaux » depuis 20 m avant, depuis 5 m après (demi-tour),
« stop » en pleine manœuvre (< 1 s), objet inconnu (refus joué), « go » après
arrivée (rejoint la route). Revue adversariale avant déploiement.

---

## 7. Lot M2 — « regarder » et « tourner » (31/10, même soirée)

David : « je lui propose de regarder à droite, il me dit qu'il ne peut pas ».
Deux gestes DISTINCTS, parce que la caméra est fixée au BUSTE (pas à la
tête, cf. mémoire suivi de personne 14/09) : tourner la tête est du jeu,
seul le corps qui pivote fait VOIR ailleurs.

### 7.1 « Regarder » — tête (cou + yeux), PROD-compatible

- Bouche : clé de fin `"regarder": "gauche" | "droite" | "devant"`.
- chat_node publie sur le nouveau topic `look` : StringTime JSON
  `{"dir": "gauche"|"droite"|"devant", "hold_ms": 4000}` (hold borné
  1000-8000 ms côté consommateur).
- Consommateur : `gaze_follower_node` (robot/nodes, PROD). À réception, il
  pose le cou (et les yeux en mode robot) à la consigne de la direction
  (gauche/droite = ±70 % de sa course utile, devant = centre), la TIENT
  `hold_ms` en ignorant les personnes, puis reprend le suivi s'il était actif
  (sinon revient au centre). Respecte l'arbitrage existant : silencieux tant
  qu'une animation a la main (`animation_state`). Rampe/amorti existants
  inchangés (ne pas monter le gain). Pas de roues.
- Autorisé aussi en tour spontané (aucun déplacement).

### 7.2 « Tourner » — pivot du corps, SIM-ONLY

- Bouche : clé `"tourner": "gauche" | "droite" | "demi_tour"`.
- Intention sur `rehearsal/chat_move` : `{"cmd": "tourner", "sens": ...}`.
- Régisseur : mêmes refus que `aller_voir` (route OFF par David, pas de pose) ;
  accepté hors séance ; lève l'arrêt vocal comme go ; stop/abort → cancel.
- route_driver : ordre `route_goto` `{"turn_rad": +1.5708|-1.5708|3.1416}`
  → manœuvre PIVOT seule (réutilise FACE de goto.py : cap cible = cap
  courant + turn_rad, ω ≤ 0,6 rad/s, fader 0 = rien, timeout 15 s, pose non
  finie/périmée = zéro, stop/off/cancel = zéro immédiat) → `arrived`.
- Jamais en tour spontané (mise en mouvement, revue B1).
- Prompt de marche : retirer « tu ne sais ni tourner ni faire demi-tour » ;
  il sait aller voir un objet de la liste, tourner la tête (regarder), et
  pivoter sur place ; il ne sait toujours ni contourner ni reculer.
