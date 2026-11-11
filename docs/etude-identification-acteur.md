# Identifier David — reconnaître l'acteur parmi les passants

> **Statut : PROPOSITION du 2026-09-14.** Rien ici n'est acté. Les sections
> marquées `[DÉCIDÉ]` le seront quand David aura tranché ; le reste est à
> discuter. Le §2 rappelle ce qui est **déjà** décidé ailleurs et ne se
> rediscute pas.

---

## 0. Pourquoi cette étude existe

Elle naît d'une phrase de David, le 14/09, en découvrant l'état du suivi de
personne :

> *« Ma première scène est la rue, d'autres personnes peuvent passer devant,
> je parle à quelqu'un on est plusieurs devant. Je pars chercher un truc je
> reviens. Il est important que Didier puisse m'identifier. »*

Quatre situations en une phrase, et le code n'en gère aucune. La
ré-identification était rangée en **phase D6** (`etude-declenchement-conversation.md`
§5.1), c'est-à-dire en dernier. La scène de rue dit que D6 arrive trop tard :
sans identification, Didier ne rate pas *un peu*, il regarde systématiquement
la mauvaise personne.

Puis une seconde question de David, une heure plus tard, qui a **réécrit cette
étude** :

> *« Il n'y a pas un moyen depuis la télécommande ? Un petit système
> électronique simple ? »*

Elle arrive après quatre pistes techniques évaluées, et elle les relègue toutes
(§4.6). Le petit système électronique existe déjà — c'est le gant, et il a des
boutons libres. **On ne cherchait pas à reconnaître David : on cherchait à ce
qu'il puisse se désigner.** Ce n'est pas le même problème, et le second est
beaucoup plus petit.

---

## 1. Le problème, tel que le code le produit aujourd'hui

`TargetPicker` (dépôt `dadou_vision_ros`, `vision/tracking/target_picker.py`)
choisit sa cible sur **`score × aire`**. L'aire, c'est la proximité. Il n'y a
aucune notion d'identité : seulement un bonus d'adhérence (rayon 0,3 d'azimut)
qui stabilise la cible d'une image à l'autre, ce qui est de la cinématique, pas
de la reconnaissance.

Conséquence directe, jouée en rue :

| Ce qui se passe sur scène | Ce que Didier fait |
|---|---|
| Un badaud se met au premier rang | il le fixe, lui |
| Un passant coupe entre David et Didier | il le suit des yeux |
| David parle à quelqu'un, plus près que lui | il regarde l'interlocuteur |
| David sort du champ et revient | il prend la plus grosse silhouette |

⚠️ **Ce ratage a déjà lieu**, avec le gaze seul, roues à l'arrêt : le gaze est
déployé et validé en réel depuis le 12/07. Ce n'est pas un problème futur.

---

## 2. Ce qui est déjà tranché — ne pas re-trancher

- **Didier est un instrument de jeu, pas un robot autonome**
  (`etude-interaction.md` §1). Ce qui suit doit servir le jeu de David, pas
  fabriquer de l'autonomie.
- **Aucune frontière jeu / régie** (décision David du 13/09) : le pilotage
  passe par la réplique, pas par une sortie de personnage. Un étalonnage
  d'identité ne peut pas être un mode « réglage » hors jeu.
- **La FSM d'engagement** (`etude-declenchement-conversation.md` §5.2, grill du
  12/07) : ABSENT → PRESENT → INTERESTED → ENGAGED → IN_CONVERSATION →
  COOLDOWN, micro armé **à l'arrêt seulement**.
- ⚠️ **Le verrou qui domine tout** (`etude-interaction.md` §8) : `e_stop` n'a
  aucun publieur, les deux boutons du dos éteignent le Pi au lieu d'arrêter les
  roues, la carte du coup-de-poing n'est pas fabriquée. **Aucune déambulation
  publique avant que ce point soit fermé.** Cette étude est antérieure à rien :
  elle passe après.
- **Le robot est immobilisé.** Comme les phases A-C de l'étude interaction,
  tout ce qui est proposé ici doit se faire au banc. C'est une contrainte de
  conception, pas un regret (§7).

---

## 3. La géométrie décide avant toute technologie

La webcam couvre ≈77° sur 640 px. À la distance `d` (mètres), la largeur de
scène vue est `2·d·tan(38,5°) = 1,59·d` mètres sur 640 px, donc :

> **pixels par mètre = 402 / d**

| Distance | px/m | Visage (~16 cm) | **IPD** (~6,3 cm) | Torse (~50 cm) |
|---|---|---|---|---|
| 2 m | 201 | 32 px | **12,7 px** | 100 px |
| 3 m | 134 | 21 px | **8,4 px** | 67 px |
| 5 m | 80 | 13 px | **5,1 px** | 40 px |

**L'IPD (écart interpupillaire) est le bon critère**, pas la largeur du visage :
c'est lui que la littérature utilise pour dire quand un modèle de
reconnaissance décroche.

Le torse, lui, reste largement mesurable partout. **Toute la suite découle de
ces deux colonnes.**

---

## 4. État de l'art — recherche sourcée du 2026-09-14

### 4.1 Reconnaissance faciale — éliminée par la géométrie

- ArXiv 2503.20108 (*Peepers & Pixels*, papier académique) : ArcFace dépasse la
  performance humaine entre **30 et 10 px d'IPD**, et passe **sous** l'humain à
  **5 px**.
- Croisé avec le §3 : **8,4 px d'IPD à 3 m**, 5,1 px à 5 m. David joue entre 2
  et 5 m. On est sous la bande utile sur presque toute la plage.
- `face_recognition` (wiki officiel + issue #915) : entre **90° et 120° de
  profil, le visage n'est même pas détecté** ; au-delà, détecté mais non
  reconnu de façon fiable. En rue, David est de dos ou de trois-quarts la
  moitié du temps.
- MediaPipe annonce une détection *full-range* jusqu'à 5 m — mais c'est de la
  **détection**, pas de la reconnaissance. Ne pas confondre les deux chiffres.
- ⚠️ **Aucun benchmark dlib/InsightFace en CPU seul sur Pi 5 n'a été trouvé.**
  Sans objet ici puisque la géométrie tranche avant, mais à savoir.

**Verdict : éliminée.** Pas « imparfaite » — hors de portée du capteur.

### 4.2 Marqueur porté (ArUco / AprilTag) — éliminé par la géométrie

- Ni OpenCV ni AprilRobotics ne publient de formule pixels/distance ; les
  paramètres ArUco exposés sont **relatifs au périmètre détecté**.
- Le seul ordre de grandeur qui circule (« ~10 px par *step* du tag ») **n'a
  pas pu être confirmé sur une source primaire** — à traiter comme non vérifié.
  Même en le divisant par deux, un marqueur lisible à 5 m en 640×480 se compte
  en **dizaines de centimètres, voire en mètre**.
- Et un marqueur est porté **d'un seul côté** : il disparaît quand David se
  retourne — exactement le cas à couvrir.
- IR rétroréfléchissant : la technique existe (mocap, un brevet cite le suivi
  d'acteur pour poursuite lumineuse), mais **aucun retour d'usage en extérieur
  n'a été trouvé**, et le soleil émet lui-même de l'IR.

**Verdict : éliminé.**

### 4.3 ReID appris (OSNet) — techniquement possible, mais fragile ici

- `deep-person-reid` MODEL_ZOO (doc officielle) : **osnet_x0_25 = 0,2 M
  paramètres, 0,08 GFLOPs**, entrée 256×128. C'est minuscule — le budget CPU
  n'est pas l'obstacle.
- Même domaine (Market1501) : Rank-1 **91,2 %**. **Domaine croisé**
  (entraîné MSMT17 → testé Market1501) : Rank-1 **59,9 %**. La chute est
  donnée par la doc officielle elle-même.
- **La rue est un domaine nouveau.** C'est le cas défavorable, pas le cas
  nominal.
- ⚠️ **Aucun benchmark OSNet sur Pi/ARM/TFLite n'a été trouvé** (4 requêtes
  dédiées). Aucune donnée de robustesse à l'éclairage non plus.

**Verdict : gardé en repli**, pas en première intention. On n'installe pas une
dépendance de modèle non mesurée pour résoudre un problème qu'un histogramme
règle — surtout quand son point faible documenté est précisément notre cas.

### 4.4 Balise radio UWB — reléguée par le §4.6, gardée pour mémoire

- Modules : **DWM3000 nu à 28,34 $** (boutique officielle Qorvo, 1-24 pièces,
  lu le 14/09) ; **ESP32 UWB DW3000 tout fait à 43,80 $** (Tindie/Makerfabs, lu
  le 14/09) ; MaUWB à 59,80 $ (prix repris par un article tiers du 09/07/2026,
  page produit inaccessible en direct — **à re-vérifier avant d'acheter**).
- L'angle d'arrivée annoncé à **±5°** n'a **pas** pu être confirmé sur une page
  primaire. Ne pas bâtir de plan dessus en l'état.
- Ce que ça réglerait d'un coup : **identité** (c'est la balise de David),
  **distance réelle** (donc la hauteur-de-boîte du §5 disparaît, sans lidar), et
  **l'occlusion** — la radio traverse les gens, la caméra non.

**Verdict : reléguée.** Le §4.6 lui retire sa raison d'être principale
(l'identité) pour le prix de zéro composant. Il ne lui resterait que la
distance et la traversée des corps — or ces deux-là servent les **roues**, qui
sont derrière le lidar et le coup-de-poing de toute façon (§5). À rouvrir
seulement si le suivi roues autonome en rue devient un objectif ferme.

### 4.6 ⭐ La DÉSIGNATION plutôt que la reconnaissance — la télécommande

**Question de David, le 14/09 :** *« Il n'y a pas un moyen depuis la
télécommande ? Un petit système électronique simple ? »*

Elle retourne le problème, et elle a raison.

Les pistes 4.1 à 4.4 cherchent toutes à fournir **direction + identité**. Mais
la direction, **on l'a déjà** : c'est ce que la caméra fait de mieux (torse à
40 px même à 5 m, azimut propre — §3). Le seul manque, c'est **« lequel
c'est moi »**. Et ça, un bouton dans la main de David le dit parfaitement.

**Le petit système électronique existe déjà et David le porte** : le gant est
une carte **RP2040** (`dadou_control_ros`, README) qui parle déjà au robot.
Mieux, **des boutons sont libres** :

| Entrée | État actuel | Fichier |
|---|---|---|
| `IHR` (gant) | `{NAME: "Inclino", CMD: {}}` — **commande vide**, bouton câblé qui ne fait rien | `controller/buttons/button_config.py:97` |
| `START`, `SELECT`, `MODE` (gamepad) | `0` — non affectés | idem, l. 120-122 |

Donc : **coût matériel nul, coût logiciel = une ligne de config.**

**Et ça abaisse énormément l'exigence de fiabilité.** Re-désigner coûte **une
pression**. Un système qu'on réarme en un quart de seconde n'a pas besoin
d'être juste à 99 % — il doit être bon *entre deux appuis*. Toutes les pistes
précédentes étaient dimensionnées pour tenir seules, indéfiniment, sans
recours. Celle-ci a un humain dans la boucle, qui est justement celui qu'on
cherche à reconnaître.

**Verdict : c'est le socle.** La signature de couleur (§4.5) ne disparaît pas —
elle devient ce qui fait *tenir* la désignation entre deux appuis, au lieu
d'être le mécanisme d'identification à elle seule.

### 4.5 Signature de couleur du costume — retenue

Pas un modèle : un **histogramme de la zone torse** de la boîte de détection.

Trois propriétés qui collent exactement au problème posé :

1. **Elle fonctionne de dos.** Le costume est le même sous tous les angles.
   C'est la propriété que la reconnaissance faciale et les marqueurs n'ont pas,
   et c'est celle dont la scène a besoin.
2. **Elle ne souffre pas du décalage de domaine**, parce qu'elle **s'étalonne
   sur place** : ce costume, ce jour-là, sous cette lumière-là. Le défaut qui
   coûte 30 points à OSNet (§4.3) n'existe pas.
3. **Le théâtre lui donne un avantage que l'industrie n'a pas** : David est
   costumé, les passants sont en manteau. Le discriminant est fort par
   construction — c'est la seule piste qui *profite* du contexte au lieu de le
   subir.

Et le torse fait encore **40 px de large à 5 m** (§3) : largement de quoi.

---

## 5. Ce que cette étude ne règle PAS — à lire avant de se réjouir

**L'identification rend le comportement JUSTE. Elle ne le rend pas SÛR.**

Même avec une identification parfaite, le suivi **roues** en rue reste
dangereux, pour une raison qui n'a rien à voir avec l'identité :

> Un enfant passe entre David et Didier. Didier ne le voit pas — il n'a
> **aucune détection d'obstacle**. Ce qu'il voit, c'est la silhouette de David
> qui rétrécit parce qu'elle est masquée. Sa loi de commande en déduit « il
> s'éloigne » et **il accélère vers l'enfant**.

La distance est estimée par la **hauteur de la boîte** (`target_picker.py`), et
l'occlusion partielle est indiscernable de l'éloignement. Ce mode de
défaillance pousse dans la mauvaise direction, et l'identification ne le touche
pas.

**Donc : ce chantier sert le REGARD, pas les roues.** Les roues en rue restent
derrière leurs verrous existants — coup-de-poing (§2), test scénique au sol,
puis perception d'obstacle (lidar). C'est ce qui rend ce chantier praticable
tout de suite : **le regard ne déplace pas 50 kg.**

---

## 6. Proposition technique

### 6.1 La signature

Zone mesurée : **le torse**, découpé dans la boîte de détection — horizontalement
les 25-75 % centraux, verticalement les 15-50 % du haut. On évite ainsi la tête
(cheveux, visage), les jambes (mouvement, occlusion fréquente) et les bords de
boîte (qui contiennent du fond).

Descripteur : **histogramme 2D Teinte × Saturation en HSV**, la **Valeur
(luminosité) étant ignorée** — c'est ce qui donne la tolérance au passage
soleil/ombre, qui est le risque principal en extérieur.

⚠️ **Le piège à ne pas manquer** : pour un pixel peu saturé ou très sombre, la
teinte est du bruit pur. Un costume noir, blanc ou gris n'a pas de teinte
exploitable. Il faut donc **masquer les pixels sous un seuil de saturation et
hors d'une plage de valeur**, et compter séparément la fraction achromatique —
qui est elle-même un discriminant. Sans ça, un costume sombre produit une
signature aléatoire et le système paraîtra « instable » sans qu'on comprenne
pourquoi.

Comparaison : distance de Bhattacharyya (ou intersection d'histogrammes) entre
le candidat et la référence, avec un seuil d'acceptation.

Coût : quelques microsecondes sur une vignette de ~40×100 px. Négligeable
devant l'inférence MediaPipe.

### 6.2 Le comportement quand personne ne correspond

Décision proposée : **aucune correspondance ⇒ pas de cible**, donc le node se
tait, donc `GazeControl` part en `LOST` et ramène lentement le cou au centre —
le comportement existe déjà, il est testé, on ne rajoute pas d'état.

Théâtralement, c'est lisible : Didier perd David et regarde droit devant. Bien
plus juste qu'un robot qui fixe un inconnu.

### 6.3 La désignation — un bouton, et c'est du jeu

**Déclencheur : un bouton du gant** (§4.6 — `IHR` est libre, sa commande est
vide). David se place devant Didier, appuie, et Didier capture la signature de
la personne **la plus centrée dans l'image** sur quelques trames.

Pourquoi la plus centrée et non la plus grosse : parce que c'est **contrôlable
par David**. Il se met en face, il appuie — le geste est sans ambiguïté, même
si un badaud est plus près. La plus grosse, c'est précisément le critère qui
échoue aujourd'hui (§1).

**Ça ne trahit pas le §2** : le gant pilote déjà les roues, les bras, le cou et
les yeux en jeu. Il *est* l'interface de jeu, il n'y a pas de sortie de
personnage. Et se planter devant le robot pour qu'il vous regarde est une
adresse lisible pour le public, pas une manipulation technique.

**Pourquoi un bouton plutôt qu'une réplique** (c'était ma première proposition,
abandonnée) : la réplique dépendrait de la reconnaissance vocale, donc de la
VAD, donc du bruit de la rue — on ferait reposer le rattrapage sur le maillon
le plus fragile, exactement quand ça va mal. Le bouton est instantané, muet, et
marche dans une foule. La réplique reste possible **en plus**, plus tard.

**Le corollaire, qui est la vraie force du dispositif** : quand la signature
décroche (nuage, changement de costume, un passant trop semblable), David
**ré-appuie**. Pas de mode dégradé à concevoir, pas de récupération
automatique à rendre infaillible — un geste. C'est ce qui rend tout le reste
dimensionnable.

### 6.4 Où le code se branche

`TargetPicker.update()` reçoit aujourd'hui les boîtes et les dimensions de
l'image, **mais pas la trame**. Donc :

- un module **pur, sans ROS, testé** — `vision/tracking/identity.py` — qui sait
  calculer une signature et en comparer deux. Même philosophie que
  `follow_control.py` et `gaze_control.py` : toute la décision dans le module
  pur, les entrées/sorties dans le node ;
- le node calcule les signatures (il a la trame) et les passe à `TargetPicker`,
  qui **préfère la correspondance** au lieu de la plus grosse aire ;
- le contrat publié sur `/vision/person*` **ne change pas** — donc ni
  `gaze_follower` ni `person_follower` ne sont touchés. C'est ce qui permet de
  livrer sans rien risquer côté roues.

---

## 7. Comment on saura que ça marche — sans public et sans robot

Le robot est immobilisé (§2) et il n'y a pas de public. La mesure passe donc
par un **corpus vidéo de rue**, exactement comme l'étude interaction §6 ter a
prévu un corpus **audio** pour la détection de voix.

**Convergence à exploiter : c'est la même sortie.** Une campagne en rue peut
enregistrer les deux à la fois — l'ambiance sonore pour la VAD, la vidéo pour
l'identité. Une seule sortie, deux chantiers servis.

Protocole proposé, calqué sur celui du corpus audio :
- caméra **à la hauteur et avec l'objectif définitifs** (sinon on mesure une
  autre machine) ;
- David en **costume de scène**, dans les quatre situations de sa phrase :
  passants qui coupent, plusieurs personnes devant, interlocuteur plus proche
  que lui, sortie puis retour dans le champ ;
- prises **longues et continues**, et annoncées à voix haute (l'enregistrement
  se documente lui-même), passages soleil/ombre inclus — c'est le cas qui
  décide ;
- vérité terrain : marquer sur quelques dizaines d'images laquelle des boîtes
  est David, et mesurer le **taux de bonne désignation**.

⚠️ **Cadre légal.** Le §5.7 de l'étude déclenchement impose un dispositif type
tournage. Filmer des passants identifiables dans l'espace public est plus
sensible que capter de l'ambiance sonore. Le corpus vidéo doit rester **local,
non versionné** (le dépôt est public) et n'a pas vocation à être conservé
au-delà de la mesure.

---

## 8. Lots proposés

| Lot | Contenu | Dépend de |
|---|---|---|
| **I0** | Bouton `IHR` → topic `designate` : une ligne de config côté gant, l'abonnement côté vision. **Rien à fabriquer.** | rien |
| **I1** | `vision/tracking/identity.py` : signature + comparaison, module pur, tests unitaires (dont le cas achromatique du §6.1) | rien |
| **I2** | Câblage dans `person_tracker_node` + `TargetPicker` ; capture sur `designate` ; contrat `/vision/person*` inchangé | I0, I1 |
| **I3** | Corpus vidéo de rue + mesure du taux de bonne désignation (§7) | I2, une sortie |
| **I4** | Réglage des seuils sur le corpus, puis essai en rue avec le **gaze seul** | I3, retour du robot |
| **I5** | *(différé)* Repli UWB — seulement si le suivi roues autonome en rue devient un objectif ferme | arbitrage §4.4 |

**I0, I1 et I2 se font entièrement au banc, robot immobilisé.** I0 est de loin
le plus petit et il a de la valeur seul : même sans signature, un bouton qui
dit « regarde CETTE personne » corrige déjà le ratage du §1 tant que David
reste visible.

Deux dettes voisines relevées en passant, à traiter ailleurs :

- **`IHR` porte un nom mort.** `{NAME: "Inclino", CMD: {}}` : un bouton câblé,
  nommé d'après une fonction qui n'existe pas, et sans commande. C'est le même
  genre de contrat mort que ceux purgés le 11/07. Le réaffecter le remet au
  travail.
- **Le toggle `follow` n'est sur aucun bouton** — ni gant, ni gamepad : il faut
  le lancer en ligne de commande. Le câbler rend à David l'autorité sur les
  50 kg. C'est de la **sécurité**, pas de l'identification : chantier roues.

---

## 9. Ce qui reste ouvert

- **Le costume.** Le §4.5 suppose qu'il est visuellement distinctif. Le dépôt
  est public et la note de création vit hors dépôt : la question se tranche
  avec David, pas ici. ⚠️ Mais depuis le §4.6, **ce n'est plus bloquant** : si
  le costume se confond avec la rue, la signature tient moins longtemps et
  David ré-appuie plus souvent. On perd du confort, pas la fonction. C'est
  exactement ce qu'on gagne à mettre un humain dans la boucle.
- **Plusieurs personnes costumées** (un second comédien) : la signature seule
  ne suffirait plus, il faudrait deux références et un arbitrage.
- **Le seuil d'acceptation** : trop bas, Didier suit un inconnu ; trop haut, il
  perd David dès qu'un nuage passe. Il se règle sur le corpus (I2), pas à
  l'intuition.
- **L'articulation avec la FSM d'engagement** : est-ce que l'identité change
  les portes d'ENGAGED (par exemple, ne jamais s'engager avec David) ? À
  reprendre dans `etude-declenchement-conversation.md`, pas ici.
