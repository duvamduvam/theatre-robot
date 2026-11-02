# Spec A1 — le sélecteur de jeu en simulation (`didier_jeu`)

*Écrite le 2026-11-02, après les dix décisions de David (`etude-autonomie-improvisation.md`
§8). SIM-ONLY tant que le corps sûr (A0) n'existe pas : garde-fou `ROS_DOMAIN_ID=43` comme
`robot_rehearsal`. Objet : répondre à « pourquoi et quand Didier agit » avec un mécanisme
réglable, journalisé, lisible — pas encore avec la vraie perception (scriptée en A1).*

## 0. Ce que A1 prouve, et ce qu'il ne prouve pas

**Prouve** (porte de sortie, §6) : qu'un sélecteur déterministe, nourri d'offres et de
pulsions, choisit *quoi jouer et quand* sans osciller, en respectant les règles de fréquence
gravées, en journalisant chaque choix avec sa raison, et que David peut le guider en macro
depuis la page scène. **Ne prouve pas** : le réglage artistique (il se fait au réel, David
derrière), la perception (A2), le fond permanent respiration/regard (A+, rouvre l'arbitrage
actionneurs), la sécurité (A0 — en sim il n'y a pas d'obstacle).

## 1. Où ça se branche (rien de neuf sur le chemin roues)

```
 perception scriptée ─► vision/person_box ──┐
 régisseur ──► rehearsal/poi_event ─────────┤
 bouche (chat_node) ──► rehearsal/chat_move ┤      ┌───────────────┐   jeu/chat_move   ┌──────────┐  route_goto  ┌──────────────┐
 page scène ──► jeu/console ────────────────┼────► │  didier_jeu   │ ─────────────────►│ régisseur │────────────►│ route_driver │─► cmd_vel_follow (prio 20)
 metteur en scène ──► mission_state, chat_situation ┘  │ (sélecteur)   │   animation       │ (director)│             └──────────────┘
                                                   └──────┬────────┘ ───────────────► animations_node (bras, cou, yeux, visage ; pistes roues de séquence : prio 10, inchangé)
                                                          │ jeu/intention (latché), jeu/journal (JSONL)
```

- **Un seul décideur du corps** (décision 6) : le régisseur n'écoute plus `rehearsal/chat_move`
  venant de la bouche mais `jeu/chat_move` venant du sélecteur — **remap dans le launch**,
  zéro changement dans `chat_node` ni `director`. La bouche continue de publier ses
  `go/stop/aller_voir/tour_de/regarder/tourner/avancer` : ils deviennent des **intentions**
  que le sélecteur pondère. **Exception gravée** : `stop` (arrêt vocal, clé `marche: stop`)
  est **relayé immédiatement et sans arbitrage** — l'arrêt gagne toujours (règle du 23/10).
- Les arbitrages du régisseur (jamais contre un `off` de David, distance max, refus
  journalisés — `spec-aller-voir` §3) **restent** : le sélecteur propose, le régisseur dispose,
  `route_driver` exécute. Le sélecteur n'a **aucun** éditeur de Twist.
- Les expressions passent par `animation` (StringTime, nom de séquence), comme la
  télécommande aujourd'hui.

## 2. Package `packages/didier_jeu/` (génération 2 : nœud mince, logique pure)

```
packages/didier_jeu/
├── package.xml, setup.py, setup.cfg, resource/, README.md (README-contrat)
├── config/
│   ├── reglages.yaml       # TOUS les chiffres du modèle de timing (valeurs de départ ci-dessous)
│   └── deplacements.yaml   # le vocabulaire de déplacements → commande régisseur
├── didier_jeu/
│   ├── repertoire.py   # charge : séquences (json/sequences/**, clés `types`), expressions,
│   │                   # vocabulaire de déplacements ; expose les ACTIONS candidates
│   ├── offres.py       # Offre(kind, piste, valeur, t_naissance, ttl) ; naissance depuis les
│   │                   # événements ; mort par TTL ou prise ; « ignore » les tue
│   ├── pistes.py       # pistes de personnes : identifiant stable, hystérésis d'apparition
│   │                   # (une redétection < 2 s n'est pas « nouvelle »)
│   ├── pulsions.py     # ennui, curiosité, lubie, fatigue : montée/retombée, bornes
│   ├── scores.py       # score(action, offres, pulsions, intention metteur en scène, console)
│   ├── arbre.py        # py_trees : ce qui est PERMIS quand (voir §3)
│   ├── selecteur.py    # tick(now) → Decision(action, cible, pourquoi) ou None ; engagement,
│   │                   # hystérésis, périodes réfractaires — PURE, testée sans ROS
│   ├── journal.py      # réutilise robot/diagnostic/journal.py (format boîte noire)
│   └── jeu_node.py     # I/O ROS seulement : abonnements, publications, remaps
└── test/               # valeurs GRAVÉES + mutation (muter une règle = rouge)
```

## 3. L'arbre (ce qui est permis) et le score (ce qui est choisi)

Racine = **sélecteur de priorités** py_trees :

1. **Arrêt vocal** (`stop` reçu) → relayer, tout annuler, verrou jusqu'au `go`. *Jamais pondéré.*
2. **Superviseur absent** (`jeu/console` sans battement depuis > 1 s **en mode exigeant** ;
   en A1 sim, mode « présence supposée » par défaut, réglable) → aucune initiative de
   déplacement ; expressions autorisées.
3. **Ordre macro en cours** (`va_la`, `joue_avec`, `reviens`, `ignore`, `plus_lent`) →
   l'ordre fixe la cible et un biais de score ; `ignore` tue les offres de la cible.
4. **Action engagée** → on la finit (durée de la séquence / `route_goto_result`) ; seule
   une offre de valeur ≥ `engagement.seuil_rupture` (défaut 0,9) peut l'interrompre.
5. **Choisir** : feuille de score — pour chaque action candidate du répertoire :
   `score = Σ considérations × poids` avec considérations dans [0,1] : offre dominante
   (valeur × fraîcheur), pulsion servie (curiosité → approche/regard ; ennui → expression
   spontanée ; lubie → arrêt réclamé), intention du metteur en scène (`chat_situation`
   / `mission_state` : un mot-clé d'action mappé), compatibilité avec la console, **temps
   depuis la dernière action du même type** (0 avant la période réfractaire), **aucune
   action = candidate aussi** (score de base de l'immobilité, qui baisse avec l'ennui).
   Gagne le meilleur **si** il dépasse le second de `hysteresis.marge` (défaut 15 %) pendant
   `hysteresis.duree_ms` (défaut 300 ms) ; sinon rien ne change (pas d'« hésitation » en A1 —
   elle viendra comme action explicite du répertoire, pas comme un défaut).

Règles gravées en tests (chiffres dans `reglages.yaml`, défauts = étude §4.2 et décisions
31/10 et 23/10) :

| Règle | Défaut |
|---|---|
| réaction à une offre (naissance → décision) | ≤ 1 000 ms |
| initiatives spontanées (sans offre) | ≥ 8 s entre deux |
| arrêts de route demandés par Didier (lubie) | ≥ 120 s entre deux ; **réclamé en mots ET amorcé** : publie l'intention + `regarder` (M2) et ne demande `stop` au régisseur que si la console n'a pas dit `ignore`/`va_la` dans `lubie.delai_refus_s` (défaut 3 s) |
| durée de vie d'une offre | 3 s |
| ennui | +0,1 / s sans événement, 0 à toute action, plafond 1 |
| curiosité | saute à 1 à la naissance d'une **piste** (pas d'une détection), retombe −0,2 / s |
| fatigue | +0,3 par action de déplacement, −0,05 / s ; une action de déplacement est interdite au-dessus de 0,8 |
| « pression de route » | ne monte **que** pendant un arrêt décidé par Didier (jamais après un `stop`/`off` de David), et ne fait que **proposer** de repartir (intention + mots), jamais couper |

## 4. Contrats (à mettre dans `theatre_contrats` quand L1a est livré ; d'ici là, constantes locales gravées)

| Topic | Sens | Format |
|---|---|---|
| `jeu/console` | page scène → sélecteur | StringTime JSON `{"cmd": "va_la"\|"joue_avec"\|"ignore"\|"reviens"\|"plus_lent"\|"stop"\|"go", "cible": "<piste ou objet>"?, "presence": true}` ; la page renvoie `presence` à 2 Hz tant qu'elle est ouverte (battement) |
| `jeu/intention` | sélecteur → page scène, télécommande (demain) | **latché**, JSON `{"action": "...", "cible": "...", "pourquoi": "offre:personne_proche 0.8 + curiosite 0.6", "t_ms": ..., "fin_prevue_ms": ...}` ; `{"action": "rien"}` au repos |
| `jeu/chat_move` | sélecteur → régisseur | **même payload** que `rehearsal/chat_move` aujourd'hui (le régisseur ne change pas) |
| `jeu/journal` | sélecteur → fichier JSONL (+ topic volatile pour la page) | une ligne par décision : offres vivantes, pulsions, scores des 3 meilleurs, choix, raison, et chaque refus |
| entrées lues | `vision/person_box` (scriptée en A1), `rehearsal/poi_event`, `rehearsal/chat_move` (bouche), `chat_situation`, `mission_state`, `route_state`, `route_goto_result`, `animation_state` | existants |

## 5. Page scène (robot_web, SIM-ONLY comme les boutons de répétition)

Un panneau « Jeu » : l'**intention en cours** en gros (action, cible, pourquoi, barre de
temps), six boutons macro (`va là` demande une cible : clic sur une piste listée ; `joue
avec lui` prend la piste que Didier regarde — décision 9), les jauges (ennui, curiosité,
lubie, fatigue) en barres, et les 20 dernières lignes du journal. `presence` envoyé tant que
l'onglet est visible. Whitelist du `web_bridge` : `jeu/console` en écriture, `jeu/intention`
et `jeu/journal` en lecture.

## 6. Porte de sortie (vérifiée, rejouable : `validate-jeu-a1.sh` dans le conteneur sim)

Monde `chantiers`, régisseur + chaîne roues + `didier_jeu` ; **perception scriptée** par le
script lui-même (une personne qui approche à t=60 s, reste 30 s, s'éloigne ; une seconde
qui passe vite à t=300 s ; silence ensuite) ; route ON ; 15 minutes.

| # | Épreuve | Seuil |
|---|---|---|
| T1 | zéro oscillation | aucun couple de décisions différentes à < 2 s d'intervalle (journal) |
| T2 | fréquences | aucune initiative spontanée à < 8 s de la précédente ; ≤ 1 arrêt de Didier par 120 s ; chaque arrêt précédé d'une intention publiée ≥ 3 s avant le `stop` |
| T3 | réaction | pour chaque naissance de piste : une décision en ≤ 1 s (journal) |
| T4 | console | `ignore` pendant une approche → aucune action vers cette piste pendant 30 s ; `va_la` → `aller_voir` accepté par le régisseur (`route_goto_result`) ; `stop` → Didier s'arrête en < 1 s et aucune initiative de déplacement jusqu'au `go` |
| T5 | arrêt vocal | `rehearsal/chat_move: "stop"` depuis la bouche → relayé en < 200 ms, sans passer par le score (journal : `relais_stop`) |
| T6 | lisibilité | `jeu/intention` latché n'est jamais vide plus de 1 s, et chaque ligne du journal porte un `pourquoi` non vide |
| T7 | rien ne sort du domaine 43 | le nœud refuse de démarrer hors 43 (test existant de rehearsal réutilisé) |

**Relu par David** : le journal d'une séance de 15 min, ligne par ligne — c'est là qu'il
dit si « pourquoi et quand » lui parle. La porte technique ne remplace pas cette lecture.

## 7. Hors A1

Fond permanent (A+), perception réelle (A2), corps sûr (A0), télécommande console (L4),
chiffres « artistiques » (réglage au réel). Et **la hésitation jouée** : pas un défaut du
sélecteur, une action du répertoire à composer par David.

## 8. Précisions du 02/11 (questions de l'implémenteur, tranchées avant le code)

| # | Question | Décision |
|---|---|---|
| 1 | mécanisme de la lubie | naît sur `rehearsal/poi_event` `enter` (offre `objet`, valeur 0,8, TTL 3 s) ; +0,5 par POI entré, −0,05/s, plafond 1 ; Didier « regarde » par `regarder <objet>` du régisseur (M2) ; le sélecteur ne lit pas `/ground_truth/odom` ; pas de doublon avec le scénario Chantiers → **scénario vide `jeu-a1.yaml`** |
| 2 | `va_la` vers une piste | objets de `rehearsal/objects` seulement (T4) ; une piste = `tourner` vers son azimut puis `avancer` ≤ 1 m, si superviseur présent et fatigue < 0,8 ; `joue_avec` = la piste regardée |
| 3 | reprise après un arrêt de Didier | règle du 31/10 gravée : il propose (« repartir ? ») puis envoie `go` lui-même après 90 s, sauf `stop`/`ignore` de la console ; **jamais de `go` automatique après un `stop`/`off` de David** ; le régisseur refusant `go` hors séance, A1 tourne avec un scénario vide (0 bug, 0 lubie) |
| 4 | répertoire | séquences avec clé `types`, **hors `bugs/` et hors toute séquence à piste `wheels`** (pas de corps sûr en A1 — filtre gravé) ; `deplacements.yaml` = valeurs de départ « composées par David » : approcher (avancer 1 m), se_tourner_vers (tourner), aller_voir, faire_le_tour (tour_de), reculer seulement si le régisseur accepte un `avancer` négatif |
| 5 | T3 vs engagement | toute naissance de piste → une ligne de décision en ≤ 1 s, qui peut être un **maintien** ; T1 ne compte que les changements d'action |
| 6 | les « mots » | `jeu/intention` seul en A1 |
| 7 | poids du score | dans `reglages.yaml`, valeurs de départ gravées : offre 1,0 ; pulsion 0,6 ; metteur en scène 0,8 ; console 1,5 ; réfractaire = facteur 0/1 ; immobilité = 0,3 − 0,3 × ennui |

py_trees absent de l'image sim et du venv : ajouté (Dockerfile-sim, package.xml, requirements-test).
