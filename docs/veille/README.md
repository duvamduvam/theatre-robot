# Veille robotique hebdomadaire

Une page HTML par semaine (`AAAA-MM-JJ.html`), sommaire dans `index.html`.
Créée le 2026-11-02 à la demande de David : se tenir au courant des avancées
**utilisables par Didier**, pas de l'actualité robotique en général.

## Comment elle tourne

- Orchestration IAction `veille-robotique` (`.iaction/orchestrations/`), agents
  `veilleur` (collecte, Sonnet) et `redacteur-veille` (tri + rédaction).
  ⚠️ `.iaction/` n'est pas versionné : ce README est la référence pour les recréer.
- Tâche planifiée `veille-robotique` : chaque lundi 08:00, créée **désarmée**.
  David l'arme dans IAction, page Orchestration.
- Deux collectes en parallèle, déposées brutes dans `brut/` (traçabilité : la
  page ne cite que ce qui est dans la collecte), puis une rédaction qui commite
  **uniquement** `docs/veille/`.
- Fenêtre : depuis la dernière édition (7 jours par défaut).

## La règle du tri (ce qui fait la valeur de la page)

Une nouveauté n'entre que si on peut dire **à quel chantier elle sert et ce
qu'elle changerait**. Sinon elle va en « Vu, écarté » en une ligne, ou nulle part.
La veille **propose**, elle ne modifie jamais un chantier ni une décision déjà
tranchée (voir les « ne pas re-trancher » de `docs/chantiers.md`).

Aucun prix, aucune date, aucune version qui ne soit lue à la source et liée.

## Centres d'intérêt (à tenir à jour avec les chantiers)

| Chantier | Ce qu'on guette |
|---|---|
| Conversation (chat_node V2) | STT/TTS locaux en français, voix féminines, LLM petits, latence, speech-to-speech, VAD, réseaux de micros |
| Mouvement autonome (A1…A4) | lidar 2D abordable, Nav2, py_trees/BehaviorTree, sécurité (e-stop, deadman, safety controller), twist_mux |
| Suivi de personne / gaze | détection et pose de personne légères, caméras de profondeur, Hailo, Jetson Orin Nano |
| Bras expressif futur | LeRobot, bras SO-101 et successeurs, servos à bus série, apprentissage par imitation, animation de robots |
| Visage, émotions, jeu | robotique sociale, HRI, robots de spectacle, animation expressive (Disney Research…) |
| Socle | ROS 2 Jazzy et distro suivante, ros2_control, Gazebo, micro-ROS (télécommande RP2040), Docker sur Pi |
| Calcul et énergie | Raspberry Pi / AI HAT, Jetson (JetPack), BMS et packs 18650 |

## Sources

Volet ROS et matériel :
- ROS Discourse, billets « ROS News for the Week » et annonces de paquets
- Notes de version Nav2, ros2_control, Gazebo, micro-ROS
- Blogs Raspberry Pi, NVIDIA Jetson, Luxonis, Orbbec, Slamtec
- The Robot Report (seulement ce qui touche les centres d'intérêt)

Volet IA et social :
- Hugging Face LeRobot (GitHub releases, blog Hugging Face)
- Modèles de parole : piper, Kyutai, Mistral (Voxtral), whisper.cpp
- IEEE Spectrum « Video Friday »
- Conférences HRI, ICSR, IROS, CoRL (résumés seulement)

## Structure d'une édition

1. **À retenir cette semaine** : 1 à 3 items, avec ce que ça changerait pour Didier.
2. **Par chantier** : une carte par item retenu (source, date, ce que c'est,
   intérêt pour Didier, verdict : *à essayer*, *à surveiller*, *pour plus tard*).
3. **Vu, écarté** : une ligne par item, avec la raison.
4. **Sources de la semaine** : liens vers les deux fichiers de `brut/`.
