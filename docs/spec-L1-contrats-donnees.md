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

### L1c — le robot publie catalogue + sha

`didier` publie, latché : `catalogue` (JSON : séquences, expressions, visuels, audios,
relais, lumières — généralisation de `web_catalog.py`) et `deploy_sha` (le sha git écrit par
Ansible au rsync, ou `dev` en sim). La page scène affiche le sha ; la télécommande garde
`BUTTONS_LAYOUT` **mais** un test gravé le compare au catalogue publié (différence = rouge) ;
Ansible écrit `DEPLOY_SHA` au rsync. Porte : en sim, `ros2 topic echo catalogue --once`
rend les 6 familles ; test télécommande vert.

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
