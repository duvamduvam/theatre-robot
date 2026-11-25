# Spec F1 — le programme de fumée (25/11/2026)

Lot F1 de l'étude `docs/etudes/etude-fumee.md` (§3 critères, §4 cible, §6 lots, §8.1 réponses
de David, §8 bis mesures F0). Remplace, à terme (F3), `machines/sim/fumee.sh` (1 250 lignes de
bash). **En F1, `fumee.sh` ne change pas** : les deux coexistent jusqu'à ce qu'ils rendent le même
verdict.

## 0. En une phrase

Un programme Python sans dépendance hors bibliothèque standard, piloté par un plan d'épreuves
déclaratif, qui rend pour chaque épreuve **vert, rouge ou invalide**, rejoue seule une épreuve
invalide, tourne sur n'importe quelle révision dans son propre arbre de travail, ne reconstruit
une image que si ses fichiers ont changé, et marche hors ligne.

## 1. Où et comment

- Code : `machines/sim/fumee/` (paquet Python : `__main__.py`, `plan.py`, `banc.py`, `sim.py`,
  `epreuve.py`, `gardiens.py`, `images.py`, `rapport.py`). Python 3.12, **bibliothèque standard
  seule** (le runner GitHub et le PC l'ont ; pas de PyYAML).
- Plan : `machines/sim/fumee/plan.toml` (`tomllib`).
- Lancement : `python3 -m fumee` depuis `machines/sim/` (une ligne d'appel documentée dans
  `docs/operations.md`).
- Cible de taille : **moins de 700 lignes** de code à nous (tests à part). Les scripts
  `validate-*.sh`, `capture_topics.py`, `captures.sh`, `coeurs_reserves.py`, `corps_sur_bringup.py`
  sont **réutilisés tels quels**.
- La page et l'historique restent ceux de `fumee_page.py` : le programme écrit un
  `resultat.json` et des lignes d'épreuve au **même format** que `fumee.sh` (champs de
  `CHAMPS_HISTORIQUE`), plus le statut `invalide`. `fumee_page.py` gagne seulement la lecture de
  `invalide` (pastille orange, ne compte pas comme rouge dans « due ? »).

## 2. Commande

```
python3 -m fumee [--rev <branche|sha|PR>] [--epreuves a1,objets | --tout]
                 [--hors-ligne] [--minuterie] [--forcer-verrou] [--essai]
```

| Option | Effet |
|---|---|
| `--rev` | révision testée (défaut : `origin/main` à jour). Mise en place dans l'arbre de travail du programme, `~/tmp/didier/fumee-arbre` (worktree git, recréé si absent, jamais le checkout de David) |
| `--epreuves` / `--tout` | sous-ensemble (défaut `--tout` en F1 ; le choix par chemins touchés est F2) ; les dépendances du plan (`demarrage`, `rtf`) sont ajoutées seules |
| `--hors-ligne` | aussi détecté seul (DNS de `github.com` injoignable) : aucune reconstruction d'image (absente du cache → `invalide : hors ligne`), `conversation` en `non_lance (hors ligne)`, pas de `git fetch` (la révision doit être locale) |
| `--minuterie` | remplace `--si-due` : décide « due ? » avec les règles actuelles de `fumee_page.py due`, reporte sans page si le banc n'est pas sain |
| `--essai` | marque la fumée « essai » (jamais référence, jamais commitée) |

« Et dodo » (extinction) **reste dans `fumee.sh`** en F1 ; F3 tranchera.

## 3. Le plan (`plan.toml`)

Une entrée par épreuve, dans l'ordre d'exécution. Exemple :

```toml
[[epreuve]]
id = "a1"
script = "validate-jeu-a1.sh"
attendu = 14
motif = "=== A1"              # ligne finale « N OK, M KO »
delai_s = 1500
sim = { monde = "chantiers", regie = "jeu-a1", jeu = true }
corps_sur_arme = true         # exiger_corps_sur_arme + noter_verrous_pendant de fumee.sh
chemins = ["packages/didier_jeu/", "packages/didier_rehearsal/", "packages/didier_core/"]
bloque = []                   # épreuves rendues inutiles par un rouge de celle-ci
```

Champs : `id`, `type` (`script` par défaut ; `interne` pour `image`, `demarrage`, `rtf`, `parle`,
codées dans le programme), `script`, `attendu`, `motif`, `delai_s`, `sim` (monde, régie,
jeu, tête), `corps_sur_arme`, `facultative`, `chemins` (servira en F2, écrit dès F1), `bloque`.
Les **valeurs attendues** (aujourd'hui `ATTENDU_*` de `fumee.sh`) passent dans le plan avec
leur commentaire ; un test grave que le plan et `fumee.sh` donnent les mêmes valeurs tant que
les deux coexistent.

**Sim partagée.** Deux épreuves consécutives qui demandent la même `sim` partagent la même
sim (comme `namespace` → `audio` aujourd'hui). Une `sim` différente arrête et relance la sim
(comme `corps_sur`, `chantiers`, `a1`, `objets`, `conversation`).

**Bloquants.** `demarrage`, `rtf` et `corps_sur` bloquent tout ce qui suit (règle actuelle).
Aucune autre épreuve ne bloque : un rouge n'arrête plus la fumée, toutes les épreuves rendent
leur compteur.

## 4. Trois verdicts

| Verdict | Quand |
|---|---|
| **vert** | compteur `N OK, 0 KO` avec `N = attendu`, code de retour 0 |
| **rouge** | compteur faux, banc sain pendant toute l'épreuve |
| **invalide** | un gardien a parlé pendant l'épreuve, ou l'enregistreur des captures est mort (« mesure invalide », déjà détecté), ou l'image manque hors ligne |

Gardiens, interrogés toutes les 5 s pendant une épreuve :

- **chaleur** : paquet CPU ≥ 85 °C (`sensors`, comme aujourd'hui). Le gardien **ne met plus la
  sim en pause** : il arrête l'épreuve (le script est tué), la marque `invalide : chaleur`,
  arrête la sim, attend que le paquet passe sous 80 °C (au plus 20 min), relance la sim de
  l'épreuve et la rejoue. Deux rejeux au plus ; ensuite `invalide`, noté sur la page.
  Jamais au-delà de 90 °C (règle de David) : à 88 °C, arrêt immédiat de toute la fumée.
- **temps réel** : sonde de 20 s avant la première épreuve de chaque sim (seuil 0,8). Sous le
  seuil : `invalide : temps réel`, une nouvelle tentative après 2 min, puis abandon.
- **réseau** (pour `conversation` seulement) : API injoignable → `non_lance (hors ligne)`.

Une fumée dont toutes les épreuves sont vertes ou facultatives non lancées est **verte** ; une
seule rouge la rend **rouge** ; sinon (au moins une invalide, aucune rouge) elle est
**invalide** et n'entre jamais dans « dernier vert ».

## 5. Images

Empreinte d'une image = sha256 des fichiers de `CHEMINS_IMAGES` (même liste que
`fumee_page.py`) qui la composent, posée en étiquette Docker (`didier.empreinte`) au build.
Image locale présente avec la même empreinte : **réutilisée**, jamais reconstruite. Sinon
reconstruite (en ligne) ou `invalide : hors ligne`. Fini « aucune fumée verte de référence, on
reconstruit tout ». `FUMEE_BUILD_ARGS` (frontend « labs » sur GitHub) est conservé.

## 6. Le banc (repris de `fumee.sh`, sans changement de règle)

Domaine 43 revérifié dans chaque conteneur ; sim de quelqu'un d'autre (`didier-sim-*` déjà là)
→ refus, jamais tuée ; verrou `~/tmp/didier/sim-occupee` (pose, péremption 6 h, `--forcer-verrou`) ;
flock contre deux fumées ; cœurs réservés (`coeurs_reserves.py`) ; profil d'énergie
`performance` sur secteur, rendu à la fin ; X d'une session pour Gazebo ; journaux récoltés
**avant** chaque arrêt de sim ; arbre de travail inchangé hors `docs/fumee` ; aucun commit
ailleurs que `docs/fumee` (et seulement depuis le checkout de main, `FUMEE_COMMIT`).
Toute variable `FUMEE_*` existante garde son sens.

## 7. Tests (CI, `packages/didier_core/test/unit/test_fumee_programme.py`)

Valeurs gravées, jamais recalculées par le code testé :

1. Lecture du plan : ordre, champs obligatoires, plan invalide refusé avec un message clair.
2. Mêmes valeurs attendues que `fumee.sh` (lu comme texte) tant que les deux existent.
3. Verdict d'une épreuve : vert, rouge, invalide (chaleur, enregistreur mort, hors ligne).
4. Verdict d'une fumée : vert / rouge / invalide ; facultative non lancée.
5. Rejeu : avec un faux exécuteur et un faux thermomètre, une épreuve invalidée est rejouée
   seule, deux fois au plus ; une épreuve rouge banc sain n'est **jamais** rejouée.
6. Bloquants : rouge de `corps_sur` → suivantes `non_lance` ; rouge de `a1` → `objets` lancée.
7. Regroupement des sims : le plan actuel donne exactement 6 démarrages de sim.
8. Empreinte d'image : stable, change si un fichier de `CHEMINS_IMAGES` change.
9. Hors ligne : aucune commande `docker compose build`, conversation `non_lance`.

Les appels système (docker, git, sensors) passent par **un seul** objet injecté, remplacé par
un faux dans les tests.

## 8. Critère de sortie de F1

- Fumée complète du nouveau programme sur le PC, **même verdict épreuve par épreuve** que
  `fumee.sh` sur le même sha.
- Une épreuve invalidée exprès (thermomètre forcé à 86 °C via `FUMEE_THERMOMETRE=<fichier>`,
  variable de test) est rejouée seule et finit verte.
- Une fumée relancée juste après une verte ne reconstruit aucune image (temps < 40 min).
- Une fumée lancée réseau coupé termine (`conversation` non lancée).
- Doc : `docs/operations.md` (commande, verdicts), `machines/sim/README.md`, `docs/chantiers.md`.

## 9. Ce que F1 ne fait pas

Choix des épreuves par chemins touchés et statut sur la PR (F2) ; suppression de `fumee.sh`
et minuterie basculée (F3) ; workflow GitHub appelant le nouveau programme (F4 bis, après F1).
