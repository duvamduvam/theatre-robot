# Spec S1 — ordres et propositions (25/11/2026)

Lot S1 de l'étude d'assainissement (`docs/etudes/etude-assainissement.md` §4 règles 1-2, §5,
§6, réponses de David §8.1, rôles §8 bis). Sim seule (domaine 43). Corrige les problèmes 3, 4,
10, 11 et 13 de la séance du 24/11 (`docs/seances/2026-11-24-seance-sim-a05.md`).

## 0. En une phrase

Chaque demande de marche porte son **origine** : `david` (un ordre) ou `didier` (une
proposition). Seul David pose et lève le verrou ; ce que Didier arrête, il le relance seul
après un silence de 10 à 40 s ; la bouche ne décide plus aucun mouvement en tour spontané.

## 1. Origine d'une demande (contrat `rehearsal/chat_move` et `jeu/chat_move`)

Payload JSON, nouvelle forme pour la marche : `{"cmd": "stop"|"go"|"pause", "origine":
"david"|"didier"}`. Les gestes (`aller_voir`, `tourner`, `avancer`, `tour_de`) gagnent le même
champ `origine`. Les anciennes formes (chaîne `"stop"`, `"go"`, `"pause"`, dict sans
`origine`) restent ACCEPTÉES par les consommateurs, lues comme `origine: "david"` (sens sûr
pour un stop : il verrouille). Constantes gravées dans `didier_rehearsal/contracts.py`
(`CHAT_MOVE_ORIGINES = ("david", "didier")`), documentées à côté de `CHAT_MOVE_TOPIC`.

Qui émet quoi (la bouche, `didier_vision.ai.conversation`) :

| Cas | Émis | Origine |
|---|---|---|
| mot d'arrêt reconnu par le STT (`emergency.py`), écoute normale ou garde | `stop` | `david` |
| tour humain, clé `marche: go`, ou un geste (`avancer`, `aller_voir`…) | `go` / geste | `david` (la bouche transmet ce que David a demandé) |
| tour humain, clé `marche: stop` (le LLM interprète) | `stop` | `didier` (réponse 1 du §8.1 : pas de verrou, il repart seul) |
| tour humain, clé `marche: pause` (« regarde ça ») | `pause` | `david` |
| **tour spontané** | **rien** : toute clé de marche ou de geste est ignorée et journalisée (« tour spontané : la bouche ne décide aucun mouvement », §8 bis) | — |
| continuation de tâche (`_serve_continuation`, lot M4) | comme aujourd'hui | `david` (la tâche vient de David) |

Supprimé : le `stop` permis en tour spontané. Le metteur en scène ne passe plus jamais par un
mouvement ; les initiatives restent celles du sélecteur (lubies) jusqu'à S4.

## 2. Le sélecteur (`didier_jeu`)

**Verrou de David seul.** `relais.Verrou` perd ses deux sources : un booléen (ou un objet
équivalent) posé par un `stop` d'origine `david` (bouche ou console), levé par un `go`
d'origine `david` (console ou tour humain). Un `stop` d'origine `didier` ne verrouille jamais.
Un `go` d'origine `didier` n'existe pas en S1 (la bouche n'en émet plus) ; s'il arrive, il est
ignoré et journalisé.

**Un ordre n'est refusé que pour trois raisons**, renvoyées sur `chat_move_reply` comme
aujourd'hui : `arrete` (verrou de David posé, pour un geste autre que `go`), sécurité (corps
sûr : déjà dit par le régisseur/route_driver), impossible (`pas_ici`, `hors_atteinte`,
`inconnu` : objet absent ou trop loin). `fatigue`, `trop_tot`, `pas_retenu`, `ignore` ne
s'appliquent PLUS à une demande d'origine `david` : elle part tout de suite (elle reste une
« ordre en cours » pour le score, qui ne l'interrompt pas). Les codes restent dans le contrat
s'ils servent encore aux propositions. Les refus « qui donnent du jeu » (§8.1, réponse 2 :
dits, jamais sur un stop, la deuxième demande passe) ne sont PAS dans S1 : ils reviennent avec
le régisseur LLM (S4), seul à pouvoir les dire. À noter dans le code et dans la PR.

**Une seule reprise.** Les trois minuteries (`reprise.apres_geste_s` 10 s, `reprise.
apres_regard_s` 6 s, `reprise.delai_s` 90 s) deviennent une règle : après un arrêt décidé par
Didier (lubie, `stop` d'origine `didier`, fin de pause-regard, fin de geste), il repart seul
après `D` secondes de SILENCE, `D` tiré au moment de l'arrêt dans `[reprise.min_s,
reprise.max_s]` = `[10, 40]` (réglages ; tirage par le générateur aléatoire déjà semé du
sélecteur, journalisé : « il repartira après 23 s de silence »). Une parole de quelqu'un remet
le compte de silence à zéro (règle du 02/11 gardée), sans retirer le tirage. Arrêt posé par
David : jamais de reprise seule (règle du 31/10). Route OFF / fader : inchangé (traité comme
David). Supprimer les réglages devenus morts, et le code des trois chemins de reprise au profit
d'un seul.

**Mots-clés du metteur en scène supprimés** : `Selecteur.sur_situation`, le chemin
`sur_mission` → `indication`, le réglage `metteur_en_scene.mots_cles` et leurs abonnements dans
`jeu_node` s'ils ne servent qu'à ça (étude improvisation : « fragile, sans identifiant ni
retour »).

**Mode dégradé (`RelaisSeul`)** : mêmes règles d'origine (verrou de David seul ; stop `didier`
relayé sans verrou ni reprise : sens sûr, il reste arrêté jusqu'à un go de David).

`jeu/chat_move` (sélecteur → régisseur) porte l'origine de la demande d'où vient l'ordre ; les
reprises et lubies du sélecteur sont `didier`.

## 3. Le régisseur (`didier_rehearsal/director.py`, `VoiceMove`)

**Règle séance symétrique** (réponse 4 du §8.1, re-tranchée) : hors séance, une demande
d'origine `didier` est ignorée, qu'elle soit `stop` ou `go` (`hors_seance`, journalisée) ; une
demande d'origine `david` est APPLIQUÉE (stop et go) : hors séance, Didier suit sa route et
t'obéit. En séance : comme aujourd'hui. (Le « dire avec humeur » est le lot S2,
`seance_non_lancee`.)

**Lubies du scénario coupées quand le jeu tourne** : avec `jeu:=true`, les pannes de type
`lubie` du scénario ne partent pas (`fault_skip`, raison `jeu`), un seul mécanisme de lubies
reste : celui du sélecteur. `jeu:=false` : inchangé (la fumée `validate-rehearsal-chantiers.sh`
tourne en `jeu:=false` et doit rester verte, à vérifier).

## 4. Ce qui ne bouge pas

Corps sûr, route_driver, mux, bornes ; le chemin d'arrêt d'urgence de la bouche (mot d'arrêt →
`stop` AVANT le LLM, interruption de la voix) garde sa priorité et son ordre ; un `stop` reste
toujours relayé quel que soit le verrou ou la séance (un arrêt n'est jamais refusé) — sauf la
seule exception voulue : hors séance, un `stop` d'origine `didier` est ignoré (Didier suit sa
route). Aucun topic de mouvement publié sur le vrai robot (domaine 42) : tout cela reste derrière
`CHAT_MOUVEMENT` et le régisseur, sim seule.

## 5. Tests exigés (valeurs gravées, pas recalculées)

1. « Un ordre de David n'est jamais annulé par la bouche » : verrou posé par `stop` `david`
   → un `stop`/`go` `didier` ne le lève pas ; un geste `david` en cours n'est pas interrompu
   par un `stop` `didier`… **attention** : un `stop` `didier` ARRÊTE quand même le corps (un
   arrêt est toujours sûr) mais ne pose pas de verrou et la reprise s'arme.
2. « Ce que Didier arrête, il le relance » : `stop` `didier` → aucune reprise avant `D` s de
   silence, `go` émis à `D` (graine fixée → `D` gravé) ; une parole remet le silence à zéro.
3. `stop` `david` → aucune reprise, jamais, jusqu'au `go` `david`.
4. Ordre `david` jamais refusé pour fatigue/trop_tot/pas_retenu (pulsions poussées au maximum).
5. Tour spontané : aucune émission sur `on_move`, quelles que soient les clés.
6. Mot d'arrêt : `stop` `david` émis avant tout appel LLM (test existant, origine ajoutée).
7. Régisseur hors séance : `didier` ignoré (stop et go), `david` appliqué (stop et go).
8. `jeu:=true` : lubies du scénario en `fault_skip` raison `jeu`.
9. Anciennes formes (chaîne `"stop"`) lues comme `david`.

Épreuves sim à réécrire si elles testent l'ancien comportement : `validate-jeu-a1.sh`,
`validate-conversation.sh` (A1 et CONV), au moins sur les cas ci-dessus. `bash -n`.

## 6. Ce que ça supprime

Relais « sans arbitrage » de la bouche ; verrou à deux sources ; `stop` en tour spontané ; refus
muets opposés à un ordre ; trois minuteries de reprise ; lubies en double ; mots-clés du metteur
en scène ; asymétrie `hors_seance`. Documentation à mettre à jour dans le même lot :
`docs/spec-A1-selecteur-de-jeu.md` (renvoi vers cette spec là où elle est dépassée),
`docs/chantiers.md`, README des packages touchés, étude §6 (S1 : fait).
