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

##### Lot F — fumée nocturne (décidé le 07/11, à faire APRÈS 3b, AVANT 3c)

**Pourquoi** : chaque lot paie aujourd'hui ses propres épreuves (≈ 1 h d'agent) ; et
l'environnement bouge sans commit (paquets Gazebo à la reconstruction, Docker, nombre de
conteneurs) — vécu le 06/11 : V-R3 de 21/21 à 18/21 sans régression du code.

**Décisions** :
1. **Zéro token** : un script shell (`conf/scripts/fumee.sh`, puis `machines/sim/` en L1e-4)
   sous minuterie systemd utilisateur sur le PC de David. Aucun agent : la fumée mesure et
   compare à des valeurs gravées, elle ne juge pas. Un agent n'intervient qu'à la demande,
   pour lire une nuit rouge.
2. **Déclenchement** : la nuit (machine calme : les épreuves longues exigent un facteur temps
   réel ≥ 0,8) **si `main` a un commit depuis la dernière fumée verte** (sha gravé dans la
   dernière page) ; plus **une passe forcée par semaine** même sans commit (dérive de
   l'environnement).
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
