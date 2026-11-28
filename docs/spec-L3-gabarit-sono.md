# Spec L3 — gabarit d'appareil + sono

**Statut : spec FERMÉE, écrite le 28/11/2026 (Fable). Rien de codé.** Étude mère :
[`etude-architecture-globale.md`](etude-architecture-globale.md) §5.0 (critère 1 : « ajouter un
appareil ≈ 1 jour »), §5.5, §5.7, §5.8, §5.9 et §6 (ligne L3). Suite de
[`spec-L2-sim-multi-conteneurs.md`](spec-L2-sim-multi-conteneurs.md) (décision 3 : la couture
« pilote » naît avec le gabarit ; §6 : la sono est le 5e service de la sim).

Un implémenteur (Opus) exécute un sous-lot SANS rien trancher : tout choix est au §2. Si un fait
relevé au §0 s'avère faux sur pièce, il **s'arrête et le rapporte**, sauf là où un repli est écrit
(§9). Aucun chemin roues, aucun arrêt d'urgence, aucune carte Sécurité n'est touché par ce lot.

**Porte de sortie du lot (étude §6)** : la sono joue en sim un audio et un relais visibles sur la
page scène ; elle est déployée sur l'hôte `s` par Ansible ; **temps mesuré ≤ 1 jour, ou le
gabarit est corrigé** (définition de la mesure : §10).

---

## 0. Faits relevés le 28/11 (sur `main` 16d2711d)

1. **Aucune trace de la sono dans le dépôt** : ni package, ni `machines/sono/`, ni hôte `s`
   (retirés le 11/11, commit 5fd66595), ni rôle Ansible propre (`sceno` n'existe plus ; les rôles
   sont génériques et pilotés par `machine.yml`). `machines/README.md` § « Ajouter une machine »
   décrit déjà les 4 gestes côté Ansible.
2. **L'ancienne sono** (archive GitHub publique `dadou_sceno_ros`, lue le 28/11, rien recopié) :
   un nœud actif (`audio_node`, abonné au topic `audio` du robot, 7 entrées dans son
   `audios.json`), un relais `cut_voice` sur **PCF8574 I²C à l'adresse 0x20, broche 0**,
   impulsion de **500 ms** (actif = voix coupée, repos = voix passante). Lecture par VLC à travers
   la lib partagée. Sur le disque il ne reste que ses audios, dans l'archive locale hors dépôt du
   12/11 : **45 fichiers, dont 42 absents du manifeste** `data/json/audios-prives.json`
   (`song` 23, `didier20` 14, `effects` 5).
3. **Audios** : hors dépôt (medias privés), manifeste `data/json/audios-prives.json` = 257
   entrées `{chemin: {sha256, taille, duree_s}}`. Le topic `audio` du robot porte un **chemin
   relatif** (`"didier20/superbe-jack.mp3"`) ou `"stop"`. Dans le rôle `synchronise`, la copie
   des audios privés est conditionnée à `donnees_dir is defined` (robot seul) ; l'écriture de
   `conf/DEPLOY_SHA` à `project_ros_dir == 'robot'`.
4. **Paquets ROS standard**, index apt `packages.ros.org` noble lu le 28/11, **amd64 et arm64** :
   `ros-jazzy-sound-play` (+ `-msgs`), `ros-jazzy-audio-play`, `ros-jazzy-audio-common` existent ;
   côté entrées-sorties, seul `ros-jazzy-gpio-controllers` (famille ros2_control). Aucun paquet
   PCF8574, I²C ou relais.
5. **Sim** : `machines/sim/docker-compose.yml` = 4 services (`monde`, `robot`, `vision`,
   `telecommande`), domaine 43 littéral, `FASTDDS_BUILTIN_TRANSPORTS=UDPv4`, réseau et IPC hôte,
   `pid: "service:monde"`. Le programme de fumée grave la liste des conteneurs
   (`machines/sim/fumee/banc.py`, `CONTENEURS`) ; les épreuves sont dans
   `machines/sim/fumee/plan.toml`.
6. **Page scène** : `web_protocol.TOPICS_LECTURE` porte les topics latchés montrés par la page
   (`corps_sur/etat`, `corps/etat`…) ; le jugement se fait côté pont dans un module pur testé
   (`panneau_audio.py`), la page affiche. **L2c (états `sim/etat/*`, panneau « Matériel simulé »)
   n'est pas fait et il est gelé** : L3 ne s'appuie pas dessus.
7. **Modèle de package neuf** : `didier_corps_sur` (logique pure en stdlib, horloge injectée,
   nœud mince sans règle, `contrat.py`, config par machine gravée, README-contrat) ; CI =
   une ligne par suite dans `.github/workflows/tests.yml`.
8. **Chemins des Pi** : `~/ros2_ws/src/<projet>/conf/` (L2e, qui les renomme, n'est pas fait).

---

## 1. Ce que L3 supprime (règle du dépôt)

| Supprimé | Quand | Pourquoi c'est sûr |
|---|---|---|
| `machines/lights/README.md` « vide pendant L0 » → remplacé par une ligne « à créer avec `nouvel_appareil.py` » | L3a | le gabarit devient LA façon de créer une entrée |
| Le § « Ajouter une machine » de `machines/README.md` (4 gestes à la main) → renvoi au README du gabarit | L3a | une seule procédure écrite |
| Les conditions par NOM dans `synchronise` (`donnees_dir is defined` pour les audios, `project_ros_dir == 'robot'` pour le sha) → variables `audios_prives`, `sha_deploye` | L3a | même effet pour le robot, gravé par test |
| La mention « rôle Ansible `sono` » partout où elle subsiste | L3d | il n'y a pas de rôle par appareil (décision 14) |
| `dadou_sceno_ros` du disque (étude §6) | — | **déjà fait le 12/11** ; l'archive locale des audios n'est pas dans le dépôt, L3 n'y touche pas |

L3 ne supprime **aucun** code du cœur, de la télécommande ni de la sim. `audio_node` et
`relays_node` du robot ne changent pas.

---

## 2. Décisions (ne pas rouvrir)

### Le gabarit

1. **Deux moitiés, pour tenir « sans copier ni code ni JSON »** :
   - une **bibliothèque** importée (`packages/theatre_gabarit/theatre_gabarit/`, package
     ament_python normal) qui porte toute la plomberie commune ;
   - un **squelette** mince (`packages/theatre_gabarit/squelette/`, marqué `COLCON_IGNORE`),
     recopié et renommé par `tools/nouvel_appareil.py <nom>`. Ce qui est recopié ne contient
     aucune règle : des fichiers à trous et des tests rouges qui disent quoi remplir.
   Écarté : tout recopier (la plomberie divergerait d'appareil en appareil — l'histoire des liens
   symboliques) ; une classe mère riche (la lib partagée fourre-tout qui renaît).
2. **La bibliothèque est bornée à 4 modules, inventaire gravé par test** :

   | Module | Rôle |
   |---|---|
   | `noeud.py` | `NoeudAppareil` (rclpy) : état latché publié à chaque changement et au plus tard toutes les 2 s, `diagnostics` à 1 Hz, lecture du sha déployé, arrêt propre (pilotes au repos), exception dans un rappel = pilotes au repos puis sortie code 1 |
   | `pilotes.py` | `choisir(nom, fabriques, ros_domain_id)` : `sim` ou `materiel` ; **`sim` hors domaine 43 = refus, sortie code 2** ; santé d'un pilote = `ok` / `absent` / `erreur` |
   | `lancement.py` | `groupe_appareil(...)` pour les launch : namespace ABSOLU `/<ROBOT_NAME>/`, arguments `pilote`, `config` |
   | `essais.py` | aides de test : pilote enregistreur, `verifier_appareil(dossier)` (décision 6) |

   **Règle d'émergence (étude §6 : « le gabarit émerge de la sono, pas l'inverse »)** : rien
   n'entre dans la bibliothèque que `sono_core` n'utilise ; un test de `sono_core` grave qu'il
   importe les 4 modules. Un 5e module exige un 2e appareil qui en a besoin.
3. **Arborescence d'un appareil** (ce que produit `nouvel_appareil.py sono`) :

   ```
   packages/sono_core/
   ├── README.md                 README-contrat (décision 5)
   ├── package.xml  setup.py  setup.cfg  resource/sono_core
   ├── sono_core/
   │   ├── contrat.py            noms, types, QoS (renvoie à theatre_contrats) ; NOM_NOEUD
   │   ├── logique.py            règles PURES, stdlib, horloge en argument
   │   ├── reglages.py           YAML + bornes dures, refus = exception lisible
   │   ├── pilotes/{base.py, sim.py, materiel.py}
   │   └── noeud.py              mince : un message = un appel à la logique, aucune règle
   ├── launch/sono.launch.py     10 lignes, par `theatre_gabarit.lancement`
   ├── config/sono.yaml          défauts sûrs du package
   └── test/{conftest.py, test_logique.py, test_reglages.py, test_pilotes.py,
             test_contrat_noeud.py, test_gabarit.py}
   machines/sono/
   ├── machine.yml  README.md  sono.yaml (câblage de CETTE machine)
   ├── docker/Dockerfile  docker/arm/docker-compose-arm.yml
   ├── packages-docker.txt  requirements.txt
   ├── scripts/launch-ros-in-docker.sh
   └── rpi/{project_bash, asound.conf}
   machines/sim/sono/entree.sh   entrée du service de sim (pose pilote:=sim)
   ```
4. **Pilote sim contre pilote matériel** (étude §5.7, couture DANS le nœud) :
   - `pilotes/base.py` : un `Protocol` par famille de matériel ; `materiel.py` importe ses libs
     **à l'appel** (le module s'importe sur le PC) ; `sim.py` tient l'état en mémoire, stdlib.
   - **Le reste du code est identique** : la logique ne sait pas quel pilote elle a.
   - Défaut du launch = `materiel` (rien à poser sur le Pi) ; la sim passe `pilote:=sim` par
     l'entrée du compose, jamais par une variable lue côté appareil (même règle que L2, décision 2).
   - Matériel absent (carte son, PCF8574) : le nœud **reste vivant**, l'organe dit
     `sante: "absent"`, `diagnostics` passe à ERROR (règle du cœur : un nœud ne meurt pas pour un
     périphérique). Un Pi hors scène passe donc `noeuds_attendus`.
   - Un appareil n'utilise **jamais** `use_sim_time` : il vit hors de Gazebo, horloge murale.
5. **README-contrat type** : 8 titres, dans cet ordre, vérifiés par `verifier_appareil` —
   `Rôle` (une phrase) · `Machine` (où il tourne, lien vers `machines/<m>/`) · `Topics` (tableau :
   nom relatif, type, sens, QoS, constante de `theatre_contrats`) · `Comportement` (règles
   numérotées) · `Pilotes` (ce que fait chacun, matériel et câblage) · `Simuler` (commande, ce
   qu'on voit sur la page scène) · `Tester` (commande, ce qui est gravé) · `Déployer` (commande,
   contrôle).
6. **`essais.verifier_appareil(dossier)`**, appelé par le `test_gabarit.py` de chaque appareil
   (3 lignes), fait rougir tant que : un titre du README manque ; le mot `APPAREIL` du squelette
   subsiste ; un topic du `contrat.py` est absolu ou absent de `theatre_contrats.topics` ;
   l'appareil n'est pas au registre (décision 9) ; `machines/<m>/machine.yml` manque ou n'a pas
   `packages`, `launch_cmd`, `noeuds_attendus`, `sentinelle_build` ; le package n'est pas dans la
   matrice de `tests.yml` ; le service `<m>` manque dans `machines/sim/docker-compose.yml` ;
   aucune épreuve de `plan.toml` ne porte son id ; le nœud contient une règle (liste gravée des
   `if` de `noeud.py`, motif `didier_corps_sur/test/test_contrat_node.py`). **Les tests rouges
   SONT la liste des gestes** : le générateur n'édite aucun fichier partagé.
7. **Tests gravés** (mémoire « graver la valeur attendue ») : toute valeur attendue est un
   littéral, jamais recalculée par le code testé ; contrôle par mutation exigé à la porte de
   chaque sous-lot (une règle faussée → au moins un test rouge, noté dans la PR).
8. **CI** : une ligne par package dans la matrice de `.github/workflows/tests.yml`
   (`theatre_gabarit`, `sono_core`), `requirements-test.txt` inchangé (stdlib + PyYAML). La casse
   d'un appareil par le commun rougit ainsi au commit (critère 4 de l'étude). Pas de nouveau
   workflow.

### Le contrat commun des appareils

9. **Module neuf `theatre_contrats/appareils.py`** (pur, testé, littéraux gravés) :
   - `REGISTRE` : `{"sono": {"etat": "sono/etat", "ordres": {"audio": "sono/audio", "relais":
     "sono/relais"}}}` — LA liste des appareils du parc, lue par le pont web ;
   - l'enveloppe d'état, **la même pour tout appareil** : `encoder_etat(...)`,
     `decoder_etat(brut)` (illisible → `None`, jamais d'exception) ;
   - les types d'organes connus : `audio`, `relais` (un 3e type = un appareil qui en a besoin).
   Les trois noms entrent dans `topics.py` (`SONO_AUDIO`, `SONO_RELAIS`, `SONO_ETAT`) et dans
   `test_inventaire.py`.
10. **Enveloppe d'état** (`StringTime`, JSON, `qos.latched()` des deux côtés) :

    ```json
    {"v": 1, "appareil": "sono", "pilote": "sim", "sha": "dev", "t_ms": 1764300000000,
     "organes": [
       {"nom": "audio", "type": "audio", "valeur": "bugs-joues/begaiement.wav",
        "debut_ms": 1764299999500, "duree_ms": 2160, "sante": "ok"},
       {"nom": "cut_voice", "type": "relais", "valeur": true, "sante": "ok"}],
     "refus": null}
    ```

    `valeur` au repos : `""` (audio), `false` (relais). `debut_ms` et `duree_ms` : `null` au
    repos. `refus` : `{"code", "detail", "t_ms"}` du DERNIER ordre refusé, remis à `null` par le
    premier ordre accepté. `sha` : contenu de `conf/DEPLOY_SHA`, `"dev"` si absent (sim).
    L'état d'un appareil est publié **en sim comme en réel** : ce n'est pas un topic `sim/etat/*`
    (ceux de L2c décrivent le matériel simulé des nœuds de génération 1 ; ils rejoindront ce
    modèle à L5, pas avant).
11. **Namespace** : un appareil du spectacle de Didier tourne sous `/<ROBOT_NAME>/` comme le
    robot, la vision et la télécommande ; ses topics sont préfixés par son nom (`sono/…`).
    Écarté : un namespace `/sono/` à part (le pont web et la télécommande ne le verraient pas ;
    « un nom par robot » reste la seule garantie prise, étude §5.2).

### `sono_core`

12. **Topics** (relatifs ; `StringTime` = ordres de jeu, règle du 11/11) :

    | Topic | Type | Sens | QoS | Contenu |
    |---|---|---|---|---|
    | `sono/audio` | `StringTime` | entrée | `volatile(10)` | chemin relatif d'un audio du manifeste, ou `"stop"` — **même forme que `audio` du robot** |
    | `sono/relais` | `StringTime` | entrée | `volatile(10)` | nom d'un relais de `sono.yaml` (`"cut_voice"`), ou `"stop"` |
    | `sono/etat` | `StringTime` | sortie | latché | enveloppe de la décision 10 |
    | `diagnostics` | `DiagnosticArray` | sortie, 1 Hz | fiable, 10 | un statut `sono` : OK / WARN (ordre refusé depuis < 10 s) / ERROR (un organe `absent` ou `erreur`) |

    Nœud `sono` (`noeuds_attendus: [/didier/sono]`), exécutable `sono_node`.
    **La sono a ses propres ordres** : elle ne s'abonne pas à `audio` ni à `relay` du robot
    (question 1 pour David, défaut appliqué).
13. **Comportement** (logique pure `logique.Sono`, horloge passée en argument, tic à 20 Hz) :
    1. **Audio, une piste à la fois.** Un chemin accepté arrête la lecture en cours puis joue ;
       le même chemin rejoué repart du début. `"stop"` arrête. Fin de fichier → repos.
    2. Chemin absolu ou contenant `..` → refus `chemin_invalide` ; chemin absent du manifeste →
       `audio_inconnu` ; au manifeste mais absent du disque (pilote matériel) → `audio_absent` et
       `sante: "erreur"` jusqu'au prochain ordre accepté. Un refus ne coupe pas la lecture en cours.
    3. **Relais = impulsion bornée.** Un nom connu met le relais à l'état actif pendant
       `tenue_ms` (bornes dures 100 à 10 000), puis repos ; rejoué pendant la tenue, il la
       prolonge d'une tenue. `"stop"` remet tous les relais au repos. Nom inconnu →
       `relais_inconnu`, rien ne bouge. Aucun ordre ne peut laisser un relais actif sans fin.
    4. Démarrage, arrêt (SIGTERM) et exception : audio arrêté, tous les relais au repos, AVANT
       de publier ou de sortir.
    5. Payload qui n'est pas une chaîne → refus `ordre_illisible`.
    6. **Hors L3** : volume, fondu, son de fond superposé, liste de lecture, piste « sono » dans
       les séquences, touches de la télécommande (L4).
14. **Données, sans copie.** La sono lit le **manifeste déployé** (`audios-prives.json`, la
    vérité reste `data/json/`) : il donne les chemins valides et les durées. Les fichiers sont
    ceux des medias privés, copiés par Ansible et vérifiés par sha, exactement comme pour le
    robot. Elle ne lit **pas** le topic `catalogue` : elle doit pouvoir jouer robot éteint
    (ambiance avant le spectacle). Aucun `audios.json`, aucun `relays.json` propre : les relais
    sont du CÂBLAGE, déclarés dans `machines/sono/sono.yaml` :

    ```yaml
    audio:  {audios_dir: /home/ros2_ws/src/sono/medias/audios,
             manifeste: /home/ros2_ws/src/sono/medias/audios-prives.json}
    relais:
      pcf8574_adresse: 0x20
      cut_voice: {canal: 0, tenue_ms: 500, actif: haut}   # repos = voix passante
    ```

    La sim lit **ce même fichier** (le pilote sim ignore adresse et canal) : on essaie en sim la
    configuration qui partira sur le Pi.
15. **Pilotes de la sono.**

    | Pilote | `sim` | `materiel` |
    |---|---|---|
    | `PiloteAudio` : `jouer(chemin)`, `arreter()`, `en_cours()`, `sante()` | muet ; « joue » pendant la `duree_s` du manifeste (horloge injectée) | un sous-processus par lecture, sur la sortie ALSA par défaut (`/etc/asound.conf` de la machine, alias par NOM de carte) ; fin = sortie du processus ; `arreter` = SIGTERM puis SIGKILL à 300 ms |
    | `PiloteRelais` : `ecrire(canal, actif)`, `sante()` | dictionnaire en mémoire | `adafruit-circuitpython-pcf8574` (déjà dans le parc, robot en 0x21), import à l'appel ; carte absente = `absent`, sans exception |

    Lecteur du pilote matériel : `mpg123 -q` pour `.mp3`, `aplay -q` pour `.wav` (les deux déjà
    dans les listes de paquets du robot), **sauf verdict contraire de l'essai borné ci-dessous**.
    Aucune dépendance à `dadou_utils_ros` (première machine du parc sans la lib partagée ; sa
    liste `packages` est explicite : `theatre_contrats`, `theatre_interfaces`, `theatre_gabarit`,
    `sono_core` ; un test qui exigerait la lib sur toute machine est assoupli pour celle-ci,
    raison écrite dans le test).

### Réutilisation : paquets standard (règle du 25/11)

16. **Relais — verdict écrit ici, pas d'essai** : le seul paquet Jazzy d'entrées-sorties est
    `gpio_controllers` (ros2_control), qui demanderait d'écrire une interface matérielle C++ pour
    UNE broche d'un PCF8574. Non retenu. La bibliothèque Adafruit, déjà utilisée par le robot,
    suffit ; le contrat (topic d'ordre + état) reste le nôtre.
17. **Lecture audio — essai borné à 1 h, en L3b, AVANT d'écrire le pilote matériel** :
    `ros-jazzy-sound-play` dans un conteneur jetable de l'image `didier-sim/robot:local`.
    Retenu **seulement si les 5 critères sont vrais** ; sinon le lecteur de la décision 15, sans
    discussion. Verdict et mesures écrits dans le README de `sono_core` (§ Pilotes) et dans
    `chantiers.md`.

    | # | Critère |
    |---|---|
    | 1 | joue un `.mp3` ET un `.wav` par un chemin de fichier, sur une sortie ALSA nommée |
    | 2 | arrêt effectif en moins de 300 ms après la demande |
    | 3 | la FIN de lecture est connue du client (résultat d'action), sans sonder |
    | 4 | pas de serveur de son exigé (ni PulseAudio ni PipeWire dans le conteneur) |
    | 5 | l'image grossit de moins de 150 Mo |

    S'il est retenu : le pilote matériel devient un client de `sound_play`, lancé par
    `sono.launch.py` quand `pilote:=materiel` ; `sono/audio`, `sono/etat` et le pilote sim ne
    changent pas.

### Page scène

18. **Une tuile « Appareils », générique**, dans la colonne technique (à côté de « Corps sûr ») :
    une ligne par appareil du `REGISTRE`, rendue d'après l'enveloppe, sans code propre à la sono.

    | Élément | Rendu |
    |---|---|
    | présence | pastille verte si un état de moins de 5 s ; grise « muette » sinon ; « jamais vue » si aucun état reçu |
    | pilote | badge « simulé » ou « matériel » |
    | version | sha court ; rouge « version différente du robot » si différent de `deploy_sha`, aucun des deux n'étant `dev` (étude §5.8) |
    | organe `audio` | « ♪ `<chemin>` — 1,2 / 2,2 s » (avance calculée dans la page d'après `debut_ms`) ou « silence » |
    | organe `relais` | pastille allumée/éteinte + nom |
    | `sante` ≠ `ok` | l'organe barré, « absent » ou « erreur » |
    | `refus` | une ligne « refusé : `<code>` — `<detail>` » |
    | avec la main | par organe `audio` : liste des audios (`/api/catalog`), **Jouer**, **Stop** ; par organe `relais` : un bouton d'impulsion |

19. **Pont web** : pour chaque appareil du registre, `etat` entre dans `TOPICS_LECTURE` ; les
    ordres de type `audio` dans `WHITELIST_SPECTACLE`, ceux de type `relais` dans
    `WHITELIST_TECHNIQUE` (construits depuis le registre, pas recopiés). **`stop_all` publie
    aussi `"stop"` sur chaque topic d'ordre du registre** : le bouton STOP arrête tout son.
    Le jugement (fraîcheur, version, texte des lignes) est dans un module pur neuf
    `didier_web/panneau_appareils.py`, testé avec des valeurs gravées ; la page affiche.
    Valable en sim et sur le robot (rien de SIM-ONLY ici). Aucun topic roues n'est concerné.

### Sim

20. **5e service `sono` dans `machines/sim/docker-compose.yml`** (pas de surcouche : « tout dans
    la sim », étude §5.0 critère 3) : conteneur `didier-sim-sono`, image `didier-sim/sono:local`,
    **le Dockerfile du Pi** (`machines/sono/docker/Dockerfile`, base `ros:jazzy-ros-base`,
    contextes nommés = sa liste `packages`), `ROS_DOMAIN_ID=43` en littéral,
    `FASTDDS_BUILTIN_TRANSPORTS=UDPv4`, réseau et IPC hôte, `pid: "service:monde"`, ni `/dev`, ni
    `privileged`, ni `restart:`. Entrée `machines/sim/sono/entree.sh` (revérifie le domaine 43,
    lance `launch-ros-in-docker.sh pilote:=sim`). Montages : ses 4 packages, `../sono` (conf),
    `data/json/audios-prives.json` en lecture seule au chemin du manifeste, journaux dans
    `$DIDIER_SIM_JOURNAUX/log-sono`. **Aucun audio monté, aucun son sur le PC** : en sim on VOIT
    la sono, on ne l'entend pas.
21. **Programme de fumée.** En L3a, `CONTENEURS` n'est plus une liste écrite à la main : elle
    est déduite des services du compose (`didier-sim-<service>`, ordre du fichier), et un test
    grave le résultat (4 noms). En L3b elle vaut donc 5 sans retouche du programme ; `image`
    construit 5 images ; `demarrage` exige domaine 43 ×5, colcon ×5 et les `noeuds_attendus` de
    `machines/sono/machine.yml` (liste des machines à nœuds attendus lue de la même façon).
    `validate-machines.sh` gagne **M11** (le nœud `/<robot>/sono` est dans le graphe vu de
    `monde`) : `attendu` 5 → **6** (M5 et M7-M10 restent réservés à L2c). `test_arborescence.py`
    grave la 5e liste (Dockerfile = `packages` = contextes = montages) et l'hôte `s`.

### Ansible

22. **Pas de rôle `sono`.** « Rôle épuré » (étude §6) = zéro rôle par appareil : un appareil est
    une entrée `machines/<m>/machine.yml` + une ligne d'inventaire. Dans `deploy/hosts` : groupe
    `sono`, hôte `s` (`machine: sono`), enfant de `didier_pi` (utilisateur, clé) — posé en L3b
    sans adresse, `ansible_host` ajouté en L3c (question 2).
23. **Trois généralisations des rôles existants, sans effet sur robot et vision** (gravées par
    `test_arborescence.py`, ajoutées à `VARIABLES_DE_CONTENU` et au tableau de
    `machines/README.md`) :

    | Variable de `machine.yml` | Effet | Robot | Vision | Sono |
    |---|---|---|---|---|
    | `audios_prives: true` | les 3 tâches « audios privés » de `synchronise` et le volet (d) d'`ecart-pi.sh` (remplace `donnees_dir is defined`) ; sans `donnees_dir`, copie aussi le manifeste dans `src/<projet>/medias/audios-prives.json` | vrai (ajouté) | — | vrai |
    | `sha_deploye: true` | écrit `conf/DEPLOY_SHA` (remplace `project_ros_dir == 'robot'`) | vrai (ajouté) | — | vrai |
    | (aucune) | rôle `conteneur` : image du compose absente → `docker compose build` avant le `up` (aujourd'hui un geste à la main sur le Pi) | sans effet (image présente) | idem | construit au 1er déploiement |

24. **`machines/sono/machine.yml`** : `project_ros_dir: sono`, `project_name: sono`,
    `conf_machine_dir`, `packages` (les 4 de la décision 15), `launch_cmd: ros2 launch sono_core
    sono.launch.py`, `sentinelle_build: src/sono_core/change`, `noeuds_attendus: [/didier/sono]`,
    `audios_prives: true`, `sha_deploye: true`, `dossiers_montes: [medias]`, `fichiers_etc`
    (`rpi/asound.conf` → `/etc/asound.conf`, alias par nom de carte lu sur le Pi par `aplay -l`).
    Chemins du Pi : la convention actuelle `~/ros2_ws/src/sono/conf/` (L2e la renommera avec
    les autres ; L3 n'attend pas L2e).
25. **Déployer** : `ansible-playbook -i hosts install-pios-lite.yml -e target_group=sono` (une
    fois), puis `deploy-pios.yml -e target_group=sono`, puis `./ecart-pi.sh sono --graver` et
    `./ecart-pi.sh sono` vert. Aucun geste entre les commandes ; tout geste constaté est une
    dette du playbook, corrigée dans le lot (mémoire « Ansible nickel »).

---

## 3. Cible (vue d'ensemble)

```
                 theatre_contrats/appareils.py : REGISTRE + enveloppe d'état
                          ▲                              ▲
page scène ◄─ pont web ───┘          sono_core ──────────┘──► theatre_gabarit (noeud, pilotes,
 tuile « Appareils »                  logique pure                lancement, essais)
      │  sono/audio, sono/relais ───►  noeud mince ──► PiloteAudio / PiloteRelais
      ◄──────────── sono/etat (latché) ─┘                 sim │ materiel
                                                   (mémoire)  │ (ALSA, PCF8574 0x20)
machines/sono/  ──► Pi « s » (Ansible, pilote materiel)       machines/sim : service `sono` (pilote sim)
```

---

## 4. Épreuve de fumée `sono`

`machines/sim/validate-sono.sh`, exécutée dans `monde`, rclpy seulement (jamais la CLI), refus
hors domaine 43, ligne finale `=== SONO : N OK, K KO`. Audio d'épreuve :
`bugs-joues/begaiement.wav` (2,16 s au manifeste — le pilote sim ne lit que le manifeste, donc
l'épreuve passe sans les medias privés).

| # | Geste | Verdict gravé |
|---|---|---|
| SO1 | lire `sono/etat` (latché) | reçu en ≤ 10 s ; `v` = 1, `appareil` = `sono`, `pilote` = `sim`, audio `""`, `cut_voice` `false`, `refus` `null` |
| SO2 | au repos, compter les états | ≥ 2 en 6 s (battement de 2 s) |
| SO3 | `sono/audio` ← `bugs-joues/begaiement.wav` | en ≤ 2 s : `valeur` = ce chemin, `duree_ms` = 2160, `debut_ms` non nul |
| SO4 | attendre la fin | retour à `""` entre 1,5 et 4 s après SO3 |
| SO5 | rejouer puis `"stop"` à 0,5 s | `""` en ≤ 1 s |
| SO6 | `sono/audio` ← `nexiste/pas.mp3`, puis `../x.wav` | `refus.code` = `audio_inconnu`, puis `chemin_invalide` ; audio resté `""` |
| SO7 | `sono/relais` ← `cut_voice` | `true` en ≤ 1 s, puis `false` entre 0,3 et 1,5 s après |
| SO8 | `sono/relais` ← `klaxon` | `refus.code` = `relais_inconnu` ; `cut_voice` resté `false` |
| SO9 | `diagnostics` | un statut `sono` de niveau OK après un ordre accepté |
| SO10 | WebSocket du pont, pendant une lecture | l'état `sono/etat` reçu par la page porte le chemin ; `scene.html` sert la tuile (id gravé) |
| SO11 | WebSocket, client avec la main : ordre `sono/audio` ; client sans la main : même ordre | le 1er change l'état ; le 2e est refusé, l'état ne change pas |
| SO12 | WebSocket `stop_all` pendant une lecture | audio `""` en ≤ 1 s |

Entrée de `plan.toml`, après `machines` :

```toml
[[epreuve]]
id = "sono"
script = "validate-sono.sh"
attendu = 12           # L3 : SO1-SO12
motif = "=== SONO"
delai_s = 180
sim = { monde = "chantiers" }
chemins = ["packages/sono_core/", "packages/theatre_gabarit/", "machines/sono/", "packages/didier_web/"]
```

Et `machines` : `attendu = 6` (M11). Non bloquante pour la suite (`bloque` absent) : une sono en
défaut n'interdit pas une répétition.

---

## 5. Tests exigés (valeurs gravées)

| Suite | Ce qui est gravé |
|---|---|
| `theatre_contrats/test/test_appareils.py` | le registre entier ; l'enveloppe de la décision 10 au caractère près ; `decoder_etat` sur 6 entrées illisibles → `None` |
| `theatre_gabarit/test/` | inventaire des 4 modules ; `choisir("sim", …, 42)` lève ; battement à 2,0 s (horloge injectée) ; `verifier_appareil` rougit pour chacune des 9 causes de la décision 6 (un cas par cause) ; le squelette généré dans un dossier temporaire a ses tests ROUGES pour les bonnes raisons |
| `sono_core/test/test_logique.py` | les 5 règles de la décision 13, bornes à leur valeur limite (tenue 499 / 500 ms, prolongation, `..`, absolu) ; suite d'actions attendue en littéral |
| `sono_core/test/test_reglages.py` | `machines/sono/sono.yaml` chargé = dictionnaire gravé ; `tenue_ms` 99 et 10 001 refusés |
| `sono_core/test/test_pilotes.py` | sim : fin de lecture à `duree_s` ; matériel : commande exacte lancée (faux exécutable en tête du PATH), SIGTERM puis SIGKILL à 300 ms, PCF8574 absent → `absent` sans exception |
| `sono_core/test/test_contrat_noeud.py` | noms, types, QoS ; liste des `if` du nœud ; launch au namespace absolu |
| `didier_core/test/unit/test_web_protocol.py`, `test_panneau_appareils.py` | whitelists construites du registre ; `stop_all` ; fraîcheur à 4,9 / 5,1 s ; version différente ; textes des lignes |
| `test_arborescence.py`, `test_namespace_contract.py`, `test_fumee_programme.py` | 5e machine, hôte `s`, launch inventorié, `CONTENEURS` à 5, `attendu` 6 et 12 |

---

## 6. Sous-lots — une porte chacun, fusionnés un à un

| Sous-lot | Contenu | Porte | Estimation (agent) |
|---|---|---|---|
| **L3a — contrat, gabarit, socle** | décisions 1-11, 18-19, 21 (liste des conteneurs déduite du compose), 23 ; `nouvel_appareil.py` ; README du gabarit = le mode d'emploi en gestes numérotés (§10) | suites vertes ; mutation ; appareil jetable `essai` généré dans un dossier temporaire : tests rouges = la liste des gestes ; page scène : tuile rendue avec un état factice (capture bureau + téléphone) ; robot redéployé hors robot, `ecart-pi.sh robot` vert (les variables de la décision 23 ne changent rien) | 7-9 h |
| **L3b — la sono, chrono en main** | **session neuve**, brief = le README du gabarit et cette spec §2 (décisions 12-17, 20-22, 24) et §4 ; gestes G1-G10 du §10 | suites vertes ; fumée ciblée `image, demarrage, rtf, machines, sono` verte (RTF ≥ 0,8 à 5 conteneurs) ; séance de 10 minutes de David sur la page scène (jouer, stop, impulsion, STOP) | 4-6 h + 2 fumées ciblées |
| **L3c — sur le Pi `s`** | décision 25, adresse de `s` ; geste G11 ; `attendu/sono.txt` gravé | une commande, `noeuds_attendus` vu, `ecart-pi.sh sono` vert ; page scène du PC : la sono « matériel », son sha égal à celui du dépôt ; si carte son et relais branchés : un audio entendu et le relais entendu claquer, notés « vu sur le Pi », sinon organes `absent` notés tels quels | 1-2 h + construction de l'image sur le Pi + David ≤ 1 h |
| **L3d — bilan** | chrono dépouillé (§10), gabarit corrigé si besoin, `README.md` (carte + table), `packages/README.md`, `machines/README.md`, `docs/interfaces.md`, `docs/operations.md`, `chantiers.md`, étude §6 (ligne L3 : fait) | fumée complète verte après fusion ; critère 1 du §5.0 coché ou écart écrit | 2 h |

**Total ≈ 14-19 h d'agent, 3 à 4 séances.** Incertitude : L3a (la tuile générique et le
programme de fumée à 5 conteneurs touchent du code partagé) ; compter ×1,5 si une épreuve
existante bouge. Modèle : Opus pour les quatre ; aucune relecture Fable requise (ni roues ni
sécurité), une relecture adverse du pont (`stop_all`, whitelists) par Opus à la fin de L3a.

Ordre par rapport au reste : L3 ne dépend ni de L2c (gelé), ni de L2d, ni de L2e. Il passe
après eux dans l'ordre de travail de `chantiers.md` seulement parce que la fiabilité passe avant.

---

## 7. Interdits (tout le lot)

- Toucher à `didier_drive`, `didier_corps_sur`, `twist_mux`, `wheels_*`, `e_stop`.
- Importer `dadou_utils_ros` ou `didier_core` depuis `theatre_gabarit` ou `sono_core`.
- Recopier un fichier de l'archive `dadou_sceno_ros` (code, JSON, compose).
- Un audio dans le dépôt ; un secret ; un chemin absolu de topic ; `git add -A`.
- Lancer ou arrêter la sim sans le verrou `~/tmp/didier/sim-occupee` ; plus d'une sim à la fois.
- Éteindre ou redémarrer un poste depuis un agent.
- Modifier une valeur gravée d'une épreuve existante autre que `machines` (5 → 6).

---

## 8. Hors L3

Volume, fondu, son de fond, listes de lecture ; piste « sono » des séquences et ordres de la
télécommande (L4) ; entendre la sono sur le PC en sim ; DoubleLights et casque (lot optionnel,
L5) ; réécriture d'`audio_node` et `relays_node` du robot sur le même modèle (L5) ; fusion de
`sim/etat/*` dans l'enveloppe (L5) ; renommage des chemins des Pi (L2e) ; image ARM de la sono
sur le Hub (elle est construite sur le Pi).

---

## 9. Replis décidés d'avance

| Si… | Alors |
|---|---|
| RTF < 0,8 avec le 5e conteneur | mesurer le coût du seul service `sono` (arrêté / lancé) ; s'il dépasse 3 % d'un cœur au repos : battement d'état à 5 s et tic à 10 Hz, re-mesurer ; sinon arrêt, rapport |
| `mpg123` ou `aplay` ne sort rien sur la carte du Pi (L3c) | lire `aplay -l`, corriger l'alias de `rpi/asound.conf` ; si la carte est muette avec `speaker-test` aussi : organe `erreur`, porte L3c passée « logiciel du Pi », matériel noté à revoir avec David |
| PCF8574 absent du Pi `s` | attendu : organe `absent`, `diagnostics` ERROR, nœud vivant ; la porte L3c ne l'exige pas |
| L'image ARM ne se construit pas sur le Pi | arrêt, rapport ; ne pas contourner par une image x86 émulée |
| Le pont web sur le robot réel ne doit pas changer avant une séance de David | L3a fusionne quand même (sim) ; le robot n'est redéployé qu'à L3c |
| Chrono > 8 h | §10, règle de correction |

---

## 10. La mesure du « ≤ 1 jour »

**Ce qui est mesuré** : le temps pour ajouter la sono **avec le gabarit déjà fusionné** (L3b +
L3c), par une session qui n'a pas écrit le gabarit. L3a n'est pas dans le chrono : c'est le
prix du gabarit, payé une fois.

**Un jour = 8 h de travail d'agent, plus 1 h de présence de David au maximum.** Les attentes de
machine (construction d'image, fumée, build sur le Pi) sont notées à part et ne comptent pas,
mais sont publiées.

**Relevé** : `docs/seances/<date>-chrono-L3.md`, une ligne par geste, heures prises par
`date -Is` au début et à la fin, commit du geste en regard. Un geste absent du README du
gabarit, ou qu'il a fallu deviner, est noté **« non guidé »** même s'il a été rapide.

| # | Geste (numérotation du README du gabarit) | Budget |
|---|---|---|
| G1 | `nouvel_appareil.py sono` ; tests rouges lus | 10 min |
| G2 | contrat : registre, topics, inventaire gravé | 30 min |
| G3 | `reglages.py` + `sono.yaml` + tests | 30 min |
| G4 | `logique.py` + tests (décision 13) | 90 min |
| G5 | pilotes sim et matériel + tests (essai borné de la décision 17 compris) | 90 min |
| G6 | nœud mince, launch, `test_contrat_noeud.py` | 40 min |
| G7 | README-contrat | 20 min |
| G8 | entrée `machines/sono/` (Dockerfile, compose ARM, script, `machine.yml`), inventaire, CI | 45 min |
| G9 | service de sim + entrée ; la sono visible sur la page scène | 45 min |
| G10 | épreuve `validate-sono.sh` + `plan.toml` ; fumée ciblée verte | 60 min |
| G11 | déploiement sur `s`, `ecart-pi.sh` gravé et vert | 30 min |
| | **Total** | **8 h** |

**Verdict** : tenu si le total ≤ 8 h, David ≤ 1 h, et aucun geste « non guidé ».
**Sinon le gabarit est corrigé** : pour chaque geste au-delà de 1,5 × son budget ou non guidé,
la cause est écrite (une ligne) et corrigée dans le gabarit (README, squelette, bibliothèque ou
`verifier_appareil`) ; ces seuls gestes sont rechronométrés sur l'appareil jetable `essai`
(branche non fusionnée). Le résultat final, tenu ou non, est écrit dans `chantiers.md` et dans
l'étude §5.0 — un dépassement honnête vaut mieux qu'un chrono arrangé.

---

## 11. Questions pour David (défaut appliqué sans réponse)

1. **La sono a-t-elle ses propres ordres, ou double-t-elle le robot ?** Avant, elle écoutait le
   même topic `audio` que le robot. **Défaut : ses propres ordres (`sono/audio`)** — on choisit
   ce qui sort sur la sono, et le robot ne résonne pas dans la façade par accident. Doubler le
   robot plus tard = une piste de séquence, pas un abonnement caché.
2. **Quel Pi est `s`, et qu'a-t-il de branché ?** Il faut son adresse IP, et savoir si la carte
   son et la carte relais (PCF8574 en 0x20) existent encore. **Défaut : un des Pi 4 sains de
   l'atelier, hors scène, sans carte relais** — la porte passe en « logiciel du Pi », le son et
   le relais réels sont vérifiés le jour où le matériel est remonté.
3. **Les 42 audios de l'ancienne sono absents du manifeste** (musiques 23, `didier20` 14, effets
   5), restés dans l'archive locale : les verser dans les medias privés ? **Défaut : non, pas
   dans L3** — la sono joue les 257 audios actuels ; on les verse quand un spectacle en a besoin.
