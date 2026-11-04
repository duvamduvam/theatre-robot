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
dans git, supprimés du disque et du déploiement).

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
un éditeur **minimal** (une séquence : texte JSON + bouton « envoyer ») — c'est l'outil de
réglage, pas l'éditeur final. Porte (celle de l'étude) : **une retouche faite depuis la
page scène arrive dans `json/` du robot (sim) et est rejouée** ; un payload invalide est
refusé et visible. Les 71 JSON de la télécommande : **supprimés** (ils sont dans git).

### L1e — renommages `didier_*` et déplacement dans `packages/`

`robot` → `didier_core`, `robot_drive` → `didier_drive`, `robot_web` → `didier_web`,
`robot_sim`/`robot_description`/`robot_bringup`/`robot_rehearsal` → `didier_*`, `vision` →
`didier_vision`, `robot_interfaces` → `theatre_interfaces` ; chaque package déplacé de
`legacy/…` vers `packages/<nom>` avec `git mv` (historique suivi), compose/Dockerfiles/launch
mis à jour ; `machines/sim/` reçoit le compose de la sim. Porte : V-R3 21/21 **depuis
`machines/sim/`**, Ansible déploie depuis `packages/` (dry-run `--check` vert).

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
