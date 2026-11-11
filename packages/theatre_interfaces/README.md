# theatre_interfaces — les messages ROS du parc Didier

Package **ament_cmake** (génération rosidl) : le type `StringTime` que portent presque tous
les topics applicatifs du parc (robot, vision, télécommande, sim, salle de répétition,
console web, sélecteur de jeu). **Copie UNIQUE** depuis le lot L1a (02/11) — les copies
vision et télécommande ont été supprimées ; renommé depuis `robot_interfaces` au lot L1e-3b
(07/11), noms de messages inchangés.

## Ce qui est généré

| Fichier | Généré | Contenu |
|---|---|---|
| `msg/StringTime.msg` | **oui** | `string msg` (payload JSON), `int64 time` (ms), `bool anim` (drapeau animation) |
| `srv/SetLedPanel.srv` | oui | `bool[] leds` → `bool success` — aucun appelant connu au 07/11 |
| `msg/HardwareStatus.msg`, `msg/LedState.msg`, `msg/TurtleTuple.msg`, `srv/ComputeRectangleArea.srv` | **non** (absents de `rosidl_generate_interfaces`) | fichiers morts, gardés tels quels jusqu'au ménage (L5) |

Le payload de `msg` n'est **pas** décrit ici : c'est le contrat `theatre_contrats`
(codec `theatre_contrats.stringtime`, clés, noms de topics).

## Qui en dépend

- Python : `from theatre_interfaces.msg import StringTime` (cœur, vision, télécommande,
  `didier_drive`, `didier_web`, `didier_rehearsal`, `didier_jeu`, `didier_sim`).
- `package.xml` : `<depend>theatre_interfaces</depend>` (`exec_depend` pour `didier_sim`).
- CLI : `ros2 topic pub /didier/face theatre_interfaces/msg/StringTime "{msg: '\"calib\"'}"`
  (toujours préfixer le namespace, voir `docs/operations.md`).

## Données, variables d'environnement

Aucune. Le package ne lit rien au démarrage.

## Où il arrive

- Sim et bancs x86 : monté (et copié par `COPY --from=theatre_interfaces`) depuis
  `packages/theatre_interfaces` par les compose de `legacy/*/conf/docker/`.
- Pi : rsyncé par Ansible vers `ros2_ws/src/theatre_interfaces` (liste `packages_default`
  et liste `packages` de l'hôte robot) ; l'ancien `robot_interfaces` est effacé de
  `src/`, `build/` et `install/` par `packages_retires` AVANT la copie — sans ça, colcon
  compilerait les deux.
- `colcon build` : la télécommande trouve les en-têtes numpy (bloc `find_package(Python3 …
  NumPy)` facultatif du `CMakeLists.txt`), les autres images compilent sans.

Graver/vérifier : `legacy/dadou_robot_ros/robot/tests/unit/test_arborescence.py` (nom du
package, `project()`, `StringTime` généré, listes Ansible, plus aucun fichier de code ou de
conf qui cite l'ancien nom).
