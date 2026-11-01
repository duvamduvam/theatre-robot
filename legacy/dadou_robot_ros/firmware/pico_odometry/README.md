# Firmware Pico — odométrie des roues

Compte les 4 capteurs inductifs (2 par roue, en quadrature) et rapporte au Pi
par une trame texte à 50 Hz. Étude complète : [`../../docs/etude-odometrie.md`](../../docs/etude-odometrie.md).

> ⚠️ **Le Pico ne commande RIEN.** Il lit, il compte, il rapporte. Il n'est pas
> sur le chemin de commande des roues. Si ce lien meurt, on perd l'odométrie —
> donc la navigation autonome s'arrête — mais aucun rempart de sécurité ne
> tombe : le deadman 400 ms de `wheels_node` reste intact. Une panne
> d'odométrie ne peut produire qu'un **arrêt**, jamais un emballement.
> Rien dans ce firmware ne doit jamais piloter une sortie.

## Les fichiers, et pourquoi ils sont séparés

| Fichier | Où il tourne | Testé ? |
|---|---|---|
| `odom_protocol.py` | **Pico + nœud ROS + tests hôte** — décodage quadrature, CRC, trames | ✅ 35 tests (`robot/tests/unit/test_odom_protocol.py`) |
| `main.py` | Pico seul — PIO, broches, boucle, chien de garde | ❌ non importable sur l'hôte (`machine`, `rp2`) |

Cette coupure est **la** décision de conception du firmware. Tout ce qui peut
être *faux* (le sens de rotation, le bouclage des compteurs, le CRC) vit dans
le fichier partagé, exercé par les tests du dépôt et par le nœud ROS. `main.py`
ne garde que ce qu'aucun test hôte ne peut atteindre : regarder des broches.

Écrire le décodeur en C aurait imposé de l'écrire **deux fois** — une fois pour
le Pico, une fois en Python pour le nœud ROS et les tests. Deux implémentations
d'une convention de signe, c'est la façon canonique d'inverser une roue sans
s'en apercevoir pendant six mois.

## Flasher

```bash
# 1. MicroPython sur le Pico, UNE fois : maintenir BOOTSEL en branchant l'USB,
#    le Pico monte comme clé USB (RPI-RP2), y déposer le .uf2 officiel.
#    https://micropython.org/download/RPI_PICO/

# 2. Déposer les deux fichiers (mpremote : pip install mpremote)
mpremote cp odom_protocol.py :odom_protocol.py
mpremote cp main.py :main.py
mpremote reset

# 3. Lire les trames
mpremote repl            # Ctrl-C interrompt main.py pour reprendre la main
#   ou, une fois la règle udev posée :
cat /dev/didier-odom
```

`main.py` démarre tout seul à la mise sous tension. **Ctrl-C dans le REPL
l'interrompt** — pratique à l'établi, sans effet en exploitation (personne
n'écrit sur le port).

## Le protocole

```
ODO <seq> <ticks_gauche> <ticks_droite> <crc>\n     50 Hz
STAT illegal_g=<n> illegal_d=<n>\n                  toutes les 5 s
```

- **`ticks` sont CUMULÉS et signés (32 bits, ils bouclent).** Pas des deltas :
  une trame perdue ne perd alors aucune distance, la suivante rattrape toute
  seule. Le nœud ROS **doit** utiliser `delta_ticks()` et jamais une
  soustraction directe — au bouclage, celle-ci produirait un saut de 4
  milliards de ticks, soit un téléport dans la carte de nav2.
- **`seq` boucle sur 16 bits** et sert à détecter les trames perdues
  (`seq_perdues()`), donc un lien qui se dégrade.
- **`crc`** : CRC-8 (polynôme 0x07) sur le texte qui précède, 2 chiffres hexa.
  Toute trame malformée ou au mauvais CRC est **refusée** (`parse_frame()`
  renvoie `None`) — jamais une valeur approchée. Une trame à moitié lue, en
  odométrie, c'est un robot qui croit avoir avancé.
- Le nœud ROS doit **ignorer les lignes qu'il ne connaît pas** : c'est ce qui
  permet d'ajouter des lignes de diagnostic sans casser le lien.

### ⚠️ `illegal` est le témoin de mensonge

Il compte les transitions **physiquement impossibles** (les deux bits qui
basculent d'un coup), c'est-à-dire les fronts perdus. C'est le seul symptôme
observable d'une odométrie qui commence à dériver : entrefer trop grand, câble
parasité, disque qui bat, capteur qui décroche. **Il doit rester à zéro.** S'il
grimpe, l'odométrie ment déjà — et rien d'autre ne le dira.

## Variante RP2040-Zero (envisagée par David le 30/08) — compatible, à UNE ligne près

La carte cible peut être une **Waveshare RP2040-Zero** au lieu d'un Pico. C'est
compatible et même préférable, mais **un point casse en silence** :

⚠️ **`GP_LED = 25` est la LED du Pico. La Zero n'a pas de LED sur GP25** (elle
porte une WS2812 RGB sur GP16). `Pin(25, Pin.OUT)` **ne lèvera aucune erreur** —
la broche existe sur la puce, elle ne va nulle part — et le témoin de vie
mourrait sans un message. Remède retenu : **une LED ordinaire sur un GPIO libre**
de la carte (elle prévoit déjà une LED de diagnostic par canal, étude §8 étape 4),
plutôt qu'un pilote NeoPixel importé juste pour faire clignoter un voyant.

Ce qui ne change PAS, et c'est l'essentiel :

- **GP2-GP5 restent valables** et sont sur les pastilles latérales de la Zero.
  Les paires A/B **doivent rester contiguës** (le PIO lit 2 broches à partir
  d'une base) — c'est le cas.
- **Même RP2040 ⇒ numéro de série unique préservé**, donc la règle udev
  `/dev/didier-odom` tient. C'était LA raison unique du rejet de l'Arduino Nano
  (clones CH340 sans numéro de série) — voir étude §6.
- **Budget GPIO confortable** : 4 (odométrie) + 1 (témoin) + 4 (LED diagnostic)
  + 4 (réserve « commande » actée le 30/08) = **13 sur ~20**.

Bénéfice non recherché : la Zero est en **USB-C**, alors que l'étude §6 désigne
le connecteur **micro-USB** comme « le seul vrai risque du montage ». ⚠️ Le
**bridage du câble à moins de 5 cm de la prise reste obligatoire** : la carte est
petite et légère, la traction s'y transmet d'autant mieux.

⚠️ **À confronter à la fiche Waveshare avant de graver** (le brochage ci-dessus
vient de la mémoire, pas d'une fiche relue) : écartement des deux rangées si l'on
veut garder le **support tulipe** (étude §8 étape 4 : « un Pico grillé se change
en dix secondes, sans fer à souder »), et le fait que les pastilles du bas sont
**castellées uniquement**, donc non socketables — sans effet ici, GP2-GP5 étant
sur les côtés. Règle du projet : une cote d'environnement vaut une cote de pièce.

## Brochage (définitif — identique au schéma KiCad `wheel-odometry`)

| Pico | Signal | Roue |
|---|---|---|
| GP2 | `ODO_LA` | gauche, capteur A |
| GP3 | `ODO_LB` | gauche, capteur B |
| GP4 | `ODO_RA` | droite, capteur A |
| GP5 | `ODO_RB` | droite, capteur B |

Le niveau haut est fabriqué par les **rappels de 10 kΩ vers le 3,3 V** de la
carte (le capteur NPN ne sait que tirer vers la masse). `RAPPEL_INTERNE = True`
dans `main.py` active le rappel interne (~50 kΩ) pour un essai d'établi **sans
la carte** : suffisant pour voir bouger un signal, pas pour tenir un câble d'un
mètre le long d'un moteur à balais.

## ⚠️ Le sens de comptage n'est pas décidé, il se MESURE

`INVERSER_GAUCHE` / `INVERSER_DROITE` dans `main.py` sont des **hypothèses**
tant que le protocole caméra n'a pas eu lieu. Le sens dépend du câblage (quel
capteur est A) et du montage de chaque roue.

Protocole, roues **hors sol** : pousser une roue à la main dans le sens de la
marche avant, lire les trames. Le compteur de cette roue doit **monter**. S'il
descend, basculer le drapeau correspondant. À faire pour chaque roue
séparément — les deux côtés ne sont pas forcément montés en miroir (cote C3 de
la fiche de mesures, non vérifiée).

Se tromper ici ne casse rien et ne se voit pas : le robot croira reculer en
avançant, et nav2 construira une carte à l'envers, proprement.

## Ce qui reste à faire

- [ ] **Nœud ROS 2** côté Pi : lit le port, `parse_frame()`, publie `/odom` +
      la TF `odom` → `base_link`. Il importe `odom_protocol.py` — ne pas le
      recopier.
- [ ] **Règle udev** `/dev/didier-odom` sur le numéro de série du Pico (il en
      a un, dérivé de l'ID de sa flash — c'est ce qui l'a fait préférer à un
      Nano à puce CH340, qui n'en a pas et casserait la règle au moindre
      changement de prise).
- [ ] **Constantes physiques** : `ROUE_D` (hyp. 250 mm) et l'entraxe des roues
      (C2, jamais mesuré). Ce sont les **deux seules** valeurs qui convertissent
      des ticks en mètres et en radians. Fausses, l'odométrie est fausse —
      proprement, silencieusement.
- [ ] **Sens de comptage** (ci-dessus), au protocole caméra.
- [ ] Horodatage éventuel dans la trame : le Pi date à la réception, avec la
      gigue de l'USB (quelques ms). Sans effet sur la distance, mais ça bruite
      une **vitesse** dérivée. À trancher quand le nœud ROS existera — ça
      modifie le format gravé au §6 de l'étude.
