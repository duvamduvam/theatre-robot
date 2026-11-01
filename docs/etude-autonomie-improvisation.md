# Autonomie et improvisation — ce que la recherche a fait, ce que Didier peut en faire

*Ouverte le 2026-11-01 au soir, à la demande de David. Statut : **DÉCIDÉE le 2026-11-02** —
étude relue de façon adversariale (Opus, 22 points dont 7 bloquants, tous repris), puis les
**dix questions du §8 tranchées par David** (toutes dans le sens recommandé) ; les lots du §9
sont actés dans cet ordre. Ne pas re-trancher sans fait nouveau. Sources : quatre collectes web du 01/11 (théâtre et
improvisation ; architectures de décision ; perception spatiale à bas coût ; co-performance et
contrôle partagé), chaque fait avec son origine ; ce qui est de seconde main est marqué
« (2ᵉ main) » ; ce qui n'a pas été trouvé est au §10.*

## 0. La question, le cadre, la réponse courte

David, le 01/11 : *« La direction est que Didier soit de plus en plus autonome, pour me libérer
le cerveau et me donner de l'élan [...] un robot qui prenne ses propres décisions, qui
improvise. »* Puis : *« il faut absolument que le robot puisse bouger de façon autonome, c'est
vraiment la clé minimum pour l'interaction »* ; *« la seule contrainte, c'est la sécurité des
gens et l'amusement général »* ; et le **cadre** : *« le robot a un objectif de destination, et
il joue avec des obstacles sur la route [...] la télécommande peut prendre le relais, guider en
macro si besoin, mais je ne veux pas diriger roue par roue, bras, expression »* ; le travail :
*« le timing d'action, de prise de décision : pourquoi et quand Didier agit »* ; et : *« à basse
vitesse, je suis derrière pour rattraper : la marge d'erreur peut être très grande, et on peut
même s'en servir »*. **Décidé en séance** : le capteur d'obstacle, « on le prendra ».

Réponses courtes :

1. **Dans tous les cas lus, le robot de scène n'est pas autonome sur le *quoi jouer*.** Les
   humains gardent ce choix — opérateur, curateur, marionnettiste — et l'autonomie qui a
   réussi est **étroite et choisie** : le timing (Jon the Robot), le regard (AUR), l'équilibre
   et les animations de fond (Disney), le texte (Dorsen). Deux noms n'ont pas été couverts
   (Demers, Knight), donc « personne » serait de trop : *dans les cas lus* (§1).
2. **Le théâtre n'exclut rien, il détourne tout** : robots du commerce, LLM grand public, robot
   industriel, théorie de la danse formalisée en IA. Réutiliser l'IA de jeu vidéo et des
   robots sociaux est la voie normale (§1.6).
3. **La stratégie proposée** (§4, option B) : un **corps sûr** déterministe que rien ne
   franchit ; un **répertoire** composé par David ; un **sélecteur** rapide et sans LLM qui
   décide *quoi jouer et quand* ; la boucle 2 déjà conçue comme **metteur en scène intérieur** ;
   David en **console macro**. Mais — et c'est le résultat le plus important de la relecture —
   **le robot n'est pas prêt à bouger seul aujourd'hui**, pas parce qu'il manque
   d'intelligence, mais parce qu'il manque trois choses de sécurité et de mesure (§3) : une
   source d'arrêt d'urgence, un signal de vie du superviseur, et une odométrie. Sans elles, le
   « champ large » est **quasi nul** sur le vrai robot ; avec elles, il est réellement large.

Et la contradiction à trancher, pas à glisser : l'étude interaction du 13/09 dit **« Didier
n'est pas un robot autonome, c'est un instrument de jeu »**. Ce soir David demande l'inverse,
ou plutôt un cran au-dessus : **l'autonomie comme instrument**. C'est un **re-tranchage**
explicite (§8, question 10), pas une note de bas de page.

## 1. Ce que la recherche et la scène ont réellement fait

### 1.1 Les robots sur scène : qui décide, en vrai

| Œuvre / travail | Ce que le robot décide seul | Ce que l'humain garde | Source |
|---|---|---|---|
| **AUR / The Confessor** (MIT, 2007) | contact visuel par caméra, réaction « à temps » | contrôle hybride scènes / beats / actions, marionnettage | robots.media.mit.edu ; Hoffman et al., RO-MAN 2008 (non lu) |
| **Sayonara** (Hirata/Ishiguro, Geminoid F, 2010) | rien | téléopéré depuis une cabine | IEEE Spectrum, 11/2010 |
| **Hello Hi There** (Dorsen, 2010) | le dialogue, généré chaque soir par deux chatbots | le corpus | anniedorsen.com |
| **ROBOT** (Blanca Li, 2013, 7 Nao) | rien | chorégraphie écrite | Hyperallergic 2015 |
| **Spillikin** (RoboThespian, 2015) | rien | l'opérateur déclenche **chaque** réplique ; l'actrice rattrape : « if it's late I have to make up time » | Broadway Baby, 08/2015 |
| **A.L.Ex.** (Mathewson & Mirowski, 2016-17, 25 spectacles) | la parole (LSTM sur ~100 000 films), gestes pré-programmés déclenchés quand il parle | le format, la justification | AIIDE-17 |
| **Jon the Robot** (Vilk & Fitter, HRI 2020, 32 shows) | **le timing** : attend le rire, reprend quand il retombe ; « tags » | le texte | HRI 2020, via ScienceDaily (2ᵉ main) |
| **Improbotics** (Fringe 2023, 26 représentations) | 3 LLM génèrent des répliques en continu | **Operator** (contexte), **Curator** (choisit), **Cyborg** (joue la réplique reçue) | arXiv 2405.07111 |
| **RoboTales** (Fringe 2025) | parole + gestes du robot, propositions de scénario | Cyborg en lunettes AR, vote du public ; « very real and very fragile » | katmasterson.com, 07/2025 |
| **Theatre in the Loop** (2025) | rejoue des gestes **improvisés par un marionnettiste**, capturés en « templates » | le metteur en scène guide, le marionnettiste improvise | arXiv 2508.03514 |
| **Disney, bipède** (01/2025) | équilibre, marche (politiques RL à 50 Hz), animations de fond | **tout le haut niveau** : « we leave such high-level decisions to a puppeteer » ; 3 couches fond / clips / joystick | arXiv 2501.05204 |

### 1.2 Ce qui a été mesuré

- **Le timing pèse plus que le contenu** (Jon) : même texte, pause adaptée au rire plutôt
  qu'attente fixe de 5 s → « significantly more funny » ; les « tags » améliorent chaque
  blague individuellement (2ᵉ main, ScienceDaily).
- **Le LLM qui improvise déçoit sur la longueur** (Improbotics 2023) : cohérence perdue sur
  les scènes longues, réponses « ignorantes de la scène » (76/100 — ce que mesure
  exactement cette note n'est pas dans le résumé), sorties répétitives, délais qui cassent le
  flux ; acteurs : « like doing long form with a 5 year old » ; **trois pannes nommées,
  dans cet ordre : la transcription vocale, les locuteurs multiples, la perception sociale**
  (« lack of social cueing and perception », AIIDE-17). La première est aussi le point
  faible connu de Didier.
- **Ce qui marche avec une IA en impro, c'est l'humain qui justifie** (AIIDE-17) : le *jeu de
  justification* (Johnstone, « lines from a hat ») ; afficher plusieurs répliques candidates
  casse l'énergie ; le mode ELIZA reste le favori du public.
- **Délais** : entre humains, décalage médian de **+100 ms** au tour de parole (Stivers 2009,
  10 langues) ; face à un robot de communication, préférence maximale à **1 s**, plateau à
  **2 s**, un « euh… » atténuant un délai plus long (Shiwa et al., **2ᵉ main**, et mesuré sur
  des *réponses verbales*, pas des actions). ⚠️ Le « 0,7-1 s au premier mot » de Didier est
  le délai du **LLM seul**, mesuré **depuis le PC** ; il ne compte ni la transcription
  (Voxtral cloud, ou 3,6-5,2 s en local) ni la synthèse : **Didier n'est pas dans la
  fenêtre aujourd'hui**, il faut le mesurer de bout en bout sur le robot.
- **Lisibilité ≠ prévisibilité du mouvement** (Dragan & Srinivasa, HRI 2013) : deux propriétés
  « fundamentally different and often contradictory ». C'est une propriété **du mouvement**
  (le geste dit son but), pas d'un affichage.
- **Un robot qui ne fait rien pendant qu'on le regarde déçoit** (Theatre in the Loop, 18
  enfants face au robot NED : pas de nuance, pas d'adaptation, « Why does it keep going to
  sleep? »).

### 1.3 Les architectures de décision disponibles

| Famille | Ce qu'elle fait | Né où | Sur quel robot | Source |
|---|---|---|---|---|
| **Behavior trees** | arbre de priorités/séquences, modulaire, réactif | IA de jeu | Jibo (« fundamental part »), Nav2 ; `py_trees_ros` empaqueté **Jazzy** | arXiv 1709.00084 ; docs.ros.org |
| **Utility AI** | score par action (courbes × facteurs), la meilleure gagne | jeux (GDC 2015, Guild Wars 2) ; Versu | **aucun robot dans les sources** ; ELEGNT (Apple 2025) note des *trajectoires* par utilité fonctionnelle + expressive, c'est la mesure de l'expressivité (56 vs 28, n=21), pas un sélecteur | gameai.com ; arXiv 2501.12493 |
| **Machine à états + fond** | une activité focalisée à la fois ; en fond regard + micro-mouvements | robots sociaux | **NAOqi Autonomous Life** (Pepper/NAO) | doc Aldebaran |
| **Couches d'animation** | fond en boucle + clips fondus + modulation continue | animation | Disney bipède ; Anki (animateurs + « emotion engine ») | arXiv 2501.05204 ; Design News (2ᵉ main) |
| **Drama manager** | séquence des beats | narration interactive | Façade, Comme il Faut — **jamais sur robot** | AIIDE 2005 ; UCSC 2012 |
| **Improvisation formalisée** | *Viewpoints* codé (espace, temps, forme), appel-réponse ; anticipation | créativité computationnelle | Viewpoints AI / LuminAI (installation) ; Shimon (jazz) | AAAI ; Autonomous Robots 2011 (non lus) |

### 1.4 Les LLM comme moteur de comportement

- **GenEM** (HRI 2024) : 4 appels GPT-4 → code de comportement expressif, jugé ≈ animateur
  expert ; **aucune latence ni coût publiés** ; un tour à la fois (arXiv 2401.14673).
- **Petits modèles embarqués** (Frontiers 05/2025) : LLaMA 1B-8B sur Jetson Orin Nano,
  5-15 tokens/s, « tête de geste » qui choisit dans un **jeu prédéfini** avec 45-50 % de
  précision. L'idée « le LLM choisit dans un répertoire fermé » est la bonne ; la précision ne
  l'est pas encore.
- **Ameca + GPT-4** (presse 2023, 2ᵉ main) : « made Ameca appear less responsive ».
- **VLA** (OpenVLA : 6 Hz sur RTX 4090, 15 Go) : manipulation, GPU — hors sujet.
- **Symbiosis of Agents** (installation, 06/2025) : RL / « drives » narratifs / LLM sur
  directives d'artiste ; gains : émergence ; pertes : contrôle instant par instant,
  reproductibilité (arXiv 2506.02606).

### 1.5 Comprendre l'espace : ce qui est réaliste

Prix **lus à la source le 01/11** (taxes/port non précisés) : lidar 2D **LD19** 360°, 12 m :
**130,90 €** (RobotShop EU, en rupture) ; ToF multizone **VL53L5CX** 8×8, 4 m : **19,95 $**
(Pololu) ; **OAK-D Lite** : **269 $** (Luxonis) ; **AI HAT+** Hailo-8L : **« from 70 $ »**
(YOLOv8n ~200 FPS annoncés par Hailo, **pré/post-traitement non précisé** ; ~15 FPS pour
YOLO26n sur le CPU du Pi 5 seul, Ultralytics). RPLidar, RealSense, Orbbec : prix primaire **non
trouvé**. ⚠️ Un ToF en plein soleil perd de la portée (impression, non mesurée).

**Les VLM sont faibles en raisonnement spatial** (SpatiaLab, ICLR 2026) : 54,9 % en QCM vs
87,6 % humain, 40,9 % en question ouverte vs 64,9 %, pires sur profondeur et navigation.
Une image toutes les 5 s à un VLM (≈ 0,0002 $ l'image à 0,75 $/M tokens Gemini 3.8 Flash
jusqu'au 31/12/2026, **double ensuite** ; ~258 tokens/image **non vérifié**) donne du **sens**,
jamais une **distance**. Réserve « droit à l'image » du 23/10 : inchangée.

### 1.6 Le théâtre exclut-il la réappropriation ? Non

LLM grand public (Improbotics), chatbots (Dorsen), robots du commerce (Nao, RoboThespian),
robot industriel détourné (Bory, *Sans Objet*, 2ᵉ main), théorie théâtrale → IA (LuminAI).
**Non trouvé** : une œuvre revendiquant l'IA de jeu vidéo. Espace vide, pas interdit.

## 2. Les quatre leçons qui comptent pour Didier

1. **L'autonomie qui marche est étroite, choisie, lisible** — le moment, le regard, la
   réaction courte ; l'humain garde le fil.
2. **Le LLM n'est pas le bon organe pour décider vite** ; sa place : écrire la matière et
   tenir le fil à cadence lente (boucle 2, déjà conçue). L'argument fort contre « le LLM
   génère le geste » n'est pas la latence (que le projet a su borner) mais la **lisibilité** :
   un geste inventé à la volée, l'acteur ne peut pas l'anticiper.
3. **La matière se compose, puis se rejoue** (Disney, Anki, Theatre in the Loop). Le
   répertoire de David est le carburant de l'autonomie.
4. **La perception est le trou** — la transcription d'abord (Improbotics), l'espace ensuite
   (David : « il ne comprend pas vraiment l'espace »).

## 3. Le mouvement autonome : exigence n° 1, et ce qu'elle impose vraiment

### 3.1 Ce qui manque AVANT de bouger seul — relevé dans le code et les décisions

| Manque | État réel (01/11) | Pourquoi c'est bloquant en autonomie |
|---|---|---|
| **Arrêt d'urgence** | `e_stop` du twist_mux **n'a aucune source** (CLAUDE.md) ; le bouton du dos éteint le Pi et **provoque un emballement** (chantiers) | aujourd'hui le deadman 400 ms *est* l'arrêt : la main de David lâche → silence → zéro. **En autonomie, c'est le sélecteur qui émet : s'il se trompe, il ne se tait pas, et le deadman ne se déclenche jamais.** Il faut une source d'arrêt indépendante (W1 de l'étude interface web) |
| **Signal de vie du superviseur** | `remote` a un `timeout: 0.5` dans twist_mux : télécommande muette → les priorités basses **reprennent la main** | une télécommande à plat ou hors de portée laisse Didier continuer son jeu, David sans rien. Règle à poser : **mouvement autonome autorisé seulement sous présence du superviseur** (battement de cœur de la télécommande, lié à l'homme-mort séparé déjà décidé pour la télécommande USB) |
| **Mesure du mouvement** | roues en boucle ouverte, PWM, `max_wheel_speed=1.0` « calibration à venir », plancher `MIN_PWM=5000` (toute consigne ≥ 1 % saute au plancher), **pas d'odométrie** (chantier ouvert, cartes PCB prêtes) | « 0,3 m/s », « ≤ 3 m », « vitesse ∝ distance » sont **invérifiables** et le ralenti proportionnel est **écrasé par le plancher PWM** là où sont les gens. Sans odométrie, les bornes se disent en % de PWM calibrés à la caméra, pas en m/s |
| **Capteur d'obstacle** | aucun | **DÉCIDÉ le 01/11 (« on le prendra »)** — reste à choisir : lidar 2D 360° (voit aussi derrière et sur les côtés — nécessaire : « un pas en arrière », pivots, `moon-walk` recule) ou ToF (devant seulement, soleil) ; **monté sur le Pi 4 robot**, pas sur le Pi 5 vision (la sûreté ne doit pas passer par le Wi-Fi) |
| **Robot au sol** | en pièces depuis le 03/09 ; cmd_vel **n'a jamais roulé au sol** (priorité 1 du tableau de bord = test télécommande en main) | le premier roulage ne doit pas cumuler deux inconnues ; l'enveloppe arrive **après** |

### 3.2 L'enveloppe de mouvement (`corps sûr`) — corrigée

Un nœud déterministe, **sans LLM**, sur le Pi 4, qui lit le capteur d'obstacle et **toutes les
consignes autonomes** avant qu'elles n'atteignent le twist_mux :

| Règle | Valeur de départ (à caler sim puis caméra) | Note de la relecture intégrée |
|---|---|---|
| **Ce qu'elle filtre** | **toutes** les entrées autonomes : `cmd_vel_follow`, `cmd_vel_anim`, `cmd_vel_web`, et demain le sélecteur — **pas** `cmd_vel_remote` (prio 100, David) | **15 des 29 séquences du spectacle (`json/sequences/eternel-show/`) ont une piste roues** (`moon-walk` recule 30 s) : un sélecteur qui les joue sans filtre ferait reculer Didier à l'aveugle. Filtre **avant** le mux obligatoirement : après, le Twist ne porte plus sa source |
| **Une seule entrée autonome** | le sélecteur devient **l'unique publieur** d'un topic `cmd_vel_auto` ; `person_follower` et `route_driver` deviennent ses **sources**, pas des publieurs concurrents | aujourd'hui `cmd_vel_follow` a **déjà deux publieurs** (suivi + route via `fault_relay`) : le dernier message gagne, bascule continue |
| zone d'arrêt dure | obstacle à **< 0,6 m de la caisse** (pas du centre : demi-largeur 0,4 m, `spec-aller-voir`) → zéro, **360°** si lidar | la rotation dans la foule : **autorisée lentement seulement si rien à < 0,6 m sur tout le tour**, sinon gel — Didier gelé dans une foule « s'endort » (§1.2) : c'est un cas de **jeu** (il râle, il parle), pas un cas de mouvement |
| zone de ralenti | 0,6-1,2 m (zone personnelle de Hall, valeurs classiques **non relues à la source** : intime < 0,45, personnelle 0,45-1,2, sociale 1,2-3,6) → PWM réduit **par palier** (pas proportionnel : plancher PWM) | |
| vitesse max autonome | **à définir en % PWM, calibrée caméra** ; cible ≈ pas de flâneur (~0,3 m/s) **quand l'odométrie existera** | |
| déplacement unitaire | **borné en temps** (ex. 4 s) tant qu'il n'y a pas d'odométrie ; en mètres après | |
| **capteur perdu** | scan figé > 300 ms, USB arraché, driver mort → **zéro et verrou**, jamais de consigne propre | cas absent de la première version |
| **superviseur perdu** | battement de cœur télécommande > 1 s → **zéro et verrou** | idem |
| **e-stop** | source W1 **préalable** ; l'enveloppe la relaie et ne la remplace pas | idem |
| deadman, télécommande prio 100 | inchangés | la chaîne du 04/07 reste la dernière ligne ; **le filtre ne protège pas des bordures ni des marches** (un lidar 2D ne les voit pas — étude suivi) : David reste la protection contre le vide |

L'enveloppe est **nécessaire** mais ne rend pas le déplacement « sûr » à elle seule : elle rend
**sûre la décision autonome**, ce qui est différent. La **marge d'erreur de décision** voulue
par David (il est derrière, l'erreur se joue) est entièrement à l'intérieur de ça.

### 3.3 Où ça se place dans la chaîne roues

```
télécommande ──(cmd_vel_remote, prio 100)──────────────────────────┐
                                                                    ▼
sélecteur ─┐                                                   twist_mux ─► twist_deadman ─► /cmd_vel ─► wheels_node
 suivi ────┼─► cmd_vel_auto ─► CORPS SÛR ──(prio 20)──────────────┘   ▲        (deadman 400 ms conservé)
 route ────┘    (lidar, battement télécommande, e_stop W1 relayé)     │
 séquences ─────► cmd_vel_anim ─► CORPS SÛR ──(prio 10)───────────────┘
 web ───────────► cmd_vel_web  ─► CORPS SÛR ──(prio 50)───────────────┘
```

C'est un **changement du chemin roues** : sim, puis protocole caméra **étendu d'une épreuve
d'obstacle** (le protocole du 04/07 n'en a aucune), puis sol. Et il entre en tension avec la
décision d'architecture « chemin roues NON touché avant L4 » (§8, question 1).

### 3.4 Trois terrains, trois niveaux d'exigence — précision de David

David, 01/11 : *« on va commencer en grande partie en sim et dans ma maison, donc aucun
risque »*. Juste — et ça **desserre l'ordre** sans desserrer les règles : les préalables du
§3.1 sont des préalables de **rue**, pas de sim ni de maison.

| Terrain | Qui est là | Ce qu'on y fait | Ce qui est exigé |
|---|---|---|---|
| **Sim** (domaine 43) | personne | tout le sélecteur, le modèle de timing, le corps sûr avec lidar simulé, les passants scriptés ; **c'est là que se fait 80 % du chantier** | rien de matériel ; tests gravés |
| **Maison** (roues au sol, David seul, derrière) | David | réglage du timing à l'oreille, corps sûr avec le vrai lidar, calibration PWM, premier déplacement autonome **borné** (4 s, PWM bas) | capteur d'obstacle (décidé) + télécommande en main avec deadman (existant) ; **e-stop et signal de vie souhaitables mais pas bloquants** : David est seul, derrière, et le mobilier ne porte pas plainte |
| **Rue** (public) | passants, enfants | A4 | **tout** le §3.1 : e-stop W1, signal de vie, odométrie, protocole caméra étendu — sans exception |

Conséquence sur le §8 : la question 1 (priorité) devient « le travail en sim peut commencer
**sans attendre** ; la rue attend L0-L2 et les préalables » ; la question 2 (W1/odométrie)
devient « préalables de **rue** ». Le reste ne change pas.

## 4. Les stratégies, et celle que je recommande

| | A — Marionnette **augmentée** | **B — Improvisation à répertoire sous corps sûr** | C — Le LLM génère le mouvement | D — Apprentissage |
|---|---|---|---|---|
| Qui décide quoi jouer | David (macro) ; le robot décide **le timing et le regard** — ce n'est **pas** le statu quo : Jon et AUR ne sont pas faits chez Didier, et c'est ce que la littérature valide | un **sélecteur déterministe** sous le fil de David | un LLM à la volée (GenEM) | une politique apprise |
| Déplacement autonome | non (ou seulement « un pas vers qui parle ») | **oui, borné** (§3) | oui, imprévisible | oui, opaque |
| Lisibilité pour David | totale | forte si répertoire fini + règles écrites + geste lisible (Dragan) + journal | faible | nulle |
| Appui dans les sources | **le plus fort** (toutes les œuvres lues) | **aucun robot ne le fait tel quel** — c'est Pepper (fond + une activité) + Jibo (BT) + Disney (couches) assemblés autrement ; **l'utility AI n'a aucun appui robotique dans les sources** | Ameca « less responsive » ; GenEM un tour à la fois | manipulation seulement |
| Coût | petit, immédiat, **sans toucher aux roues** | lidar + 3 packages + W1 + calibration PWM ; **plusieurs semaines** d'un travail que David ne code pas (ordre de grandeur, pas une estimation) | coût API par geste, qualité non garantie | hors de portée |
| Verdict | **à faire d'abord, de toute façon** : c'est l'étape 0 de B | **recommandée comme cible**, à condition des préalables §3.1 | outil de **composition hors ligne** | écartée |

**B contient A.** L'honnêteté commande de dire que A répond déjà à une part de la demande
(« me libérer le cerveau ») sans toucher aux roues, et qu'elle est la seule validée par les
sources. B est le pari supplémentaire que David fait en demandant le déplacement autonome.

### 4.1 B, concrètement

```
   metteur en scène intérieur (boucle 2, LLM lent, 3-10 s) — EXISTE (23/10)
   lit image, parole, tableau → écrit tableau de situation + INTENTIONS (« approche l'enfant »)
                     ▼
   ┌────────────────────────┐  perçoit : personnes (pistes suivies, distance lidar, qui parle),
   │ SÉLECTEUR DE JEU       │  obstacles, David, jauges internes
   │ (sans LLM, ~10 Hz)     │  choisit UNE action focalisée parmi le RÉPERTOIRE, sur un FOND
   └───────────┬────────────┘  publie l'intention en cours + le « pourquoi » (journal)
               ▼
   CORPS SÛR (§3.2) → twist_mux → … ;  bras/cou/yeux/visage : arbitrage actionneurs existant
```

- **Le répertoire** = séquences + expressions + un **vocabulaire de déplacements courts**,
  composé par David, dans `data/`. ⚠️ Le « faire le tour de X » (M3) et la route/POI sont
  **SIM-ONLY** aujourd'hui (vérité terrain Gazebo, refus hors domaine 43) : au réel ils
  attendent l'odométrie.
- **Un seul décideur du corps.** Aujourd'hui la **bouche** demande déjà des mouvements (I1
  `marche`, M1-M4 « le corps fait ce que la conversation dit », via le régisseur). Avec un
  sélecteur, il y aurait **deux** décideurs. Règle proposée : la bouche et le metteur en scène
  ne **commandent** plus, ils déposent des **intentions** que le sélecteur pondère — c'est
  déjà la lettre du contrat I1 (« le LLM propose, l'exécutif dispose »), mais ça **change le
  câblage de M1-M4** (§8, question 6).
- **Le sélecteur** : la relecture a raison, l'utility AI n'a aucun appui robotique dans les
  sources et le projet a déjà prévu un **exécutif py_trees**. Proposition **hybride** : un
  behavior tree `py_trees_ros` pour la **structure** (ce qui est permis quand : superviseur
  présent ? corps sûr libre ? David a dit « ignore » ?) et, dans la feuille « choisir une
  action », un **score d'utilité** pour la **variété**. Avec des règles anti-échec que la
  première version oubliait : **hystérésis et engagement** (une action commencée se finit ;
  un candidat doit dominer de X % pendant Y ms pour la remplacer — sinon la « hésitation
  jouée » n'est qu'une oscillation), **pistes suivies** (une personne redétectée en bord de
  champ n'est pas « nouvelle » ; une intention de la boucle 2 porte l'identifiant d'une piste,
  pas « l'enfant »), et un **fond** (respiration, regard) qui suppose de **rouvrir l'arbitrage
  actionneurs** (aujourd'hui le gaze se tait pendant une séquence — pas de mélange).
- **David** : veto, mots secrets, fil de la mission, et une **console macro** (« va là »,
  « joue avec lui », « ignore », « reviens », « plus lent », « stop »). Deux trous à combler :
  **désigner « là » et « lui »** n'a aucun mécanisme (le bouton du gant dit seulement « c'est
  moi », `TargetPicker` vise le plus proche — étude identification) ; **lire l'intention** en
  rue sans écran de régie contredit « aucune frontière jeu/régie » (13/09) → la lisibilité
  doit être **dans le geste** (Dragan : le regard et l'amorce du corps disent le but), l'écran
  n'étant que l'outil de réglage en atelier.

### 4.2 Pourquoi et quand Didier agit — le modèle de timing

Ce que la recherche donne : le timing pèse plus que le contenu (Jon) ; une réponse verbale
au-delà d'1 s gagne à s'annoncer (Shiwa, 2ᵉ main) ; un robot qui ne fait rien pendant qu'on
le regarde déçoit (NED) ; Pepper vit sur un **fond permanent** avec **une seule activité**
focalisée. Modèle à cinq étages — **chaque chiffre est un réglage de départ**, aucun n'est
sourcé, et ceux qui touchent aux décisions du 31/10 sont marqués ⚠️ :

| Étage | Question | Mécanisme | Réglage de départ |
|---|---|---|---|
| **Mission** | où va-t-on ? | destination + route ; la mission **tire** | ⚠️ une « pression de route » qui monte pendant un arrêt **contredit** « aucun minuteur ne coupe une scène qui vit » et « relance à 90 s seulement après un arrêt de SON fait » (31/10). Alternative compatible : la pression ne monte que pendant les arrêts **de Didier**, jamais après un « stop » de David, et elle ne coupe pas : elle **propose** de repartir (en mots) |
| **Pulsions** | pourquoi maintenant ? | jauges **ennui** (rien ne se passe), **curiosité** (nouveau sur une piste suivie), **lubie**, frein **fatigue** | ennui +1/10 s, remis à 0 par toute action ; lubie **≤ 1 / 2 min** (31/10) |
| **Offres** | à quoi réagir ? | Johnstone : tout événement est une offre à prendre ou refuser — entrée en zone sociale, voix forte, signe de David, enfant qui approche, obstacle sur la route ; valeur + **durée de vie** (~3 s) | zones de Hall (valeurs classiques, non relues) |
| **Sélecteur** | quoi jouer, est-ce le moment ? | BT + score ; **une action focalisée** sur un **fond** ; **période réfractaire** ; hystérésis | réaction à une offre : viser < 1 s ; initiative spontanée : **un seul chiffre à unifier** — 8 s entre tours spontanés (23/10), 2 min entre arrêts (31/10) : proposition = **≥ 8 s entre deux initiatives, ≥ 2 min entre deux arrêts de route**, les deux gravés en tests |
| **Exécution** | comment ? | séquence + pas sous corps sûr ; **anticipation** : le regard se tourne avant le corps (principe de Shimon/AUR — **aucun délai chiffré dans les sources** ; « 300 ms » de la première version était inventé) | durée d'une action : 2-15 s ; un arrêt qui vit n'a pas de minuteur (31/10) |

⚠️ **« Les arrêts sont joués »** : le 31/10 a décidé que Didier **réclame d'abord en mots**
un arrêt (refusable). Jouer directement l'arrêt serait un re-tranchage (§8, question 5).
Compatible : il **réclame en mots ET amorce** (regard, ralentissement), et ne s'arrête que si
David ne refuse pas dans les 3 s — c'est l'hésitation jouée, et c'est lisible.

Chaque action est **journalisée avec l'offre et la pulsion qui l'ont gagnée** : c'est le
journal que David relit pour régler les potards. **Les obstacles sur la route sont des
partenaires** : le corps sûr garantit qu'on ne les touche pas, le sélecteur décide si on les
contourne, si on s'arrête, si on parle, si on suit trois pas.

## 5. Comprendre l'espace : trois niveaux

| Niveau | Question | Source | État |
|---|---|---|---|
| **Obstacle** | quelque chose à moins d'un mètre, tout autour ? | **lidar 2D** sur le Pi 4 (décidé) | **absent** |
| **Personnes** | où, à quelle distance (lidar fusionné, plus la hauteur de boîte), qui regarde, qui parle (ReSpeaker : direction **non couverte** par la recherche) | caméra + détection sur Pi 5 — ⚠️ **charge CPU non mesurée** avec `chat_node` + piper + MediaPipe déjà dessus ; AI HAT+ si besoin | partiel, fragile (occlusion) |
| **Sens** | que se passe-t-il ? | VLM, boucle 2 | codé, à nourrir |

Garde-fous : jamais une distance demandée à un VLM ; jamais la caméra seule qui autorise un
mouvement ; une intention de la boucle 2 **porte l'identifiant d'une piste**, sinon elle est
périmée à l'arrivée.

## 6. Conséquences sur l'architecture (mono-dépôt `dadou`)

Trois packages côté robot, absents de l'arborescence du 01/11 : `didier_corps_sur` (Pi 4,
§3.2-3.3), `didier_perception` (Pi 5, état du monde publié, contrat testé), `didier_jeu`
(sélecteur + répertoire + journal). Plus : les contrats correspondants dans `dadou_contrats` ;
le vocabulaire de déplacements dans `data/` ; un **lidar simulé** et des **passants** dans la
sim (HuNavSim est testé Humble/Fortress, **pas** Jazzy/Harmonic — à vérifier ; à défaut des
acteurs gz scriptés) — sachant que **la caméra Gazebo ne détecte personne** (étude interaction
§10.8) : en sim, la perception des personnes reste **scriptée**, donc une porte de sortie
« sans ennui en sim » teste le **mécanisme**, pas le **réglage**.

Et trois **frictions** avec les décisions du 01/11, à ne pas cacher : le chemin roues serait
touché **avant** L4 ; la télécommande « Twist dès sa naissance » (L4) devient « console macro
+ Twist en mode manuel », ce qui n'est pas la même télécommande ; l'homme-mort séparé décidé
pour la télécommande USB devient le **signal de vie** du §3.1 — à écrire dans son étude.

## 7. La contradiction à trancher

| 13/09 | 01/11 | Réconciliation possible |
|---|---|---|
| « Didier n'est pas un robot autonome, c'est un instrument de jeu » | « qu'il prenne ses propres décisions, qu'il improvise » ; « bouger de façon autonome est la clé minimum » | **Didier est un instrument qui joue seul dans le cadre que David a écrit** — répertoire, règles, mission ; David garde veto, fil, et la console macro. L'autonomie est un réglage de l'instrument. |

Ce n'est pas une note de bas de page : c'est la question 10 du §8.

## 8. Les dix décisions — TRANCHÉES par David le 2026-11-02

| # | Question | Décision |
|---|---|---|
| 1 | Priorité | **S'insère** : la sim démarre sans attendre ; la maison après le premier roulage au sol télécommande en main (priorité 1 inchangée) ; la rue après L0-L2 + préalables |
| 2 | Préalables | **W1 (source e-stop) avant la rue ; odométrie avant A4** — pas bloquants en sim ni à la maison |
| 3 | Signal de vie | **Télécommande présente** (battement de cœur ; muette > 1 s = zéro et verrou) ; l'homme-mort TENU reste pour le manuel |
| 4 | Capteur | **Lidar 2D 360° sur le Pi 4** (modèle/prix à lire à l'achat) |
| 5 | Le 31/10 | **Gardé, variante « réclame ET amorce »** ; la pression de route ne monte qu'après SES arrêts, propose, ne coupe pas |
| 6 | Le corps | **Un seul décideur : le sélecteur** ; bouche et metteur en scène déposent des intentions (câblage de M1-M4 à changer) |
| 7 | Sélecteur | **Hybride py_trees (permis/interdit) + score (variété)**, hystérésis et engagement obligatoires |
| 8 | Télécommande L4 | **Deux modes nommés** : MANUEL (Twist direct, homme-mort tenu — la décision L4 tient) / CONSOLE (ordres macro + battement de cœur), état visible |
| 9 | Désigner | **Voix + regard de Didier** : « lui » = la piste qu'il regarde, « là » = sa direction de regard ; correction en jeu (« non, l'autre ») |
| 10 | Le 13/09 | **Re-tranché** : « Didier est un instrument qui joue seul dans le cadre que David a écrit » |

*Formulation d'origine des questions, conservée pour l'historique :*

1. **Priorité** : l'autonomie passe-t-elle devant les priorités 0-1 (chat_node V2 réel, test
   au sol télécommande en main) et devant l'ordre L0-L5 du mono-dépôt ? Ou s'y **insère**-t-elle
   (A0 après le premier roulage au sol, le reste après L1-L2) ? *Ma recommandation : s'insérer.*
2. **W1 (source d'arrêt d'urgence) et l'odométrie** deviennent-ils des **préalables** d'A0 et
   d'A4 ? *Recommandation : oui pour W1 avant tout roulage autonome ; odométrie avant A4.*
3. **Signal de vie** : le mouvement autonome est-il conditionné à un battement de cœur de la
   télécommande (présence) ou à l'homme-mort **tenu** (geste) ? *Recommandation : présence
   pour l'autonome borné, homme-mort tenu pour le manuel — à écrire dans l'étude télécommande.*
4. **Capteur** : lidar 2D 360° (voit derrière, ~130 €) ou ToF frontaux (20 € pièce, devant
   seulement, soleil) — et monté sur le **Pi 4**. *Recommandation : lidar, Pi 4.*
5. **Rouvre-t-on le 31/10** : arrêts réclamés en mots (ou amorcés), relance à 90 s, pas de
   minuteur ? *Recommandation : garder les trois, avec la variante « réclame ET amorce ».*
6. **Qui commande le corps** : la bouche (I1/M1-M4 via régisseur) ou le sélecteur ?
   *Recommandation : un seul — le sélecteur ; la bouche dépose des intentions.*
7. **Sélecteur** : exécutif py_trees déjà prévu, utility AI, ou l'hybride proposé ?
8. **L4** : la télécommande neuve reste-t-elle « Twist dès sa naissance », ou devient-elle
   « console macro + Twist manuel » ? *Recommandation : les deux, nommées comme deux modes.*
9. **Désigner « là » et « lui »** : par quel geste ? (étude identification : bouton du gant =
   « c'est moi » seulement.)
10. **Re-tranche-t-on le 13/09** (« pas un robot autonome ») dans le sens du §7 ?

## 9. Lots — ACTÉS le 02/11 dans cet ordre (A-préalables peut chevaucher A0 ; la sim démarre tout de suite)

| Lot | Contenu | Porte de sortie (mesurable) |
|---|---|---|
| **A-préalables** | W1 source e-stop ; battement de cœur télécommande + verrou dans twist_mux ; **premier roulage au sol télécommande en main** (priorité 1, inchangée) ; calibration PWM ↔ vitesse à la caméra | protocole du 04/07 rejoué + e-stop déclenché depuis la télécommande arrête en < 500 ms ; télécommande coupée → zéro en < 1 s |
| **A0 Corps sûr** | lidar sur le Pi 4 + `didier_corps_sur` + lidar simulé ; **toutes** les entrées autonomes filtrées ; cas capteur/superviseur perdus | sim : obstacle à 0,5 m → zéro en < 200 ms sur 20/20 essais, **y compris sur une séquence `moon-walk`** ; scan figé → zéro ; caméra : protocole 04/07 **+ épreuve d'obstacle** (carton à 0,5 m, roues hors sol puis au sol à PWM calibré) |
| **A+ Timing et regard** (= option A) | fond permanent (respiration, regard qui suit — rouvre l'arbitrage actionneurs) ; réaction au rire/à la voix ; **mesure de bout en bout** du délai parole sur le robot | délai STT→premier mot mesuré sur le robot ; une séance où Didier réagit en < 1,5 s à une voix forte sans David |
| **A1 Répertoire + sélecteur** | vocabulaire de déplacements dans `data/` ; `didier_jeu` (BT + score, hystérésis, pistes) ; journal « pourquoi » ; ordres macro depuis la page scène ; **perception scriptée** | **mécanisme** : 15 min de sim, zéro oscillation (deux changements d'action en < 2 s = échec), toutes les règles de fréquence respectées (gravées) ; **réglage** : séance réelle à l'arrêt, David derrière |
| **A2 Perception** | pistes de personnes + distance lidar + direction de voix → état du monde | occlusion partielle **au réel** (David passe devant un passant) : Didier n'avance pas ; distance ±20 cm sur mire |
| **A3 Metteur en scène** | la boucle 2 dépose des intentions liées à des pistes | une séance où ≥ 3 arrêts de Didier sont motivés par ce qu'il a vu, **relus par David** (pas par le système) |
| **A4 Rue** | déambulation autonome bornée, **après odométrie** | sortie filmée ; nombre de **vetos** de David compté et commenté (un veto n'est pas un échec, un contact l'est) |

## 10. Ce que la recherche n'a pas couvert (assumé)

Paroles de metteurs en scène sur l'autonomie ; Demers, Knight ; Ameca en improvisation ; Furhat
en Wizard-of-Oz ; Johnstone/Spolin **implémentés** ; latences des API LLM ; FPS Hailo avec pré/
post-traitement ; Depth Anything sur Pi 5 ; localisation de source sonore (ReSpeaker) ; robots
sociaux low-cost documentés ; drama managers sur robot ; prix RPLidar/RealSense/Orbbec ; HuNavSim
sur Jazzy/Harmonic. Seconde main : Shiwa, Jon the Robot (via ScienceDaily), Ameca, Anki, Bory,
la conclusion « curaté > autonome » d'Improbotics.

## 11. Journal

- **2026-11-01 soir** — Question de David pendant le lot L0. Quatre collectes web parallèles
  (≈ 270 k tokens), synthèse, exigence ajoutée en cours : **mouvement autonome = clé
  minimum** ; cadre : destination + obstacles-partenaires, télécommande macro, travail =
  pourquoi et quand Didier agit ; **capteur d'obstacle DÉCIDÉ** ; marge d'erreur de décision
  = atout (David), contact = non négociable (moi, accepté).
- **2026-11-01 nuit — relecture adversariale (Opus, 137 k tokens)** : 7 bloquants, 9
  importants, 6 mineurs. Les plus lourds : e-stop sans source présenté comme acquis ; deadman
  inopérant en autonomie ; 15 séquences à piste roues hors enveloppe ; perte de liaison non
  traitée ; bornes en m/s invérifiables sans odométrie ; contradictions tues avec le 31/10 et
  le 01/11 ; « 300 ms » inventé ; « 0,7-1 s » mal relu ; utility AI sans appui robotique ;
  option A caricaturée. **Étude réécrite** : §3.1 (préalables), §3.2-3.3 (enveloppe corrigée),
  §4 (A contenue dans B), §8 (dix décisions nommées), §9 (lot préalables + A+).
- **2026-11-01 nuit (suite)** — David : « on va commencer en grande partie en sim et dans ma
  maison, donc aucun risque » → §3.4 : trois terrains, les préalables §3.1 deviennent des
  préalables de **rue** ; le travail sim peut démarrer sans attendre.
- **2026-11-02** — **Les dix questions tranchées par David**, toutes dans le sens recommandé
  (§8). Étude passée en DÉCIDÉE ; lots A-préalables → A0 → A+ → A1 → A2 → A3 → A4 actés ;
  conséquences reportées dans `etude-interaction.md` §1 (re-tranchage du 13/09),
  `etude-architecture-globale.md` (3 packages, L4 à deux modes) et `chantiers.md`.
