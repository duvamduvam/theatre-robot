# Étude — passer toutes les cartes de Didier sous 100 × 100 mm (2026-09-26)

Demande de David, à la lecture du chiffrage [`cout-cartes.md`](cout-cartes.md) :
*« tout passer en 10 × 10, la carte principale en deux parties, pour être
envisagée sur deux étages par exemple »*.

Pourquoi ça vaut une étude : sous 100 × 100 mm, un PCB 2 couches coûte **5 $ les
cinq** ; à 150 × 100 il coûte **41 $** (pages primaires PCBWay, lues le 26/09).
`main-carrier` fait 195 × 150. Le seuil n'est pas une nuance de tarif, c'est un
mur — et il est franchissable, à condition de savoir ce qu'on coupe.

> **Verdict en trois lignes.** `audio-relays` passe en 100 × 100 sans sacrifice
> (42 % d'occupation). `main-carrier` **ne tient pas sur deux cartes en gardant
> ses trois emplacements « futurs »** (M2, M6, M9) : soit **deux cartes** en
> renonçant au 2ᵉ PCA9685 et à la cascade PCF, soit **trois cartes** en gardant
> tout. Les deux variantes sont **fail-safe à la déconnexion** de la nappe
> inter-cartes, et la 2-cartes garde la chaîne de sécurité d'un seul tenant.

Tout ce qui suit est **mesuré dans les fichiers KiCad** (courtyards, nets,
placement) — pas dans la doc, qui est en retard sur la bande sécurité du 14/07.

---

## 1. Ce que le passage achète, et ce qu'il coûte

| | Aujourd'hui | Après passage |
|---|---|---|
| Cartes | 2 (195×150 + 150×100) | 3 ou 4, toutes ≤ 100×100 |
| PCB nus, 5 ex. de chaque | 41 $ + **non chiffré** (~80 $ par règle de trois) | **15 $** (3 cartes) ou **20 $** (4 cartes) |
| Emprise physique de la « principale » | 292,5 cm² d'un bloc | 200 cm² côte à côte, ou **100 cm² empilés** |

Ce que ça coûte :

- **du travail de placement et de routage** — mais il était dû de toute façon :
  `audio-relays` n'a **aucune** piste, et `main-carrier` a sa bande sécurité en
  chevelu. Ce qui est réellement jeté : la table `routes()` de `main-carrier`
  (~120 lignes, 259 segments). La table des nets (`INSTANCES`) et tout le
  schéma **ne bougent pas** ;
- **une nappe inter-cartes** (IDC 2×8 + nappe 16 fils : dans le stock,
  `t0363`/`t0420`) et des entretoises (200+ en stock, **filetage M2.5/M3 à
  mesurer**, `t0630`) — matériel à coût nul ;
- **des emplacements « futurs »** en variante 2 cartes — c'est la vraie décision,
  §3.4.

---

## 2. `audio-relays` → 100 × 100 : faisable, sans sacrifice

**Mesuré** : 53 empreintes, **41,8 cm² de courtyards** sur 150. Sur 100 cm²
→ **42 %** d'occupation, ce qui est la densité d'une carte traversante confortable.

Ce qui structure la carte aujourd'hui (`generate_pcb.py`) et se conserve :

- **deux plans de masse** (audio à l'ouest, puissance à l'est) pontés par un
  seul net-tie — l'étoile de masse. Sur 100 mm de large, la coupure passe de
  x≈69 à x≈45 : la zone audio garde 45 mm, ce qui suffit pour 2 relais signal
  (10,6 × 20,8 chacun), le transfo (17,7 × 12,6) et la colonne de 4 RCA ;
- **les 4 RCA sur le bord ouest** : 4 × 10,1 mm = 40 mm de bord ;
- **les 5 borniers du bord nord** : 4 × 13,2 + 23,3 = **76 mm**, pour un bord
  utile d'environ 84 mm (100 moins deux coins à trous M3). Ça passe, mais
  serré : déplacer **J9 (9 V pédales, en réserve, non câblé)** sur le bord est
  rend la rangée nord respirable ;
- **les 2 TO-220 avec radiateur** (7805/7809) restent au nord, radiateurs vers
  le bord, loin du transfo.

Ce qu'il faut vérifier au placement, et rien d'autre : la distance entre les
bobines des relais puissance (K3/K4, 17 × 23 mm chacun) et la zone audio ne
descend pas sous ce qu'elle est aujourd'hui (~40 mm). Si elle descend, on le
sait : c'est une carte dont l'objectif n° 1 est la ronflette.

**Verdict : oui, en une passe de placement.** Elle n'a pas de piste : c'est le
moment.

---

## 3. `main-carrier` : les chiffres, puis le partage

### 3.1 Pourquoi une seule carte 100 × 100 est exclue

La somme des courtyards fait 72,8 cm². Mais les modules enfichés (PCA9685
62,2 × 25,4, HW-171 47,9 × 15,6, ISO1540, INA226) **dépassent largement leur
support 1×6** : c'est leur *ombre* qui compte pour le placement — seuls des
composants plats passent dessous (8,5 mm de support). Ombres comprises :

**128,6 cm² d'encombrement réel** — sur une carte de 292,5 (44 %, ce qui
explique qu'elle ait été confortable : la décision du 05/07 était « pas de
miniaturisation »). Sur 100 cm², ce serait 129 %. Une carte, c'est non ; la
question est deux ou trois.

Deux postes pèsent lourd et méritent d'être nommés :

- **8 porte-fusibles Keystone 5×20 : 14,4 cm²** (26,3 × 6,9 chacun). Des
  porte-fusibles à lame automobile (mini-ATO) feraient ~1,3 cm² pièce — mais le
  stock compte 150 à 250 fusibles verre 5×20 (`c0639`). On garde le 5×20 et on
  paie la surface ;
- **16 borniers de bord : 27,6 cm²**. Incompressible, c'est la fonction de la
  carte.

### 3.2 Les blocs, et les nets qui les relient

Lus dans la netlist (43 nets) :

| Bloc | Composants | Nets internes |
|---|---|---|
| **P — puissance** | J20 (alim 6 pts), F1…F8, J25/J26/J27/J33/J36…J40, J32, chaîne V+ servos (JP1, J28, F2, J35, JP3, C2, J29, J30), C1, LED présence | +12V, 12V_BRAS, 12V_AUX, 12V_OUT, +24V, 24V_IN, 5V_RPI*, VSERVO*, 5V_LED* |
| **Pi — interface** | J1 (IDC 2×20), ISO1540 (M4/M5), J10 Qwiic, J12 SYS, U4 74AHCT125 | +3V3, SDA/SCL_PI, LED_DATA_33 ×2, SHUTDOWN/RESTART/STATUS |
| **S — sécurité** | U6 74HC123 (chien de garde), U7 74HC74 (verrou), Q1, R10…R21, D20…D23, C4…C6, SW1 ARM, J41 ARM déporté, J42 coup-de-poing, J43 relais 40 A | HEARTBEAT (de J1), WD_*, SAFE, ARM, RUN, RUN_SENSE et ESTOP_SENSE (vers J1), ESTOP_LOOP, GATE, **OE_WHEELS → M1** |
| **M — modules bus 5 V** | M1 PCA9685 0x40 (roues, **le seul câblé aujourd'hui**), M2 PCA9685 0x41 (*futur*), M6 PCF8574 0x22 (*futur*), M9 cascade (*futur*), M7/M8 INA226, J11 I2C 5 V | SDA/SCL_5V, VSERVO, OE_WHEELS |

Trois observations qui décident du découpage :

1. **`OE_WHEELS` est le net de sécurité** : Q1 (bloc S) → M1 (bloc M). Le couper
   par un connecteur est possible mais demande une règle (§3.5). Le garder
   d'un seul tenant est mieux.
2. **`HEARTBEAT`, `RUN_SENSE`, `ESTOP_SENSE` viennent de J1** : la sécurité
   veut vivre sur la carte du connecteur Pi.
3. **Le V+ servos (10 A, F2)** ne doit **jamais** traverser une nappe : il va
   déjà **par fil** de J29/J30 au bornier vert de chaque module. La broche V+
   du support 1×6 (M1.6) devient NC en cas de séparation — le module est
   alimenté par son bornier, comme le prévoit sa conception.

### 3.3 Variante A — deux cartes : « puissance » et « Pi + sécurité + modules »

| Carte | Contenu | Surface (ombres incluses) |
|---|---|---|
| **P** | bloc P + **M7/M8 INA226** (leurs shunts J34/J35 sont sur P : module et shunt sur la même carte, pas de fil entre étages) + header nappe | **56,5 cm²** |
| **L** | Pi + S + **M1** + **M6** + header nappe | **55,1 cm²** |
| L avec M2 + M6 + M9 | tout garder | **78,4 cm²** — irréaliste en traversant avec des pistes de puissance |

**56 % / 55 %** : dense mais tenable (aujourd'hui 44 %), d'autant que ~23 cm² des
ombres de modules accueillent des composants plats — les 12 résistances et
4 diodes de la bande sécurité (8 cm²) y vont naturellement.

Bord de la carte P : 178 mm de connecteurs enfichables (J20 33,5 ; 7 × 13,2 ;
2 × 18,2 ; KF128 ×2) pour ~340 mm de bord utile → **52 %**, ça passe.

**La nappe L → P (IDC 2×8, 16 fils)** :

| Fils | Net | Sens | Courant |
|---|---|---|---|
| 2 | +5V | P → L | logique des modules, ISO, 74xx : < 0,3 A |
| 3 | GND | — | |
| 2 | +12V | P → L | bobine du relais 40 A (J43) : ~0,2 A |
| 2 | LED_DATA_5V, LED2_DATA_5V | L → P | signal |
| 2 | SDA_5V, SCL_5V | L → P | I²C vers M8 (INA servos) |
| 3 | SDA_PI, SCL_PI, +3V3 | L → P | I²C vers M7 (INA Pi) |
| 2 | libres | | |

**Ce que la variante sacrifie** : le 2ᵉ emplacement PCA9685 (M2, 0x41) et le
support cascade PCF (M9). Ce n'est pas rien, et ce n'est pas à moi de le
trancher : « 2 emplacements PCA9685 » est une **décision de David du 05/07**.
Éléments pour la reprendre : le 2ᵉ PCA9685 physique « n'a jamais été réellement
câblé » (relevé du 04/07) ; 10 canaux sur 16 sont utilisés sur 0x40 ; et **J11
(I²C 5 V déporté) existe précisément pour chaîner un module par câble** — un
futur PCA9685 se branche là, sur sa propre platine, sans toucher à la carte.

### 3.4 Variante B — trois cartes : « puissance », « modules », « Pi + sécurité »

| Carte | Contenu | Surface |
|---|---|---|
| **P** | bloc P seul | **46,1 cm²** |
| **M** | M1, M2, M6, M9, M7, M8, J11 | **62,2 cm²** (dont 55 d'ombres : le dessous est libre pour les pistes) |
| **L** | Pi + S | **31,4 cm²** |

Garde **tout**. Coûte une carte de plus (5 $ les 5), deux nappes au lieu d'une,
trois cartes à fixer — et surtout **`OE_WHEELS` traverse la nappe M ↔ L**, ce
qui impose la règle du §3.5. Le V+ va toujours par fil.

### 3.5 Sécurité : la nappe doit être « à manque »

La règle du projet : toute fonctionnalité mouvement traite son cas d'arrêt.
Ici le cas nouveau, c'est **la nappe débranchée, coupée ou mal enfichée**. Bilan
net par net, variante A :

- **+5V coupé** → les modules s'éteignent → plus de PWM → les SmartDrive40
  sans commande s'arrêtent (même hypothèse que l'`OE`) ;
- **+12V coupé** → la bobine du relais 40 A retombe → **24 V moteurs coupé**.
  C'est le principe « à manque de courant » de la boucle coup-de-poing : la
  nappe s'y intègre sans rien ajouter ;
- **`OE_WHEELS` ne traverse pas** ; `HEARTBEAT` ne traverse pas (J1 est sur L) ;
- I²C et data LED coupés → perte de supervision et de lumière, pas de danger.

**Aucun fil de la nappe n'a besoin d'être présent pour que le robot s'arrête.**
C'est la propriété à conserver en routage, et à vérifier au protocole caméra
(débrancher la nappe en plein mouvement, roues hors sol — même geste que le
« kill de la chaîne » du 04/07).

Variante B, en plus : **R10 (pull-up 10 k de `OE_WHEELS` vers +5V) doit être
sur la carte M, à côté de M1**, pas sur L avec Q1. Nappe débranchée = `OE` haut
= sorties coupées. Sur L, le pull-up serait débranché avec la nappe et l'`OE`
flotterait — exactement le trou que la carte est faite pour fermer.

Dans les deux variantes, la logique de la chaîne (monostable, verrou, ET de
sûreté, relectures) **ne change pas d'un net** : le contrat figé en tests sur
la branche `chaine-securite` reste valable tel quel. Ce qui change est
mécanique. La règle CLAUDE.md s'applique quand même : revue Opus du schéma
découpé avant Gerber, protocole caméra au premier montage.

---

## 4. Deux étages, ou côte à côte

Côte à côte, les deux cartes occupent 200 × 100 = 200 cm² — **déjà moins que les
292,5 d'aujourd'hui**. L'empilement n'est donc pas nécessaire pour l'emprise ;
il l'est si la place dans le robot est un carré, pas un rectangle. Si on empile,
l'ordre n'est pas libre :

| Ordre | Ce qui est accessible | Ce qui ne l'est plus |
|---|---|---|
| P en bas, L en haut | bande sécurité, bouton ARM, modules, nappe Pi | **les 8 fusibles**, sous L → **non** : un fusible se change dans une loge, en cinq minutes |
| **L en bas, P en haut** | fusibles, LED de présence, tous les borniers de puissance ; les borniers J41-J43 de L par la tranche (fiches horizontales) | le bouton ARM local SW1 et les modules — acceptables : **J41 « ARM déporté » existe pour ça** (le START de la télécommande), et on ne touche aux modules qu'à l'atelier |

Recommandation si empilé : **L en bas, P en haut**. Contraintes à mesurer avant
de figer l'entraxe des entretoises (pas de valeur inventée ici) :

- hauteur du PCA9685 enfiché sur son support 8,5 mm, condensateur et bornier
  vert compris — c'est lui qui fixe l'écart entre étages ;
- hauteur des MSTBA horizontaux et des porte-fusibles sur P (vers le haut,
  libres) ;
- les 4 trous M3 aux **mêmes coordonnées** sur P et L (entraxe commun, une
  colonne d'entretoises par coin) ; la nappe 16 fils replie sur 30 mm sans
  contrainte ;
- l'IDC 2×20 de J1 (59,5 mm de long) sous P : nappe Pi à brancher **avant**
  d'empiler, ou J1 en bord de carte.

Le support/capot imprimé prévu au DESIGN (« entretoises 150×150 ») est à
redessiner dans tous les cas.

---

## 5. Ce que ça change dans les scripts

Les cartes sont générées (`generate_schematic.py` → `INSTANCES`, `generate_pcb.py`
→ `PLACE`/`routes()`/`ZONES`). Le découpage se fait **dans la table**, pas à la
souris :

1. `INSTANCES` : ajouter les deux connecteurs de nappe (J50 sur L, J51 sur P)
   avec leurs 16 nets ; passer M1.6 (V+) à `NC` ; supprimer ou non M2/M9 selon
   la variante. Le schéma peut rester **un seul schéma** avec deux feuilles
   hiérarchiques — le contrat de la chaîne de sécurité continue de se lire sur
   une page.
2. Deux `generate_pcb.py` (ou un seul paramétré par carte), `W, H = 100, 100`,
   `HOLES` aux quatre coins **identiques** sur les deux cartes.
3. Nouvelles tables `PLACE` — c'est le vrai travail ; `routes()` à réécrire
   (celle de main-carrier est jetée, celle de la bande sécurité n'existait pas).
4. Les vérifs existantes rejouent telles quelles : ERC, DRC, `check_silk.py`,
   rendu `kicad-cli`.

Effort : une session de placement par carte, une de routage par carte. Le
routage de puissance (P) est le plus long — pistes 2 à 3 mm, 8 ponts de
porte-fusibles. La carte L a 16,5 cm² de bande sécurité déjà pensée en colonne
(commentaires du 14/07 : DIP en Y, résistances à gauche, diodes à droite) qui
se transpose.

---

## 6. Le coût, une fois passé

| Poste | Avant | Après (var. A) | Après (var. B) |
|---|---|---|---|
| PCB nus, 5 ex. de chaque (PCBWay, prix lus) | 41 $ + ~80 $ (règle de trois) | 3 × 5 $ = **15 $** | 4 × 5 $ = **20 $** |
| Nappe(s) IDC 2×8 + entretoises | — | stock | stock |
| Frais fixes d'import (port, 3 € douane, DDP min. 12 €) | idem | idem — **inchangés**, ils sont par commande |

Le gain est sur le seul poste PCB, ~100 $ → 15-20 $. Les composants ne bougent
pas (mêmes pièces, mêmes 81 € vérifiés, même quarantaine de références non
chiffrées). En Europe, Aisler facture au cm² : la surface totale passe de 442
à 300-400 cm², gain modeste — **le seuil 100×100 est un effet des tarifs
chinois, pas d'une économie de matière**.

---

## 7. Décisions à prendre, hypothèses à mesurer

**À trancher par David** (aucune n'est technique, toutes conditionnent le placement) :

1. **Deux cartes (sans M2/M9) ou trois cartes (tout gardé) ?** — c'est reprendre
   la décision « 2 emplacements PCA9685 » du 05/07. Ma recommandation : **deux**,
   avec J11 comme port d'extension par câble ; le 2ᵉ PCA9685 n'a jamais été
   câblé et 6 canaux restent libres sur le premier.
2. **Empilé (L en bas, P en haut) ou côte à côte ?** — dépend de la place dans le
   robot, que je ne connais pas. Côte à côte est plus simple et déjà plus petit
   qu'aujourd'hui.
3. **Fusibles 5×20 (stock) ou lames auto ?** — 14,4 cm² contre ~10 ; je propose
   de garder le 5×20 : le stock est là, la surface tient.

**À mesurer avant de figer** (à l'atelier, pied à coulisse) :

- hauteur du PCA9685 enfiché (§4) ; hauteur MSTBA et porte-fusibles ;
- filetage des entretoises laiton (M2.5 / M3) ;
- taille réelle du module INA226 retenu — **hypothèse 26 × 20 mm** dans les
  surfaces ci-dessus ;
- entraxe du HW-171 (déjà noté au DESIGN, jamais mesuré).

---

## 8. Décisions de David (2026-09-26, le jour même) — et ce qu'elles rouvrent

**Tranché** : **trois cartes** (tout gardé : M2, M6, M9) et **empilées**.
Fusibles 5×20 conservés (pas d'objection).

Le choix « trois » rend caduc l'ordre d'empilement proposé au §4, qui raisonnait
à deux cartes. À trois niveaux, la question devient : où mettre M (les modules,
la carte la plus haute, ~25 mm avec un PCA9685 enfiché) et L (le nœud des
nappes). Ce point est technique, je le tranche et je l'explique :

| Niveau | Carte | Pourquoi là |
|---|---|---|
| **haut** | **P** puissance | les 8 fusibles, les LED de présence et tous les borniers de puissance restent sous la main — la seule contrainte non négociable |
| **milieu** | **L** Pi + sécurité | c'est **le nœud** : elle parle à P (+5V, +12V bobine, data LED) et à M (I²C, `OE_WHEELS`, +5V des modules). Au milieu, **les deux nappes sont courtes et adjacentes** ; aucune nappe ne saute un niveau, aucun net ne transite par une carte tierce. Ses borniers J41-J43 se prennent par la tranche |
| **bas** | **M** modules | on n'y touche qu'à l'atelier ; leur hauteur tombe dans l'écart bas, qu'on dimensionne pour eux ; le V+ 10 A arrive **par fil** de P aux borniers verts, le long de la colonne d'entretoises |

Conséquences à graver dans les tables :

- **le +5V des modules passe par L** (P → L → M) : nappe L↔M débranchée =
  modules éteints = PWM coupés ; nappe P↔L débranchée = L **et** M éteints,
  bobine du relais 40 A retombée. La propriété « aucun fil n'a besoin d'être
  présent pour que Didier s'arrête » tient toujours, à trois cartes ;
- **R10 (pull-up `OE_WHEELS`) sur M, à côté de M1** — règle du §3.5, désormais
  obligatoire ;
- **deux nappes**, pas trois : P↔L (2×5 suffit : +5V ×2, +12V ×2, GND ×3,
  LED data ×2, 1 libre) et L↔M (2×8 : +5V ×2, GND ×3, SDA/SCL_5V, `OE_WHEELS`,
  SDA/SCL_PI, +3V3 pour M7, 4 libres). M7/M8 (INA226) restent sur **P** avec
  leurs shunts, comme au §3.3 — la carte M ne porte que les modules du bus et
  J11 ;
- **quatre trous M3 aux mêmes coordonnées sur les trois cartes** ; l'écart
  bas (M→L) se mesure sur le PCA9685 enfiché, l'écart haut (L→P) sur les DIP
  sur support et l'IDC J1 (nappe Pi à brancher avant d'empiler, ou J1 en bord).

Surfaces à trois cartes, inchangées : P 46 / M 62 / L 31 cm².

## 9. Plan d'exécution

1. ~~David tranche §7-1 et §7-2.~~ **Fait le 26/09** (§8).
2. `audio-relays` en 100 × 100 : nouvelle `PLACE`, DRC placement, rendu, **puis
   routage** (elle est la plus simple et la plus urgente pour la ronflette).
3. `main-carrier` : découpage de `INSTANCES` (deux connecteurs de nappe par
   carte concernée, M1.6 NC, R10 déplacé vers M, feuilles hiérarchiques), puis
   carte L (Pi + sécurité), puis M (modules), puis P (puissance).
4. **Revue Opus** du schéma découpé, avec la question unique : « une nappe
   débranchée arrête-t-elle le robot, net par net ? » (§3.5 et §8).
5. Gerbers des quatre cartes → **une seule commande**, DDP → premier prix ferme.
6. Mesures d'atelier avant le support imprimé : hauteur du PCA9685 enfiché,
   filetage des entretoises, taille du module INA226.
7. Montage, puis **protocole caméra** roues hors sol, avec le geste nouveau :
   débrancher chaque nappe en plein mouvement.

---

## 10. Réalisation (26-27/09/2026) — les 4 cartes sont prêtes à fabriquer

Dépôt `didier/pcb`, dossier `kicad/`. **Les 4 cartes : ERC 0, DRC 0 violation /
0 pad non connecté, sérigraphie 0 conflit, pile cohérente** ; Gerber + perçages
dans `kicad/fab/<carte>.zip` (`make_fab.sh`), contours contrôlés dans les Gerber :
100,00 × 100,00 mm.

| Carte | Commit clé | Particularité |
|---|---|---|
| `audio-relays` | `56a1e5b` | 150×100 → 100×100 sans sacrifice, routée pour la 1ʳᵉ fois |
| `carrier-l` Pi + sécurité | `dccd525` | bande de sécurité inchangée net pour net |
| `carrier-m` modules | `946eaa5`, `9a21307` | R10 (pull-up OE) contre M1 |
| `carrier-p` puissance | `9a21307`, `4222f0a` | **posée tournée de 180°**, PTC de tête de nappe, nappe autoroutée |

Outillage (tout rejouable, `/usr/bin/python3 generate_pcb.py` par carte) :
`pcbgen.py` (tables → carte, zones remplies en headless), `schgen.py`,
`carrier_design.py` (LA table des 3 cartes + nappes), `check_stack.py`
(alignement mécanique de la pile), `make_fab.sh`, et Freerouting pour les seuls
signaux de nappe de P (session `.ses` versionnée, réimportée à l'identique).

**Plan de la pile** : [`plan-pile-cartes.png`](plan-pile-cartes.png), généré par
`didier/pcb/kicad/render_stack.py` (écarts entre étages non à l'échelle).

**Écarts avec les §3-§8, à connaître :**

1. **Les deux nappes sont des IDC 2×8** (le §8 prévoyait P↔L en 2×5 : les I²C
   des INA226, qui vivent sur P, y passent aussi).
2. **J1.17 (2ᵉ 3V3 du Pi) est NC** : le relier coûtait une lane entière le long
   de J1 ; le pin 1 suffit.
3. **Erreur de conception trouvée et corrigée le 27/09 : les nappes n'étaient
   pas alignées d'un étage à l'autre** (J50 de P au bord ouest face à J51 de L
   au bord est ; J53 de M 30 mm à côté de J52). Les trois DRC étaient à 0 : un
   DRC vérifie une carte, pas une pile. Corrigé : J53 sous J52 ; **P posée
   tournée de 180°** (4 trous symétriques) avec J50 tourné, pour tomber broche 1
   sur broche 1 au-dessus de J51. Conséquence physique : les borniers de P
   changent de côté dans le robot (le faisceau suit). `check_stack.py` vérifie
   désormais la pile broche par broche (contre-épreuve : l'ancien placement
   sort 16 défauts).
4. **Les nappes contournent la tranche est** (connecteurs sur la face supérieure,
   la carte du dessus est en travers) : ~7 mm entre connecteur et bord.
   Sertissage normal aux deux bouts.
5. **Revue de sûreté des nappes faite (net par net, §3.5)** : la logique d'arrêt
   tient, et elle a trouvé **un défaut, corrigé : F9/F10, PTC de tête de nappe
   sur P** — le +5V et le +12V de la nappe étaient pris avant tout fusible et
   passent dans du 28 AWG. Détail : `kicad/carrier-p/DESIGN.md`.

**Reste avant commande** : cotes réelles des RCA et du transfo (empreintes
provisoires d'`audio-relays`), brochage G5V-2 sur fiche Omron, entraxe du HW-171,
choix des deux PTC (maintien ≥ 0,5 A, ≤ 0,4 Ω sur le +5V), et mesure du courant
de la bobine du relais 40 A. **Au premier montage** : protocole caméra roues hors
sol, avec le geste nouveau — débrancher chaque nappe en plein mouvement.
