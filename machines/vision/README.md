# machines/vision

Le Pi 5 de la tête (hôte `ai` de `deploy/hosts`). Ex `legacy/dadou_vision_ros/{conf,mediamtx}`
sans le banc x86 (lot L1e-4c, 11/11) ; copié dans `~/ros2_ws/src/vision/conf/` du Pi (chemin
inchangé). Le code est le package `packages/didier_vision`.

- `machine.yml` : packages, launch, alias ALSA (`rpi/asound.conf` → `/etc/asound.conf`), secret
  (modèle `secret.example`, valeurs dans `~/.config/didier/` du PC), voix Piper.
- `docker/arm/` : compose, Dockerfile et `Dockerfile-arm.dockerignore` (**exclut `conf/secret` de
  l'image publiée** ; ex `.dockerignore` racine du dépôt vision).
- `scripts/` : entrée du conteneur, calibrage distance, enregistrements, mesure CPU.
- `mediamtx/`, `ansible/` : l'ancien flux vidéo vers un serveur cloud (playbook à part, non rejoué).

Le banc PC de la vision est `../sim/banc-vision/`.
