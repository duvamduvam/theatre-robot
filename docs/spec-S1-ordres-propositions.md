# Spec S1 — ordres et propositions (25/11/2026, révisée les 25-26/11 : règles R1 à R6)

> **Révision après la relecture adverse (25/11) et la fumée du 26/11** — elle fait foi là où
> le texte d'origine diverge ; détail au §7. R1 : le régisseur n'ignore jamais un `stop`. R2 :
> hors séance, le sélecteur ne prend aucune initiative. R3 : le verrou de David a deux genres
> (console, voix). R4 : un `stop` `didier` suspend l'ordre de David, repris après le silence.
> R5 : tests de la chaîne sélecteur → régisseur. R6 : un ordre de David part au tick, devant
> toute initiative, sans score.

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
| continuation de tâche (`_serve_continuation`, lot M4) | gestes ; `stop` ; `go` **non émis** (R3) | gestes : `david` (la tâche vient de David) ; `stop` : `didier` (le LLM décide) ; pas de `go` : la reprise du sélecteur relance après le geste |

Supprimé : le `stop` permis en tour spontané. Le metteur en scène ne passe plus jamais par un
mouvement ; les initiatives restent celles du sélecteur (lubies) jusqu'à S4.

## 2. Le sélecteur (`didier_jeu`)

**Verrou de David seul.** `relais.Verrou` perd ses deux sources : un booléen (ou un objet
équivalent) posé par un `stop` d'origine `david` (bouche ou console), levé par un `go`
d'origine `david` (console ou tour humain) — *à deux genres depuis R3 (§7) : console ou
voix*. Un `stop` d'origine `didier` ne verrouille jamais.
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

**Origine et séance (remplacé par R1, §7)** : le régisseur n'ignore JAMAIS un `stop`, séance
ou non, quelle que soit l'origine ; il retient l'origine de l'arrêt vocal en cours : un `go`
`didier` ne lève qu'un arrêt `didier`, un `go` `david` lève tout. Hors séance, il refuse
seulement les GESTES d'origine `didier` (réponse `hors_seance`) — c'est le sélecteur qui, hors
séance, ne lance aucune initiative (R2). La fin de séance et l'abort GARDENT l'arrêt vocal (le
`go` de David qui suit rend la vitesse retenue). (Le « dire avec humeur » est le lot S2,
`seance_non_lancee`.)

**Lubies du scénario coupées quand le jeu tourne** : avec `jeu:=true`, les pannes de type
`lubie` du scénario ne partent pas (`fault_skip`, raison `jeu`), un seul mécanisme de lubies
reste : celui du sélecteur. `jeu:=false` : inchangé (la fumée `validate-rehearsal-chantiers.sh`
tourne en `jeu:=false` et doit rester verte, à vérifier).

## 4. Ce qui ne bouge pas

Corps sûr, route_driver, mux, bornes ; le chemin d'arrêt d'urgence de la bouche (mot d'arrêt →
`stop` AVANT le LLM, interruption de la voix) garde sa priorité et son ordre ; un `stop` reste
toujours relayé et appliqué quel que soit le verrou, la séance ou l'origine (un arrêt n'est
jamais refusé, R1 : plus d'exception). Aucun topic de mouvement publié sur le vrai robot (domaine 42) : tout cela reste derrière
`CHAT_MOUVEMENT` et le régisseur, sim seule.

## 5. Tests exigés (valeurs gravées, pas recalculées)

1. « Un ordre de David n'est jamais annulé par la bouche » : verrou posé par `stop` `david`
   → un `stop`/`go` `didier` ne le lève pas ; un `stop` `didier` pendant un geste `david`
   ARRÊTE le corps, sans verrou, et SUSPEND l'ordre : à la reprise (D s de silence), le geste
   de David est ré-émis (origine `david`) — R4 ; un `stop` `david` entre-temps annule tout.
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

## 7. Révision des 25-26/11 (relecture adverse Fable, fumée du 26/11) — FAIT FOI

| Règle | Contenu | Où, et test qui la couvre |
|---|---|---|
| **R1** (B1, B3, M2) | Le régisseur n'ignore jamais un `stop`. Il retient l'origine de l'arrêt vocal : un `go` `didier` ne lève qu'un arrêt `didier` (`arret_de_david` sinon), un `go` `david` lève tout. Hors séance, seuls les GESTES `didier` sont refusés (`hors_seance` ; sous un arrêt de David aussi : `arret_de_david`). Fin de séance et abort GARDENT l'arrêt vocal. | `director.VoiceMove` (`hold_origine`, `geste_refuse`, `fin_de_seance`) ; `test_director.py::test_s1_7_*`, `test_s1_m2_*`, `test_director_node.py::test_s1_m2_stop_en_seance_fin_de_seance_go_de_david_il_repart`, `test_s1_geste_de_didier_refuse_hors_seance_celui_de_david_passe` |
| **R2** | Hors séance (ou état inconnu), le sélecteur ne prend aucune initiative : ni lubie, ni approche de son initiative (« joue avec » reste permis), ni reprise d'un arrêt qu'il n'a pas posé (la fin d'un geste de David). Il lit `rehearsal/state` (latché). La reprise d'un arrêt qu'il a posé (pause, stop `didier` relayé) reste permise. | `Selecteur.sur_seance`, `jeu_node` ; `test_ordres_propositions.py::test_r2_*` |
| **R3** (B2) | Verrou de David à deux genres — trois depuis la seconde relecture (ci-dessous) : `console` (STOP console), levé seulement par un GO console ; `voix` (mot d'arrêt), levé par un `go` `david` de tour humain ou un GO console. Continuation de tâche : `stop` en `didier`, `go` non émis. (Le prompt de continuation n'invitait à aucun `go` : rien à retirer.) | `Selecteur.verrou`, `RelaisSeul`, `conversation._notify_move` ; `test_go_de_la_bouche_ne_leve_pas_un_stop_de_david`, `test_r3_*`, `test_continuation_avec_*` |
| **R4** (M1) | Un `stop` `didier` pendant un geste de David (aller_voir, tour_de, avancer, tourner) arrête le corps et SUSPEND l'ordre : à la reprise, le geste est ré-émis (`david`), journal « ordre de David suspendu, repris après D s ». Un `stop` `david` entre-temps annule tout. | `Selecteur.relayer_stop`, `_reprise_due` ; `test_1_r4_*` |
| **R5** (M3) | Tests qui enchaînent le sélecteur et le vrai `VoiceMove`, séance on et off : pause-regard (il repart), geste de David hors séance (il part), stop `didier` (appliqué, puis il repart), STOP console puis go de la bouche (le verrou reste), mot d'arrêt puis go de tour humain (il repart) ; garde superviseur de la reprise ; R4 ; R2. | `test_ordres_propositions.py::test_r5_*`, `test_2_r5_la_reprise_attend_le_superviseur` |
| **R6** (fumée du 26/11, A1 T4) | Un ordre de la console (et un ordre `david` de la bouche) passe avant toute initiative (expression, lubie, approche, regard), sans score ni écart minimal entre décisions : il part au prochain tick et interrompt l'initiative en cours. Branche `ordre_macro` de l'arbre, `console.ordre_ttl_s` et gains d'ordres supprimés. | `Selecteur._ordre_console`, `_executer_ordre` ; `test_r6_*` |

Mineurs : une `pause` d'origine inconnue est un `stop` (lu `david`) ; `lire_chat_move` normalise
casse et espaces (`" STOP"` est un stop) ; `pause` émise par le sélecteur en `stop` `didier`
(c'est lui qui la relance, sinon son `go` ne lèverait pas l'arrêt au régisseur) ; codes morts
`fatigue` / `trop_tot` / `ignore` retirés de `move_task`, `gains.bouche` retiré.

### 7 bis. Seconde relecture adverse (26/11, sur e0d29ad5) — FAIT FOI

| Point | Règle | Test |
|---|---|---|
| **Bloquant** (Route OFF puis ON) | route_driver publie la cause `cmd` à chaque `off` et rien au `on` : le verrou « console » posé par R3 restait après OFF/ON (Didier roulait, refusait tout). **Troisième genre `route`** : posé par la Route OFF, levé quand `route_state` revient à `on` APRÈS avoir été vu `off` (l'ancien `on` latché ne lève rien), ou par un GO console ; jamais par un go vocal. Un STOP console posé avant garde son verrou. Les épreuves A1 et CONV ne sont pas « réparées » par un GO. | `test_bloquant_*`, `test_r3_route_off_de_david_verrou_de_la_route_le_go_vocal_ne_le_leve_pas` |
| **Majeur 1** (R4 rejouait un ordre périmé) | Tout NOUVEL ordre de David (console, n'importe lequel, ou geste de la bouche) efface l'ordre suspendu ; `_armer_reprise` qui sort sur R2 efface aussi la reprise précédente et son ordre ; âge maximal `reprise.ordre_suspendu_max_s` = 60 s depuis la suspension (au-delà : « ordre de David abandonné : trop ancien », simple go) ; la ré-émission repasse par `_hors_atteinte` et les contrôles d'un ordre neuf (refus = simple go) ; les gestes RELATIFS (`avancer`, `tourner`) ne sont jamais rejoués (« geste relatif non repris »), seuls `aller_voir` et `tour_de`. | `test_m1_*` |
| **Majeur 2** (M1 pour la console) | Tout engagement d'origine `david` est suspendu (console comprise : son étape en cours) ; un second stop `didier` pendant la suspension garde l'ordre (la reprise est re-tirée, l'ordre et son âge restent). | `test_m2_un_ordre_console_est_suspendu_et_un_second_stop_le_garde` |
| Mineur 1 | Tests ajoutés pour les mutations restées vertes : garde R3 de `RelaisSeul` (test d'origine de la revue A1 rétabli), reprise qui attend la fin d'un déplacement, `self.ordre = None` dans `relayer_stop`, désarmement R2 à la fin de séance, `_ordre_console` avant `_reprise_due`. | `test_relais_seul_go_de_la_bouche_ne_leve_pas_un_stop_de_david`, `test_mineur_*` |
| Mineur 2 (rafale R6) | Un ordre console de déplacement IDENTIQUE (même commande, même cible) reçu moins de `console.rebond_s` = 1 s après le précédent est ignoré (journal `console`, `doublon`) : un double-clic ne nourrit pas la fatigue. | `test_mineur_r6_rafale_*` |
| Mineur 3 (« reviens » pendant un geste) | Le régisseur n'annule une manœuvre que sur un `stop` (il publie `cancel` sur `route_goto`) et ne relance la route sur un `go` qu'une fois l'état sorti de `goto`. « reviens » pendant une manœuvre : le sélecteur envoie `stop` (origine `david`), puis le `go` de David quand `route_state` quitte `goto` (au plus 5 s). Le sélecteur ne publie toujours que des demandes. | `test_mineur_reviens_*` |
| Mineur 4 (respawn de `jeu_node`) | **Limite connue, sens sûr, pas de code** : un `jeu_node` relancé (respawn) perd son verrou, sa reprise et son ordre suspendu ; il relit les topics latchés (`route_state`, `route_state_cause`, `rehearsal/state`). Une cause `cmd` latchée d'une Route OFF ancienne, déjà suivie d'un ON, repose un verrou `route` qui ne tombera qu'au prochain OFF/ON ou GO console ; hors séance il ne fait rien de lui-même ; le régisseur garde l'arrêt vocal (M2). Au pire Didier reste arrêté, jamais il ne repart seul. |
