<!-- généré par IAction — NE PAS ÉDITER : mis à jour à chaque tour -->

# Outils MCP disponibles dans ce projet

État constaté au dernier tour lancé depuis IAction (2026-11-01T23:51:26.052Z). Liste vérifiée, pas déclarative : ce qui est listé ici répond.

## claude_ai_Claude_Docs — connected

- `mcp__claude_ai_Claude_Docs__batch`
- `mcp__claude_ai_Claude_Docs__create`
- `mcp__claude_ai_Claude_Docs__delete`
- `mcp__claude_ai_Claude_Docs__export`
- `mcp__claude_ai_Claude_Docs__guide`
- `mcp__claude_ai_Claude_Docs__query`
- `mcp__claude_ai_Claude_Docs__read`
- `mcp__claude_ai_Claude_Docs__update`

## iaction — connected

- `mcp__iaction__search_chat`
- `mcp__iaction__search_knowledge`
- `mcp__iaction__session_distante_demander`
- `mcp__iaction__sessions_distantes_lister`

## studio — connected

- `mcp__studio__ask_user`

Serveurs déclarés sans aucun outil exposé : claude.ai Claude Docs (connected), claude.ai WordPress.com (needs-auth). Ne pas compter dessus.

## Règle : source avant mémoire

Quand une question porte sur une donnée servie par l'un de ces outils
(mails, base de pilotage, dossier distant…), l'interroger AVANT de répondre —
y compris quand la mémoire ou le RAG semblent déjà contenir la réponse : un
index est une copie, il périme ; l'outil, non. Si l'outil est indisponible,
le dire explicitement au lieu de répondre de mémoire.
