# Conversation en déambulation — intention de communiquer, contenu, robustesse

*Étude du 2026-07-12, **GRILLÉE le jour même** (grill complet en 8 axes) :
le plan ci-dessous est **DÉCIDÉ — ne pas re-trancher** ; les points encore
ouverts sont explicitement listés au §8. Le périmètre initial (déclenchement
seul) a été **élargi au grill** à toute l'intégration du chat en déambulation :
déclenchement + contenu de la conversation + robustesse rue. Le nom du fichier
reste `etude-declenchement-conversation.md` (liens existants).*

## 1. Le problème

Didier est destiné à la déambulation : parler à des gens dans la rue. Or le
déclenchement actuel de la conversation est purement acoustique :

- Dès que le toggle `chat` est ON, le `ConversationEngine` tourne en boucle
  ([conversation.py](../../dadou_vision_ros/vision/ai/conversation.py)) : le
  VAD à énergie ([vad.py](../../dadou_vision_ros/vision/audio/vad.py), seuil =
  médiane du bruit de fond × 1,3) déclenche STT → LLM → TTS sur **n'importe
  quel bruit** dépassant le seuil. Le seul garde-fou est le filtre
  « ≥ 2 caractères alphanumériques » après transcription.
- **Aucun signal de perception n'entre dans la décision** : pas de lien avec
  `/vision/person`, pas de notion de personne présente, s'approchant, faisant
  face ou parlant AU robot.
- **Aucune notion de session** : une seule conversation ChatDB pour toute la
  vie du node, pas de timeout, pas de début/fin liés à l'arrivée ou au départ
  d'une personne.

Conséquences déjà observées : chat_node coupé sur le Pi vision depuis le 11/07
parce qu'il écrasait le visage au moindre bruit. En rue, ce serait pire :
Didier répondrait au trafic, parlerait dans le vide, ou interpellerait des
gens qui passent sans intention — exactement le mode d'échec dominant mesuré
par la littérature (§3.2).

L'objectif est déjà écrit dans la vision V3 de
[`ARCHITECTURE.md`](../../dadou_vision_ros/ARCHITECTURE.md) côté vision :
*« il décide seul de suivre du regard, d'interpeller quelqu'un […] Didier
remarque quelqu'un qui entre, le suit du regard, engage la conversation »*.
Cette étude en est la concrétisation.

## 2. Cadre décidé (grill du 2026-07-12)

- **Situation nominale** : opérateur à vue avec la télécommande, **le robot
  peut rouler pendant qu'il repère et interpelle** — le déclenchement doit
  fonctionner caméra en mouvement (conséquences §5.2).
- **Résultat visé** : Didier crédible en rue — repère qui veut lui parler,
  invite, converse, clôt. Tout le périmètre est dedans, mais **séquencé**
  (lots D0→D6, §7).
- **Critère de réussite** : le test rue chiffré du lot D5 (grille §7).
- **Échéance** : pas de date dure — chantier de fond, derrière les priorités
  0 (protocole chat V2) et 1 (test scénique au sol).

## 3. Ce qu'on a déjà (état des lieux 2026-07-12)

**Signaux disponibles** :

| Signal | Source | Contenu | Fréquence |
|---|---|---|---|
| Position d'une personne | `/vision/person` | azimut [-1..1], élévation, confiance | ~16,7 Hz max |
| Distance approximative | `/vision/person_box` | azimut, **hauteur de silhouette** [0..1] (proxy monoculaire, EMA) | idem |
| Parole/silence | VAD interne chat_node | machine à états CALIBRATING/IDLE/SPEECH + RMS | interne, **non exposé en topic** |
| Séquence en cours | `animation_state` (latché) | nom ou "", time=remaining_ms | événementiel |
| Toggles régie | `chat`, `gaze`, `follow` | "on"/"off" | console web |

Détection : MediaPipe EfficientDet-Lite0 int8 (~24 % CPU du Pi 5 à 16,7 Hz),
une seule cible retenue à la fois (adhérence anti-saut dans
`target_picker.py`).

**Signaux absents** : pose corporelle (un backend MediaPipe Pose existe dans
`vision/tracking/bench_detection.py`, jamais branché en prod), détection et
orientation du visage, trajectoire dans le temps (au-delà du lissage EMA
frame à frame), multi-personnes, niveau micro ambiant exposé, état interne du
chat (écoute/réfléchit/parle) publié en ROS. **Pas d'odométrie sur le vrai
robot** (pas d'encodeurs) — le mouvement propre ne peut se lire que sur la
consigne `/cmd_vel`.

**Atouts en place** : le gaze cou+yeux est VALIDÉ EN RÉEL (12/07) — c'est
précisément le « signal de disponibilité » que la littérature recommande
d'utiliser en premier (§4.2) ; l'arbitrage `animation_state` protège déjà le
visage et la tête pendant les séquences ; le toggle `chat` est le canal
d'activation naturel.

## 4. État de l'art (recherche du 2026-07-12)

### 4.1 Les zones de Hall — la grille de distances de toute la littérature

Hall (1966), validé humain-robot par Walters et al. (2005) : intime 0–0,45 m,
personnelle 0,45–1,2 m, **sociale 1,2–3,6 m** (interaction avec des
inconnus), publique > 3,6 m. La zone sociale est la fenêtre d'abordage :
au-delà, un signal d'intention n'est pas lisible fiablement ; en deçà, on est
déjà dans l'espace personnel de la personne.

### 4.2 Michalowski et al. 2006 — la position statique ne suffit PAS

« A Spatial Model of Engagement for a Social Robot » (CMU Roboceptionist,
12,5 h de vidéo annotée,
[PDF](https://www.ri.cmu.edu/pub_files/pub4/michalowski_marek_piotr_2006_3/michalowski_marek_piotr_2006_3.pdf)) :

- Un modèle à zones fixes **surestime massivement** l'engagement : 1500
  personnes vues « engaged » par le robot contre 174 réelles — l'écart, ce
  sont les gens qui **passent**. 66 % des rotations de tête du robot visaient
  de simples passants.
- 54 % des salutations verbales bien dirigées ne recevaient AUCUNE réponse
  (gêne sociale documentée).
- **Asymétrie clé** : tourner la tête est peu coûteux socialement (26 % de
  suivi d'interaction si bien dirigé) et peut être généreux/anticipé ; la
  **parole** doit être conservatrice (48 % de suivi si bien dirigée, mais un
  échec = malaise réel).
- Conclusion des auteurs : **direction et vitesse du mouvement sont plus
  fiables que la position** ; leur modèle révisé : *Present* (passage
  rapide/tangentiel → ignorer) → *Interested* (approche ou mouvement lent →
  tourner la tête) → *Engaged* (quasi stationnaire + visage détecté → le
  robot peut parler) → *Interacting*.

### 4.3 Satake, Kanda et al. — l'abordage de passants (ATR)

« How to Approach Humans? » (HRI'09, centre commercial réel,
[PDF](https://dl.acm.org/doi/10.1145/1514095.1514117)) :

- Taxonomie des échecs d'un abordage naïf : *unreachable* (cible partie),
  *unaware* (ne perçoit pas le robot), *unsure* (perçoit mais hésite),
  *rejected* (ignore délibérément).
- Classification de trajectoires par SVM (fast-walk / idle-walk / wandering /
  stop) : **88,9 % de reconnaissance** — la trajectoire seule est un signal
  très exploitable.
- Résultat terrain : 56 % de succès (33/59) avec anticipation de trajectoire
  contre 35 % (20/57) en naïf. Le **rejet reste incompressible** (~27-29 %
  dans les deux cas) : il dépend de la volonté humaine, pas du robot — ne
  jamais insister.
- Suite 2022 (« Behavioral Assessment… », Int. J. Social Robotics,
  [PMC9331028](https://pmc.ncbi.nlm.nih.gov/articles/PMC9331028/)) : critère
  d'arrêt opérationnel = présence continue **3 s** dans une zone de
  1,2 × 2,5 m devant le robot. Les **enfants** s'arrêtent significativement
  plus (p<0,01), les **groupes** s'arrêtent et écoutent plus que les
  personnes seules. Un robot « en difficulté » attire plus qu'un robot qui
  salue ou danse — et attire bien plus qu'un humain dans le même rôle
  (stop rate humain : 0,8–4,1 %).

### 4.4 Rich et al. 2010 — les « connection events » et leurs durées

« Recognizing Engagement in HRI » (HRI'10,
[PDF](https://dl.acm.org/doi/10.1145/1734454.1734580)) : l'engagement en
cours se mesure par 4 événements (regard dirigé, regard mutuel,
question-réponse, backchannel). Chiffres réutilisables comme timeouts :
établissement du regard mutuel ~0,6–0,7 s ; temps moyen entre événements de
connexion (MTBCE) **5,7 s** chez l'humain, ~3 s dans leur implémentation
robot ; timeouts calibrés 1,8–3,1 s. Un silence bien au-delà du MTBCE =
désengagement.

### 4.5 Vaufreydaz et al. 2015 — 7 features suffisent

« Starting Engagement Detection Toward a Companion Robot »
([arXiv:1503.03732](https://arxiv.org/abs/1503.03732)) — le plus proche d'une
spec pour nous :

- Validation expérimentale que **distance et vitesse seules ne suffisent
  pas** (on passe près du robot sans le vouloir).
- Classe WILL_INTERACT (détecter l'intention AVANT l'interaction) : SVM
  multimodal à 3 classes → **précision 0,95 / rappel 0,93**.
- Sélection MRMR : **7 features suffisent**, hétérogènes — dont *taille et
  position du visage détecté* (proxy bon marché de proximité + face-à-face),
  localisation sonore, vitesse latérale, et **rotation des épaules**
  (métrique de Scheflen, validée là pour la première fois en HRI).

### 4.6 MuMMER 2019 — le pipeline complet, et ses compromis

Pepper en centre commercial ([arXiv:1909.06749](https://arxiv.org/abs/1909.06749)) :
pose de tête via OpenHeadPose **comme proxy du regard** (le vrai eye-tracking
est explicitement jugé trop coûteux en multi-personnes), fusion distance +
orientation de tête + localisation sonore → une probabilité d'attention
comparée à un seuil, **pénalité anti-re-sollicitation** de quelqu'un qui
vient d'interagir. Perception complète à 10 fps. Limite documentée par
ailleurs (HRI'15) : la pose de tête est un proxy dégradé du regard,
surtout chez l'enfant.

### 4.7 Spécificités rue / espace public

- Le robot doit **signaler sa propre disponibilité** : orientation du regard
  et du corps du robot vers la personne = l'invitation la plus lisible
  (Satake : le différentiel d'orientation robot→cible est un facteur clé de
  la « conscience » du passant ; littérature gaze-cues piétons 2023).
- Biais à éviter : le « robot privilege » (Pelikan 2024) — les robots publics
  tendent à faire porter l'ajustement au piéton. Didier doit inviter, jamais
  imposer ni bloquer le passage.
- En rue ouverte (vs centre commercial), l'effet de surprise amplifie les
  échecs *unaware*/*unsure* ; les groupes et les enfants seront les
  interactions majoritaires (46 % de groupes chez Michalowski ; souvent une
  personne en entraîne une autre).

### 4.8 Les 5 signaux au meilleur rapport fiabilité/coût (convergence)

1. **Direction + vitesse d'approche** (dérivée temporelle de la boîte
   englobante — aucun modèle ML nouveau requis).
2. **Arrêt soutenu ≥ 3 s en zone sociale** (position + minuteur).
3. **Taille/position du visage détecté** (détecteur de visage léger — proxy
   de proximité ET d'orientation frontale).
4. **Pose de tête** comme proxy du regard (MediaPipe, ~18 fps mesurés sur
   Pi 5 en config « balanced »).
5. **Orientation du corps/des épaules** (pose corporelle type
   MoveNet/YOLO-pose ; coût quasi constant avec le nombre de personnes pour
   les architectures bottom-up).

La parole adressée et le geste explicite sont des signaux forts mais chers à
détecter fiablement (attribution de locuteur = réseau de micros) : en
**confirmation**, pas en détection primaire.

## 5. DÉCISIONS (grill du 2026-07-12 — ne pas re-trancher)

### 5.1 Périmètre et séquencement

Tout est au périmètre du chantier, mais séquencé :

- **Groupe** : traité DÈS la FSM v1 en « dégradé digne » — une seule cible
  choisie (le `target_picker` existant), les autres ignorées proprement,
  sans panique ni saut de cible. Choix d'interlocuteur amélioré en D4.
  (Le groupe est le cas MAJORITAIRE en rue — pas reportable.)
- **Multi-langues** : au lot contenu (D3) — whisper détecte déjà la langue,
  il faut une voix piper par langue.
- **Mémoire des gens** (ré-identification) : phase finale (D6).
- **Abordage mobile autonome** (l'engagement commande un déplacement vers la
  personne, façon Satake) : **phase finale (D6), conditionnée aux verrous
  roues** — test scénique au sol fait, e_stop câblé (W1), suivi de personne
  validé en réel, protocole caméra dédié. D'ici là, rien de ce chantier ne
  publie vers la chaîne cmd_vel.

### 5.2 Déclenchement (la FSM)

- ⚠️ **RE-TRANCHÉ le 08/11** : « micro à l'arrêt » est abandonné — Didier écoute en marche,
  pour tout le monde (`etude-interaction-en-mouvement.md` §2 bis ; préalable robot : mesurer le
  bruit des moteurs dans le micro). La porte ENGAGED garde son rôle : à qui il répond.
- **Caméra en mouvement — décision « regard roulant, micro à l'arrêt »** (révisée, ci-dessus) :
  en roulant, seuls les états généreux vivent (PRESENT/INTERESTED → gaze,
  expressions ; un faux positif ne coûte rien). Le passage en ENGAGED
  (micro armé) **exige le robot à l'arrêt** — l'état de mouvement se lit sur
  la consigne `/cmd_vel` (pas d'odométrie réelle). Pas de compensation
  d'ego-motion (écartée : features bruitées, calibration pénible).
- **Porte ENGAGED (armement du micro)** — robot à l'arrêt ET personne en
  zone sociale ET l'une des deux portes :
  - (a) quasi stationnaire depuis **≥ 3 s** (critère Satake 2022), ou
  - (b) **parole détectée par le VAD pendant que la personne est visible en
    zone sociale** — celui qui dit bonjour n'attend pas 3 s.
  Le bruit sans personne visible ne déclenche JAMAIS rien.
- **Clôture de session** : silence > **12 s** en conversation (2× le MTBCE
  humain), ou cible perdue > **3 s**. Clôture = reset de l'historique LLM,
  retour au neutre.
- **Cooldown : 45 s** après une clôture ou une invitation ignorée (pénalité
  anti-re-sollicitation, façon MuMMER).
- Toutes ces valeurs sont **paramétriques**, à caler en rue (D5) ; ce sont
  les valeurs de départ issues de la littérature.
- Le toggle `chat` régie reste le **master switch** au-dessus de tout
  (ET logique, comme le gaze avec `animation_state`).

### 5.3 Abordage et théâtralité

- **Réactif d'abord** : dans les lots D1→D5, Didier n'émet JAMAIS le premier
  mot — il invite par le corps et ne parle que si on lui parle.
  L'interpellation verbale proactive arrive en D6, sur un déclenchement déjà
  fiabilisé (rappel : 54 % des salutations de robot restent sans réponse).
- **L'invitation non-verbale** (états INTERESTED/ENGAGED) est faite de :
  regard verrouillé (gaze existant) + **expressions visage dédiées**
  (« curieux » puis « accueillant ») + **gimmick sonore non verbal** à créer
  (signale « je t'ai vu, je suis dispo » — répond au mode d'échec *unaware*
  de Satake) + **animation corporelle « invite »** à créer (via
  animations_node, donc arbitrage existant).
  Le registre « en difficulté » (Satake 2022 : attire 2× plus) est ÉCARTÉ du
  plan — noté comme option de mise en scène future.
- **Le rejet est encaissé en jeu** : expression brève de déception, retour au
  neutre, cooldown. Jamais d'insistance (le ~28 % de rejet est
  incompressible). Le râteau visible signale aussi aux autres passants que le
  robot est vivant.

### 5.4 Contenu de la conversation

- **Persona à créer de zéro** : le personnage parlé n'existe pas encore —
  atelier d'écriture dédié (David + Dadou, l'IA en brouillon) : qui est
  Didier, son humour, ses limites, sa façon de parler aux enfants. Livrable =
  system prompt.
  **Complément d'atelier (2026-07-13)** : pas UN personnage mais des
  **personnalités commutables à tester** — socle commun (robot assumé qui en
  joue, complice des enfants, esquives par opinions absurdes décalées, ne
  sort jamais du personnage) + 3 variantes complètes : « bougon » (artiste
  recalé de l'Eurovision), « naif » (échappé de l'usine), « vantard »
  (ex-gloire imaginaire des Zéniths). Sélection par config au démarrage et à
  chaud via topic `persona` (console web faite ; télécommande à câbler côté
  dadou_control_ros). Textes : `vision/ai/personas.py`, versionnés au repo
  (tranché : texte de spectacle assumé public, la CI garde le contrat
  technique). Brouillons à valider avec David.
- **Garde-fous : confiance au modèle pour l'instant** (décision du grill) —
  pas de modération technique, pas de red-team formalisée ; le persona
  portera naturellement quelques règles de registre. **À réévaluer après les
  premières sorties** (sur incident).
- **Répliques courtes et relanceuses** : 1-2 phrases max, souvent terminées
  par une question au passant — contrainte écrite au prompt. Nourrit l'état
  IN_CONVERSATION et évite de monopoliser le TTS.

### 5.5 Audio et latence

- **Micro : U20 mono conservé, on MESURE d'abord** (D0 : enregistrements en
  conditions rue + rejeu dans le VAD ; intelligibilité du TTS mesurée au même
  moment). Changement de matériel (directionnel, array) seulement sur échec
  constaté.
- **Latence cible : < 2 s entre la fin de la phrase du passant et le premier
  son de Didier.** Moyens : streaming par phrase (en place), piper in-process
  (acquis), modèle LLM rapide, **signal d'écoute immédiat** (expression
  « tend l'oreille ») pour couvrir le délai restant.
- **VAD : recalibration périodique du bruit de fond en IDLE** (la calibration
  unique de 1 s au démarrage ne tiendra pas une rue au niveau variable).

### 5.6 Perception et calcul

- **Tester sur le Pi 5 d'abord** : D0 mesure le CPU réel en conversation
  complète (détection + whisper + piper), puis on ajoute E2 (visage) et on
  re-mesure. Accélérateur (Hailo/Coral) seulement si la mesure le condamne.
- **Soupape identifiée : déporter whisper vers une API** (Groq/OpenAI) pour
  libérer le CPU — la 4G est déjà une dépendance dure (LLM via OpenRouter),
  ça n'ajoute pas de mode de panne. Idéalement bascule locale/API
  paramétrique.
- Extensions par coût croissant : **E1** (gratuit — trajectoire/arrêt depuis
  `/vision/person_box`), **E2** (léger — visage frontal MediaPipe, feature
  n°1 de Vaufreydaz), **E3** (pose de tête/épaules, seulement si E1+E2
  montrent leurs limites en terrain).

### 5.7 Données et cadre légal

- **Corpus complet assumé, AVEC dispositif type tournage** : la déambulation
  est traitée comme un tournage de rue — affichage visible « spectacle
  filmé/enregistré » aux abords, l'opérateur propose APRÈS l'échange de
  garder l'enregistrement ; refus ou absence de réponse = **effacement de la
  session par défaut**.
- Implication technique : enregistrement par session + **bouton
  « garder / effacer » sur la console de régie** (rejoint la boîte noire du
  chantier télédiagnostic).
- Le texte des échanges (ChatDB, sans identité) sert à améliorer persona et
  déclenchement.

## 6. Architecture

### 6.1 Un node `engagement_node` (Pi vision), logique pure testée

Nouveau node à côté de `person_tracker_node`, même patron que le reste du
projet : node = I/O, logique dans un module pur testé sans ROS
(`vision/engagement/…`).

- **Entrées** : `/vision/person_box` (azimut + hauteur + confiance),
  l'état de mouvement du robot (consigne `/cmd_vel` — gate ENGAGED),
  `animation_state` (se taire pendant une séquence de spectacle), l'état
  interne du chat (topic à créer, §6.2), toggle régie. Plus tard : visage
  frontal (E2), pose (E3).
- **Cœur** : fenêtre glissante de quelques secondes sur la cible → features
  (vitesse d'azimut, dérivée de hauteur = approche, stationnarité, temps de
  présence en zone sociale) → **machine à états** :

```
ABSENT → PRESENT → INTERESTED → ENGAGED → IN_CONVERSATION → COOLDOWN
```

  - PRESENT : personne détectée, loin ou en passage rapide/tangentiel →
    ne rien faire.
  - INTERESTED : approche OU mouvement lent en zone sociale → **regard**
    (gaze existant) + expression curieuse + gimmick sonore. Généreux,
    actif MÊME en roulant.
  - ENGAGED : porte du §5.2 (arrêt 3 s OU parole en zone, robot à l'arrêt) →
    expression accueillante, animation « invite », **micro armé**.
  - IN_CONVERSATION : le VAD confirme une parole exploitable → session
    ouverte, tenue tant que les échanges continuent.
  - COOLDOWN : 45 s après clôture ou invitation ignorée ; rejet encaissé en
    jeu (expression déception).
  - Perte de personne > 3 s → clôture de session + retour ABSENT.

- **Sorties** : topic `engagement` latché (état + confiance, patron
  `animation_state`), consommé par chat_node ; événements théâtraux
  (« invite », « accueille », « déçu ») vers face/animations **via
  l'arbitrage existant** ; JAMAIS rien vers cmd_vel (jusqu'à D6).

### 6.2 Adaptations chat_node (Pi vision)

- S'abonner à `engagement` : le VAD n'écoute qu'en ENGAGED/IN_CONVERSATION
  (le toggle `chat` régie reste master switch — ET logique).
- **Sessions** : ouverture/clôture pilotées par l'engagement — nouvelle
  entrée ChatDB par session, reset de l'historique, timeout de silence 12 s,
  retour visage au neutre en fin de session.
- Publier l'état interne (`listening`/`thinking`/`speaking`) sur un topic —
  nécessaire à l'engagement (tenir IN_CONVERSATION), utile à la régie et au
  télédiagnostic.
- **Enregistrement par session** (corpus type tournage) : audio conservé en
  tampon, bouton garder/effacer console, effacement par défaut.
- Prompt : persona (D3) + contrainte « court et relanceur » + langue du
  passant (whisper la détecte).

## 7. Lots D0 → D6 (décidés au grill)

| Lot | Contenu | Validation |
|---|---|---|
| **D0 — Mesures & calibration** | CPU Pi 5 en conversation complète ; enregistrements rue (VAD + intelligibilité TTS) + rejeu ; calibration hauteur de silhouette → mètres (1,2 / 2,4 / 3,6 m, adulte ET enfant) ; état chat exposé en topic | mesures consignées au §9 |
| **D1 — FSM v1 + micro gated + sessions** | `engagement_node` (logique pure + tests), signaux existants seuls (E1), gate `/cmd_vel`, groupe « dégradé digne », sessions + timeouts | sim d'abord (perception scriptée `/vision/person_box`) : passage / approche+arrêt / départ / bruit sans personne ; puis atelier |
| **D2 — Invitation non-verbale + rejet joué** | expressions « curieux »/« accueillant »/« déçu », gimmick sonore, animation « invite » (via arbitrage) | protocole atelier : l'enchaînement se lit sans mode d'emploi |
| **D3 — Persona & répliques** | atelier d'écriture (David + Dadou), system prompt, court-et-relanceur, multi-langues, latence < 2 s vérifiée (soupape whisper API si besoin) | conversations tests au casque + chrono latence |
| **D4 — Visage frontal (E2)** | face detection sur la cible, porte ENGAGED durcie, choix d'interlocuteur amélioré en groupe | atelier : passer devant sans regarder = pas d'armement |
| **D5 — Première rue chiffrée** | sortie ≥ 1 h en rue passante, dispositif corpus type tournage (affichage + bouton garder/effacer) | **grille de réussite ci-dessous** |
| **D6 — Verrous levés** | abordage verbal proactif ; abordage mobile (⟸ test scénique + e_stop W1 + suivi réel + protocole caméra) ; mémoire des gens | protocoles dédiés, à écrire le moment venu |

**Grille de réussite du test rue (D5)** — sortie ≥ 1 h, filmée pour
dépouillement :
- (a) **ZÉRO** prise de parole sans personne en zone sociale ;
- (b) **≥ 80 %** des conversations ouvertes jugées pertinentes à la revue
  vidéo ;
- (c) **≥ 10** conversations menées ET closes proprement ;
- (d) **zéro** insistance après refus.

Méthode maison inchangée : logique pure testée → sim → réel ; docs mises à
jour dans le même lot ; implémentation sur spec fermée déléguée (Sonnet),
revue par modèle fort. **Verrou d'entrée global : le protocole physique
chat_node V2 (chantier 0) doit passer d'abord.**

## 8. Points encore ouverts (assumés, pas oubliés)

1. ~~**Emplacement du prompt persona**~~ **TRANCHÉ le 2026-07-13** :
   versionné au repo public (`vision/ai/personas.py`) — texte de spectacle
   assumé, la CI vérifie que chaque variante embarque le contrat technique.
2. **Mécanisme de bascule whisper local/API** (et choix du fournisseur) :
   seulement si D0 condamne le CPU local.
3. **Le gimmick sonore et les expressions** : à créer en répétition (D2) —
   le plan ne fixe que leur existence, pas leur contenu.
4. **Garde-fous LLM** : « confiance au modèle » est un choix POUR L'INSTANT —
   réévaluer après chaque sortie (incident = retour de la question
   modération).
5. **Sortie son en rue** (puissance, intelligibilité) : mesurée en D0,
   matériel à trancher seulement si insuffisant.
6. **Contexte VISUEL de la conversation** — question soulevée le 2026-09-05,
   NON tranchée. Aujourd'hui la conversation est **100 % audio** : vérifié dans
   `conversation.py`, aucune image n'est jamais envoyée au LLM. Donner à Didier
   « ce qu'il voit » (un homme seul, une casquette rouge, un groupe d'enfants)
   suppose d'envoyer des images à un modèle de vision — et c'est là que le coût
   dérape si on le fait mal. **Garde-fous à respecter le jour où on l'ouvre** :
   - **Le local décide QUAND, le cloud ne voit QU'UNE image.** MediaPipe tourne
     déjà en permanence sur le Pi 5 (~24 % CPU, coût nul) et fournit présence,
     azimut, distance, persistance : c'est l'essentiel du contexte, gratuitement.
     Une image ne part QU'au basculement ENGAGED (§2), jamais en flux.
   - **Plafonds DANS LE CODE, pas dans l'intention** : jamais hors ENGAGED,
     délai minimal entre deux images, maximum par session. Même logique que le
     deadman roues — une limite qu'on espère n'est pas une limite.
   - **Compteur d'images par session, loggué** (boîte noire du télédiagnostic) :
     le coût réel se LIT après une déambulation, il ne se devine pas.
   - La fluidité perçue ne vient PAS de la fréquence des images : elle vient du
     gaze, déjà validé en réel — Didier suit du regard en local, donc il a l'air
     de regarder en continu. L'image n'a besoin d'exister qu'au moment où il
     ouvre la bouche.
   - En data 4G, ces images sont négligeables (quelques dizaines de Ko) : elles
     ne dimensionnent PAS le forfait (`etude-interface-web.md` §9.7).

## 9. Journal des mesures et décisions

*(à remplir au fil des lots — calibrations distance, seuils retenus, mesures
CPU/VAD de D0, résultats des protocoles)*

- 2026-07-12 : grill complet (8 axes) — toutes les décisions du §5, lots §7.
- 2026-07-13 : **D0 outillage FAIT** (dadou_vision_ros 53c6d13, 162 tests) :
  topic `chat_state` latché (listening/thinking/speaking/off, TRANSIENT_LOCAL
  des deux côtés comme animation_state), rejeu VAD de PROD sur wav
  (`python -m vision.audio.vad_replay`), scripts `enregistre-rue.sh`
  (16 kHz mono = format exact du pipeline), `mesure-cpu-conversation.sh`,
  `calibre-distance.sh` (protocole 1,2/2,4/3,6 m adulte ET enfant).
  **Reste de D0 = la campagne elle-même** (robot allumé + une sortie
  d'enregistrement) : mesures à consigner ici.
- 2026-07-13 : **atelier persona (D3, partie écriture + commutation) FAIT** :
  3 personnalités commutables (« bougon » défaut / « naif » / « vantard »,
  décisions reportées au §5.4), textes dans `vision/ai/personas.py` (repo
  public — §8.1 tranché), `StreamingBrain.reconfigure()` (nouveau prompt +
  nouvelle session ChatDB), topic `persona` + paramètre ROS + sélecteur
  console web (whitelist technique). 176 tests vision / 559 robot.
  **Reste de D3** : validation des textes par David, bouton télécommande
  (dadou_control_ros, avec le START télédiagnostic ?), multi-langues,
  chrono latence < 2 s en réel.

## 10. SPEC FERMÉE — gate « source audio vivante » (half-duplex élargi, 30/08)

Arbitrée le 2026-08-30. **Ne pas re-trancher** : implémentation directe.
Périmètre = dépôt `dadou_vision_ros` UNIQUEMENT (aucun chemin roues, aucune
modification de la lib partagée). Verrou levé : c'est le dernier point de code
bloquant avant le protocole physique chat_node V2 (chantier 0).

### 10.1 Ce qui existe déjà, et qu'il est INTERDIT de réécrire

Le relevé de code du 30/08 a corrigé le diagnostic : un demi-gate fonctionne
déjà. `ConversationEngine.run_once` coupe le micro avant que Didier ne parle
(`conversation.py:243`) et ne le rouvre qu'après `_player.drain()` (`:329`) ;
`MicCapture.stop()` purge le ring buffer pour qu'un redémarrage ne puisse
jamais faire réapparaître une trame antérieure à l'arrêt (`mic.py:95-111`,
verrouillé par `test_mic.py:175`).

Ce lot est donc un **élargissement de périmètre**, pas une implémentation
depuis zéro. Toucher à `mic.stop()` ou à sa purge est hors sujet.

### 10.2 Le principe : quatre canaux en OU

Le micro n'est armé que si **aucune** source audio n'est vivante dans le
châssis — qui EST l'enceinte (cf. `hardware/overview.md` §Echo). Un seul canal
suffit à bloquer :

| # | Canal | Source couverte | État |
|---|---|---|---|
| C1 | sa propre voix | TTS piper + bips | **DÉJÀ FAIT** (`mic.stop()`) |
| C2 | queue acoustique | réverbération + tampon ALSA après `drain()` | à faire |
| C3 | acoustique inconnue | **voix HF de David par la sono**, salle, klaxon | à faire — le cœur du lot |
| C4 | séquence de spectacle | piste audio d'une animation en cours | à faire |

C3 est le seul canal heuristique, et c'est celui qui ferme le trou réel : la
voix de l'interprète sort par le même châssis pendant que le micro écoute, donc
Didier transcrit David et lui répond (mode de panne du 11/07, **reproduit à la
demande le 26/08**).

### 10.3 Le module — `vision/audio/live_audio_gate.py`

Logique **PURE**, stdlib uniquement, horloge injectée — même patron que
`vision/audio/vad.py` (qui ne reçoit que des `float` déjà calculés et se teste
donc sans micro). Le calcul sur les octets reste dans `mic.py`, avec numpy.

```python
@dataclass(frozen=True)
class LiveAudioGateConfig:
    loud_rms: float = 2800.0   # −21,4 dBFS — cf. 10.4
    clip_peak: float = 32000.0 # −0,2 dBFS : l'entrée écrête sur la sono
    hold_s: float = 1.0        # maintien après la dernière trame bruyante
    tail_hold_s: float = 0.5   # queue acoustique après drain()

class LiveAudioGate:
    def __init__(self, config, now=time.monotonic): ...
    def feed(self, level: float, peak: float, show_audio: bool = False) -> bool:
        """True = BLOQUÉ, la trame doit être JETÉE."""
    def block_for(self, seconds: float) -> None: ...
    def arm_tail(self) -> None:   # block_for(config.tail_hold_s)
    @property
    def blocked(self) -> bool: ...
```

`feed` réarme le maintien jusqu'à `now + hold_s` dès que l'une des trois
conditions est vraie (`level > loud_rms`, `peak >= clip_peak`, `show_audio`),
et retourne `now < hold_until`. Le maintien couvre les pauses entre les mots :
sans lui, le gate battrait au rythme de la parole de David et rattraperait des
fragments entre ses syllabes.

`mic.py` gagne une fonction PURE `frame_peak(frame) -> float` (max des
valeurs absolues) exposée aussi en méthode liée, exactement comme `frame_rms`
— et pour la même raison : `vad_replay` doit pouvoir rejouer un enregistrement
de rue à travers le MÊME code que la prod.

⚠️ Un échantillon isolé à pleine échelle coûtera 1 s de surdité. C'est
**assumé** : le sens de la dégradation est le seul qui soit tolérable (cf.
10.6).

### 10.4 D'où viennent les valeurs — mesures du 26/08, pas des constantes magiques

`frame_rms` rend un RMS linéaire en unités int16 (0 à 32768), donc
`dBFS = 20·log10(rms / 32768)` :

| Mesure du 26/08 | dBFS | RMS linéaire |
|---|---|---|
| silence, ampli allumé | −60,0 | 33 |
| humain à 3 m | −32,4 | 786 |
| **seuil retenu `loud_rms`** | **−21,4** | **2800** |
| Didier par sa propre sono | −10,4 | 9897 |

Le seuil est posé au **milieu géométrique** des deux cas mesurés : **11,0 dB de
marge de chaque côté**, exactement. Ce n'est pas un réglage d'atelier, c'est le
point qui maximise la marge sur les deux erreurs possibles.

⚠️ **À recalibrer si le gain micro change** (changement de carte, d'alias ALSA,
de réglage `xvf_host`) : ces chiffres sont adossés à une chaîne d'acquisition
précise. Même piège que le seuil d'écrêtage de l'effet de prod (étude voix
§2.1) : changer un étage déplace la voix **en silence**.

**Conséquence acceptée** : un humain qui parle à moins de ~0,85 m dépasse le
seuil et sera pris pour la sono (11 dB = un facteur 3,5 en distance). Didier
ignorera donc quelqu'un qui se penche sur lui. C'est le prix de la marge, il
est mesurable pendant la campagne D0, et la DoA du ReSpeaker le lèvera plus
tard — mais **pas maintenant** : la carte n'est pas fixée, l'offset d'azimut
est inconnu, et un azimut absolu faux a l'air juste (cf. la `value 2` constante
à 90°).

### 10.5 Câblage

**`ConversationEngine`** : deux kwargs optionnels, `gate=None` et
`show_audio_active=None`. **`None` = comportement historique à l'octet près**
(les tests existants restent verts sans y toucher — c'est la clause qui rend le
lot réversible).

Dans `_listen_for_utterance`, une trame bloquée est **jetée AVANT la VAD** :

1. la VAD ne doit **jamais** voir une trame bruyante. Sa calibration est à
   usage unique (médiane des 1000 premières ms, `vad.py:100-110`) : une sono
   vivante pendant cette fenêtre empoisonne le seuil **pour toute la vie de
   l'instance**, et Didier devient sourd à un humain sans que rien ne le
   signale. C'est la raison n°1 de mettre le gate en amont ;
2. un blocage en pleine phrase **jette l'énoncé partiel** (`speech_bytes`
   remis à vide, `in_speech` à False) — jamais de recollage d'avant/après ;
3. le pré-roll est purgé (nouvelle méthode `MicCapture.purge_preroll()`,
   extraite du `self._ring.clear()` de `stop()` et appelée aux deux endroits) ;
4. la VAD est ramenée en IDLE par une méthode **publique** `EnergyVad.reset()`
   (délègue à `_reset_to_idle`, **conserve le seuil calibré**, no-op si encore
   en CALIBRATING). Sans ça une VAD restée en SPEECH attendrait son
   `end_silence_ms` sur des trames qu'elle ne reçoit plus.

`arm_tail()` est appelé **avant** `_mic.start()` dans les deux sorties de
`_speak_reply` — celle du succès (après `drain()`) **et celle de l'exception**,
où le player peut encore être en train de jouer.

**`chat_node`** : construit le gate depuis la config et fournit
`show_audio_active`. Celui-ci **réutilise** la méthode d'état effectif déjà
présente (`arbitration.effective_state`, `chat_node.py:477-481`) — ne pas la
dupliquer : c'est elle qui porte la péremption qui évite de rester sourd pour
toujours si `animations_node` meurt.

⚠️ **`CHAT_ANIMATION` ("parle") est EXCLUE de C4.** C'est l'animation que le
chat lance lui-même ; son audio est déjà couvert par C1+C2. L'inclure créerait
un blocage circulaire (chat sourd tant que son propre « parle » n'est pas
retombé).

⚠️⚠️ **CORRIGÉ le 30/08 à la revue — `None` est EXCLU AUSSI.** La première
rédaction de cette spec donnait `state not in ("", CHAT_ANIMATION)`. **C'était
faux**, et d'une manière qui ne se serait vue qu'au premier essai réel :
`effective_state` rend `None` tant qu'`animations_node` n'a **rien publié**
(Pi robot éteint, topic absent, node pas encore démarré), et
`None not in ("", "parle")` vaut **`True`** — le gate aurait bloqué **chaque
trame**, rendant Didier **sourd définitivement et en silence**. C'est
exactement la panne que la péremption deadman de `arbitration` existe pour
empêcher, et `allow_message` avait déjà tranché ce cas dans l'autre sens
(« jamais reçu : TOUT passe »).

**Ce qui rend l'exclusion sûre, et pas seulement commode** : C4 n'est pas le
canal porteur. Une piste audio de spectacle qui joue **vraiment** déclenche C3
acoustiquement — elle sort par la même sono, le micro l'entend. C4 ne fait que
l'anticiper. Ignorer une information **absente** ne coûte donc rien de réel ;
la lire comme « une séquence joue » coûte tout.

Formule juste, et elle vit dans **`arbitration.show_audio_live()`** (pas dans
`chat_node`) : les deux exclusions sont la même doctrine que celle
d'`allow_message`, elles se tranchent à un seul endroit.

```python
def show_audio_live(animation_state) -> bool:
    return animation_state not in (None, "", CHAT_ANIMATION)
```

*Règle générale que ce cas illustre, et qui vaut au-delà de ce lot* :
**ne jamais déduire un état actif de l'absence d'information.** Même
discipline que le garde-fou d'obstacle (`chantiers.md`, pistes en veille) :
exiger un battement de cœur positif, jamais lire un silence comme une valeur.

**Config** (`vision_config.py`) : `"chat_live_audio_gate": LiveAudioGateConfig()`
— un objet complet, même patron que `"chat_vad": VadConfig()`, pour rester
source unique de vérité si la dataclass gagne un champ.

### 10.6 Sens de la dégradation — la règle qui tranche tous les cas limites

**Bloquer à tort coûte une réplique manquée. Ne pas bloquer coûte une boucle** :
Didier s'entend, se répond, et sa réponse repart dans la sono. En cas de doute,
le gate bloque. Toute optimisation qui inverse ce sens est refusée.

### 10.7 Non-buts explicites (pour que le lot ne dérive pas)

- **Pas d'AEC** — l'entrée écrête (crête −0,0 dBFS, 65 échantillons saturés) :
  un AEC exige un chemin linéaire, il n'y a plus rien à soustraire. Mesuré,
  pas supposé.
- **Pas de barge-in** — physiquement hors de portée d'un robot qui EST la
  sono. Compensation dramaturgique : des répliques COURTES (§5.4).
- **Pas de DoA** (cf. 10.4), **pas de nouvel état ROS** : le contrat
  `chat_state` est déjà consommé par la console et le futur `engagement_node`,
  et un état qui bat à 33 Hz n'y a pas sa place. Les transitions du gate sont
  **journalisées en INFO** avec le niveau et la cause — le premier test micro
  réel s'est fait à l'aveugle faute de logs (11/07), on ne recommence pas.

### 10.8 Contrat de tests (c'est la spec, pas une suggestion)

`vision/tests/unit/test_live_audio_gate.py` : niveau fort bloque ; écrêtage
bloque **même sous le seuil de niveau** ; le maintien tient puis retombe ;
`arm_tail` bloque sur des trames silencieuses ; une séquence de spectacle
bloque mais **« parle » ne bloque pas** ; et surtout **gate ouvert = la trame
passe** — le test de POLARITÉ, celui qui interdit l'inversion silencieuse qui a
déjà coûté cher deux fois à ce projet (déphasage nul des capteurs d'odométrie,
contact NF du coup-de-poing).

Côté `test_conversation.py` : les trames bloquées n'atteignent **jamais** la
VAD (faux VAD compteur) ; un blocage en pleine phrase jette l'énoncé partiel ;
`gate=None` laisse le comportement strictement inchangé ; après `drain()` le
micro redémarre avec le gate amorcé. Côté `test_vad.py` : `reset()` conserve le
seuil calibré.

### 10.9 Découverte du 30/08 — la carte audio est déjà pilotée par logiciel

`hardware/overview.md` §Echo dit : « la carte audio commute déjà entre les
récepteurs HF et le Pi — **c'est cet état qu'il faut lire** ». Relevé fait :
cet état **est déjà en mémoire**, côté robot, dans
`robot/actions/relays.py` — un **PCF8574 à l'adresse 0x21** dont la broche 3
(`power_hf`) alimente le récepteur HF, la 1 (`effect`) l'octaver et la 0
(`voice_out`) la sortie voix. Il est basculé depuis la télécommande
(`relays.json`, touches D5/D6) et **n'est publié sur aucun topic**.

⚠️ **Mais il ne remplace PAS C3, et c'est pour ça qu'il n'est pas dans ce
lot** : il dit « David *peut* parler », jamais « David parle ». Bloquer le
micro sur le seul fait que le HF est alimenté rendrait Didier sourd pendant
tout le spectacle. Sa vraie valeur est ailleurs — un verrouillage
d'exploitation (« ne pas activer la parole IA pendant que le HF est vivant »)
et une ligne de boîte noire pour le télédiagnostic. À instruire quand le
chantier 0 sera passé au réel ; ça touchera le dépôt robot, pas celui-ci.

### 10.10 Révision du 08/11 — le micro se ferme sur le SON, pas sur le GESTE

> **08/11, plus tard dans la soirée : ce § redevient À FAIRE** — David : « la même règle pour
> tout le monde », Didier écoute en marche aussi pour les passants, qui n'ont pas de bouton
> (`etude-interaction-en-mouvement.md` §2 bis). Le paragraphe ci-dessous date du début de soirée.
>
> **DÉCISION DU 08/11 (David) — ce § est EN VEILLE, gardé pour les PASSANTS.**
> Quand c'est David qui parle, pas besoin de deviner : au casque le micro est le sien,
> et sur le robot il appuiera sur un bouton « c'est moi ». Le gate (C3/C4) existe pour un
> micro **dans le châssis qui est l'enceinte**, pas pour ça. **Fait le jour même** :
> `CHAT_MICRO_CONFIANCE=true` (banc, domaine 43 seulement) → gate non construit
> (`_chat_wiring.construire_gate`, clause `gate=None` du §10.5), comportement historique.
> Sur le robot : le bouton de la télécommande rendra ce « micro de confiance » dynamique
> (chantier télécommande RP2040). Le reste de ce § — publier si une séquence a du son —
> redevient utile le jour où Didier écoute des **passants** par le micro du châssis
> pendant qu'il bouge : à ressortir alors, tel quel.

**Le problème (séance A1, 08/11).** David est compris 1 fois sur 10. Le micro marche ;
c'est la tête qui le ferme à chaque geste de Didier. Le robot n'annonce que le *nom* de la
séquence en cours, jamais si elle a du son → la tête ferme le micro pour toutes. Le
sélecteur de jeu joue un geste toutes les 3-10 s, presque tous muets (15 des 18 séquences
`eternel-show`) : le micro est fermé la plupart du temps et la phrase en cours est jetée.
Seconde cause, réglée le jour même sur le banc : voix du casque trop forte, prise pour la
sono (`asound-pc.conf` ×0,15 → ×0,075, plus aucun blocage « niveau »).

**La règle (David, 08/11) : il écoute dès qu'il ne parle pas.** Micro ouvert sauf si un
son sort de Didier : sa voix (déjà fait), **ou une piste audio de séquence** (le geste
muet ne compte plus), ou une source vivante au micro (déjà fait).

**La solution.** Le robot publie un second état, `animation_audio_state` : le nom de la
séquence **si elle a une piste audio**, sinon `""`. La tête ne ferme le micro que là-dessus.
Même forme que `animation_state` (latché, `time` = temps restant → péremption deadman).
Pourquoi un topic de plus et pas un `animation_state` enrichi : trois lecteurs (gaze, chat,
jeu) attendent une chaîne et traiteraient autre chose comme « repos » — aveugles aux
séquences pendant le déploiement, qui se fait Pi par Pi. Le champ `StringTime.anim` est
déjà pris (« vient d'une animation », deadman roues).

**Ce que ça ne rend jamais pire.** Tête mise à jour avant le robot : topic jamais reçu →
elle n'en tient pas compte → elle écoute (le canal acoustique couvre). Robot avant la
tête : un topic que personne ne lit. Aucun ordre ne rend Didier sourd.

**À trancher**

| # | Question | Proposition | Si on choisit l'autre voie |
|---|---|---|---|
| 1 | Garder une fermeture pendant une séquence **à son** ? | **Oui** (C4 sur le son) | Supprimer C4 : une piste discrète (sous 2800 RMS) serait transcrite et Didier se répondrait ; une piste jouée pendant la calibration de la VAD fausserait son seuil pour toute la session |
| 2 | Granularité : la **séquence** ou le **clip** ? | **Séquence** (10 s de séquence avec 2 s de son = 10 s fermées) | Le clip : `audio_node` publierait « clip en cours » ; plus juste, lot séparé, à instruire si la gêne se mesure |
| 3 | Tour spontané pendant un geste muet ? | **Autorisé** (sa voix part, le visage reste au geste — déjà le cas quand David lui parle pendant une séquence) | L'interdire : garder l'interdit sur « toute séquence », au prix de tours spontanés rares dès que le sélecteur bouge |

**Spec d'implémentation** (fermée si les 3 propositions tiennent ; Opus ; relecture adverse
du câblage tête avant déploiement — le piège du 30/08, `None` lu comme actif, revient vite
par copier-coller).
- Contrat : `theatre_contrats.topics.ANIMATION_AUDIO_STATE = 'animation_audio_state'` ;
  `docs/interfaces.md` ligne sous `animation_state`.
- Robot (`didier_core`) : `AnimationManager.audio_state_name()` (`""` sans séquence ou sans
  piste, sinon le nom) ; `animations_node._publish_state` publie les deux, mêmes transitions,
  même QoS.
- Tête (`didier_vision/chat_node`) : second abonnement, second couple état/échéance tenu par
  `_on_animation_audio_state` qui réutilise `parse_animation_state` + `state_expiry` ;
  `_show_audio_active()` lit ce couple (formule `show_audio_live` inchangée : `None`, `""`,
  `"parle"` exclus) ; `allow_message` continue de lire `animation_state` (le visage ne change
  pas de règle).
- Tests gravés : `audio_state_name` sur les vrais JSON (`aurore` → `"aurore"`, `little-neck`
  → `""`, repos → `""`) ; constante de topic ; câblage tête : `animation_state="little-neck"`
  seul → micro ouvert, `animation_audio_state="aurore"` → fermé, 5,1 s après → ouvert, `face`
  retenu pendant `little-neck`. Mutation : rebrancher `_show_audio_active` sur
  `animation_state` doit faire rougir ; retirer l'exclusion de `None` aussi.
- Fumée : l'épreuve `parle` relève aussi `animation_audio_state` (« parle » a une piste),
  compteur gravé mis à jour. Sim : séance A1 10 min, `cause=spectacle` seulement pendant les
  séquences à son.
- Docs du lot : ce §, `interfaces.md`, `chantiers.md`, renvoi dans
  `etude-arbitrage-actionneurs.md`. Déployer les 2 Pi, `ecart-pi.sh` vert.

## Sources

- Hall, *The Hidden Dimension* (1966) ; Walters et al. 2005 (validation HRI).
- Michalowski, Sabanović & Simmons, *A Spatial Model of Engagement for a
  Social Robot*, IEEE AMC'06 —
  <https://www.ri.cmu.edu/pub_files/pub4/michalowski_marek_piotr_2006_3/michalowski_marek_piotr_2006_3.pdf>
- Satake, Kanda et al., *How to Approach Humans?*, HRI'09 —
  <https://dl.acm.org/doi/10.1145/1514095.1514117>
- Kanda et al., *Behavioral Assessment of a Humanoid Robot When Attracting
  Pedestrians in a Mall*, IJSR 2022 —
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC9331028/>
- Rich, Ponsler, Holroyd & Sidner, *Recognizing Engagement in Human-Robot
  Interaction*, HRI'10 — <https://dl.acm.org/doi/10.1145/1734454.1734580>
- Vaufreydaz, Johal & Combe, *Starting Engagement Detection Toward a
  Companion Robot Using Multimodal Features*, 2015 —
  <https://arxiv.org/abs/1503.03732>
- Foster et al., *MuMMER: Socially Intelligent Human-Robot Interaction in
  Public Spaces*, 2019 — <https://arxiv.org/abs/1909.06749>
- Pelikan, *Encountering Autonomous Robots on Public Streets*, 2024 (« robot
  privilege ») ; littérature gaze-cues piétons (IJSR 2023).
