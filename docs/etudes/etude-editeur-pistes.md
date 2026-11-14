# Étude — l'éditeur de séquences en pistes, et les chorégraphies sur morceaux choisis

*Écrite le 2026-11-13 (Fable) à partir de ce que David a dit le 12/11. **Étude écrite, rien
d'acté** : elle prépare ses décisions (§12), avec une recommandation tranchée (§0). Elle
s'appuie sur [`etude-danse.md`](../etude-danse.md) (grille de beats, retards, droits), sur la
spec L1d de [`spec-L1-contrats-donnees.md`](../spec-L1-contrats-donnees.md) (`data_edit`,
contrat, porte sim) et sur [`etude-banc-temoin.md`](etude-banc-temoin.md) (mini-Didier). Faits
relevés dans le code et sondés dans Gazebo le 13/11 (§2) ; recherche web courte le même jour.*

Cahier des charges, mots de David (12/11) :

- « quelque chose comme l'édition vidéo / son, c'est-à-dire un retour de simulation en direct,
  avec différentes pistes qui seront les sources de mouvement et d'expression possibles » ;
- Gazebo doit pouvoir « revenir à un point précis, revenir en arrière, changer de position » ;
  le `random` est le cas qui gêne ;
- « une des petites pépites serait des chorés sur quelques morceaux choisis », réglées « avec le
  robot en travail avec des retours caméra ».

## 0. Réponse courte et recommandation

1. **L'éditeur est une page du pont web, `/montage`**, à côté de la page scène : même pont, même
   session d'écriture, zéro chaîne de build, et **`data_edit` reste la seule écriture**. Pas de
   Blender, pas d'application de bureau (§4).
2. **Le principe du 12/11 tient, avec une correction de fond.** Gazebo sert bien de rendu et la
   téléportation marche (sondé, §2.2). Mais **une image clé de servo n'est pas un point à
   interpoler : c'est une CIBLE émise**, que le servo rejoint à sa vitesse. L'état à l'instant t
   ne se calcule donc pas par une formule ; il s'obtient en **rejouant à blanc, en temps virtuel,
   les primitives du lecteur** (`Track` + la loi de mouvement du servo) de 0 à t. Le lecteur reste
   la référence, l'aperçu est construit DESSUS, pas à côté (§5).
3. **Trois moniteurs, pas un.** Gazebo donne 5 images/s : il montre l'espace (où va le robot, ce
   qu'il heurte), il ne peut pas juger un calage à ±40 ms. Le calage au temps se lit sur **un
   mannequin dessiné dans la page** (60 images/s, synchro exacte avec le son du navigateur) et sur
   les courbes calculées posées sur la grille de beats ; le troisième moniteur est la **webcam du
   banc** (§6, §9).
4. **Chorégraphies : la partition appartient à l'œuvre, les retards à la machine.** La séquence
   porte un bloc `partition` (figures placées en mesures et temps) et ses pistes compilées aux
   temps NOMINAUX ; **le lecteur applique au chargement le profil de retards de SA machine**
   (avance par piste, vitesse par servo). C'est un écart assumé avec `etude-danse.md` (« zéro
   changement embarqué ») : sans lui, une danse réglée sur le mini-Didier est fausse sur Didier, et
   chaque nouvelle mesure oblige à recompiler toutes les danses (§7).
5. **Réglage filmé : l'agent corrige le PROFIL, jamais la partition.** Corrélation du son
   enregistré avec le fichier de référence, détection des arrivées de geste par zone d'image,
   médiane des écarts par piste, deux ou trois passes. Seul sur le mini-Didier ; avec David sur
   Didier (§9).
6. **Les roues dansées ne sont pas dans ce plan.** Mesure du 12/11 : une piste roues ne produit
   qu'une impulsion de 0,41-0,48 s. Toute chorégraphie qui se déplace attend le chantier roues
   séparé (Opus minimum, sim puis protocole caméra). L'éditeur AFFICHE les pistes roues telles
   qu'elles se jouent aujourd'hui, il ne les « répare » pas (§5.4).
7. **Un fait à traiter à part, découvert en route** : des chansons du commerce sont DÉJÀ suivies
   dans ce dépôt public (§8.3).

Plan : 7 lots, ≈ 34 h d'agent (Opus), deux séances avec David (§11).

## 1. Ce que David obtient, vu de sa chaise

- Une page avec **neuf pistes** (son, visage, cou, œil gauche, œil droit, bras gauche, bras droit,
  roues, lumières), une règle de temps, une tête de lecture.
- Il **déplace la tête** : le mannequin, le visage et la vignette Gazebo montrent l'état du robot
  à cet instant, le son se cale. Il **revient en arrière** autant qu'il veut.
- Il **choisit la pose de départ** (x, y, cap, ou un repère du monde) : la trajectoire des roues
  se dessine sur un plan vu de dessus, le robot Gazebo s'y téléporte.
- Il **pose, tire, copie des images clés** ; sur une chanson, elles s'aimantent aux temps ; une
  figure (un hochement, un coup de bras) se pose comme un clip et se répète.
- **Aperçu = brouillon** (rien n'est écrit). **Lecture réelle = enregistré** : le vrai lecteur
  joue le fichier, en entier ou depuis la tête, avec la vraie physique. « Rejouer en entier »
  tamponne la porte sim comme aujourd'hui.
- Sur le banc, il lance « Régler le calage » : le robot joue, la webcam filme, l'agent annonce
  les écarts par piste et propose la correction.

## 2. Faits relevés (13/11)

### 2.1 Le format et le lecteur

- 48 séquences ; pistes en usage : `audios`, `faces`, `neck`, `left_eye`, `right_eye`,
  `left_arm`, `right_arm`, `wheels`, `robot_lights` (+ `lights`, 2 fichiers). Images clés
  `[fraction de duration, valeur]`.
- **`AnimationManager` lit TOUTES les pistes en `Track.emissions`** : `[t, v]` = « émettre v à
  t × duration », une fois. Rien n'est interpolé. Un servo reçoit une cible ; `Servo.process()`
  l'y amène par une rampe de **160 unités/s** (échelle 0-99), puis le servo physique suit à sa
  vitesse propre.
- Valeurs de servo rencontrées : un nombre, ou **un dict `{"mode": "random", …}`** (bornes de
  course et de délai), présent sur les cinq servos : c'est le « hors random » de David. Le tirage
  utilise le `random` global dans `Servo` ; `ServoSim` (sim) a déjà un générateur INJECTÉ.
- **Deux implémentations de la loi de servo** : `didier_core/actions/servo.py` (réel, avec
  rampe) et `didier_sim_lib/servos_logic.py` (sim, **sans rampe**, tick 10 Hz).
- Bizarreries à reproduire telles quelles : une valeur « fausse » (servo `0`) n'est pas émise
  (`if event_action:`) ; une valeur dans ]0, 1] est multipliée par 100 ; un `random` reçu pendant
  un `random` est ignoré ; une seule activation par piste et par tick (20 Hz).
- `AnimationManager` lit l'horloge globale (`TimeUtils`) : il ne sait jouer que du début, et ne
  se pilote pas en temps virtuel. `Track`, lui, est déjà pur (`now_ms` passé par l'appelant).
- **Roues** : en mode `cmd_vel`, une image roues = UN Twist, coupé 0,41 s plus tard par
  `twist_deadman` (mesuré le 12/11, `docs/operations.md`). Les pistes roues jouent des impulsions.
- Le visage en sim (`face_sim_node`) exécute la vraie classe `Face` à l'horloge murale : il sait
  afficher une expression depuis son début, pas « à l'instant t de l'expression ».

### 2.2 Gazebo, sondé sur pièce

Sonde du 13/11 : image `dadou-sim-x86`, **Gazebo Sim 8.15.0**, monde `stage.sdf`, robot créé depuis
le xacro, conteneur isolé (sans réseau), commandes `gz service` / `gz topic`.

| Question | Résultat |
|---|---|
| Téléporter le robot en marche (`/world/stage/set_pose`) | **oui** : (0 ; 0) → (2,000 ; 1,000) lu sur `dynamic_pose/info`. Déjà utilisé par les scripts `validate-rehearsal-*.sh` |
| Mettre en pause (`/world/stage/control`, `pause: true`) | **oui** : horloge figée |
| Téléporter EN PAUSE | **oui** : pose appliquée telle quelle (z resté à 0,30, pas de chute) |
| Avancer d'un nombre de pas (`multi_step: 300`) | **oui** : +0,300 s exactement |
| Imposer une articulation d'un coup | **non** : aucun service ne le fait. Seul chemin : la cible du `JointPositionController` (`/<servo>/position`), que l'articulation rejoint à la vitesse limite de l'URDF. Mesuré : 0 → 0,877 rad en 0,300 s, soit **≈ 2,9 rad/s** (limite 3,0 pour cou et bras, 5,0 pour les yeux). En pause, la cible n'a aucun effet |
| Revenir en arrière par la physique | **non**, comme prévu. `reset: {all: true}` remet l'horloge à zéro mais **le robot créé après le démarrage disparaît** de `dynamic_pose/info` : à ne jamais utiliser |
| Téléporter à z = 0,30 | le robot retombe de 7 cm et **glisse de 14 mm** : téléporter à la hauteur de repos (z ≈ 0,23) |
| Rejeu d'un enregistrement Gazebo avec curseur (`/world/stage/playback/control`) | le service existe ; exige un second Gazebo lancé en mode rejeu : écarté (§5.5) |
| Cadence d'une caméra à chaud | service `/camera_ext/image_raw/set_rate` présent (non essayé) |
| Appeler ces services depuis un nœud Python | `gz.transport13` et `gz.msgs10` s'importent dans l'image ; `ros_gz_interfaces/srv/SetEntityPose` et `ControlWorld` existent aussi |
| Image de caméra rafraîchie en pause | **non tranché** (une image reçue, horodatée à l'instant de la pause ; aucune après les 300 pas dans la fenêtre d'écoute) : à lever au lot E0 |

Conséquences :

- **Le défilement (« scrub ») se fait Gazebo EN MARCHE, pas en pause** : c'est la tête de lecture
  de l'éditeur qui est en pause, pas la physique. Le robot téléporté tient en place, les
  articulations rejoignent leur cible, la caméra rend. On évite la question de la pause.
- **Délai de pose après un saut : jusqu'à ≈ 1,1 s** (π rad à 3 rad/s). Acceptable pour Gazebo ; le
  mannequin de la page, lui, est instantané.
- **Gazebo ment sur les vitesses**, dans les deux sens : bras à 3 rad/s contre ≈ 1,05 rad/s
  annoncés pour les vrais (1 s/60° à 12 V) ; cou plafonné à 3 rad/s alors que la rampe logicielle
  vaut 5,1 rad/s. Tant que `ServoSim` n'a pas de rampe, une danse vue en sim a des bras 2,8 fois
  trop vifs.
- Caméras à **5 images/s** (choix du 06/11 pour tenir 0,88 du temps réel) : 200 ms entre deux
  images, cinq fois la cible de calage.

### 2.3 Ce que L1d fournit déjà

`data_edit` (demande) / `data_edit_result` (verdict), `base_sha256` contre les conflits,
sauvegarde, journal, rechargement à chaud, quota de 200 sauvegardes par jour ; contrat pur
`theatre_contrats/donnees.py` (bornes roues comprises) ; porte sim (`validations-sim.json`,
observateur, « Valider les roues ») ; éditeur minimal en L1d-3 (texte + envoi d'image).
L1d-1 est fait ; **L1d-2 et L1d-3 sont un préalable** de cette étude.

## 3. État de l'art, en bref (web, 13/11/2026)

- **Choregraphe (NAO/Pepper)** : une *Timeline* = une couche de mouvement (une sous-couche par
  articulation, images clés INTERPOLÉES, vue courbes) + des couches de comportement en parallèle ;
  le son est un comportement posé sur une couche. Fermé, lié à NAOqi. À retenir : pistes parallèles
  et tête de lecture unique ; à ne pas copier : l'interpolation, qui n'est pas la sémantique de
  Didier. (Miroirs de la doc 2.1 : fileadmin.cs.lth.se/robot/nao/doc/software/choregraphe/panels/timeline_panel.html)
- **Spot Choreographer** (déjà cité dans `etude-danse.md` §4.4) : temps découpé en tranches de
  quart de temps, mouvements = blocs de durée entière, entrée de 3 s. C'est le modèle des
  « figures » retenu au §7.
- **Blender + export** : éditeur de courbes complet, mais il faut y importer le robot, écrire
  l'export, et il ne connaît ni `data_edit`, ni la porte sim, ni le visage LED. David devrait
  apprendre Blender pour poser des cibles de servo.
- **Bibliothèques de timeline web** : `animation-timeline-js` (composant canvas, sans dépendance,
  MIT d'après npm — npmjs.com/package/animation-timeline-js) ; Theatre.js (`@theatre/core` Apache,
  **`@theatre/studio` AGPL 3.0** — npmjs.com/package/@theatre/studio), pensé pour animer une page
  web, avec chaîne de build. `wavesurfer.js` v7 pour la forme d'onde (greffons *regions* et
  *timeline* — wavesurfer.xyz/docs ; **licence non vérifiée ici**).
- **Gazebo** : le rejeu avec curseur existe pour les enregistrements (`gz sim --playback`,
  gazebosim.org/api/sim/8/classgz_1_1sim_1_1PlaybackScrubber.html), pas pour une sim vivante.
- **Beats** : rien de neuf depuis `etude-danse.md` §4.1 (librosa pour les temps, `beat_this` pour
  les temps forts, grille précalculée, jamais de détection en direct).

Aucun outil existant ne se branche sur le format de Didier : on écrit l'éditeur. La seule vraie
question est OÙ (§4).

## 4. Où vit l'éditeur

| Option | Pour | Contre |
|---|---|---|
| **A. Page `/montage` du pont web** (recommandée) | même pont, même jeton d'écriture, mêmes flux (caméras, visage) ; pages servies telles quelles, sans build ; marche à distance et sur tablette ; `data_edit` et la porte sim sont déjà là | il faut écrire le composant de pistes (≈ 1 000 lignes de JS) |
| B. Blender + script d'export | courbes, 3D, outil mûr | apprentissage ; hors `data_edit` ; pas de visage, pas de random, pas de roues ; second outil à maintenir |
| C. Application de bureau ou Theatre.js | confort d'un vrai logiciel de montage | chaîne de build Node, licence AGPL du studio, rien de réutilisable côté robot |

**Recommandation : A, composant de pistes écrit à la main en canvas, sans dépendance.** La
sémantique à dessiner est propre à Didier (cible émise et courbe calculée, bloc `random` avec son
enveloppe, image tenue du visage, grille de beats irrégulière) ; une bibliothèque imposerait la
sienne. La forme d'onde se calcule avec l'API Web Audio du navigateur (décodage + crêtes), sans
greffon. Repli si le composant dérape au lot E3 : `animation-timeline-js` copié dans
`static/vendor/` (un fichier, MIT à relire à la source).

Trois fichiers neufs (`montage.html`, `montage.js`, `montage.css`), les communs dans `commun.js`.
La page scène n'est pas touchée : on JOUE sur `/scene`, on ÉCRIT sur `/montage`.

## 5. L'état à l'instant t

### 5.1 Qui est la référence

**Le lecteur.** L'aperçu n'a pas le droit d'avoir sa propre idée du format. Trois briques pures,
horloge et générateur aléatoire injectés :

1. **`Track`** — existe, déjà pur. Inchangé.
2. **Une loi de servo unique**, `theatre_contrats/mouvement.py` (stdlib seule) : cible, rampe,
   mode `random`, bizarreries du §2.1. `Servo` (réel) et `ServoSim` (sim) s'appuient dessus au lieu
   de porter chacun leur copie ; la sim gagne la rampe qui lui manque.
3. **`didier_core/sequences/etat.py`** — `etat_a(sequence, t_ms, profil, graine, pose_depart)` :
   construit les neuf `Track.emissions`, avance par ticks de 50 ms de 0 à t en appliquant chaque
   émission à la loi de servo, et rend `{servos: {nom: position}, visage: (expression, depuis_ms),
   lumieres, son: (fichier, position_ms), roues: (x, y, cap), random: {nom: enveloppe}}`.
   `courbes(sequence, …)` rend la même chose échantillonnée sur toute la durée (une séquence de
   300 s = 6 000 ticks × 5 servos : quelques millisecondes).

Garde-fou gravé : pour chacune des 48 séquences, la liste `(instant, piste, valeur)` produite par
`etat.py` est IDENTIQUE à celle d'`AnimationManager` piloté en temps virtuel. Cela demande
d'injecter l'horloge dans `AnimationManager` (aujourd'hui `TimeUtils` global) — petit, et utile
au-delà de l'éditeur.

**Correction du principe du 12/11** : « servos = interpolation des images clés » devient « servos
= cibles rejouées à travers la loi de mouvement ». Entre deux images clés, la position dépend de
la rampe et de la vitesse du servo, pas d'une droite.

Le navigateur ne recalcule rien : il reçoit les courbes échantillonnées et interpole entre deux
échantillons. Une seule sémantique, en Python.

### 5.2 Le `random`

- Dans l'aperçu, le générateur est `Random(graine)` avec une graine FIXE par (séquence, piste,
  image clé) : la même tête de lecture montre toujours la même pose. Un bouton « autre tirage »
  change la graine de la session.
- Sur la piste, un `random` est un **bloc hachuré** avec son enveloppe (course min-max) et le
  tirage d'exemple en trait fin.
- **Le robot, lui, continue de tirer au hasard** : aucune graine dans le JSON, rien ne change en
  jeu. L'aperçu montre UN exemple, et le dit.
- Une partition de danse (§7) refuse le `random` : on ne tombe pas sur le temps par hasard.

### 5.3 Visage, lumières, son

- **Visage** : l'état calculé donne l'expression en cours et depuis quand. Le mannequin de la page
  l'affiche exactement (images servies par le pont, cadence lue dans `expressions.json`). La
  vignette `face_sim`, elle, reçoit le nom de l'expression et la rejoue depuis son début : exacte
  en lecture réelle, approximative au défilement — suffisant.
- **Lumières** : nom de l'effet en cours, pastille de couleur ; pas de rendu fidèle (la vraie
  classe `Lights` ne tourne pas hors du Pi).
- **Son** : c'est le NAVIGATEUR qui joue (`audio.currentTime = position`), la sim n'a pas de nœud
  audio. Fichiers servis en lecture seule par le pont, depuis `medias/audios/` et depuis le dossier
  privé du §8.

### 5.4 Roues

- **Aperçu** : intégration cinématique différentielle depuis la pose de départ, avec **le
  comportement réel de la chaîne** lu dans le profil de la machine. Aujourd'hui :
  `roues: "impulsion"` (0,41 s par image clé, accélérations bornées du `DiffDrive`). Le jour où le
  chantier roues rétablit la tenue, le profil passe à `"tenue"` et l'aperçu suit. L'éditeur ne
  modifie ni `wheels_bridge`, ni `twist_mux`, ni `twist_deadman`.
- La trajectoire calculée se dessine sur un **plan vu de dessus** (avec l'emprise du robot) :
  c'est la première fois qu'on voit OÙ une piste roues emmène Didier avant de la jouer.
- **La lecture réelle reste la seule référence** (glissement, inertie) : c'est elle qui tamponne
  la porte sim. Une épreuve mesure l'écart entre pose calculée et vérité terrain après un rejeu
  réel ; au-delà de 15 cm ou 10°, la page l'affiche en orange (un constat, pas un blocage).
- Les bornes roues du contrat (≤ 0.89, tenue ≤ 60 s, arrêt final) s'appliquent à ce que l'éditeur
  écrit, comme à tout le reste. **Elles n'autorisent aucun roulage au sol.**

### 5.5 Piloter Gazebo

Un nœud **`apercu_node`** (dans `didier_core/nodes`, lancé par `sim.launch.py` SEUL, comme
`face_sim_node` ; logique dans `etat.py`) :

- écoute `apercu_demande` (`{id, sequence: <brouillon>, t_ms, pose_depart, graine}`, ≤ 131 072
  octets, jamais latché) et répond sur `apercu_etat` (état + courbes) ;
- pour Gazebo : publie les cinq cibles `<servo>/position`, appelle `set_pose` à la hauteur de
  repos, envoie l'expression à `face` ; **refuse si `animation_state` n'est pas vide** (le vrai
  lecteur a la main) ;
- **ne publie jamais `animation_state`** : l'observateur de la porte sim ne peut donc pas
  tamponner un aperçu — par construction ;
- ne publie jamais sur `wheels` ni `cmd_vel`.

**Lecture réelle depuis la tête** : `animations_node` accepte `{"sequence": nom, "debut_ms": n}`
quand le paramètre `lecture_partielle` est vrai (sim et banc ; **faux sur Didier**). Règle de
rattrapage : la dernière image clé passée de chaque piste servo, visage et lumières est émise au
départ ; **aucune commande de roues n'est jamais rattrapée** (seules les images roues à venir
jouent) ; le son part à la position voulue si le lecteur audio sait sauter, sinon à la prochaine
image `audios`. En sim, `apercu_node` téléporte d'abord le robot à la pose calculée. Une lecture
partielle ne tamponne pas la porte (l'observateur exige 0,95 × `duration`).

Écarté : l'enregistrement Gazebo rejoué avec curseur (un second Gazebo, des journaux de plusieurs
centaines de Mo, aucun gain sur l'état calculé) ; la pause physique à chaque saut (caméra non
tranchée, §2.2).

## 6. La page `/montage`

```
┌ barre : séquence ▾ · enregistrer · rejouer en entier · valider les roues · état de la porte ┐
├───────────────┬───────────────────────────────┬──────────────────────────────────────────────┤
│ mannequin     │ Gazebo (caméra de poursuite)  │ plan vu de dessus : pose de départ,          │
│ + visage      │                               │ trajectoire calculée                         │
├───────────────┴───────────────────────────────┴──────────────────────────────────────────────┤
│ règle : secondes │ mesures.temps      ▼ tête de lecture       zoom · aimant · lecture / pause  │
│ son      ▁▃▇▅▂▁▃▇▆▃▁  (forme d'onde, traits de temps, temps forts épais)                       │
│ visage   [ parle      ][ default ][■][ default                ]                                │
│ cou      ●────╲___●──────●       ▒▒▒ random 35-80 ▒▒▒                                          │
│ œil G · œil D · bras G · bras D   (cible = point, trait = position calculée)                   │
│ roues    ▮▮  ▮▮      ▮▮          (impulsions, signe par couleur)                               │
│ lumières [ trip                 ][ off ]                                                       │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- Le brouillon vit dans la page ; chaque retouche envoie `apercu_demande` (au plus 10 par
  seconde) et redessine les courbes.
- **Enregistrer** = une demande `data_edit` `sequence` (`replace` avec `base_sha256`, ou
  `create`), verdict affiché tel quel (`conflit`, `contrat` avec son détail, `inchange`…).
  L'éditeur n'a AUCUN autre chemin d'écriture.
- **Rejouer en entier** = le vrai lecteur depuis 0 → tampon `rejeu` de l'observateur ; **Valider
  les roues** = le bouton de L1d, inchangé. L'état de la porte est toujours visible.
- Changer `duration` : la page propose « garder les instants » (les fractions sont recalculées) ou
  « étirer ». Aujourd'hui, toucher `duration` dans le JSON déplace tout en silence.
- Mannequin : vue de face, cinq angles, visage en LED, à la cadence de l'écran. C'est lui qui
  permet de juger un geste contre le son ; Gazebo ne le peut pas (§2.2).
- Téléphone : lecture seule (tête de lecture, moniteurs). On ne monte pas au pouce.

## 7. Chorégraphies : le modèle de données

### 7.1 Ce qui ne change pas

Les 48 séquences, leur format, leur lecture. Une séquence sans bloc `partition` est jouée
exactement comme aujourd'hui, au tick près.

### 7.2 Ce qui s'ajoute

**(a) Une grille par chanson** — `json/grilles/<chanson>.json`, nouveau `kind` `grille` de
`data_edit` : `{audio: "song/<fichier>.wav", sha256_audio, duree_ms, temps_ms: [...],
premier_temps_fort, temps_par_mesure, outil: "librosa 0.11"}`. Une LISTE d'instants, jamais
« BPM × n » (écart-type de 16 à 25 ms entre temps sur le corpus, `etude-danse.md` §4.1). Produite
sur le PC par un outil du venv d'outillage ; le temps fort se corrige à la main dans la page
(« le 1 est ici »). `sha256_audio` détecte un fichier différent de celui qui a été analysé.

**(b) Un bloc `partition` dans la séquence** (une clé de plus dans la liste gravée de L1d) :

```json
"partition": {
  "grille": "tactique-du-gendarme",
  "entree_mesures": 1,
  "decalage_gout_ms": 0,
  "figures": {
    "hochement":    {"temps": 1, "neck": [[0, 35], [0.5, 65]], "faces": [[0, "flash"], [0.25, "default"]]},
    "coup-de-bras": {"temps": 4, "left_arm": [[0, 70], [2, 40]]}
  },
  "placements": [
    {"figure": "hochement",    "mesures": "1-8"},
    {"figure": "coup-de-bras", "mesures": "9-16"}
  ]
}
```

Instants en temps musicaux (0,5 = contretemps). `decalage_gout_ms` est le seul réglage de
« sensation » (jouer un rien derrière le temps) : il est à David, l'agent n'y touche pas.

**(c) Une compilation pure** — `theatre_contrats/partition.py` : `compiler(partition, grille)`
→ pistes ordinaires aux temps NOMINAUX (l'instant du temps dans le fichier audio, sans aucun
retard de machine). La page compile à l'enregistrement et envoie partition ET pistes ;
**`verifier_sequence` recompile et refuse si les pistes ne sont pas celles de la partition** :
la source et le compilé ne peuvent pas diverger. Règles de contrat d'une partition : pas de
`random`, **pas de piste `wheels` en v1**, amplitude d'un saut de bras plafonnée (30 unités au
départ, `etude-danse.md` §7), `duration` = durée de la chanson + entrée.

**(d) Un profil de retards par machine** — `json/profils/<machine>.json`, nouveau `kind`
`profil`, relu à chaud :

```json
{"mesure_le": "2026-12-01", "methode": "banc filme, 3 passes",
 "son_ms": 140, "visage_ms": 45,
 "servos": {"neck": {"latence_ms": 60, "vitesse_u_s": 160}, "left_arm": {"latence_ms": 110, "vitesse_u_s": 33}},
 "roues": "impulsion"}
```

**(e) Le lecteur applique le profil au chargement** quand la séquence porte une partition :
une image clé de servo veut dire « ÊTRE ARRIVÉ à cette valeur à cet instant », et le lecteur
l'émet à `t + son_ms − latence − |Δ| / vitesse − 25 ms` (formule de `etude-danse.md` §3.4) ; le
visage est avancé de `visage_ms − son_ms`. Fonction pure, valeurs gravées en test. Sans profil,
ou sans partition : avance nulle, comportement d'aujourd'hui. **Les roues ne sont jamais
décalées** par ce mécanisme (refusé par le contrat du profil). Bornes : |avance| ≤ 1 500 ms.

### 7.3 Le vrai choix : où appliquer les retards

| | Compilés en dur dans le fichier (`etude-danse.md` §5) | **Appliqués par le lecteur, depuis le profil de la machine** (recommandé) |
|---|---|---|
| Code embarqué | inchangé | une fonction pure de plus au chargement (cœur, pas le chemin roues) |
| Mini-Didier et Didier | deux fichiers compilés différents, alors que `data/` est commun | le même fichier, deux profils |
| Après une nouvelle mesure (rail servo 24 V, autre carte son) | recompiler et repasser la porte sim pour chaque danse | changer un profil |
| Boucle filmée | réécrit des centaines d'images clés | corrige cinq nombres |
| Risque | divergence entre machines, fichiers illisibles à la main | un profil faux décale toute une piste (borné, visible dans la page) |

Le profil n'entre pas dans la porte sim : la sim n'a rien à dire sur les retards du matériel
(elle a son propre profil, qui lui donne enfin des bras lents).

### 7.4 Dans la page

Règle en mesures.temps, traits de temps sur toutes les pistes, **aimant** (temps, demi-temps,
quart), figures posées comme des clips et étirées par mesures entières. Sur chaque image clé de
servo : la cible (le point), le départ calculé de la commande (un trait en amont) et **l'écart
d'arrivée chiffré** (« +12 ms »). Un geste impossible (le bras ne peut pas parcourir Δ dans le
temps disponible) passe en rouge AVANT d'être joué : c'est la règle « bras lents = temps forts »
rendue visible.

## 8. Fichiers audio et droits

### 8.1 Règle proposée

- **Aucun fichier d'un morceau du commerce dans le dépôt public.** Dossier privé hors git, sur le
  PC (`~/.local/share/didier/audios-prives/`, chemin dans une variable `DIDIER_AUDIO_PRIVE_DIR`),
  posé sur les Pi par un rôle Ansible dédié, sur le modèle du rôle `secrets` ; monté dans les
  conteneurs à côté de `medias/audios/`. Une séquence y renvoie par `prive/<fichier>.wav`.
- Le contrat accepte une référence `prive/…` sans exiger le fichier (la CI publique ne l'a pas) ;
  le lecteur journalise une erreur claire s'il manque ; `ecart-pi.sh` compare les empreintes.
- **WAV pour les chansons de danse** (pas d'amorce MP3 à deviner, `etude-danse.md` §3.3).
- La grille (une liste d'instants et un nom de fichier) reste dans le dépôt : elle ne contient pas
  l'œuvre. Si David préfère ne pas afficher les titres, les grilles vont aussi dans le dossier
  privé — une ligne de configuration.

### 8.2 Droits

Inchangé depuis `etude-danse.md` §4.5 (grandes lignes, pas un conseil juridique) : diffusion en
public = SACEM par l'organisateur, droits voisins (SPRÉ) pour un enregistrement du commerce, titre
au relevé de programme ; cas de la déambulation sans organisateur non tranché par les sources.
Pas d'assurance, pas de sortie publique roues actives avant la RC (étude standards, 11/11).

### 8.3 Fait découvert le 13/11, hors périmètre de l'étude

`git ls-files data/medias/audios` rend **255 fichiers suivis**, dont `song/great-balls.mp3`,
`song/tactique-du-gendarme.mp3`, `song/le-professionnel.mp3`, `song/annie.mp3`. Ce dépôt est
public : ces enregistrements du commerce y sont déjà publiés, historique compris. Les retirer de
l'arbre ne suffit pas, et réécrire l'historique est une décision de David (question 3, §12).
Rien n'a été modifié.

## 9. Le réglage fin filmé

### 9.1 Ce qu'on mesure

Ce qui compte pour le public : **l'écart entre l'arrivée du geste et le temps ENTENDU**. On le
mesure directement, sans passer par l'horloge du robot.

1. **Prise** : une webcam USB fixe, image + son dans le même fichier (`ffmpeg`, v4l2 + ALSA),
   exposition manuelle, éclairage constant (leçons du 10/07 et du banc témoin §9), 60 images/s si
   la webcam le permet.
2. **Décalage image/son de la webcam** : cinq claps de mains devant l'objectif au début de la
   prise. L'agent en tire le décalage propre à la caméra (médiane) — c'est le seul repère
   indépendant du robot. Le flash du visage ne peut pas servir de repère : son retard fait partie
   de ce qu'on mesure.
3. **Où en est la chanson** : corrélation croisée du son enregistré avec le fichier de
   référence → l'instant de la chanson à la milliseconde, donc tous les temps de la grille. Plus
   robuste que de détecter des beats dans une prise d'atelier.
4. **Quand le geste arrive** : une zone d'image fixe par actionneur (cou, chaque bras, chaque œil,
   visage). Différence d'images dans la zone : début de mouvement au franchissement du seuil,
   ARRIVÉE quand l'énergie retombe. Visage : luminosité de la zone (allumé / éteint — la caméra
   ne lit pas un motif, elle n'a pas à le faire).
5. **Écart par événement**, apparié à l'arrivée attendue ; **médiane par piste** ; correction
   `profil.<piste> += médiane` ; rejeu ; arrêt quand |médiane| ≤ 10 ms et 90 % des événements dans
   ±40 ms (cible de `etude-danse.md` §3.1), ou après trois passes.

Résolution : à 30 images/s une arrivée est connue à ±17 ms, mais la médiane de N événements l'est
à ≈ 10/√N ms : **huit gestes par piste suffisent** pour corriger une avance moyenne. La caméra ne
suffit pas, en revanche, à mesurer la gigue d'un geste isolé.

### 9.2 Deux temps

- **Étalonnage, une fois par machine** : séquences générées (un saut par servo, trois amplitudes,
  dix répétitions ; dix lancements du son) → `latence_ms` et `vitesse_u_s` par servo, `son_ms`,
  `visage_ms`, **et la gigue du démarrage du son** — la mesure qui décide de tout
  (`etude-danse.md` §6 question 1). Au-delà de ≈ 30 ms de gigue, aucun profil ne rattrape : il
  faut changer de lecteur audio (lot à part, `mpv` ou `sounddevice`).
- **Vérification, par danse** : jouer la danse, sortir le tableau des écarts par piste et par
  mesure, corriger le profil si une piste a dérivé.

### 9.3 Qui fait quoi

| L'agent, seul | David |
|---|---|
| générer les séquences d'étalonnage, lancer les prises, analyser, écrire le profil (`data_edit`, `kind: profil`), rejouer, rendre un tableau et une image annotée par piste | les cinq claps ; placer et verrouiller la caméra ; valider les zones d'image une fois |
| signaler un geste impossible, une piste instable, une gigue hors cible | choisir les figures, les amplitudes, le `decalage_gout_ms`, décider si un bras en retard est drôle |
| **ne jamais retoucher une partition** | tout ce qui est de la mise en scène |

### 9.4 Bancs et limites

- **Mini-Didier (banc témoin)** : même Pi, même PCA9685, même code, visage WS2812, bras sur SG90,
  **pas de cou** (concept du 12/11). Il valide la MÉTHODE, la chaîne son si elle est celle du
  robot, le visage, le tick. **Son profil n'est pas celui de Didier** (SG90 ≠ ASME) : c'est
  précisément pourquoi le profil est par machine. L'agent y travaille seul : aucune pièce ne peut
  blesser, et la boucle refuse toute séquence portant une piste `wheels`.
- **Tête de Didier sur l'établi** (cou + yeux, démontée pendant la refonte) : étalonnage réel du
  cou et des yeux, avec David.
- **Bras de Didier** : 37 N·m, boucle ouverte, courant jamais mesuré. Pas de boucle autonome :
  David présent, mesure de courant (INA219) avant un essai long, amplitude plafonnée. Relecture
  adverse (Fable) avant la première prise.
- **Roues** : hors de ce plan. Le jour venu : sur cale uniquement avant la refonte électrique,
  protocole caméra, Opus minimum. La boucle filmée ne lance jamais de roues.
- `time.monotonic()` dans la chaîne du lecteur avant toute danse réelle (`etude-danse.md` §7).

## 10. Risques

| Risque | Parade |
|---|---|
| L'aperçu diverge du lecteur | il est bâti sur `Track` et la loi unique ; égalité des émissions gravée sur les 48 séquences |
| Extraire la loi de servo casse le robot | tests existants des deux implémentations verts SANS être modifiés ; contrôle par mutation ; Pi hors robot avant fusion |
| La page devient un second logiciel | trois fichiers statiques, aucune dépendance, aucune écriture hors `data_edit` ; budget borné, repli sur un composant existant |
| Gazebo trop lent ou trop saccadé | le mannequin porte le jugement du calage ; Gazebo ne sert qu'à l'espace ; cadence de la caméra de poursuite à essayer au lot E0 |
| Lecture partielle : une commande de roues ressort au mauvais moment | aucune commande de roues rattrapée, paramètre faux sur Didier, test gravé |
| La gigue du son dépasse la cible | mesurée au lot F1 AVANT d'écrire des danses longues ; sinon lot « lecteur audio » |
| Quota `data_edit` (200 sauvegardes par jour) atteint en séance | l'aperçu n'écrit pas ; `inchange` ne compte pas ; à surveiller, à relever si besoin |
| Sim à 0,88 du temps réel, lecteur à l'horloge murale | facteur temps réel affiché dans la page ; l'écart roues calculé / réel est un constat |
| Droits | fichiers hors dépôt ; relevé de programme ; §8.3 à traiter |

## 11. Plan par lots

Préalable : **L1d-2 et L1d-3 terminés**. Chaque lot : documentation dans le même lot, sim verte
en fin de lot, déploiement hors robot sur un Pi dès qu'un package déployé change.

| Lot | Contenu | Porte vérifiable | Modèle, durée | Ce que le lot supprime |
|---|---|---|---|---|
| **E0 — sondes** | lever les inconnues du §2.2 : image en pause, cadence 15 Hz en 320×240 de la caméra de poursuite et facteur temps réel, appel de `set_pose` depuis un nœud, limite de vitesse du cou dans l'URDF | tableau de mesures ajouté à cette étude | Opus, ≈ 1,5 h | les points « non tranché » |
| **E1 — état calculé** | loi de servo unique (`theatre_contrats/mouvement.py`), horloge injectée dans `AnimationManager`, `etat.py` (servos, random à graine, visage, son, roues en impulsion), profil de la sim | six suites vertes sans retouche des tests existants ; égalité des émissions sur 48 séquences ; valeurs gravées ; mutations rouges | Opus, ≈ 6 h | la double écriture de la loi de servo (`servo.py` / `servos_logic.py`), l'absence de rampe en sim, l'horloge globale du gestionnaire |
| **E2 — tête de lecture en sim** | `apercu_node`, topics `apercu_demande` / `apercu_etat`, pilotage de Gazebo, pose de départ, lecture partielle (`debut_ms`), `validate-apercu.sh` | épreuves : saut à t → `joint_states` à ±0,05 rad en ≤ 1,5 s ; pose = pose calculée à ±2 cm ; refus pendant une animation ; registre de la porte inchangé après 20 aperçus ; aucune commande de roues rattrapée ; écart calculé / vérité terrain noté | Opus, ≈ 5 h | « `animations_node` ne sait jouer que du début » |
| **E3 — page `/montage`** | pistes, images clés, tête de lecture, mannequin, visage, forme d'onde, plan vu de dessus, enregistrement `data_edit`, boutons de la porte ; captures | en sim : retoucher `moon-walk`, voir l'aperçu, enregistrer, rejouer, tamponner ; un JSON hors contrat affiche son refus ; `test_web_protocol.py` étendu ; **David valide la page** | Opus, ≈ 8 h (deux séances) | l'édition de séquences en TEXTE du panneau L1d-3 (les quatre autres familles gardent le leur) |
| **C1 — partition** | outil de grille (venv d'outillage), `kind` `grille` et `profil`, bloc `partition`, compilation pure, cohérence au contrat, profil appliqué au chargement, dossier audio privé + rôle Ansible | danse de référence : instants compilés gravés à la main ; contrat refuse une piste qui ne vient pas de sa partition ; sans profil, les 48 séquences émettent comme avant ; Pi hors robot : fichier privé présent, `ecart-pi.sh` vert | Opus, ≈ 6 h | les lots D0 et D1 de `etude-danse.md` (repris ici) |
| **C2 — montage musical** | règle en mesures, aimant, figures en clips, écart d'arrivée chiffré, geste impossible en rouge ; **première danse** (haut du corps) | une danse de 16 mesures écrite dans la page, tamponnée par la porte ; tous les écarts d'arrivée calculés ≤ 40 ms ; **David la regarde** (mannequin + son) | Opus, ≈ 4 h | le calage « à la main sur des fractions de durée » |
| **F1 — banc filmé** | prise `ffmpeg`, analyse (venv d'outillage : numpy, opencv), séquences d'étalonnage, boucle de correction du profil, sur le mini-Didier | gigue du démarrage du son chiffrée sur dix lancements ; profil convergé en ≤ 3 passes (\|médiane\| ≤ 10 ms, 90 % dans ±40 ms) sur visage et bras ; la boucle refuse une piste `wheels` | Opus, ≈ 5 h + une séance David | le lot D2 de `etude-danse.md` ; « retard son inconnu » |
| **F2 — Didier réel** | tête sur l'établi, puis bras après la refonte électrique | relecture adverse avant la première prise ; profil de Didier daté | Fable (relecture) + Opus, avec David | le lot D3 de `etude-danse.md` |

Total ≈ 34 h d'agent hors F2. Ordre recommandé : E0 → E1 → E2 → E3 → C1 → C2 → F1. E1 à E3
servent toutes les séquences (et l'éditeur final de L4) ; les chorégraphies viennent dessus.
Chaque lot Opus reçoit une spec fermée courte (Fable, ≈ 30 min) si David veut déléguer sans
suivre. Aucun lot ne touche `wheels_bridge`, `twist_mux`, `twist_deadman`, `wheels_node`.

**Hors plan, à ouvrir séparément** : tenue des pistes roues (conception Fable, réalisation Opus,
sim puis protocole caméra) — préalable de toute chorégraphie qui se déplace ; « danser en
suivant » (`etude-danse.md` §7 bis, lot D4) ; lecteur audio à horodatage si F1 le demande.

## 12. Questions pour David

1. **Les retards sont appliqués par le lecteur, depuis un profil par machine** (§7.3) — donc une
   petite fonction de plus dans le code embarqué, contre l'avis initial de l'étude danse.
   *Défaut : oui.*
2. **L'éditeur général d'abord (E1-E3), les chorégraphies ensuite (C1-C2)** — la première danse
   arrive après ≈ 30 h. L'inverse (danse d'abord, écrite en JSON à la main, page plus tard) la
   donne en ≈ 10 h mais sans montage. *Défaut : l'éditeur d'abord.*
3. **Morceaux du commerce** : dossier privé hors dépôt pour les nouveaux (§8.1) ; et pour les
   chansons DÉJÀ publiées dans ce dépôt (§8.3), les sortir de l'arbre maintenant et décider à part
   d'une réécriture de l'historique ? *Défaut : oui aux deux, la réécriture restant ta décision.*
   Quels deux ou trois morceaux pour commencer ?
4. **La boucle filmée tourne seule sur le mini-Didier** (visage, bras SG90, son ; jamais de
   roues), et seulement avec toi sur Didier. *Défaut : oui.*

## Sources

Code (13/11, main 8996126) : `packages/didier_core/didier_core/sequences/{track,animation_manager}.py`,
`actions/servo.py`, `nodes/{animations_node,face_sim_node}.py`,
`packages/didier_sim/{didier_sim_lib/servos_logic.py,scripts/servos_sim_node,config/gz_bridge.yaml,worlds/stage.sdf}`,
`packages/didier_description/urdf/*.xacro`, `packages/didier_web/` (pont, `data_edit.py`),
`packages/theatre_contrats/theatre_contrats/donnees.py`, `data/json/sequences/` (48 fichiers),
`machines/sim/validate-rehearsal-route.sh`, `docs/operations.md` (constat « impulsions »).
Sonde Gazebo du 13/11 : conteneur jetable sans réseau, Gazebo Sim 8.15.0.
Web (consulté le 13/11/2026) : doc Choregraphe 2.1 (miroir fileadmin.cs.lth.se) ·
npmjs.com/package/animation-timeline-js · npmjs.com/package/@theatre/studio ·
wavesurfer.xyz/docs · gazebosim.org/api/sim/8 (LogPlayback, PlaybackScrubber).
Non vérifié : licence de wavesurfer.js v7 ; rafraîchissement des caméras Gazebo en pause.
