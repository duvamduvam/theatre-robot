# Inventaire du matériel EMBARQUÉ sur Didier (2026-09-03)

> **Complété le 2026-11-05** par un second tour filmé, robot remonté :
> [`releve-2026-11-05.md`](releve-2026-11-05.md). Il corrige ici quatre lectures (haut-parleurs
> `ICU 570`, TC Helicon **VoiceTone C1** tenu par une sangle, alimentation **SD-50B-5** lue,
> isolateur audio confirmé monté) et porte l'état des étages, la proposition d'implantation
> et les vérifications à faire avant la commande des cartes.

> **État : première passe.** 139 des 185 images d'une vidéo d'atelier de 3 min 05 s ont été
> lues (les 46 écartées sont sous le seuil de netteté). C'est le **troisième gisement** de
> matériel du projet, et le seul qui n'avait jamais été relevé : l'inventaire du stock du
> 02/09 se terminait sur « **le robot reste à filmer** ». C'est fait.

**À quoi sert ce fichier.** À dire ce qui est **physiquement sur le robot**, avec les
références **réellement lues**. Il complète `inventaire-stock.md` (ce qu'on a en bac) et
`overview.md` (ce que l'architecture *prévoit*). Les trois ne disent pas la même chose, et
c'est précisément l'écart entre eux qui est utile — voir §1.

**Ce que ce fichier N'EST PAS.** Un relevé exhaustif. La vidéo est filmée à main levée,
**muette** (David ne commente pas — confirmé), en gros plans souvent flous, pendant une
**intervention mécanique en cours**. Donc :

- **Une absence ici ne prouve rien.** Beaucoup de matériel est dans des boîtiers fermés,
  hors cadre, ou noyé dans un faisceau. « Non observé » ≠ « pas sur le robot ». C'est
  l'erreur exactement symétrique de celle du 03/09 (`croisement-etudes.md` §2), et elle
  guette dans les deux sens.
- **Aucune référence n'est déduite.** Consigne unique aux 14 agents de dépouillement : ne
  citer une référence que si elle est **lue**. Sinon la colonne est vide et la désignation
  reste descriptive. Les lectures qui engagent une décision ont été **re-vérifiées
  directement** (disque d'odométrie, étiquette « lead acid », équerre fissurée).
- **La tête est très peu filmée.** L'essentiel des plans est l'intérieur du torse et le bas
  de caisse. Conclure quoi que ce soit sur le visage, les yeux ou le micro serait abusif.

**Colonne « repère »** : `t0140` = seconde 140 de la vidéo, rejouable directement.

---

## 1. Ce que cette vidéo change

### 1.1 Le robot est EN PIÈCES — ce n'est pas un état de repos

C'est le fait dominant, et il conditionne la lecture de tout le reste. Sont **déposés** au
moment du tournage :

| Ce qui est déposé | Repère |
|---|---|
| **Le disque d'odométrie garni de ses 10 cibles**, posé à même le sol | `t0169` |
| Pignons, jantes, maillons de chaîne, visserie — au sol, avec un **pied à coulisse** | `t0000`, `t0009` |
| Panneau rouge du torse (tenu à la main, caméra glissée dans l'ouverture) | `t0136`, `t0139`, `t0150` |
| Panneau de torse blanc perforé + panneau gris, appuyés contre le châssis | `t0039`, `t0040` |
| Robot **soulevé/calé sur une bûche**, roues accessibles | `t0000`, `t0033` |
| Plusieurs connecteurs débranchés qui pendent (JST vert, 3 fils, faisceaux) | `t0020`, `t0021`, `t0061`, `t0062` |

**Conséquence directe et non négociable : le robot n'est pas en état de rouler.** Toute
reprise du chantier « test scénique au sol » (priorité 1) suppose d'abord un **remontage
complet et une revérification**, pas un simple « on rallume ». Et la remise en place du
disque d'odométrie devra repasser par les vigilances déjà écrites (fluage, faux-rond,
cibles inox).

### 1.2 Le disque d'odométrie a été déposé — vérifié à l'image

`t0169` : disque circulaire, **10 empreintes hexagonales noyées en couronne** + un écrou
hexagonal central, posé au sol, une chaîne à rouleaux juste à côté. C'est la description
exacte de ce que `chantiers.md` consigne au 02/09 : « les 2 disques sont **GARNIS** de leurs
10 cibles ». **J'ai relu l'image moi-même** plutôt que de m'en remettre au dépouillement,
parce que c'est un fait qui engage un chantier.

Ce que ça ne dit pas : **pourquoi**. Dépose volontaire pour mesurer la distance de
commutation (c'est justement l'action n° 1 du chantier odométrie : « mesurer la distance de
commutation d'un LJ12A3 sur une tête montée »), remplacement des cibles inox par de l'acier
zingué, ou tout autre motif. **À demander à David** — la réponse oriente la suite du
chantier.

### 1.3 L'« octaver » est un TC Helicon — le chantier voix gagne une référence

`t0113`-`t0116`, `t0122` : boîtier noir à façade bleue, écran, plusieurs molettes dont une
**lue `GENDER`**, marque **`TC HELICON`** lue. Le modèle exact n'est pas lisible.

`etude-voix-didier.md` appelle cet étage « l'octaver » d'un bout à l'autre, sans référence.
Or un TC Helicon à molette `GENDER` est un **processeur de voix** (harmonisation, formants,
genre) — pas un simple octaveur. Ça compte pour le chantier :

- le §3 de l'étude raisonne sur « ce que l'octaver écrase » ; si l'étage manipule les
  **formants**, il n'écrase pas la même chose qu'un doubleur d'octave ;
- le banc **V0** (« banc octaver », prochaine action du chantier) doit être monté sur
  **cet** appareil, avec ses réglages réels — donc lire son modèle et **relever la position
  de toutes les molettes avant d'y toucher** est un préalable gratuit ;
- l'écrêteur dur à ±3000 déjà mesuré est un fait distinct, il reste valable.

⚠️ Sur les images, l'appareil est **posé en vrac, non fixé**, entouré de faisceaux en
boucles libres. À confirmer : est-ce son montage habituel, ou est-il déposé comme le reste ?

### 1.4 Le récepteur HF a une référence : Shure BLX4, bande M17

`t0029`, étiquette lue au zoom : `MODEL: BLX4` / `FREQ: 662-686 MHz`. La doc mentionnait
« HF receiver » sans plus. La bande compte pour l'exploitation (662-686 MHz est une bande
UHF dont la disponibilité dépend du lieu de représentation) — à noter avant une tournée.

### 1.5 Le routeur 4G est confirmé ET référencé : Teltonika **RUT955**

`t0108`, étiquette constructeur lue : `TELTONIKA` + `RUT9…` (dernier chiffre coupé).
C'est exactement le trou signalé par `croisement-etudes.md` : le routeur 4G **est sur le
robot** mais **absent d'`overview.md`**. Il y est maintenant, avec sa gamme.

✅ **Modèle tranché le 2026-09-13 : c'est un RUT955**, David ayant relu l'étiquette sur
pièce. Le chiffre manquant n'est plus une inconnue.

> ⚠️ **DÉMENTI du 2026-09-13 — ce paragraphe disait le contraire.** Il affirmait que le
> routeur était « suspendu par ses propres câbles, sans fixation visible », et le
> classait au §3 comme écart de fiabilité n° 5. **C'est faux : le routeur est monté sur
> un support, à droite** (David, sur pièce). L'image `t0108` est un gros plan pris
> pendant un démontage : le support était hors cadre.
>
> **C'est la deuxième fois que le même piège se referme** (le premier : le ReSpeaker et
> le routeur déclarés « à acheter » alors qu'ils étaient montés — `croisement-etudes.md`
> §2). La règle qui en découle vaut pour tout ce fichier : **une absence à l'image n'est
> pas une absence sur le robot**, et un cadrage serré pendant un démontage ne prouve
> rien sur le montage.
>
> Ce qui reste vrai et utile : le support existant **est jugé perfectible par David**, et
> son amélioration est le point de départ du support imprimé en cours de conception
> (voir `~/Nextcloud/dev/didier/plans/` — hors de ce dépôt).

### 1.6 Le chargeur : ✅ RÉSOLU le soir même — c'est un Victron multi-chimie

**Le déroulé complet, parce qu'il illustre la méthode.** `t0131` — relu directement par
moi : sous la carte `…rtDrive4`, une étiquette porte `WARNING`, `battery !`, et
**`CHARGES LEAD ACID`**. Alerte levée : un profil de charge plomb sur du lithium, c'est un
feu. **David est allé sortir l'appareil et l'a photographié** (`../pictures/charger-victron.jpg`, versionnée).

**Ce que la photo montre — tout est lu :**

| | |
|---|---|
| Appareil | **Victron Energy Blue Smart Charger, 24 V / 5 A**, `IP65 waterproof`, Bluetooth |
| Étiquette dessous | `220-240V~ 1.4A`, `50-60Hz 150W`, `24V 5A`, `IP65`, `CE` |
| Phrase complète | **`CHARGES LEAD ACID OR LI-ION BATTERIES ONLY`** |
| Modes (4 LED) | `li-ion` · `recondition` · `high [29,4 V]` · `normal [28,8 V]` |
| État | LED verte sur **`li-ion`** — David était en `normal`, **il a basculé en li-ion** |

**Donc l'alerte tombe** : la mention « lead acid » n'était que la moitié d'une phrase. Le
chargeur est explicitement multi-chimie, il ne pouvait pas appliquer un profil plomb « par
erreur de conception ». **La leçon de méthode tient quand même** : une étiquette lue à
moitié dans un gros plan flou disait littéralement le contraire de la vérité. C'est
exactement pourquoi ce fichier n'autorise aucune déduction — et pourquoi une alerte se
lève en allant voir, pas en raisonnant.

**Ce qui reste ouvert, et qui est plus fin qu'un danger — une question de JUSTESSE.**
D'après Victron, l'absorption du mode `li-ion` en 24 V vaut ~**28,3-28,4 V**, valeur
calibrée pour du **LiFePO4** (8 × ~3,55 V). Or `overview.md` décrit le pack comme des
**18650**, typiquement du Li-ion **NMC** à 4,2 V/cellule (**pack de 18650 confirmé par David
le 01/11** — la chimie exacte reste à lire sur une cellule). Selon la configuration réelle :

- **7S NMC** → 28,4 V ne fait que **4,05 V/cellule** : *sous-charge* (autonomie réduite),
  sans danger. C'est `high [29,4 V]` qui donnerait pile 4,2 V/cellule ;
- **8S LiFePO4** → le mode `li-ion` est exactement le bon.

⚠️ **Et une incohérence de doc à lever** : `overview.md` écrit « 18650, 8×5 ». Si c'est
**8S** en NMC, le pack monte à **33,6 V** pleine charge — **un chargeur 24 V ne peut pas le
charger**. Donc la doc se trompe sur la configuration, ou sur la chimie.

**Trois vérifications gratuites, dans l'ordre :**
1. **Le chargeur est Bluetooth** : VictronConnect donne l'historique et la tension
   réellement atteinte. C'est la mesure qui tranche tout, sans rien démonter.
2. Compter les **cellules en série** et lire la **chimie** marquée sur les cellules.
3. Vérifier le réglage du **BMS Daly** — le garde-fou de dernier ressort, quel que soit le
   mode du chargeur.

**Au passage, le pack lui-même** : il existe bien (David, 03/09) et il est **au fond de la
caisse**, ce qui explique qu'il n'apparaisse sur aucune des 139 images. Son absence de ce
relevé était un **angle mort de cadrage, pas un écart**.

### 1.7 La transmission est par CHAÎNE (et il y a peut-être aussi une courroie)

`t0000`, `t0173`, `t0174` : **chaîne à rouleaux** enroulée sur un pignon solidaire du moyeu
de roue, descendant vers le bloc moteur-réducteur. Ce n'est donc **pas un entraînement
direct**. Séparément, `t0081` montre une **courroie crantée** entre deux poulies et un
carter alu.

`overview.md` dit « wheels differential drive » sans décrire l'organe de transmission. Un
rapport de réduction par pignons **change le calcul d'odométrie** (impulsions par tour de
roue) : le firmware Pico compte des cibles sur un disque, mais la conversion en distance
dépend de la chaîne cinématique complète. **À relever : nombre de dents pignon moteur et
pignon roue.** Sans ça, l'odométrie sortira des mètres faux.

### 1.8 La chaîne audio est entièrement de la hi-fi automobile

Références lues : haut-parleurs **`FOCAL UNIVERSAL ICU 570`** (`t0008`, `t0158` ; lu `S70` le 03/09, corrigé le 05/11 sur deux images nettes), ampli
**`FOCAL` « THE SPIRIT OF SOUND »**, `…D CLASS COMPACT AMPLIFIER` (`t0165`), mixette
**`the t.mix MicroMix 2USB`** — `USB AUDIO INTERFACE`, `XLR-MIC`, `1/4"-LINE IN`, `GAIN`,
`HEADSET` (`t0159`, `t0161`). Étiquetage des fils au standard autoradio : `RR+`, `RR−`,
`RL−`, `RF−`, `GND` (`t0164`, `t0165`).

Ça éclaire le chantier ronflement : une installation autoradio complète (ampli classe D,
masses communes, câblage RCA non symétrique) est **structurellement sensible aux boucles de
masse**. Et `t0163` montre une petite carte rouge sérigraphiée **`Car Audio Hi-Fi`** /
`HIFI` avec deux composants moulés jaunes — même famille que l'**isolateur de masse à
transformateurs** repéré au stock (`inventaire-stock.md` §1.5, repère `c0331`). Autrement
dit : il y a **peut-être déjà un isolateur monté**, et un second en stock. À vérifier avant
d'acheter une DI.

### 1.9 Deux confirmations franches

- **Cytron SmartDrive 40** : `SmartDrive 4.0` + `DS40B` + `RC1 RC2` lus nettement
  (`t0140`, `t0141`, `t0149`, revus `t0129`-`t0132`). La doc est juste, et on a la
  référence de carte exacte.
  ⚠️ **CORRECTION du 2026-09-26, de David : il y a UNE CARTE PAR ROUE, donc DEUX.**
  Ce sont des drivers à **canal simple** (`RC1`/`RC2` sont les deux entrées du mode
  radio, pas deux canaux moteur) — la vidéo n'en a filmé qu'une, et « driver moteur
  double » au tableau §1.10 était une déduction fausse tirée de ce marquage.
  Le code le confirme : `robot_config.py` réserve **quatre** canaux PCA9685 pour les
  roues (`WHEEL_LEFT_DIR=0`, `WHEEL_LEFT_PWM=1`, `WHEEL_RIGHT_PWM=2`,
  `WHEEL_RIGHT_DIR=3`), soit un couple PWM+DIR par carte. C'est cette correction qui
  rend intéressant le remplacement instruit dans `etude-odometrie.md` §6 bis : un
  contrôleur double canal remplacerait **deux** cartes, pas une.
- **PCA9685** : `HW-170` lu (`t0046`, `t0047`) — c'est la sérigraphie des modules PCA9685
  16 voies. Cohérent avec la doc et avec l'exemplaire de rechange vu au stock (`t0273`).

---

## 2. Table du matériel observé

Confiance : **H** = référence lue ou forme sans ambiguïté · **M** = famille sûre, détail non ·
**B** = forme seule, à vérifier physiquement.

### 2.1 Motricité et transmission

| Élément | Référence lue | Montage observé | Repère | Conf. |
|---|---|---|---|---|
| Driver moteur **canal simple, ×2 (une par roue** — corrigé le 26/09, cf. §1.9) | `SmartDrive 4.0` / `DS40B` / `RC1 RC2` | vissé verticalement au-dessus d'un boîtier perforé, bornier vert, domino à levier en entrée | t0140, t0141, t0149 | H |
| Carte rouge sur dissipateur alu massif, 2 trimmers `A`/`B`, bornier `M1`/`M2` | *(sérigraphie non lue)* | dans le bas de caisse, câblage rose/magenta | t0061 | M |
| Transmission **par chaîne à rouleaux** + pignon sur moyeu | — | roue ↔ bloc moteur-réducteur | t0000, t0173, t0174 | H |
| Transmission **par courroie crantée** + carter alu | — | entre deux axes, dans le bas de caisse | t0081 | M |
| Moteurs cylindriques, étiquette ESD | `CAUTION STATIC SENSITIVE DEVICES / NOT TO BE HANDLED BY UNAUTHORIZED PERSONNEL` | colliers serflex, fils rouge/noir/rose | t0062, t0067 | H |
| Repère de câblage moteur | `B` (cerclé, sérigraphié sur le flanc) | sur un des moteurs | t0064 | H |
| Moteur/actionneur, étiquette partielle | `…12V/24V… ROBOT S…` (**incomplet, ne pas compléter**) | sous équerre bois, 2 vis | t0031, t0034 | M |
| **Disque à 10 cibles hexagonales + écrou central — DÉPOSÉ AU SOL** | — | au sol, près d'une chaîne | t0169 | H |
| Pneus à crampons, jantes, moyeux, pignons déposés | — | au sol, avec pied à coulisse | t0000, t0009 | H |

### 2.2 Calculateurs, commande et réseau

| Élément | Référence lue | Montage observé | Repère | Conf. |
|---|---|---|---|---|
| **Routeur 4G** | `TELTONIKA` **`RUT955`** (chiffre confirmé sur pièce le 13/09) | ~~suspendu par ses câbles~~ → **monté sur un support, à droite** (démenti du 13/09 : le support était hors cadre) ; 2 antennes | t0108 | H |
| Driver PWM 16 voies | `HW-170` (+ `PWM`, `GND +`, `I2C ADD…`) | au-dessus d'un véroboard, JST bleu 4 pts | t0046, t0047 | H |
| Module **4 relais** | `GND IN1 IN2 IN3 IN4 VCC`, `IN1`/`IN2`/`IN3` | vissé sur carte perforée, sur panneau noir | t0099-t0101 | H |
| Composant à bornes jaunes | `…gx Zhong` + `-40~85 °C` (**partiel**) | vissé sur la carte perforée | t0043 | M |
| Cartes sur véroboard/stripboard **faites main** (TO-220 sur clip, LED témoins, trimmer, CI DIP, condensateurs) | *(aucune sérigraphie lue)* | plusieurs, vissées sur montants bois du torse | t0082, t0087, t0097, t0098 | M |
| Borniers débrochables verts (blocs 2/3 pts, plusieurs colonnes) | — | sur support gris à fentes, sur bois | t0117-t0121, t0126 | H |
| Nappes IDC arc-en-ciel | — | entre cartes du torse | t0034, t0083, t0177 | H |
| **Raspberry Pi 4 / Pi 5** | — | **NON OBSERVÉS** dans les 139 images | — | — |

### 2.3 Énergie

| Élément | Référence lue | Montage observé | Repère | Conf. |
|---|---|---|---|---|
| **Chargeur de batterie** — *voir §1.6* | `Victron Energy Blue Smart Charger 24V/5A`, `IP65`, Bluetooth, `220-240V~ 1.4A 150W`, **`CHARGES LEAD ACID OR LI-ION BATTERIES ONLY`** ; modes `li-ion`/`recondition`/`high [29,4 V]`/`normal [28,8 V]` | à bord, sous la carte SmartDrive ; **basculé de `normal` à `li-ion` le 03/09** | t0131 + photo | H |
| Boîtiers métalliques perforés (silhouette alim à découpage), **LED verte allumée** | *(aucune référence lue)* | 2 exemplaires empilés, dans le torse | t0123, t0129, t0138 | M |
| Porte-fusibles cylindriques | *(calibres non lus)* | 2, au-dessus d'un bornier vert 3 pts | t0084, t0085 | M |
| Fusible verre sur porte-fusible | *(calibre non lu)* | sur véroboard, près du `HW-170` | t0046 | M |
| Connecteurs de puissance type XT, gaine thermo rouge | — | dans le faisceau, **état de branchement indéterminable** | t0131, t0135 | B |
| Connecteurs ronds jaunes 2 pts (bullet) | — | faisceau moteur de roue | t0173 | M |
| **Pack batterie lithium** | — | **PRÉSENT — confirmé par David le 03/09**, au **fond de la caisse** ; jamais dans le cadre (angle mort, pas un écart) | — | H (parole de David) |
| **Mean Well `SD-50B-5`** | `INPUT DC24V(19-36V) 3A` / `OUTPUT +5V 10A` — **lu au zoom le 05/11** | posée de biais sur le rebord de la caisse, apparemment non fixée ; un second boîtier perforé sombre, non lu, est dans la caisse basse | `releve-2026-11-05.md` | H |
| **BMS Daly** | — | **NON OBSERVÉ** | — | — |

### 2.4 Audio et voix

| Élément | Référence lue | Montage observé | Repère | Conf. |
|---|---|---|---|---|
| **Récepteur HF** | `MODEL: BLX4` / `FREQ: 662-686 MHz` (Shure BLX4, bande M17) | dans le châssis, connecteur d'antenne, jack 3,5 | t0029 | H |
| **Processeur de voix** | `TC HELICON` **`VOICETONE C1`** (lu le 05/11), molette `GENDER`, `HARD`, `POWER` | tenu par une **sangle noire** contre la paroi du fond du coffre (05/11), noyé sous les faisceaux — le 03/09 il paraissait posé en vrac | t0113-t0116, t0122 | H |
| Mixette / interface USB | `the t.mix MicroMix 2USB`, `USB AUDIO INTERFACE`, `XLR-MIC`, `1/4"-LINE IN`, `GAIN`, `HEADSET` | sur équerres alu vissées aux montants bois | t0158, t0159, t0161, t0162 | H |
| Haut-parleurs | `FOCAL UNIVERSAL ICU 570` (corrigé le 05/11) | sur panneaux bois du torse (≥ 2 vus) | t0008, t0158 | H |
| Amplificateur | `FOCAL`, `THE SPIRIT OF SOUND`, `…D CLASS COMPACT AMPLIFIER` | sous une traverse bois, RCA en façade | t0165, t0179-t0184 | H |
| Petite carte d'isolation/adaptation audio | `Car Audio Hi-Fi` / `HIFI` (générique, **pas une référence**) — 2 composants moulés jaunes | vissée sur montant bois, cosses serties vers un HP | t0163 | M |
| Étiquetage des fils au standard autoradio | `RR+`, `RR−`, `RL−`, `RF−`, `GND` | sur le faisceau HP | t0164, t0165 | H |
| **ReSpeaker XVF3800 (anneau 4 micros)** | — | **NON OBSERVÉ** — la tête est très peu filmée | — | — |

### 2.5 Tête, vision, actionneurs

| Élément | Référence lue | Montage observé | Repère | Conf. |
|---|---|---|---|---|
| Webcam USB sur support articulé | `USB Webcam` (étiquette lue, détails flous) | pince/clip sur équerre alu, **près de la mixette dans le torse** | t0160 | M |
| Webcam (même ou autre ?) | *(aucun logo lu)* | clipsée sur le bord supérieur du panneau bois du torse | t0002, t0004 | M |
| Boîtier hexagonal blanc/gris à couvercle | — | **au sommet de la tête**, sur arceau métallique | t0000, t0011 | M |
| Deux capots ovoïdes imprimés 3D (« oreilles »), filament rose/cuivré | — | vissés (4 vis) de part et d'autre de l'arceau de tête | t0011, t0002 | H |
| Bandeau LED (LED CMS visibles, fil rouge) | — | sur support métallique noir | t0089 | M |
| Servo/actionneur, sigle partiel | `X5` (**partiel**) | sous le panneau haut du torse, collier jaune | t0176 | B |
| Câblage 3 fils type servo (rouge/jaune/noir) | — | nombreux, le long de l'arceau de tête | t0014-t0020 | M |

---

## 3. Anomalies et points de vigilance

Rien ici n'est un verdict : ce sont des **constats visuels** à confirmer sur pièce. Ils sont
classés par ce qu'ils coûteraient s'ils étaient réels.

| # | Constat | Repère | Pourquoi ça compte |
|---|---|---|---|
| 1 | ~~Étiquette `CHARGES LEAD ACID`~~ → **✅ RÉSOLU le 03/09** : Victron Blue Smart 24V/5A, `LEAD ACID **OR LI-ION**`, basculé en mode `li-ion` | t0131 | Reste une question de **justesse** de tension de charge, plus de danger — §1.6 |
| 2 | **Conducteur cuivre nu, sans gaine**, apparent | t0040 | Court-circuit possible dans une caisse qui vibre et qui contient de la puissance |
| 3 | **Ligne sombre nette traversant une équerre métallique** de fixation | t0166 | *J'ai relu l'image :* **on ne peut pas trancher entre fissure et rayure.** Si c'est une fissure, c'est une fixation structurelle sur 50 kg mobiles |
| 4 | **Réparations improvisées** : ruban adhésif sur mousse déchirée, ruban alu enroulé à la main, épissure sous gaine thermo | t0043, t0044, t0124, t0177 | Montages provisoires devenus permanents — à recenser et reprendre |
| 5 | ~~Routeur 4G suspendu par ses câbles, sans fixation~~ → **❌ DÉMENTI le 13/09** : il est **sur un support**, le cadrage le masquait (§1.5). Reste un vrai sujet, mais moindre : **le support existant est perfectible** (avis de David), un support imprimé le remplacera | t0108 | C'est le lien de la télé-présence et du télédiagnostic — et c'est le 2ᵉ « absent de l'image » pris à tort pour un « absent du robot » |
| 6 | **TC Helicon** ~~posé en vrac, non fixé~~ → sanglé au fond du coffre, sous les câbles (05/11) | t0113-t0122 | Idem : organe de la voix, en vrac dans une caisse qui roule |
| 7 | **Gaine tressée effilochée** à la base d'une pièce mécanique | t0019 | À regarder de près (usure ou échauffement — indécidable à l'image) |
| 8 | **Tige filetée longue pendant librement** sous le châssis | t0168 | Fonction non identifiée ; si c'est un tirant, il ne tire rien |
| 9 | **Pince crocodile de mesure laissée en place** | t0156 | Un cordon de test oublié dans une caisse sous tension |
| 10 | **Faisceaux non peignés, non gainés**, mélangeant puissance et signal | partout | Cause classique de bruit induit — à rapprocher du chantier ronflement |
| 11 | **Aucun coupe-circuit ni arrêt d'urgence identifié** dans les 139 images | — | Cohérent avec ce que le projet sait déjà (`e_stop` sans source, coup-de-poing inexistant). Un interrupteur à bascule est vu sur le panneau rouge (`t0173`), fonction non déterminée |

---

## 4. Zones d'ombre — par ordre de rentabilité

**Priorité 0 — sécurité et intégrité**

0a. ~~L'appareil `CHARGES LEAD ACID`~~ — **FAIT le 03/09** (§1.6). Ce qu'il en reste, sans
    urgence : **relever la tension de charge réelle dans VictronConnect** (Bluetooth, rien
    à démonter), compter les cellules en série, lire la chimie, vérifier le BMS — et
    **corriger `overview.md`**, dont le « 18650, 8×5 » est incompatible avec un chargeur
    24 V si c'est du 8S NMC.
0b. **L'équerre de `t0166`** : passer un doigt / une loupe. Fissure ou rayure ?
0c. **Le conducteur nu de `t0040`** : gainer.

**Priorité 1 — débloque un chantier en cours**

1. **Pourquoi le disque d'odométrie est-il déposé (`t0169`) ?** Une phrase de David réoriente
   le chantier. Et si c'est pour la mesure de distance de commutation, c'est l'action n° 1
   du chantier — autant la faire pendant que la pièce est en main.
2. **Nombre de dents des pignons** (moteur et roue) et **présence/rôle de la courroie
   `t0081`** : sans le rapport de réduction, l'odométrie produira des distances fausses.
   Deux comptages, cinq minutes.
3. **Modèle exact du TC Helicon** + **photo des positions de molettes avant d'y toucher** :
   préalable gratuit au banc V0 du chantier voix.
4. **Y a-t-il un ReSpeaker sur la tête ?** Il n'apparaît nulle part. La tête est peu filmée,
   donc ce n'est probablement qu'un angle mort — mais c'est l'organe du chantier n° 0.
   **Un plan fixe de 5 s sur la tête suffit.**

**Priorité 2 — complète le relevé**

5. **Références des deux boîtiers perforés** (`t0123`, `t0138`) : Mean Well ou pas ?
6. **Où sont les Raspberry Pi ?** Jamais vus. Probablement dans un boîtier fermé — mais
   c'est le cœur du robot et il n'a pas d'adresse dans ce relevé.
7. ~~**Combien de webcams, et où ?**~~ **RÉGLÉ le 2026-09-14 par David** : la caméra de
   perception est **FIXE SUR LE BUSTE**, sur un support **devant la bouche**. Elle ne tourne
   PAS avec le cou. C'est bien l'image qui avait raison contre la doc — `overview.md` disait
   « head-mounted » depuis le début, et deux commentaires de code en tiraient une
   justification fausse (corrigés le même jour : `gaze_follower_node.py`, `gaze_control.py`).
   Reste ouvert : **une seule caméra ou deux ?** Les images montrent aussi une webcam clipsée
   sur le bord supérieur du panneau bois (`t0002`, `t0004`) — même objet vu deux fois, ou
   second boîtier ?
8. **Calibres des fusibles** (`t0046`, `t0084`, `t0085`) et fonction de l'interrupteur du
   panneau rouge (`t0173`).

### Limite : ce qui ne se lèvera jamais par cette vidéo

Le tournage est **muet et en gros plans flous** pendant un démontage. Beaucoup de
sérigraphies sont physiquement illisibles à cette résolution, et la tête n'est quasiment pas
couverte. **Pour compléter, refilmer autrement** : plans fixes de 3 s, un organe par plan,
lumière rasante, en s'arrêtant sur chaque étiquette — comme déjà écrit pour le stock. Un
panoramique de 30 s ne vaut rien ; c'est la netteté qui décide.

---

## 5. Méthode et médias

**Source** : `VID_20260903_191115.mp4` (3 min 05 s, 1080p60, **muette** — vérifiée, David ne
commente pas), importée du Xiaomi 13T par MTP le 2026-09-03.

**Dépouillement** : extraction à 1 image/s (185 images), tri par **variance du laplacien**
(script versionné `conf/scripts/frames-nettete.py`), 25 % des plus floues écartées → **139
images** lues par **14 agents en parallèle**, sur des tranches temporelles **contiguës** (une
sérigraphie floue sur une image l'est parfois moins sur sa voisine). Consigne unique :
**ne citer une référence que si elle est lue**. Les lectures engageant une décision ont été
**re-vérifiées directement** : `t0169` (disque), `t0131` (lead acid), `t0166` (équerre),
`t0061` (driver).

**Où sont les médias.** La vidéo est **hors Nextcloud** — `~/Vidéos/didier-atelier/` — pour
ne pas synchroniser 470 Mo à chaque poste. Les 139 images lues sont sous
`docs/pictures/robot-2026-09-03/` (**gitignoré**, le dépôt est public), avec le CSV des
scores de netteté. Les images brutes se régénèrent en une commande :

```bash
ffmpeg -v error -i ~/Vidéos/didier-atelier/VID_20260903_191115.mp4 \
       -vf "fps=1,scale=1600:-1" -q:v 2 frames_all/a_%04d.jpg -y
.venv/bin/python conf/scripts/frames-nettete.py frames_all/ triees/ --percentile 25
```

**Voir aussi** : `inventaire-stock.md` (le stock d'atelier), `overview.md` (l'architecture
prévue), `croisement-etudes.md` (le post-mortem qui a établi qu'il fallait trois gisements
distincts et pas un seul).
