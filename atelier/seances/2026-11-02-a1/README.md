# Séance A1 du 2026-11-02 — première séance du sélecteur de jeu (sim, scénario vide `jeu-a1`)

15 minutes, monde `chantiers`, perception SCRIPTÉE par `validate-jeu-a1.sh` (une personne
qui approche à t=60 s, une seconde qui passe à t=300 s), route ON, console = page scène.
Résultat technique : 13 OK / 0 KO (T1-T7).

**À lire par David, ligne par ligne** (spec A1 §6) : `*_jeu.jsonl` = une ligne par
décision du sélecteur — offres vivantes, jauges (ennui, curiosité, lubie, fatigue), les trois
meilleurs scores, le choix et son `pourquoi`. C'est là qu'on dit si « pourquoi et quand
Didier agit » parle, et quels potards de `packages/didier_jeu/config/reglages.yaml` tourner.
Les autres fichiers : journal du régisseur, sorties des deux scripts de vérification.
