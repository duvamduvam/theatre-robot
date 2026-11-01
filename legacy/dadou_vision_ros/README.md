Dadou Vision

## Outillage D0 conversation

Outils du lot D0 (mesures & calibration) du chantier "conversation en
déambulation" (cf. `../dadou_robot_ros/docs/etude-declenchement-conversation.md`) :

- **Topic d'état du chat** `chat_state` (StringTime latché, `listening` /
  `thinking` / `speaking` / `off`) publié par `chat_node` — abonnez-vous-y
  pour observer l'état interne de la conversation (régie, télédiagnostic,
  futur `engagement_node`) : `ros2 topic echo /chat_state`.
- **Rejeu VAD sur enregistrement** (mesure le taux de déclenchement du VAD de
  prod sur du son capté en rue, sans resampling) :
  `python -m vision.audio.vad_replay fichier.wav [autres.wav...]`.
- **Enregistrement micro rue** (16 kHz mono 16 bits, segments de 60 s) :
  `conf/scripts/enregistre-rue.sh [dossier_de_sortie] [duree_totale_s]`.
- **Mesure CPU/RAM en conversation** (échantillonnage 1 Hz vers un CSV,
  host ou conteneur) : `conf/scripts/mesure-cpu-conversation.sh [duree_s] [dossier_de_sortie]`.
- **Calibration distance** (hauteur de silhouette `/vision/person_box` ->
  mètres, à lancer dans le conteneur vision) :
  `conf/scripts/calibre-distance.sh <distance_en_m> [dossier_de_sortie]`.

## Personnalités de Didier (lot D3)

Quatre personnalités commutables (`vision/ai/personas.py`, brouillons
d'atelier du 2026-07-13 à valider avec David) : `bougon` (défaut, config
`chat_persona`), `naif`, `vantard`, et `mauvaisefoi` (lot R3 du 14/10, écrite
pour la répétition simulée : chaque panne est « une fonctionnalité ») — socle commun (robot assumé, complice
des enfants, esquives par opinions absurdes) + variante du jour. Changement
à chaud (nouvelle session de conversation) :
`ros2 topic pub --once persona robot_interfaces/msg/StringTime "{msg: 'naif'}"`
— ou les boutons « Personnalité » de la console web côté robot.

## Topics de régie du chat (14/10)

Lot R3 « Chantiers » (spec fermée : `../dadou_robot_ros/docs/etude-repetition-simulee.md`
§13.4 point 3 et §13.6). Logique pure dans `vision/ai/stage.py` (testée sans ROS),
câblage dans `chat_node`. Tous en `robot_interfaces/StringTime` :

| Topic | Sens | Contrat |
|---|---|---|
| `chat_text` | sub | Texte « entendu » sans micro ni STT (clavier de la régie). JSON string ou brut, vide refusé. Servi au prochain tour, même micro mort ; coupe une écoute en cours. |
| `chat_instruction` | sub | Consigne de jeu courante, JSON string ou brut ; `""` = levée. Envoyée au LLM comme second message system (« Consigne de mise en scène (à jouer, jamais à prononcer) : … ») à chaque tour ; **péremption locale 120 s**. |
| `rehearsal/chat_fault` | sub | Panne publiée par le régisseur de la répétition simulée : JSON `{"op": pass\|delay\|garble\|deaf\|mute\|phantom, "params": {...}, "until_ms": n}`, `until_ms` = DURÉE en ms (même convention que les ordres relais). **Plafond local 60 s** (None/absurde = 60 s). `delay` (`delay_ms` 1..60000) = sommeil avant le LLM ; `garble` = texte compris remplacé par un contresens (liste gravée ou `params.texts`) ; `deaf` = énoncés jetés ; `mute` = répliques non synthétisées (texte publié quand même) ; `phantom` (`params.text`) = ponctuel, servi comme un énoncé entendu. Sans effet en prod tant que personne ne publie. |
| `chat_transcript` | pub | Flux (QoS volatile, depth 10) : JSON `{"role": "david"\|"didier", "text", "t_ms"}` (`t_ms` = epoch ms). `david` = ce que Didier a compris (après garble), `didier` = chaque phrase. Jamais les consignes ni les pannes. |

Test à la main (domaine 43) :
`ros2 topic pub --once chat_text robot_interfaces/msg/StringTime "{msg: 'bonjour Didier'}"`.
