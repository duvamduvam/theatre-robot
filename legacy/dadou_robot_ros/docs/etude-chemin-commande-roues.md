# Étude — le chemin de COMMANDE des roues (PWM moteur)

*Ouverte le 2026-08-30 sur une question de David. Conclusion : **le Pico ne commandera pas
les roues** — non par dogme, mais parce que le bénéfice visé est déjà obtenu par la chaîne
de sécurité matérielle conçue le 14/07. Ne pas re-trancher sans lire le §5.*

Cette étude est le pendant de [`etude-odometrie.md`](etude-odometrie.md), qui traite du
chemin de **mesure**. Ici on ne parle que du chemin de **commande** : ce qui va du Pi au
Cytron SmartDrive40.

## 1. La question posée

> « Je branche les odomètres. Pour les moteurs de roues, j'ai cru comprendre que ce n'était
> pas idéal de brancher à la Raspberry ; actuellement c'est en I²C, pas de vrai timing.
> Quitte à rajouter une RP2040, ne vaudrait-il pas mieux tout brancher sur le même
> contrôleur ? »

Question juste, et elle mérite mieux qu'un renvoi à la règle « le Pico ne commande RIEN »
du §6 de l'étude odométrie. Cette règle a une raison ; encore faut-il vérifier qu'elle
tient face à l'argument du timing.

## 2. Le chemin de commande AUJOURD'HUI (constaté dans le code le 30/08)

```
   Pi 4 ──I²C── ISO1540 ──I²C── PCA9685 (0x40) ──PWM+DIR── Cytron SmartDrive40 ── moteurs
                (barrière        │
                 galvanique)     └── canaux 4/5/7/8/15 : tête, bras, yeux (SERVOS)
```

Trois constats, dont deux n'étaient consignés nulle part.

### 2.1 ⚠️ Roues et servos partagent la MÊME puce — donc la même fréquence

La démonstration tient en quatre points, tous vérifiables dans le dépôt :

| # | Constat | Preuve |
|---|---|---|
| 1 | Un PCA9685 a exactement **16 canaux (0-15)** | roues = 0,1,2,3 · servos = 4,5,7,8,**15** (`robot_config.py:99-107`) → une seule étendue |
| 2 | `PCA9685(i2c)` appelé **sans adresse** | `wheels.py:88` → défaut **0x40** |
| 3 | `ServoKit(channels=16)` appelé **sans adresse** | `servo.py:59` → défaut **0x40** |
| 4 | **Aucune** adresse explicite ailleurs dans le code | seule occurrence du dépôt : PCF8574 relais `0x21` (`relays.py:41`) |

Même bus + même adresse = **même puce physique**. Irréfutable depuis le code.

Conséquence que personne n'avait relevée : **la fréquence PWM des moteurs se joue à une
course au démarrage**. `wheels_node` la force à 60 Hz (`wheels.py:89`), le constructeur de
`ServoKit` la force à 50 Hz. Le dernier à s'initialiser gagne. Personne ne l'a décidée.

Et la course n'oppose pas deux processus mais **six** : le launch instancie **cinq
`servo_node` séparés** (tête, bras G/D, yeux G/D — `robot_app.launch.py` lignes 75/87/99/111/123)
plus `wheels_node`, tous clients de la même puce.

**Conséquence opérationnelle : BÉNIGNE — et une première rédaction disait le contraire.**

Cette section affirmait le 30/08 qu'un `servo_node` qui redémarre « change le comportement
des roues », et qu'il fallait « le soupçonner en premier devant une dérive des roues
inexpliquée ». ⚠️ **C'est FAUX, et c'était une fausse piste de diagnostic** — le genre
d'erreur qui coûte une soirée d'atelier à chasser un fantôme. Corrigé le 30/08 après lecture
du code de la lib (`venv/.../adafruit_pca9685.py`), qui tranche sur trois points :

| Ce qui se passe vraiment | Preuve |
|---|---|
| `reset()` n'écrit que `MODE1 = 0x00` — il **n'efface PAS** les registres de rapport cyclique | l. 157-159 |
| Le setter de fréquence **endort la puce ~5 ms** (`mode1_reg \| 0x10` → prescale → restore → `sleep(0.005)`) : micro-coupure du PWM moteur, puis reprise à la même consigne | l. 171-182 |
| **À rapport cyclique égal, la tension moyenne est identique à 50 ou 60 Hz** — la vitesse des roues ne change pas ; seule l'ondulation de courant bouge | électronique de base |

Donc : une micro-coupure de ~5 ms sur une machine de 50 kg est **imperceptible**, et la
vitesse ne dérive pas. La course existe, elle est réelle, mais son effet est négligeable.
Elle mérite d'être corrigée par **propreté** (personne n'a choisi cette fréquence), pas par
urgence. ⚠️ **Ne pas la re-promouvoir en incident** : c'est déjà arrivé une fois.

~~Reste un point de *qualité*, lui bien réel mais non mesuré : 50-60 Hz est une fréquence de
*servo* […] un **ronflement audible à 60 Hz**~~ — 🔴 **FAUX, corrigé le 2026-09-26** après
lecture du **manuel officiel du MDS40B** (Rev 1.0, déc. 2015), qui tranche en deux phrases :

> *« **PWM Input Mode** – The input is PWM signal. **The filter capacitor is connected and the
> input signal is low pass filtered to be an analog signal.** »* (§8.2, p. 17)
> *« MOSFETs are switched at **16 KHz** to ensure quiet operation and no annoying whining
> sound. »* (§1, p. 3)

**Le Cytron ne recopie pas le PWM d'entrée : il le FILTRE en tension, puis pilote ses MOSFET
à 16 kHz régénérés en interne.** Le moteur n'a donc jamais été haché à 60 Hz, et il n'y a
aucun ronflement de 60 Hz à aller chercher. Un argument avancé en faveur d'un changement de
driver (« il supprimerait le ronflement ») tombe avec cette correction — détail dans
[`etude-driver-roues-asservi.md`](etude-driver-roues-asservi.md) §9 bis.

⚠️ **MAIS la découverte ouvre un autre sujet, celui-là non réglé.** Puisque l'entrée est
**filtrée en tension**, la fréquence du PCA9685 ne détermine plus le hachage du moteur — elle
détermine la **qualité du filtrage**. Or on l'attaque à **60 Hz** (période 16,7 ms), et **le
manuel ne donne AUCUNE plage de fréquence d'entrée acceptée** : la donnée n'existe pas dans le
document. Un filtre passe-bas dimensionné pour du PWM de quelques kHz, attaqué à 60 Hz, laisse
passer une **ondulation résiduelle sur la tension de consigne** — donc une vitesse qui tremble,
surtout à faible rapport cyclique.

Ce serait une explication au *vestige révélateur* ci-dessous (`FREQUENCY = 500` déclaré et
jamais utilisé) : quelqu'un avait peut-être constaté le tremblement.

👉 **À observer au test scénique au sol** (chantier priorité 1) : chercher une vitesse qui
oscille à basse consigne, roues hors sol d'abord. Si c'est confirmé, la séparation 0x40/0x41
du §4 cesse d'être un simple confort et devient la condition pour monter la fréquence roues. ⚠️ Mais **ce n'est PAS un problème de gigue ou de « vrai
timing »** : la PCA9685 est un générateur PWM matériel (oscillateur 25 MHz, compteur 12 bits)
et la forme d'onde est propre quoi que fasse Linux ; l'I²C ne fait que porter les *changements
de consigne*, à 20 Hz, ce qui suffit très largement. Personne n'a jamais signalé ce ronflement
sur Didier : **à écouter une fois, roues hors sol**, avant d'en faire quoi que ce soit.

⚠️ **Et on ne peut pas monter la fréquence sans détruire les servos.** C'est un verrou dur,
pas un réglage — voir §4, il tombe tout seul.

*Vestige révélateur* : `wheels.py:34` déclare `FREQUENCY = 500`, qui n'est **utilisé nulle
part**. Quelqu'un avait vu le problème et n'est pas allé au bout. Ne pas supprimer cette
ligne sans lire ce paragraphe : c'est une trace, pas du code mort ordinaire.

### 2.2 DIR n'est pas un GPIO, c'est un canal PWM détourné

`set_direction()` (`wheels.py:207`) écrit `duty_cycle = 0` ou `65530` sur un canal PWM du
PCA9685. Ça fonctionne — mais 65530 n'est pas 65535 : la ligne DIR retombe brièvement à
chaque période. Le Cytron filtre vraisemblablement, ce n'est pas un incident constaté ; c'est
noté ici pour qu'on ne cherche pas ailleurs le jour où une inversion de sens sera signalée.

### 2.3 Aucun chien de garde — mais c'est DÉJÀ traité (§3)

Le deadman 400 ms vit dans `Wheels.check_stop()`, appelé par le timer de `wheels_node`. Si
**le nœud lui-même** meurt (kill, OOM, conteneur qui tombe), le PCA9685 **conserve sa
dernière consigne indéfiniment**. Le protocole caméra du 04/07 a validé la mort de la chaîne
*amont*, jamais celle du rempart lui-même — et il ne pouvait pas : c'est lui, le rempart.

Ce trou était déjà découvert le 14/07 et il a sa parade (§3). Il est rappelé ici parce que
c'est **le vrai grief** du chemin de commande — bien plus que le timing.

## 3. Ce qui est DÉJÀ conçu : la chaîne de sécurité matérielle

**Branche `chaine-securite`** (commit `30c164e`), schéma KiCad main-carrier révisé le 14/07.
Détail dans [`chantiers.md`](chantiers.md#chaîne-de-sécurité-matérielle-carte-main-carrier) :

- **watchdog 74HC123** (250 ms), réarmé par un battement GPIO26 émis *seulement après une
  écriture I²C réussie* → ET par diodes avec la boucle coup-de-poing → bascule **74HC74** à
  `/CLR` dominant → **`OE` du PCA9685 roues** ;
- **coup-de-poing catégorie 0** : relais 40 A, purement électromécanique ;
- **modèle exécutable de la carte** (`robot/tests/unit/safety_chain_model.py`) branché sur le
  **vrai** code `Wheels`, **11 tests** : mort du nœud, bus figé, `/CLR` dominant, et le piège
  du réarmement (sans remise à zéro des registres, ARM rejoue l'ancien PWM).

Ce dispositif agit **sous le logiciel et sous l'I²C** : il coupe même si le bus est figé,
ce qu'aucun firmware ne peut faire. C'est structurellement supérieur à un watchdog logiciel
dans un microcontrôleur.

**Verrou** : la bande sécurité du PCB est **placée mais pas routée** (122 chevelus,
volontaire). *C'est ce routage qui rend Didier sûr — pas un microcontrôleur de plus.*

### ⚠️ 3 bis. Et aujourd'hui, sur le robot réel : RIEN de tout ça n'existe

Précision de David (30/08), à ne surtout pas perdre entre les lignes : **le robot ne tourne
PAS sur le design KiCad main-carrier. Il tourne sur une carte stripboard DIY.** Le watchdog
74HC123, la bascule 74HC74, le `OE` piloté, le coup-de-poing 40 A : tout cela est **conçu,
testé en modèle, et physiquement inexistant.**

Conséquence à écrire noir sur blanc, parce que le reste de cette étude pourrait faussement
rassurer :

> **Sur le Didier d'aujourd'hui, si `wheels_node` meurt, rien n'arrête les roues.**
> Le deadman 400 ms est *dans* le processus qui meurt, `e_stop` n'a toujours aucune source,
> et il n'existe aucune coupure matérielle. Le seul arrêt disponible est la coupure
> générale d'alimentation, à la main.

C'est le vrai état de la sécurité roues, et il est **sans rapport avec la fréquence PWM ou
avec l'endroit où l'on branche un RP2040**. Toute discussion sur le chemin de commande qui
ne commence pas par ce constat se trompe de sujet.

⚠️ **Priorité qui en découle** : router la bande sécurité et fabriquer la carte est le
**seul** travail qui change quelque chose à la sécurité de Didier. En attendant, la règle
d'exploitation reste celle du projet : roues hors sol pour tout essai, et **quelqu'un à
portée de l'interrupteur général** dès que les roues sont au sol (dont le test scénique,
chantier 1).

## 4. Le bénéfice non répertorié de la séparation 0x40 / 0x41

La révision du 14/07 prévoit **deux PCA9685 séparés : roues en 0x40, servos en 0x41**. Le
motif écrit est « pour que couper les roues ne fige plus le visage ».

**Elle règle aussi, gratuitement, le problème de fréquence du §2.1** : chaque puce retrouve
sa fréquence propre, et les roues peuvent monter sans que les servos en souffrent.

Ce bénéfice n'était écrit nulle part, et personne n'y penserait après coup. À faire au
moment du câblage des deux puces :

1. donner une adresse explicite dans le code (aujourd'hui les deux sont implicites) ;
2. régler la fréquence roues **délibérément**, après avoir lu la fiche du SmartDrive40 ;
3. le faire passer par le **protocole caméra** — c'est le chemin roues.

## 5. DÉCIDÉ — le Pico ne commandera pas les roues

### Pourquoi le GPIO du Pi est EXCLU (question de David, et il a raison)

`docs/hardware/overview.md:653` : l'I²C du Pi est isolé par un **ISO1540**, *« to protect the
main board »*. Sortir du PWM sur les deux canaux matériels du Pi 4 (GPIO12/13) **percerait
cette barrière galvanique** : un défaut côté Cytron remonterait par un fil logique nu
jusqu'au SoC. La commodité ne vaut pas le Pi. **Piste fermée.**

### Pourquoi le Pico non plus

Une fois la chaîne de sécurité en place, le bilan est sans appel :

| Gain visé | Couvert par |
|---|---|
| Vrai timing PWM | ✅ séparation 0x40 / 0x41 (§4) |
| Arrêt si le logiciel meurt | ✅ 74HC123 + 74HC74 + `OE` (§3) — **mieux** qu'un firmware |
| Sortir du bus I²C partagé | ✅ l'`OE` coupe même bus figé |
| **Boucle de vitesse locale** | ❌ **seul gain restant** — et c'est l'étape 5 (nav2) |

Mettre la commande sur le Pico **dupliquerait** une chaîne déjà conçue, modélisée et testée,
en remplaçant de l'électromécanique par du logiciel. Mauvais échange. S'y ajoutent deux
coûts : le lien USB deviendrait le chemin de commande (or le §6 de l'étude odométrie
identifie le connecteur micro-USB comme *le* point faible du montage), et le Pico
deviendrait un organe de sécurité à part entière — donc protocole caméra complet sur du
firmware neuf, au moment précis où la priorité 1 est le premier test au sol.

### Ce qu'on réserve quand même — et ce qu'on ne câble PAS

Sur la carte `wheel-odometry` (PCB pas encore gravé — étape 4, après validation 1-3) :

- ✅ **réserver 4 broches GPIO** sur le Pico (2 PWM + 2 DIR) et les **documenter dans le
  `DESIGN.md`** de la carte. Coût nul aujourd'hui, respin évité si l'étape 5 les réclame ;
- ❌ **ne router aucun étage de sortie** (opto, buffer, bornier). Raison : si le Pico
  commandait un jour, sa sortie devrait passer par la **même** chaîne de sécurité
  (`OE` / `/CLR`) — sinon on crée un second chemin de commande qui **contourne le
  watchdog**. Cette intégration n'est pas conçue. Un demi-étage déjà câblé sur la carte,
  c'est l'invitation à le brancher « vite fait » hors chaîne de sécurité.

**Réouvrir cette étude si, et seulement si**, l'étape 5 (`ros2_control` + nav2) montre qu'un
asservissement de vitesse à 20 Hz depuis le Pi ne tient pas — auquel cas la boucle locale
dans le Pico devient le sujet, avec l'intégration à la chaîne de sécurité comme préalable.

## 6. Ce qui reste à faire

| | Action | Où |
|---|---|---|
| 1 | **Router la bande sécurité** du main-carrier (122 chevelus) | `pcb/kicad/main-carrier` |
| 2 | Confirmer la fréquence PWM max du SmartDrive40 sur sa fiche | — |
| 3 | Adresses I²C explicites dans le code (0x40 roues / 0x41 servos) | `wheels.py`, `servo.py` |
| 4 | Régler la fréquence roues délibérément → **protocole caméra** | chemin roues |
| 5 | Réserver + documenter les 4 GPIO du Pico | `pcb/kicad/wheel-odometry/DESIGN.md` |
| 6 | **Le SmartDrive40 a-t-il une entrée *brake* / *enable* exploitable ?** | fiche constructeur |

Rien de tout cela ne précède le **test scénique au sol** (priorité 1), sauf l'item 5 qui est
gratuit et l'item 1 qui vit sur son propre chantier.

⚠️ **L'item 6 n'est pas une curiosité** : si le driver expose une entrée de freinage câblable,
elle offrirait à la chaîne de sécurité un **second point de coupure**, en aval du PCA9685 —
donc indépendant de l'`OE`. Deux coupures en série sur des principes différents valent bien
mieux qu'une seule, et cela pourrait alléger le relais 40 A. À instruire **avec** le chantier
main-carrier, pas séparément.

## 7. Incohérence de doc relevée au passage

`chantiers.md` (section odométrie) annonce encore le lien Pico ↔ Pi en **UART (J6 :
5V/TX/RX/GND)**, alors que le §6 de `etude-odometrie.md` a été **renversé vers l'USB le
2026-08-20** (paire différentielle blindée, règle udev sur le numéro de série, bridage du
câble obligatoire). La carte KiCad a été dessinée avant ce renversement : vérifier quel lien
elle porte réellement avant de graver.
