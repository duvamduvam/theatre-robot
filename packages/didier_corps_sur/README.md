# didier_corps_sur — le corps sûr de Didier (lot A0)

Filtre déterministe placé AVANT `twist_mux` sur les trois entrées autonomes des
roues (`cmd_vel_anim`, `cmd_vel_follow`, `cmd_vel_web`). Il met zéro dès qu'un
obstacle est à moins de 0,6 m de la caisse ; entre 0,6 et 1,2 m, il ralentit
par palier. Il met zéro **et se verrouille** si le lidar se tait, si le
superviseur disparaît ou si `e_stop` tombe. Il refuse tout mouvement vers ce
que le lidar ne voit pas. La télécommande (`cmd_vel_remote`, prio 100) n'y
passe pas. Spec FERMÉE : `docs/spec-A0-corps-sur.md`.

**État (A0-4, 20/11)** : logique pure (A0-3) + le nœud `corps_sur_node`, EN LIGNE devant
`twist_mux` (lancé par `didier_drive/launch/drive.launch.py`, `respawn` faux), les contrats de
topics (`theatre_contrats.topics`) et les 25 épreuves de sim CS1-CS13
(`machines/sim/validate-corps-sur.sh`, phase `corps_sur` de la fumée, rouge bloquant). Le package
est dans la liste `packages:` du robot (`machines/robot/machine.yml`) : le PROCHAIN déploiement
du Pi le portera. Reste à A0-6 : le pilote du lidar dans l'image, `lidar_node` dans
`robot_app.launch.py`, la règle udev, la preuve à blanc sur le Pi hors robot.

```
télécommande ─ wheels ─► wheels_bridge ─► cmd_vel_remote ───────────────────── (prio 100) ─┐
séquences ──────────────────────────────► cmd_vel_anim ───┐                                 ▼
suivi, route ───────────────────────────► cmd_vel_follow ─┼─► corps_sur ─► cmd_vel_*_sur ─► twist_mux ─► cmd_vel_mux ─► twist_deadman ─► cmd_vel
pont web ───────────────────────────────► cmd_vel_web ────┘      ▲   (anim 10, follow 20, web 50)      ▲ e_stop (255)
                       scan, e_stop, superviseur/battement, corps_sur/rearmer ──┘ ─► corps_sur/etat (latché), diagnostics
```

⚠️ **Sur le robot, tant que le lidar n'est pas monté** : `corps_sur` reste en DEMARRAGE
« capteur_absent » ; AUCUNE source autonome (séquences à piste roues, suivi, route, web) ne fait
tourner les roues ; la télécommande conduit comme avant (spec §14).

## Le contrat des modules (stdlib seule, PyYAML dans `reglages` ; ni rclpy ni numpy)

Toute horloge est passée en argument (secondes, float), comme dans `TwistDeadman`.

| Module | Rôle | API |
|---|---|---|
| `geometrie` | caisse, pose du lidar, distance à la caisse, invariant du pivot | `Caisse(x_avant, x_arriere, demi_largeur, x_essieu, rayon_balayage)` (sans argument = défauts §4.1), `PoseLidar(x, y, lacet_rad)`, `distance_caisse(caisse, x, y)`, `point_dans_base(pose, angle_rad, r)`, `points_dans_base(pose, angle_min, increment, distances)` (saute les non finis), `ecart_pivot(caisse)`, `invariant_pivot(caisse, marge_arret_m) → (ok, ecart)` |
| `balayage` | validité des points et d'un balayage, masques, témoin | `lire_balayage(params, caisse, pose, stamp_s, stamp_precedent_s, maintenant_s, angle_min, increment, distances) → Lecture(motifs, d_min_m, retour_dans_caisse, rayons, points_valides, temoin_points)`, `.valide` ; `dans_arc`, `dans_masque` |
| `couverture` | régions vues / aveugles | `calculer_couverture(caisse, pose, masques_deg, marge_arret_m=0.60, pas_m=0.05, part_aveugle_max=0.10) → {"avant"\|"arriere"\|"flanc_g"\|"flanc_d": {"part_aveugle", "vue", "echantillons", "aveugles"}}` (JSON tel quel) ; `vue_de(couv) → {région: bool}` |
| `zones` | LIBRE / RALENTI / ARRET, hystérésis | `Zones(ParametresZones(...)).observer(d_min, valide=True) → zone` |
| `garde` | DEMARRAGE / ARME / VERROU, péremptions, réarmement, durée bornée | `Garde(ParametresGarde(...))` : `balayage_valide(t)`, `battement(t)`, `noter_e_stop(v, t)`, `tic(t)`, `rearmer(t) → (accepté, raison)`, `noter_entree(canal, t, nulle)`, `noter_sortie(canal, t, nulle)`, `pause_duree`, `superviseur_etat(t)`, `etat`, `cause` |
| `filtre` | transformation d'une consigne (§5.3) | `filtrer(v, w, canal, EtatFiltre(etat, zone, pause_duree, vue), ParametresFiltre(...)) → (v', w', motif)` |
| `reglages` | YAML + bornes dures | `charger_reglages(chemin, ros_domain_id) → Reglages`, `reglages_depuis(dict, ros_domain_id)` ; refus = `ReglagesError` |
| `moteur` (A0-4) | le corps sûr ASSEMBLÉ : séquence des appels, zéro anticipé, état, diagnostics | `CorpsSur(reglages)` : `balayage(t, stamp, angle_min, increment, ranges)`, `consigne(canal, t, v, w)`, `e_stop(v, t)`, `battement(t)`, `tic(t)` → `[Sortie(canal, v, w, motif)]` à publier DANS L'ORDRE ; `rearmer(t) → (accepté, raison)` ; `etat(t)`, `etat_json(t)`, `diagnostic(t, duree_rappel_s) → Diagnostic(niveau, message, valeurs)` ; `vue`, `couverture` |
| `contrat` (A0-4) | noms, types, QoS du nœud (§3.2) | `ENTREES`, `SORTIES`, `SCAN`, `E_STOP`, `BATTEMENT`, `REARMER`, `ETAT`, `DIAGNOSTICS`, `TYPES`, `QOS`, `NOM_NOEUD`, `CONFIG_DEFAUT` |

Le nœud `corps_sur_node` (rclpy) n'a aucune règle : chaque message devient un appel à `CorpsSur`,
chaque `Sortie` un `Twist` (les quatre composantes non lues restent à zéro). Configuration absente
ou refusée : message lisible et sortie (code 2), RIEN n'est publié. Exception pendant un rappel :
zéro sur les trois sorties, puis sortie (code 1). Gravé par `test/test_contrat_node.py` (noms,
types, QoS, liste des `if` du nœud, insertion dans `drive.launch.py` et `twist_mux.yaml`).

| Topic (relatif, sous `/<ROBOT_NAME>/`) | Type | Sens | QoS |
|---|---|---|---|
| `scan` | `sensor_msgs/LaserScan` | entrée | best effort, 1 |
| `cmd_vel_anim`, `cmd_vel_follow`, `cmd_vel_web` | `geometry_msgs/Twist` | entrée (demandes) | fiable, 1 |
| `cmd_vel_anim_sur`, `cmd_vel_follow_sur`, `cmd_vel_web_sur` | `geometry_msgs/Twist` | sortie (vers `twist_mux`) | fiable, 10 |
| `e_stop` | `std_msgs/Bool` | entrée | fiable, 10 |
| `superviseur/battement` | `std_msgs/Empty` | entrée | best effort, 1 |
| `corps_sur/rearmer` | `std_msgs/Empty` | entrée | fiable, 10 |
| `corps_sur/etat` | `theatre_interfaces/StringTime` (JSON §5.7) | sortie, à chaque changement | latché (`qos.latched()`) |
| `diagnostics` | `diagnostic_msgs/DiagnosticArray` | sortie, 1 Hz | fiable, 10 |

Réarmer à la main (sim) : `ros2 topic pub --once /didier/corps_sur/rearmer std_msgs/msg/Empty "{}"` ;
lire l'état : `ros2 topic echo --qos-durability transient_local --qos-reliability reliable
/didier/corps_sur/etat theatre_interfaces/msg/StringTime`.

### Conventions écrites ici (la spec les laisse ouvertes)

- **Masques** : dans `laser_frame`, en degrés, sens trigonométrique. Un masque
  `[debut, fin]` couvre l'arc parcouru de `debut` à `fin` dans le sens CROISSANT,
  bornes comprises, angles pris modulo 360. Ainsi `[90, 270]` et `[100, -100]`
  désignent l'arrière (l'arc passe par 180°), et `[350, 10]` comme `[-10, 10]`
  désignent ±10° autour de l'avant. `[270, 90]` désigne l'avant : l'ordre compte.
  Un arc de 360° ou plus couvre tout le tour.
- **Couverture** : grille aux centres des cases (`(i + ½)·pas`), bande `0 < d < marge`.
  Les coins arrondis appartiennent à AVANT et ARRIERE (x > x_avant, x < x_arriere) ;
  les flancs sont la bande le long de la caisse. Seuls les masques rendent
  aveugle : la portée minimale et l'ombre du corps ne sont pas modélisées, et
  c'est l'ombre que les masques mesurés recouvrent.
- **Zones** : un balayage invalide peut faire ENTRER en ARRET mais ne compte jamais pour
  en sortir. Avant le premier balayage, la zone vaut ARRET.
- **Garde** : le réarmement exige qu'AUCUNE cause ne soit présente, pas seulement la
  cause du verrou. En DEMARRAGE, la cause publiée est `sante_en_cours` tant que le
  capteur est sain depuis moins de `sante_s`. PAUSE_DUREE est un drapeau ; l'état
  reste ARME.
- **Filtre** : le tour toléré est plafonné à `min(w_max du canal, w_max_aveugle)`.
  La pause durée met zéro, avec le motif `PAUSE_DUREE`.
- **Moteur (A0-4)** : le zéro anticipé part au PASSAGE en blocage (état autre que ARME, zone
  ARRET ou pause de durée), sur chaque canal ayant reçu une demande depuis moins de **1,0 s** —
  le double du délai du mux (0,5 s) : à la frontière, un zéro de trop ne peut que masquer une
  source plus basse, jamais la télécommande. Blocage né pendant une demande : les AUTRES canaux
  actifs reçoivent leur zéro avant la sortie (nulle) de la demande. L'horodatage du balayage
  précédent ne fait que croître : un `stamp` qui recule invalide les balayages (capteur perdu,
  verrou). Diagnostics : ERROR en VERROU, WARN en DEMARRAGE et, sur `terrain: reel`, tant que le
  superviseur ou le témoin ne sont pas exigés.

## Configuration

Chaque machine a SA configuration, gravée par `test/test_configs_machines.py` :
`machines/sim/robot/corps_sur.yaml` (colonne « sim » du §5.4 ; refusée hors domaine 43 ;
`angulaire_aveugle_autorise` vrai, décision du 18/11) et `machines/robot/corps_sur.yaml` (colonne
« robot » ; `angulaire_aveugle_autorise` FAUX, superviseur non exigé tant que le battement
n'existe pas, durée bornée 4 s). Le fichier ci-dessous reste la référence du package.

`config/corps_sur.yaml` : défauts SÛRS du package (`terrain: reel`, superviseur
exigé, angulaire aveugle refusé, pose A face avant 0,33 ; 0, plan à 0,25 m).
Masque PROVISOIRE `[90, 270]` jusqu'à la mesure (`mesurer_masques`, A0-7) :
la couverture n'annonce alors que l'AVANT vu. Gravé en entier dans
`test/test_reglages.py`. Les bornes dures du §5.6 sont refusées au chargement,
tout comme l'invariant du pivot violé.

## Tests

```bash
cd packages/didier_corps_sur && ../../.venv/bin/python -m pytest -q -o addopts=
mypy didier_corps_sur            # --strict, configuration dans setup.cfg (ROS ignoré sur le PC)
```

Épreuves de sim (25 verdicts, ≈ 15 min, monde `stage`) :
`docker exec didier-sim-monde bash /home/ros2_ws/validate-corps-sur.sh` (sous-ensemble :
`-e CS_SEULEMENT=CS2,CS3`). Elles sont dans la fumée (`ATTENDU_CORPS_SUR=25`).

Valeurs **gravées** (table du §6.2) ; pour `couverture`, une seconde méthode
indépendante (grille en entiers et aires exactes) est citée en tête de
`test/test_couverture.py`.

### Contrôle par mutation (§6.3) — appliqué le 18/11, un mutant à la fois, code restauré et vérifié octet par octet

| # | Mutant | Test(s) qui tombe(nt) |
|---|---|---|
| 1 | `< marge_arret` → `< marge_arret − 0,1` (`zones`) | `test_zones::test_suite_gravee_de_la_spec`, `test_balayage::test_un_point_devant_a_0_56_arrete` (+2) |
| 2 | masques plus appliqués (`balayage`) | `test_balayage::test_le_meme_dans_un_masque_est_ignore`, `test_temoin_present_valide` |
| 3 | `min` → `max` dans le facteur de plafond (`filtre`) | `test_filtre::test_libre_plafonne` (+7, dont la propriété 1 000 tirages) |
| 4a | sortie d'ARRET sans la marge d'hystérésis (`zones`) | `test_zones::test_suite_gravee_de_la_spec` |
| 4b | sortie d'ARRET au premier balayage (`zones`) | `test_zones::test_suite_gravee_de_la_spec` (+2) |
| 5 | âge du capteur inversé, chien de garde (`garde`) | `test_garde::test_capteur_perdu` (+7) |
| 5b | âge à la réception inversé (`balayage`) | `test_balayage::test_age_0_26_invalide` (+6) |
| 6 | `e_stop` plus lu (`garde`) | `test_garde::test_e_stop_verrouille_sur_le_champ`, `test_e_stop_au_demarrage_empeche_d_armer`, `test_rearmement_cause_presente_refuse` |
| 7 | témoin plus vérifié (`balayage`) | `test_balayage::test_temoin_exige_et_absent_invalide`, `test_temoin_trop_peu_de_points_invalide` |
| 8 | signe de `lacet_rad` inversé (`geometrie`) | `test_geometrie::test_signe_du_lacet` |
| 8b | signe du lacet inversé dans le relèvement (`couverture`) | `test_couverture::test_signe_du_lacet_dans_la_couverture` (écrit APRÈS une survie : le lacet π ne distinguait pas le signe) |
| 9 | en ARRET, `filtrer` rend l'entrée | `test_filtre::test_arret`, `test_propriete_courbure_1000_tirages` |
| 10 | le réarmement n'examine plus la cause (`garde`) | `test_garde::test_rearmement_cause_presente_refuse`, `test_rearmement_superviseur_encore_absent_refuse` |
| 11 | le ralenti ne touche que v (`filtre`) | `test_filtre::test_ralenti_plafonne_puis_divise` (+2) |
| 12 | (nœud) zéro anticipé supprimé → CS2 > 200 ms à 5 Hz | `test_moteur::test_zero_anticipe_sur_les_seuls_canaux_actifs` (+9) ; en sim : voir « Mutant 12 en sim » plus bas |

### Mutants du moteur et des configurations (A0-4, 20/11, copie du package, un à la fois)

| Mutant | Test(s) qui tombe(nt) |
|---|---|
| fenêtre d'activité = délai du mux (0,5 s au lieu de 1,0) | `test_moteur::test_canal_actif_jusqu_a_une_seconde` (+1) |
| le blocage ignore la pause de durée | `test_moteur::test_pause_duree_zero_anticipe_aux_autres_canaux` |
| le blocage ignore la zone ARRET | `test_moteur::test_zero_anticipe_sur_les_seuls_canaux_actifs` (+4) |
| pas de tic avant de filtrer une demande | `test_moteur::test_le_zero_part_aux_autres_canaux_quand_le_blocage_nait_pendant_une_demande` (+1) |
| un balayage invalide nourrit le chien de garde | `test_moteur::test_balayage_fige_ne_nourrit_pas_le_capteur` (+2) |
| le stamp précédent n'est jamais retenu | `test_moteur::test_balayage_fige_ne_nourrit_pas_le_capteur` (+1) |
| un balayage invalide ne peut plus faire entrer en ARRET | `test_moteur::test_balayage_trop_vieux_ne_nourrit_pas_mais_arrete` (+1) |
| `e_stop` non transmis à la garde | `test_moteur::test_e_stop_zero_verrou_puis_rearmement_apres_relache` (+1) |
| entrée ou sortie non notée (durée bornée) | `test_moteur::test_pause_duree_robot` (+1) |
| dernier refus non mémorisé (diagnostics) | `test_moteur::test_diagnostics_niveaux` (+1) |
| ERROR en VERROU devenu WARN | `test_moteur::test_diagnostics_niveaux` (+1) |
| sim : `angulaire_aveugle_autorise` faux | `test_configs_machines::test_sim_gravee` (+2) |
| robot : superviseur exigé | `test_configs_machines::test_robot_gravee` (+4) |

Piège rencontré : un mutant de même taille (`min` → `max`), restauré dans la
même seconde, laisse un `.pyc` périmé, car la validation du cache se fait à la
seconde près et par la taille. Les mutants se jouent donc avec
`PYTHONDONTWRITEBYTECODE=1`, après avoir purgé `__pycache__`.

### Mutant 12 en sim (20/11)

Copie du package dans le conteneur `monde` (`/tmp/m12`, jamais dans l'arbre), `if bloque and not
self._bloque:` → `if False:` dans `moteur.py`, nœud relancé par l'épreuve avec
`CS_NOEUD_PYTHONPATH=/tmp/m12`, `CS_SEULEMENT=CS1,CS2` : **CS2d tombe** (5 Hz : 13/20 sous 200 ms,
max 301 ms ; 20 Hz : max 155 ms, encore sous la porte). Sans mutant, la même passe donne 20/20 à
5 Hz, max 133 ms. Le zéro anticipé est donc ce qui tient la porte à 5 Hz, comme la spec l'annonce.

## A0-4 (20/11) — points ouverts de sécurité, tranchés du côté sûr ou laissés à A0-8

1. **`e_stop` coupe en ≈ 0,43 s, pas en 0,1.** Le verrou `e_stop` du mux (255) masque aussi la
   sortie du corps sûr : son zéro anticipé n'atteint pas `cmd_vel`, et `twist_mux` ne publie
   AUCUN zéro quand un verrou se pose. Le zéro vient du deadman (400 ms de silence). Mesuré
   0,43 s (CS11, critère gravé à 0,5 s). Chaîne inchangée par A0 (spec §3.1) : à traiter avec W1
   (source réelle d'`e_stop`) et à la relecture adverse (A0-8) — par exemple un zéro publié en
   aval du mux à la pose du verrou. `wheels_node` garde son propre deadman de 400 ms.
2. **Un nœud figé plus de 0,30 s se verrouille seul** (`capteur_perdu`, réarmement exigé).
   L'exécuteur de rclpy sert les minuteries AVANT les abonnements : après un gel, le tic voit
   un dernier balayage vieux de plus de 0,30 s avant de traiter celui qui attend. Sûr (zéro et
   verrou), mais un verrou de plus à lever. Vu en sim sous charge (environ une fois par quart
   d'heure, avant que le banc ne le réarme) : `/clock` y arrive à ≈ 930 Hz et coûte 50 à 80 %
   d'un cœur à CHAQUE nœud Python en `use_sim_time`. Sur le Pi 4 (horloge murale), la fréquence
   de ces verrous est à mesurer en A0-6/A0-7 ; la borne de 0,30 s ne se relâche pas (spec §5.6).
   **21/11, mesuré sur le BRINGUP** (SIGSTOP du seul nœud, lidar jamais arrêté) : gel ≤ 0,25 s,
   0 verrou sur 5 ; gel de 0,4 à 0,6 s, 3 verrous sur 5. C'est ce verrou qui a fait tomber la fumée
   2026-11-20-1707 (verrou à 17:08:38 pendant validate-namespace, edition n°7 sans `cmd_vel`).
   **À trancher par David** : un nœud gelé, et non un capteur muet, doit-il verrouiller ? Pendant
   un gel, le nœud ne publie rien et le deadman coupe en 0,4 s (spec §3.1). Au réveil, le
   balayage frais montre le monde. Ne pas verrouiller reviendrait à juger la péremption sur
   l'horodatage du balayage plutôt qu'à sa réception, donc à changer la lecture de §5.6. Le code
   n'y touche pas.
   **Il bloque la fumée** : 2026-11-21-1929, un verrou pendant V-R3 (19:46:51, 5 min après le
   départ, sans pause thermique) a arrêté Didier jusqu'à la fin de la route (19/21). Les pistes, à
   trancher : (a) changer la lecture de §5.6 (règle de sécurité, donc David, avec une relecture
   Fable) ; (b) alléger la sim : `/clock` à ≈ 930 Hz coûte 50 à 80 % d'un cœur à chaque nœud Python
   (sim seule, aucune règle touchée, mais tout le chronométrage des épreuves en dépend) ; (c) un
   banc qui réarme aussi PENDANT les épreuves roulantes, avec une borne et dit sur la page (masque
   davantage).
3. **Écarts du banc à la spec, écrits dans l'en-tête de `validate-corps-sur.sh`** : CS3 borne
   basse 0,2 s au lieu de 0,3 (trois balayages de sortie à 10 Hz) ; CS5 « ARRIERE vue » joué au
   niveau du moteur (`test_moteur.py`), la pose A ne voyant pas l'arrière ; CS11 à 0,5 s (point 1).
4. **Le banc se protège de lui-même, jamais du nœud** : un essai d'obstacle où Didier n'était pas
   en marche à T0 VU DU PILOTE (pilote en retard sur ses réceptions) est rejoué deux fois au plus ;
   un VERROU `capteur_perdu` trouvé en tête d'essai (point 2) est compté, dit au journal et
   réarmé, deux au plus par passe, sinon la passe est rouge. Latence, distance et état attendu ne
   se rejouent jamais.
   La fumée fait de même pour le corps sûr DU BRINGUP (21/11, `machines/sim/corps_sur_bringup.py`) :
   ARME exigé avant chaque épreuve qui fait rouler Didier (edition, V-R3, A1, OBJ, CONV), sinon
   l'épreuve est rouge, avec l'état lu. Seul un VERROU `capteur_perdu` est réarmé, deux fois au
   plus par épreuve, et chaque réarmement est dit sur la page. Un verrou né PENDANT une épreuve y est
   aussi dit. Avant cela, l'épreuve CS (qui relance son propre nœud) était seule à éprouver un
   corps sûr.
5. **Hors A0, relevé en route** : `wheels_bridge` publie UNE consigne par clé `wheels` ; le mux ne
   republie pas ; le deadman met zéro 0,4 s après. Une clé roues de séquence fait donc rouler
   Didier 0,4 s, pas jusqu'à la clé suivante (vu en CS4b sur `little-move3` : 0,5 m/s puis zéro
   0,4 s plus tard). Antérieur à A0, côté sûr ; à signaler pour les chorégraphies (danse, M6).
6. **Corrigé le 21/11 : un réarmement REFUSÉ tuait le nœud** s'il suivait un réarmement accepté.
   rclpy refuse qu'une même ligne journalise tantôt en info, tantôt en warning
   (`journal = info if accepte else warning`). Le nœud mourait, côté sûr (zéro puis sortie, sans
   relance), mais il fallait relancer tout le bringup. Le correctif donne un site d'appel par
   sévérité. Il est gravé par `test_contrat_node.py::test_chaque_appel_du_journal_a_une_severite_fixe`,
   et vu en sim : accepté, refusé, accepté, nœud vivant.

## Relecture critique d'A0-3 (19/11) — points ouverts, documentés, pas tranchés

1. **Les coins de la caisse et le rayon de balayage ne disent pas la même chose.** Le
   rectangle majorant (`x_arriere` −0,57, `demi_largeur` 0,40) a ses coins arrière à
   hypot(0,10 + 0,57 ; 0,40) = **0,78 m** de l'essieu, alors que `rayon_balayage` vaut **0,65**
   (bout de la flèche arrière, spec §4.1). Les deux sont cohérents seulement si le corps RÉEL
   n'occupe pas les coins du rectangle (c'est l'hypothèse de la spec : le rectangle sert aux
   distances, le rayon au pivot). Si les coins sont pleins, un pivot les fait passer à 0,78 m
   de l'essieu : l'invariant devient 0,10 + 0,78 − 0,30 = **0,58 > 0,55** et `reglages` refuse
   la configuration (Didier ne bouge plus seul). Les cinq cotes réelles sont mesurées en
   **A0-7** ; c'est là que l'on saura si `rayon_balayage` ou le rectangle doit bouger. Rien
   n'est changé d'ici là.
2. **Le masque `[90, 270]` est PROVISOIRE.** Il cache le demi-tour arrière du plan du lidar.
   En sim (pose 25 cm, corps en boîtes), le masque mesuré est `[96.64, -96.64]` : le provisoire
   le recouvre (6,6° de plus de chaque côté), aucun auto-retour ne tombe hors de lui, et la
   couverture annonce la même chose (avant vu seulement). Sur le robot réel, rien n'est mesuré :
   un auto-retour hors de `[90, 270]` (roue, porte, câble) donnerait `retour_dans_caisse` et un
   ARRET permanent — visible tout de suite, donc sûr, mais à mesurer au banc avec
   `tools/mesurer_masques.py` (**A0-7**) avant de remplacer la valeur.
3. **L'analyse de `tools/mesurer_masques.py` n'a pas de tests.** Sa docstring cite
   `test/test_mesurer_masques.py`, qui n'existe pas ; la fusion circulaire des masques et le
   choix du témoin ne sont vérifiés que par l'essai en sim du 19/11. À écrire (valeurs gravées)
   avant l'usage au banc en A0-7.
4. **Témoin de vie en sim = artefact.** Le lidar simulé renvoie son boîtier et la face de la
   caisse à exactement 0,05 m (portée minimale) sur tout le secteur masqué ; la règle « à plus de
   0,05 m » passe pour 0,05000000074 (flottant). L'outil propose donc un témoin couvrant tout le
   masque, à partir de 0,005 m : il ne doit pas être recopié dans un fichier de configuration.
   Durcir la règle (strictement au-dessus de `portee_min_m` + une marge) est à décider avec le
   témoin réel en A0-7.
5. **Un obstacle sur un flanc n'arrête pas l'avance.** Essai en sim du 19/11 (ci-dessous) :
   cylindre à 0,4 m du flanc droit, masqué, zone LIBRE, `filtrer` laisse passer 0,3 m/s vers
   l'avant. C'est la conséquence assumée de la décision du 18/11 (flancs et dos = zone de David)
   et de la règle « refuser le mouvement VERS ce qui n'est pas vu » : une avance droite ne va pas
   vers le flanc, mais une courbe serrée (v et ω non nuls, tour toléré à la maison) balaie
   l'avant du flanc sans le voir. À regarder à la relecture adverse (A0-8).

## Premier essai du lidar simulé contre cette logique (19/11, avant le nœud d'A0-4)

Le nœud n'existe pas encore : une sonde (hors dépôt) lisait `/didier/scan` dans le conteneur
`monde` (monde `stage`, pose 25 cm, masque `[90, 270]`, réglages par défaut) et appliquait
`lire_balayage` → `Zones.observer` → `filtrer(0,3 ; 0 ; follow)` à chaque balayage, l'obstacle
étant posé par `set_pose` et sa vraie distance lue à la vérité terrain.

| Obstacle (cylindre r 0,15 m) | Distance vraie à la caisse | `d_min` lidar | Zone | Sortie | Réaction après T0 |
|---|---|---|---|---|---|
| devant | 2,00 m | 1,992 | LIBRE | 0,30 | — |
| devant | 0,90 m | 0,885 | RALENTI | 0,15 | — |
| devant | 0,50 m | 0,469 | ARRET | 0 | 100 ms (1 balayage) |
| coin avant gauche | 0,42 m | 0,409 | ARRET | 0 | 50 ms |
| flanc droit | 0,40 m | — (masqué) | LIBRE | 0,30 | voir point 5 |
| derrière | 0,50 m | — (masqué) | LIBRE | 0,30 (recul refusé : arrière non vu) | — |
| retiré | — | — | LIBRE | 0,30 | — |

Passant (cylindre r 0,20 m) en travers à 0,5 m devant la caisse, deux vitesses : `d_min`
0,484 m ; LIBRE → RALENTI → ARRET → RALENTI → LIBRE ; ARRET pendant 1,80 s à 1,0 m/s et
1,30 s à 1,5 m/s (géométrie : 1,57 s et 1,05 s, plus la sortie retardée de 3 balayages et 5 cm).
