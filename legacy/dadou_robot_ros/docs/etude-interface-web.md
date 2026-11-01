# Interface web de contrôle de Didier — plan du chantier

*Étude du 2026-07-11, remaniée le jour même après cadrage complet (grill). Statut :
**plan décidé**, rien d'implémenté. Les décisions ci-dessous sont arrêtées ; les
inconnues restantes sont listées en §9.*

## 1. Objectif et critère de réussite (décidés)

- **Scénario principal : télé-présence en spectacle.** Le robot est en représentation
  quelque part (déambulation **au milieu du public**), l'opérateur (David, seul
  utilisateur) le pilote depuis un autre lieu à travers Internet.
- **C'est réussi quand** : une séance complète est déroulée à distance — déplacement
  + animations + sons + visage — sans personne aux commandes sur place.
- **Échéance** : pas de date imposée, rythme soutenu.
- L'interface couvre aussi, de fait, l'usage LAN (backstage, préparation, sim).
- La télécommande physique n'est pas remplacée : elle reste l'outil de scène quand
  un opérateur est sur place, et elle garde **toujours** la priorité (câblé dans le
  twist_mux, voir §5).

## 2. Modèle de sécurité (décidé — c'est l'axe n°1 du chantier)

Le pire cas de conception : 50 kg télé-opérés à travers Internet au milieu d'un
public. Cinq décisions :

1. **Référent sécurité dédié, toujours présent** en salle pendant une télé-présence.
   Briefé, à portée du robot, ligne téléphonique ouverte avec l'opérateur pendant
   toute la représentation (il est aussi les « yeux extérieurs », voir §3).
2. **E-stop matériel : bouton coup-de-poing SANS FIL** dans les mains du référent,
   qui coupe l'**alimentation puissance des roues** (pas le Pi). Indépendant de tout
   logiciel et de tout réseau. → Chantier élec à spécifier (récepteur radio + relais
   de puissance sur l'alim moteurs), **bloquant avant la première télé-présence
   publique**, pas avant.
3. **Vitesse plafonnée dans le robot** en mode distant : clamp appliqué par le
   backend côté robot avant publication (un navigateur bugué ou compromis ne peut
   pas l'outrepasser). Valeur cible ~0,3-0,5 m/s — à fixer après calibration de
   `max_wheel_speed` (feuille de route existante, point 3).
4. **Perte de liaison → arrêt roues net + boucle d'attente scénique locale** :
   les deadman existants stoppent les roues, et le robot joue une séquence d'attente
   pré-enregistrée (respiration LED, petits mouvements de tête, son ambiant —
   **sans piste roues**) pour que le public ne voie pas une panne. À la reconnexion,
   reprise de main **explicite** par l'opérateur, jamais automatique.
5. **Vision = couche bonus, jamais LA sécurité.** Quand `/vision/person` tourne, le
   robot ralentit/stoppe de face si quelqu'un est trop proche ; sa panne n'empêche
   pas de jouer. La sécurité V1 = plafond vitesse + référent + deadman. (Une
   détection 360° embarquée reste la condition pour déambuler un jour SANS référent
   — hors périmètre.)

Règles transverses conservées de l'étude initiale : heartbeat applicatif web
(silence → retour supervision seule), session de contrôle exclusive, horodatage +
péremption des commandes de mouvement (une commande retardée par le réseau est
jetée, pas rejouée), journal de toute commande web dans `robot.log`, bandeau
domain 42/43 « ROBOT RÉEL / SIMULATION » permanent dans l'UI.

Le backend mesure en continu le RTT du heartbeat, l'affiche dans l'UI, et **gèle le
mouvement au-delà d'un seuil** (à fixer à la mesure, ordre de grandeur 250 ms).

## 3. Retour opérateur (décidé)

- **Caméra embarquée seule** (webcam du Pi 5 vision), diffusée en **MJPEG**
  à travers le VPN. **Réalisé le 2026-07-11** (variante sans `web_video_server`,
  plus simple : person_tracker publie `camera/image_raw/compressed` JPEG 5 i/s
  → web_bridge du Pi robot le sert tel quel sur `/video`, `camera_compressed`,
  cf. interfaces.md). Pas de plan large de salle : choix assumé —
  la conduite se fait au flux embarqué, le **référent au téléphone est les yeux
  extérieurs** (et le son de la salle passe par cette même ligne).
- Conséquence protocole : le référent n'est pas un simple porteur d'e-stop, il
  guide (« quelqu'un arrive à ta gauche ») — à écrire dans son briefing.
- Débit : MJPEG ≈ 1-2 Go/h en 640×480/15 fps — dimensionne le forfait 4G (§4) ;
  résolution/fps à ajuster à la mesure.
- WebRTC (latence moindre, débit moindre) = amélioration ultérieure possible, pas
  un prérequis.

## 4. Réseau (décidé)

- **Côté robot : routeur 4G/5G dédié dans le flight case** (~50-100 € + forfait
  ≥ 50 Go/mois). Le robot, le Pi vision et le téléphone du référent s'y accrochent :
  même réseau partout, répétable chez soi à l'identique, zéro dépendance au wifi du
  lieu. Point de vigilance par lieu : la couverture 4G (checklist d'installation, §7).
  **Le routeur existe déjà et il est DUAL-SIM** : c'est un **`TELTONIKA RUT955`**
  (modèle confirmé sur pièce le 2026-09-13 ; le relevé filmé du 03/09 ne donnait que
  `RUT9…`, dernier chiffre coupé — `hardware/robot-embarque.md` §1.5). Le RUT955 a
  deux emplacements SIM avec bascule automatique (failover). Deux SIM de
  **réseaux différents** (ex. Orange + SFR) sont donc la parade matérielle au
  risque « salle mal couverte » — à activer si une salle le justifie, pas d'office.
- **VPN : Headscale auto-hébergé** (protocole Tailscale, serveur de coordination à
  nous) sur un **serveur existant de David** — lequel : à préciser (prérequis : IP
  publique fixe, capacité à héberger le relais DERP intégré — indispensable pour
  percer le CGNAT 4G). Clients Tailscale standard sur Pi robot, Pi vision, PC
  opérateur.
- Le backend web ne sait rien de tout ça : il écoute sur un port, le VPN fait le
  reste. Aucun port ouvert nulle part, aucune exposition publique.

## 5. Architecture technique (décidée)

### Pont web ↔ ROS : `web_bridge_node` dédié
Node rclpy + serveur WebSocket (FastAPI), **package autonome façon `robot_drive`**
(aucun import robot.*), dans le conteneur robot. Rejeté : rosbridge_suite (expose
tout le graphe, pas de heartbeat/péremption protocolaires — voir §8 pour l'analyse
des standards conservée).

- API étroite : seuls les topics whitelistés existent. Écran spectacle : `wheels`
  (gamepad), `animation`, `face`, `audio`, `robot_lights`, e-stop, état/latence.
  Panneau technique séparé (préparation, jamais pendant le jeu) : servos directs
  (`neck`, yeux, bras), `relay`, `gaze` on/off, `system`, calibrations.
- Contenus : le backend republie les **StringTime existants** (contrat inchangé,
  payloads JSON identiques à la télécommande).
- **Roues : nouvelle entrée twist_mux `cmd_vel_web`, priorité 50** (remote 100 >
  web 50 > anim 10, verrou e_stop 255, timeouts 0.5 s identiques). La télécommande
  physique garde structurellement la main ; les deadman existants couvrent le
  nouveau flux sans modification. Chaîne : gamepad (Gamepad API navigateur) →
  WebSocket ~20 Hz → backend (clamp vitesse, péremption, heartbeat) → `cmd_vel_web`.
- **E-stop logiciel web = première source du verrou `e_stop`** (priorité 255,
  latché) + `animation: false` + arrêt servos. Toujours accessible, même en
  supervision seule. Une fois câblé, la télécommande physique pourra publier la
  même chose.
- Auth : appareils du VPN + token simple (opérateur unique). Session exclusive en
  écriture.

### Front
Une page statique servie par le backend, vanilla JS ou lib légère (pas de gros
framework, pas de build complexe — reprenable par n'importe qui/IA). Écran
spectacle pensé PC (gamepad + flux vidéo + gros e-stop), panneau technique
utilisable au téléphone en backstage.

```
PC opérateur (navigateur + gamepad USB) ── WSS/heartbeat ──┐
                                                     [VPN Headscale]
téléphone référent ── ligne téléphonique ── opérateur      │
bouton coup-de-poing sans fil ══ alim puissance roues      │ (hors logiciel)
                                                           ▼
                              web_bridge_node (Pi robot, whitelist/clamp/journal)
                                │ StringTime (animation, face, audio, lights…)
                                │ Twist → cmd_vel_web (twist_mux prio 50)
                                │ e_stop (verrou 255)
                                ▼
                              graphe ROS existant (mux, deadman — inchangés)
Pi vision ── person_tracker JPEG 5 i/s ──► web_bridge /video MJPEG ──► navigateur
```

## 6. Phasage (décidé — s'insère dans la feuille de route sans la bousculer)

Les priorités existantes 0 (chat_node V2 matériel) et 1 (test scénique au sol,
télécommande physique) **restent devant**. Le web démarre en parallèle :

- **W0 — fondations (démarre maintenant)** : `web_bridge_node` supervision +
  contenus + panneau technique, UI, token, heartbeat, session exclusive.
  Développé et validé 100 % en sim (domain 43). Puis LAN robot réel.
  **Implémentée le 2026-07-11 (sim)** — voir [`interfaces.md`](interfaces.md)
  §"API web (W0)" pour le protocole complet (endpoints, whitelist, messages
  WS, session/heartbeat).
- **W1 — e-stop** : source logicielle du verrou `e_stop` (validation sim puis
  protocole caméra roues hors sol). En parallèle : spec + achat + intégration du
  coup-de-poing sans fil (chantier élec).
- **W2 — accès distant (sans roues)** : Headscale sur le serveur, routeur 4G,
  MJPEG embarqué. Répétitions de déclenchement de contenus à distance.
- **W3 — roues web en LAN** : `cmd_vel_web` + twist_mux + gamepad. **Prérequis
  absolu : le test scénique au sol (priorité 1) est fait** — la première fois que
  cmd_vel roule au sol, c'est avec la télécommande physique, pas via le web.
  Validation : protocole caméra hors sol (façon `validate-cmdvel-protocol.sh`,
  étendu : coupure WebSocket en plein mouvement, commande périmée jetée, clamp
  vitesse), puis roues au sol en local.
  - **W3 (partie sim) entamée le 2026-07-11** : entrée twist_mux `cmd_vel_web`
    (prio 50, entre remote 100 et anim 10 ; contrat gelé testé par
    `test_twist_mux_contract.py`), canal protocole `drive` (clamp serveur
    `drive_to_twist`, zéro auto `DriveFlow` 0.3 s, `drive_enabled` défaut false),
    pad web + manette + retour vidéo caméra (gz → `camera/image_raw` → MJPEG
    `/video`), le tout validé en sim (SIM-ONLY, `WEB_DRIVE=false` par défaut).
    Le passage robot réel reste conditionné au test scénique au sol (priorité 1)
    PUIS au protocole caméra roues hors sol.
- **W4 — mouvement à distance** : mêmes commandes à travers 4G + Headscale, robot
  SANS public (atelier/autre pièce, puis autre lieu). Mesure du RTT réel, fixation
  du seuil de gel, boucle d'attente scénique branchée et testée en coupant le lien
  volontairement.
- **W5 — qualification télé-présence publique** : **3 séances complètes à distance
  sans incident** (séquence de spectacle entière, conditions réelles, référent en
  place ; tout incident sécurité ou coupure non rattrapée ⇒ correction + compteur
  remis à zéro). Coup-de-poing opérationnel + checklist lieu (§7). Alors seulement :
  première date devant public.

## 7. Vérification (méthode)

- Chaque étage suit l'échelle maison : **sim (domain 43) → protocole caméra roues
  hors sol → sol local → distance sans public → 3 séances qualifiantes**.
- Protocoles rejouables scriptés dans `conf/scripts/` (comme
  `validate-cmdvel-protocol.sh`), captures ffmpeg à l'appui.
- **Checklist d'installation par lieu** (à écrire en W4) : couverture 4G mesurée,
  RTT affiché sous le seuil, test e-stop coup-de-poing, test perte de liaison
  volontaire, briefing référent (rôle yeux + téléphone + bouton).

## 8. Standards ROS — analyse conservée (état 2026)

| Brique | Rôle | Verdict pour Didier |
|---|---|---|
| rosbridge_suite + roslib.js | Pont JSON/WebSocket standard, maintenu en Jazzy (2.3.0) | Rejeté comme pont de prod : expose tout le graphe, pas d'auth par topic ni de péremption. Utilisable ponctuellement en debug LAN, jamais dans le bringup. |
| Vizanti | UI web toute faite sur rosbridge, compatible Jazzy | Rejeté (générique, mêmes limites que rosbridge, ignore StringTime et nos règles). Source d'inspiration UI. |
| Foxglove | Visualisation/debug WebSocket | Hors périmètre (supervision de dev, pas une télécommande). |
| Zenoh (`rmw_zenoh` / `zenoh-bridge-ros2dds`) | Transport ROS 2 pensé pour NAT/Internet, officiel en Jazzy | Reporté : bascule d'infrastructure sur toute la flotte, et les deux voies Zenoh sont non interopérables entre elles. À réévaluer si un jour la télécommande physique doit elle-même franchir les réseaux. |
| Fast DDS Discovery Server | Découverte sans multicast | Sans objet ici (ne traite ni NAT ni chiffrement). |
| VPN WireGuard (Headscale/Tailscale) | Réseau privé par-dessus Internet | **Retenu** (Headscale auto-hébergé, §4). |

Rappel réseau existant : RMW par défaut (Fast DDS multicast), Docker
`network_mode: host`, domain 42 robot / 43 sim — rien de tout ça ne change ; seul
le backend et le VPN s'ajoutent.

## 9. Inconnues et points ouverts (assumés, à lever au fil des phases)

1. **Quel serveur pour Headscale** — à préciser (IP publique fixe, port DERP
   ouvrable, Docker ou systemd dispo).
2. **Chantier élec coup-de-poing** — produit radio à choisir, schéma de coupure
   puissance roues à concevoir (lien avec les cartes PCB en cours), test de portée
   en salle.
3. **Plafond de vitesse distant chiffré** — après calibration `max_wheel_speed`.
4. **Seuil de gel latence** — après mesure RTT réelle 4G + Headscale + DERP (W4).
5. **Boucle d'attente scénique** — contenu artistique à créer (séquence sans piste
   roues) ; techniquement : déclenchée par le backend sur perte de heartbeat.
6. **Charge machines** — backend sur le Pi 4 (à côté du tick 20 Hz) et MJPEG sur le
   Pi 5 : à mesurer, logs de boucle chaude déjà en place.
7. **Forfait data** — dimensionner après mesure du débit MJPEG retenu.
   **Défriché le 2026-09-05** (sources lues ce jour, prix à revérifier avant de
   souscrire) : *(a)* **Free ne propose AUCUNE option multi-SIM** — position
   assumée de l'opérateur, pas une limite du forfait de David : impossible d'y
   rattacher une SIM data pour le routeur. *(b)* **Sosh la propose** (5 €/mois
   + 10 € de mise en service, forfait ≥ 20 Go requis), mais l'enveloppe est
   **PARTAGÉE avec le forfait téléphone** : 2 h de télé-présence = 2-4 Go pris
   sur la ligne perso, et le robot devient dépendant de l'abonnement personnel.
   **Piste retenue : ligne data DÉDIÉE au robot**, sans engagement (~7-12 €/mois
   pour 100-200 Go chez les MVNO) — même budget, sans le couplage.
   *(c)* **Seul le flux MJPEG dimensionne le forfait.** Les éventuelles photos de
   contexte envoyées à un LLM pèsent des dizaines de Ko : négligeables en data
   (leur coût est en tokens, borné côté conversation — voir
   `etude-declenchement-conversation.md` §8.6).
   *(d)* **Cible chiffrée : 20 à 50 Go/mois.** David a précisé le 2026-09-05 que
   le télé-pilotage l'intéresse mais restera **ponctuel** — le §4 parlait de
   « ≥ 50 Go » par prudence, c'est un plafond, pas un besoin. Un « mode économe »
   (320×240, 5 i/s) reste à mesurer comme repli en salle mal couverte.
   *(e)* **DÉCIDÉ ET COMMANDÉ le 2026-09-05** (commande Sosh `X040972152`) :
   **Sosh 200 Go 5G à 15,99 € + option Multi-SIM « extra » à 5 €**, soit
   ~20,99 €/mois, **avec portabilité du numéro Free** (RIO fourni) — donc la
   ligne Free disparaît. Écart assumé avec *(b)* : l'enveloppe partagée cessait
   d'être un piège à 200 Go, et David voulait aussi une SIM data autonome au
   bureau. **Conséquence pour le robot : la 2ᵉ SIM part au travail, le robot
   n'en a donc PAS encore.** Deux issues, à trancher quand le compte MySosh sera
   actif : soit une 2ᵉ option Multi-SIM se cumule (l'option « Internet + 1Go »
   par-dessus l'« extra » — cumul NON vérifié, les sources tierces se
   contredisent et la page Sosh est derrière l'authentification), soit il faut
   une ligne data séparée pour le flight case. À noter : tout sur un seul
   opérateur fait perdre l'assurance « deux réseaux » du routeur dual-SIM (§4).
8. **Arbitrage `neck`** (animations ↔ gaze ↔ panneau technique web) — problème
   existant, aggravé par chaque nouvelle source ; à traiter au plus tard en W3.
9. **Risque résiduel assumé** : en V1, aucune détection d'obstacles embarquée — la
   déambulation publique repose sur plafond vitesse + référent + deadman. La
   détection 360° est la condition d'une déambulation sans référent, un jour.
10. **Démarrer/arrêter la SIM depuis la console** (demande du 2026-07-11) : le
   pont tourne DANS le conteneur sim, il ne peut pas se relancer lui-même — il
   faudrait un mini-agent sur l'hôte (accès docker) piloté par la console, ou
   exposer le socket Docker (à éviter). À concevoir plus tard ; en attendant,
   la sim se pilote au `docker compose`, **headless par défaut** (vérifié le
   2026-07-11 : la caméra gz rend hors écran, la console web EST la fenêtre —
   Gazebo GUI seulement quand on veut voir la scène en 3D).
