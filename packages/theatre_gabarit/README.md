# theatre_gabarit — ajouter un appareil au parc

Lot L3a (28/11), spec [`docs/spec-L3-gabarit-sono.md`](../../docs/spec-L3-gabarit-sono.md). Un
**appareil** est une machine du spectacle hors du robot (sono, lumières de scène…) : il tourne
sous le namespace du robot (`/<ROBOT_NAME>/`), publie UN état (enveloppe commune), reçoit des
ordres, et se voit sur la page scène (tuile « Appareils ») sans une ligne de code de page.

Deux moitiés, pour ne copier ni code ni JSON :
- une **bibliothèque** importée (`theatre_gabarit/`, 4 modules, inventaire gravé par test) ;
- un **squelette** mince (`squelette/`, `COLCON_IGNORE`), recopié et renommé par
  `tools/nouvel_appareil.py` : des fichiers à trous (`APPAREIL`) et des tests rouges qui disent
  quoi remplir. Le générateur n'édite **aucun** fichier partagé : ces gestes-là sont dits par
  `test_gabarit.py` (`verifier_appareil`).

## La bibliothèque

| Module | Rôle |
|---|---|
| `noeud.py` | `NoeudAppareil` (tient un nœud rclpy, pas d'héritage) : paramètres `pilote`, `config`, `sha_fichier` ; état latché `<appareil>/etat` publié à chaque changement et au plus tard toutes les 2 s (`Battement`) ; `diagnostics` à 1 Hz (`niveau_diagnostic` : ERROR si un organe `absent`/`erreur`, WARN si un ordre refusé depuis < 10 s, sinon OK) ; sha lu dans `conf/DEPLOY_SHA` (`dev` si absent) ; `abonner(topic, rappel)` (StringTime `volatile(10)`, valeur décodée par `decode_or_raw`) ; `tourner()` : SIGINT/SIGTERM -> pilotes au repos, sortie 0 ; exception d'un rappel -> pilotes au repos, sortie 1 |
| `pilotes.py` | `choisir(nom, fabriques, ros_domain_id)` : `sim` ou `materiel` ; **`sim` hors domaine 43 = `PiloteRefuse`, sortie code 2** ; santé `ok` / `absent` / `erreur` |
| `lancement.py` | `groupe_appareil(paquet, executable, nom_noeud, config)` : arguments `robot_name`, `pilote` (défaut `materiel`), `config` ; UN `PushRosNamespace` absolu ; jamais `use_sim_time` |
| `essais.py` | `Enregistreur` (faux pilote qui note ses appels) ; `verifier_appareil(dossier)` : la liste des gestes restants (9 causes, docstring du module) |

**Règle d'émergence** : rien n'entre ici que la sono (`sono_core`, L3b) n'utilise ; un 5e module
exige un 2e appareil qui en a besoin.

## Les gestes (numérotation du chrono, spec §10)

Exemple : `sono`. Chaque geste dit ce qu'il produit et le test qui passe au vert.

1. **G1 — générer** : `python3 packages/theatre_gabarit/tools/nouvel_appareil.py sono` (refus si
   l'appareil existe). Écrit `packages/sono_core/`, `machines/sono/`, `machines/sim/sono/entree.sh`.
   Lancer `cd packages/sono_core && ../../.venv/bin/python -m pytest -q -o addopts=` : 5 tests
   rouges ; celui de `test_gabarit.py` liste les gestes restants.
2. **G2 — contrat** : dans `packages/theatre_contrats/`, ajouter l'appareil à
   `appareils.REGISTRE` (topic d'état, topics d'ordres par type d'organe), ses topics à
   `topics.py`, à `test/test_inventaire.py` et au compte de `test/test_topics_relatifs.py` ;
   graver le registre dans `test/test_appareils.py`. Dans `sono_core/contrat.py` : `TOPICS` et
   les noms, depuis `theatre_contrats.topics`. Le pont web et la page scène suivent seuls
   (whitelists, `stop_all`, tuile) : relancer `packages/didier_core` (`test_web_protocol.py`
   grave les listes du pont — les y étendre).
3. **G3 — réglages** : `reglages.py` (YAML + bornes dures, `ReglagesError`), `config/sono.yaml`
   (défauts sûrs), `machines/sono/sono.yaml` (câblage de CETTE machine, lu aussi par la sim),
   `test_reglages.py` (fichier chargé = dictionnaire gravé ; bornes refusées).
4. **G4 — logique** : `logique.py` PUR (stdlib, horloge en argument, pilotes injectés —
   `essais.Enregistreur` pour les tests) ; `etat(t_ms)` rend `(organes, refus)` construits par
   `theatre_contrats.appareils.organe_*` / `refus` ; `test_logique.py` gravé, bornes à leur limite.
5. **G5 — pilotes** : `pilotes/base.py` (un `Protocol` par famille), `sim.py` (mémoire),
   `materiel.py` (libs importées à l'appel ; matériel absent = `absent`, jamais d'exception) ;
   `test_pilotes.py` (faux exécutable en tête du PATH pour la commande exacte).
6. **G6 — nœud, launch** : `noeud.py` mince — un `app.abonner(...)` par ordre, **aucun `if`**
   (hors `__main__`) ; `launch/sono.launch.py` tient en `groupe_appareil(...)` ;
   `test_contrat_noeud.py` (noms, types, QoS, liste des `if`, namespace absolu ; motif
   `didier_corps_sur/test/test_contrat_node.py`).
7. **G7 — README-contrat** : `packages/sono_core/README.md`, 8 titres dans l'ordre (Rôle,
   Machine, Topics, Comportement, Pilotes, Simuler, Tester, Déployer), aucun trou `APPAREIL`.
8. **G8 — machine, CI** : `machines/sono/` (Dockerfile, compose ARM, script, `machine.yml` :
   `packages`, `launch_cmd`, `noeuds_attendus`, `sentinelle_build`, et les variables du tableau
   de `machines/README.md` — `sha_deploye`, `audios_prives`…) ; `deploy/hosts` (groupe, hôte
   `machine: sono`) et `HOTES_MACHINES` de `test_arborescence.py` ; une ligne `suite:` dans
   `.github/workflows/tests.yml`.
9. **G9 — sim** : service `sono` dans `machines/sim/docker-compose.yml` (le Dockerfile du Pi,
   domaine 43 littéral, `pilote:=sim` posé par `machines/sim/sono/entree.sh`) ; la fumée le prend
   seule (conteneurs déduits du compose) ; l'appareil apparaît dans la tuile « Appareils ».
10. **G10 — épreuve** : `machines/sim/validate-sono.sh` et son `[[epreuve]]` (`id = "sono"`)
    dans `machines/sim/fumee/plan.toml` ; fumée ciblée verte.
11. **G11 — déploiement** : `ansible-playbook -i hosts deploy-pios.yml -e target_group=sono`,
    `./ecart-pi.sh sono --graver`, puis `./ecart-pi.sh sono` vert.

`test_gabarit.py` vert = gestes G2, G6 (partie nœud), G7, G8 (machine, CI), G9, G10 faits ; les
autres tests de l'appareil disent le reste.

## Tester

```bash
cd packages/theatre_gabarit && ../../.venv/bin/python -m pytest -q -o addopts=
```

Gravé : les 4 modules ; `choisir("sim", …, 42)` lève ; battement à 2,0 s ; niveaux de
diagnostic ; `verifier_appareil` rougit pour chacune des 9 causes (un cas par cause) ;
l'appareil jetable `essai`, généré dans un dossier temporaire, a ses tests rouges pour les bonnes
raisons et sa liste de gestes gravée en entier.
