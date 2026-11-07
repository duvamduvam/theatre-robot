# Ansible « nickel » — écarts relevés et plan

**Pourquoi** (David, 07/11/2026) : en cas de panne, il doit pouvoir réinstaller un Pi
rapidement et seul. Ansible fait foi ; tout geste fait à la main pendant un déploiement est une
dette du playbook, pas une note de doc.

**Cadence décidée le 07/11** :
- **À chaque déploiement** : détection d'écart automatique (≈ 1 min) =
  `ansible-playbook … --check --diff` (ce qu'Ansible changerait) + un script d'inventaire
  (paquets apt manuels, services activés, fichiers de `/etc` hors Ansible, crontab, dossiers de
  `~`, images Docker) comparé à une liste gravée dans le dépôt. Tout écart = rouge.
- **De temps en temps, et à chaque grosse mise à jour** (OS, ROS, image Docker) : David
  reflashe les deux cartes, l'agent déroule `install-pios-lite.yml` + `deploy-pios.yml` et
  consigne ici ce qui a manqué ; on comble, on repart de là.
- **Une fois tout vert** : image `dd` de chaque SD = restauration rapide (≈ 10 min, sans Ansible).
- Jamais sur le robot câblé roues avant le protocole caméra (verrou L1b).

## Relevé du 07/11 (lecture seule, Pi hors robot)

Robot = Pi 4 de rechange en .131, SD réinstallée le 04/11 ; vision = Pi 5 en .151, SD d'origine.
Les deux en Debian 13 trixie.

### Gestes manuels faits pendant le déploiement de 3b (même jour)

| Geste | Pourquoi | Dans le playbook ? |
|---|---|---|
| `sudo chown -R pi:pi ~/ros2_ws/src` | Docker crée en root les dossiers de montage absents ; rsync suivant en code 23 | non |
| `-e ansible_user=pi --private-key ~/.ssh/keys/didier` | `hosts` ne donne ni utilisateur ni clé pour robot/vision (seul `integration` en a, avec un ancien chemin `~/Nextcloud/divers/keys/didier`) | non |
| `touch` de la sentinelle de build | `chemins_retires_lib` efface `build/` et `install/` de robot ET vision **à chaque déploiement** (pensé pour une fois) : sans sentinelle, rien n'est recompilé et la vision meurt (`Package 'vision' not found`, vécu le 07/11) | non |
| Nom de sentinelle différent par dépôt | robot : `src/robot/robot/change` ; vision : `src/vision/vision/CHANGE` (majuscules) | à unifier |
| `docker compose up -d` (recréation) | `docker restart` ne relit pas le compose | non |
| Reconstruction de l'image ARM du robot (≈ 35 min sur Pi 4) | image du 04/11 construite AVANT le renommage L1e-2 : elle embarquait `robot_bringup`, `robot_drive`, `robot_interfaces`… compilés à côté des `didier_*` (passé inaperçu au déploiement du matin) | non ; l'image du Hub `dadouuu/dadou-robot-arm:latest` est une Humble de 2024 |

### Ce que les Pi portent hors Ansible

**Les deux**
- `~/.asoundrc` (robot : 04/11 ; vision : 04/07) — origine à retrouver.
- `~/local_packages`, `~/scripts` (scripts `compose-up-*.sh` périmés, purge L5).

**Robot**
- `avahi-alias-didier.service` **ABSENT** : perdu à la réinstallation du 04/11 →
  `didier.local` n'est plus publié. Source versionnée existante :
  `legacy/dadou_robot_ros/conf/systemd/avahi-alias-didier.service`.
- `.bashrc` sans le bloc projet (la vision l'a) : le rôle `set-bashrc` n'a pas tourné, ou pas
  jusqu'au bout, le 04/11.

**Vision**
- **Secrets présents seulement sur le Pi** : `~/ros2_ws/src/vision/conf/secret` (clés
  ChatGPT, Google Cloud, OpenRouter, CometAPI, identifiants MQTT) et `~/didier_proto/secret`
  (OpenRouter). Ignorés par git (correct), mais sans copie ailleurs jusqu'au 07/11 :
  **sauvegardés le 07/11 sur le PC dans `~/.config/didier/` (chmod 600, hors dépôt, hors
  Nextcloud)**, avec la clé API Anthropic (fournisseur LLM par défaut décidé le 07/11).
- `/etc/asound.conf` (26/08 : alias `mixette`, `casque_mic`) + sauvegarde
  `~/asound.conf.bak-avant-micro-camera` : pas dans Ansible (le rôle `usb-audio` ne pose que
  la liste noire ALSA).
- `~/didier_proto` (460 Mo : boucle VAD→whisper→LLM→piper, modèles), `~/bench-v1` (55 Mo),
  `~/xvf_host`, `~/mic_test` : outils d'atelier, à trier (garder = Ansible ; jeter = noter).
- `conf/docker/x86/workspace/` (build x86 du PC) arrive sur le Pi par le rsync : déchet à
  exclure.
- Image `dadouuu/dadou-vision-arm:latest` vieille de 4 mois (le code est monté, elle
  fonctionne ; à reconstruire à la prochaine mise à jour).

## Plan du lot (à faire, Opus)

1. Playbook : utilisateur et clé dans `hosts` (`group_vars`), `chown` avant rsync, sentinelle
   posée par le rôle à chaque synchronisation (nom unique), recréation du conteneur
   (`compose up -d`) en fin de déploiement, `chemins_retires_*` sans effacer à chaque passe
   ce que le build doit refaire (ou sentinelle obligatoire — l'un ou l'autre, pas le hasard).
2. Secrets : rôle qui pousse depuis `~/.config/didier/` et ÉCHOUE clairement si un fichier
   manque ; `secret.example` reste la liste des clés attendues.
3. Système : `avahi-alias-didier`, `/etc/asound.conf` de la vision, `.asoundrc`, bloc
   `.bashrc` — versionnés et posés par `install-pios-lite.yml`.
4. Images : publier les images ARM à jour sur le Hub (aucun secret dedans) pour qu'une
   réinstallation télécharge au lieu de reconstruire 35 min ; reconstruire quand un
   Dockerfile change.
5. Détection d'écart : `--check --diff` + script d'inventaire, dans `deploy-hors-robot.sh`
   (lot F, décision 5).
6. Preuve : David reflashe les deux cartes, on déroule, on consigne ici.
