# Banc du lidar, 23/11/2026 — premier allumage (spec A0 §10.1, gestes 1 et 2)

Lidar SLAMTEC RPLIDAR C1 livré le 23/11, branché par David sur le Pi 4 de rechange (hôte `r`,
192.168.1.131, série `10000000bec1ed98`), **hors robot**, sur l'établi. Aucun moteur. Fait par
l'agent seul (Opus 5.5), sans geste de David ; les gestes 3 à 8 (cartons, matières, plein jour,
débranchement) restent à faire avec lui (A0-7).

## Geste 1 — brancher

| Mesure | Valeur |
|---|---|
| Adaptateur | Silicon Labs CP2102N, `10c4:ea60`, série `6a08780ca81df111a44fc9e40f0f12f8` → règle `machines/robot/udev/99-didier-lidar.rules` |
| Port | `/dev/ttyUSB0`, puis le lien `/dev/didier-lidar` posé par Ansible (vérifié après déploiement) |
| Lidar | S/N `D29EFC8DC4E09DCAB7939AF7513F5071`, firmware 1.02, révision matérielle 18, santé OK |
| Mode | `Standard`, 5 kHz d'échantillonnage, 10 Hz, portée annoncée par le lidar 16 m |
| `vcgencmd get_throttled` | `0x0` avant, pendant et après le démarrage du moteur (alim du Pi par sa propre source) |
| Température du Pi | 41 °C à la fin |

## Geste 2 — laisser tourner 60 s

Pilote `sllidar_ros2` au commit épinglé `3430009`, compilé sous Jazzy ARM dans un conteneur
jetable de l'image du robot : **48 s, aucune erreur** (la spec le donnait « à mesurer »). Domaine
ROS 44 (isolé du robot), abonné Python qui compte tout pendant 60 s.

| Mesure | Valeur | Commentaire |
|---|---|---|
| Fréquence | 9,98 Hz (600 balayages) | conforme |
| Écart entre deux balayages | p99 105 ms, max 202 ms | un tour manqué sur 600 ; sous la borne `capteur_perdu` de 0,30 s |
| Rayons par message | 720 (fixe) | pas de 0,501°, de −π à +π : `angle_compensate` ; **la sim en publie 500** (lot à part, voir plus bas) |
| Points finis | 87 % | pièce encombrée, 0,07 à 8,32 m |
| `range_min` / `range_max` | 0,05 / 16,0 m | 0,05 en dur dans le pilote |
| `frame_id` | `laser` (lancement d'origine) | le robot lance avec `laser_frame` (lien de l'URDF) |
| CPU du pilote | **6,4 % d'un cœur** (30 s, `/proc/<pid>/stat`) | |
| CPU de `corps_sur` | 7,2 % d'un cœur **sans scan** (le robot tournait en domaine 42, sans lidar) | but de la spec « < 15 % à eux deux » : **juste**, à remesurer branchés ensemble |

## Dans le vrai bringup, après A0-6 (même soir)

Image reconstruite sur le Pi (pilote compilé en 1 min 7 s dans la couche dédiée), déployée par
Ansible, poussée sur le Hub (`sha256:86beb03a…`). `ecart-pi.sh robot` **VERT**.

| Mesure | Valeur |
|---|---|
| `lidar_node` | `/didier/lidar_node` démarré par le launch, santé OK, `/dev/didier-lidar` → `ttyUSB0` |
| `corps_sur` | `capteur_absent` → `sante_en_cours` → **ARME** en 2,2 s, sans geste ; zone ARRET (objet à 5 cm sur l'établi) |
| Preuve à blanc (spec §9) | ≈ 1 200 `Twist` non nuls publiés sur `cmd_vel_anim` en 6 s : **1 202 reçus sur `cmd_vel_anim_sur`, 0 non nul** |
| Image SANS pilote (avant reconstruction) | bringup intact, « sllidar_ros2 absent de l'image » au journal, corps sûr en `capteur_absent` |
| CPU, 30 s chacun | pilote **4,5 %**, `corps_sur` **17,6 %** d'un cœur (7,2 % sans scan) ; charge du Pi 1,3 sur 4 cœurs |
| `ros2 topic hz /didier/scan` (CLI) | 10,4 Hz, mais **écart max 425 ms** chez cet abonné Python ; le corps sûr, lui, n'a eu aucun verrou `capteur_perdu` |
| Scripts d'atelier | `relancer-lidar.sh` : pilote tué par PID → corps sûr **VERROU `capteur_perdu`** → pilote relancé seul (respawn) ; `rearmer-corps-sur.sh` : « réarmement accepté » → **ARME** |
| Alim, température | `0x0`, 45,7 °C |

**Deux points ouverts**, consignés pour A0-7 et A0-8 :
1. **Budget CPU dépassé** : 22 % d'un cœur à eux deux contre « moins de 15 % » (spec §10.1). Le
   nœud Python traite 720 rayons à 10 Hz (la sim n'en envoie que 500). Pas une panne, le Pi est
   large, mais à optimiser ou à re-budgéter avant le terrain.
2. **Gels d'abonnés sur le Pi** : 425 ms vus par la CLI, au-delà de la borne `capteur_perdu` de
   0,30 s. Hypothèse (non prouvée ici) : le piège Fast DDS en mémoire partagée vu en sim le 21/11 (`docs/operations.md`).
   Le robot n'est pas en UDP seul. À mesurer sur une longue durée en A0-7 : un verrou spontané
   en marche arrêterait Didier (sûr, mais injouable).

### Mesures du soir sur ces deux points (23:20-23:35)

**Gels : aucun en 10 min.** Abonné Python DANS le conteneur du robot (`/didier/scan`, profondeur
10), 600 s : 6 006 balayages ; écart à la RÉCEPTION p50 100 ms, p99 104, **max 109 ms**, aucun
au-dessus de 200 ms ; écart des HORODATAGES du pilote max 122 ms ; zéro gel de l'abonné seul.
Et dans le journal du robot, de 20:52 à 23:35, **un seul `capteur_perdu`** : celui provoqué par
`relancer-lidar.sh`. Les 425 ms du `ros2 topic hz` étaient donc propres à la CLI (son démarrage
ou son abonné), pas au système. Point 2 **largement levé au repos** ; reste à le revoir en
charge (vision, audio, roues alimentées) en A0-7/A0-9 — c'est là que la sim gelait.

**CPU : la logique n'est pas le problème.** Micro-mesure sur le Pi, vraie configuration du
robot, 720 rayons (87 % finis) : `lire_balayage` **3,65 ms**, `CorpsSur.balayage` 3,55 ms,
`tic` 0,005 ms (sur le PC : 0,48 ms). À 10 Hz : ≈ 3,6 % d'un cœur. Le reste des 17,6 % (dont
7,2 % sans aucun scan) est la plomberie rclpy : exécuteur, minuterie à 20 Hz, désérialisation du
`LaserScan`, publication de l'état. Pistes, sans rien changer ce soir : l'`EventsExecutor` de
rclpy, ou ne publier l'état qu'à son changement. Le but « < 15 % » de la spec date d'avant toute
mesure : **à re-trancher en A0-8** (relecture Fable) plutôt qu'à forcer — le Pi est à 1,3 de
charge sur 4 cœurs.

## Ce qui en découle

- A0-6 fait le même soir : pilote dans l'image, règle udev, `lidar_node` dans le bringup (voir
  `docs/chantiers.md`).
- **Sim à aligner** : le `gpu_lidar` simulé publie 500 rayons (0,72°), le vrai 720 (0,5°). La
  logique du corps sûr ne dépend que de `angle_increment`, mais le coût CPU et le RTF, si. Lot à
  part, avec remesure du RTF et épreuve CS (500 y est gravé).
- Reste du banc (A0-7, David, 20 min) : orientation (carton à 1 m devant puis à gauche), portée
  minimale réelle, délai balayage → ARRET, jean noir / vitre / miroir, débranchement de l'USB,
  plein jour dehors.
