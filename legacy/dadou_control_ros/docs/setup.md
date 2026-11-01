# Developer Setup (Controller)

## Repository Layout
Clone the three repositories side by side to keep relative paths consistent:
```
~/Nextcloud/dev/didier/python/
├── dadou_control_ros
├── dadou_robot_ros
└── dadou_utils_ros
```

## Prerequisites
- Python 3.11+
- (Optional) ROS 2 Humble or higher if you want to run end-to-end integration locally
- `pygame`, `tkinter`, and other dependencies listed in `requirements.txt`
- Access to the shared utility repo (`dadou_utils_ros`) so imports resolve

## Local Environment
```
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Running Tests
```
python -m unittest -v -s controller/tests -p "test_*.py"
```

## Running the GUI Without Hardware
1. Ensure the ROS 2 stack is not strictly required by starting `controller/nodes/main_gui.py` in isolation.
2. The GUI instantiates `USBGamepad` in “silent” mode if no physical controller is detected, allowing UI exploration.

## Notes for Remote Deployment
- The Ansible playbooks live in `dadou_utils_ros/ansible`. Use them to deploy the controller onto a Raspberry Pi-based remote.
- To trigger a remote build, create/update the `controller/change` file before running the playbook (`make i` in the corresponding `conf/Makefile`).
- Jenkins/Sonar: the Jenkins container already includes OpenJDK 21, but SonarScanner must use it.
  - If the analysis fails with `Could not find 'java' executable`, install or refresh the JRE inside the container: `sudo docker exec --user root jenkins bash -lc "apt-get update && apt-get install -y openjdk-21-jre-headless"`.
  - Remove the bundled JRE under `/var/jenkins_home/tools/hudson.plugins.sonar.SonarRunnerInstallation/.../jre` (Ansible does this automatically) so the scanner falls back to `/opt/java/openjdk/bin/java`.
  - Si Jenkins affiche « Warning: JENKINS-41339 », fixe `JAVA_HOME` et `PATH+JAVA=/opt/java/openjdk/bin` dans *Manage Jenkins → Configure System* pour tous les jobs.
  - Redéploie Jenkins via Ansible ou redémarre le conteneur avant de relancer `dadou_robot_sonar`.
- GitHub Commit Status depuis Jenkins:
  - Les jobs `dadou_robot_ci` et `debug_github_notify` n'utilisent plus le plugin `githubNotify`; ils publient directement le statut via l'API REST avec `curl`.
  - Crée un credential Jenkins `Secret text` (ID `github-token4`) contenant un PAT disposant au minimum du scope `repo:status`.
  - Dans *Manage Jenkins → Configure System → GitHub*, déclare un serveur `https://api.github.com` et associe ce credential (le bouton *Test connection* doit afficher le quota restant).
  - Les variables `GITHUB_NOTIFY_ACCOUNT/REPO/CREDENTIALS_ID` reçoivent des valeurs par défaut (`duvamduvam`, `dadou_robot_ros`, `github-token4`) mais peuvent être surchargées via les paramètres de job si besoin.
  - En cas d'échec API, relance simplement le job; aucune dépendance supplémentaire n'est nécessaire côté Jenkins car l'appel curl est autogéré.

More operational recipes are documented in [`testing.md`](testing.md).
