# theatre-robot — mono-dépôt du système Didier (CLAUDE.md unique)

Lot L0 en cours (2026-11-02) : les anciens dépôts vivent dans `legacy/`, **tels quels**, avec
leurs propres `CLAUDE.md` qui restent la référence pour travailler dans leur code :
`legacy/dadou_robot_ros/CLAUDE.md` (règles de sécurité roues, commandes sim, priorités).
Ce fichier-ci grossira à mesure que `legacy/` se vide ; il ne doit jamais dupliquer ce que
`README.md` (la carte) et `docs/` disent.

## Règles qui valent dès maintenant pour TOUT le dépôt

- Sécurité roues : celles de `legacy/dadou_robot_ros/CLAUDE.md`, sans exception.
- Toute proposition de déplacement dit ce qu'elle SUPPRIME ; la sim doit marcher en fin de lot.
- Noms de packages : `didier_*` / `<appareil>_*` / `theatre_*` ; noms de topics **relatifs**
  (namespace par robot), jamais absolus.
- Documentation dans le même lot que le code ; état des chantiers dans `docs/chantiers.md`
  (encore dans `legacy/dadou_robot_ros/docs/` pendant L0).
- Dépôt public : aucun secret, jamais (les secrets vivent hors git, voir l'étude architecture).

## Comment travailler ici (depuis le 02/11)

- Ouvrir **ce dossier** (`theatre-robot/`) dans IAction / Claude Code — plus jamais les anciens
  `dadou_*_ros`, qui sont des archives (bandeau en tête de leur README).
- Le code et la sim sont encore sous `legacy/<ancien nom>/` : les commandes des CLAUDE.md
  de legacy s'exécutent depuis là (`cd legacy/dadou_robot_ros && .venv/bin/pytest -q` ;
  sim : `legacy/dadou_robot_ros/conf/docker/sim`). Le venv de test a été recréé dans legacy.
- Déploiement Ansible : `legacy/dadou_utils_ros/ansible` (il rsync depuis `legacy/`).
  Depuis L1e-1 (06/11) : les packages ROS viennent de `packages/`, copiés par LISTE EXPLICITE
  par machine (`packages:` de l'hôte dans `ansible/hosts`, défaut `packages_default`) — un
  package absent de la liste n'arrive jamais sur le Pi.
- Skill `/diag` : `.claude/skills/diag` (copié de l'ancien dépôt ; ses chemins visent encore
  `docs/incidents/` de legacy — à déplacer avec la doc).
