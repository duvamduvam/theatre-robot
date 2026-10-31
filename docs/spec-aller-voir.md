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
