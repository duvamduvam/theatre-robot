# medias/audios/ — les sons de Didier ne sont plus ici

Depuis le 14/11 (décision de David du 13/11), **aucun fichier sonore n'est dans ce dépôt public** :
une partie sont des chansons du commerce. Ce dossier est ignoré par git, sauf ce README.

- **Où sont les fichiers** : `~/Nextcloud/dev/didier/medias-prives/audios/` (variable
  `DIDIER_MEDIAS_PRIVES` pour un autre chemin), hors git, synchronisé par Nextcloud, même
  arborescence que l'ancien `data/medias/audios/`.
- **Ce que le dépôt en garde** : le manifeste `data/json/audios-prives.json` (chemin tel que les
  séquences le citent, sha256, taille, durée des wav). Les séquences et les autres JSON citent les
  audios sous leur nom INCHANGÉ.
- **Sur le robot et dans la sim**, les fichiers sont à leur place habituelle
  (`src/robot/medias/audios/`) : copiés par Ansible (rôle `synchronise`), montés en lecture seule
  par la sim.
- **Ajouter un audio** : le déposer dans le dossier privé, puis régénérer le manifeste
  (`docs/operations.md`, « Audios privés »). Ne jamais le poser ici ni ailleurs dans le dépôt :
  `test_audios_prives.py` rougit dès qu'un fichier du manifeste entre dans git, même renommé.

L'historique git n'a pas été réécrit : les anciens commits portent encore ces fichiers.
