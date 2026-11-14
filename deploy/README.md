# deploy/

Ansible de toutes les machines, à la racine du dépôt depuis le lot L1e-4a (08/11 ; ex
`legacy/dadou_utils_ros/ansible/`). Rien n'a changé sur les Pi : mêmes chemins, mêmes images.

```bash
cd deploy
ansible-playbook -i hosts deploy-pios.yml -e target_group=robot   # ou vision
./ecart-pi.sh robot                                                 # vert = code 0
```

| Fichier | Rôle |
|---|---|
| `deploy-pios.yml` | déploiement courant, une commande (système de l'hôte, rsync, secrets, conteneur recréé et contrôlé) |
| `install-pios-lite.yml` | réinstallation d'un Pi reflashé (Docker, I²C, service), PUIS `deploy-pios.yml` |
| `install-pios-full.yml`, `install-controller-ubuntu.yml` | anciennes installations (Pi OS Full, console Ubuntu/Humble), non rejouées depuis L0 |
| `hosts` | inventaire SEUL (L1e-4c, 11/11) : groupes, IP, utilisateur, clé, et `machine:` par hôte — le contenu (`packages`, `noeuds_attendus`, secrets…) est dans `machines/<machine>/machine.yml`, chargé en `pre_tasks` des playbooks (convention : `machines/README.md`) |
| `vars/main.yml` | chemins de l'arbre déduits du playbook (`machines_dir` = `machines/`, `packages_dir` = `packages/`, `local_projects_dir` = `legacy/` pour les machines pas encore déménagées : un worktree déploie SON arbre), listes de nettoyage des Pi |
| `roles/` | un rôle par geste ; gravés par `packages/didier_core/test/unit/test_arborescence.py` |
| `templates/` | fichiers posés sur les Pi (scripts, unité systemd, ALSA, logging) |
| `ecart-pi.sh`, `attendu/` | détection d'écart Pi ↔ dépôt (voir `docs/ansible-ecarts.md`) |
| `rapatrier-editions.yml`, `rapatrier_editions.py` | L1d-4 : ramène dans `data/` du PC (sans commiter) les éditions faites sur le robot ; à lancer quand la garde du déploiement le demande (`docs/operations.md` § « Rapatrier avant de déployer ») |

Secrets : `~/.config/didier/` du PC, posés par le rôle `secrets` — jamais dans le dépôt ni un log.
Mode d'emploi détaillé : `docs/operations.md` § « Déployer / réinstaller un Pi ».
Ménage de L1e-4a (étude §5.8) : rôles orphelins, Jenkins/Sonar, playbooks de CI et de test,
groupe `integration`, anciens playbooks de `legacy/` — supprimés.
