# Journal d'incidents — la mémoire de panne du robot

Chaque investigation de panne (humaine ou agent IA, skill `/diag`) se termine
par un post-mortem ici. **Même non résolue** : « cause inconnue, pistes
écartées » évite à la prochaine investigation de refaire le même chemin.
C'est le vrai « RAG » du télédiagnostic (décision du 2026-07-12,
`../etude-telediagnostic.md` §4) : le dossier est rsyncé sur le Pi avec le
reste du repo, l'agent embarqué le lira.

## Format

Un fichier par incident : `YYYY-MM-DD-symptome-court.md` (ex.
`2026-07-15-visage-fige-deambulation.md`), structure :

```markdown
# <symptôme en une phrase>

- **Date/contexte** : quand, où (représentation, répétition, atelier), quoi en cours
- **Symptôme** : ce qui a été observé, précisément
- **Traces** : tarball/extraits (chemins, lignes de log horodatées)
- **Investigation** : ce qui a été vérifié, dans l'ordre, avec les constats
- **Cause** : la cause établie — ou les hypothèses restantes, classées
- **Remède** : ce qui a été fait (et si ça a suffi)
- **Prévention** : ce qui éviterait la récidive (fix, test, procédure) — et le
  commit si un correctif a été poussé
```

Court et factuel : 15-30 lignes suffisent. Le but est d'être **cherchable par
symptôme** par le prochain investigateur.
