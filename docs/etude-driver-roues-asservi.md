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
| ~~RoboClaw 2x60A V7~~ (3292) | 320 g — 3,4″ × 3,9″ × 1,2″ | 60 A / 120 A | oui | 229,95 $ mais **OBSOLÈTE** ; **retiré de l'offre chez TME** |
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
| **Chaîne de sécurité conçue** | 🔴 **à refondre** (accrochage sur `E-Stop`, watchdog à réarmer autrement) | 🔴 **à refondre** | 🟢 **inchangée** |
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
| 9 | **Révision livrée par RobotShop EU** (`RB-Bat-48` / `IMC414`) | leur demander — le V8 de Pololu est équipé et sans boutons ; la photo RobotShop montre des boutons, donc une révision antérieure | non, mais à demander AVANT d'acheter |
| 10 | **Isolation du lien TTL série** Pi ↔ RoboClaw | le pilotage passe par le TTL (l'USB est déconseillé par le fabricant en milieu bruité) : signal logique nu entre deux masses, au milieu des moteurs → même problème qu'au §5 de l'étude odométrie | 🔴 **OUI** — à traiter comme la barrière des capteurs |
| 12 | **Réarmement du watchdog 74HC123** : plus d'écriture I²C roues à prouver | le réarmer sur l'acquittement d'une trame Packet Serial ; à trancher au routage de la bande sécurité. ⚠️ **Ne concerne QUE les architectures A et B** — en architecture C (mode RC), le watchdog et le `OE` restent valables tels quels (§6 bis) | 🔴 **OUI en A/B**, sans objet en C |
| 13 | 🔴 **En mode RC, les compteurs d'encodeurs sont-ils lisibles par USB ?** | banc, 10 min : RoboClaw en mode RC, USB branché, commande 16/17 « Read Encoder Count ». Le manuel dit « read status information » sans les nommer | 🔴 **OUI** — c'est le seul point qui peut faire tomber l'architecture C, la plus prudente des trois |
| 11 | **Source de la batterie logique séparée** | le datasheet l'exige sous forte charge (effondrement de tension = redémarrage logique en pleine manœuvre) ; le rail 12 V Mean Well existe-t-il assez près ? | 🔴 **OUI** |

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
