# Rapport de collecte brut : ROS 2 en 2026, alternatives, robots de spectacle, HRI, sécurité, simulation

Date de consultation : 2026-11-11. Rapport de collecte, pas un livrable. Aucune conclusion ni recommandation.

## Couverture et méthode

- Pages chargées en entier (LU) : 11 sur un plafond de 12. Marquées **[LU]**.
- Faits venant seulement d'un résumé de moteur de recherche (page non ouverte) : marqués **[EXTRAIT]**. Ces résumés sont produits par l'outil de recherche, pas par moi : à vérifier avant citation chiffrée.
- Pages LU : metrics 2025, ros4hri packages, copper-rs GitHub, dora GitHub, INRS, Discourse « Challenges commercial robots », Reachy 2 Discourse, Isaac Sim 6.2 requirements, wiki Engineered Arts Ameca, Discourse « Frustrations hobby ROS 2 », (EUR-Lex a été tenté : contenu vide renvoyé).
- Non couvert : Drake, Zenoh seul/NATS/MQTT (hors un témoignage), Isaac ROS, Genesis (licence primaire), Webots (licence primaire), O3DE, Disney (page primaire), Hugging Face/LeRobot (page primaire), Furhat/Misty/Navel (détail), Bottango→Blender, pratique des petits fabricants (relais de sécurité), assurance/vitesse pour robots de divertissement, coût CPU ROS4HRI sur Pi 5, texte exact Art. 2/3 du règlement Machines, ISO 13850 texte normatif, ISO 13482 détail, ISO 3691-4 vitesse.
- Aucun prix relevé dans ce rapport sauf Viam (voir Q2). Tout est en monnaie d'origine, rien converti.

## Tableau de synthèse

| Sujet | Fait | Statut | Source |
|---|---|---|---|
| ROS 2 part des téléchargements ROS | 91,2 % (oct. 2025) | LU | discourse.openrobotics.org/t/2025-ros-metrics-report/52575 (19/02/2026) |
| Humble / Jazzy | 48,53 % / 24,45 % | LU | idem |
| Téléchargements 2025 | 984 135 185 (+85,18 % vs 2024) | LU | idem |
| IP uniques oct. 2025 | 1 315 867 (oct. 2024 : 843 959) | LU | idem |
| dora-rs | Apache-2.0, 4,1k étoiles, 1.0 (02/09/2026) | LU | github.com/dora-rs/dora |
| copper-rs | Apache-2.0, 1,5k étoiles | LU | github.com/copper-project/copper-rs |
| rmw_zenoh | Tier 1 depuis Kilted ; défaut Lyrical = Fast DDS | EXTRAIT | docs.ros.org + Discourse (mai 2026) |
| Règlement Machines 2023/1230 | application 20/01/2027 | LU (INRS) + EXTRAIT | inrs.fr |
| Isaac Sim 6.2 | min RTX 4080 16 Go, 32 Go RAM | LU | docs.isaacsim.omniverse.nvidia.com/6.2.0 |
| ROS4HRI | Jazzy = distro principale ; hri_face_detect etc. « from sources » | LU | ros4hri.github.io/packages.html |

## Q1. Adoption de ROS 2

### 1.1 2025 ROS Metrics Report [LU, page communautaire officielle Open Robotics, post du 19/02/2026]
URL : https://discourse.openrobotics.org/t/2025-ros-metrics-report/52575
- ROS 2 = 91,2 % de tous les téléchargements ROS (octobre 2025).
- Humble 48,53 % ; Jazzy 24,45 %.
- ROS 1 : 12 206 979 paquets (oct. 2024) -> 11 590 884 (oct. 2025), baisse d'un peu plus de 5 %.
- 984 135 185 paquets téléchargés en 2025, +85,18 % vs 2024, malgré les données de juillet manquantes.
- IP uniques octobre 2025 : 1 315 867 contre 843 959 en octobre 2024 (près de +56 %).
- Méthode : AWStats sur serveurs OSU OSL ; migration de juillet 2025 a perdu la plupart des logs de juillet, recalcul manuel. Les auteurs parlent d'« estimations » et de « borne basse raisonnable ». Pas de ventilation par pays.
- Précaution : ce sont des téléchargements, pas des déploiements en production.

### 1.2 Rapport 2024 [EXTRAIT, non ouvert]
URL : https://discourse.openrobotics.org/t/2024-ros-metrics-report/42354
- ROS 2 = 72 % des téléchargements ; Humble 39,39 % vs Noetic 22,18 % (oct. 2024).

### 1.3 Part des entreprises en production
Non trouvé. Aucune enquête 2025/2026 chiffrée trouvée. Seuls trouvés : étude académique Rocha et al. (oct. 2024, >100 participants, raisons de non-migration ROS 1->2), https://link.springer.com/article/10.1007/s41315-024-00393-4 [EXTRAIT, chiffres non lus] ; enquête Open Robotics 2020, obsolète [EXTRAIT] ; compte rendu ROS-Industrial Conference 2025 (17/02/2026), anecdotique : https://rosindustrial.org/news/2026/2/17/ros-2-in-industry-key-takeaways-from-the-ros-industrial-conference-2025 [EXTRAIT].

### 1.4 Témoignages et critiques
- « Challenges with ROS2 on commercial robots » [LU, fil Discourse, 25/03-02/04/2025] https://discourse.openrobotics.org/t/challenges-with-ros2-on-commercial-robots/42784
  - Nauticus (robots sous-marins) : confusion callback groups/executors ; DDS lent sur gros messages (RTI conseille ~60 participants DDS ; nœuds composables aidant) ; rosdep tire des dépendances lourdes (images Docker de dizaines de Go contre centaines de Mo en build manuel) ; ROS inadapté aux modems acoustiques, communication maison.
  - ivaughn-spear : lecture des rosbags MCAP exige un workspace complet de même version ; IDL ROS sans champs optionnels, contournement par traduction en protobuf ; ticket rosidl #850.
  - chfritz cite un exposé NVIDIA : pas de calcul non-CPU, pas de replay déterministe, fiabilité de livraison.
  - JM_ROS (automatisation de cellules) : récupération après arrêt d'urgence, supervision maison car cycle de vie standard insuffisant.
- « Frustrations With State Of Hobby ROS 2 Robotics » [LU, 02-29/02/2024] https://discourse.openrobotics.org/t/frustrations-with-state-of-hobby-ros-2-robotics/35900
  - Auteur (ingénieur logiciel, 2 ans de robot maison ROS 2) : « simple architecture to learn and yet such a complex environment to build a robot » ; Pi 5 à ~50 % CPU = goulot à 100 % sur Create3, attribué par lui aux middlewares par défaut (diagnostic non confirmé dans le fil).
  - Réponse mainteneur (Katherine_Scott, 23/02/2024) : DDS « sub-optimal for a lot of simple use cases, especially over WiFi », renvoie vers RMW Zenoh prévu pour Jazzy ; limite = ressources humaines.
  - Autres répondants : burn-out sur projets ROS solo (iliao, Hal_cat).
- Billet d'un amateur ayant quitté ROS 2 pour NATS + Protobuf (AUV) [EXTRAIT, page = résumé généré par IA, original non lu] https://bot-vault.pages.dev/ai/Clippings-my-problems-with-ros-2-and-why-im-going-my-own-way-and-salty-about-it
- Fil Hacker News (PeppyOS) [EXTRAIT] https://astro-hacker-news.pages.dev/47296255 : un commentateur dit que le projet est né de la frustration envers ROS ; autre : écrire son propre middleware serait « un rite de passage » (dates non relevées).
- Neobotix a arrêté le support ROS 1 pour pousser vers ROS 2 [EXTRAIT] https://www.neobotix-robots.com/company/news-events/detail/announcement-transitioning-from-ros-noetic-to-ros-2-embracing-the-future
- Équipe projet Hackaday revenue à ROS 1 faute de documentation ROS 2 [EXTRAIT] https://hackaday.io/project/181449/log/197314 (date non relevée).
- Aucun billet « why we left ROS » d'une startup en 2025-2026 trouvé (recherche faite, résultat négatif).

### 1.5 Réponses côté ROS
- rmw_zenoh Tier 1 dans Kilted ; défaut Lyrical = rmw_fastrtps_cpp, changement de défaut « non considéré » pour cette release (fil Discourse mai 2026) [EXTRAIT] https://discourse.openrobotics.org/t/upcomming-rmw-feature-freeze-april-6th-2026-ros-lyrical/53696.md ; https://docs.ros.org/en/lyrical/Installation/RMW-Implementations/Non-DDS-Implementations/Working-with-Zenoh.html
- Rapport Open Robotics sur middleware alternatif (Zenoh retenu) [EXTRAIT] https://discourse.openrobotics.org/t/ros-2-alternative-middleware-report/33771

## Q2. Alternatives à ROS 2

### dora-rs [LU] https://github.com/dora-rs/dora (consulté 11/11/2026)
- Licence Apache-2.0 ; 4,1k étoiles, 476 forks. Annonce « dora 1.0 is out » ; date 2026-09-02 déduite du nom de fichier du billet lié (pas affichée).
- Rust et Python >=3.11 en première classe ; C/C++ supportés ; pont ROS 2 (Foxy+) expérimental (topics/services/actions via DDS ou rmw_zenoh_cpp ; pas d'Operator API).
- Limites déclarées : reprise des dataflows après redémarrage du coordinateur « partielle » ; Node Hub « unstable » ; Windows/WSL « best effort ».
- Article japonais [EXTRAIT] https://www.issoh.co.jp/md/tech/8827 : 1.1.0 le 8 oct. 2026 ; 1.0 non interopérable avec 0.x ; latence Python-Python annoncée 10-17x plus faible que rclpy (benchmark du projet, non vérifié).
- Navigation / simulation / outils : rien d'affiché sur la page lue.

### Copper (copper-rs) [LU] https://github.com/copper-project/copper-rs (consulté 11/11/2026)
- Apache-2.0 ; 1,5k étoiles, 112 forks, 1 829 commits ; Releases vide ; exige Rust 1.96+.
- Graphes de tâches statiques (RON) compilés ; journal `.copper` avec replay déterministe ; démos de simulation navigateur (robot auto-équilibré, quadricoptère) ; pont ROS 2 via Zenoh ; plateformes : Linux, macOS, SBC, microcontrôleurs bare-metal ; support Python lié sans détail.
- Navigation : non mentionnée sur la page.

### Zenoh [EXTRAIT]
- Retenu comme alternative DDS dans ROS 2 (voir 1.5). Zenoh « seul » comme remplaçant de ROS : non étudié.

### Viam [EXTRAIT, non ouvert] https://www.viam.com/pricing ; https://github.com/abe-winter/rdk
- viam-server sous AGPLv3 (dépôt, fork) ; site : « open-source » sur le matériel. Palier développeur gratuit, usage cloud facturé après 5 $/mois (devise $ ; HT/TTC non précisé). Offre industrielle « à partir de 120 000 $ par an » signalée puis retirée de la grille selon un suivi tiers (https://pricingsaas.com/companies/viam/diffs/2026W46). Licence des SDK et du cloud non confirmée.

### LeRobot (Hugging Face) [EXTRAIT] https://huggingface.co/docs/lerobot/en
- Apache 2.0 (plusieurs sources tierces) ; bibliothèque d'apprentissage de robots, bras SO-101 (~130 $ de pièces selon une source tierce). Rôle de « pile de robot » complète : non établi.

### Basis [EXTRAIT] https://hn.svelte.dev/item/41976368
- Show HN : framework C++ pub/sub orienté tests et production, topics/types déclarés en fichier de config, Protobuf. Date, licence, état actuel, support Python : non trouvés.

### HORUS [EXTRAIT] https://users.rust-lang.org/t/i-was-tired-of-ros2-so-i-rewrote-it-in-rust/135139 ; https://hackaday.com/2026/01/09/horus-framework-a-rust-robotics-library
- Framework Rust, IPC mémoire partagée, bindings Python/C++ ; créé oct. 2025 ; 123 étoiles début 2026 (obsolète) ; performances annoncées (87 ns, 296 ns, 11-196 ns ; 100x-575x vs ROS 2) = chiffres du projet, contradictoires entre eux.

### Autres
- Drake, MQTT/NATS maison, Isaac ROS : non trouvé (pas recherchés en détail ; NATS cité seulement dans le billet AUV ci-dessus).
- Hiroz (ZettaScale) : annonce Discourse [EXTRAIT] https://discourse.openrobotics.org/t/introducing-hiroz-by-zettascale/55081 (contenu non lu).
- Mouvement mesurable de migration hors ROS : non trouvé. Seule mesure trouvée = téléchargements ROS en hausse (1.1).

## Q3. Robots de spectacle / sociaux

- Pollen Robotics Reachy 2 [LU, annonce Discourse du 23/04/2025] https://discourse.openrobotics.org/t/reachy-2-humanoid-full-ros-2-dev-stack-now-open-source-one-line-docker-sim-python-sdk/43362 : middleware ROS 2 Humble (ros2_control, TF, state publishers) ; contrôle bas niveau en Rust ; SDK Python `reachy2-sdk` ; simulation Gazebo, MuJoCo « coming soon » ; dépôts Blender (`reachy2-blender`), émotions, IK symbolique ; licence « open-source » non nommée (Apache 2.0 affirmée par un catalogue tiers, non confirmée).
- Reachy Mini [EXTRAIT] https://huggingface.co/docs/reachy_mini/main/SDK/python-sdk : SDK Python via pip avec démon ; ROS non mentionné dans les résultats.
- Engineered Arts Ameca [LU, wiki, modifié le 29/07/2024] https://wiki.engineeredarts.co.uk/Ameca : Gen 2 sous « Tritium 3 », Gen 1 sous « Tritium 2 » ; ROS non mentionné ; animations « Virtual Robot » appelables par API REST et Python ; IDE Python intégré (Gen 1) ; Blender non mentionné. Une source tierce [EXTRAIT] (https://www.robotics247.com/article/ameca_humanoid_robot_engineered_arts_debuts_ces_2022) dit qu'ils ont choisi leur OS plutôt que ROS ; citation non vérifiée sur la page.
- Disney BDX / personnage bipède : [EXTRAIT] https://arxiv.org/html/2501.05204v1 (Disney Research, janv. 2025) : conception pilotée par l'intention artistique ; l'apprentissage par renforcement transforme des animations en politiques de contrôle (récompenses d'imitation) ; un « moteur d'animation » mélange des sources d'animation à l'exécution ; un opérateur par robot. Entraînement PPO sous Isaac Gym selon une revue tierce (à vérifier). Utilisation de ROS par Disney : non trouvé.
- Newton (Disney Research, Google DeepMind, NVIDIA) : annoncé au Linux Foundation le 29/09/2025 [EXTRAIT] https://www.linuxfoundation.org/press/linux-foundation-announces-contribution-of-newton-by-disney-research-google-deepmind-and-nvidia-to-accelerate-open-robot-learning ; Apache 2.0, bêta, basé sur NVIDIA Warp.
- Enchanted Tools Mirokaï [EXTRAIT, presse] https://www.electronicdesign.com/technologies/embedded/video/55278100/enchanted-tools-mirokai-cobot-is-designed-to-interact-with-people : ROS avec logiciel maison, deux modules NVIDIA Jetson. Page éditeur indique qu'en 2026 un accompagnateur doit rester proche pour raisons de sécurité [EXTRAIT] https://enchanted.tools/buy-mirokai.
- Furhat [EXTRAIT] https://furhatrobotics.com/furhat-sdk : SDK Kotlin/Java, robot virtuel inclus ; Realtime API multi-langages (Python, JS, C++, etc.). ROS : non mentionné.
- Misty [EXTRAIT] https://docs.mistyrobotics.com/misty-ii/web-api/overview/ : API HTTP, SDK JS/.NET. Rachat par Furhat en 2022 : non vérifié.
- Navel Robotics [EXTRAIT] : studio GUI + SDK Python cités dans une étude (https://arxiv.org/pdf/2605.21053) ; pas de doc publique trouvée.
- Bottango [EXTRAIT] https://www.digikey.com/en/maker/tutorials/2024/how-to-get-started-with-bottango : outil gratuit, timeline à keyframes, envoie des commandes série à un microcontrôleur compatible Arduino ; Windows/Mac/Linux ; API pour autres microcontrôleurs. Import Blender : non trouvé.
- Compagnies de théâtre robotique et pile utilisée : non trouvé.

## Q4. HRI, voix, LLM+ROS

### ROS4HRI [LU] https://ros4hri.github.io/packages.html (consulté 11/11/2026)
- « primarily developed and tested on ROS 2 Jazzy » ; Noetic « maintenance mode » ; Humble et Rolling « should also work », moins testés.
- Paquets : hri_face_detect, hri_emotion_recognizer, hri_face_identification, hri_body_detect, asr_vosk, hri_person_manager, hri_engagement, hri_face_body_matcher : « from sources » (sauf face_body_matcher en apt). hri_msgs, hri_actions_msgs, human_description, libhri, pyhri, hri_rviz : `apt install ros-<distro>-...`.
- Seule organisation nommée : PAL Robotics (copyright). Adoption hors PAL : non trouvé.
- REP-155 : « still evolving » [EXTRAIT] https://docs.ros.org/en/independent/api/rep/html/rep-0155.html.
- Index ROS : hri_face_detect 2.2.2 listé pour Humble, « No version for distro jazzy showing humble », changelog 09/07/2025 [EXTRAIT] https://index.ros.org/p/hri_face_detect/ ; hri_msgs branche Jazzy 2.3.2 (10/02/2026) [EXTRAIT]. Contradiction avec « Jazzy principal » ci-dessous.
- hri_face_detect actuel : YuNet + MediaPipe Face Mesh [EXTRAIT] https://docs.ros.org/en/humble/p/hri_face_detect.
- Coût CPU sur Raspberry Pi 5 : non trouvé (aucun benchmark ROS4HRI). Chiffres tiers non ROS4HRI : MediaPipe face detection 15-40 FPS sur Pi 4, CPU 40-50 % [EXTRAIT] https://www.mintlify.com/Daval03/Eulerian-Vitals-Extraction/guides/raspberry-pi-deployment (projet différent, non vérifié).

### Conversation vocale temps réel
- Pipecat : pipeline Python (VAD, STT, LLM, TTS), transports Daily/WebSocket/Twilio/LiveKit ; LiveKit Agents : WebRTC ; les deux acceptent un modèle speech-to-speech [EXTRAIT] https://livekit.com/blog/best-open-source-voice-and-video-ai-agent-frameworks ; https://medium.com/@hello_18940/livekit-vs-pipecat-for-voice-ai-orchestration-e8780fe3e5d3.
- Ponts ROS : `polymathrobotics/livekit_ros2_bridge` (JSON via LiveKit <-> topics/services ROS 2, testé Humble, Jazzy, Kilted, Rolling) [EXTRAIT] https://gh.r-mj.com/polymathrobotics/livekit_ros2_bridge ; doc LiveKit robotique (tool calls -> RPC) https://docs.livekit.io/robotics/start/use-cases/voice/ [EXTRAIT] ; EdgeVox a un pont ROS 2 optionnel [EXTRAIT] https://edgevox.pages.dev/guide/ros2. Pont Pipecat->ROS 2 : non trouvé.

### LLM + ROS
- ROSA (NASA JPL) : agent LangChain ReAct, ROS 1 Noetic et ROS 2 Humble/Iron/Jazzy, Apache-2.0, pip `jpl-rosa` [EXTRAIT] https://arxiv.org/html/2410.06472v1 et https://www.sourcepulse.org/projects/1827782 (état de maintenance non vérifié).
- RAI (Robotec.AI) : cadre d'agents embodied sur ROS 2 (Jazzy/Humble), paquets rai_asr, rai_tts, rai_sim, rai_bench, etc. ; article arXiv mai 2025 [EXTRAIT] https://github.com/RobotecAI/rai ; https://arxiv.org/pdf/2505.07532. Deux dépôts (RobotecAI/rai et EmbodiedAINexus/rai), canonique non établi.
- ros2ai : cité dans un exposé ROSCon 2024 comme extension CLI [EXTRAIT] https://roscon.ros.org/2024/talks/Agent-based_AI_Framework_for_ROS_2.pdf ; dépôt/état : non trouvé.
- ros-mcp-server (robotmcp) : MCP via rosbridge, ROS 1/2 [EXTRAIT] https://www.sourcepulse.org/projects/14363566 ; autres serveurs MCP ROS homonymes existent.
- Fil Discourse « Building and Integrating AI Agents for Robotics » [EXTRAIT, non lu] https://discourse.openrobotics.org/t/building-and-integrating-ai-agents-for-robotics-experiences-tools-and-best-practices/52465

## Q5. Sécurité réglementaire

- Règlement (UE) 2023/1230 : application le 20 janvier 2027 ; remplace la directive 2006/42/CE ; sous réserve de « certaines dispositions transitoires » non détaillées [LU, INRS, mis à jour 20/10/2023] https://www.inrs.fr/publications/juridique/focus-juridiques/nouveau-reglement-machines.html. Concordant [EXTRAIT] : Wolters Kluwer 17/03/2026 https://www.wolterskluwer.com/fr-be/expert-insights/machinery-regulation ; rectificatif du 04/07/2023 (travail-industrie.com) ; notification des sanctions par les États au plus tard le 20/10/2026 (Nemko) https://digital.nemko.com/regulations/eu-machinery-regulation.
- Contenu lu sur INRS : modification substantielle (physique ou numérique) = acte de fabricant ; machines à comportement « autoévolutif » : actions prévues à communiquer de façon compréhensible à l'opérateur ; protection contre la corruption accidentelle ou intentionnelle des composants de données/logiciel essentiels ; exigences de cohabitation homme-machine adaptées. La page n'aborde pas la mise en service pour usage propre.
- Exclusions Art. 2(2) [EXTRAIT, texte EUR-Lex non obtenu] : équipements de fêtes foraines/parcs d'attractions (point b) ; machines conçues pour la recherche, usage temporaire en laboratoire (point m). Guide danois (Danish Technological Institute) : exclusion recherche interprétée très strictement, prototypes uniques exploités par les chercheurs seuls https://www.dti.dk/_/media/97346%5FGuide%20to%20CE%20marking.pdf (guide national, non contraignant). Définition « putting into service » = premier usage dans l'Union pour sa destination [EXTRAIT]. Application à un prototype artistique exploité par son constructeur : non trouvé.
- Texte officiel à lire : https://eur-lex.europa.eu/eli/reg/2023/1230/en (chargement tenté : contenu vide ; un amendement 2026/1744 est mentionné dans les extraits, non vérifié).
- ISO 10218-1/-2:2025 : éditions courantes (industriel) ; ISO/TS 15066 intégrée ou non selon sources [EXTRAIT] https://www.tuv.com/landingpage/en/robotics/main/standard-update-alert/ ; https://standardbots.com/blog/collaborative-robot-safety-standards.
- ISO 13482:2014 : robots de soins/service (mobile servant, physical assistant, person carrier) ; exclut jouets, >20 km/h, médical, militaire ; seconde édition au stade FDIS selon une source [EXTRAIT] https://webstore.ansi.org/standards/iso/ISO134822014. Article EPFL : la norme manque d'exigences pour passants/spectateurs en espace public [EXTRAIT] https://infoscience.epfl.ch/record/282663.
- ISO 3691-4 : chariots industriels sans conducteur, appliquée aux AGV/AMR [EXTRAIT] TÜV (lien ci-dessus). Limites de vitesse : non trouvé.
- Arrêt d'urgence : catégories d'arrêt 0, 1, 2 (EN 60204-1) ; pour un arrêt d'urgence, ISO 13850 exige catégorie 0 ou 1 [EXTRAIT, blogs/fabricants] https://industrialmonitordirect.com/blogs/knowledgebase/en-13849-1-emergency-stop-pl-requirements-and-design-guide ; modules relais Schmersal jusqu'à PL e / cat. 4 (EN ISO 13849-1), SIL 3 https://products.schmersal.com/en_GB/safety-monitoring-modules-1000268497. Exigence d'indépendance vis-à-vis du logiciel : non établie par ces sources. Texte normatif non lu.
- Évaluation des risques EN ISO 12100 ; ISO 13849 / IEC 62061 pour la sécurité des commandes [EXTRAIT] https://www.intertek.com/blog/2026/06-24-a-quiet-reminder-of-functional-safety/.
- Pratique des petits fabricants (relais, coupure de puissance matérielle, homme-mort), assurance et limites de vitesse des robots de divertissement en espace public : non trouvé.

## Q6. Simulation

- Isaac Sim 6.2 [LU, doc éditeur NVIDIA, consultée 11/11/2026] https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html : minimum GeForce RTX 4080, 16 Go VRAM, CPU i7 7e gén. ou Ryzen 5 (4 cœurs), 32 Go RAM, SSD 50 Go ; « good » RTX 5080, 64 Go RAM ; « ideal » RTX PRO 6000 Blackwell 48 Go ; Ubuntu 22.04/24.04 ou Windows 11 ; « GPUs with less than 16GB VRAM may be insufficient » pour scènes complexes ; GPU sans RT Cores (A100, H100) non supportés. Versions antérieures (4.5) : minimum RTX 3070 8 Go [EXTRAIT]. 5.1 : sources forum contradictoires (8 Go vs 16 Go) [EXTRAIT] https://forums.developer.nvidia.com/t/is-8gb-vram-enough-for-basic-isaac-sim-5-1-usage/373600.
- Licences [EXTRAIT, tableaux comparatifs tiers, dépôts non lus] : MuJoCo Apache 2.0 (open source mai 2022) https://mujoco.org/ ; Webots Apache 2.0 ; Genesis Apache-2.0 ; Newton Apache-2.0 (Linux Foundation, bêta) ; Isaac Sim licence NVIDIA Omniverse ; Isaac Lab BSD-3. Sources : https://www.roboticscenter.ai/rl-environments/best-2026/ ; https://jslee02.github.io/awesome-robotics-libraries/COMPARISONS.html.
- Webots : orienté CPU, prototypage/enseignement [EXTRAIT, tiers]. MuJoCo MJX : parallélisme GPU. Exigences matérielles primaires de MuJoCo, Webots, Genesis, Newton, O3DE : non trouvé.
- Pertinence pour tester de la logique de comportement plutôt que de l'apprentissage : non trouvé (aucune source dédiée).
- Reachy 2 propose Gazebo, MuJoCo « coming soon » (voir Q3).

## Contradictions et incertitudes

1. ROS4HRI : la page paquets (LU) dit Jazzy distro principale ; l'index ROS montre hri_face_detect uniquement pour Humble (2.2.2, 07/2025) et « no version for distro jazzy » [EXTRAIT]. Un ancien doc disait Jazzy « planned but not yet available » [EXTRAIT]. Non tranché.
2. Règlement Machines : INRS (LU) écrit « entrera en vigueur le 20 janvier 2027 » ; d'autres sources distinguent entrée en vigueur (juillet 2023) et application (20/01/2027). INRS cite des dispositions transitoires non détaillées ; Wolters Kluwer dit pas de coexistence [EXTRAIT].
3. ISO/TS 15066 : intégrée à ISO 10218-2:2025 selon une source, document séparé selon une autre [EXTRAIT].
4. Isaac Sim 5.1 : 8 Go ou 16 Go VRAM selon le forum [EXTRAIT].
5. HORUS : latences et facteurs de gain contradictoires entre pages du projet [EXTRAIT].
6. Viam : offre industrielle à 120 000 $/an signalée puis retirée de la grille (suivi tiers) [EXTRAIT].
7. Newton : page CO/AI datée août 2026 contre annonce du 29/09/2025 [EXTRAIT].
8. dora-rs : date de la 1.0 (02/09/2026) déduite d'un nom de fichier, pas d'une date affichée [LU] ; article japonais concordant [EXTRAIT].
9. Les « extraits » ci-dessus passent par un résumé généré par l'outil de recherche ; certains détails (numéros d'étoiles, citations) peuvent différer des pages.

## Non trouvé / douteux

- Part d'entreprises utilisant ROS 2 en production (aucun chiffre).
- Billets « why we left ROS » de startups 2025-2026 ; mesure de migration hors ROS.
- Drake, Isaac ROS, MQTT/NATS maison : pas de page dédiée consultée.
- Basis : date, licence, maintenance, Python. LeRobot comme pile complète.
- Pile logicielle de Disney, Pollen (Reachy Mini), Furhat (ROS), Navel, compagnies de théâtre robotique.
- Pipeline Blender -> servos (hors Reachy 2 : dépôt `reachy2-blender` cité).
- ROS4HRI : adoption hors PAL, coût CPU Pi 5, paquet voix autre que asr_vosk.
- Règlement Machines : texte exact Art. 2 et 3, statut d'un prototype artistique exploité par son constructeur.
- Normes : texte ISO 13850, ISO 13482 (détail), ISO 3691-4 (vitesse), exigence d'indépendance logicielle de l'arrêt d'urgence.
- Pratique des petits fabricants, assurance, vitesse limitée des robots de divertissement.
- Exigences matérielles primaires de MuJoCo/Webots/Genesis/Newton/O3DE ; pertinence pour tests de comportement.
