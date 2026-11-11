# theatre-robot — mono-dépôt du système Didier (CLAUDE.md unique)

Depuis L1e-4e (11/11), `legacy/` ne garde que des README d'archive et deux `CLAUDE.md` qui
restent la référence : `legacy/dadou_robot_ros/CLAUDE.md` (règles de sécurité roues, commandes
sim, priorités) et `legacy/dadou_vision_ros/CLAUDE.md` ; la télécommande vit encore entière dans
`legacy/dadou_control_ros/` (lot L4).
Ce fichier-ci grossira à mesure que `legacy/` se vide ; il ne doit jamais dupliquer ce que
`README.md` (la carte) et `docs/` disent.

## Règles qui valent dès maintenant pour TOUT le dépôt

- Sécurité roues : celles de `legacy/dadou_robot_ros/CLAUDE.md`, sans exception.
- Toute proposition de déplacement dit ce qu'elle SUPPRIME ; la sim doit marcher en fin de lot.
- Noms de packages : `didier_*` / `<appareil>_*` / `theatre_*` ; noms de topics **relatifs**
  (namespace par robot), jamais absolus.
- Documentation dans le même lot que le code ; état des chantiers dans `docs/chantiers.md`.
- Dépôt public : aucun secret, jamais (les secrets vivent hors git, voir l'étude architecture).
- Mission salariée : ni employeur, ni client, ni poste ou réseau de travail dans ce dépôt (règle du CLAUDE.md global, section « Confidentialité de la mission salariée »).
- Jamais d'extinction du poste depuis un agent : ni `fumee.sh --et-dodo`, ni `systemctl
  poweroff/reboot/suspend` (vécu le 07/11 : le PC de David éteint par un essai « à blanc »). Une
  extinction ne se teste qu'avec un FAUX `systemctl` en tête du PATH.

## Choix du modèle

Règle générale dans le CLAUDE.md global (signal en une ligne Opus ↔ Fable). Ici, en plus :
roues, arrêt d'urgence et carte Sécurité = Opus minimum, jamais Sonnet/Haiku ; leur conception
ou une relecture adverse avant le terrain = Fable.

## Comment travailler ici (depuis le 02/11)

- Ouvrir **ce dossier** (`theatre-robot/`) dans IAction / Claude Code — plus jamais les anciens
  `dadou_*_ros`, qui sont des archives (bandeau en tête de leur README).
- Le cœur du robot est `packages/didier_core` depuis L1e-3c (08/11) ; données dans `data/` (`DIDIER_DATA_DIR`),
  conf des machines dans `machines/`. Venvs (L1e-4e) : `.venv` à la racine (cœur, contrats, jeu,
  lib, télécommande) et `packages/didier_vision/.venv`. Tests du cœur :
  `cd packages/didier_core && ../../.venv/bin/python -m pytest -q -o addopts=` (les six suites :
  `docs/operations.md`, CI `.github/workflows/tests.yml`) ;
  sim : `machines/sim/banc-robot` (depuis L1e-4c, 11/11). Vision = `packages/didier_vision` depuis L1e-3d
  (08/11 ; `DIDIER_VISION_DATA_DIR` ; tests : `cd packages/didier_vision &&
  .venv/bin/python -m pytest -q -o addopts=`).
  Télécommande : encore sous `legacy/`.
- Déploiement Ansible : `deploy/` depuis L1e-4a (08/11) ; il rsync `packages/`, `data/` (robot) et
  `machines/<machine>/` ; de `legacy/` seulement les projets pas encore déménagés (télécommande, gants).
  Depuis L1e-1 (06/11) : les packages ROS viennent de `packages/`, copiés par LISTE EXPLICITE
  par machine (`packages:` dans `machines/<machine>/machine.yml` depuis L1e-4c — `deploy/hosts` = inventaire + `machine:` seulement ; défaut `packages_default`) — un
  package absent de la liste n'arrive jamais sur le Pi.
  Depuis L1e-3a (07/11) : la lib `dadou_utils_ros` est un package de `packages/` (dans
  `packages_default` ET la liste de l'hôte robot) ; `chemins_retires_lib` efface sur les Pi les
  anciennes copies embarquées (src/, build/, install/ de robot, vision, controller).
- Déployer un Pi (depuis le 07/11, « Ansible nickel ») : `cd deploy &&
  ansible-playbook -i hosts deploy-pios.yml -e target_group=robot|vision` — UNE commande, aucun
  geste avant/après (utilisateur, clé, IP dans `hosts`), puis `./ecart-pi.sh <groupe>` (vert = 0).
  Secrets : `~/.config/didier/` du PC, posés par le rôle `secrets` — jamais dans le dépôt ni un log.
  Écarts et reste à faire : `docs/ansible-ecarts.md`.
- Skill `/diag` : `.claude/skills/diag` (incidents dans `docs/incidents/`).
