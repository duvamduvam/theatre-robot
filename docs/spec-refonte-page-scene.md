# Spec — refonte de la page scène (`/scene`)

Écrite le 12/11/2026 (Fable), à exécuter par Opus. Demande de David : « c'est le bordel
actuellement ». Périmètre : **la présentation de la page scène seulement**. Aucun changement de
protocole, de topic, de pont (`web_bridge_node.py`) ni de la console de régie (`/`).

Capture de l'état de départ : `docs/pictures/page-scene/avant-1600.png`.

## 1. Ce qui ne va pas (constat sur la capture, 1600 × 1400)

1. **Rien ne tient dans l'écran.** Les trois vidéos sont empilées en pleine largeur de colonne :
   la page fait environ 2 000 px de haut, « Ce que Didier voit » est sous la ligne de flottaison.
2. **Le panneau Jeu mange le haut de page** : cinq jauges étirées sur 1 000 px pour afficher
   « 0.00 », un grand vide à droite des ordres, et les vidéos repoussées vers le bas.
3. **La barre de commandes n'a aucune hiérarchie** : 16 pastilles identiques sur deux lignes,
   les réglages d'avant séance (personnalité, webcam, source) au même rang que ce qui sert
   pendant le jeu. Chaque groupe traîne un badge « — » orphelin.
4. **STOP a le même poids visuel que « Ignore »**, et il est à l'endroit le moins prévisible.
5. **La conversation**, qui est ce que David lit en jouant, est une colonne parmi trois, coincée
   sous un tableau « Oreille » ouvert en permanence.
6. **Des réglages permanents** qui ne servent qu'une fois : l'adresse du flux visage.
7. **Les erreurs** sont en pied de page, hors écran.

## 2. Principe

Une page = **un poste de jeu**, lu d'un coup d'œil, sans défilement sur un écran de bureau.
Trois zones, par fréquence d'usage :

| Zone | Contenu | Quand |
|---|---|---|
| **Préparer** (rail gauche, étroit) | Parole, Personnalité, Vision, Route, Séance | avant de jouer |
| **Regarder + diriger** (centre, large) | une grande vue + vignettes ; dessous, le Jeu | pendant |
| **Écouter + souffler** (droite) | fil de conversation, saisies, Oreille repliée | pendant |

```
┌ bandeau : Didier · scène | SIMULATION | connecté | main | ⚠ 2 | [ticket…] ┐
├ PRÉPARER ──┬ VUE PRINCIPALE ─────────────┬ vignettes ┬ CONVERSATION ──────┤
│ Parole     │                             │ visage    │ fil (prend toute   │
│ Personnal. │   (extérieur par défaut)    │ caméra    │ la hauteur)        │
│ Vision     │                             │ perception│                    │
│ Route      ├─────────────────────────────┴───────────┤ [souffler…]        │
│ Séance     │ JEU : action → cible · pourquoi · ▓▓▓░  │ [consigne…] Lever  │
│            │ [Va là ▾][Joue][Ignore][Reviens][Lent]  │ ▸ Oreille de Didier│
│            │ jauges compactes        [ GO ] [ STOP ] │                    │
└────────────┴─────────────────────────────────────────┴────────────────────┘
```

## 3. Décisions (ne pas re-trancher en implémentant)

- **D1 — Grille plein écran.** `body.scene-page` en grille `100dvh` : bandeau, puis trois
  colonnes `minmax(200px, 240px) | 1fr | minmax(320px, 400px)`. À 1600 × 1000 et 1280 × 800,
  **aucun défilement de page** ; seuls le fil de conversation, le journal du jeu et l'Oreille
  défilent à l'intérieur de leur boîte.
- **D2 — Une vue principale, les autres en vignettes.** Les quatre flux (extérieur, caméra de
  Didier, perception, visage) gardent leurs `<img>` et leurs ids. Un clic sur une vignette la
  **promeut** en vue principale (échange de classes CSS, pas de rechargement de flux) ; le choix
  est mémorisé (`localStorage`, clé `sceneVuePrincipale`). Défaut : extérieur s'il est annoncé,
  sinon caméra de Didier. Une vignette masquée par le serveur (`hidden`) qui était principale
  rend la main au défaut. Le visage reste **toujours visible** (vignette ou principale).
- **D3 — ON/OFF en contrôle segmenté, pas en interrupteur.** Les paires gardent deux boutons
  distincts (`data-topic`/`data-value` inchangés) collés en un seul contrôle ; le segment allumé
  est l'ÉTAT RÉEL (`surlignerGroupe`, inchangé). Raison : l'état arrive avec 2 s de retard, un
  interrupteur enverrait l'inverse de ce qu'on veut (même raison que STOP/GO distincts, revue
  A1). Le badge d'état passe **dans l'en-tête du groupe**, à droite du titre ; il n'affiche plus
  « — » quand il n'y a rien à dire (vide = masqué en CSS via `:empty` ou classe).
- **D4 — STOP est unique en son genre.** Rouge plein (`--stop`), plus grand, toujours au même
  endroit (coin bas droit du panneau Jeu), séparé des ordres macro. GO à côté, neutre.
- **D5 — Jeu compact.** Une ligne d'intention (action en gros, cible, pourquoi sur une ligne
  tronquée avec `title`), barre de temps, ordres, puis les cinq jauges en **une rangée de
  mini-barres** (libellé au-dessus, valeur en `title`). Le journal « pourquoi » passe dans un
  `<details>` replié par défaut (« Journal du jeu »).
- **D6 — Oreille repliée par défaut** (`<details>` sans `open`), placée SOUS les saisies. Son
  badge moteur reste visible dans le `summary`.
- **D7 — Adresse du flux visage derrière un bouton ⚙** sur la tuile visage (le formulaire
  `scene-form-visage` garde ses ids, il est simplement masqué tant qu'on n'a pas cliqué).
- **D8 — Erreurs dans le bandeau.** Le `<footer>` devient un `<details>` du bandeau : compteur
  « ⚠ n » (masqué à 0), la liste `#journal-erreurs` s'ouvre en panneau flottant. Si `commun.js`
  doit exposer le compte, le faire par un `MutationObserver` dans `scene.js` — **ne pas modifier
  `commun.js`** (partagé avec la régie).
- **D9 — Téléphone et tablette (< 900 px).** Une colonne, dans cet ordre : bandeau (ticket
  replié derrière un bouton), vue principale + vignettes en bande horizontale, Jeu,
  Conversation, Préparer (dans un `<details>`). **STOP collé en bas de l'écran**
  (`position: sticky`) tant que le panneau Jeu est affiché.
- **D10 — CSS de la scène dans son fichier.** Sortir de `style.css` tout ce qui est `.scene-*`
  et `.jeu-*` (lignes ≈ 538-729) vers un nouveau `static/scene.css`, chargé après `style.css`
  par `scene.html` seulement. Les jetons (`:root`) et les classes communes (`.badge`, `.carte`,
  `.bouton-catalogue`, `.video-wrap`…) restent dans `style.css`, **non modifiés** : la régie ne
  doit pas bouger d'un pixel. Couleurs en dur de la scène (`#2e7d32`, `#b26a00`, `#999`) →
  jetons existants ou nouveaux jetons déclarés en tête de `scene.css`.

## 4. Invariants (une régression ici est un échec du lot)

- **Tous les ids et tous les `data-topic` / `data-value` / `data-jeu` existants sont conservés.**
  `scene.js` et `commun.js` les adressent ; les tests aussi.
- **La page n'affiche jamais plus qu'aujourd'hui** : ni pannes, ni consigne du régisseur, ni
  vitesse relue. Aucun nouvel appel `valeurTopic(msg.topics, …)` (test
  `test_scene_ne_lit_que_les_topics_d_etat_publics`).
- **Masquages de sécurité intacts** : `.scene-repetition` masqué hors `hello.rehearsal`,
  extérieur et perception masqués tant que le serveur ne les annonce pas, commandes désactivées
  sans la main (le sélecteur de `liaison.surLiaison` doit continuer à attraper tous les contrôles).
- **STOP et GO restent deux boutons.** Le battement `presence` à 2 Hz n'est pas touché.
- Vanilla JS, zéro dépendance, aucun CDN, aucun build. `setup.py` prend déjà `glob('static/*')`.
- Aucun accès aux roues par cette page (inchangé).

## 5. Lots (un commit chacun, dans l'ordre)

| Lot | Contenu | Fichiers |
|---|---|---|
| **S1** | D10 : extraction de `scene.css`, zéro changement visuel. Preuve : captures avant/après identiques. | `style.css`, `scene.css`, `scene.html` |
| **S2** | D1, D3, D4, D5, D6, D7, D8 : nouvelle structure HTML + grille bureau. | `scene.html`, `scene.css`, `scene.js` (⚙, compteur d'erreurs) |
| **S3** | D2 : vue principale et vignettes. | `scene.html`, `scene.css`, `scene.js` |
| **S4** | D9 : mise en page étroite + STOP collant. | `scene.css` |
| **S5** | Doc : `docs/operations.md` (description de la page scène), README de `didier_web`, ligne de `docs/chantiers.md`, captures « après ». | docs |

## 6. Vérification (à chaque lot)

Sim « Chantiers » lancée (`docs/operations.md`, section Séance « Chantiers »). Les fichiers
statiques sont installés par colcon : après une modification,
`docker exec dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && cd /home/ros2_ws && colcon build --packages-select didier_web'`
puis recharger la page (le pont sert les fichiers à chaque requête).

1. **Tests** : `cd packages/didier_core && ../../.venv/bin/python -m pytest -q -o addopts= test/unit/test_web_protocol.py` — verts.
2. **Captures** (Chromium sans fenêtre, sortie sous `$HOME`, pas `/tmp` : c'est un snap) :
   ```bash
   env -u LD_LIBRARY_PATH chromium --headless=new --disable-gpu --hide-scrollbars \
     --window-size=1600,1000 --virtual-time-budget=10000 \
     --screenshot=$HOME/scene-shots/apres-1600.png http://localhost:8765/scene
   ```
   aux tailles **1600 × 1000**, **1280 × 800**, **390 × 844**. Les regarder (outil Read), puis
   copier les finales dans `docs/pictures/page-scene/`.
3. **Pas de défilement de page** à 1600 × 1000 et 1280 × 800 :
   `document.documentElement.scrollHeight <= innerHeight` (via `--dump-dom` + script, ou à la main).
4. **Console JS sans erreur** au chargement.
5. **À la main, avec la main prise** (David ou l'agent si Chrome est branché) : chaque bouton
   s'allume sur l'état réel ; « Souffler » fait apparaître la réplique ; STOP arrête ; clic sur
   une vignette l'agrandit et le choix survit à un rechargement.
6. **La régie `/` n'a pas changé** : capture avant/après de `http://localhost:8765/` identique.

## 7. Hors périmètre

- La console de régie (`index.html`, `app.js`) — même si elle mérite sans doute le même
  traitement, c'est un autre lot.
- Tout nouveau contenu (carte du trajet, courbe des jauges, etc.) : cette refonte range, elle
  n'ajoute rien.
- L'éditeur en pistes (`docs/chantiers.md`) : il aura sa page.
