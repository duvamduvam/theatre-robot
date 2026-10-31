# Architecture cible — dadou_vision_ros (refonte 2026-07)

**Le CERVEAU AUTONOME de Didier** — sur Raspberry Pi 5 (8 Go, hostname `vision`,
Pi OS Lite trixie). Objectif assumé (2026-07-04) : **un personnage à part entière**,
qui suit et reconnaît les gens, interagit de sa propre initiative avec le public et
avec son créateur, ressent et exprime des émotions. Le robot (dadou_robot_ros) est
son corps ; ce dépôt est sa tête. Remplace la « suite d'essais » 2023-2025 (état des
lieux du 2026-07-04 : 3 briques réutilisables, le reste refait).

## Principes (non négociables, hérités du parc)

1. **Mêmes standards que dadou_robot_ros** : ROS 2 Jazzy en Docker, provisioning
   Ansible d'utils, CI GitHub Actions minimale, tests unitaires purs (sans matériel),
   `ROS_DOMAIN_ID` 42 (prod) / 43 (sim).
2. **Interfaces ROS standard** — pas de nouveau format maison. La vision *publie des
   perceptions*, le robot *décide des mouvements* : aucune commande moteur ne part
   d'ici, tout passe par le twist_mux/deadman du robot (sécurité déjà validée).
3. **Jamais de secret dans le code ni le dépôt** (GitHub public) : tout vient de
   `conf/secret` (gitignoré), chargé par un unique module config. `conf/secret.example`
   documente les clés attendues.
4. Chaque lot laisse un système **démontrable** (règle : Didier jouable à chaque étape).

## Structure cible

```
dadou_vision_ros/
├── ARCHITECTURE.md / CLAUDE.md      # ce document + passation sessions
├── conf/
│   ├── requirements.txt             # MINIMAL (openai, opencv-headless, sounddevice, sqlobject…)
│   ├── packages-docker.txt          # apt du conteneur (filtré par sed, cf. leçons Dockerfiles)
│   ├── secret.example               # modèle sans valeurs (chatgpt_key=, google_cloud=…)
│   ├── docker/arm/                  # FROM ros:jazzy-ros-base — calqué sur le robot,
│   │                                #  AVEC les leçons: sed s/#.*// packages, PAS de pip
│   │                                #  upgrade, PIP_BREAK_SYSTEM_PACKAGES=1, entrypoint
│   │                                #  sentinelle vision/CHANGE
│   └── ros2/                        # package ament "vision" (PAS "robot") : setup.py propre
├── vision/
│   ├── nodes/                       # fins : I/O ROS seulement, zéro logique
│   │   ├── person_tracker_node.py   # V1 — caméra → /vision/person
│   │   └── chat_node.py             # V2 — micro → GPT → TTS + topics face/audio
│   ├── tracking/                    # V1 — logique PURE testable :
│   │   ├── detector.py              #   backend de détection interchangeable
│   │   └── target_picker.py         #   choix cible + lissage + bbox→angle
│   ├── ai/                          # V2 — briques recyclées et durcies :
│   │   ├── interactions.py          #   GPT (parsing JSON structuré, plus d'ast.literal_eval)
│   │   ├── tts.py                   #   TTS OpenAI streaming + effet robot (gardé tel quel)
│   │   └── stt.py                   #   à retrancher : faster-whisper local vs API (bench V2)
│   ├── db/chat_db.py                # gardé (SQLite conversations)
│   └── tests/unit/                  # purs, lancés par la CI
└── json/, medias/                   # épurés (les configs lumières copiées du robot : supprimées)
```

Supprimé à la refonte : MQTT (essais), torch/whisper/blinka/pysftp (jamais utilisés),
tests lumières/neopixel (copiés du robot), `conf/ros2_dependencies/` dupliqué (le vrai
`robot_interfaces` arrive par le rsync ansible comme sur les autres machines),
`robot` symlink (dépendance à retirer du code), venv commité sur disque.

## Interfaces ROS (le contrat avec le robot)

| Topic | Type | Sens | Contenu |
|---|---|---|---|
| `/vision/person` | `geometry_msgs/msg/PointStamped` | vision → robot | x = azimut normalisé [-1..1] (0 = face caméra), y = élévation, z = confiance [0..1]. 10-15 Hz. Silence = personne perdue (le consommateur gère son timeout, comme cmd_vel). |
| `/vision/person_box` | `geometry_msgs/msg/PointStamped` | vision → robot | Ajouté pour le suivi AUX ROUES (`person_follower`). x = azimut (identique à `/vision/person`), **y = HAUTEUR de la silhouette [0..1]** (et non l'élévation : c'est le proxy de distance monoculaire), z = confiance. ⚠️ Deux topics dont le `y` ne veut PAS dire la même chose — ne pas les confondre. |
| `designate` | `robot_interfaces/StringTime` | télécommande → vision | **« C'est moi »** (2026-09-14). `"on"` verrouille le suivi sur la personne la plus **CENTRÉE** de l'image, `"off"` relâche. Sans ça, `TargetPicker` choisit sur `score × aire`, donc sur la PROXIMITÉ — en rue, le robot fixe le spectateur du premier rang au lieu de l'acteur. Commande (VOLATILE), pas un état latché. Étude : `dadou_robot_ros/docs/etude-identification-acteur.md`. |
| `camera_enable` / `camera_state` | `robot_interfaces/StringTime` | page web → vision / vision → page web | **Coupe-webcam** (vie privée de l'acteur, arrêter que Didier s'adresse à lui). Commande `"on"`/`"off"` (JSON, true/false, 1/0 tolérés ; valeur inconnue = warning, rien ne change). `"off"` LIBÈRE `/dev/video0` (LED éteinte) et coupe `/vision/person`, `/vision/person_box` et `camera/image_raw/compressed` ; `"on"` rouvre au tick suivant (réessai si échec). `camera_state` = état EFFECTIF, **latché** (TRANSIENT_LOCAL, depth 1), défaut `"on"`. Décision pure : `vision/tracking/camera_switch.py`. |
| `camera_source` / `camera_source_state` / `camera_sources` | `robot_interfaces/StringTime` | page web → vision / vision → page web | **Source d'images à chaud** (répétition simulée). Commande `"webcam"` (défaut) ou `"gazebo"` (brut ou JSON ; inconnu = warning ; `"gazebo"` sans `sim_camera_topic` = refus, rien ne change). `"gazebo"` LIBÈRE la webcam et s'abonne à `sim_camera_topic` (sensor_msgs/Image `rgb8` seulement, converti à la main — pas de cv_bridge — BEST_EFFORT depth 1) ; la dernière frame est consommée par le même tick (détection, `/vision/person*`, flux compressé), une frame n'est jamais retraitée. `camera_enable` `"off"` coupe quelle que soit la source. `camera_source_state` = source EFFECTIVE, **latché**. `camera_sources` = JSON des sources disponibles (`["webcam"]` ou `["webcam","gazebo"]`), **latché**, publié une fois. Paramètre `sim_camera_topic` (défaut vide = Gazebo indisponible) : renseigné par le SEUL compose x86 (`VISION_SIM_CAMERA_TOPIC`, défaut `camera/image_raw`), jamais sur le Pi. `reflection_node` n'affirme « la caméra filme le partenaire » que si la source est `webcam`. Logique pure : `vision/tracking/camera_source.py`. |
| `/face`, `/audio` | `robot_interfaces/StringTime` | vision → robot | V2 : émotions et parole via les topics EXISTANTS du robot (lights_node/audio_node) — zéro modif côté robot. |
| `animation_state` | `robot_interfaces/StringTime` (latché) | robot → vision | Arbitrage amont (étude 2026-07-12 côté robot, dadou_robot_ros/docs/etude-arbitrage-actionneurs.md) : chat_node s'y abonne et retient face/animation tant qu'une séquence de spectacle a la main ; son stop d'animation devient CIBLÉ (n'arrête que "parle", jamais une séquence en cours), cf. vision/ai/arbitration.py. |

### Topics de régie du chat (14/10)

Lot R3 « Chantiers » (spec fermée : `../dadou_robot_ros/docs/etude-repetition-simulee.md`
§13.4 point 3 et §13.6). Logique pure dans `vision/ai/stage.py` (testée sans ROS),
câblage dans `chat_node`. Tous en `robot_interfaces/StringTime` :

| Topic | Sens | Contrat |
|---|---|---|
| `chat_text` | sub | Texte « entendu » sans micro ni STT (clavier de la régie). JSON string ou brut, vide refusé. Servi au prochain tour, même micro mort ; coupe une écoute en cours. |
| `chat_instruction` | sub | Consigne de jeu courante, JSON string ou brut ; `""` = levée. Envoyée au LLM comme second message system (« Consigne de mise en scène (à jouer, jamais à prononcer) : … ») à chaque tour ; **péremption locale 120 s**. |
| `rehearsal/chat_fault` | sub | Panne publiée par le régisseur de la répétition simulée : JSON `{"op": pass\|delay\|garble\|deaf\|mute\|phantom, "params": {...}, "until_ms": n}`, `until_ms` = DURÉE en ms (même convention que les ordres relais). **Plafond local 60 s** (None/absurde = 60 s). `delay` (`delay_ms` 1..60000) = sommeil avant le LLM ; `garble` = texte compris remplacé par un contresens (liste gravée ou `params.texts`) ; `deaf` = énoncés jetés ; `mute` = répliques non synthétisées (texte publié quand même) ; `phantom` (`params.text`) = ponctuel, servi comme un énoncé entendu. Sans effet en prod tant que personne ne publie. |
| `chat_transcript` | pub | Flux (QoS volatile, depth 10) : JSON `{"role": "david"\|"didier", "text", "t_ms"}` (`t_ms` = epoch ms). `david` = ce que Didier a compris (après garble), `didier` = chaque phrase. Jamais les consignes ni les pannes. |

### STT distant (23/10)

`vision/ai/stt.py` : `OpenRouterStt` (Voxtral `mistralai/voxtral-mini-transcribe`,
`/audio/transcriptions` d'OpenRouter, même clé que le LLM) enveloppé dans
`FallbackStt` → repli sur `FasterWhisperStt` local (toujours chargé) à la
moindre exception ; 2 échecs de suite = local seul 60 s. Paramètre ROS
`stt_backend` (`openrouter` | `local`), timeout 4 s, aucun nouvel essai.
Banc du 23/10 (enregistrements de David, voix de ventriloque — biais connu) :
Voxtral 0,3-1,8 s, phrases complètes, `""` sur l'inintelligible ;
whisper-large-v3 hallucine sur le bruit ; whisper base local 3,6-5,2 s sur Pi 5
et nettement moins juste. **À re-mesurer sur la voix NORMALE de David en séance.**

### Metteur en scène intérieur (23/10)

Étude `../dadou_robot_ros/docs/etude-niveaux-reflexion.md`, spec fermée
`../dadou_robot_ros/docs/spec-metteur-en-scene.md`. Deux boucles qui ne
s'attendent JAMAIS : la parole (`chat_node`, Haiku 5.5 réflexion coupée) et la
réflexion (`reflection_node`, Haiku 5.5 effort medium ; Sonnet 5.5 sur demande).
Contrat partagé : `vision/ai/reflection_contract.py`. Un seul interrupteur :
`CHAT_REFLEXION` (chat_node le lit ; `launch-ros-in-docker.sh` en déduit
`reflection_enabled`). Tous en `robot_interfaces/StringTime` :

| Topic | Sens | Contrat |
|---|---|---|
| `chat_situation` | reflection → chat | JSON `{"text", "t_ms"}` : tableau de situation (perception, direction, mission, compris ; ≤ 700 car.). Republié chaque seconde ; **péremption côté parole 5 s** (réflexion morte = tableau absent). Envoyé au LLM comme message system à chaque tour, jamais historisé. |
| `chat_prompt` | reflection → chat | JSON `{"direction", "raison"}` : demande de tour SPONTANÉ. Emplacement unique (le plus récent gagne), **TTL 8 s**, servi seulement après 3 s d'écoute silencieuse, jamais en pleine parole, ni pendant un son de spectacle, ni chat OFF. |
| `chat_reflect` | chat → reflection | JSON `{"demande"}` : clé `reflechir` du JSON de fin (instruction complexe) → réflexion PROFONDE immédiate, réponse toujours renvoyée en `chat_prompt`. |
| `mission_state` | reflection → (console) | Latché : état de mission I0 (5 critères love/tenderness/friendship/speed/strong, guides, dernière indication). |

reflection_node s'abonne aussi à `chat_transcript`, `chat_state` (latché),
`chat_instruction`, `rehearsal/poi_event`, `route_state` (latché),
`/vision/person_box` et `camera/image_raw/compressed` (trame ≤ 3 s jointe au
LLM, décision de David du 23/10). **Arrêt d'urgence vocal** (`vision/ai/emergency.py`) :
une phrase faite UNIQUEMENT de mots d'arrêt (« Stop ! », « Arrête-toi ! »…)
publie `"stop"` sur `rehearsal/chat_move` AVANT le LLM (sans régisseur : loggé
« NON transmis », aucun effet).

Test à la main (domaine 43) :
`ros2 topic pub --once chat_text robot_interfaces/msg/StringTime "{msg: 'bonjour Didier'}"`.

Côté **robot** (chantier séparé, dadou_robot_ros) : un node `gaze_follower`
/vision/person → `/neck/position` (**suivre du regard d'abord** — théâtral, sans
risque, les servos sim/réels existent déjà) ; la conduite (cmd_vel prio basse via le
mux) ne viendra qu'après validation scénique du regard.

## Lots

- **V0 — socle sain** : structure ci-dessus, Dockerfile Jazzy, package `vision`,
  requirements minimal, briques recyclées déplacées + durcies, tests unitaires purs,
  CI, provisioning Ansible du Pi 5 (install-pios-full, groupe `vision`/hôte `ai`).
  Démo de fin de lot : conteneur qui tourne sur le Pi 5, `ros2 topic list` propre.
- **V1 — suivi de personne** : bench de détection SUR LE PI 5 réel (candidats :
  YOLO11n via ncnn, MediaPipe pose, moondream-tiny ; critère : ≥10 Hz en 640×480,
  CPU < 60 %) → `person_tracker_node`. Démo : `/vision/person` suit quelqu'un qui
  passe devant la webcam (validable par mon protocole caméra).
  Si le CPU ne suffit pas : Hailo AI HAT (~70 €) en plan B.
- **V2 — parole & émotions** : chat_node (STT → GPT-4o → TTS + émotion → /face),
  micro USB à acheter avant. Démo : conversation avec Didier qui « ressent ».
- **V3 — le personnage autonome** (l'objectif final) : un exécutif comportemental
  (py_trees, cf. Phase 4 de la feuille de route du parc) qui ORCHESTRE les briques :
  état interne (humeur, énergie, curiosité) ; **persona Didier** (prompt système
  versionné = sa personnalité, son histoire, son humour) ; **mémoire des personnes**
  (extension de chat_db : qui il a vu, de quoi ils ont parlé — il reconnaît son
  créateur) ; **initiative** : il décide seul de suivre du regard, d'interpeller
  quelqu'un, de bouder, de jouer une animation. Les comportements moteurs restent
  soumis au mux/deadman du robot — l'autonomie n'affaiblit JAMAIS la sécurité :
  sur scène, la télécommande garde toujours la priorité (remote > autonome).
  Démo : Didier remarque quelqu'un qui entre, le suit du regard, engage la
  conversation, et s'en souvient le lendemain.

## Matériel

- Webcam USB Jieli 1080p (validée le 2026-07-04, MJPEG 30 fps) — V1 travaillera en 640×480.
- Micro : MANQUANT — requis pour V2 (USB omnidirectionnel simple).
- Caméra CSI : possible plus tard (nappe 22 broches spécifique Pi 5).
