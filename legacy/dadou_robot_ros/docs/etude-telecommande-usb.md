# Étude — petite télécommande USB à base de RP2040

*Ouverte le 2026-09-14, à partir de quatre photos d'atelier d'un module joystick.
Rien n'est fabriqué. Les décisions marquées **OUVERT** attendent David.*

Documents liés : [`chantiers.md`](chantiers.md) · [`etude-chemin-commande-roues.md`](etude-chemin-commande-roues.md) ·
[`etude-suivi-personne.md`](etude-suivi-personne.md) · [`hardware/inventaire-stock.md`](hardware/inventaire-stock.md)

---

## 1. Ce que c'est, et ce que ce n'est pas

**Le besoin, mot pour mot** : « j'aimerais faire une petite télécommande USB avec une
RP2040 ». Destination confirmée : **la télécommande Pi 4 existante ET la simulation**.

**Ce n'est pas** un remplacement de la télécommande de scène (`dadou_control_ros`, Pi 4
portable, 10 périphériques USB, GUI, liaison Wi-Fi). C'est un **petit boîtier filaire**,
qui se branche par un câble USB soit sur cette télécommande, soit sur le PC d'atelier.

**Pourquoi ce chantier peut avancer maintenant.** Depuis le 2026-09-12, le Pi 4 du robot a
fumé et **le robot est en pièces** : les chantiers 0 et 1 sont gelés. Celui-ci ne touche
**aucun matériel du robot** — il se développe et se vérifie entièrement au banc (PC +
simulation Gazebo). C'est du travail utile pendant le gel, et il prépare le test scénique
au sol (priorité 1) au lieu de l'attendre.

---

## 2. Le matériel constaté sur les photos

Photos : [`hardware/photos/2026-09-14-module-joystick/`](hardware/photos/2026-09-14-module-joystick/)
(**6 images**, copiées du Xiaomi le 14/09 : 4 du joystick à 22:11, **2 de l'OLED à 22:36**
— celles-ci dépouillées au §4.6. C'est le seul relevé dont on dispose : **rien n'a été mesuré
à l'établi**, aucune règle n'est apparue dans le cadre, et aucune dimension ci-dessous n'est
une cote.)

| Fait | Comment il est établi | Confiance |
|---|---|---|
| Module **`HW-504`** (famille « KY-023 ») | sérigraphie lue sur le flanc et au dos (`221117`, `221123`) | **H** |
| Brochage `GND · +5V · VRx · VRy · SW`, barrette 5 broches au pas 2,54 | sérigraphie lue en gros plan (`221113`) | **H** |
| 2 potentiomètres montés à 90° + poussoir sur l'appui du manche | forme, sans ambiguïté | **H** |
| **L'emplacement `R5` est VIDE** au dos | vu en gros plan (`221123`) | **H** |
| Valeur des potentiomètres (10 kΩ ?) | **non lue** — aucune sérigraphie visible | ⛔ |
| Second objet noir en bord de cadre (potentiomètre rotatif de panneau ?) | forme seule, hors sujet depuis §4.6 | **B** |

### 2.1 Deux pièges qui se paient cher, à traiter dès le premier câblage

**⚠️ Piège 1 — la broche `+5V` doit être alimentée en 3,3 V, jamais en 5 V.**
Le module n'est qu'un pont diviseur : le rail alimente le haut des potentiomètres, donc
`VRx`/`VRy` sortent au maximum la tension d'alimentation. En 5 V, ces sorties attaquent les
entrées analogiques du RP2040, dont le maximum absolu est 3,63 V — destruction de la carte,
éventuellement silencieuse et différée. En 3,3 V le module fonctionne exactement pareil, on
perd seulement de la dynamique qu'on n'utilisait pas. **Cette ligne est la seule erreur de ce
montage qui coûte une carte.**

**⚠️ Piège 2 — `SW` est flottant sur cet exemplaire.** `R5`, la résistance de tirage du
poussoir, n'est pas peuplée : sans tirage, la broche lit du bruit, et le bouton paraîtra
« parfois appuyé ». Remède gratuit : **pull-up interne du RP2040** (`Pull.UP`), bouton actif
à l'état bas. Aucune résistance à souder. À écrire dans le firmware **et** dans le test.

---

## 3. Ce que l'existant impose (relevé dans les dépôts, pas supposé)

La télécommande Pi 4 sait déjà lire dix périphériques USB. Leur convention n'est pas
négociable si on veut s'y brancher sans rien casser :

| Fait | Où c'est écrit |
|---|---|
| Les périphériques sont des **séries USB CDC**, identifiés par un chemin udev stable `SERIAL_ID` | `dadou_control_ros/controller/control_config.py:169-245` |
| Il existe **déjà** un device `JOYSTICK` sur un **Waveshare RP2040-Zero**, et un device `sliders` sur un second | idem, lignes 232-245 |
| Trame du `JOYSTICK` : **4 caractères**, deux entiers de 2 chiffres, mappés `10..99 → -100..+100` | `controller/input/serial_inputs.py:64` (`send_gamepad`) |
| Un chemin **totalement distinct** existe pour les manettes du commerce : `USBGamepad` (pygame) | `controller/input/usb_gamepad.py` |
| Côté robot, `twist_mux` arbitre `cmd_vel_remote` (100) > `cmd_vel_web` (50) > `cmd_vel_anim` (10), avec un verrou `e_stop` latché | `conf/ros2_dependencies/robot_drive` |
| Le repo héberge déjà du firmware RP2040, avec une convention de découpage explicite | `firmware/pico_odometry/README.md` |

**Deux observations qui orientent la conception.**

1. **Le protocole existant est trop pauvre pour ce boîtier.** 4 caractères, ~90 pas de
   résolution par axe, **aucun bouton, aucune somme de contrôle, aucun compteur de séquence**.
   On ne peut pas y faire entrer un homme-mort et quatre boutons. Il faudra un nouveau type de
   périphérique — voir §4.5.
2. **Incohérence relevée au passage, non corrigée ici** : la config déclare `msg_size: 6`
   pour le `JOYSTICK` alors que `send_gamepad` exige `len(msg) == 4` et journalise une erreur
   sinon. Ça marche sans doute parce que le séparateur est retiré en amont, mais les deux
   chiffres se contredisent. **À instruire dans `dadou_control_ros`, pas ici.**

---

## 4. Décisions

### 4.1 Carte : **Seeed XIAO RP2040** — DÉCIDÉ (révisable au §7)

Faits sourcés le 2026-09-14 sur les wikis officiels (voir §8 pour les réserves) :

| | XIAO RP2040 | Waveshare RP2040-One | RP2040-Zero |
|---|---|---|---|
| USB | **Type-C** | **USB-A mâle intégré** (façon clé USB) | Type-C |
| Broches exposées | **11** (D0-D10) | 20 en bord de carte | 20 en bord de carte |
| ADC utilisateur | **4** (A0-A3 = GP26-29) | 4 (broches non précisées par le wiki) | 4 |
| Dimensions | **21 × 17,8 mm** | non publiées en texte | non publiées en texte |
| En stock ? | **oui** (+ 2 cartes Seeed non identifiées) | oui, 1 | **non** |

**Pourquoi le XIAO.** (a) L'USB-C accepte un câble détachable : un objet tenu en main tire
sur son câble, et le connecteur USB-A mâle du RP2040-One obligerait à faire sortir la carte
elle-même du boîtier, en porte-à-faux — le wiki Waveshare admet d'ailleurs que « la fiche USB
tient lâche » et livre un autocollant pour la caler. Mauvais pour un objet de scène.
(b) 4 ADC là où le Raspberry Pi Pico n'en offre que 3 (sur Pico, GP29 mesure VSYS) : il reste
**deux voies analogiques libres** après le joystick. (c) 21 × 17,8 mm. (d) Il est en stock,
donc on soude ce soir.

**La contrainte à accepter** : **11 broches, pas une de plus.** Le décompte ci-dessous
montre que ça passe, mais sans marge :

| Fonction | Broche | Reste |
|---|---|---|
| `VRx` | A0 / GP26 | |
| `VRy` | A1 / GP27 | |
| Homme-mort | D6 / GP0 | |
| 4 boutons | D7, D8, D9, D10 | |
| OLED I²C (SDA/SCL) | D4 / GP6, D5 / GP7 | |
| **Libres** | **A2, A3** (GP28, GP29) | 2 analogiques |

Le `SW` du joystick **n'a plus de broche numérique** : il faut le câbler sur A2 ou A3 (une
entrée analogique se lit très bien en numérique). C'est possible, mais ça consomme la
dernière réserve d'extension. **Si David veut le `SW` ET une extension future, c'est le
RP2040-One (20 broches) qu'il faut prendre**, en acceptant sa mécanique USB.

### 4.2 Une seule interface : la série USB CDC — DÉCIDÉ (révisé le 14/09 au soir)

> **Cette décision a été prise, puis renversée le soir même.** La première version proposait
> que le boîtier se présente AUSSI comme une manette de jeu USB (classe HID), pour que la
> simulation le lise avec `joy_node` sans écrire une ligne de code. **David a écarté le HID.**
> La trace est gardée ici parce que l'argument du renversement est bon et qu'il resservira.

**Pourquoi le HID est écarté.** Il n'aurait servi qu'**un seul** des deux usages (la conduite
en simulation), et **aucunement le menu**, qui est le cœur du besoin : le profil manette ne
transporte que des axes et des boutons, pas des lignes de texte ni des sélections. Il
apportait en revanche la seule inconnue capable de bloquer le chantier — aucun exemple
officiel ne montre HID et CDC-data cohabitant sur RP2040, et le nombre d'endpoints USB du
RP2040 n'est chiffré nulle part ; en cas de manque, CircuitPython part en mode sans échec.
**Une inconnue bloquante au service d'un demi-usage : mauvais marché.**

Donc : **tout passe par la série USB CDC**, dans les deux sens (§4.6). Pour la simulation, on
écrit un petit nœud qui lit cette série et publie `/cmd_vel_remote`. C'est du code en plus par
rapport à `joy_node`, mais il est modeste et il réutilise le décodeur déjà écrit et testé du
§4.5 — alors que le HID aurait imposé de maintenir deux représentations des mêmes entrées.

*Si le besoin « brancher le boîtier sur une machine qui n'a pas notre logiciel » apparaît un
jour, c'est ici qu'il faudra rouvrir le HID — et commencer par la vérification d'endpoints.*

### 4.3 Homme-mort : bouton séparé sous l'index — DÉCIDÉ (choix de David)

Règle non négociable du projet : « toute fonctionnalité mouvement DOIT traiter son cas
d'arrêt ». Le `SW` du module a été écarté : c'est un clic sec obtenu en **enfonçant le
manche**, pénible à tenir plusieurs minutes, et l'appui parasite l'axe qu'on tient.
Un poussoir dédié (le stock en contient 40-60 en 6×6 et 12×12) est tenu sans y penser.

**Ce que ça apporte au-delà du confort.** Aujourd'hui, l'arrêt d'urgence effectif du robot
est le deadman 400 ms **en aval** : il se déclenche sur *absence de trame*, c'est-à-dire sur
une **panne**. Aucun geste volontaire ne coupe les roues, et CLAUDE.md note que le verrou
`e_stop` de `twist_mux` est déclaré mais que **personne ne le publie**. Un bouton tenu, plus
un bouton d'arrêt franc (§4.4), donneraient enfin au projet ces deux sources manquantes.

**Ce que ça n'apporte pas** : ce boîtier reste **filaire**. Il ne remplace ni le
coup-de-poing sans fil du chantier web (W1), ni la coupure générale. Et il ne répare pas le
danger actif des deux boutons du dos (« stop » = `shutdown`, donc emballement).

### 4.4 Les 4 boutons = la navigation du menu — DÉCIDÉ (choix de David)

Intention de David, mot pour mot : « je préférerais un petit menu, comme ça je peux contrôler
**tous les éléments** via la télécommande ». Les 4 boutons sont donc les touches du menu
(haut, bas, valider, retour), et non 4 actions directes comme je le proposais.

**L'argument que j'avais opposé, et ce qu'il en reste.** Un menu fabrique des **modes** : le
même bouton ne fait plus la même chose selon l'écran affiché, et l'étude du robot suiveur du
14/09 vient d'identifier le mode implicite comme *le* mode dangereux du projet. Mais cet
argument vise le **pilotage**, pas le **catalogue** : « tous les éléments » (animations,
visages, lumières, bascules) ne tiendra jamais sur quatre boutons, et un menu est la seule
forme qui grandit sans redessiner l'objet. La réponse au risque de mode n'est donc pas de
refuser le menu, c'est la règle ci-dessous — plus le fait que **la conduite ne passe jamais
par lui** (§4.7).

> **Règle de sécurité NON négociable : le menu est inerte tant que l'homme-mort est tenu.**
> Naviguer un écran à deux mains pendant que 50 kg roulent, c'est l'accident. Homme-mort
> tenu ⇒ l'écran n'affiche que la conduite et les 4 touches ne produisent rien. Cette règle
> vit dans le module partagé, donc elle se teste sur l'hôte (§6).

Le `SW` du joystick reste **OUVERT** (§7) : il pourrait doubler « valider », mais il coûte la
dernière voie analogique libre du XIAO.

### 4.7 Ce qui ne passe JAMAIS par le menu ni par l'hôte — DÉCIDÉ

La conduite est **entièrement locale au RP2040** : lecture des axes, homme-mort, émission
50 Hz. Elle ne dépend ni de l'écran, ni de l'état du menu, ni de la santé de l'hôte.

C'est ce qui rend le §4.6 acceptable : si le logiciel hôte plante ou se fige, le menu gèle et
l'écran ment — mais le boîtier continue d'émettre la vérité des axes et de l'homme-mort, et
s'il ne l'émet plus, le deadman 400 ms en aval arrête le robot. **Une panne d'affichage ne
peut produire qu'un menu mort, jamais un mouvement.** C'est la même discipline que le
firmware d'odométrie, qui lit et rapporte mais ne commande rien.

### 4.5 Protocole série : un **nouveau** type de périphérique — DÉCIDÉ

On ne touche pas au device `JOYSTICK` existant ni à `send_gamepad` : une trame étendue
casserait le contrôle `len(msg) == 4`. On déclare un **nouveau type** (`remote_usb`) avec
son propre décodeur, à côté. L'existant continue de marcher sans être relu.

Trame proposée, une ligne ASCII terminée par `\n`, **émise inconditionnellement à 50 Hz**
(c'est cette répétition qui fait vivre le deadman aval — un boîtier silencieux au repos
serait indistinguable d'un boîtier débranché) :

```
R;<seq>;<x>;<y>;<flags>;<crc8>\n
    seq   : compteur 0..255, pour détecter les trames perdues
    x, y  : entiers signés -1000..+1000 (centré, zone morte appliquée à bord)
    flags : masque hexadécimal — bit0 homme-mort, bit1..4 boutons, bit5 SW
    crc8  : sur tout ce qui précède
```

**Pourquoi un CRC sur un câble USB, qui a déjà le sien ?** Parce que le CRC de l'USB protège
le transport, pas le décodage : une trame tronquée à la reconnexion, un buffer réassemblé de
travers, et `x` prend une valeur plausible. Sur un chemin qui commande des roues, une valeur
plausible et fausse est le pire cas. `firmware/pico_odometry` a déjà tranché dans ce sens.

**Découpage du code — on copie la convention `pico_odometry`, qui est bonne :**

| Fichier | Où il tourne | Testé ? |
|---|---|---|
| `firmware/remote_usb/remote_protocol.py` | RP2040 **+ nœud/décodeur hôte + tests** | ✅ à écrire |
| `firmware/remote_usb/code.py` | RP2040 seul (broches, ADC, boucle) | ❌ non importable sur l'hôte |
| `firmware/remote_usb/boot.py` | RP2040 seul (déclaration USB) | ❌ |

Tout ce qui peut être *faux* — le signe des axes, la zone morte, le masque de boutons, le
CRC — vit dans le fichier partagé, exercé par les tests du dépôt. C'est ce qui évite
d'écrire deux fois une convention de signe et d'inverser un axe sans s'en apercevoir.

### 4.6 L'OLED : le menu vit **côté hôte**, pas dans le firmware — DÉCIDÉ (révisé)

> **⏸ MIS DE CÔTÉ le 2026-11-01 (choix de David).** Pour l'instant le RP2040 ne fait que
> **boutons + transmission** ; le menu s'affiche sur l'écran du Pi 4 de la télécommande
> (chantier UI sans X11). Raison donnée : le code d'un Pico et celui d'un Pi sont trop
> différents pour partager un afficheur. Le raisonnement ci-dessous reste valable si l'OLED
> revient un jour — ne pas le rouvrir sans demande.

> **Deuxième décision renversée le 14/09 au soir.** J'avais acté « OLED local seul » (l'écran
> n'affiche que ce que le boîtier sait de lui-même). Ça tenait tant que l'écran servait à
> afficher de l'état. **« Contrôler tous les éléments » le fait tomber** : le catalogue des
> animations, visages et lumières vit côté robot, pas dans le boîtier.

Deux façons de faire un menu, et elles ne se valent pas :

| | Menu **dans le firmware** | Menu **côté hôte** (retenu) |
|---|---|---|
| Où vit la liste | figée dans le RP2040 | dans le logiciel qui connaît déjà les séquences |
| Ajouter une animation | reflasher le boîtier | rien à faire, elle apparaît |
| Ce que le firmware sait du métier | tout | **rien** |
| Flux descendant à écrire | non | oui (mais la série est bidirectionnelle par nature) |

**Retenu : le menu côté hôte.** Le RP2040 devient un **terminal générique** — il affiche les
lignes qu'on lui envoie, il remonte les appuis et le curseur. Il ne connaît aucun nom
d'animation, donc **son firmware ne change plus jamais** quand le spectacle change. Un
catalogue figé dans le firmware serait une copie de la vérité, et une copie périme : c'est
exactement l'erreur que l'inventaire de stock documente sur trois pages.

Le coût est faible et il était déjà payé : la liaison série est bidirectionnelle, et il
fallait de toute façon du code hôte pour interpréter les sélections. Ce qui s'ajoute, c'est
un protocole descendant simple (effacer, écrire ligne N, surligner la ligne du curseur).

**Réserve, et c'est le §4.7 qui la lève** : l'écran dépend maintenant de l'hôte. S'il plante,
le menu gèle. Acceptable uniquement parce que la conduite, elle, ne passe jamais par là.

**Matériel identifié le 14/09 au soir** (photos `oled-ou-carte-2236*`, réf. lues au dos) :
module OLED I²C 4 broches `GND · VCC · SCL · SDA`, avec un sélecteur d'adresse sérigraphié
`IIC ADRESS SELECT` marqué **`0x78` / `0x7A`** — soit **0x3C / 0x3D** en adressage 7 bits,
la forme qu'attendent les bibliothèques. ~~⚠️ La dalle paraît soulevée d'un côté~~ →
**vérifié par David le 14/09 : la nappe n'est pas décollée, c'était un reflet.**

⚠️ **Le contrôleur reste inconnu** (il est sous la dalle ; David ne sait pas non plus) :
`SSD1306` et `SH1106` sont indiscernables à l'œil. **Ce n'est pas un problème, à condition de
ne pas le traiter comme une panne** : le SH1106 a 132 colonnes pour 128 affichées, donc son
image sort **décalée de 2 pixels** et rognée sur un bord. Conduite à tenir : écrire le code
avec le pilote en **paramètre** (une constante en tête de fichier, pas une supposition
enfouie), essayer SSD1306 d'abord — c'est le plus répandu — et si l'image est décalée,
basculer. **Coût du doute : une ligne.** Coût de ne pas l'avoir écrit : une soirée à chercher
une panne d'affichage qui n'existe pas.

Le potentiomètre-limiteur de vitesse proposé le 14/09 a été **écarté par David** au profit
des boutons. Les voies A2/A3 restent libres : la décision est réversible sans redessiner.

### 4.8 Le menu — PROPOSÉ le 14/09, à valider par David

Demande de David, mot pour mot : « propose un menu simple, **qu'est-ce qui est en train d'être
actionné avec quelle valeur** ». Ce n'est pas seulement une liste de commandes : c'est un
**moniteur**. Chaque ligne doit dire trois choses — quel élément, **qui le commande en ce
moment**, et **à quelle valeur**.

**Contrainte d'affichage**, qui décide de tout le reste : 128 × 64 pixels en police 6×8 font
**21 colonnes sur 8 lignes**. Tout ce qui suit tient dans ce cadre, sans défilement horizontal.

#### Écran A — CONDUITE (affiché dès que l'homme-mort est tenu, et lui seul)

```
CONDUITE       LIEN ok
----------------------
  avance     + 42 %
  rotation   - 07 %
----------------------

  HOMME-MORT  TENU
```

Pas de menu, pas de curseur, rien à lire de complexe : on roule. C'est l'application directe
de la règle du §4.4 — l'écran bascule ici tout seul, et les 4 touches ne produisent rien.

#### Écran B — LISTE (homme-mort relâché) : *le* moniteur demandé

```
DIDIER            anim
----------------------
> cou      A    + 15°
  bras G   A      0°
  bras D   -    - 30°
  yeux     S     suit
  visage   A    parle
  lumieres -     60 %
```

La colonne du milieu est la réponse à « qu'est-ce qui est en train d'être actionné » :

| Marque | Qui tient cet actionneur en ce moment |
|---|---|
| `A` | une **animation** le pilote (séquence en cours) |
| `S` | le **suivi** (gaze) le pilote |
| `M` | **moi**, depuis ce menu |
| `-` | personne — valeur au repos |

**Pourquoi cette colonne vaut plus qu'elle n'en a l'air.** Le projet a un chantier
« arbitrage des actionneurs » (`animation_state` latché, péremption du deadman) dont la
vérification restante est *visuelle* : voir que le gaze ne tremble pas pendant une séquence.
Cet écran affiche l'arbitrage **en direct, dans la main**. Ce n'est plus seulement une
télécommande : c'est le premier afficheur de diagnostic embarqué du projet — et il coûte une
colonne de six caractères.

#### Écran C — ÉDITION (après « valider » sur une ligne)

```
cou                  M
----------------------

       + 15°
   [======    ]

 valider=ok  retour=x
```

Entrer ici **prend la main** sur l'élément : sa marque passe à `M` sur l'écran B, et le reste
du système sait qu'il est tenu manuellement. « retour » rend la main.

#### Les 4 touches, et rien d'autre à retenir

| Touche | Écran B (liste) | Écran C (édition) |
|---|---|---|
| haut / bas | déplace le curseur | change la valeur |
| valider | entre en édition, **ou déclenche** si la ligne est une action | confirme |
| retour | — | annule et rend la main |

Les lignes ne sont pas toutes des valeurs : `visage` et les animations sont des **choix dans
une liste**, `follow` est une **bascule**. Le firmware n'a pas à le savoir — c'est l'hôte qui
envoie le libellé et le type, conformément au §4.6.

#### Ce que le protocole descendant doit transporter (minimum)

Une ligne = `<marque> <libellé> <valeur>`. Donc, dans le sens hôte → boîtier : effacer,
écrire la ligne N, positionner le curseur, basculer d'écran. **Rien de plus** : pas de
graphisme, pas de police, pas de coordonnées. Un écran entier tient en 8 messages courts, et
à 20 Hz de rafraîchissement c'est indolore sur une liaison série.

> **OUVERT** : la liste des éléments ci-dessus est une **proposition** tirée de ce que la
> chaîne sait déjà commander (cou, bras, yeux, visage, lumières, animations, `follow`). C'est
> à David de dire lesquels il veut voir, et dans quel ordre — l'ordre d'une liste qu'on
> parcourt à l'aveugle en scène n'est pas un détail.

---

## 5. Ce que ce boîtier change — et ce qu'il ne change pas

**Il change** : un geste volontaire peut enfin arrêter les roues (§4.3) ; la simulation se
pilote au joystick au lieu du clavier ; le projet gagne des sources pour `e_stop`.

**Il ne change pas** : les roues au sol restent suspendues au test scénique (priorité 1) et
au protocole caméra ; `direction_sign` n'est toujours pas tranché en réel ; la chaîne de
sécurité matérielle (watchdog, `OE`, coup-de-poing) reste physiquement inexistante.

> ⚠️ **Le jour où ce boîtier commande des roues réelles, il entre dans le chemin roues** :
> validation en simulation d'abord, puis **protocole caméra** roues hors sol, plus revue par
> un modèle fort. Tant qu'on est en simulation et au banc, rien de tout ça ne s'applique —
> et c'est justement pourquoi les lots T0-T3 sont conçus pour rester de ce côté-là.

---

## 6. Lots

*Révisé le 14/09 au soir : l'ancien T0 (cohabitation HID + CDC) disparaît avec le HID (§4.2).
Le chantier n'a plus d'inconnue capable de le bloquer — il commence par du code testable.*

| Lot | Contenu | Où ça se vérifie | Verrou |
|---|---|---|---|
| **T1** | `remote_protocol.py` + ses tests hôte : CRC, zone morte, signes, masque de boutons, trame tronquée, **et la règle « menu inerte si homme-mort tenu »** | `.venv/bin/pytest` | — |
| **T2** | `code.py` : lecture ADC, pull-up du `SW`, 4 boutons, homme-mort, émission 50 Hz inconditionnelle | banc, joystick câblé à l'air | T1 |
| **T3** | OLED : trancher SSD1306/SH1106 au premier affichage, adresse 0x3C/0x3D, puis le **protocole descendant** (effacer / écrire ligne / curseur) | banc | T2 |
| **T4** | **Simulation** : nœud qui lit la série et publie `/cmd_vel_remote` ; conduite dans Gazebo, homme-mort compris | sim headless + console web | T1-T2 |
| **T5** | Intégration `dadou_control_ros` : type `remote_usb`, `SERIAL_ID`, décodeur, **et le menu qui expose les éléments réels** (animations, visages, lumières) | dépôt télécommande | T3-T4 |
| **T6** | Boîtier imprimé 3D (PETG), une fois que l'électronique marche à l'air | CR-10 | T2 |

L'ordre compte toujours, mais pour une autre raison : **T1 n'a besoin d'aucun matériel** (ni
carte, ni robot, ni simulation) et il contient tout ce qui peut être *faux*. C'est le lot à
faire en premier, et il est faisable ce soir.

---

## 7. Inconnues à lever (et par qui)

| # | Inconnue | Comment la lever | Bloque |
|---|---|---|---|
| ~~1~~ | ~~CircuitPython tient-il HID + CDC-data ?~~ | **sans objet** — le HID est écarté (§4.2) | — |
| ~~2~~ | ~~Référence de l'OLED~~ | **LEVÉE le 14/09** : module I²C 4 broches, adresse 0x78/0x7A ⇒ **0x3C/0x3D** (§4.6) | — |
| ~~3~~ | ~~4 actions directes ou menu ?~~ | **TRANCHÉ par David : menu** (§4.4) | — |
| 4 | Le contrôleur est-il un **SSD1306 ou un SH1106** ? (décalage de 2 px) | premier affichage, T3 | rien (se corrige en une ligne) |
| 5 | La dalle de l'OLED est-elle **décollée** ? (vu sur photo, à confirmer) | à la main, 10 s | T3 si elle l'est |
| 6 | Le `SW` du joystick est-il câblé ? Il coûte la dernière voie analogique libre (§4.1) | arbitrage de David | T2 |
| 7 | Valeur des potentiomètres du `HW-504` | ohmmètre, 1 min | rien (informatif) |
| 8 | Combien de XIAO exactement ? (l'inventaire dit 1 sûr + 2 cartes Seeed non identifiées) | ouvrir le tiroir | T2 |
| 9 | Dimensions du RP2040-One / Zero (jamais publiées en texte) | pied à coulisse, si on change de carte | §4.1 si repli |

---

## 8. Provenance des chiffres du §4.1

Relevé le **2026-09-14** sur les pages officielles (wiki Seeed, wiki Waveshare, docs
CircuitPython), avec les réserves suivantes, à ne pas effacer :

- Les **dimensions des cartes Waveshare** ne sont publiées qu'en image de plan coté, jamais
  en texte. Une valeur vue en synthèse de moteur de recherche a été **écartée** faute de page
  primaire. Si on passe au RP2040-One, **mesurer au pied à coulisse**.
- Le mapping GP26-29 → ADC0-3 du RP2040-Zero/One n'est confirmé que par des sources tierces ;
  le wiki officiel dit seulement « 4 × ADC 12 bits ».
- L'absence de conflit sur A3/GP29 du XIAO de base est établie **par contraste** avec le
  paragraphe du modèle *Plus* (où GP29 est multiplexé avec la mesure batterie), pas par une
  phrase affirmative. À confirmer à la première lecture analogique.
- Le nombre d'endpoints USB du RP2040 n'est chiffré **nulle part** dans la doc consultée.
  *Sans objet depuis l'abandon du HID (§4.2) — conservé parce que c'est précisément ce trou
  documentaire qui rendait l'option coûteuse, et il faudra le rouvrir si le HID revient.*

Conformément à la règle du projet, aucun de ces chiffres n'a été écrit de mémoire ; ceux qui
manquent sont déclarés manquants plutôt que comblés.
