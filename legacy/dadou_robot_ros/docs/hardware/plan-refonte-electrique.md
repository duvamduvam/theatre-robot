# Plan global : refonte électrique de Didier (2026-11-05, proposition)

Demande de David : traiter ensemble les cartes, de nouveaux étages en plexiglas et la reprise
de tout le câblage et des passages de câbles. État : **plan proposé, rien de commencé.**
Il englobe [`plan-verification-cartes.md`](plan-verification-cartes.md), qui reste le détail
de l'étape cartes.

## 1. Pourquoi un seul plan

Les trois sujets se commandent l'un l'autre : la place des cartes fixe la longueur des nappes
et des fils, les passages de câbles fixent les découpes des étages, et le câblage peut changer
un connecteur sur une carte. Pris séparément, chacun ferait refaire les autres.

Ce que la refonte règle, tout ensemble :

| Problème connu | Source |
|---|---|
| **Pas de chien de garde matériel, d'`OE` ni de coup-de-poing** : si `wheels_node` meurt, rien n'arrête les roues | `chantiers.md`, chaîne de sécurité |
| Boutons du dos : « stop » éteint le Pi au lieu d'arrêter les roues | `chantiers.md`, DANGER ACTIF |
| Faisceaux non peignés, puissance et signal mélangés | `robot-embarque.md` §3, point 10 |
| Ronflement : masses communes, câblage audio non symétrique | `robot-embarque.md` §1.8, étude voix |
| Un seul RJ45 branchable sur le routeur (support trop serré) | `chantiers.md`, interface web |
| TC Helicon posé en vrac, stripboards sur montants bois | `robot-embarque.md` §2 |
| Pack et BMS difficiles d'accès | David, 05/11 |

## 2. Règles de la refonte

1. **Une chose à la fois.** Ne jamais changer le logiciel et le câblage dans la même étape :
   le protocole caméra de la branche `l1-namespace-catalogue` se fait **avant** de démonter,
   sinon une panne ne dira pas lequel des deux est en cause.
2. **Rien n'est débranché sans étiquette ni photo.** Le relevé précède le démontage.
3. **Le cahier de câblage fait foi** : un fil qui n'y est pas n'existe pas (§4).
4. **Vérifier le réel avant le modèle** : aucune découpe de plaque sans mesures sur le robot et
   sans gabarit essayé en place.
5. **Chemin roues** : règles de `CLAUDE.md` inchangées. Toute la chaîne repasse le protocole
   caméra, roues hors sol, avant le sol.

⚠️ **Le retour arrière ne sera plus un simple rebranchement.** Le plan de vérification disait
de garder l'ancienne carte montée : ce n'est plus possible si tout le câblage change. On garde
les anciennes cartes étiquetées, en boîte, avec photos et relevé : revenir en arrière prend
des heures, pas des minutes. À assumer avant de démonter.

## 3. Les étapes, et comment savoir qu'elles sont finies

| # | Étape | Fini quand |
|---|---|---|
| 0 | **Solder le logiciel** : protocole caméra de la branche L1, fusion | protocole vert, ou décision écrite de le reporter |
| 1 | **Relevé du réel** : photos de chaque étage, cotes intérieures (hauteur libre, passages), liste des câbles existants, référence du BMS et des alimentations | relevé dans `robot-embarque.md`, chaque fil étiqueté |
| 2 | **Implantation sur papier** : zones, emplacement de chaque appareil, chemins de câbles, y compris ce qui arrive (lidar, odométrie, ReSpeaker, INA226) | plan validé par David |
| 3 | **Cahier de câblage** : voir §4 | chaque fil a son fusible, sa section et sa longueur |
| 4 | **Cartes** : `plan-verification-cartes.md`, ajustées selon 2 et 3 | commande passée, **une seule** |
| 5 | **Étages** : modèle paramétrique, gabarit carton ou imprimé essayé dans le robot, puis découpe | une plaque d'essai posée sans forcer |
| 6 | **Montage à blanc sur table** : cartes, étages et faisceaux hors robot, alimentation limitée en courant | tous les rails bons, chaîne de sécurité testée |
| 7 | **Dépose et pose** | robot remonté, cahier à jour de ce qui a changé |
| 8 | **Validation** : mise sous tension graduée, protocole caméra (dont débrancher chaque nappe en mouvement), mesure du ronflement avant/après | protocole vert ; ensuite seulement le sol |

Les étapes 4 et 5 peuvent avancer en parallèle une fois 3 fini.

> **Étape 1 commencée le 05/11** : relevé à l'image dans
> [`releve-2026-11-05.md`](releve-2026-11-05.md) (état de chaque niveau, conformité de la doc,
> proposition d'implantation). **Les cotes et l'étiquetage des fils restent à faire** : liste
> fermée au §6 du relevé.

## 4. Câblage

**Trois familles, séparées physiquement :** puissance (batterie, moteurs, 12 V et 24 V),
logique (I²C, nappes, GPIO, USB, Ethernet), audio (micro, ligne, haut-parleurs). Chacune a son
chemin. Quand deux doivent se croiser, c'est à angle droit, jamais en parallèle.

**Masse :** en étoile, avec un point unique choisi à l'étape 2. C'est la leçon du ronflement ;
les cartes actuelles ont une seule masse commune, donc c'est le câblage qui décide. L'audio
ne doit pas servir de retour à la puissance.

**Cahier de câblage** : un tableau versionné, une ligne par fil.

| Repère | De | À | Famille | Section | Fusible | Connecteur | Longueur |
|---|---|---|---|---|---|---|---|

Il sert à vérifier automatiquement section contre fusible, à générer les étiquettes de
la Marklife P15, et à mettre à jour la doc sans la réécrire.

**Démontable :** chaque étage se déconnecte par connecteurs, sans dévisser de bornier. C'est
ce qui donne l'accès voulu. Prévoir aussi le chemin de sortie du pack et du BMS.

**Réserve :** une gaine libre par chemin, pour les prochains ajouts.

## 5. Étages en plexiglas

**Pistes :** l'étage imprimé actuel `plans/elec/support-etage` mesure 167 × 212 × 4 mm. Si ce
format est bien celui de l'emplacement (à vérifier à l'étape 1), deux cartes de 100 mm y
tiennent côte à côte : la carte Moteurs pourrait rester à côté de Puissance et Sécurité.

**Atout :** transparent, isolant, et il montre LED et fusibles.

**Points de vigilance :**
- le PMMA est cassant : Didier pèse 50 kg et roule dehors. Pas de filetage dans le plexi, trous
  avec jeu, rondelles larges, pas de serrage fort, angles arrondis. Le polycarbonate encaisse
  bien mieux les chocs et les vibrations : à comparer, prix lus à la source ;
- pas de collage ni de chauffe à proximité des régulateurs et des résistances de puissance ;
- une plaque isolante ne dissipe rien : prévoir la ventilation du Pi et des alimentations ;
- dessiner les passages de câbles, les colliers et les entretoises M3 de l'entraxe 90 × 90.

**Méthode :** modèle paramétrique (OpenSCAD, export DXF), comme le reste du dépôt `plans/`,
gabarit d'abord. Le moyen de découpe reste à trancher.

## 5 bis. Découpe : prix lus le 05/11

Base de calcul : 5 plaques de 167 × 212 mm, soit 0,177 m² (hypothèse, nombre réel à l'étape 2).

| Option | Ce qui est lu | Limites |
|---|---|---|
| **eMode, Cholet** (association, 20 rue du Carteron) | Laser 60 W, plateau 726 × 432 mm, acrylique jusqu'à 1 cm, PVC interdit ; CNC 30 × 18 × 4,5 cm. Adhésion « à partir de 24 € / an », réservation 1 h minimum, initiation requise | Grille : **42 €** pour le laser, **6 €** pour la CNC, unité et catégorie du particulier à confirmer ; le polycarbonate n'est pas dans la liste du laser. Tél. 02 41 71 69 33 |
| **ICI Nantes** | Trotec et CNC selon fablabs.io ; abonnement atelier privatif 255 € HT / mois | Inadapté à un besoin ponctuel, sauf tarif à l'heure non trouvé |
| **Plexi Cindar** (en ligne) | PMMA coulé 5 mm 51,85 € HT/m² (62,22 € TTC) ; polycarbonate 4 mm 43,80 € HT/m² (52,56 € TTC) ; découpe laser et CNC annoncées | Matière seule ≈ 11 € ou 9,30 € TTC pour 0,177 m². Option « Découpe sur mesure » à 7 € TTC, dont l'unité n'est pas claire ; minimum, port et découpe de trous sur fichier **non lus**, devis à demander |

Non vérifiés : Systeal (site bloqué, prix écartés), plexiglasssurmesure.fr (aucun prix lu),
Angers, Ancenis et Beaupréau (aucun lieu trouvé). Polycarbonate : plus résistant aux chocs
(fournisseur et SendCutSend), mais orienté fraise plutôt que laser.

## 5 ter. Alimentations des actionneurs et de l'audio — options (06/11, proposé, rien de tranché)

Question de David : plutôt que sortir les bras du 12 V, séparer les servos et l'audio, et
gérer les redémarrages.

**Ce qui est sur le 12 V aujourd'hui** (une seule SD-50B-12, 4,2 A, coupure et redémarrage
automatique au-delà de 105-150 %) : trois servos ASME-MR (deux bras, la bouche), le servo des
yeux, la carte Audio (relais, klaxon, récepteur HF, 7805/7809), le TC Helicon, la boucle du
coup-de-poing et la bobine du relais 40 A. **Inconnus** : ce qui alimente l'ampli Focal, et le
type du servo du cou.

**Deux faits lus dans la doc qui changent la question :**
- la notice ASME du dépôt (`datasheets/ASME-02-series-wingxine-manual.pdf`, série ASME-02)
  donne une tension de service de **12 à 24 V** et un **courant limité à 5 A ± 0,2 par servo**.
  Le « ~10 A pic pièce » de nos documents ne vient donc pas de cette notice. Les ASME-MR ont
  la même carte (incident du 03/11), **mais la notice n'est pas la leur : à confirmer sur
  l'étiquette d'un ASME-MR** ;
- le servo des yeux (JX CLS-12V7346) est un servo **12 V** : il ne va pas sur le 24 V.

### Les options

| | Principe | Pour | Contre |
|---|---|---|---|
| **A. ASME en 24 V direct** (avis) | les 3 ASME prennent le 24 V du pack, **après le relais 40 A** et un fusible chacun ; la SD-50B-12 ne garde que les petites charges : yeux, cou si 12 V, audio, sécurité | plus de convertisseur sur les grosses charges, donc plus de décrochage en jeu ; les bras sont **enfin coupés par l'arrêt d'urgence** (220 à 340 kg·cm, ce n'est pas anodin) ; bras deux fois plus rapides possibles (0,5 s/60° au lieu de 1 s) ; rien à acheter | bras plus violents : la limite de vitesse logicielle (`RAMP_SPEED`) devient une sécurité ; ASME-MR en 24 V à confirmer ; câbles des bras depuis la caisse basse ; J36/J37 de la carte Puissance ne servent plus aux bras |
| **B. Deux 12 V** (proposition de David) | un convertisseur « actionneurs » dimensionné pour les pointes (3 × 5 A au pire), la SD-50B-12 actuelle pour audio et sécurité | garde le 12 V partout ; l'audio ne voit plus les pointes des moteurs ; un décrochage ne touche plus que les actionneurs | un convertisseur à acheter et à loger ; bras toujours lents ; les bras restent hors de l'arrêt d'urgence |
| **C. Un seul 12 V, pointes limitées** | ne jamais lancer deux bras à fond ensemble (logiciel), petit convertisseur dédié à la sécurité | le moins de matériel | la puissance repose sur le logiciel ; l'audio continue de voir les pointes : contraire au chantier ronflement |

A et B règlent aussi la séparation audio demandée par David. Dans A comme dans B, **l'audio
garde une alimentation que rien de gros ne partage**, ce qui va dans le sens de la masse en
étoile (D6).

### Gérer les redémarrages — quatre mesures, cumulables

1. **Ne pas en avoir** : aucune grosse charge sur un convertisseur qu'elle peut saturer
   (options A ou B).
2. **Une source qui ne décroche jamais pour la sécurité** : la boucle du coup-de-poing et la
   bobine du relais 40 A sur une alimentation que rien d'autre ne charge (la SD-50B-12 dans A,
   ou un petit convertisseur à part). La carte Sécurité reste en 12 V : la passer en 24 V
   changerait ses résistances de relecture.
3. **Relais 40 A à auto-maintien** : après toute coupure, le relais reste ouvert jusqu'à un
   réarmement humain. C'est la règle des machines industrielles contre le redémarrage
   intempestif. Aujourd'hui seul le verrou logique est maintenu, pas le relais ; c'est lui qui
   s'use en cas de coupures répétées. **Touche la chaîne d'arrêt** : schéma, relecture
   indépendante, protocole caméra.
4. **Redémarrage doux côté logiciel** : l'INA226 du rail servos (carte Puissance) mesure sa
   tension ; sur une chute, le Pi gèle les consignes, et au retour il repart de la position
   réelle en rampe au lieu de laisser les servos sauter à leur dernière consigne. Le Pi 4 est
   sur la SD-50B-5, séparée : il survit à une chute du 12 V.

### Isolation contre le bruit audio (question de David, 06/11)

Possible à quatre niveaux, du moins cher au plus cher :

1. **L'alimentation de l'audio, isolée** : les SD-50 sont des convertisseurs isolés (fiche :
   1,5 kV entre entrée et sortie). Une SD-50B-12 qui n'alimente **que** l'audio sépare donc
   galvaniquement l'audio du pack et des moteurs.
   ⚠️ *Corrigé le 06/11 (David)* : ce n'est **pas gratuit**. Dans l'option A, la SD-50B-12
   existante n'est pas réservée à l'audio : elle garde aussi le servo des yeux et la boucle
   d'arrêt. A retire les grosses pointes (les bras), sans rien acheter, mais l'audio partage
   encore son alimentation. Une alimentation audio vraiment seule demande **un second
   convertisseur** (une SD-50B-12 de plus, par exemple), à acheter.
2. **Le signal, par transformateur** : l'isolateur rouge déjà monté sur la porte, et les
   emplacements de transformateurs 600:600 prévus sur la carte Audio.
3. **La liaison USB Pi 5 → mixette** : c'est par elle que la masse du Pi entre dans l'audio.
   Un isolateur USB la coupe, mais la plupart plafonnent à 12 Mbit/s : vérifier d'abord que la
   mixette fonctionne à cette vitesse.
4. **La commande** : déjà isolée, les relais audio sont pilotés par le bus I²C derrière l'ISO1540.

**La limite** : une isolation est annulée par un seul fil de masse en trop (blindage RCA, USB,
châssis). C'est pour ça que la masse en étoile (D6) reste la décision qui compte. Et la source
du ronflement mesurée le 30/08 est l'alimentation secteur du Pi 5 : sur batterie elle disparaît.
Le bruit des moteurs, lui, n'a jamais été mesuré. **Mesurer avant d'acheter** : 1 est gratuit,
1 et 3 ne s'achètent que si une mesure le montre.

### Symptôme rapporté par David le 06/11 : l'ampli redémarre souvent

Hypothèse forte, **non prouvée** : l'ampli Focal (ampli auto, 12 V) est sur la SD-50B-12, et
celle-ci décroche quand les bras tirent ; ou l'ampli lui-même la sature à fort volume. Signature
attendue : la fiche donne **2,5 s de démarrage** à la SD-50, donc des coupures de quelques
secondes, au rythme des gestes ou des forts volumes.

Ce qui la prouverait, dans l'ordre :
1. **Où l'ampli prend son 12 V** (question encore ouverte) : s'il n'est pas sur la SD-50B-12,
   l'hypothèse tombe.
2. **Corrélation** : musique forte, bras immobiles, puis bras en mouvement. Les redémarrages
   suivent-ils les bras ?
3. **Mesure** : la tension aux bornes de l'ampli pendant un geste, à l'oscilloscope (Hantek,
   pince de masse au moins batterie seulement). Un 12 V qui tombe et revient en ~2,5 s signe
   le décrochage.

Autres causes à écarter : protection thermique de l'ampli (enfermé dans le bois), protection
de sous-tension propre aux amplis auto, fil de commande à distance (REM) mal raccordé.

**Si c'est confirmé**, l'option A (bras en 24 V) devrait faire cesser les redémarrages sans
rien acheter : à vérifier en premier, en débranchant simplement les bras du 12 V pour l'essai.

**Un convertisseur plus gros ?** Oui si on en achète un, mais dimensionné sur des courants
**mesurés** (ampli à fort volume, et ce qui partage son alimentation), pas sur une marge au
jugé. Et pour l'audio, la taille compte moins que d'être seul sur son alimentation.

**Confirmé par David le 06/11** : l'ampli est bien sur la SD-50B-12, et **l'ampli seul**, quand
il sature, suffit à la faire décrocher. Les bras n'y sont pour rien dans ce cas-là : l'option A
ne règle donc pas les redémarrages d'ampli. **Il faut un convertisseur dédié à l'audio.**

### Convertisseur audio : choix (fiches Mean Well lues le 06/11, archivées dans `datasheets/`)

| Modèle | 12 V | Surcharge | Refroidissement | Encombrement |
|---|---|---|---|---|
| SD-50B-12 (en place) | 4,2 A | coupe et **redémarre seul** (2,5 s) | sans ventilateur | 159 × 97 × 38 mm |
| SD-100B-12 | 8,5 A | coupe et redémarre seul | sans ventilateur | 199 × 98 × 38 mm |
| SD-150B-12 | 12,5 A | coupe et redémarre seul | sans ventilateur | 199 × 110 × 50 mm |
| SD-200B-12 | 16,7 A | **coupe et reste coupé** jusqu'à remise sous tension | convection, sans ventilateur | 215 × 115 × 50 mm |
| SD-350B-12 | 27,5 A | coupe et reste coupé ; entrée 20-36 V | **ventilateur intégré** | 215 × 115 × 50 mm |

Entrée de toutes les versions B : 19 (ou 20) à 36 V, isolée 1,5 kV, réglable de 11 à 16 V.

**Piège de choix** : à partir du SD-200, une surcharge **coupe l'audio jusqu'à ce qu'on
éteigne et rallume**. En spectacle, c'est pire qu'un redémarrage de 2,5 s. Soit on prend un
modèle qui redémarre seul (SD-150 au plus), soit on prend un modèle si large qu'il ne sature
jamais.

**Le chiffre qui décide : le courant maximal de l'ampli.** On le lit sur **le fusible de
l'ampli** (sur son boîtier) ou sur **le porte-fusible à lame en ligne** vu sur la porte : un
ampli auto est fusiblé à sa consommation maximale. Règle : convertisseur ≥ fusible de l'ampli
+ TC Helicon + carte Audio (moins de 1 A). Exemple : fusible de 10 A → SD-150B-12 ; au-delà,
le SD-150 ne suffit plus et il faut choisir entre une coupure maintenue et un bridage du
volume de l'ampli.

**Fusible de l'audio lu par David le 06/11 : 25 A.** Un fusible est calibré au-dessus de la
consommation maximale : l'ampli tire donc moins de 25 A, mais rien ne dit combien. La SD-150B-12
(12,5 A) **ne couvre pas** ce cas : elle décrocherait encore quand l'ampli sature. Deux voies :

- **SD-350B-12 (27,5 A), avis** : au-dessus du fusible, donc le fusible de l'ampli saute avant
  que le convertisseur ne sature ; sa coupure sans redémarrage ne joue plus. Contre : plus gros
  (215 × 115 × 50 mm), entrée à partir de 20 V au lieu de 19, et **un ventilateur intégré**
  (fiche : « Forced air cooling by built-in DC Fan ») : un bruit permanent dans un robot de
  théâtre qui porte des micros. À écouter avant de l'adopter.
- **SD-150B-12 + gain de l'ampli bridé** pour rester sous 12,5 A : plus petit, moins cher,
  mais repose sur un réglage que quelqu'un peut remonter.

- **SD-200B-12 (16,7 A)** : silencieuse, mais si l'ampli dépasse ~17 à 25 A, elle coupe le son
  jusqu'à remise sous tension.

**Aucun modèle n'est à la fois silencieux, assez fort pour 25 A et à redémarrage automatique.**
Ce qui départage : **le courant réel de l'ampli**, donné par son modèle exact (étiquette de
l'ampli, puis sa fiche) ou mesuré à fort volume. Ne rien acheter avant.

**L'ampli : Focal Impulse 4.320** (David, 06/11). Notice officielle lue et archivée
(`datasheets/focal-impulse-4320-notice.pdf`) : 4 × 55 W RMS sous 4 Ω, 4 × 80 W sous 2 Ω,
2 × 160 W ponté ; **fusible 25 A (15 A en montage sur faisceau ISO)** ; 750 mA en veille ;
protections dont **chute de tension** ; câble d'alimentation 3,3 mm² (12 AWG) jusqu'à 3 m.
**La notice ne donne pas sa consommation.**

Ce qu'on en tire :
- **les redémarrages s'expliquent** : l'ampli se protège lui-même sur chute de tension ; dès
  que la SD-50B-12 plie sous sa demande, il se coupe et redémarre ;
- **ordre de grandeur, calcul et non mesure** : 220 W RMS sur 4 canaux, avec un rendement de
  classe D supposé à 80 % (pas sur la fiche), font ~23 A sous 12 V à pleine puissance, ce qui
  colle avec le fusible de 25 A. La voix et la musique en tirent bien moins tant que l'ampli
  ne sature pas ; Focal accepte d'ailleurs un fusible de 15 A dans un autre montage ;
- **« ça crache » = l'ampli sature** : c'est précisément là qu'il tire le plus. Régler son gain
  (0,2 à 5 V) pour qu'il ne sature jamais au niveau maximal de la mixette améliore le son et
  divise le courant de pointe.

**Avis : SD-150B-12 + gain de l'ampli réglé pour ne jamais saturer.** Silencieuse, redémarre
seule si elle décroche quand même (2,5 s de coupure plutôt que le silence jusqu'à remise sous
tension), trois fois le courant d'aujourd'hui, et la plus compacte. **Si une mesure montre plus
de 12 A en spectacle**, passer à la SD-200B-12 (16,7 A, silencieuse, mais coupure maintenue).
La SD-350B-12 n'est utile qu'à pleine puissance permanente, avec son ventilateur.

**Combien de convertisseurs 12 V, et où (06/11, question de David) :** deux. La SD-50B-12 en
place reste où elle est et ne garde que les petites charges (yeux, sécurité, cou si 12 V) :
**un seul boîtier de plus**, celui de l'audio. Il ne va **pas** dans la caisse basse, avec les
cartes des moteurs, mais dans le coffre des alims, **vertical sur la paroi**, au plus près de
la porte audio : câbles 12 V courts jusqu'à l'ampli, et loin des moteurs, ce qui sert aussi le
bruit. La place se libère au même endroit : le TC Helicon monte à l'étage audio, le bornier gris
perd l'essentiel de son rôle. Encombrement lu sur les fiches : SD-150 199 × 110 × 50 mm contre
159 × 97 × 38 pour une SD-50 (4 cm de long et 1,2 cm d'épaisseur de plus). À mesurer : la
place libre sur cette paroi.

Alternative sans boîtier de plus : un ampli qui accepte le 24 V, branché directement sur le
pack. Écartée par défaut : l'audio perdrait l'isolement du convertisseur, donc l'objectif bruit.

Attention aussi à la fin de batterie : si le pack est en 7S, il descend vers 19-21 V en fin de
décharge, là où ces convertisseurs B s'arrêtent. C'est déjà le cas de la SD-50B-12.

### Répartition proposée le 06/11 (après le choix du convertisseur audio)

| Source | Charges | Pourquoi |
|---|---|---|
| **Pack 24 V direct, après le relais 40 A** | roues (SmartDrive), **3 ASME** (deux bras, bouche), un fusible par ASME | la batterie encaisse (constat de David) ; plus de convertisseur sur les moteurs ; les bras deviennent coupés par l'arrêt d'urgence. ASME-MR en 24 V à confirmer sur l'étiquette |
| **SD-150B-12, nouvelle** | ampli Focal, TC Helicon, carte Audio (relais, klaxon, récepteur HF) | audio seul et isolé |
| **SD-50B-12, en place** | servo des yeux (JX CLS-12V7346), servo du cou (type à lire), boucle du coup-de-poing, bobine du relais 40 A | petites charges seulement |
| **SD-50B-5 ×2** | Pi 4 et logique ; Pi 5 et vision | décidé le 12/09 |

Conséquences sur la carte Puissance : J36/J37 et F7 ne servent plus aux bras (alimentés et
fusiblés à la distribution 24 V du coffre) ; le V+ des modules PCA9685 (yeux, cou) se prend sur
**J28 câblé depuis la SD-50B-12, JP1 ouvert**, pour ne pas faire passer les servos par un
cavalier limité à 3 A.

**État réel confirmé par David le 06/11** : bouche, bras et yeux sont aujourd'hui tous sur
le 12 V. David pense que les ASME pourraient se brancher directement sur la batterie.

**Le point à vérifier avant de les brancher sur le pack : la tension batterie pleine.** La
notice ASME donne **12 à 24 V en service** et **30 V au maximum absolu**. Un pack 7S Li-ion
monte à **29,4 V** pleine charge (le chargeur Victron a un mode 28,8 V et un mode 29,4 V) :
c'est sous le maximum absolu, mais **au-dessus de la plage de service**, avec 0,6 V de marge.
La chimie et le nombre de cellules du pack ne sont toujours pas établis. Donc, avant tout
branchement :
1. **lire la plage de tension sur l'étiquette d'un ASME-MR** (la notice du dépôt est celle de
   l'ASME-02) ;
2. **mesurer la tension du pack juste après une charge complète**, au multimètre ;
3. si la plage de l'ASME-MR s'arrête à 24 V et que le pack monte au-dessus de 28 V : ne pas
   brancher en direct.

**Mesure du 06/11 (David, lue dans VictronConnect) : 28,41 V**, chargeur en mode li-ion. C'est
la tension d'absorption de ce mode, donc **le maximum que le pack voit avec ce chargeur**.
Marge sous les 30 V absolus de la notice ASME : **1,6 V**. Hors de la plage de service
(12-24 V), mais sous le maximum absolu. Conséquences :
- **ne jamais passer le chargeur en mode « high » (29,4 V)** : la marge tomberait à 0,6 V ;
- il reste à lire l'étiquette d'un ASME-MR : si elle donne la même plage que l'ASME-02
  (30 V max), le branchement direct est acceptable ; si elle s'arrête plus bas, repli.

**Étiquette ASME-MR lue par David le 06/11 : « 12-24 V ».** Elle ne donne pas de maximum
absolu ; les 30 V viennent de la notice de l'ASME-02, même carte électronique. **Le risque, à
assumer en connaissance de cause** : un pack Li-ion de « 24 V » passe l'essentiel de sa vie
entre 25 et 28,4 V, donc **au-dessus de la plage marquée**, sous le maximum de la notice voisine.
C'est le cas courant des appareils « 24 V » sur batterie (les réseaux 24 V des véhicules
chargent aussi vers 28-29 V), mais rien sur l'ASME-MR lui-même ne le garantit. Mitigation :
jamais le mode « high » du chargeur, et toucher les servos (température) après les premiers
essais. Un convertisseur 24 V régulé supprimerait ce risque mais ramènerait le problème de
saturation (3 servos à 5 A max = 15 A). **Avis : branchement direct.**

**Répartition retenue en conséquence** : la SD-50B-12 actuelle est **gardée** pour les yeux,
la boucle du coup-de-poing et la bobine du relais 40 A ; **seule la SD-150B-12 de l'audio est à
acheter**, puisque l'ampli seul fait décrocher la SD-50B-12. Repli : un convertisseur 24 V régulé pour les ASME, ou les garder en 12 V
   sur un convertisseur dédié aux actionneurs (option B).

Au recâblage, **le fil rouge du connecteur 3 points des ASME reste non raccordé** : c'est une
sortie 5 V (incident du 03/11).

**Réserve sur la sécurité** : elle partage encore la SD-50B-12 avec deux servos. Le courant
de blocage du servo des yeux n'est pas publié (fiche JX lue : 12 V, 38 à 47 kg·cm, rien sur le
courant). **À mesurer** : yeux et cou bloqués ensemble. S'ils approchent les 4,2 A, la boucle
d'arrêt passe sur un petit convertisseur à elle.

### Avis

**A + 2 + 4 tout de suite, 3 à instruire.** A supprime la cause (pas de convertisseur sur les
moteurs), met les bras sous l'arrêt d'urgence, et ne coûte rien. 2 et 4 rendent les chutes
restantes sans danger. 3 est la vraie protection contre le redémarrage, mais elle touche la
chaîne d'arrêt : elle se conçoit à part.

**Avant de trancher** : l'étiquette d'un ASME-MR (tension), ce qui alimente l'ampli Focal, le
type du servo du cou, et le courant réel d'un bras en mouvement puis bloqué.

## 6. Décisions à prendre

| # | Décision | Avis |
|---|---|---|
| D1 | Refonte avant ou après le premier essai au sol | **DÉCIDÉ par David le 05/11 : avant.** Pas de roulage au sol sans arrêt matériel |
| D2 | Plexiglas ou polycarbonate, et qui découpe | Voir §5 bis : PMMA coulé 5 mm au laser d'eMode, une plaque d'essai d'abord |
| D3 | Emplacement de la carte Moteurs | Avis du relevé (§5.3) : à côté de la pile en haut **si elle y tient** — 12 mm de marge sur 212 mm, à trancher au gabarit carton dans le robot |
| D4 | Pistes 10 A de la carte Puissance | ✅ **Fait le 05/11 : élargies par plages de cuivre**, 1 oz, aucune pastille déplacée ; 35 trajets mesurés, 0 sous son exigence. En découlent : fusibles amont au coffre (15 A / 10 A) et cavaliers JP1, JP3 à 3 A max (`carrier-p/DESIGN.md`) |
| D8 | Fusibles amont du 12 V et du 5 V au coffre | **À inscrire au cahier de câblage** : 15 A et 10 A, sans quoi les troncs de la carte Puissance ne sont pas protégés |
| D10 | 12 V des bras séparé du 12 V de la sécurité | **Options A, B, C au §5 ter (06/11) ; avis : ASME en 24 V direct après le relais 40 A.** Constat de départ : le 12 V est une SD-50B-12 (4,2 A, David 05/11), deux bras à ~10 A en pointe la font décrocher, et elle porte aussi la boucle du coup-de-poing. Mesurer d'abord le courant réel d'un bras (relevé §4.4) |
| D9 | Alimentation des servos | Externe sur J28, ou 12 V carte par JP1 à 3 A au plus : à trancher avec les courants réels |
| D5 | Échange des broches 7 et 8 de la nappe Sécurité-Moteurs | À faire si la nappe s'allonge — donc tant que sa longueur réelle n'est pas mesurée |
| D6 | Point de masse en étoile | Quatre questions à répondre d'abord (relevé §5.3) : masse des sorties isolées des convertisseurs, barrière de la carte Odométrie, masse du 12 V, retour par l'USB du Pi 5 |
| D7 | Fiches du faisceau | ✅ **Clos le 05/11** : fiches 5,08 simples, réutilisées telles quelles ; embases des cartes dans la même série (relevé §4.3) |
