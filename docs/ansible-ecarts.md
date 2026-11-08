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
- ~~Image `dd` de chaque SD~~ **abandonnée** (David, 07/11 : « ce ne sera jamais la bonne version ») :
  la restauration rapide = Ansible en une commande + images Docker publiées sur le Hub.
- Jamais sur le robot câblé roues avant le protocole caméra (verrou L1b).

## État au 07/11 au soir — lot « Ansible nickel » FAIT (branche `l1e-3`)

Mode d'emploi : `legacy/dadou_robot_ros/docs/operations.md` §« Déployer / réinstaller un Pi ».
En bref, depuis `deploy/` à la racine du dépôt (ex `legacy/dadou_utils_ros/ansible/`, déménagé
au lot L1e-4a du 08/11) :
`ansible-playbook -i hosts deploy-pios.yml -e target_group=robot|vision` (rien avant, rien
après), puis `./ecart-pi.sh robot|vision` (vert = code 0).

L1e-4a a aussi fait le ménage décidé par l'étude (§5.8) : rôles orphelins (`activate-spi`,
`download-install-docker-from-url`, `root_ssh`, `ros_dependencies`, `waveshare-screen`),
Jenkins/Sonar (rôles, `group_vars/jenkins_server`, variables, `legacy/dadou_utils_ros/jenkins/`),
playbooks de CI et de test, groupe `integration` de `hosts`, anciens playbooks de `legacy/`.
Rien ne change sur les Pi : mêmes chemins, mêmes `attendu/*.txt`.

| Plan | État |
|---|---|
| 1. Gestes manuels du déploiement | **fait** : utilisateur + clé (groupe `didier_pi`) et IP par défaut dans `hosts` ; chemins de l'arbre déduits du playbook (un worktree déploie sans `-e`) ; squelette `ros2_ws` + `chown` de `src/` avant le rsync ; sentinelle posée à chaque synchronisation (noms gardés : ceux que lisent les scripts d'entrée, plus personne ne les tape) ; `up -d --force-recreate` ; attente des nœuds attendus + `running` / `restarts=0`, sinon échec. `chemins_retires_lib` : build/install effacés seulement s'ils contiennent encore la lib embarquée (build incrémental : 4,6 s vision, 21 s robot). |
| 2. Secrets | **fait** : rôle `secrets` (`~/.config/didier/` → Pi, 600, `no_log`, sans diff ; échec clair si une source ou une clé de `secret.example` manque). `secrets.env` (clé Anthropic) **non poussé** : aucun consommateur sur les Pi tant que la bascule de `chat_node` n'est pas faite. |
| 3. Système | **fait** dans `deploy-pios.yml` (rôle `config-hote`, rejoué à chaque déploiement donc vu par la détection) : `avahi-utils` + `avahi-alias-didier.service` (robot), `/etc/asound.conf` (vision, versionné dans `dadou_vision_ros/conf/rpi/asound.conf`). `~/.asoundrc` : c'était déjà le gabarit du rôle `usb-audio` (identique sur les deux Pi), désormais rejoué au déploiement. `.bashrc` : voir la correction du relevé ci-dessous ; `set-bashrc` rendu idempotent et rejoué au déploiement. Rsync : `.venv/`, `.pytest_cache/`, workspace x86, `conf/secret`, sentinelles commitées exclus ; `.venv` déjà poussés effacés (269 Mo robot, 342 Mo vision). |
| 4. Images sur le Hub | **FAIT le 07/11** : `dadouuu/dadou-robot-arm:latest` (0,83 Go) et `dadouuu/dadou-vision-arm:latest` (1,15 Go, reconstruite le jour même) publiées ; jeton Docker Hub `didier-pi` (Read & Write, sans expiration, révocable sur app.docker.com) dans `~/.config/didier/dockerhub-token` du PC, les 2 Pi connectés. **Republier = seulement quand un Dockerfile ou une liste de paquets change** (le code est monté, pas dans l'image) : sur le Pi concerné, `cd ~/ros2_ws/src/<robot\|vision>/conf/docker/arm && sudo docker compose -f docker-compose-arm.yml build && sudo docker push dadouuu/dadou-<robot\|vision>-arm:latest`, puis redéployer. Un Pi reflashé doit d'abord `docker login -u dadouuu --password-stdin < jeton` pour POUSSER (tirer ne demande rien : dépôts publics). Automatisation prévue : GitHub Actions (lot L2). |
| 5. Détection d'écart | **fait** : `ecart-pi.sh <groupe>` = (a) `--check --diff` + (b) inventaire comparé à `attendu/<groupe>.txt` (gravés le 07/11). Pas encore branché dans un `deploy-hors-robot.sh` (n'existe pas). Fichiers de `/etc` hors Ansible : non inventoriés (trop de bruit de l'OS ; à revoir si besoin). |
| 6. Preuve | **partielle faite** : `~/ros2_ws` effacé sur la vision, une commande, tout revient (secret : même taille, même sha256). **Reste** : reflash des deux cartes par David. |

Deuxième passage d'un déploiement : seules restent « changed » la **sentinelle** et la
**recréation du conteneur**, voulues (chaque déploiement recompile et redémarre). En
`--check` (détection d'écart), 0 tâche « changed » sur les deux Pi.

**Outils d'atelier de la vision : TRIÉS le 07/11 avec David** (« on supprime tout ce qui n'est
pas utile ») : `~/didier_proto` (proto d'octobre, remplacé par `chat_node`), `~/bench-v1`,
`~/xvf_host`, `~/mic_test`, la vieille sauvegarde `asound.conf`, 2 photos → archivés sur le PC
(`~/Nextcloud/dev/didier/archives/vision-pi-outils-atelier-2026-11-07.tgz`, 109 Mo, sans venv ni
secret) puis effacés du Pi ; lignes `?` et secret `didier_proto` retirés. Parler à Didier en
simulation avec retour visuel = le **banc PC** (operations.md § « Banc PC »), sur le PC : il
n'utilisait aucun de ces outils.

**Image changée = build/ périmé (trouvé le 08/11, L1e-3d)** : `build/` et `install/` sont des
dossiers de l'HÔTE ; après reconstruction de l'image de la vision (libfastcdr plus récente), le
cache CMake de `build/theatre_interfaces` visait l'ancienne bibliothèque et plus rien ne
compilait. Corrigé dans le rôle `conteneur` : l'identifiant de l'image du build est noté dans
`~/ros2_ws/.image-du-build` ; image différente → `build/` et `install/` vidés avant la
recréation (colcon complet au démarrage). Idempotent : même image = rien.

**L1e-4b (08/11) : le robot ne reçoit plus le projet entier.** Les données du robot sont dans
`data/` à la racine ; l'hôte robot (variable `donnees_dir` de `hosts`) reçoit deux copies
explicites — `data/{json,medias,db}` → `src/robot/{json,medias,db}` et
`legacy/dadou_robot_ros/conf/` → `src/robot/conf/` — au lieu de la copie « projet » (qui poussait
aussi docs 139 Mo, essais, firmware, `CLAUDE.md`, réglages d'éditeur…) et de la copie à plat de
`conf/ros2/` (`launch.txt`). Ces déchets ont été effacés du Pi au premier déploiement (liste
conditionnelle `chemins_retires_legacy_robot`, 18 entrées) avec le workspace colcon de la fumée
(`conf/docker/sim/workspace`, 8 Mo, ajouté à `dechets_rsync`) : `src/robot/` = `conf db json
medias`, rien d'autre. Chemins Pi et conteneur inchangés. La vision garde sa copie « projet »
(L1e-4c). Sha publié : `-dirty` ne regarde plus que `chemins_deployes` (`packages data
legacy/dadou_robot_ros/conf legacy/dadou_vision_ros deploy`) — une fumée en cours (journaux non
suivis sous `docs/fumee/`) le rendait faussement sale. Image ARM du robot reconstruite sur le Pi
(contexte nommé `data`), redéployée (build/ et install/ vidés par le rôle `conteneur`, colcon
complet), poussée sur le Hub (`e1420fc9…`). Porte : RECAP `failed=0` ×2, conteneurs `running`
restarts=0, catalogue 6 familles, sha `5895e24` sans `-dirty`, `ecart-pi.sh` vert ×2 sans
regraver `attendu/`. Piège vu : une connexion multiplexée d'Ansible (`~/.ansible/cp/`) restée
pendue a figé un `ecart-pi.sh` 10 min sur la première tâche `become` ; tuer le mux et relancer
suffit.

**Voix de Didier (trouvé le 07/11 au soir)** : `medias/voices/didier.onnx` n'existait que sur la
vision, déposée à la main ; `medias/` est bind-monté et MASQUE la voix que le Dockerfile met dans
l'image ; la preuve à blanc (effacement de `~/ros2_ws`) l'a donc perdue sans qu'aucune épreuve le
voie. Corrigé : `telechargements_hote` (rôle `config-hote`) la télécharge avec empreinte sha256
gravée (= fichiers du proto validé le 10/07). Leçon : la preuve à blanc vérifiait les secrets, pas
les fichiers lourds hors dépôt — `ecart-pi.sh` ne voit que `~` au premier niveau.

**Corrections du relevé ci-dessous** (constatées pendant le lot) :
- `.bashrc` : c'est le robot qui a ses deux blocs ; sur la vision le bloc projet est vide parce
  que `dadou_vision_ros/conf/rpi/project_bash` est vide (rien ne manque côté Ansible). Le rôle
  `set-bashrc` n'était pas idempotent (bloc posé avec `PROJECT=` puis réécrit par lineinfile).
- Sentinelle : `robot/change` et `vision/change` (minuscules) sont **commités** depuis L0. Le
  rsync recréait donc la sentinelle du robot à chaque passage (d'où un robot qui recompilait et
  une vision qui ne recompilait pas : son script lit `CHANGE`).
- `install-pios-lite.yml` lançait `synchronise` en `become` : tout `src/` en root, cause
  probable des code 23 du déploiement suivant. Corrigé, **non rejoué** (pas de reflash).

## Relevé du 07/11 (lecture seule, Pi hors robot)

Robot = Pi 4 de rechange en .131, SD réinstallée le 04/11 ; vision = Pi 5 en .151, SD d'origine.
Les deux en Debian 13 trixie.

### Gestes manuels faits pendant le déploiement de 3b (même jour)

| Geste | Pourquoi | Dans le playbook ? |
|---|---|---|
| `sudo chown -R pi:pi ~/ros2_ws/src` | Docker crée en root les dossiers de montage absents ; rsync suivant en code 23 | non |
| `-e ansible_user=pi --private-key ~/.ssh/keys/didier` | `hosts` ne donne ni utilisateur ni clé pour robot/vision (seul `integration` en a, avec un ancien chemin `~/Nextcloud/divers/keys/didier`) | non |
| `touch` de la sentinelle de build | `chemins_retires_lib` efface `build/` et `install/` de robot ET vision **à chaque déploiement** (pensé pour une fois) : sans sentinelle, rien n'est recompilé et la vision meurt (`Package 'vision' not found`, vécu le 07/11) | non |
| Nom de sentinelle différent par dépôt | robot : `src/robot/robot/change` (devenu `src/didier_core/change` au L1e-3c, 07/11) ; vision : `src/vision/vision/CHANGE` (majuscules) | oui, `sentinelle_build` par hôte (Ansible nickel) ; à unifier au 3d |
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

## Plan du lot (rédigé le 07/11 ; état ci-dessus)

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
