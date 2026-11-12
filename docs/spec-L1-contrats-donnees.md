# Spec L1 — contrats + données (mono-dépôt `theatre-robot`)

*Écrite le 2026-11-02 après la fermeture de L0. Décisions de référence :
`legacy/dadou_robot_ros/docs/etude-architecture-globale.md` §5.3-5.4 (01/11) et
`etude-autonomie-improvisation.md` §8 (02/11). Méthode : sous-lots petits, chacun avec sa
porte de sortie vérifiée, la sim verte en fin de chaque sous-lot, David valide entre deux.*

## 0. Faits relevés le 02/11 (ce sur quoi la spec s'appuie)

| Fait | Mesure |
|---|---|
| `dadou_utils_ros/utils_static.py` | **94** constantes ; **74** importées par robot/télécommande/vision (comptage AST, imports multi-lignes compris — mon premier comptage ligne à ligne disait 58/32, il était FAUX) ; 20 non importées par eux, dont **17 servent à la lib elle-même** ; **3 vraiment mortes** (`JSON_NOTES`, `NOTE`, `FILES`) ; `IP` ne sert qu'aux modules `ws_server`/`ws_com`, eux-mêmes morts (L5) |
| Décodage StringTime (`json.loads((ros_)?msg.msg)`) | **12 fichiers** : robot `payload.py` (strict : None + log), `gaze_control`, `gaze_follower_node` (×2), `person_follower_node`, `route_driver_node`, `director.py`, `director_node.py` (×3), `fault_relay_node.py`, `web_bridge_node.py` (×2), `wheels_bridge_node` ⚠️ chemin roues, vision `reflection_contract` (None sans log), `chat_node.py`. ⚠️ La plupart sont **volontairement tolérants** (JSON invalide → chaîne brute, pour les `on`/`off` tapés à la main) : le codec commun doit offrir les DEUX variantes |
| `robot_interfaces` | **3 copies** (robot, vision, télécommande) ; 4 `.msg` (`StringTime`, `LedState`, `HardwareStatus`, `TurtleTuple`) ; seul le `CMakeLists.txt` de la télécommande diffère |
| Topics absolus | vision : `/vision/person`, `/vision/person_box`, `/vision/status` — rien d'absolu côté robot |
| Catalogue de commandes | `robot_web/web_catalog.py` (construit depuis les JSON, publié) vs `BUTTONS_LAYOUT` (télécommande, recopié à la main) |
| Édition des JSON | 8 modules de la télécommande écrivent localement ; le robot n'écrit que `animations_node` et le journal |

## 1. Ce que L1 supprime (règle du §0 de l'étude)

`utils_static.py` comme source du CONTRAT (shim pour topics/clés/organes, inchangé pour
chemins/logging/couleurs/réglages, qui restent à la lib jusqu'à L5) ; les 3 constantes
mortes ; 11 décodeurs StringTime sur 12 (le 12ᵉ, `wheels_bridge`, part avec le pont en L4) ; 2 copies de `robot_interfaces` sur 3 ; `BUTTONS_LAYOUT` comme vérité (il
reste un cache vérifié par test jusqu'à L4) ; les 71 JSON de la télécommande (sauvegardés
dans git, supprimés du disque et du déploiement) — précisé le 12/11 : 61 à L1d, les 10 que la
télécommande lit encore partent avec elle à L4, voir L1d décision 14).

## 2. Sous-lots

### L1a — `theatre_contrats` + `theatre_interfaces` (pur, testé, consommé par shim)

**Crée** `packages/theatre_contrats/` (ament_python, **aucune dépendance** hors stdlib —
importable sur le PC sans ROS) :

```
packages/theatre_contrats/
├── package.xml, setup.py, setup.cfg, resource/
├── theatre_contrats/
│   ├── __init__.py
│   ├── topics.py        # noms de topics (relatifs, jamais de « / » initial) — les constantes
│   │                    # de utils_static qui nomment un topic
│   ├── keys.py          # clés de payload (WHEELS, LEFT_ARM, NECK, FACE, DURATION, KEYS…)
│   ├── organs.py        # les 11 noms d'organes de Didier
│   ├── stringtime.py    # LE codec : encode(value, time_ms, anim) ; decode(msg) STRICT (invalide →
│   │                    # None + log erreur = payload.decode actuel) ; decode_or_raw(msg) TOLÉRANT
│   │                    # (invalide → chaîne brute, log DEBUG) — chaque site d'appel garde sa variante
│   └── qos.py           # les 2 profils : volatile(depth) / latched (TRANSIENT_LOCAL depth 1)
├── test/
│   ├── test_topics_relatifs.py   # AUCUNE constante de topics ne commence par « / » (gravé)
│   ├── test_stringtime.py        # valeurs attendues GRAVÉES (pas recalculées) ; mutation du
│   │                             # codec = rouge
│   ├── test_inventaire.py        # la liste des constantes REPRISES (topics, clés, organes) est
│   │                             # GRAVÉE : en ajouter/retirer une exige de toucher le test
│   └── (tools/inventaire.py)     # le script AST qui compte les imports — rejouable, c'est lui
│                                 # qui a trouvé l'erreur du premier comptage
└── README.md            # README-contrat : rôle, ce que chaque module expose, comment tester
```

**Déplace** `robot_interfaces` (copie du robot) dans `packages/robot_interfaces/` — pas de
renommage avant L1e ; les 2 autres copies supprimées, les 3 dépôts le montent depuis là. Le
bloc numpy du `CMakeLists.txt` de la télécommande (`find_package(Python3 … NumPy)`) est repris
en **facultatif** (sans `REQUIRED`, `include_directories` sous `if(Python3_NumPy_FOUND)`),
commenté avec son origine.

**Branche les consommateurs sans les réécrire** :
- `legacy/dadou_utils_ros/utils_static.py` → shim : `from theatre_contrats.topics import *`
  etc. + les constantes NON-contrat qui restent (couleurs, chemins, réglages) ; `JSON_NOTES`,
  `NOTE`, `FILES` **supprimées** ; un commentaire en tête dit que le fichier disparaît en L5.
- `robot/nodes/payload.py` → délègue à `theatre_contrats.stringtime.decode` ; les 10 autres
  sites (hors `wheels_bridge`) appellent `decode` ou `decode_or_raw` selon leur comportement
  actuel, prouvé par un test d'équivalence par site (mêmes entrées → mêmes sorties, cas
  invalide compris).
- vision : `reflection_contract` utilise le codec ; ses 3 topics absolus deviennent relatifs
  (`vision/person`…) — **et** le consommateur côté robot (`person_follower`, `gaze`) lit la
  même constante de `theatre_contrats.topics`.
- Montage/COPY de `packages/theatre_contrats` et `packages/robot_interfaces` dans les compose
  et Dockerfiles de **sim, robot ARM/x86, vision x86/ARM, télécommande** ; `conftest.py` des
  trois dépôts ajoutent `packages/` au `sys.path`.

**Interdits L1a** : toucher `wheels_bridge_node.py`, `twist_mux.yaml`, `twist_deadman`,
`wheels_node` (chemin roues) ; changer un nom de topic autre que les 3 de vision ; changer
le comportement d'un décodeur (le test d'équivalence le prouve).

**Porte de sortie** : pytest vert dans robot (≥ 601), vision (≥ 960), télécommande ; tests de
`theatre_contrats` verts ; `grep -rnE "json\.loads\(\s*(ros_)?msg\.msg" legacy/ --include=*.py | grep -v /test` ne
renvoie que `wheels_bridge_node.py` ; sim `stage` + animation `parle` jouée ; **V-R3 Chantiers 21/21 rejoué** ;
`grep -rnE "create_(publisher|subscription)\([^,]+,\s*['\"]/" legacy/*/vision legacy/*/robot`
= 0.

### L1b — un nom par robot (`ROBOT_NAME`, namespace)

Les launch (robot, vision, sim) prennent `ROBOT_NAME` (défaut `didier`) et posent le
namespace sur tous les nœuds ; la télécommande et la page scène le prennent aussi (même
variable) ; test gravé : avec `ROBOT_NAME=didier2`, `ros2 topic list` en sim ne montre
**aucun** topic hors `/didier2/…` (sauf `/rosout`, `/parameter_events`). ⚠️ Le chemin roues
change de nom de topic (pas de code) → sim + **protocole caméra à la prochaine séance
robot** (noté au tableau de bord, verrou de déploiement).

#### L1b — conception détaillée (04/11, Fable ; spec FERMÉE pour l'implémenteur)

**Faits relevés le 04/11** (balayage du dépôt, repris dans cette conception) :
- 7 launch files, aucun ne pose de namespace : `robot_bringup/robot_app`, `robot_drive/drive`
  (inclus par le précédent ET lancé seul en sim), `robot_sim/sim`, `robot_web/web`,
  `robot_rehearsal/rehearsal` (lance aussi `didier_jeu`), `robot_description/display`,
  `vision/vision`. La télécommande n'a pas de launch : `ros2 run controller controller_node`
  dans ses deux scripts `launch-*-docker.sh`.
- Noms absolus restants dans le code : `robot_rehearsal/contracts.py` `ODOM_TOPIC =
  "/ground_truth/odom"`, `robot/nodes/gaze_follower_node.py` `NECK_TOPIC_SIM = "/neck/position"`.
  Tout le reste est relatif (L1a), le pont web et la page scène ne manipulent que des noms
  relatifs (whitelist) : ils suivent le namespace de leur node sans changement.
- `robot_sim/config/gz_bridge.yaml` : 13 entrées, côté ROS **absolues** (`/cmd_vel`, `/odom`,
  `/ground_truth/odom`, `/joint_states`, `/<servo>/position` ×5, `/material_color`, `/clock`,
  `/tf`) sauf les 2 caméras déjà relatives.
- 7 scripts shell utilisent la CLI `ros2 topic pub/echo` avec des noms relatifs ou absolus
  (`validate-rehearsal-{route,faults,chantiers}.sh`, `validate-jeu-a1.sh` — pilote rclpy
  `rclpy.init()` + `Node(...)` sans namespace —, `validate-cmdvel-protocol.sh` ⚠️ protocole
  caméra du robot : `/wheels`, `/e_stop`, `pub.sh`, `collect-incident.sh`). **Un nom relatif
  tapé dans la CLI se résout à la racine, pas dans le namespace** : ces scripts cassent en
  silence dès que les nœuds sont namespacés.
- Commandes manuelles documentées (CLAUDE.md legacy, operations.md, README de didier_jeu,
  person_follower, teleop clavier) : mêmes noms relatifs en CLI.

**Décisions (ne pas rouvrir)** :
1. **Une seule variable, `ROBOT_NAME`**, défaut `didier`, lue par les launch via
   `EnvironmentVariable("ROBOT_NAME", default_value="didier")` et exposée en argument
   `robot_name:=` (défaut = la variable). Posée dans les 6 compose (`robot` arm/x86, `vision`
   arm/x86, `control` arm/x86, `sim`) comme `ROS_DOMAIN_ID` : `ROBOT_NAME=${ROBOT_NAME:-didier}`.
2. **Namespace ABSOLU** : chaque launch enveloppe ses nœuds dans
   `GroupAction([PushRosNamespace(["/", robot_name]), …])`. Absolu = idempotent : `drive.launch`
   inclus par `robot_app.launch` OU lancé seul donne `/didier/…` dans les deux cas (launch_ros
   ignore le namespace parent quand le poussé commence par `/`). Jamais de `namespace=` par
   nœud (on l'oublierait au prochain nœud).
3. **Exceptions GRAVÉES, globales par construction ROS** : `/clock` (TimeSource rclcpp/rclpy
   s'abonne à `/clock` absolu), `/tf` et `/tf_static` (TransformBroadcaster), `/rosout`,
   `/parameter_events`. Rien d'autre. `robot_description` et `joint_states` passent sous le
   namespace (`robot_state_publisher` et `ros_gz_sim create -topic robot_description` sont dans
   le groupe, ils se suivent).
4. **`gz_bridge.yaml`** : `ros_topic_name` relatifs (on retire le `/` initial) pour tout sauf
   `/clock` et `/tf` ; les `gz_topic_name` ne changent PAS (le monde gz ignore ROS). Le
   `parameter_bridge` est dans le groupe : rclcpp étend les relatifs avec son namespace.
   Commentaire en tête du YAML qui dit pourquoi ces deux-là restent absolus.
5. **Code** : `ODOM_TOPIC` et `NECK_TOPIC_SIM` deviennent relatifs (`ground_truth/odom`,
   `neck/position`), rien d'autre ne change dans les nœuds. **Interdit** : toucher
   `wheels_bridge_node.py`, `twist_mux.yaml`, `twist_deadman`, `wheels_node` — leurs topics
   changent de nom PAR le namespace, pas par le code (c'est l'objet du protocole caméra).
6. **CLI** : les scripts posent `NS="/${ROBOT_NAME:-didier}"` et préfixent CHAQUE topic
   (`$NS/route`, `$NS/ground_truth/odom`, `$NS/wheels`, `$NS/e_stop`…) ; le pilote rclpy de
   `validate-jeu-a1.sh` reçoit `namespace=NS`. La télécommande : `ros2 run controller
   controller_node --ros-args -r __ns:=/${ROBOT_NAME:-didier}`. Lancements manuels documentés
   (`ros2 run robot person_follower`, `gaze_follower`, `didier_jeu jeu_node`, teleop) : même
   `--ros-args -r __ns:=/didier` ; `ros2 topic pub /didier/animation …` dans CLAUDE.md
   (legacy) et operations.md.
7. **Preuve gravée, deux niveaux** :
   - host (pytest, sans ROS) : `legacy/dadou_robot_ros/robot/tests/unit/test_namespace_contract.py`
     — (a) chaque `*.launch.py` des 3 dépôts contient `PushRosNamespace` ET `ROBOT_NAME` ;
     (b) dans `gz_bridge.yaml`, tout `ros_topic_name` est relatif sauf la liste gravée
     `{"/clock", "/tf"}` ; (c) le grep des noms absolus de L1a étendu aux constantes
     `ODOM_TOPIC`/`NECK_TOPIC_SIM` ; (d) chaque script `conf/scripts/validate-*.sh` et `pub.sh`
     qui appelle `ros2 topic` définit `NS=` et n'a aucun `ros2 topic (pub|echo|hz) [^$/]`
     (regex gravée).
   - sim : `conf/scripts/validate-namespace.sh` (monté dans le conteneur comme les autres) —
     lance drive + rehearsal(jeu:=true) + web dans la sim démarrée avec `ROBOT_NAME=didier2`,
     attend 10 s, puis `ros2 topic list` : **tout** commence par `/didier2/` sauf les 5
     exceptions gravées ; `ros2 node list` : tout sous `/didier2/`. KO = sortie 1 avec la
     liste des intrus. Rejouable avec `ROBOT_NAME=didier` (le défaut) : même règle.
8. **Porte de sortie L1b** : pytest robot/vision/télécommande/contrats verts ;
   `validate-namespace.sh` OK avec `didier2` puis `didier` ; **V-R3 Chantiers 21/21** et
   **validate-jeu-a1 13/13** rejoués (les scripts préfixés) ; animation `parle` jouée en sim ;
   doc : operations.md, CLAUDE.md legacy (commandes), `packages/README.md`, tableau de bord
   (`chantiers.md` : L1b fait en sim, **verrou = protocole caméra à la prochaine séance robot,
   `validate-cmdvel-protocol.sh` préfixé à rejouer**).

### L1c — le robot publie catalogue + sha

`didier` publie, latché : `catalogue` (JSON : séquences, expressions, visuels, audios,
relais, lumières — généralisation de `web_catalog.py`) et `deploy_sha` (le sha git écrit par
Ansible au rsync, ou `dev` en sim). La page scène affiche le sha ; la télécommande garde
`BUTTONS_LAYOUT` **mais** un test gravé le compare au catalogue publié (différence = rouge) ;
Ansible écrit `DEPLOY_SHA` au rsync. Porte : en sim, `ros2 topic echo catalogue --once`
rend les 6 familles ; test télécommande vert.

#### L1c — conception détaillée (04/11, Fable ; spec FERMÉE pour l'implémenteur)

**Faits relevés le 04/11** :
- `robot_web/web_catalog.py` construit déjà 5 familles en logique PURE (stdlib) : `faces`
  (clés de `expressions.json`), `audios` (`{label, value=path}` depuis `audios.json`, entrées à
  path vide exclues), `animations` (noms sous `json/sequences/**`), `relays`, `robot_lights`.
  Servi par `GET /api/catalog` du pont web, consommé par la page. La 6ᵉ famille de l'étude,
  les **visuels**, vit dans `json/visuals.json` : `{"visual": [{"name", "path"}, …]}`.
- La télécommande : `controller/buttons/button_config.py` `BUTTONS_LAYOUT[mode][bouton] =
  {NAME, CMD: {clé: valeur}}` ; les clés visées par le catalogue sont `ANIMATION` (str, ou
  `STOP`, ou `{TYPE: "bug"}` = tirage par type), `AUDIO` (valeur publiée telle quelle, le
  robot attend un **chemin** — `AudioManager.play_sound(msg[AUDIO])`), `RELAY`, `FACE`,
  `ROBOT_LIGHTS`. Le test existant `test_button_config.py` ne vérifie que les TOPICS, pas les
  valeurs : un bouton peut viser une séquence ou un audio qui n'existe pas.
- Déploiement : rôle Ansible `synchronise` (rsync de l'arbre de travail, SANS `--delete`,
  `local_projects_dir` = `theatre-robot/legacy`). Le conteneur robot monte
  `conf/ → /home/ros2_ws/src/robot/conf` (arm et x86) : un fichier déposé dans `conf/` sur le
  Pi est visible du conteneur et survit aux rsync suivants.
- Pont web : `TOPICS_LECTURE` (web_protocol.py) = topics latchés lus en TRANSIENT_LOCAL et
  rediffusés dans le message `state` (2 Hz) ; la page les affiche en badge (`badge-mode`…).

**Décisions (ne pas rouvrir)** :
1. **Deux topics, dans `theatre_contrats.topics`** : `CATALOGUE = 'catalogue'` et
   `DEPLOY_SHA = 'deploy_sha'` (ajoutés à l'inventaire gravé `test_inventaire.py`). Les deux
   sont **StringTime latchés** (`qos.latched()`), `msg` = JSON : le catalogue = l'objet des 6
   familles ; le sha = une chaîne JSON (`"a1b2c3…"` ou `"dev"`).
2. **Un nœud dédié, `robot_web/catalogue_node.py`, exécutable `catalogue`** (pas dans
   `web_bridge_node` : le catalogue sert la télécommande même sans pont web, et le pont web
   est optionnel en sim). Paramètres : `json_dir` (défaut `/home/ros2_ws/json`),
   `deploy_sha_file` (défaut `""` = pas de fichier = `dev`), `refresh_period_s` (défaut 2.0).
   Au démarrage il publie les deux ; puis à chaque période il reconstruit le catalogue et ne
   **republie que si le JSON a changé** (comparaison de la chaîne sérialisée : c'est ce qui
   rend L1d trivial — écrire un fichier suffit, le catalogue suit). Le sha ne change jamais
   en cours de vie : lu une fois.
3. **Logique pure dans `web_catalog.py`** : `build_catalog()` gagne la famille `visuals`
   (liste triée des `name` de `visuals.json["visual"]`, `[]` + WARNING si absent/illisible,
   jamais d'exception — même contrat que les 5 autres) ; nouvelle fonction
   `read_deploy_sha(path: str) -> str` : fichier absent/vide/illisible → `"dev"`, sinon
   contenu `strip()`. Les clés existantes (`faces`, `audios`, `animations`, `relays`,
   `robot_lights`) **ne sont pas renommées** (la page les consomme). Le nœud reste mince :
   timer + comparaison + publication, rien d'autre.
4. **Lancement** : `robot_app.launch.py` ajoute `catalogue` (toujours, pas conditionné) avec
   `json_dir=/home/ros2_ws/src/robot/json` et `deploy_sha_file=/home/ros2_ws/src/robot/conf/DEPLOY_SHA` ;
   `sim.launch.py` l'ajoute toujours (`json_dir` par défaut, pas de fichier sha → `dev`).
   Dans le groupe namespace de L1b, comme les autres.
5. **Ansible écrit le sha** : tâche ajoutée à la FIN du rôle `synchronise` (robot uniquement
   pour L1c ; vision/télécommande = quand `machines/` existera, L1e) : `copy` avec
   `content: "{{ lookup('pipe', 'git -C ' ~ local_projects_dir ~ ' rev-parse HEAD') }}{{ '-dirty' if lookup('pipe', 'git -C ' ~ local_projects_dir ~ ' status --porcelain') else '' }}"`
   vers `{{ ros2_ws }}/src/robot/conf/DEPLOY_SHA`. Le suffixe `-dirty` est OBLIGATOIRE :
   le rsync copie l'arbre de travail, pas un commit — un sha propre mentirait. Côté PC, le
   fichier `conf/DEPLOY_SHA` ne doit JAMAIS exister : ajouté au `.gitignore` de
   `legacy/dadou_robot_ros` avec un commentaire (sinon la sim afficherait un faux sha).
6. **Page scène et console** : `deploy_sha` entre dans `TOPICS_LECTURE` ; `index.html` et
   `scene.html` affichent un badge `badge-version` à côté de `badge-mode`, rempli depuis
   `state` (chaîne `dev` ou les 7 premiers caractères du sha, suffixe `-dirty` conservé
   et affiché en badge d'alerte). `catalogue` N'entre PAS en lecture (la page garde
   `/api/catalog`, même fonction donc même contenu).
7. **Test gravé télécommande** :
   `legacy/dadou_control_ros/controller/tests/unit/test_buttons_vs_catalogue.py`. Le conftest
   de la télécommande ajoute `legacy/dadou_robot_ros/conf/ros2_dependencies/robot_web` au
   `sys.path` (module pur, stdlib) ; le catalogue est construit depuis
   `legacy/dadou_robot_ros/json` (chemin relatif au dépôt, calculé depuis le fichier de
   test). Pour chaque bouton de chaque mode : `ANIMATION` str ∈ `animations` (formes
   acceptées gravées : `STOP`, `{TYPE: …}`) ; `AUDIO` ∈ valeurs `value` (chemins) de
   `audios` ; `RELAY` ∈ `relays` ; `FACE` ∈ `faces` ; `ROBOT_LIGHTS` ∈ `robot_lights`.
   Message d'échec : mode, bouton, libellé, valeur, et la famille où elle manque.
   ⚠️ Attendu : ce test va probablement **rougir sur des boutons existants** (ex. `AUDIO:
   'ca-va'` n'est pas un chemin). Règle : **ne corrige un bouton que si la cible voulue est
   sans ambiguïté** (un audio dont le label est exactement `ca-va` → sa `value`) ; sinon
   laisse le test rouge, marque-le `xfail(strict=True)` avec la raison, et liste-le dans
   le rapport : c'est David qui tranche ce qu'un bouton doit jouer.
8. **Preuve sim** : `conf/scripts/validate-catalogue.sh` (monté dans le compose comme les
   autres) : `ros2 topic echo $NS/catalogue --once --qos-durability transient_local --field msg`
   → JSON à **6 clés** toutes non vides (sauf `visuals` qui peut l'être si le JSON est vide :
   non, il contient des entrées, exiger non vide) ; `$NS/deploy_sha` → `"dev"` ; puis
   `touch`/ajout d'une séquence temporaire sous `json/sequences/tmp-l1c/` → en ≤ 5 s le
   catalogue republié contient le nouveau nom ; suppression → disparaît. KO = sortie 1.
9. **Tests host** : `test_web_catalog.py` étendu (visuals, `read_deploy_sha` : absent → dev,
   vide → dev, contenu → strip) avec valeurs GRAVÉES ; `test_catalogue_node.py` sur la
   logique « republie seulement si changé » (le nœud expose une fonction pure
   `next_publication(previous_json, current_json) -> str | None`, testée sans rclpy).
10. **Porte de sortie L1c** : pytest robot + télécommande + contrats verts (ou xfail
    gravés listés) ; `validate-catalogue.sh` OK en sim ; `validate-namespace.sh` toujours OK
    (le nouveau nœud est sous le namespace) ; doc : README de `robot_web` (le nœud, les deux
    topics), `docs/interfaces.md` (legacy robot : les deux topics), operations.md (badge
    version : à quoi sert `-dirty`), README Ansible (le sha), `packages/README.md`,
    tableau de bord `chantiers.md` (L1c fait en sim ; verrou = premier déploiement robot
    affiche le sha).

### L1d — édition à travers le robot

Topic `data_edit` (StringTime, payload JSON `{kind, name, content}`) ; le robot **valide**
le contenu avec les mêmes contrats que les tests (schéma de séquence, audio/visuel
existant), écrit `json/<kind>/<name>.json` **après** une sauvegarde `json/backup/<date>/`,
republie `catalogue` ; refus loggué + publié sur `data_edit_result`. La page scène obtient
un éditeur **minimal** (texte JSON + bouton « envoyer » ; depuis l'amendement du 12/11 :
séquences, expressions, lumières, et envoi d'une image du visage) — c'est l'outil de
réglage, pas l'éditeur final. Porte (celle de l'étude) : **une retouche faite depuis la
page scène arrive dans `json/` du robot (sim) et est rejouée** ; un payload invalide est
refusé et visible. Les 71 JSON de la télécommande : **supprimés** (ils sont dans git).

#### L1d — conception détaillée (12/11, Fable ; spec FERMÉE pour l'implémenteur) : une seule écriture, jamais perdue au déploiement

**Amendée le 12/11 au soir après réponses de David** : (1) édition sur le vrai robot désactivée à
la fin de L1d, activée sur sa décision — retenu ; (2) mêmes règles d'édition en sim et en réel —
retenu ; (3) **roues PAS gelées** : une piste `wheels` est une donnée, bornée par le contrat
(décision 7) ; (4) **séquences, lumières ET expressions dès L1d**, avec envoi d'image validé par le
robot (décisions 3, 4, 6, 12) ; (5) **« validation sim obligatoire avant déploiement », sans
corvée** : rejeu automatique en sim de tout ce qui a changé, validation à l'œil pour les roues
seulement, deux barrières (décisions 7 bis, 7 ter). Cinq sous-étapes au lieu de quatre,
**≈ 14 h** au lieu de ≈ 8 h (décision 17).

**Faits relevés le 12/11** :
- **Les contrats de données n'existent que sous forme de tests** : `packages/didier_core/test/unit/
  test_sequences_json.py` (format : `keys` str, `duration` > 0, keyframes `[t, valeur]`, t ∈ [0,1]
  croissant, servos, roues) et `test_sequences_assets.py` (références : `faces` → clés
  d'`expressions.json`, `robot_lights` → clés de `robot_lights.json`, `audios` → `stop` ou fichier
  sous `medias/audios/`). Aucune fonction réutilisable : « les mêmes contrats que les tests »
  exige de les EXTRAIRE, pas de les recopier.
- **48 séquences** sous `data/json/sequences/<dossier>/<nom>.json` (6 dossiers), toutes conformes
  à `^[a-z0-9][a-z0-9_-]{0,63}/[a-z0-9][a-z0-9_-]{0,63}$` ; la plus grosse fait 38 580 octets ;
  17 clés de premier niveau en usage (liste en décision 6) ; **24 portent une piste `wheels`
  non vide**. Un nom existe dans deux dossiers (`appel-eternel-life`). 16 fichiers sur 48
  seulement sont au format `json.dumps(indent=4)` (les autres sont formatés à la main).
- **Une piste `wheels` commande réellement les roues** : `animations_node` la publie sur `wheels`
  (`PUBLISHER_LIST`, `anim=true`) → `wheels_bridge` → `twist_mux` (anim 10) → `twist_deadman`.
  Les keyframes sont en fraction de `duration` : changer `duration` change la durée du mouvement.
- **Les séquences sont lues UNE fois**, au démarrage d'`animations_node`
  (`AbstractJsonActions.load_multi_files_sequences`, indexées par nom de fichier sans dossier) :
  sans rechargement, une retouche n'est rejouée qu'après redémarrage. Ce chargeur lit **tout
  fichier** sous `sequences/` (`FilesUtils.get_folder_files`, sans filtre d'extension) : un
  fichier temporaire laissé là ferait tomber le nœud au démarrage suivant.
- `catalogue_node` republie si la liste des NOMS change (L1c) : une création le fait bouger, une
  retouche de contenu NON.
- **Montages** : `json/` est monté en lecture-écriture partout (compose ARM :
  `../../../json:/home/ros2_ws/src/robot/json` ; sim : `data/json` du PC monté deux fois,
  `/home/ros2_ws/json` et `/home/ros2_ws/src/robot/json`). Les conteneurs tournent en root : en
  sim, un fichier écrit par le conteneur appartient à root DANS l'arbre de travail du PC.
- **Déploiement** : le rôle `synchronise` copie `data/{json,medias,db}` vers `src/robot/` sans
  `--delete` ni `--update` : un fichier retouché sur le Pi est ÉCRASÉ par la version du PC, un
  fichier créé sur le Pi y reste sans jamais revenir dans git. `ecart-pi.sh` (a) voit « changed »
  dans les deux sens, sans dire lequel a raison.
- **Pont web** : écriture réservée à la session « writer » (jeton), publishers créés par liste
  blanche seulement ; `TOPICS_FLUX` → messages `feed` ; `rehearsal_enabled` ignoré hors 43.
  Le pont tourne aussi sur le vrai robot (`noeuds_attendus`).
- **Télécommande** (`legacy/dadou_control_ros/json/`, 71 fichiers) : le seul lanceur
  (`controller/nodes/main_gui.py`) ouvre `SmallGui` ; `NormalGui`, qui porte les fenêtres
  d'édition (les « 8 modules qui écrivent »), n'est instancié nulle part. Le chemin vivant lit
  `expressions.json`, `lights_base.json`, `lights_methods.json` (`ControlJsonManager.__init__`)
  et `playlists/*.json` (7, `small_playlist.py`) : **10 fichiers lus, 61 que rien de lancé ne lit**.
- `data/json/backup/maker_fair.json` (suivi) : ancienne sauvegarde d'une playlist, aucun lecteur
  dans `packages/`.

**Faits relevés le 12/11 au soir (amendement)** :
- **Les 24 pistes `wheels`** ne contiennent que des paires numériques `[gauche, droite]` — aucune
  commande texte, aucun dict, alors que le test les tolère. Plus forte consigne : **0.89**
  (`eternel-show/seq1`, 1 s, clé `C2`) ; puis 0.8 (`iloveyou2`), 0.6 (les 5 `bugs/`), ≤ 0.5 ailleurs.
  Plus longue `duration` d'une séquence à roues : **300 000 ms** (`appel-eternel-life2`) ; 600 000
  sans roues. Plus longue TENUE d'une consigne non nulle (écart jusqu'à l'image suivante ×
  `duration`) : **55,8 s** (`trip`). 22 pistes finissent par `[0, 0]` (12 à la fraction 1, 10 avant,
  de 0.75 à 0.99) ; **2 finissent en mouvement** : `iloveyou2` (`[-0.8, 0.8]` à 0.6) et `seq1`
  (`[0.84, 0.78]` à 1.0). `moon-walk` porte deux images à la même fraction 1.
- **Unités** : la paire est une consigne dans [-1, 1]. Chaîne `cmd_vel` : `wheels_bridge` en fait un
  Twist avec `max_wheel_speed` = 1,0 m/s à consigne 1.0, valeur nominale (« calibration physique à
  venir ») — **aucune vitesse réelle n'est mesurée**. PWM : rapport cyclique = `MIN_PWM` 5 000 +
  |consigne| × (`MAX_PWM` 39 318 − 5 000), sur 65 535 → 34 % à 0.5, 54 % à 0.89, 60 % à 1.0. Le
  protocole caméra du 04/07 n'a validé que 50 %.
- **Fin de séquence** : `animations_node` publie `stop` sur TOUTES les pistes (`send_msgs`), roues
  comprises. La durée passée au lancement (`time` du message `animation`) remplace `duration`.
- **Lu dans le code, pas mesuré** : en mode `cmd_vel` (config officielle depuis le 04/07) une image
  roues est émise UNE fois (`Track.emissions`) → un seul Twist → `twist_deadman` coupe 400 ms plus
  tard. La tenue jusqu'à l'image suivante était le fait du mode legacy (`animation_deadline`). Si
  la mesure le confirme, les pistes roues ne jouent aujourd'hui que des impulsions : constat à
  établir à l'épreuve 7 (décision 15), **pas à corriger dans L1d** (chemin roues intouché).
- **Expressions** : `expressions.json`, 37 entrées, clés en usage `name, follow audio, loop, keys,
  duration, left_eyes, right_eyes, mouths, default` ; contrat déjà écrit en test
  (`test_expressions_json.py` : `duration` > 0, `loop` bool, 3 pistes obligatoires `[t, fichier]`,
  fichier présent, bouche 24×16, œil 8×8). **Images** : 127 PNG sous `medias/visuals/{mouth,eye}/`
  (3 en sous-dossiers `persos/`, `test/`), au plus 12 460 octets ; 106 en RVB 8 bits, 20 bouches en
  RVB 16 bits (15 référencées par une expression), 1 en RVBA. `Face.load_visuals` les charge TOUTES
  au démarrage (`imageio.imread`, récursif, sans filtre d'extension, indexées par nom de fichier nu,
  bouche et yeux dans le même dictionnaire — aucun homonyme aujourd'hui) : un fichier illisible
  ferait tomber le visage au démarrage suivant. Pixels posés tels quels : **aucune palette**, la
  luminosité est le réglage global du ruban ; une image de mauvaise taille est refusée en silence.
- **Lumières** : `robot_lights.json` (13 entrées, clés `loop, duration, keys, sequences, default` ;
  `sequences` = dict ORDONNÉ `{brique: fraction}`) enchaîne les briques de `lights_base.json` (20,
  clés `method, color, speed, period, max_intensity, min_intensity`) ; couleurs dans `colors.json`
  (13). Contrat déjà en test (`test_lights_json.py`). `lights_methods.json` ne peut pas servir de
  référence : ses noms (`colorcycle`) ne sont pas les `method` des briques (`color_cycle`).
  Les 70 noms d'entrées tiennent dans `^[a-z0-9][a-z0-9 _-]{0,63}$` (l'espace est en usage).
- **Lecture unique** : expressions, images, lumières et briques sont lues au démarrage (sur le robot,
  visage et lumières vivent dans `lights_node`). **En sim** : le visage est `face_sim` (`FACE=true`,
  la vraie classe `Face` sur un ruban factice) ; les lumières sont `leds_sim_node`, logique propre à
  la sim — la vraie classe `Lights` dépend de bibliothèques qui n'existent que sur le Pi.
- **Fumée** : elle ne modifie jamais l'arbre de travail hors `docs/fumee/` ; elle ne peut donc pas
  écrire un registre versionné. Somme des `duration` des 48 séquences : 2 521,5 s (42 min).
- **Télécommande** : sa copie d'`expressions.json` a 15 entrées contre 37 côté robot (déjà périmée) ;
  `lights_base.json` et `lights_methods.json` sont identiques à ceux du robot.

**Décisions (ne pas rouvrir)** :
1. **Deux topics, pas un service** : `DATA_EDIT = 'data_edit'` (demande) et
   `DATA_EDIT_RESULT = 'data_edit_result'` (verdict), dans `theatre_contrats.topics` et
   l'inventaire gravé, relatifs (namespace du robot), StringTime, **`qos.volatile(10)` des deux
   côtés**. Pourquoi : tout le parc parle StringTime (codec, pont web, télécommande) ; le verdict
   doit être vu de TOUS (page, journal, rechargement), pas du seul appelant ; un `.srv` imposerait
   de reconstruire `theatre_interfaces` sur chaque image. Le défaut d'un topic (pas de
   corrélation) est payé par un `id` recopié dans le verdict et une attente de 5 s côté client.
   **Jamais latché** : une demande rejouée à un écrivain redémarré réécrirait une vieille retouche.
2. **Demande** (`msg` = JSON, ≤ **131 072 octets**, sinon `trop_gros` avant tout décodage) :
   `{"id": 1-64 car. [A-Za-z0-9_-], "kind": <décision 3>, "mode": "create"|"replace",
   "name": <forme propre au kind>, "content": {…} (pour `image` : les octets du PNG en base64),
   "base_sha256": "<hex>"}` (`base_sha256` exigé en `replace` : sha256 de ce que l'éditeur a
   chargé — octets du fichier pour `sequence` et `image`, **JSON canonique de l'ENTRÉE** pour les
   trois autres, afin que deux retouches d'entrées différentes du même fichier ne se gênent pas ;
   différent du disque → `conflit`). JSON canonique, partout dans L1d : `json.dumps(x,
   sort_keys=True, separators=(",", ":"), ensure_ascii=False)` en UTF-8. **Verdict** : `{"id", "ok",
   "code", "detail": [≤ 20 chaînes ≤ 300 car.], "kind", "name", "mode", "sha256", "sauvegarde",
   "avertissements": [chaînes GRAVÉES : `a_rejouer_en_sim`, `roues_a_valider_en_sim`]}`. Codes
   GRAVÉS : `ok`, `inchange` (contenu identique :
   ni sauvegarde ni journal), `edition_desactivee`, `payload_invalide`, `trop_gros`,
   `kind_inconnu`, `mode_inconnu`, `nom_invalide`, `dossier_absent`, `existe_deja`, `absent`,
   `nom_en_double`, `conflit`, `cle_inconnue`, `contrat`, `quota_jour`, `erreur_ecriture`
   (`roues_gelees` est retiré : une piste roues hors bornes est une faute de `contrat`). Journal ROS : INFO si `ok`, WARNING sinon (id, nom, code — jamais le contenu).
3. **Liste blanche `kind` : cinq, table `KINDS` gravée** (amendée : « on édite à travers le
   robot » vaut pour tout ce que la page règle) :

   | `kind` | cible | `name` | `content` |
   |---|---|---|---|
   | `sequence` | `json/sequences/<dossier>/<nom>.json` (un fichier) | `<dossier>/<nom>` | objet |
   | `expression` | une entrée d'`expressions.json` | nom d'entrée | objet |
   | `lumiere` | une entrée de `robot_lights.json` | nom d'entrée | objet |
   | `brique` | une entrée de `lights_base.json` | nom d'entrée | objet |
   | `image` | `medias/visuals/<zone>/<nom>.png`, zone ∈ `mouth`, `eye` | `<zone>/<nom>` | PNG en base64 |

   Noms d'entrée : `^[a-z0-9][a-z0-9 _-]{0,63}$` ; dossier, nom de séquence et nom d'image :
   `^[a-z0-9][a-z0-9_-]{0,63}$`. Hors liste : relais, audios, `colors.json`, `visuals.json`,
   playlists (L4). **Pas de suppression, pas de renommage, pas de création de dossier** par le
   topic : ça passe par git et un déploiement. **Pas d'outil de dessin** : l'image se fabrique
   ailleurs et s'envoie ; le dessin dans la page est explicitement reporté (éditeur final, L4).
4. **Le contrat devient un module pur, `theatre_contrats/donnees.py`** (stdlib seule, donc ni
   `imageio` ni `didier_core`) : `nom_valide(kind, name) -> bool`, `charger_references(data_dir)`,
   et une fonction par kind, qui rend TOUTES les erreurs (liste vide = conforme) :
   - `verifier_sequence(sequence, references)` : les règles et les messages des deux tests actuels,
     **plus les bornes roues de la décision 7** (seul durcissement) ;
   - `verifier_expression(nom, expression, references)` : les règles de `test_expressions_json.py` ;
     la taille d'une image se lit dans l'en-tête PNG (plus d'`imageio` dans le contrat) ;
   - `verifier_lumiere(nom, lumiere, references)` et `verifier_brique(nom, brique, references)` :
     les règles de `test_lights_json.py` ; `keys` = liste de chaînes ou la chaîne `"None"` (3
     entrées la portent) ; `method` ∈ `METHODES_LUMIERE`, liste gravée dans `donnees.py`, dont
     l'égalité avec les méthodes de `LightsAnimations` est gravée par un test de `didier_core` ;
     `color` ∈ `colors.json` ; les autres champs d'une brique sont des nombres ;
   - `verifier_image(zone, octets)` — **contrat d'image, strict pour tout ce qui ENTRE** : signature
     PNG, CRC de chaque bloc juste, `IHDR` = 24×16 (`mouth`) ou 8×8 (`eye`), **RVB 8 bits, non
     entrelacé** (le format de 106 des 127 images), `IDAT` décompressé de la longueur attendue
     (`hauteur × (1 + largeur × 3)`), au plus **16 384 octets** (max relevé 12 460). Aucune
     contrainte de palette : le code n'en a pas.
   Les quatre tests de données (`test_sequences_json.py`, `test_sequences_assets.py`,
   `test_expressions_json.py`, `test_lights_json.py`) sont **réécrits pour appeler le module**
   (`== []` sur tout `data/`) : un seul contrat, lu par les tests — donc aussi par ce qui arrive par
   git —, l'écrivain, le rapatriement et, demain, la télécommande. Nouveau test sur les images de
   `data/` : les 127 passent `verifier_image`, sauf une **liste d'exceptions gravée par nom** — les
   20 bouches en 16 bits et l'image RVBA, héritées (leur rendu réel sur la matrice n'est pas
   relevé : à convertir ou non, décision à part, hors L1d). Nouveau
   `packages/theatre_contrats/test/test_donnees.py` : une donnée fautive par règle, message attendu
   GRAVÉ ; PNG d'essai construits octet par octet dans le test.
5. **L'écrivain = un nœud dédié, `didier_web/data_edit_node.py`, exécutable `data_edit`**, mince ;
   toute la logique dans `didier_web/data_edit.py` (stdlib + `theatre_contrats`), fonction
   `traiter(brut, data_dir, enabled, maintenant) -> dict`, testée sans ROS sur `tmp_path`. Pas dans
   `catalogue_node` (lecteur, toujours actif, ne doit pas tomber avec l'écrivain), pas dans le
   pont web (optionnel). Paramètres : `data_dir` (défaut `/home/ros2_ws/src/robot`, enfants
   `json/` et `medias/` — même chemin en sim et sur le Pi ; ⚠️ vérifier que `medias/` est monté en
   lecture-écriture comme `json/`, sinon le corriger dans les deux compose), `enabled` (défaut
   `false`). Lancé
   TOUJOURS par `robot_app.launch.py` et `sim.launch.py` (ajouté à `noeuds_attendus`) : désactivé,
   il répond `edition_desactivee` à chaque demande — un refus visible vaut mieux qu'un silence.
6. **Règles propres à l'édition** (dans `data_edit.py`, après le contrat), listes de clés GRAVÉES
   (`cle_inconnue`) : séquence `audio, audio_name, audio_path, audios, duration, faces, keys,
   left_arm, left_eye, lights, loop, neck, right_arm, right_eye, robot_lights, types, wheels` ;
   expression `name, follow audio, loop, keys, duration, left_eyes, right_eyes, mouths, default` ;
   lumière `loop, duration, keys, sequences, default` ; brique `method, color, speed, period,
   max_intensity, min_intensity`. `create` refuse une cible présente (`existe_deja`), `replace` une
   cible absente (`absent`). Séquence : le dossier existe déjà (`dossier_absent`) ; un nom déjà
   porté dans un autre dossier est refusé en `create` comme en `replace` (`nom_en_double`, le
   chargeur indexe par nom nu). Image : même refus si le nom existe dans l'AUTRE zone (`Face` indexe
   par nom de fichier nu). Chemin résolu (`realpath`) strictement sous le dossier cible, cible ni
   lien symbolique ni dossier (`nom_invalide`). **Une référence ne casse jamais** : rien ne se
   supprime, et remplacer une entrée ou une image garde son nom.
7. **Roues : BORNÉES par le contrat, pas gelées** (amendée — David : « pourquoi je ne pourrais pas
   modifier un chemin de roue ? »). La règle « sim + protocole caméra » protège le CODE du chemin
   roues, qui reste intouché ; une piste `wheels` est une DONNÉE qui passe par cette chaîne
   (télécommande 100 > animation 10, deadman 400 ms, verrou `e_stop`) et qu'on retouche déjà à la
   main dans le JSON. L'éditeur n'est pas plus sévère que cette pratique, mais une faute de frappe
   ne doit pas lancer 50 kg. Bornes gravées dans `donnees.py`, appliquées par `verifier_sequence`
   à TOUTE séquence — éditeur, tests de `data/`, donc git :

   | Borne | Valeur | Source (faits du 12/11 au soir) |
   |---|---|---|
   | forme d'une image | `[fraction, [gauche, droite]]`, deux nombres finis, ni booléen ni texte ni dict | 24 pistes sur 24 ; `{"speed": …}` réglerait en plus le plafond de vitesse du pont pour la télécommande |
   | fractions | dans [0, 1], croissantes au sens large | règle existante ; `moon-walk` a deux images à 1 |
   | `VITESSE_ROUES_MAX` | \|consigne\| ≤ **0.89** | plus forte consigne relevée (`seq1`) ; 54 % de PWM, le protocole caméra n'a validé que 50 % |
   | `TENUE_ROUES_MAX_MS` | (fraction suivante − fraction) × `duration` ≤ **60 000** pour toute image non nulle ; la dernière compte jusqu'à 1 | plus longue relevée 55,8 s (`trip`) |
   | `DUREE_ROUES_MAX_MS` | `duration` ≤ **300 000** si la piste est non vide | plus longue relevée (`appel-eternel-life2`) ; un zéro de trop est refusé |
   | arrêt final | la dernière image vaut `[0, 0]`, à n'importe quelle fraction | 22 pistes sur 24 |

   Les consignes sont sans unité : aucune vitesse réelle n'est mesurée (faits), les bornes disent
   « pas plus que ce qui a déjà été écrit », pas « sûr en m/s ». **Arrêt final à n'importe quelle
   fraction, et non à 1.0** : 10 pistes s'arrêtent AVANT la fin (0.75 à 0.99), ce qui est plus
   prudent, et l'arrêt de fin de séquence existe déjà (`stop` sur toutes les pistes).
   **Deux séquences violent l'arrêt final** : `eternel-show/iloveyou2` et `eternel-show/seq1`.
   Choix : corriger la donnée — L1d-1 leur ajoute l'image `[1, [0, 0]]`, sans effet sur le jeu
   (c'est l'instant du `stop` de fin). Aucune autre séquence ne viole une borne. À trancher par
   David, hors L1d : si `seq1` est un reste d'essai, la supprimer ramène la borne à 0.8, et à 0.6
   sans `iloveyou2`.
   Ce que les bornes ne couvrent pas, dit : la `time` passée au lancement d'une animation étire la
   séquence sans passer par le contrat (existant, inchangé). **Le roulage au sol reste verrouillé**
   (refonte électrique + protocole caméra), indépendamment de L1d : ces bornes n'autorisent rien.
   Le chemin roues (`wheels_bridge`, `twist_mux`, `twist_deadman`, `wheels_node`) n'est pas touché.
7 bis. **Porte sim : rien de modifié n'atteint le vrai robot sans avoir été joué en sim** (David,
   12/11 : « validation sim obligatoire avant déploiement », et « ça serait peut-être super
   laborieux »). Les bornes ne disent rien de OÙ va le robot ; et la porte ne doit pas être une
   corvée. Donc : **automatique pour tout, à l'œil pour les roues seulement**.
   - **Empreintes** (pures, `donnees.py`, sha256 du JSON canonique, nombres convertis en `float`) :
     `empreinte_contenu` — séquence : le fichier ; expression : l'entrée + le sha256 de chaque
     image référencée ; lumière : l'entrée + les briques référencées (une image ou une brique
     retouchée périme donc ce qui la montre ; une expression retouchée ne périme PAS les séquences
     qui la citent : pas de cascade) ; `empreinte_roues` — `{duration, wheels}` d'une séquence à
     piste non vide, sinon `None`.
   - **Registre versionné `data/json/validations-sim.json`** (`indent=1`, clés triées, écriture
     atomique) : `{"version": 1, "sequence": {"<dossier>/<nom>": {"rejeu": <empreinte_contenu>,
     "roues": <empreinte_roues>, "origine_roues": "sim"|"heritee"}}, "expression": {"<nom>":
     {"rejeu": …}}, "lumiere": {…}}`. Il part sur le Pi avec `data/` ; **il ne s'écrit qu'en sim**
     (rien à rapatrier : le Pi ne le modifie jamais).
   - **Rejeu automatique = un observateur, `didier_web/validation_sim_node.py`** (exécutable
     `validation_sim`, logique pure dans `validation_sim.py`), lancé par `sim.launch.py` SEUL et qui
     s'arrête hors domaine 43 (même garde que `rehearsal_enabled`). Il regarde ce qui se joue,
     **quel que soit le déclencheur** (page, régisseur, script), et pose le tampon `rejeu` quand :
     séquence — `animation_state` passe au nom puis revient à `""` entre 0,95 × `duration` et
     `duration` + 5 s (jouée jusqu'au bout, pas interrompue), aucune ligne ERROR ou CRITICAL
     nouvelle dans le journal du robot (`config[LOGGING_FILE_NAME]`, lu depuis l'offset noté au
     départ ; si la sim n'écrit pas ce journal, l'implémenteur s'arrête et le rapporte), les nœuds
     attendus toujours présents, et pour une piste roues le dernier `cmd_vel` reçu est nul 1 s
     après la fin ; expression — nom reçu sur `face`, `face_sim` vivant et sans erreur pendant
     min(`duration`, 10 s) sans autre commande ; lumière — idem sur `robot_lights` avec
     `leds_sim_node`. Les bornes des servos ne sont pas remesurées : le contrat les garantit.
     Empreinte déjà au registre → aucune écriture (la fumée, qui joue `parle`, ne salit rien).
     Verdict publié sur `validation_sim` (StringTime, `qos.volatile(10)`, JSON `{kind, name, ok,
     code, detail}`).
   - **Validation à l'œil des roues** : demande `{id, name}` sur `validation_sim_demande` (bouton
     « Valider les roues pour le robot » de la page, décision 12). Acceptée seulement si le tampon
     `rejeu` de la séquence égale son empreinte actuelle (`non_rejouee` sinon) : on ne valide pas
     une trajectoire qu'on n'a pas vue jusqu'au bout. Écrit `roues` + `origine_roues: "sim"`.
   - **Par lot, sans page** : `machines/sim/rejouer-modifiees.sh` démarre la sim sans écran si elle
     ne tourne pas (`ANIMATIONS=true FACE=true`, domaine 43), publie tour à tour chaque élément que
     `donnees.a_rejouer(data_dir)` rend, attend son tampon, affiche OK / KO et ce qui reste à
     valider à l'œil. Aucune logique propre : l'observateur décide.
   - **Registre initial** : les tampons `rejeu` des 48 séquences, 37 expressions et 13 lumières
     sont posés par un VRAI passage de `rejouer-modifiees.sh` en L1d-2 (≈ 50 min de machine, aucun
     geste). Les 24 pistes roues entrent **validées d'office, `origine_roues: "heritee"`** : la
     porte attrape les CHANGEMENTS, ces pistes sont sur le robot depuis des années, et les exiger
     bloquerait tout déploiement — banc témoin compris — jusqu'à une séance de 24 visionnages.
     « Héritée » veut dire « jamais regardée en sim » et reste lisible dans la page ; la moindre
     retouche la fait passer par la porte. Les revoir en sim avant le premier roulage au sol est
     recommandé (voir le fait « impulsions »), et relève de ce verrou-là, pas de L1d.
   - **Ce que ça coûte à David** :

     | Cas | Gestes en plus | Attente |
     |---|---|---|
     | retouche sans roues, en sim, par la page | **0** (Envoyer puis Rejouer, qu'il fait de toute façon) | la durée de la séquence, jouée jusqu'au bout |
     | retouche des roues, en sim, par la page | **1 clic** (Valider les roues) | idem |
     | retouche à la main dans git, ou rapatriée du robot | **1 commande** (`rejouer-modifiees.sh`), + 1 clic par piste roues touchée | démarrage de la sim (à mesurer en L1d-2) + somme des durées touchées |
     | commit et déploiement | 0 : le registre est un fichier de plus dans le commit | — |

     Une séquence interrompue avant la fin n'est pas tamponnée ; la commande par lot la rattrape.
     Limite dite : la porte empêche l'OUBLI, pas la fraude — le registre est un fichier git, le
     modifier à la main se voit dans le diff.
7 ter. **Deux barrières, parce que chacune a un trou que l'autre ferme.**
   - **Au déploiement (tôt, bruyant, pour tout)** : test hôte `test_validations_sim.py` (dans les
     suites et la CI) — chaque séquence, expression et lumière de `data/` a son tampon `rejeu` à
     jour, chaque piste roues son tampon `roues`, aucune entrée orpheline au registre ; et garde
     Ansible dans `synchronise`, avant la copie des données, jouée aussi en `--check`
     (`python3 -m theatre_contrats.donnees non-validees data/` sur le PC) : liste non vide → `fail`
     avec la liste et les deux commandes. **Aucune échappatoire** : passer la porte coûte moins
     que la contourner. C'est aussi elle qui soumet les retouches faites à la main dans git à la
     même porte que l'éditeur. Son trou : elle ne voit pas un fichier écrit directement sur le Pi.
   - **Au jeu, sur le robot (tard, pour les roues seulement)** : `AnimationManager` construit la
     piste `wheels` VIDE si `donnees.roues_validees` ne reconnaît pas l'empreinte de la séquence
     (un homonyme non validé refuse aussi) ; le reste de la séquence joue ; WARNING au journal et
     message `{name, raison: "non_validee_sim"}` sur `roues_refusees` (StringTime,
     `qos.volatile(10)`). Paramètre `exiger_validation_roues` d'`animations_node`, **vrai par
     défaut**, mis à faux par `sim.launch.py` seul et ignoré hors domaine 43 : il faut bien pouvoir
     jouer en sim ce qu'on vient y valider. C'est la seule barrière pour une retouche faite sur le
     robot (édition activée) ou un fichier posé à la main sur le Pi. Son trou : elle se découvre
     en scène — d'où la première.
   - **Conséquence à connaître avant d'activer l'édition sur le robot** : une retouche SANS roues
     faite sur le vrai robot y joue tout de suite, sans sim (c'est le but du réglage, borné par le
     contrat) ; elle passera la porte au rapatriement. Une retouche DES roues y est écrite, mais sa
     piste ne jouera qu'après rapatriement, visionnage en sim et redéploiement — le verdict porte
     l'avertissement `roues_a_valider_en_sim`.
   - Topics ajoutés au contrat et à l'inventaire gravé : `VALIDATION_SIM`, `VALIDATION_SIM_DEMANDE`,
     `ROUES_REFUSEES`.
8. **Écriture, dans cet ordre** (échec à une étape = `erreur_ecriture`, cible intacte ; le FICHIER
   écrit est le fichier de séquence, le PNG, ou — pour `expression`, `lumiere`, `brique` — le
   fichier à plusieurs entrées relu, l'entrée posée par la fonction pure `donnees.poser_entree`
   (ordre des autres entrées conservé, entrée neuve en fin), puis réécrit EN ENTIER) :
   (a) `replace`, et toute écriture dans un fichier à plusieurs entrées : copie de l'ancien fichier
   dans `json/backup/<AAAA-MM-JJ>/<kind>__<nom, « / » et espaces en « _ »>__<HHMMSS>__<id>.<ext>` ; ≥ 200 fichiers dans le
   dossier du jour → `quota_jour` ; (b) ligne ajoutée + `fsync` au **journal des éditions non
   rapatriées** `json/backup/EDITIONS-EN-ATTENTE.jsonl` : `{t, id, kind, name, mode, sha256,
   sauvegarde}` — AVANT l'écriture : un crash laisse au pire une ligne en trop, jamais une
   retouche inconnue du journal ; (c) contenu sérialisé `json.dumps(content, indent=4,
   ensure_ascii=False) + "\n"` (ordre des clés conservé ; pour une image, les octets reçus tels
   quels) dans `json/backup/.tmp/<id>` (`fsync`) — **jamais sous `sequences/` ni sous
   `medias/visuals/`**, dont les chargeurs lisent tout fichier, voir les faits ; (d) `os.replace` vers la cible,
   `fsync` du dossier ; (e) fichiers et dossiers créés prennent l'uid/gid de `json/`
   (`os.chown`, `PermissionError` ignorée) : rien n'appartient à root dans l'arbre du PC.
   Rotation : au-delà des **30** dossiers datés les plus récents (`^\d{4}-\d{2}-\d{2}$`), les plus
   anciens sont effacés ; `.tmp/` vidé au démarrage du nœud. Premier passage sur un fichier
   formaté à la main = diff de mise en forme, une fois : accepté.
9. **Rechargement à chaud** : `animations_node` s'abonne à `data_edit_result` ; sur `ok` +
   `kind == "sequence"` + `nom_valide`, il appelle `AnimationManager.recharger_sequence(name)`,
   qui RELIT le fichier du disque (le message ne porte aucun contenu : un verdict forgé ne fait
   que relire un fichier), remplace l'entrée de `sequences_name`, purge puis repose celle de
   `sequences_key`, reconstruit `random_animation_sequence`. Fichier illisible = log ERROR,
   ancienne version gardée. Une séquence en cours finit sur ses pistes déjà construites
   (`Track.emissions` au départ) : aucune piste ne change en plein jeu. Le même verdict fait
   relire le registre des validations (décision 7 ter). **Visage et lumières, même principe** :
   `lights_node` (robot) et `face_sim` (sim) s'abonnent au verdict ; `expression` ou `image` →
   `Face.recharger()` relit `expressions.json` et le SEUL fichier image nommé (illisible = ERROR,
   ancienne image gardée) ; `lumiere` ou `brique` → `Lights.recharger()` relit `robot_lights.json`
   et `lights_base.json`. L'affichage en cours n'est pas touché : la nouvelle version s'applique à
   la commande suivante. `leds_sim_node` : même abonnement seulement s'il lit ces fichiers (à
   relever par l'implémenteur). Tests gravés : après rechargement, l'entrée retouchée a sa
   nouvelle valeur et une entrée voisine est inchangée.
10. **Activation : un seul drapeau, `DATA_EDIT`, OFF par défaut partout.** Compose sim
    `DATA_EDIT=${DATA_EDIT:-false}` → `launch-sim-in-docker.sh` → argument `data_edit` de
    `sim.launch.py` → `enabled` de l'écrivain et `data_edit_enabled` du pont. Robot : même
    variable dans le compose ARM, lue par `robot_app.launch.py`, posée par le mot-clé `environment:`
    de la tâche « Recreate the project container » depuis `edition_donnees: false` de `machines/robot/machine.yml`.
    **Pas de garde de domaine** (à la différence de la répétition : éditer sur le vrai robot EST
    le but), mais **`edition_donnees` reste `false` dans le dépôt à la fin de L1d** : le passer à
    `true` est une décision de David, après sa validation du lot et une relecture adverse (Fable).
    Qui peut écrire : quiconque publie sur le domaine ROS du robot — même frontière de confiance
    que tous les topics d'actionneurs aujourd'hui (réseau du robot) ; par le web, la session
    « writer » et son jeton. Ce qui borne les dégâts : drapeau, contrat (bornes roues comprises),
    porte sim (roues non validées jamais jouées sur le robot), sauvegarde, journal.
11. **Pont web** : nouveau type WebSocket `data_edit` (writer seul ; parseur pur
    `_parse_data_edit` dans `web_protocol.py` : forme + taille, constante dupliquée et égalité
    gravée par test, motif du package) → publication sur `data_edit` par un publisher créé
    SEULEMENT si `data_edit_enabled` ; `data_edit` n'entre dans aucune `WHITELIST` (un `cmd`
    générique ne peut pas le publier). `data_edit_result`, `validation_sim` et `roues_refusees` entrent dans
    `TOPICS_FLUX`. Lecture : `GET /api/data?kind=<kind>` → liste triée des noms, chacun avec
    `rejeu` et `roues` (`a_jour`, `a_faire`, `heritee`, ou absent) lus au registre ; `&name=…` →
    `{name, content, sha256}` (base64 pour une image ; nom validé par `nom_valide`, 404 sinon).
    Second type WebSocket, `valider_roues` (writer seul), publié sur `validation_sim_demande` par
    un publisher créé SEULEMENT en domaine 43. `build_hello` gagne `data_edit` et `validation_sim`
    (défaut `False`). La lecture du contenu par ROS (télécommande) = L4.
12. **Éditeur de la page scène** (`scene.html`/`scene.js`), panneau `<details>` masqué si
    `hello.data_edit` est faux — **tout au même endroit** : sélecteur de famille (séquence,
    expression, lumière, brique), liste, « Charger », zone de texte JSON, champ nom, « Envoyer »
    (`replace` avec le sha chargé si le nom est celui chargé, sinon `create`), « Rejouer » (publie
    `animation`, `face` ou `robot_lights` avec le nom, par le `cmd` existant ; rien pour une
    brique), ligne de verdict (code, détails, avertissements ; vert/rouge). **Envoi d'image** :
    choix d'un fichier PNG, zone (bouche/œil), nom, aperçu agrandi du fichier choisi, « Envoyer
    l'image » — la page ne juge rien, c'est le robot qui valide (décision 4) et son refus
    s'affiche comme les autres. Pas de dessin (décision 3). **En sim seulement**
    (`hello.validation_sim`) : chaque nom porte son état (« rejouée », « à rejouer », « roues à
    valider », « roues héritées ») et le bouton « Valider les roues pour le robot » apparaît pour
    une séquence rejouée dont la piste roues attend. JSON illisible = erreur locale, rien n'est
    envoyé ; pas de verdict du même `id` en 5 s = « pas de réponse du robot ».
13. **Retour vers git — le Pi ne garde jamais une retouche que le dépôt ignore** :
    - `deploy/rapatrier-editions.yml` (`-e target_group=robot`) : renomme le journal en
      `EDITIONS-EN-ATTENTE.rapatriement.jsonl` (les retouches suivantes ouvrent un journal
      neuf) ; refuse si un des fichiers visés a une modification locale non commitée
      (`git status --porcelain -- <fichier>`), sans rien copier ; tire du Pi chaque séquence et
      chaque image vers `data/` ; pour `expression`, `lumiere`, `brique`, tire le fichier du Pi dans
      un dossier temporaire et n'en reporte QUE les entrées du journal dans le fichier du PC
      (`donnees.poser_entree` — tirer le fichier entier écraserait une entrée commitée sur le PC
      et pas encore déployée) ; lance les quatre tests de données et celui des images (rouge =
      arrêt, journal laissé en attente) ; `test_validations_sim.py` rouge n'arrête PAS : c'est
      attendu, le script affiche « N élément(s) à rejouer en sim : machines/sim/rejouer-modifiees.sh » ; copie chaque fichier rapatrié dans
      `json/backup/<date>/<dossier>__<nom>__rapatrie.json` et archive le journal en
      `json/backup/<date>/EDITIONS-rapatriees-<HHMMSS>.jsonl` ; affiche `git status --short
      data/json` et « relis, commite, déploie ». **Il ne commite pas.**
    - **Garde de déploiement** : première tâche du rôle `synchronise` (`donnees_dir` défini,
      exécutée aussi en `--check`) : un `EDITIONS-EN-ATTENTE*.jsonl` non vide sur le Pi → `fail`
      « N édition(s) non rapatriée(s) : ansible-playbook -i hosts rapatrier-editions.yml … ».
      Échappatoire explicite `-e ecraser_editions=true` : le journal est alors archivé en
      `EDITIONS-ecrasees-<HHMMSS>.jsonl` (les sauvegardes restent sur le Pi).
    - `ecart-pi.sh` : volet **(c)** « éditions non rapatriées : N » (rouge si N > 0, avec la
      commande) ; le `--check` du volet (a) est rouge aussi, par la garde.
    - **Seconde garde, juste après** : celle des validations sim (décision 7 ter), sans
      échappatoire.
    - Copie des données : `--exclude=/backup/` (le journal d'une sim du PC ne part jamais sur le
      Pi) ; `.gitignore` : `data/json/backup/`. En sim, la retouche tombe directement dans
      `data/json/` du PC : `git diff` la montre, rien à rapatrier.
14. **JSON de la télécommande : 61 supprimés, 10 restent jusqu'à L4** (corrige le « 71 » du §1).
    Supprimés (`git rm`) : `json/sequences/**` (41), `json/backup/`, `json/projects_lights/` (3),
    et les 16 fichiers de la racine autres que `expressions.json`, `lights_base.json`,
    `lights_methods.json`. Restent : ces 3 et `json/playlists/` (7). Test gravé
    `controller/tests/unit/test_json_restants.py` : la liste exacte des 10, et
    `ControlJsonManager()` se construit (`monkeypatch.setitem(config, JSON_DIRECTORY, …)` vers
    `legacy/dadou_control_ros/json/` : sur l'hôte, le chemin par défaut est celui du Pi), chaque
    playlist se charge. Les fenêtres d'édition mortes ne sont pas touchées
    (L4). Rien n'est effacé sur un Pi de télécommande (rsync sans `--delete`).
    **Revue après l'élargissement du périmètre : décision inchangée.** Expressions et lumières
    s'éditent désormais à travers le robot, et les copies de la télécommande ne suivront pas —
    c'est déjà le cas (15 expressions chez elle, 37 chez le robot) et rien ne s'y aggrave. Les
    synchroniser serait écrire un second chemin d'édition, ce que L1d supprime ; les effacer
    casserait `ControlJsonManager`. Le test grave la LISTE des 10, pas leur contenu ; aucun `kind`
    ne les vise ; la télécommande neuve lira le catalogue (L4).
15. **Preuve sim** : `machines/sim/validate-data-edit.sh` (domaine 43 exigé ; sim lancée avec
    `DATA_EDIT=true ANIMATIONS=true FACE=true`), compteur gravé **13** ajouté à `fumee.sh` :
    (1) création de `tmp-l1d/l1d-retouche` → `ok`, fichier présent, nom au catalogue en ≤ 5 s ;
    (2) retouche (`neck` à 0.37) → `ok`, octets du fichier = attendu, sauvegarde présente, 2 lignes
    au journal ; (3) `animation "l1d-retouche"` → `animation_state` porte le nom ET `neck` reçoit
    0.37 (le rechargement est prouvé) ; (4) `faces` vers une expression inconnue → `contrat`,
    fichier inchangé ; (5) `name` = `../x/y` puis `tmp-l1d/../../x` → `nom_invalide`, aucun fichier
    créé hors cible ; (6) roues HORS bornes, trois demandes — consigne 0.95, dernière image
    `[0.2, 0.2]`, image `{"speed": 100}` → `contrat` chaque fois, message gravé, aucun fichier ;
    (7) roues DANS les bornes — `tmp-l1d/l1d-roues`, `duration` 4000, `wheels` `[[0.1, [0.2, 0.2]],
    [0.5, [0, 0]]]` → `ok` avec l'avertissement `roues_a_valider_en_sim` ; jouée : `cmd_vel` non
    nul observé, puis nul à la fin ; **la durée pendant laquelle `cmd_vel` est resté non nul est
    écrite au rapport** (constat « impulsion ou tenue », pas un critère) ; (8) `base_sha256` faux →
    `conflit` ; (9) demande de 131 073 octets → `trop_gros` ; (10) image : un PNG 24×16 RVB 8 bits
    en `mouth/l1d-bouche` → `ok`, fichier présent ; le même en zone `eye` → `contrat` ; des octets
    qui ne sont pas un PNG → `contrat` ; (11) expression `l1d visage` qui montre cette image → `ok`,
    au catalogue (`faces`) en ≤ 5 s ; publiée sur `face`, `face_sim` l'affiche sans erreur
    (rechargement prouvé) ; (12) lumière `l1d lumiere` chaînant deux briques existantes → `ok`, au
    catalogue ; avec une brique inconnue → `contrat` ; (13) porte sim : `valider_roues` sur
    `l1d-roues` interrompue en cours de jeu → `non_rejouee` ; rejouée jusqu'au bout → tampon
    `rejeu` au registre ; `valider_roues` → tampon `roues`, `origine_roues: "sim"`.
    Le script sauvegarde puis restaure `expressions.json`, `robot_lights.json` et
    `validations-sim.json`, efface ce qu'il a créé (dossier `tmp-l1d/`, image, sauvegardes, lignes
    du journal) : `git status --porcelain` identique avant et après. La barrière de jeu (7 ter) ne
    se prouve pas en sim, où elle est levée : elle est gravée en test hôte (décision 16).
16. **Tests hôte, valeurs GRAVÉES** (`packages/didier_core/test/unit/test_data_edit.py`, sur
    `tmp_path`, horloge injectée) : octets exacts du fichier écrit et son sha256 en littéral, pour
    chacun des cinq kinds ; nom exact de la sauvegarde ; ligne exacte du journal ; un cas par code
    de la décision 2 ; rotation à 31 dossiers ; `.tmp/` vide après succès et après échec ; rien de
    neuf sous `sequences/` ni `medias/visuals/` après un refus ; une entrée posée ne change pas les
    octets canoniques des entrées voisines. `test_donnees.py` : chaque borne roues à sa valeur
    limite (0.89 passe, 0.9 refuse ; 60 000 ms passe, 60 001 refuse ; 300 000 passe, 300 001
    refuse), empreintes en littéral. `test_validation_sim.py` (logique pure, horloge injectée) :
    tampon posé / refusé pour chaque critère. `test_animation_manager.py` : séquence à roues non
    validée → piste roues vide, autres pistes jouées, refus émis ; validée → piste jouée.
    **Mutations à jouer et à lister au rapport (chacune doit rougir)** : `VITESSE_ROUES_MAX` portée
    à 1.0 ; règle d'arrêt final retirée ; plafond de tenue retiré ; commande texte acceptée dans
    une piste roues ; contrôle de taille d'image inversé (bouche ↔ œil) ; contrôle CRC du PNG
    retiré ; regex du nom relâchée ; sauvegarde sautée ; ligne de journal sautée ; une règle du
    contrat retirée de `donnees.py` ; drapeau ignoré ; temporaire sous `sequences/` ; tampon
    `rejeu` posé sur un jeu interrompu ; validation des roues acceptée sans rejeu ; observateur
    actif hors domaine 43 ; barrière de jeu ignorée (roues non validées jouées) ; l'une et l'autre
    garde Ansible retirée (`test_arborescence.py` grave leur présence et leur place avant la copie
    des données, ainsi que `--exclude=/backup/`).
17. **Cinq sous-étapes, une porte chacune, fusionnées une à une — ≈ 14 h** (≈ 8 h avant
    l'amendement ; le périmètre élargi en coûte ≈ 3, la porte sim ≈ 3) :
    - **L1d-1 (Opus, ≈ 4 h)** — contrat pur des cinq kinds et bornes roues, empreintes et lecture
      du registre (pures ; registre absent = tout est « à faire »), correction des deux séquences
      (décision 7), écrivain + journal, topics, rechargements (séquences, visage,
      lumières), tests et mutations, `validate-data-edit.sh` épreuves 1 à 12, fumée. Porte : 6
      suites vertes, épreuve 12/12, namespace 5/5 (nouveau nœud sous le namespace), fumée verte.
    - **L1d-2 (Opus, ≈ 3 h)** — porte sim : écriture du registre, observateur, validation des
      roues, barrière de jeu, `rejouer-modifiees.sh`, registre initial (≈ 50 min de machine en
      tâche détachée), `test_validations_sim.py`, épreuve 13. Porte : épreuve 13/13, suites vertes,
      registre complet, mutations de la porte rouges, fumée verte.
    - **L1d-3 (Opus, ≈ 3 h)** — pont web + éditeur (quatre familles, envoi d'image, états et bouton
      de validation). Porte de l'étude, en sim : une retouche faite depuis la page scène arrive
      dans `json/`, « Rejouer » la joue et la tamponne ; une image envoyée s'affiche dans
      `face_sim` ; un JSON ou un PNG hors contrat affiche son refus ; drapeau OFF = panneau absent ;
      `test_web_protocol.py` étendu.
    - **L1d-4 (Opus, ≈ 3 h)** — rapatriement (par entrée, images), les deux gardes, `ecart-pi.sh`
      (c), exclusions, drapeau du compose ARM. Porte, **Pi hors robot, aucun actionneur** :
      déploiement par défaut → une demande reçoit `edition_desactivee` ; `-e edition_donnees=true` →
      une retouche de séquence, une d'expression, une image ; `ecart-pi.sh` ROUGE (c),
      `deploy-pios.yml` REFUSE, rapatriement, `git diff` montre les trois ; déploiement REFUSÉ par
      la seconde garde tant que `rejouer-modifiees.sh` n'est pas passé, accepté après (puis
      `git checkout` : ce sont des retouches d'essai), redéploiement par défaut, `ecart-pi.sh` VERT
      sur robot ET vision.
    - **L1d-5 (Sonnet, ≈ 45 min)** — décision 14 + doc. Porte : suite télécommande verte, test des
      10 restants, liens Markdown morts = 0.
    Orchestration Opus ; David valide après L1d-3 (le nouveau mode d'édition) et tranche
    l'activation sur le robot après L1d-4 et la relecture adverse.
18. **Interdits (toutes sous-étapes)** : toucher `wheels_bridge`, `twist_mux.yaml`,
    `twist_deadman`, `wheels_node`, ou la publication des pistes dans `animations_node` (seuls y
    entrent l'abonnement, l'appel de rechargement et — exception nommée — la piste roues
    construite vide pour une séquence non validée, décision 7 ter : elle ne peut que RETIRER un
    mouvement) ; écrire hors des cibles de la décision 3, de `json/backup/` et du registre ; écrire
    le registre ailleurs qu'en domaine 43 ; une échappatoire à la garde des validations ; un second écrivain (toute écriture passe par `traiter`) ; recopier une
    règle du contrat au lieu d'appeler `donnees.py` ; `edition_donnees: true` dans le dépôt ;
    domaine 42 depuis le PC ; `git add -A`, `git push`, commit dans la plage sans commit ;
    extinction du poste.
19. **Ce que L1d supprime** : les contrats de séquence, d'expression et de lumière écrits dans les
    tests (remplacés par l'appel du module), et avec eux `imageio` comme juge de la taille d'une
    image ; la tolérance des commandes texte et des dicts dans une piste roues de séquence ; 61 JSON de la télécommande ; `data/json/backup/maker_fair.json` ;
    l'écrasement silencieux d'une retouche par un déploiement.
20. **Doc vivante, à chaque sous-étape** : `docs/interfaces.md` (deux topics, demande, verdict,
    codes), README de `didier_web` et de `theatre_contrats`, `data/README.md`,
    `deploy/README.md` + `docs/ansible-ecarts.md` (garde, rapatriement), `docs/operations.md`
    (« Retoucher une séquence, une expression, une lumière », « Envoyer une image », « La porte
    sim : rejouer, valider les roues », « Rapatrier avant de déployer », épreuve et fumée),
    `legacy/dadou_control_ros/README.md`, README racine, tableau de bord ; CLAUDE.md listés au
    rapport, appliqués par l'orchestrateur.

### L1e — renommages `didier_*` et déplacement dans `packages/`

`robot` → `didier_core`, `robot_drive` → `didier_drive`, `robot_web` → `didier_web`,
`robot_sim`/`robot_description`/`robot_bringup`/`robot_rehearsal` → `didier_*`, `vision` →
`didier_vision`, `robot_interfaces` → `theatre_interfaces` ; chaque package déplacé de
`legacy/…` vers `packages/<nom>` avec `git mv` (historique suivi), compose/Dockerfiles/launch
mis à jour ; `machines/sim/` reçoit le compose de la sim. Porte : V-R3 21/21 **depuis
`machines/sim/`**, Ansible déploie depuis `packages/` (dry-run `--check` vert).

#### L1e — conception détaillée (06/11, Fable) : quatre étapes, la sim verte à chacune

**Pourquoi L1e passe AVANT L1d (écart d'ordre assumé, 06/11)** : L1d demande une conception
validée par David ; L1e est mécanique et ne dépend pas de L1d. Et le roulage au sol attend
désormais la refonte électrique : geler le déménagement jusqu'au protocole caméra le
bloquerait des semaines. Tout se fait sur la branche `l1-namespace-catalogue` ; la fusion
dans `main` reste verrouillée par le protocole caméra (L1b), inchangé.

**Faits relevés le 06/11** :
- 6 packages ament bien formés vivent dans `legacy/dadou_robot_ros/conf/ros2_dependencies/` :
  `robot_drive` (13 fichiers suivis), `robot_web` (17), `robot_sim` (12), `robot_description`
  (5), `robot_bringup` (3), `robot_rehearsal` (25). Une trentaine de fichiers hors `.md`
  citent ce chemin (compose sim/arm/x86, Dockerfiles, 3 `conftest.py`, ~10 tests qui lisent
  des fichiers par chemin, 2 rôles Ansible, quelques sources).
- Sur un Pi, la disposition est `ros2_ws/src/<package>/` à plat : Ansible y copie
  `conf/ros2_dependencies/*` ET `packages/*`. **Cette disposition côté Pi ne change pas**
  dans L1e-1 ni L1e-2 (seuls les noms changent en L1e-2).
- ⚠️ La tâche Ansible « packages communs » copie TOUT `packages/` sur CHAQUE machine
  (sauf `packages_sim_only`). Y déménager les packages du robot sans rien changer les
  enverrait sur le Pi vision et la télécommande, dont le `colcon build` (tout `src/`)
  échouerait sur leurs dépendances (twist_mux, ros_gz…).
- Le package `robot` (cœur) n'a PAS la forme ament : code dans `legacy/dadou_robot_ros/robot/`,
  `setup.py`/`package.xml` dans `conf/ros2/`, assemblés par montages Docker ; la lib
  `dadou_utils_ros` y est montée comme sous-dossier. Idem `vision` et `controller`. Leur
  déménagement est une étape à part (L1e-3), pas un `git mv`.

**Les quatre étapes** (chacune : commit(s), tests, sim, doc ; on ne commence pas la suivante
si la porte n'est pas franchie) :

| Étape | Quoi | Porte |
|---|---|---|
| **L1e-1** | Les 6 packages ament déménagent dans `packages/` **sans changer de nom** ; Ansible passe à une **liste de packages par machine** | pytest verts ; V-R3 21/21 ; namespace 5/5 ; catalogue 4/4 ; `ansible-playbook --syntax-check` |
| **L1e-2** | Renommage des 6 : `robot_drive`→`didier_drive`, `robot_web`→`didier_web`, `robot_sim`→`didier_sim`, `robot_description`→`didier_description`, `robot_bringup`→`didier_bringup`, `robot_rehearsal`→`didier_rehearsal` (dossier, package, module Python, launch, share) | mêmes portes + A1 14/14 ; `grep` des anciens noms = 0 hors études et historique |
| **L1e-3** | `robot`→`packages/didier_core`, `vision`→`packages/didier_vision` (forme ament vraie), `robot_interfaces`→`theatre_interfaces` ; sort de la lib `dadou_utils_ros` à décider | conception séparée (touche ~tous les imports ; place de la lib = arbitrage) |
| **L1e-4** | `machines/sim/` reçoit le compose de la sim ; `machines/<hôte>/` porte les listes de packages ; Ansible déploie depuis `packages/` + `machines/` | V-R3 21/21 **depuis `machines/sim/`** ; dry-run `--check` sur un Pi allumé |

##### L1e-1 — spec FERMÉE (implémenteur Sonnet)

1. `git mv legacy/dadou_robot_ros/conf/ros2_dependencies/<p> packages/<p>` pour les 6 ;
   le dossier `conf/ros2_dependencies/` disparaît (vide). **Aucun renommage**, aucun
   changement de contenu des packages au-delà des chemins qu'ils citent eux-mêmes.
2. **Compose et Dockerfiles côté PC** (sim, x86 robot) : les 6 packages se montent et se
   copient depuis `packages/<p>`, **avec le motif déjà posé par L1a** pour
   `theatre_contrats`/`robot_interfaces` (volumes `../../../../../packages/<p>` ;
   `additional_contexts` nommés + `COPY --from=<p>`). Pas de nouveau motif. Les chemins
   DANS les conteneurs (`/home/ros2_ws/src/<p>`) ne changent pas.
3. **Compose et Dockerfiles ARM** (robot, vision, télécommande) : la disposition sur le Pi
   ne change pas → ne modifier que ce qui cite réellement l'ancien chemin PC (souvent des
   commentaires). Ne rien « améliorer ».
4. **Ansible — liste de packages par machine** (rôle `synchronise`) : la tâche « packages
   communs » ne copie plus l'arbre `packages/` entier ; elle boucle sur
   `{{ packages | default(packages_default) }}` et copie `{{ packages_dir }}/<p>/` vers
   `{{ ros2_ws }}/src/<p>/` (mêmes exclusions). `vars/main.yml` : `packages_default:
   [theatre_contrats, robot_interfaces]` ; la variable `packages_sim_only` est SUPPRIMÉE
   (une liste explicite la remplace). `hosts` : l'hôte robot (`r`) déclare `packages:` =
   les 2 communs + les 6 déménagés — **exactement ce que le Pi reçoit aujourd'hui**
   (aucun changement de comportement ; le tri « sim-only hors du Pi » est L1e-4). La
   tâche qui copiait `conf/ros2_dependencies/` (conditionnée par un `stat`) est supprimée
   avec son `stat` ; le rôle `ros_dependencies` : le lire, le corriger ou le signaler s'il
   est mort. Commentaires français qui disent POURQUOI la liste est explicite (le
   `colcon build` d'un Pi compile tout `src/`).
5. **Tests et conftest** : chemins mis à jour (les 3 `conftest.py`, `packages/didier_jeu/test`,
   les tests qui lisent launch/yaml/xacro par chemin, les listes gravées de
   `test_namespace_contract.py`). Un test gravé nouveau, dans
   `legacy/dadou_robot_ros/robot/tests/unit/test_arborescence.py` : (a)
   `conf/ros2_dependencies` n'existe plus ; (b) chacun des 6 packages est dans `packages/`
   avec `package.xml` ; (c) dans `ansible/hosts`, la liste `packages` de l'hôte robot est
   égale à la liste gravée des 8 ; (d) tout package cité dans une liste `packages`/
   `packages_default` existe dans `packages/`.
6. **Scripts et sources** qui citent le chemin (`gen.py` du monde chantiers,
   `servos_logic.py`, `control_static.py`, `chat_node.py`, `vision.launch.py`…) : corriger
   le chemin ou le commentaire, sans toucher à la logique.
7. **Doc vivante** : `README.md` racine (table de migration : L1b/L1c faits sur la
   branche, L1e-1 fait), `packages/README.md` (les 6 arrivés, encore sous leur ancien
   nom), `legacy/dadou_robot_ros/docs/operations.md`, `architecture.md`, README des
   packages déplacés, tableau de bord `chantiers.md` (ligne « Architecture globale »).
   Les études (`etude-*.md`) et les fiches d'incident sont de l'HISTOIRE : ne pas les
   réécrire. `CLAUDE.md` : ne pas y toucher (liste dans le rapport ce qu'il faut y changer).
8. **Interdits** : modifier la logique d'un nœud ; toucher `twist_mux.yaml`,
   `wheels_bridge_node.py`, `twist_deadman`, `wheels_node` au-delà d'un chemin en
   commentaire ; renommer quoi que ce soit ; `git push` ; ssh ; exécuter Ansible
   (seulement `--syntax-check`).
9. **Porte L1e-1** : pytest robot (≥ 1543 + nouveaux), télécommande, vision, contrats,
   jeu verts ; sim depuis la copie de travail : `validate-rehearsal-chantiers.sh` 21/21,
   `validate-namespace.sh` 5/5, `validate-catalogue.sh` 4/4 ;
   `ansible-playbook deploy-pios.yml -i hosts --syntax-check` OK ;
   `grep -rn "ros2_dependencies"` hors `docs/etude-*`, incidents et historique = 0.

##### L1e-2 — spec FERMÉE (implémenteur Opus : le package de la chaîne roues change de nom)

**Table de renommage (la seule ; rien d'autre ne change de nom)** :

| Ancien package | Nouveau | Module(s) Python |
|---|---|---|
| `robot_drive` | `didier_drive` | `robot_drive` → `didier_drive` |
| `robot_web` | `didier_web` | `robot_web` → `didier_web` |
| `robot_sim` | `didier_sim` | `robot_sim_lib` → `didier_sim_lib` |
| `robot_description` | `didier_description` | — |
| `robot_bringup` | `didier_bringup` | — |
| `robot_rehearsal` | `didier_rehearsal` | `robot_rehearsal` → `didier_rehearsal` |

1. **Ce qui change, par package** : le dossier `packages/<ancien>` → `packages/<nouveau>`
   (`git mv`) ; `package.xml` (`<name>`, et les `<depend>` des AUTRES packages qui le
   citent, dont `didier_jeu`) ; `setup.py` (`package_name`, `packages`, `data_files`
   `share/<nom>`, `entry_points` : le MODULE change, le nom de l'exécutable NON) ;
   `setup.cfg` (`lib/<nom>`) ; le fichier marqueur `resource/<nom>` ; le dossier du module
   Python ; tous les `import`/`from` ; `package="…"` dans les launch ; `FindPackageShare`,
   `get_package_share_directory` ; `package://…` et `$(find …)` dans les xacro ; les
   listes `colcon build --packages-select` ; les cibles de montage des compose
   (`/home/ros2_ws/src/<nouveau>`) et les `additional_contexts`/`COPY` ; `ros2 launch
   <pkg>` / `ros2 run <pkg>` dans les scripts, la liste blanche de processus du régisseur,
   `launch_cmd` de `ansible/hosts`, la liste `packages` de l'hôte robot.
2. **Ce qui NE change PAS (gravé)** : aucun nom de topic, de nœud, d'exécutable, de
   paramètre, d'argument de launch, de fichier à l'intérieur d'un package, d'image ou de
   conteneur Docker, de dossier de journaux. Le package `robot` (cœur), `vision`,
   `controller`, `robot_interfaces`, `theatre_contrats`, `didier_jeu` gardent leur nom
   (L1e-3). Le modèle gz s'appelle toujours `dadou_robot`, les fichiers
   `dadou_robot*.urdf.xacro` aussi.
3. ⚠️ **PIÈGE `robot_description`** : c'est AUSSI le nom STANDARD ROS du paramètre et du
   topic qui portent l'URDF (`robot_state_publisher` : paramètre `robot_description` ;
   `ros_gz_sim create -topic robot_description` ; variable Python locale du launch). Ces
   usages-là NE SONT PAS le package : les laisser tels quels. Seuls changent
   `FindPackageShare("robot_description")`, les chemins, `package.xml`, les montages. Un
   remplacement aveugle fait disparaître le robot de la sim sans erreur claire.
4. **Nettoyage des Pi (Ansible, rôle `synchronise`)** : le rsync n'efface rien — après le
   renommage, les anciens `src/robot_*`, `build/robot_*`, `install/robot_*` resteraient
   sur le Pi et `colcon build` compilerait anciens ET nouveaux. Nouvelle variable
   `packages_retires` (liste gravée des 6 anciens noms) dans `vars/main.yml` et une tâche
   `file: state=absent` (avec `become: yes` : build/install appartiennent à root) qui
   boucle sur `src/`, `build/`, `install/` pour chaque nom retiré, AVANT la copie des
   packages. Commentaire : pourquoi (doublons compilés), et que la liste ne se vide jamais
   (un Pi resté éteint doit pouvoir rattraper).
5. **Tests** : mise à jour des chemins/imports ; `test_arborescence.py` étendu — (a) les 6
   nouveaux noms existent dans `packages/` avec un `package.xml` dont `<name>` est égal
   au nom du dossier ; (b) aucun des 6 anciens noms n'existe dans `packages/` ; (c)
   `packages_retires` est égal à la liste gravée des 6 anciens ; (d) la liste `packages`
   de l'hôte robot est égale à la nouvelle liste gravée ; (e) le marqueur
   `resource/<nom>` de chaque package ament_python porte le nom du package. Contrôle par
   mutation : au moins 3 mutations (renommer un dossier, un `<name>`, un marqueur) font
   rougir.
6. **Doc vivante** : `README.md` racine, `packages/README.md`, README de chaque package,
   `operations.md`, `architecture.md`, `interfaces.md`, tableau de bord. Études, fiches
   d'incident, veille, journaux : HISTOIRE, ne pas réécrire. `CLAUDE.md` : ne pas y
   toucher, lister dans le rapport les commandes à changer.
7. **Interdits** : modifier la logique d'un nœud ; changer `twist_mux.yaml` (contenu),
   `wheels_bridge_node.py`, `twist_deadman`, `wheels_node` au-delà des imports et chemins ;
   `git push` ; ssh ; exécuter Ansible (seulement `--syntax-check`).
8. **Porte L1e-2** : pytest robot, télécommande, vision, contrats, jeu verts ; sim depuis
   la copie de travail (image reconstruite) : V-R3 **21/21**, A1 **14/14**, namespace
   **5/5** (il relit les paramètres de twist_mux : c'est la preuve que le share du package
   renommé est trouvé), catalogue **4/4**, animation `parle` jouée ;
   `ansible-playbook … --syntax-check` OK ; pour chacun des 6 anciens noms,
   `git grep -w <ancien>` ne rend que : études/incidents/veille, la liste
   `packages_retires` + son test, la table de renommage de cette spec, et — pour
   `robot_description` seulement — les usages paramètre/topic du point 3 (les lister dans
   le rapport).

##### L1e-3 — conception détaillée (07/11, Fable) : le cœur, la vision, les interfaces et la lib deviennent de vrais packages

**Faits relevés le 07/11** :
- `robot` (cœur) n'a pas la forme ament : code dans `legacy/dadou_robot_ros/robot/` (nodes,
  actions, visual, sequences, move, diagnostic, db, `robot_config.py`, `robot_static.py`,
  **112 fichiers de tests** dans `robot/tests/`), `setup.py`/`package.xml`/`setup.cfg`/
  `resource/` dans `conf/ros2/`, montés par Docker sous `/home/ros2_ws/src/robot/` avec
  `json/` (72 fichiers), `medias/` (389), `db/`, `conf/`. `find_packages()` y trouve `robot`
  ET `dadou_utils_ros` (lien symbolique `legacy/dadou_robot_ros/dadou_utils_ros → ../dadou_utils_ros`,
  copié par rsync `copy_links`). `vision` et `controller` sont bâtis pareil (3 symlinks).
- `robot_config.py` : `PROJECT_DIRECTORY = /home/ros2_ws/src/robot/` (données `json/`,
  `medias/`, `db/`, `conf/` dessous) ; sur l'hôte, repli = le parent du dossier du package.
  Déplacer le code sans toucher ça casserait les tests hôte (le parent deviendrait
  `packages/didier_core/`).
- `dadou_utils_ros` = 40 fichiers Python (sous-paquets `com`, `lcd`, `utils`, `audios`,
  `files`, `fonts`…) + `ansible/` + `jenkins/` + `conf/` + 4 tests. 120 fichiers l'importent.
  Elle disparaît à L5 (59 % morte) : jusque-là elle garde son nom.
- `robot_interfaces` : 72 fichiers hors .md + 13 scripts/docs qui tapent `robot_interfaces/msg/StringTime` en CLI.
- La sentinelle de build `robot/change` est un fichier SUIVI (dette), lue par
  `launch-ros-in-docker.sh` à `/home/ros2_ws/src/robot/robot/change`.

**Décisions (ne pas rouvrir)** :
1. **Quatre sous-étapes, une porte chacune, dans cet ordre** : 3a lib, 3b interfaces, 3c cœur,
   3d vision. Jamais deux renommages dans le même commit.
2. **Les DONNÉES ne bougent pas en L1e-3** : `json/`, `medias/`, `db/`, `conf/` restent dans
   `legacy/dadou_robot_ros/` (idem `medias/`, `models/`, `mediamtx/` de la vision) et aux mêmes
   chemins conteneur (`/home/ros2_ws/src/robot/…`, `/home/ros2_ws/src/vision/…`). Leur
   déménagement vers `data/` est L1e-4 (avec `machines/`). Seul le CODE bouge.
3. **Racine des données = variable d'environnement** : `DIDIER_DATA_DIR` (défaut
   `/home/ros2_ws/src/robot/`) lue par `robot_config.py` à la place du repli « parent du
   package » ; `DIDIER_VISION_DATA_DIR` (défaut `/home/ros2_ws/src/vision/`) pour
   `vision_config`. Les compose la posent explicitement ; les `conftest.py` hôte la posent vers
   `legacy/dadou_robot_ros/` (chemin calculé depuis le dépôt). C'est le SEUL changement de
   logique du lot, testé (valeur gravée).
4. **3a — `packages/dadou_utils_ros`** (ament_python, nom INCHANGÉ) : `package.xml`, `setup.py`
   (`packages=find_packages(include=['dadou_utils_ros', 'dadou_utils_ros.*'])`), `resource/`,
   le code dans `packages/dadou_utils_ros/dadou_utils_ros/` (git mv des .py et sous-paquets),
   ses 4 tests dans `test/`. **Ne déménagent PAS** : `ansible/` (→ `deploy/` en L1e-4),
   `jenkins/`, `conf/`, `docs/`, `scripts/` (restent dans `legacy/dadou_utils_ros/`). Les 3
   symlinks sont supprimés ; `find_packages` des 3 setup.py n'incluent plus que leur propre
   module ; `dadou_utils_ros` entre dans `packages_default` (toutes les machines) ; compose/
   Dockerfiles montent/copient `packages/dadou_utils_ros` (motif L1a) ; `conftest.py` des 3
   dépôts ajoutent `packages/dadou_utils_ros` au `sys.path`. Porte : 5 suites pytest + lib ;
   sim : namespace 5/5, catalogue 4/4, `parle` joué.
5. **3b — `robot_interfaces` → `theatre_interfaces`** (CMake) : dossier, `package.xml`,
   `CMakeLists.txt` (`project(theatre_interfaces)`), tous les `from robot_interfaces.msg`
   (robot, vision, télécommande, didier_jeu, didier_web, didier_drive, didier_rehearsal, contrats),
   les `robot_interfaces/msg/StringTime` des scripts `validate-*.sh`, `pub.sh`,
   `collect-incident.sh`, `calibre-distance.sh`, `capture_seance.py`, les compose (montage,
   contextes), Ansible (`packages_default`, `packages_retires` += `robot_interfaces`), doc
   vivante + CLAUDE.md (listés au rapport). Noms de MESSAGES inchangés (`StringTime`,
   `LedState`, `HardwareStatus`, `TurtleTuple`). Porte : pytest ; sim rebuild : namespace,
   catalogue, **A1 14/14** (son pilote rclpy importe le type), `parle`. Opus (wheels_bridge
   importe StringTime).
6. **3c — `robot` → `packages/didier_core`** : forme ament vraie (`package.xml`, `setup.py`,
   `setup.cfg`, `resource/didier_core`, module `didier_core/` = git mv de `legacy/dadou_robot_ros/robot/`
   SANS `tests/` ni `change`, tests → `packages/didier_core/test/` avec `pytest.ini` et
   `conftest.py`), entry points inchangés en NOM (`wheels_node = didier_core.nodes.wheels_node:main`…),
   `from robot.` → `from didier_core.` partout (68 fichiers + tests), `package="robot"` des
   launch → `didier_core`, `ros2 run robot …` des scripts/docs → `ros2 run didier_core …`.
   Sentinelle : `packages/didier_core/change` (GITIGNORÉE — fin de la dette du fichier suivi),
   lue à `/home/ros2_ws/src/didier_core/change` par `launch-ros-in-docker.sh`, écrite par le
   Makefile. Compose ARM/x86/sim : montage `packages/didier_core → /home/ros2_ws/src/didier_core`,
   plus de montage de `setup.py`/`package.xml` ni de `robot/robot` ; `json/medias/conf/db`
   restent montés sous `/home/ros2_ws/src/robot/`. Ansible : `packages` de l'hôte robot +=
   `didier_core`, `dadou_utils_ros` ; nouvelle liste gravée `chemins_retires_robot` (sous
   `src/robot/` : `robot/`, `dadou_utils_ros/`, `setup.py`, `package.xml`, `setup.cfg`,
   `resource/`, `test/` ; plus `build/robot`, `install/robot`) nettoyée AVANT la copie — sans
   ça colcon trouverait encore un package `robot` via l'ancien `package.xml`. Porte : pytest
   (1558+ depuis `packages/didier_core`), télécommande, contrats, jeu ; sim rebuild :
   namespace 5/5, catalogue 4/4, **V-R3 21/21**, **A1 14/14**, `parle` ; `git grep -w robot`
   comme NOM DE PACKAGE = 0 (le mot `robot` seul est partout ailleurs : le test gravé vise
   `package="robot"`, `ros2 run robot`, `src/robot/robot`, `from robot.`). **Opus** (déplace
   wheels_node, twist_deadman n'est pas là mais le launch de prod si).
7. **3d — `vision` → `packages/didier_vision`** : même recette que 3c (module `didier_vision`,
   tests → `test/`, `DIDIER_VISION_DATA_DIR`, `chemins_retires_vision`, `packages` de l'hôte
   vision += `didier_vision`), `launch_cmd` de `hosts`. Porte : pytest vision 991 ; banc x86
   vision (`legacy/dadou_vision_ros/conf/docker/x86`) construit et `vision_status` visible
   sous `/didier/` dans la sim (domaine 43). Sonnet.
8. **Télécommande (`controller`)** : reste dans `legacy/dadou_control_ros/` (L4 la réécrit) mais
   suit 3a et 3b (symlink supprimé, imports `theatre_interfaces`). Ses tests restent verts.
9. **Interdits** : modifier la logique d'un nœud (hors décision 3) ; toucher
   `twist_mux.yaml` ; renommer un topic/nœud/exécutable ; déplacer des données ; `git push` ;
   ssh ; exécuter Ansible (seulement `--syntax-check`).
10. **Doc vivante** : README racine (table de migration), `packages/README.md`, README-contrat
    de chaque package créé (rôle, données attendues, variables d'env), `operations.md`
    (commandes de test : `cd packages/didier_core && <venv legacy> -m pytest`),
    `architecture.md`, tableau de bord. CLAUDE.md : listés au rapport, appliqués par Fable.

#### L1e-4 — conception détaillée (08/11, Fable) : le dépôt prend sa forme cible, les Pi ne bougent pas

**État au 08/11** : L1e-3 terminé — tout le CODE est dans `packages/`. Restent sous `legacy/` :
les données du robot (`json/` 72 fichiers, `medias/` 112 Mo, `db/` 3 SQLite — tous suivis),
la conf machine du robot (`conf/` : docker arm/sim/x86, scripts, rpi, systemd, logging, listes de
paquets), celle de la vision (`conf/`, `mediamtx/`), Ansible (`legacy/dadou_utils_ros/ansible`),
et la doc. Les dossiers cibles `data/`, `deploy/`, `machines/`, `docker/` n'ont qu'un README.

**La décision qui simplifie tout : seul le DÉPÔT change ; les chemins sur les Pi et dans les
conteneurs restent IDENTIQUES** (`~/ros2_ws/src/robot/{json,medias,db,conf}`,
`~/ros2_ws/src/vision/{conf,medias,db}`, `DIDIER_DATA_DIR`/`DIDIER_VISION_DATA_DIR` inchangées,
`deploy_sha_file` du launch inchangé, voix et secret aux mêmes places). Pourquoi : chaque
consommateur de chemin (launch, config, Ansible `secrets`/`telechargements_hote`, scripts
d'épreuve) reste intouché ; le risque se réduit aux SOURCES des rsync et des montages. Renommer les
chemins Pi/conteneur est le travail de L2 (un conteneur par machine, nouvelles images) — pas avant.

**Décisions (ne pas rouvrir)** :
1. **Quatre sous-étapes, une porte chacune, fusionnées une à une** : 4a `deploy/`, 4b `data/`,
   4c `machines/`, 4e ménage. **Pas de 4d `docker/`** : un Dockerfile de base commun ARM/x86 est
   une nouvelle conception (robot et vision n'ont pas les mêmes dépendances), c'est L2 ;
   `docker/` garde son README qui le dit.
2. **Le déploiement hors robot sur les Pi FAIT PARTIE de chaque sous-étape** (consigne du 07/11 ;
   lève l'ambiguïté qui a arrêté l'implémenteur de 3d) : Ansible exécuté sur `192.168.1.131` et
   `.151` (aucun actionneur), `ecart-pi.sh` vert sur les deux à la fin. Toujours interdit : un
   robot aux roues câblées avant le protocole caméra.
3. **4a — `deploy/`** : `git mv legacy/dadou_utils_ros/ansible deploy` (playbooks, `hosts`, `vars/`,
   `roles/`, `templates/`, `attendu/`, `ecart-pi.sh`). `vars/main.yml` : `local_projects_dir` =
   `{{ playbook_dir | dirname }}/legacy`, `packages_dir` = `{{ playbook_dir | dirname }}/packages`
   (aujourd'hui trois `dirname`). **Ménage décidé par l'étude (§5.8), fait ici** : suppression des
   rôles orphelins `activate-spi`, `download-install-docker-from-url`, `root_ssh`,
   `ros_dependencies`, `waveshare-screen` (et `set-vim` s'il existe), de `jenkins`, `sonar`,
   `install-ci*.yml`, `configure-local-ci.yml`, `install-test-pios.yml`, `deploy-test-pios.yml`, du
   groupe `integration` de `hosts`, et de `deploy/legacy/` ; `legacy/dadou_utils_ros/jenkins/`
   part avec. Le reste de `legacy/dadou_utils_ros/` (`conf/`, `docs/`, `scripts/`) attend 4e.
   Porte : `--syntax-check` ; `test_arborescence.py` (chemins gravés `deploy/…`) ; déploiement des
   2 Pi depuis `deploy/`, `ecart-pi.sh` vert ×2 ; CLAUDE.md racine (chemin) listé au rapport.
4. **4b — `data/`** : `git mv` de `legacy/dadou_robot_ros/{json,medias,db}` vers
   `data/{json,medias,db}` — le contenu du robot est UNE famille (les JSON référencent les
   médias ; le catalogue les publie ensemble), on ne la coupe pas. **Aucun code ne change.**
   Compose sim/x86/arm : montages `…/data/json:/home/ros2_ws/src/robot/json` (idem medias, db).
   Dockerfile ARM/x86 du robot : `COPY` depuis `data/` (contexte nommé `data`, motif des
   packages) — reconstruction de l'image robot à la fin. Ansible : la synchro « projet » de
   `legacy/dadou_robot_ros/` vers `src/robot/` est REMPLACÉE par deux copies explicites :
   `data/{json,medias,db}` → `src/robot/` (hôte robot seul, variable `donnees_dir`) et
   `legacy/dadou_robot_ros/conf/` → `src/robot/conf/` (jusqu'à 4c) ; plus rien d'autre de
   `legacy/` ne part sur le Pi (docs, essais, firmware, .venv : déchets). `conftest`/tests hôte
   qui posent `DIDIER_DATA_DIR` vers `legacy/dadou_robot_ros/` : la racine de données hôte
   devient `<dépôt>/data/` — et c'est le seul endroit où `json/`, `medias/`, `db/` doivent être
   des enfants directs de la racine, comme sur le Pi (`src/robot/`). La vision n'a pas de
   `data/` : rien de suivi hors `mediamtx/` (conf → 4c) ; sa voix et son `db/` restent des
   fichiers d'exécution posés par Ansible. Porte : pytest 6 suites ; `test_arborescence`
   (`data/` présent, `legacy/dadou_robot_ros/{json,medias,db}` absents, aucune synchro « projet »
   dans le rôle) ; **fumée complète verte sur la branche** (namespace 5/5, catalogue 4/4, `parle`,
   V-R3 21/21, A1 14/14) ; déploiement robot (image reconstruite, catalogue 6 familles, sha
   publié), vision inchangée, `ecart-pi.sh` vert ×2.
5. **4c — `machines/`** : `machines/robot/` ← `legacy/dadou_robot_ros/conf/` SAUF ce qui est sim
   (`docker/sim`, `docker/x8664`, `scripts/{launch-sim-in-docker.sh,validate-*.sh,fumee.sh,
   fumee_page.py,pub.sh}`, `systemd/didier-fumee.*`, `systemd/installer-fumee.sh`) qui va dans
   **`machines/sim/`** (le banc x86 du robot dans `machines/sim/banc-robot/`, celui de la vision
   `legacy/dadou_vision_ros/conf/docker/x86` dans `machines/sim/banc-vision/` — L2 les fondra en
   un compose). `machines/vision/` ← `legacy/dadou_vision_ros/{conf,mediamtx}` ;
   `legacy/dadou_vision_ros/tools/` → `packages/didier_vision/tools/` (il importe le package ;
   non installé). **Variables par machine** : `deploy/hosts` ne garde que l'inventaire
   (groupes, IP, utilisateur, clé, et `machine: robot|vision|…`) ; tout ce qui décrit le
   CONTENU d'une machine (`packages`, `sentinelle_build`, `launch_cmd`, `noeuds_attendus`,
   `dossiers_montes`, `secrets_hote`, `telechargements_hote`, `fichiers_etc`, `unites_systemd`,
   `paquets_hote`, `project_ros_dir`, `project_name`) vit dans **`machines/<machine>/machine.yml`**,
   chargé par `include_vars` au début de `deploy-pios.yml` et `install-pios-lite.yml`. Ansible
   copie `machines/<machine>/` → `src/<project_ros_dir>/conf/` (chemin Pi stable, voir plus
   haut). Chemins qui changent dans les fichiers déplacés : montages relatifs des compose
   (`../../packages/…`, `../../data/…`), contextes des Dockerfiles, `DOCKER_DIR`/
   `CHEMIN_DOCKER_SIM` de `fumee.sh`, `installer-fumee.sh` (ExecStart), `ecart-pi.sh`,
   `docs/ansible-ecarts.md`. **À la fusion** : relancer `machines/sim/installer-fumee.sh` depuis
   main (l'unité pointe sur l'ancien chemin) et vérifier `systemctl --user list-timers`.
   Porte : pytest ; `test_arborescence` (plus de `conf/` sous `legacy/dadou_robot_ros`, plus de
   `conf/`/`mediamtx/` sous `legacy/dadou_vision_ros`, `machine.yml` par hôte, `hosts` sans
   variable de contenu) ; `--syntax-check` ×2 ; **fumée verte lancée par `machines/sim/fumee.sh`**
   ; images ARM robot ET vision reconstruites, déployées, poussées sur le Hub ; `ecart-pi.sh`
   vert ×2 ; première fumée AUTOMATIQUE verte après fusion = la porte finale.
6. **4e — ménage de L1e (peut glisser en L5 si le temps manque, mais se fait en une passe)** :
   `legacy/dadou_robot_ros/docs/` → `docs/` (le tableau de bord devient `docs/chantiers.md`,
   comme le CLAUDE.md l'annonce), avec réécriture des liens et un test qui échoue sur tout lien
   Markdown mort du dépôt ; `legacy/dadou_robot_ros/{essais,firmware}` → `atelier/{essais,firmware}`
   ; `legacy/dadou_robot_ros/ci/` et `legacy/dadou_utils_ros/{conf,docs,scripts,jenkins}` →
   supprimés (rien ne les lit : vérifier par `git grep` avant) ; venvs : un `.venv` à la racine
   (cœur, contrats, jeu, lib, télécommande) et `packages/didier_vision/.venv` (dépendances
   propres), `requirements-test.txt` à la racine ; `legacy/dadou_robot_ros/` et
   `legacy/dadou_vision_ros/` ne contiennent plus que leur README (bandeau « archive ») — ou
   disparaissent si rien ne les référence. `legacy/dadou_control_ros/` reste (L4). Porte :
   pytest 6 suites depuis les nouveaux venvs, lien mort = 0, fumée verte.
7. **Interdits (toutes sous-étapes)** : modifier la logique d'un nœud ; renommer un topic, un
   nœud, un exécutable, un chemin Pi ou conteneur ; toucher `twist_mux.yaml` ; `git push` ;
   `systemctl poweroff/reboot/suspend`, `fumee.sh --et-dodo` ; domaine 42.
8. **Qui** : 4a, 4b, 4c = implémenteur **Opus** (Ansible et déploiement : l'implémenteur Sonnet de
   3d s'est arrêté devant ; 4c touche la sim et les images) ; 4e = Sonnet (mécanique, liens).
   Orchestration Opus, une sous-étape par session, fusion après chaque porte, les Pi branchés.
   Estimation : 4a ≈ 1 h, 4b ≈ 1 h 30, 4c ≈ 3 h (deux images ARM), 4e ≈ 1 h 30.
9. **Doc vivante** à chaque sous-étape : README racine (carte des dossiers : ce qui est VRAI
   maintenant, ligne L1 courte), `packages/README.md`, README de `data/`, `deploy/`,
   `machines/` (rôle, convention `machine.yml`), `operations.md`, `ansible-ecarts.md`, tableau de
   bord ; CLAUDE.md listés au rapport, appliqués par l'orchestrateur.

##### Lot F — fumée nocturne (décidé le 07/11, à faire APRÈS 3b, AVANT 3c)

**Pourquoi** : chaque lot paie aujourd'hui ses propres épreuves (≈ 1 h d'agent) ; et
l'environnement bouge sans commit (paquets Gazebo à la reconstruction, Docker, nombre de
conteneurs) — vécu le 06/11 : V-R3 de 21/21 à 18/21 sans régression du code.

**Décisions** :
1. **Zéro token** : un script shell (`conf/scripts/fumee.sh`, puis `machines/sim/` en L1e-4)
   sous minuterie systemd utilisateur sur le PC de David. Aucun agent : la fumée mesure et
   compare à des valeurs gravées, elle ne juge pas. Un agent n'intervient qu'à la demande,
   pour lire une nuit rouge.
2. **Déclenchement — OPPORTUNISTE, jamais une plage à réserver** (David : « je n'arrive jamais
   à garder une plage vide ») : une fumée est DUE dès qu'un commit entre dans `main` après la
   dernière fumée verte (sha gravé dans la dernière page), ou après 7 jours sans fumée (dérive
   de l'environnement). Tant qu'elle est due et que le PC est allumé, une minuterie systemd
   utilisateur réessaie toutes les 30 min : chaque essai mesure la charge (load average) et le
   facteur temps réel 20 s ; si charge trop haute ou RTF < 0,8, il ne lance RIEN et note
   « reporté » ; sinon il déroule. Un PC en usage normal (chats, navigation) suffit — mesuré :
   RTF 0,86 pendant le travail courant ; 0,49 avec deux agents + reconstruction d'image.
   Variante **« fumée et dodo »** : `fumee.sh --et-dodo` enchaîne la fumée puis `systemctl
   poweroff` — à lancer en allant se coucher, le PC s'éteint seul ≈ 45 min après, la page
   attend au matin. Règle humaine : l'agent AVERTIT David après chaque fusion qu'une fumée est
   due, et le prévient si 2 jours passent sans créneau trouvé.
3. **Contenu, dans l'ordre, arrêt au premier rouge bloquant** : reconstruction de l'image si
   un Dockerfile a changé (3-5 min) → sim headless + colcon (1 min) → sonde RTF 20 s (rouge
   si < 0,8 : le reste n'est pas fiable) → `validate-namespace.sh`, `validate-catalogue.sh`,
   animation `parle` (3 min) → chaîne roues + régisseur + regard puis
   `validate-rehearsal-chantiers.sh` (16 min) → sim relancée, `validate-jeu-a1.sh` (16 min).
   ≈ 40 min.
4. **Sortie** : une page `docs/fumee/AAAA-MM-JJ.html` + `index.html` (même facture que la
   veille) : sha testé, RTF, vert/rouge par épreuve avec le compteur (21/21, 14/14…), lien
   vers les journaux copiés hors conteneur (les journaux de séance meurent avec lui). Commit
   automatique de `docs/fumee/` seulement.
5. **Déploiement hors robot** : hors de la fumée (il faut les Pi branchés, consigne de
   David du 07/11) mais scripté de la même façon (`deploy-hors-robot.sh` : Ansible + contrôles
   nœuds/mux/sha/catalogue, ≈ 5 min par Pi), lancé par David ou par un lot.
6. **Taille** : 1 à 2 passes Sonnet (tout existe, il s'agit d'enchaîner) ; porte = une nuit
   verte complète lue le matin, et une nuit rouge provoquée (ex. RTF forcé) correctement
   signalée.

##### Outils de qualité retenus pour la CI (décidé le 07/11, à porter par le lot L2)

Pas de SonarQube ni de Jenkins (serveurs à maintenir, décidés sortants en L5). Dans le premier
palier de CI (GitHub Actions, tests unitaires, gratuit sur dépôt public) : **ruff** (lint +
format), **pytest-cov** (voir ce qu'aucun test ne traverse, pas un pourcentage à atteindre),
**mypy sur le code de NOUVELLE GÉNÉRATION seulement** — dès maintenant dans la cible : `packages/
theatre_contrats`, `packages/didier_jeu`, et tout package neuf (gabarit L3 avec annotations dès
la naissance) ; legacy exclu jusqu'à réécriture —, **ansible-lint**, **hadolint** ; **vulture**
ponctuellement (liste du code mort pour L5) ; **pip-audit** mensuel.

## 3. Ordre, délégation, gates

| Sous-lot | Qui | Gate avant le suivant |
|---|---|---|
| L1a | implémenteur Opus (spec fermée, touche 3 dépôts + compose) → relecture Opus distincte | tests + V-R3 + grep |
| L1b | implémenteur Opus (launch, sécurité roues = Opus minimum) | sim ; caméra au prochain robot |
| L1c | implémenteur Sonnet (publication, tests) | topic + test |
| L1d | conception Fable (protocole) puis implémenteur Opus (écriture de fichiers sur le robot = sécurité des données) | porte de l'étude |
| L1e | implémenteur Sonnet (mécanique) + vérification V-R3 | V-R3 depuis machines/sim |

David valide après L1a (c'est le premier code du mono-dépôt) et après L1d (c'est le
nouveau mode d'édition).

## 4. Hors L1 (pour ne pas y toucher par inadvertance)

Le chemin roues (`wheels_bridge` compris) ; la télécommande neuve (L4) ; les packages
d'autonomie (`didier_corps_sur`, `didier_perception`, `didier_jeu` — lots A, en parallèle,
dans `packages/` dès qu'ils existent) ; la CI mono-dépôt (vient avec L2).
