# Robot Interfaces

## Message contract: `StringTime` + JSON payload

Almost every application topic uses `theatre_interfaces/msg/StringTime`:

```
string msg    # JSON-ENCODED payload (see below)
int64  time   # duration in ms — for wheels/servos during an animation it
              # carries the REMAINING time, used to arm their deadman
bool   anim   # true when the message is emitted by a running animation
```

**`msg` is JSON encoded as a string.** A bare name is NOT valid JSON: publish
`{msg: '"joie"'}` (with embedded quotes), an object as `{msg: '{"brightness": 0.15}'}`,
a stop as `{msg: '"stop"'}` (animation stop: `{msg: 'false'}`, JSON boolean).
Invalid payloads are rejected with an explicit ERROR log naming the topic
(`robot/nodes/payload.py`) — before 2026-07-11 they were silently dropped.

## ROS 2 application topics (all `StringTime`, no prefix)

| Topic | Node | Payload examples | Description |
|-------|------|------------------|-------------|
| `animation` | `animations_node` | `"parle"`, `false` (stop) | Plays/stops a JSON sequence; fans out per-track messages to the topics below. |
| `face` | `lights_node` | `"joie"`, `"calib"`, `"stop"` | Facial expression (mouth 24x16 + two 8x8 eyes). |
| `robot_lights` | `lights_node` | `"trip"`, `{"brightness": 0.15}` | Body LED sequences; brightness is global and non-persistent (default 0.05). |
| `audio` | `audio_node` | `"didier20/superbe-jack.mp3"`, `"stop"` | Audio cues (VLC). |
| `relay` | `relays_node` | relay keys | Accessory relays. |
| `system` | `system_node` | system commands | Shutdown/restart/status. |
| `neck`, `left_eye`, `right_eye`, `left_arm`, `right_arm` | one `servo_node` each | `50`, `"up"`, `{"mode": "random", ...}`, `"stop"` | Servo targets (0-99), reached through a linear ramp; random mode self-paces. |
| `wheels` | `wheels_bridge` (didier_drive) | `[0.5, 0.5]` pairs in [-1, 1] | Legacy wheels input, converted to Twist (see drive chain). |
| `gaze` | `gaze_follower_node` | `"on"` / `"off"` | Enables the neck person-following (OFF by default, launched manually). |
| `look` | `gaze_follower_node` | `{"angle_deg": 30, "hold_ms": 4000}`, compat `{"dir": "gauche"\|"droite"\|"devant"}` | « Regarder » gesture (lot M2, [`spec-aller-voir.md`](spec-aller-voir.md) §7.1), published by `chat_node`. `angle_deg` + = LEFT ; scaled on the neck's tracking course (gain × 180/99 °, ±36.4° at gain 20), beyond it SATURATED and logged ; `dir` = full course / centre. `hold_ms` bounded 1000-8000 (default 4000), counted from arrival ; persons ignored while held, then slow return to centre, interrupted by the first detection when `gaze` is on. Works with `gaze` on or off ; an explicit `gaze` off cuts it. At most 3 consecutive re-arms without returning to tracking, beyond that the hold is cut and `look` ignored 4 s. Malformed payloads are refused and logged, never fatal. Ignored while an animation has the hand (`animation_state`), cut when a sequence starts. Neck + eyes (robot), `/neck/position` (sim). Volatile. Never wheels. |
| `chat_text` | `chat_node` (vision Pi) | `"bonjour Didier"` | Text « heard » WITHOUT mic nor STT (régie keyboard, web `/scene`) : served at the next turn, interrupts a listening in progress. Prod-generic (2026-10-14). |
| `chat_instruction` | `chat_node` (vision Pi) | `"tu es amoureux du lampadaire"`, `""` (lifted) | Current stage direction, injected as a second system message every turn ; local expiry 120 s. Published by the sim régisseur (lubies) or by the régie. **Masked** in the web `state` (David must not see the draw). |
| `rehearsal/chat_fault` | `chat_node` (vision Pi) | `{"op": "delay", "params": {"delay_ms": 6000}, "until_ms": 40000}`, `{"op": "pass"}` | Conversation fault from the sim régisseur (`delay`/`garble`/`deaf`/`mute`/`phantom`) ; `until_ms` = duration, capped locally at 60 s. No publisher on the real robot. |
| `chat_transcript` | `chat_node` (vision Pi) | `{"role": "david", "text": "...", "t_ms": 1760...}` | **Flow** (volatile, depth 10) : what Didier understood (`david`, after garble) and each sentence he says (`didier`). Never directions nor faults. Relayed by the web bridge as `feed`. |
| `rehearsal/chat_move` | `director` (didier_rehearsal, **SIM-ONLY**) | `"go"`, `"stop"`, `{"cmd": "aller_voir", "objet": "anneaux"}`, `{"cmd": "tourner", "angle_deg": 90}` (compat `"sens"`), `{"cmd": "avancer", "metres": 2}` | Movement intents (lots M1/M2, [`spec-aller-voir.md`](spec-aller-voir.md)) : `tourner` = pivot in place, + = LEFT, 0 < \|a\| ≤ 180 ; `avancer` = straight line holding the current heading, 0.1 ≤ m ≤ 5, negative refused (no reversing) ; arrived when the projection on the heading reaches m. Arbitrated like `aller_voir` (refused when the route is OFF by David or without a fresh pose ; lifts the voice hold ; `stop`/abort → `cancel`), journalised `tourner` / `avancer`, executed by `route_driver` via `route_goto`. Walk order requested by Didier (lot I1, 2026-10-22) : `"marche"` key of the LLM's final JSON, published by `chat_node` (vision) ONLY when `CHAT_MOUVEMENT` is set (rehearsal bench). The régisseur alone decides and acts through `route` / `route_speed` (never above the speed in effect, never against a `route off`) ; journalised `voice_move`. No consumer on the real robot : no effect. Volatile. `chat_node` forces it OFF unless `ROS_DOMAIN_ID=43`. |
| `chat_situation` | `chat_node` (vision) | `{"text": "[Perception] …", "t_ms": …}` | Situation board written by `reflection_node` (the inner stage director, 2026-10-23) : perception, play direction, mission, understanding. Republished every second ; **5 s expiry** on the speech side ; sent as a system message each turn, never stored. Only when `CHAT_REFLEXION` is set. |
| `chat_prompt` | `chat_node` (vision) | `{"direction": "…", "raison": "…"}` | Spontaneous-turn request from `reflection_node` : single slot, 8 s TTL, served only after 3 s of silent listening, never while someone speaks, during show audio or with chat off. |
| `chat_reflect` | `reflection_node` (vision) | `{"demande": "…"}` | `"reflechir"` key of Didier's final JSON (complex instruction) → immediate deep reflection (Sonnet 5.5), answer always sent back as `chat_prompt`. |
| `mission_state` | console (future gauge) | `{"criteres": {…}, "guides": […], "indication": …}` | Latched mission state (I0) : the five criteria, guides, last indication. Written only by `reflection_node`. Never commands the body. |
| `rehearsal/state` (**SIM-ONLY**) | `director` (didier_rehearsal) | `{"seance": "attente"\|"en_cours"\|"terminee", "arret_vocal": true\|false}` | **Latched** (`TRANSIENT_LOCAL`, depth 1, both sides) state of the rehearsal session for the scene page : published at start-up and at EVERY change (start, end by duration/stop/abort, voice hold set or released by voice/fader/abort/end), never repeated. `arret_vocal` = Didier held by a spoken « stop » (route_speed 0 retained). Carries NO fault/lubie information (the page must not reveal the draw). Read-only for the web bridge (`TOPICS_LECTURE`). |
| `camera_enable` | web scene page (**SIM-ONLY**, `WHITELIST_REPETITION`) | `"on"`, `"off"` | Switches the perception webcam on/off (consumed on the vision side). Writable from the web only when `rehearsal_enabled`, never on the real robot. |
| `camera_state` | vision (perception webcam) | `"on"`, `"off"` | **Latched** (`TRANSIENT_LOCAL`) real state of the webcam, answer to `camera_enable`. Read-only for the web bridge (`TOPICS_LECTURE`) ; when `off` the scene page shows « webcam coupée » instead of a frozen image. |
| `camera_source` | web scene page (**SIM-ONLY**, `WHITELIST_REPETITION`) | `"webcam"`, `"gazebo"` | Selects, live, the image SOURCE of the perception (PC webcam or Gazebo camera ; consumed by `person_tracker` on the vision side). Writable from the web only when `rehearsal_enabled`, never on the real robot. |
| `camera_source_state` | vision (`person_tracker`) | `"webcam"`, `"gazebo"` | **Latched** (`TRANSIENT_LOCAL`) source actually in use, answer to `camera_source`. Read-only for the web bridge (`TOPICS_LECTURE`) ; the scene page highlights the button and shows the source in the « Ce que Didier voit » title. |
| `camera_sources` | vision (`person_tracker`) | JSON list, e.g. `["webcam"]` or `["webcam","gazebo"]` | **Latched** (`TRANSIENT_LOCAL`) sources AVAILABLE. Read-only for the web bridge (`TOPICS_LECTURE`) ; the scene page hides « Caméra Gazebo » until `"gazebo"` is listed. |
| `route_goto` (**SIM-ONLY**) | `route_driver` | `{"name": "anneaux", "x": 78.42, "y": 4.19, "standoff": 1.5}`, `{"turn_rad": 1.5708}`, `{"forward_m": 2.0}`, `"cancel"` | Manoeuvre order from the `director` (exclusive forms, refused if invalid, never saturated). `route_driver` is the only Twist producer (`cmd_vel_follow`, prio 20) ; bounds in `didier_rehearsal/goto.py` (\|ω\| ≤ 0.6 × fader factor, floor 0.15 ; pivot timeout 15 s and stall detection ; straight line 10 s + 4 s/m and ≤ 1.5 × m travelled, stall 2 s ; a repeated gesture is a new order, fader 0 = nothing, stale pose = zero, `cancel`/route off = immediate zero). State `goto` → `arrived` on `route_state`. Volatile. |
| `route_state_cause` (published by `route_driver`, **SIM-ONLY**) | `director` | `"boot"`, `"cmd"` | **Latched** (`TRANSIENT_LOCAL`, depth 1, both sides) cause of the route state : `"boot"` at node start, `"cmd"` at EVERY switch-off by command (`off`/`false`/`0`/`"0"`). The régisseur relaunches by voice only on state `off` + cause `boot` ; unknown cause = refused. |
| `animation_state` | `animations_node` | `"parle"`, `""` (idle) | **State topic** (not an actuator track), latched (`TRANSIENT_LOCAL`, depth 1 — subscribers MUST use the same durability or they miss the latch): current sequence name or `""` at rest. Published on transition AND on every sequence (re)start (same name included) with `time = remaining_ms`, so subscribers can arm a deadman-style expiry (remaining + 2 s) in case `animations_node` dies mid-sequence. Actuator-arbitration upstream (lot B, [`etude-arbitrage-actionneurs.md`](etude-arbitrage-actionneurs.md)): `gaze_follower_node` (robot) and `chat_node` (vision Pi) subscribe and go silent on face/head while a sequence has the hand. |
| `catalogue` | `catalogue_node` (`didier_web`) | `{"faces": [...], "audios": [{"label", "value": path}], "animations": [...], "relays": [...], "robot_lights": [...], "visuals": [...]}` | **State topic**, latched (`TRANSIENT_LOCAL` on BOTH sides), lot L1c. What the robot can play, built from `json/` by `didier_web.web_catalog.build_catalog` (same function as `GET /api/catalog`, plus `visuals`). Re-published only when the serialized JSON changes (checked every `refresh_period_s`, 2 s) : dropping a file in `json/` is enough. Audio `value` is the PATH the robot expects on `audio`, not the label. The remote's `test_buttons_vs_catalogue` compares `BUTTONS_LAYOUT` to it.  |
| `deploy_sha` | `catalogue_node` (`didier_web`) | `"a1b2c3d…"`, `"a1b2c3d…-dirty"`, `"dev"` | **State topic**, latched, lot L1c. Git sha written by Ansible into `conf/DEPLOY_SHA` at rsync (read once at start), `"dev"` when the file is absent (sim). `-dirty` = the rsynced tree was not a clean commit. Read by the web bridge (`TOPICS_LECTURE`) for the version badge. |
| `data_edit` | `data_edit_node` (`didier_web`) | `{"id": "a1", "kind": "sequence", "mode": "replace", "name": "eternel-show/parle", "content": {…}, "base_sha256": "…"}` | **Edit request**, lot L1d. Volatile (`qos.volatile(10)` both sides), **never latched** (a replayed request would rewrite an old edit). ≤ 131 072 bytes. Written only when the node's `enabled` is true (`DATA_EDIT` flag, OFF by default everywhere) ; otherwise answered `edition_desactivee`. See « Data editing through the robot » below. |
| `data_edit_result` | `data_edit_node` (`didier_web`) | `{"id": "a1", "ok": true, "code": "ok", "detail": [], "kind": "sequence", "name": "…", "mode": "replace", "sha256": "…", "sauvegarde": "json/backup/…", "avertissements": ["a_rejouer_en_sim"]}` | **Verdict**, lot L1d, volatile, seen by ALL : `animations_node` (sequence), `lights_node` / `face_sim` (expression, image ; lights_node also light, brick) and `leds_sim_node` (light, brick) re-read the written file on `ok` (hot reload, the message carries no content). |
| `validation_sim` | `validation_sim_node` (`didier_web`, **SIM ONLY**, refuses outside domain 43) | `{"kind": "sequence", "name": "eternel-show/parle", "ok": true, "code": "tamponnee", "detail": []}` (+ `"id"` when answering a wheel validation request) | **Sim gate verdict**, lot L1d-2, volatile. One per thing played (whatever the trigger) and per wheel validation request. See « Sim gate » below. |
| `validation_sim_demande` | page scène (L1d-3), scripts | `{"id": "v1", "name": "eternel-show/trip"}` | **Wheel validation request** (« Valider les roues pour le robot »), lot L1d-2, volatile, sim only. Accepted only if the current version was played to the end in sim (`non_rejouee` otherwise). |
| `roues_refusees` | `animations_node` | `{"name": "trip", "raison": "non_validee_sim"}` | **Play gate**, lot L1d-2, volatile : a wheel track not validated in sim is built EMPTY on the robot (the rest of the sequence plays) ; WARNING in the log. |

Other inputs: `/vision/person` (`PointStamped`, from the vision Pi) feeds
`gaze_follower_node`.

## Data editing through the robot (lot L1d)

Spec: [`spec-L1-contrats-donnees.md`](spec-L1-contrats-donnees.md) « L1d ». ONE writer,
`data_edit_node` (`didier_web/data_edit.py`, `traiter()`), launched always by
`robot_app.launch.py` and `sim.launch.py`, enabled only by `DATA_EDIT=true`.

- **Kinds** (`theatre_contrats.donnees.KINDS`) : `sequence` → `json/sequences/<dossier>/<nom>.json`
  (name `<dossier>/<nom>`) ; `expression` / `lumiere` / `brique` → ONE entry of
  `expressions.json` / `robot_lights.json` / `lights_base.json` (entry name
  `[a-z0-9][a-z0-9 _-]{0,63}`) ; `image` → `medias/visuals/<mouth|eye>/<nom>.png`, content = PNG
  bytes in base64. No delete, no rename, no folder creation (git + deploy).
- **Request** : `{id, kind, mode: create|replace, name, content, base_sha256?}` ; `base_sha256`
  required in `replace` = sha256 of what the editor loaded (file bytes for `sequence`/`image`,
  canonical JSON of the ENTRY for the three others) ; different from disk → `conflit`.
  Canonical JSON : `json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
- **Verdict codes** (engraved) : `ok`, `inchange` (identical content : no backup, no journal),
  `edition_desactivee`, `payload_invalide`, `trop_gros`, `kind_inconnu`, `mode_inconnu`,
  `nom_invalide`, `dossier_absent`, `existe_deja`, `absent`, `nom_en_double` (the loaders index by
  bare file name), `conflit`, `cle_inconnue` (top-level keys outside the engraved list),
  `contrat`, `quota_jour` (200 backups/day), `erreur_ecriture` (target untouched).
  Warnings : `a_rejouer_en_sim`, `roues_a_valider_en_sim` (sim gate below).
- **Contract** : `theatre_contrats.donnees` (`verifier_sequence`, `verifier_expression`,
  `verifier_lumiere`, `verifier_brique`, `verifier_image`) — the SAME functions as the data
  tests. Wheel tracks are bounded : `[fraction, [left, right]]` numbers only, |value| ≤ 0.89,
  a non-zero image held ≤ 60 000 ms, `duration` ≤ 300 000 ms when the track is non-empty, last
  image `[0, 0]`. Images entering : PNG, CRCs right, 24x16 (mouth) / 8x8 (eye), RGB 8 bits
  non-interlaced, ≤ 16 384 bytes.
- **Write order** : backup of the old file in `json/backup/<YYYY-MM-DD>/` (replace, and any
  entry-file write ; 30 dated folders kept) → line appended + fsync to
  `json/backup/EDITIONS-EN-ATTENTE.jsonl` (BEFORE writing) → temp file `json/backup/.tmp/<id>`
  (`medias/.tmp/<id>` for an image : other mount) → `os.replace` + fsync of the folder → owner of
  `json/` restored, mode of the replaced file kept.

### Sim gate (lot L1d-2)

Nothing modified reaches the real robot without having been played in sim. Register
`data/json/validations-sim.json` (versioned ; `indent=1`, sorted keys ; written ONLY in sim by
`validation_sim_node`, never by hand) : `{"version": 1, "sequence": {"<dossier>/<nom>": {"rejeu",
"roues", "origine_roues": "sim"|"heritee"}}, "expression": {"<nom>": {"rejeu"}}, "lumiere": {…}}`.
Fingerprints : `theatre_contrats.donnees.empreinte_contenu` / `empreinte_roues`.

- **Stamp `rejeu`** (observer, whatever triggered the play) : sequence — `animation_state` goes to
  the name then back to `""` between 0.95 × `duration` and `duration` + 5 s, no new ERROR/CRITICAL
  line in the robot log, nodes present at start still there, and for a wheel track a `cmd_vel`
  received during the play and the last one null 1 s after the end ; expression / light — name
  received on `face` / `robot_lights`, `face_sim_node` / `leds_sim_node` alive and error-free for
  min(`duration`, 10 s) without another command. Same fingerprint already stamped → no write.
- **Codes** (engraved, `didier_web.validation_sim`) : played — `tamponnee`, `deja_tamponnee` (ok),
  `interrompue`, `trop_longue`, `erreur_journal`, `noeud_absent`, `roues_sans_cmd_vel`,
  `roues_non_arretees`, `absente`, `homonyme` (same bare name in two folders : never stamped),
  `erreur_ecriture` ; wheel request — `roues_validees`, `deja_validees` (ok), `non_rejouee`,
  `sans_roues`, `absente`, `nom_invalide`, `payload_invalide`, `erreur_ecriture`.
- **Barriers** : host test `test_validations_sim.py` (every element stamped, every wheel track
  validated, no orphan) ; `python3 -m theatre_contrats.donnees non-validees <data>` (exit 1 if
  anything waits — read by the Ansible guard, L1d-4) ; on the robot, `animations_node` parameter
  `exiger_validation_roues` (default true ; set false by `sim.launch.py` only, ignored outside
  domain 43).

## Drive chain (geometry_msgs/Twist — safety path, frozen contract)

```
wheels (StringTime) -> wheels_bridge -> cmd_vel_anim ┐
cmd_vel_web (web_bridge_node, SIM-ONLY) -------------┤ twist_mux (remote 100 >
cmd_vel_remote (teleop/controller) ------------------┤  web 50 > anim 10,
                                                     ┘  e_stop lock 255)
        -> cmd_vel_mux -> twist_deadman (zeros at 20 Hz after 400 ms silence)
        -> cmd_vel -> wheels_node (local 400 ms deadman, hard stop on zero twist)
```

`cmd_vel_web` (priority **50**, timeout 0.5 s) is the web drive input, between the
physical remote (100, always wins) and animations (10). It is published ONLY when
`web_bridge_node` runs with `drive_enabled:=true` (default false, **SIM-ONLY** —
real-robot use is gated on the wheels camera protocol). Frozen contract verified
by `test_twist_mux_contract.py`.

⚠️ The `e_stop` lock is declared in `twist_mux.yaml` but **no node publishes on
`e_stop` yet** (neither robot nor controller, checked 2026-07-11). The actual
emergency stop relies on the deadman (silence → zeros). Wiring a real source is
pending, with the wheels camera protocol.

## API web (W0)

Pont HTTP + WebSocket (`didier_web` package, autonome façon `didier_drive`, node
`web_bridge_node`) exposant un SOUS-ENSEMBLE des topics ci-dessus pour une UI
navigateur. Implémentée le 2026-07-11 (sim), voir
[`etude-interface-web.md`](etude-interface-web.md) pour le plan complet
(phases W1-W5). **W0 = supervision + contenus + panneau technique. La whitelist
`cmd` n'expose NI roues (`wheels`/`cmd_vel_*`) NI verrou `e_stop`** — garantie
inchangée. Le pilotage roues (W3, partie sim) passe par un canal `drive`
SÉPARÉ (message `drive` → `cmd_vel_web`), **SIM-ONLY, derrière `drive_enabled`
(défaut false)** : voir le bloc pilotage plus bas. Le verrou `e_stop` reste sans
source (W1 à venir).

- **Port** : paramètre ROS `web_port` (défaut `8765` — 8088 évité, c'est le
  défaut Superset et la collision a été vécue sur le PC de dev en réseau
  host ; `WEB_PORT` le surcharge en sim). En sim :
  `WEB=true docker compose -f docker-compose-sim.yml up -d` puis
  `http://localhost:8765`.
- **Endpoints HTTP** : `GET /` (page UI), `GET /static/*` (assets), `GET
  /api/catalog` (catalogue JSON pour les boutons — faces/audios/animations/
  relais/robot_lights, construit depuis `json/`), `GET /video` (flux MJPEG
  `multipart/x-mixed-replace` de la caméra embarquée, servi à `video_fps` ;
  **503 "pas de vidéo"** si aucune frame fraîche depuis 2 s — l'UI affiche alors
  un placeholder).
- **Source vidéo** (paramètre `camera_compressed`, 2026-07-11) : en **sim**,
  `camera/image_raw` (sensor_msgs/Image brut de la caméra gz, encodé JPEG par le
  bridge) ; sur le **vrai robot**, `camera/image_raw/compressed`
  (sensor_msgs/CompressedImage DÉJÀ en JPEG, publié ~5 i/s par le
  `person_tracker` du **Pi vision** — seule source possible, la webcam lui
  appartient en exclusif) servi TEL QUEL, zéro ré-encodage (~125 Ko/s réseau,
  compatible WiFi/4G). Câblé dans `robot_app.launch.py` (robot réel) et
  exposé en argument de `web.launch.py`.
- **Second flux, perception** (paramètre `perception_topic`, 2026-10-31, défaut
  vide = désactivé, aucun abonnement) : `GET /perception`, MJPEG LECTURE SEULE
  d'un `CompressedImage` (QoS best effort depth 1), servi par le même code que
  `/video` (404 si désactivé). `hello.perception` l'annonce ; la page `/scene`
  affiche alors « Ce que Didier voit ». Posé par `sim.launch.py`
  (`camera/image_raw/compressed`, la webcam vue par person_tracker) ; jamais sur
  le vrai robot (`robot_app.launch.py` ne le passe pas). Topic hors whitelist.
- **WebSocket** : `GET /ws`. Le `msg` publié sur les topics ROS est sérialisé
  EXACTEMENT comme la télécommande (`msg.msg = json.dumps(valeur)`, pas de
  ré-emballage `{topic: valeur}` sur le fil).

**Whitelist** (`didier_web.web_protocol.WHITELIST`, seuls topics publiables) :
  - spectacle : `animation`, `face`, `audio`, `robot_lights`
  - technique : `relay`, `neck`, `left_eye`, `right_eye`, `left_arm`,
    `right_arm`, `gaze`, `chat`, `persona`, `system`, `chat_text`,
    `chat_instruction` (2026-10-14 : souffler un texte « entendu » / poser une
    consigne de jeu, cf. tableau des topics) (`chat` = toggle on/off
    de la parole IA, consommé par chat_node sur le Pi vision — même contrat
    que `gaze` ; `persona` = sélection de la personnalité de Didier, payload
    `"bougon"`/`"naif"`/`"vantard"`/`"mauvaisefoi"`, cf. `vision.ai.personas` —
    nouvelle session de conversation à chaque changement)
  - **répétition** (`WHITELIST_REPETITION`, SIM-ONLY) : `route`, `route_speed`,
    `rehearsal/cmd`, `camera_enable`, `camera_source` — dans la whitelist EFFECTIVE seulement si le node a
    `rehearsal_enabled` (launch `rehearsal:=true`, env `REHEARSAL=true`) ET
    tourne en domaine 43 (`rehearsal_allowed`) ; annoncés par `hello.rehearsal`.
    Sur le vrai robot : refusés comme un topic inconnu.
  - **masqués** (`TOPICS_MASQUES`) : `chat_instruction` et `route_speed` sont
    publiables mais leur dernière valeur n'apparaît JAMAIS dans `state` (la
    lubie en cours, la batterie faible = le tirage que David ignore).
  - lecture seule (`TOPICS_LECTURE`, jamais publiables depuis le web) :
    `chat_state`, `persona_state`, `route_state`, `chat_audio_chain`, `rehearsal/state`
    (séance + arrêt vocal, sans info de panne), `camera_state`, `camera_source_state` et `camera_sources`, topics d'ÉTAT latchés publiés par
    chat_node (Pi vision) — pilotent la surbrillance verte `en-cours` des
    boutons Parole/Personnalité de la console (chat_node absent = aucun
    bouton vert). Le groupe Gaze, lui, est surligné d'après le DERNIER ORDRE
    vu sur le topic `gaze` (gaze_follower ne publie pas d'état propre —
    approximation à remplacer si un `gaze_state` naît un jour).

**Messages client → serveur** (JSON, un objet `{"type": ...}` par message) :
| Type | Champs | Effet |
|------|--------|-------|
| `auth` | `token: str\|null` | Authentifie la connexion ; token serveur vide/null = accès libre (dev/sim). |
| `hb` | `t: int` (ms client) | Heartbeat du writer ; répond `hb_ack` avec le même `t` (mesure RTT côté client). |
| `cmd` | `topic: str` (whitelist), `value: any`, `time: int` (ms, défaut 0) | Publie sur le topic ROS (writer seulement). |
| `take_control` | — | Reprise d'écriture explicite (toujours autorisée pour un client authentifié). |
| `stop_all` | — | Bouton STOP : publie dans l'ordre `animation=false`, `audio="stop"`, `face="stop"`, `stop` sur les 5 servos, ET un Twist nul sur `cmd_vel_web` ; répétition activée : puis `route="off"` et `rehearsal/cmd="stop"` (la route est un mode latché, la séance se termine, le régisseur révoque ses pannes). |
| `drive` | `x: float`, `z: float` (∈ [-1, 1]) | **SIM-ONLY.** Consigne de pilotage roues normalisée (x = linéaire avant/arrière, z = angulaire). Voir bloc pilotage ci-dessous. |

**Pilotage roues (`drive`, SIM-ONLY, W3)** — canal SÉPARÉ des `cmd` (ne passe
PAS par la whitelist ; `cmd_vel_web` n'y figure jamais) :
- **Format** : `{"type":"drive","x":<float>,"z":<float>}`, émis ~15 Hz par le pad
  ou la manette. `x`/`z` non-numériques (bool exclu), NaN ou inf → **refusés**
  (`err`) ; débordement de [-1, 1] → **clampé SILENCIEUSEMENT** (pas de spam à
  15 Hz sur 1 % de dépassement).
- **Plafonds SERVEUR (durs)** : `drive_to_twist` applique `|lin| ≤ max_linear`
  (défaut 0.5 m/s) et `|ang| ≤ max_angular` (défaut 1.0 rad/s) — un navigateur
  bugué/compromis ne peut pas les outrepasser. Le facteur "vitesse %" de l'UI ne
  fait que réduire davantage.
- **Zéro automatique** : après `DRIVE_TIMEOUT_S = 0.3 s` de silence de drive, le
  node publie UN Twist nul (arrêt franc), une seule fois par arrêt (anti-spam,
  motif `DriveFlow`). Zéro immédiat aussi sur : relâchement du pad, déconnexion
  du writer, perte d'écriture (timeout heartbeat / `take_control`) et `stop_all`.
- **`drive_enabled`** : paramètre node (défaut **false**). À false, le publisher
  `cmd_vel_web` N'EXISTE PAS (aucun mouvement possible) et un `drive` reçu est
  refusé (`err "pilotage désactivé"`). L'UI grise alors le pad. Réel = protocole
  caméra d'abord (SIM-ONLY).

**Messages serveur → client** : `hello` (`domain_id`, `mode`:
`SIMULATION`/`ROBOT RÉEL`/`INCONNU` selon `ROS_DOMAIN_ID` 43/42/autre,
`writer`, `token_required`, + `drive_enabled`, `max_linear`, `max_angular` pour
que l'UI verrouille le pad et affiche les plafonds), `hb_ack` (`t` échoté),
`rehearsal` (bool : boutons route/vitesse/séance de `/scene`)), `feed`
(`topic`, `msg` — UN message par événement d'un topic de FLUX, `TOPICS_FLUX =
{chat_transcript}`, diffusé immédiatement à tous les clients, sans historique),
`ack` (`topic` — non émis pour `drive` : 15 Hz spammerait le fil), `err`
(`reason` — connexion JAMAIS fermée sur un message invalide, motif du
décodage StringTime commun), `state` (toutes les 2 s : dernier payload +
âge par topic, liste des nodes ROS vivants, nombre de clients, écriture
détenue ou non).

**Pages** : `/` = console de régie ; `/scene` (2026-10-14) = la scène de
répétition : caméra (`/video`), visage LED (flux MJPEG de `face_sim`, URL
modifiable), conversation en direct (`feed`), clavier (`chat_text`), consigne
(`chat_instruction`), Parole/persona, et — si `hello.rehearsal` — route
on/off/restart, slider `route_speed`, séance start/stop. Fichiers :
`scene.html` + `scene.js` + `scene.css` (styles propres, chargés après le
`style.css` partagé avec la console ; disposition : `docs/spec-refonte-page-scene.md`,
12/11). La scène ignore la
cible mémorisée de la console (jamais de bascule silencieuse vers le vrai
Didier) et n'affiche ni pannes ni consignes.

**Session / heartbeat** : écriture EXCLUSIVE — le premier client authentifié
l'obtient, les suivants sont lecteurs (`take_control` la reprend
explicitement). Le writer doit battre (`hb`) au moins toutes les
`HEARTBEAT_PERIOD_S` = 1.0 s ; silence > `WRITE_TIMEOUT_S` = 3.0 s → écriture
libérée (personne ne la récupère automatiquement). Toute la logique
(`didier_web.web_protocol`) est pure (horloge injectée) et testée sans ROS ni
réseau (`robot/tests/unit/test_web_protocol.py`, `test_web_catalog.py`).

## Files & directories consumed
- `json/expressions.json`, `json/sequences/**`, `json/robot_lights.json`,
  `json/lights_base.json`, `json/colors.json`: validated by the data contract
  `theatre_contrats.donnees` (lot L1d), called by the data tests
  (`packages/didier_core/test/unit/test_sequences_json.py`, `test_sequences_assets.py`,
  `test_expressions_json.py`, `test_lights_json.py`) AND by the robot's writer — every
  referenced visual/audio/brick must exist, wheel tracks are bounded.
- `medias/visuals/{mouth,eye}/`: PNG assets, mouth 24x16 / eye 8x8 (enforced) ;
  `test_visuels_png.py` holds them to the strict image contract, 21 legacy exceptions engraved.
- `json/backup/` (lot L1d, not versioned) : backups, journal of edits not yet brought back.
- `medias/audios/`: audio assets (versioned).

## Outputs
- Application log: `/home/ros2_ws/log/robot.log` INSIDE the container (not
  docker stdout).
- Hardware side-effects through `robot/actions/*` (PCA9685 servos/wheels PWM,
  WS2812 strip via `FastNeoPixel` (vendored write, frame-completion sleep
  kept — incident 2026-07-13), relays).
