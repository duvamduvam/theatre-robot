# Étude — ce que Didier voit ↔ ce qu'il sait du lieu : une seule vérité sur les objets

*Écrite les 2026-11-17 et 18 (conception Fable), décidée par David le 16/11 après la séance du 15/11.
**Statut (18/11 au soir) : questions du §13 tranchées par David (Q1, Q3, Q5, Q7, Q8 oui ; Q4 sans
objet avant O2 ; Q2 modifiée : lidar commandé, essais d'autonomie à la première sortie — rien ici
n'interdit plus tard « rouler vers un objet vu ») ; lots O0 et O1 faits le 18/11 (branche
`o0-o1-objets`), voir `docs/chantiers.md`.** Texte d'origine :
Rien n'est acté : les questions du §13 attendent David. Le banc de mesure du §4 est réel
(caméra Gazebo du monde `chantiers`, trois modèles via OpenRouter, 744 appels, 1,05 $ dépensés) ; son
outil est `packages/didier_vision/tools/banc_pointage.py`, ses résultats bruts hors dépôt
(`~/tmp/banc-pointage/`).*

**Règle qui borne toute l'étude : le chemin roues ne change pas.** Ce qui est proposé ici
fournit une CIBLE (un nom, un point au sol, une incertitude). Vitesses, deadman, `twist_mux`,
arrêt d'urgence, bornes de `goto.py` : intouchés. Les décisions du 02/11
(`etude-autonomie-improvisation.md` §8 : sélecteur seul décideur du corps, lidar 2D sur le
Pi 4, odométrie avant la rue) ne sont pas re-tranchées.

## 0. Verdict en dix lignes

1. La panne du 15/11 n'est pas une panne de précision, c'est une panne d'**identité** : rien ne
   relie « ce que montre l'image » à « une entrée de la liste ». Et la bouche **ne voit aucune
   image** : elle lit une liste de 30 noms et une phrase libre écrite 6 à 30 s plus tôt.
2. Il faut **un tableau des objets**, un seul, écrit par un seul nœud, lu par la bouche, la
   réflexion, le sélecteur et la régie. La carte (POI) et la vision y sont deux **sources**.
3. **En sim, la voie (a) suffit** pour la panne du 15/11 — à condition de la faire dans le
   tableau (objets *dans le champ*, pas seulement *proches*) et de donner la même liste à la
   réflexion. Pas besoin d'un modèle de vision pour ça. Coût : les lots O0 et O1, 11 h d'agent.
4. **En rue, seule la voie (b) existe aujourd'hui**, et elle marche pour le nom et la
   direction : sur 70 questions, les deux Gemini désignent le bon objet 94 à 100 % du temps
   (99-100 % en demandant le pied de l'objet), à 0,2° d'azimut près, en 1 s (3.5-flash) ou
   3 s (3.7-flash), pour 0,2 centime l'appel.
5. Mais **la question fermée ment** : interrogés sur un objet absent, les deux Gemini désignent
   un sosie 9 à 29 % du temps selon le modèle et la question, et **les mêmes sosies reviennent
   d'une série à l'autre** (la flaque pour « table très basse », le plot pour « bagues
   géantes »). C'est la panne du 15/11, reproduite côté vision. D'où : **inventaire d'abord**
   (« que vois-tu ? », aucun nom suggéré), désignation par nom seulement en second.
6. **L'azimut est une mesure ; la distance ne vaut que ce que vaut l'inclinaison de la
   caméra.** La géométrie (caméra à 1,06 m, horizontale) donne 4 cm par pixel à 5 m et 68 cm à
   20 m ; 1° d'inclinaison ignorée coûte 0,4 m à 5 m et 6,6 m à 20 m. Mesuré, robot à plat
   (série B), Gemini 3.7-flash interrogé sur le pied de l'objet : à 0,13 m du centre vrai sous
   6 m (13/13 à moins de 0,5 m), 0,16 m de 6 à 12 m (9/10), 0,31 m au-delà avec des écarts
   jusqu'à 3,5 m. Les mêmes questions avec 1,6° d'inclinaison ignorée (série A) : 0,2 m,
   0,6 m, puis 5 m. Le modèle n'est pas le maillon faible ; la pose de la caméra l'est.
7. Conséquence de conception : un objet vu est d'abord **une direction**. La distance par
   projection sert jusqu'à 10 m en sim (pose exacte) et jusqu'à 6 m sur le robot réel tant que
   l'inclinaison n'est pas tenue à 0,5° ; au-delà, on s'approche par bonds et on regarde à
   nouveau ; le lidar décidé le 02/11 donnera la vraie distance dans la direction de la caméra.
8. **La voie (c) (détecteur ouvert local sur le PC) est écartée pour l'instant** : le PC n'est
   pas dans la rue. En revanche le détecteur déjà embarqué (EfficientDet, 16 Hz sur le Pi 5)
   connaît 80 classes et on jette tout sauf `person` : c'est un déclencheur gratuit de lubies
   — à mesurer sur de vraies photos avant d'y croire (en sim il ne reconnaît presque rien).
9. Ce que ça supprime : le topic des objets proches du sélecteur, `proximite.py`, le refus « > 10 m » du
   sélecteur, les deux listes de 30 noms dans le prompt. Les deux gardes saines restent
   (garde déterministe du chat, corrélation des résultats), branchées sur le tableau.
10. Plan : 5 lots, ≈ 25 h d'agent (Opus), une relecture Fable, 2 × 15 min de David (mire et
    photos). Les lots O0-O1 passent avant L2c ; le pointage (O2) après.

## 1. Le problème, redit avec ce que le code montre

Séance du 15/11, 21:29 : Didier est vers x ≈ 14 m, David regarde un objet à gauche. Didier
dit « le banc est là, bien en vue », demande le tour du banc ; la régie accepte ; il roule
22 m le long de la route. Le seul `banc` de la carte est à (36,2 ; 2,5).

Ce qui s'est passé, composant par composant :

- la **réflexion** (seule à recevoir l'image) a écrit une phrase libre de 25 mots au plus sur
  ce que montrait la caméra — avec ses mots à elle, sans connaître les noms de la carte ;
- la **bouche** (Haiku, texte seul) a reçu cette phrase, plus la liste des 30 objets de
  l'itinéraire sans position, et a fait le rapprochement toute seule : une table basse vue
  + un « banc » dans la liste = « le banc est là » ;
- la **régie** a résolu le nom `banc` dans son YAML et ordonné le déplacement vers ce point.

Trois acteurs, trois représentations, aucun identifiant commun. Les garde-fous posés les 15
et 16/11 (liste des tours possibles, objets proches du sélecteur avec distance et côté, refus au-delà
de 10 m, garde déterministe du chat, corrélation des résultats par nom d'ordre) ont rendu la
panne honnête — Didier ne ment plus sur ce qu'il a fait — mais pas impossible : la bouche
choisit toujours un nom dans une liste en devinant, à partir d'un texte, lequel elle « voit ».

Et en rue il n'y a ni carte ni régie : la liste n'existera pas. Les lubies sur des objets et
« va voir ça » devront partir de ce que la caméra montre.

## 2. État des lieux : qui sait quoi

### 2.1 Les connaissances, leur source, leur fraîcheur

| Qui | Ce qu'il sait des objets | D'où | Fraîcheur / cadence | Vaut en rue ? |
|---|---|---|---|---|
| **Régie** (`didier_rehearsal/director`, SIM-ONLY) | 30 POI : ancre (x, y), rayon de déclenchement, `desc`, `alias` ; 13 tours (centre, rayon) calculés sur les collisions du SDF | `config/chantiers.yaml`, `chantiers_tours.yaml` (généré) | statique ; publiée latchée sur `rehearsal/objects` | non (pas de carte) |
| **Régie** — pose de Didier | (x, y, cap) exacts | `ground_truth/odom` (Gazebo, 2D) | continu | **non** : pas d'odométrie sur le robot (chantier ouvert), encore moins de pose monde |
| **Sélecteur** (`didier_jeu`, SIM-ONLY) | les 6 objets les plus proches : distance à 0,1 m, côté par quart de tour (devant = ±45°) | pose vérité terrain + ancres de `rehearsal/objects` (`proximite.py`) | 1 Hz, le topic des objets proches | non |
| **Bouche** (`chat_node`, Haiku 5.5 réflexion coupée, **texte seul**) | la liste des 30 noms + `desc` (≤ 1 200 car.), la liste des tours (≤ 600 car.), les 6 proches, le tableau de situation (≤ 700 car.) | topics ci-dessus + `chat_situation` | relus à chaque réplique ; premier mot < 1 s | la liste : non ; le tableau : oui |
| **Réflexion** (`reflection_node`, Haiku 5.5 effort moyen, **avec image**) | ce que montre l'image, en une phrase libre (`situation`, 25 mots) ; le nom du POI qu'on vient de franchir | trame JPEG 640×480 de moins de 3 s + `rehearsal/poi_event` | sur événement, au moins 4 s entre deux appels, battement à 20 s ; 5,9-6,8 s par appel (banc du 23/10) ; la phrase reste affichée 30 s | oui |
| **Suivi de personne** (`person_tracker`, MediaPipe EfficientDet-Lite0) | les boîtes des **personnes** (azimut, hauteur) ; les 79 autres classes COCO sont jetées (`detector.py`, filtre `person`) | webcam | 16,7 Hz sur le Pi 5, ≈ 24 % CPU, sans réseau | oui |

Lecture : la seule chose qui *voit* les objets (la réflexion) ne connaît pas leurs noms ni
leurs positions ; ceux qui connaissent noms et positions (régie, sélecteur) ne voient rien ;
la bouche, qui parle et demande les gestes, ne voit rien et ne sait pas où est quoi.

### 2.2 La caméra

| | Sim (`dadou_robot_gz.urdf.xacro`, relu et vérifié dans Gazebo le 17/11) | Robot réel |
|---|---|---|
| Montage | fixée au **buste**, ne tourne pas avec le cou | idem (établi le 14/09) — webcam USB sur un support devant la bouche |
| Hauteur de l'axe optique | 1,06 m (0,23 + 0,83, lu sur `camera_link`) | **non mesurée** |
| Inclinaison | 0° (axe horizontal, robot à plat) | **non mesurée** |
| Champ | 60° horizontal (1,047 rad) → 46,8° vertical, focale 554 px | **non mesuré** (webcam Jieli UVC) |
| Image | 640×480, 5 Hz (rendu CPU) | 640×480 MJPG, 16,7 img/s ; republiée en JPEG à 5 img/s |
| Sol visible à partir de | 2,45 m (bas de l'image) | à mesurer |

Trois « non mesuré » sur le robot réel : c'est le premier préalable de la voie (b) en rue
(lot O4, une mire au sol, 15 min de David).

Conséquence du montage au buste, déjà écrite dans le prompt de la bouche : tourner la tête ne
montre rien de neuf, seul un pivot du corps fait voir de côté. Un objet « à gauche » hors du
champ de ±30° n'est **pas vu** : il faut pivoter puis regarder.

### 2.3 Ce qui manque au robot réel (rappel, non re-tranché)

Pas d'odométrie, pas de lidar, pas de pose : un objet vu ne peut être rangé ni dans un repère
monde ni dans un repère d'odométrie. Aujourd'hui, sur le vrai robot, la position d'un objet vu
n'a de sens que **par rapport au robot, tant qu'il ne bouge pas**. Le modèle du §6 en tient
compte au lieu de supposer une carte.

## 3. La géométrie de la projection au sol

Caméra à la hauteur `h`, axe horizontal, focale `f` (px), centre (cx, cy). Un pixel (u, v)
**sous l'horizon** (v > cy) touche le sol à :

```
avant  = h · f / (v − cy)
gauche = avant · (cx − u) / f          azimut = atan((cx − u) / f)
```

Deux grandeurs de qualité très différente :

- **l'azimut** ne dépend que de la colonne et de la focale : 1 pixel = 0,10°. Il ne dépend ni
  de la hauteur, ni de l'inclinaison, ni de la pente du sol ;
- **la distance** dépend de la ligne, de la hauteur et de l'inclinaison, et sa sensibilité
  croît comme le **carré** de la distance.

| Distance | Lignes sous l'horizon | Erreur pour 1 px | Erreur pour 1° d'inclinaison ignorée | Erreur pour une pente de 2 % (1,15°) |
|---|---|---|---|---|
| 3 m | 196 px | 1,5 cm | 0,15 m | 0,17 m |
| 5 m | 117 px | 4 cm | 0,41 m | 0,47 m |
| 8 m | 73 px | 11 cm | 1,05 m | 1,2 m |
| 10 m | 59 px | 17 cm | 1,65 m | 1,9 m |
| 15 m | 39 px | 38 cm | 3,7 m | 4,3 m |
| 20 m | 29 px | 68 cm | 6,6 m | 7,6 m |

(h = 1,06 m, f = 554 px ; erreurs au premier ordre : d²/(h·f) par pixel, d²/h par radian.)

Trois conséquences qui structurent la suite :

1. **Portée utile de la distance sur le robot réel : ≈ 6 m**, 10 m au grand maximum. Au-delà,
   un demi-degré de tangage du châssis vaut près d'un mètre. En sim, où la pose est exacte, le
   banc tient jusqu'à 12 m (§4.3) : c'est l'inclinaison qui borne, pas le pointage.
2. **Le point à demander est le pied de l'objet** (là où il touche le sol), pas son centre :
   le centre d'un lampadaire est à 2 m de haut, son rayon ne touche jamais le sol au bon
   endroit. D'où les deux variantes du banc : « pied » (point) et « boîte » (milieu du bord bas).
3. **L'inclinaison de la caméra est un paramètre de sécurité de la cible**, pas un détail.
   Preuve involontaire pendant le banc : ma première série d'images a été prise avec un robot
   cabré de 1,6° (téléporté à z = 0 parce que `ground_truth/odom` est publié en 2D, il s'est
   enfoncé dans la dalle et en est ressorti penché). Toutes les distances projetées à 20 m
   étaient fausses de 5 m, alors que les azimuts restaient justes à 0,2°. Le robot réel penche
   au freinage, sur un trottoir en dévers, sur ses pneus : en rue, la distance par projection
   est une **estimation**, l'azimut est une **mesure**.

Incliner la webcam vers le bas améliorerait la distance (plus de lignes par mètre) mais
couperait les visages : à 2 m, un visage d'adulte est à +15° au-dessus de l'axe, le champ
vertical n'offre que ±23°. Avis : **ne pas l'incliner** ; la bonne source de distance est le
lidar (décidé le 02/11), pas la caméra.

## 4. Le banc de mesure

### 4.1 Protocole

- Monde `chantiers`, conteneur `monde` seul (rien ne roule), robot téléporté par le service
  Gazebo `set_pose` à **20 poses** : 11 « en marche » le long du tracé (objets de 6 à 25 m) et
  9 « tourné vers l'objet » à 4-5 m (le cas « le banc à gauche » après un pivot). Pose 3D vraie
  relue dans Gazebo après stabilisation ; capture refusée si le robot n'est pas à plat.
- Vérité : centre et rayon d'emprise de chaque objet calculés sur la géométrie du SDF (même
  code que `compute_tours.py`), pas sur les ancres des POI (l'ancre du banc est à 1,1 m de
  son centre).
- **35 cibles** (13 à moins de 6 m, 10 de 6 à 12 m, 12 au-delà) et **17 questions pièges** :
  un objet de la carte qui n'est pas dans l'image (hors champ, à plus de 12 m).
- L'objet est nommé par son `desc` (« banc en bois », « trois bacs jaune, vert, gris ») : ce
  qu'on voit, pas le nom du POI.
- Trois variantes de question : **pied** (« le point où il touche le sol, [y, x] 0-1000 »),
  **boîte** (`box_2d`, on projette le milieu du bord bas), **inventaire** (question ouverte,
  aucun nom suggéré : « liste les objets visibles, 8 au plus, avec leur boîte »).
- Trois modèles (identifiants vérifiés sur la liste publique d'OpenRouter le 17/11) :
  `google/gemini-3.7-flash` (0,75 / 3,75 $ par million de jetons), `google/gemini-3.5-flash`
  (1,5 / 9 $), `qwen/qwen3-vl-30b-a3b-instruct` (0,15 / 0,6 $). Température 0, réflexion au
  minimum pour Gemini, appel non streamé, image JPEG qualité 90.
- Mesures : bonne désignation (l'azimut du point tombe dans l'emprise angulaire de l'objet, à
  3° près), erreur d'azimut, erreur au sol (distance entre le point projeté et le centre vrai ;
  « hors emprise » = au-delà du rayon de l'objet), piège (objet absent déclaré visible),
  latence, coût facturé (champ `usage.cost` d'OpenRouter).

Deux séries de 372 appels chacune : **A** (20 images, robot cabré de 1,6°, voir §3 —
exploitée pour la désignation, l'azimut, les pièges, la latence et l'inventaire, **pas** pour
la distance) et **B** (mêmes poses, robot à plat : z = 0,230 m et tangage 0,00° relus dans
Gazebo à chaque pose — la seule exploitée pour l'erreur au sol). Les deux séries posent les
mêmes questions sur des images légèrement différentes : leur accord est la seule mesure de
répétabilité du banc.

### 4.2 Résultats — désigner le bon objet (séries A et B)

70 cibles et 34 pièges par ligne (35 + 17 par série). « Bon objet » : l'azimut du point rendu
tombe dans l'emprise de l'objet.

| Modèle | Question | Bon objet (A + B) | Erreur d'azimut médiane (p90) | Objet absent déclaré visible | Latence médiane (p90) | Coût par appel |
|---|---|---|---|---|---|---|
| gemini-3.7-flash | pied | 35 + 35 = **70/70** | 0,14-0,18° (0,6°) | 2 + 3 = **5/34 (15 %)** | 3,1 s (4,2-5,1 s) | 0,0016 $ |
| gemini-3.7-flash | boîte | 34 + 32 = 66/70 (94 %) | 0,18-0,19° (0,9°) | 1 + 2 = 3/34 (9 %) | 2,7 s (3,5-4,1 s) | 0,0016 $ |
| gemini-3.5-flash | pied | 34 + 35 = 69/70 (99 %) | 0,17-0,21° (0,8-1,2°) | 3 + 2 = 5/34 (15 %) | 1,0 s (1,2-1,3 s) | 0,0020 $ |
| gemini-3.5-flash | boîte | 34 + 34 = 68/70 (97 %) | 0,17-0,18° (0,9-1,0°) | 5 + 5 = **10/34 (29 %)** | 1,1 s (1,4-1,5 s) | 0,0021 $ |
| qwen3-vl-30b, réponse lue comme demandé ([y, x]) | pied | 12 + 13 = 25/70 (36 %) | 4,5-5,3° | **0/34** | 0,8 s (1,9-2,3 s) | 0,00008 $ |
| qwen3-vl-30b, lue comme demandé | boîte | 12 + 11 = 23/70 (33 %) | 3,6-4,0° | **0/34** | 0,9-1,0 s (2,7 s) | 0,00009 $ |
| qwen3-vl-30b, relue en [x, y] | pied | 15 + 10 = 25/70 (36 %) | 2,7-4,8° | — | — | — |
| qwen3-vl-30b, relue en [x, y] | boîte | 32 + 32 = 64/70 (91 %) | 0,5-0,7° (1,4-3,5°) | — | — | — |

Lecture :

- **Désigner un objet présent est acquis** pour les deux Gemini, dans les deux formats. Le seul
  raté commun est la `pelouse` (un panneau de 20 cm de rayon à 15 m).
- **Désigner un objet absent est le vrai défaut**, et il n'est pas propre à un modèle : les
  quatre lignes Gemini déclarent visible la « table très basse » de la pose 5 (c'est la flaque
  au premier plan) dans les deux séries (8 fois sur 8), et les « bagues géantes » de la
  pose 18 (c'est le plot de chantier) 7 fois sur 8. Ce n'est pas du bruit : la même scène
  redonne le même sosie. 3.5-flash en boîte en ajoute trois par série (le « plan incliné
  vers l'eau », une seconde « table très basse »).
- **Qwen ne se trompe jamais sur un absent (0/68) mais ne respecte pas le format demandé** : il
  rend [x, y] quand on demande [y, x]. Relu dans son ordre, sa boîte vaut presque celle de
  Gemini (91 %, 0,5-0,7°) ; son point « pied », lui, reste faux dans les deux lectures (36 %) :
  il ne sait pas pointer une base, seulement encadrer.

### 4.3 Résultats — projeter au sol (série B, robot à plat)

Erreur au sol = distance entre le point projeté et le **centre** vrai de l'objet, sur les
objets bien désignés. Le rayon d'emprise des cibles va de 0,2 à 2,6 m (1,0 m pour le banc).

| Modèle, question | Moins de 6 m (13 cibles) | 6 à 12 m (10 cibles) | 12 à 25 m (12 cibles) |
|---|---|---|---|
| gemini-3.7-flash, **pied** | **0,13 m** (p90 0,34, max 0,37) ; 13/13 à moins de 0,5 m | **0,16 m** (p90 0,44, max 0,50) ; 9/10 | 0,31 m (p90 2,9, max 3,5) ; 8/12 |
| gemini-3.5-flash, pied | 0,14 m (p90 0,54, max 0,87) ; 9/13 | 0,23 m (p90 2,5, max 3,1) ; 6/10 | 0,45 m (p90 2,1, max **30**) ; 7/12 |
| gemini-3.7-flash, boîte | 0,53 m (p90 0,85) ; 6/12 ; biais −0,52 | 0,65 m (p90 1,2) ; 4/10 ; biais −0,65 | 1,06 m (p90 1,5) ; 2/10 ; biais −1,05 |
| gemini-3.5-flash, boîte | 0,47 m (p90 0,84) ; 7/13 ; biais −0,47 | 0,63 m (p90 1,2) ; 3/10 ; biais −0,63 | 1,02 m (p90 1,5) ; 3/11 ; biais −1,01 |
| qwen3-vl-30b, boîte relue en [x, y] | 0,56 m (p90 **8,0**) ; 5/12 | 0,31 m (p90 1,1) ; 6/10 | 1,47 m (max **90**) ; 0/10 |

(médiane ; p90 et maximum ; part des cibles à moins de 0,5 m ; biais = erreur médiane de
distance, négative = trop court.)

Les mêmes questions sur la série A (1,6° d'inclinaison **ignorée**), pour mesurer ce que
coûte une caméra mal connue : 3.7-flash « pied » passe de 0,13 / 0,16 / 0,31 m à
**0,20 / 0,64 / 5,1 m** ; la boîte de 0,53 / 0,65 / 1,06 m à 0,24 / 1,25 / 5,1 m.

Lecture :

- **Robot à plat, pose connue, la projection est bonne jusqu'à 12 m** avec 3.7-flash et la
  question « pied » : 22 cibles sur 23 à moins de 0,5 m. C'est mieux que ce que la géométrie
  seule laissait craindre ; la limite de 6 m du §3 vient de l'inclinaison du robot réel, pas
  du modèle.
- **« Pied » et « boîte » ne mesurent pas la même chose.** Le milieu du bord bas de la boîte
  est le bord **proche** de l'objet : l'erreur est un biais régulier, toujours trop court,
  de l'ordre du rayon (−0,5 m de près, −1 m de loin), et le point reste dans l'emprise
  (sous 12 m : 21/22 pour 3.7-flash, 22/23 pour 3.5-flash). Le
  banc à 4,3 m : 0,85 m par la boîte, 0,24 m (3.7-flash) ou 0,50 m (3.5-flash) par le pied.
  Pour s'arrêter à 1,5 m d'un centre, il faut le pied ; pour ne pas rentrer dans l'objet, le
  bord proche est le chiffre prudent.
- **3.5-flash a des queues** : au-delà de 6 m, 4 points « pied » sur 10 sont posés trop haut
  sur l'objet (+1,2 à +3,1 m). Sous 6 m il tient 13/13 à moins de 1 m.
- **Près de l'horizon, un point n'a plus de distance** : l'écart de 30 m vient d'un point posé
  11 lignes sous l'horizon (un vélo à 21 m). Règle pour le module : à moins de 40 lignes sous
  l'horizon (au-delà de 15 m), on garde l'azimut et on jette la distance.
- Qwen : deux boîtes sur douze à 8 m de leur objet sous 6 m. Pas pour une cible de roues.

### 4.4 Résultats — la question ouverte (« inventaire »)

Une question par image, aucun nom suggéré. Mesure : chaque cible du plan est-elle rendue (une
boîte dont le milieu tombe dans son emprise angulaire), et sous quel nom ?

| Modèle | Cibles retrouvées (A + B) | Objets listés par image (médiane) | Erreur au sol, série B : < 6 m / 6-12 m / > 12 m | Latence médiane (p90) | Coût par appel |
|---|---|---|---|---|---|
| **gemini-3.5-flash** | 35 + 35 = **70/70** | 6,5-7 | 0,42 / 0,58 / 1,02 m | **1,9 s** (2,5 s) | 0,0039 $ |
| gemini-3.7-flash | 32 + 35 = 67/70 | 4,5-5,5 | 0,42 / 0,58 / 1,19 m | 3,8-4,1 s (5,5-5,8 s) | 0,0027 $ |
| qwen3-vl-30b, relu en [x, y] | 32 + 34 = 66/70 | 8 (le plafond demandé) | 0,51 / 0,34 / 5,5 m | 5,6-6,4 s (12-18 s) | 0,00024 $ |
| qwen3-vl-30b, lu comme demandé | 20 + 21 = 41/70 | 8 | inexploitable | idem | idem |

Les noms donnés (aucun n'était suggéré) :

- Gemini décrit ce qu'il voit, et c'est juste : « banc en bois », « table basse en bois »,
  « cône de chantier », « poubelle jaune », « borne d'incendie rouge », « vélo orange »,
  « tas de sable ». La « petite boule grise sur pied » de la carte (`pigeon`) devient une
  « borne sphérique » : c'est ce que montre l'image. D'une série à l'autre le nom bouge (« tas
  de sable » en A, « gros rocher » en B) : **l'étiquette d'un objet vu n'est pas un
  identifiant**, d'où l'`id` du §6.2.
- Qwen nomme plus mal : le chien est un « robot », les anneaux une « bouée », le conteneur
  rouge un « banc ».

Lecture : **l'inventaire retrouve tout ce que la désignation retrouvait, sans pouvoir être
piégé par un nom** — on ne lui en donne pas. Sa position est celle d'une boîte (bord proche,
−0,4 à −1 m, §4.3) : suffisante pour dire « un banc à quatre mètres à gauche » et le
regarder, pas pour s'arrêter à 1,5 m. Ce que le banc **ne mesure pas** : les objets inventés
(une ligne d'inventaire qui ne correspond à rien). Le recoupement automatique est impossible
ici — les bâtiments de la carte couvrent tout l'horizon — et je n'ai pas compté à l'œil sur
les planches de la série B. À mesurer en O2, sur réponses enregistrées, avant de brancher.

### 4.5 Le détecteur déjà embarqué, sans son filtre

Essai en marge du banc (aucun coût) : `efficientdet_lite0.tflite`, celui du suivi de
personne, lancé sur les 20 images de la série A **sans** le filtre `person`, seuil 0,3.

| | Résultat |
|---|---|
| Cibles nommables en COCO (banc ×4, vélo ×3, chien ×2, bouche d'incendie ×1) | **2 / 10** reconnues à la bonne place (un banc à 4,3 m, la bouche d'incendie à 5,3 m) |
| Fausses classes | 4 (la table basse dite « bench », les anneaux dits « bicycle » deux fois, une grue dite « airplane ») |
| Fausses personnes | 3, toutes sous 0,4 (le seuil de production les écarte) |

Ce chiffre ne dit rien de la rue : les objets de Gazebo sont des boîtes et des cylindres, un
détecteur entraîné sur des photos n'a aucune raison de les reconnaître. Il dit seulement que
**ce détecteur ne servira pas en sim**, et qu'il faut le mesurer sur de vraies photos avant de
compter dessus (lot O3, porte de sortie chiffrée).

### 4.6 Coût et limites du banc

**744 appels, aucune erreur d'appel, 1,049 $ facturés** (série A 0,523 $, série B 0,527 $ ;
plafond fixé à 2 €) : 0,445 $ pour gemini-3.7-flash, 0,577 $ pour gemini-3.5-flash, 0,027 $
pour Qwen (248 appels chacun). Rejouer une série : 372 appels, ≈ 15 min, ≈ 0,5 $.

Limites à garder en tête :

- **images de synthèse** : formes primitives, pas de foule, pas de contre-jour, pas de flou
  de bougé. La désignation sera plus dure en rue (encombrement) et la description plus
  facile (de vrais objets). Le lot O4 refait 20 questions sur de vraies photos ;
- **un seul passage par question et par série**, température 0 : la variabilité n'est vue
  que par l'écart entre les séries A et B (mêmes scènes, 1,6° d'écart) ;
- **Claude n'est pas au banc** : la bouche et la réflexion sont passées à l'API Anthropic en
  direct (lot tête, 16-17/11), et la réflexion reçoit déjà l'image. Savoir si Haiku 5.5 sait
  pointer n'a pas été mesuré — les trois modèles étaient ceux décidés le 16/11. La vision des
  objets passerait donc par OpenRouter, qui reste déjà en secours de la tête : aucun secret
  nouveau, mais un second fournisseur dans le chemin de la parole. À mesurer en tête d'O2
  (40 appels) avant de figer le client ;
- **latences mesurées depuis le PC en fibre** ; le Pi 5 en 4G ajoutera son réseau ;
- la « bonne désignation » est jugée sur l'azimut : un point posé sur un autre objet aligné
  derrière la cible compterait bon (cas non observé à l'œil sur les planches de contrôle).

## 5. Les trois voies comparées

| | (a) La carte, mieux exposée | (b) Modèle de vision → point → sol | (c) Détecteur à vocabulaire ouvert, local sur le PC |
|---|---|---|---|
| Principe | calculer, depuis la pose et la carte, ce qui est **dans le champ** de la caméra et le dire à la bouche et à la réflexion | demander au modèle où est l'objet (ou ce qu'il voit), projeter le pied au sol par la pose de la caméra | un réseau du type YOLO-World / Grounding DINO sur le GPU du PC (RTX 4060, 8 Go), interrogé avec des mots |
| Précision de position | celle de la carte : centimétrique en sim | azimut 0,2° ; distance à 0,13-0,16 m jusqu'à 12 m en sim, robot à plat (3.7-flash, « pied ») ; 0,5-0,65 m par la boîte ; sur le robot réel, bornée par l'inclinaison : ≈ 6 m (§3) | boîtes du même ordre que (b) — **non mesuré ici** ; même géométrie, donc même limite en distance |
| Identité (« le banc » = quel objet) | exacte : c'est l'objet de la carte | bonne si on demande un objet présent (94-100 %) ; **fragile si l'objet est absent** (sosie 9 à 29 % du temps, §4.2) ; saine en question ouverte | même fragilité attendue sur une requête par mot (non mesuré) |
| Latence | 0 (calcul local, 1 Hz ou plus) | 1,0 s (3.5-flash), 2,7-3,1 s (3.7-flash) par question ; 1,9 s / 4 s par inventaire | dizaines à centaines de ms annoncées par les auteurs — **non mesuré ici** |
| Coût | 0 | ≈ 0,002 $ la question, 0,003-0,004 $ l'inventaire (Gemini) ; 15 à 25 fois moins avec Qwen | 0 par appel ; un GPU allumé |
| Réseau | aucun | **obligatoire** (comme la bouche et la réflexion aujourd'hui) | aucun en atelier ; en rue il faudrait joindre le PC de la maison par le VPN : pire que (b) |
| Rue | **impossible** : pas de carte, pas de pose | **oui**, dès que la caméra réelle est calibrée ; azimut d'abord | **non** tant que le calcul n'est pas embarqué (le Pi 5 n'a pas de GPU ; l'AI HAT ne fait pas tourner ces modèles tels quels) |
| Images de passants | aucune ne sort | une image par appel part chez le fournisseur — déjà décidé « oui » le 23/10 pour la réflexion | rien ne sort : son seul vrai avantage |
| Maintenabilité | ≈ 60 lignes de géométrie pure, testables ; mais une carte à dessiner à la main par lieu | ≈ 150 lignes (client HTTP + projection), un prompt, une calibration caméra ; dépend d'un fournisseur et d'un identifiant de modèle qui change tous les six mois | pile PyTorch + CUDA de plusieurs Go dans une image, pilote GPU, poids à suivre ; rien de commun avec le Pi |
| Ce qu'elle ne résout pas | la rue ; les objets absents de la carte (un passant pose un sac) | la distance de loin ; la panne réseau | la rue |

Lecture sans complaisance :

- **(a) est la bonne réponse à la panne du 15/11**, et elle est presque faite : il manque le
  filtre « dans le champ » (aujourd'hui « proche » = dans un rayon, y compris derrière) et le
  fait de donner la même liste à la réflexion. Aller chercher un modèle de vision pour une
  séance en sim serait payer du réseau et de la latence pour retrouver ce que la carte sait
  déjà au centimètre.
- **(b) est la seule voie pour la rue**, et le banc montre qu'elle est mûre pour la
  **direction** et pour le **nom** ; pour la **distance** elle est bonne en sim jusqu'à 12 m,
  et ne vaudra sur le robot réel que ce que vaudra la calibration de sa caméra (lot O4).
- **(c) n'apporte rien aujourd'hui** : elle ne marche que là où (a) suffit déjà. Elle
  redeviendra une question le jour où un calculateur embarqué avec GPU entrera dans le robot,
  ou si la décision du 23/10 sur les images de passants est rouverte. Gemini Robotics-ER 2
  (API Google seule) n'est pas nécessaire : les généralistes n'échouent pas.

## 6. Le modèle cible : le tableau des objets

### 6.1 Principe

**Un tableau, un écrivain, quatre lecteurs.** Le tableau liste les objets que Didier connaît
*en ce moment*, qu'ils viennent d'une carte, de la caméra, ou des deux. Chaque objet a un
identifiant, un nom qu'on peut dire, une position **avec son repère et son incertitude**, et la
date de sa dernière observation. Personne d'autre ne calcule « où est le banc ».

```
 carte (régie, SIM / lieu préparé) ──► rehearsal/objects ─┐
 caméra ──► inventaire (question ouverte, à l'arrêt) ─────┤
 caméra ──► désignation par nom (à la demande) ───────────┼─► objets_node ──► scene/objets (latché)
 caméra ──► détecteur embarqué (classes COCO, 16 Hz) ─────┤   (SEUL écrivain)        │
 pose (vérité terrain en sim ; odométrie plus tard) ──────┤                           │
 lidar (plus tard : distance dans l'azimut) ──────────────┘                           │
                                                                                      ▼
      bouche (ce qui t'entoure) · réflexion (mêmes noms) · sélecteur (offres, cibles) · régie (résolution)
```

Le nœud `objets_node` est le premier habitant du package `didier_perception`, prévu au §6 de
l'étude autonomie (« état du monde publié, contrat testé ») ; les pistes de personnes du lot
A2 l'y rejoindront. Il tourne avec la vision (Pi 5 ; conteneur `vision` en sim), à côté de la
caméra. Le contrat (forme d'un objet, nom du topic, encodage) va dans `theatre_contrats`.

### 6.2 Un objet

```json
{"id": "o7", "nom": "banc", "desc": "banc en bois", "sources": ["carte", "vu"],
 "repere": "monde", "x": 36.2, "y": 2.5, "sigma_m": 0.0,
 "azimut_deg": 14.0, "distance_m": 4.3, "cote": "devant", "en_vue": true,
 "vu_il_y_a_s": 1.2, "tour": true, "atteignable": true}
```

| Champ | Sens | Qui le calcule |
|---|---|---|
| `id` | identifiant stable tant que l'objet vit ; c'est lui que portent les ordres et les journaux | `objets_node` |
| `nom` | ce qu'on dit ; **unique dans le tableau à un instant** (deux bancs : « banc » le plus proche, « banc 2 ») | carte (`name`) ou étiquette de l'inventaire, normalisée |
| `sources` | `carte`, `vu`, ou les deux | fusion |
| `repere`, `x`, `y`, `sigma_m` | position et écart-type ; repère `monde` (carte), `odom` (vu, robot doté d'une odométrie) ou `robot` (vu, robot sans odométrie) | projection §3 ou carte |
| `azimut_deg`, `distance_m`, `cote` | la même position vue de Didier **maintenant** ; recalculée à chaque publication | `objets_node` — les lecteurs ne refont jamais ce calcul |
| `en_vue` | dans le champ de la caméra maintenant (carte + pose : par la géométrie ; vu : observé il y a moins de 3 s) | `objets_node` |
| `vu_il_y_a_s` | âge de la dernière observation caméra (absent pour un objet de carte jamais vu) | `objets_node` |
| `tour` | on sait en faire le tour (géométrie de collision connue) : objets de carte seulement, tant qu'il n'y a pas de lidar | carte |
| `atteignable` | le corps a le droit de le prendre pour cible d'un déplacement (règle du §6.5) | `objets_node` |

### 6.3 Identité : « le banc dont on parle », c'est lequel ?

Règle unique, déterministe, dans `objets_node` (`resoudre(nom)`) :

1. correspondance normalisée exacte (celle de `route.normalize_name`, déjà gravée des deux
   côtés) sur `nom` et alias, **parmi les objets `en_vue` ou à portée** ; plusieurs candidats →
   le plus proche de l'axe du regard ;
2. sinon, **désignation à la demande** : une image, une question par nom ; le point trouvé
   crée (ou confirme) un objet `vu` ; garde contre le sosie : l'objet désigné doit coïncider
   avec une ligne de l'inventaire dont l'étiquette est compatible, sinon il est refusé ;
3. sinon, s'il existe sur la carte mais loin ou hors champ : réponse **« connu, pas ici »**
   avec sa distance et son côté — Didier peut le dire (« le banc ? il est à vingt mètres
   derrière moi »), il ne part pas ;
4. sinon : inconnu.

La bouche ne nomme que des noms du tableau, la garde déterministe du chat
(`set_gesture_vocabulary`, 15/11) vérifie sur le tableau, et l'intention de geste porte l'`id`
résolu. La régie reçoit un `id` et une position : elle ne cherche plus le nom dans son YAML.
Bouche, sélecteur et régie parlent donc du même objet par construction, pas par chance.

**Rapprochement vu ↔ carte** (en sim, ou dans un lieu préparé) : un objet vu projeté à
STRICTEMENT moins de `max(2·sigma_m, emprise + 1 m)` du CENTRE d'un objet de carte de nom
compatible est **le même** — `emprise` = rayon d'emprise au sol de l'objet de carte (majorant
de sa collision, `emprise_m`), 1 m s'il est inconnu (revue O1 du 19/11 : le code d'O0 prenait le
rayon de l'ORBITE de tour, ≈ emprise + 1 m, soit un seuil d'environ emprise + 2 m) : les
sources fusionnent, la position de la carte gagne (elle est exacte), la caméra apporte
« je le vois ». Sinon c'est un objet nouveau (le sac posé par un passant).

### 6.4 Durée de vie et incertitude

| Objet | Repère | Incertitude | Fin de vie |
|---|---|---|---|
| de carte | monde | 0 | jamais |
| vu, robot **avec** odométrie (sim aujourd'hui, robot réel après le chantier odométrie) | odom | `sigma_m` à la création = `max(0,3 m ; 4 % de d) + (d² / h) × σ_inclinaison` — le premier terme est le p90 du banc (§4.3, « pied ») ; `σ_inclinaison` vaut 0 en sim et 0,5° visé après la calibration O4, soit +0,3 m à 6 m et +0,8 m à 10 m ; grandit de 5 % de la distance parcourue depuis l'observation | non revu depuis 120 s, ou `sigma_m` > 2 m, ou contredit (il devrait être dans le champ et l'inventaire ne le rend plus, deux fois de suite) |
| vu, robot **sans** odométrie (robot réel aujourd'hui) | robot | idem à la création | sa **position** tombe dès que le robot bouge (première consigne de roues non nulle) ; son **nom** reste 30 s pour la parole (« le vélo qu'on a croisé ») sans plus pouvoir être une cible |

Une vieille position est pire qu'aucune : c'est la règle déjà posée pour le tableau de
situation (`etude-niveaux-reflexion.md` §3), appliquée aux objets.

### 6.5 Ce que le corps a le droit d'en faire

`atteignable` est vrai si **toutes** ces conditions tiennent : position dans un repère `monde`
ou `odom` (jamais `robot`) ; `sigma_m` ≤ 1,0 m ; distance ≤ 10 m (la borne posée le 15/11,
désormais à un seul endroit) ; objet de carte, ou vu il y a moins de 10 s.

- **Atteignable** → `aller_voir` comme aujourd'hui : même ordre `route_goto {name, x, y,
  standoff}`, même `goto.py`, mêmes bornes. La seule différence est l'origine du point.
  **Distance d'arrêt** (revue O1 du 19/11) : non plus 1,5 m du centre pour tout objet, mais
  `max(1,5 ; emprise + 0,5 (Didier) + 0,5 (marge))`, 2,5 m si la taille est inconnue
  (`director.standoff_pour`, spec-aller-voir §2.3) — 1,5 m du centre du banc le touchait.
- **Vu mais pas atteignable** (trop loin, trop incertain) → **approche par bonds**, avec les
  gestes qui existent déjà : `tourner` de l'azimut (la mesure fiable), `avancer` d'au plus la
  moitié de la distance estimée et jamais plus de 3 m, puis regarder à nouveau. La tâche en
  cours (`MoveTask`, lot M4) sait déjà enchaîner des gestes jusqu'au bout ; chaque bond garde
  ses bornes. C'est robuste à l'erreur de distance : on ne s'engage jamais sur un chiffre
  qu'on n'a pas.
- **Faire le tour** : objets de carte seulement. Un objet vu n'a pas de géométrie de
  collision ; le tour d'un objet vu attendra le lidar.
- Quand le lidar sera là (lot A0, décidé) : la distance d'un objet vu devient la mesure du
  lidar dans son azimut, `sigma_m` tombe à quelques centimètres, l'approche par bonds
  redevient un `aller_voir` direct. Aucun changement de contrat.

**En rue, rien de tout cela ne fait rouler Didier** avant le corps sûr, l'odométrie et les
préalables du 02/11. D'ici là le tableau sert la parole, le regard (`look`, tête seule, déjà
compatible production) et les offres de jeu.

### 6.6 Sim et rue : le même tableau, deux remplissages

| | Sim / lieu préparé | Rue |
|---|---|---|
| Sources | carte (30 POI) + pose vérité terrain ; caméra Gazebo en option (pour répéter la rue : carte vidée) | caméra seule : inventaire à l'arrêt, désignation à la demande, détecteur embarqué si le lot O3 le valide |
| Repère | monde | robot (odom quand l'odométrie existera) |
| « Banc » | l'objet de la carte, s'il est en vue | le banc que l'inventaire a listé, tant que Didier n'a pas bougé |
| Coût réseau | aucun | un inventaire par arrêt + un par battement (20 s) à l'arrêt : ≈ 0,7 $/h avec Gemini 3.5-flash, moins de 0,05 $/h avec Qwen (chiffres §4.4) |
| Ce que la bouche lit | « Devant toi : table_basse à 4 m, un peu à gauche. Plus loin : poster_bizarre… Tu ne vois pas : banc (22 m derrière). » | « Devant toi : un banc en bois à environ 4 m à gauche ; un vélo orange, loin à droite. » |

La même section de prompt dans les deux cas, écrite par le même code : la rue ne sera pas un
second chantier de prompt.

## 7. Ce que ça supprime

| Rustine du 15-16/11 | Devient |
|---|---|
| le topic des objets proches du sélecteur, `didier_jeu/proximite.py`, `stage.decode_near_payload`, `NEAR_*` de `personas.py` | **supprimés** : la distance et le côté sont des champs du tableau |
| Phrase « Un objet de ta liste qui n'est pas ici est loin : ce n'est pas lui que tu vois » | **supprimée** : la bouche ne reçoit plus que ce qui est en vue ou à portée |
| Refus « > 10 m » du sélecteur (`geste.distance_max_chat_m`, `_trop_loin`) | **supprimé** : c'est la règle `atteignable`, à un seul endroit |
| Liste des 30 objets (≤ 1 200 car.) et liste des tours (≤ 600 car.) relues à chaque réplique | **remplacées** par les objets en vue et à portée (une demi-douzaine de lignes) : prompt plus court, premier mot plus rapide |
| Résolution du nom dans la régie (`director.resolve_object` sur le YAML) | **remplacée** par l'`id` du tableau ; la régie garde ses propres refus (route coupée par David, 40 m) |
| Garde déterministe du chat (`set_gesture_vocabulary`) | **gardée**, alimentée par le tableau : c'est une vraie garde, pas une rustine |
| Corrélation geste ↔ résultat par nom d'ordre (§9.6 de `spec-aller-voir`) | **gardée**, sur l'`id` |
| Réponse honnête à un geste refusé (`chat_move_reply`) | **gardée** : c'est par elle que « connu, pas ici » et « je ne le vois pas » arrivent à la bouche |

Trois rustines supprimées, deux remplacées, trois mécanismes sains conservés. Rien de
supprimé ne touche le chemin roues.

## 8. Recommandation

1. **Faire le tableau des objets, alimenté d'abord par la carte seule** (lots O0-O1). C'est la
   voie (a), faite proprement : elle règle la panne du 15/11 en sim sans un seul appel réseau
   de plus, et elle pose le contrat dont la rue a besoin.
2. **Y brancher la vision en deuxième source** (lot O2), en deux temps mesurés au banc :
   **inventaire** à l'arrêt avec `google/gemini-3.5-flash` (1,9 s, 70 cibles sur 70, noms
   justes) — il dit ce qui est là et dans quelle direction ; puis, **seulement quand un objet
   devient la cible d'un déplacement, une question « pied »** avec `google/gemini-3.7-flash`
   (3 s, 22 cibles sur 23 à moins de 0,5 m jusqu'à 12 m), toujours recoupée avec l'inventaire.
   Jamais de désignation par nom sans ce recoupement. Distance exploitée jusqu'à 10 m en sim,
   6 m sur le robot réel ; approche par bonds au-delà.
3. **Ne pas faire la voie (c).** Mesurer en revanche, sur de vraies photos, ce que voit le
   détecteur déjà embarqué une fois son filtre levé (lot O3) : s'il tient, c'est le
   déclencheur continu et gratuit des lubies en rue ; s'il ne tient pas, l'inventaire à
   l'arrêt suffit et on n'y revient pas.
4. **Calibrer la caméra réelle avant tout chiffre en rue** (lot O4) : hauteur, inclinaison,
   champ. Sans ça la voie (b) ne donne qu'un azimut — ce qui suffit déjà à la parole et au
   regard.

Ce que je déconseille explicitement : continuer à ajouter des lignes au prompt de la bouche
pour lui apprendre à ne pas confondre ; confier une distance à un modèle de langage (règle du
02/11, que le banc confirme : le modèle donne un *pixel*, c'est la géométrie qui donne les
mètres) ; incliner la webcam ; brancher la désignation par nom sans le recoupement.

## 9. Plan en lots

| Lot | Contenu | Agent | Durée | Porte de sortie |
|---|---|---|---|---|
| **O0 — contrat** | `theatre_contrats` : forme d'un objet, topic `scene/objets`, encodage ; logique PURE du tableau (fusion, nom unique, péremption, `resoudre`, `atteignable`, géométrie « dans le champ »), tests à valeurs gravées + mutation | Opus | 4 h | tests verts ; la séance du 15/11 rejouée en test pur : à x = 14, « banc » → « connu, pas ici, 22 m » |
| **O1 — la carte dans le tableau** | package `didier_perception`, `objets_node` (sources : `rehearsal/objects` + pose) ; bouche : section « ce qui t'entoure » ; réflexion : mêmes noms ; garde du chat, sélecteur et régie branchés sur le tableau ; suppressions du §7 ; doc et README | Opus | 7 h | épreuves 1, 2 et 4 du §10 vertes ; fumée complète verte ; plus aucune trace du topic des objets proches dans le dépôt (`git grep`) |
| **O2 — la caméra dans le tableau** | en tête, 40 appels : Haiku 5.5 sait-il pointer (§4.6) ? ; module pur de projection (repris du banc, distance jetée à moins de 40 lignes sous l'horizon), client de vision (inventaire, puis « pied » recoupé pour une cible ; un adaptateur de format par modèle), comptage des objets inventés sur réponses enregistrées, paramètres de caméra par machine (`machines/<machine>/`), source caméra Gazebo ; approche par bonds ; relecture adverse avant fusion | Opus + **Fable 1 h** (relecture) | 8 h | épreuves 3 et 5 vertes sur réponses enregistrées ; à la main, en vrai : carte vidée, « va voir le banc » depuis 4,3 m → arrêt à 1,5 m ± 0,5 m du centre (mesuré au banc : 0,24 m d'erreur avec 3.7-flash « pied ») |
| **O3 — le détecteur embarqué, filtre levé** | mesure d'abord (30 photos de rue à hauteur de buste) ; si la porte passe : classes utiles publiées, source du tableau, offres de lubies | Opus | 1 h de mesure, puis 3 h | **porte : ≥ 70 % des objets nommables retrouvés, ≤ 1 fausse classe pour 10 images** ; sinon abandon écrit |
| **O4 — la caméra réelle** | mire au sol (4 repères à 2, 4, 6 et 8 m) : hauteur, inclinaison, champ ; les 20 questions du banc refaites sur de vraies photos | Opus + David 2 × 15 min | 2 h | distance projetée à ± 0,3 m à 6 m sur la mire ; tableau du §4 refait en réel |
| *plus tard* | distance par le lidar dans l'azimut ; tour d'un objet vu | — | avec A0 | — |

Total ≈ 25 h d'agent Opus (dont 3 h d'O3 seulement si sa porte passe), 1 h de Fable. O0 et O1 d'abord (ils rendent les séances en sim
saines), **avant L2c** comme prévu au tableau des chantiers ; O2 après L2c ; O3 et O4 quand
David peut prendre les photos. Rien ici n'est du code de sécurité roues ; aucun lot pour
Sonnet ou Haiku (la garde et la cible touchent ce que le corps fera).

## 10. Épreuves de fumée prévues

Toutes sans réseau (la fumée nocturne reste à zéro jeton, décision du lot F) : la vision y est
rejouée sur des réponses **enregistrées**. Version réelle à la main.

| # | Épreuve | Vert si |
|---|---|---|
| 1 | **« montre-moi le banc », il est là** : Didier à (32,5 ; 0), cap 25° ; demande `aller_voir banc` | l'ordre porte l'`id` du banc ; arrêt à 2,1 m ± 0,3 m du centre (36,2 ; 2,5) et au moins 0,2 m de jeu entre le banc et Didier (contact = rouge ; revue O1 du 19/11, avant : 1,5 m ± 0,3, qui acceptait le contact), face à lui (± 10°) |
| 2 | **« le banc », il n'est pas là** (la séance du 15/11) : Didier à x = 14 | réponse « connu, pas ici » avec la distance ; **zéro** consigne de roues ; la réplique d'échec est dite |
| 3 | **carte vidée (la rue en sim)** : mêmes poses, objets venus de la seule caméra | depuis 4,3 m, l'inventaire fait entrer le banc au tableau dans son emprise (à moins de 1,0 m du centre) et la question « pied » le ramène à moins de 0,5 m ; depuis 22 m (la pose du 15/11) il est « vu, pas atteignable » et l'approche part par bonds |
| 4 | **une seule vérité** : sur une séance de 10 gestes | le nom dit, la cible du sélecteur et la cible de la régie portent le même `id`, dans les trois journaux |
| 5 | **péremption** : objet vu, puis 5 m de route sans odométrie | il n'est plus atteignable ; il disparaît à l'échéance |
| 6 | **chemin roues intact** : V-R3 et les épreuves de route existantes | vertes, sans modification |

## 11. Risques

| Risque | Parade |
|---|---|
| Le sosie : Didier va voir la mauvaise chose avec aplomb | inventaire d'abord, désignation recoupée, `id` journalisé ; et c'est du théâtre : une erreur d'objet se joue, un mensonge sur ce qu'on a fait non (acquis du 15/11, conservé) |
| Distance fausse (dévers, freinage, caméra déréglée) | `sigma_m` explicite (inclinaison comprise), portée 6 m sur le robot réel, distance jetée près de l'horizon, approche par bonds, lidar à terme ; en rue rien ne roule avant le corps sûr |
| Panne réseau en rue | le tableau se vide par péremption, Didier dit qu'il ne voit plus rien ; le détecteur embarqué (si O3 passe) continue |
| Le modèle change ou disparaît d'OpenRouter | identifiant en configuration, banc rejouable en 15 min pour 0,5 $ (`banc_pointage.py`) |
| Format de sortie non respecté (Qwen rend [x, y] malgré la consigne : 33 % de bonnes désignations lu tel quel, 91 % relu) | un adaptateur par modèle, testé sur réponses enregistrées ; refus de toute réponse hors bornes ; tout changement de modèle repasse par le banc |
| Le prompt de la bouche grossit à nouveau | plafond gravé pour la section « ce qui t'entoure » ; objets hors de portée résumés en une ligne |
| Deux chantiers écrivent le même package (`didier_perception` : objets ici, personnes en A2) | contrat dans `theatre_contrats`, un nœud par sujet |
| Images de passants envoyées à chaque arrêt | même régime que la réflexion (décidé le 23/10) ; un inventaire par arrêt, pas un flux ; à rouvrir avec le reste si la décision change |

## 12. Liens avec les autres chantiers

- **Étude « improvisation en vrai »** (à écrire ensuite) : les lubies sur des objets vus
  deviennent des **offres** nées d'une entrée du tableau (`sources` contient `vu`), au lieu des
  seuls `poi_event` de la régie. Les « bugs joués » sur le vrai robot n'ont pas besoin du
  tableau ; les lubies, si. En rue, première version : lubie = parole + regard vers l'azimut
  de l'objet, jamais les roues.
- **Autonomie, décisions du 02/11** : le sélecteur reste le seul décideur du corps — il lit le
  tableau, il n'en est pas l'auteur. « Jamais une distance demandée à un VLM » est respecté :
  le modèle rend un pixel. « Jamais la caméra seule qui autorise un mouvement » : en sim la
  pose vient de la vérité terrain et la cible passe par la régie ; en rue rien ne roule avant
  le lidar. Le lot A2 (pistes de personnes) et ce tableau partagent `didier_perception`.
- **Spec A2 à venir (déplacements en actions ROS)** : l'`id` d'objet est la cible naturelle
  d'un but d'action ; rien ici ne s'y oppose.
- **Niveaux de réflexion** : la réflexion garde son rôle (le sens, l'histoire) ; elle reçoit
  les noms du tableau pour dire « le banc » comme tout le monde. L'inventaire est un appel
  séparé, plus court et moins cher que la réflexion ; les fondre en un seul appel est une
  optimisation possible, non mesurée.
- **L2c (rendu LED en sim)** : indépendant. **Refonte électrique, odométrie** : l'odométrie
  fera passer les objets vus du repère `robot` au repère `odom` sans changer le contrat.

## 13. Questions pour David

| # | Question | Mon avis par défaut |
|---|---|---|
| 1 | O0 + O1 (le tableau, la carte dedans, les rustines supprimées) avant L2c ? | **Oui** : c'est ce qui rend les séances en sim fiables, et 11 h d'agent |
| 2 | En rue, avant le lidar et l'odométrie, Didier parle des objets qu'il voit et les regarde, mais ne roule pas vers eux. D'accord ? | **Oui** : c'est la conséquence des décisions du 02/11 |
| 3 | « Montre-moi X » prend 1 à 3 s : Didier comble par une réplique (« attends, je regarde… »). Acceptable ? | **Oui** : la réplique dure plus longtemps que l'appel |
| 4 | Quel modèle pour la vision des objets ? | **Gemini 3.5-flash pour l'inventaire** (1,9 s, rien de manqué) et **Gemini 3.7-flash pour pointer le pied avant un déplacement** (3 s, deux à quatre fois moins d'écarts) ; deux identifiants en configuration, un seul fournisseur. Qwen écarté malgré son prix (20 fois moins) et son zéro sosie : il ne respecte pas le format, ne sait pas pointer une base et met 6 s par inventaire. Haiku 5.5 à mesurer en tête d'O2 : s'il pointe aussi bien, un fournisseur de moins |
| 5 | On laisse la webcam horizontale ? | **Oui** : l'incliner couperait les visages ; la distance viendra du lidar |
| 6 | Tu prends 30 photos de rue à hauteur de buste (1,06 m) et tu poses une mire au sol 15 min, pour O3 et O4 ? | **Oui**, quand tu veux : rien d'autre n'en dépend avant O2 |
| 7 | Un inventaire par arrêt en rue (une image au fournisseur à chaque fois) : même régime que la réflexion ? | **Oui** ; à rouvrir avec la question des images de passants si tu la rouvres |
| 8 | Nom du topic `scene/objets` et package `didier_perception` | **Oui** : conformes aux règles de nommage, et `didier_perception` est déjà annoncé par l'étude autonomie |

## 14. Reproduire le banc

```
cd packages/didier_vision
python3 tools/banc_pointage.py preparer                 # plan.json dans ~/tmp/banc-pointage/
# sim : cd machines/sim && HEADLESS=true WORLD=chantiers docker compose up -d monde
docker exec -i didier-sim-monde bash -c 'source /opt/ros/jazzy/setup.bash; \
    source /home/ros2_ws/install/setup.bash; cat > /tmp/b.py; \
    python3 /tmp/b.py capturer --plan /home/ros2_ws/log/banc/plan.json \
    --sortie /home/ros2_ws/log/banc' < tools/banc_pointage.py
OPENROUTER_API_KEY=… python3 tools/banc_pointage.py interroger --budget-usd 0.7
python3 tools/banc_pointage.py mesurer
```

La clé ne passe que par la variable d'environnement ; l'outil ne l'affiche ni ne l'écrit.
`interroger` reprend là où il s'est arrêté (un appel payé n'est jamais refait) et s'arrête au
plafond de dépense.

## 15. Ce que cette étude ne re-tranche pas

Le sélecteur seul décideur du corps, l'hybride py_trees + score, le lidar 2D sur le Pi 4, les
préalables de rue (arrêt d'urgence W1, signal de vie, odométrie), les images dans le cloud
(23/10), l'arrêt vocal toujours prioritaire, « un tour spontané ne met jamais Didier en
mouvement », et le chemin roues.
