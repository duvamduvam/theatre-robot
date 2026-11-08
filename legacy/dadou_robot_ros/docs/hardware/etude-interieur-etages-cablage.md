# Intérieur du torse : étages coulissants, implantation et passage des câbles

**Étude du 2026-11-06, proposée — c'est l'étape 2 du
[`plan-refonte-electrique.md`](plan-refonte-electrique.md) (« implantation sur papier »), avec
l'ossature de l'étape 3 (cahier de câblage) et le modèle de l'étape 5 (étages).** Elle
part du [`releve-2026-11-05.md`](releve-2026-11-05.md) et des décisions des 05 et 06/11, et
elle ne revient sur aucune. **Rien ici n'est mesuré** : la liste des mesures qui ferment
l'étude est au §7, et aucune plaque ne se découpe avant.

Pièces jointes :

| Fichier | Ce que c'est |
|---|---|
| [`schema-interieur-niveaux.svg`](schema-interieur-niveaux.svg) | le torse en coupe, niveau par niveau, avec les deux colonnes montantes |
| [`cablage/bornier-distribution.png`](cablage/bornier-distribution.png) | **le plan simple** : une ligne par tension, borniers verts 5,08 et cosses à vis, généré par `cablage/schema_bornier.py` depuis le cahier ; demandé par David le 07/11, à préférer pour lire la distribution |
| [`cablage/schema-alim.svg`](cablage/schema-alim.svg) | la distribution d'énergie câble par câble, plus et masses, générée depuis le cahier par `cablage/schema_alim.py` ; pointillés = câbles absents du cahier, proposés le 07/11 |
| [`cablage/schema-dessus.svg`](cablage/schema-dessus.svg) | les trois platines de distribution vues de dessus, à l'échelle, avec les 39 lignes de puissance et de masse ; générée par `cablage/schema_dessus.py` |
| [`cablage/cahier-cablage.csv`](cablage/cahier-cablage.csv) | **le cahier de câblage** : 74 fils, un par ligne, dérivés des connecteurs des 5 cartes ; `cablage/check_cablage.py` vérifie section contre fusible (0 erreur, 66 longueurs à mesurer) |
| `~/Nextcloud/dev/didier/plans/elec/etages/` (dépôt `didier`, hors de ce dépôt) | le modèle paramétrique OpenSCAD des plaques et des rails, rendus et DXF de démonstration |

---

## 0 bis. Cadre de l'étude complète — semaine du 10/11 (David, 08/11)

**Commande de David.** « Ça doit être super clean, c'est un peu ma carte de visite. Pro et
design. » L'intérieur de Didier se montre : à un technicien de salle, à un partenaire, en
photo. L'étude complète livre donc **des visuels de toute l'organisation interne**, pas
seulement des cotes. Trois exigences nouvelles s'ajoutent au cadre du §1, sans en retirer :

1. **Propre à montrer.** Aucun fil en l'air, aucune surlongueur lovée, aucune épissure :
   goulottes ou peignes imprimés dans les deux colonnes, faisceaux gainés, une couleur par
   tension (§5.3), étiquette Marklife à chaque bout, visserie et entretoises d'une seule
   famille, cartes alignées sur une même trame. Ce qui n'est pas beau est suspect : un
   faisceau désordonné cache toujours un fil qu'on ne sait plus suivre.
2. **Maintenable seul, sans démonter** (règle 6 du plan, grille §2 bis) : l'implantation est
   déroulée contre la grille avant d'être figée. Accès technique porte ouverte seulement ;
   en façade : coup-de-poing, armement, général, prise de charge, voltmètre.
3. **LED de contrôle en couleur**, lisibles porte ouverte, pour voir d'un coup d'œil ce qui
   est alimenté : **une LED par rail sur les boîtes de distribution**, dans la couleur du
   code des fils (rouge 24 V permanent, orange 24 V moteurs, jaune 12 V, violet 12 V audio,
   bleu 5 V contrôle et 5 V vision), chacune derrière son fusible — une LED éteinte = fusible
   sauté ou domaine isolé. Plus deux LED d'état sur la carte Sécurité : **chaîne d'arrêt armée**
   (vert) / **arrêt** (rouge), et **vie du Pi 4** (clignotant). Sur 24 V, résistance série
   calculée pour 2 mA (≈ 12 kΩ, 0,06 W) ; LED 3 mm en façade des boîtes, perçage prévu dans le
   modèle `plans/elec/bornier-distribution`. Rien de plus : une rangée de LED qui clignotent
   sans raison n'est plus un tableau de bord.

**Étages : PMMA coulé 5 mm fraisé à la CNC** (David, 08/11 — change l'avis D2 du §4.3, qui
préférait le laser). Conséquences : rayons intérieurs ≥ rayon de fraise (3 mm, à mettre en
paramètre du modèle), contour et trous en une passe, plaque bridée sur martyr ; **la CNC
d'eMode fait 300 × 180 mm, une plaque de 212 × 167 y entre de justesse** — à confirmer avec
la machine réelle avant de dessiner la plaque au maximum des pans. PMMA coulé obligatoire
(l'extrudé fond et colle à la fraise).

**Livrables de l'étude complète**, tous dans ce dossier et `plans/elec/` :

| Livrable | Forme | Outil |
|---|---|---|
| Vue éclatée du torse : 4 niveaux + porte, chaque élément à sa place | rendu 3D | OpenSCAD, modèle `etages/etage.scad` étendu en « montage complet » avec fantômes de tous les éléments du §2 |
| Une vue de dessus par niveau, cotée, avec chemins de câbles et colonnes | PNG + DXF | idem, projection par niveau |
| Façade et porte ouverte : ce qu'on voit, ce qu'on touche (interrupteurs, LED, fusibles, ports) | dessin 2D | SVG généré, comme `cablage/bornier-distribution.svg` |
| Schéma de câblage par niveau, dérivé du cahier (repères, couleurs, sections) | SVG | `cablage/schema_*.py` existants, étendus |
| Grille de maintenabilité remplie, geste par geste | tableau | plan §2 bis |
| Par carte : bord de sortie de chaque connecteur, droit ou coudé, hauteur libre | tableau | entrée de la session de corrections PCB |
| Fichiers de découpe des étages | DXF | `etage.scad`, après mesures et gabarit carton |

**Préalable non négociable : les mesures M1-M13 du §7.** Sans elles, les visuels seraient
des hypothèses dessinées proprement, ce qui est pire qu'un croquis. La séance commence par
le robot, pas par l'écran. Une feuille de mesures imprimable est à produire en premier.

## 0. En bref

1. **Cadre fixé par David le 06/11** (§1) : toute la hauteur du torse est reprise, de la
   tête aux roues ; le torse est un **octogone** ; les plaques restent dans les **cinq pans
   fixes** ; elles **coulissent** sur rails et sortent **par la porte audio**.
2. **Une fonction par niveau** (§3) : caisse basse = 24 V et moteurs ; coffre = conversion,
   distribution, réseau, odométrie ; étage milieu = audio et modules ; étage haut = logique et
   sécurité, les deux Pi suspendus dessous. Tout ce qui n'est pas sur une plaque est **debout
   sur un pan**, sur un support imprimé : plus rien ne tient par ses fils.
3. **Trois familles de câbles, deux colonnes montantes** dans les coins arrière, l'audio par
   la charnière seulement (§5). Chaque étage se sort en débranchant des fiches qui regardent
   la porte ; les colonnes passent dans des encoches et ne touchent jamais la plaque.
4. **Masse en étoile** sur une barre dans le coffre, une cosse par domaine (§6) : c'est la
   réponse aux quatre questions laissées ouvertes le 05/11.
5. **Deux incohérences à lever par la mesure** avant tout dessin définitif (§7) : la plaque
   actuelle fait 212 mm de large alors qu'un pan mesuré fait 130 mm utiles (les rails iront
   peut-être sur les montants bois, pas sur les pans) ; et 167 × 212 n'est pas la cote d'un
   octogone régulier.

---

## 1. Cadre : ce que David a tranché le 06/11 (ne pas re-trancher)

| Question | Réponse de David | Conséquence |
|---|---|---|
| Périmètre | **Tout l'intérieur** : étages, coffre des alims, caisse basse | le pack devient extractible, le relais 40 A et le fusible général ont une place, les convertisseurs un support |
| Forme | **Octogone**, pas hexagone — « c'est un octogone, pardon » | `overview.md` corrigé le même jour ; 8 pans de sapin 18 mm, dont **3 pans avant = la porte audio** |
| Emprise | **Même emprise qu'aujourd'hui, dans l'octogone, sans dépasser les 5 pans** | plaque = contour des 5 pans fixes, bord droit au bout des pans latéraux, jamais dans le volume de la porte |
| Démontage | **Coulissant sur rails** | deux rails sur les deux supports verticaux parallèles à l'axe de sortie ; la plaque flotte, rien de vissé dans le plexi |
| Ouverture | **Par la porte audio** | les fiches des cartes regardent la porte ; le faisceau audio de la porte doit laisser passer une plaque |
| Câbles | **De la tête aux roues** | colonnes jusqu'au cou et aux épaules, boucle de service pour la rotation du tambour de la bouche |

Décisions antérieures qui s'appliquent telles quelles : pile **Puissance sur Sécurité** en
haut, **Moteurs en zone audio** avec la carte Audio, nappe Sécurité-Moteurs < 30 cm (05/11) ;
**ASME (bras et cou) sur le pack 24 V** après le relais 40 A ; **SD-150B-12 dédiée à l'audio**,
verticale sur la paroi du coffre près de la porte ; SD-50B-12 gardée pour les yeux et la
boucle d'arrêt ; deux SD-50B-5, une par Pi (12/09) ; refonte **avant** tout roulage au sol.

---

## 2. Ce qu'il faut loger

Tout ce qui doit avoir une place, avec ce qu'on sait de son encombrement. Une case vide est
une mesure à faire (§7). « Niveau » est la proposition du §3.

| Élément | Encombrement connu | Fixation prévue | Niveau |
|---|---|---|---|
| Pack 18650 + BMS Daly | **non mesuré** ; 7S probable, chimie à lire | tiroir ou berceau extractible | caisse basse |
| Fusible général + relais 40 A + barre 24 V | relais : modèle **non lu**, courant de bobine à mesurer | platine imprimée près du pack | caisse basse |
| SmartDrive40 ×2 | une carte lue, l'autre devinée ; bornier vert | vissées sur platine, câble de commande blindé | caisse basse |
| Chargeur Victron Blue Smart 24/5 IP65 | boîtier à liseré bleu, posé en vrac | fixé, **prise de charge en panneau** | caisse basse |
| Capteurs d'odométrie LJ18A3 ×2 + disques | berceau v5.1 dessiné (M18) | sur les paliers | caisse basse |
| SD-50B-5 ×2, SD-50B-12 | 159 × 97 × 38 chacune (fiche) | **debout**, 38 mm de pan chacune, support `support-sd50b5` (2 joues, PETG) | coffre |
| SD-150B-12 (à acheter) | 199 × 110 × 50 (fiche) | debout, même principe, support à dessiner (4 cm plus long) | coffre, paroi côté porte |
| Boîte de distribution du coffre (24 V permanent, 12 V, 5 V) | décidé par David le 07/11 : support imprimé comme la boîte grise, fils soudés au dos, borniers verts ; porte-fusible 5×20 de panneau à choisir | `plans/elec/bornier-distribution`, 126,2 × 133,25 × 30 | coffre |
| Boîte de distribution moteurs (24 V après relais) | même principe ; les 25 A passent par des cosses M5 et un fusible à lame en ligne | `plans/elec/bornier-distribution`, 86,2 × 89 × 30 | caisse basse |
| Routeur RUT955 | support en conception (`plans/supports/support-teltonika-rut955`), face avant vers la porte | debout sur la tranche | coffre |
| Carte Odométrie | 92 × 84 | entretoises M3 sur le coffre (décision 02/09) | coffre |
| Carte Audio | 100 × 100, entraxe 90 × 90 | entretoises M3 traversantes | étage milieu |
| Carte Moteurs | 100 × 100 | idem, **à l'aplomb de la pile** | étage milieu |
| VoiceTone C1 | boîtier à molettes, **non mesuré** | support imprimé sur un pan, molettes accessibles | pan, hauteur milieu |
| Récepteur Shure BLX4 | demi-rack, support `support-blx` déjà dessiné (2024) | sur un pan | pan, hauteur milieu |
| Pile Puissance sur Sécurité | 2 × 100 × 100, hauteur de pile **non mesurée** (modules enfichés, entretoises) | entretoises M3 traversantes | étage haut |
| Pi 4 + Pi 5 | plaque mère 109 × 172, **≥ 45 mm libres dessous** (`support-rpi4-rpi5`) | suspendus sous la plaque, traîneaux, poignées vers la porte | sous l'étage haut |
| Lidar 2D (décidé 02/11, à acheter) | support `support-lidar-c1` existe | à placer — **emplacement non décidé** | hors torse probablement |
| Mixette, ampli Focal, 3 HP, isolateur | sur la porte, inchangés | — | porte |
| Dos : 2 boutons + 2 LED ; coup-de-poing ; bouton d'armement | **emplacements à trouver** pour les deux derniers | — | pans |

**Budget de place, ordre de grandeur.** Un étage de 212 × 167 reçoit deux cartes de 100 côte
à côte, avec 4 à 10 mm entre elles selon la largeur réelle : c'est le point D3, à trancher au
gabarit carton. Un pan utile de 130 mm (mesure du 12/09) prend **trois convertisseurs debout**
(3 × 38 = 114 mm) qui avancent de 97 mm dans le volume : les quatre convertisseurs tiennent
sur deux pans du coffre. Rien n'est donc impossible en surface ; ce sont les **hauteurs
libres** qui ne sont pas connues (§7).

---

## 3. Implantation niveau par niveau

Voir [`schema-interieur-niveaux.svg`](schema-interieur-niveaux.svg). Du bas vers le haut, du
plus lourd et du plus bruyant au plus fragile.

### 3.1 Caisse basse — 24 V et moteurs, rien d'autre

- **Pack et BMS extractibles** sans toucher au reste : tiroir ou berceau à poignée, sortie
  par l'ouverture de la caisse (laquelle : mesure M12). Le BMS reste accessible (Bluetooth
  pour l'indicateur de batterie, branche A0 de l'étude odométrie).
- **Fusible général** sur le + du pack, puis **relais 40 A** au plus près, sur une platine
  imprimée : le chemin pack → fusible → relais → barre « 24 V moteurs » fait quelques
  centimètres de câble de 6 mm².
- **Deux barres 24 V** : *permanente* (avant le relais : convertisseurs, routeur, chargeur) et
  *moteurs* (après le relais : SmartDrive ×2, ASME ×3). Tout ce qui doit survivre à un arrêt
  d'urgence est sur la permanente ; tout ce qui bouge est sur l'autre. **C'est la règle qui
  rend les bras et le cou coupés par le coup-de-poing** — ils ne l'ont jamais été.
- SmartDrive40 ×2 sur platine, **câble de commande blindé à embouts** à la place du câble
  réseau dégainé (anomalie 1 du relevé). La borne à leviers flottante et le connecteur de
  panneau pendant disparaissent (anomalie 2).
- Chargeur fixé, **prise de charge en panneau** : on ne rouvre plus la caisse pour charger.
- Le boîtier perforé sombre non identifié : s'il est un convertisseur, il monte au coffre
  (mesure M4 du relevé).

### 3.2 Coffre des alims — conversion, distribution, réseau, odométrie

- Les **quatre convertisseurs debout sur les pans**, chacun sur deux joues imprimées (le
  support SD-50B-5 existe ; à décliner pour la SD-150). La **SD-150B-12 sur la paroi côté
  porte**, au plus près de l'ampli (décision du 06/11). Les trois SD-50 sur le pan opposé ou
  le pan arrière : loin de l'audio.
- **Bloc 24 V permanent** : porte-fusibles à lames, une voie par convertisseur et une pour le
  routeur, avec la **barre de masse en étoile** à côté (§6).
- Routeur sur son nouveau support, **deux RJ45 branchables**, face avant vers la porte.
- Carte Odométrie sur entretoises, près du passe-fil des capteurs (ses deux câbles descendent
  aux roues).
- Le **bornier gris imprimé disparaît** : ses départs 12 V et 5 V sont repris par les fusibles
  de la carte Puissance, alimentée par un seul tronc de 6 fils (J20).
- **Plancher du coffre : trois passe-fils à œillet** (colonne puissance, colonne logique,
  capteurs d'odométrie). Les surlongueurs lovées sous l'étage disparaissent : chaque fil est
  coupé à la longueur du cahier.

### 3.3 Étage milieu — audio et modules

- **Carte Moteurs à l'aplomb de la pile** (nappe Sécurité-Moteurs verticale, < 30 cm) ;
  **carte Audio côté charnière** (son 12 V et ses RCA sortent par là).
- **VoiceTone C1 et BLX4 sur les pans**, pas sur la plaque : la plaque est pleine avec deux
  cartes, et ces deux appareils ont des molettes et des antennes qu'il faut atteindre. Le
  VoiceTone perd sa sangle ; le support BLX4 dessiné en 2024 se réutilise s'il tient le
  récepteur à la bonne hauteur.
- L'abaisseur LM2596 de l'ancienne carte disparaît (prévu).

### 3.4 Étage haut — logique et sécurité

- **Pile Puissance sur Sécurité** sur quatre entretoises traversantes, fusibles et LED
  visibles à travers le plexi.
- **Les deux Pi sous la plaque**, sur le support à traîneaux déjà conçu : ses six vis à bois
  deviennent des M3 traversants, les poignées sortent **côté porte**. La **nappe GPIO** monte
  par une lumière de la plaque jusqu'à J1 de la carte Sécurité (repère rouge = broche 1 des
  deux côtés : incident du 04/11).
- **Hauteur nécessaire** : 45 mm sous la plaque (ventirad) + 5 mm de plaque + la hauteur de la
  pile avec ses modules enfichés (non mesurée). C'est le niveau le plus contraint : mesure M5.

### 3.5 Tête, cou, bras

- Les câbles de la tête (servos des yeux, rubans LED, ReSpeaker, caméra d'essai) montent par
  les colonnes jusqu'à la tablette blanche, puis **le long de l'arceau sous gaine tressée**
  avec un serre-câble tous les 10 cm. Plus de torsades libres le long du montant.
- **Le tambour de la bouche tourne** (ASME du cou) et porte les panneaux de LED de la bouche :
  le câble des LED et le signal data traversent une pièce mobile. **Boucle de service**
  dimensionnée sur la course angulaire réelle du cou — qui n'est **limitée nulle part dans le
  logiciel** (étude actionneurs, point ③). Deux solutions, à trancher sur mesure M10 : limite
  d'angle logicielle + boucle, ou bague collectrice si la course doit rester libre.
- **Les ASME des bras** reçoivent leur 24 V de la caisse basse par la colonne puissance, et
  leur signal de la carte Moteurs par la colonne logique ; les deux arrivent à l'épaule en
  boucle de service autour du pivot. Le **fil rouge** du connecteur 3 points des ASME **reste en
  l'air** (sortie 5 V, incident du 03/11). Le second connecteur des ASME (retour de position
  magnétique) est à identifier au passage : c'est un câble gratuit vers la détection de blocage.

### 3.6 Porte audio

Inchangée. Le faisceau de la porte (12 V audio, RCA mixette, USB Pi 5 → mixette, HP) passe la
charnière **dans une seule gaine**, boucle de service et serre-câble de chaque côté. Il doit
**laisser passer une plaque qui sort** : la gaine se fixe en haut ou en bas de la charnière,
pas à hauteur des étages.

---

## 4. Les étages : conception

### 4.1 Forme

Le contour est celui des **cinq pans fixes** : pan arrière, deux pans diagonaux arrière, deux
pans latéraux, et un **bord avant droit au bout des pans latéraux**. Rien ne dépasse dans le
volume de la porte, même porte fermée. Deux **encoches** semi-circulaires au milieu des pans
diagonaux reçoivent les colonnes montantes (gaine de 20 mm). Angles arrondis R4 : le PMMA
part en fissure sur un angle vif.

Le modèle (`plans/elec/etages/etage.scad`) est entièrement paramétrique : largeur entre
supports, profondeur des diagonales, profondeur de plaque, et une liste de cartes et de
passages par niveau. Ses `assert` refusent une plaque où deux cartes ne tiennent pas, un trou
hors plaque, ou un rail plus long que son support. Il produit le DXF de découpe.

### 4.2 Rails et tenue

- **Deux rails en U**, PETG, vissés au bois par trois vis Ø4 × 20 max (sapin 18 mm, jamais
  traversé). Gorge = épaisseur de plaque + 0,8 mm, **butée arrière fermée** : c'est elle qui
  fixe la position de la plaque, pas le pan arrière (3 mm de retrait). Entrée chanfreinée
  côté porte pour présenter la plaque seul, à genoux devant le robot.
- **Verrou avant** : une vis moletée M3 dans un écrou piégé **du rail** (pas de filetage dans
  le plexi) traverse un trou à jeu de la plaque ; ou un loquet imprimé qui se rabat devant le
  bord. Mode spectacle : la plaque ne peut pas avancer sous une vibration.
- **Sur quoi vissés** : les deux supports verticaux parallèles à l'axe de sortie. Pans latéraux
  si la plaque les touche, **montants bois intérieurs** sinon — c'est l'incohérence n° 1 du
  §7, que seule la mesure M1 lève.
- **Fixation des cartes et des supports sur la plaque** : trous Ø3,4 à jeu, entretoises M3,
  **rondelles larges des deux côtés**, écrous nylstop, **pas de serrage fort**. Jamais de vis à
  bois, jamais de taraudage dans le plexi.

### 4.3 Matière — D2, avis

**PMMA coulé 5 mm, découpé au laser (eMode, Cholet), pour la plaque d'essai.** Raisons : la
plaque est une **tablette qui flotte dans deux rails**, elle ne tient aucun effort de
structure ; le laser fait contour, encoches, lumières et 30 trous en une passe, bords propres ;
la transparence montre fusibles et LED ; prix de matière lu le 05/11 (plan §5 bis). Le
polycarbonate encaisse mieux les chocs mais se fraise plutôt qu'il ne se lase (fumées), et
la CNC d'eMode (300 × 180 mm) prend une plaque de 212 × 167 de justesse : **à garder en repli
si une plaque PMMA casse** aux essais de roulage. Rails en PETG, pas en PLA : les
convertisseurs chauffent à 60 °C à proximité.

### 4.4 Hauteur entre étages

À fixer par les mesures M5 et M6. Ordre de grandeur des besoins : étage haut ≥ 45 (Pi) + 5 +
hauteur de pile ; étage milieu ≥ hauteur des modules PCA9685 enfichés + fiches 2EDG debout ;
au-dessus du coffre, la hauteur des convertisseurs debout (159, ou 199 pour la SD-150) décide
de l'altitude de l'étage milieu. **Si la SD-150 debout ne passe pas sous l'étage milieu, elle
se couche** sur son flanc (support à 2 joues identique, tourné).

---

## 5. Câbles

### 5.1 Trois familles, deux colonnes

| Famille | Ce qu'elle porte | Chemin |
|---|---|---|
| **Puissance** (rouge) | 24 V permanent et moteurs, 24 V des ASME, 12 V, 5 V, rubans LED, tronc J20 | **colonne puissance** : coin arrière **opposé à la charnière** de la porte |
| **Logique** (bleu) | bobine du relais 40 A, boucle du coup-de-poing, PWM des SmartDrive, signaux servo, USB, RJ45, nappe Sécurité-Moteurs | **colonne logique** : l'autre coin arrière |
| **Audio** (violet) | 12 V audio, RCA, USB mixette, HP, antennes | **jamais en colonne** : du coffre à la porte par la charnière ; les coaxiaux d'antenne seuls sous clips le long d'une paroi |

Quand deux familles se croisent, **à angle droit**, jamais en parallèle sur plus de quelques
centimètres. Les deux paires de sécurité (bobine du relais, boucle du coup-de-poing) sont
**torsadées, étiquetées, et leur débranchement fait partie du protocole caméra**.

### 5.2 Sortir un étage

Règle retenue, la plus simple : **les embases des cartes sont les connecteurs de l'étage** et
**regardent toutes la porte**. Le faisceau arrive des colonnes, longe le pan jusqu'au bord
avant, et ses fiches 2EDG se branchent sur les cartes ; chaque fiche est **retenue au pan par
un serre-câble** à 5 cm, pour qu'on ne puisse pas tirer la plaque sans l'avoir débranchée. Les
ports des Pi regardent aussi la porte (traîneaux). Pour sortir un étage : ouvrir la porte,
débrancher ce qui est devant soi, dévisser la vis moletée, tirer. **Aucun connecteur
intermédiaire** : chaque connecteur en plus est une panne possible.

Exception : la **nappe Sécurité-Moteurs** relie deux étages entre eux. Elle descend
verticalement entre les deux plaques, à l'aplomb des deux cartes, avec 5 cm de mou ; elle se
débranche côté Moteurs pour sortir l'étage milieu, côté Sécurité pour l'étage haut. Si sa
longueur mesurée dépasse 25 cm, D5 (échange des broches 7 et 8) se fait avant la commande.

### 5.3 Le cahier de câblage

[`cablage/cahier-cablage.csv`](cablage/cahier-cablage.csv) : **74 lignes**, une par fil,
colonnes du plan (repère, de, à, famille, tension, section, fusible, connecteur, chemin,
longueur, couleur, statut, note). Les fils viennent des connecteurs des cinq cartes KiCad
(relevés fichier par fichier le 06/11) et des appareils du relevé. Repères : `P` puissance,
`L` logique, `A` audio, `G` masses.

Ce qu'il fixe déjà, et qui ne dépend d'aucune mesure :

- **chaque fil de puissance a son fusible et sa section** : `check_cablage.py` les compare
  (table section/calibre conservatrice, coffre en bois non ventilé) et rougit sur une section
  trop faible ou un fusible manquant — vérifié par mutation ;
- les **fusibles amont** du 12 V (15 A) et du 5 V (10 A) au coffre (D8) ;
- **JP1 ouvert, V+ des yeux par J28** : le cavalier est limité à 3 A ;
- **J36, J37, J38 ne servent plus** aux ASME, qui partent de la barre 24 V moteurs ; leur
  sérigraphie se renomme après le protocole caméra, pas avant ;
- **une couleur par tension** (anomalie 8 du relevé) :

| Tension | Couleur du + | Retour |
|---|---|---|
| 24 V permanent | rouge | noir |
| 24 V moteurs (après relais) | orange | noir |
| 12 V | jaune | noir |
| 12 V audio | violet | noir |
| 5 V | bleu | noir |
| signaux | gris / blanc | — |
| audio | coaxial noir | blindage = masse audio seulement |

Le repère du cahier va sur une étiquette Marklife à chaque bout (15 s entre deux étiquettes,
sinon elle cale). Le script produira la liste d'étiquettes quand les longueurs seront là.

Ce qui manque au cahier et ne se devine pas : **66 longueurs** (après le gabarit carton, ruban
à mesurer en suivant le chemin réel), la tension d'alimentation du BLX4, la polarité du jack
du VoiceTone, le courant du klaxon, le modèle du relais 40 A et de son courant de bobine.

---

## 6. La masse en étoile — réponse aux quatre questions du 05/11

Proposition : **une barre de masse dans le coffre**, à côté du bloc 24 V, **une cosse par
domaine**, et aucun autre chemin de retour.

| Question du relevé §5.3 | Réponse proposée |
|---|---|
| Les sorties des Mean Well sont isolées : relie-t-on leur « − » à celui de la batterie, et où ? | **Oui, chacune par un seul fil à la barre.** Une sortie isolée laissée flottante prend un potentiel au hasard (fuites, ESD) ; référencée en un seul point, elle n'a pas de boucle. Le « − » de la batterie (sortie BMS) arrive aussi à la barre, par un seul câble de 6 mm². |
| La carte Odométrie garde une barrière GND / GNDPWR ; une barre unique la court-circuite-t-elle ? | **Non, tant que ses deux côtés ne se rejoignent qu'à la barre.** Son 12 V capteurs vient de la SD-50B-12 et son USB du Pi 4, tous deux du domaine contrôle : la barrière reste utile contre le bruit des capteurs sur 2 m de câble, et la seule jonction est l'étoile, loin de la carte. Aucun fil GND ↔ GNDPWR sur la carte ni dans le faisceau. |
| La « masse du 12 V » | C'est le « − » de la SD-50B-12 : **une cosse à la barre**, et le GND de J20 revient de la pile par deux conducteurs du tronc — pas par la nappe, pas par un châssis. |
| Le Pi 5 relié en USB à la mixette donne à l'audio un retour qui ne passe pas par le fil prévu | **On l'accepte et on le rend unique** : le Pi 5 (SD-50B-5 n° 1) et l'audio (SD-150B-12) forment **un seul domaine « vision-audio »** — c'est la topologie du 12/09. Leurs deux « − » vont à la barre ; le blindage des RCA et l'USB ne forment une boucle que si un **autre** fil de masse relie l'audio au reste : il ne doit pas y en avoir (pas de masse par l'ampli vers la tôle, pas de cosse « GND » du faisceau HP vers une barre). |

Les domaines, et leur unique cosse chacun : pack ; **contrôle** (SD-50B-5 n° 2, SD-50B-12) ;
**vision-audio** (SD-50B-5 n° 1, SD-150B-12) ; **moteurs** (barre « − » des SmartDrive, un
seul câble vers l'étoile). Le bois ne conduit pas ; l'arceau d'acier de la tête et la tôle de la
caisse ne sont reliés à rien et doivent le rester.

**À relire par un œil indépendant avant câblage** : c'est de la masse et de l'audio, les deux
sujets où une bonne intention refait la boucle qu'elle voulait supprimer. **À mesurer après** :
le ronflement avant/après (étape 8 du plan), et le bruit des moteurs, jamais mesuré.

---

## 7 bis. Mesures relevées par David le 08/11

| Mesure | Valeur | Conséquence |
|---|---|---|
| Épaisseur du bois | **18 mm** | — |
| Largeur d'un pan | **145 mm à l'extérieur, 130 à l'intérieur** | 145 − 2 × 18 × tan 22,5° = 130,1 : **octogone régulier**, angles de 135° entre pans, coupes à 22,5° (M2 résolu par le calcul) |
| Hauteur du torse | **550 mm** | — |
| Étages | **étage 1 à 320 mm, étage 2 à 430 mm, mesurés depuis le haut du cadre métallique** (David, 08/11) | 110 mm entre les deux étages ; l'origine est le haut du cadre en métal, pas le bas du torse |
| Charnière de la porte | **côté gauche** | M7 ; vue supposée de face, à confirmer vue de l'intérieur |
| Ouverture de la porte | **318 mm** (M4) | la plaque de 311,8 passe avec ~3 mm par côté : **aucun faisceau ni rail ne doit empiéter sur l'ouverture** côté charnière ; à vérifier au gabarit carton |
| Coffre | **550 mm = tout le volume du torse en bois** (David, 08/11) | trois zones au-dessus du cadre métallique : **0 → 320 mm** sous l'étage 1, **320 → 430 mm** entre étages (110 mm, cartes et modules), **430 → 550 mm** au-dessus de l'étage 2 (120 mm). ⚠️ **Corrigé par David le 08/11 : les convertisseurs sont DANS LE CADRE MÉTALLIQUE**, avec le pack et les SmartDrive, pas dans le torse. Conséquences : la SD-150B-12 (199 × 110 × 50) et la boîte de distribution du coffre doivent tenir dans le cadre (cotes intérieures du cadre **non relevées**). **Bas du torse (zone 0 → 320) : le départ des alimentations** (David, 08/11) — c'est là que va la boîte de distribution du coffre (`plans/elec/bornier-distribution`), à la place du bornier gris, alimentée par les convertisseurs du cadre juste dessous : trajets courts, fusibles et LED de contrôle à hauteur de main porte ouverte |
| Dessus de l'étage 2 | photos existantes | `docs/pictures/robot-2026-11-05/`, à relire pour la tablette et le passage du cou |
| Pack batterie | **280 mm × 100 mm de profondeur ; hauteur ≈ hauteur d'une 18650 + 1 cm, soit ≈ 75 mm** (M12, estimation de David) | cellules debout (65 mm) : l'empreinte loge ~15 × 5 cellules, compatible avec un 7S10P (70 cellules) — à confirmer en comptant. Prévoir 85 mm de hauteur libre pour le tiroir. Sortie du pack non relevée |
| Récepteur BLX4 | **alimenté par le convertisseur 12 V** (M13) | 12 V, départ J8 de la carte Audio (cahier P32) |
| Moteurs de roues | **250 W chacun** (David : choisis pour limiter la vitesse) | ≈ 10,4 A nominal par moteur sous 24 V, ≈ 21 A pour les deux ; usage courant du pack ≈ 31 A, pire cumul ≈ 51 A. Le fusible général de 40 A (temporisé) et 25 A par SmartDrive restent cohérents ; la mesure roues hors sol reste à faire pour les pointes de démarrage et le blocage |

Géométrie calculée (intérieur, bois à bois) : **313,8 mm entre pans latéraux**, 339,7 mm entre
coins, pans diagonaux arrière de 91,9 mm de profondeur, pans latéraux utiles de 130 mm.
**Plaque d'étage : 311,8 × 218,9 mm** (modèle `plans/elec/etages`, au lieu de 212 × 167).

Deux points ouverts que ces chiffres font apparaître :
1. ~~M1~~ **Réglé le 08/11 : l'étage actuel repose sur des supports imprimés en 3D**, d'où ses
   212 mm. Ils disparaissent avec la refonte : la nouvelle plaque va bois à bois, portée par
   les rails vissés sur les pans latéraux. La largeur utile est bien 313,8 mm.
2. ~~CNC trop petite~~ **Réglé le 08/11 : CNC du frère de David, 1500 × 1500 mm.** Toutes les
   plaques d'une pièce, et les 4 niveaux tiennent sur une seule plaque de PMMA (chute minimale).
   **La machine se pilote avec CNCjs, qui envoie du G-code** : le modèle sort du DXF, il faut
   donc une étape de FAO (DXF → G-code, avec la fraise, les passes, les attaches et l'origine)
   faite par le frère de David, ou générée par nous une fois connus le contrôleur (GRBL ?),
   la fraise et l'origine machine. PMMA coulé jamais testé sur cette machine : si besoin,
   David achète une **fraise 1 dent (« O-flute ») spéciale acrylique** ; rayon des coins
   intérieurs ≥ rayon de cette fraise (paramètre `R_COIN`). ⚠️ **Lentement ne veut pas dire
   mieux** : une avance trop faible fait frotter la fraise, le PMMA chauffe et fond. Ce qui
   compte, c'est la vitesse de broche et l'avance réglées ensemble, avec plusieurs passes peu
   profondes. Faire un essai sur une chute avant la vraie plaque.

## 7. Les mesures qui ferment l'étude

Liste fermée. Les cinq premières décident de la forme des plaques ; sans elles, rien ne se
dessine. Prendre chaque cote **en haut et en bas** du niveau : un torse en sapin n'est pas
d'équerre.

| # | Quoi | Sert à |
|---|---|---|
| M1 | **Sur quoi s'appuie la plaque actuelle** : les pans latéraux ou des montants bois intérieurs ? Largeur bois à bois entre ces deux supports, à chaque niveau | forme, rails — lève l'incohérence n° 1 (pan 130 utile contre plaque 212) |
| M2 | Profondeur des pans diagonaux arrière (projection sur l'axe de la porte) et **leur angle** | contour (45° supposé) — lève l'incohérence n° 2 (167 × 212 n'est pas un octogone régulier) |
| M3 | Du pan arrière au bout des pans latéraux (profondeur maximale de plaque) | `PROF_PLAQUE` |
| M4 | Largeur de l'ouverture de la porte et épaisseur du faisceau à la charnière, porte ouverte | une plaque doit sortir |
| M5 | Hauteur libre : tablette → étage haut → étage milieu → plancher du coffre → fond de la caisse | altitude de chaque rail |
| M6 | Hauteur de la pile Puissance + Sécurité avec modules enfichés ; hauteur d'un PCA9685 enfiché sur Moteurs | M5, étage haut |
| M7 | Côté de la charnière de la porte, vu de l'intérieur | quel coin reçoit quelle colonne |
| M8 | Longueur réelle du chemin Sécurité → Moteurs à l'aplomb | D5 |
| M9 | Largeur utile de chaque pan du coffre entre montants, et hauteur du coffre | convertisseurs debout ou couchés, SD-150 |
| M10 | Course angulaire du tambour de la bouche (cou) et des bras ; diamètre des passages à l'épaule | boucles de service ou bague collectrice |
| M11 | Place libre sur la paroi côté porte du coffre pour la SD-150B-12 (199 × 110 × 50) | décision du 06/11 |
| M12 | Par où sort le pack aujourd'hui, et dimensions du pack avec BMS | tiroir extractible |
| M13 | Référence du relais 40 A, courant de sa bobine ; modèle du bloc d'alimentation du BLX4 ; polarité du jack du VoiceTone | cahier |
| M14 | Après le gabarit carton : les **66 longueurs** du cahier, ruban sur le chemin réel | cahier, étiquettes |

Et les lectures déjà demandées par le relevé (§6) qui restent ouvertes : étiquette des boîtiers
perforés, second PCA9685 noir, calibre de chaque fusible en place, BMS et cellules, photos de
la tête, du dos et du pack.

---

## 8. Dans quel ordre

Cette étude est l'étape 2 du plan. Ce qui suit la referme :

1. **Mesures M1-M13** (une séance, réglet et pied à coulisse, photos à chaque cote).
2. **Modèle renseigné**, rendus relus par David ; **gabarit carton** d'une plaque découpé au
   cutter, posé dans le robot avec les cartes et le support Pi dessus : c'est là que D3
   (deux cartes dans la largeur) se tranche.
3. **Une plaque d'essai** en PMMA 5 mm + deux rails PETG, montés sur le robot : glisse,
   verrou, passage par la porte. Si ça passe, le reste des plaques.
4. **Longueurs M14** sur le gabarit, cahier complété, étiquettes imprimées. Puis étape 4
   (commande des cartes, une seule) et étape 6 (montage à blanc sur table).

Les **supports imprimés** à dessiner, dans l'ordre d'utilité : joues de la SD-150B-12 (copie
du support SD-50B-5 avec les cotes de la fiche), platine fusible + relais 40 A, platine des
SmartDrive, tiroir du pack, support du VoiceTone, boîtes de distribution (dessinées le 07/11 dans
`plans/elec/bornier-distribution`, à essayer sur une bande d'une rangée avant impression). Tous en PETG, vis à bois Ø4 × 20 max, modèle paramétrique avec rendu avant impression.

---

## 9. Décisions

| # | Décision | État |
|---|---|---|
| D2 | Matière et découpe | **DÉCIDÉ par David le 08/11 : PMMA coulé 5 mm fraisé à la CNC** (§0 bis). Rayons intérieurs ≥ 3 mm, plaque d'essai d'abord ; laser en repli si la CNC ne prend pas la plaque |
| D3 | Deux cartes dans la largeur de l'étage milieu | **au gabarit carton** après M1 ; repli si ça ne tient pas : carte Moteurs sur un pan, debout, à côté de la pile |
| D5 | Échange des broches 7 et 8 de la nappe | après M8 ; à faire si > 25 cm |
| D6 | Point de masse en étoile | **proposé §6**, relecture indépendante avant câblage |
| D11 | Rails sur les pans ou sur les montants | après M1 ; le modèle ne change pas |
| D12 | Boucle de service ou bague collectrice au cou | après M10 ; avis : **limite d'angle logicielle + boucle**, c'est aussi le point ③ de l'étude actionneurs |
| D13 | Emplacement du coup-de-poing, du bouton d'armement, du lidar | **ouverts** — à placer avec David sur le robot, pas sur le papier |

Les décisions de David du 06/11 (§1) et celles du plan (D1, D4, D7, D8, D10) ne sont pas
rouvertes ici.
