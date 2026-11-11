# Veille brute : distros ROS 2, Gazebo, rmw_zenoh, multi-machines, Pi (collecte du 2026-11-11)

Date de consultation de toutes les sources : 2026-11-11.
Légende : **[LU]** = page chargée et lue (extraction par le modèle de lecture de l'outil WebFetch, pas par moi). **[EXTRAIT]** = uniquement un résumé de moteur de recherche, page non chargée.

## Couvert / non couvert

- Budget : 11 pages chargées sur 12. Les pages docs.ros.org (release notes Lyrical/Kilted, REP-2000, Working-with-Zenoh, Installing-on-Raspberry-Pi) renvoient toutes une page « Access Denied » Anubis (6 chargements perdus). Tout ce qui vient de docs.ros.org est donc [EXTRAIT].
- Non couvert : dates EOL de Humble, Jazzy et Kilted lues sur page officielle ; nouveautés Kilted ; EOL Harmonic et Jetty ; zenoh-bridge-ros2dds ; Tailscale/Husarnet ; Cyclone peers statiques (doc officielle) ; retours d'expérience négatifs concrets sur rmw_zenoh (issues GitHub) ; confirmation arm64 de `ros:lyrical-ros-base` ; Ubuntu 26.04 sur Pi 4/5.

## Q1. Distributions ROS 2

- Lyrical Luth : sortie générale le 22 mai 2026, 12e distribution ROS 2, LTS, supportée jusqu'à mai 2031. Ubuntu 26.04 (Resolute) amd64 et arm64 = Tier 1 ; Ubuntu Noble 24.04 = Tier 3. [LU] https://discourse.openrobotics.org/t/ros-2-lyrical-luth-released/55021 (post du 22/05/2026)
- Lyrical, RMW par défaut : la page d'annonce ne le nomme pas [LU]. Un post de Jaime Martin Losa (eProsima) du 25/05/2026 dit « Fast DDS will continue serving as the default middleware implementation for ROS 2 » [LU] https://discourse.openrobotics.org/t/ros-2-lyrical-luth-and-11-years-of-fast-dds-as-ros-2-default-middleware/55062.md (source d'un fournisseur de Fast DDS, pas une page de doc officielle).
- Nouveautés Lyrical citées dans l'annonce [LU, même URL que ci-dessus] : Callback Group Events Executor (« uses 10% to 15% less CPU » que Single/Multithreaded) ; `AsyncNode` dans rclpy (asyncio avec les callbacks) ; `rosidl::Buffer` (zéro-copie GPU, seul rmw_fastrtps_cpp le supporte, Zenoh « à venir ») ; améliorations URDF ; améliorations rosbag2 (non détaillées) ; commandes `ros2 param` multi-paramètres ; shell fish. Gazebo Jetty : `sudo apt install ros-lyrical-ros-gz`.
- Kilted Gazebo = Ionic et EOL Kilted = décembre 2026 : voir Q2.
- EOL Jazzy = mai 2029 : [EXTRAIT, billet tiers openelab.io, non chargé] https://openelab.io/blogs/learn/ros-2-lyrical-vs-jazzy (date inconnue).
- EOL Humble : non trouvé (la page https://docs.ros.org/en/humble/Releases/End-of-Life.html est apparue dans les résultats, non chargée).
- Calendrier Lyrical : https://docs.ros.org/en/lyrical/Releases/lyrical/release-timeline.html [EXTRAIT : « May, 2031 - End-of-life », GA vendredi 22 mai 2026].
- Images Docker : [EXTRAIT] un post Discourse (https://discourse.openrobotics.org/t/lyrical-luth-test-and-tutorial-party-instructions/54427/14) annonce des tags `lyrical`, `lyrical-ros-base`, `lyrical-ros-base-resolute` sur l'image officielle `ros`. Arm64 non confirmé directement ; une image tierce `rostooling/setup-ros-docker` montre un digest linux/arm64 (non officielle). Un billet tiers montre `ros:lyrical-ros-base-resolute` tournant sur un hôte Ubuntu 24.04 (openelab, lien ci-dessus).

## Q2. Gazebo

- Tableau d'appariement [LU, la table était mal extraite, lignes associées par ordre] https://gazebosim.org/docs/all/ros_installation (date de page inconnue) :
  - Humble : Fortress recommandé ; Harmonic « non recommandé ».
  - Jazzy : Harmonic recommandé.
  - Kilted : Ionic recommandé ; Harmonic « non recommandé ».
  - Lyrical : Jetty recommandé ; Harmonic et Ionic « non recommandé ».
  - Légende de la page : ✅ recommandé, ⚡ possible mais prudence, ❌ incompatible. Fortress, Harmonic et Jetty sont marqués LTS ; Ionic non.
- Ionic : sorti en septembre 2024, EOL en décembre 2026 avec Kilted ; Jetty est apparié à Lyrical ; aucune date EOL pour Jetty ni mention de Harmonic. [LU] https://discourse.openrobotics.org/t/gazebo-ionic-reaching-end-of-life-in-december-2026/57981 (post du 09/09/2026).
- EOL Harmonic : non trouvé. EOL Jetty : non trouvé.

## Q3. rmw_zenoh

- Statut : [EXTRAIT] un post Discourse (https://discourse.openrobotics.org/t/wire-breaking-change-in-rmw-zenoh-for-ros-2-jazzy/44367, date non lue) : Tier 1 à partir de Kilted ; aucune déclaration de stabilité pour Jazzy, où des changements de protocole cassants ont été rétroportés ; compatibilité de protocole visée à partir de Kilted.
- Lyrical : `sudo apt install ros-lyrical-rmw-zenoh-cpp` [EXTRAIT, docs.ros.org Working-with-Zenoh/lyrical non chargée]. Tier de rmw_zenoh sous Lyrical : non trouvé.
- README GitHub [LU] https://github.com/ros2/rmw_zenoh (date de page non indiquée) :
  - Installation : `sudo apt update && sudo apt install ros-<DISTRO>-rmw-zenoh-cpp`.
  - « rmw_zenoh is incompatible between Humble and newer distributions » ; les type hashes depuis Iron font que les messages inter-distros sont silencieusement perdus.
  - Routeur : « Without the Zenoh router, nodes will not be able to discover each other since multicast discovery is disabled by default ». Lancement : `ros2 run rmw_zenoh_cpp rmw_zenohd`. Le README ne dit pas explicitement « un par machine » dans l'extraction ; les extraits de moteur parlent d'un routeur par hôte, ponts entre routeurs pour étendre la découverte.
  - Multi-machines : routeurs reliés en ajoutant l'endpoint de l'autre hôte sous `connect` dans la config du routeur (`ZENOH_ROUTER_CONFIG_URI`) ; un nœud distant se connecte à un routeur via `ZENOH_CONFIG_OVERRIDE='mode="client";connect/endpoints=["tcp/192.168.1.1:7447"]'` ou `ZENOH_SESSION_CONFIG_URI`. Multicast activable par `scouting/multicast/enabled=true`.
  - Limites : sous Zenoh SHM et forte charge CPU, des appels de service ou des publications historiques TRANSIENT_LOCAL peuvent être perdus silencieusement (issue #978) ; le routeur plante sur systèmes IPv4 seulement ; plantage possible à la sortie si le Context n'est pas arrêté explicitement ; non interopérable avec zenoh-plugin-ros2dds / zenoh-bridge-ros2dds. Sécurité : contrôle d'accès, authentification, chiffrement via le paquet `zenoh_security_tools`. QoS générique, rosbag2, Wi-Fi/VPN/NAT : non mentionnés dans la page lue.
- Hostname dans un endpoint de routeur non accepté pour la connexion inter-réseaux : [EXTRAIT] https://discourse.ros.org/t/rmw-zenoh-router-configuration/43885 (non chargé, date inconnue).
- Wi-Fi mesuré [LU] https://learn.arm.com/learning-paths/cross-platform/tuning-zenoh-ros2-lp3/4-measure-real-wifi/ (pas de date sur la page ; un extrait de moteur mentionne un billet Arm distinct « Oct 2026 »). Un Pi client Zenoh en Wi-Fi 2,4 GHz, conteneur ROS 2 Jazzy, routeur sur un serveur Arm. Le texte ne cite pas « rmw_zenoh ». Mesures : base /scan 7,90 Hz, image 4,2 Hz, nuage de points rien reçu, ~62 Mbps de trafic dont près de la moitié inutile ; avec compression image 11,87 Hz ; compression + contrôle d'accès ~29 Mbps utiles. Pas de CPU, latence ni modèle de Pi.
- Pi + CPU + VPN spécifique à rmw_zenoh : non trouvé. Les résultats CPU Pi trouvés concernaient ZeroTier, hors sujet.
- Fil Discourse « Oh rmw_zenoh, come quickly! » [EXTRAIT] https://discourse.openrobotics.org/t/oh-rmw-zenoh-come-quickly/36769 : utilisateurs qui échouent à configurer fastrtps_cpp à travers deux réseaux reliés par VPN (donc un problème DDS, pas Zenoh).
- Benchmarks : aucun benchmark 2025-2026 comparant rmw_zenoh, Fast DDS et Cyclone trouvé [EXTRAIT]. Étude 2023 citée par arXiv 2025 (https://arxiv.org/html/2505.02734v1, non chargée) : Cyclone meilleur sur Ethernet, Zenoh meilleur sur Wi-Fi et 4G (Zenoh en général, pas rmw_zenoh). Rapports eProsima 2021-22 (vendeur) : Fast DDS 2,56 ms vs Cyclone 6,11 ms inter-processus (https://osrf.github.io/TSC-RMW-Reports/humble/eProsima-response.html, [EXTRAIT]).

## Q4. Alternatives sans changer de RMW

- Fast DDS Discovery Server : découverte sans multicast via un serveur central, nœuds pointés par variable d'environnement [EXTRAIT, billet Medium/NetRobiCS]. « Easy Mode » (un discovery server par machine) lié à Fast DDS v3, non rétroporté à Jazzy [EXTRAIT, fil Discourse « Announcing ROS 2 Easy Mode » https://discourse.openrobotics.org/t/announcing-ros-2-easy-mode/41974].
- Cyclone DDS : pairs statiques par XML manuel, pas de discovery server [EXTRAIT, billet Medium 2023 https://medium.com/@arshad.mehmood/setting-up-node-discovery-across-multiple-systems-in-ros2-infrastructure-a1a5c25f052f, à recouper avec la doc Cyclone actuelle].
- Papier NetRobiCS 2026 (https://ceur-ws.org/Vol-4243/paper9.pdf, [EXTRAIT]) : la découverte P2P DDS par multicast peut saturer le Wi-Fi (multicast au débit de base sans ACK MAC).
- Husarnet : `husarnet-dds` existe (https://husarnet.com/docs/ros2/husarnet-dds/ [EXTRAIT]). Tailscale : non trouvé. zenoh-bridge-ros2dds : non couvert. Recommandation officielle 2026 pour le multi-machines Wi-Fi : non trouvée (pages docs.ros.org bloquées).

## Q5. ROS 2 sur Raspberry Pi

- Guide docs.ros.org Lyrical « ROS 2 on Raspberry Pi » : page existe (https://docs.ros.org/en/lyrical/How-To-Guides/Installing-on-Raspberry-Pi.html), contenu non lu (Anubis).
- Billet tiers openelab.io (https://openelab.io/blogs/learn/ros-2-lyrical-vs-jazzy, [EXTRAIT], date inconnue) : choisir OS et ROS en bloc, Ubuntu 24.04 + Jazzy ou 26.04 + Lyrical ; Lyrical « raisonnable » pour un nouveau Pi 5 après vérification caméra/GPIO/série/LiDAR ; Jazzy conseillé si l'image fournisseur est Jazzy. Docker : images officielles pour les deux, conteneur 26.04 sur hôte 24.04 possible.
- Fil Reddit mai 2026 [EXTRAIT] : dépendances manquantes dans les paquets Lyrical sur 26.04 au moment du post.
- Ubuntu 26.04 sur Pi 4/5 et ROS en Docker sur Raspberry Pi OS (pratique courante) : non trouvé.

## Non trouvé / douteux

- EOL Humble, Jazzy (officiel), Kilted (hors Gazebo Ionic « avec Kilted » en décembre 2026) : non lus sur page officielle.
- Nouveautés Kilted : non trouvé.
- EOL Harmonic, Jetty : non trouvé.
- Tier de rmw_zenoh sous Lyrical : non trouvé. « Tier 1 depuis Kilted » vient d'un extrait de moteur.
- Contradiction possible : la page gazebosim classe Harmonic « non recommandé » sous Kilted et Lyrical, et marque Harmonic LTS ; aucune date EOL donnée pour confirmer.
- Le tableau Gazebo a été reconstitué par ordre de colonnes par l'outil d'extraction (lecture imparfaite).
- Le billet sur Fast DDS par défaut émane d'un acteur commercial ; docs.ros.org n'a pas pu confirmer.
- Date du billet Arm « Oct 2026 » non vérifiée.

## Complément lu le 2026-11-11 par l'orchestrateur (sources GitHub de la doc officielle)

docs.ros.org et ros.org refusant les robots (Anubis), les deux pages ont été lues dans leurs
dépôts sources, via un résumeur.

- `ros2_documentation`, `source/Releases.rst`, branche rolling —
  https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Releases.rst :
  Humble 23 mai 2022 → mai 2027 ; Iron 23 mai 2023 → 4 déc. 2024 ; Jazzy 23 mai 2024 →
  mai 2029 ; Kilted 23 mai 2025 → décembre 2026 ; Lyrical Luth 22 mai 2026 → mai 2031 ;
  distribution future Makoa Mata-mata, mai 2027 → décembre 2028.
- REP-2000 — https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-2000.rst
  (100 000 premiers caractères sur 100 962) : Jazzy « May 2024 - May 2029 », Ubuntu Noble
  amd64/arm64 Tier 1, RMW Tier 1 = rmw_fastrtps_cpp (défaut), rmw_cyclonedds_cpp,
  rmw_connextdds ; **rmw_zenoh_cpp absent du tableau Jazzy**. Kilted « May 2025 - November
  2026 » (écart d'un mois avec Releases.rst), rmw_zenoh_cpp **Tier 1**, défaut toujours
  rmw_fastrtps_cpp. Lyrical n'apparaît pas dans la partie lue.
