<!-- généré par IA Studio — NE PAS ÉDITER : mis à jour automatiquement -->

# IA Studio — guide d'intégration du projet

Ce projet est ouvert dans **IA Studio** (app de bureau de chat/agents
multi-fournisseur). Ce fichier décrit le contrat entre l'app et le projet :
ce qu'elle lit ici, ce qu'elle expose aux agents, et comment ajouter une
capacité — sans jamais avoir besoin de lire le code source d'ia-studio.

## Ce qu'IA Studio lit dans le projet

- `CLAUDE.md` — instructions projet du moteur Claude (chargées à chaque tour).
- `.claude/` — réglages locaux (`settings.local.json`), skills du projet
  (`.claude/skills/`), mémoire agent (`.claude/memory/*.md`). Les skills et
  réglages GLOBAUX (`~/.claude/`) ne sont PAS hérités (isolation par projet).
- `.mcp.json` — serveurs MCP du projet (stdio ou http), chargés par le moteur
  projet. Jamais en mode « chat pur » (page Chat, aucun outil).
- `.iadadou/` — dossier d'IA Studio dans le projet :
  - `project.json` : identité du projet dans l'app ;
  - `connaissances/` : documents sources du RAG local (« Automatiques ») —
    fichiers texte/markdown, les liens symboliques sont suivis, > 1 Mo ignoré ;
  - `connaissances-index/` : index d'embeddings GÉNÉRÉ (chunks.jsonl +
    meta.json) — ne pas éditer, ne pas committer (gitignoré).

## Ce qu'IA Studio expose aux agents du projet

- **RAG local** : quand l'index existe, l'outil MCP
  `mcp__iadadou__search_knowledge` (serveur in-process `iadadou`) répond aux
  recherches sémantiques sur les connaissances du projet. Sources indexées :
  documents épinglés dans le panneau Connaissances, `.iadadou/connaissances/`,
  `CLAUDE.md`, `.claude/memory/*.md`. Embeddings locaux via Ollama
  (`nomic-embed-text` par défaut). Indexation : panneau Connaissances.
- **Moteurs** : Claude (abonnement ou clé API) et moteur neutre
  (Ollama local / OpenRouter), avec routage automatique possible.
- **Orchestration** : enchaînements d'étapes multi-agents (page Orchestration),
  chaque étape pouvant cibler un moteur/modèle différent. Définis PAR FICHIERS
  dans le projet (voir ci-dessous) : un agent du projet peut donc en créer.
- **Tâches de fond** : un tour dont le modèle a fini mais dont des tâches de
  fond (commandes longues, sous-agents) vivent encore reste ouvert pour
  recevoir leurs rapports — plafonné (10 min par défaut), bouton « Rendre la
  main » dans l'UI pour clore sans attendre.

## Ajouter une capacité au projet

- **Un outil autonome** (serveur, script, API) → le déclarer dans
  `.mcp.json` ; préférer un outil générique par-projet plutôt que codé en dur.
- **De la connaissance** (docs de référence, notes) → déposer ou symlinker des
  `.md` dans `.iadadou/connaissances/` puis relancer l'indexation.
- **Un savoir-faire agent** (workflow outillé, checklist) → un skill dans
  `.claude/skills/`.
- **De la mémoire durable** → `.claude/memory/*.md` (indexée dans le RAG).
- **Un agent réutilisable** (rôle nommé pour l'orchestration) →
  `.iadadou/agents/<nom>.yaml` :

  ```yaml
  name: relecteur            # [a-z0-9-], unique
  description: Relit les pages et signale les problèmes.
  engine: claude             # claude | neutral | auto (routeur)
  provider: null             # neutral : ollama, openrouter…
  model: claude-fable-5      # ou qwen3:8b, etc. (null en auto)
  permissionMode: default    # default | acceptEdits | plan | bypassPermissions
  instructions: |
    Tu es relecteur. Réponds en français.
  mcp: true                  # hérite du .mcp.json du projet
  maxTurns: 12
  ```

  (Les `.claude/agents/*.md` de Claude Code sont aussi visibles, en lecture
  seule.)
- **Un enchaînement d'orchestration** (visible et lançable dans l'onglet
  Orchestration) → `.iadadou/orchestrations/<nom>.yaml` :

  ```yaml
  name: revue-docs
  description: Contrôle puis synthèse.
  inputs:                    # variables demandées au lancement
    - name: cible
      label: "Page ou dossier à contrôler"
      default: ""            # utilisé si non fourni (chaîne vide permise) ;
                             # sans default, l'input est REQUIS — une tâche
                             # planifiée échouerait au lancement
  steps:
    - id: controle
      agent: relecteur       # nom d'agent (projet, puis global)
      task: "Contrôle {{cible}} et liste les problèmes."
    - id: synthese
      agent: relecteur
      needs: [controle]      # DAG par dépendances
      task: "Synthétise : {{steps.controle.output}}"
  limits:
    maxParallel: 2
    maxDurationMin: 30
  ```

  Portée globale possible (tous projets) dans
  `~/.config/net.duvam.ia-studio/agents/` et `orchestrations/` ; en cas de
  collision de nom, le projet gagne.
- **Une tâche récurrente** (exécution planifiée d'une orchestration) : un
  agent PEUT la créer en écrivant le manifeste
  `~/.config/net.duvam.ia-studio/taches/<nom>/tache.yaml` — c'est la SEULE
  écriture autorisée hors du projet (zone de contrat de l'app), et
  UNIQUEMENT avec `enabled: false` : l'armement du timer systemd reste un
  acte de l'utilisateur (bascule « Armée » dans la page Orchestration, où la
  tâche apparaît dès le fichier écrit). Format :

  ```yaml
  name: revue-hebdo            # [a-z0-9-], = nom du dossier
  description: Revue hebdomadaire de la doc.
  orchestration: revue-hebdo   # nom d'orchestration
  schedule: "Mon *-*-* 08:00"  # OnCalendar systemd
  inputs: {}                   # gabarit {{today}} disponible
  report: rapports/{{today}}.md
  enabled: false               # TOUJOURS false — l'utilisateur arme dans l'app
  cwd: /chemin/absolu/du/projet  # fait résoudre l'orchestration dans le repo
  ```

  Poser l'orchestration versionnée dans `.iadadou/orchestrations/` du
  projet et la référencer via `cwd`. Faire aussi écrire le rapport dans le
  repo par la dernière étape de l'orchestration le rend versionnable et
  interrogeable.

## Règles

- Le projet ne doit JAMAIS dépendre du code d'ia-studio (chemins, imports) :
  le contrat, c'est ce fichier + les emplacements ci-dessus.
- Ce fichier est déposé et mis à jour par IA Studio. Pour le compléter,
  utiliser un autre fichier de `connaissances/` — toute édition ici sera
  écrasée à la prochaine mise à jour de l'app.
