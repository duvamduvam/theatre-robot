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

## 7. Lot M2 — gestes chiffrés « regarder », « tourner », « avancer » (31/10)

David : « je lui propose de regarder à droite, il me dit qu'il ne peut pas ».
Décision de David (même soirée) : **pas de cas figés, des GESTES GÉNÉRAUX
CHIFFRÉS**, composables plus tard par un planificateur. Les noms
(gauche/droite/demi-tour) restent acceptés en compat. Convention commune :
angle **+ = gauche** (ROS, REP 103, z vers le haut).

« Regarder » et « tourner » sont DISTINCTS parce que la caméra est fixée au
BUSTE (pas à la tête, cf. mémoire suivi de personne 14/09) : tourner la tête
est du jeu, seul le corps qui pivote fait VOIR ailleurs.

### 7.1 « Regarder » — tête (cou + yeux), PROD-compatible

- chat_node publie sur le topic `look` : StringTime JSON
  `{"angle_deg": <float, + = gauche>, "hold_ms": <int>}`. Compat :
  `{"dir": "gauche"|"droite"|"devant"}` (= +course, −course, 0).
- Consommateur : `gaze_follower_node` (robot/nodes, PROD), logique pure dans
  `robot/move/gaze_control.py` (`parse_look`, état `LOOK`).
- Angle -> azimut ÉQUIVALENT (celui d'une personne vue sous cet angle), puis
  le MÊME mapping que le suivi : sens et gains validés le 12/07, cou et yeux
  (miroir) du bon côté sans nouveau réglage. Échelle = course utile du COU
  (± gain consignes = gain × 180/99 °, soit ±36,4° au gain 20) : le cou
  atteint l'angle demandé ; au-delà, **saturé** à la course et journalisé
  (±90° -> ±36,4°). Les yeux font ce qu'ils font pour une personne sous cet
  angle (gain propre).
- `hold_ms` borné 1000-8000 côté consommateur (absent/illisible -> 4000).
  La tenue court à partir de l'ARRIVÉE sur la consigne ; les personnes sont
  ignorées pendant la tenue. Puis retour lent au centre, interrompu par la
  première détection si le suivi est ON (reprise du suivi). Marche suivi ON
  comme OFF. « gaze off » EXPLICITE coupe le geste (la télécommande prime) ;
  une republication d'`animation_state` au repos, non.
- Anti-flux (revue M2) : au plus 3 réarmements de suite sans retour au
  suivi / au repos ; au-delà, la tenue en cours est coupée et tout `look`
  est ignoré 4 s.
- Payload hostile (entier géant, imbrication profonde) : refus journalisé,
  jamais fatal ; `gain <= 0` refusé au démarrage du node.
- Arbitrage existant : ordre ignoré tant qu'une animation a la main
  (`animation_state`), geste coupé net quand une séquence démarre. Rampe /
  amorti / gains inchangés. Pas de roues. Mode sim (`/neck/position`) et
  robot (`neck` + yeux).
- Autorisé aussi en tour spontané (aucun déplacement).

### 7.2 « Tourner » — pivot du corps, SIM-ONLY

- Intention sur `rehearsal/chat_move` : `{"cmd": "tourner", "angle_deg":
  <float signé, + = gauche>}`, 0 < |a| ≤ 180 (sinon refus `invalid`
  `hors_bornes`, jamais saturé). Compat `{"sens": "gauche"|"droite"|
  "demi_tour"}` = +90 / −90 / +180 (demi-tour par la gauche).
- Régisseur : mêmes refus que `aller_voir` (route OFF par David, pas de
  pose), journal `tourner` ; accepté hors séance ; lève l'arrêt vocal comme
  go ; stop/abort -> cancel.
- route_driver : `route_goto` `{"turn_rad": radians(a)}` -> pivot seul (FACE
  de goto.py) : rotation INTÉGRÉE depuis la première pose fraîche (pas de
  repli ±π : le sens d'un demi-tour ne dépend pas du bruit), |ω| ≤ 0,6 ×
  facteur du fader (plancher 0,15 rad/s si facteur > 0 ; s'applique aussi
  aux pivots d'« aller voir »), fader 0 = rien, timeout 15 s, translation
  ≤ 1 m (poussé = abandon), calage (|ω| > 0,2 et rotation < 0,05 rad sur
  2 s -> `stalled`), pose non finie/périmée = zéro, stop/off/cancel = zéro
  immédiat -> `arrived`.
- Un geste redemandé pendant un geste (« encore à gauche ») est un NOUVEL
  ordre compté depuis la pose courante : l'ancien tombe (zéro franc,
  `goto_suivant`), chacun garde ses bornes. Pas de cumul. (Le même OBJET
  d'« aller voir » redemandé reste ignoré.)
- Jamais en tour spontané (mise en mouvement, revue B1).

### 7.3 « Avancer » — ligne droite, SIM-ONLY

- Intention : `{"cmd": "avancer", "metres": <float>}`, 0,1 ≤ m ≤ 5. Négatif
  refusé (`invalid` `recul` : on ne recule pas), < 0,1 ou > 5 -> `hors_bornes`.
- Régisseur : comme « tourner » (journal `avancer`).
- route_driver : `route_goto` `{"forward_m": m}` -> DRIVE de goto.py en
  TENANT le cap de la première pose fraîche, sans FACE ; `arrived` dès que la
  projection du déplacement sur ce cap atteint m (à 0,05 m près) — jamais de
  pivot de retour s'il dépasse (revue M2). Mêmes bornes : fader,
  croisière, calage 2 s, distance parcourue ≤ 1,5 × m, timeout = 10 s +
  4 s/m, pose non finie/périmée = zéro, stop/off/cancel = zéro immédiat ->
  `arrived`. Pas d'évitement (§5).
- Jamais en tour spontané.

### 7.4 Côté vision (chat_node, hors de ce dépôt)

- Clés de bouche à définir sur ce contrat (angle chiffré, mètres).
- Prompt de marche : retirer « tu ne sais ni tourner ni faire demi-tour » ;
  il sait aller voir un objet de la liste, tourner la tête (regarder), pivoter
  sur place et avancer tout droit ; il ne sait toujours ni contourner ni
  reculer.

---

## 8. Lot M3 — « Faire le tour de X » (01/11)

David : « je veux lui faire faire le tour des poubelles mais c'est super
laborieux » — chaque geste (pivot, 1 m) se terminait par un arrêt et
attendait une relance (un geste par réplique ; un tour spontané ne remet
jamais en mouvement, revue B1). Un tour est la demande composée la plus
fréquente : il devient UN geste, exécuté de bout en bout par route_driver.
SIM-ONLY (vérité terrain), comme tout robot_rehearsal.

### 8.1 Géométrie des tours — `config/chantiers_tours.yaml` (GÉNÉRÉ)

L'ancre d'un POI n'est PAS le centre de l'objet (poubelle_tri : ancre
(27 ; 1,4), bacs centrés en (27 ; 2,4)). Le tour se calcule sur la géométrie
de COLLISION du monde Gazebo :
- outil `robot_rehearsal/tools/compute_tours.py <world.sdf> <itinéraire.yaml>`
  (stdlib + yaml) : pour chaque POI de l'itinéraire, le modèle SDF de même
  nom ; centre = milieu de la boîte englobante (x, y) des collisions
  (cylindre : rayon ; boîte : demi-diagonale, rotation de lien ignorée →
  majorant) ; rayon objet = distance max centre → bord ; rayon de tour =
  rayon objet + TOUR_CLEARANCE_M (0,4 Didier + 0,6 marge = 1,0 m), arrondi
  au 0,1 m supérieur, au moins TOUR_MIN_RADIUS_M (1,5).
- tour IMPOSSIBLE (champ absent) si : rayon de tour > TOUR_MAX_RADIUS_M (6),
  ou un AUTRE modèle (hors sol : modèles dont l'emprise dépasse 50 m) a une
  collision à moins de 0,5 m de l'anneau [r − 0,6 ; r + 0,6].
- sortie : `{poi: {x, y, rayon}}` triée, en-tête « GÉNÉRÉ — ne pas éditer ».
- test hôte `test_tours.py` : regénère depuis le SDF et compare au fichier
  (désynchronisation = rouge) ; valeurs gravées pour poubelle_tri.

### 8.2 Contrat

- chat_move : `{"cmd": "tour_de", "objet": "<texte>", "sens": "gauche"|"droite"}`
  (`sens` absent = "gauche"). gauche = sens trigonométrique (l'objet reste
  à GAUCHE de Didier), droite = horaire.
- route_goto : `{"name": "tour de <poi>", "orbit_x", "orbit_y", "orbit_r",
  "orbit_dir": 1|-1}` — 4e forme exclusive de parse_order. Bornes : r dans
  [TOUR_MIN_RADIUS_M ; TOUR_MAX_RADIUS_M], dir ∈ {1, −1}, finis.
- Côté bouche : clé `"faire_le_tour": "<nom de la liste>"` (+ clé optionnelle
  `"sens": "gauche"|"droite"`), préséance stop > aller_voir > faire_le_tour >
  tourner > avancer > go ; jamais en tour spontané.

### 8.3 Arbitrage (régisseur) — comme aller_voir

Objet résolu (nom + alias) ; inconnu → `unknown` ; connu sans tour →
refus `no_tour` (journal) ; route OFF par David → refus ; centre à plus de
GOTO_MAX_DISTANCE_M → `too_far` ; accepté hors séance ; lève l'arrêt vocal
comme go ; stop/off/cancel → cancel ; un nouvel ordre remplace l'ancien.

### 8.4 Manœuvre (goto.py, OrbitOrder)

1. APPROCHE : point d'entrée E = C + r·(pose − C)/|pose − C| (le point du
   cercle le plus proche ; si Didier est à < 0,2 m du centre : E devant lui).
   ALIGN puis DRIVE vers E (mêmes règles que aller_voir, arrivée à
   arrive_tol_m).
2. ORBIT : θ = atan2(y − cy, x − cx). Cap visé = θ + dir·π/2 +
   dir·clamp(k_r·(d − r), ±0,6 rad) (k_r = 1,0 : trop loin → rentre vers le
   centre). ω = ang_gain·erreur + dir·v/r (anticipation), plafonds habituels ;
   v = min(max_lin × facteur, TOUR_CRUISE_MS 0,35) × facteur de cap (comme
   DRIVE : à l'entrée, il pivote d'abord). Angle balayé INTÉGRÉ
   (Σ dir·wrap(Δθ), jamais négatif compté) ; ≥ 2π → FACE (vers C) → ARRIVED.
3. SÉCURITÉ (en plus de toutes celles du DRIVE) : |d − r| > TOUR_MAX_DEV_M
   (1,0) pendant ORBIT → abandon `off_track` ; délai = GOTO_TIMEOUT_S +
   2πr / TOUR_MIN_MS (0,1) ; distance parcourue ≤ 1,5 × (|pose − E| + 2πr),
   plancher min_travel_m ; calage, odom périmée, pose NaN, fader 0, cancel :
   inchangés (zéro franc).
4. Tests purs : tour complet simulé (intégrateur cinématique) dans les deux
   sens, arrêt face au centre ; cancel immédiat ; fader 0 ; off_track
   (pose téléportée) ; calage ; timeout ; NaN ; bornes parse_order ;
   mutation des gardes principales.

### 8.5 Hors lot

Suites de gestes enchaînés (« tourne, avance, va voir ») : lot suivant.
Pas d'évitement : le cercle est réputé libre (§8.1).

---

## 9. Lot M4 — Tâche en cours : il fait ce qu'il annonce, jusqu'au bout (01/11)

David : « je ne veux pas une liste d'instructions pour chaque mouvement ; il
dit qu'il fait quelque chose, il le fait — pourquoi il s'arrête ? ».
Cause : chaque geste finit par un arrêt et Didier ne reprend JAMAIS la main
à ce moment ; un tour spontané ne peut pas le remettre en mouvement (B1).
Décision de David (01/11) : une TÂCHE ouverte par une demande humaine se
poursuit d'elle-même, geste après geste, jusqu'à ce que Didier dise qu'elle
est finie. Assouplissement BORNÉ de B1 : seule une tâche ouverte par un
humain peut enchaîner ; un tour spontané du metteur en scène ne bouge
toujours jamais. Tout côté vision (chat_node lit `route_goto_result`, déjà
publié par route_driver) ; aucun changement robot. SIM-ONLY (le mouvement à
la voix n'existe qu'au domaine 43).

### 9.1 Logique pure — `vision/ai/move_task.py`, `MoveTask` (verrou interne)

- `gesture_emitted(request, continuation, now)` : appelé quand une réplique
  NON spontanée émet un geste de corps (aller_voir, tour_de, tourner,
  avancer — pas go/stop). Tour humain : NOUVELLE tâche (request = texte de
  David, steps = 1). Tour de continuation : même tâche, steps += 1.
  Dans les deux cas `awaiting = True`.
- `close(reason)` : tour humain servi (avant sa réplique ; il rouvre si sa
  réplique émet un geste), arrêt d'urgence vocal, clé "marche": "stop",
  chat OFF, réplique de continuation SANS geste (= « c'est fini »).
  Journalisé (tâche close + raison).
- `on_result(payload, now) -> Optional[str]` (payload route_goto_result
  {name, result, reason, travelled}) :
  - aucune tâche ou pas `awaiting` → None ; reason "goto_suivant" → None
    (remplacé par un ordre plus récent, la tâche attend le sien) ;
  - result "arrived", ou reason ∈ {timeout, max_travel, stalled, off_track,
    too_far} → si steps < TASK_MAX_STEPS (8) et âge < TASK_MAX_S (180) :
    `awaiting = False`, rend le texte de continuation ; sinon close
    ("budget") et None ;
  - toute autre raison (cancel, cancelled, stop, route on/off…) → close, None
    (défaut SÛR : ce qu'on ne connaît pas arrête la tâche).
- Texte de continuation (direction), gravé dans les tests :
  « Ton geste « {name} » est terminé ({travelled} m parcourus). » ou
  « Ton geste « {name} » s'est interrompu ({raison en clair}). », puis
  « Ta tâche, demandée par David : « {request} ». Si elle n'est pas finie,
  dis où tu en es en quelques mots et fais le geste suivant ; si elle est
  finie, dis-le en une phrase, SANS clé de geste. »

### 9.2 Moteur (conversation.py)

- Emplacement de continuation (StageState ou MoveTask, un seul, la plus
  récente remplace) servi pendant l'écoute comme un tour spontané, MAIS :
  prioritaire sur la direction du metteur en scène ; silence minimal
  TASK_MIN_SILENCE_S (0,5 s) au lieu de SPONTANEOUS_MIN_SILENCE_S ; pas
  soumis à SPONTANEOUS_MIN_GAP_S ; jamais pendant in_speech ni son de
  spectacle ; texte tapé et parole de David passent avant (et ferment la
  tâche).
- `_serve_continuation(direction)` : comme `_serve_prompt` (visage
  « reflechit », pas de ligne « david », panne mute seule) mais
  `spontaneous=False` pour _notify_move (les gestes PASSENT, par
  _emit_start : barrière des stops tardifs + verrou de la garde) ; ÉCOUTE
  GARDE ARMÉE comme pour un tour humain (« stop » pendant la réplique de
  continuation doit arrêter) ; texte utilisateur fixe TASK_USER_TEXT.
- Tours spontanés (metteur en scène) : inchangés, jamais de geste (B1).

### 9.3 chat_node

Abonnement `route_goto_result` (StringTime JSON) SEULEMENT si le mouvement
à la voix est actif ; JSON illisible = warning, ignoré ; `on_result` →
direction poussée dans l'emplacement de continuation ; log « tâche :
continuation (geste n/8) » / « tâche close (raison) ».

### 9.4 Prompt (MOVE_TEMPLATE)

Remplacer « un geste à la fois, réplique après réplique » par : un seul
geste de corps par réplique ; pour une demande qui en demande plusieurs,
fais le premier : à la fin de chaque geste on te redonne la main et tu
enchaînes le suivant toi-même, jusqu'à dire que c'est fini. Ce que tu
annonces, tu le fais jusqu'au bout ; ne t'arrête que si on te le demande.

### 9.5 Tests (purs + moteur avec doubles) et mutation

Ouverture/continuation/budget 8 et 180 s/goto_suivant ignoré/raison
inconnue = close/tour humain ferme/stop ferme/réplique sans geste ferme ;
moteur : continuation servie avant un prompt spontané, gestes émis en
continuation, JAMAIS en spontané, garde armée, priorité du texte tapé.
Mutation : budget, défaut sûr des raisons, spontaneous=False réservé à la
continuation.
