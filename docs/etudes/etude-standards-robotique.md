# Étude — Didier face aux standards de la robotique (petites structures), novembre 2026

*Écrite le 2026-11-11 à la demande de David. Trois questions : le travail en cours reprend-il
les standards qu'applique une petite entreprise de robotique ? ROS est-il toujours le bon
choix ? Y a-t-il des méthodes ou des logiciels meilleurs à intégrer ?*

**⚠️ RIEN N'EST DÉCIDÉ ICI.** Six arbitrages sont proposés au §7 ; tout le reste confirme des
décisions déjà prises (rappelées, pas rouvertes).

**Sources.** Le dépôt, relevé le 11/11 (commit `46ecb38`). Trois collectes web du 11/11,
conservées brutes : `docs/veille/brut/2026-11-11-standards-distros-zenoh.md`,
`…-standards-briques-ros.md`, `…-standards-alternatives-pratiques.md`. Les collectes sont
**partielles** (docs.ros.org et ros.org refusent les robots ; plafond de pages atteint) : ce
qui n'a pas été lu sur une page est marqué *(extrait)* ou *(de mémoire, à relire)*. Aucun prix
n'est cité de mémoire.

---

## 1. Verdict en dix lignes

1. **Oui, le socle est celui d'une petite structure sérieuse** : ROS 2 Jazzy (LTS), Gazebo
   Harmonic, URDF, chaîne `cmd_vel` avec `twist_mux` et homme-mort, `py_trees`, Docker par
   machine, Ansible, 1 619 tests, simulation rejouée chaque nuit. Sur les tests et la sim,
   c'est **au-dessus** de l'usage courant.
2. **L'écart qui compte n'est pas logiciel** : il n'existe aujourd'hui **aucun arrêt
   d'urgence matériel** (le verrou `e_stop` n'a pas de publieur, la carte Sécurité n'est pas
   fabriquée). C'est connu, c'est la priorité n° 1 du projet, et c'est exactement ce que le
   métier exige. Rien de ce qui suit ne passe avant.
3. **ROS reste le bon choix**, et il le devient davantage : Didier s'en sert surtout comme
   d'un bus de messages, alors que sa vraie valeur (lidar, évitement, odométrie,
   enregistrement) est précisément ce qui arrive dans les lots d'autonomie.
4. **Rester sur Jazzy** (soutenue jusqu'en mai 2029). Lyrical, la LTS de mai 2026, attendra
   la fin de la migration.
5. **Je retire ma recommandation « passer à Zenoh »** faite plus tôt le même jour : l'étude
   web de juillet l'avait reportée, et les faits de novembre lui donnent raison (§5.1).
6. **`ros2_control` : non**, ni pour les servos (déjà écarté) ni pour les roues. Ce que
   l'écosystème exige, c'est le **contrat** `cmd_vel` → `odom` + TF, pas cette brique (§5.2).
7. **Nav2 : par morceaux.** Le moniteur de collision mérite un essai pour le « corps sûr » ;
   la navigation sur carte n'a pas d'emploi dans une déambulation de rue (§5.3).
8. **Trois manques d'outillage, peu coûteux** : la CI ne tourne plus depuis le mono-dépôt,
   aucun enregistrement `rosbag`, pas de topic de santé standard (§4, lignes G et I).
9. **Deux habitudes ROS que le projet a réinventées** : les *actions* (ordres longs avec
   retour et annulation) et les messages typés. La première vaut d'être adoptée pour les
   déplacements autonomes ; la seconde est un écart assumé à borner par une règle (§6).
10. **Le vrai risque est la charge d'une personne seule**, pas l'outil. La réponse est
    d'intégrer **moins** de briques, choisies, et non de changer de cadre.

---

## 2. Ce qu'une petite structure fait en 2026 — la référence utilisée

Il n'existe pas de norme écrite ; la référence ci-dessous est ce que font les robots ouverts
de même taille et ce que publient leurs mainteneurs.

| Couche | Pratique courante | Source |
|---|---|---|
| Distribution | une LTS, souvent en retard d'une : Humble pèse encore 48,5 % des téléchargements, Jazzy 24,5 % (octobre 2025) | rapport ROS Metrics 2025, lu |
| Roues d'un petit différentiel | pas de règle unique : `linorobot2` passe par micro-ROS sur microcontrôleur, et sa page matériel ne mentionne pas `ros2_control` ; Reachy 2 utilise `ros2_control` | pages lues |
| Sécurité | coupure de puissance **indépendante du logiciel**, arrêt de catégorie 0 ou 1 | ISO 13850 *(extrait, sources de fabricants)* |
| Obstacles | lidar 2D + moniteur de collision placé sur le chemin de `cmd_vel` | README Nav2, lu |
| Comportement | arbres de comportement (`py_trees_ros`, soutenu de Humble à Lyrical ; ou BehaviorTree.CPP) | page GitHub, lue |
| Enregistrement | `rosbag2` au format MCAP (défaut en Jazzy), mode « instantané » à tampon circulaire | README rosbag2, lu |
| Déploiement | Docker + Ansible ou équivalent ; **aucun outil de mise à jour à distance ne fait consensus** | fil Discourse du 18/10/2026, lu |
| Robots de spectacle | partagé : Reachy 2 sur ROS 2 + Gazebo, Mirokaï sur ROS + maison *(extrait)*, Ameca sur un cadre maison (Tritium) | pages lues sauf mention |

---

## 3. Où en est Didier, couche par couche

Légende : ✅ conforme · 🟡 écart assumé, à garder · 🟠 écart à combler · ⛔ manque bloquant.

| # | Couche | État relevé dans le dépôt | Verdict |
|---|---|---|---|
| A | Distribution, build | Jazzy, `colcon`/ament, packages à plat nommés, un seul reste Humble (rôles `deploy/roles/ros_humble_*` hors liste) | ✅ — supprimer les deux rôles Humble au lot 4e |
| B | Messages | presque tout passe par `StringTime` (JSON dans une chaîne) ; les grandeurs physiques sont typées (`Twist`, `PointStamped`, `Odometry`) | 🟡 — voir §6.2 |
| B | Ordres longs | aucun service ni action ; l'état d'avancement est refait à la main (`animation_state` latché, `route_state_cause`, durée restante) | 🟠 pour le neuf — voir §6.1 |
| B | Nommage, QoS | namespace par robot, topics relatifs, profils QoS et catalogue dans `theatre_contrats`, gravés en tests | ✅ au-dessus de l'usage |
| B | Middleware | Fast DDS par défaut, découverte multicast, Docker en réseau hôte, domaines 42/43 | ✅ — voir §5.1 |
| C | Chaîne roues | `Twist` en unités SI (REP-103), `twist_mux` à priorités, homme-mort double, protocole caméra | ✅ c'est le schéma standard |
| C | **Arrêt d'urgence** | verrou `e_stop` déclaré, **aucun publieur** ; robot sur plaque à bandes, sans chien de garde ni coup-de-poing | ⛔ connu, en cours (carte Sécurité, refonte électrique) |
| C | Odométrie, TF | absentes sur le robot réel (pas d'encodeurs) | 🟠 déjà au plan (étude odométrie) |
| C | Servos | nœud maison (rampe, anti-saturation I²C, homme-mort), `ros2_control` écarté le 26/09 | 🟡 décision confirmée |
| D | Perception | suiveur de personne maison (MediaPipe / YOLO) → `PointStamped` | 🟡 — ROS4HRI non retenu, §5.5 |
| D | Parole | chaîne maison (détection de voix → transcription → LLM → synthèse) | 🟡 aucun standard ROS n'existe |
| E | Décision | `py_trees` + score, sim seulement | ✅ |
| E | Animations | séquences JSON à images clés | 🟡 comme tout le métier du spectacle |
| F | Simulation | Gazebo Harmonic (la version appariée à Jazzy), sans écran, facteur temps réel mesuré, fumée nocturne | ✅ au-dessus de l'usage |
| G | **Enregistrement** | zéro `rosbag` dans le dépôt ; boîte noire décidée le 12/07, pas faite | 🟠 |
| G | Santé | message maison `HardwareStatus` + battement de cœur vision ; `/diagnostics` n'est publié que par `twist_mux` | 🟠 petit |
| H | Cycle de vie | pas de nœuds *lifecycle* ; redémarrage Docker + `respawn` | 🟡 suffisant, §5.5 |
| H | Horloges | `systemd-timesyncd` sur les Pi (liste `deploy/attendu/`) | ✅ tant que le routeur 4G donne Internet ; dérive possible hors ligne, jamais mesurée |
| I | Déploiement | Ansible en une commande, contrôle d'écart, empreinte de version publiée, secrets hors git | ✅ |
| I | **CI** | les 4 `tests.yml` sont restés sous `legacy/*/.github/` : **GitHub ne les exécute plus** depuis le 02/11 ; la fumée ne lance pas les tests unitaires | 🟠 |
| J | Réglementation | aucune analyse de risques écrite, aucune mention du règlement Machines dans la doc | 🟠 — §5.6 |

**Lecture d'ensemble.** Les lignes ✅ sont les fondations ; les 🟡 sont des choix défendables
qu'il serait coûteux et inutile de « normaliser ». Restent une ligne ⛔ déjà prise en charge
et six lignes 🟠, dont quatre se règlent en moins d'une séance.

---

## 4. ROS est-il toujours le bon choix ?

**Oui.** Les raisons, dans l'ordre de leur poids pour Didier :

- **Aucun mouvement de sortie mesurable.** ROS 2 représente 91,2 % des téléchargements ROS ;
  les adresses uniques d'octobre passent de 844 000 à 1,3 million en un an *(téléchargements,
  pas déploiements)*. La collecte n'a trouvé **aucun** récit récent d'entreprise quittant
  ROS, ni aucun chiffre de part en production : l'absence de preuve vaut dans les deux sens.
- **Les alternatives sont jeunes et en Rust.** `dora-rs` annonce sa version 1.0 en
  septembre 2026 et déclare elle-même une reprise après redémarrage partielle ; `copper-rs`
  est plus petit encore. Ni l'une ni l'autre n'a de navigation, de simulateur intégré ni de
  pilotes de lidar. Changer voudrait dire réécrire 1 619 tests de Python vers un autre
  langage pour perdre Gazebo et `twist_mux`.
- **Ce que ROS apporte à Didier arrive maintenant.** Jusqu'ici le robot joue des séquences :
  un bus de messages suffisait. Avec le lidar, le corps sûr, l'odométrie et la boîte noire,
  chaque brique existe toute faite côté ROS. Partir aujourd'hui, c'est partir la veille du
  jour où l'investissement rapporte.
- **Les pairs du spectacle ne tranchent pas contre.** Reachy 2 (Pollen) est sur ROS 2 ;
  Ameca a un cadre maison, mais Engineered Arts a une équipe pour l'entretenir.

**Ce que ROS coûte vraiment, et la parade :**

| Critique relevée dans la communauté | Vrai pour Didier ? | Parade |
|---|---|---|
| DDS « sous-optimal » en Wi-Fi (dit par une mainteneuse, 02/2024) | à mesurer : aucun incident DDS n'est documenté dans le dépôt | §5.1 |
| Images Docker et dépendances lourdes | oui (build sur Pi) | déjà traité : images sur le Hub |
| Pas de champs optionnels dans les messages | contourné par le JSON de `StringTime` | §6.2 |
| Épuisement des projets tenus par une seule personne | **oui, c'est le risque n° 1** | intégrer peu, supprimer ce qui ne sert plus |

**Distribution.** Dates lues dans les sources de la documentation officielle (dépôts GitHub
`ros2_documentation` et `rep`, le 11/11) :

| Distribution | Sortie | Fin de support | Ubuntu | Gazebo apparié |
|---|---|---|---|---|
| Humble | mai 2022 | mai 2027 | 22.04 | — |
| **Jazzy** (LTS, celle de Didier) | mai 2024 | **mai 2029** | 24.04 | Harmonic |
| Kilted | mai 2025 | décembre 2026 | 24.04 | Ionic |
| Lyrical (LTS) | 22 mai 2026 | mai 2031 | 26.04 | Jetty |

Rester sur Jazzy : deux ans et demi de marge. Passer à Lyrical changerait Ubuntu, Gazebo
(Harmonic y est « non recommandé ») et des API ; un fil de mai 2026 signale des paquets
encore incomplets *(extrait)*. **Fenêtre raisonnable : après L5, quand le robot roule, par un
essai en sim** (c'est un changement d'image de base, que Docker rend réversible). La fin de
support de Gazebo Harmonic n'a pas été lue *(de mémoire : 2028, à relire)*.

---

## 5. Les briques « standard » : lesquelles prendre, lesquelles laisser

### 5.1 Zenoh à la place de DDS — **non maintenant** (je corrige ma première réponse)

Faits du 11/11 :
- Sous **Jazzy**, `rmw_zenoh` s'installe par paquet mais **n'apparaît pas** dans le tableau
  de niveaux de support (REP-2000, lu) ; il est de niveau 1 à partir de Kilted. Des
  changements de protocole cassants y ont été rétroportés *(extrait)*.
- Il faut un routeur `rmw_zenohd` par machine et des adresses explicites ; pas de multicast.
- Défaut connu (issue n° 978, cité par le README) : sous forte charge processeur, **perte
  silencieuse** possible de services et de publications `TRANSIENT_LOCAL`. Or Didier repose
  sur une dizaine de topics latchés (`animation_state`, `catalogue`, `camera_state`…).
- Aucune mesure comparée récente n'a été trouvée ; la seule mesure Wi-Fi lue (Arm) montre
  qu'un Zenoh **non réglé** gaspille la moitié du débit.

Jugement : le bénéfice est supposé (aucun incident DDS au dossier), le risque est réel (topics
latchés, Pi 4 chargé), et le middleware porte le `Twist` de la télécommande — y toucher,
c'est toucher le chemin des roues, donc refaire le protocole caméra. La décision de juillet
(`etude-interface-web.md` §8, « reporté ») tient.

**Ce qui la rouvrirait** : (a) le passage à Lyrical ; (b) un défaut DDS **mesuré** sur le
Wi-Fi du robot ; (c) une télécommande qui doit franchir les réseaux. En cas de (b), essayer
d'abord le moins cher : découverte par pairs statiques, sans multicast, avec les variables
`ROS_AUTOMATIC_DISCOVERY_RANGE` et `ROS_STATIC_PEERS` *(de mémoire, présentes depuis Iron ;
à relire dans la doc Jazzy)* — zéro changement de middleware.

### 5.2 `ros2_control` pour les roues — **non** (re-tranche « l'étape 5 »)

La feuille de route dit « étape 5 = `ros2_control` + nav2 ». Je propose de la reformuler.

- Une interface matérielle `ros2_control` s'écrit en **C++** : la collecte n'a trouvé aucune
  voie Python. Ce serait le premier C++ du dépôt, pour un projet maintenu en Python.
- L'API bouge : Lyrical vient d'en supprimer une partie (billet du 06/11/2026, lu).
- Ce que la brique apporterait — cinématique différentielle, limites, odométrie — tient en
  quelques centaines de lignes Python, dont la moitié existe (`didier_drive/diff_drive.py`).
- Le robot de référence de cette taille (`linorobot2`) pilote ses moteurs par micro-ROS ; sa page
  matériel ne cite pas `ros2_control`.

Ce que Nav2 et le reste de l'écosystème exigent, c'est l'**interface** : `cmd_vel` en entrée,
`odom` + TF `odom → base_link` en sortie. **Étape 5 reformulée : « contrat odométrie/TF
conforme (REP-105) + briques Nav2 choisies »**, `ros2_control` restant possible plus tard si
un pilote du commerce l'impose (le RoboClaw a les deux formes, étude du 26/09).

*Ce que ça supprime* : un chantier C++ et une dépendance à API mouvante. *Ce que ça ne
supprime pas* : l'odométrie elle-même, toujours nécessaire.

### 5.3 Nav2 — **le moniteur de collision oui (à l'essai), la navigation sur carte non**

- **Moniteur de collision** (`nav2_collision_monitor`) : il lit un `LaserScan`, se place sur
  le chemin de `cmd_vel`, ignore les cartes de coût, et coûte 4 à 5 ms par balayage de
  360 points (README Jazzy, lu). Zones d'arrêt, de ralenti et d'approche se déclarent en
  YAML. C'est, trait pour trait, la « zone d'arrêt dure < 0,6 m » et la « zone de ralenti »
  du corps sûr (`etude-autonomie-improvisation.md` §3.2).
- **Limites prévisibles** *(de mémoire, à vérifier à l'essai)* : c'est un nœud *lifecycle* à
  activer ; son ralenti est proportionnel, pas « par palier » ; il ne connaît ni le verrou
  après perte du capteur, ni le battement de cœur de la télécommande. Le corps sûr resterait
  donc un petit nœud maison **autour** de lui.
- **SLAM, localisation, planification sur carte** : pas d'emploi. Une rue pleine de monde
  n'a pas de carte stable, et les déplacements voulus (« suivre », « aller voir à 3 m »,
  « pivoter ») sont locaux. Aucune mesure de Nav2 complet sur Pi 4 4 Go n'a été trouvée.

Proposition : au lot A0, **essayer le moniteur en sim** avec trois critères d'acceptation —
il exprime les règles du §3.2, il arrête sur capteur muet, sa charge sur Pi 4 est mesurée.
S'il échoue à l'un des trois, on écrit le filtre maison, sans regret.

### 5.4 Enregistrement et visualisation — **oui, c'est le manque d'outillage le plus rentable**

La boîte noire est décidée depuis le 12/07 (`etude-telediagnostic.md` §6 : segments de 60 s
sur SD, 30 jours, sans caméra). L'étude d'aujourd'hui précise seulement **avec quoi** :

- `rosbag2`, format MCAP (défaut de Jazzy : le fichier embarque ses définitions de messages,
  ce qui lève la critique « un enregistrement illisible hors de son espace de travail »).
- Le **mode instantané** (`--snapshot-mode`, tampon circulaire en mémoire vidé sur appel de
  service) répond au bouton START de la télécommande sans user la carte SD. À combiner ou à
  substituer aux segments continus : à trancher quand le lot s'ouvre, mesure d'usure à l'appui.
- Lecture : **Foxglove** (offre gratuite lue le 11/11 : 3 utilisateurs, 5 appareils, 10 Go ;
  les fichiers locaux s'ouvrent sans Internet) ou PlotJuggler (libre, non relu). Réserve :
  le JSON de `StringTime` s'affiche comme du texte, il ne se trace pas en courbe.

*Ce que ça supprime* : tout enregistreur maison ; à terme `collect-incident.sh` n'aurait plus
qu'à joindre le fichier.

### 5.5 Ce que je recommande de **ne pas** intégrer

| Brique | Pourquoi non |
|---|---|
| Nœuds *lifecycle* partout | utiles à Nav2, pas à des nœuds Python de 20 Hz déjà protégés par homme-mort et redémarrage ; non sourcé comme norme des petites équipes |
| ROS4HRI (REP-155) | développé et testé par un seul acteur (PAL), installation depuis les sources, coût sur Pi 5 inconnu. À la rigueur, **emprunter son vocabulaire** quand le lot A2 nommera personnes et voix |
| BehaviorTree.CPP + Groot2 | C++ ; l'éditeur Groot2 est sous licence PRO, prix non publié. `py_trees` fait le travail |
| micro-ROS sur les RP2040 | maintenu mais sans version publiée ; le protocole série maison est testé, et la télécommande Twist direct est tranchée |
| Cadres de conversation (Pipecat, LiveKit) | aucun pont Pipecat trouvé ; LiveKit suppose une infrastructure WebRTC. La chaîne maison porte des contraintes (repli hors ligne, didascalies vers le visage) qu'ils n'ont pas |
| Isaac Sim | exige au minimum une RTX 4080 16 Go (page NVIDIA, lue) ; conçu pour l'apprentissage, pas pour tester une logique de jeu |
| Outils de mise à jour à distance (Mender, balena, RAUC) | aucun consensus, aucun retour d'expérience lu ; Ansible en une commande suffit à deux Pi |
| `rosbridge` | déjà rejeté en juillet, motif inchangé (expose tout le graphe) |

### 5.6 Sécurité et réglementation — le seul point où le « standard » est une obligation

- **Technique** : la règle du métier est celle que le projet s'est déjà donnée — l'arrêt
  coupe la puissance sans passer par le logiciel. Tant que la carte Sécurité n'existe pas,
  aucune brique de cette étude n'autorise un roulage au sol.
- **Méthode manquante** : une **analyse de risques d'une page** (masse, vitesse maximale,
  distance d'arrêt, énergie, qui est à portée, ce qui se passe à chaque panne). C'est la
  pratique de base de tout constructeur, elle n'existe pas dans la doc, et l'assureur la
  demandera. Les matériaux sont déjà là (incidents, protocole caméra, §3.2 du corps sûr).
- **Réglementation** : le règlement Machines (UE) 2023/1230 s'applique le **20 janvier 2027**
  (page INRS, lue). **Le statut d'un prototype artistique exploité par son constructeur n'a
  pas été établi** : le texte de l'article 2 n'a pas pu être lu, seuls des résumés évoquent
  des exclusions. Je ne suis pas juriste et je ne conclus pas. À faire avant la première
  sortie publique : poser la question à l'assureur de la compagnie, par écrit.

---

## 6. Deux habitudes ROS réinventées

### 6.1 Les actions, pour les déplacements autonomes

Un ordre long avec retour, résultat et annulation s'appelle en ROS une **action**. Le projet
en a reconstruit la sémantique trois fois (`animation_state` + durée restante,
`route_goto` + `"cancel"`, `route_state_cause`), chaque fois avec ses propres pièges
(durabilité à accorder des deux côtés, cause inconnue = refus).

Proposition, **pour le neuf seulement** : les déplacements du sélecteur de jeu (`aller_voir`,
`tourner`, `avancer`) deviennent des actions. `py_trees_ros` fournit le client tout fait, et
c'est le schéma qu'emploie Nav2. On ne touche ni aux animations ni à la console web, qui
fonctionnent.

*Ce que ça supprime* : les topics d'état et de cause à inventer pour chaque nouveau geste.
*Coût* : un package de définitions d'actions dans `theatre_interfaces`, et le pont web devra
savoir annuler.

### 6.2 `StringTime` — écart assumé, à borner par une règle

Faire passer du JSON dans une chaîne est le plus gros écart du dépôt avec l'esprit de ROS :
le middleware ne vérifie rien, les outils n'affichent que du texte. Mais le contrat est tenu
ailleurs (`theatre_contrats`, refus explicite du JSON invalide, inventaire gravé), et il
donne la souplesse que les messages ROS n'ont pas.

**Ne pas réécrire.** Graver en revanche, dans le README de `theatre_contrats`, la règle déjà
suivie de fait : *toute grandeur physique ou perçue voyage dans un message standard typé*
(`Twist`, `LaserScan`, `Odometry`, `JointState`, `PointStamped`, `DiagnosticArray`) ;
`StringTime` est réservé aux **ordres de jeu**. Corollaire pour la santé : les prochains
signaux (batterie, lidar, odométrie) vont sur `/diagnostics` plutôt que dans de nouveaux
champs de `HardwareStatus` — les outils les affichent sans rien écrire.

---

## 7. Ce que je propose, dans l'ordre

| # | Action | Nature | Coût | Quand |
|---|---|---|---|---|
| 0 | Carte Sécurité, publieur `e_stop`, refonte électrique | **déjà décidé** | — | en cours, avant tout roulage |
| 1 | **Remettre une CI à la racine** : tests unitaires des trois packages à chaque poussée | arbitrage D1 | une séance ; Opus suffit | maintenant, sans attendre L2 |
| 2 | Règle « physique = typé » + santé sur `/diagnostics` dans `theatre_contrats` | arbitrage D2 | une heure, doc et un test | au prochain lot qui touche le contrat |
| 3 | Boîte noire en `rosbag2` MCAP, mode instantané à évaluer | précise une décision du 12/07 | le lot prévu | télédiagnostic étape 2 |
| 4 | Analyse de risques d'une page + question écrite à l'assureur | arbitrage D3 | une séance avec David | avant le premier roulage au sol |
| 5 | Étape 5 reformulée : contrat `odom`/TF, sans `ros2_control` | arbitrage D4 | zéro (c'est un renoncement) | à acter |
| 6 | Essai du moniteur de collision Nav2 en sim, trois critères | arbitrage D5 | dans le lot A0 | à l'arrivée du lidar |
| 7 | Actions ROS pour les déplacements du sélecteur | arbitrage D6 | dans la spec A2 | lot d'autonomie suivant |
| 8 | Supprimer les rôles `ros_humble_*` | ménage | minutes | lot 4e |
| 9 | Essai de Lyrical en sim | veille | une séance | après L5, pas avant 2027 |

**À ne pas rouvrir** : mono-dépôt et noms de packages (01/11), télécommande Twist direct
(01/11), `ros2_control` pour les servos (26/09), `rosbridge` et Zenoh reportés (11/07),
boîte noire sans caméra (12/07), `py_trees` + score (02/11), lidar 2D sur le Pi 4 (02/11).

## 8. Limites de cette étude

- Les collectes n'ont couvert ni les nœuds *lifecycle*, ni `diagnostic_updater`, ni les
  retours ROSCon 2025-2026, ni la pratique d'assurance des robots en espace public.
- Aucune mesure n'a été faite : la charge de Nav2 sur Pi 4, le comportement de DDS sur le
  Wi-Fi du robot et la dérive d'horloge hors ligne restent à mesurer avant d'en parler.
- Quatre affirmations reposent sur ma mémoire et sont marquées comme telles (variables de
  découverte statique, limites du moniteur de collision, fin de support de Harmonic, client
  d'action de `py_trees_ros`).
- La partie réglementaire n'est pas un avis juridique.
