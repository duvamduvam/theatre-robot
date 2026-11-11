# Étude — l'architecture de commande des actionneurs (roues, bras, cou, yeux)

*Ouverte le 2026-09-26 à la demande de David : « fais une analyse sur l'architecture de
commande des roues et des bras, est-ce sérieux ou d'autres solutions pourraient être
envisagées pour une meilleure qualité — toujours dans un contexte DIY, je ne suis pas un
industriel ».*

**Cadrage assumé** : tout ce qui est proposé ici doit être achetable à l'unité, montable à
l'établi, imprimable sur une CR-10, et compréhensible six mois plus tard. Aucune solution
« industrielle » (ros2_control complet, EtherCAT, servomoteurs à variateur) n'est retenue
comme cible, même quand elle serait techniquement supérieure.

## 1. L'état des lieux, relevé dans le code le 2026-09-26

| | Canal PCA9685 | Servo | Défaut |
|---|---|---|---|
| Cou | 4 | *modèle absent de la doc* | 50 |
| Bras gauche | 5 | `ASME-MR` | 90 |
| Bras droit | **15** | `ASME-MR` | **180** |
| Œil gauche | 7 | `JX CLS-12V7346` (46 kg·cm, 12 V) | 70 |
| Œil droit | 8 | idem | 45 |
| Roues (PWM+DIR ×2) | 0, 1, 2, 3 | — | — |

Boucle à **20 Hz** (`TICK_PERIOD_S`, `robot_static.py:131`), rampe linéaire
`RAMP_SPEED = 160` unités/s (`servo.py:28`, ~0,6 s pour la pleine course), et **six nœuds ROS
distincts** écrivent sur la **même puce** PCA9685 à l'adresse `0x40` — jamais écrite
explicitement, donc implicite (`servo.py:57-60`).

## 2. Ce qui est sérieux — et il y en a plus qu'on ne croit

Il faut le dire avant les critiques, parce que c'est vrai et que ça se perd de vue :

1. 🟢 **La rampe utilise le `dt` RÉEL mesuré, pas les 50 ms supposés** (`servo.py:190-201`).
   C'est exactement ce qui sépare un code qui marche sur le bureau d'un code qui marche sur
   scène : quand le tick dérape, le mouvement ne dérape pas avec lui.
2. 🟢 **L'anti-spam I²C** (`servo.py:176-188`) : la valeur n'est écrite que si l'angle entier
   change. C'est ce qui évite de marteler le bus à 20 Hz avec des variations sous le degré —
   et le commentaire dit que le servo vibrait avant.
3. 🟢 **Le deadman servo, calqué sur celui des roues** (`servo.py:34, 106-107, 209-214`), avec
   une péremption `temps restant + 2 s`. Peu de projets amateurs traitent la fin d'animation
   comme un cas d'arrêt ; ici c'est fait.
4. 🟢 **38 tests unitaires** sur les servos, dont 17 sur le gaze, exécutables sans matériel.
5. 🟢 **Le suivi de position est interne, pas relu du PCA9685** (`servo.py:125`) : une
   transaction I²C de moins par tick, et un comportement déterministe en test.

**Verdict sur ce point : oui, c'est sérieux.** Ce n'est pas du code de bidouille — c'est du
code qui a déjà rencontré le réel et en a tiré des leçons.

## 3. Les trois faiblesses structurelles

### 3.1 🔴 La boucle est ouverte de bout en bout — on ne sait JAMAIS où sont les bras

Aucune lecture de position, de courant, de couple ni de température n'existe dans le code de
production (relevé : « absent » sur les quatre). Le robot **commande** ses actionneurs ; il ne
les **observe** pas.

Conséquences concrètes, par ordre de gravité :

1. **Aucune détection de blocage.** Un bras qui rencontre un décor, un câble ou une personne
   continue de pousser jusqu'à ce que quelque chose cède. Sur un actionneur annoncé à
   **380 kg·cm — soit ~37 N·m**, c'est-à-dire environ **9 kg de force au bout d'un bras de
   40 cm** — ce n'est pas un défaut de confort, c'est un sujet de sécurité pour un robot qui
   joue près du public.
2. **Position réelle inconnue au démarrage.** Le code part de `default_pos`, mais rien ne
   garantit que le bras y est. Le premier mouvement peut donc être une course complète
   inattendue.
3. **Aucune donnée pour le télédiagnostic.** Le chantier télédiagnostic sait lire des logs ;
   il ne peut rien dire d'un servo qui chauffe ou qui force, faute de mesure.

### 3.2 ⚠️ Six processus, une seule puce, aucune coordination

Six nœuds ROS instancient chacun leur propre `ServoKit` sur la **même** puce. Le bus I²C est
sérialisé par le noyau, donc il n'y a pas de corruption — mais il reste deux couplages
invisibles :

- **la fréquence PWM se joue à la course au démarrage** (déjà documenté dans
  [`etude-chemin-commande-roues.md`](etude-chemin-commande-roues.md) §2.1) ;
- **l'adresse `0x40` est implicite.** Le jour où un second PCA9685 arrive (c'est justement le
  plan 0x40/0x41), rien dans le code ne dit qui parle à qui. Une erreur d'adresse ne
  produirait pas une exception mais un **mouvement inattendu**.

**Correctif à coût quasi nul, à faire avant la séparation 0x40/0x41** : écrire l'adresse
explicitement à chaque instanciation. Deux lignes, et un piège de moins.

### 3.3 ⚠️ Aucune limite d'angle par servo

Le clipping est universel : 0-99 en consigne, 0-180° en sortie (`servo.py:173`). Mais chaque
articulation a sa propre butée mécanique, et rien dans le code ne la connaît. Un bug, une
valeur d'animation erronée ou un fichier de séquence mal écrit peut donc commander une
position que la mécanique refuse — et le servo forcera jusqu'à la limite de son couple.

Le contrat de données testé (« chaque visuel/audio/brique référencé doit exister ») protège
des références manquantes, pas des valeurs hors butée.

## 4. ⭐ LE DOUTE EST LEVÉ — et il révèle un actif dormant

`docs/hardware/overview.md` écrivait : *« The arms and mouth are controlled by ASME-MR
380 kg·cm **continuous-rotation** RC servos. »* J'ai d'abord soupçonné une erreur d'une lettre
(`ASME` continu / `ASMC` positionnel chez DSSERVO). **C'était plus intéressant que ça.**

La photo produit du dépôt (`docs/pictures/consumable-parts/arm-motor.png`) confirme la
référence `ASME-MR` et la mention « 360 Degree » — donc **pas d'erreur de référence**. Mais la
fiche du fabricant dit ce que « ASME-MR » désigne réellement :

> **`ASME-MR` = Magnetic Encoding Series Digital Servo, 360 degree.** Capteur magnétique
> **12 bits**, *« uses digital ports to directly read sensor data and **return angle
> information**, with a true 360-degree controllable range »*. Origine réglable à 1500 µs dans
> les 360°. Couple de démarrage 380 kg·cm, couple de maintien 340 kg·cm.

**Ce sont donc des servos POSITIONNELS**, pas à rotation continue : le modèle de commande de
`servo.py` (`target_pos`, rampe, `default_pos`) est **juste**. La documentation était fausse,
elle est corrigée.

### ⭐ Et la vraie découverte : le retour de position EXISTE DÉJÀ dans le matériel

La faiblesse n° 1 de cette étude — « la boucle est ouverte, on ne sait jamais où sont les
bras » — **n'est pas une fatalité du matériel. C'est un câble qu'on n'a pas branché.**

Ces servos embarquent un encodeur magnétique 12 bits et savent renvoyer leur angle. Le robot
possède donc déjà, sur ses deux actionneurs les plus puissants, exactement ce que j'allais
recommander d'acheter.

**Ce qui reste à vérifier, et qui demande le robot** (gelé depuis l'incident Pi 4 du
2026-09-12) :

1. **Le modèle exact** : `ASME-MR` simple ou variante `ASME-MRB` ? La fiche la plus explicite
   sur le retour d'angle est celle du `MRB`. À lire sur l'étiquette du servo monté.
2. **Le câblage** : la photo montre **deux connecteurs** (un câble servo 3 fils classique, plus
   un second). Le second est probablement la liaison de retour. Est-il seulement raccordé sur
   Didier, ou pend-il dans le vide depuis le début ?
3. **Le protocole** : « digital ports » n'est pas une spécification. Quel bus, quelle trame ?
   À obtenir du fabricant ou à observer à l'analyseur logique.

⚠️ Tant que ces trois points ne sont pas levés, **ne pas compter dessus** — mais **ne pas
acheter de solution de retour non plus** (§5.C devient sans objet si le retour est déjà là).

## 5. Les alternatives, classées par rapport gain / effort

### 🥇 A′ (NOUVEAU, prioritaire depuis le §4). Brancher et lire le retour d'angle des bras

**Coût : zéro euro si le câble est déjà là.** Avant toute autre chose, établir si le retour de
position des `ASME-MR` est raccordé et lisible. S'il l'est, on obtient d'un coup la position
réelle des deux actionneurs les plus dangereux du robot — et, par comparaison entre consigne et
position réelle, **une détection de blocage** : si l'écart ne se referme pas, c'est que le bras
force contre quelque chose.

C'est exactement la fonction que A et C ci-dessous allaient acheter. **À instruire en premier**,
dès que le robot est réalimentable.

### 🥈 A. Mesurer le courant des servos — le meilleur rapport SI le retour d'angle n'existe pas

**Le problème qu'elle règle** : la détection de blocage (§3.1), donc le seul point de
*sécurité* de cette étude.

**Comment, en DIY** : un module **`INA219`** (mesure tension + courant sur shunt, I²C) ou un
**`ACS712`** (sortie analogique, isolé par effet Hall) sur l'alimentation des servos. On ne
touche à aucun servo, à aucune mécanique, à aucun câblage de commande : on insère une mesure
sur le rail.

- **Mesure globale** (un seul capteur sur le rail servos) : ~3 €, détecte « un servo force »
  sans dire lequel. Suffit à déclencher un arrêt de sécurité.
- **Mesure par servo** : un capteur par ligne, plus cher et plus de câblage, mais permet de
  nommer le coupable et alimente le télédiagnostic.

⚠️ L'`INA219` est en I²C, que l'étude odométrie interdit **pour les capteurs de roue** — la
raison y est la longueur de câble et le bruit moteur. Ici le capteur est dans le même coffre
que la puce, sur quelques centimètres : le contexte n'est pas le même. À trancher, pas à
appliquer mécaniquement.

**Effort** : une carte, un nœud de lecture, un seuil. **Gain** : on passe d'« aucune détection
de blocage » à « le robot sait qu'il force ».

### 🥉 B. Passer les YEUX et le COU en servos à bus série

**Le problème qu'elle règle** : la boucle ouverte (§3.1) et les limites d'angle (§3.3), sur
les articulations où c'est le plus utile — le regard, qui est déjà asservi par le gaze.

Les servos à bus série (**Feetech `STS3215` / Waveshare `ST3215`**, ~15-25 € pièce ;
`LX-16A` ; Dynamixel `XL330` plus cher) renvoient **position réelle, charge, température et
tension**, acceptent des **limites d'angle stockées dans le servo**, et se chaînent **sur un
seul fil** — ce qui décharge l'I²C au lieu de l'encombrer.

⚠️ **Ils ne peuvent PAS remplacer les bras** : ces séries plafonnent vers 30-60 kg·cm, très
loin des 380 annoncés. C'est une amélioration ciblée sur les yeux (46 kg·cm actuels) et
peut-être le cou, pas une refonte.

**Effort** : moyen — nouveau bus, nouveau protocole, nouveau nœud, et il faut retoucher les
supports imprimés (l'empreinte diffère). **Gain** : les articulations d'expression deviennent
observables.

### C. Ajouter un retour de position sur les bras — ⚠️ probablement SANS OBJET (cf. §4)

Si le test du §4 révèle des servos à rotation continue, le retour de position devient
**indispensable** et non plus confortable. En DIY : un **potentiomètre** monté sur l'axe de
sortie (le plus simple, le plus robuste, quelques euros) ou un **encodeur magnétique AS5600**
(sans contact, mais I²C).

**Effort** : mécanique (il faut un accouplement propre sur l'axe). **Gain** : on sait enfin où
sont les bras.

### D. Ce que je NE recommande PAS

- **`ros2_control` pour les servos.** C'est la réponse « propre » et elle est hors sujet ici :
  elle impose une refonte complète pour un robot dont les actionneurs n'ont, pour l'instant,
  aucun retour à offrir à un contrôleur. À reconsidérer **après** A ou B, jamais avant.
- **Remplacer les servos de bras.** 380 kg·cm en bus série n'existe pas à un prix DIY. Et
  s'ils sont positionnels (hypothèse la plus probable), ils font déjà leur travail.
- **Un microcontrôleur dédié aux servos.** Ajouter une carte pour piloter ce que le PCA9685
  pilote déjà correctement, c'est déplacer la complexité sans la réduire — le même
  raisonnement qui a fait écarter les cartes du commerce pour l'odométrie.

## 6. Ce que je recommande, dans l'ordre

0. ⚠️ **Rappel de contexte** : le robot est **gelé depuis le 2026-09-12** (incident Pi 4).
   Tout ce qui demande de l'alimenter attend la levée de ce blocage — ce qui inclut les
   points 1 et 4.
1. ✅ **FAIT le 26/09** : le doute du §4 est levé (servos **positionnels** à encodeur
   magnétique), `overview.md` est corrigé, et il en sort une piste **A′** qui prime sur tout
   le reste : **le retour de position existe déjà dans le matériel**.
2. **Rendre les adresses I²C explicites** (§3.2). Deux lignes, à faire **avant** la séparation
   0x40/0x41, pas après.
3. **Coder les limites d'angle par servo** (§3.3), dans la configuration, avec un test qui
   refuse une valeur hors butée. C'est le genre de garde-fou que ce projet sait déjà écrire.
4. **Instrumenter le courant des servos** (§5.A) — le seul point qui touche la *sécurité*.
5. Envisager les servos à bus série pour les yeux (§5.B) **seulement** quand 1 à 4 sont faits,
   et jamais pendant une période de préparation de spectacle.

**Et une remarque de méthode pour finir** : les points 1, 2 et 3 ne coûtent presque rien, ne
touchent pas au chemin roues, et peuvent se faire pendant que le robot est en pièces. Le
point 4 demande une carte à 3 €. Aucun des cinq ne demande de renoncer à quoi que ce soit de
ce qui existe — **cette architecture n'est pas à refaire, elle est à instrumenter.**
