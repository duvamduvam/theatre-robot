# Le robot suiveur — hypothèses, modes de défaillance, et ce qu'il manque

> **Statut : PROPOSITION du 2026-09-14.** L'analyse et les chiffres sont fermes
> (ils se recalculent) ; les correctifs proposés ne sont pas actés.

---

## 0. Pourquoi cette étude existe, et pourquoi si tard

Le suivi de personne est **le seul chantier du dépôt sans étude**. Tous les
autres en ont une — roues, arbitrage, conversation, interaction, web,
odométrie, télédiagnostic, voix, identification.

Il a été construit d'un bloc le **11/07 au soir** (« fait la total »), validé en
simulation 5/5 le soir même, déployé sur les deux Pi le lendemain. Le résultat
est bon — §1 le dit sans réserve. Mais il n'a jamais eu que **vingt lignes de
statut** dans `chantiers.md`, et **aucune de ses hypothèses n'a jamais été
écrite**. Or elles sont nombreuses, et la scène de rue les casse presque toutes.

L'élément déclencheur : David a décrit le 14/09 sa vraie scène — la rue, des
passants, plusieurs personnes devant lui. Il a demandé si suivre était
« faisable facilement dans un grand nombre d'environnements ». La réponse
honnête a exigé de reconstituer, par la lecture du code, des hypothèses que
personne n'avait consignées. **C'est ce document qui manquait.**

---

## 1. Ce qui existe, et ce qui est bon dedans

La chaîne : `person_tracker_node` (MediaPipe EfficientDet-Lite0, ~16,7 Hz,
~24 % CPU sur la Pi 5) → `/vision/person_box` → `person_follower` →
`cmd_vel_follow` → `twist_mux` **priorité 20** (remote 100 > web 50 > follow 20
> anim 10).

**Les garde-fous sont sérieux, et il faut le dire** :

- plafonds **durs** au constructeur (`ABS_MAX_LIN 0,5` / `ABS_MAX_ANG 1,0`) qui
  bornent jusqu'aux paramètres passés — un mauvais réglage ne peut pas les
  franchir ;
- **zéro franc** sur perte de cible > 600 ms, et sur OFF ;
- **marche arrière interdite** par défaut (`allow_reverse=False`) : la caméra
  regarde devant, donc reculer serait aveugle. C'est une **asymétrie de
  sécurité** délibérée — on retient l'idée, elle resservira au §4 ;
- la télécommande écrase toujours (priorité 100), toggle `follow` **OFF par
  défaut**, node pas dans le bringup ;
- logique pure testée hors ROS, comme `gaze_control` et le chemin roues.

**Et un choix de conception qui est juste** : le proxy de distance est la
**hauteur** de la boîte, pas son aire. L'aire varie avec la pose (bras
écartés) ; la hauteur d'une personne debout ne varie qu'avec la distance. Le
commentaire de `target_picker.py` le justifie explicitement. C'est le bon
réflexe — et c'est précisément pour ça que le §3 fait mal : le point faible qui
reste n'est pas un oubli, c'est la limite de la monoculaire.

**Ce que valent les réglages, en unités physiques** — jamais écrit jusqu'ici :

Pour une personne de 1,75 m et un champ vertical ≈61,6° (77° horizontal, 4:3) :

> `height ≈ 1,468 / d` (d en mètres)

Donc `target_height = 0,55` ⇒ **distance de confort ≈ 2,7 m**, et la zone morte
`height_deadzone = 0,08` ⇒ Didier ne bouge pas tant que David est entre ≈2,3 m
et ≈3,2 m. C'est cohérent avec la zone sociale de l'étude conversation
(1,2-3,6 m) — par chance plus que par calcul, mais cohérent.

---

## 2. Les hypothèses implicites — aucune n'est vraie en rue

Le code les suppose toutes, sans les écrire :

| # | Hypothèse | Vraie en atelier | Vraie en rue |
|---|---|---|---|
| H1 | Une seule personne dans le champ | oui | **non** |
| H2 | La personne suivie est la plus grosse à l'image | oui | **non** |
| H3 | Rien ne masque la personne | oui | **non** |
| H4 | La silhouette ne change de taille que par la distance | oui | **non** |
| H5 | Le chemin entre le robot et la personne est libre | oui | **non** |
| H6 | Le sol est plat et continu | oui | **non** |
| H7 | La personne reste dans le cône de ±38° | oui | à peu près |
| H8 | L'éclairage permet la détection | oui | variable |

H1/H2 sont traitées par [`etude-identification-acteur.md`](etude-identification-acteur.md)
(désignation par bouton du gant). **H3 et H4 sont l'objet du §3-4 : ce sont les
dangereuses.** H5/H6 demandent un capteur (§5). H7 est une limite de cadrage
(caméra fixe sur le buste, champ ≈77° → cône dur de ±38° autour de l'axe du
châssis). H8 échoue du bon côté (§3).

---

## 3. Modes de défaillance — et leur DIRECTION

C'est le cœur de l'étude. Pour un robot de 50 kg, un mode de défaillance ne se
juge pas à sa fréquence mais à **la direction dans laquelle il pousse**.

| Cause | Ce que Didier mesure | Ce qu'il fait | Direction |
|---|---|---|---|
| Personne hors champ, ou confiance < 0,4 | plus rien | timeout 600 ms → **zéro franc** | ✅ sûr |
| Occlusion **totale** par un passant | plus rien | timeout → **zéro franc** | ✅ sûr |
| Lumière insuffisante | confiance s'effondre | timeout → zéro | ✅ sûr |
| Deux personnes se chevauchent | une boîte plus grande | « trop près » → recul interdit → **arrêt** | ✅ sûr |
| **Occlusion PARTIELLE** (jambes masquées) | boîte **rétrécie** | « il s'éloigne » → **AVANCE** | ⛔ **dangereux** |
| David s'accroupit, s'assoit, se penche | boîte **rétrécie** | « il s'éloigne » → **AVANCE** | ⛔ **dangereux** |
| David caché à mi-corps (table, muret, voiture) | boîte **rétrécie** | **AVANCE** | ⛔ **dangereux** |
| Obstacle au sol (marche, bordure, trou, câble) | rien du tout | poursuit sa route | ⛔ **dangereux** |
| Faux positif (affiche, mannequin, statue) | une « personne » fixe | s'en approche et se fige | ⚠️ modéré |

### 3.1 Le résultat contre-intuitif

**L'occlusion totale est sûre. L'occlusion partielle est dangereuse.**

Quand un passant masque complètement David, la détection disparaît, le deadman
tombe, Didier s'arrête. Quand le passant ne masque que le bas du corps — ce qui
est le cas le plus fréquent en foule — la détection **tient**, la boîte
rétrécit, et la loi de commande interprète ce rétrécissement comme un
éloignement :

```
err = target_height - ema_height      →  positif et grand
lin = gain_lin × err                  →  AVANCE, jusqu'à max_lin = 0,25 m/s
```

Il n'y a aucun timeout, puisque les messages continuent d'arriver. **Le
rempart ne se déclenche pas, parce que rien n'est perdu — c'est la mesure qui
est fausse.**

### 3.2 Le biais est structurel, pas accidentel

Le proxy « hauteur de boîte » est **asymétrique par nature** : tout ce qui
réduit la silhouette apparente sans éloignement réel produit une accélération.
Or en foule, presque tout réduit la silhouette apparente.

Autrement dit : **plus il y a de monde, plus Didier a tendance à avancer.**
C'est exactement l'inverse de ce qu'on veut.

---

## 4. Un correctif gratuit — la limite de vraisemblance asymétrique

Il existe une parade **purement logicielle**, sans capteur, qui convertit le
mode dangereux du §3.1 en mode sûr. Elle repose sur le fait qu'une occlusion et
un éloignement n'ont pas du tout la même **vitesse**.

Puisque `height ≈ 1,468/d`, la vitesse relative de la hauteur vaut :

> `(dh/h)/dt = −(dd/dt) / d`

- **Éloignement réel**, marche rapide à 1,5 m/s depuis 2,7 m :
  `−1,5 / 2,7 ≈ −56 %/s`. C'est le maximum physique d'un humain qui marche.
- **Occlusion** : la boîte perd la moitié de sa hauteur en 1 à 2 trames à
  16,7 Hz, soit ~120 ms. Même amorti par l'EMA (α = 0,4, constante de temps
  ≈ 0,15 s), le pic se compte en **plusieurs centaines de %/s**.

**Un ordre de grandeur sépare les deux.** Ils sont discriminables.

**La parade** : limiter le **taux de décroissance** de la hauteur utilisée pour
calculer l'avance — et seulement celui-là.

- la hauteur qui **augmente** (David se rapproche) passe **sans limite** :
  Didier ralentit ou s'arrête, direction sûre ;
- la hauteur qui **diminue** est limitée à un taux plausible : si elle chute
  plus vite qu'un humain ne peut s'éloigner, c'est une occlusion, pas une
  distance — on refuse d'en déduire une accélération.

C'est la même asymétrie de sécurité que `allow_reverse=False` (§1) : on ne
bride que le sens qui peut blesser.

**Propriétés** : logique pure, testable hors ROS et hors matériel, aucun
capteur, aucun coût CPU, aucun changement de contrat de topic. Le seuil se règle
sur corpus, pas à l'intuition — **je ne propose pas de chiffre ici**, seulement
la borne physique (−56 %/s) qui dit où il ne peut pas être.

⚠️ **Ce que ça ne fait pas** : ça empêche Didier d'accélérer vers un obstacle
qu'il ne voit pas. Ça ne lui fait **pas** voir l'obstacle. C'est un rempart, pas
une perception.

---

## 5. Ce qu'il manque vraiment, par ordre

1. **La perception d'obstacle.** Rien, aujourd'hui, dans le chemin roues : ni
   mur, ni marche, ni personne, ni bordure. C'est le seul manque qui rende le
   suivi au sol en public réellement défendable. Un lidar 2D d'entrée de gamme
   règle **l'obstacle et la distance** d'un coup — donc il supprime aussi la
   cause racine du §3.
2. **La distance réelle**, qui disparaît avec le point 1. Tant qu'elle est
   déduite de la hauteur de boîte, le §4 est un pansement — un bon pansement,
   mais un pansement.
3. **L'identité** — traitée ailleurs
   ([`etude-identification-acteur.md`](etude-identification-acteur.md)).
4. **Le cône de ±38°** : acceptable pour suivre (à 2,7 m, le plafond de
   0,6 rad/s encaisse ≈1,6 m/s de déplacement latéral), limitant pour
   ré-acquérir quelqu'un qui n'est pas devant.
5. **Le sens de rotation `direction_sign` du suiveur n'a jamais été tranché sur
   le vrai robot** — même dette que le gaze avant le 12/07. À établir au
   protocole caméra roues hors sol, avant tout essai au sol.

---

## 6. Lots proposés

| Lot | Contenu | Où |
|---|---|---|
| **S0** | Limite de vraisemblance asymétrique (§4) : logique pure + tests, dont le cas occlusion et le cas accroupissement | banc |
| **S1** | Réglage du seuil sur corpus vidéo — le **même** corpus que l'identification (§7 de l'autre étude) et que la VAD | banc + une sortie |
| **S2** | Protocole caméra roues hors sol : `direction_sign`, plafonds, e-stop, + rejeu d'une occlusion filmée | robot |
| **S3** | Perception d'obstacle (lidar 2D) — étude matérielle à ouvrir | à chiffrer |

S0 et S1 se font **robot immobilisé**.

---

## 7. Ce qui reste ouvert

- **Le seuil de vraisemblance** : trop serré, Didier se fige dès que David
  marche vite ; trop lâche, il ne filtre rien. Corpus.
- **Que faire quand la limite se déclenche** : figer l'avance, ou s'arrêter
  franchement ? La seconde est plus sûre et plus lisible en scène (Didier
  hésite), la première est plus douce. À trancher avec David — c'est une
  question de **jeu** autant que de sécurité.
- **Le suivi en marche arrière** reste interdit et doit le rester tant que rien
  ne regarde derrière.
- **L'articulation avec le gaze** : pendant que Didier suit des roues, le cou
  suit aussi. Les deux sont indépendants (caméra fixe sur le buste, donc pas de
  couplage — établi le 14/09), mais personne n'a regardé ce que ça **donne à
  voir** : un robot qui roule vers vous en vous fixant n'a pas le même effet
  qu'un robot qui roule en regardant devant. Question de jeu, à porter à
  `etude-interaction.md`.
