# didier_corps_sur — le corps sûr de Didier (lot A0)

Filtre déterministe placé AVANT `twist_mux` sur les trois entrées autonomes des
roues (`cmd_vel_anim`, `cmd_vel_follow`, `cmd_vel_web`). Il met zéro dès qu'un
obstacle est à moins de 0,6 m de la caisse ; entre 0,6 et 1,2 m, il ralentit
par palier. Il met zéro **et se verrouille** si le lidar se tait, si le
superviseur disparaît ou si `e_stop` tombe. Il refuse tout mouvement vers ce
que le lidar ne voit pas. La télécommande (`cmd_vel_remote`, prio 100) n'y
passe pas. Spec FERMÉE : `docs/spec-A0-corps-sur.md`.

**État (A0-3, 18/11)** : la logique PURE et ses tests seulement. Le nœud
`corps_sur_node.py`, son insertion dans la chaîne, les contrats de topics et
les épreuves de sim arrivent en A0-4. Le déploiement arrive en A0-6. Aucun
Pi ne reçoit ce package tant qu'il n'est pas dans une liste `packages:` de
`machines/<machine>/machine.yml`.

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

## Configuration

`config/corps_sur.yaml` : défauts SÛRS du package (`terrain: reel`, superviseur
exigé, angulaire aveugle refusé, pose A face avant 0,33 ; 0, plan à 0,25 m).
Masque PROVISOIRE `[90, 270]` jusqu'à la mesure (`mesurer_masques`, A0-7) :
la couverture n'annonce alors que l'AVANT vu. Gravé en entier dans
`test/test_reglages.py`. Les bornes dures du §5.6 sont refusées au chargement,
tout comme l'invariant du pivot violé.

## Tests

```bash
cd packages/didier_corps_sur && ../../.venv/bin/python -m pytest -q -o addopts=
```

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
| 12 | (nœud) zéro anticipé supprimé → CS2 > 200 ms à 5 Hz | **reporté à A0-4** (le nœud n'existe pas encore) |

Piège rencontré : un mutant de même taille (`min` → `max`), restauré dans la
même seconde, laisse un `.pyc` périmé, car la validation du cache se fait à la
seconde près et par la taille. Les mutants se jouent donc avec
`PYTHONDONTWRITEBYTECODE=1`, après avoir purgé `__pycache__`.

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
