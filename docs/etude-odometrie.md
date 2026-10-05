# Étude — odométrie des roues (retour de rotation)

*Décidée le 2026-07-14. Ne pas re-trancher ce qui est marqué DÉCIDÉ : les alternatives ont
été pesées, et les raisons du rejet valent plus que la conclusion. Les inconnues restantes
sont listées en §7.*

## 1. Le problème

Les roues de Didier n'ont **aucun retour de rotation**. Ce n'est pas un oubli, c'est une
conséquence du matériel : le moteur est un **MY1016Z à balais** (et non un brushless, comme
la fiche matériel l'a longtemps prétendu à tort — corrigé le 2026-07-14). Un moteur à balais
n'a pas de capteurs Hall de commutation ; il n'y a donc rien à dériver, aucun encodeur
gratuit. Les Cytron SmartDrive40 qui les pilotent — **un par roue, donc deux** (corrigé le
2026-09-26) — sont eux aussi des drivers *brushed* (PWM + DIR) et n'exposent aucune
sortie tachymétrique.

Deux conséquences, qu'il faut bien distinguer parce qu'elles se réparent ensemble mais ne
font pas mal au même endroit :

**La boucle de vitesse est ouverte.** `/cmd_vel` est un mensonge poli : les m/s commandés
sont un rapport cyclique PWM déguisé. La vitesse réelle dérive avec la tension batterie, le
sol, la pente, la charge. Sur 50 kg, le robot ne va pas droit et ne tourne pas d'un angle
connu.

**Il n'y a pas d'odométrie.** Nav2 exige une TF `odom` → `base_link` localement lisse : AMCL
s'en sert comme modèle de mouvement, les contrôleurs y déroulent leurs trajectoires, la
costmap locale s'y accroche. Sans elle, nav2 ne démarre pas.

Ni le lidar ni la caméra ne comblent ce trou. Le lidar peut fabriquer de l'odométrie par
recalage de scans, mais dans une salle de théâtre — rideaux noirs, public mobile, décor
déplacé entre les scènes, murs longs et symétriques — c'est le pire cas du scan-matching, et
à 10 Hz ça ne referme jamais une boucle de vitesse. La caméra monoculaire 130°, elle,
n'a **pas d'échelle métrique** : elle ne peut pas produire de vitesse en m/s.

## 2. La contrainte mécanique — RELEVÉE SUR PHOTOS le 2026-07-14

⚠️ **Correction.** Cette section affirmait « axe acier Ø 20 mm ». C'est **faux** : les photos
du train arrière (2026-07-14) montrent tout autre chose. La conception qui en découlait — une
**bague de serrage fendue Ø 20** en nomenclature — est **caduque**.

Ce qu'il y a réellement, de l'extérieur vers l'intérieur :

```
  pneu │ jante │ COURONNE 428 │ écrou M20 │ FILETAGE NU │ ÉTRIER alu + ROULEMENT │ châssis
                                   ↑            ↑
                        l'ENTRAÎNEUR      ~30 mm de tige filetée libre
                        (déjà en place)
```

- **L'axe est une TIGE FILETÉE M20** — mesuré au mètre le 14/07 : l'écrou fait **30 mm sur
  plats**. Le Ø 20 de l'étude était donc juste ; ce qui était faux, c'est qu'il soit **lisse**.
- **Elle TOURNE avec la roue** — vérifié au feutre (trait tracé sur la tige, roue tournée à la
  main : le trait suit). Ce n'est pas un détail de curiosité : c'est le **postulat de tout le
  montage**. Si la tige avait été un axe mort et la roue montée sur ses propres roulements, un
  disque serré dessus n'aurait mesuré rigoureusement **rien**.
- **La chaîne est marquée 428** → pas de **12,7 mm** confirmé (l'étude le supposait).
- La **couronne est boulonnée à la jante par 3 boulons**, freinés au fil.
- Il reste **~30 mm de filetage nu** au-delà de l'écrou de moyeu (et de la visserie peut
  être ajoutée si besoin).

Cette tige filetée n'est pas une contrainte : c'est un **cadeau**. Un filetage est une interface
de fixation gratuite, réglable et démontable — voir §3 bis.

⚠️ **Mais le M20 coince** : un écrou M20 fait **16 mm de haut**. Serrer le disque entre deux
écrous *ajoutés* coûterait 2 × 16 + 10 (disque) = **42 mm** — bien plus que les ~30 disponibles.
C'est cette cote, et elle seule, qui impose le montage en **coiffe** du §3 bis.

### La garde sous la caisse : 30 mm — et le piège qu'elle tend

Mesuré le 14/07 : **il n'y a que 30 mm entre l'axe et le bas de caisse.** De quoi croire le
disque mort-né (celui qu'on avait dessiné faisait 129 mm de Ø, il aurait tapé au premier tour).

Sauf que **cette garde ne vaut que sous la caisse, à l'aplomb de l'étrier**. Plus loin le long
de l'axe, côté roue, la caisse s'arrête — et **la couronne le prouve** : elle fait 55 mm de
rayon, presque le double de la garde, et elle tourne déjà librement, tous les jours. Il y a
**30 mm de créneau** entre le bord de la caisse et la face de la couronne.

D'où la géométrie retenue, qui n'est pas intuitive et mérite d'être retenue telle quelle :

```
        │ caisse ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
        │  30 mm ↕              │← la caisse s'arrête ici
   ─────┼───────────────────────┼──────── axe M20 ────────
        │ contre-écrou │ COIFFE │ DISQUE R=78 │ écrou │ COURONNE R=55
        │   (sous la caisse :    │ (dans le créneau de 30 :
        │    R=22 < 30, ça passe) │  le grand rayon y est permis)
```

**Le grand disque va du côté de la couronne, pas du côté de la caisse.** Seule la coiffe
(R = 22 mm) passe sous la caisse, où elle tient sans peine dans les 30.

⚠️ Conséquence à ne pas rater au montage : **rien ne doit dépasser côté couronne**. Les écrous
des cibles sont donc **noyés dans des lamages**, et c'est ce qui fixe l'épaisseur du disque
(10 mm). Une vis qui dépasse de ce côté-là tape la chaîne.

### La chaîne : le disque passe DEVANT, il ne la contourne pas

Mesuré le 14/07 : **la couronne ne fait que Ø 110**, donc la chaîne tourne dans un cercle de
**55 mm de rayon**. Le disque en fait 78. **Il déborde.**

Et pourtant il passe — parce qu'**un disque n'a pas à rester dans le cercle de la chaîne, il
lui suffit d'être hors de son PLAN**. Une 428 ne déborde que de ~6 mm de la face de la couronne.
Le disque est donc **décalé de 10 mm par une jupe** : il passe *devant* la chaîne, ne la croise
jamais, et **garde son grand rayon — donc sa résolution**.

```
   face couronne ─┬─ chaîne (R=55, déborde de 6 mm)
                  │        ╭── DISQUE R=78, à 10 mm : hors du plan de la chaîne
                  │   ╭────┴──────────────╮
   ───────────────┴───┴──── axe ──────────┴──────
```

L'alternative — réduire le disque à R = 50 pour « rentrer dans la chaîne » — aurait coûté très
cher : 9 cibles au lieu de 15, soit ~22 mm/front, à peine une impulsion par période de contrôle
à 20 Hz. Inasservissable, une fois de plus.

⚠️ **Le créneau est désormais plein** : décalage (10) + disque (10) + tête de vis (5,3) +
entrefer (2,5) = **27,8 mm pour 30 disponibles**. Ça passe, mais sans gras — et ce qui taperait
la caisse, en cas d'erreur, ce serait **le nez du capteur**. Un `assert()` le vérifie.

## 3. La cible — DÉCIDÉ : roue phonique, lue par la FACE

Un **disque** serré entre deux écrous sur la tige filetée de l'axe (voir §2), portant des **cibles
radiales**. Le capteur est **couché, parallèle à l'axe**, face au disque : il voit défiler
*acier / lumière / acier / lumière*. C'est le principe d'une couronne d'ABS automobile.

### Pourquoi pas les dents du pignon (lecture radiale)

Ça marche, et ça ne demande aucune pièce neuve — c'était la première piste. Mais **la chaîne
impose le pas** : 12,7 mm. Un pas aussi serré force un capteur M8, qui ne détecte qu'à
1,5–2 mm. Cela veut dire un **entrefer d'un millimètre, à vie**, sur une machine de 50 kg qui
part en tournée.

Sur un disque qu'on dessine soi-même, on **choisit le pas** : on l'ouvre à 20–25 mm, ce qui
autorise un capteur M12 détectant à 4 mm, donc un entrefer de 2,5–3 mm — tolérant aux
vibrations, au jeu des paliers, au montage approximatif. Le montage à plat sur une platine
est en prime bien plus facile à aligner qu'une équerre à 1 mm d'une denture.

### Pourquoi pas la chaîne

Piste séduisante, et elle existe en industrie. Trois raisons de la garder en secours :

- **Elle n'apporte aucune résolution supplémentaire.** Par définition d'une transmission par
  chaîne, celle-ci avance d'exactement un pas par dent : compter les maillons ou les dents
  donne le même nombre d'impulsions par tour de roue. Pas de repas gratuit.
- **Elle fouette.** Plusieurs millimètres de battement latéral, face à une portée de
  détection de 1,5 mm → impulsions perdues. Une odométrie qui perd des impulsions dérive, et
  personne ne s'en aperçoit avant que le robot ne parte de travers.
- **Piège discret** : ses maillons alternent extérieur / intérieur tous les **deux** pas. Un
  capteur qui s'accroche sur ce motif-là plutôt que sur les rouleaux **divise silencieusement
  la résolution par deux**. Erreur invisible, robot qui croit avoir parcouru la moitié de la
  distance.

Si le disque s'avérait impossible à loger, la chaîne reste jouable — mais **sur le brin
tendu uniquement**, à deux ou trois centimètres du point de tangence, là où les dents la
contraignent géométriquement et où elle ne peut pas battre.

## 3 bis. La FIXATION du DISQUE — la COIFFE (et le détour par le sandwich)

**Décision finale, 2026-08-17 au soir : on garde la COIFFE sur l'écrou M20**,
telle que décidée le 14/07 et décrite ci-dessous. 10 cibles, Ø 113,
**19,6 mm/front**. Le disque est imprimé.

### Le détour par le « sandwich sur la couronne », et ce qu'il a rapporté

Les 16 et 17/08, à la demande de David (couronne déposée en main), une variante
a été explorée : **boulonner le disque sur la couronne** à travers ses 4 trous de
fixation, pour n'avoir **qu'un seul ensemble à monter**. Le bénéfice visé était
la simplicité de montage — pas un gain de place.

Elle est **mise de côté**, et le raisonnement complet vit dans
`plans/odometrie/variante-sandwich-couronne/NOTE.md`. En deux lignes : le cercle
des vis, **mesuré à Ø 77**, met la visserie à R 38,5, donc les logements d'écrou
(Ø 15,6) et les taraudages de cible se disputent la même bande de matière. On
tombait à **8 cibles, 24,5 mm/front** — sous le seuil de 22 que le §7 ci-dessous
juge inasservissable. Les récupérer imposait une visserie non standard et faisait
tenir toutes les marges à leur minimum en même temps. La coiffe, elle, existe
déjà et donne 19,6.

**Mais le détour n'a pas été perdu — il a produit quatre cotes MESURÉES qui
renforcent la coiffe :**

| cote | avant | mesuré le 17/08 |
|---|---|---|
| épaisseur de la couronne | — | **6 mm** |
| chaîne 428 hors-tout | — | **16 mm** |
| → **débord de chaîne** | 6 (hypothèse « optimiste ») | **5 mm** par face |
| **obstacle carter** (`OBSTACLE_R`) | 63 (extrapolé du Ø 155 en butée) | **~66 mm** — disque Ø 113 présenté, **≥ 10 mm d'air** relevés contre 6,5 au modèle |

Autrement dit, les deux hypothèses les plus inquiétantes du chantier étaient
**pessimistes** : le disque passe plus au large qu'on ne le croyait, et la chaîne
déborde moins. C'est le genre de résultat qu'on n'obtient qu'en allant mesurer.

### ⚠️ Et une erreur trouvée au passage, qui concerne la coiffe aussi

Toute la documentation du support prescrivait « capteur A à hauteur d'axe,
capteur B réglé 7 mm plus bas ». **C'est faux.** Les deux capteurs étant
diamétralement opposés (3 H / 9 H), monter l'un et descendre l'autre les fait
tourner *dans le même sens angulaire* : l'écart reste 180°, **déphasage 0,00°**.
Les deux LED basculeraient ensemble, le décodeur en quadrature ne verrait aucun
sens de rotation — et **rien ne casserait** : le robot lirait un pivot comme une
ligne droite, nav2 partirait de travers en silence. C'est le frère exact de
l'erreur de signe qui a tué les v3.x du support (§3 ter).

**Règle juste** : à 180°, il faut décaler les deux capteurs **du même côté** de
l'axe, de `h = R · sin(pas_de_cible / 8)` chacun — soit **3,45 mm** à R 44 avec
10 cibles. Corrigé dans `patte-capteur.scad`, qui tire désormais la valeur des
mêmes paramètres que le disque.

---

## 3 bis (le détail). La COIFFE — DÉCIDÉ le 2026-07-14 d'après photos

*C'est la solution RETENUE. Le texte ci-dessous est d'origine (14/07) et reste valable ;
seules les cotes d'environnement ont été affinées le 17/08 — voir le tableau ci-dessus.*

Le disque **coiffe l'écrou M20 déjà en place** contre le moyeu de roue, et un **seul
contre-écrou** le bloque. Rien d'autre : pas de perçage, pas de soudure, pas de collier, pas
une seule pièce du robot démontée — et **on ne desserre jamais l'écrou existant**, on s'appuie
dessus (le contre-écrou pousse le disque vers la roue, donc dans le sens qui le serre).

### Pourquoi une coiffe, et pas simplement deux écrous

C'était le plan initial, et **le M20 l'a tué** : un écrou M20 fait 16 mm de haut, donc deux
écrous ajoutés plus le disque réclament 38 mm, pour 35 disponibles. Ça ne rentre pas.

L'écrou déjà monté résout le problème en rendant **deux services d'un coup**, gratuitement :

- il sert d'**entraîneur** — l'empreinte hexagonale de la coiffe s'emboîte sur ses 30 mm sur
  plats, donc le disque est entraîné en **prise mécanique positive** ;
- il sert d'**appui** — il ne reste plus qu'un écrou à ajouter.

Bilan : **22 mm consommés** (6 de disque + 16 de contre-écrou) au lieu de 38. La coiffe, elle,
ne coûte rien en longueur : elle enveloppe un écrou qui était déjà là.

### Pourquoi PAS sur les 3 boulons de la couronne (la piste évidente, et le piège)

C'était tentant : trois boulons déjà là, un grand cercle de perçage, un grand rayon de lecture
donc une belle résolution. **Non.** Ces trois boulons sont le **chemin de couple** de la roue :
tout ce qui fait avancer 50 kg de robot passe par eux. Y ajouter une pièce impose des vis plus
longues, un nouveau serrage, un frein-filet refait — donc de remettre en cause une liaison qui
fonctionne, pour un capteur en lecture seule. La règle du projet vaut ici comme ailleurs : on
ne touche pas au chemin roues sans nécessité. Il n'y en a aucune.

### Pourquoi un seul contre-écrou suffit largement

Parce que **le disque ne transmet aucun couple** : il ne fait que tourner. Rien ne le freine,
rien ne le pousse. Le seul effort est son inertie propre — quelques dizaines de grammes.

Le seul vrai risque est qu'il **patine**, et il faut le prendre au sérieux : *une odométrie qui
patine ment sans prévenir*, et le robot croit avoir parcouru une distance qu'il n'a pas faite.
D'où deux remparts :

1. **L'empreinte hexagonale de la coiffe** : le disque est entraîné par l'écrou lui-même, en
   **prise mécanique positive**, pas par la seule friction d'un serrage sur du plastique.
2. **Un repère fraisé sur la tranche** : d'un coup d'œil, roue en main, on voit si le disque a
   tourné sur son axe.

### La cible : des têtes de vis M8, pas des lumières découpées

Un inductif ne voit **que le métal** — le plastique lui est parfaitement transparent. Le disque
imprimé n'est donc pas un pis-aller : c'est un **porte-cibles**. Ce que le capteur voit, ce sont
**10 têtes de vis M8 en acier** (Ø 15 mm sur angles ≥ 3 × Sn, la règle des inductifs — du M6 à
10 mm serait sous le seuil), montées tête côté capteur, **écrou noyé côté couronne, tête indexée
dans une empreinte hexa côté capteur** (ajout du 16/08 : profil identique pour toutes les
cibles, plus rien à tenir au serrage). Imperdables, épaisses, et elles ne se décollent
pas sous vibrations — ce que des rondelles collées feraient tôt ou tard.

Écrous **normaux + frein-filet**, pas des nylstop : un nylstop M8 fait 8 mm de haut et ne
rentrerait pas dans le lamage.

Conséquence heureuse : **la géométrie validée en plastique est exactement celle qu'on gravera
dans l'acier**. Le prototype n'est pas une approximation du disque final, il en est le plan.

## 3 ter. Le SUPPORT — ⚠️ v4 MORTE AU MONTAGE le 2026-08-19, direction v5 : prise sur la VIS DE SUSPENSION du palier

**Essai réel du 19/08 (photos `../plans/odometrie/photos/`) : la patte v4 ne se place pas** —
le corps du palier (chape pendante + visserie de suspension) occupe le volume sous caisse
visé par la semelle. Troisième pièce tuée par une cote d'environnement jamais mesurée
(après le carter et la couronne) : la v4 n'avait jamais été présentée roue montée.

**v5 DESSINÉE le 20/08 — le BERCEAU** (idée d'ancrage de David, palier identifié KP004
par sa fiche constructeur) : une pièce par roue, **pincée sur le filetage libre des 2 vis
M8 du palier** (entraxe 80, ≥ 20 mm de filet mesurés) entre **deux écrous à elle** — c'est
le retour de l'ancrage-palier v2 (mécaniquement supérieur : le palier porte le roulement,
donc l'entrefer ignore la flexion de caisse), et l'empilement qui porte la roue n'est
JAMAIS touché (fluage PETG → serrage qui tombe, sinon). Les **2 capteurs sont EN BAS à
±49,5°** (à hauteur d'axe ils percuteraient les vis) : la quadrature est un **modulo du
pas de cible** — un écart de 81° = 2,25 pas vaut électriquement un quart de pas, intégré
à la pièce ; le trim fin se fait en glissant le pinçage sur le filet, aux LED. Bloc **E**
de `plans/odometrie/MESURES.md` : tout est ✅ sauf **E4 = 25 mm (HYPOTHÈSE — axe des vis
→ têtes de cibles, à valider au réglet avec la vue de montage AVANT impression)**.
Détail et rendus : README du dossier plans, section v5, `rendus/berceau-v5-*.png`.

Au passage le 19/08 : **impression du disque validée**, monté par David **plaqué contre la
couronne avec rondelles en entretoise** (la visserie de la couronne empêche le contact
plan) — deux vigilances consignées au README plans (fluage dans l'empilement serré →
contre-écrou + re-serrage ; faux-rond à vérifier à la LED, roue en l'air).

### ~~v4 (2026-08-16)~~ : une patte par capteur, de part et d'autre du palier — conservée pour mémoire

**La décision du 14/07 (bride puis équerre sur le palier) est SUPPLANTÉE, et les v3.x du
16/08 après-midi aussi.** Montage de David : **4 pattes identiques** (2 par roue) vissées
**sous la caisse**, un capteur de chaque côté du palier, **à hauteur d'axe** (3 H / 9 H).
Là, 30 mm séparent l'axe de la caisse : **montage classique, un écrou M12 de chaque côté du
voile** — la quincaillerie livrée avec le capteur. `plans/odometrie/patte-capteur.scad`,
rendus de montage dans `plans/odometrie/rendus/`.

Les v3.x (capteurs à 6 H, pièce double, puis corps taraudé faute d'écrou arrière) sont
mortes deux fois : imposition héritée de la v2 qui ne se justifiait plus, ET une **erreur
de signe** dans les calculs de profondeur (l'axe est 30 mm SOUS la caisse — à 6 H les
capteurs pendraient à ~71 mm sous la caisse, pas 11). C'est David qui a vu les deux
(« pourquoi si bas ? », « je ne peux pas mettre d'écrou »).

**La quadrature est un réglage VERTICAL** : deux capteurs face à face = 180° = 5 pas de
cible pile = déphasage nul. Il faut un quart de pas — **9°, soit ~7 mm d'arc à R = 44** :
le capteur B se règle 7 mm plus bas que A dans la **lumière verticale (±8 mm)** de son
voile, aux **LED intégrées** (la LED de B bascule à mi-chemin entre deux bascules de A).
Lumières de semelle = rayon (±4 mm), écrous = entrefer (cale de 2,5).

⚠️ Avant perçage : présenter roue montée (palier, bride, carter), et **re-mesurer la
couronne déposée le 16/08** — au réglet elle fait ~130-135 mm hors-tout, l'étude disait
« Ø 110 mesuré ». Sans effet sur le disque (l'obstacle mesuré `OBSTACLE_R = 63` reste le
plafond), mais les gardes chaîne des asserts s'y recalent.

Ce qu'on gagne : on **ne touche plus aux boulons du palier** (un organe qui porte la roue),
plus de tôle à découper/plier, plus de plan papier, les 3 cotes de palier deviennent sans
objet, et du PETG autour du nez — le cas idéal pour un capteur non noyable. Ce qu'on concède :
l'ancrage caisse re-couple l'entrefer à la flexion du châssis (l'argument pro-palier
ci-dessous reste vrai) — mais sur 11 mm de bras au droit des paliers, la flexion locale est
minime, et l'entrefer à 60 % de Sn tolère ±1 mm. La quadrature dépend du monteur (une patte
par capteur) : se caler avec les LED des capteurs, disque monté.

*Historique (v1 → v2), conservé parce que le raisonnement resservira :*

Première idée, abandonnée : boulonner le support **sous la caisse**. À l'atelier, ça ne passe
pas — **les paliers sont dans le chemin** (et les capteurs du Ø 155 pendaient 31 mm plus bas).

Le support se **bride sur le palier lui-même** : deux coquilles imprimées pincent son plat comme
un étau, serrées par 2 vis M5 qui passent de part et d'autre. **Zéro perçage** sur une pièce qui
porte la roue.

### Ce n'est pas un pis-aller, c'est mécaniquement supérieur

Le palier **porte le roulement** : il bouge donc *exactement* avec l'axe, donc avec le disque.
Un support ancré dessus tient un entrefer constant quoi qu'il arrive. Ancré sous la caisse, la
moindre flexion du châssis fait **respirer l'entrefer** — et un entrefer qui respire, ce sont
des impulsions perdues, donc une odométrie qui dérive **sans que personne ne s'en aperçoive**.

### Deux aubaines dans la géométrie du palier

C'est une **chape pendante** : un plat d'alu suspendu par une tige filetée, roulement en bas.

1. **Sa face est perpendiculaire à l'axe, donc parallèle au disque** — exactement l'orientation
   qu'il faut pour coucher les capteurs.
2. **Le plat descend sous l'axe** : la bride pince là, et le bras des capteurs descend tout droit
   jusqu'à 6 h. Court, donc rigide — au lieu d'un long porte-à-faux depuis la caisse.

Le corps du capteur fait 60 mm : depuis le palier, il n'a qu'à **avancer d'environ 18 mm** vers
la couronne pour venir lire le disque. Le réglage d'entrefer reste ses deux écrous.

⚠️ **Les capteurs ne doivent pas remonter au-dessus de ~25°** : à R = 65, ils passeraient
au-dessus du fond de caisse (30 mm) et leur corps de 60 mm irait taper dedans. Un `assert()` le
vérifie.

## 4. Le capteur — DÉCIDÉ : LJ12A3-4-Z/BX

Capteur de proximité **inductif** M12, **NPN NO**, 6–36 V DC, portée 4 mm, 500 Hz.
~2,35 € pièce. Ce n'est pas un « capteur de vitesse » automobile : c'est un détecteur de métal
industriel, et c'est exactement ce qu'il nous faut.

> ### <https://fr.aliexpress.com/item/1005010394186100.html>
> **`LJ12A3-4-Z/BX` NPN NO, 6–36 V, 4 mm** — vendeur DIYUSER. **3,19 € pièce, 2,80 € dès 2.**
>
> ✅ **Cette annonce-ci ne vend QU'UNE variante** : la NPN NO, écrite en toutes lettres dans le
> titre. Pas de sélecteur BX/AX/BY — **le piège PNP décrit ci-dessous n'existe pas ici**, et
> c'est précisément pourquoi c'est elle qu'on retient. (Les annonces « multi-variantes », où le
> PNP se cache dans le sélecteur, sont à fuir : voir §4, elles tuent le Pico.)
>
> Prendre **6 pièces** (4 + 2 rechange) → 16,80 € : au-dessus du seuil de **port gratuit (10 €)**.

### Comment il fonctionne — et pourquoi ça explique tout le reste

Derrière son nez, une **bobine** rayonne un champ magnétique alternatif à haute fréquence.
Quand un **métal** entre dans ce champ, celui-ci y induit des **courants de Foucault**, qui
dissipent de l'énergie — de l'énergie que le capteur doit fournir. Son oscillation s'amortit,
un comparateur le détecte, la sortie bascule. C'est tout.

Le capteur ne détecte donc pas « un objet » : il détecte **ce qui lui pompe de l'énergie**. Seuls
les conducteurs le font. **Le plastique, le bois, le verre, la main : parfaitement invisibles.**

Trois conséquences, qui ne sont pas des règles arbitraires mais des corollaires directs :

1. **Le disque imprimé marche.** Le capteur voit les têtes de vis *à travers* le PETG, comme si
   le plastique n'existait pas. Le disque n'est pas un pis-aller, c'est un porte-cibles.
2. **La couronne, juste derrière, ne le perturbe pas** : elle est en acier, mais à ~18 mm du
   nez — bien au-delà des 4 mm de portée. Trop loin pour lui pomper quoi que ce soit.
3. **Un support métallique le saturerait** (cf. le piège « non noyable » ci-dessous).

### ⚠️ Quatrième piège : ACIER ZINGUÉ, jamais INOX

Puisque tout repose sur les courants induits, **la portée dépend du métal de la cible**. Les
4 mm annoncés valent pour l'**acier doux** :

| Métal de la cible | Portée réelle |
|---|---|
| **Acier doux** | 4 mm (la référence) |
| Inox | ~2,8 mm |
| Laiton | ~1,6 mm |
| Aluminium | ~1,4 mm |
| Cuivre | ~1,2 mm |

Avec des vis **inox**, la portée tombe à 2,8 mm nominale, soit **~2 mm garantis** : notre
entrefer de 2,5 mm serait **hors de portée**, et le capteur ne verrait rien. Or l'inox A2 est
précisément ce qu'on trouve le plus facilement en visserie du commerce. Le piège est parfait —
la panne est incompréhensible pour qui ignore la règle.

#### 🔴 LE PIÈGE S'EST REFERMÉ — cibles montées en A2-70 le 2026-09-02

Les 2 disques ont été garnis de leurs 10 cibles (photos
`plans/odometrie/photos/2026-09-02-disques-cibles-*.jpg`). Tout le reste du montage est
conforme — sens correct (écrous noyés côté couronne, têtes en saillie côté capteur),
10 cibles, écrous normaux et non nylstop, rien ne dépasse côté couronne. **Mais le
marquage lu sur les têtes est `A2-70` (fabricant `GD`) : c'est de l'INOX AUSTÉNITIQUE**,
exactement ce que cette section interdit. La visserie inox est ce qu'on a sous la main —
c'est là toute la force du piège : rien dans l'aspect ne la distingue de l'acier zingué.

Deux points s'ajoutent, vus sur les mêmes photos :

1. **La tête porte une empreinte 6 pans CREUSE** (avec téton central), là où la
   nomenclature dit « tête H ». Le capteur lit une couronne de métal percée en son centre —
   c'est-à-dire précisément là où le champ est le plus dense. La perte se cumule à celle
   du matériau. Au remplacement : **tête hexagonale PLEINE** (DIN 933 / ISO 4017).
2. Les écrous, eux, peuvent rester inox : **ils ne sont jamais lus** (ils sont noyés côté
   couronne, dos au capteur). Seule la tête est une cible.

**Ne pas racheter à l'aveugle : mesurer d'abord.** Les capteurs LJ12A3 sont reçus depuis
le 16/08, donc la question se tranche en cinq minutes sur l'établi, et la mesure vaut mieux
que la table ci-dessus (qui donne des ordres de grandeur, pas notre exemplaire) :

- **Test de l'aimant, 30 s** — l'A2 est amagnétique, l'acier zingué colle franchement.
  Confirme le marquage, et sert à qualifier les vis de remplacement *au magasin*.
- **Test de commutation, 5 min** — capteur alimenté en 12 V, approché d'une tête montée sur
  le disque, distance de bascule de la LED relevée au réglet ou à la cale. C'est la seule
  mesure qui compte : elle porte sur NOTRE capteur et NOTRE cible.
  - **≥ 3,5 mm** → l'entrefer de 2,5 mm garde sa marge de 60 % : on garde les vis inox.
  - **2,5 à 3,5 mm** → ça bascule, mais sans le gras qui pardonne le voile du disque et le
    jeu de roulement. Vis zinguées.
  - **< 2,5 mm** → la table avait raison, remplacement obligatoire.

📄 **Fiche d'atelier imprimable** (câblage, montage à cales, relevé, verdict) :
`docs/pictures/odometrie/2026-10-05-fiche-mesure-portee.svg`.
Câblage sur breadboard (capteur seul, option LED externe + 2 kΩ qui préfigure une voie de la
carte) : `docs/pictures/odometrie/2026-10-05-breadboard-mesure-portee.svg`.

Refaire la même mesure sur une vis zinguée avant de rééquiper : c'est le comparatif qui
gravera enfin un chiffre mesuré à la place des ~2,8 mm de catalogue.

### L'entrefer : 2,5 mm, mesuré depuis l'ACIER

Pas depuis la surface du disque : depuis la **tête de vis**. Le capteur ne voit que le métal (le
PETG lui est transparent), mais le plastique occupe quand même la place — les têtes font saillie
de 5,3 mm, et c'est d'elles que partent les 2,5 mm.

**Pourquoi 2,5 et pas 4.** Les 4 mm sont la portée *nominale* (Sn), mesurée en usine sur une
plaque d'acier doux à 20 °C. La portée **garantie**, tolérances de fabrication comprises, vaut
~0,72 × Sn ≈ **2,9 mm**. Au-delà, ça marche peut-être — ou pas, selon la température et la pièce,
et on ne le découvrira qu'en tournée. Il faut en outre de la marge de l'autre côté : le disque
voile, le roulement a du jeu. **2,5 mm = 60 % de la portée : le compromis qui pardonne.**

Réglage : le corps est fileté sur toute sa longueur → cale de 2,5 mm, deux écrous M12, on bloque.

### ⚠️ Troisième piège : il est NON NOYABLE

Le `LJ12A3-**4**-Z/BX` porte à 4 mm précisément parce qu'il est **non noyable** (un M12 noyable
— le `-2-` — ne porte qu'à 2 mm). Un non-noyable **ne supporte pas d'être entouré de métal** :
le métal environnant le sature, et il **ne voit plus rien défiler**. La LED reste allumée, tout
a l'air normal, mais le train d'impulsions est mort.

Conséquence directe sur le support : **en plastique, aucun problème** (il est transparent pour
le capteur). Mais le repli « on redécoupe le même support dans de l'alu si le PETG plie » **ne
marche pas tel quel** : il faudrait que le nez dépasse de la plaque d'au moins 4 mm, avec un
dégagement autour. Piège coûteux, parce qu'il se manifeste comme une panne intermittente.

**Ce qu'il ne faut PAS acheter**, parce que la recherche « capteur de vitesse » n'y mène que :

- **Capteurs ABS / boîte de vitesses** : soit à réluctance variable — ils sortent une
  sinusoïde dont l'amplitude *croît avec la vitesse*, donc **rien du tout à basse vitesse**,
  or c'est précisément là que Didier vit ; soit actifs à sortie en courant (7/14 mA), qui
  exigent un circuit de conditionnement dédié.
- **Capteurs de vélo (Magene…)** : Bluetooth, et une impulsion par tour.
- **Kits e-bike (BAFANG…)** : leur fiche annonce « 1 pulse/cycle ». Une impulsion par tour.

### Deux pièges irréversibles

**⚠️ NPN, et JAMAIS PNP.** La variante `/BY` est PNP et se cache dans le *sélecteur de
couleur* de la même annonce. Une sortie NPN est un collecteur ouvert : elle ne fait que
**tirer vers la masse**, donc un rappel vers le 3,3 V du Pico donne un signal propre 0/3,3 V
alors même que le capteur est alimenté en 12 ou 24 V. Une sortie PNP **pousse la tension
d'alimentation** : elle enverrait 24 V dans un GPIO 3,3 V et tuerait le microcontrôleur.
Vérifier la variante dans le panier, pas dans le titre.

**⚠️ Mesurer avant de brancher.** Sur une pièce à 2 €, ne pas parier le Pico sur la fiche
technique : alimenter le capteur seul, et vérifier au multimètre que le fil noir **ne monte
jamais** à la tension d'alimentation. Puis optocoupler quand même (§5).

### Vérification de fréquence (rassurante)

Roue Ø 250 mm (à confirmer), 24 lumières, 1 m/s → **30 Hz**. Le capteur tient 500 Hz. Marge
d'un facteur 15 : même le capteur le moins cher est très largement assez rapide. Inutile de
payer plus.

## 5. L'isolation — DÉCIDÉ : 4 PC817 sur supports, sur la carte

Le châssis est électriquement hostile : deux moteurs **à balais** de 250 W (les balais
**arcent** en permanence), un ampli de sono, des rubans LED à fronts raides. On n'attaque pas
un GPIO en direct là-dedans.

**Quatre PC817 individuels (DIP-4), sur supports tulipe.** Le PC847 (quatre PC817 dans un seul
DIP-16) a d'abord été retenu, puis écarté : à 7 centimes la puce (lot de 20 pour 1,33 €), des
DIP-4 séparés se remplacent **un par un** dans une loge, sans fer à souder — même logique que le
Pico sur supports. Un PC847 grillé, c'est trois canaux sains jetés avec le quatrième. Le seul coût
est un peu de surface de carte : sans objet ici.

Surtout **pas** un module tout fait empilé en mezzanine : deux cartes, deux fixations, un
connecteur de plus à vibrer. Et le module d'établi devient inutile lui aussi — avec les puces
nues, **c'est nous qui choisissons la résistance série**, donc ce qu'on valide sur l'établi est
*exactement* ce qui partira sur le PCB. (Un module tout fait, lui, a une résistance d'entrée
inconnue : on validerait sur l'établi autre chose que ce qu'on grave.)

**L'ISO1540 existant n'est PAS réutilisable** (la question s'est posée). C'est un isolateur
**I²C** bidirectionnel : ses deux canaux sont pris (SDA + SCL), ce n'est pas le bon type de
circuit, il est du mauvais côté du robot (les capteurs parlent au **Pico**, pas au Pi), et il
est **sur le chemin des actionneurs** — le bricoler imposerait de repasser le protocole
caméra. Pour économiser 2 €, c'est absurde.

### Câblage d'un canal

La LED de l'optocoupleur se branche « à l'envers » de l'intuition, parce que le capteur NPN
ne *pousse* rien : il **tire vers la masse**. C'est donc lui qui ferme le circuit de la LED.

```
   +12 V ──────┬───────────────────────────┬── IN+ ─┐
               │                           │        │
        (brun) │                           │     ┌──┴──────────┐
          ┌────┴─────────┐                 │     │   PC817     │
          │   CAPTEUR    │      (noir)     │     │   canal n   │
          │ LJ12A3-4-Z/BX├─────────────────┴── IN-│             │
          │     NPN      │                        │  OUT ───────┼──→ GPIO Pico
          └────┬─────────┘                        │  (rappel 10k vers 3,3 V)
        (bleu) │                                  └─────────────┘
    GND 12 V ──┘
        ◄──── domaine 12 V ────►  ┊  ◄──── domaine 3,3 V ────►
                                  ┊
                    BARRIÈRE : les deux masses ne se rejoignent NULLE PART.
                    Sur le PCB : fente fraisée sous les PC817.
```

- **Alimenter les capteurs en 12 V**, pas en 24 V (le rail Mean Well 12 V existe). Ils
  acceptent 6–36 V : c'est gratuit, ça réduit l'énergie qu'un défaut peut pousser dans le
  circuit, et l'immunité au bruit reste excellente.
- Résistance série : `(12 − 1,2) / 2200 ≈ 4,9 mA` dans la LED — largement assez pour un
  PC817 — et **0,05 W** dissipés. (C'est ce calcul que ratent les modules chinois à 1 kΩ
  quand on les attaque en 24 V : 0,5 W dans une résistance prévue pour 0,125 W. Elle noircit.)
- Rappel de sortie : **10 kΩ vers le 3,3 V**.
- **Conséquence logicielle : métal détecté = niveau BAS.** La logique est inversée.
- **Vitesse de l'optocoupleur** : un PC817 commute en quelques dizaines de µs, le signal
  plafonne à 30–60 Hz. Facteur mille de marge, ce n'est pas un sujet.
- **Test d'acceptation de l'isolation** : en continuité, entre la masse d'entrée et la masse
  de sortie, on doit lire un **circuit ouvert**. Si ça bipe, la carte n'isole rien.

## 6. L'architecture — DÉCIDÉ

### Deux capteurs PAR ROUE, donc quatre

Trois raisons indépendantes, chacune suffisante :

1. **Chaque roue a besoin de sa propre mesure.** Une traction différentielle tourne
   *précisément parce que* ses deux roues diffèrent.
2. **Un capteur seul ne sait pas dire l'avant de l'arrière.** Il voit du métal défiler,
   point : le train d'impulsions est identique dans les deux sens. Deux capteurs décalés
   donnent la **quadrature** — celui qui voit la lumière en premier révèle le sens — et
   exploiter les 4 fronts au lieu de 2 **quadruple la résolution**, gratuitement.
3. **Le sens doit être MESURÉ par roue, jamais déduit de la commande PWM.** En pivot sur
   place, une roue recule pendant que l'autre avance : supposer un signe commun ferait lire
   un pivot comme une ligne droite. Et un robot de 50 kg redescend seul une scène en pente.

**⚠️ Piège d'entraxe** : un quart de pas fait ~6 mm, un corps M12 en fait 12 — les deux
capteurs se rentreraient dedans. On les espace d'**un pas ET quart** : la phase électrique
est rigoureusement identique (c'est un modulo — le capteur ignore combien de lumières
entières le séparent de son voisin), et les corps ont la place.

### ~~La carte va à côté du Pi, PAS près des roues~~ — RENVERSÉ le 2026-08-20 (voir plus haut)

Contre-intuitif, et pourtant décisif. Le câble capteur porte un signal **12 V à collecteur
ouvert** : basse impédance, forte amplitude — une brute, quasi insensible aux parasites
(c'est pour ça que l'industrie l'utilise dans des armoires bourrées de variateurs). Le lien
Pico → Pi, lui, est du **3,3 V logique** : fragile.

Donc on fait porter la longue distance au signal robuste. La carte se monte **dans le boîtier
électronique**, le lien fragile fait 15 cm, et les câbles capteurs (1–2 m) partent vers les
roues. Les router **loin des câbles moteur et ampli** ; croiser à 90° si inévitable.

### Comptage : un Raspberry Pi Pico, pas le Pi

Python sur le Pi 4 perdrait des fronts. Le **PIO du RP2040 décode la quadrature en
matériel**, sans faute, et la carte sert au passage de tampon électrique.

#### ⚠️ Un Arduino Nano ferait-il l'affaire ? (question de David, 2026-08-20)

**Techniquement oui, largement — et pourtant on garde le Pico.** À 1 m/s chaque capteur
ne sort que **12,7 impulsions/s** (10 cibles, roue Ø 250), soit ~51 fronts/s par roue
après décodage ×4 : un ATmega328 à 16 MHz a trois décades de marge. L'argument « PIO qui
décode en matériel » ci-dessus était une précaution de confort, pas une nécessité.

Ce qui tranche est ailleurs, et c'est le **lien USB** (voir ci-dessous) :

1. **Le numéro de série.** Une règle udev stable (`/dev/didier-odom`) s'accroche au
   numéro de série du périphérique. Le Pico en a un, dérivé de l'ID unique de sa flash.
   Les clones de Nano à puce **CH340 n'en ont pas** — ils annoncent tous le même
   descripteur. La règle ne pourrait alors viser que le *chemin du port physique*, qui
   casse dès qu'on change de prise. Sur un robot qui part en tournée, c'est une panne
   sournoise de plus. **C'est cette raison, et elle seule, qui décide.**
2. **Le niveau logique.** Le Nano parle en 5 V ; la broche RX du Pi ne tolère pas le
   5 V. Un lien UART aurait exigé un pont diviseur — deux résistances, mais une de plus
   à oublier, et l'oubli tue le Pi. (Sans objet avec l'USB.)
3. **La carte est déjà dessinée autour du Pico** (schéma KiCad, plan de plaque à bandes,
   nomenclature) : le garder, c'est zéro refonte.

Les Nano restent bons pour un poste où le lien n'est pas un port USB nommé.

#### Le firmware est en MicroPython, pas en C — et ce n'est pas de la paresse

Écrit le 2026-08-20 : `firmware/pico_odometry/` (voir son README). Trois raisons :

1. **Le langage ne touche pas le chemin critique.** Le comptage est fait par le **PIO**,
   un automate matériel indépendant du CPU : cinq instructions qui surveillent les
   broches et empilent les changements dans une FIFO de 8 mots, avec un `push()`
   **bloquant** (on prend du retard, on ne perd jamais un pas). Le CPU ne fait que vider
   cette file 50 fois par seconde, pour ~13 événements par roue et par seconde. Une
   pause du ramasse-miettes est absorbée par la FIFO — plusieurs secondes de matelas.
2. **La raison décisive : un seul décodeur, pas deux.** En C, le décodage de quadrature
   et le CRC seraient écrits **deux fois** — une fois en C pour le Pico, une fois en
   Python pour le nœud ROS et les tests. Deux implémentations d'une convention de signe,
   c'est la façon canonique d'inverser une roue sans s'en apercevoir pendant six mois.
   Ici `odom_protocol.py` est **un seul fichier**, qui tourne sur le Pico, dans le nœud
   ROS et dans les **35 tests** du dépôt (`robot/tests/unit/test_odom_protocol.py`).
   C'est la règle du projet : la vérification exécute le même code que la prod.
3. **L'itération à l'établi** : éditer, copier, redémarrer. Aucune chaîne de compilation
   croisée sur un banc où l'on tâtonne.

Le C s'imposerait s'il fallait horodater chaque front à la microseconde, ou si le débit
était cent fois supérieur. Ni l'un ni l'autre.

**Deux choix du firmware qui ne vont pas de soi**, consignés pour ne pas être « corrigés » :

- **Compteurs CUMULÉS, pas des deltas.** Une trame perdue ne perd alors aucune distance,
  la suivante rattrape. Avec des deltas, chaque trame perdue effacerait pour toujours un
  morceau de trajet — silencieusement. Corollaire : le nœud ROS **doit** passer par
  `delta_ticks()` (bouclage 32 bits), jamais par une soustraction directe.
- **Un compteur `illegal`** (transitions où les deux bits basculent d'un coup, donc
  physiquement impossibles) publié sur une ligne `STAT`. C'est le **seul symptôme
  observable** d'une odométrie qui commence à mentir : entrefer trop grand, câble
  parasité, disque qui bat. Il doit rester à zéro.
- ⚠️ Et **les PC817 n'inversent PAS le sens** : ils inversent les deux voies, ce qui
  décale le cycle de Gray sans changer son ordre. Un test verrouille ce point — pour
  empêcher une « correction » de signe faite au nom des optocoupleurs, qui serait fausse.

### ⚠️ RENVERSÉ le 2026-08-20 : carte EN BAS près des roues, lien USB

**Décision de David**, et elle est meilleure que le plan ci-dessous — qui reste écrit
juste après, parce que son raisonnement est juste et qu'il faut voir pourquoi il tombe.

Le plan de juillet fait porter la longue distance au signal 12 V collecteur ouvert
(robuste) pour ne garder que 15 cm de lien logique fragile. Correct — mais il visait un
**UART nu en 3,3 V**, un fil logique sans défense. **L'USB n'est pas ça** : c'est une
paire différentielle blindée, conçue pour traverser plusieurs mètres d'environnement
bruyant et qui rejette le bruit de mode commun par construction. Sur ~1,5 m dans ce
châssis, l'USB est plus solide qu'un fil logique de 15 cm n'était fragile. Et on
raccourcit du même coup les câbles capteurs, donc l'antenne côté sale : on gagne des
deux côtés.

Les deux motifs qui avaient fait rejeter l'USB en juillet tombent ou se traitent :

- *« le nom du périphérique est une loterie »* → **règle udev sur le numéro de série**
  du Pico (il en a un ; c'est ce qui l'a fait préférer au Nano, cf. plus haut).
- *« le connecteur micro-USB est le point faible »* → **reste vrai**, et c'est le seul
  vrai risque du montage. **Bridage obligatoire** : le câble collié au châssis à moins
  de 5 cm de la prise, pour qu'aucune traction n'atteigne jamais le connecteur soudé.

**Ce que la carte y gagne** : alimentée par le câble USB, elle perd le bornier J6, la
Schottky D13 et le rail 5 V. **Ce qu'elle y perd** : l'armoire électronique était un
environnement protégé ; en bas c'est poussière, humidité et chocs → **boîte imprimée
fermée obligatoire**.

⚠️ **On garde les 4 PC817.** La tentation sera forte de les sauter maintenant que le
câble capteur est court : non. La barrière d'isolation vaut *encore plus* en bas, au
milieu des moteurs à balais. Les deux masses ne se rejoignent nulle part.

~~⚠️ **Inconnue** : le 12 V est-il disponible en bas, là où ira la carte ?~~ —
**LEVÉE le 2026-09-02 : OUI.** Mieux : la carte se fixera **sur le coffre de départ
des alimentations 5 V / 12 V / 24 V** (décision de David, cf. ci-dessous) — la paire
12 V se pique à la source, quelques centimètres.

### Décisions du 2026-09-02 — connectique et implantation (la carte passe à l'atelier)

David commence la plaque à bandes (photos dans `docs/pictures/odometrie/`). Quatre
décisions prises ce soir, qui amendent le plan `DESIGN.md` du 14/07 :

1. **RP2040-Zero au lieu du Pico 40 broches.** Rien ne s'y oppose : GPIO2-5 présents et
   contigus (le PIO lit des broches contiguës), numéro de série unique en flash (la règle
   udev tient), et son **USB-C** est plus robuste que le micro-USB que craignait l'étude —
   le bridage du câble à < 5 cm reste obligatoire. Deux barrettes tulipe 1×9, jamais soudé.
2. **Un JST-XH 4 points par ROUE** (`+12V` · `GNDPWR` · `SENS_A` · `SENS_B`), pas un
   bornier par capteur : les deux câbles 3 fils d'un palier sont épissés en un seul câble
   4 fils **à la bride** (gaine thermo), et il ne court que **2 câbles** sous la caisse au
   lieu de 4. Les capteurs arrivent avec ~1,2 m de câble surmoulé : **couper court**,
   l'antenne côté sale doit rester minimale.
3. **Entrée 12 V sur JST-XH 2 points rouge** (remplace le bornier à vis J5). F1, D11,
   D12, C11 restent — la carte vit à côté des départs de puissance, l'écrêtage se justifie
   d'autant plus.
4. **La carte (dans sa boîte imprimée fermée) se fixe sur le coffre des alimentations**,
   pas sur la tôle du fond : le 12 V est à demeure, le coffre est déjà un volume protégé
   des chocs, et les deux câbles capteurs remontent des paliers vers un point unique.

**Plan de plaque REDESSINÉ et REVÉRIFIÉ le soir même** :
`docs/pictures/odometrie/2026-09-02-implantation-stripboard-rp2040-zero.png` (copie
d'atelier à imprimer ; la source est `gen-stripboard.py` dans le dépôt pcb, et le
document de référence reste son `DESIGN.md`). Plaque **26 × 29 trous (~66 × 74 mm)**,
67 coupures, 10 straps. Affectation : **roue G → GP2/GP3, roue D → GP4/GP5** (le PIO
exige des broches contiguës) ; GP0/GP1 réservés UART de secours ; GP6/GP7/GP26/GP27
réservés au chantier PWM roues.

**Compacté une seconde fois le 02/09** (« pourquoi un plan avec tant d'espace ? ») :
rangées 1, 11 et 12 supprimées — les deux blocs roues se touchent — et colonne 14
supprimée. **27 × 32 → 26 × 29**, soit 69 × 81 → **66 × 74 mm**. On ne peut pas aller
plus loin : le reste du « vide » est soit la barrière, soit le dessous du corps du
module, soit — et c'est le contre-intuitif — **la piste elle-même**. Sur une plaque à
bandes un trou libre n'est pas perdu : le cuivre entre deux composants EST la liaison,
le supprimer coûterait un strap. Mesure faite avant de répondre : 13 % des trous
occupés, un chiffre qui ne veut rien dire ici.

**Optimisé une première fois, à la demande de David** : le module est passé sous les blocs
roues, **sur les mêmes rangées que le bloc 12 V mais de l'autre côté de la barrière** —
une rangée peut porter deux nets sans risque puisque la barrière coupe entre eux. Plaque
raccourcie de 7 rangées (99 → 81 mm) et fils d'odométrie ramenés de 94 à 62 rangées
cumulées. La variante « module au CENTRE » a été écartée : elle raccourcit encore les
fils (44 rangées) mais met l'USB-C au milieu de la carte, donc un câble coudé dans la
boîte sur le connecteur le plus fragile du montage.

⚠️ Le brouillon photographié le 02/09 (module au centre, connecteurs de part et
d'autre) **ne doit pas être poursuivi tel quel** : des connecteurs capteurs à droite du
module mettraient du 12 V dans le domaine propre, et la barrière (§5) ne serait plus
sciable d'un trait. Le plan la garde d'un seul trait, colonnes 11-12.

Trois trouvailles du redessin, qui ne se voyaient pas sur le papier :
- **L'ordre des fils dans le XH n'est pas libre** — `noir A · brun · bleu · noir B`. Le
  PC817 veut son anode sur la rangée juste au-dessus de sa cathode ; dans 4 rangées
  consécutives occupées par un connecteur, seule la **première** broche a une rangée
  libre au-dessus. D'où cet ordre, et d'où le seul strap qui reste par roue.
- **Le corps du Zero déborde d'une rangée de chaque côté de ses pastilles** : on met ce
  débord à profit en le posant en bas de plaque, **USB-C affleurant le bord**.
- ⚠️ **Le module a NEUF pastilles par colonne, pas huit** (tulipes 1×9). Le premier jet en
  avait compté huit, d'après la photo d'atelier — `GP14` et `GP8` manquaient. La géométrie
  est désormais tirée du **footprint constructeur**
  (<https://github.com/CountParadox/RP2040-Zero-Kicad>), qui confirme au passage l'entraxe
  de **15,24 mm = 6 pas** — que la même photo faisait lire à 7 pas. **Une photo en
  perspective ne se mesure pas** ; c'est la leçon de `feedback-cao-verifier-le-reel`
  appliquée à l'électronique, avec sa réciproque : le réel se vérifie sur la pièce ou sur
  le fichier du fabricant, jamais sur une image.
- **Le vérificateur a été éprouvé par mutation** (strap retiré, coupures supprimées,
  opto déplacé) : il refuse les trois. Un contrôle qui répond toujours « vert » ne
  prouve rien. **Une quatrième mutation est passée** — module décalé d'une colonne :
  électriquement juste, mais son corps (18 mm de large pour 6 pas de pastilles)
  surplombait le bus +3,3 V, qui devenait insoudable. D'où un **contrôle
  d'encombrement des corps** ajouté le jour même : une faute trouvée à la main est
  une faute que le script doit trouver à notre place la fois suivante.

### ⚠️ Les 74AHCT125 de David ne remplacent PAS les PC817 (question du 02/09)

David a un lot de **`SN74AHCT125N` / `SN74AHC125N`** (DIP-16, Texas Instruments)
acheté pour les rubans LED, et a proposé de les employer ici. **Non** — et la raison
est la règle d'or de cette carte, pas une préférence : un 74AHCT125 est un **buffer
logique alimenté, à masse commune**. Il n'isole **rien**. Le monter à la place des
optocoupleurs reviendrait à souder `GNDPWR` et `GND` ensemble, au milieu de deux
moteurs à balais de 250 W — exactement ce que la barrière (§5) existe pour empêcher.
La confusion est facile et vaut d'être écrite : le boîtier ressemble à un opto, le rôle
n'a rien à voir.

En revanche ces puces **servent ailleurs, et sur un problème connu** : le post-mortem
`docs/incidents/2026-07-13-glitch-visage-driver-led.md` laisse en suspens des « ratés
épars » du visage, avec pour piste matérielle explicite un *level shifter 3,3 → 5 V*.
Le 74AHCT125 est précisément le remède canonique du WS2812 attaqué en 3,3 V.
⚠️ **Seuls les AHC`T` conviennent** (seuils TTL, `Vih` = 2,0 V) ; les **AHC** sans T
demandent 0,7 × VCC = 3,5 V et ne garantissent pas la lecture d'un niveau 3,3 V — or
le lot contient les deux. Trier avant usage.

### ~~Lien Pico ↔ Pi : UART~~ — DÉCIDÉ le 2026-07-14, RENVERSÉ le 2026-08-20 (cf. ci-dessus)

**J6, 4 broches : `+5V` · `TX` · `RX` · `GND`.** Le Pico est alimenté par le rail 5 V du robot
via une Schottky (D13) sur `VSYS`. L'USB **reste branchable**, mais seulement pour flasher le
Pico à l'atelier : il ne porte plus le lien opérationnel.

Pourquoi ce revirement : un connecteur **micro-USB sur un châssis de 50 kg qui part en tournée**
est le point faible du montage, et le nom du périphérique (`/dev/ttyACM0` ou `1`…) est une
loterie. L'UART donne un chemin fixe et un bornier qui ne se déboîte pas.

**La Schottky D13** aiguille le 5 V : le rail du robot entre par `VSYS`, mais ne peut pas
*remonter* dans le port USB du PC quand on flashe. Montage prescrit par la fiche du Pico ;
vérifié sur la netlist (`VBUS` reste isolée de `VSYS`).

### ⚠️ L'I²C est INTERDIT — et ce n'est pas une question de procédure

La question s'est posée (« l'USB me gêne, peut-on faire de l'I²C ? »). La réponse est non, et la
raison est un **scénario d'emballement**, pas une contrainte administrative :

`wheels_node.stop()` **écrit le PWM par le bus I²C** (`robot/actions/wheels.py` → PCA9685). Un
esclave I²C qui plante en tenant SDA à la masse **fige le bus entier**. Enchaînement :

> bus mort → `stop()` ne peut plus écrire → **le PCA9685 conserve sa dernière consigne** → les
> roues continuent de tourner.

Le deadman de 400 ms s'exécuterait, croirait avoir arrêté le robot, et n'aurait rien arrêté. Le
Pico serait le **seul composant du robot capable de tuer le frein**.

Un bus I²C **dédié** (le Pi 4 sait activer `i2c-3` à `i2c-6` par dtoverlay) contiendrait le
risque — un bus figé ne tuerait que l'odométrie. Mais il reste mauvais : le contrôleur I²C du Pi
a un **bug documenté d'étirement d'horloge** qui mord précisément sur les esclaves *logiciels*
(ce qu'est un RP2040 en mode esclave), et l'I²C est le bus le plus sensible aux parasites de ce
châssis — qui a **déjà produit un incident**
(`docs/incidents/2026-07-13-glitch-visage-driver-led.md`).

### Inconnue côté Pi

**Quel UART ?** Le primaire (GPIO14/15) est encombré par la console série et le Bluetooth. Un
UART dédié activé par `dtoverlay` (`uart2`…`uart5`) donnerait un `/dev/ttyAMA*` stable — **à
condition que ses GPIO soient libres sur la carte principale**, ce qui n'est pas encore vérifié.
À trancher avant de câbler.

### Protocole série

Une trame à 50 Hz, avec **numéro de séquence** et **somme de contrôle** :

```
ODO <seq> <ticks_gauche> <ticks_droite> <crc>\n
```

Le numéro de séquence n'est pas décoratif : c'est lui qui permet de détecter un lien mort ou
des trames perdues. Côté Pi, un nœud ROS 2 Python lit le port série et publie. Débogable à la
main par un simple `cat /dev/didier-odom`.

### ⚠️ Règle non négociable : le Pico ne commande RIEN

Il lit, il compte, il rapporte. Il n'est **pas** sur le chemin de commande des roues.

Conséquence à écrire noir sur blanc : **si le lien série meurt, on perd l'odométrie — donc la
navigation autonome s'arrête — mais aucun rempart de sécurité ne tombe.** Le deadman 400 ms
de `wheels_node` reste intact. Une panne d'odométrie ne peut produire qu'un arrêt, jamais un
emballement.

#### « Puisqu'on ajoute une RP2040, pourquoi ne pas y brancher aussi les moteurs ? » (David, 2026-08-30)

Bonne question, et la règle ci-dessus **tient toujours** — mais pas pour la raison qu'on
croit, et le relevé de code qu'elle a déclenché a trouvé pire que ce qu'elle visait. Le
détail vit dans `chantiers.md` § « Chemin de commande des roues V2 » ; en trois lignes :

- Le grief avancé (« l'I²C n'a pas de vrai timing ») est réel : roues et servos partagent
  **la même puce PCA9685**, donc **la même fréquence PWM**, arbitrée par une *course au
  démarrage* entre 50 Hz (`ServoKit`) et 60 Hz (`wheels.py:89`). On ne peut donc pas monter
  la fréquence moteur sans dégrader les servos.
- Mais le grief **le plus grave** est ailleurs : **le PCA9685 n'a aucun chien de garde**. Si
  `wheels_node` meurt, la puce garde sa dernière consigne et les roues continuent — le
  deadman 400 ms est *dans* le processus qui meurt.
- ⚠️ **Fusionner dans CE Pico ne serait pourtant pas la bonne réponse** : ça mettrait l'USB
  (dont le §6 dit lui-même qu'il est le seul vrai point faible du montage) sur le chemin de
  commande, et ça ne paie vraiment que si la **boucle de vitesse** se ferme dans le Pico —
  ce qui n'arrivera qu'à l'étape 5. Un **watchdog matériel** (second MCU) ou, mieux et moins
  cher, une **coupure de puissance câblée** traitent le vrai problème sans renverser le §6.

**Donc : le Pico d'odométrie reste en lecture seule.** Renverser cette règle est possible,
mais c'est une décision de sécurité à prendre explicitement — jamais un effet de bord d'un
chantier capteur.

## 6 bis. « Une carte du commerce ne le fait-elle pas déjà ? » — RECHERCHE du 2026-09-26

**Question de David** : « la carte d'odométrie est beaucoup plus compliquée que j'aurais pensé,
il n'y a pas de petites cartes qui font déjà ça ? » Recherche menée le 2026-09-26 sur cinq
axes (contrôleurs moteur à encodeur, cartes d'entrées isolées pour Pi, compteurs de
quadrature, automates industriels compacts, cartes « contrôleur ROS » toutes faites).
**Tous les prix ci-dessous ont été LUS sur la page du vendeur le 26/09/2026** ; ce qui n'a pas
pu être lu est écrit « prix non lu » — jamais complété de mémoire.

**Réponse courte : chaque brique existe séparément, aucune carte ne fait l'ensemble, et rien
de ce qui existe n'est à la fois moins cher, plus sûr et plus rapide à mettre en œuvre que la
plaque en cours.** Une seule trouvaille mérite un examen — et elle ne concerne pas
l'odométrie mais le *chemin roues* (voir « le seul vrai candidat » plus bas).

### Pourquoi ça n'existe pas : cette carte tombe dans un trou entre deux mondes

Le besoin croise quatre exigences que personne ne réunit dans un produit :
capteur **industriel 12 V NPN à collecteur ouvert**, **isolation galvanique**,
**quadrature** (donc le sens), et **très basse résolution** (40 impulsions/tour).

| Monde | Ce qu'il offre | Ce qui manque |
|---|---|---|
| **Robotique de loisir / ROS** | entrées encodeur, PID parfois, prix bas | **jamais d'isolation**, logique 3,3/5 V, puissance 12 V / 1-3 A — conçu pour des robots de 2 à 5 kg |
| **Automatisme industriel** | entrées 24 V **isolées**, comptage, robustesse | souvent **PNP seulement**, comptage bridé, liaison Modbus/EtherCAT, **150 à 340 €**, et tout le pont ROS reste à écrire |

La carte de Didier est exactement la pièce qui manque entre les deux. **Elle n'est pas
compliquée parce qu'elle est mal conçue : elle est compliquée parce qu'elle est à
l'intersection.** Et sa complexité est de la **répétition, pas de la conception** — quatre
voies identiques de part et d'autre d'une barrière. C'est ce qui fabrique les 67 coupures.

### Ce qui existe, brique par brique

**Brique « isolation + mise à niveau » (§5) — ça existe, et ça porte un nom industriel.**
On l'appelle *convertisseur de signal codeur HTL 24 V → TTL 5 V, isolé, 4 voies, rail DIN*
(NPN **et** PNP, jusqu'à 2 MHz). Fabricants sérieux : **motrona GV210**, **Johannes Hübner**,
**Nidec DSR4** — aucun ne publie ses prix (gamme industrielle sur devis, **prix non lu**).
Les exemplaires à bas prix ne se trouvent que sur Amazon US et AliExpress.
- **Pi-Plates DIGIplate** : la **seule** carte de toute la recherche qui affirme noir sur blanc
  accepter du **NPN comme du PNP** ; isolation 1400 Vpeak entrée↔Pi **et 500 VDC
  canal-à-canal** ; **SPI** (donc pas d'I²C) ; 2 kHz mesuré sur Pi 4. **74,99 $** + 29,99 $
  pour le support rail DIN, site éditeur US → import. Mais elle se monte **sur le Pi**, ce qui
  contredit la décision du 20/08 (carte en bas, près des roues, lien USB).
- **Sequent Microsystems** (16 entrées 60 $, 8 entrées HV 50 $) : **éliminés, I²C uniquement**
  (cf. §6, l'I²C est interdit).
- **Widgetlords PI-SPI-DIN-8DI** : 35,95 $, SPI, opto TLP292-4, mais exige en plus un module
  hôte séparé, et **aucune fréquence documentée**.
- **Modules génériques PC817 en UE** : Kamami (PL) vend des modules **4 et 8 canaux**
  (prix non lu, page non extractible) ; elektroweb.pl 8 canaux 15,50 PLN — **en rupture** ;
  botnroll.pt 9,90 € — **arrêté**.
  ⚠️ **Et la fiche du module polonais confirme noir sur blanc le piège que redoutait le §5** :
  ses **masses sont reliées par des cavaliers d'origine**, l'isolation n'existe qu'après les
  avoir retirés. Un module tout fait n'isole pas parce qu'il s'appelle « isolateur ».

**Brique « comptage » — rien d'utilisable.**
- **Phidgets 1047** : 4 voies quadrature sur USB, **85 $**, **hors stock** au 26/09, **non isolé**.
  Le DAQ1400 (25 $) accepte explicitement NPN/PNP mais **ne fait pas de quadrature**.
- **LS7366R** : compteur quadrature 32 bits SPI, mais c'est un **circuit nu SOIC-14** ; les
  breakouts tout faits n'ont pas pu être atteints (403). Le HCTL-2032 n'a **aucun** breakout.
- **Industriels** : Beckhoff EL1512 = pas de vraie quadrature (compteur + fil de sens),
  **EtherCAT**, 1 kHz ; ADAM-4080 = isolé 2500 V, 50 kHz, mais **compteur simple**, prix sur
  devis ; Brainboxes ED-038 plafonne à **200 Hz** ; Wago 750-637 non documenté.
- **Aucun driver ROS 2 trouvé pour aucun d'entre eux.**

**Brique « tout-en-un » : les automates compacts — ça existe vraiment, et c'est cher.**
- **Revolution Pi RevPi DIO** : **14 entrées 24 V galvaniquement isolées**, configurables en
  **jusqu'à 6 décodeurs de quadrature**, 500 Hz en mode encodeur (largement au-dessus de nos
  30 Hz), anti-rebond réglable. C'est le produit **qui fait le plus exactement le travail** de
  cette carte. **196 € le module seul** (revolutionpi.com) — **et il faut en plus un RevPi Core
  pour l'héberger**. Polarité NPN/PNP non précisée au datasheet.
- **Arduino Portenta Machine Control** : 8 entrées 24 V + **2 canaux encodeur dédiés**,
  **336 € TTC**. **Arduino Opta Lite** : 156 € TTC, aucune fonction compteur documentée.
- **NORVI IIOT-AE03** : 8 entrées 24 V **opto-isolées**, annoncées **« Sink/Source » donc NPN
  accepté** — le seul de la famille à un prix voisin : **84,95 € TTC** (minipc.de, DE). Mais
  **aucun comptage documenté** : il faudrait programmer son ESP32… c'est-à-dire refaire
  exactement ce que le firmware RP2040 fait déjà.
- ⚠️ **Industrial Shields M-Duino** : donné **PNP seulement** par les résumés — ce serait
  **éliminatoire** ici. Non confirmé (site en 403).

**Brique « carte contrôleur ROS toute faite » — toutes éliminées par la puissance.**
Hiwonder (5-12,6 V), Yahboom (12 V max, 79 $), Waveshare General Driver (7-13 V, et
**2 entrées encodeur seulement**, 27,99 $), Husarion CORE2 (6-16 V, **1 A continu / 2 A crête
par moteur**). Ce sont des cartes pour robots de 2 à 5 kg : les MY1016Z demandent 24 V et
~10-20 A. **Aucune n'est isolée.** ODrive S1 (149 €, rupture) est écarté pour une autre
raison, structurelle : **sortie triphasée, brushless uniquement**.

### Le seul vrai candidat — et ce n'est pas une décision d'odométrie

**Basicmicro RoboClaw 2x30A USB V6B — 152,50 € TTC / 128,15 € HT, Botland (PL, UE), en stock,
expédition 24 h** (lu le 26/09/2026). 6-34 V, **30 A continu / 60 A crête par canal**,
**double PID en boucle fermée** (position ET vitesse), entrées **quadrature** jusqu'à
19,6 M pps, **USB + série TTL**, et des drivers ROS 2 existent (`basicmicro/basicmicro_ros2`,
MIT, `ros2_control`).

Il remplacerait **à la fois les DEUX Cytron SmartDrive40** (un par roue) **et** le comptage, et surtout il
fermerait la boucle de vitesse **dans le matériel** au lieu de la faire en Python sur le Pi.
C'est la seule piste de cette recherche qui apporte quelque chose que la carte maison
n'apporte pas.

**Mais trois réserves, dont une bloquante :**
1. **Ses entrées encodeur ne sont PAS isolées** — logique 3,3/5 V à masse commune. Les quatre
   optocoupleurs restent nécessaires **de toute façon**. Le RoboClaw supprime le RP2040
   (~5 €), pas la barrière.
2. **C'est le CHEMIN ROUES.** Changer le driver de puissance déclenche la règle non
   négociable : simulation d'abord, puis protocole caméra roues hors sol, puis revue Opus. Sur
   un robot **actuellement en pièces**, alors que la priorité n° 1 est le test scénique au sol
   **avec le Cytron déjà validé le 2026-07-04**.
3. On perdrait le bénéfice du **Cytron MDDS30 de rechange** présent en stock
   (`inventaire-stock.md` §1.4).

**Donc : instruit à part**, dans [`etude-driver-roues-asservi.md`](etude-driver-roues-asservi.md)
— c'est une décision de *driver de puissance*, pas d'odométrie, et elle a ses propres
verrous de sécurité.

### Conclusion : rien à acheter pour lire les capteurs

**Le plan de la carte ne change pas** — ni le schéma, ni le plan de plaque, ni la
nomenclature. Aucun produit ne réunit capteur 12 V NPN + isolation galvanique +
quadrature à un prix ou à une simplicité supérieurs, et les deux familles qui
s'en approchent échouent chacune sur un point dur : les cartes de loisir n'isolent
jamais, les automates coûtent 85 à 336 € et restent à programmer.

Le seul enseignement qui change quelque chose n'est **pas** dans le périmètre de
cette étude : c'est le **RoboClaw**, qui ne remplace pas la lecture des capteurs mais
**les deux drivers de puissance**. Instruit à part — voir
[`etude-driver-roues-asservi.md`](etude-driver-roues-asservi.md).

> **Sources consultées le 2026-09-26** (prix lus à la source) : botland.store (RoboClaw
> 2x30A V6B), generationrobots.com (Kangaroo x2 : 25,22 € TTC — mais c'est un add-on qui
> exige un Sabertooth/SyRen, que nous n'avons pas), revolutionpi.com (RevPi DIO),
> store.arduino.cc (Opta Lite, Portenta Machine Control), minipc.de (NORVI AE03),
> pi-plates.com (DIGIplate), phidgets.com (1047, DAQ1400), sequentmicrosystems.com,
> widgetlords.com, berrybase.de (RP2040-Zero sans header : **4,90 €**),
> resources.basicmicro.com, beckhoff.com (EL1512), advantech.com (ADAM-4080),
> elektroweb.pl et botnroll.com (modules PC817 génériques), waveshare.com, norvi.io,
> yahboom.net, husarion.com, eu.odriverobotics.com.

## 7. Inconnues à lever

Relevé du 14/07 — **six inconnues levées**, il en reste **trois**, et **plus aucune ne bloque** :

| Cote | Statut | Valeur |
|---|---|---|
| Pas de chaîne | ✅ levé (marquage 428) | 12,7 mm |
| Ø de l'axe + écrou | ✅ mesuré au mètre | **tige filetée M20**, écrou 30 sur plats / 16 de haut |
| Filetage nu au-delà de l'écrou | ✅ mesuré | **~30 mm** (de la visserie peut être ajoutée) |
| L'axe tourne-t-il avec la roue ? | ✅ vérifié au feutre | **oui** — postulat de tout le montage |
| Garde axe → bas de caisse | ✅ mesuré | **30 mm** — ne contraint que la coiffe (R=22), pas le disque |
| Créneau caisse ↔ couronne | ✅ mesuré | **30 mm** — et il est plein à 27,8 |
| Ø de la couronne (donc de la chaîne) | ✅ mesuré | **Ø 110** → chaîne à R=55. Le disque déborde, mais passe **devant** (jupe de 10 mm) |
| Écrou M20 du moyeu | ✅ vérifié | **standard, AVEC rondelle** — la rondelle est la face d'appui de la jupe |
| Épaisseur de cette rondelle | à confirmer | *hyp. 3 mm* — fixe la hauteur de jupe, donc la position du disque |
| Ø extérieur du pneu | à mesurer | *hyp. 250 mm* — convertit les ticks en mètres |
| **Entraxe des deux roues** | à mesurer | `wheel_separation` — indispensable à l'odométrie différentielle |
| Plat du palier : épaisseur + largeur | à mesurer | *hyp. 12 / 32 mm* — la **bride** du support pince dessus |

Fiche de relevé : **`plans/odometrie/MESURES.md`**.

Plus rien ne bloque l'impression du disque. L'épaisseur de la rondelle est la seule cote qui
puisse encore décaler la pièce (2 mm d'erreur sont absorbables, 5 mm non). Le pneu et l'entraxe
des roues sont les **deux seules constantes** qui convertissent les impulsions en mètres et en
radians : fausses, l'odométrie ment silencieusement et nav2 part de travers sans se plaindre.

Contraintes de dimensionnement, toutes **codées en `assert()`** dans
`plans/odometrie/parametres.scad` — une géométrie fausse **refuse de compiler** :
**pas de lecture ≥ 2 × Ø du nez** (sinon le capteur voit deux cibles à la fois), **cible ≥ 3 × Sn**,
**vide entre cibles ≥ 3 × Sn** (sans quoi le capteur reste collé à l'état « métal » et le train
d'impulsions disparaît), la coiffe qui passe sous la caisse, le disque en dedans de l'obstacle
carter/chaîne, et l'encombrement du créneau.

**Géométrie retenue (recalée le 16/08) : 10 cibles à R = 44 mm**, disque **Ø 113 × 12 mm**,
décalé de 10 mm, pas de lecture 27,6 mm (métal 15 / vide 12,6), entraxe des capteurs 45°.
Après décodage ×4 : **19,6 mm de résolution au sol** — suffisant pour nav2 (l'EKF et le lidar
corrigent) et correct pour asservir la vitesse à 20 Hz.

⚠️ La géométrie initiale (15 cibles à R = 65, Ø 155, 13,1 mm/front) a été **contredite par le
réel le 16/08**, disque imprimé en main : il bute sur le **carter du réducteur** — jamais
mesuré, le modèle ne connaissait que la caisse, la couronne et le plan de la chaîne — et la
chaîne traverse bel et bien son plan (le débord estimé était optimiste). Cote relevée disque
en butée : **axe → obstacle le plus proche = 63 mm** (`OBSTACLE_R`, carter et chaîne
confondus), garde retenue 6 mm. Le garde-fou « hors du plan de la chaîne » n'existe plus :
la contrainte est purement **radiale**. Leçon consignée dans `MESURES.md` : une cote
d'environnement vaut une cote de pièce.

Le contraste mérite d'être noté, parce qu'il justifie deux fois le même raisonnement : un disque
résigné à tenir **sous la caisse** aurait été plafonné à R = 25 (4 cibles, 49 mm/front) ; un
disque résigné à rentrer **dans le cercle de la chaîne** aurait été plafonné à R = 50 (9 cibles,
22 mm/front). Dans les deux cas, pas même une impulsion par période de contrôle à 20 Hz :
**inasservissable**. C'est d'avoir cherché la place *à côté* — dans le créneau, puis *devant* le
plan de la chaîne — qui sauve le chantier.

## 8. Plan de mise en œuvre — par étapes, du sûr vers le risqué

L'ordre n'est pas négociable : **on ne grave un PCB que quand on a déjà vu le système
fonctionner.** Le prototype EST le cahier des charges de la carte.

### Étape 1 — Établi, sans robot (zéro risque)

Banc de test : une chute de bois, des **rondelles d'acier vissées tous les 25 mm**, passée à
la main devant deux capteurs. Linéaire au lieu de rotatif, mais ça teste exactement la même
chose — et comme on peut la faire **aller et venir**, ça teste le **sens**, qui est tout
l'enjeu.

Valide : la détection, l'entrefer réel obtenu, la logique inversée, la quadrature, le
décodage ×4, le firmware Pico, le nœud ROS. Tout le logiciel se débogue là, sans robot.

### Étape 2 — Carte dédiée provisoire (plaque à trous)

La même chose soudée sur plaque à trous, avec le **brochage DÉFINITIF** (mêmes GPIO, mêmes
borniers, même ordre des capteurs). Ainsi le firmware et le nœud ROS écrits à l'étape 1 sont
*exactement* ceux qui tourneront sur le PCB : la vérification exécute le même code que la
prod.

Les composants sont les **mêmes qu'au PCB final** (PC817 nus + résistances choisies), pas un
module tout fait : ce qu'on valide sur l'établi est alors *exactement* ce qui sera gravé.

Le schéma KiCad de cette carte est fait et vérifié :
`~/Nextcloud/dev/didier/pcb/kicad/wheel-odometry/` (ERC 0 violation, netlist contrôlée,
plan de câblage plaque à trous dans son `DESIGN.md`).

### Étape 3 — Robot, ROUES HORS SOL, protocole caméra

Roue phonique et support capteurs **imprimés** (`plans/odometrie/`, cf. §3 bis), **roues hors
sol**, webcam USB, captures ffmpeg.

⚠️ **La roue phonique s'imprime en DEUX pièces** (`PIECE="disque"` + `PIECE="jupe"`), et ce
n'est pas un confort : d'un bloc, son moyeu dépasse des deux côtés du disque — c'est une
bobine, aucune orientation ne la pose à plat, et la couronne du Ø 155 imprimerait dans le vide
(Cura, 15/08 : pièce entièrement en rouge, 13 h 22, support désactivé → impression vouée à
l'échec). Coupée dans le plan de la face côté couronne, le disque se pose à plat, sans un seul
support. La coupe ne coûte rien mécaniquement : la jupe ne transmettait déjà aucun couple, tout
passe par l'empreinte hexagonale, et l'écrou M20 de 16 mm traverse les deux pièces empilées —
chacune est entraînée en prise directe.

**16/08 — premier jeu imprimé (Ø 155)… et CONTREDIT PAR LE RÉEL** : gabarit → jupe → disque
dans l'ordre prévu (CR-10, PETG gris Geeetech), mais le disque **bute sur le carter du
réducteur** et la chaîne traverse son plan — il est bon pour le bac (photos de la collision
dans `plans/odometrie/photos/`). Redimensionné le jour même : **Ø 113, 10 cibles,
19,6 mm/front** (cf. §7, cote `OBSTACLE_R = 63` mesurée). Le gabarit, lui, a rendu son
verdict : à `JEU_HEX = 0.4` l'empreinte hexa entre libre avec un léger jeu — passé à
**0.25** pour viser le maillet, **à revalider par le gabarit** avant tout disque. S'ajoute
une **empreinte hexa côté tête** (cibles indexées, serrage sans clé à tenir), disque épaissi
à 12 mm pour l'âme entre les deux poches.

~~⚠️ Le support tôle se fabrique à partir d'un PLAN PAPIER…~~ — **SANS OBJET depuis la
fixation v3 du 16/08** (§3 ter) : plus de tôle, plus de plan papier, plus de cotes de palier.
Le support capteurs est désormais la **patte sous caisse** (`patte-capteur.scad`, ×4),
vissée dans la tôle du fond — vérif visuelle chaîne/corps de capteur roue montée, puis
2 autoperceuses par patte.

Découverte du 2026-08-15, à ne pas reperdre : le **développé exporté était faux de 8 mm** (le
retrait de pli n'était pas déduit), et **la bande de pli rebouchait le dégagement d'axe**. Les
deux sont corrigés, avec un `assert()` qui compare désormais le dessin à la cote qu'il annonce
— jusque-là, le fichier affichait 144,96 en exportant 152,96, et rien ne le contredisait. À
retenir aussi pour le montage : **le pli traverse le dégagement d'axe**, il ne reste que deux
bretelles de ~34 mm, à plier ensemble en une seule passe sous peine de vriller les deux ailes.

C'est ici qu'on mesure **enfin la vraie vitesse pour un PWM donné** — la première mesure
objective du chemin roues depuis le début du projet. Rejouer
`conf/scripts/validate-cmdvel-protocol.sh` en enregistrant l'odométrie en parallèle.

### Étape 4 — PCB KiCad

Seulement là, et seulement si les étapes 1–3 sont vertes. Fente fraisée sous les PC817, Pico
sur **supports tulipe** (un Pico grillé se change en dix secondes dans une loge, sans fer à
souder), **une LED de diagnostic par canal** (on *voit* un capteur mort ou un câble coupé
sans brancher d'ordinateur — utile sur un plateau, et ça alimente le chantier télédiagnostic).

### Étape 5 — Aval (hors périmètre de cette étude)

`ros2_control` / `diff_drive_controller`, EKF `robot_localization` (encodeurs pour la
translation + IMU BNO055 pour le yaw), puis nav2. À noter : **le BNO055 existe déjà dans le
code** (`robot/move/bno_055_extended.py`, `Wheels.set_9dof()`) mais **personne ne l'appelle
en production** — seulement dans `robot/tests/sandbox/`. Vérifier s'il est encore
physiquement sur le robot.

## 9. Nomenclature

### Achat immédiat (étapes 1–3)

| Pièce | Qté | Prix unitaire |
|---|---|---|
| Capteur inductif `LJ12A3-4-Z/BX` **NPN** (TENSTAR ROBOT) | 6 (4 + 2 rechange) | 2,35 € |
| **PC817C DIP-4**, lot de 20 (TriArk) — sert au prototype ET au PCB | 1 lot | 1,33 € |
| Supports tulipe DIP-4 | 4+ | qques centimes |
| ~~Raspberry Pi Pico~~ → **RP2040-Zero** (décision du 02/09) | 2 | ~5 € |
| Plaque à BANDES, ~~borniers à vis~~ → **JST-XH**, résistances 10 kΩ | — | qques € |

> ✅ **Capteurs et optocoupleurs : RIEN À ACHETER.** Les capteurs sont arrivés avec la
> commande du 14/07 (celle des 10,81 € de droits, 3 catégories). Et le 02/09, David a
> trouvé dans son stock un **PC817 DIP-4 traversant** — pattes ressortant bien au dos de
> la plaque, essai fait — **en quantité largement suffisante**, indépendamment du lot
> de 20 de juillet.
>
> ⚠️ **La LETTRE (A/B/C/D) est INDIFFÉRENTE pour cette carte**, contrairement à ce que
> demandait le sélecteur d'achat ci-dessous. La voie injecte 4,9 mA dans la LED de l'opto
> et ne réclame que 0,33 mA en sortie : même un **PC817A** (CTR minimum 80 %) fournit
> 3,9 mA, soit **12 fois trop**, et il resterait de la marge après la perte de CTR du
> vieillissement (~ −50 % sur dix ans). L'exigence « C » était une prudence générale, pas
> un besoin de ce montage. **Ce qui n'est PAS négociable reste le boîtier : DIP-4**, pour
> le support tulipe et le remplacement sans fer à souder dans une loge.

**Lien — celui-ci, et pas un autre** (vendeur **TriArk Electronic**, 4,8/5, 2000+ vendus) :

> ### <https://fr.aliexpress.com/item/1005006281381268.html>
> **PC817C — lot de 20 pièces — 1,33 €** (dégressif : 1,07 € dès 2 lots, 0,80 € dès 5)
> Livraison **gratuite dès 10 € d'achat** → à combiner avec les capteurs (cf. ci-dessous).

⚠️ **LE TITRE DE L'ANNONCE MENT : il annonce « DIP-8 ». C'est un DIP-4.** La photo montre un
boîtier SHARP PC817 à **4 pattes**, et les 271 avis confirment. Ne pas écarter cette annonce à
cause de son titre — l'erreur a déjà été commise une fois (le 14/07, en cherchant le lien perdu,
elle a été rejetée pour ce motif, et il a fallu que David la retrouve lui-même).

⚠️ **Les autres pièges sont, eux, dans le SÉLECTEUR** — jamais dans le titre, même mécanique que
le piège NPN/PNP du capteur :

- **DIP-4, jamais SOP-4.** Le SOP-4 est du CMS : impossible à monter sur un support tulipe, donc
  impossible à remplacer dans une loge sans fer à souder. C'était tout l'argument du choix.
- **PC817C**, pas A/B/D : la lettre est le gain de transfert (CTR).

### Reste à acheter — état au 2026-09-02

> 🔎 **« Et une carte du commerce ? »** — question posée le 26/09, instruite sur cinq
> axes en §6 bis : **rien à acheter**, aucun produit ne réunit capteur 12 V NPN +
> isolation + quadrature à un prix inférieur. Ne pas refaire la recherche, la lire.

> 📋 **Avant de commander, passer par `docs/hardware/inventaire-stock.md` §1.1** : la liste
> ci-dessous y est confrontée au stock ligne à ligne (inventaire du 03/09). Quatre lignes y
> deviennent des *vérifications d'atelier* au lieu d'achats — en particulier les **trois
> lignes JST-XH** (boîtiers et contacts), qui sont probablement couvertes par la boîte à
> connecteurs de David. Chaque ligne évitée, c'est potentiellement 3,60 € de droits de
> catégorie, soit l'ordre de grandeur du composant lui-même.
>
> ⚠️ L'inventaire relève aussi un **écart de comptage sur les capteurs** : 3 sachets scellés
> visibles en vidéo contre 6 annoncés ici. À compter avant de se fier à la marge de rechange.

Ce qui est **déjà là** : capteurs LJ12A3 (×6 — *à recompter, cf. ci-dessus*), **PC817 DIP-4
en stock** (voir l'encadré ci-dessus), plaque à bandes (entamée), disques phoniques imprimés
et garnis.

Ce qui **manque** pour souder la carte. Tout est standard → **une seule commande chez un
distributeur UE** (port unique, zéro douane — cf. la règle ci-dessous) :

| Qté | Pièce | Piège |
|---|---|---|
| 2 | **RP2040-Zero** (Waveshare) | dispo en UE : BerryBase (DE), Botland (PL), Gotronic (FR). **Version SANS header soudé** |
| 2 | Barrette **tulipe 1×9** (sécable) | support du module — c'est ce qui permet de le changer sans fer |
| 2 | Barrette **mâle 1×9** | à souder dans les castellations du Zero |
| 4 | Support **tulipe DIP-4** | idem pour les optos |
| 2 | **JST-XH 4 pts** vertical THT + boîtiers + contacts | pas 2,5 mm — un kit XH couvre tout |
| 1 | **JST-XH 2 pts** vertical THT + boîtier + contacts | entrée 12 V |
| 4 + 4 | R **1,5 kΩ** et R **10 kΩ** 1/4 W | ⚠️ 1,5 k, pas 2,2 k (cf. plus bas) |
| 4 | LED 3 mm | diagnostic, visibles hors boîte |
| 4 + 1 | C **10 nF** céramique + C **100 µF/25 V** radial | |
| 1 | **1N5819** (Schottky DO-41) | ⚠️ le schéma dit `SS14`, qui est un boîtier CMS — acheter du **traversant** |
| 1 | **P6KE15A** ou SA15A (TVS 15 V, DO-41) | ⚠️ idem, `SMAJ15A` au schéma = CMS |
| 1 | **PTC 500 mA** (RXEF050 / MF-R050) | |
| — | Gaine thermo | épissures des capteurs à la bride |

> 🛒 **État au 2026-10-05** (liste confrontée au stock avec David) : **plus rien à
> acheter** — la PTC (F1) est commandée aussi (`RXEF050` radiale). RP2040-Zero : en stock. Supports DIP-4 : tulipes DIP-10 coupées.
> **R série = 2 kΩ au lieu de 1,5 kΩ** (pas de 1,5 k au stock) : 3,7 mA dans la boucle,
> sortie demandée 0,33 mA → marge ×4 même PC817A vieilli de −50 %. Commandés sur
> AliExpress : kit MLCC 50 V (10 nF), TVS P6KE15A et PTC — trois catégories, ~11 € de droits
> acceptés plutôt que d'ouvrir une commande UE pour trois pièces. ⚠️ Le schéma KiCad et
> `DESIGN.md` (dépôt pcb) disent encore 1,5 kΩ.

⚠️ **Ne PAS commander ça sur AliExpress** : une dizaine de catégories tarifaires ×
3,60 € de droits chacune coûterait plus cher que les composants (voir juste en dessous).

### ⚠️ DOUANE — la règle a changé le 1er juillet 2026, et elle change la façon d'acheter

L'UE a **supprimé la franchise de droits** sur les envois de moins de 150 € (la règle *de
minimis*). À la place : un **droit forfaitaire de 3 €** — **par CATÉGORIE TARIFAIRE présente dans
le colis**, pas par article, pas par euro dépensé. Plus la TVA dessus, soit **~3,60 € par
catégorie**.

Constaté sur la commande du 14/07 : 19,18 € de marchandise (capteurs + optocoupleurs +
condensateurs = **3 catégories**) → **10,81 € de droits**. Soit **56 %**. Non pas parce que la
commande était grosse, mais parce qu'elle contenait **trois choses différentes**.

**Conséquence, valable pour tout le projet :**

| | |
|---|---|
| **AliExpress** | uniquement ce dont l'écart de prix justifie l'import — ici, **les capteurs** (2,80 € contre 10–20 € chez un distributeur UE). Une catégorie, 3,60 € de droits, on reste très gagnant. |
| **Distributeur UE** (Reichelt, TME…) | **tout le reste** : résistances, LED, diodes, condensateurs, borniers, supports tulipe, plaque à bandes, Pico. Des composants standards à quelques centimes, où AliExpress n'apporte rien. **Une commande, un port, zéro douane.** |

Le piège : commander les ~8 catégories restantes sur AliExpress coûterait **25 à 30 € de droits**
pour une trentaine d'euros de composants. Ce n'est plus « moins cher », c'est le contraire.

⚠️ **Seuils de port gratuit** : 10 € chez chaque vendeur AliExpress (les articles « Choice » se
groupent). Sinon le port coûte plus cher que les composants.

### PCB final (étape 4)

| Pièce | Qté |
|---|---|
| **PC817C** (DIP-4) + support tulipe | 4 (+ rechanges) |
| Résistances **1,5 kΩ** (série LED, calibrées 12 V) | 4 |
| Résistances 10 kΩ (rappel vers 3,3 V) | 4 |
| **RP2040-Zero** + supports tulipe 1×8 | 1 |
| **JST-XH 4 points** vertical (capteurs, un par ROUE) | 2 |
| **JST-XH 2 points** + fusible réarmable + TVS (entrée 12 V) | 1 |
| LED + résistance (diagnostic) | 4 |
| Disque phonique acier 3 mm, découpe laser — *même géométrie que le disque imprimé validé* | 2 |

⚠️ **Cette table annonçait 2,2 kΩ jusqu'au 2026-09-02** — corrigé : le schéma KiCad et
`DESIGN.md` disent **1,5 kΩ**, avec le calcul (`(12 − 2,0 − 1,2 − 1,5) / 1500 ≈ 4,9 mA`).
Les deux valeurs fonctionneraient, mais une seule doit être écrite. La liste de courses
est la table ci-dessus ; **la valeur qui fait foi est celle du schéma**.

~~Bague de serrage fendue Ø 20 mm~~ — **supprimée** : il n'y a pas d'axe Ø 20 lisse (§2). Le
disque **coiffe l'écrou M20 existant** (§3 bis) et un seul contre-écrou serre l'empilement.
Ce qu'il faut acheter à la place, pour l'étape 3 :

| Pièce | Qté |
|---|---|
| **Écrou M20** + rondelle large M20 (le contre-écrou du disque — *un seul par roue*, l'autre est déjà sur le robot) | 2 + 2 |
| Vis M8×16 tête H **en ACIER ZINGUÉ — jamais inox** (les **cibles**) + écrous M8 normaux + frein-filet | 20 + 20 |
| Impression PETG : 2 roues phoniques (**2 pièces chacune** : disque + jupe — cf. plus bas), 2 supports, 1 banc | — |

## 10. Pédagogie

Une maquette 3D interactive explique le principe (le capteur est fixe, ce sont les dents qui
défilent ; un capteur seul ne connaît pas le sens ; la roue phonique lue à l'horizontale) :
`/home/dadou/capteur-dents.html` — page autonome, à ouvrir dans un navigateur.
