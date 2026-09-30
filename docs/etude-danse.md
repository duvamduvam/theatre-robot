# Étude — faire danser Didier en cadence (déambulation, chanson, gestes à la con)

*Ouverte le 2026-10-01 à la demande de David : « serait-il possible de faire danser
Didier, avec des chorégraphies pas forcément parfaites, mais le tempo reste super
important pour l'effet comique ; en déambulation, pendant qu'on chemine, il met une
chanson et développe des mouvements à la con en cadence ». Recherche complète
(code, docs, web) faite le jour même ; **rien n'est acté, tout est à valider par
David** (§6). Le robot réel est gelé (Pi 4 fumé le 12/09) : les premiers lots se
font sur PC et en simulation, ce qui tombe bien — c'est là que le calage se règle.*

## 0. Réponse courte

**Oui, et le gros du moteur existe déjà.** Le lecteur de séquences (`Track`,
`animations_node`, tick 20 Hz) sait déjà jouer un son et des keyframes servos/visage/
roues sur une même horloge. Ce qui manque n'est pas un nouveau système d'animation,
c'est **quatre choses précises** :

1. **une grille de beats par chanson**, précalculée sur PC (librosa fait ça en une
   seconde, mesuré §4.1) et embarquée en JSON ;
2. **un format d'écriture en temps musicaux** (mesures et temps, pas des fractions de
   durée) et un **compilateur** qui le transforme en séquence JSON ordinaire — le code
   embarqué ne change pas ;
3. **deux retards mesurés une fois** et compensés par anticipation : le retard de
   démarrage du son (aujourd'hui inconnu, le lecteur audio n'horodate rien) et le temps
   de parcours de chaque servo ;
4. **un banc de vérification automatique** du calage, en simulation, avec le vrai code.

Ce qui est **hors de portée avec le matériel actuel** : des bras vifs. Les servos de
bras sont annoncés à **1 s par 60° sous 12 V** (§3.2) : à 120 BPM ils ne peuvent
parcourir que ~30° par temps. Le rythme se joue donc avec **le cou, les yeux et le
visage** (rapides), les bras marquant **les temps forts** (un par mesure) — ce qui, pour
un robot lourdaud qui danse « à la con », est plutôt un atout comique qu'un défaut.

Ce qui reste **soumis aux verrous existants** : toute piste **roues** dans une danse est
du chemin roues (sim → protocole caméra → revue Opus), et la danse en déambulation
doit rester **haut du corps seulement** tant que le test scénique au sol (chantier 1)
n'est pas fait.

## 1. Le besoin, tel que formulé

- **Situation** : déambulation en rue, David pilote à la télécommande. À un moment
  Didier lance une chanson et « fait le con » en rythme tout en avançant.
- **Ce qui compte** : être **sur le temps**. Une chorégraphie approximative sur le
  tempo est drôle ; une belle chorégraphie à côté du tempo ne l'est pas. Ce constat est
  documenté en robotique (§4.4) : la synchronie seule fait lire « il danse », et le
  timing est la variable qui décide si un robot est drôle.
- **Ce qui ne compte pas** : la richesse gestuelle. Des figures simples, répétées,
  avec des accents et des ruptures aux changements de partie (refrain), suffisent.

## 2. Ce qui existe déjà (audit du 01/10)

| Brique | État | Ce que ça donne pour la danse |
|---|---|---|
| Séquences JSON `json/sequences/**` | 40+ séquences, format `[t_rel 0..1, valeur]` par piste (`audios`, `faces`, `neck`, `left_eye`, `right_eye`, `left_arm`, `right_arm`, `wheels`, `robot_lights`), `duration` en ms, `loop` | Le format cible du compilateur. Rien à changer côté lecteur. |
| `Track` (`robot/sequences/track.py`) | moteur temporel unique, `poll(now_ms)` émet chaque keyframe une fois à son instant | Quantification à la période du tick (50 ms), voir §3.1 |
| `animations_node` | tick 20 Hz, horloge `time.time()` (via `TimeUtils.current_milli_time`), publie `animation_state` latché + `remaining_ms` pour les deadman | Le gaze et le chat se taisent pendant une séquence (arbitrage déjà déployé) : une danse est une séquence comme une autre |
| Audio (`audio_manager.py` → `SoundObject` de dadou_utils_ros) | lecture par `playsound` dans un `multiprocessing.Process`, `starting_time = default_timer()` pris **avant** le fork, aucun horodatage de sortie DAC | **Le retard son est inconnu et non mesuré par le code** ; à mesurer (§3.3). `playsound` d'origine n'est plus maintenu (successeur `playsound3`, §4.2) |
| Chansons | `medias/audios/song/` : 6 fichiers ici (`great-balls`, `tactique-du-gendarme`, `le-professionnel`, `annie`, `caca-kaki`, `gig.wav`), d'autres dans `dadou_control_ros` (`motivation-long`, `lacrimosa`, `game-show1`…) | Corpus d'essai immédiat |
| Playlists `json/playlists/*.json` | associent chanson + animation (`little-move`, `trip`) — **jamais lues par le code** | Idée déjà présente dans le projet (chanson + geste), sans tempo |
| Séquences « dansantes » existantes | `moon-walk` (30 s, roues avant/arrière sur `il-est-genial-ce-corps`), `breakdown` (loop 30 s, roues alternées **toutes les 3 s**, servos random), `crasy-move`, `emotion` | Calées à la main sur des fractions de durée, pas sur des beats : c'est exactement la limite qu'on lève |
| `json/expressions.json` | 4 expressions (`sexy`, `speak`, `speak red`, `speak loop`) portent `"follow audio": true` — **drapeau jamais lu** (déjà relevé le 13/09) | Le visage n'a aucune notion d'audio ; la danse le pilotera par keyframes `faces` |
| Sandbox | `robot/tests/sandbox/audios/test_beat_detector.py` : 4 lignes instanciant **BeatNet** en mode `stream` | David a déjà tourné autour de la détection de beat temps réel ; elle n'a jamais été branchée |
| Servos (`robot/actions/servo.py`) | rampe linéaire `RAMP_SPEED = 160` unités/s (0,62 s pleine course 0-99), anti-spam I²C (écriture au degré entier), deadman `remaining + 2 s`, `MAX_POS = 180` pour les 5 servos (1 unité ≈ 1,8°) | Rampe = retard **déterministe**, donc compensable ; la vitesse réelle des bras est bien en dessous (§3.2) |
| Roues | piste `wheels` → `wheels_bridge` → `twist_mux` prio **anim 10** (< follow 20 < web 50 < remote 100), deadman 400 ms, deadman animation | En déambulation la télécommande écrase toujours l'anim ; **mais dès que David lâche le manche, l'anim passe** (§7) |
| Simulation | `ANIMATIONS=true` lance `animations_node` ; **pas d'`audio_node`** en sim | Les émissions `audio`/servos/visage sont horodatables par un abonné : banc de calage automatique avec le code de prod (§5, lot D1) |

## 3. Physique et budget de temps

### 3.1 Quel écart est « à côté du temps » ?

Repères sourcés (§4.4) : deux sons complexes fusionnent jusqu'à ~40 ms d'écart ;
des auditeurs entraînés discriminent 15-20 ms sur des tons purs, ~30 ms sur du piano ;
des chanteurs en duo tiennent ~57 ms d'asynchronie sans que ça choque. Aucune source
ne mesure « geste de robot vs beat » — on retient **±40 ms comme cible**, **±80 ms
comme limite** au-delà de laquelle l'effet « en rythme » se perd. À valider à l'œil
en sim puis en réel (§6, question 3).

### 3.2 Ce que les actionneurs peuvent faire par temps

À 120 BPM un temps dure 500 ms, une mesure à 4 temps 2 s. Chansons du corpus
mesurées (§4.1) : 96, 129 et 161 BPM.

| Actionneur | Vitesse limitante | Course possible en 1 temps (500 ms) | En 1 mesure (2 s) |
|---|---|---|---|
| Bras (ASME-MR 380 kg·cm) | **servo** : 1,0 s/60° à 12 V, 0,5 s/60° à 24 V (fiches revendeurs, §4.3 ; tension réelle du rail servo à relever) | **~30°** (12 V) / ~60° (24 V) | ~120° / ~240° |
| Cou, yeux (JX CLS-12V7346 : 0,12 s/60°) | **la rampe logicielle** (160 u/s ≈ 290°/s) | ~80 unités ≈ 145° | toute la course |
| Visage LED | `show()` ~31 ms bloquant | instantané (flash sur le temps) | — |
| Roues | rampe PWM + inertie 50 kg (non mesurée) | avant/arrière franc peu réaliste par temps ; **par mesure** oui (`breakdown` alterne toutes les 3 s) | — |

Conséquences de conception :
- **Le tempo se joue au cou, aux yeux et au visage.** Ce sont eux qui « tapent » le
  temps (hochement, yeux qui claquent, flash de bouche). Le flash visage sur chaque
  temps est en plus **le métronome visible** qui aide l'œil du public à lire le calage.
- **Les bras marquent la mesure**, pas le temps : un lever sur le temps fort, une
  descente sur le 3, amplitude ≤ 30 unités à 12 V. Un bras qui arrive lourdement mais
  **pile** sur le 1 est plus drôle qu'un bras qui s'agite à côté.
- Le retard des bras (jusqu'à 0,5 s pour 30°) exige une **anticipation** de la
  consigne (§3.4) : sans elle, tout arrive un demi-temps en retard, ce qui est
  précisément le pire cas pour l'effet comique.

### 3.3 Les sources d'erreur de calage (chaîne actuelle)

| Source | Ordre de grandeur | Nature | Remède |
|---|---|---|---|
| Tick 20 Hz : une keyframe sort au premier tick ≥ son instant | 0 à +50 ms (moyenne +25) | gigue systématique | accepter (dans la cible) ou avancer les keyframes de 25 ms ; un tick plus fin pour la danse seule n'est PAS justifié à ce stade |
| Démarrage du son : fork du `Process` + `playsound` (GStreamer sous Linux) + tampon ALSA du DAC USB | **inconnu**, vraisemblablement 50-300 ms ; ex. Pi 3 + carte USB : 109-124 ms (source secondaire, §4.2) | constante **si** la gigue entre lancements est faible — à mesurer | mesure caméra+micro (§5 lot D2), puis compensation par un `audio_latency_ms` dans le compilateur ; si la gigue dépasse ~30 ms : changer de lecteur (`mpv` IPC, `mpg123 -R`, ou `sounddevice` avec `outputBufferDacTime`) |
| Décodage MP3 : silence d'amorce LAME 576 + 529 échantillons (~25 ms à 44,1 kHz) retiré ou non selon que l'analyseur et le lecteur lisent le tag LAME | ≤ 25-40 ms | constante | **convertir les chansons de danse en WAV** (supprime la question) |
| Rampe servo `|Δ|/160` s | 0 à 620 ms | déterministe | compensé par le compilateur (anticipation calculée) |
| Retard physique du servo (commande → arrivée) | bras : jusqu'à 1 s/60° ; projet hobbyiste : 100-135 ms de retard mesuré par articulation | quasi constant par servo | mesuré caméra une fois par servo, inscrit dans le profil (§5) |
| Horloge `time.time()` non monotone (NTP, `fake-hwclock`) | saut rare mais **fatal** pendant une chanson | accident | `time.monotonic()` pour la danse (ou pour tout `TimeUtils`, à évaluer : changement transverse) |
| Dérive horloge Pi vs DAC | ~100-140 ppm Pi, ±100 ppm DAC (sources disjointes) → ≤ 1 ms/5 s, **≤ 60 ms sur 5 min** | lente | utiliser la **liste** des instants de beats (pas un BPM constant) n'y change rien ; sur une chanson de 2-3 min c'est sous la cible ; sinon re-synchroniser en début de partie (refrain) |
| Tempo réel de la chanson (rock joué, pas quantifié) | Great Balls : écart-type **16 ms** entre beats, tactique/professionnel : 25 ms | intrinsèque | grille de beats librosa (liste), jamais « BPM × n » |

Somme raisonnable après compensation : tick (±25) + gigue son (à mesurer) + gigue
servo (~±20) → **tenable sous ±40 ms si le lecteur audio démarre de façon répétable**.
C'est LA mesure qui décide (§6, question 1).

### 3.4 Le principe : anticiper pour ARRIVER sur le temps

Pour qu'un servo soit à sa cible à l'instant du beat `b_k` (mesuré dans le fichier),
sachant que le son démarre à `t0 + L_audio` et que le servo met `T_ramp(Δ) + T_servo`
à parcourir Δ, la keyframe doit être émise à :

```
t_cmd = b_k + L_audio − T_ramp(Δ) − T_servo − 25 ms (moitié du tick)
```

Si `t_cmd < 0` pour les premiers beats, on ne joue pas ces temps (ou on insère un
« lead-in » d'une mesure, comme le Choreographer de Spot qui recommande 3 s d'entrée,
§4.4). Tout ceci est calculé **hors ligne** par le compilateur : le robot ne fait
qu'exécuter une séquence ordinaire.

## 4. État de l'art (recherche web du 01/10/2026)

### 4.1 Extraire la grille de beats d'une chanson connue — hors ligne

Testé sur les chansons du robot, sur le PC, librosa 0.11 dans un venv jetable :

| Chanson | Durée | BPM | Beats | Écart-type inter-beat | Temps de calcul |
|---|---|---|---|---|---|
| great-balls.mp3 | 115,8 s | 161,5 | 292 | 16 ms | 6,5 s (1er appel, compilation numba) |
| tactique-du-gendarme.mp3 | 125,0 s | 129,2 | 261 | 25 ms | 0,2 s |
| le-professionnel.mp3 | 308,7 s | 95,7 | 456 | 25 ms | 0,4 s |

- **librosa** `beat_track` (Ellis 2007, programmation dynamique) : beats + tempo global,
  **pas de temps forts** (downbeats). Suffit pour tout ce qui « tape le temps » ; le
  temps fort se fixe alors à la main (index du premier « 1 » + temps par mesure).
- **beat_this** (Foscarin, Schlüter, Widmer, ISMIR 2024 ; pip `beat-this`, torch ≥ 2.0,
  CPU possible) : beats **et downbeats**, F-mesure GTZAN 88,9 % / 75,5 %, Ballroom
  96,2 % / 93,7 %. C'est l'outil à prendre si on veut les temps forts automatiques
  (torch sur le PC seulement, jamais sur le Pi).
- **madmom** : mort (numpy `np.float`, issue ouverte depuis 2023) ; un `madmom-prebuilt`
  0.17.post1 (mars 2026, Python 3.9-3.13) existe, compatibilité numpy 2 non affirmée.
- **BeatNet** (PyPI 1.1.3, nov. 2023) : dépend de madmom et torch ; GTZAN 75 % / 46 %.
  Plus faible que beat_this et plus lourd. Le stub du sandbox le visait en `stream`
  (micro) — cas « musique venant de l'extérieur », hors périmètre (§8).
- **Essentia** (wheels Linux x86_64 **et aarch64**, AGPL) : `RhythmExtractor2013`,
  exige 44,1 kHz ; précision non trouvée. **All-In-One** (KAIST 2023, `allin1`) : tempo,
  beats, downbeats **et segments** (intro/couplet/refrain) — intéressant pour placer
  les ruptures de figure sur les refrains, non chiffré.
- Pratique courante confirmée (Spot Choreographer, dépôt `ardrone20-dance`, projet
  `physical-ai-hack`) : **grille précalculée + chorégraphie écrite en beats**, jamais
  de détection temps réel quand le morceau est connu.

### 4.2 Lecture audio et horodatage

- `playsound` (utilisé aujourd'hui) : non maintenu ; sous Linux passe par GStreamer.
  `playsound3` 3.3.2 (07/2026) : backends GStreamer, aplay, mpg123, FFmpeg — pas de
  latence documentée.
- Options avec horodatage : **`mpv`** en IPC JSON (`time-pos/full` en ms, `audio-pts`
  tenant compte du retard driver, `--audio-delay`) ; **`mpg123 -R`** (mode distant,
  `jump <n>s` ; `--preload` est une **fraction** de tampon, pas des ms) ;
  **`sounddevice`**/PortAudio (`outputBufferDacTime` dans le callback = l'instant réel
  de sortie DAC, même base que `Stream.time`).
- Latence USB audio : ~2 ms structurels USB 2.0 ; PipeWire quantum par défaut 2048
  échantillons = 42,6 ms à 48 kHz ; Pi + carte USB : 109-124 ms mesurés (Pi 3B/B+,
  source secondaire). Mesure de référence : `jack_iodelay` en boucle physique, ou
  **caméra + micro** (une capture ffmpeg contient les deux : flash LED vs attaque du
  son, résolution 33 ms à 30 i/s, mieux à 60).
- MP3 : amorce LAME 576 + décodeur ~529 échantillons ; retirée seulement si le lecteur
  lit le tag LAME (mpg123 « pas toujours ») ; comportement de librosa/soundfile non
  tranché → WAV pour les chansons de danse.
- Horloges : `time.monotonic()` recommandé (PEP 418) ; sans RTC, `fake-hwclock` et
  `systemd-timesyncd` peuvent faire sauter `time.time()` en cours de route — piège déjà
  payé le 12/09 (`incidents/2026-09-12-fumee-rpi4.md`).

### 4.3 Servos

- **ASME 380 kg·cm** (05B / MRB / MXB, fiches revendeurs — pas de fiche constructeur) :
  0,5 s/60° à 24 V, **1,0 s/60° à 12 V** ; rien sur l'échauffement ni le courant de
  pointe en inversions répétées (absent de toutes les fiches, l'une le dit).
  ⚠️ Trois références différentes partagent la même fiche ; la MXB (3600°) annonce
  elle-même une précision faible. Le modèle exact des bras est un point ouvert de
  `etude-architecture-actionneurs.md`.
- **JX CLS-12V7346** (yeux) : 0,12 s/60° à 11,1 V, 0,10 s/60° à 14 V, 330 Hz.
- Projet hobbyiste `physical-ai-hack` : retard mesuré **100-135 ms par articulation**,
  compensé par articulation ; mouvements échantillonnés au 1/32 de beat, vitesse
  bornée, fondus enchaînés entre figures.

### 4.4 Robots qui dansent, et pourquoi ça marche

- **Keepon** (Michalowski, Šabanović, Kozima, HRI 2007, DOI 10.1145/1228716.1228729) :
  extrait le rythme dominant du son ou de la vue, synchronise un mouvement simple
  (balancement) ; **la synchronie seule** augmente l'engagement des enfants. Version
  commerciale « My Keepon » : détection de beat au micro.
- **Spot Choreographer** (Boston Dynamics) : temps découpé en **slices** (4 par beat,
  soit des doubles-croches en 4/4), tous les mouvements durent un nombre entier de
  slices, BPM de la partition = BPM de la musique, **lead-in de 3 s** recommandé.
- **Sony Aibo** : « AIBO Dancer » (2002) puis MàJ 6.00 (2024) — détecte le beat,
  choisit un mouvement, synchronise mouvement + LED. Même triplet que Didier
  (geste + visage lumineux).
- **Timing comique** : étude « Jon the Robot » (Oregon, 2020, 32 spectacles de 10-20
  personnes) — un robot au bon timing est jugé **significativement plus drôle** ; le
  mode « mauvais timing » = pause fixe de 5 s. Ça vaut pour les blagues, mais c'est
  le même mécanisme (attente → chute au bon moment) que David vise.
- **Perception** : fusion de deux sons complexes jusqu'à 40 ms ; discrimination
  15-30 ms ; duo chanté 57-95 ms. Aucune source « geste robot vs beat ».
- **Nao/Pepper** : Choregraphe cale son et mouvement sur une timeline commune, à la
  main (doc Aldebaran inaccessible). **ROS** : un seul dépôt trouvé (`ardrone20-dance`,
  ROS 1) — librosa en amont, grille précalculée ; rien en ROS 2. Il n'y a **pas de
  package à réutiliser** : on écrit le compilateur (petit).

### 4.5 Droits musicaux (grandes lignes, pas un conseil juridique)

- Diffuser une chanson du répertoire en public = autorisation préalable **SACEM**,
  demandée par **l'organisateur** (festival, commune), relevé de programme des œuvres ;
  −20 % si demande ≥ 15 jours avant, −5 % si gratuit d'intérêt général
  (associations.gouv.fr). Grille reproduite par un tiers (PlaySafe, 2025-2026) :
  forfait « gratuit, budget ≤ 1 000 € » ≈ 50 € HT, +25 % si musique enregistrée.
  **Aucune page SACEM primaire « arts de la rue » trouvée** ; le cas de la compagnie
  qui déambule sans organisateur n'est tranché par aucune source.
- **Droits voisins** (SPRÉ, interprètes + producteurs) pour un phonogramme du
  commerce : ~65 % du montant SACEM, collectés par la SACEM ; la page officielle SPRÉ
  ne cite que les lieux sonorisés, un tiers affirme que la rue est concernée — non
  confirmé en source primaire. Un avocat spécialisé écrit que la SACEM ne délivre pas
  l'autorisation des producteurs (contrat direct) ; un blog dit qu'elle centralise —
  contradiction non résolue.
- Le « droit de synchronisation » est une notion **audiovisuelle** dans toutes les
  sources lues ; rien ne l'étend à une chorégraphie scénique.
- Alternatives : domaine public (auteur mort > 70 ans **et** enregistrement libre —
  durée des droits voisins 50 ou 70 ans selon les sources, Légifrance non consulté),
  Musopen (CC0 / CC BY-SA), Pixabay Music (CC0, non vérifié), Jamendo Licensing
  (licence par projet, **interdit de diffuser l'œuvre seule** : à lire avant usage).
- Ce que ça change pour le chantier : rien techniquement ; en prod, le titre joué
  figure au relevé de programme du festival, comme les autres chansons du spectacle.

## 5. Architecture proposée (à valider)

Principe directeur : **zéro changement du code embarqué pour le lot 1**. Une danse
est compilée sur PC en séquence JSON standard, jouée par `animations_node` tel quel.

```
PC                                                     Robot (inchangé)
────────────────────────────────────────────────       ─────────────────────
chanson.wav ──► extract_beats.py ──► json/beats/<chanson>.json
                (librosa ; option beat_this pour les downbeats)
json/dances/<danse>.json  ─┐
  (figures en temps musicaux)│
json/beats/<chanson>.json  ─┼─► compile_dance.py ──► json/sequences/danses/<danse>.json ──► animations_node
conf/dance_profile.json    ─┘                          (format existant, duration = chanson + lead-in)
  (L_audio, T_servo par servo, mesurés)
```

**Format d'écriture** (`json/dances/<danse>.json`, proposition) :

```json
{
  "song": "song/great-balls.wav",
  "beats": "beats/great-balls.json",
  "beats_per_bar": 4,
  "first_downbeat_index": 1,
  "lead_in_bars": 1,
  "figures": {
    "hochement": {"beats": 1, "neck": [[0, 35], [0.5, 65]], "faces": [[0, "flash"], [0.25, "default"]]},
    "coup-de-bras": {"beats": 4, "left_arm": [[0, 70], [2, 40]], "right_arm": [[2, 70], [0, 40]]}
  },
  "score": [
    {"bars": "1-8",  "play": ["hochement"]},
    {"bars": "9-16", "play": ["hochement", "coup-de-bras"]},
    {"bars": "17",   "play": ["freeze"]}
  ]
}
```

- Les instants des figures sont **en temps** (fraction de temps possible : 0,5 =
  contretemps), jamais en ms. Le compilateur applique la grille réelle (liste des
  beats), l'anticipation par servo (§3.4), et écrit une séquence ordinaire.
- Les valeurs de sortie sont **gravées dans un test** (règle du 14/09 : un test qui
  recalcule l'attendu avec la fonction testée ne teste rien) : une danse de référence
  compilée → keyframes attendues en ms, à la main.
- Le profil (`L_audio`, `T_servo`) est un fichier de **mesures**, daté, avec la
  méthode de mesure notée à côté — comme les gains du gaze.

**Vérification (le même code que la prod)** : en sim, `ANIMATIONS=true`, un script
`conf/scripts/check-dance-timing.py` s'abonne aux topics `audio`, `neck`, `left_arm`…
avec `time.monotonic()`, prend l'émission `audio` comme t0, et vérifie que chaque
émission tombe à `b_k + L_audio − anticipation ± 30 ms`. Sortie : tableau des écarts,
verdict vert/rouge. Ça valide `Track`, le tick et le compilateur ensemble ; ça ne
valide **pas** les retards physiques, qui sont l'objet du lot D2.

**Déclenchement** : topic `animation` existant (nom de séquence), donc dès aujourd'hui
depuis la télécommande ou le web. Le futur menu côté hôte de la télécommande USB
(`etude-telecommande-usb.md`) listera les danses comme les autres séquences.

**Arbitrage** : une danse est une séquence → `animation_state` latché → gaze et
chat se taisent, comme prévu. Le micro est déjà coupé quand du son sort
(`live_audio_gate`, « any audio live »). Rien à ajouter.

## 6. Questions à trancher par David

1. **Le lecteur audio démarre-t-il de façon répétable ?** C'est la mesure qui décide
   de tout (§3.3). Si la gigue dépasse ~30 ms, on remplace `playsound` (mpv IPC ou
   sounddevice) — un changement de `dadou_utils_ros`, à mener alors comme un lot à part.
   Impossible à mesurer avant le dégel du robot (§9).
2. **Tension du rail servo** (12 ou 24 V ?) : double la vitesse des bras. À lire sur
   le robot (LM2596 ? Mean Well ?). Ne change pas l'architecture, change l'amplitude
   permise aux bras.
3. **La cible ±40 ms** est un choix de goût autant que de science : à valider à l'œil
   sur la première danse en sim (la sim n'a pas de son : on affichera un métronome
   visuel dans la console web, ou on jouera le WAV sur le PC en même temps — à décider
   au lot D1).
4. **Roues dans la danse** (déhanché sur place, quart de tour sur le refrain) : oui
   mais **jamais en déambulation** (§7) et après le test scénique. Ou pas du tout.
5. **Danse « réactive »** (Didier entend une musique dans la rue et s'y cale) : hors
   périmètre proposé, en veille (§8). David a déjà regardé BeatNet ; ce n'est pas la
   même difficulté (temps réel, micro dans le bruit de rue, ronflement du 30/08).

## 7. Sécurité et risques

- **Roues + twist_mux en déambulation** : la piste `wheels` d'une danse est publiée
  en prio 10. Tant que David tient le manche (prio 100) elle est écrasée ; **au moment
  où il le lâche**, le mux bascule sur l'anim et le robot part de lui-même en plein
  public. C'est un mouvement non commandé par l'humain, donc **interdit** : les danses
  de déambulation n'ont **pas de piste `wheels`**, et le compilateur le vérifie (refus
  de compiler une danse « déambulation » qui en contient une). Les danses avec roues
  sont une famille à part, jouées à l'arrêt, avec le protocole roues complet.
- **Bras** : 37 N·m, boucle ouverte, aucune limite d'angle par servo, aucune mesure de
  courant (`etude-architecture-actionneurs.md`). Une danse répète des inversions
  pendant 2-3 min : chauffe et pointes de courant **inconnues** (aucune fiche ne les
  donne). Règles : amplitude des bras plafonnée par le compilateur (30 unités au
  départ), bras sur les temps forts seulement, et **la mesure de courant (INA219, point
  ④ de l'étude actionneurs) passe devant** le premier essai réel long. Le retour de
  position magnétique des ASME-MR (actif dormant, point ①) rendrait le calage réel
  mesurable sans caméra — à brancher quand le robot revient.
- **Deadman** : inchangés. Une danse est une séquence : `remaining_ms` + 2 s sur
  servos et roues, 400 ms roues. Si `animations_node` meurt, tout revient au repos.
- **e_stop** : toujours sans source (rappel CLAUDE.md). La danse n'aggrave rien mais
  ne corrige rien.
- **Horloge** : passer la danse (ou tout `TimeUtils`) sur `time.monotonic()` avant le
  premier essai réel — un saut NTP en pleine chanson enverrait toutes les keyframes
  d'un coup.
- **Visage** : le flash par temps à 2-3 Hz reste loin du cas `chase` (20 rendus/s) qui
  avait révélé le bug du driver LED (13/07) ; le sleep de fin de trame est rétabli.
  À garder à l'œil quand même.

## 8. Pistes en veille (ne pas ouvrir maintenant)

- **Beat en temps réel** (musique extérieure, micro) : BeatNet `stream` (stub du
  sandbox), aubio `tempo` (causal, ~3 s avant le premier beat selon un utilisateur).
  Demande le micro vivant → dépend du ronflement (chantier 0) et de la charge CPU
  du Pi 5. Beaucoup plus incertain que la chanson choisie.
- **Tempo dans `Track`** (keyframes en beats interprétées à l'exécution, BPM
  modifiable en direct, « accélère ! » comme gag) : joli, mais change le code embarqué
  et n'a de sens qu'après une danse compilée qui marche.
- **Segments automatiques** (All-In-One) pour placer les ruptures sur les refrains
  sans les chercher à l'oreille.
- **Odométrie** : quand elle existera, un « pas » de roue par mesure devient
  mesurable, donc calable.

## 9. Plan par lots

| Lot | Contenu | Où | Verrou |
|---|---|---|---|
| **D0 — outillage PC** | `conf/scripts/dance/extract_beats.py` (librosa, venv d'outillage séparé — pas dans le venv de test ni sur le Pi), `compile_dance.py`, format `json/dances/`, profil de retards avec valeurs **provisoires explicitement marquées**, tests à valeurs gravées, conversion WAV des chansons de danse, doc `docs/software/` | PC | aucun |
| **D1 — première danse en sim** | une danse sur `tactique-du-gendarme` (129 BPM, écart-type 25 ms) : hochement + yeux + flash, bras sur le 1 ; `check-dance-timing.py` ; regard de David sur Gazebo avec le WAV joué sur le PC | sim | D0 ; robot non requis |
| **D2 — mesures réelles** | (a) retard et gigue du démarrage son : 10 lancements, caméra + micro, flash `faces` à t=0 ; (b) `T_servo` cou, yeux, bras pour 3 amplitudes ; (c) tension du rail servo ; (d) `time.monotonic()` dans la chaîne ; profil de retards **mesuré**, daté | robot, roues hors sol, robot immobile | **dégel du Pi 4** ; ne touche pas au chemin roues |
| **D3 — danse réelle haut du corps** | rejouer D1 sur le robot, roues débranchées ; mesure de courant servos pendant 3 min (INA219) ; ajustement amplitude bras | robot | D2 ; point ④ actionneurs conseillé avant un essai long |
| **D4 — déambulation** | danse haut du corps pendant que David roule à la télécommande ; règle « pas de `wheels` » vérifiée par le compilateur | rue / scène | **test scénique au sol (chantier 1)** |
| **D5 — roues dans la danse** (optionnel) | famille « à l'arrêt » avec quarts de tour sur le refrain | sim → caméra → Opus | chemin roues complet |

D0 et D1 se font **maintenant, sans le robot**. C'est, avec la télécommande USB, l'un
des rares chantiers qui avance pendant le gel.

## Sources

Code : `robot/sequences/track.py`, `robot/nodes/animations_node.py`,
`robot/actions/servo.py`, `robot/actions/audio_manager.py`,
`../dadou_utils_ros/audios/sound_object.py`, `json/sequences/eternel-show/{breakdown,moon-walk}.json`,
`robot/tests/sandbox/audios/test_beat_detector.py`,
`conf/ros2_dependencies/robot_bringup/launch/robot_app.launch.py` (MAX_POS 180).
Mesures librosa du 01/10 : venv jetable `/tmp/beats-venv`, librosa 0.11, `sr=22050`.

Web (consulté le 01/10/2026) : librosa doc 0.10.2 `beat_track` · CPJKU/beat_this README
et arXiv 2407.21658 / 2508.09790 · madmom issue #527, PyPI `madmom-prebuilt` ·
PyPI `BeatNet`, `essentia`, `playsound3` · lame.sourceforge.io/tech-FAQ.txt ·
python-sounddevice Streams API · mpv manual (IPC) · mpg123 README.remote ·
wiki.linuxaudio.org/latency (`jack_iodelay`) · PEP 418 · Wikipedia A/V sync (EBU R37,
ATSC) · PMC6561579 (fusion/discrimination temporelle) · Michalowski et al. HRI 2007
(publications.ri.cmu.edu) · dev.bostondynamics.com Choreographer · sciencedaily
19/05/2020 (« Jon the Robot ») · github v-bonilla/physical-ai-hack ·
github mmarashan/ardrone20-dance · fiches ASME (Amazon/AliExpress/insightfpv) et
JX CLS-12V7346 (revendeurs, site constructeur inaccessible) · associations.gouv.fr
SACEM · playsafe.fm (grille tierce) · spre.fr · didierfelix-avocat.com ·
orfeo.pro · village-justice.com (synchronisation, 09/2025).
Non atteints : Repp & Su 2012 (paywall), doc Aldebaran Choregraphe (ECONNRESET),
Artcena SPRÉ (403), grille SACEM primaire, Légifrance (durée droits voisins).
