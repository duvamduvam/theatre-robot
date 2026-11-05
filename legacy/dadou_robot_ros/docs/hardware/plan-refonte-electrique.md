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

## 6. Décisions à prendre

| # | Décision | Avis |
|---|---|---|
| D1 | Refonte avant ou après le premier essai au sol | **DÉCIDÉ par David le 05/11 : avant.** Pas de roulage au sol sans arrêt matériel |
| D2 | Plexiglas ou polycarbonate, et qui découpe | Voir §5 bis : PMMA coulé 5 mm au laser d'eMode, une plaque d'essai d'abord |
| D3 | Emplacement de la carte Moteurs | Après le relevé |
| D4 | Pistes 10 A de la carte Puissance | Élargir, sinon cuivre 2 oz |
| D5 | Échange des broches 7 et 8 de la nappe Sécurité-Moteurs | À faire si la nappe s'allonge |
