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

Mode d'emploi : `docs/operations.md` §« Déployer / réinstaller un Pi ».
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
| 3. Système | **fait** dans `deploy-pios.yml` (rôle `config-hote`, rejoué à chaque déploiement donc vu par la détection) : `avahi-utils` + `avahi-alias-didier.service` (robot), `/etc/asound.conf` (vision, versionné dans `machines/vision/rpi/asound.conf` depuis L1e-4c). `~/.asoundrc` : c'était déjà le gabarit du rôle `usb-audio` (identique sur les deux Pi), désormais rejoué au déploiement. `.bashrc` : voir la correction du relevé ci-dessous ; `set-bashrc` rendu idempotent et rejoué au déploiement. Rsync : `.venv/`, `.pytest_cache/`, workspace x86, `conf/secret`, sentinelles commitées exclus ; `.venv` déjà poussés effacés (269 Mo robot, 342 Mo vision). |
| 4. Images sur le Hub | **FAIT le 07/11** : `dadouuu/dadou-robot-arm:latest` (0,83 Go) et `dadouuu/dadou-vision-arm:latest` (1,15 Go, reconstruite le jour même) publiées ; jeton Docker Hub `didier-pi` (Read & Write, sans expiration, révocable sur app.docker.com) dans `~/.config/didier/dockerhub-token` du PC, les 2 Pi connectés. **Republier = seulement quand un Dockerfile ou une liste de paquets change** (le code est monté, pas dans l'image), dans cet ordre (L2a, 14/11) : (1) déployer (le Dockerfile `conf/docker/Dockerfile` arrive sur le Pi) ; (2) sur le Pi, `cd ~/ros2_ws/src/<robot\|vision>/conf/docker/arm && sudo docker compose -f docker-compose-arm.yml build` ; (3) redéployer (`build/` et `install/` vidés, colcon complet ; **vision : le rôle `conteneur` vérifie que le secret n'est pas dans l'image**, rouge sinon) ; (4) avant de pousser, contrôler l'image : vision `sudo docker run --rm --entrypoint test <image> ! -e /home/ros2_ws/src/vision/conf/secret`, robot `sudo docker run --rm --entrypoint ls <image> -A /home/ros2_ws/src/robot/medias/audios` (vide : audios privés exclus) ; (5) `sudo docker push dadouuu/dadou-<robot\|vision>-arm:latest`. Détail et preuves : § L2a ci-dessous. Un Pi reflashé doit d'abord `docker login -u dadouuu --password-stdin < jeton` pour POUSSER (tirer ne demande rien : dépôts publics). Automatisation prévue : GitHub Actions (lot L2). |
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

**L1e-4c (11/11) : `machines/`, et `hosts` ne garde que l'inventaire.** La conf de chaque machine
est `machines/<machine>/` (robot : ex `legacy/dadou_robot_ros/conf/` sans la sim ; vision : ex
`legacy/dadou_vision_ros/{conf,mediamtx}` ; la sim, la fumée et les bancs PC : `machines/sim/`, qui
ne part sur aucun Pi). Le CONTENU d'une machine (packages, launch, nœuds attendus, secrets,
fichiers système…) a quitté `hosts` pour `machines/<machine>/machine.yml`, chargé par
`include_vars` en `pre_tasks` ; `hosts` = groupes, IP, utilisateur, clé et `machine:` (convention :
`machines/README.md`). Le rôle `synchronise` copie `machines/<machine>/` (sans `machine.yml`,
`README.md`, `secret`) dans `src/<robot|vision>/conf/` : **chemins Pi et conteneur inchangés**. La
vision ne reçoit plus sa copie « projet » ; la télécommande, oui (`local_project_dir`, lot L4).
Nettoyage conditionnel au premier déploiement (listes qui ne se vident jamais) :
`chemins_retires_sim` (la partie sim restée dans `src/robot/conf/` — banc x86, scripts de fumée et
de vérification de la sim, minuterie — et `src/vision/conf/docker/x86`) et
`chemins_retires_legacy_vision` (`.github/` mort, docs, requirements, `tools/` — désormais
`src/didier_vision/tools/` —, `mediamtx/` — désormais `conf/mediamtx/`). Gardés exprès :
`validate-cmdvel-protocol.sh` (protocole caméra, tourne dans le conteneur du robot) et
`src/vision/.dockerignore`. **Secret de la vision** : le `.dockerignore` racine du dépôt vision ne
partait plus sur le Pi ; il est devenu `machines/vision/docker/arm/Dockerfile-arm.dockerignore`,
que BuildKit lit à la place d'un `.dockerignore` racine — prouvé sur le Pi par une construction
d'essai sans `.dockerignore` racine (le secret factice reste dehors), et l'image neuve ne contient
pas `conf/secret`. Images reconstruites sur les Pi et poussées : vision `b3d364ac…`, robot
`40652ca9…` ; redéploiement = `build/` et `install/` vidés par le rôle `conteneur`, colcon complet,
`running` restarts=0, robot : 17 nœuds sous `/didier/` (16 + `vision_status`), catalogue 6
familles. À la fusion : relancer `machines/sim/installer-fumee.sh` depuis main (l'unité visait
`legacy/dadou_robot_ros/conf/scripts/fumee.sh`).

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

## Éditions du robot : deux gardes et le rapatriement (lot L1d-4, 13/11)

Écart fermé : le rsync des données écrasait sans rien dire une retouche faite sur le Pi (et une
création y restait sans jamais revenir dans git). Mode d'emploi : `docs/operations.md`
§« Rapatrier avant de déployer ».
- **Garde 1** (première tâche du rôle `synchronise`, aussi en `--check`) : un journal
  `json/backup/EDITIONS-EN-ATTENTE*.jsonl` non vide sur le Pi → refus, avec la commande
  `rapatrier-editions.yml`. Échappatoire explicite `-e ecraser_editions=true` (journal archivé en
  `json/backup/<date>/EDITIONS-ecrasees-<HHMMSS>.jsonl`, sauvegardes gardées sur le Pi).
- **Garde 2** (juste après, sur le PC, sans échappatoire) : `python3 -m theatre_contrats.donnees
  non-validees data/` non vide → refus (porte sim, `machines/sim/rejouer-modifiees.sh`).
- Copie des données : `--exclude=/backup/` et `--exclude=/.tmp/` (sauvegardes, journal et
  temporaires de l'écrivain ne voyagent jamais).
- `ecart-pi.sh` : volet **(c)** « éditions non rapatriées : N » ; le volet (a) est rouge aussi
  (la garde 1 fait échouer le `--check`).
- Drapeau `DATA_EDIT` du conteneur : `edition_donnees: false` de `machines/robot/machine.yml`,
  passé par la tâche « Recreate the project container » ; essai ponctuel `-e edition_donnees=true`.
  Limite : un `docker compose up` lancé hors Ansible (à la main) le remet à faux.
- Prouvé le 13/11 sur les deux Pi hors robot (épreuve au rapport du lot, `ecart-pi.sh` vert ×2).

**Audios privés (14/11, décision de David du 13/11) : les sons quittent le dépôt public.** Les
254 audios vivent dans `medias_prives_dir`/audios/ du PC (`deploy/vars/main.yml` :
`$DIDIER_MEDIAS_PRIVES`, défaut `~/Nextcloud/dev/didier/medias-prives`), le dépôt n'en porte que
le manifeste `data/json/audios-prives.json`. Rôle `synchronise`, hôte robot seul (`donnees_dir`) :
- la copie de `data/medias` exclut `/audios/` (elle ne peut ni y écrire ni en effacer) ;
- (1) sur le PC, `python3 -m theatre_contrats.donnees verifier-audios data <dossier privé>` : le
  dossier privé doit être EXACTEMENT le manifeste (chaque audio, son sha, rien en plus), sinon
  refus avec la commande qui régénère le manifeste ;
- (2) rsync du dossier privé → `src/robot/medias/audios/` (chemin Pi inchangé), sans `--delete` ;
- (3) sha256 relus sur le Pi, jugés sur le PC (`verifier-sommes`) ; un fichier du Pi hors
  manifeste est signalé, pas refusé (rien n'est effacé sur le Pi : un audio retiré du dossier
  privé y reste, à effacer à la main si on le veut).
- `ecart-pi.sh` : volet **(d)** « audios privés : N au manifeste, présents avec leur sha256 » sur
  une machine qui porte les données, « sans objet » ailleurs. `attendu/` non regravé.
- Prouvé le 14/11 : déploiement robot puis vision `rc=0`, `ecart-pi.sh` vert ×2 ; sur le Pi robot
  254 audios, mêmes chemins et mêmes sha que le dossier privé.
- Reste hors de ce lot : l'image ARM du robot poussée sur le Hub le 08/11 (`e1420fc9…`) a été
  construite avec `COPY --from=data medias/` — elle contient les audios d'alors ; les Dockerfile
  ARM et x86 du robot copient toujours `medias/` (sur le Pi, `medias/audios/` est rempli). Aucune
  décision prise ici sur la publication des images.

## L2a — un Dockerfile par machine (14/11, branche `l2`)

Spec L2, décisions 4, 5, 6, 16. `conf/docker/Dockerfile` (robot, vision) remplace
`conf/docker/arm/Dockerfile-arm` ; contexte principal = `conf/docker/`, rien n'en est copié ; tout
arrive par contextes nommés (`conf: ../..`, `data: ../../..` pour le robot, un par package). Les
compose ARM restent à leur place (Ansible et systemd les visent). Effacement conditionnel neuf :
`chemins_retires_l2` (anciens `Dockerfile-arm*`, et `conf/docker/{.dockerignore,Dockerfile-bak,
docker_bashrc,jenkins,scripts}` du robot — le `.dockerignore` serait désormais LU, il est à la racine
du nouveau contexte). Le compose ARM du robot monte en plus `didier_description`,
`didier_rehearsal` et `didier_sim` (avant, le conteneur compilait la copie de l'IMAGE de ces trois
packages, pas celle d'Ansible).

**Secret de la vision, trois verrous** : (a) `machines/vision/.dockerignore` (racine du contexte
`conf`, arrive sur le Pi en `src/vision/conf/.dockerignore`), (b) `COPY --from=conf --exclude=secret`,
(c) rôle `conteneur` : après le `up`, `docker run --entrypoint test <image> ! -e /home/<dest>` pour
chaque `secrets_hote` — rouge si le fichier est dans l'image ou si le contrôle échoue. Preuve au
secret FACTICE, chaque verrou isolé (témoin sans verrou = présent, (a) seul = absent, (b) seul =
absent) : **PC** (buildx 0.34) et **Pi vision** (Docker 29.6.1, buildx 0.35) identiques — aucun repli.
Image du PC construite avec un `machines/vision/secret` factice en place : absent, aucune trace dans
l'arborescence ni l'historique. Image du Pi : `conf/secret` absent, 0 fichier au sha256 du secret de
l'hôte, verrou (c) vert au déploiement.

**Audios privés du robot** : sur le Pi le contexte `data` est `src/robot/`, dont `medias/audios/`
est rempli par Ansible ; la copie devient `COPY --from=data --exclude=audios/* medias/` (dossier
vide gardé, point de montage). Les images du Hub poussées AVANT ce lot les contiennent : relu le
14/11 sur le `latest` d'alors (construit le 11/11) : **254 audios** dans `medias/audios/` (même
constat pour `e1420fc9…` du 08/11). Le `latest` neuf n'en a plus, mais un ancien digest peut rester
tirable sur le Hub — à traiter là-bas (décision de David, rien fait).

Script d'entrée du robot : build aussi si `install/setup.bash` manque ; `exec ros2 launch … "$@"`
(l'`ENTRYPOINT` ne passe rien : comportement du Pi inchangé ; le launch reçoit lui-même le signal
d'arrêt du conteneur au lieu du shell).

**Porte (14/11)** : (1) les deux images construites sur le PC depuis le dépôt ; (2) secret factice
ci-dessus ; (3) image robot x86 lancée seule (domaine 43, réseau bridge, non privilégiée, sans
`/dev` ni montage) : 17/17 `noeuds_attendus` en 22 s puis à chacune des 10 relectures sur 5 min,
`running 0` (`audio_node`/`system_node` vivent sans carte son : repli `asound-sim.conf` inutile) ;
(4) images reconstruites SUR les Pi (vision ≈ 5 min, robot 11 min, caches), chaque Pi déployé deux
fois (Dockerfile posé, puis image neuve : `build/`/`install/` vidés, colcon complet), `failed=0`,
vision `vision_status`, robot 17 nœuds, `running` restarts=0, `ecart-pi.sh` VERT ×2 (vision 284,
robot 286 entrées, audios 254/254) — **`attendu/` non regravé : aucun écart** ; (5) fumée complète
de la branche verte (RTF 1,00 ; 5, 4, 3, 13, 21, 14 ; 35 min) ; (6) banc vision : `person_tracker`
vivant sur la webcam du PC. Images republiées : vision `498c299b…`, robot `9d87ce83…` ; relues
depuis le PC (arborescence exportée) : aucun audio hors sons système, pas de `conf/secret`.

**Piège vu en route** : un déploiement du robot lancé PENDANT une fumée du même arbre a été refusé
par la garde 2 (porte sim) : l'épreuve « édition » écrit une séquence temporaire
`tmp-l1d/l1d-roues` dans `data/` (monté dans la sim) puis l'efface. La garde a eu raison ; règle :
ne jamais déployer le robot depuis un arbre dont une fumée tourne.

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
