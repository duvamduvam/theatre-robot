# Mini-robot de démonstration ou banc témoin ? (étude du 2026-11-07)

**Question de David** : « Avec ce que j'ai déjà, est-ce que je pourrais faire un petit robot pas
cher, pour la démonstration et la simulation, en attendant que le gros robot soit à jour ? Sinon,
est-ce que je dois faire une carte avec quelques composants I²C et autres pour parfaire ma CI en
construction ? »

**Statut** : analyse, **rien d'acté**. À trancher par David.

**Sources lues** : `legacy/dadou_robot_ros/docs/hardware/inventaire-stock.md` (stock d'atelier,
quantités = minorants, référence citée seulement si lue), `etude-architecture-globale.md` §3.1
(nœuds et matériel) et §5.10 (CI), `docs/spec-L1-contrats-donnees.md` §Lot F (fumée) et §Outils
qualité, `hardware/overview.md` (chaîne roues).

---

## 1. Réponse courte

- **Mini-robot roulant : non, pas maintenant.** Le stock permet la mécanique (moteurs TT, roues,
  plateaux, L298N), mais **aucun Raspberry Pi libre** pour y faire tourner le code de Didier. Avec
  un Pico ou un ESP32, ce serait un troisième logiciel à maintenir, qui ne teste rien de
  `theatre-robot`. Et il ne montre rien de ce qui fait Didier (visage, voix, regard).
- **« Une carte avec quelques composants I²C » : non plus, pas sous cette forme.** Un composant
  qu'aucun code de Didier n'utilise (horloge DS3231, IMU BNO055, expandeur PCF8574) ne teste rien.
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

**Exclus volontairement** : DS3231, BNO055, PCF8574, OLED, ultrasons. Aucun code de Didier ne s'en
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
