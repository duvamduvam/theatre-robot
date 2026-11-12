# theatre_contrats — le contrat commun du parc Didier

Ce que deux machines (robot, télécommande, vision, sim, page scène) doivent écrire
**pareil** pour se comprendre : noms de topics, clés de payload, noms d'organes, codec
StringTime, profils QoS. Créé au lot L1a (2026-11-02) pour remplacer
`dadou_utils_ros/utils_static.py` comme source du contrat ; ce dernier n'en est plus
qu'un **shim** qui ré-exporte d'ici (il disparaît au lot L5).

**Python pur, stdlib seulement** : s'importe sur le PC de dev sans ROS (seul `qos.py` utilise rclpy, importé à l'appel — d'où l'unique `exec_depend`). C'est un package
ament_python pour que colcon l'installe dans chaque conteneur (sim, robot, vision,
télécommande) — `dadou_utils_ros/utils_static.py` l'importe, donc **tout conteneur qui
embarque la lib doit avoir ce package dans son `src/`**.

## Ce que chaque module expose

| Module | Contenu | Règle |
|---|---|---|
| `organs.py` | les 10 organes de Didier (`FACE`, `NECK`, `LEFT_ARM`…, tuple `ORGANS`) | critère : topic consommé par un node actionneur du robot ; chaque nom est aussi topic, piste de séquence et clé de payload |
| `topics.py` | tous les noms de topics : organes (ré-exportés), `ANIMATION`, `ANIMATION_STATE`, `EXPRESSION`, `LIGHTS`, `SPEAK`, `SYSTEM`, `VISION_PERSON`, `VISION_PERSON_BOX`, `VISION_STATUS`, ceux du sélecteur de jeu (lot A1) `JEU_CONSOLE`, `JEU_INTENTION`, `JEU_CHAT_MOVE`, `JEU_JOURNAL`, du catalogue (L1c) `CATALOGUE`, `DEPLOY_SHA`, et de l'édition (L1d) `DATA_EDIT`, `DATA_EDIT_RESULT` | **relatifs**, jamais de `/` initial (namespace par robot au lot L1b) |
| `keys.py` | clés et valeurs de payload (`DURATION`, `KEYS`, `MODE`, `JOYSTICK`…) | valeurs de fil reprises à l'identique, incohérences historiques comprises (`UP = "UP"`) |
| `stringtime.py` | `decode(ros_msg, topic)` / `decode_payload(raw, topic)` **stricts** (invalide → `None` + log ERROR) ; `decode_or_raw(raw, topic="")` **tolérant** (invalide → la chaîne brute, log DEBUG) ; `loads(raw)` nu (lève comme `json.loads`) ; `encode(value, time_ms=0, anim=False, msg_type=None)` | chaque site d'appel garde SA variante — voir la docstring du module |
| `qos.py` | `volatile(depth=10)`, `latched()` (TRANSIENT_LOCAL, depth 1) | rclpy importé à l'appel ; latché = des DEUX côtés |
| `donnees.py` | **lot L1d** : le contrat des DONNÉES du robot — `nom_valide`, `charger_references`, `verifier_sequence` (bornes roues comprises : consigne ≤ `VITESSE_ROUES_MAX` 0.89, tenue ≤ 60 000 ms, durée ≤ 300 000 ms, arrêt final `[0, 0]`), `verifier_expression`, `verifier_lumiere`, `verifier_brique`, `verifier_image` (PNG strict), `poser_entree`, empreintes (`empreinte_contenu`, `empreinte_roues`), lecture du registre `json/validations-sim.json` (`a_rejouer`, `roues_a_valider`, `roues_validees`), `verdict_a_recharger` | stdlib seule ; chaque `verifier_*` rend TOUTES les erreurs (liste vide = conforme) ; lu par les tests de `data/` ET par l'écrivain du robot — une règle se change ICI, jamais dans un test |

Ce qui n'est **pas** ici et reste dans `utils_static.py` jusqu'à L5 : chemins et
répertoires, logging, plateforme (`RPI_TYPE`, `SERIAL_ID`, `MSG_SIZE`), couleurs
(`ORANGE`), constantes internes à `dadou_utils_ros`.

## Règle : ce qui est physique est typé (décidée le 2026-11-11)

`StringTime` (du JSON dans une chaîne) est réservé aux **ordres de jeu** : animation, visage,
son, lumières, consignes de parole, états de séance. **Toute grandeur physique ou perçue
voyage dans un message ROS standard typé** — `Twist`, `LaserScan`, `Odometry`, `JointState`,
`PointStamped`, `DiagnosticArray`… — jamais dans un nouveau payload JSON. Pourquoi : le
middleware et les outils (enregistrement, tracé, moniteur de collision) ne comprennent que
les types ; un nombre caché dans une chaîne ne se trace pas et ne se vérifie pas.

Corollaire pour la santé du matériel : les prochains signaux (batterie, lidar, odométrie)
vont sur `diagnostics` (`diagnostic_msgs`), pas dans de nouveaux champs de `HardwareStatus`.
Les topics existants ne sont pas réécrits. Origine : `docs/etudes/etude-standards-robotique.md` §6.2.

## Tester

```bash
# depuis la racine du mono-dépôt (n'importe quel python avec pytest) :
.venv/bin/python -m pytest packages/theatre_contrats/test -q
# recompter qui importe quoi (AST, imports multi-lignes compris — un grep se trompe) :
python3 packages/theatre_contrats/tools/inventaire.py
```

Les tests gravent les valeurs **en dur** (`test_inventaire.py` : la liste complète de ce
qui est repris ; `test_stringtime.py` : les sorties du codec, cas invalides compris) :
ajouter ou changer un nom du contrat exige de toucher le test. Les tests de contrat des
consommateurs (`test_contrat_utils.py` côté robot, `test_utils_static_contract.py` côté
télécommande) continuent de figer les mêmes valeurs à travers le shim.
