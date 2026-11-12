# Mini-robot de démonstration ou banc témoin ? (étude du 2026-11-07)

**Question de David** : « Avec ce que j'ai déjà, est-ce que je pourrais faire un petit robot pas
cher, pour la démonstration et la simulation, en attendant que le gros robot soit à jour ? Sinon,
est-ce que je dois faire une carte avec quelques composants I²C et autres pour parfaire ma CI en
construction ? »

**Statut** : analyse, **rien d'acté**. À trancher par David.

**Sources lues** : `docs/hardware/inventaire-stock.md` (stock d'atelier,
quantités = minorants, référence citée seulement si lue), `etude-architecture-globale.md` §3.1
(nœuds et matériel) et §5.10 (CI), `docs/spec-L1-contrats-donnees.md` §Lot F (fumée) et §Outils
qualité, `hardware/overview.md` (chaîne roues).

---

> **Mise à jour du 07/11, même jour.** David pense avoir encore des Pi en stock, pas encore
> inventoriés. Le constat « aucun Pi libre » ci-dessous ne vaut que pour les Pi **relevés** (table
> « Raspberry Pi de l'atelier » de l'inventaire). Voir §7 : ce que l'inventaire des Pi change.

## 1. Réponse courte

- **Mini-robot roulant : non, pas maintenant.** Le stock permet la mécanique (moteurs TT, roues,
  plateaux, L298N), mais **aucun Raspberry Pi libre** pour y faire tourner le code de Didier. Avec
  un Pico ou un ESP32, ce serait un troisième logiciel à maintenir, qui ne teste rien de
  `theatre-robot`. Et il ne montre rien de ce qui fait Didier (visage, voix, regard).
- **« Une carte avec quelques composants I²C » : non plus, pas sous cette forme.** Un composant
  qu'aucun code de Didier n'utilise (horloge DS3231, IMU BNO055) ne teste rien. *Correction du
  07/11 : le PCF8574 est bien utilisé — il commande les relais en 0x21 (`robot/actions/relays.py`) ;
  il va donc sur le banc (§8).*
- **Ce qui vaut le coup : un banc témoin**, c'est-à-dire les vrais pilotes de Didier sur un vrai Pi,
  **sans aucun moteur branché**, avec un témoin qui MESURE ce qui sort. Il sert aux deux usages
  demandés : démonstration (le visage s'anime, la voix sort) et vérification automatique sur
  matériel réel, là où la sim et GitHub Actions sont aveugles. **Zéro achat** si on prend le Pi du
  robot pendant la refonte électrique (voir §4).

---

## 2. Ce que le stock permet réellement

| Besoin | En stock (inventaire du 03/09) | Verdict |
|---|---|---|
| Calculateur qui fait tourner ROS + le code de Didier | Pi 4 2 Go = **le Pi du robot** (sain, hors robot depuis le 04/11). Pi 4 4 Go et 3ᵉ Pi : **ne démarrent plus** (LED fixes, 04/11). Pi 5 = vision. Zero 2 W = gant | **Le seul Pi libre est celui du robot**, tant que le robot est en pièces |
| Microcontrôleurs | Pico ×2-3, RP2040-One, XIAO-RP2040, Nano ×5-7, Teensy 3.2 ×2, ESP32 LoRa | Abondant, mais ne fait pas tourner `theatre-robot` |
| Base roulante | Motoréducteurs TT ×3-5, roues ×2-4, plateaux ajourés ×2, L298N ×1-2, LM2596 ×5-10 | Suffisant pour un châssis 2 roues |
| Énergie embarquée | **un seul** support 18650 ; carte BMS non identifiée | Insuffisant : un L298N perd ~2 V, il faut au moins 2 cellules |
| Capteurs mobiles | HC-SR04 ×2 (référence probable, non lue), fourches optiques ×8-10 (encodeurs possibles), BNO055 neuve | Suffisant pour un robot éducatif |
| Driver de servos du robot | **PCA9685 de rechange** (référence lue) | ✅ pièce maîtresse du banc |
| Visage | Matrices WS2812B-64 8×8 ×3-5, SN74AHCT125N ×6-8 (le level shifter du robot) | ✅ un visage de banc complet |
| Servos de loisir | **Aucun vu dans le stock.** Ceux du robot sont sur la tête démontée | À emprunter au robot ou à acheter (prix à lire à la source) |
| Alimentation de banc | DIANQI D-30A neuves ×3-5 (5 V 4 A + 12 V 1 A) | ✅ alimente Pi + matrice à luminosité limitée |
| Prototypage | plaques à bandes, plaques à pastilles, breadboards, fils Dupont | ✅ aucune carte à faire fabriquer |

---

## 3. Le mini-robot roulant : pourquoi pas maintenant

**Ce qu'il apporterait.** Du mouvement réel sans danger : un robot d'un kilo ne blesse personne,
donc on pourrait tester un comportement autonome au sol sans le protocole caméra de Didier.

**Pourquoi ça ne tient pas aujourd'hui.**

1. **Pas de calculateur.** Le seul Pi libre est celui du robot. Sans Pi, il faut réécrire la
   logique sur microcontrôleur (micro-ROS ou firmware maison). On obtient alors une troisième cible
   (sim, Didier, mini-robot), à l'opposé de la décision du 01/11 : une génération de code, un pilote
   matériel interchangeable.
2. **Rien ne se transfère à Didier.** Moteurs TT sans encodeur fiable, masse et inerties sans
   rapport, driver L298N (PWM + sens) au lieu du SmartDrive : un réglage de suivi fait sur le
   mini-robot ne vaut rien sur Didier. La chaîne de sécurité roues (twist_mux, deadman, e_stop) y
   serait un portage, pas le vrai code.
3. **La démonstration est ailleurs.** Ce qui fait Didier, c'est le visage, la voix, le regard. Un
   châssis jaune à deux roues n'en montre rien. Pour le mouvement, la sim et la page scène le
   montrent déjà.
4. **Le temps de David est la ressource rare.** La refonte électrique, les cartes à corriger, le
   lot F et A1 attendent déjà. Un mini-robot ajoute du câblage, de l'énergie embarquée et une
   maintenance logicielle.

**Quand la question redeviendra juste.** À l'arrivée du lidar décidé le 02/11 (autonomie, A1).
Tester un décideur et un évitement d'obstacles en vrai, sans les verrous roues de Didier, a alors
une vraie valeur. Il faudra un Pi dédié et une batterie 2S au moins. À reposer à ce moment-là,
avec le lidar comme raison d'être, pas avant.

---

## 4. Le banc témoin : ce qu'il vérifie que rien d'autre ne vérifie

### 4.1 Les angles morts actuels

| Vérification | GitHub Actions (L2) | Fumée sim (lot F) | Banc témoin |
|---|---|---|---|
| Tests unitaires, lint, mypy | ✅ | — | — |
| Nœuds, topics, namespace, catalogue | — | ✅ | ✅ |
| Image ARM, `colcon build` ARM, chemins install-space | ❌ | ❌ (x86) | ✅ |
| Bus I²C réel, adresse PCA9685, droits `/dev/i2c-*` | ❌ | ❌ (pilote sim) | ✅ |
| **Deadman roues sur le vrai PWM** | ❌ | ❌ | ✅ **sans moteur branché** |
| Trame WS2812 réelle (visage) | ❌ | ❌ | ✅ (visuel, puis mesure en étape 2) |
| Sortie audio ALSA | ❌ | ❌ | ✅ |

Les trous de droite ne sont pas théoriques. La mémoire du projet en garde plusieurs : chemins ARM
« jamais exécutés » à chaque lot L1, bug REPO_ROOT en install-space découvert sur le Pi,
`FastNeoPixel` qui exige une pause de fin de trame, sentinelle `colcon build` oubliée qui laisse
l'ancien code tourner en silence.

### 4.2 Le test qui justifie le banc à lui seul : le deadman roues

Les roues sont commandées par les canaux 1-2 du PCA9685 (PWM + sens vers le SmartDrive). Sur le
banc, **aucun driver ni moteur n'est branché** : on publie un `cmd_vel`, on arrête de publier, et
on vérifie que le rapport cyclique retombe à zéro dans les 400 ms du deadman. Idem pendant une
animation, là où le deadman a déjà été troué, et après un `e_stop`.

C'est le vrai code, le vrai Pi, le vrai PCA9685, et un risque nul. Deux niveaux de mesure :

1. **Relecture des registres du PCA9685** par I²C : zéro câblage, prouve que le logiciel a écrit
   ce qu'il fallait.
2. **Un Pico témoin** sur les sorties PWM : il mesure le signal électrique réel, y compris
   la broche d'activation des sorties. Il rapporte en série USB au Pi.

Ce test ne remplace **pas** le protocole caméra roues hors sol, qui reste obligatoire avant tout
usage au sol. Il le prépare : on arrive au robot avec une chaîne déjà prouvée sur le vrai PWM.

### 4.3 Composition, tout depuis le stock

| Élément | Rôle sur le banc | Origine |
|---|---|---|
| Pi 4 2 Go | le Pi du robot, avec son image et son Ansible réels | robot, pendant la refonte |
| PCA9685 | servos + canaux roues, relus par I²C | rechange du stock |
| 1-2 servos | voir bouger un cou ou un œil en démonstration | empruntés à la tête démontée, sinon facultatifs |
| Matrice WS2812B-64 + 74AHCT125 | le visage, même câblage logique que le robot | stock |
| Pico | témoin des PWM (étape 2) | stock |
| DIANQI D-30A | 5 V pour le Pi et la matrice | stock, neuve |
| Plaque à bandes + Dupont | montage | stock |

**Exclus volontairement** : DS3231, BNO055, OLED, ultrasons (le PCF8574 des relais est inclus, §8). Aucun code de Didier ne s'en
sert, donc ils ne testeraient rien. On les ajoutera le jour où un package les utilisera, avec le
test qui va avec.

**Pas de PCB.** Le banc se monte sur plaque à bandes. La règle « une seule commande de cartes après
le cahier de câblage » reste intacte.

### 4.4 Où il entre dans la CI

Il ne va pas dans GitHub Actions : le cloud ne voit pas l'atelier. Il prolonge le point 5 du lot F,
le déploiement hors robot, qui exige déjà un Pi branché :

```
deploy-hors-robot.sh  →  Ansible + contrôles nœuds/mux/sha/catalogue   (prévu au lot F)
banc-temoin.sh        →  i2cdetect, deadman sur registres, trame visage, son   (nouveau)
```

Même facture que la fumée : un script, des valeurs attendues gravées dans le test, une page de
résultat, zéro token. Lancé quand le Pi est branché, comme le veut la consigne « Pi branchés dès
que nécessaire ».

### 4.5 Ce qu'il sert en démonstration

Le visage qui joue une séquence, la voix qui sort, un servo de cou qui suit, le tout en vrai, sur
une table. C'est plus proche de Didier qu'un châssis roulant. On le montre pendant que le torse est
ouvert.

---

## 5. Préalables et risques

1. **Le Pi du robot n'est prêté que pendant la refonte.** Au remontage, le banc perd son Pi. Piste
   gratuite : tenter la récupération du bootloader des deux Pi 4 qui ne démarrent plus. Mais le
   Pi 4 Go est mort au branchement sur la nappe du robot : ses GPIO sont suspects. Un banc qui donne
   de faux rouges est pire que pas de banc. Il ne servira de banc qu'après un test GPIO complet.
2. **Courant de la matrice.** 64 LED au blanc plein tirent environ 3,8 A (60 mA chacune, valeur
   usuelle des WS2812B). Ajoutées au Pi sur le même 5 V, elles dépassent les 4 A de la D-30A. Il
   faut brider la luminosité dans la configuration du banc, ou alimenter le Pi à part.
3. **Jamais de moteur sur le banc.** Ni driver SmartDrive, ni L298N. Le banc teste la commande, pas
   la puissance. C'est ce qui le rend sûr.
4. **Le banc ne valide pas la sécurité au sol.** Les verrous roues de
   `legacy/dadou_robot_ros/CLAUDE.md` restent entiers.

---

## 6. Découpage proposé, si David dit oui

| Lot | Contenu | Qui | Porte |
|---|---|---|---|
| **B0** | Câblage : Pi + PCA9685 + matrice + level shifter sur la D-30A | David, environ 1 h | `i2cdetect` voit 0x40, le visage s'allume |
| **B1** | `banc-temoin.sh` : déploiement réel, relecture des registres, deadman roues (repos, animation, e_stop), séquence visage, son | implémenteur **Opus** (chaîne roues) | une passe verte, et une mutation du deadman qui rougit |
| **B2** | Pico témoin : mesure électrique des PWM et de l'écart entre trames WS2812 | Sonnet, spec fermée | mesure concordante avec les registres |

Ordre conseillé : après le lot F, dont B1 réutilise la facture. B0 peut se faire n'importe quand,
il ne coûte que du temps d'atelier.

**Ce que ça supprime** : rien. Le mini-robot n'est pas rejeté, il est reporté à l'arrivée du lidar.

---

## 7. Si l'inventaire trouve des Pi en stock

> **07/11, soir** : David a retrouvé **5 Pi 4**, et pense avoir **3 Pi 3**. **Les 5 Pi 4 sont relevés
> le même soir : tous de 4 Go et sains**, dont un à fente SD cassée qui démarre sur USB (voir l'inventaire). Le banc aura donc un Pi 4 à lui, et le mini-robot aussi le jour du lidar.
> La récupération du bootloader des deux Pi 4 morts n'est plus urgente.

**Ce qui change.**

- **Le banc devient permanent.** Il ne rend plus de Pi au remontage du robot. Le risque n° 1 du
  §5 tombe, et le banc peut tourner après chaque fusion, robot remonté ou non.
- **Le mini-robot perd ses deux obstacles matériels.** David déclare aussi « plein de 18650 »
  (07/11, non inventoriées). Avec un Pi et des cellules, il ne manque plus que des supports et une
  protection : un seul support 18650 vu en stock, la carte BMS n'est pas identifiée.
- **Les obstacles de fond restent.** Rien ne se transfère à Didier, le mini-robot ne montre pas
  le visage, et le temps de David reste rare. Le verdict tient : **pas maintenant, à l'arrivée du
  lidar**. Mais il change de nature : ce jour-là, le mini-robot devient le porteur naturel du
  lidar pour tester A1 en vrai pendant que Didier est en refonte. Ce n'est plus « peut-être »,
  c'est le moment prévu pour le construire.

**Les 18650, avec précaution.** Cellules d'origine et d'état inconnus : tension à vide mesurée une
par une, jamais de cellule sous 2,5 V remise en service, cellules appairées en tension dans un même
pack, et une protection (BMS) obligatoire. Vérifier aussi qu'elles ne sont pas les rechanges du pack
de Didier avant de les prélever.

**Quel Pi pour quoi** (à confirmer par l'essai, pas par la fiche) :

| Modèle trouvé | Banc témoin | Mini-robot (plus tard) |
|---|---|---|
| Pi 4 ou Pi 5, 2 Go et plus | ✅ même famille que le robot, le meilleur choix | ✅ |
| Pi 3 (1 Go) | ⚠️ à essayer : l'image du robot n'a jamais tourné sur 1 Go | ⚠️ juste |
| Zero 2 W | ❌ 512 Mo, déjà jugé trop juste pour Docker (gant) | ❌ |

**Le relevé à faire pour chaque Pi**, à recopier dans la table « Raspberry Pi de l'atelier » de
l'inventaire :

1. Modèle et mémoire lus sur la carte (sérigraphie près du SoC ou étiquette mémoire).
2. Démarrage avec la carte SD **et** le chargeur qui font marcher un Pi connu. Noter les LED.
3. S'il démarre : `cat /proc/device-tree/model`, `free -h`, `cat /proc/cpuinfo | grep Serial`.
4. Pour un Pi destiné au banc : un test des GPIO avant tout usage. Un Pi aux GPIO douteuses donne
   de faux rouges.

---

## 8. Câblage du banc (B0) — relevé dans le code du robot le 07/11

**Schéma imprimable (A4 paysage, noir pur)** : [`banc-temoin-cablage.svg`](banc-temoin-cablage.svg),
régénéré par `atelier/outils/schema_banc_temoin.py` (une valeur qui change se corrige là).

**Règle n° 1, tirée de l'incident du 04/11 (deux Pi abîmés par la nappe)** : le Pi est alimenté
**uniquement par son propre chargeur USB-C**. **Aucun fil** entre les broches 5 V du Pi (2 et 4) et
l'alimentation du banc. Seule la **masse** est commune, par un seul fil.

**Valeurs du robot** (`legacy/dadou_robot_ros/robot/robot_config.py`, `actions/wheels.py`,
`actions/relays.py`, `dadou_utils_ros/utils/status.py`) :

| Organe | Où dans le robot |
|---|---|
| PCA9685 (servos ET roues) | I²C bus 1, adresse **0x40** (défaut) |
| Roues | PCA9685 canaux **1** (PWM gauche), **2** (PWM droite), **0** (sens gauche), **3** (sens droite) |
| Servos | cou **4**, bras gauche **5**, œil gauche **7**, œil droit **8**, bras droit **15** |
| Relais | PCF8574 en **0x21**, broches 0 à 3 (sortie voix, effet, klaxon, alim HF) |
| LED (corps + visage) | GPIO **18**, 1 000 LED, visage = LED 513 à 673, luminosité 0,05 |
| Boutons | GPIO **16** (arrêt), GPIO **20** (réarmement / extinction), entrée avec pull-up : bouton vers la masse |
| LED d'état | GPIO **12** |

**Connexions** :

| De | Vers | Remarque |
|---|---|---|
| Pi broches 1 / 3 / 5 / 6 (3,3 V, SDA, SCL, GND) | ISO1540 côté 1 (VCC1, SDA1, SCL1, GND1) | comme la carte Sécurité du robot |
| ISO1540 côté 2 (VCC2, SDA2, SCL2, GND2) | 5 V du banc ; SDA/SCL du PCA9685 et du PCF8574 ; masse | bus I²C des cartes en **5 V**, comme sur le robot |
| PCA9685 VCC, PCF8574 VCC | 5 V du banc | (et non plus 3,3 V du Pi) |
| Pi broche 6 (GND) | masse commune du banc | **le seul** lien d'alimentation avec le Pi ; masses communes des deux côtés de l'ISO1540, comme sur le robot |
| Pi broche 12 (GPIO 18) | 74AHCT125 broche 2 (1A) | |
| 74AHCT125 broche 3 (1Y) | résistance 330 Ω, puis DIN de la matrice | |
| 74AHCT125 broche 1 (1OE) et 7 | masse | sortie 1 toujours active |
| 74AHCT125 broche 14 | 5 V du banc | + condensateur 100 nF entre 14 et 7 |
| 74AHCT125 broches 5, 9, 12 | masse | entrées inutilisées |
| 74AHCT125 broches 4, 10, 13 | 5 V du banc | sorties inutilisées désactivées |
| DIANQI 5 V | PCA9685 V+ (bornier), matrice 5 V, 74AHCT125 | jamais vers le Pi |
| DIANQI GND | masse commune | |
| Matrice 5 V / GND | condensateur 470 à 1 000 µF en parallèle | kit BOJACK |
| PCF8574 A0 = 1, A1 = 0, A2 = 0 | cavaliers d'adresse | donne 0x21 ; vérifier que la puce est bien une 8574 (la 8575 est une autre bête) |
| Pi broche 36 (GPIO 16) | bouton poussoir vers la masse | arrêt |
| Pi broche 38 (GPIO 20) | bouton poussoir vers la masse | réarmement ; appui long = extinction du Pi du banc |
| Pi broche 32 (GPIO 12) | LED + 330 Ω vers la masse | LED d'état |
| PCA9685 canaux 0 à 3 | **rien**, ou 4 LED témoins + 330 Ω vers la masse | jamais de driver moteur ; les LED montrent le deadman à l'œil |
| PCA9685 canal 4 | un servo (facultatif) | emprunté à la tête ; alimenté par V+ |
| DIANQI 12 V | isolé | inutilisé |

**Montage (décidé par David le 11/11)** : sur **plaque à pastilles soudée**, plus propre qu'une
breadboard. Modules (PCA9685, PCF8574, ISO1540) sur **barrettes femelles**, 74AHCT125 sur **support
tulipe** : tout se remplace sans dessouder. Si le Pi arrive par une nappe 40 fils, **couper ou ne
pas câbler les broches 2 et 4** côté plaque (le connecteur les amène d'office).

**Isolateur I²C : oui, un ISO1540 (décidé le 11/11).** Pas pour protéger le Pi — le banc n'a ni
moteur ni 24 V, et sur le robot les deux côtés de l'ISO1540 partagent déjà la masse (étude
odométrie : « ce n'est pas une barrière galvanique ») — mais parce que **le robot fait passer son
I²C par un ISO1540, côté cartes en 5 V**. Un banc sans lui testerait un autre bus que celui du
robot. Bonus : il valide un ISO1540 avant de souder la carte Sécurité. Prendre un exemplaire
**neuf** (achat refonte) ; celui de l'ancienne carte du 04/11 est sur le chemin de la panne et
ne se monte qu'après contrôle au multimètre entre VCC1 et GND1, et entre VCC2 et GND2.

**Implantation sur plaque à pastilles 160 × 100 mm** : [`banc-temoin-implantation.svg`](banc-temoin-implantation.svg)
(vue de dessus, trous numérotés colonnes 0-62 × rangées 0-38 ; liste des fils :
`atelier/outils/implantation_banc_temoin.py --liste`). Elle suit la **carte Moteurs de la refonte**
(`pcb/kicad/carrier_design.py`) plutôt que le robot actuel : **deux supports de PCA9685**, 0x40 pour
les roues avec sa ligne **OE tirée au 5 V par R10 (10 kΩ)** et un cavalier **JP1** vers la masse
(posé = roues actives, retiré = PWM roues coupés, le comportement de sûreté de la refonte), 0x41
pour les servos (support vide tant que le code vise 0x40 pour tout). Le PCF8574 reste en 0x21
(code actuel ; la refonte prévoit 0x22). J1 se câble en fils Dupont un par un : aucune broche 5 V du
Pi ne peut arriver sur la plaque.

**Plaque à bandes 60 × 140 mm** (la seule du stock assez grande, 11/11 ; pas d'achat) :
[`banc-temoin-bandes.svg`](banc-temoin-bandes.svg), générée et **vérifiée** par
`atelier/outils/implantation_banc_temoin_bandes.py` (`--liste` : coupures, straps, composants ;
55 trous × 25 bandes, comptés par David ; la colonne 54 et les bandes 23-24 restent libres). Le script reconstruit les liaisons (bandes − coupures + straps) et refuse
d'écrire le dessin au moindre court-circuit ou réseau coupé (contrôlé par trois mutations).
Sur cette surface, **le PCA9685 0x41 (servos) et le PCF8574 (relais) quittent la plaque** : ils se
branchent en chaîne sur **J7** (bus I²C 5 V, JST 4 pts, 5 V · SDA · SCL · GND, ordre de J11 de la
carte Moteurs) par leurs barrettes traversantes, posés sur le socle. Restent sur la plaque : J1a/J1b
(JST 4 pts vers le Pi, câble JST → Dupont femelle), ISO1540, PCA9685 ROUES avec R10/JP1, témoins J4
(signal/masse alternés, résistances en ligne), **J5/J6 vers le MDD10A** (JST 3 pts « sens · GND · PWM »
par roue, pris avant les résistances des témoins), 74AHCT125, boutons, LED d'état, J2 (bornier),
J3 (matrice, JST 3 pts). La matrice tire son courant **par J2, jamais par les bandes**. Bus I²C
sur le cuivre (ISO1540 côté 2 et PCA ROUES alignés). Pas d'extension côté Pi : un module 3,3 V se
branche sur le Pi, et un INA226 (0x40 d'usine) n'irait jamais sur J7. Contours des modules
indicatifs : les poser à blanc avant de souder ; plaque comptée : 55 trous × 25 bandes.

**À savoir avant B1** :
- la configuration du robot écrit 1 000 LED et place le visage aux LED 513-673 : sur une matrice de
  64, sans réglage propre au banc, on voit les 64 premières LED du **corps**, pas le visage
  (suffisant pour « ça s'allume », pas pour la séquence visage) ;
- **constat** : `servo` (ServoKit, 50 Hz par défaut) et `wheels` (60 Hz) ouvrent le **même** PCA9685
  en 0x40 ; la fréquence est celle du dernier nœud démarré. Le banc le rendra visible (registre
  PRE_SCALE). À examiner, pas un défaut avéré ;
- le kit de condensateurs céramiques commandé le 05/10 fournit le 100 nF, s'il est arrivé.

---

## 9. Aller « jusqu'au bout » : caméra, roues en l'air, bras (proposé par David le 11/11, rien d'acté)

**Idée de David** : une caméra qui vérifie qu'il y a du mouvement dans les LED et les servos, et un
petit robot de table avec des roues **qui ne touchent pas le sol** et des bras comme Didier.

**Avis : oui, mais par étages, et seulement ce qui ressemble à Didier.** Le banc vaut parce qu'il
fait tourner la chaîne réelle ; chaque ajout doit prolonger cette chaîne, pas en créer une autre.

| Ajout | Ce qu'il prouve de plus | Condition pour qu'il vaille | Étage |
|---|---|---|---|
| Relecture des registres (B1) | le logiciel a écrit la bonne consigne | — | B1 |
| Pico témoin (B2) | le signal électrique sort vraiment | — | B2 |
| **Roues en l'air** | la chaîne complète jusqu'au moteur : sens de chaque roue, arrêt du deadman, coupure par OE (JP1) | **un petit driver** (décision de David le 11/11 : pas de gros driver pour des moteurs TT), **commandé en PWM + sens** comme le SmartDrive40, pour que le code des roues soit celui de Didier (PWM sur les canaux 1-2, sens sur 0-3). Un driver à deux entrées IN1/IN2 (type DRV8833, MX1508) exigerait un autre code : faux témoin, sauf petit inverseur pour fabriquer IN2 depuis le sens. **Moteurs sur une alimentation séparée** (une 2ᵉ DIANQI), pas sur le 5 V de la logique. **Choix du 11/11 : le Cytron `MDD10A` du stock** (2 voies, PWM + sens par voie : une carte pour les deux roues ; moteurs **5 à 30 V** en rév. 2.0, 10 A par voie, PWM jusqu'à 20 kHz, logique 3,3/5 V — fiches revendeurs lues le 11/11 ; le condensateur rapporté est sans doute une réparation : contrôler au multimètre l'absence de court-circuit sur l'entrée puissance avant la première mise sous tension). **Moteurs (11/11)** : **deux** micromoteurs **N20** à réducteur métallique, roue montée, logés dans une pièce imprimée et fixés au pistolet à colle (berceau ajusté + point de colle sur le réducteur, pas sur l'arrière du moteur : il reste démontable) ; essai de David sur un chargeur 9 V = rotation normale, donc très probablement la version **12 V** (le TT jaune ne tourne pas : hors service). **Alimentation des moteurs = un chargeur 12 V par jack rond** (embases 2,1 × 5,5 en stock), **directement** sur l'entrée puissance du MDD10A (5-30 V) : pas d'abaisseur. Polarité du chargeur vérifiée au multimètre avant de brancher (les drivers Cytron n'ont pas de protection contre l'inversion, et le condensateur rapporté du MDD10A en est peut-être la trace) ; une diode **1N5819** du stock en série sur le + protège contre l'inversion (1 A, assez pour deux N20). Toucher le moteur après une minute en 12 V : chaud = ce n'est pas un 12 V ; à défaut deux `MD13S`/`MD10C`. Les L298N sont écartés (entrées IN1/IN2) | B3 |
| Un ou deux servos sur 0x41 | la séquence fait bouger quelque chose de réel | servos à emprunter (aucun en stock) ; un servo de loisir ne remplace pas un ASME du bras, il teste la commande, pas la mécanique | B3 |
| **Caméra** | le résultat physique : la LED s'allume, le servo bouge, la roue tourne | **oui/non sur une zone fixe, exposition manuelle, éclairage maîtrisé** — leçons du 10/07 (l'auto-exposition trompe) et du visage (la caméra ne sait pas lire un motif) ; jamais une mesure fine | B4 |
| **Bras simples** (levier imprimé au bout de chaque servo) | la caméra voit bouger le bras : chaîne servo vérifiée de bout en bout, comme les roues | bras **imprimés**, pas une copie de la mécanique de Didier ; servos de loisir sur 0x41 : ils testent la commande, pas le comportement des ASME 12 V du vrai robot (et si un ASME vient sur le banc : son fil rouge est une SORTIE 5 V, ne jamais le relier au 5 V, incident du 03/11) | B3 |

**Correction du même jour, après réponse de David** : les bras ne sont pas « de la mécanique » ;
un levier au bout d'un servo donne à la caméra une indication de mouvement, comme les roues. La
caméra ne mesure ni position, ni vitesse : elle dit seulement « ça a bougé quand il fallait, et
pas quand il ne fallait pas » — c'est suffisant et c'est ce qu'on lui demande.

**Le « petit robot » = un socle élégant pour le banc, rien de plus (précision de David).** La
plaque, le Pi, la matrice (visage), deux bras et deux roues dans une coque qui ressemble à un
petit Didier, utile aussi pour les démonstrations. Les roues sont **surélevées par construction** :
le socle les tient au-dessus de la table, elles ne peuvent pas entraîner l'ensemble — c'est une
garantie mécanique, dans l'esprit des règles roues, et elle doit le rester. Bonus pour la caméra :
fixée à la coque, elle voit toujours les mêmes zones (bras, roues, visage) sous le même angle,
ce qui rend le test « ça bouge / ça ne bouge pas » fiable.

**Révisé par David le 12/11 (concept v1, `plans/banc-temoin/`, mini-Didier)** : il **peut rouler**
(deux N20 motrices + une roue folle à bille arrière), mais **au banc il est posé sur sa cale**, qui
porte le socle et laisse les roues 12 mm au-dessus du plateau. Plus de cou (tête fixe) ; bras sur
les **2 TowerPro SG90** en stock. Conséquence assumée : la garantie n'est plus « par construction »
mais **« tant qu'il est sur sa cale »** — la cale a des logements qui tiennent le socle, et le banc
se pose loin du bord de la table (un N20 qui s'emballe ne le fait pas sauter de la cale, mais un
robot posé à même la table, si). Le protocole caméra des roues se joue **sur la cale**.

**Le gain réel des roues en l'air** : répéter sur la table le protocole caméra des roues (sens par
roue, deadman, e_stop, OE) avant de le faire sur Didier, sans aucun danger. Le socle n'est pas le
mini-robot roulant reporté au lidar (§3) : il peut rouler (démonstrations), mais les essais se
font sur la cale. 
