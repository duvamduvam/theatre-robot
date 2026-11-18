# Spec A0 — le corps sûr (`didier_corps_sur`) : lidar, filtre des entrées autonomes, verrous

*Écrite le 2026-11-18 (Fable). Spec FERMÉE : un agent Opus l'implémente sans trancher. Elle
applique les décisions du 02/11 (`etude-autonomie-improvisation.md` §3.2, §3.3, §8, §9) et
l'ajout du 11/11 (essai du moniteur de collision Nav2) ; elle n'en re-tranche aucune. Ce qui
est nouveau ici est marqué « choix de la spec ». Trois questions restent pour David (§13) ;
chacune a un comportement par défaut, donc aucune ne bloque le début du travail.*

*Fait nouveau du 18/11 : le lidar est commandé — **SLAMTEC RPLIDAR C1**, livraison estimée
fin novembre - début décembre. Objectif de David : Didier dans la rue fin février 2027 avec
des essais d'autonomie, préparés à la maison.*

## 0. Ce que A0 prouve, et ce qu'il ne prouve pas

**Prouve** : qu'aucune consigne de roues venue d'une source autonome (suivi, route, séquence
à piste roues, pilotage web) n'atteint `twist_mux` sans être passée par un filtre déterministe
qui (1) met zéro dès qu'un obstacle est à moins de 0,6 m de la caisse, (2) ralentit par palier
entre 0,6 et 1,2 m, (3) met zéro **et se verrouille** si le lidar se tait, si le superviseur
disparaît ou si l'arrêt d'urgence tombe, (4) refuse tout mouvement autonome tant que le lidar
n'a pas prouvé qu'il vit. Porte de sortie de l'étude (§9) : obstacle à 0,5 m → zéro en moins de
200 ms, 20 essais sur 20, en sim ; puis protocole caméra avec épreuve d'obstacle.

**Ne prouve pas, et ne fait pas** :

- **La télécommande (priorité 100) et le deadman ne changent pas.** `cmd_vel_remote` ne passe
  pas par le filtre : David garde la main même contre un obstacle. La chaîne du 04/07
  (`twist_mux` → `twist_deadman` 400 ms → `cmd_vel` → `wheels_node`, deadman local) reste la
  dernière ligne.
- **Le vide.** Un lidar 2D voit une tranche horizontale. Bordures, marches, trous, câbles au
  sol : invisibles. David reste la protection contre le vide (étude §3.2).
- **Ce qui est hors de la tranche** : plateau de table, guidon, bras tendu, objet couché plus
  bas que le plan de balayage. La marge de 0,6 m en couvre une partie, pas tout.
- **Les surfaces qui ne renvoient rien** (vitre, miroir, noir mat, plein soleil) : mesurées au
  banc (§10.1), pas garanties.
- **L'arrêt matériel** : c'est la refonte électrique et W1. Le corps sûr obéit à `e_stop`, il
  ne le remplace pas.
- **Le jeu autour du gel** (Didier râle quand il est bloqué) : A1/A+. A0 publie l'état qui le
  rendra possible.
- **L'unification `cmd_vel_auto`** (le sélecteur seul publieur, étude §3.2) : lot du sélecteur
  réel. A0 filtre chaque canal existant par son nom, quel que soit son publieur.

## 1. Le RPLIDAR C1 — ce qui est vérifié à la source

Sources lues le 18/11 : fiche technique SLAMTEC C1 v1.0 du 13/10/2023, modèle C1M1-R2
([PDF](https://files.waveshare.com/wiki/RPLIDAR-C1/SLAMTEC_rplidar_datasheet_C1_v1.0_en.pdf)) ;
page de spécifications SLAMTEC ([lien](https://www.slamtec.com/en/c1/spec)) ; dépôt du pilote
([`Slamtec/sllidar_ros2`](https://github.com/Slamtec/sllidar_ros2), fichiers
`src/sllidar_node.cpp`, `launch/sllidar_c1_launch.py`, `scripts/rplidar.rules`) ; index des
paquets Jazzy ([`ros/rosdistro`, `jazzy/distribution.yaml`](https://github.com/ros/rosdistro/blob/master/jazzy/distribution.yaml)).

| Point | Valeur lue | Source |
|---|---|---|
| Principe, laser | temps de vol, 905 nm (895-915), classe 1 (IEC 60825) | fiche, fig. 2-2 |
| Portée | 0,05 à 12 m sur blanc (70 %), 0,05 à 6 m sur noir (10 %) ; hors bornes, des points sortent encore, « pour référence seulement » | fiche, fig. 2-1, note 1 |
| Cadence d'échantillonnage | 5 kHz (fluctuation < 1 %) | fiche, note 2 |
| Fréquence de balayage | 8 à 12 Hz, 10 Hz typique (fluctuation < 5 % à l'arrêt) | fiche, note 3 |
| Résolution angulaire | 0,72° typique, soit 500 points par tour à 10 Hz (5000 / 10) | fiche ; division |
| Précision, résolution en distance | ± 30 mm (cible de 10 à 90 % de réflexion, 25 °C), 15 mm | fiche, note 4 |
| Planéité du plan de balayage | 0° à 1,5° | fiche |
| Lumière ambiante | limite annoncée **40 000 lux** | fiche |
| Interface | **UART TTL 3,3 V, 460 800 bauds, 8N1** ; connecteur XH2.54-5P (VCC, TX, RX, GND) | fiche, fig. 2-5 à 2-8 |
| Alimentation | 5 V (4,8 à 5,2), ondulation ≤ 150 mV ; **800 mA au démarrage**, 230 mA typique (260 max) à 10 Hz | fiche, fig. 2-7 |
| Moteur | ne démarre ni ne s'arrête seul : il suit la commande de balayage | fiche |
| Auto-protection | coupe le laser et le balayage si la vitesse est instable ou trop lente, ou si l'alimentation est basse | fiche |
| Repère du capteur | **main gauche**, angle croissant dans le sens horaire, axe x = « droit devant » | fiche, fig. 2-4 |
| Indice de protection, température | IP54 ; −10 à 40 °C en service | fiche |
| Masse, taille | 110 g ; 55,6 × 55,6 × 41,3 mm | fiche ; page SLAMTEC |
| Pilote ROS 2 | `sllidar_ros2`, licence BSD-2 ; README : foxy, galactic, humble, rolling — **Jazzy n'est pas cité** ; dernier commit le 17/06/2024 (« set the minimum distance to 5cm »), support du C1 depuis le 31/10/2023 | dépôt |
| Paquet binaire Jazzy | `sllidar_ros2` **absent** de rosdistro Jazzy ; `rplidar_ros` y est en **2.1.0**, alors que le support du C1 n'est que dans la partie « Forthcoming » du journal de sa branche `ros2` → **le binaire `ros-jazzy-rplidar-ros` ne pilote pas le C1** ; il faut compiler depuis les sources | rosdistro ; `CHANGELOG.rst` de `Slamtec/rplidar_ros` |
| Message | `sensor_msgs/LaserScan` sur `scan` (relatif), QoS `KeepLast(10)` fiable ; `range_min` = 0,05 en dur ; une distance nulle devient `+inf` ; horodatage = horloge de l'hôte **au début** de la lecture du tour | `sllidar_node.cpp` |
| Lancement C1 | port `/dev/ttyUSB0`, 460 800 bauds, `frame_id` = `laser` (défaut du nœud : `laser_frame`), `angle_compensate` vrai, `scan_mode` = `Standard` | `sllidar_c1_launch.py` |
| Règle udev fournie | CP210x seulement (`10c4:ea60`), `MODE 0777`, lien `/dev/rplidar` | `scripts/rplidar.rules` |

**Non vérifié, donc « à mesurer » au banc (§10.1)** : compilation de `sllidar_ros2` sous Jazzy ;
nombre de rayons par message avec `angle_compensate` ; orientation réelle du repère `laser_frame`
après la conversion du pilote ; comportement du pilote quand l'USB est arraché (il boucle sans
se terminer, d'après le code : à confirmer) ; charge sur le Pi 4 ; tenue de l'alimentation USB
du Pi 4 au démarrage du moteur ; nombre de retours en plein soleil (le plein soleil direct
dépasse 40 000 lux, ordre de grandeur usuel non relu à la source) ; retours sur vitre, miroir,
tissu noir. **Adaptateur USB-série** : celui de l'annonce n'est pas confirmé
(`hardware/achats-refonte.md`) ; David branche le sien (460 800 bauds, niveaux 3,3 V).

## 2. Incohérence relevée, à ne pas enterrer

`hardware/overview.md` § lidar (13/07 et 27/08) écrit : « 360° n'est PAS nécessaire », montage
bas à l'avant, arrière masqué par le corps, pas de marche arrière autonome. L'étude **décidée
le 02/11** écrit l'inverse et le motive : arrêt dur sur **360°**, parce que Didier pivote, fait
« un pas en arrière », et que `moon-walk` recule. Le support imprimable dessiné
(`plans/supports/support-lidar-c1`) est celui du montage avant. L'emplacement réel n'est pas
décidé (`etude-interieur-etages-cablage.md`, D13 : « à placer avec David sur le robot »).

Conséquence, traitée par la spec et non par un choix silencieux :

- le logiciel est **indépendant du montage** : il calcule ce que le lidar voit vraiment
  (§5.4) et **refuse tout mouvement vers ce qu'il ne voit pas** ;
- la sim sert, avant l'arrivée du capteur, à comparer les emplacements (§8.3) ;
- le choix de l'emplacement et son prix sont la question 1 du §13 ;
- `hardware/overview.md` est corrigé au sous-lot A0-7 (la règle du 02/11 prime).

## 3. Architecture

### 3.1 Où s'insère le filtre

```
télécommande ─ wheels ─► wheels_bridge ─► cmd_vel_remote ─────────────────────(prio 100)─┐
                              │ (StringTime.anim)                                         ▼
séquences ────────────────────┴─► cmd_vel_anim ───┐                                  twist_mux ─► cmd_vel_mux ─► twist_deadman ─► cmd_vel ─► wheels_node
suivi, route (fault_relay) ─────► cmd_vel_follow ─┼─► CORPS SÛR ─► cmd_vel_anim_sur ──(prio 10)─┤      ▲                (400 ms)             (deadman local)
pont web ───────────────────────► cmd_vel_web ────┘        │   ─► cmd_vel_follow_sur (prio 20)─┤      │
                                                           │   ─► cmd_vel_web_sur ────(prio 50)─┘      │
   scan (lidar) ──────────────────────────────────────────►│                                           │
   superviseur/battement, e_stop, corps_sur/rearmer ──────►│        e_stop (verrou 255, inchangé) ─────┘
                                                           └─► corps_sur/etat (latché), diagnostics
```

- **Avant le mux, obligatoirement** (étude §3.2) : après lui, un `Twist` ne porte plus sa
  source, et la télécommande serait filtrée avec le reste.
- **Trois canaux, un pour un.** Chaque entrée garde sa sortie et sa priorité. Les publieurs
  ne changent pas (`wheels_bridge`, `person_follower`, `route_driver`, `fault_relay`,
  `web_bridge`) ; les épreuves existantes qui lisent `cmd_vel_follow` lisent désormais la
  **demande**, plus ce qui atteint le mux.
- **Le seul changement dans la chaîne existante** : `config/twist_mux.yaml` s'abonne à
  `cmd_vel_web_sur`, `cmd_vel_follow_sur`, `cmd_vel_anim_sur` au lieu des trois noms bruts.
  `remote`, les priorités, les délais de 0,5 s et le verrou `e_stop` sont inchangés.
- **Sûr par construction** (règle du 27/08, `chantiers.md`) : le filtre est EN LIGNE. S'il
  meurt, se fige ou n'est pas lancé, plus rien n'arrive sur les `_sur`, le mux se tait, le
  deadman met zéro en 400 ms. Aucune sécurité ne se déduit de l'absence d'un veto.
- **`cmd_vel_remote` n'y passe pas** : c'est la décision (prio 100, David). `e_stop` reste un
  verrou du mux, qui coupe aussi la télécommande.

### 3.2 Topics (tous RELATIFS, sous `/<ROBOT_NAME>/`)

| Topic | Type | Sens | QoS | Note |
|---|---|---|---|---|
| `scan` | `sensor_msgs/LaserScan` | entrée | best effort, profondeur 1 | compatible avec le pilote (fiable) et le pont Gazebo ; on ne veut que le plus récent |
| `cmd_vel_anim`, `cmd_vel_follow`, `cmd_vel_web` | `geometry_msgs/Twist` | entrée | fiable, profondeur 1 | la dernière consigne seule compte |
| `cmd_vel_anim_sur`, `cmd_vel_follow_sur`, `cmd_vel_web_sur` | `geometry_msgs/Twist` | sortie | fiable, profondeur 10 | comme la chaîne actuelle |
| `e_stop` | `std_msgs/Bool` | entrée | fiable, profondeur 10 | le même que le verrou du mux ; source = W1 |
| `superviseur/battement` | `std_msgs/Empty` | entrée | best effort, profondeur 1 | **contrat posé ici pour A-préalables** : la télécommande le publie à 5 Hz au moins ; tout message vaut « présent » |
| `corps_sur/rearmer` | `std_msgs/Empty` | entrée | fiable, profondeur 10 | lève un verrou si sa cause a disparu (§5.6) |
| `corps_sur/etat` | `theatre_interfaces/StringTime` | sortie | `latched()` de `theatre_contrats.qos` | JSON, publié à chaque changement seulement (§5.7) |
| `diagnostics` | `diagnostic_msgs/DiagnosticArray` | sortie | fiable, profondeur 10 | 1 Hz ; règle du 11/11 : la santé du matériel va sur `diagnostics` |

Les noms entrent dans `theatre_contrats/topics.py` (`SCAN`, `CMD_VEL_*_SUR`,
`SUPERVISEUR_BATTEMENT`, `CORPS_SUR_ETAT`, `CORPS_SUR_REARMER`) et dans son test d'inventaire.

### 3.3 Fréquences et budget de latence

- Le nœud est **mono-fil**, piloté par les événements : chaque `Twist` entrant est filtré et
  republié dans le même rappel ; chaque `scan` met l'état des zones à jour ; une minuterie à
  **20 Hz** surveille les péremptions et publie l'état.
- **Zéro anticipé** : à l'instant où l'état passe à ARRET ou VERROU, le nœud publie un `Twist`
  nul sur chaque canal **actif** (une entrée reçue depuis moins de 0,5 s, le délai du mux).
  C'est la seule publication qui ne répond pas à une entrée, et elle ne peut être que nulle.
  Sans elle, l'arrêt attendrait la prochaine consigne de la source (jusqu'à 100 ms).
- Hors ce cas : **une sortie par entrée, jamais de consigne propre** (étude §3.2). Une source
  qui se tait fait taire sa sortie, et le délai du mux puis le deadman jouent comme aujourd'hui.

Budget de la porte « obstacle à 0,5 m → zéro en moins de 200 ms », en sim :

| Maillon | Budget | Nature |
|---|---|---|
| attente du balayage suivant (10 Hz) | ≤ 100 ms | par construction |
| pont Gazebo → ROS, transport entre conteneurs | ≤ 10 ms | à mesurer (CS2) |
| rappel `scan` du corps sûr (500 à 720 points, Python pur) | ≤ 5 ms sur le PC | à mesurer (CS2) |
| zéro anticipé → `twist_mux` → `twist_deadman` → `cmd_vel` | ≤ 10 ms | à mesurer (CS2) |
| **total** | **≤ 125 ms**, marge 75 ms | |

Sur le vrai capteur s'ajoute le temps du tour lui-même : le pilote publie le tour **complet**,
horodaté à son début, donc un point a entre 0 et environ 100 ms d'âge à la publication, et un
obstacle qui surgit juste derrière le faisceau attend un tour de plus. Pire cas théorique :
environ 200 ms avant le rappel, puis les mêmes 25 ms. **Valeur réelle : à mesurer** (§10.1 et
§10.2), ainsi que la distance d'arrêt des roues, qui dépend de la calibration PWM.

## 4. Géométrie

### 4.1 La caisse

« À moins de 0,6 m **de la caisse**, pas du centre » (étude §3.2). La caisse est modélisée par
un rectangle dans `base_link` (x vers l'avant, y vers la gauche, origine au centre de la boîte
de collision de l'URDF) :

| Paramètre | Défaut | D'où vient le défaut (`dadou_robot.urdf.xacro`, cotes « estimées depuis les photos ») |
|---|---|---|
| `x_avant` | +0,30 m | face avant de la boîte : +0,275 |
| `x_arriere` | −0,57 m | bout de la roue folle : −0,45 − 0,10 = −0,55 |
| `demi_largeur` | 0,40 m | valeur de l'étude ; l'URDF donne 0,3275 au flanc extérieur des roues (0,29 + 0,0375) : 0,40 est le majorant |
| `x_essieu` | +0,10 m | axe des roues motrices (centre de rotation d'un pivot) |
| `rayon_balayage` | 0,65 m | de l'essieu au point le plus éloigné de la caisse (bout de la flèche arrière) |

**À mesurer sur le robot** (David, mètre ruban, 5 cotes, sous-lot A0-7) ; les valeurs mesurées
vont dans `machines/robot/corps_sur.yaml`. La sim garde les défauts.

`distance_caisse(x, y)` = distance euclidienne du point au rectangle (0 dedans). La **zone
d'arrêt** est l'ensemble des points à moins de 0,6 m : le rectangle gonflé, coins arrondis.

**Invariant du pivot, vérifié au démarrage** : le disque balayé par la caisse quand elle
pivote (centre `(x_essieu, 0)`, rayon `rayon_balayage`) doit tenir dans la zone d'arrêt avec
5 cm de garde : `max distance_caisse(point du cercle) ≤ marge_arret − 0,05`. Avec les défauts :
0,10 + 0,65 − 0,30 = **0,45 ≤ 0,55**. C'est ce qui rend vraie la règle de l'étude « rotation
seulement si rien à moins de 0,6 m sur tout le tour » : si la zone est vide, pivoter ne touche
aucun obstacle immobile. Une configuration qui viole l'invariant est **refusée** (le nœud
s'arrête : plus aucune sortie, donc aucun mouvement autonome).

### 4.2 Le lidar : repère, pose, masques, témoin

- **Repère** : `frame_id` = `laser_frame`, imposé en paramètre au pilote (son lancement C1 dit
  `laser`). Convention ROS : x devant, angles dans le sens trigonométrique. La conversion du
  repère « main gauche » du capteur est faite par le pilote ; **l'orientation réelle se vérifie
  au banc** (un carton à gauche doit sortir à y > 0) et se corrige par `lacet_rad`.
- **Pose dans `base_link`** : `lidar: {x, y, lacet_rad}` dans le fichier de configuration du
  corps sûr. **Pas de TF sur le chemin de sécurité** : le module pur reçoit la pose en
  paramètre. Le montage tête en bas se règle par le paramètre `inverted` du pilote.
- **Hauteur du plan** : visée 0,25 m du sol (fenêtre 0,20-0,30 de `hardware/overview.md`,
  non re-tranchée). Elle n'entre pas dans le calcul (2D) ; elle est consignée dans le YAML.
- **Masques** : le lidar voit le corps de Didier. Les secteurs correspondants sont exclus :
  `masques_deg: [[début, fin], …]` dans `laser_frame`. Ils se **mesurent** (outil
  `mesurer_masques`, §6.3) en espace dégagé, jamais ne se devinent : tout angle où un retour
  tombe dans la caisse gonflée de 5 cm sur 100 balayages est masqué, élargi de 2° de chaque côté.
- **Un retour dans la caisse hors masque** vaut obstacle (ARRET, motif `retour_dans_caisse`).
  Des masques faux se voient donc tout de suite : Didier ne bouge pas.
- **Témoin de vie optique** (choix de la spec) : un capteur aveuglé (capot posé, vitre sale,
  laser coupé) renvoie « rien », ce qui ressemble à « voie libre ». Si la mesure des masques
  trouve des auto-retours **stables** (au moins 5 points, écart-type < 2 cm sur 100 balayages,
  à plus de 0,05 m), ils deviennent le témoin : `temoin: {exige: true, secteur_deg, distance_m:
  [min, max], points_min}`. Un balayage sans son témoin est **invalide**. S'il n'y a pas
  d'auto-retour exploitable, `exige: false` et la limite est écrite dans le YAML et dans
  `diagnostics` (niveau WARN permanent). Le témoin ne détecte pas un aveuglement partiel par
  le soleil dans le secteur avant : c'est une mesure du banc, pas une garantie.

### 4.3 Validité d'un point et d'un balayage

Un **point** compte si sa distance est finie, `portee_min_m` (0,05) ≤ r ≤ `portee_max_m` (12),
et si son angle est hors masque. `inf`, `NaN`, 0 et hors bornes : ni obstacle ni preuve de vie.

Un **balayage** est valide, donc nourrit le chien de garde du capteur, si tout ceci est vrai :
au moins `rayons_min` (300) rayons ; `header.stamp` strictement postérieur au précédent (un
republieur figé ne nourrit rien) ; âge à la réception (horloge du nœud − `stamp`) ≤
`age_max_reception_s` (0,25, à caler au banc) ; témoin présent s'il est exigé.

## 5. Règles du filtre (logique pure)

### 5.1 Zones

| Zone | Condition sur `d_min` = plus petite `distance_caisse` des points valides | Effet |
|---|---|---|
| **ARRET** | `d_min` < `marge_arret_m` (**0,60**) : un seul point, un seul balayage suffisent | zéro sur les trois canaux, linéaire ET angulaire |
| **RALENTI** | 0,60 ≤ `d_min` < `marge_ralenti_m` (**1,20**) | consigne multipliée par `facteur_ralenti` (**0,5**) : un palier, pas une proportion (plancher PWM, étude §3.2) |
| **LIBRE** | sinon | plafonds seulement |

- **Entrée immédiate, sortie retardée** : on quitte ARRET quand `d_min` ≥ 0,60 +
  `hysteresis_m` (0,05) pendant `balayages_de_sortie` (3) balayages valides de suite ; même
  règle pour quitter RALENTI (1,25). Un faux arrêt est une gêne, un arrêt manqué un accident.
- L'arrêt de zone **n'est pas un verrou** : Didier repart seul quand la voie se libère (le gel
  est un cas de jeu, étude §3.2).
- La zone est **la même tout autour** (pas de zone par direction) : « rien à moins de 0,6 m
  sur tout le tour », y compris pour avancer. Un obstacle derrière arrête la marche avant.
- **Conséquence pour David** : avec un lidar qui voit l'arrière, se tenir à moins de 0,6 m du
  bout de la flèche (soit 1,2 m du centre) gèle Didier.

### 5.2 Ce que le lidar ne voit pas (choix de la spec, découle du §2)

`couverture.py` découpe la bande d'arrêt (zone d'arrêt moins la caisse) en quatre régions —
AVANT (x > `x_avant`), ARRIERE (x < `x_arriere`), FLANC_G, FLANC_D — et l'échantillonne au pas
de 5 cm. Un échantillon est **aveugle** si son relèvement vu du lidar tombe dans un masque.
Une région est **vue** si sa part aveugle est ≤ `part_aveugle_max` (0,10). Calcul fait une fois
au démarrage, publié dans l'état.

| Mouvement demandé | Exigence | Sinon |
|---|---|---|
| avancer (v > 0) | AVANT vue | zéro, motif `avant_aveugle` |
| reculer (v < 0) | ARRIERE vue | zéro, motif `recul_aveugle` |
| tourner (ω ≠ 0), seul ou en arc | les quatre régions vues | si `angulaire_aveugle_autorise` est vrai **et** AVANT vue : accepté, plafonné à `w_max_aveugle` ; sinon zéro, motif `tour_aveugle` |

`angulaire_aveugle_autorise` vaut **faux** par défaut dans le code. Le passer à vrai dans le
fichier d'une machine est une décision de David, datée en commentaire dans le YAML (§13, Q1).

### 5.3 Transformation d'une consigne

`filtrer(v, ω, canal, etat) → (v', ω', motif)`, dans cet ordre :

1. consigne non finie (`NaN`, `inf`) → (0, 0), `consigne_invalide` ; seuls `linear.x` et
   `angular.z` sont lus, les quatre autres composantes sortent à zéro ;
2. état global autre que ARME → (0, 0), motif = l'état ;
3. zone ARRET → (0, 0) ;
4. mouvement vers une région non vue (§5.2) → (0, 0) ;
5. plafonds du canal : facteur `k = min(1, v_max/|v|, w_max/|ω|)` (avec `w_max_aveugle` si le
   cas du §5.2 s'applique), **appliqué aux deux composantes** ;
6. zone RALENTI → multiplication des deux composantes par `facteur_ralenti`.

**Règle gravée : le filtre ne change jamais la courbure.** Il met tout à zéro ou il réduit v et
ω du même facteur ; il ne supprime jamais une seule composante (aller tout droit au lieu de
tourner serait une trajectoire que personne n'a demandée).

### 5.4 Vitesses par machine

| | sim (`terrain: sim`) | robot (`terrain: reel`) |
|---|---|---|
| `follow` : `v_max`, `w_max` | 0,5 m/s, 1,0 rad/s (= `ABS_MAX_LIN`/`ABS_MAX_ANG` des sources : aucun changement de comportement) | **0,25 et 0,5, provisoires** |
| `web` | 0,5, 1,0 (= défauts de `web_bridge`) | 0,25 et 0,5, provisoires |
| `anim` | 0,9, 3,2 (≥ borne des données : consigne ≤ 0,89 par roue, soit ω ≤ 2 × 0,89 / 0,58 = 3,07) | 0,25 et 0,5, provisoires |
| `w_max_aveugle` | 1,0 (personne en sim) | **0,3, provisoire** |
| `duree_max_mouvement_s` | 0 = désactivé (la vérité terrain tient lieu d'odométrie) | **4,0** (étude §3.2) |
| `superviseur.exige` | faux (les épreuves existantes n'ont pas de battement) | faux **tant que le battement n'existe pas** (maison : non bloquant, étude §3.4) ; **vrai obligatoire avant la rue** |

Sur le robot, un `Twist` de 1,0 vaut aujourd'hui 100 % de PWM (`max_wheel_speed` = 1,0,
« calibration à venir ») : 0,25 = 25 % de PWM, la valeur du protocole du 04/07. Les valeurs
« provisoires » sont remplacées par celles de la **calibration PWM** (A-préalables) ; la cible
reste le pas de flâneur (environ 0,3 m/s, étude). Si la distance d'arrêt mesurée au sol dépasse
0,20 m, on baisse `v_max`, jamais la marge.

### 5.5 Durée bornée (pas d'odométrie)

Si `duree_max_mouvement_s` > 0 : dès qu'une sortie non nulle dure plus que cette valeur sans
interruption, état `PAUSE_DUREE`, zéro sur les trois canaux, jusqu'à ce que **toutes** les
entrées soient nulles ou muettes pendant `pause_s` (1,0). Pas un verrou. Sur le robot,
`moon-walk` et toute piste roues de plus de 4 s sont donc coupées : c'est la borne décidée.

### 5.6 États globaux et verrous

```
DEMARRAGE ──(capteur sain 1 s, superviseur présent si exigé, e_stop faux)──► ARME
ARME ──(capteur perdu | superviseur perdu | e_stop vrai)──► VERROU(cause)
VERROU ──(corps_sur/rearmer ET cause disparue)──► ARME
```

| Cause | Déclenchement | Valeur décidée |
|---|---|---|
| `capteur_absent` (DEMARRAGE) | aucun balayage valide depuis le lancement | autonomie refusée |
| `capteur_perdu` | pas de balayage valide depuis plus de `capteur.perime_s` | **0,30 s** → zéro et verrou |
| `superviseur_absent` (DEMARRAGE) | exigé et jamais entendu | autonomie refusée |
| `superviseur_perdu` | exigé et muet depuis plus de `superviseur.perime_s` | **1,0 s** → zéro et verrou |
| `e_stop` | `e_stop` vrai (jamais reçu = faux, comme le mux : aucune source avant W1) | zéro et verrou ; le mux coupe aussi la télécommande |

- **DEMARRAGE s'arme seul** quand tout est sain depuis `sante_s` (1,0 s) : rien n'a été perdu.
  **Un VERROU ne se lève que par `corps_sur/rearmer`**, refusé (et journalisé) tant que la
  cause est là ou que le capteur n'est pas sain depuis 1 s. Relâcher l'arrêt d'urgence rend
  la télécommande, pas l'autonomie.
- Le nœud est lancé **sans relance automatique** (`respawn` faux) : un redémarrage du nœud
  repasserait par DEMARRAGE et effacerait un verrou. S'il meurt, l'autonomie est morte
  jusqu'au redémarrage du conteneur, qui est un geste voulu.
- Toutes les horloges sont celle du nœud (`use_sim_time` en sim), passées en argument à la
  logique pure, comme `TwistDeadman`.
- **Bornes dures** (`reglages.py` refuse le fichier, le nœud ne démarre pas) :
  `marge_arret_m` ≥ 0,60 ; `marge_ralenti_m` ≥ `marge_arret_m` + 0,30 ; `capteur.perime_s` ≤
  0,30 ; `superviseur.perime_s` ≤ 1,0 ; `facteur_ralenti` ≤ 0,5 ; `v_max` ≤ 0,9 ;
  `part_aveugle_max` ≤ 0,10 ; `terrain: sim` hors `ROS_DOMAIN_ID=43`. Une configuration ne
  peut qu'être plus stricte que la décision.

### 5.7 État publié

`corps_sur/etat` (JSON dans `StringTime`, à chaque changement) :
`{"etat": "ARME|DEMARRAGE|VERROU", "cause": "…", "zone": "LIBRE|RALENTI|ARRET|PAUSE_DUREE",
"d_min_m": 0.72, "vue": {"avant": true, "arriere": false, "flanc_g": false, "flanc_d": false},
"superviseur": "present|absent|non_exige", "temoin": "ok|absent|non_exige", "terrain": "sim"}`.
`d_min_m` est arrondi à 5 cm pour ne pas republier à chaque balayage. `diagnostics` porte en
plus : âge du dernier balayage, rayons reçus, points valides, dernier motif de refus par canal,
durée du rappel `scan` (max sur 1 s). Niveau ERROR en VERROU, WARN si `superviseur` ou `temoin`
vaut `non_exige` sur `terrain: reel`.

## 6. Le package `packages/didier_corps_sur/` (génération 2 : logique pure, nœud mince)

```
packages/didier_corps_sur/
├── package.xml, setup.py, setup.cfg, resource/, README.md (README-contrat, table des mutants)
├── config/corps_sur.yaml        # défauts SÛRS (terrain reel, superviseur exigé, angulaire aveugle refusé)
├── didier_corps_sur/
│   ├── geometrie.py    # Caisse, PoseLidar, distance_caisse, points_dans_base, invariant du pivot
│   ├── balayage.py     # validité des points et d'un balayage, masques, témoin → Lecture
│   ├── couverture.py   # régions vues / aveugles (§5.2)
│   ├── zones.py        # LIBRE / RALENTI / ARRET avec hystérésis
│   ├── garde.py        # DEMARRAGE / ARME / VERROU, péremptions, réarmement, durée bornée
│   ├── filtre.py       # filtrer(v, w, canal, etat) (§5.3)
│   ├── reglages.py     # lecture du YAML, bornes dures
│   └── corps_sur_node.py   # abonnements, publications, minuterie 20 Hz — AUCUNE règle ici
├── tools/
│   ├── mesurer_masques.py    # 100 balayages → masques, témoin, couverture, extrait YAML
│   └── couverture_poses.py   # table de couverture pour une liste de poses (§8.3)
└── test/
```

### 6.1 Contraintes de code

- Les sept modules de logique n'importent **ni rclpy ni numpy** : stdlib seule (plus PyYAML
  dans `reglages.py`, déjà requis par `drive.launch.py`), testés sur le
  PC avec `.venv` (suite ajoutée à `docs/operations.md` et à la CI `tests.yml`).
- Le nœud n'a aucun `if` de règle : il convertit des messages en appels et des retours en
  messages. Un test de contrat (modèle : `didier_jeu/test/test_contrat_node.py`) grave noms de
  topics, types et QoS.
- Fichier de configuration : paramètre `config` du nœud (chemin). Défaut du lancement :
  `/home/ros2_ws/src/robot/conf/corps_sur.yaml` (= `machines/robot/corps_sur.yaml`, la conf de
  la machine). La sim passe `corps_sur_config:=/home/ros2_ws/sim/corps_sur.yaml` par
  `machines/sim/robot/entree.sh` (même mécanique que `exiger_validation_roues`). Fichier
  absent ou refusé : le nœud s'arrête avec une erreur lisible.
- `mypy` sur tout le package (code neuf, consigne du 07/11).

### 6.2 Tests à valeurs gravées (extraits obligatoires ; l'attendu est écrit en dur, jamais recalculé par la fonction testée)

| Module | Cas | Attendu gravé |
|---|---|---|
| `geometrie` | `distance_caisse` avec la caisse par défaut : (0,90 ; 0) · (0,80 ; 0) · (0,60 ; 0,80) · (0 ; 0,95) · (−1,17 ; 0) · (0 ; 0) | 0,60 · 0,50 · 0,50 (triangle 0,3-0,4-0,5) · 0,55 · 0,60 · 0 |
| `geometrie` | invariant du pivot, défauts ; puis `x_essieu` = 0,30 | 0,45 accepté ; 0,65 refusé |
| `geometrie` | lidar en (0,33 ; 0), lacet 0 : rayon d'angle 0 à 0,56 m ; d'angle 90° à 0,90 m ; lacet π, angle 0 à 0,50 m | points (0,89 ; 0) → 0,59 ; (0,33 ; 0,90) → 0,501 (dx 0,03, dy 0,50) ; (−0,17 ; 0) → 0 |
| `balayage` | 500 rayons à `inf` sauf un à 0,56 m devant ; le même dans un masque ; le même à 0,04 m ; `NaN` | ARRET ; ignoré ; ignoré ; ignoré |
| `balayage` | 299 rayons ; `stamp` égal au précédent ; âge 0,26 s ; témoin exigé et absent | quatre balayages invalides, quatre motifs distincts |
| `zones` | suite de `d_min` : 1,30 · 1,10 · 0,59 · 0,62 · 0,66 · 0,66 · 0,64 · 0,66 · 0,66 · 0,66 | LIBRE · RALENTI · ARRET · ARRET · ARRET · ARRET · ARRET · ARRET · ARRET · RALENTI |
| `garde` | dernier balayage valide à t = 1,00 ; tics à 1,25 et 1,35 (jamais un tic pile sur le seuil : arrondi flottant) | ARME ; VERROU `capteur_perdu` |
| `garde` | dernier battement à t = 5,00 (exigé) ; tics à 5,95 et 6,05 | ARME ; VERROU `superviseur_perdu` |
| `garde` | réarmement : cause présente ; capteur sain depuis 0,9 s ; depuis 1,1 s | refusé ; refusé ; ARME |
| `garde` | durée 4,0 : sortie non nulle de t = 0 à 4,05 ; entrées nulles 0,9 s ; 1,1 s | `PAUSE_DUREE` à 4,05 ; maintenue ; levée |
| `filtre` | LIBRE, plafonds 0,25/0,5 : (0,4 ; 0,2) · RALENTI, même entrée | (0,25 ; 0,125) · (0,125 ; 0,0625) |
| `filtre` | tour non vu, autorisé, `w_max_aveugle` 0,3 : (0,2 ; 0,6) · non autorisé | (0,1 ; 0,3) · (0 ; 0) `tour_aveugle` |
| `filtre` | ARRIERE non vue : (−0,2 ; 0) · ARRET : (0,3 ; 0,4) · (`NaN` ; 0) | (0 ; 0) `recul_aveugle` · (0 ; 0) · (0 ; 0) `consigne_invalide` |
| `filtre` | propriété, 1 000 tirages à graine fixe | sortie nulle, ou `v'/ω'` = `v/ω` à 1e-9 près |
| `couverture` | masque [90° ; 270°] avec lidar en (0,33 ; 0) ; aucun masque ; masque [170° ; 190°] | AVANT vue seule ; quatre vues ; valeurs de part aveugle calculées UNE fois par une seconde méthode (intégration à la main ou pas de 1 cm) puis gravées |
| `reglages` | chaque borne dure du §5.6, franchie d'un cran | huit refus, huit messages |

### 6.3 Contrôle par mutation (obligatoire avant fusion)

Douze mutants appliqués à la main, un par un ; chacun doit faire rougir au moins un test ; la
table (mutant → test tombé) est recopiée dans le README du package. Un mutant qui survit est
un test à écrire, pas une case à cocher.

1. `< marge_arret` devient `< marge_arret − 0,1` ; 2. les masques ne sont plus appliqués ;
3. `min` devient `max` dans le facteur de plafond ; 4. la sortie d'ARRET ignore l'hystérésis ;
5. la comparaison d'âge du capteur est inversée ; 6. `e_stop` n'est plus lu ; 7. le témoin
n'est plus vérifié ; 8. le signe de `lacet_rad` est inversé ; 9. en ARRET, `filtrer` rend
l'entrée ; 10. le réarmement n'examine plus la cause ; 11. le ralenti ne touche que v ;
12. (nœud) le zéro anticipé est supprimé → l'épreuve CS2 doit dépasser 200 ms sur une source
publiée à 5 Hz.

## 7. Insertion dans le dépôt (liste fermée des fichiers touchés hors du nouveau package)

| Fichier | Changement |
|---|---|
| `packages/didier_drive/config/twist_mux.yaml` | trois noms de topics (`_sur`), commentaires |
| `packages/didier_drive/launch/drive.launch.py` | nœud `corps_sur` (package `didier_corps_sur`, dans le groupe du namespace, `respawn` faux), argument `corps_sur_config` ; `package.xml` : `exec_depend` |
| `packages/didier_bringup/launch/robot_app.launch.py` | nœud `lidar_node` (`sllidar_node`, port `/dev/didier-lidar`, 460 800, `frame_id: laser_frame`, `angle_compensate: true`, `scan_mode: Standard`, `respawn` vrai, délai 5 s) sous l'argument `lidar_materiel` (défaut vrai ; la sim passe faux) |
| `packages/theatre_contrats/` | noms de topics, test d'inventaire |
| `packages/didier_description/urdf/dadou_robot_gz.urdf.xacro` | lien `laser_frame` + capteur (§8.1) — l'URDF nominal GELÉ n'est pas touché |
| `packages/didier_sim/` | pont du lidar en processus séparé, nœud `passant_sim_node`, modèles d'obstacle (§8) |
| `machines/sim/` | `robot/corps_sur.yaml`, `robot/entree.sh` (deux arguments), `docker-compose.yml` (contextes et montages : `didier_corps_sur` dans `robot` ET `monde`), `validate-corps-sur.sh`, `fumee.sh` |
| `machines/robot/` | `machine.yml`, `corps_sur.yaml`, `udev/`, `docker/Dockerfile`, `docker/arm/docker-compose-arm.yml`, `scripts/` (§9) |
| `deploy/roles/config-hote/` | rechargement d'udev quand une règle change |
| tests existants | `test_twist_mux_contract.py`, `test_namespace_contract.py`, `test_arborescence.py`, `validate-namespace.sh` (sentinelles) : valeurs gravées mises à jour dans le même commit, en le disant |
| `packages/didier_web/` (A0-5) | page scène : état du corps sûr et bouton « réarmer » |
| docs | `README.md`, `docs/operations.md`, `docs/interfaces.md`, `docs/chantiers.md`, `packages/README.md`, `hardware/overview.md` (§2), `legacy/dadou_robot_ros/CLAUDE.md` (chaîne cmd_vel) |

Règles de sécurité roues (`legacy/dadou_robot_ros/CLAUDE.md`) appliquées sans exception :
instantané commité avant A0-4 ; sim d'abord ; domaine 43 pour tout essai ; protocole caméra
avant tout usage au sol ; aucun déploiement sur le robot aux roues câblées avant la relecture
adverse (A0-8).

## 8. Simulation

### 8.1 Lidar simulé

Dans `dadou_robot_gz.urdf.xacro`, sur le modèle de `camera_link` : lien `laser_frame` (boîte
55 × 55 × 41 mm, masse 0,11 kg, **sans collision**), joint fixe sur `base_link` avec
`preserveFixedJoint`, pose en arguments xacro `lidar_x`, `lidar_y`, `lidar_z`, `lidar_lacet`
(défauts : **0,33 ; 0 ; 0,02 ; 0** — face avant, plan à 0,25 m du sol, le sol étant à
z = −0,23). Un test grave l'égalité de ces défauts avec `machines/sim/robot/corps_sur.yaml`.

Capteur `gpu_lidar` aux caractéristiques du C1 : 500 échantillons horizontaux sur 360°
(pas de 0,72°), 1 vertical, 10 Hz, portée 0,05 à 12 m, résolution 0,015 m, bruit gaussien
d'écart-type 0,01 m (± 30 mm à 3 σ), `<topic>scan</topic>`, `gz_frame_id` = `laser_frame`,
`always_on`. Le système `Sensors` (`ogre2`) est déjà dans les mondes.

**Pont séparé** : l'entrée `scan` (`gz.msgs.LaserScan` → `sensor_msgs/LaserScan`) n'entre PAS
dans `gz_bridge.yaml` ; elle a son propre `parameter_bridge`, nommé `pont_lidar`, dans
`monde.launch.py`. Raison : les épreuves doivent pouvoir couper le lidar seul (SIGSTOP, kill)
sans figer `/clock`, sur lequel vivent le deadman et le chien de garde.

Le lidar simulé doit voir le corps de Didier, comme le vrai. Si le rendu ignore le modèle
porteur (à constater au premier lancement), ajouter au xacro gz un visuel « dos du support »
(plaque de 60 × 60 mm à 6 cm derrière le capteur) : il existe sur le vrai support.

### 8.2 Coût CPU et facteur temps réel

Le rendu des capteurs est fait par le CPU et a déjà coûté cher (06/11 : 0,49 du temps réel à
15 + 10 Hz, 0,88 à 5 + 5 Hz). **Non mesuré à l'écriture de cette spec** : la sim du PC était
prise par une autre session dans la nuit du 17 au 18/11. Premier geste d'A0-2, avec
`sonde_rtf` de `fumee.sh`, monde `chantiers`, sans tête, cœurs réservés comme la fumée, trois
mesures de 20 s : RTF sans lidar, puis avec.

Échelle fermée, on s'arrête au premier échelon qui passe **RTF ≥ 0,90 et ≥ 0,95 × le RTF sans
lidar** :

1. 500 échantillons, 10 Hz ;
2. 250 échantillons (1,44°), 10 Hz — `rayons_min` de la sim passe à 150 ;
3. 250 échantillons, 10 Hz, et la caméra de poursuite à 2 Hz (elle ne sert qu'à l'œil) ;
4. échec : arrêt du sous-lot et compte rendu à David (règle « fiabilité d'abord » du 16/11).
   La fréquence de 10 Hz ne se baisse pas : elle porte la porte des 200 ms.

Les valeurs mesurées sont écrites dans le commentaire du capteur, comme pour les caméras.

### 8.3 Table de couverture des emplacements (livrée AVANT l'arrivée du lidar)

`couverture_poses.py` lance la sim avec chaque pose candidate (arguments xacro), mesure les
masques avec `mesurer_masques` en espace dégagé (monde `stage`), et écrit un tableau dans
`docs/hardware/overview.md` : pour chaque pose, secteurs masqués, régions vues, mouvements
autorisés. Trois poses, d'après l'URDF (cotes estimées — la table sert à choisir, pas à percer) :

| Pose | x ; y ; z (`base_link`) | Idée |
|---|---|---|
| A — avant bas | 0,33 ; 0 ; 0,02 | le support dessiné, sur la face avant |
| B — sous la caisse | 0,10 ; 0 ; −0,13 (plan à 0,10 m du sol) | entre les roues, tête en bas ; à confronter à la garde au sol réelle |
| C — pont avant | 0,20 ; 0 ; 0,14 (plan à 0,37 m) | sur le dessus de la caisse, devant le torse |

### 8.4 Obstacles et passants scriptés

- **Obstacle** : cylindre statique (rayon 0,15 m, hauteur 1 m) portant le système
  `PosePublisher` (vérité terrain des épreuves), créé une fois hors champ (x = 50), déplacé par `gz service /world/stage/set_pose` (la mécanique des épreuves actuelles).
- **Passant** : `passant_sim_node` (package `didier_sim`, lancé dans `monde`, refus hors
  domaine 43) déplace un cylindre (rayon 0,20 m, hauteur 1,7 m) par `set_pose` à 20 Hz le long
  d'un segment : topic `sim/passant` (`StringTime`, JSON `{de: [x, y], a: [x, y], vitesse}`),
  fin de course publiée sur `sim/passant_etat`. Statique, sans physique : il ne pousse pas
  Didier, on mesure la distance, pas un choc. Pas de HuNavSim (non vérifié sur Jazzy, étude §6).
- Les positions sont données dans le repère de Didier et converties avec `ground_truth/odom`.

### 8.5 Épreuves de fumée — `machines/sim/validate-corps-sur.sh`

Dans `monde`, monde `stage` (plateau nu), écrites en rclpy avec `capture_topics.py` (la CLI
perd des messages sur ce PC). Temps mesurés à l'horloge **simulée**. `T0` d'une apparition se lit
à la **vérité terrain**, jamais à l'heure de l'appel : l'obstacle porte le système gz
`PosePublisher` (100 Hz, pont `sim/obstacle_pose`), et `T0` est l'horodatage du DERNIER message
qui le montre encore à l'ancienne place (erreur ≤ 10 ms, comptée contre nous). Graine fixe 20261118. `ATTENDU_CORPS_SUR=25` dans
`fumee.sh` ; phase placée après `machines`, avant `chantiers` ; son rouge est **bloquant**.

| N° | Épreuve | Critère chiffré | Verdicts |
|---|---|---|---|
| CS1 | démarrage | `scan` à 10 Hz ± 10 %, nombre de rayons = celui de l'échelon retenu ; état ARME moins de 5 s après le premier balayage ; `vue` publié conforme à la pose | 3 |
| CS2 | **porte de l'étude** : `cmd_vel_follow` 0,3 m/s publié à 20 Hz, obstacle posé à 0,5 m de la caisse, 20 relèvements tirés dans les régions vues | 20/20 : premier zéro sur `cmd_vel` moins de **200 ms** après `T0` ; distance parcourue après `T0` ≤ 0,15 m ; aucune distance vraie caisse-obstacle sous 0,30 m ; **les 20 mêmes essais avec la source à 5 Hz** : 20/20 sous 200 ms (c'est le zéro anticipé qui le permet) ; max et médiane au journal | 4 |
| CS3 | reprise | obstacle retiré : `cmd_vel` non nul entre 0,3 et 1,0 s après | 1 |
| CS4 | les trois canaux | même essai, une fois sur `cmd_vel_web` (publié par l'épreuve), une fois sur `cmd_vel_anim` par le VRAI chemin (séquence à piste roues jouée par `animations_node`, phase avant) | 2 |
| CS5 | `moon-walk` | ARRIERE non vue : pendant toute la séquence, aucun `linear.x` négatif sur `cmd_vel` alors que `cmd_vel_anim` en porte, motif `recul_aveugle` publié. ARRIERE vue : obstacle à 0,5 m derrière pendant le recul → zéro en moins de 200 ms | 1 |
| CS6 | ralenti | obstacle à 0,9 m : `cmd_vel` = 0,15 ± 0,01 pour 0,3 demandé ; à 1,5 m : 0,30 | 1 |
| CS7 | télécommande non filtrée | obstacle à 0,3 m devant, `cmd_vel_remote` 0,2 pendant 1 s : `cmd_vel` = 0,2 ; et `cmd_vel_follow` simultané ne passe pas | 1 |
| CS8 | capteur perdu en marche | SIGSTOP de `pont_lidar` : zéro sur `cmd_vel` moins de 0,45 s après le dernier balayage, état VERROU `capteur_perdu` ; SIGCONT : toujours zéro 3 s après ; `rearmer` : repart en moins de 2 s | 3 |
| CS9 | capteur absent au démarrage | nœud relancé, `pont_lidar` figé : 5 s de `cmd_vel_follow`, aucune sortie non nulle, état DEMARRAGE `capteur_absent` ; SIGCONT : ARME en moins de 3 s sans réarmement | 2 |
| CS10 | mort du filtre | `kill -9` puis, relancé, SIGSTOP du nœud en marche : zéro sur `cmd_vel` en moins de 500 ms ; la télécommande conduit toujours | 2 |
| CS11 | arrêt d'urgence | `e_stop` vrai : zéro, VERROU `e_stop` ; `e_stop` faux : la télécommande conduit, l'autonome reste à zéro ; `rearmer` : repart | 1 |
| CS12 | **la configuration du robot réel jouée en sim** : nœud relancé avec `machines/robot/corps_sur.yaml` (pose et masques de la sim substitués par l'épreuve, tout le reste intact) | sans battement : DEMARRAGE `superviseur_absent` si exigé ; battement 5 Hz puis coupé : zéro en moins de 1,1 s et VERROU ; mouvement continu coupé à 4,0 ± 0,1 s, repris après 1 s d'entrées nulles ; vitesse plafonnée à la valeur du fichier | 3 |
| CS13 | passant | 6 passages en travers (0,5 ; 1,0 ; 1,5 m/s, deux sens), Didier à 0,3 m/s demandés ; trajet calculé pour que la surface du passant ENTRE dans la zone d'arrêt à 0,5 ± 0,05 m devant la caisse (l'épreuve anticipe l'avance de Didier, relève l'entrée réelle à la vérité terrain et rejoue un essai hors tolérance, 3 fois au plus) : distance vraie surface-caisse ≥ 0,30 m à tout instant ; reprise moins de 1 s après la sortie de zone | 1 |

Après chaque épreuve qui relance le nœud, la configuration de la sim est remise et vérifiée.

**Non-régression, même fumée** : `namespace`, `machines` (nœuds attendus + `corps_sur`), V-R3
21/21, A1 14/14, CONV 13/13. **Risque connu** : les tours d'objet passent à 1,0 m du bord
(`TOUR_CLEARANCE_M` = 0,4 + 0,6), soit un flanc à 0,6 m pile : arrêts et ralentis sont
attendus dans les répétitions. Règle fermée : on écarte le **scénario** (dégagement des
tours, distances d'approche, durées d'épreuve), **jamais** le corps sûr ; chaque valeur
changée est citée dans le commit. Au-delà de 4 h de corrections, arrêt et compte rendu à David.

## 9. Déploiement (« Ansible nickel » : une commande, zéro geste)

- **Pilote** : `machines/robot/docker/Dockerfile` clone `Slamtec/sllidar_ros2` au commit épinglé
  `34300099fadfc772965962dec837bf436706188f` dans `/opt/lidar_ws`, le compile (colcon) ;
  `launch-ros-in-docker.sh` source `/opt/lidar_ws/install/setup.bash` avant l'espace de
  travail. Rien du pilote n'est copié dans le dépôt. Si la compilation échoue sous Jazzy
  (ARM ou x86) : repli fermé sur `Slamtec/rplidar_ros`, branche `ros2`, commit épinglé, nœud
  `rplidar_node`, mêmes paramètres ; le repli est écrit dans le Dockerfile et le README.
  L'image ARM est reconstruite et poussée par le flux existant.
- **Port série** : `machines/robot/udev/99-didier-lidar.rules`, posé par `fichiers_etc` (rôle
  `config-hote`) : `SUBSYSTEM=="tty", ATTRS{idVendor}=="…", ATTRS{idProduct}=="…",
  ATTRS{serial}=="…", SYMLINK+="didier-lidar", GROUP="dialout", MODE="0660"` (pas le `0777`
  de la règle SLAMTEC). Les trois identifiants sont ceux de l'adaptateur de David, lus une
  fois au banc (`udevadm info`), commités : c'est la seule donnée qui attend le matériel. Le
  rôle gagne une tâche « recharger udev si une règle change ». Le conteneur est déjà
  privilégié avec `/dev` monté : le lien y apparaît.
- **`machine.yml` du robot** : `packages` + `didier_corps_sur` ; `noeuds_attendus` +
  `/didier/corps_sur` (toujours vivant, même sans lidar). **`lidar_node` n'y entre pas** : sans
  capteur il se termine et se relance toutes les 5 s ; sa santé se lit dans `diagnostics`.
- **Compose ARM et compose de la sim** : contextes nommés et montages de `didier_corps_sur`
  (les tests d'arborescence gravent « la liste `packages`, ni plus ni moins »).
- **Scripts** (`machines/robot/scripts/`) : `rearmer-corps-sur.sh`, `relancer-lidar.sh` (tue
  le pilote, la relance le reprend), `protocole-corps-sur.sh` (§10.2).
- **`ecart-pi.sh robot` vert** en fin de lot ; preuve « à blanc » sur le Pi 4 hors robot :
  déploiement complet, `corps_sur` en DEMARRAGE `capteur_absent`, aucun `Twist` non nul sur
  les `_sur` quand on publie sur `cmd_vel_anim` (domaine 42, roues non câblées).
- Le Pi vision n'est pas touché.

## 10. Épreuves sur le matériel

### 10.1 Banc, dès la livraison (David 20 min, aucun moteur, aucun risque)

Lidar sur son adaptateur, branché au Pi 4 du robot posé sur l'établi, déployé par Ansible.
Un script (`banc-lidar.sh`) pose les questions et écrit `docs/seances/<date>-banc-lidar.md`.

| # | Geste | Mesure consignée |
|---|---|---|
| 1 | brancher | identifiants USB (→ règle udev) ; `vcgencmd get_throttled` avant/après le démarrage du moteur |
| 2 | laisser tourner 60 s | fréquence, rayons par message, part de points finis, charge CPU du pilote et de `corps_sur` (but : moins de 15 % d'un cœur à eux deux) |
| 3 | carton à 1 m devant, puis à gauche | orientation de `laser_frame` → `lacet_rad` |
| 4 | carton à 5, 10, 20 cm | portée minimale réelle |
| 5 | carton à 0,5 m, entré d'un coup | délai balayage → état ARRET lu au journal (but : moins de 250 ms) |
| 6 | jean noir, vitre, miroir à 0,6 et 1,2 m | nombre de points renvoyés par cible |
| 7 | débrancher l'USB, rebrancher | VERROU en moins de 0,4 s ; le pilote se termine-t-il ? revient-il seul ? |
| 8 | dehors, plein jour, carton blanc puis noir à 1 et 3 m | points renvoyés, comparés à l'intérieur |

### 10.2 Hors sol (David seul, 30 min au plus, roues levées)

Préalables : relecture adverse faite (A0-8) ; lidar à sa place, masques mesurés ; 2 m dégagés
autour ; webcam sur les roues. C'est aussi le **protocole caméra dû depuis L1b** (namespace),
jamais rejoué sur le robot : on commence par lui. `protocole-corps-sur.sh` enchaîne, attend
une touche entre les étapes, enregistre vidéo et journaux, écrit le compte rendu.

| Min | Étape | Attendu |
|---|---|---|
| 0-3 | caler le robot, vérifier à la main que les roues tournent libres, télécommande en main | — |
| 3-8 | `validate-cmdvel-protocol.sh` (les 4 épreuves du 04/07) | 4/4 |
| 8-10 | état du corps sûr affiché | ARME, régions vues conformes à la table |
| 10-14 | consigne autonome 25 % par salves de 3,5 s, pause 1,5 s (la borne de 4 s du robot) ; carton présenté à 0,5 m devant pendant une salve, retiré, trois fois | arrêt à chaque fois ; reprise après retrait ; au journal : balayage → zéro publié ≤ 20 ms, zéro → `stop()` ≤ 50 ms |
| 14-17 | carton sur chaque flanc et derrière | selon la table de couverture ; rien d'inattendu |
| 17-20 | USB du lidar arraché en marche, rebranché, réarmé | arrêt en moins de 0,5 s ; reste arrêté ; repart au réarmement |
| 20-23 | télécommande avec le carton devant ; relâcher | les roues tournent (prio 100 non filtrée) ; arrêt au relâcher |
| 23-26 | `moon-walk` | pas de recul si l'arrière n'est pas vu ; coupure à 4 s |
| 26-28 | `kill` du nœud en marche | arrêt en moins de 0,5 s |
| 28-30 | si le battement existe : couper la télécommande | arrêt en moins de 1 s, verrou |

Un écart = arrêt de la séance, rien au sol.

### 10.3 Au sol, à la maison, télécommande en main (David, 30 min)

Préalables, tous : refonte électrique (arrêt matériel, décision du 05/11) ; **premier roulage
au sol télécommande en main** fait (A-préalables, priorité 1) ; calibration PWM faite et
reportée dans `corps_sur.yaml` ; §10.2 vert.

1. Couloir dégagé de 4 m, David derrière à plus d'un mètre du bout de la flèche.
2. Carton à 2 m devant, consigne autonome à la vitesse calibrée : arrêt ; **mesurer au mètre**
   la distance caisse-carton au repos. Critère : ≥ 0,40 m, trois fois sur trois. Sinon on
   baisse `v_max`.
3. Carton tiré par une ficelle en travers, à 1 m devant, Didier en marche : arrêt, reprise.
4. Départ carton à 0,5 m : aucun mouvement.
5. Reprise à la télécommande pendant un arrêt de zone : immédiate.
6. Borne de 4 s : Didier s'arrête seul sans obstacle.

## 11. Sous-lots, ordre, dépendances

Opus au minimum partout (chemin roues) ; aucun Sonnet ni Haiku. Heures d'agent.

| Sous-lot | Contenu | Modèle | Heures | Dépend de | Porte |
|---|---|---|---|---|---|
| A0-1 | **essai borné de `nav2_collision_monitor`** (décision du 11/11), §12 | Opus | 2 | sim libre | verdict écrit, binaire |
| A0-2 | lidar simulé, pont séparé, RTF mesuré, obstacle, passant, table de couverture des trois poses | Opus | 4 | — | échelon RTF retenu ; table dans `overview.md` |
| A0-3 | `didier_corps_sur` : logique pure, tests gravés, 11 mutants | Opus | 5 | — (parallèle d'A0-2) | tests verts, table des mutants |
| A0-4 | nœud, insertion dans la chaîne, contrats, `validate-corps-sur.sh`, fumée, non-régression des répétitions | Opus | 7 | A0-2, A0-3, instantané commité | fumée complète verte, CS 25/25 |
| A0-5 | page scène : état du corps sûr, bouton « réarmer » | Opus | 1,5 | A0-4 | vu par David en séance sim |
| A0-6 | déploiement : pilote dans l'image, udev, `machine.yml`, Ansible, preuve à blanc sur le Pi hors robot | Opus | 3 | A0-4 ; Pi branché | `ecart-pi.sh robot` vert |
| A0-7 | banc C1 (§10.1), masques réels, 5 cotes de la caisse, correction d'`overview.md` | Opus + David 20 min | 2 | **livraison du lidar**, A0-6 | compte rendu, YAML du robot rempli |
| A0-8 | **relecture adverse** du chemin roues modifié, puis corrections | **Fable** 2 h + Opus 2 h | 4 | A0-4, A0-6 | aucun bloquant ouvert |
| A0-9 | protocole hors sol (§10.2) | Opus 1,5 h + David 30 min | 1,5 | A0-7, A0-8 ; lidar monté ; roues alimentées | protocole vert, vidéo |
| A0-10 | au sol à la maison (§10.3) | Opus 1 h + David 30 min | 1 | A0-9 ; refonte électrique ; premier roulage ; calibration PWM | 3/3, compte rendu |
| **Total** | | | **31 h** dont 2 h Fable | | |

- **Avant l'arrivée du lidar** (fin novembre) : A0-1 à A0-6, soit 22,5 h. À l'arrivée : A0-7.
- **Avec A-préalables** : rien d'A0-1 à A0-9 n'en dépend. Le **battement** se branche sur
  `superviseur/battement` (contrat du §3.2) et fait passer `superviseur.exige` à vrai ; **W1**
  publie `e_stop`, déjà lu ; la **calibration PWM** remplace les vitesses provisoires. A0-10
  attend le premier roulage. **La rue attend en plus W1, le battement exigé et l'odométrie
  (A4)** : séquence du 02/11, inchangée.
- **Avec O0-O1** (tableau des objets, en tête du cap du 18/11) : aucune dépendance de fond.
  Fichiers communs : `machines/sim/docker-compose.yml`, `fumee.sh`, `test_arborescence.py`,
  listes de packages. A0-3 est sans conflit et peut tourner en même temps ; A0-2 et A0-4 se
  fusionnent **après** O1, ou avant, mais jamais en même temps (une seule sim). Plus tard,
  « la distance d'un objet vu = la mesure du lidar dans son azimut » (étude objets §6.5) lira
  `scan` depuis `didier_perception` : A0 n'a rien à prévoir de plus que ce topic.
- **Avec le régisseur et le sélecteur** : ils ne lisent pas encore `corps_sur/etat` ; un trajet
  gelé par le corps sûr leur apparaît comme un trajet lent. Suffisant pour A0 ; le brancher
  est un lot de jeu (« le corps raconte », M6).

## 12. A0-1 — l'essai du moniteur de collision Nav2 (décidé le 11/11, borné ici)

Paquet `ros-jazzy-nav2-collision-monitor` (navigation2 1.3.14 dans rosdistro Jazzy). Lu à la
source (`params/collision_monitor_params.yaml`, branche `jazzy`) : zones `stop`, `slowdown`
(`slowdown_ratio`), `limit`, `approach` ; `source_timeout` ; `base_shift_correction` ;
`odom_frame_id` ; un `cmd_vel_in_topic` et un `cmd_vel_out_topic` par nœud. Le README annonce
4 à 5 ms par balayage de 360 points. La page de documentation des paramètres n'a pas pu être
lue (deux adresses en 404).

Essai en sim, **2 h au plus**, lidar d'A0-2. Les trois critères du 11/11, rendus binaires :

1. **Il exprime les règles** : (a) trois instances filtrent les trois canaux ; (b) un polygone
   d'arrêt = caisse + 0,6 m arrête linéaire et angulaire ; (c) le ralenti est un facteur fixe ;
   (d) les auto-retours du corps sont exclus avec au plus UN nœud de plus sur le chemin ;
   (e) il tourne **sans TF `odom`** (le robot réel n'a pas d'odométrie), sans transformée
   factice ; (f) CS2 passe à 20/20.
2. **Il arrête sur capteur muet** : `source_timeout` 0,3 → CS8 (partie arrêt) passe.
3. **Sa charge est mesurée sur un Pi 4** : trois instances, balayage rejoué à 10 Hz, moins de
   15 % d'un cœur au total.

Un seul « non » → filtre maison, sans regret (texte du 11/11). Tout « oui » → `zones.py` et la
partie zone de `filtre.py` sont remplacés par les trois instances, placées **en amont** de
`didier_corps_sur`, qui garde tout le reste (verrous, couverture, plafonds, durée, état) : le
nœud maison reste en ligne dans les deux cas. Le verdict et les mesures vont dans
`docs/etudes/etude-standards-robotique.md` §5.3. Voir la question 2.

## 13. Questions pour David

**Réponses de David (18/11, soir)** — décisions, ne pas re-trancher :

1. **Emplacement : sur la face AVANT** (la porte/caisse ; la tête est exclue vu la taille du robot).
   Deux hauteurs candidates : **25 cm, en bas de la caisse** (retenue par défaut : c'est la hauteur
   de balayage de l'étude, 20-30 cm, qui voit jambes, enfants, chiens, bornes ; fixe, sans
   charnière) ou **45 cm sur la porte** (repli ; câble par la charnière, repositionnement à la
   fermeture). A0-2 produit la table de couverture des DEUX poses avant tout perçage. Couverture
   avant seulement assumée : pas de recul autonome, pivots lents (`angulaire_aveugle_autorise`
   vrai seulement à la maison, plafond 0,3 rad/s), flancs et dos = zone de David.
2. **Essai Nav2 (A0-1) : sauté**, sur l'avis de la spec (le nœud maison est nécessaire de toute
   façon ; moins de maillons sur le chemin des roues). La décision « standards par morceaux » du
   11/11 reste : on relira le moniteur de collision si le nœud maison grossit.
3. **A0-2 et A0-3 lancés tout de suite**, avant la livraison du lidar, en parallèle d'O0-O1.

| # | Question | Avis, et ce qui se passe sans réponse |
|---|---|---|
| 1 | ~~**Où monte-t-on le C1 ?**~~ (répondu ci-dessus) Le support dessiné (face avant, bas) ne voit que devant : pas de marche arrière autonome (`moon-walk` joue sans reculer), et les pivots se font flancs et arrière **non vus** — ce n'est pas le « 360° » décidé le 02/11. | **Sim et maison : pose A**, avec `angulaire_aveugle_autorise` vrai et rotation plafonnée (0,3 rad/s au réel) : chez toi il n'y a personne sur les flancs. **Rue : à décider sur la table de couverture d'A0-2** (pose B ou C, ou tu acceptes par écrit que flancs et arrière sont ta zone). Sans réponse : pose A en sim ; le fichier du robot garde `angulaire_aveugle_autorise` **faux**, donc Didier n'y tourne pas seul. |
| 2 | ~~**Saute-t-on l'essai Nav2 (A0-1) ?**~~ (répondu ci-dessus) | **Je le sauterais.** Le nœud maison reste en ligne de toute façon (verrous, régions non vues, durée), la partie remplaçable fait une centaine de lignes déjà couvertes par les tests gravés, et le moniteur ajoute trois nœuds *lifecycle* sur le chemin des roues. Sans réponse : l'essai est fait (ta décision du 11/11 tient), 2 h. |
| 3 | ~~**Lance-t-on A0-2 et A0-3 maintenant ?**~~ (répondu ci-dessus) | **Oui** : le lidar arrive dans deux semaines et tout ce qui précède le banc se fait sans lui. Sans réponse : A0-3 seul démarre (aucun fichier commun, aucune sim), le reste après O1. |

## 14. Ce que ce lot SUPPRIME

- **L'accès direct des sources autonomes au mux.** Sans corps sûr vivant et lidar sain, **plus
  aucune piste roues de séquence ne fait tourner les roues**, en sim comme sur le robot (24
  fichiers de séquence ont une clé `wheels`, comptés le 18/11 ; l'étude en relevait 15 sur les
  29 du spectacle), ni le suivi, ni la route, ni le pilotage web.
  Sur le robot, tant que le lidar n'est pas monté, les séquences jouent sans leurs roues ; la
  télécommande conduit comme avant.
- **Les reculs autonomes** tant que l'arrière n'est pas vu, et **tout mouvement autonome de
  plus de 4 s** sur le robot tant qu'il n'y a pas d'odométrie.
- **Le sens de `cmd_vel_follow`, `cmd_vel_anim`, `cmd_vel_web`** : ce sont des demandes, plus
  des consignes ; ce qui atteint le mux porte le suffixe `_sur`.
- **Les phrases périmées** de `hardware/overview.md` (« 360° n'est pas nécessaire », « pas de
  marche arrière autonome, déjà garanti par le code ») et de `chantiers.md` (« arc AVANT
  suffit »), remplacées par un renvoi ici.
- **Rien d'autre** : aucun fichier supprimé, `wheels_bridge`, `twist_deadman`, `wheels_node`
  et la télécommande ne sont pas modifiés.

## 15. Risques

| Risque | Parade |
|---|---|
| Le RTF tombe avec le lidar | échelle du §8.2, mesurée avant d'écrire les épreuves |
| Les répétitions existantes rougissent (ralentis, arrêts près des objets) | règle du §8.5, budget de 4 h, on écarte le scénario |
| Faux arrêts au réel (poussière, pluie, soleil, sol vu sur une pente) | entrée sur un point assumée ; taux mesuré au banc et à la maison ; le plan à 0,25 m incliné de 5° voit le sol à 2,9 m, hors zone (`overview.md`) |
| Capteur aveuglé qui dit « voie libre » | témoin de vie quand il existe ; sinon limite affichée en WARN ; mesure au soleil (§10.1) |
| `sllidar_ros2` ne compile pas sous Jazzy | repli fermé sur `rplidar_ros` branche `ros2` (§9) |
| Le Pi 4 s'écroule au démarrage du moteur (800 mA) | mesuré au banc ; sinon alimentation 5 V séparée, à inscrire au cahier de câblage (ligne L21) |
| Un verrou en pleine rue sans moyen de réarmer | page scène en A0-5 ; la télécommande CONSOLE (L4) devra porter le réarmement |
| La marge de 2D donne une fausse confiance | §0 écrit ce que le corps sûr ne voit pas ; la relecture adverse le vérifie contre le code |

## 16. Ce que cette spec ne re-tranche pas

Lidar 2D sur le Pi 4 ; filtre avant le mux sur toutes les entrées autonomes ; 0,6 m de la
caisse, 0,6 à 1,2 m de ralenti par palier ; 300 ms et 1 s ; zéro et verrou ; télécommande et
deadman inchangés ; W1 avant la rue, odométrie avant A4, maison après le premier roulage ;
essai Nav2 avant le filtre maison ; un seul décideur du corps ; hauteur de balayage de 20 à
30 cm ; pas de TF ni de Nav2 complet sur le chemin de sécurité.
