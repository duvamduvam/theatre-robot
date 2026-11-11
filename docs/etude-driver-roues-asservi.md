# Étude — remplacer les drivers de roues par un contrôleur asservi (RoboClaw)

*Ouverte le 2026-09-26, à la demande de David. Née d'une question sur l'odométrie
(« il n'y a pas de petites cartes qui font déjà ça ? », instruite dans
[`etude-odometrie.md`](etude-odometrie.md) §6 bis) qui a produit une réponse
inattendue : rien à acheter pour LIRE les capteurs, mais un candidat sérieux pour
**remplacer les drivers de puissance**.*

**⚠️ RIEN N'EST DÉCIDÉ ICI.** Ce document instruit, il ne tranche pas : la décision
appartient à David, et elle engage le **chemin roues**, donc le protocole complet
(simulation → protocole caméra roues hors sol → revue). Tous les prix ont été LUS à la
source le 2026-09-26 ; ce qui n'a pas pu être lu est écrit « non lu ».

## 1. La question de David, et pourquoi elle est bonne

> « Ça m'intéresse de creuser le RoboClaw, car les cartes Cytron sont chères, et si je paie
> 150 pour remplacer 2 cartes à 100 € et que le tout est plus simple, c'est intéressant. »

Le raisonnement est juste, et même meilleur que l'intuition qui l'a produit — parce que
**le gain n'est pas d'abord de l'argent, c'est de la surface de câblage et de la sécurité**.

⚠️ **Correction factuelle acquise le 26/09, qui est le point de départ de tout** : il y a
**un driver PAR ROUE, donc deux**, et ce sont des **canaux simples**. La fiche
`robot-embarque.md` disait « driver moteur double » — déduction fausse tirée du marquage
`RC1 RC2`, qui désigne en réalité les deux entrées du mode radio (`RC1` = avance/recul,
`RC2` = direction) mixées pour piloter **un seul** moteur. Le code le confirme :
`robot_config.py` réserve quatre canaux PCA9685 pour les roues (`WHEEL_LEFT_DIR=0`,
`WHEEL_LEFT_PWM=1`, `WHEEL_RIGHT_PWM=2`, `WHEEL_RIGHT_DIR=3`), soit un couple PWM+DIR par
carte.

## 2. Le calcul économique — lu à la source

| | Prix unitaire | Total | Entrée encodeur | PID |
|---|---|---|---|---|
| **Cytron MDS40B / SmartDrive40** (monté, ×2) | **88,30 € TTC** / 73,58 € HT — Neven7 (CZ), 10 en stock | **176,60 €** | non | non |
| **RoboClaw 2x30A USB V6B** (1 carte, 2 canaux) | **152,50 € TTC** / 128,15 € HT — Botland (PL), en stock 24 h | **152,50 €** | 2 | oui, 300 Hz |
| *pour mémoire* Cytron MDDS30 (**2 en stock**, double canal) | 77,50 € TTC — Botland | *déjà payé* | non | non |

**Remplacer les deux Cytron à l'identique coûte donc PLUS CHER que passer au RoboClaw.**

Et un fait qui ferme la porte du côté Cytron : **aucun driver Cytron pour moteurs à balais
n'a d'entrée encodeur ni d'asservissement** — ni MDS40B, ni MDDS30, ni MDDS60. Ce n'est pas
un choix de gamme à faire chez eux, il faut changer de marque pour asservir. (Absence
constatée sur trois fiches et un manuel, pas une déclaration de Cytron : nuance conservée.)

> 💡 **À découpler de la décision** : les **2 MDDS30 en stock sont des doubles canaux**.
> Un seul remplacerait déjà les deux MDS40B, **sans rien acheter**, et diviserait par deux
> le nombre de cartes de puissance. Sans PID ni encodeur, mais c'est gratuit. Cela dit,
> c'est aussi le chemin roues : même protocole. Et ça consommerait le rechange.

## 3. Ce que le RoboClaw SIMPLIFIE — le vrai argument, plus large que le prix

Chemin de commande aujourd'hui (cf. [`etude-chemin-commande-roues.md`](etude-chemin-commande-roues.md)) :

```
  Pi 4 ──I²C── ISO1540 ──I²C── PCA9685 (0x40) ──PWM+DIR×2── 2× Cytron MDS40B ── moteurs
                                     │
                          + carte odométrie (RP2040 + 4 optos) ──USB── Pi
```

Avec un RoboClaw :

```
  Pi 4 ──USB── RoboClaw 2x30A ──── moteurs
                    │
                    └── 4 optos (la barrière du §5 de l'étude odométrie, INCHANGÉE)
```

Disparaissent du chemin roues : **le PCA9685, l'ISO1540, l'I²C tout entier, et le RP2040**.
Et avec eux, trois défauts documentés du chemin actuel :

1. **Le conflit de fréquence roues/servos** (§2.1 de l'étude chemin) : les deux partagent
   aujourd'hui la même puce, donc la même fréquence. Le RoboClaw le règle gratuitement, et
   mieux que la séparation 0x40/0x41 prévue — il n'y a plus de PWM du tout côté Pi.
2. **Le détournement de DIR en canal PWM** (§2.2) : disparaît.
3. **L'I²C dans le chemin roues** — ce même I²C que l'étude odométrie §6 déclare interdit
   pour les capteurs. Il resterait pour les servos, où il est acceptable.

S'ajoutent, en gain net : **le PID tourne à 300 Hz dans le contrôleur** (3,3 ms), et le
RoboClaw renvoie **courant par moteur, tension batterie, deux températures, PWM, erreurs de
vitesse et bits de statut détaillés** (commande agrégée 73 « Read All Status »). C'est de la
matière directe pour le chantier télédiagnostic, aujourd'hui aveugle sur la puissance.

## 4. LA SÉCURITÉ — ce qu'on gagne, ce qu'il faut recâbler, et quatre pièges

### 4.1 Ce qu'on gagne, et c'est considérable

**Un timeout de communication DANS LE MATÉRIEL.** Commande 14 : 0 à 25,5 s par pas de
100 ms, 0 = désactivé. Passé ce délai sans octet reçu, « both motors will stop ».

Il faut mesurer ce que ça change. Aujourd'hui, le deadman 400 ms vit **dans le processus
`wheels_node`** : si ce processus meurt, le deadman meurt avec lui, et
`etude-chemin-commande-roues.md` §3 bis l'écrit noir sur blanc — *« sur le Didier
d'aujourd'hui, si `wheels_node` meurt, rien n'arrête les roues »*. Un timeout dans le
contrôleur de puissance survit à la mort du nœud, au gel du Pi, au câble USB arraché.
**C'est structurellement supérieur à tout deadman logiciel.**

**Une entrée E-Stop matérielle.** Les broches `S3`/`S4`/`S5` se configurent en `E-Stop`
(actif bas, pull-up interne pour ne pas se déclencher si le fil casse… mais voir le piège
inverse plus bas) ou en **`E-Stop (Latching)`** — arrêt maintenu jusqu'au reset du
contrôleur. Comportement : *« Motors are stopped by braking »* — **freinage actif**.

⚠️ **Correction d'une analyse hâtive faite le 26/09 en cours de recherche** : j'avais écrit
que la chaîne de sécurité conçue (watchdog 74HC123 → bascule 74HC74 → `OE` du PCA9685)
devenait *caduque* faute de `OE` à couper. **C'est faux.** Elle change de **point
d'accrochage** : la sortie de la bascule va sur l'entrée `E-Stop (Latching)` au lieu du `OE`.
La logique est identique — une sortie logique qui, en tombant, arrête les roues *sous* le
logiciel — et le résultat est **meilleur** : le `OE` du PCA9685 ne fait que couper le PWM
(roue libre, un robot de 50 kg continue sur son élan), là où l'E-Stop du RoboClaw **freine**.
Le coup-de-poing 40 A catégorie 0 sur l'entrée de puissance, lui, est inchangé.

### 4.2 Quatre pièges, tous issus de la documentation officielle

0. 🔴🔴 **En architecture C (mode RC), `Idle Mode = Braking` n'est plus une bonne pratique
   mais une CONDITION DE SÉCURITÉ** — puisqu'il n'y a pas d'entrée E-Stop dans ce mode et que
   tout l'arrêt repose sur `RC Timeout` (§6 ter ③). Laissé en `Freewheel`, un robot de 50 kg
   coupé en pleine course continue sur son élan.
1. 🔴 **« Stop » veut dire ROUE LIBRE par défaut.** Le mode d'arrêt dépend du réglage
   *Idle Mode* (commande 160), dont le **défaut usine est `Freewheel`** : « Motors coast ».
   Sur 50 kg et sur une scène en pente, la roue libre **n'est pas un arrêt**. Il faut régler
   `Braking` explicitement — et le sauvegarder (voir piège 3). La valeur d'usine du timeout
   lui-même n'est **pas documentée** : elle doit être écrite explicitement, jamais supposée.
2. 🔴 **`Home (Auto)` fait BOUGER le moteur à la mise sous tension.** Si `S4`/`S5` est
   configuré ainsi : *« On startup, the motor will move until the switch is triggered or the
   timeout period elapses »* — et si le switch est déjà actif, il avance 3 secondes pour le
   dégager. **Interdiction absolue de configurer ce mode sur Didier.** À vérifier sur un
   contrôleur d'occasion ou reconfiguré.
3. ⚠️ **Les réglages ne sont PAS sauvegardés automatiquement.** Il faut émettre la commande
   94 « Write Settings to NVM ». Un PID ou un Idle Mode réglé puis non sauvegardé est perdu
   à la coupure — et le robot redémarre en roue libre avec les constantes d'usine
   (QPPS 44000, P=1,0). À intégrer comme étape de la procédure de mise en service, avec
   relecture de contrôle (commande 95).
4. 🔴 **Pousser Didier à la main peut créer un état non sûr.** Le manuel, littéralement :
   *« Brushed DC motors act as generators when in motion. If a robot is pushed or allowed to
   coast, the motors can generate sufficient voltage to intermittently power RoboClaw's logic
   circuits, creating an unsafe operating state. »* Or **Didier se pousse à la main** — en
   coulisses, à l'atelier, et il est en pièces en ce moment. Le manuel demande de
   *« toujours fournir un chemin de retour vers la batterie »*, et évoque une diode de forte
   intensité quand les moteurs sont entraînés mécaniquement contrôleur hors tension.
   **C'est un point de câblage à instruire avant tout essai, pas une note de bas de page.**

### 4.3 La régénération, à dimensionner

Le RoboClaw est régénératif : il renvoie dans la batterie au freinage. Le manuel prévient
que l'énergie régénérée *« peut endommager le contrôleur si elle n'est pas gérée »*, et
décrit le remède : batterie en parallèle comme chemin de retour, ou clampage sur une
**résistance de puissance** (R3, typiquement 10 Ω / 50 W), avec une procédure d'essai par
paliers de 5 % et, si insuffisant, 5 000 à 10 000 µF de capacité de découplage sur B+/B−.

💡 **Il existe un produit dédié** (relevé sur la page Pololu le 26/09) : le **Basicmicro
`VClamp`**, *« a voltage clamp specifically designed to work with the RoboClaw and MCP to
suppress such voltage spikes »*, donné pour des alimentations jusqu'à 60 V et 60 A — donc
dimensionné pour notre cas. **Prix non lu.** À chiffrer avec la carte, pas après : c'est un
accessoire de sécurité, pas une option.
Didier redescend des scènes en pente : ce dimensionnement n'est pas optionnel.

Autres protections, pour mémoire : limite de courant réglable par canal (commandes
133/134), dérating thermique à partir de 85 °C jusqu'à 0 A à 100 °C (puis défaut → roue
libre), seuils de tension réglables (57/58). ⚠️ **Aucune protection contre l'inversion de
polarité** — *« Never reverse battery polarity. Doing so will permanently damage the motor
controller »* (les Cytron non plus, pour être juste).

## 5. LE POINT DUR — notre encodeur est ~500 fois moins résolu que ce qu'il attend

C'est le vrai risque technique de cette étude, et il ne se voit pas dans une fiche produit.

Géométrie retenue par l'étude odométrie : **10 cibles, décodage ×4 = 40 impulsions par tour
de roue**, soit **19,6 mm par front**, donc **~51 impulsions par mètre**. En vitesse :

| Vitesse | Impulsions/s vues par le PID |
|---|---|
| 1 m/s (rapide, hors scène) | ~51 |
| 0,5 m/s | ~26 |
| **0,2 m/s (le régime de jeu)** | **~10** |

Or **la boucle PID du RoboClaw tourne à 300 Hz** (une mise à jour toutes les 3,3 ms), et la
constante `QPPS` d'usine est **44 000**. Notre QPPS réel serait de l'ordre de **~80**.
Trois ordres de grandeur d'écart : ce contrôleur est conçu pour des encodeurs optiques de
plusieurs centaines à milliers de points par tour.

**Conséquence concrète** : à la vitesse de jeu, le PID passe des dizaines de cycles sans
aucune information nouvelle. Il ne peut pas asservir finement là où Didier vit. Aucun seuil
minimal de résolution n'est documenté par Basicmicro (cherché, non trouvé) ; le seul indice
est un fil du forum officiel — **non vérifiable, le domaine ne répond pas** — décrivant des
« à-coups aléatoires » sur un montage à ~48 impulsions/s, imputés au bruit et au réglage
PID, et résolus par **un condensateur 10 nF entre les voies A/B et la masse** (à noter : ce
sont exactement les 10 nF que notre carte prévoit déjà).

**Ce que ça change pour la décision, et c'est une nuance importante** : le RoboClaw garde
tout son intérêt **même sans utiliser son PID**. En boucle ouverte, il remplace les deux
Cytron, supprime le PCA9685 et l'I²C, apporte le timeout et l'E-Stop matériels, compte les
encodeurs et publie l'odométrie. L'asservissement peut alors se faire **plus haut**, dans
`ros2_control`, sur une fenêtre de mesure plus longue — là où 10 impulsions/s redeviennent
exploitables. **Il ne faut donc pas acheter ce contrôleur POUR son PID**, mais pour la
simplification et la sécurité, le PID étant un bonus à évaluer sur banc.

## 5 bis. 🔴 LE DIMENSIONNEMENT — l'objection de David, et elle est fondée

> « Ce qui me fait peur, c'est que la carte est petite, elle ne semble pas dimensionnée pour
> mon besoin. J'ai testé beaucoup de cartes, je ne veux pas tout changer pour avoir à
> remettre. » (David, 26/09)

**Cette intuition est vérifiée par les chiffres, et elle porte plus loin qu'un choix de
modèle.** Une carte de puissance légère, c'est peu de cuivre et peu de masse thermique :
elle tient son chiffre en pointe, pas en durée.

| | Dimensions | **Masse** | Courant annoncé |
|---|---|---|---|
| **Cytron MDDS30** (le rechange en stock) | 101 × 96 × 42 mm | **250 g** | 30 A continu / 80 A crête |
| Cytron MDS40B (ce qui est monté) | *non lu* (même famille) | *non lu* | 40 A continu / **80 A crête** |
| **RoboClaw 2x30A** | 53 × 74 × 23 mm | **60 g** | 30 A continu / 60 A crête |
| **RoboClaw 2x45A** | 52 × 74 × 18 mm | **62 g** | 45 A continu / *non lu* |

### ⚠️ AMENDEMENT du 26/09 (David sort le datasheet du 2x60A) : la bonne carte existe

David a téléchargé `roboclaw_datasheet_2x60A.pdf` et demandé : « on peut facilement rajouter
un radiateur ? » **Il n'y en a pas besoin — le 2x60A en a un d'usine, et il joue dans une
autre catégorie que le 2x30A.** Extrait du datasheet (lu en local) : `Weight 2X60A
10.4 (295) Oz (g)`, `Motor Current Per Channel 60 (typ) / 120 (max) A`, résistance à l'état
passant **2,75 mΩ**, et en tête des caractéristiques : « **Air Cooled** » et « **Dual Cooling
Fan Control** ». Le dissipateur sert même de repère de câblage dans la doc (« *the ground pin
is near the heatsink* »). Le pilotage de ventilateurs délivre 5 V / 230 mA, enclenche à
45 °C, coupe à 35 °C, pour **deux ventilateurs 40 × 40 mm** (référence testée par le
fabricant : DigiKey 259-1794-ND) ; sur le V7, les dissipateurs ont des **trous taraudés pour
les monter directement**.

La gamme complète, masse et prix lus à la source le 26/09 :

| Modèle | Masse | Courant/canal | Dissipateur | Prix lu |
|---|---|---|---|---|
| RoboClaw 2x30A V6B | 60 g | 30 A / 60 A | non | **152,50 € TTC** (Botland, en stock) |
| RoboClaw 2x45A | 62 g | 45 A / *non lu* | non | *« withdrawn products » chez Botland* |
| **RoboClaw 2x60A V8** (3687) | **300 g** — 100 × 86 × 30 mm | **60 A / 120 A** | **oui** | **229,95 $** (Pololu, « New! ») |
| ~~RoboClaw 2x60A V7~~ (3292) | 300 g — 100 × 86 × 30 mm | 60 A / 120 A | oui, **taraudés** | 229,95 $ mais **OBSOLÈTE** ; **retiré de l'offre chez TME** |
| *pour mémoire* Cytron MDS40B ×2 | *non lu* | 40 A / 80 A | — | 176,60 € TTC les deux |

Le V8 diffère du V7 par la suppression des boutons de configuration physiques : **tout se
configure en logiciel**. À noter au vu des quatre pièges du §4.2 — plus aucun réglage n'est
visible ni modifiable sans ordinateur, ce qui est un point de moins pour l'exploitation sur
un plateau, mais un point de plus pour la reproductibilité (tout est scriptable).

🔴 **Et voilà où le raisonnement de David se retourne** : il voulait « plus simple **et** moins
cher ». Avec le modèle correctement dimensionné, c'est **plus simple, mieux dimensionné, mais
PLUS CHER** — 229,95 $ chez Pololu (import US : + TVA 20 %, + port, + les frais de douane
documentés dans le commit `44dfd52`), ou **250,86 € TTC franco** chez **RobotShop EU** (prix relevé par David sur la page le 26/09 ; réapprovisionnement en cours). Contre 176,60 € pour remplacer les deux Cytron
à l'identique.

**L'arbitrage est donc binaire, sans option intermédiaire** (le 2x45A ne pèse que 2 g de plus
que le 2x30A, il ne résout rien) :

- **152,50 €** → une seule carte, asservie, **mais 60 g et 30/60 A : moins que l'existant** ;
- **250,86 € TTC franco** (RobotShop EU) → une seule carte, asservie, **300 g et 60/120 A :
  plus que l'existant**, moins encombrante que les deux Cytron réunies, pour **~74 € de plus**
  que le remplacement à l'identique.

⚠️ Une variante existe aussi en **`RoboClaw Solo 60A`** (canal unique, POLOLU-3291, prix non
lu) : deux exemplaires reproduiraient l'architecture actuelle « une carte par roue » avec
l'asservissement en plus — mais on perdrait justement la simplification recherchée, et le
prix serait doublé. Mentionné pour mémoire, pas retenu.

### Amendement n° 2 du 26/09 — le prix réel, l'USB, et les ventilateurs (David)

**① Le prix.** David a trouvé la carte chez **RobotShop EU** (page `eu.robotshop.com/fr`,
« Contrôleur de moteur régénératif RoboClaw 2x60A, 6-34VDC », BASICMICRO, UGS `RB-Bat-48`,
n° fabricant **`IMC414`**) : **250,86 € taxe incluse**, livraison gratuite dès 250 € — donc
**franco**. Stock : « **Réapprovisionnement prochain** » (pas en stock au 26/09).

Le chiffre de 322,69 € cité plus haut (Steplab, jamais confirmé par lecture directe) est donc
**à écarter**. Le surcoût réel par rapport au remplacement à l'identique des deux Cytron
(176,60 €) est de **~74 €**, pas de 150. Le raisonnement de David tient bien mieux qu'annoncé.

**② L'encombrement, gain non compté jusqu'ici.** Une carte de 100 × 86 × 30 mm remplace deux
cartes de la classe 101 × 96 × 42 mm (cote lue sur le MDDS30) : le volume occupé est divisé
par deux environ, et surtout il n'y a plus qu'**un** jeu de câbles de commande, **un** point
de fixation, **un** connecteur d'alimentation. Sur un robot où la place se négocie au
millimètre, ça compte autant que le prix.

**③ « On peut tout contrôler en USB ? » — OUI techniquement, mais le fabricant le
DÉCONSEILLE en milieu bruité.**

⚠️ **Correction du 26/09** : cette section affirmait d'abord « NON ». C'était trop tranché, et
David l'a relevé sur la page Pololu du V8, qui écrit : *« The RoboClaws have a USB interface
that acts as a virtual serial (COM) port, **allowing it to be controlled directly from a
computer** »*. C'est exact, et ce n'est pas propre au V8 : toute la famille le permet.

**Les deux sources ne se contredisent pas, elles ne parlent pas de la même chose** : Pololu
décrit une **capacité** (l'USB porte tout le jeu de commandes), Basicmicro décrit une **limite
d'usage**. Noter d'ailleurs que la même phrase Pololu oppose « *controlled directly from a
computer* » (USB) à « *controlled via **TTL serial for use with embedded systems*** » — et un
Raspberry Pi embarqué dans un robot, c'est la seconde catégorie.

La limite, elle, est écrite dans le datasheet 2x60A, section *USB*, littéralement :

> « A dual ferrit core USB cable is required. **The USB port should be used for configuration
> and debugging. The USB protocol is not designed for electrically noisy environments. The USB
> port will likely disconnect and not automatically recover during operation in electrically
> noisy environments.** »

Or Didier, c'est exactement l'environnement décrit : deux moteurs à balais de 250 W qui
arcent, un ampli de sono, des rubans LED à fronts raides — c'est le §5 de l'étude odométrie,
mot pour mot.

**Ce n'est donc pas une impossibilité, c'est un arbitrage de risque** :

| | USB | TTL série (Packet Serial) |
|---|---|---|
| Câblage | 1 câble (à double ferrite, **exigé** par le datasheet) | 3 fils sur l'UART du Pi |
| Nom du périphérique | `/dev/ttyACM*`, variable → règle udev par n° de série | port fixe, rien à résoudre |
| Risque documenté | *« will likely disconnect and **not automatically recover** »* | aucun mentionné |
| Reprise après coupure | **manuelle** (débrancher/rebrancher le câble, d'après la doc) | sans objet |
| Isolation des masses | à faire (Basicmicro vend un isolateur USB) | à faire aussi (opto sur RX/TX) |

⚠️ **Ce qui fait pencher, c'est la nature du métier** : avec le timeout matériel réglé, une
déconnexion USB **arrête les moteurs** — c'est sûr, mais sur un plateau, en représentation,
c'est un robot qui s'immobilise en plein jeu et qui ne repart pas sans intervention humaine
sur un câble. Un incident de spectacle, pas seulement un incident technique.

**Recommandation de l'étude : le pilotage passe par le `TTL serial` en mode Packet Serial**
(trame à CRC16), l'USB restant pour ce qu'il fait le mieux — Motion Studio à l'atelier,
configuration, mises à jour de firmware, diagnostic. Rien n'interdit de **commencer les
essais en USB** (c'est plus rapide à câbler) et de basculer en TTL avant le premier usage
scénique : les deux modes coexistent, et le protocole applicatif est identique.

Ce n'est pas une mauvaise nouvelle : le TTL série est **3 fils sur le connecteur du Pi**, sans
énumération USB, sans `/dev/ttyACM*` qui change de nom, sans hub. C'est plus simple que l'USB,
pas moins — c'est d'ailleurs le sens du renversement inverse qu'avait fait l'étude odométrie
pour le RP2040 (où c'était le connecteur micro-USB **mécanique** qui posait problème, pas le
protocole). ⚠️ Conséquence à ne pas rater : le lien redevient un **signal logique nu entre
deux masses différentes**, au milieu des moteurs — donc la question de l'isolation se repose,
exactement comme au §5 de l'étude odométrie. Le manuel mentionne un **isolateur USB** vendu
par Basicmicro pour casser les boucles de masse ; pour le TTL, ce serait un isolateur
numérique ou un optocoupleur sur RX/TX.

**④ Deux avertissements de câblage, à graver :**

- **Batterie logique SÉPARÉE.** Datasheet : *« A second power source should be used to power
  the logic section in situations where the main power will be under heavy load. Voltage drops
  can occur from constant full load or high speed direction changes. Voltage drop can cause
  logic brown outs if only a main battery is used without a logic battery. »* Un robot de
  50 kg qui change de sens brutalement, c'est le cas décrit. La carte a une entrée
  `Logic Battery` (6-34 V) prévue pour ça — **elle doit être utilisée**, sinon un
  effondrement de tension redémarre la logique en pleine manœuvre.
- ⚠️ *« Do not disconnect the negative terminal if other ground sources are connected, such as
  USB cable. Damage will occur. »* — l'ordre de branchement/débranchement n'est pas libre.

**⑤ Les ventilateurs : où les mettre ?** Question de David, et la réponse honnête est que
**le datasheet ne spécifie AUCUN point de montage**. Il dit seulement : *« any 40mmx40mm fan
can be used »*, avec une référence testée (DigiKey `259-1794-ND`), 5 V / 230 mA max, deux
ventilateurs pilotés automatiquement (ON à 45 °C, OFF à 35 °C).

C'est la page Pololu du **V7** qui précise que « *les dissipateurs incluent désormais des
trous taraudés permettant de monter directement une paire de ventilateurs* » — le mot
« désormais » indiquant que c'est une **nouveauté du V7**. La carte photographiée chez
RobotShop montre des **boutons de configuration** (`MODE`/`SET`/`LIPO`) en bas de carte, or le
V8 les a supprimés : **la carte vendue là est donc antérieure au V8, et probablement au V7** —
donc sans trous taraudés. À vérifier sur la carte reçue, ou en demandant la révision exacte au
vendeur avant d'acheter.

Deux remarques qui désamorcent largement le sujet :

1. **Les ventilateurs ne sont sans doute pas nécessaires.** Le datasheet les présente comme un
   moyen « d'aider à maintenir des courants continus **dans des conditions extrêmes** ». Une
   carte donnée pour 60 A continu par canal, alimentant des moteurs de **moins de 13,4 A au
   nominal**, travaille à ~20 % de sa capacité. C'est précisément pour ça qu'on prend la carte
   massive : pour ne pas avoir besoin de la ventiler. La mesure à la pince (§5 bis) le
   confirmera ou l'infirmera.
2. **Et s'il en faut, c'est un support imprimé.** Deux ventilateurs 40 × 40 en soufflage au
   travers des ailettes, tenus par un berceau en PETG vissé sur les trous de fixation de la
   carte — c'est exactement le type de pièce que le projet sait faire (CR-10, cf.
   `plans/`). Aucun perçage du dissipateur n'est nécessaire.

### Ce qui reste vrai du constat initial

Deux faits à retenir :

1. **À courant annoncé comparable, le RoboClaw a quatre fois moins de masse et quatre fois
   moins de volume que le Cytron.** Et Pololu écrit que ses courants maximaux *« ne peuvent
   être atteints et maintenus qu'avec une dissipation thermique adéquate »* — ce que confirme
   le datasheet, qui prévoit une **sortie de commande de ventilateur** (enclenchement à
   45 °C, arrêt à 35 °C) et un **dérating dès 85 °C jusqu'à 0 A à 100 °C**. Une carte qui a
   besoin d'un ventilateur pour tenir son chiffre annonce un chiffre de laboratoire.
2. **Monter en gamme ne règle rien** : le 2x45A pèse **62 g**, deux grammes de plus que le
   2x30A. Ce n'est pas un défaut de référence, c'est la conception de toute la famille
   RoboClaw — des cartes compactes refroidies par l'air ambiant. (Et les 2x45A sont classés
   « withdrawn products » chez Botland : la disponibilité UE se dégrade quand on monte.)

**Donc le RoboClaw 2x30A — et lui seul — serait un recul de puissance par rapport à
l'existant** (le 2x60A, lui, est au-dessus, cf. l'amendement ci-dessus) :
30 A continu / 60 A crête contre 40 A / 80 A aujourd'hui. Ce n'est pas rédhibitoire — les
MY1016Z tirent **moins de 13,4 A au nominal** (fiche constructeur, à vide < 2,2 A), donc
30 A continu reste plus du double du nominal. Le risque n'est pas le régime établi, c'est le
**transitoire** : démarrage de 50 kg, montée de pente, et surtout **roue calée contre un
décor** — un incident normal au théâtre, pas un cas limite. Le courant de blocage du
MY1016Z n'est documenté nulle part (cherché, non trouvé) ; pour un moteur à balais de cette
classe il est de l'ordre de plusieurs dizaines d'ampères, donc **au-delà des 60 A de crête
du 2x30A**. La limitation de courant réglable (commandes 133/134) protège la carte, mais au
prix du couple : elle transforme un blocage en perte de motricité.

### La mesure qui tranche, et elle est gratuite

Le courant réellement tiré par les moteurs de Didier n'a **jamais été mesuré**. Tant qu'il
ne l'est pas, tout dimensionnement est une conjecture — dans les deux sens.

> **Poser une pince ampèremétrique sur un fil moteur pendant le test scénique au sol**
> (chantier priorité n° 1, déjà prévu, avec les Cytron en place). Relever : courant au
> démarrage, en régime, en montée, et **roue volontairement bloquée à la main, roues hors
> sol**. Coût : zéro euro, zéro démontage, et c'est la donnée qui manque à toutes les
> décisions de puissance de ce robot — pas seulement à celle-ci.

### Et la peur du retour en arrière : l'essai est réversible

L'autre moitié de l'objection — *« je ne veux pas tout changer pour avoir à remettre »* — a
une réponse concrète : **cet essai ne demande de rien démonter.**

Les deux Cytron restent **vissés en place et câblés**, simplement débranchés : côté commande
on débranche 4 fils (PWM + DIR de chaque carte, qui viennent du PCA9685), côté puissance on
déplace les deux paires de fils moteur et l'alimentation vers les borniers du RoboClaw. Le
retour en arrière est l'opération inverse, **une quinzaine de minutes, sans fer à souder**,
et la chaîne logicielle actuelle (`wheels_node` + PCA9685) n'est pas modifiée — elle est
seulement inutilisée le temps de l'essai.

⚠️ Deux réserves sur cette réversibilité : (a) le nœud ROS du RoboClaw est un développement
à part entière, ce n'est pas un essai d'une soirée ; (b) le **chemin de retour batterie** et
la **diode anti-génération** du §4.2 (piège 4) doivent être câblés **avant** le premier
essai, pas après — c'est le seul câblage qui ne se défait pas en quinze minutes.

### Amendement n° 4 — la gamme complète, et l'arbitrage import US / achat UE

David a ouvert la page Pololu du **V8** (item 3687) le 26/09 : **229,95 $** l'unité
(216,15 $ dès 5), **11 en stock**, backorders acceptés. Les photos du V8 montrent bien les
**deux dissipateurs à ailettes** — l'inconnue n° 9 tombe donc pour cette version : le V8 est
équipé, et il a perdu les boutons de configuration (tout en logiciel).

**Le tableau comparatif de la gamme, relevé sur cette page**, rend l'arbitrage définitif :

| Modèle | Canaux | Tension | Continu | **Crête** |
|---|---|---|---|---|
| Solo 30A / 60A / 300A | 1 | 6-34 / 6-60 / 6-60 V | 30 / 60 / 300 A | 60 / 120 / 300 A |
| 2x7A | 2 | 6-34 V | 7,5 A | 15 A |
| 2x15A | 2 | 6-34 V | 15 A | 30 A |
| **2x30A** | 2 | 6-34 V | 30 A | 60 A |
| **2x45A** | 2 | 6-34 V | 45 A | **60 A seulement** |
| **2x60A** | 2 | 6-34 V | **60 A** | **120 A** |
| 2x60AHV | 2 | 10,5-60 V | 60 A | 120 A |
| 2x200A | 2 | 10,5-60 V | 200 A | 200 A |

Et les prix, tailles et masses de la même page :

| Modèle | Taille | Masse | Prix Pololu |
|---|---|---|---|
| Solo 30A / **Solo 60A** | 60×32,5×23,5 / **99×72,6×30 mm** | 130 g / **340 g** | 89,95 $ / **119,95 $** |
| 2x7A | 48×42×17 mm | 20 g | 79,95 $ |
| 2x15A / 2x30A / 2x45A | **74×52×17 mm** (identiques) | **60 g** (identiques) | 99,95 / **134,95** / 179,95 $ |
| **2x60A** | **100×86×30 mm** | **300 g** | **229,95 $** |
| 2x60AHV (10,5-60 V) | 100×86×30 mm | 300 g | 299,95 $ |
| 2x200A | 155×126×50 mm | 1200 g | 599,95 $ |

Ce tableau dit tout en une ligne : **les 2x15A, 2x30A et 2x45A sont la MÊME carte** (mêmes
dimensions, même masse), seul le silicium change. Le premier double canal à changer de
catégorie mécanique sous 34 V est le **2x60A**, et il n'y a rien entre les deux.

> À noter, sans le retenir : **deux `Solo 60A`** (119,95 $ pièce, 340 g chacun, 60 A/120 A)
> coûteraient **239,90 $**, à peine plus que le 2x60A, et reproduiraient l'architecture
> actuelle « une carte par roue » avec l'asservissement en plus. Mais on garderait deux
> cartes, deux fixations, deux jeux de câbles, 680 g — c'est-à-dire qu'on paierait le même
> prix pour perdre la simplification recherchée.

⚠️ **Le 2x45A a la MÊME crête que le 2x30A (60 A)** — il n'apporte que du continu, pour
2 g de dissipateur en plus (c'est-à-dire aucun). Il est définitivement hors course : sur ce
robot, c'est la **crête** qui compte (démarrage de 50 kg, roue calée contre un décor). Le
choix se réduit donc bien à **2x30A (60 A crête) ou 2x60A (120 A crête)**.

Noté au passage : le **BEC 5 V du 2x60A est tombé à 1,2 A sur les versions « V7 or later »**
(contre 3 A avant). Sans importance si on n'alimente rien depuis la carte, à savoir si on
comptait y brancher des capteurs.

### Les révisions V6 → V7 → V8, et ce qu'il faut exiger à l'achat

*Question de David, 26/09. Tout est lu sur les pages Pololu des items 3292 (V7) et 3687 (V8).*

| | V6 et antérieurs | **V7** | **V8** |
|---|---|---|---|
| MOSFET | d'origine | 🟢 **améliorés** (« *improved MOSFETs for better performance* ») | identiques au V7 |
| Dissipateurs **taraudés** pour monter 2 ventilateurs | ❌ non | 🟢 **oui** (« *the heat sinks **now** include tapped holes* ») | oui |
| BEC 5 V | 3 A | **1,2 A** (« *V7 or later* ») | 1,2 A |
| Boutons de configuration physiques | oui | **oui** | ❌ **supprimés** |
| Configuration | boutons **ou** logiciel | boutons **ou** logiciel | **logiciel uniquement** |
| Format, emplacements des connecteurs | — | inchangés (« *drop-in replacement* ») | inchangés |
| Dimensions / masse / prix | — | 100 × 86 × 30 mm · 300 g · 229,95 $ | **identiques** |
| Statut au 26/09/2026 | — | 🔴 **obsolète**, retiré de l'offre chez TME | **au catalogue, 11 en stock chez Pololu** |

**Deux changements comptent vraiment pour Didier, et ils sont tous les deux au V7 :**

1. 🔴 **Les MOSFET améliorés.** On choisit précisément cette carte pour sa marge thermique
   (§5 bis) : prendre une révision antérieure au V7, ce serait acheter la masse du dissipateur
   sans l'amélioration du silicium qui va avec.
2. 🔴 **Les trous taraudés des dissipateurs.** C'est la réponse à la question « où mettre les
   ventilateurs ? » (§6 quater) : elle n'existe **qu'à partir du V7**. Sur une révision plus
   ancienne, il faudrait fabriquer un berceau ; à partir du V7, les ventilateurs se vissent
   directement.

⚠️ **Le BEC est descendu de 3 A à 1,2 A au V7.** Sans effet ici (le domaine propre de la carte
optos ne consomme que quelques milliampères), mais à savoir si un jour on voulait alimenter
autre chose depuis le contrôleur.

### Et un arbitrage contre-intuitif : le V7 serait PRÉFÉRABLE au V8 pour ce robot

Le seul changement du V8 est la **suppression des boutons de configuration**. Or sur un robot
de théâtre, ces boutons sont un **avantage d'exploitation** : ils permettent de vérifier ou de
corriger un mode **sans ordinateur**, dans une loge, avant l'entrée en scène. Vu les quatre
pièges de configuration du §4.2 — `Idle Mode` en roue libre par défaut, `Home (Auto)` qui fait
bouger le moteur au démarrage — pouvoir contrôler un réglage sans sortir un portable et un
câble n'est pas un luxe.

Le V8 a en échange un vrai mérite : **tout est scriptable**, donc reproductible et
versionnable — ce qui va dans le sens du projet (une configuration en fichier, rejouable après
un remplacement de carte).

**Conséquence pratique** : si RobotShop EU livre un **V7** sous sa référence `IMC414`, c'est
une bonne nouvelle, pas une déception — à condition que ce soit bien un V7 et pas un V6.
**La question à leur poser devient donc précise** : *« la carte livrée est-elle une V7 ou une
révision antérieure ? »* Une V6 serait à refuser (MOSFET d'origine, dissipateurs non taraudés) ;
une V7 est le meilleur compromis pour cet usage ; une V8 convient aussi.

#### Où l'acheter : deux offres, deux compromis

| | Prix affiché | Stock | Révision | À ajouter |
|---|---|---|---|---|
| **Pololu** (US) | **229,95 $** | **11 en stock** | **V8** (dissipateurs ✅, config 100 % logicielle) | port international, **TVA 20 %**, frais de douane — cf. le chiffrage du commit `44dfd52` |
| **RobotShop EU** | **250,86 € TTC franco** | « réapprovisionnement prochain » | ⚠️ **inconnue** — la photo de la fiche montre les boutons `MODE`/`SET`/`LIPO`, **que le V8 n'a plus** : ce serait donc une révision antérieure | rien |

**L'écart est plus faible qu'il n'y paraît** : 229,95 $ sont hors taxes et hors port ; une fois
le transport international, la TVA à 20 % et les frais de dossier ajoutés (la règle douanière
du 01/07/2026 documentée dans `44dfd52`), l'import US arrive vraisemblablement **au-dessus**
des 250,86 € TTC franco de RobotShop. Le prix n'est donc pas le bon critère de choix entre
les deux — **la révision l'est**.

⚠️ **Question à poser à RobotShop avant d'acheter** (elle n'a pas pu être vérifiée : leur site
refuse la consultation automatisée) : *quelle révision est livrée sous l'UGS `RB-Bat-48` /
n° fabricant `IMC414` ?* Si c'est une V5/V6, il faut savoir que (a) les dissipateurs n'ont
peut-être pas les trous taraudés des ventilateurs, et (b) les boutons de configuration
physiques existent — ce qui est plutôt un **avantage** en exploitation (on peut vérifier ou
corriger un mode sans ordinateur), à mettre en regard de la reproductibilité du tout-logiciel.

### Amendement n° 3 — « si on ne peut pas en USB, comment ça marche ? » (David, 26/09)

**Question exacte** : « on reste sur les mêmes cartes multiplexeur PWM ? » — **NON.**
Confusion à lever, et elle est naturelle : **le TTL série n'a rien à voir avec le PWM.**

Le PCA9685 est un **générateur de PWM** : on lui parle en I²C, il fabrique 16 signaux carrés.
Le TTL série, c'est l'**UART natif du Raspberry Pi** — deux fils de données et une masse, sur
des broches GPIO qui existent déjà. Il n'y a **rien à intercaler** entre le Pi et le RoboClaw.

```
   AUJOURD'HUI
   Pi ──I²C── ISO1540 ──I²C── PCA9685 ──PWM+DIR ×4── 2× Cytron ── moteurs

   AVEC LE RoboClaw EN TTL SÉRIE
   Pi ──── 3 fils ──── RoboClaw ── moteurs
      TXD (GPIO14) ──► S1
      RXD (GPIO15) ◄── S2
      GND ─────────── GND
```

**Câblage officiel, lu dans le manuel constructeur** (schéma « MCU ↔ RoboClaw ») :

| Côté Pi | Côté RoboClaw |
|---|---|
| `UART TX` | **`S1` Signal** (entrée du RoboClaw) |
| `UART RX` | **`S2` Signal** (sortie du RoboClaw) |
| `GROUND` | `GROUND` |
| ~~5 VDC~~ | ~~5 VDC~~ — ⚠️ *« If the MCU has its own power supply, **do not connect** the 5 V output »* |

**Trois fils, donc.** Et aucun adaptateur de niveau : le datasheet est explicite — *« All pins
are 5V tolerant and **output 3.3V for compatibility with processor such as Raspberry Pi** and
Arduino »*. Le fabricant nomme le Raspberry Pi. (La mention d'un MAX232 dans la doc ne
concerne qu'un PC muni d'un vrai port RS-232 à ±12 V, pas nous.)

Le mode à utiliser est **`Packet Serial`** : c'est le seul qui accepte les encodeurs **et**
qui autorise la lecture d'état. Chaque carte y porte une **adresse** (8 possibles), donc le
jour où il en faudrait une seconde, le même lien série les dessert toutes.

**Et le PCA9685 dans tout ça ?** Il reste — mais **pour les servos seulement** (visage, bras,
cou). C'est exactement ce que cherchait à obtenir la séparation 0x40/0x41 prévue au §4 de
[`etude-chemin-commande-roues.md`](etude-chemin-commande-roues.md) : chaque puce retrouve sa
fréquence propre, et couper les roues ne fige plus le visage. Ici c'est obtenu **gratuitement,
et mieux** : il n'y a plus du tout de PWM roues à cadencer.

#### 🔴 Conséquence en cascade sur la chaîne de sécurité — à ne pas rater

Le watchdog 74HC123 de la carte main-carrier est réarmé par « un battement GPIO26 émis
**seulement après une écriture I²C réussie** ». C'est astucieux : le battement prouve que le
bus vit. **Mais si les roues ne passent plus par l'I²C, cette preuve ne prouve plus rien de
ce qui concerne les roues.**

Il faudrait donc réarmer le watchdog sur **l'acquittement d'une trame série par le RoboClaw**
(le mode Packet Serial en renvoie un), et non plus sur l'écriture I²C. La logique reste la
même — un battement émis uniquement quand la communication est prouvée vivante — mais le
déclencheur change. **À traiter au moment de router la bande sécurité**, ce qui est déjà le
rendez-vous fixé au §8. C'est une modification de conception, pas de câblage.

⚠️ Détail d'intégration à ne pas découvrir le jour J : sur un Raspberry Pi 4, l'UART primaire
doit être **libéré** (console série désactivée, `enable_uart=1`), et le mini-UART lié à
l'horloge du cœur est à éviter pour un lien à débit soutenu. À instruire au lot
d'implémentation.

## 6. L'intégration ROS 2 — trois drivers, aucun parfait

| Dépôt | Licence | Dernier commit | Type | Distro | Sécurité si le flux ROS s'arrête |
|---|---|---|---|---|---|
| `wimblerobotics/ros2_roboclaw_driver` | MIT | **2026-05-11** | nœud simple (pas `ros2_control`) | **Jazzy cité explicitement** | ✅ `max_seconds_uncommanded_travel`, défaut **0,25 s** → arrêt moteurs |
| `basicmicro/basicmicro_ros2` (l'éditeur) | MIT | 2026-02-17 | vrai plugin `ros2_control` | non précisée | ❌ **non documenté** — à lire dans le code |
| `dumbotics/roboclaw_hardware_interface` | Apache-2.0 | 2024-08-04 | vrai plugin `ros2_control` | **Humble seulement** | ✅ via `cmd_vel_timeout` (0,1 s) de `diff_drive_controller` |

- **Aucun ne publie la TF `odom` → `base_link` de lui-même** : les deux plugins la délèguent
  à `diff_drive_controller` (`enable_odom_tf: true`), ce qui est la bonne architecture — et
  c'est déjà la cible de l'étape 5 de l'étude odométrie.
- 🔴 **Aucun plugin Gazebo.** Seul `basicmicro_ros2` fournit des « mock interfaces » (tests
  sans matériel), ce qui **n'est pas** une simulation physique Gazebo Harmonic. Or la règle
  du projet est : *validation en simulation d'abord*. Cette règle deviendrait difficile à
  tenir telle quelle — à instruire avant tout achat, c'est un verrou de méthode.
- ⚠️ **Tickets fermés sur notre matériel exact** : `ros2_roboclaw_driver` a des issues
  « RoboClaw readByteWithTimeout issue on **Raspberry Pi 4B** » (20/08/2023), « Unable to
  open USB port » (09/02/2025), « Invalid ACK response » (14/12/2023). Fermées, mais ce sont
  des symptômes de fragilité du lien série sur un Pi 4.
- Le nom du périphérique USB (`/dev/ttyACM*`) est une loterie — problème déjà résolu par
  ailleurs dans le projet : **règle udev sur le numéro de série**, comme prévu pour le
  RP2040 d'odométrie.

Point d'architecture à ne pas rater : en `Packet Serial`, la trame porte un **CRC16 CCITT
(polynôme 0x1021)**, et le contrôleur impose un **timeout inter-octet de 10 ms** (tout
paquet dont un octet arrive en retard est jeté). Le projet a déjà été mordu par un CRC que
rien ne figeait (leçon `feedback-tests-graver-la-valeur`, lot T1 de la télécommande) : si du
code de trame est écrit ici, **graver des vecteurs de test**.

## 6 bis. Les MODES DE PILOTAGE — et une troisième architecture qu'on n'avait pas vue

*Section écrite le 26/09 à la demande de David : « va jusqu'au bout pour le pilotage par pin
pour bien comprendre la différence ». Tout vient du manuel utilisateur officiel, lu en local.*

### Les cinq modes, et ce qui les sépare vraiment

| Mode | Support physique | Encodeurs pour l'asservissement | **Peut-on LIRE les compteurs ?** |
|---|---|---|---|
| **RC** | impulsions servo sur `S1`/`S2` | ✅ oui | ❌ non (par ce lien) |
| **Analog** | 0-2 V sur `S1`/`S2` | ✅ oui | ❌ non |
| **Simple Serial** | TTL sur `S1` seul | ❌ **non** | ❌ non — *« receive only device »* |
| **Packet Serial** | TTL `S1`(RX)/`S2`(TX), adressé, CRC16 | ✅ oui | ✅ **oui** |
| **USB** | port COM virtuel | ✅ (selon le mode actif) | ✅ oui |

**La ligne qui compte est la dernière colonne.** RC et Analog pilotent avec un *signal* : le
dialogue est à sens unique, on commande mais on n'apprend rien. Packet Serial et USB
**dialoguent** : on envoie des consignes et on relit les compteurs d'encodeurs, le courant par
moteur, les tensions, les températures, les bits d'erreur.

Pour Didier, la conséquence est directe : **l'odométrie — le but initial de tout ce
chantier — exige un lien capable de LIRE.** Un RoboClaw piloté en RC seul asservirait bien sa
vitesse tout seul, mais resterait muet : pas de TF `odom` → `base_link`, donc pas de nav2.

⚠️ Et `Simple Serial` est un piège à éviter : c'est du TTL comme Packet Serial, mais
unidirectionnel **et sans support d'encodeur**. Il n'apporte rien ici.

### La trouvaille : le mode RC accepte les encodeurs, ET l'USB reste lisible par-dessus

Deux phrases du manuel, qui prises ensemble ouvrent une voie :

> **`RC Mode with feedback for velocity or position control`** — *« RC Mode supports encoder
> feedback with either velocity or position PID control. »*

> **`USB Control`** — *« USB can be used in any mode. [...] if RoboClaw is not in packet serial
> mode, motor movement commands will be overridden by Analog or RC pulse input. **USB packet
> serial commands can then only be used to read status information and set configuration
> settings.** »*

Autrement dit : en mode RC, on peut **asservir la vitesse par encodeur**, et brancher l'USB
**en lecture seule** — ses commandes de mouvement sont ignorées (le RC gagne), mais toutes
les commandes de lecture répondent.

Or des impulsions servo de 1120 à 1920 µs, **c'est exactement ce que le PCA9685 produit
déjà** pour les servos du visage.

```
  ARCHITECTURE C — « mode RC », la migration douce

  Pi ─I²C─ ISO1540 ─I²C─ PCA9685 ──2 impulsions servo──► RoboClaw ──► moteurs
                            ▲                              ▲
                            │                              └── encodeurs (les 4 optos, inchangés)
                    OE ◄── chaîne de sécurité                       │
                          (watchdog 74HC123 + 74HC74,               │
                           INCHANGÉE, réarmée par l'I²C)            │
                                                                    ▼
  Pi ◄──────── USB, LECTURE SEULE ──────── odométrie, courant, tension, température
```

### Pourquoi cette variante est remarquable

1. 🟢 **La chaîne de sécurité conçue reste valable telle quelle.** Le `OE` du PCA9685 a
   toujours quelque chose à couper, et le watchdog 74HC123 réarmé « après une écriture I²C
   réussie » prouve toujours ce qu'il doit prouver. **L'inconnue n° 12 disparaît dans cette
   variante** — c'est la seule des trois architectures qui ne demande pas de refondre une
   conception déjà faite.
2. 🟢 **Le risque USB devient bénin.** Si le port lâche (le défaut documenté), on perd la
   *mesure*, jamais la *commande*. Plus de robot immobilisé en plein jeu pour un câble.
3. 🟢 **`RC Timeout` : arrêt des moteurs si le signal est perdu plus de 100 ms** — quatre fois
   plus rapide que le deadman logiciel actuel (400 ms), et **dans le matériel**. Et quand la
   chaîne de sécurité coupe le `OE`, les impulsions cessent : les deux mécanismes se
   composent au lieu de se remplacer.
4. 🟢 **`Safe Start`** : le moteur refuse de démarrer tant que l'entrée n'est pas revenue au
   centre. Un redémarrage de `wheels_node` ne peut plus relancer une consigne ancienne — c'est
   exactement le piège du « réarmement » que le modèle de la chaîne de sécurité avait identifié
   (`safety_chain_model.py`).
5. 🟢 **`Fwd Limit (%)` / `Rev Limit (%)`** : bridage de la vitesse maximale **en dur dans la
   carte**, indépendant du logiciel. Pour un robot qui joue près du public, c'est une ceinture
   que rien dans ROS ne peut desserrer.
6. 🟢 **`Exponential`** : sensibilité accrue à basse vitesse. Précisément le régime de jeu.
7. 🟢 **Deux défauts documentés du chemin actuel tombent d'eux-mêmes** : le PCA9685 ne hache
   plus un moteur à 60 Hz (donc plus d'ondulation de courant ni de **ronflement audible** —
   le §2.1 de l'étude chemin devient sans objet), et **la ligne `DIR` détournée disparaît**
   (§2.2 : un canal servo par roue au lieu d'un couple PWM+DIR, donc plus de `65530 ≠ 65535`).

### Ses deux limites, à connaître avant de choisir

1. 🔴 **`MCU Mode` est OBLIGATOIRE.** Par défaut, le RoboClaw **auto-calibre sa plage
   d'impulsions au démarrage et à la volée** : *« If a pulse shorter than 1250 µs or longer
   than 1750 µs is detected, the new value is set as the updated range limit. »* Piloté par un
   microcontrôleur, c'est inacceptable — la correspondance consigne → vitesse changerait toute
   seule en cours de spectacle. Avec `MCU Mode` activé, la plage est figée : **1120 µs plein
   arrière, 1520 µs arrêt, 1920 µs plein avant**. À graver dans la procédure de mise en
   service, au même titre que `Idle Mode = Braking`.
2. ⚠️ **La résolution de consigne chute.** Le PCA9685 est un compteur 12 bits sur la période :
   à 50 Hz, un pas vaut ~4,9 µs, donc la plage utile de 800 µs ne porte que **~164 niveaux**
   (~82 par sens) au lieu des 4096 d'un PWM direct. Sur 0 à 1 m/s, cela fait environ **1 cm/s
   de granularité** — largement suffisant pour ce robot, mais c'est une perte réelle, à
   mesurer si un jour on cherche de la finesse à très basse vitesse.

### Les trois architectures, côte à côte

| | **A — Packet Serial (TTL)** | **B — USB seul** | **C — Mode RC + USB en lecture** |
|---|---|---|---|
| Câblage | 3 fils sur l'UART du Pi | 1 câble USB | PCA9685 (existant) + 1 câble USB |
| PCA9685 dans le chemin roues | ❌ sort | ❌ sort | ✅ reste (2 canaux au lieu de 4) |
| I²C dans le chemin roues | ❌ sort | ❌ sort | ✅ reste |
| Odométrie + télémétrie | ✅ | ✅ | ✅ (par l'USB) |
| Asservissement par encodeur | ✅ | ✅ | ✅ |
| **Chaîne de sécurité conçue** | 🔴 **à refondre** (accrochage sur `E-Stop`, watchdog à réarmer autrement) | 🔴 **à refondre** | 🟢 **inchangée** — mais ⚠️ **pas d'entrée E-Stop en mode RC** (réservée au mode série) : l'arrêt passe par la coupure du `OE`, donc par `RC Timeout` + `Idle Mode = Braking`. Voir §6 ter ③ |
| Arrêt sur perte de lien | timeout série réglable (défaut **non documenté** → à régler) | idem | **`RC Timeout` 100 ms** + `OE` |
| Panne du lien en spectacle | arrêt (sûr) | ⚠️ arrêt, **reprise manuelle** | 🟢 perte de la mesure seule |
| Résolution de consigne | pleine | pleine | ~164 niveaux |
| Travail logiciel | nouveau nœud + protocole CRC16 | idem | **`wheels_node` à peine modifié** (2 canaux servo) + un lecteur d'état |

**Aucune n'est évidente, et c'est pour ça que la question de David était la bonne.** L'axe A
est le plus propre architecturalement (il sort l'I²C du chemin roues, ce que le projet cherche
par ailleurs) mais il oblige à refondre une chaîne de sécurité déjà conçue et testée en
modèle. L'axe C est le plus prudent : il n'entame rien de l'existant, apporte quatre sécurités
matérielles supplémentaires, et laisse la porte ouverte — **on peut passer de C à A plus tard
sans racheter quoi que ce soit**, puisque c'est la même carte et le même câble d'encodeurs.

⚠️ À vérifier avant de trancher, et ce n'est pas dans le manuel : en mode RC, le RoboClaw
**publie-t-il vraiment ses compteurs d'encodeurs par USB** ? La phrase citée dit « read status
information », ce qui devrait les inclure (commandes 16/17 « Read Encoder Count »), mais elle
ne les nomme pas explicitement. **C'est le seul point qui peut faire tomber l'architecture C —
à tester en dix minutes sur banc, avant tout le reste.**


## 6 ter. PLAN DE CÂBLAGE — où va quoi, physiquement

*Écrit le 26/09 sur quatre questions de David, en lisant le manuel et la vue de dessus du V8.*

Le bandeau de connecteurs du V8, de gauche à droite (visible sur la photo produit Pololu) :

```
  ┌──────────── borniers à vis (puissance) ────────────┐
  │  M1B  M1A   +   -   M2B  M2A                       │   ← batterie principale + 2 moteurs
  └────────────────────────────────────────────────────┘
  ┌──────── barrettes 2,54 mm (signal) ────────────────┐
  │  LB IN │ - + │ EN1 │ EN2 │ S1 S2 S3 S4 S5 │ + -    │
  └────────────────────────────────────────────────────┘
        │              │                │
        │              │                └── commande, E-Stop, fins de course
        │              └── ENCODEURS (A, B, +5 V, GND)
        └── batterie logique de secours
```

### ① « Où est l'odométrie ? Sur les S1-S4 ? » — **Non : sur `EN1` et `EN2`**

Ce sont des **entrées dédiées**, séparées des entrées de commande. Manuel : *« EN1 and EN2 are
the inputs from the encoders on pin header versions of RoboClaw. »* Chaque bloc porte quatre
broches : **`A`, `B`, `+` et `−`**, avec deux repères physiques à connaître —
*« The positive (+) is located **at the board edge** and supplies +5VDC. The ground (−) pin is
**near the heatsink** »*, et *« `A` of both EN1 and EN2 are located at the board edge ;
channel `B` pins are located near the heatsink. »*

Donc : **roue gauche → `EN1`, roue droite → `EN2`**, deux fils de signal par roue, exactement
ce que produit la carte à optocoupleurs. Les `S1`-`S5` ne servent **jamais** à l'odométrie.

⚠️ **Piège de sens, déjà connu du projet sous une autre forme** : *« make sure the leading
channel for the direction of rotation is connected to A. If one encoder is backwards to the
other you will have one internal counter counting up and the other counting down. »* Les deux
roues d'un différentiel étant montées en miroir, **l'une des deux sera nécessairement à
l'envers**. Ça se corrige soit en croisant A et B au câblage, soit par logiciel
(*« which encoder is used on which motor can be swapped via a software setting »*). C'est
exactement le « sens de comptage à MESURER au protocole caméra » déjà inscrit au tableau de
bord — le RoboClaw ne supprime pas cette vérification, il la déplace.

### ② « Quid des 12 V nécessaires ? » — le RoboClaw ne les fournit pas, et c'est sans effet

Le RoboClaw ne sort que du **5 V** (BEC, **1,2 A** sur les versions V7 et ultérieures) sur les
broches `+` des connecteurs d'encodeur. Or les `LJ12A3-4-Z/BX` demandent 6 à 36 V et sont
alimentés en **12 V** (décision du §5 de l'étude odométrie, depuis le rail Mean Well).

**Rien ne change donc pour eux** : le 12 V continue de venir du rail du robot, et
**la carte à optocoupleurs reste strictement indispensable** — c'est elle qui fait la
frontière entre le domaine 12 V sale et le domaine logique propre.

Une seule valeur bouge dans la nomenclature de cette carte :

| | Avec le RP2040 (plan actuel) | Avec le RoboClaw |
|---|---|---|
| Alimentation capteurs | 12 V (rail Mean Well) | **12 V — identique** |
| Optocoupleurs + R série 1,5 kΩ | inchangés | **inchangés** |
| Rappel de sortie | 10 kΩ vers le **3,3 V** du RP2040 | 10 kΩ vers le **+5 V** du connecteur `EN` |
| Destination du signal | GP2-GP5 du RP2040 | **`EN1 A/B`, `EN2 A/B`** |
| Le RP2040-Zero | nécessaire | **devient inutile** |

Le RoboClaw accepte ce niveau sans adaptateur (`Input High` : min 2 V, max 5 V). ⚠️ Vérifier
que les 1,2 A du BEC suffisent — ils alimenteraient seulement les quatre phototransistors,
donc quelques milliampères : très large.

### ③ « Où branche-t-on le stop ? » — sur `S3`, `S4` ou `S5`… **mais seulement en mode SÉRIE**

🔴 **Nuance décisive, qui corrige l'architecture C du §6 bis.** Le manuel est explicite :

> *« S1 and S2 are the control inputs for serial, analog and RC modes. S3 can be used as a
> flip switch input when in RC or Analog modes. **In serial mode** S3, S4 and S5 can be used
> as emergency stop inputs or as voltage clamp control outputs. When set as E-Stop inputs they
> are active when pulled low and have internal pullups so they will not accidentally trip when
> left floating. »*

**L'entrée E-Stop n'existe donc PAS en mode RC.** En mode RC, `S3` est un inverseur de sens et
`S4`/`S5` des contacts de fin de course ou d'origine.

Ce n'est pas rédhibitoire pour l'architecture C, **mais ça change la façon dont elle arrête le
robot** — et il faut l'écrire précisément :

| | Architecture A/B (série) | Architecture C (mode RC) |
|---|---|---|
| Point d'accrochage de la chaîne de sécurité | `S3` configuré en **`E-Stop (Latching)`** | le **`OE` du PCA9685**, comme aujourd'hui |
| Ce qui arrête les moteurs | l'E-Stop, **par freinage** (« *Motors are stopped by braking* ») | la disparition des impulsions → **`RC Timeout` 100 ms** |
| Mode d'arrêt | freinage, garanti | **celui d'`Idle Mode`** → 🔴 `Freewheel` par défaut, **à régler sur `Braking`** |
| Latence | immédiate | **≤ 100 ms** |

Autrement dit, en architecture C la sécurité ne passe plus par une broche du RoboClaw mais par
le fait de **taire la commande** — ce qui est précisément ce que la chaîne conçue sait faire.
C'est cohérent, c'est même élégant, mais **ça repose entièrement sur le réglage `Idle Mode =
Braking`** : laissé en `Freewheel`, un robot de 50 kg coupé en pleine course continuerait sur
son élan. Ce réglage passe du rang de « bonne pratique » à celui de **condition de sécurité**.

**Et dans les deux cas, le coup-de-poing 40 A reste le dernier mot**, ce que le manuel demande
d'ailleurs explicitement : *« The motor controller should be wired with an external contactor,
relay or high-amperage mechanical switch on the main power input. »* C'est exactement le
coup-de-poing catégorie 0 déjà conçu sur la carte main-carrier — **inchangé**.

### ④ « On ne peut pas souder un câble USB ? Ou faire du "pin USB" ? »

**Il n'existe aucun connecteur USB en barrette sur cette carte** : le manuel et le datasheet ne
mentionnent que le port micro-USB. Pas de « pin USB » documenté.

Souder un câble directement sur les pastilles du micro-USB est physiquement possible, mais
c'est une mauvaise affaire : ce sont des pastilles CMS minuscules, un arrachement emporte la
piste, et on perdrait alors **à la fois la configuration et le diagnostic** — c'est-à-dire le
seul moyen de régler `Idle Mode`, `MCU Mode` et le PID. Le connecteur fragile deviendrait
irréparable.

**Deux réponses meilleures, et le projet connaît déjà la première :**

1. **Brider le câble mécaniquement.** C'est exactement la décision prise pour le RP2040-Zero
   dans l'étude odométrie (« le bridage du câble à moins de 5 cm reste obligatoire ») : une
   bride ou un collier fixé à la carte support, de sorte qu'aucun effort n'arrive au
   connecteur. Le manuel impose de toute façon un **câble à double ferrite**.
2. **Choisir une architecture où l'USB n'est pas critique.** C'est tout l'intérêt de
   l'architecture C : l'USB n'y porte que la *lecture*. S'il se déconnecte, on perd
   l'odométrie et la télémétrie — jamais la commande, jamais la sécurité. Le connecteur
   fragile cesse alors d'être un point de défaillance du spectacle.


## 6 quater. PROPOSITION — la carte d'odométrie dans la variante RoboClaw

*Demandée par David le 26/09.* ⚠️ **Ceci est une VARIANTE conditionnelle.** Le plan officiel
reste celui de [`etude-odometrie.md`](etude-odometrie.md) (RP2040-Zero, plaque 26 × 29,
`2026-09-02-implantation-stripboard-rp2040-zero.png`) **tant que le RoboClaw n'est pas
décidé**. Rien de ce qui suit ne remplace quoi que ce soit aujourd'hui.

### Ce qui change, et ce qui ne change pas

**Le cœur ne bouge pas.** La barrière d'isolation du §5 de l'étude odométrie reste identique
au composant près : c'est elle qui justifiait la carte, et le RoboClaw ne l'apporte pas
(ses entrées `EN` sont à masse commune). Quatre voies, quatre optocoupleurs, même calcul.

| Bloc | Plan actuel (RP2040) | **Variante RoboClaw** |
|---|---|---|
| Entrée 12 V protégée (`F1` PTC, `D11` Schottky, `D12` TVS, `C11` 100 µF) | ✅ | ✅ **identique** |
| 4 × `PC817` sur support tulipe DIP-4 | ✅ | ✅ **identique** |
| 4 × R 1,5 kΩ (série LED d'opto, calibrée 12 V) | ✅ | ✅ **identique** |
| 4 × LED 3 mm de diagnostic | ✅ | ✅ **identique** |
| 4 × C 10 nF (filtre arcs de balais) | ✅ | ✅ **identique** |
| 2 × JST-XH 4 pts (capteurs, un par roue) | ✅ | ✅ **identique** |
| 1 × JST-XH 2 pts (entrée 12 V) | ✅ | ✅ **identique** |
| 4 × rappel 10 kΩ | vers le **3,3 V** du RP2040 | vers le **+5 V du RoboClaw** |
| **`U5` RP2040-Zero** | module + 2 barrettes tulipe 1×9 + 2 barrettes mâles 1×9 | 🔴 **SUPPRIMÉ** |
| Lien vers le Pi | USB-C du module, bridé | 🔴 **SUPPRIMÉ** (c'est le RoboClaw qui parle au Pi) |
| GPIO réservés au futur chantier PWM (GP6/7/26/27) | réservés | 🔴 sans objet |
| **Sortie vers le contrôleur** | — | 🟢 **2 connecteurs 4 pts → `EN1` et `EN2`** |

**Bilan** : −1 module, −4 barrettes 1×9, −1 lien USB ; +2 connecteurs. La carte devient un
**pur organe d'isolation**, sans aucune intelligence — ce qui est une simplification de fond :
plus de firmware embarqué, plus de flashage, plus de règle udev, plus de numéro de série à
gérer. Le seul code restant vit côté Pi.

### Schéma fonctionnel (une voie sur quatre)

```
   ◄──────── domaine 12 V « sale » ────────►┊◄──── domaine 5 V « propre » ────►
                                            ┊        (alimenté PAR le RoboClaw)
   +12V ──┬── R 1,5k ──┬── LED diag ──┐     ┊
          │            │              │     ┊      +5V (du connecteur EN)
     (brun)│      ┌─────┴──────┐       │     ┊            │
    ┌──────┴────┐ │  PC817     │       │     ┊         R 10k
    │ LJ12A3    │ │ (support   │       │     ┊            │
    │ NPN NO    ├─┤  tulipe)   ├───────┘     ┊            ├──────► EN1.A  (ou .B)
    └──────┬────┘ │ anode  cath│             ┊            │
     (bleu)│      │            │  collecteur ├────────────┤
   GNDPWR ─┘      └────────────┘             ┊         C 10nF
                                             ┊            │
                        BARRIÈRE ────────────┊──────────► GND (du connecteur EN)
                   (fente fraisée au PCB,    ┊
                    les 2 masses ne se       ┊
                    rejoignent NULLE PART)   ┊
```

🟢 **Un gain d'intégrité de signal, gratuit** : le domaine propre est désormais alimenté par
le **5 V du RoboClaw lui-même**, et non plus par l'USB via le Pi. La masse de référence des
signaux est donc celle de la carte qui les lit, au bout d'un câble court. C'est
électriquement meilleur que le montage actuel.

### Où la poser — ⚠️ le placement change

L'étude odométrie avait renversé sa décision le 20/08 : *carte en bas, près des roues*, parce
que le lien fragile (3,3 V vers le Pi) devait être court. **Le raisonnement reste le même mais
la cible change** : le lien fragile devient `optos → EN1/EN2`, donc

> **la carte doit être collée au RoboClaw**, pas aux roues.

Et comme le RoboClaw sera lui-même près des moteurs (câbles de puissance de 60 A aussi courts
que possible), les deux se retrouvent au même endroit — vraisemblablement le coffre des
alimentations retenu le 02/09, où le 12 V est déjà à demeure. Les câbles capteurs (1 à 2 m,
signal 12 V à collecteur ouvert, robuste) continuent de faire la longue distance, exactement
comme le §6 de l'étude odométrie l'avait raisonné.

### Encombrement

**PLAN GÉNÉRÉ le 26/09**, à la demande de David :
`pcb/kicad/wheel-odometry/gen-stripboard-roboclaw.py` → `stripboard-roboclaw.png`/`.svg`
(dépôt `pcb`, commit `5914674`). Le plan officiel à RP2040 est **intact** — les six fichiers
de référence n'ont pas été touchés.

| | Plan officiel (RP2040) | **Variante RoboClaw** |
|---|---|---|
| Plaque | 26 × 29 trous (~66 × 74 mm) | **26 × 27 trous (~66 × 69 mm)** |
| Coupures | 67 | **54** |
| Straps | 10 | 10 |
| Nets / broches | — | 22 / 74 |

⚠️ **Le gain de surface est modeste, et il faut le dire** : la suppression du module libère
8 rangées, les deux connecteurs de sortie en reprennent 5. J'avais annoncé « sensiblement
plus petite » — c'est deux rangées. **Le vrai gain est ailleurs** : 13 coupures de moins, et
surtout plus de module, donc **plus de firmware, plus de flashage, plus de règle udev, plus
de numéro de série à gérer**.

**Vérification par mutation, rejouée par l'orchestrateur** (pas seulement déclarée par l'agent
qui a produit le plan) : barrière découpée → 5 courts-circuits dont `GNDPWR + GND` sur la
même bande, refusé ; strap `ODO_LA → J7.A` retiré → « net éclaté sur 2 tronçons », refusé ;
bus `+5V_RC` tronqué → « éclaté sur 5 tronçons », refusé.

> 💡 **Enseignement d'une mutation mal ciblée, qui resservira** : supprimer les coupures de la
> *seule* colonne 11 laisse le vérificateur vert — à raison. La barrière est coupée sur **deux**
> colonnes (11 et 12) et une seule suffit électriquement ; la seconde est une **redondance
> volontaire**, la marge qui pardonne une coupure mal faite ou une bavure de cuivre. Ne pas la
> prendre pour un défaut du contrôle.

### Trois points à vérifier sur la carte réelle, avant tout plan

1. 🔴 **L'ordre exact des broches de `EN1`/`EN2`.** Le manuel donne des repères (« le `+` est
   au bord de carte et sort du 5 V », « le `−` est près du dissipateur », « les voies `A` sont
   au bord ») mais pas un brochage explicite pour ce modèle. **À relever sur la carte reçue ou
   sur le fichier du fabricant, jamais sur une photo en perspective** — c'est la leçon
   `feedback-cao-verifier-le-reel`, déjà payée une fois sur ce chantier avec les neuf
   pastilles du RP2040-Zero comptées à huit.
2. **Le sens A/B par roue** : les deux roues étant en miroir, l'une comptera à l'envers
   (§6 ter ①). Se corrige au câblage ou par réglage logiciel — mais il faut choisir, et
   l'écrire.
3. **Le niveau logique visé** : le RoboClaw accepte 0-5 V (`Input High` ≥ 2 V). Le rappel vers
   5 V donne le meilleur rapport signal/bruit ; un rappel vers 3,3 V fonctionnerait aussi.
   À trancher au moment du plan.

### Sur le micro-USB — David a raison, et voici ce qu'on peut y faire

> « C'est quand même con d'être resté en micro-USB, c'est le pire connecteur pour cet usage. »

C'est un fait objectif : le micro-USB est donné pour **~10 000 cycles** et sa rétention
mécanique repose sur deux petites pattes latérales ; l'USB-C est donné pour ~10 000 cycles
aussi mais avec une rétention franchement supérieure et surtout **réversible**. Un
RP2040-Zero à 5 € a de l'USB-C ; une carte de puissance à 230 $ destinée à des machines qui
vibrent est restée en micro-USB, et le V8 — révision de 2024+ — ne l'a pas corrigé. Il n'y a
pas de bonne raison, sinon la compatibilité avec la lignée précédente.

Ce qu'on peut faire, par ordre d'efficacité :

1. **Ne pas en dépendre.** C'est l'argument le plus fort en faveur de l'architecture C : si
   l'USB ne porte que la lecture, son arrachement coûte l'odométrie, jamais la commande ni la
   sécurité. Un connecteur fragile qui ne tient rien de critique cesse d'être un problème.
2. **Brider le câble**, comme déjà décidé pour le RP2040-Zero : collier ou bride sur la carte
   support, à moins de 5 cm, de sorte qu'aucun effort n'atteigne le connecteur. Le manuel
   impose de toute façon un **câble à double ferrite**.
3. **Câble coudé + boîtier imprimé.** Une prise micro-USB coudée sortant à ras, plus un capot
   PETG qui l'emprisonne : c'est le type de pièce que le projet sait produire, et ça supprime
   le bras de levier, qui est le vrai tueur de ces connecteurs.
4. ❌ **Ne pas souder sur les pastilles** (§6 ter ④) : on y perdrait la configuration ET le
   diagnostic, donc le seul accès à `Idle Mode`, `MCU Mode` et au PID.


## 6 quinquies. RECOMMANDATION — ce que je propose concrètement

*Demandée par David le 26/09, après son constat : « c'est vraiment du debug finalement,
contrairement à la doc ».*

### Le constat qui tranche

Il y a bien **deux discours**, et il faut choisir lequel engage :

| Source | Ce qu'elle dit de l'USB | Ce qu'elle est |
|---|---|---|
| **Pololu** (page produit) | *« allowing it to be controlled directly from a computer »* | le **revendeur** |
| **Basicmicro** (datasheet) | *« The USB port **should be used for configuration and debugging**. The USB protocol is not designed for electrically noisy environments. »* | le **concepteur** |

**On croit le concepteur.** L'USB de cette carte est un port d'atelier, pas un lien
d'exploitation. David a raison, et ça a une conséquence que la section §6 bis n'avait pas
tirée jusqu'au bout.

### ⚠️ Ce que ça change : l'architecture C est affaiblie

J'ai présenté l'architecture C (mode RC + USB en lecture) comme « la plus prudente ». **Pour
la sécurité, elle l'est** — perdre l'USB n'y coûte jamais la commande. **Mais pour l'objectif,
elle ne l'est pas** : en mode RC, l'USB est le **seul** chemin qui remonte les compteurs
d'encodeurs. Or l'odométrie *est* le but de tout ce chantier.

Un USB intermittent donne donc une **odométrie intermittente** — c'est-à-dire une TF
`odom` → `base_link` qui saute, donc nav2 qui décroche et le suivi de personne qui perd sa
référence. Ce n'est pas un risque de sécurité, c'est un risque **fonctionnel**, et il porte
précisément sur ce qu'on cherchait à obtenir.

**Conclusion : C est une excellente configuration de BANC, une mauvaise CIBLE.**

### Ma recommandation : A en cible, C pour le banc

**Cible — architecture A, `Packet Serial` sur TTL :**

```
  Pi 4 ──UART, 3 fils (isolés)──► RoboClaw ──► moteurs
                                     ▲
  chaîne de sécurité ──────────► S3 « E-Stop (Latching) »
  (watchdog 74HC123 + 74HC74)        ▲
                                  EN1/EN2 ◄── carte optos ◄── capteurs 12 V
  USB : DÉBRANCHÉ en service, rebranché à l'atelier pour Motion Studio
```

Pourquoi c'est la bonne cible, en trois raisons indépendantes :

1. **C'est le seul lien qui porte la commande ET la lecture de façon fiable.** Un seul chemin
   à fiabiliser, à isoler et à tester, au lieu de deux chemins dont un fragile.
2. **L'E-Stop matériel `S3 (Latching)` est supérieur au `OE` du PCA9685** : il **freine**
   (« *Motors are stopped by braking* ») là où le `OE` coupe le PWM et laisse 50 kg sur leur
   élan ; et il est **latché**, donc il ne se réarme pas tout seul.
3. **Le moment est le bon, et il ne se représentera pas.** La bande sécurité de la carte
   main-carrier est **placée mais pas routée** (122 chevelus, volontaire). Changer le point
   d'accrochage maintenant coûte un dessin ; le changer après gravure coûte une carte.
   Ce qui ressemblait à un défaut de l'architecture A (« elle oblige à refondre la chaîne »)
   est en réalité une **opportunité de calendrier**.

**Banc — architecture C, pour la mise au point :**

Mode RC piloté par le PCA9685 existant, USB branché pour observer. C'est là que l'USB est
exactement à sa place : configuration, réglage du PID, lecture des compteurs, diagnostic. On
y valide la mécanique, les optocoupleurs, le sens de comptage par roue, les constantes PID —
**sans écrire une ligne du protocole série**. Puis on bascule en Packet Serial pour la cible,
sans rien racheter : même carte, même câblage d'encodeurs, mêmes optos.

### Les réglages qui ne sont pas négociables, quelle que soit l'architecture

| Réglage | Valeur | Pourquoi |
|---|---|---|
| `Idle Mode` | **`Braking`** | le défaut `Freewheel` laisse 50 kg sur leur élan |
| `MCU Mode` (si mode RC) | **activé** | sinon la plage d'impulsions s'auto-calibre en cours de spectacle |
| `Timeout` série | **réglé explicitement** | la valeur d'usine n'est pas documentée |
| `Home (Auto)` sur S4/S5 | **jamais** | fait bouger le moteur à la mise sous tension |
| `Fwd/Rev Limit` | bridé au besoin | ceinture matérielle que ROS ne peut pas desserrer |
| Écriture en NVM (cmd 94) | **après chaque réglage** | rien n'est sauvegardé automatiquement |
| Batterie logique sur `LB IN` | **oui** | évite le redémarrage logique sous forte charge |

### Ce que ça demande de décider, et dans quel ordre

1. **Rien tout de suite.** La mesure du courant moteur à la pince, pendant le test scénique au
   sol, décide du modèle (2x30A à 152,50 € ou 2x60A à 250,86 €) et ne coûte rien.
2. **Si le RoboClaw est retenu** : acheter le 2x60A, et instruire au même moment le
   ré-accrochage de la chaîne de sécurité sur `S3` — c'est un lot de conception, à faire
   **avant** de router la bande sécurité.
3. **L'inconnue n° 13 (les compteurs sont-ils lisibles par USB en mode RC ?) perd son
   caractère bloquant** dans cette recommandation : elle ne conditionne plus que le confort du
   banc, plus l'architecture cible. Elle reste utile à lever, elle n'arrête plus rien.


## 6 sexies. « Des odomètres en 5 V, ce ne serait pas plus simple ? » — non, et le manuel l'explique

*Question de David le 26/09 : « sinon ça ne serait pas plus simple des odomètres à 5 V ?
C'est courant ? Fiable ? »* Elle est excellente, parce qu'elle vise le seul composant qui
pourrait disparaître — et la réponse tient en une phrase : **l'optocoupleur n'est pas là pour
convertir une tension, il est là pour séparer deux masses.** Changer la tension du capteur ne
supprime donc pas le besoin ; ça supprime seulement l'illusion du besoin.

### Est-ce courant ? Oui. Est-ce fiable ? Ça dépend entièrement du châssis

**Courant : absolument.** Un encodeur 5 V branché directement sur les entrées d'un contrôleur,
c'est la norme de toute la robotique de loisir et de la plupart des robots de service. Les
`EN1`/`EN2` du RoboClaw sont faits pour ça.

**Fiable : sur un robot propre, oui. Sur Didier, non** — et ce n'est pas un avis, c'est écrit
dans le manuel du RoboClaw, section *Encoder Signal Conditioning* :

> *« RoboClaw accepts direct quadrature encoder inputs but **does not include built-in signal
> conditioning**, as this would limit maximum count speed. Some encoders provide weak or noisy
> signals that may require external conditioning [...] This can include **adding pull-up
> resistors to open-collector or open-drain outputs** [...] Some encoders may **inject noise
> onto the power lines, which can interfere with RoboClaw and other connected devices**. For
> applications in **electrically noisy environments, differential encoders are strongly
> recommended** to improve noise immunity and signal integrity. »*

Trois choses à en retenir, dans l'ordre :

1. **Le RoboClaw ne conditionne rien.** Ses entrées sont nues, par choix de conception (pour
   ne pas plafonner la vitesse de comptage). Tout le filtrage est à notre charge.
2. **Il recommande lui-même d'ajouter des rappels sur les sorties à collecteur ouvert** —
   c'est-à-dire exactement le montage de notre carte, qui existait avant lui.
3. **Il avertit qu'un capteur peut injecter du bruit dans l'alimentation** et perturber le
   contrôleur *et les autres appareils connectés*. Alimenter des capteurs 5 V depuis le BEC du
   RoboClaw, au bout de 1 à 2 m de câble courant le long des moteurs, c'est précisément le
   scénario qu'il déconseille.
4. Et pour un milieu bruité, sa recommandation n'est pas « du 5 V simple », c'est **du
   différentiel** — c'est-à-dire *plus* de précautions que ce qu'on a, pas moins.

### Le point qui tue l'idée : avec le RoboClaw, la masse logique EST la masse de puissance

C'est l'argument décisif, et il est prouvé par une phrase du datasheet :

> *« **Do not disconnect the negative terminal if other ground sources are connected**, such as
> USB cable. Damage will occur. »*

Si débrancher le `B−` de la batterie pouvait détruire la carte quand un câble USB est
branché, c'est que **la masse de puissance et la masse logique sont le même cuivre**. Or ce
cuivre-là voit passer **jusqu'à 120 A de crête** quand les moteurs démarrent.

Conséquence concrète : brancher un capteur 5 V en direct reviendrait à faire courir sa masse
de retour sur 1 à 2 m, le long des moteurs, pour la raccorder à ce cuivre. Quelques
milliohms × 60 A = **des centaines de millivolts** de chute qui s'ajouteraient au signal
logique, dont le seuil haut est à 2 V. Ce n'est pas une marge confortable, c'est une loterie
— et une loterie intermittente, qui ne se manifesterait qu'en pleine accélération, donc le
soir de la représentation.

**L'isolation est donc PLUS nécessaire avec le RoboClaw qu'avec le RP2040**, pas moins : le
RP2040 avait au moins une masse logique propre, alimentée par l'USB.

### Ce qu'on perdrait aussi, et qui n'est pas évident

Le §6 de l'étude odométrie avait choisi le 12 V à collecteur ouvert pour une raison précise :
*« basse impédance, forte amplitude — une brute, quasi insensible aux parasites ; c'est pour
ça que l'industrie l'utilise dans des armoires bourrées de variateurs »*. C'est ce signal-là
qui fait les 1 à 2 m jusqu'aux roues.

En 5 V, on remplacerait ce signal robuste par un signal fragile **sur la même longueur de
câble**, dans le même environnement. On ne déplacerait pas le problème : on l'aggraverait aux
deux bouts.

### ⚠️ Correction du 26/09 : la variante 5 V EXISTE (David l'a trouvée)

Cette section affirmait d'abord que ces capteurs « ne descendent pas à 5 V ». **C'est faux au
niveau de la famille** : le **`LJ12A3-4-Z/BX-5V`** existe, vendu explicitement « tension de
travail 5 VDC, spécial pour MCU », **4,29 € TTC** (ELECAPITAL, AliExpress, relevé par David le
26/09 ; 40 vendus, 2 avis). C'était vrai des **six exemplaires en stock** — eux sont bien en
6-36 V — mais pas de la référence en général. L'argument « fait accompli » était donc le plus
faible des quatre, et il tombe à moitié : il resterait ~26 € et un délai pour rééquiper.

**Mais les trois autres arguments tiennent intégralement, et deux EMPIRENT en 5 V :**

| Argument | En 12 V | En 5 V |
|---|---|---|
| L'opto isole deux masses | nécessaire | **toujours aussi nécessaire** — la tension n'y change rien |
| Marge de bruit sur 1-2 m le long des moteurs | large (le signal est « une brute ») | 🔴 **divisée par plus de deux** : seuil haut à 2 V, seuil bas à 0,8 V |
| Chute de masse due au courant moteur (jusqu'à 120 A de crête) | noyée dans l'amplitude | 🔴 **mange directement la marge** |
| Bruit injecté sur l'alimentation du capteur | sans effet (rail 12 V dédié) | 🔴 remonterait vers le **BEC du RoboClaw** — ce que son manuel déconseille explicitement |

Autrement dit : **le seul scénario où le 5 V simplifierait vraiment, c'est celui où l'on
renoncerait à l'isolation.** Et c'est le scénario qu'on refuse, pour la raison écrite plus
haut — avec le RoboClaw, la masse logique *est* la masse de puissance.

Un capteur 5 V **derrière** l'optocoupleur, lui, n'apporte rien du tout : on garderait la
carte, on paierait de nouveaux capteurs, et on perdrait la robustesse du 12 V sur les deux
mètres qui comptent. Il n'existe donc **aucun scénario où le 5 V est meilleur ici** — ce qui
est une conclusion plus forte, et mieux fondée, que le simple « on les a déjà achetés ».

> 💡 **À garder en tête pour un AUTRE robot** : sur une machine plus petite, aux moteurs plus
> faibles et au câblage court, le `LJ12A3-4-Z/BX-5V` branché en direct sur un `EN1`/`EN2`
> serait le bon choix — simple, éprouvé, et à 4,29 €. Ce n'est pas une mauvaise idée en soi,
> c'est une mauvaise idée **pour ce châssis-ci**.

Enfin, l'arbitrage du §4 de l'étude odométrie (inductif plutôt qu'optique : tolérance à la
poussière de plateau et à la graisse, portée réglable, robustesse industrielle) **reste
valable dans les deux tensions** — il n'est pas rouvert par cette question.

> À titre de complétude : des solutions 5 V existent bel et bien en stock — les **fourches
> optiques** `MH-Sensor-Series` (8 à 10 modules, cf. `inventaire-stock.md` §1.3). Elles restent
> le plan B documenté si un capteur inductif venait à manquer. Mais elles ne suppriment pas la
> barrière non plus, **et une fourche optique sur un robot de théâtre est un capteur qui se
> remplit de poussière de plateau** — c'est une des raisons du choix inductif.

### « Il faut garder l'optocoupleur ? » — oui, et voici l'argument qui décide

*Question de David, 26/09.* Elle mérite une réponse franche, y compris sur ce qui est
discutable.

**Avec les capteurs 12 V actuels : ce n'est pas négociable.** Les entrées `EN` du RoboClaw
acceptent 0-5 V, maximum absolu 5 V. Un capteur 12 V dont la sortie se retrouverait
accidentellement au potentiel d'alimentation — fil pincé, capteur claqué, erreur de câblage
sur un bornier — enverrait **12 V dans une entrée prévue pour 5** et détruirait le
contrôleur. C'est exactement le piège « NPN, et JAMAIS PNP » du §4 de l'étude odométrie, avec
une carte à 250 € au bout au lieu d'un RP2040 à 5 €. L'opto, lui, encaisse : le défaut meurt
sur la LED, et il ne coûte que 7 centimes à remplacer dans son support tulipe.

**Avec des capteurs 5 V, c'est techniquement discutable — et je le dis honnêtement.** On
pourrait s'en passer. C'est ce que fait l'immense majorité de la robotique, et le corps des
`LJ12A3` étant monté dans une patte en PETG imprimé, il est déjà isolé du châssis : câblés en
étoile depuis le connecteur `EN`, les capteurs ne créeraient pas de boucle de masse. L'idée
tient debout.

**Ce qu'on perdrait quand même, et qui n'est pas rattrapable ailleurs :**

1. **La protection contre les défauts** (ci-dessus) : elle disparaît, quelle que soit la
   tension nominale. Un capteur à 4 € peut tuer un contrôleur à 250 €.
2. **L'immunité aux arcs de balais.** Deux mètres de câble longeant des moteurs qui commutent
   jusqu'à 120 A captent des transitoires par couplage capacitif et inductif — ça ne passe pas
   par la masse, donc un câblage en étoile n'y change rien. Avec un seuil de basculement à
   2 V, la marge est mince ; c'est précisément ce que le manuel RoboClaw anticipe en
   recommandant des **encodeurs différentiels** en milieu bruité.
3. **Le filtre `C 10 nF`**, qui avale les pointes des balais, perdrait son point d'application
   propre.

**Et le coût de la garder est faible, surtout maintenant.** Sans le RP2040, la carte se réduit
à quatre voies identiques et à sa protection d'entrée : ~7 centimes par optocoupleur, des
composants **déjà en stock**, et une carte nettement plus petite qu'aujourd'hui (§6 quater).
Face à un contrôleur à 250 € et à un robot qui joue devant du public, le rapport est sans
appel.

> **La formulation juste n'est donc pas « faut-il garder l'opto ? » mais « que coûterait de le
> retirer ? ».** Réponse : quatre composants à 7 centimes et environ deux heures de montage,
> contre la disparition d'une barrière qui protège une carte à 250 €, dans un châssis dont
> l'étude odométrie a déjà établi qu'il est « électriquement hostile ». Le projet a une règle
> de sécurité non négociable et des incidents roues au compteur : on ne retire pas une
> protection déjà conçue, testée en modèle et dont les composants sont achetés, pour économiser
> deux heures.


### Conclusion

**La carte à optocoupleurs reste indispensable, quelle que soit la tension des capteurs et
quel que soit le contrôleur.** C'est même le seul élément de tout ce chantier qu'aucune des
architectures étudiées ne remet en cause. Le §6 quater ne change donc pas d'une ligne.


## 7. Inconnues à lever avant toute décision

| # | Inconnue | Comment la lever | Bloquant ? |
|---|---|---|---|
| 1 | **Courant réellement tiré par les moteurs** (nominal lu : < 13,4 A ; blocage **non documenté**) | **pince ampèremétrique pendant le test scénique au sol**, + roue bloquée roues hors sol (§5 bis) | 🔴 **OUI** — c'est LUI qui décide entre le 2x30A (152,50 €, 30/60 A) et le 2x60A (~322 €, 60/120 A). Sans ce chiffre on paie 170 € de marge dont on ignore si elle sert |
| 2 | **Comment tenir la règle « simulation d'abord »** sans plugin Gazebo | lire si `basicmicro_ros2` peut tourner en mock dans la sim, ou si `diff_drive_controller` suffit à valider la cinématique | 🔴 **OUI** — c'est une règle de méthode du projet |
| 3 | Le PID tient-il à ~10 impulsions/s (régime de jeu) ? | banc d'établi, roues hors sol, avant tout usage au sol | non (repli : boucle ouverte + odométrie) |
| 4 | Câblage du chemin de retour batterie / diode, quand Didier est **poussé à la main** | manuel §Wiring + dimensionnement | 🔴 **OUI** — sécurité |
| 5 | Dimensionnement du clamp de régénération (R3) | procédure par paliers du manuel | non, mais avant les pentes |
| 6 | Les entrées encodeur A/B ont-elles vraiment des pull-ups internes ? | multimètre sur la carte — la doc l'affirme *globalement* mais pas pour EN1/EN2 | non (on met un pull-up externe de toute façon, §5 odométrie) |
| 7 | `basicmicro_ros2` arrête-t-il les moteurs si le flux ROS cesse ? | lire le code, pas le README | 🔴 **OUI** si c'est ce driver qui est retenu |
| 8 | Valeur d'usine du timeout série | non documentée → **la régler explicitement**, ne jamais s'y fier | non (contourné) |
| 9 | **Révision livrée par RobotShop EU** (`RB-Bat-48` / `IMC414`) : **V7 ou antérieure ?** | leur demander. La photo montre des boutons, donc ce n'est pas un V8 — reste à savoir si c'est un **V7 (acceptable, voire préférable)** ou un **V6 (à refuser** : MOSFET d'origine, dissipateurs non taraudés) | 🔴 **OUI avant d'acheter** |
| 10 | **Isolation du lien TTL série** Pi ↔ RoboClaw | le pilotage passe par le TTL (l'USB est déconseillé par le fabricant en milieu bruité) : signal logique nu entre deux masses, au milieu des moteurs → même problème qu'au §5 de l'étude odométrie | 🔴 **OUI** — à traiter comme la barrière des capteurs |
| 12 | **Réarmement du watchdog 74HC123** : plus d'écriture I²C roues à prouver | le réarmer sur l'acquittement d'une trame Packet Serial ; à trancher au routage de la bande sécurité. ⚠️ **Ne concerne QUE les architectures A et B** — en architecture C (mode RC), le watchdog et le `OE` restent valables tels quels (§6 bis) | 🔴 **OUI en A/B**, sans objet en C |
| 13 | **En mode RC, les compteurs d'encodeurs sont-ils lisibles par USB ?** | banc, 10 min : RoboClaw en mode RC, USB branché, commande 16/17 « Read Encoder Count » | **non bloquant depuis la recommandation §6 quinquies** : ne conditionne plus que le confort du banc, l'architecture cible étant A |
| 11 | **Source de la batterie logique séparée** | le datasheet l'exige sous forte charge (effondrement de tension = redémarrage logique en pleine manœuvre) ; le rail 12 V Mean Well existe-t-il assez près ? | 🔴 **OUI** |

## 9 bis. COMPARATIF SÉRIEUX — Cytron MDS40B (monté) contre RoboClaw 2x60A

*Demandé par David le 26/09 : « j'ai un doute finalement ».* Le doute est fondé, et ce
comparatif a fait tomber **trois** de mes arguments antérieurs. Sources : manuel officiel
Cytron `MDS40B User's Manual` Rev 1.0 (déc. 2015, 24 p., lu page par page) et documentation
Basicmicro (datasheet 2x60A + user manual, lus en local). ⚠️ Une `Rev 1.1` de juillet 2023
est signalée par une recherche mais n'a **pas pu être lue** — ce comparatif ne couvre que la
Rev 1.0.

### Le tableau

| | **Cytron MDS40B ×2** (monté) | **RoboClaw 2x60A** |
|---|---|---|
| Prix | **75,00 € TTC** pièce (Opencircuit, NL) → **150 €** les deux | **250,86 € TTC** franco (RobotShop EU) |
| Tension | **10-45 V** | 6-34 V |
| Courant continu / crête par canal | 40 A / **80 A (1 s)** | **60 A / 120 A** |
| Dérating thermique | 🟢 **progressif, ne coupe JAMAIS** : 80 A < 50 °C, 50 A à 50-70 °C, 45 A à 70-100 °C, 40 A à 100-110 °C, **35 A au-delà de 110 °C** | 🔴 dérating de 85 °C à **0 A à 100 °C**, puis défaut → roue libre |
| Commutation | **16 kHz**, régénérée en interne | non lue (élevée) |
| Encombrement | 105 × 106 × 38 mm **× 2** = ~844 cm³ | **100 × 86 × 30 mm** = ~258 cm³ |
| Masse | non trouvée (nulle part) | 300 g |
| Safe start | 🟢 **oui** (« the input data must be 'stop' … prevent the driver from sudden run ») | 🟢 oui (option `Safe Start`) |
| **Timeout de perte de signal** | ⚠️ **documenté SEULEMENT en mode RC** (100 ms). **Rien pour le mode PWM/Analog — celui qu'on utilise** | 🟢 série réglable (0-25,5 s) **et** `RC Timeout` 100 ms |
| Entrée E-Stop pour chaîne externe | 🔴 **aucune** (le bornier `M` ne coupe que la logique) | 🟢 `S3/S4/S5` en `E-Stop (Latching)`, freinage |
| Entrée encodeur | 🔴 aucune | 🟢 2 × quadrature |
| Asservissement | 🔴 aucun | PID 300 Hz *(voir la réserve ci-dessous)* |
| Télémétrie relisible | 🔴 **aucune** — les deux modes série sont en **écriture seule** | 🟢 courant, tensions, 2 températures, encodeurs, erreurs |
| Sous-tension | ⚠️ **avertissement seul, la puissance est maintenue** | roue libre tant que la condition dure |
| Surtension | > 45 V → arrêt | seuils réglables |
| Inversion de polarité | 🔴 **aucune protection** (répété 3× en rouge) | 🔴 aucune non plus |
| Régénération | même avertissement : batterie en parallèle obligatoire | idem + `VClamp` dédié |
| Statut catalogue 2026 | contradictoire ; **commandable chez Opencircuit (UE), 5-7 j** | au catalogue, 11 en stock |
| **Validé sur Didier** | 🟢 **OUI — protocole caméra 4/4 du 2026-07-04** | ❌ jamais branché |

### Trois de mes arguments tombent — il faut le dire

**1. 🔴 Le ronflement à 60 Hz n'existe pas.** Le manuel Cytron, mode PWM : *« The filter
capacitor is connected and **the input signal is low pass filtered to be an analog signal**. »*
Le Cytron ne recopie donc pas le PWM d'entrée : il le **filtre en tension**, puis pilote ses
MOSFET à **16 kHz régénérés en interne** (*« switched at 16 KHz to ensure quiet operation and
no annoying whining sound »*). Le moteur n'a jamais été haché à 60 Hz.
👉 **Correction à reporter dans [`etude-chemin-commande-roues.md`](etude-chemin-commande-roues.md) §2.1**,
qui présentait ce ronflement comme « un point de qualité, lui bien réel mais non mesuré ».
Il n'est pas réel. Et l'argument « le RoboClaw supprime le ronflement » disparaît avec lui.

**2. 🔴 Le PID à 300 Hz est inutilisable au régime de jeu.** Avec 40 impulsions par tour de
roue (~51/m) : ~51 impulsions/s à 1 m/s, mais **~10/s à 0,2 m/s** — le PID passerait une
trentaine de cycles à corriger sur une mesure périmée. On ne peut pas asservir plus vite qu'on
ne mesure. Un asservissement côté Pi à 20 Hz, alimenté par le comptage du RP2040, ferait
presque aussi bien. **L'argument « il asservit tout seul » vaut donc surtout au-dessus de
0,5 m/s**, c'est-à-dire hors du régime où Didier joue.

**3. 🔴 Le Cytron tient mieux la chaleur que le RoboClaw.** C'est contre-intuitif vu les
masses, mais c'est écrit : le Cytron **dégrade progressivement et ne coupe jamais** (35 A
encore disponibles au-delà de 110 °C), là où le RoboClaw **tombe à 0 A à 100 °C** puis passe
en défaut roue libre. Pour un spectacle, une dégradation progressive vaut mieux qu'un arrêt
net — un robot qui ralentit se rattrape, un robot qui s'arrête casse la scène.

### Ce qui reste, et qui est réel

**Au crédit du RoboClaw :**

1. 🟢 **Le timeout et l'E-Stop matériels.** C'est le point le plus lourd, et le comparatif
   l'aggrave encore en faveur du RoboClaw : le manuel Cytron ne documente un timeout **qu'en
   mode RC**, or Didier utilise le **mode PWM/Analog**, pour lequel *rien* n'est écrit. Pire,
   ce mode filtre l'entrée en tension : si le PCA9685 se fige (bus I²C planté), le condensateur
   garde sa charge et **le moteur continue**. C'est exactement le scénario que la chaîne de
   sécurité matérielle existe pour traiter — et ce comparatif confirme qu'elle est
   indispensable, RoboClaw ou pas.
2. 🟢 **Aucune télémétrie côté Cytron** : ses deux modes série sont en **écriture seule**. Pas
   de courant, pas de tension, pas de température. Le chantier télédiagnostic restera aveugle
   sur la puissance tant qu'on gardera les Cytron.
3. 🟢 **L'encombrement** : 258 cm³ contre ~844 cm³ pour les deux Cytron réunis, soit **trois
   fois moins**, avec un seul jeu de câbles et une seule fixation.
4. 🟢 **L'odométrie intégrée**, qui supprime le RP2040 et son firmware.

**Au crédit du Cytron :**

1. 🟢 **Il est validé sur le robot** — protocole caméra 4/4 du 2026-07-04. C'est le seul
   maillon du chemin roues qui ait été éprouvé physiquement. Ça ne se remplace pas par une
   fiche technique.
2. 🟢 **Il est moins cher** : 150 € les deux contre 250,86 €. L'écart réel est de **~100 €**,
   pas de 74 € comme l'indiquait le premier chiffrage (le prix Opencircuit à 75 € est
   inférieur aux 88,30 € de Neven7).
3. 🟢 **Meilleure marge de tension** (10-45 V contre 6-34 V) et **meilleur comportement
   thermique**.
4. 🟢 **Zéro travail logiciel, zéro risque de régression.**

### ⚠️ Une découverte qui concerne le montage ACTUEL, indépendamment de toute décision

Le mode PWM du Cytron **filtre le signal en tension**. Or on l'attaque à **60 Hz** (période
16,7 ms), et **le manuel ne donne aucune plage de fréquence d'entrée acceptée** — la donnée
n'existe pas dans le document. Un filtre passe-bas dimensionné pour du PWM de quelques kHz,
attaqué à 60 Hz, laisse passer une **ondulation résiduelle** sur la tension de consigne.

Cela pourrait expliquer le vestige relevé dans le code et jamais élucidé : `wheels.py:34`
déclare `FREQUENCY = 500`, **utilisé nulle part**. Quelqu'un avait vu qu'il fallait monter la
fréquence, et n'est pas allé au bout.

👉 **C'est une vérification à faire au test scénique au sol**, quelle que soit la suite : on
cherche une consigne qui tremble à basse vitesse. Si c'est le cas, monter la fréquence du
PCA9685 est bloqué par les servos qui partagent la puce (§2.1) — ce qui redonne du poids à la
séparation 0x40/0x41 déjà prévue… **ou au RoboClaw, qui supprime le problème à la racine.**

### Verdict

**Le RoboClaw reste le meilleur contrôleur sur le fond** — timeout et E-Stop matériels,
télémétrie, encombrement, odométrie intégrée. Mais le comparatif a réduit son avance : son
PID ne sert pas au régime de jeu, il ne supprime aucun ronflement, il tient moins bien la
chaleur, et il coûte 100 € de plus.

**Et surtout : aucun de ses avantages n'est un verrou du projet aujourd'hui.**

- La sécurité réelle viendra de la **bande sécurité routée**, pas du choix de driver — le
  comparatif le confirme même doublement, puisque le Cytron en mode PWM n'a aucun timeout
  documenté.
- L'odométrie a **déjà** sa solution complète, écrite et testée (RP2040, 35 tests, carte
  dessinée et vérifiée).
- Le verrou n° 1 du projet reste le **test scénique au sol**, qui se fait avec l'existant.

**Recommandation révisée, et elle s'aligne avec le doute de David : ne pas changer
maintenant.** Faire rouler le robot au sol avec les Cytron validés, mesurer le courant à la
pince, écouter la consigne à basse vitesse. Ces trois informations coûtent zéro euro et
décideront mieux que n'importe quelle fiche technique.

> 💡 **Une précaution qui ne coûte presque rien et préserve les deux options** : au moment de
> **router la bande sécurité**, sortir la sortie de la bascule 74HC74 sur un **cavalier à deux
> positions** — l'une vers le `OE` du PCA9685 (architecture actuelle), l'autre vers un
> connecteur 2 points destiné à une entrée `E-Stop` externe. Le coût est d'un cavalier et de
> deux pastilles. Le bénéfice : la carte main-carrier reste valable **quel que soit le driver
> choisi plus tard**, et la décision RoboClaw cesse d'être bloquée par le calendrier du
> routage. C'est la seule action de cette étude qui mérite d'être faite **maintenant**.


## 8. Où en est la décision

**Ce qui est acquis** : le calcul de David est juste (152,50 € contre 176,60 € pour un
remplacement à l'identique), la simplification est réelle et va bien au-delà du prix, et le
gain de sécurité — timeout et E-Stop **matériels** — est le plus important depuis que la
chaîne de sécurité a été conçue. Ce n'est pas un gadget : c'est la première réponse
crédible au *« si `wheels_node` meurt, rien n'arrête les roues »*.

**Ce qui s'y oppose aujourd'hui**, et il faut le peser honnêtement :

- c'est le **chemin roues** : simulation, puis protocole caméra roues hors sol, puis revue —
  or le robot est **en pièces** depuis le 03/09, et la priorité n° 1 est le **test scénique
  au sol avec les Cytron déjà validés le 2026-07-04** ;
- la règle « simulation d'abord » n'a **pas** de réponse évidente ici (inconnue 2) ;
- le 2x30A est **moins costaud** que les MDS40B actuels (30/60 A contre 40/80 A) tant que
  l'inconnue 1 n'est pas levée ;
- la bande sécurité de la carte main-carrier est **placée mais pas routée** : la refonder
  autour de l'E-Stop du RoboClaw changerait une conception en cours, pas une carte finie —
  ce qui est d'ailleurs le **bon moment** pour le faire, si on le fait.

- 🔴 **le dimensionnement (§5 bis) a déplacé la question du technique vers le PRIX.**
  L'objection de David était fondée sur le 2x30A (60 g, 30/60 A, moins que l'existant) ; mais
  le **2x60A** existe, avec dissipateur d'usine, 300 g et 60/120 A — au-dessus de l'existant.
  Seulement il coûte **250,86 € TTC franco** (RobotShop EU, relevé par David) contre 176,60 €
  pour remplacer les deux Cytron à l'identique. Le « plus simple ET moins cher » devient donc
  **« plus simple, plus compact, mieux dimensionné, pour ~74 € de plus »** — un arbitrage
  bien plus favorable que ce que laissait croire le premier chiffrage.

**Séquence proposée, sans rien acheter et sans rien démonter :**

1. **Mesurer le courant moteur à la pince ampèremétrique pendant le test scénique au sol**
   (§5 bis) — chantier priorité n° 1, déjà prévu, avec les Cytron en place. Cette mesure
   n'existe pas aujourd'hui et elle conditionne **toute** décision de puissance sur ce robot,
   celle-ci comme les suivantes. C'est la seule action dont la valeur est certaine.
2. Lever l'inconnue 2 (**comment tenir « simulation d'abord » sans plugin Gazebo**) : c'est
   une règle de méthode du projet, pas un détail d'outillage.
3. Reprendre cette étude **au moment de router la bande sécurité** de la carte main-carrier.
   C'est là que le point d'accrochage de la chaîne (`OE` du PCA9685 ou `E-Stop (Latching)` du
   RoboClaw) doit être choisi, et il vaut mieux le choisir avant de graver le cuivre
   qu'après. Si le RoboClaw est retenu un jour, c'est le moment où il coûte le moins cher à
   intégrer.

**Ce qui n'est PAS proposé** : acheter maintenant, ni toucher au plan de la carte
d'odométrie (§6 bis de l'étude odométrie : il ne change pas), ni démonter quoi que ce soit.

> **Sources, toutes consultées le 2026-09-26.** Prix : neven7.eu (MDS40B, 88,30 € TTC),
> botland.store (RoboClaw 2x30A V6B 152,50 € TTC ; MDDS30 77,50 € TTC), jsumo.com
> (SmartDrive40, 185 $, rupture — écart non expliqué). Documentation officielle Basicmicro,
> PDF téléchargés et lus localement : `roboclaw_datasheet_2x30A.pdf` (v3.0, 16 p.) et
> `roboclaw_user_manual.pdf` (firmware 4.3.0+, rév. 6.0, ~93 p.) — timeout (cmd 14, p. 79),
> E-Stop (p. 35-39), Idle Mode (cmd 160, p. 89), Home Auto (p. 36), régénération (p. 11,
> 44-45), NVM (cmd 94, p. 90), PID vitesse (cmd 28/29, p. 79-80), télémétrie (p. 70-77),
> CRC16 (p. 65), entrées encodeur (p. 9, 53-54). Manuel MDS40B via manualslib.com (RC1/RC2).
> ⚠️ **cytron.io est inaccessible (403 systématique)** : aucune donnée de cette étude ne
> vient de la page constructeur Cytron. ⚠️ **forums.basicmicro.com ne résout pas** (DNS) :
> les retours d'expérience cités comme « indices » ne sont pas vérifiés à la source.
> Dépôts ROS 2 : métadonnées via l'API GitHub (dates de `pushed_at`).
