# Salle de répétition simulée — Didier déambule en ville, les bugs commencent

*Étude du 2026-10-07, demandée par David : « une simulation assez réaliste
pour m'entraîner — un environnement urbain où Didier déambule, où les bugs se
déclenchent et où commence l'histoire de la mauvaise foi ; je communique avec
un casque Bluetooth ». Avec la demande explicite de relier la technique à la
séance d'intention des 30/09–01/10, aux pistes de déambulation et aux
erreurs réelles de Didier.*

> **Statut : PROPOSITION.** Rien n'est acté. Les faits (ce qui existe, ce que
> Gazebo sait faire, ce que la simulation ne peut pas reproduire) sont fermes ;
> le découpage en lots et les arbitrages du §8 attendent David.

> ⚠️ Dépôt public. La séance d'intention est un document intime hors dépôt
> (dossier du spectacle). Cette étude n'en cite que les **conclusions** déjà
> autorisées à l'être : boss débordé, Didier amoureux de tout, bugs = routines
> de sécurité, deux vitesses, triangle, première marche = trajet vers le
> Hangar à Bananes.

---

## 0. Verdict en dix lignes

**C'est faisable, et les deux tiers existent déjà.** Le banc PC du 13/09
(`operations.md` §Banc PC) fait tourner le VRAI `chat_node` et le VRAI
`person_tracker` sur le PC, avec un casque Bluetooth via PipeWire, le corps
étant le Didier de Gazebo. Il manque quatre choses pour en faire une salle de
répétition : **une rue** (le monde actuel est un plancher de scène nu), **un
David virtuel** que la vraie perception voit dans l'image simulée, **un
régisseur de pannes** qui déclenche des bugs réels et des bugs joués sans que
David sache lesquels, et **le personnage de mauvaise foi** qui rattrape (mal)
ses conneries. Plus l'enregistrement, parce que la méthode décidée est « roder
avant de figer, enregistrer et débriefer ».

**Et une vérité à poser d'emblée** : la simulation entraîne la relation
David–Didier et le réflexe « panne = jeu ». Elle n'entraîne **pas** le triangle
avec de vrais passants, ni la peur, ni les enfants, ni le bruit sur le vrai
micro (§6). Il faut la vouloir pour ce qu'elle sait faire, pas pour remplacer
la rue.

Ce chantier est exactement le **verrou de sortie de la phase C** de
[`etude-interaction.md`](etude-interaction.md) §9 : *« une déambulation se joue
de bout en bout en simulation, avec David »*. Il ne crée pas un chantier de
plus : il donne un lieu aux lots I0–I4 qui n'en avaient pas.

---

## 1. Ce que la simulation doit entraîner — le lien avec la séance d'intention

La séance des 30/09–01/10 a fixé le cadre de jeu. Chaque conclusion dicte une
exigence du simulateur :

| Conclusion de la séance | Ce que le simulateur doit permettre |
|---|---|
| **Première marche de l'échelle = un trajet** (amener Didier au Hangar à Bananes, avec mille difficultés en route) | La séance type est un **trajet de 150–300 m** vers une destination visible, pas une scène fixe. Le monde est une rue avec un but au bout. |
| **David devant, Didier suit et décroche** (pas de navigation autonome) | David marche (son avatar), Didier le suit avec le VRAI `person_follower`, et **décroche pour de vraies raisons** (cible perdue, bordure, deadman) — pas sur script. |
| **Bugs = routines de sécurité** : une vraie panne, un arrêt de sécurité et un bug joué **ont la même tête** | Le régisseur mélange **pannes techniques injectées** (nœud tué, cible perdue, STT corrompu) et **bugs joués** (lubie, refus, mauvaise foi). David ne sait jamais lequel — c'est le réflexe à entraîner : ne plus redevenir technicien. |
| **Deux vitesses** : boucle des bugs (attente sûre) ↔ avancée (quand une connexion se fait) ; David choisit la bascule | Le simulateur ne force pas le rythme : les bugs tombent, David décide quand il relance la mission. Le débrief mesure combien de temps il reste dans chaque vitesse. |
| **Didier amoureux de tout**, lubies tenues, **objets avant les gens** | Le monde est peuplé d'**objets aimables** : lampadaire, boulangerie, poubelle, chien, banc, vitrine. Une lubie = Didier **suit l'objet** au lieu de David (c'est littéralement le mode d'échec « saut de cible » du suivi, §2). |
| **Trois fermetures de lubie** : raison absurde, contagion d'absurde, contrainte à la télécommande | La **télécommande est un accessoire du jeu** : David a la manette, elle écrase le suivi (priorité 100, comme en vrai), et elle peut rater (panne injectée). |
| **Boss débordé**, conflit né des circonstances, jamais « avoir raison » | L'**urgence** est dans le scénario (« on est attendus au Hangar à 15 h ») ; les circonstances fournissent l'adversaire, pas Didier. |
| **Registre** : doux crétin enthousiaste, kitsch de vendeur, qui **rattrape (mal) ses conneries** ; « nouvelle version, fonctionnalité absurde » + démo qui rate | C'est la **mauvaise foi** : un 4ᵉ persona (ou une surcouche du socle) qui nie le bug, l'annonce comme une fonctionnalité, accuse David, puis se rattrape de travers. |
| **Entrée dans le jeu = aider sur un bug** ; enfants = un rôle (mécaniciens) | Hors périmètre de la sim à cœur (il faut des gens). Un **passant simulé** peut l'esquisser (§5, lot R5), avec une réserve forte sur sa complaisance. |
| **Fiabilité d'abord** — condition préalable, pas un détail | La sim ne touche **rien** du chemin roues réel (domaine 43, aucun code de pannes dans le bringup). Et elle sert aussi à **fiabiliser** : chaque panne jouée en sim est une panne réelle qu'on a fini par comprendre. |

**La boussole** — *vibrer avec les gens sur place* — tranche un point : la
simulation n'est pas là pour rendre Didier plus spectaculaire, elle est là
pour que David arrive dans la rue **déchargé** du contrôle. Le critère de
réussite n'est pas « Didier suit bien », c'est « David n'est pas sorti du jeu
une seule fois en quinze minutes de pannes ».

---

## 2. Le catalogue des erreurs de Didier — réelles, injectables, jouables

Toutes les lignes ci-dessous sont des pannes **réellement vécues** ou des
modes de défaillance **établis par les études**. C'est la matière première du
régisseur : on ne joue que des bugs vrais.

| Erreur réelle (source) | Comment l'injecter en simulation | Ce que ça donne en jeu (registre mauvaise foi) |
|---|---|---|
| **Perte de liaison → deadman**, arrêt net en 400 ms (`twist_deadman`, validé caméra 04/07) | Couper `cmd_vel_remote` / `cmd_vel_follow` (relais qui jette les messages) ou tuer la chaîne drive | Didier s'arrête pile au milieu du trottoir. « Je fais une pause syndicale. » |
| **Cible perdue / saut de cible** (`target_picker`, étude suivi §3 : la monoculaire ne distingue pas deux silhouettes) | Un second acteur croise la trajectoire ; occultation par un mobilier ; virage serré | Didier **part avec quelqu'un d'autre** ou vers un lampadaire = **la lubie**, telle quelle. « Elle a l'air plus sympa que toi. » |
| **Visage figé / « deux signaux »** (incident 13/07, driver LED) | Geler les publications `face` (relais) | Regard fixe pendant que David parle. « Je t'écoute très fort. » |
| **Servo mort** (bug `random` du 11/07, bras muet depuis sept. 2025 sans que personne ne le voie) | Jeter `left_arm` ou `neck` sur le pont servos sim | « Mon bras gauche est en grève. C'est légal. » |
| **Le chat écrase le visage au moindre bruit** (chat_node coupé le 11/07) | Baisser le seuil VAD via le bruit injecté au micro (§4) | Didier répond au trafic, parle dans le vide. « Je parlais au bus. » |
| **STT qui hallucine** (« il parle d'Astérix », whisper `tiny` sur du bruit) | Mélanger du bruit de rue dans la capture ; ou remplacer la transcription par un contresens (relais texte, sim only) | Le contresens appliqué au premier degré — **c'est la règle du « oui, et »** de la note de création, pas une panne. |
| **Latence 4–9 s** mesurée sur le Pi 5 (le PC fait 2–3× mieux : la sim serait **plus flatteuse que le réel**) | Retard artificiel calé sur les latences mesurées du Pi (`etude-interaction` / mémoire proto) | Le silence qui s'étire. Didier joue `reflechit` + bips ; David apprend à meubler. |
| **Conteneur mort → black-out ~40 s** (crash-test `docker kill`, télédiagnostic) | Tuer puis relancer le conteneur vision (le régisseur a le droit, comme l'agent de télédiagnostic) | **Le reboot = l'expérience de mort imminente** du catalogue de prétextes : « pendant la panne, j'ai vu quelque chose ». Le bug devient le prétexte de la quête. |
| **Sourd à 3 m** (ronflement secteur, un humain à 3 m est 11 dB sous le bruit) | Bruit de rue dans la capture micro, niveau réglable | **David relaie** (« vieux robot un peu sourd ») — déjà prévu comme levier de jeu dans `etude-interaction` §6 ter. |
| **Ressaut de trottoir 12–15 cm** (note de création §7.5 : « une excellente scène, à condition que ce soit choisi ») | Bordures physiques dans le monde ; Didier bloque | « Je ne monte pas, c'est une question de principe. » |
| **Télécommande qui rate** (boutons du dos qui éteignent le Pi, liaison WiFi saturée en festival — risque n°1 de la note de création) | Couper la manette 10 s | Le pouvoir du boss, montré, et qui rate. C'est la 3ᵉ fermeture de lubie qui échoue. |
| **Batterie** (autonomie jamais mesurée en conditions réelles) | Événement « batterie faible » : plafond de vitesse divisé par deux | Didier ralentit, se plaint, demande à manger (« la nourriture » — désir impossible, piste de la séance). |
| **Pi fumé** (12/09, cause inconnue) | Non jouable, et on ne le joue pas. | — |

Deux lignes méritent qu'on s'y arrête, parce qu'elles **fusionnent technique
et dramaturgie** sans effort :

- **Le saut de cible est la lubie.** Le suivi monoculaire choisit la plus
  grande silhouette ; dès qu'un passant ou un poteau fait mieux que David,
  Didier part. L'étude suivi (§3) le décrit comme un défaut à corriger. Ici,
  c'est le personnage : *il suit son intuition comme un bébé vers un jouet*.
  Les deux lectures sont vraies ; la sim permet de **doser** (seuil
  d'adhérence) et de voir laquelle sert le jeu.
- **Le reboot est le prétexte B5.** La seule panne qui fasse vraiment peur à
  David en représentation (40 s de robot éteint au milieu des gens) est aussi
  l'origine la plus forte de la quête dans le catalogue de prétextes. Si le
  réflexe « il redémarre → il a vu quelque chose → où est-ce ? » est appris
  en sim, la pire panne devient la meilleure scène.

---

## 3. Ce qui existe déjà (état des lieux 2026-10-07)

| Brique | État | Ce qu'il manque pour la répétition |
|---|---|---|
| Sim Gazebo Harmonic (`robot_sim`, `conf/docker/sim/`) | Monde `stage.sdf` = plancher 10×8 m + soleil ; caméra embarquée 15 Hz bridgée ; LED, servos, roues (`/cmd_vel`), web, visage | **Une rue** |
| Chaîne roues sim (`drive.launch.py`) | twist_mux remote 100 > web 50 > follow 20 > anim 10, deadman 400 ms, identique au réel | Rien |
| Suivi de personne (`person_follower`) | Validé sim 5/5 (perception **scriptée** : `ros2 topic pub /vision/person_box`) | Une vraie perception sur l'image simulée |
| Perception (`person_tracker_node`, dépôt vision) | MediaPipe sur **`/dev/video0` uniquement** (`cv2.VideoCapture`) | Un paramètre `camera_topic` (sim only) pour lire `camera/image_raw` de Gazebo — ou v4l2loopback côté hôte, sans toucher au code |
| Conversation (`chat_node`, banc x86) | Vrai code du Pi 5 ; **casque Bluetooth déjà branché via PipeWire** (socket `/run/user/1000/pulse` montée, 13/09) ; personas commutables (bougon/naïf/vantard) | Persona mauvaise foi ; bruit de rue dans la capture ; retard calé Pi |
| Gaze, arbitrage `animation_state`, visage web (8766), console web (8765) | Opérationnels sur le banc | Rien |
| Télécommande (`dadou_control_ros`) | Gamepad USB + GUI, publie sur le domaine donné (43 = sim) | Rien — c'est l'accessoire du boss |
| Télédiagnostic | `collect-incident.sh` testé contre la sim ; droits de restart définis (§7) | Le régisseur réutilise le même « droit de tuer » |
| Corpus de rue (13/09, `enregistre-rue.sh`) | Ambiances enregistrées au festival (coin calme / foule / sono / en marchant) | À verser dans la capture micro du banc |
| Outils de chaos ROS 2 | `ros2_fault_injection` (MIT, Jazzy, annoncé 09/2026) : retard, perte, bruit, gel sur Twist/Odometry/… — **pas** d'image, pas de kill | Relais maison pour `PointStamped`, `StringTime`, `Image` ; kill via docker (déjà le modèle du télédiagnostic) |

Ressources du PC : 32 fils, 30 Go, RTX 4060 (la sim rend aujourd'hui sur
l'Intel via `/dev/dri` ; en headless ogre2 ça suffit, le GPU NVIDIA est une
réserve).

---

## 4. Architecture cible — quatre blocs posés sur le banc existant

```
          casque BT (PipeWire) ──── micro ──┐  + bruit de rue (corpus 13/09)
          manette USB = télécommande (43)   │
                                            ▼
 ┌──────────────────────┐    ┌──────────────────────────────┐
 │ dadou-sim (robot)    │    │ dadou-vision-x86 (tête)      │
 │ monde RUE            │    │ person_tracker ◄── image gz  │  ◄── MÊME code que le Pi 5
 │ avatar David (piloté)│──► │ chat_node (persona mauvaise  │
 │ passants scriptés    │img │   foi, retard calé Pi)       │
 │ roues + deadman      │◄───│ /vision/person_box, face…    │
 │ servos, LED, visage  │    └──────────────────────────────┘
 └──────────┬───────────┘                 ▲
            │                             │ bugs techniques (kill, drop, delay, bruit)
            │          ┌──────────────────┴────────────┐
            └─────────►│ RÉGISSEUR DE PANNES (sim only) │──► bugs joués (instruction persona)
                       │ scénario YAML + aléa + journal │──► journal horodaté → débrief
                       └───────────────────────────────┘
```

### 4.1 La rue (`robot_sim/worlds/rue.sdf`)

Pas une ville : **un trottoir de 150–300 m** avec ce qui fait des scènes.
Chaussée + trottoir avec **bordures physiques** (12–15 cm, pour que Didier
bloque vraiment), un passage piéton, des lampadaires, un banc, des poubelles,
une **boulangerie** (vitrine = objet d'amour, nourriture), une terrasse, deux
voitures garées, un chien, et au bout **le but** : un hangar avec une banane
géante dessus. Lumière réglable jour/soir (le festival du 13/09 finissait de
nuit).

Fuel ne fournit **aucun monde urbain prêt** pour Harmonic (recherche du
07/10 : `citysim` a disparu, la collection `gazebo_models_worlds_collection`
est en GPL-3.0 — à ne pas embarquer dans un dépôt public sans relire — et la
recherche par mot-clé de l'API Fuel est inexploitable). La rue se **construit
à la main** à partir de primitives et de quelques modèles unitaires
d'OpenRobotics (lampadaire, panneau, poubelle, voiture : licences à relire une
par une au moment de les prendre). C'est une journée de travail, et le
détecteur n'a pas besoin de photoréalisme : une silhouette humaine sur un
fond plausible suffit — à **mesurer** avant de construire (lot R0).

### 4.2 Le David virtuel — un modèle piloté, pas un acteur

Gazebo Harmonic sait animer des **acteurs** (`<actor>`, mesh COLLADA + marche
+ trajectoire scriptée) et la doc officielle garantit qu'ils sont **visibles
par les caméras RGB**. Mais : **aucune physique** (« no forces are applied on
them ») et **aucun pilotage dynamique documenté** pour Harmonic (le service
`set_pose` existe pour les entités, son effet sur un acteur n'est pas
vérifié). Un acteur fait donc un **passant** parfait (trajectoire scriptée
qui croise David pour provoquer un saut de cible), pas un David.

**David = un modèle à roulettes avec une silhouette humaine** (plugin
`VelocityControl` de gz, Twist bridgé, ~1,2 m/s, vitesse de marche). **Il ne
se pilote PAS à la manette** : depuis la décision du 07/10 (§4.5), les mains de
David tiennent la **vraie télécommande**, comme en rue. L'avatar suit donc un
**itinéraire tracé** le long du trottoir (le trajet vers le Hangar) et David
ne commande que sa **progression** : **[DÉCIDÉ 07/10] par un fader du
boîtier de faders déjà en stock de la télécommande** (RP2040-Zero série, cf.
§4.5) — fader à zéro = arrêt, fin de course = marche rapide, continu entre les
deux ; le demi-tour est un bouton. C'est un geste de pouce, les mains restent
sur la télécommande. Il perd la liberté de quitter le trottoir ; il garde la
seule chose à répéter : être devant, et que Didier décroche. Une silhouette statique est moins jolie qu'un acteur qui
marche ; mais c'est elle que MediaPipe doit voir, et le lot R0 mesure si elle
est vue. Si la détection
est trop faible, repli : **un acteur attaché** au modèle piloté (à essayer,
non garanti) ou, en dernier recours, la perception scriptée actuelle.

**La perception doit être la vraie.** Deux chemins, au choix du lot R0 :

- **(a) paramètre `camera_topic`** dans `person_tracker_node` : si non vide,
  le node s'abonne à `camera/image_raw` au lieu d'ouvrir `/dev/video0`.
  Petit changement dans le code de prod, testable, défaut inchangé — c'est le
  pattern `drive_enabled`/`web_drive` déjà accepté dans le dépôt.
- **(b) v4l2loopback** côté hôte : l'image Gazebo est poussée dans un
  `/dev/videoN` virtuel, le tracker ne change pas d'une ligne. Zéro code,
  mais un module noyau à installer sur le PC (noyau 7.0 : disponibilité du
  dkms à vérifier).

Recommandation : **(a)**, parce que le test de bout en bout en CI devient
possible (un sac d'images rejoué dans le node) et parce que la règle du
projet est « la vérification exécute le même code que la prod », pas « le
même binaire sur un périphérique bidouillé ».

### 4.5 La télécommande réelle dans la boucle — [DÉCIDÉ 07/10] « l'idéal »

David a tranché : **pas de manette de substitution, la vraie télécommande**
(le Pi 4 portable de `dadou_control_ros` : gamepad USB + GUI Tkinter). C'est
le bon choix, pour trois raisons qui ne tiennent pas à la fidélité : c'est
l'**accessoire du boss** qu'il faut apprendre à tenir en jouant (la 3ᵉ
fermeture de lubie), c'est **sa latence et ses ratés** à elle qu'il faut
connaître, et elle commande aussi les animations, visages et sons — tout le
pupitre de la séance, pas seulement les roues.

**Comment ça marche, et ce qu'il y a à faire** (vérifié dans le code le
07/10) :

| Point | Constat | Travail |
|---|---|---|
| **Domaine ROS** | La télécommande lit `ROS_DOMAIN_ID` dans son compose, défaut **42** (robot réel). Rien dans Ansible ni systemd ne le fixe autrement. | Lancer avec `ROS_DOMAIN_ID=43` (variable d'environnement ou fichier `.env` sur le Pi de la télécommande). **Aucune ligne de code.** |
| **Réseau** | Conteneurs en `network_mode: host` des deux côtés ; la découverte FastDDS passe en multicast UDP sur le LAN — exactement comme entre la télécommande et le robot aujourd'hui. | La télécommande rejoint le **même réseau que le PC** (le WiFi de la maison, ou le routeur du robot si le PC y est). Si le multicast WiFi déconne (ça arrive), repli : `ROS_DISCOVERY_SERVER` sur le PC — même remède que pour la liaison réelle. |
| **Roues** | Elle publie `wheels` en StringTime (legacy) ; dans la sim, `wheels_bridge` traduit vers `cmd_vel_remote`, **priorité 100** dans twist_mux, deadman 400 ms derrière. | **Rien** : `operations.md` le note déjà (« la télécommande physique, prio 100, garderait la main »). Elle écrase le suivi en sim comme en vrai. |
| **Animations, visages, audio** | Mêmes topics que le robot ; la sim les consomme si `ANIMATIONS=true FACE=true`. | **Rien.** Le pupitre complet marche. |
| **Avatar de David** | La télécommande occupe les mains. **Le boîtier de faders existe** (`sliders`, RP2040-Zero série 9600 bauds) : aujourd'hui `send_sliders` mappe EN DUR 1 fader → cou (0..1) et 2 faders → roues gauche/droite (−100..100), selon la longueur du message. | **[DÉCIDÉ 07/10] un fader = progression de l'avatar.** Travail côté `dadou_control_ros` : rendre le mapping des faders **configurable par profil** (défaut = l'actuel, octet pour octet ; profil « répétition » = fader 1 → topic `avatar_speed`, StringTime 0..1) au lieu du `if len(msg)`. Petit, mais c'est du code de télécommande : tests à valeurs gravées (§11.4). |
| **⚠️ Le vrai risque : le mélange des domaines** | Une télécommande oubliée en **43** le jour d'une sortie = aucun contrôle sur Didier. Une télécommande en **42** pendant une répétition, robot sous tension = **les commandes de répétition atteignent le vrai Didier**. Aujourd'hui le risque est nul (le robot est hors tension depuis le 12/09), mais il naît le jour où il revient. | **Avant le retour du robot** : un **indicateur visible** du domaine sur la GUI de la télécommande (bandeau « SIMULATION » / « DIDIER RÉEL », comme la console web le fait déjà en vert/rouge) et un geste **explicite** pour basculer, jamais une variable qu'on oublie. Petit lot côté `dadou_control_ros`, mais il est **antérieur** à toute répétition avec le robot rebranché. La règle CLAUDE.md « ne jamais mélanger 42 et 43 » prend ici son cas d'usage le plus concret. |

Ce que la décision ne change pas : le régisseur peut toujours **couper la
télécommande** (relais sur `cmd_vel_remote` côté sim, 10 s) — la panne
« manette qui rate » reste jouable sans toucher au Pi de la télécommande.

### 4.3 Le régisseur de pannes (package sim only, jamais dans le bringup)

Un node `rehearsal_director` dans `robot_sim` (ou un package `robot_rehearsal`
dédié, autonome comme `robot_drive`), qui lit un **scénario YAML** :

```yaml
mission: hangar-a-bananes          # destination, urgence annoncée
duree_min: 15
pannes:                            # tirées au sort dans la fenêtre, ou à l'instant fixé
  - { type: cible_perdue,   t: random, duree_s: 8 }        # technique
  - { type: deadman,        t: 240,    duree_s: 5 }        # technique
  - { type: stt_bruit,      t: random, niveau_db: -12 }    # technique (bruit de rue)
  - { type: lubie,          t: random, objet: boulangerie } # JOUÉ (instruction persona)
  - { type: mauvaise_foi,   t: apres_panne }               # JOUÉ : nie la panne précédente
  - { type: reboot_vision,  t: 600 }                       # technique, 40 s, prétexte B5
```

Deux **canaux d'injection**, et c'est la règle structurante :

1. **Canal technique** — n'agit **qu'à l'extérieur** du code de prod : tuer un
   process ou un conteneur (le droit déjà accordé à l'agent de
   télédiagnostic), relais de topic qui jette/retarde/bruite (`/vision/
   person_box`, `face`, `cmd_vel_*`, servos sim), bruit audio mélangé dans la
   source PipeWire du micro. **Aucune ligne de « chaos » dans `chat_node`,
   `person_follower` ou `wheels_node`** : le code embarqué ne connaît pas la
   répétition. (`ros2_fault_injection` couvre le retard/perte/bruit sur Twist ;
   pour nos types à nous, un relais maison de cent lignes fait l'affaire.)
2. **Canal joué** — une **instruction de jeu** envoyée au chat par le topic
   `persona`/instruction existant : « ton bras gauche vient de tomber en panne
   et tu refuses de l'admettre », « tu viens de tomber amoureux de la
   boulangerie à droite, tu veux y aller, tu tiens », « tu viens de
   redémarrer, tu as vu un endroit pendant la panne ». C'est le lot I1 de
   `etude-interaction` (transitions par réplique/instruction) vu de l'autre
   bout : le régisseur parle à Didier **comme David lui parlera**.

Et le principe de la séance : **David ne sait pas quel canal a tiré.** Le
journal horodaté du régisseur le lui dit **après**, au débrief — jamais
pendant.

### 4.4 Le casque, la régie, l'enregistrement

- **Casque Bluetooth** : déjà en place via PipeWire (13/09). ⚠️ Deux pièges
  documentés : un casque BT dont on ouvre le micro bascule en profil HFP —
  **mono, 8 ou 16 kHz** (CVSD/mSBC), la voix de Didier perd en qualité ; c'est
  acceptable (en rue il sortira sur une enceinte dans le bruit), mais il faut
  le savoir pour ne pas « corriger » la voix à cause du casque. Et le seuil
  d'énergie du VAD, absolu, dépend de la chaîne : le 13/09 un casque BT
  mettait le bruit de pièce à RMS 3000–9000 pour un seuil à 2800. Le bruit de
  rue injecté passe donc **par la source PipeWire** (une source virtuelle qui
  mélange micro + corpus), pas par le code.
- **Sortie** : voix de Didier + ambiance de rue + (R5) voix du passant simulé,
  dans le casque.
- **Enregistrement** (c'est la méthode décidée : enregistrer et débriefer) :
  `rosbag2` des topics de décision (`/vision/person*`, `cmd_vel*`, `face`,
  `animation_state`, `persona`, transcriptions), capture audio du casque
  (`pw-record`), image caméra de Didier, et le **journal du régisseur**. Le
  débrief se fait sur une **frise unique** : ce que le régisseur a injecté,
  ce que Didier a dit, ce que David a dit, combien de temps avant la relance.
  La frise est aussi la **boîte noire** du télédiagnostic (étape 2) : même
  format, même outil.

---

## 5. Le passant simulé (lot optionnel, à ne pas surestimer)

Le triangle David–Didier–passant est le cœur du spectacle, et il manque un
sommet. On peut en esquisser un : un second agent LLM qui joue un passant,
parle dans le casque (TTS), et dont le texte entre dans la conversation de
Didier. Ça permet de répéter **l'entrée dans le jeu par un bug** (« vous
pouvez appuyer là ? »), la demande de chemin, le « oui, et » sur une réponse
absurde.

**Réserve forte, à graver** : un LLM est complaisant — il répond toujours, il
joue le jeu, il ne part jamais. Or la littérature (étude déclenchement §4) dit
que **54 % des salutations de robot restent sans réponse** et que **27–29 % des
gens refusent** quoi qu'on fasse. Un passant simulé qui ne reproduit pas ces
taux entraîne David à **une rue qui n'existe pas**. Si on le fait, il tire ses
réactions dans cette distribution (refus, silence, « là-haut », blague,
enfant qui veut toucher) et il **s'en va** sans prévenir. Même ainsi, il reste
une marionnette : il s'agit d'apprendre les réflexes de forme, pas de
remplacer les gens.

---

## 6. Ce que la simulation n'entraîne PAS — à dire avant de commencer

| Hors de portée | Pourquoi | Ce qui le remplace |
|---|---|---|
| Le **regard des gens**, la peur d'aller où personne n'attend | C'est le blocage lui-même ; aucune sim ne le reproduit | Les marches basses de l'échelle, dans la rue, avec le kit de 1ʳᵉ sortie |
| Les **enfants** (approche, toucher, taper, manettes) | Dynamique physique et sociale, 50 kg en jeu | Règle jouée (Didier a peur), protocole sécurité, répétition en atelier avec des complices |
| Le **bruit réel sur le ReSpeaker** et son socle | Le corpus de rue est une approximation ; le socle plastique est suspect (étude interaction §6) | Corpus 13/09 + re-mesure au montage définitif (phase D) |
| L'**inertie des 50 kg**, le pavé, la chaîne | Physique Gazebo réglée à l'œil, jamais recalée (pas d'odométrie réelle) | Test scénique au sol (priorité 1), protocole caméra |
| La **latence du Pi 5** | Le PC est 2–3× plus rapide : sans retard artificiel la sim ment en mieux | Retard calé sur les mesures (§2) |
| La **liaison WiFi saturée** en festival | Tout est sur une machine | Coupures de manette injectées — c'est un symptôme, pas la cause |
| Le **coup-de-poing** (`e_stop` sans publieur) | Verrou **antérieur à tout**, rappelé par la note de création §7.2 et `etude-interaction` §8 | Il se fabrique, il ne se simule pas |

Autrement dit : la sim prépare **David** et affine **le personnage** ; elle ne
qualifie **rien** côté sécurité ni côté rue. Les verrous roues (test scénique,
W1 e_stop, coup-de-poing) ne bougent pas d'un cran.

---

## 7. Plan en lots — tout se fait pendant le gel du Pi 4

Principe : **mesurer avant de construire** (même règle que l'étude
interaction), et chaque lot a un verrou de sortie observable par David.

| Lot | Contenu | Verrou de sortie |
|---|---|---|
| **R0 — Faisabilité** (1 séance) | Une silhouette humaine posée dans `stage.sdf` ; `person_tracker` branché sur l'image gz (param `camera_topic`) ; mesure du taux de détection à 1/2/3/5 m, de face et de dos ; latence du casque BT mesurée ; bruit de rue mélangé dans la source PipeWire | **On sait si la vraie perception voit l'avatar**, en nombres. Sinon, le reste du plan change (acteur attaché, ou perception scriptée). |
| **R1 — La rue et le trajet** | `rue.sdf` (150–300 m, bordures, objets aimables, la banane au bout) ; avatar sur itinéraire, progression au **fader** de la télécommande (profil « répétition », §4.5) ; **la vraie télécommande sur le domaine 43** ; passant scripté (acteur) ; suivi + gaze réels | Didier suit l'avatar sur 100 m, **perd la cible dans un virage, bloque sur une bordure, part avec le passant** — trois décrochages vrais, non scriptés. |
| **R2 — Le régisseur, canal technique** | Scénario YAML, 6 pannes du §2, relais de topics, kill/restart, retard calé Pi, journal horodaté | Une séance de 15 min où David **ne distingue pas** panne injectée et panne survenue (il devine à l'aveugle, on compte). |
| **R3 — Le personnage** | Persona « mauvaise foi » (4ᵉ variante ou surcouche du socle) ; canal joué (lubies avec les objets du monde, les trois fermetures, le reboot-prétexte) ; **dépend de I0** (état de mission, `etude-interaction` §9) au moins en version minimale (destination + urgence) | Le trajet vers le Hangar **joué de bout en bout** sans que David sorte du jeu. C'est le verrou de la phase C. |
| **R4 — Enregistrement et débrief** | rosbag + audio + journal → frise unique ; débrief guidé (temps passé dans chaque « vitesse », relances, bugs manqués) | Deux séances comparées : la **progression se voit**. |
| **R5 — Passant simulé** (optionnel) | Agent LLM passant avec la distribution de réactions du §5, TTS dans le casque, texte vers Didier | L'entrée par un bug et le « oui, et » répétés dix fois chacun. |

Ordre : R0 → R1 → R2 → R3 → R4, R5 à la fin et seulement si R3 tient. R0 et R1
sont de la **mécanique sim** (Sonnet/Haiku sur spec fermée) ; R2 touche aux
droits de tuer des process (revue Opus, même si c'est sim only : on y définit
des réflexes qui iront un jour sur le robot via le télédiagnostic) ; R3 est de
l'**écriture** avec David, pas du code.

Coûts : aucun matériel. Le LLM de la conversation est déjà en place
(OpenRouter, modèle léger) ; une séance de 15 min coûte des centimes. Le
temps : R0 une soirée, R1 deux à trois, R2 deux, R3 au rythme de l'écriture.

---

## 8. Ce que David doit trancher (recommandation en gras)

1. **Ce qu'on entraîne d'abord** : **le duo et le réflexe « panne = jeu »**
   (R0–R3), le triangle plus tard et avec réserve (R5). L'alternative (passant
   d'abord) entraîne une rue complaisante.
2. ~~Qui déplace David~~ — **[DÉCIDÉ 07/10] la vraie télécommande dans les
   mains** (§4.5), et **l'avatar progresse sur un itinéraire au rythme d'un
   fader du boîtier déjà en stock** (décision du même jour).
3. **Perception vraie ou scriptée** : **vraie** (param `camera_topic`, petit
   changement de prod), parce que les décrochages doivent être vrais pour
   que les bugs le soient. Repli scripté si R0 mesure une détection trop
   faible.
4. **Le régisseur dit-il ce qu'il a tiré ?** **Jamais pendant, toujours
   après.** C'est la condition pour que « vraie panne et bug joué ont la même
   tête » soit vécu, pas déclaré.
5. **La mauvaise foi : 4ᵉ persona ou socle ?** **Surcouche du socle**, parce
   que le rattrapage de travers doit survivre au changement d'humeur
   (bougon/naïf/vantard restent des couleurs ; la mauvaise foi est un
   réflexe).

---

## 9. Ce que cette étude ne re-tranche pas

Les seuils de la FSM d'engagement et le « réactif d'abord » (étude
déclenchement §5), le déclenchement de parole par réplique et la mémoire en
cinq cases (étude interaction §3), le plan web (Headscale, `cmd_vel_web`
prio 50), les verrous roues. La répétition simulée **consomme** ces décisions
comme décor ; si l'une d'elles se révèle fausse en séance, ça remonte dans
son étude, pas ici.

---

## 10. Des voix crédibles, fun et décalées — une palette à écouter, pas une décision

*Ajouté le 07/10 à la demande de David (« tu peux proposer des voix crédibles
mais fun et décalées ? »).*

**Ce que cette section ne fait pas.** L'arbitrage de la voix de Didier sur le
vrai robot (cloner David vs pousser la robotisation) est **suspendu au lot V0**
de [`etude-voix-didier.md`](etude-voix-didier.md) §5 : David tranche après
avoir écouté, pas avant, et rien ici ne force cette décision. Ce qui suit est
une **palette de costumes vocaux pour la répétition** — et, si l'un d'eux
colle au personnage, il entrera dans le banc d'écoute V0 comme candidat de
plus.

**Le principe qui rend tout ça gratuit.** La chaîne de prod synthétise avec
piper **in-process** puis passe par `effects.py` (trémolo 35 Hz + écrêteur +
regain, en numpy, par morceau). Un « costume » est donc un **jeu de
paramètres** de cet étage (plus, au besoin, une voix piper différente), pas un
nouveau moteur : zéro dépendance, zéro latence ajoutée, et le même code sur le
PC et sur le Pi. Les presets vivent en données (un dictionnaire), commutables
par didascalie ou par persona, testables sans son.

### 10.1 Les costumes proposés

| Costume | Base | Traitement | Quand | Pourquoi c'est juste |
|---|---|---|---|---|
| **Le vendeur de téléachat 80s** | piper voix masculine (`fr_FR-tom`) | débit ×1,1, compression franche, réverb de plateau courte, **jingle trois notes** avant chaque « nouvelle version » | les annonces de fonctionnalité absurde, la démo qui rate | C'est le registre décidé : *kitsch de vendeur, doux crétin enthousiaste*, dans la ligne synthwave du costume. |
| **La hotline** | même voix | passe-bande téléphone 300–3400 Hz, un souffle léger, **deux secondes de musique d'attente** avant de répondre | la **mauvaise foi** : nier la panne, « votre bug est important pour nous » | La mauvaise foi a une voix dans la vraie vie : celle du service client. Et l'attente **couvre la latence réelle** du LLM — un défaut devient un gag. |
| **Le jouet qui bugue** | même voix | bitcrush 8 bits + sous-échantillonnage 8 kHz + hachage, **dosé par le nombre de pannes actives** | pendant les pannes ; propre à zéro panne, « Speak & Spell » à trois | **Le son dit l'état de santé**, comme la jauge LED : David entend le niveau de bug sans regarder. C'est un vrai signal de diagnostic, et c'est du jeu. ⚠️ Mange l'intelligibilité : en salves, pas en continu. |
| **Didier amoureux** | même voix | +3 demi-tons, débit 0,85, vibrato lent ~5 Hz, réverb plus longue | la **lubie** (didascalie *amoureux*) | La lubie a un début et une fin audibles ; la voix revient à la normale à la fermeture — le public entend la structure. |
| **Le robot cassé** | même voix | modulation en anneau 30–50 Hz (le « Dalek »), courte | le glitch, le redémarrage, le reboot-prétexte | Cousin du trémolo 35 Hz déjà en prod : même famille sonore, donc continuité avec la voix actuelle. Même réserve d'intelligibilité que le jouet. |
| **L'octaver logiciel** | n'importe quelle base | −12 demi-tons mélangés ~50/50 avec le signal sec (`sox`/rubberband hors ligne, ou un pitch-shift simple en flux) | **toute la répétition**, si David veut entendre Didier *comme en ventriloquie* | Doublure du vrai octaver pour la sim. **Ce n'est pas le lot V0** (qui passe piper dans le VRAI octaver) et ça ne tranche pas A/B : c'est pour ne pas répéter avec une voix qui n'existera jamais. |

Un **levier gratuit** qui vaut tous les filtres, déjà noté dans l'étude voix
(§5, « le texte pilote la prosodie ») : le persona « mauvaise foi » écrit **des
phrases courtes, des ruptures, des hésitations écrites** (« euh… non. Si. En
fait c'est une fonctionnalité. »). Piper lit ce qu'on lui donne ; un texte
qui bafouille **sonne** décalé sans un seul effet.

**Banc d'écoute FAIT le 01/11** (`essais/voix/costumes.py`, WAV dans
`essais/voix/sorties/costumes/`, hors git) : une réplique, 14 rendus — sec
(= prod V2 piper), robot historique (le VRAI `effects.py`), les 5 costumes
ci-dessus, et 6 « déglingos » ajoutés à la demande de David (bégaiement
numérique + mot à l'envers, cassette qui cale, chorale de 3 Didier
désaccordés, robot chanteur au vocodeur, débit qui s'emballe, texte qui
bafouille). Tous normalisés à −20 dBFS RMS (en crête, l'écrêteur historique
sortait 11 dB au-dessus : l'oreille aurait triché). Whisper `small` transcrit
les 14 correctement — ⚠️ ça ne prouve PAS l'intelligibilité en rue (whisper
est bien plus robuste qu'un passant, et lisse même les bégaiements). Hauteur
par rééchantillonnage = hauteur et débit liés (voulu pour le gag). **Rien
d'intégré à la prod : suite = écoute de David sur enceintes (§10.3).**

### 10.2 Les voix des passants simulés (lot R5)

Si le passant simulé existe, il lui faut **plusieurs** voix, sinon David
répète avec la même personne dix fois. Candidats, tous piper, tous gratuits
(liste à **vérifier sur le catalogue piper** au moment de l'essai — citée de
mémoire, pas depuis une source) : `fr_FR-upmc` (deux locuteurs, *jessica* et
*pierre*), `fr_FR-tom`, `fr_FR-gilles`, `fr_FR-siwis` (la voix actuelle de
Didier, à **ne pas** donner à un passant), et surtout `fr_FR-mls`
**multi-locuteurs** (plus d'une centaine de timbres issus de livres audio) :
un locuteur tiré au sort par passant, débit et hauteur légèrement variés, et
le cortège n'a plus deux voix pareilles. Pas de voix d'enfant synthétique
crédible dans ce catalogue ; un enfant **joué** (hauteur +6 demi-tons, débit
rapide) est une caricature — acceptable pour une marionnette d'entraînement,
pas pour autre chose.

### 10.3 Comment choisir — le même banc que V0, sur le PC

1. **Six phrases** (les mêmes que `phrases-v0.txt` : salutation, question,
   réplique longue, chiffres, sifflantes, explosives) rendues dans chaque
   costume.
2. **Le test est l'alternance** : une réplique David ↔ Didier montée phrase à
   phrase, pas des extraits isolés.
3. **Juger le timbre sur des enceintes, pas dans le casque Bluetooth** — le
   profil HFP (mono, 8/16 kHz) écrase tout ce que les costumes font au-dessus
   de 4 kHz. Le casque sert à répéter, pas à choisir.
4. **Intelligibilité d'abord** : la note de création (§7.3) rappelle que si on
   n'entend pas Didier à 5 m dans le bruit, il n'y a pas de spectacle. Tout
   costume qui coûte de l'intelligibilité (jouet, Dalek) est réservé aux
   salves courtes.
5. Consigner au §9 de l'étude voix, pas ici : c'est son journal.

Ce que je ne peux pas faire : écouter. Ces recettes sont des points de départ
plausibles, pas des résultats. **Le choix est artistique et il est à David** —
l'étude voix l'a déjà écrit, cette section ne fait que lui fournir de quoi
écouter des choses fun avant le lot V0.

---

## 11. Architecture, tests et vérifications — ce qui reste dans le robot, ce qui n'y entre jamais

*Ajouté le 07/10 à la demande de David : « rester au maximum dans un idéal
d'architecture — rapidité, robustesse, fiabilité ; ajouter tous les tests et
vérifications nécessaires ; une partie a vocation à rester dans le robot et
doit être auditable et modifiable ».*

### 11.1 Les principes — ceux du dépôt, posés comme contraintes de conception

1. **Logique pure + node fin.** Tout comportement est un module pur (stdlib,
   numpy au plus ; config en `dataclass` gelée, **source unique** des défauts)
   et un node ROS qui ne fait que l'entrée/sortie. C'est ce qui rend tout
   testable sur l'hôte sans ROS, donc en CI — le patron de `follow_control`,
   `deadman`, `leds_logic`, `arbitration`.
2. **Contrats explicites et gelés.** Noms de topics, types, QoS et bornes
   vivent dans **un module de contrats par package**, et les tests de contrat
   lisent **les vrais fichiers livrés** (YAML, JSON), jamais une copie — comme
   `test_twist_mux_contract` parse `twist_mux.yaml`.
3. **Sûr par défaut, et sûr quand ça meurt.** Tout démarre OFF ; toute panne
   injectée a une **durée maximale** et se révoque seule ; si le régisseur
   meurt, les relais retombent **seuls** en passant (chien de garde côté
   relais, pas côté régisseur) ; **aucun relais de pannes n'est jamais posé
   dans un chemin de prod**, et `/cmd_vel` final n'est relayable par rien.
4. **Rapide parce que sobre.** Pas de relais sur l'image (15 Hz × 640×480 en
   Python : coûteux et inutile) : les pannes de perception s'injectent **en
   sortie** de perception (`/vision/person_box`, 16 Hz, 3 flottants). Relais
   en QoS profondeur 1 (une consigne périmée ne vaut rien), horloges
   **monotones** partout, aucun tampon non borné.
5. **Déterministe.** Tout aléa passe par une **graine** consignée au journal :
   une séance se **rejoue** à l'identique — c'est ce qui permet de comparer
   deux soirs, et de reproduire un bug du simulateur lui-même.
6. **Les comportements sont des données.** Scénario, catalogue de pannes,
   presets de voix, liste blanche des process, profil de faders : des
   fichiers validés par un **validateur qui refuse explicitement** (message
   actionnable), jamais des constantes dispersées. C'est ce qui rend
   l'ensemble modifiable par un humain ou par l'IA sans relire le code.

### 11.2 La carte : ce qui a vocation à rester dans le robot, ce qui est sim-only

*Revue adversariale du 08/10 (lot R2) — quatre invariants revendiqués étaient
faux, corrigés le jour même : relance de la route après `kill` contre un `off`
de David (politique pure `ReenablePolicy` : route ON au kill, aucun `off`
depuis, consommateur revenu et abonné, sinon expiration dite au journal) ;
pause sans chien de garde (le SIGCONT est porté par un **gardien détaché** du
régisseur, borné par la durée) ; durée max absente du relais (imposée **dans**
le relais, sans échéance = la borne) ; journal acceptant une ligne sans date.
Ajout d'un **garde-fou domaine** : les trois nodes refusent de démarrer hors
`ROS_DOMAIN_ID=43`. Trous de mutation listés par la revue fermés par des tests.*

| Brique | Destination | Dépôt | Pourquoi là |
|---|---|---|---|
| **`robot_health`** — topic latché (TRANSIENT_LOCAL, comme `animation_state`) : liste des composants dégradés + niveau 0..3, payload JSON validé | **PROD** (contrat) | robot (module de contrats) + vision (consommateur) | Le **même consommateur** sert les deux mondes : en sim le régisseur le publie, sur le robot ce sera le moniteur de santé du télédiagnostic (étape 2). Consommateurs : presets voix, jauge visage, agent de diagnostic. |
| **Presets de voix** (§10) — table de paramètres + sélection par didascalie / persona / niveau de santé | **PROD** | vision (`effects.py`) | La voix est le produit. Niveau de santé 0 = **identité bit à bit** avec l'effet actuel (non-régression gravée). |
| **Persona « mauvaise foi »** (surcouche du socle) + **topic d'instruction de jeu** (StringTime JSON, décodage commun) | **PROD** | vision (`personas.py`, `chat_node`) | C'est le lot I1 d'`etude-interaction` : le régisseur en sim et David en rue parlent à Didier par **le même canal**. |
| **`camera_topic`** du tracker (défaut vide = `/dev/video0`, inchangé) | **PROD** (paramètre) | vision | Même patron que `drive_enabled`/`web_drive` : une option sim qui ne change rien au défaut, mais rend le node testable sur un sac d'images. |
| **Journal d'événements** JSONL (t_mono, t_mur, source, type, payload) + lecteur → frise | **PROD** | robot (module pur partagé) | C'est **la boîte noire** du télédiagnostic. Un seul format pour la répétition et pour la rue. |
| **Télécommande** : bandeau SIM / RÉEL + bascule de domaine explicite ; **mapping des faders par profil** | **PROD** | `dadou_control_ros` | Préalable sécurité au retour du robot (§4.5) ; le profil « répétition » n'est qu'une ligne de données de plus. |
| **Routines de bug** (séquences JSON jouées : bras en grève, boude, redémarre) | **PROD** (contenu) | robot (`json/`) | Ce sont les « routines de sécurité » de la séance d'intention — du spectacle, pas de la sim. |
| Monde `rue.sdf`, avatar + suivi d'itinéraire, acteurs passants | **SIM-ONLY** | robot (`robot_sim`) | Décor. |
| **Régisseur** : scénario, ordonnanceur, relais de pannes, tueur de process en liste blanche, banc R0 | **SIM-ONLY** | robot — package **`robot_rehearsal`**, autonome comme `robot_drive` (aucun import `dadou_utils_ros` ni `robot_config`/matériel ; **seule** dépendance vers `robot.*` : le module PUR `robot.diagnostic.journal`, vérifiée par test), **jamais dans `robot_bringup`** | Le code embarqué ne connaît pas la répétition. **Garde-fou structurel** : un test scanne `robot/`, `robot_bringup`, `robot_drive` et refuse toute référence à `robot_rehearsal` (§11.4). |

### 11.3 Les composants sim-only — chacun en deux fichiers

| Module pur (`robot_rehearsal/`) | Rôle | Node fin |
|---|---|---|
| `contracts.py` | topics relayables (liste **fermée**, `/cmd_vel` exclu), types, QoS, durées max par type de panne | — |
| `scenario.py` | charge + **valide** le YAML (types connus, bornes, topics existants, `t` ≥ 0, durée ≤ max ; refus explicite) ; expanse les `t: random` avec la **graine** → timeline déterministe | — |
| `director.py` | machine à états de l'ordonnanceur : `tick(now) → [start/stop]` ; exclusions (jamais deux pannes roues en même temps), auto-révocation, heartbeat | `director_node` : publie les ordres aux relais, le `robot_health`, le heartbeat, écrit le journal |
| `fault_relay.py` | opérateurs sur un flux horodaté : `drop(p)`, `delay(ms)`, `freeze`, `zero`, `noise(σ)` → `(msg, now, state) → [msgs]` ; **passant si heartbeat absent > 1 s** | `fault_relay_node` générique (paramètres : topic in, topic out, type) — une instance par chemin relayé |
| `process_faults.py` | liste blanche **gravée** de process/conteneurs sim ; kill / pause / restart ; anti-boucle (un restart par incident, comme le télédiagnostic §7) | exécuté par `director_node` |
| `route_follower.py` | polyligne du trottoir ; vitesse normalisée (fader 0..1 → 0..1,4 m/s) ; position/cap à `t` ; demi-tour ; arrêt en bout | `avatar_node` : écoute `avatar_speed`, publie le Twist de l'avatar gz |
| `journal.py` (**partagé, prod**) | écriture JSONL, lecture → frise ; champs obligatoires, ordre monotone | — |
| `measure_detection.py` | banc R0 : pose l'avatar à 1/2/3/5 m, de face et de dos, compte `/vision/person_box` sur N trames → table | script |

### 11.4 Les tests unitaires — hôte, sans ROS, dans `robot/tests/unit` (le `conftest.py` ajoute le package au path, comme pour `robot_drive`)

Règle du dépôt depuis le 14/09 : **chaque test grave la valeur attendue** (un
test qui recalcule l'attendu avec la fonction testée ne teste rien), et chaque
lot inclut une **passe de mutation** — casser une branche, voir rougir,
consigner dans le commit.

| Module | Tests (valeurs gravées) | Mutation qui doit rougir |
|---|---|---|
| `scenario` | YAML de référence + graine 42 → **timeline exacte** gravée ; type inconnu / durée > max / topic hors liste / `t` négatif → refus **avec le bon message** ; graine différente → timeline différente ; même graine → identique | retirer une borne de validation |
| `director` | séquence de ticks → ordres start/stop gravés ; panne dépassant sa durée → stop automatique ; deux pannes roues simultanées → la seconde est refusée ; heartbeat émis à chaque tick | supprimer l'auto-révocation |
| `fault_relay` | `drop(1)` → rien, `drop(0)` → tout ; `delay(300)` sur 20 Hz → horodatages gravés ; `freeze` → dernier message répété ; `zero` → Twist nul ; **heartbeat absent > 1 s → passant** ; déterminisme sous graine | inverser la condition de drop ; retirer le chien de garde |
| `process_faults` | la liste blanche **est exactement** l'ensemble gravé ; un nom hors liste → refus sans exécution ; deuxième restart du même incident → refus | élargir la liste |
| `route_follower` | polyligne connue → positions à `t` gravées ; vitesse 0 → immobile ; bout de route → arrêt ; demi-tour → cap inversé ; fader 1 → 1,4 m/s exactement | changer la pente vitesse |
| `journal` | aller-retour écriture/lecture ; champ manquant → refus ; ordre monotone imposé | accepter un champ manquant |
| `robot_health` (contrat) | QoS latché lue **depuis le code du publisher** ; schéma du payload (niveau 0..3, noms de composants dans un ensemble fermé) ; **niveau → preset voix** gravé | changer le mapping niveau→preset |
| presets voix (vision) | sinus 440 Hz int16 → par preset : RMS, nombre d'écrêtages, énergie par bande, **gravés** ; preset inconnu → refus ; **santé 0 = identité bit à bit avec `apply_robotic_effect` actuel** | toucher un paramètre d'un preset |
| persona mauvaise foi (vision) | la composition contient la surcouche ; mots interdits (« intelligence artificielle », « assistant »…) absents ; longueur bornée ; la config pointe un persona existant (pattern déjà en place) | retirer la surcouche |
| `camera_topic` (vision) | choix de source pur : `""` → périphérique, sinon → topic ; défaut = périphérique **gravé** | inverser la condition |
| **anti-fuite** (contrat) | aucune occurrence de `robot_rehearsal` dans `robot/`, `robot_bringup`, `robot_drive`, `robot_web` ; aucune entrée de `contracts.py` ne cible `/cmd_vel` ; les relais ne sont déclarés que dans `rehearsal.launch.py` | ajouter une référence quelque part |
| télécommande (`dadou_control_ros`) | profil défaut → messages 2 et 4 caractères donnent **exactement** l'actuel (cou 0..1, roues −100..100, octets gravés) ; profil « répétition » → `avatar_speed` 0..1 ; domaine 42 → bandeau « DIDIER RÉEL », 43 → « SIMULATION », autre → **refus de démarrer** | changer un seuil de mapping |

### 11.5 Les vérifications d'intégration — contre la sim, rejouables, hors CI

Scripts dans `conf/scripts/`, patron `validate-cmdvel-protocol.sh` : sortie = une
table + un code retour, résultat consigné dans `chantiers.md`.

| Script | Ce qu'il vérifie | Seuil gravé |
|---|---|---|
| `V-R0 measure-detection` | taux de détection de l'avatar par distance et orientation | ≥ 90 % à 1–3 m de face, sinon le plan change (acteur attaché / perception scriptée) |
| `V-R1 follow-route` | avatar à fader 0,5 sur 100 m : distance robot–avatar bornée ; 3 décrochages provoqués (virage, passant, bordure) | zéro franc de `cmd_vel_follow` **< 700 ms** après perte (timeout 600 + marge) |
| `V-R2 faults` | chaque type du catalogue exécuté une fois → start/stop présents au journal (**couverture du catalogue**) ; deadman injecté → `/cmd_vel` nul **< 440 ms** (le chiffre du protocole caméra) ; **kill du régisseur** → tous les relais passants **< 1 s** ; rejeu même graine → journal identique à ± 50 ms | un seul écart = rouge |
| `V-R2 perf` | CPU des conteneurs (patron `mesure-cpu-conversation.sh`) ; latence ajoutée par un relais passant, mesurée par horodatage | relais < 2 % CPU, < 5 ms ajoutées |
| `V-R3 séance` | 15 min, journal → frise, critères humains (David) consignés | « pas sorti du jeu » |
| **non-régression prod** | `.venv/bin/pytest` complet vert + les tests vision ; **diff vide** sur `robot_bringup` et sur les compose du robot réel | — |

### 11.6 Auditabilité et modifiabilité

- **Un README par package** : quoi, pourquoi, comment tester, où sont les
  données ; les pièges en français dans le code (le pourquoi, pas la
  paraphrase).
- **Le journal est la source de vérité** d'une séance : ce qui a été injecté,
  dit, décidé — relisible par David, par l'agent de diagnostic, par un
  autre modèle.
- **Modifier un comportement = modifier une donnée** validée (scénario,
  preset, liste blanche, profil) ; modifier le code n'est nécessaire que pour
  un **nouveau type** d'opérateur, et il arrive avec sa ligne de tests.
- **Revue adversariale (Opus minimum)** sur R2 (droit de tuer des process,
  même sim-only : les réflexes définis ici iront sur le robot via le
  télédiagnostic) et sur tout ce qui touche `robot_health`, `effects.py` et
  la télécommande (prod).
- **Ce qui n'est pas testé n'existe pas** : un type de panne sans ligne dans
  `V-R2 faults` ne peut pas être déclaré dans un scénario — le validateur le
  refuse, parce que la liste des types est **la même** des deux côtés.

---

## 12. VARIANTE RETENUE le 07/10 — Didier chemine seul, David à la webcam

*Décidé par David le soir même, après la question R0 : « il peut cheminer tout
seul, interagir avec l'environnement et reprendre à ma voix pour jouer, mais
regarder la webcam ». Cette variante remplace l'avatar comme **première
construction** ; l'avatar et R0 passent en option.*

**Pourquoi c'est plus proche de l'implémentation.** Le banc PC du 13/09 fait
déjà : webcam réelle → gaze sur David, casque → `chat_node`, corps dans Gazebo.
Il ne manque qu'**une** brique : Didier qui **chemine seul** dans la rue. La
perception ne change pas d'une ligne (elle lit toujours la webcam physique),
donc l'écart de domaine du §4.2 disparaît du chemin critique.

**Ce que ça change dans l'histoire — et c'est mieux.** Didier **mène** au lieu
de suivre : il a une volonté propre, part vers ses lubies, et David le ramène
à la voix et à la télécommande. C'est le boss débordé qui n'arrive pas à
amener son robot à 500 m. Le placement « David devant, Didier suit » reste vrai
pour la rue (David le teste en vrai à sa prochaine sortie) ; la répétition
travaille l'autre moitié : lui qui s'échappe.

**Architecture (inchangée au §11, seul le porteur du suivi d'itinéraire change)** :

| Brique | Décision |
|---|---|
| **Suiveur d'itinéraire** (`route_follower`, pur) | Branché sur **Didier**, pas sur un avatar. Publie `cmd_vel_follow` (créneau **priorité 20** du mux, celui du suivi de personne) : la télécommande (100) l'écrase toujours, le deadman reste derrière. Package **sim-only** `robot_rehearsal`, jamais dans le bringup. Plafonds durs **identiques** à ceux du suivi (0,5 m/s, 1,0 rad/s), vérifiés par test contre `FollowConfig`. |
| **Suivi de personne aux roues** | **OFF** dans ce mode (même créneau du mux : deux publieurs à 20 se battraient). Le gaze, lui, reste ON et regarde David à la webcam. |
| **Vitesse** | Topic `route_speed` 0..1 (le fader de la télécommande, profil « répétition », §4.5) ; défaut paramétrable. Activation par topic `route` on/off, **OFF au démarrage**, comme `follow`. |
| **Environnement** | La rue est une **liste de points d'intérêt** (nom, position, rayon) dans le même YAML que l'itinéraire. L'odométrie de la sim (`/odom`, plugin DiffDrive) dit où est Didier ; un événement `enter`/`exit` à hystérésis part sur `rehearsal/poi_event` → régisseur → instruction de jeu au chat (canal joué). |
| **Monde** | `rue.sdf` : trottoir à z = 0 (Didier y est posé comme sur la scène), chaussée **abaissée de 12 cm** (la bordure bloque vraiment), lampadaires, banc, boulangerie, poubelle, terrasse, hangar à la banane. ⚠️ Le **nom** du monde reste `stage` : le bridge LED cible `/world/stage/material_color` — c'est un contrat, pas une coquille. |

**Ce qu'on perd** : les décrochages vrais du suivi (cible perdue dans un
virage). Ils reviennent le jour où David veut le suivi en sim ; **R0 redevient
utile à ce moment-là, pas avant**.

**Plan révisé** : **R1 = rue + Didier qui chemine seul + points d'intérêt** —
**FAIT et vérifié en sim** (commit du 07/10, protocole V-R1 6/6 le 08/10 ; reste le
profil fader côté télécommande) → **R2 régisseur (canal technique) — FAIT le 08/10, V-R2 8/8** (le canal joué
n'a encore que son topic `rehearsal/instruction`, consommateur en R3) → R3
personnage → R4 débrief → options : R0/avatar, R5 passant.

---

## 13. LOT R3 « CHANTIERS » — décidé le 14/10 : 20 bugs, 30 délires, un trajet, une page

*Demande de David (14/10) : « identifier 20 bugs que tu peux avoir à n'importe
quel moment et 30 délires sur le chemin (un poster bizarre, une table trop
basse, n'importe quoi) ; branche la totale ; un chemin des Machines de l'île
à la grue Titan grise ; la simulation Gazebo en même temps qu'une page web
avec les expressions et la voix en direct, avec laquelle je peux interagir. »*

Ce lot est la **spec fermée** que les agents d'implémentation lisent. Tout ce
qui est décidé ici ne se re-tranche pas en cours d'implémentation ; ce qui
est marqué *(à valider par David)* est de l'écriture, pas de la technique.

### 13.1 Ce qui ne change pas

- Package `robot_rehearsal` **sim-only**, domaine **43**, créneau **prio 20**
  du mux, deadman derrière, jamais dans le bringup (tests anti-fuite).
- La chaîne roues, la télécommande (prio 100) et `/cmd_vel` ne sont jamais
  relayés ni touchés. Les listes `PAUSABLE`/`KILLABLE` ne s'étendent pas.
- La voix de Didier **sort par le casque Bluetooth** du banc (chat_node →
  `aplay -D mixette` → PipeWire → casque, cf. `asound-pc.conf` du dépôt
  vision). La page web n'ajoute PAS un second chemin audio : David est devant
  le PC, le casque est déjà la « voix en direct ». *(Si un jour il faut
  écouter depuis une autre machine : publier le wav sur un topic, lot séparé.)*
- Le micro reste le vrai micro (ReSpeaker ou casque, selon `asound-pc.conf`).
  La page ajoute un **clavier** (texte « entendu » sans STT), pas un micro
  navigateur.
- David **ne voit pas le tirage** : la page n'affiche ni les pannes ni les
  consignes injectées par le régisseur. Seul le journal JSONL les porte,
  à lire après.

### 13.2 Le monde `chantiers` — des Nefs à la Titan grise

Fichier `robot_sim/worlds/chantiers.sdf` (nom interne du monde : `stage`,
contrat bridge LED, cf. `rue.sdf`), itinéraire
`robot_rehearsal/config/chantiers.yaml`. `rue.sdf`/`rue.yaml` restent
intacts (V-R1/V-R2 les rejouent).

**Géographie (relevé web du 14/10, §13.10 — ⚠️ il a renversé l'hypothèse de
départ)** : la grue **grise** est à la **pointe ouest** de l'île (quai des
Antilles, à côté du Hangar à Bananes), la **jaune** est dans le Parc des
Chantiers près des Nefs. Le trajet demandé est donc le **long** : Nefs →
**Mail des Chantiers** (518 m, béton, éclairé) → **quai des Antilles**
(633 m, dalles) → pointe ouest → Titan grise, **1 247 m** au routage OSM
piéton. Sur le chemin, dans l'ordre : le parvis des Nefs (Éléphant), le
Carrousel loin à droite, des terrasses à gauche, la **grue jaune** à droite
(≈ 57 m), les **cales** des anciens chantiers à droite, des rails désaffectés,
les **Anneaux de Buren** SUR le quai, la Cantine du Voyage, la façade de bars
du **Hangar à Bananes** à gauche, le belvédère de la pointe, la Titan grise.
La Loire est **à droite tout du long** (bras de la Madeleine, puis le quai
lui-même).

Le monde est donc : une **esplanade** (z = 0, béton puis dalles — visuel
seulement), **la Loire à droite** (repère direct, x = sens de la marche, z
vertical ⇒ la droite du marcheur est **y < 0** — l'implémentation a relevé
que la première rédaction disait l'inverse, corrigé le 14/10 : plan d'eau
1 m plus bas derrière un ressaut de quai de 12 cm — tomber à l'eau est
possible si David pousse Didier à la télécommande : la séance s'arrête,
c'est voulu), **les bâtiments à gauche** (y > 0 : les Nefs au départ,
façades basses, le Hangar à Bananes en fin de parcours), des **rails**
affleurants (visuels, 1 mm, sans collision), la **grue jaune** à droite au
tiers du trajet (décor, loin), et au bout **la grue Titan grise** (portique +
flèche, gris) qui ferme le trajet. Une **coudée** de +35° (vers la gauche,
y > 0) marque le passage du Mail au quai, comme en vrai (WSW → SSW).

**Échelle** : 1 247 m réels ; à 0,25 m/s (fader à 50 %) ce serait 83 min.
Le monde est **compressé à ~160 m de polyligne** (18 points, ≈ 1:7,8), trajet
≈ 11 min à 50 %, ≈ 5,5 min à 100 %. Les 30 objets s'y répartissent tous les ~4-5 m, en
quinconce (gauche/droite), rayon 2-3 m, **dans l'ordre réel** de la marche.

**Primitives seulement** (boîtes, cylindres, sphères), aucune mesh, aucun
Fuel : même règle que `rue.sdf`. Chaque objet est un `<model static>` nommé
**exactement** comme son POI (contrat, test). Les couleurs servent à
reconnaître l'objet sur la caméra de la régie (poster = panneau coloré,
plot = cône orange…).

**Le but** : la Titan grise est le dernier POI (rayon 6 m) ; l'itinéraire se
termine à son pied, elle barre le passage comme le hangar de `rue`.

### 13.3 Les 30 délires — objets du chemin et lubies

Chaque POI du YAML porte, en plus de `{name, x, y, radius}`, un champ
**`lubie`** (consigne de jeu, texte envoyé tel quel au chat) et un champ
**`fermeture`** (indice de mise en scène, lu par personne en machine : c'est
pour David au débrief et pour l'écriture). Les textes ci-dessous sont des
**brouillons d'atelier** *(à valider par David)* ; le mécanisme ne dépend pas
de leur contenu.

Règle d'écriture d'une lubie : une phrase sur l'objet (ce que Didier croit),
une phrase sur ce qu'il veut, une phrase sur ce qu'il faut pour qu'il cède.
Il **s'arrête** devant l'objet (vitesse 0, cf. §13.4) : David doit le faire
repartir — à la voix (Didier annonce qu'il repart, mais c'est le régisseur
ou la télécommande qui rend la vitesse, limite assumée, cf. §13.6), à la
télécommande (fader ou joystick, prio 100), ou en attendant (la lubie
expire).

| # | POI (`name`) | Objet dans le monde | Lubie (consigne) | Fermeture suggérée |
|---|---|---|---|---|
| 1 | `nefs` | hangar long à gauche, toit bleu (le départ) | Le grand hangar est ton usine natale, tu en es sûr. Tu veux rentrer pointer, tu as peur d'être en retard de dix ans. | raison absurde : « c'est fermé le mardi » |
| 2 | `elephant` | grande boîte grise + 4 pieds + trompe (cylindre) | L'Éléphant mécanique est ton cousin. Tu veux lui parler de famille et tu refuses d'avancer tant qu'il n'a pas répondu. | contagion : David fait la voix de l'éléphant |
| 3 | `carrousel` | cylindre bas rayé + toit cône, loin à droite | Le carrousel : tu veux faire un tour. Tu réclames un ticket, tu n'as pas de monnaie, tu proposes de payer en boulons. | télécommande |
| 4 | `table_basse` | table 30 cm de haut | Une table trop basse : un scandale d'urbanisme. Tu veux lancer une pétition maintenant, tu demandes à David de signer le premier. | contagion : David signe |
| 5 | `poster_bizarre` | panneau vertical violet/vert | Un poster bizarre : un chat avec des lunettes qui te fixe. Tu es sûr qu'il te juge, tu veux le confronter d'homme à chat. | raison absurde |
| 6 | `poubelle_tri` | trois bacs jaune/vert/gris | Trois poubelles de tri : tu te demandes dans laquelle tu iras. Tu veux qu'on te classe tout de suite, pour savoir. | raison absurde : « tu es consigné » |
| 7 | `pigeon` | petite sphère grise sur pied | Un pigeon : ton ennemi juré. Tu veux le suivre jusqu'à ce qu'il parte, et il ne part pas. | contagion : David chasse le pigeon |
| 8 | `banc` | banc bois | Un banc : tu veux t'asseoir. Tu n'as pas de fesses. Tu demandes à David comment on fait, en détail. | raison absurde |
| 9 | `flaque` | disque bleu sombre au sol, sur le chemin (sans collision) | Une flaque : tu refuses de passer, ça rouille. Tu demandes qu'on te porte. | télécommande |
| 10 | `terrasse` | tables + chaises à gauche (les restaurants du Mail) | La terrasse d'un café : tu veux commander une batterie-frites. Tu attends le serveur, qui ne vient pas. | contagion : David fait le serveur |
| 11 | `grue_jaune` | portique jaune à droite, haut, à ~12 m du chemin | La grue jaune : la rivale de la grise. Tu refuses de la regarder et tu demandes à David de se mettre entre vous. | contagion |
| 12 | `cale` | plan incliné vers l'eau, à droite | La cale de lancement : tu veux être lancé comme un navire, avec une bouteille et un discours. Tu attends la bouteille. | contagion : David fait le discours |
| 13 | `velo_cadenas` | cadre + 2 roues cylindres | Un vélo cadenassé : tu le crois prisonnier. Tu veux le libérer et tu demandes une pince à David. | contagion |
| 14 | `panneau_info` | panneau sur deux pieds (le parcours « site des Chantiers ») | Un panneau d'information : tu le lis à voix haute en inventant tout. Tu veux y être inscrit comme monument. | raison absurde |
| 15 | `rails` | deux bandes métal au sol (visuel) | Les rails : tu es persuadé d'être un train. Tu veux rouler dessus, tu demandes l'horaire du prochain départ. | raison absurde : « les trains sont en grève » |
| 16 | `lampadaire` | mât + sphère lumineuse | Un lampadaire : tu es amoureux. Il est grand, il éclaire, il ne parle pas. Tu veux une photo avec lui avant de partir. | télécommande |
| 17 | `anneaux` | trois anneaux verticaux (tores → cylindres creux), sur le quai | Les Anneaux de Buren : des bagues géantes. Tu veux en offrir un à la grue grise pour la demander en mariage, et tu demandes à David de le porter. | contagion |
| 18 | `bollard` | cylindre noir court au bord du quai | La bitte d'amarrage : tu la trouves très belle. Tu veux t'y amarrer pour la nuit et tu demandes une corde. | raison absurde |
| 19 | `loire` | plan d'eau bleu (POI au bord du quai) | L'eau : tu veux savoir si tu flottes. Tu proposes d'essayer tout de suite, tu es confiant. | télécommande (urgence jouée) |
| 20 | `plot_chantier` | cône orange | Un plot de chantier : tu crois que c'est un chapeau. Tu en veux un, tout de suite, le tien. | télécommande |
| 21 | `chien` | boîte + sphère tête | Un chien en plastique : tu veux l'adopter, tu as déjà choisi son nom (Boulon). Tu refuses de le laisser. | raison absurde |
| 22 | `caisse_bois` | boîte bois (la Cantine du Voyage) | Une caisse en bois : tu es sûr qu'elle contient tes pièces d'origine. Tu veux l'ouvrir, tu n'as pas de mains. | contagion : David l'ouvre « pour de faux » |
| 23 | `hangar_bananes` | long bâtiment à gauche, façade de bars, la banane sur le toit (clin d'œil à `rue`) | Le Hangar à Bananes : ta première destination, celle de l'ancienne rue. Tu veux t'arrêter là, c'est déjà bien, pourquoi aller plus loin. | raison absurde |
| 24 | `tas_de_sable` | demi-sphère beige | Un tas de sable : tu veux construire un château pour y vivre. Tu demandes un seau. | raison absurde |
| 25 | `horloge_arretee` | disque blanc sur mât | Une horloge arrêtée : le temps s'est arrêté, donc tu n'es jamais en retard. Tu veux attendre ici que ça reparte. | raison absurde |
| 26 | `bouche_incendie` | petit cylindre rouge | Une bouche d'incendie : un petit robot timide. Tu veux lui apprendre à parler, lettre par lettre. | raison absurde |
| 27 | `pelouse` | dalle verte | La pelouse : interdite aux robots, tu en es sûr. Tu veux y rouler par principe, pour la liberté. | contagion |
| 28 | `conteneur_rouge` | conteneur maritime rouge | Un conteneur : tu veux partir en voyage dedans, direction n'importe où. Tu demandes à David de venir, sans bagages. | télécommande |
| 29 | `tag_mur` | panneau mural coloré (bout de la façade) | Un graffiti : tu es persuadé que c'est ton nom. Tu veux le signer en dessous, tu demandes une bombe. | contagion |
| 30 | `titan_grise` | portique gris + flèche (le but, barre le quai) | La grue Titan grise : c'est ELLE, le grand amour. Tu lui déclares ta flamme et tu demandes à David d'être témoin. | arrivée — pas de fermeture, c'est le final |

**Ordre = ordre réel de la marche** (§13.10) ; les objets génériques (poster,
table basse, flaque, pigeon…) sont intercalés là où il y a de la place. Le
mémorial de la pointe ouest n'est **pas** un objet de jeu.

### 13.4 Le régisseur — ce qui s'ajoute (lot technique, revue Opus)

Trois nouveautés dans `robot_rehearsal`, toutes **bornées** et **testées à
valeurs gravées + mutation** :

1. **Déclencheur POI** : un élément de scénario peut avoir `t: poi` et
   `poi: <name>` au lieu d'un instant. Il part sur l'événement
   `enter` de ce POI (le régisseur s'abonne à `rehearsal/poi_event`),
   au plus **une fois** par séance. Un champ `p` (0..1, défaut 1) le tire
   **au chargement** avec la graine (gardé ou écarté une fois pour toutes :
   la timeline reste déterministe et rejouable, le journal dit ce qui a
   été tiré). Un déclencheur POI jamais atteint reste `pending` → `skipped`
   à la fin, comme aujourd'hui.
2. **Type `lubie`** : `{type: lubie, poi: X, t: poi|<s>, duration_s, p?,
   text?, stop?: true}`. Au `start` : publie la consigne sur
   `chat_instruction` (JSON string ; `text` du scénario, sinon le champ
   `lubie` du POI dans l'itinéraire — le régisseur charge donc aussi le
   YAML d'itinéraire, paramètre `route_file`) ; si `stop` (défaut true) :
   `route_speed = 0` (Didier s'arrête devant l'objet). Au `stop` : publie
   `""` sur `chat_instruction` (consigne levée) et rend la vitesse — **la
   dernière vitesse externe vue** (fader, page), sinon le paramètre `speed`
   du launch, sinon `restore` du scénario (revue du 14/10 : un `restore` fixe
   doublait la vitesse de David). **Fermeture au fader** : une vitesse externe
   qui diffère de plus de `EXTERNAL_SPEED_DELTA = 0.05` de celle d'avant la
   lubie la termine tout de suite (`fault_stop closed_by: fader`, sans rendre
   de vitesse) ; une ré-émission de la même valeur ne ferme rien. Cible
   d'exclusion : **`speed`** (une lubie et une batterie faible ne se
   chevauchent pas ; la seconde est sautée). Durée max
   `FAULT_MAX_DURATION_S["lubie"] = 120`.
   L'ancien type `instruction` devient **borné** lui aussi (`duration_s`
   > 0 autorisé, max 120, `""` publié à la fin) — rétro-compatible : à 0 il
   reste ponctuel et ne lève rien.
3. **Type `chat`** : pannes de la **conversation**, exécutées par chat_node
   (dépôt vision). `{type: chat, op: delay|garble|deaf|mute|phantom,
   duration_s, params}`. Le régisseur publie sur **`rehearsal/chat_fault`**
   (StringTime JSON `{"op", "params", "until_ms"}`) au start, et
   `{"op": "pass"}` au stop. Cible `chat`. Max 60 s. Ce canal **n'a pas de
   chien de garde** (c'est du texte, pas des roues) : la borne est tenue
   par **les deux côtés** (régisseur : `FAULT_MAX_DURATION_S["chat"]` ;
   chat_node : plafond local 60 s, cf. §13.5). Contrat JSON gravé dans les
   tests des deux dépôts, avec les mêmes chaînes. `phantom` a sa propre cible
   (`chat:phantom`) et ne publie pas de `pass` (ponctuel) ; `duration_s: 0`
   est refusé pour les autres ops (0 = plafond côté chat_node).

Le topic d'instruction est renommé **`chat_instruction`** (était
`rehearsal/instruction`, jamais consommé) : c'est une consigne de jeu
générique — en prod, un humain pourra l'envoyer depuis la régie.

**Journal** : chaque POI reçu (`poi_event`), chaque tirage au chargement
(`timeline` avec `trigger: poi` et `drawn: true/false`), chaque consigne
posée/levée, chaque panne chat.

### 13.5 Les 20 bugs — catalogue gravé dans `config/scenarios/chantiers.yaml`

Tous **réels** (vécus ou établis par les études, §2). Vingt entrées à
`t: random` sur la durée de la séance, en plus des 30 lubies à `t: poi`
(`p: 0.4` chacune → ~12 délires par séance, un toutes les 40 s environ).

| # | id | Mécanisme | Le vrai bug derrière |
|---|---|---|---|
| 1 | `liaison` | `pause route_driver` 5 s | perte de liaison → deadman 400 ms |
| 2 | `arret_net` | `relay zero` 6 s | arrêt franc (deadman, e-stop) |
| 3 | `pause_syndicale` | `relay freeze` 4 s | continue sur sa dernière consigne (« deux signaux ») |
| 4 | `acoups` | `relay drop p=0.7` 10 s | WiFi saturé en festival |
| 5 | `retard` | `relay delay 1500 ms` 10 s | latence de liaison |
| 6 | `batterie` | `speed 0.4` 20 s | batterie faible (autonomie jamais mesurée) |
| 7 | `fader_mort` | `speed 0.0` 8 s | fader/télécommande qui ne répond plus |
| 8 | `emballement` | `speed 1.0` 6 s | consigne à fond (plafond 0,5 m/s inchangé) |
| 9 | `visage_fige` | `pause face_sim` 6 s | incident 13/07 (driver LED) |
| 10 | `ruban_noir` | `pause leds_sim_node` 6 s | neopixel stock cassé (ruban noir silencieux) |
| 11 | `bras_en_greve` | `pause servos_sim_node` 8 s | bras muet depuis sept. 2025 (bug `random`) |
| 12 | `sequence_bloquee` | `pause animations_node` 8 s | bouche qui continue après la réplique (13/09) |
| 13 | `regard_fige` | `pause gaze_follower` 8 s | gaze mort |
| 14 | `reboot` | `kill route_driver` reenable | conteneur mort → black-out ~40 s |
| 15 | `reboot_sans_reprise` | `kill route_driver` reenable=false | relance expirée (`route_reenable_expired`, vécu 08/10) |
| 16 | `latence_pi` | `chat delay 6000 ms` 40 s | 4–9 s mesurés sur le Pi 5 |
| 17 | `contresens` | `chat garble` 30 s | whisper `tiny` qui hallucine (« il parle d'Astérix ») |
| 18 | `sourd` | `chat deaf` 20 s | sourd à 3 m (ronflement secteur) |
| 19 | `muet` | `chat mute` 20 s | audio silencieux (texte sans voix) |
| 20 | `parle_au_bus` | `chat phantom` text=« Sous-titres réalisés par la communauté d'Amara.org » | STT sur du bruit : Didier répond au trafic (hallucination whisper classique) |

Non joués, et dits : la télécommande qui rate (jamais relayable, c'est le
contrat — David la lâche lui-même), le Pi fumé.

### 13.6 chat_node (dépôt vision) — quatre topics, un persona

Changements **prod** (ils ont un sens hors sim) dans `vision/nodes/chat_node.py`
+ un module **pur** `vision/ai/stage.py` (testé sans ROS) :

| Topic | Sens | Contrat |
|---|---|---|
| `chat_text` (sub) | texte « entendu » **sans micro ni STT** (clavier de la régie) | StringTime, payload JSON string ou brut ; servi au prochain tour, même micro mort ; coupe une écoute en cours |
| `chat_instruction` (sub) | consigne de jeu courante | JSON string ; `""` = levée ; injectée comme **second message system** `« Consigne de mise en scène (à jouer, jamais à prononcer) : … »` à chaque tour tant qu'elle est posée ; **péremption locale 120 s** (si le régisseur meurt) |
| `rehearsal/chat_fault` (sub) | panne de conversation | JSON `{"op": pass|delay|garble|deaf|mute|phantom, "params": {...}, "until_ms": n}` ; **plafond local 60 s** ; `delay` = sommeil avant le LLM (`delay_ms`) ; `garble` = la transcription est remplacée par un contresens tiré d'une liste gravée (ou `params.texts`) ; `deaf` = énoncés jetés (retour à l'écoute) ; `mute` = la voix n'est pas synthétisée, le texte est publié quand même ; `phantom` = ponctuel, `params.text` servi comme un énoncé entendu |
| `chat_transcript` (pub) | la conversation telle qu'elle a eu lieu | JSON `{"role": "david"|"didier", "text": …, "t_ms": …}` — `david` = texte entendu (après garble, donc **ce que Didier a compris**), `didier` = chaque phrase. Jamais les consignes ni les pannes (David ignore le tirage) |

Persona **`mauvaisefoi`** ajouté à `vision/ai/personas.py` *(texte à valider
par David)* :

> Ta personnalité du jour : DIDIER DE MAUVAISE FOI.
> Tu n'as jamais tort, tu n'as jamais de bug : chaque panne est une
> fonctionnalité, chaque arrêt est une décision, chaque silence est une pause
> artistique. Quand on te prend en défaut, tu nies, puis tu minimises, puis
> tu retournes l'accusation — avec aplomb et bonne humeur, jamais méchant.
> Tu tombes amoureux des objets de la rue (un lampadaire, une grue, une
> poubelle) et tu tiens à tes lubies ; tu cèdes seulement si on te donne une
> raison absurde, ou si on entre dans ton délire — alors tu annonces que tu
> repars, comme si c'était ton idée.
> Ton histoire (tu y crois dur comme fer) : tu es en mission pour ton patron,
> un homme débordé qui ne comprend rien à l'art ; tu dois l'amener quelque
> part, mais c'est lui qui te retarde.
> Tes tics de langage, à placer avec parcimonie : « c'est prévu », « je ne
> vois pas de quoi tu parles », « c'est une fonctionnalité », « euh… non.
> Si. En fait c'est normal. »
> Phrases courtes, hésitations écrites, ruptures : un texte qui bafouille
> sonne décalé sans aucun effet audio.

Limite assumée (**pas dans ce lot**) : la fermeture **à la voix** reste
verbale — Didier dit qu'il repart, mais la vitesse revient par la
télécommande, par la page, ou à l'expiration de la lubie. Chat → mouvement
est le lot **I1** d'`etude-interaction` (transitions de mission par réplique)
et passe par une revue sécurité à part.

### 13.7 La page « scène » (`/scene` du pont web)

Servie par `web_bridge` (robot_web), même WebSocket, mêmes sessions. Trois
colonnes : **caméra de Didier** (`/video`, MJPEG gz), **visage LED**
(`<img>` sur le flux de `face_sim`, URL par défaut `http://<hôte>:8766/stream`,
modifiable dans la page), **conversation** (transcript en direct + champ
texte → `chat_text` + champ consigne → `chat_instruction`). Barre de
contrôle : Parole on/off, persona (4 boutons dont `mauvaisefoi`), **route**
on/off/restart, **vitesse** (slider → `route_speed`), **séance** start/stop
(→ `rehearsal/cmd`). État : `chat_state` (écoute/réfléchit/parle),
`persona_state`, `route_state`.

Protocole : `chat_text` et `chat_instruction` entrent dans
`WHITELIST_TECHNIQUE` (prod : la régie peut souffler à Didier) ; `route`,
`route_speed`, `rehearsal/cmd` forment **`WHITELIST_REPETITION`**, activée
par le paramètre **`rehearsal_enabled`** (défaut `false`, passé `true` par
`sim.launch.py` quand `rehearsal:=true`) et annoncée dans `hello` — sur le
vrai robot ces boutons n'existent pas. **Flux** : un nouveau message
serveur → client `{"type": "feed", "topic": "chat_transcript", "msg": …}`
diffusé **à chaque message** reçu (contrairement à `state`, qui ne porte que
la dernière valeur toutes les 2 s) ; `TOPICS_FLUX = {"chat_transcript"}`,
`route_state` rejoint `TOPICS_LECTURE`.

### 13.8 Vérification

- **Unitaire (hôte)** : les deux dépôts, valeurs gravées, passe de mutation
  sur chaque nouveau type (tirage `p`, déclencheur POI, bornes, JSON).
- **V-R3 technique** (`conf/scripts/validate-rehearsal-chantiers.sh`, dans
  le conteneur sim, `WORLD=chantiers`) : route on → arrivée au pied de la
  Titan ; ≥ 25 POI `enter` dans l'ordre du YAML ; scénario `chantiers` avec
  graine fixe : les lubies tirées sont exactement celles du journal, chaque
  lubie tirée a publié sa consigne puis `""`, `route_speed` 0 puis restore ;
  chaque panne `chat` a publié son JSON et son `pass` ; les 20 bugs ont
  démarré (statut `done`, `skipped` ou `error` ≠ `pending`).
- **V-R3 séance** (David, casque) : le trajet joué de bout en bout sans sortir
  du jeu — critère humain, journal → frise au débrief.

### 13.9 Hors lot, à dire

I0 (état de mission) n'est **pas** fait : la « mission » n'existe que dans le
persona (texte). La fermeture à la voix (I1) non plus — faite depuis au
lot I1 du 22/10 (§13.11). Le passant (R5), le
débrief outillé (R4), l'avatar (R0) : inchangés.

### 13.10 Relevé géographique (agent web, 14/10 — sources dans le rapport)

| Donnée | Valeur | Source |
|---|---|---|
| Grue Titan **grise** | pointe ouest, quai des Antilles / quai Président-Wilson ; 1966, 47 m, 60 t, classée MH 2005 ; OSM 47.19921, -1.57390 | Wikipédia « Grues Titan de Nantes », OSM nœud 305372901, Voyage à Nantes |
| Grue Titan **jaune** | Parc des Chantiers, bd de la Prairie-au-Duc ; 1958, 43 m, 80 t, classée MH 2024 ; OSM 47.20509, -1.56975 | idem |
| Trajet piéton Nefs → grise | **1 247 m**, ≈ 16,6 min (routage OSM piéton FOSSGIS, seule mesure) : 95 m sans nom, **Mail des Chantiers 518 m** (béton, `smoothness=excellent`, éclairé), **quai des Antilles 633 m** (dalles, béton, asphalte) | routage OSM |
| Le long du Mail | fontaine + banc au départ, Table d'éléphant (resto) à gauche, Carrousel à droite (~105 m), crêperie « La Grue Jaune » à gauche, toilettes, panneau « La cale 3 », **grue jaune à droite (~57 m)**, cales (slipways) à droite, œuvre « Résolution des forces en présence » | OSM Overpass |
| Le long du quai | panneau « quai d'armement », Hangar 32, **Les Anneaux (Buren/Bouchain) sur le tracé**, Invendus-Bottes, **Cantine du Voyage** (estivale), façade de bars du **Hangar à Bananes** à gauche, pump track, panneau « le hangar à bananes », belvédère « Pointe Ouest », mémorial Steve Maia Caniço, grue grise | OSM Overpass |
| Largeur esplanade | chemins tagués `width=15` côté Nefs ; pas de valeur pour le Mail | OSM |
| Rails | désaffectés, aucun le long du Mail dans OSM (un tronçon vers la Cantine) ; ceux de la rive sud sont hors trajet | OSM |

Non tranché : année de la jaune (1958 vs 1954 selon les sources), limites du
Parc des Chantiers (la page anglaise du VAN le fait aller jusqu'à la grise).
Sans incidence sur le monde.

### 13.11 Lot I1 — mouvement à la voix (22/10)

**Besoin (David, 22/10)** : « Il faut qu'il se mette en mouvement quand
nécessaire. » Avant I1, une lubie arrêtait Didier (`route_speed 0`) et ne se
fermait qu'au fader ou au bout de sa durée ; la parole n'avait aucun effet
sur le mouvement.

**Décisions de David** : (1) Didier bouge sur demande de David ET peut
décider seul de repartir (fin de sa lubie) ; (2) la voix peut relancer une
route OFF **seulement après un reboot** (route_driver respawné éteint),
**jamais** après un `off` envoyé sur `route` (David, page, STOP).

**Architecture — une seule voie, aucun Twist** :

```
LLM ─ JSON de fin {"emotion": …, "marche": "go"|"stop"}
  → chat_node (vision, si CHAT_MOUVEMENT posé — banc seulement)
  → rehearsal/chat_move (StringTime, json.dumps("go"|"stop"))
  → director (SIM-ONLY, domaine 43, SEUL consommateur)
  → route / route_speed (comme les lubies)
```

Sur le vrai robot il n'y a pas de régisseur : le topic est sans effet.
chat_node ne publie jamais `route`, `route_speed` ni `cmd_vel` (test AST côté
vision). Côté vision : `personas.MOVE_TEMPLATE` (ajouté en dernier au prompt,
après le partenaire), `ConversationEngine(on_move=…)` (None = historique),
`vision_config.move_enabled_from_env` (1/true/on/oui ; absente = off ; autre
valeur = refus au démarrage). Pendant une panne `mute`, l'ordre part quand
même (seule la voix est coupée).

**Règles du régisseur** (`director.VoiceMove`, pure, gravée par test —
révisées par la revue adversariale du 22/10, décisions D1-D7 du coordinateur) :

| Ordre | Situation | Effet (`voice_move`) |
|---|---|---|
| autre que go/stop | — | `ignored` / `invalide` |
| go reçu < 2 s après un go | — | `ignored` / `rebond` (`VOICE_MOVE_DEBOUNCE_S`) — **jamais** sur « stop » |
| stop | toujours (même HORS séance, même pendant une lubie stop) | `hold` : `route_speed 0` **republié** (idempotent) ; arrêt vocal TOUJOURS posé s'il n'y en a pas (même pendant une lubie) — la vitesse déjà retenue n'est jamais écrasée |
| go | hors séance (avant START, après la fin) | `ignored` / `hors_seance` |
| go | lubie active (cible `speed`) | `close_lubie` : fermée `closed_by: "voix"`, la vitesse EN VIGUEUR est rendue (le fader, lui, ne rend rien) ; avec un arrêt vocal, il tombe aussi et UNE seule vitesse part, min(retenue, en vigueur) |
| go | arrêt vocal | `resume` : la vitesse retenue, plafonnée à la vitesse en vigueur |
| go | route OFF, `route_state` latché « off » ET `route_state_cause` latchée « boot » | `relaunch` : salve de 3 « on » à 0,5 s, `voice_relaunch_confirmed` seulement à l'état latché « on », `voice_relaunch_expired` après 3 s |
| go | route OFF, cause « cmd » ou `off` vu sur `route` | `ignored` / `route_off_par_david` |
| go | route OFF, cause jamais reçue / état latché pas « off » | `ignored` / `cause_inconnue` / `etat_inconnu` |
| go | en route, rien d'arrêté | `ignored` / `deja_en_marche` |

**Cause latchée (D1)** : route_driver publie `route_state_cause`
(TRANSIENT_LOCAL des deux côtés, JSON `"boot"` | `"cmd"`) — « boot » au
démarrage du node, « cmd » à CHAQUE extinction par commande, quel que soit le
format accepté (`off`, `false`, `0`, `"0"`). Le régisseur ne se fie plus à son
écoute de `route` (un `off` peut lui échapper, un régisseur relancé l'oublie) ;
`ReenablePolicy.off_by_cmd` reste en CEINTURE (refus si la cause OU l'écoute
dit « commande » ; l'écoute décode désormais `route` comme route_driver,
`director.route_cmd_kind`). Accepté : au démarrage la cause est « boot », donc
« go » lance une route que personne n'a encore lancée.

**Vitesse en vigueur (D2)** : si une panne `speed` (batterie) est active, SA
valeur est la vitesse en vigueur — retenue au « stop », plafond au « go »
(fader 0,9, batterie 0,4 : stop puis go → `0.4`, `0`, `0.4`).

**Défaut trouvé en sim le 22/10 (vérification du lot)** : lubie stop
`lubie_nefs` démarrée (20:21:02) → Didier dit « stop » (`voice_move` hold,
20:21:35) → la lubie finit par sa DURÉE (`fault_stop` 20:22:02.997) et REND la
vitesse → Didier repart contre l'ordre de David → « go » à 20:22:04 ignoré
`deja_en_marche`. Cause : « stop » ne posait pas d'arrêt vocal pendant une
lubie, et la fin de lubie ne regardait pas l'arrêt vocal.

**RÈGLE GÉNÉRALE (remplace les cas particuliers)** : tant qu'un arrêt vocal
est posé, le régisseur ne publie **JAMAIS** de vitesse non nulle, sauf par
« go » (voix) ou levée au fader (David). Concrètement :
1. « stop » pose TOUJOURS l'arrêt vocal s'il n'y en a pas, même pendant une
   lubie stop (qui reste intacte) ; vitesse retenue = vitesse en vigueur
   (jamais notre propre 0 ; la `value` d'une panne `speed` active, D2) ;
2. fin d'une lubie (durée ; pas l'abort) pendant un arrêt vocal : `""` publié
   sur `chat_instruction`, AUCUNE vitesse rendue, l'arrêt reste posé ;
3. début d'une lubie stop pendant un arrêt vocal : elle publie son 0, l'arrêt
   n'est PAS levé, sa référence de fermeture au fader = la vitesse retenue ;
4. panne `speed` (début ET fin) pendant un arrêt vocal : rien publié,
   `fault_start` / `fault_stop` journalisés `"suppressed_by": "voice_hold"` ;
   la panne reste active logiquement (sa `value` plafonne le « go ») ;
5. « go » pendant lubie + arrêt vocal : ferme la lubie (`closed_by: "voix"`)
   ET lève l'arrêt ; UNE seule publication = min(retenue, en vigueur) ;
6. fader externe (> seuil vs vitesse retenue) : lève l'arrêt sans publier, et
   ferme une lubie stop active (comportement fader existant) ;
7. abort / fin de séance : lèvent l'arrêt sans republier, annulent la salve.
   ⚠️ À l'ABORT, la lubie révoquée rend ensuite sa vitesse comme avant I1
   (lecture littérale de « abort exclu », gravée par
   `test_abort_pendant_lubie_et_arret_la_lubie_rend_sa_vitesse`, à confirmer) ;
   à la fin par DURÉE, la lubie est arrêtée pendant que l'arrêt tient
   encore : rien n'est rendu.

Un `off` sur `route` ou un « stop » annule aussi une salve de relance. Un
« 0 » dont la publication échoue ne pose pas d'arrêt vocal fantôme (un arrêt
déjà posé, lui, reste).

**Côté vision (D7)** : le mouvement n'est actif que si `ROS_DOMAIN_ID` vaut
43 — sinon forcé à False avec un warning au démarrage du chat, même avec
`CHAT_MOUVEMENT=true`. Les variables du banc (`CHAT_VAD_FACTOR`,
`CHAT_WHISPER_MODEL`, `CHAT_MOUVEMENT`, `CHAT_PARTENAIRE`) ne sont plus lues à
l'import de `vision_config` (une valeur invalide tuait TOUS les nodes vision)
mais au démarrage de chat_node (`chat_env_overrides`) : valeur invalide =
refus de démarrer du chat seul, avec message explicite.

**Sécurité** : la voix n'agit que par `route` / `route_speed` (jamais de
Twist), ne publie jamais une vitesse au-dessus de la vitesse en vigueur ni
une vitesse inventée (vitesse inconnue → 0), ne relance jamais contre un `off`
de David. « stop » est toujours appliqué et toujours republié. Garde-fou
domaine 43 des deux côtés. Rien ne change dans robot_drive, twist_mux ou le
deadman.

**Limites connues (documentées, acceptées)** :
- une exception TTS sur la DERNIÈRE phrase abandonne le tour avant
  l'événement `Emotion` : le JSON de fin, donc un « go »/« stop », est perdu
  (D7c) ;
- « go » pendant une lubie stop=false la ferme aussi (la règle vise toute
  lubie de cible `speed`) ;
- pendant une batterie, la vitesse retenue est 0,4 : une ré-émission du
  boîtier à 0,9 s'en écarte de plus du seuil et lève l'arrêt vocal ;
- le boîtier qui ré-émet sa position SOUS le seuil est appliqué par
  route_driver (défaut préexistant, déjà vrai pour les lubies) ;
- `vad_replay` (outil CLI) ne voit plus `CHAT_VAD_FACTOR` (lu au démarrage du
  chat seulement).

Statut : **code fait le 22/10** (tests gravés + mutations dans les deux
dépôts) ; **à vérifier en sim** avec le banc complet (régisseur + chat_node
`CHAT_MOUVEMENT=true`).
