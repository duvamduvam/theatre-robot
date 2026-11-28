# didier_jeu — le sélecteur de jeu de Didier (lot A1, SIM-ONLY)

Ce package répond à « pourquoi et quand Didier agit » : un **arbre py_trees**
décide de ce qui est permis, et un **score** choisit l'action. Les offres, les
pistes de personnes et les pulsions alimentent ce choix ; chaque décision est
journalisée avec son `pourquoi`. Spec :
`docs/spec-A1-selecteur-de-jeu.md` (décisions §8 du 02/11), **révisée par
`docs/spec-S1-ordres-propositions.md`** (lot S1, 25/11 : ordres et propositions,
verrou de David seul, une seule reprise), **puis par `docs/spec-S2-le-corps-raconte.md`**
(lot S2a, 27/11 : le sélecteur écrit `corps/etat` et répond à toute demande de David) ; le pourquoi se trouve dans
`docs/etude-autonomie-improvisation.md` §4.1-4.2 et `docs/etudes/etude-assainissement.md` §4.

**SIM-ONLY** : `jeu_node` refuse de démarrer hors `ROS_DOMAIN_ID=43`. Il utilise
le garde-fou `check_domain` de `didier_rehearsal`, importé tel quel ; son message
d'erreur dit donc « didier_rehearsal refuse de démarrer », ce qui est connu. Le
refus a lieu **avant** `rclpy.init`. **Aucun Twist** : les roues ne bougent que
par des demandes au régisseur (`jeu/chat_move`), qui les arbitre, puis par
`route_driver`.

## Le contrat

| Topic | Sens | Format |
|---|---|---|
| `jeu/console` | page scène → sélecteur | StringTime JSON `{"cmd": "va_la"\|"joue_avec"\|"ignore"\|"reviens"\|"plus_lent"\|"stop"\|"go", "cible"?, "presence": true}` ; la page envoie `{"presence": true}` à 2 Hz (battement) |
| `jeu/intention` | sélecteur → page | **latché**, republié toutes les 0,5 s : `{"action", "cible", "pourquoi", "t_ms", "fin_prevue_ms", "reste_ms", "verrou", "jauges", "proposition"?}` ; `"action": "rien"` au repos, jamais vide |
| `jeu/chat_move` | sélecteur → régisseur | même contrat que `rehearsal/chat_move` (lot S1) : marche `{"cmd": "stop"\|"go", "origine": "david"\|"didier"}`, geste avec son `origine` ; les reprises et lubies du sélecteur sont `didier`, ce qui vient de David garde `david`. Le régisseur y est remappé par `rehearsal.launch.py jeu:=true` |
| `rehearsal/chat_move_reply` | sélecteur → chat_node (et régisseur → tous) | `{"demande", "effect", "reason", "source": "jeu"}` : depuis le lot S2a, une réponse à **TOUTE** demande d'origine `david` de la bouche — go, stop, pause, gestes : `accepted` (relayée ; un geste : transmis, réponse partie AVANT lui, donc avant le verdict du régisseur) ou `dropped` + code (`arrete` avec `"verrou"`: `console`\|`route`\|`voix`, `sans_superviseur`, `pas_ici`, `hors_atteinte`, `corps_sur`) ; un stop n'est jamais refusé et sa réponse part APRÈS lui. Aussi : `pas_retenu` (proposition de geste d'origine `didier`, seule demande `didier` qui a une réponse), `degrade` (mode dégradé, gestes seulement), `no_reply` (régisseur muet 3 s). Le sélecteur écoute aussi les réponses `source: "director"` : `accepted` accuse l'étape, un refus finit l'engagement tout de suite (15/11) |
| `corps/etat` | sélecteur → page scène (S2b : bouche, réflexion) | **latché**, profondeur 1 : l'état du corps (`theatre_contrats.corps_etat`, spec-S2 §2) — `marche`, UNE `cause`, `qui_relance`, `repart_dans_s`, `geste`, `ici`, `phrase` (≤ 300 car.). Republié à chaque changement et au plus tard toutes les 2 s (`Selecteur.rafraichir_corps`, appelé par le node avant chaque vidage) ; rien en mode dégradé |
| `jeu/journal` | sélecteur → page (+ fichier) | une ligne JSONL (format boîte noire `robot.diagnostic.journal`) par message |
| `animation` | sélecteur → animations_node | nom de séquence (JSON chaîne) |
| `look` | sélecteur → gaze_follower | `{"angle_deg", "hold_ms"}` (« regarder », spec-aller-voir §7.1) |
| entrées | | `vision/person_box`, `rehearsal/poi_event`, `rehearsal/chat_move` (la bouche, lue par `didier_rehearsal.contracts.lire_chat_move` : anciennes formes = `david`), `chat_transcript` (rôle `david` = parole entendue), `route_state`, `route_state_cause`, `route_goto_result`, `rehearsal/chat_move_reply`, `animation_state`, `scene/objets` (le tableau des objets, latché, lot O1 — remplace `rehearsal/objects` et la pose vérité terrain), `rehearsal/state` (latché : séance et arrêt vocal), `corps_sur/etat` (latché, lot S2a) |

Les noms `jeu/*` sont définis dans `theatre_contrats.topics`. Ceux du régisseur
viennent de `didier_rehearsal.contracts`, qui est importé et non recopié.

## Bugs joués (lot I0, 22/11)

Étude : `docs/etudes/etude-improvisation.md` §2. Un bug joué est une séquence de
`data/json/sequences/bugs-joues/` (type `bug-joue`), jugée par `theatre_contrats.bugs_joues`
(ni `wheels` ni `relay`, ≤ 15 s, sons ≤ 4 s lus au manifeste, classe V ou M, `desc`,
`direction` facultative, repos du visage et des lumières rétabli).

- `repertoire.candidates()` les EXCLUT (dossier et type) : le sélecteur ne les joue pas encore.
- `repertoire.bugs_joues(sequences_dir)` rend l'inventaire (acceptés, refusés avec raisons) ;
  `jeu_node` le journalise au démarrage (`bugs_joues`, `bugs_refuses` de la ligne `demarrage`).
  L'emploi `bug` (annonce, réfractaires, rétablissement, coupures) est le lot I1.
- Au 22/11 : les 6 bugs de classe V de l'étude §2.2 ; les 2 de classe M attendent le
  protocole caméra (I5). Jeu manuel : groupe « Bugs joués » de la page scène.
- **Sons** (`bugs-joues/begaiement.wav`, `bips-mise-a-jour.wav`, `demarrage.wav`) : synthèse,
  dans les AUDIOS PRIVÉS (jamais dans le dépôt). Les refaire :

  ```bash
  docker run --rm --user $(id -u):$(id -g) -v $PWD/packages/didier_jeu/tools:/outil:ro \
    -v ~/Nextcloud/dev/didier/medias-prives/audios/bugs-joues:/sortie --entrypoint python3 \
    didier-sim/vision:local -I /outil/sons_bugs_joues.py /sortie \
    --voix /home/ros2_ws/src/vision/medias/voices/didier.onnx
  PYTHONPATH=packages/theatre_contrats python3 -m theatre_contrats.donnees manifeste-audios data
  ```

  La voix (Piper `fr_FR-siwis-medium`) est dans l'image de la vision ; bips et démarrage sont en
  stdlib. Déterministe : mêmes octets à chaque fabrication. En sim, aucun son n'est audible
  (`audio_node` sans carte son) : les écouter directement.
- Tests : `test/test_repertoire.py` (exclusion, inventaire réel, séquence piégée refusée) ;
  garanties gravées une par une dans `packages/theatre_contrats/test/test_bugs_joues.py`.

## Ce qui décide (dans l'ordre de l'arbre)

1. **Arrêt vocal** : un `stop`, quelle que soit son origine, est **relayé dès
   sa réception, sans passer par le score** — un arrêt n'est jamais refusé.
   **Origine `david`** (mot d'arrêt, console, STOP CONTENUS de la page) : il pose
   le **verrou de David**, seul verrou qui existe (lot S1 ; supprimé : le verrou à
   deux sources console/bouche), à **trois genres** (R3, 25-26/11) : `console`
   (STOP de la console), levé par un GO de la console **seulement** ; `route`
   (Route OFF par David — `route_state_cause = cmd`), levé quand la route revient à
   `on` (ou par un GO console), jamais par un go vocal ; `voix` (mot d'arrêt), levé
   aussi par un `go` de David en tour humain. Un ordre de David suspendu par un stop
   de Didier n'est rejoué que s'il vise un objet (`aller_voir`, `tour_de` ; jamais
   `avancer`/`tourner`), a moins de 60 s, passe les contrôles d'un ordre neuf, et
   qu'aucun nouvel ordre de David n'est venu entre-temps. Un ordre console identique
   reçu dans la seconde est ignoré ; « reviens » pendant une manœuvre l'annule d'abord
   (`stop`) et ne relance qu'une fois l'annulation vue. **Origine `didier`** (le `marche: stop` du LLM, en tour
   humain ou en continuation) : il arrête, **sans verrou**, et la reprise s'arme ;
   pendant un geste de David, l'ordre est **suspendu** puis ré-émis à la reprise
   (R4). Un `go` d'origine `didier` est ignoré et journalisé. Il n'y a jamais de
   `go` automatique après un stop de David.
2. **Superviseur absent** (mode `exigeant` seulement ; le défaut en A1 est `suppose`) :
   aucun déplacement.
3. **Ordres de la console** (hors de l'arbre depuis R6, 26/11 : ils partent au
   prochain tick, avant toute initiative, sans score ni écart de 2 s ; plus de
   branche `ordre_macro` ni d'expiration « pas faisable en 10 s ») :
   `va_la` vise un objet du tableau `scene/objets` (→ `aller_voir` avec son `id`)
   ou une piste (→ `tourner` vers elle, puis `avancer` 1 m). `joue_avec` vise la
   piste regardée, approches répétées permises. `ignore` coupe les offres de
   la cible pendant 30 s et annule une lubie en attente ou une reprise.
   `reviens` envoie `go`. `plus_lent` = **moins souvent** (décision de David du
   02/11) : toutes les périodes réfractaires sont multipliées par 2 pendant 60 s.
   Ce n'est pas une vitesse de roues : le sélecteur n'en a aucune.
   **Garde de distance** de toute approche : jamais si la hauteur de boîte de
   la piste atteint `approche.hauteur_max` (0,55, soit environ 2,7 m).
4. **Action engagée** : elle se finit. Seule une offre de valeur ≥ 0,9 peut
   l'interrompre — il n'y en a plus depuis le lot S1 — et **jamais** un ordre
   de David engagé.
5. **Choisir** : le score de chaque candidat (immobilité comprise), puis
   l'hystérésis (+15 % pendant 300 ms), et jamais deux changements à moins de 2 s.
   **Hors séance** (`rehearsal/state` ≠ `en_cours`, ou jamais reçu — R2) : aucune
   initiative de mouvement (ni lubie, ni approche de son initiative ; « joue avec »
   reste permis), ni reprise après un geste de David.

**Lubie** : un `poi_event enter` fait naître une offre `objet`. Didier réclame
l'arrêt (par l'intention) **et** l'amorce (`look` vers l'objet, angle calculé
depuis l'odométrie vérité terrain, donc SIM-ONLY ; à défaut de pose, il s'en
tient à l'intention). Il ne demande `stop` que si la console n'a dit ni `ignore`
ni `va_la` dans les 3 s. Il propose ensuite « repartir ? » et repart de lui-même
par **la reprise** (ci-dessous).

**Une seule reprise** (lot S1, 25/11 ; remplace les trois minuteries 90 s / 10 s /
6 s) : après un arrêt décidé par Didier — lubie, `stop` d'origine `didier`, pause
« regarde ça », fin (réussie ou non) d'un geste de la bouche ou de son propre
déplacement — il envoie `go` (origine `didier`) après **D s de silence**, D tiré au
moment de l'arrêt dans `[reprise.min_s, reprise.max_s]` = **[10, 40] s** par le
générateur semé du sélecteur (paramètre `graine` de `jeu_node`, journalisée au
démarrage ; ligne `reprise_armee` : « il repartira après 23,4 s de silence »). Toute
parole entendue (`chat_transcript`, rôle `david`) remet le silence à zéro sans
retirer le tirage (02/11). Elle attend qu'aucun déplacement ne roule ; un stop de
David, une Route OFF, un `ignore` ou un `go` de David l'annulent. L'humeur qui
choisira D viendra avec le régisseur LLM (S4). Tests :
`test/test_ordres_propositions.py`.

**Un arrêt de Didier par 2 min** couvre tout arrêt de route qu'il cause : lubie,
approche de sa propre initiative. Un ordre de David n'en est jamais un, et
**une demande de geste de la bouche non plus** (décision de David du 15/11 :
elle vient toujours d'un humain, donc une tâche peut enchaîner ses gestes).

**Un ordre de David n'est refusé que pour trois raisons** (lot S1, étude
assainissement règle 1) : verrou de David (`arrete`), sécurité (dite par le
régisseur et le corps sûr ; `sans_superviseur` ici) et impossible (`pas_ici`,
`hors_atteinte` ; objet inconnu : le régisseur). Un geste de la bouche d'origine
`david` (tour humain ou continuation de SA tâche) part **à la réception**, sans
score ni hystérésis (journal `ordre`) ; un ordre de la console part au prochain tick,
de même (R6). Ni fatigue ni réfractaire ne les arrêtent. Fatigue et réfractaires bornent les
seules initiatives de Didier. Les refus « qui donnent du jeu » (étude §8.1,
réponse 2) ne sont PAS là : ils viendront avec le régisseur LLM (S4).

**« Regarde ça »** (lot « texte raccord », séance du 18/11 21:35) : la bouche envoie la pause
(`{"cmd": "pause", "origine": "david"}`) sur `rehearsal/chat_move`. Didier en marche : `stop`
relayé tout de suite, d'origine `didier` (c'est lui qui le relancera), **sans verrou**, puis la reprise (journal
`pause_regard` puis `reprise`). Déjà arrêté (verrou, reprise armée) ou pas en route : rien ne
bouge, jamais de `go` qu'il n'aurait pas eu sans elle. Dans les trois cas, le sélecteur publie
lui-même un `look` devant (angle 0, `durees_s.regarder`) dans le même tick (fumée du 28/11 : le
regard ne venait que de la bouche, au gré du LLM). Mode dégradé : un `stop`. Tests :
`test/test_pause_regard.py`.

**Objets** (lot O1, 18/11 ; remplace les « distances » du 15/11) : le sélecteur LIT le
tableau des objets `scene/objets` (écrit par `didier_perception`) ; il n'a plus ni pose ni
carte. Un `aller_voir` ou `tour_de` de la bouche dont l'objet (désigné par son `id`) n'est
pas `atteignable` est refusé tout de suite : réponse `dropped` / `pas_ici` (ni en vue ni à
portée) ou `hors_atteinte` (en vue mais trop loin), avec `distance_m` et `cote`. `va_la`
résout le nom dans le tableau et l'ordre porte l'`id` ; la console n'est pas soumise à
`atteignable` (la régie garde ses 40 m). Le regard d'une lubie vise l'azimut du tableau.
Le tableau est PÉRIMÉ après `theatre_contrats.objets.PEREMPTION_S` (3 s) sans republication
(`Selecteur.tableau(now)`, revue O1 du 19/11) : ni regard ni « va là » sur une donnée figée ;
l'oubli et le retour sont journalisés (type `tableau`).

**Réponse à la bouche** (15/11, séance « fais le tour de l'éléphant ») : toute
demande de GESTE de la bouche a une issue que le chat apprend. Transmise, le
sélecteur répond `accepted` (lot S2a) et le régisseur rend son verdict. Non transmise (offre morte au bout de ses 3 s), une
ligne `refus` dit pourquoi et `rehearsal/chat_move_reply` porte `dropped` + le
code. Sinon Didier affirmait un geste qui n'avait pas eu lieu. Un déplacement
**refusé** par le régisseur, ou resté sans réponse, n'a pas eu lieu : ses
périodes réfractaires et sa fatigue sont **rendues**. Une nouvelle demande de la
bouche interrompt celle en cours, même sur le même objet (le plus récent ordre de
David gagne). Seule l'issue de l'ordre accepté (`name` de la réponse du régisseur)
finit l'étape ; les autres sont journalisées `issue_ignoree`.

**L'état du corps** (lot S2a, 27/11, spec-S2 §2) : le sélecteur est le SEUL écrivain de
`corps/etat`. Il rassemble les faits (`route_state`, `corps_sur/etat`, `rehearsal/state` et son
arrêt vocal, genre du verrou, cause de la reprise armée, dernier geste, tableau des objets) ; la
règle — priorité corps sûr > verrou de David > geste en cours > reprise > hors séance > en
route — et la phrase sont dans `theatre_contrats.corps_etat` (pur, textes gravés). Une source
jamais reçue ou illisible : état INCONNU (« Tu ne sais pas où en est ton corps. »). Chaque
changement de `marche` ou de `cause` est une ligne `corps_etat` du journal, dont le `pourquoi`
est la phrase. Corps sûr VERROUILLÉ (ou en démarrage) : un go ou un geste de David est refusé
`corps_sur`, ni relayé ni transmis (un go relayé lèverait l'arrêt de David pour un départ
surprise au réarmement) ; pas en zone ARRET (un pivot pour se dégager doit rester possible).
Hors séance, un ordre de David part toujours (S1, R1/R5) : le sélecteur ne répond jamais
`hors_seance`. Tests : `test/test_corps_etat_jeu.py`.

**Metteur en scène** : plus de mots-clés depuis le lot S1 (`sur_situation`,
l'indication de `mission_state` et `metteur_en_scene.*` supprimés — « fragiles,
sans identifiant ni retour », étude improvisation) ; `jeu/proposition` les
remplacera (I3).

Chaque offre née, personne ou objet, reçoit en ≤ 1 s une ligne de décision :
un choix, ou un « il continue … : » qui dit pourquoi il ne réagit pas.

**Répertoire** : les séquences qui ont une clé `types`, **sauf** celles de `bugs/`
et **sauf toute séquence à piste `wheels`** (A1 n'a pas de corps sûr). Les types
`bonjour` donnent un « accueil » (réponse à une personne) ; `random` et `little
move` donnent une expression spontanée (servie par l'ennui). Les déplacements
sont dans `config/deplacements.yaml` ; `reculer` en est absent, car le régisseur
refuse tout `avancer` négatif. Deux séquences du même nom dont l'une est jouable
sont refusées au chargement ; des homonymes sans emploi sont seulement listés.

**Journal** : les phrases sont écrites pour David (`phrases.py`), par exemple
« il s'ennuie (0,40) → une expression spontanée « aurore » ». Pulsions et offres
sont photographiées à l'instant du choix. Une ligne sans `pourquoi` n'est jamais
perdue : elle part avec « (absent — bug) » et un compteur.

**Mode dégradé** (`relais.RelaisSeul`) : si le répertoire, les réglages ou le
vocabulaire sont illisibles, `jeu_node` démarre quand même. Il relaie alors
`stop`/`go` (bouche et console) sans aucune initiative et écrit `degrade` au
journal, avec les mêmes règles d'origine : verrou de David seul, `go` de Didier
ignoré, `stop` de Didier relayé sans verrou **ni reprise** (sens sûr : il reste
arrêté jusqu'à un `go` de David). Le chemin d'arrêt vocal ne dépend jamais d'un JSON.

Tous les chiffres sont dans `config/reglages.yaml` (« réglage de départ, se
règle au journal »), et **gravés** dans `test/test_reglages.py`.

## Lancer (conteneur sim)

```bash
ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true
```

Ce launch démarre **lui-même** `jeu_node` (respawn), sous la même condition que
le remap de la bouche. Il ne faut jamais le lancer à part : un remap sans relais
perdrait le `stop` de la bouche.

Namespace (lot L1b) : `jeu_node` vit sous `/<ROBOT_NAME>/` (défaut `/didier/`),
posé par le launch — ses topics sont `/didier/jeu/intention`, `/didier/jeu/console`…
À la CLI, toujours préfixer (`ros2 topic echo /didier/jeu/journal`).

Le journal est écrit dans `/home/ros2_ws/log/jeu/<horodatage>_<pid>_jeu.jsonl`.
Vérification rejouable : `validate-jeu-a1.sh` (voir `docs/operations.md`).

## Tester

```bash
.venv/bin/python -m pytest packages/didier_jeu/test -q
```

Chaque règle chiffrée est testée avec une valeur écrite en dur, et accompagnée
d'un test de **mutation** : la même scène, rejouée avec le réglage cassé, doit
violer la règle. Les mutations du code faites le 02/11 rougissent toutes (voir
le message du commit).
