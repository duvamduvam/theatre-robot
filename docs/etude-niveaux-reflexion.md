# Étude — Niveaux de réflexion : parler du tac au tac ET analyser (caméra, mouvement, instructions)

> **Statut : CODE FAIT le 2026-10-23** (vision 640f270 : N1-N4 + I0, revue
> adversariale corrigée, banc réel + test de fumée ROS) — **reste la séance
> avec David**. 4 décisions de David le même jour (§10, ne pas re-trancher). Le §3 bis (faire avancer l'histoire) est né de
> sa réponse. Les chiffres du §1 sont MESURÉS
> (bancs OpenRouter du 22-23/10), pas estimés.

## 0. La question

David, 23/10 : *« j'ai besoin de différents niveaux de réflexion : une
réflexion courte, du tac au tac, pour la parole, mais ça doit aussi analyser
la caméra, le mouvement, les instructions que je donne. Comment allier les
deux ? »*

La tension est réelle : depuis la bascule Haiku 5.5 du 22/10
(`dadou_vision_ros` a79b481), la parole tourne **réflexion coupée** — c'est ce
qui la rend rapide, et c'est aussi ce qui l'empêche de « penser ». Un seul
appel LLM ne peut pas être à la fois réflexe et réfléchi.

## 1. Ce que coûte chaque niveau — mesuré

Banc : persona « bougon » réelle (`compose_system_prompt`), image caméra
640×480 JPEG (~45 Ko), 3 à 4 essais par ligne, via OpenRouter depuis le PC
d'atelier (fibre). TTFT = délai avant le premier mot de texte.

| Usage | Configuration | TTFT | Durée totale | Coût / appel |
|---|---|---|---|---|
| Réplique (texte) | Haiku 5.5, réflexion coupée | **0,62-1,20 s** | 1,3-1,9 s | ~0,00023 $ |
| Réplique (texte) | Haiku 4.5 (ancien réglage) | 0,91-1,38 s | 2,0-2,5 s | ~0,0017 $ |
| Réplique (texte) | Sonnet 5.5, effort `low` | **0,61-0,73 s** | 1,9-2,0 s | ~0,0045 $ |
| Réplique **+ image** | Haiku 5.5, réflexion coupée | 1,43-2,21 s | 3,5-3,9 s | ~0,00034 $ |
| Analyse de scène JSON + image | Haiku 5.5, réflexion coupée | 1,3-2,4 s | 3,3-4,0 s | ~0,00022 $ |
| Analyse de scène JSON + image | Haiku 5.5, effort `medium` | 5,9-6,8 s | 5,9-6,8 s | ~0,00035 $ |
| Analyse de scène JSON + image | Sonnet 5.5, effort `medium` | 1,7-3,3 s | 5,0-6,5 s | ~0,0050 $ |
| Réplique | Haiku 5.5 réflexion par défaut, max_tokens 200 | **∞ (réponse vide)** | — | — |

Trois leçons :

1. **Une image sur le chemin de la parole coûte ~1 s de plus** au premier mot.
   C'est exactement la marge qu'on vient de gagner — on ne la rend pas.
2. **La réflexion coûte 3 à 6 s.** Incompatible avec la cible < 2 s de la
   parole (étude déclenchement), parfaitement acceptable pour une analyse de
   fond qui tourne À CÔTÉ.
3. **Sonnet 5.5 en effort `low` parle aussi vite que Haiku** sur une réplique
   simple (il ne réfléchit pas, 0 token de réflexion), pour ~20× le prix
   (~0,45 $ les 100 répliques — négligeable). Mais sa réflexion **ne se coupe
   pas** (doc Anthropic : `thinking.disabled` non supporté sur Sonnet 5.5) :
   sur une phrase qu'il juge difficile, il peut se mettre à réfléchir et
   prendre des secondes. Latence imprévisible = défaut grave pour la parole.

Et un constat sur l'existant, découvert en lisant I1 : **le « stop » vocal
passe par le LLM**, sous la clé `"marche": "stop"` du JSON **de fin** de
réplique. L'ordre n'existe donc qu'après la génération complète de la
réplique (+1,3 à 1,9 s après la transcription), elle-même après le STT
(3,6-5,2 s sur la Pi 5 en `base`). Un « arrête ! » met ~5-7 s à agir.

## 2. Le principe : trois boucles, trois cadences, qui ne s'attendent jamais

C'est l'architecture classique des robots sociaux et des jeux vidéo (réflexes
/ comportement / délibération), et c'est déjà, sans le nom, celle de Didier
côté roues. La règle d'or : **la boucle rapide n'attend jamais la boucle
lente ; la boucle lente écrit, la boucle rapide lit.**

| Boucle | Cadence | Qui | Ce qu'elle fait | Existe ? |
|---|---|---|---|---|
| **0 — Réflexes** | ms, 16-20 Hz | code déterministe, AUCUN LLM | deadman, twist_mux, télécommande prio 100, `person_tracker` MediaPipe, gaze, follow_control, **ordres vocaux d'arrêt** | oui (sauf l'arrêt vocal déterministe) |
| **1 — Parole** | < 1 s au 1er mot | Haiku 5.5, réflexion coupée, **texte seul** | répliques, émotions, didascalies, intentions simples (`marche`) | oui |
| **2 — Réflexion** | toutes les 3-10 s, ou sur événement | LLM AVEC réflexion, **avec image** | comprendre la scène, les instructions longues de David, proposer du jeu, tenir la mission | **non** |

Personne ne commande les roues depuis un LLM — ni boucle 1 ni boucle 2. Les
deux ne font que **proposer des intentions** au régisseur (aujourd'hui, en
répétition) / à l'exécutif (demain, en rue), qui les filtre par liste blanche
et ne passe jamais au-dessus d'un `off` de David ni de la télécommande. C'est
le contrat I1 déjà en place, généralisé.

## 3. Le point de jonction : le tableau de situation

**Réponse directe à « comment allier les deux » :** la boucle 2 tient à jour
un **tableau de situation** — un court texte structuré, publié sur un topic
latché — et la boucle 1 le relit **à chaque tour, sans l'attendre**. La parole
garde son TTFT de 0,7-1 s ; elle parle simplement avec ce que la réflexion a
compris *jusqu'à il y a quelques secondes*.

Le mécanisme existe déjà à 90 % : c'est `extra_system` de `StreamingBrain`
(lot R3), alimenté par `StageState.instruction()` avec péremption. Le tableau
de situation est une **deuxième source** du même tuyau :

```text
[Situation, il y a 4 s] Deux personnes devant toi ; David à ta gauche, un
enfant au centre qui te montre un ballon rouge. Vous êtes arrêtés devant la
boulangerie. David t'a demandé tout à l'heure de trouver quelqu'un qui
connaît le chemin du Titan : personne n'a encore répondu.
```

Règles du tableau (à graver en tests) :

- **Daté et périmé** : chaque entrée porte son âge ; au-delà d'un TTL (ex.
  15 s), elle disparaît du prompt. Une vieille vision du monde est pire
  qu'aucune (Didier parlerait d'un enfant parti depuis 30 s).
- **Court** : ≤ ~80 mots. Chaque token d'entrée rallonge la boucle 1.
- **Jamais historisé** dans ChatDB (même règle que `extra_system` aujourd'hui).
- **Deux auteurs, un format** : la boucle 0 (comptage MediaPipe, position de
  David, état de route) y écrit **sans LLM** ; la boucle 2 y ajoute le sens.
  Le tableau a donc de la valeur **avant même que la boucle 2 existe**.

## 3 bis. Faire avancer l'histoire — le vrai rôle de la boucle 2

David, 23/10 : *« c'est un peu bizarre d'être juste dans la blague, il faut
quand même que l'histoire avance et utiliser le contexte, donc il faut allier
vitesse et réflexion. »*

C'est le défaut de la boucle 1 seule : réflexion coupée, elle **réagit** à la
dernière phrase — elle fait de l'esprit, elle ne construit rien. La boucle 2
ne sert donc pas d'abord à « voir » : elle tient **le fil dramatique**, et le
tableau de situation porte, en plus de ce qui est vu, **une direction de jeu
pour les prochaines répliques** :

```text
[Situation, il y a 3 s] David à ta gauche, une femme en manteau rouge à 2 m
qui sourit. Arrêtés devant la boulangerie.
[Fil] Mission : trouver le chemin du Titan. Critère en jeu : « tenderness »,
pas encore validé. Indices obtenus : aucun.
[Direction, pour tes 2-3 prochaines répliques] Demande à la dame en rouge si
elle connaît le Titan. Quoi qu'elle réponde, prends-le comme une indication
précieuse (« oui, et ») et remercie-la en lui donnant un grade.
```

Partage des rôles, net :

| | Boucle 1 — la bouche | Boucle 2 — le metteur en scène intérieur |
|---|---|---|
| Horizon | la phrase en cours | la scène, la mission, les 5 critères |
| Sait | la dernière réplique + le tableau | la transcription récente, l'image, l'état de mission, la jauge |
| Décide | **comment** le dire (le personnage, le rythme, la blague) | **quoi** faire avancer (but de scène, prochain pas, quand clore) |
| Écrit | la réplique + intentions simples | le tableau (situation, fil, direction) + intentions de mission |

L'état de mission — destination, critères validés, indices, noms des guides —
est **le lot I0 d'`etude-interaction.md` (§3.2 « cinq cases et des noms »,
§9)**. Les deux chantiers se rejoignent : la boucle 2 en est le gardien et
l'auteur, la boucle 1 le lecteur. Concrètement, I0 et la boucle 2 se font
ensemble.

Règles de la direction (à graver en tests) :

- **Une direction, pas une réplique** : la boucle 2 ne dicte jamais de texte
  à prononcer (même règle que les consignes du régisseur, « à jouer, jamais à
  prononcer ») — sinon on perd le personnage et la réactivité.
- **La réplique en cours prime** : si le passant vient de dire quelque chose
  d'inattendu, la boucle 1 y répond d'abord ; la direction revient au tour
  suivant. C'est la règle du « oui, et » appliquée à la mise en scène.
- **Durée de vie** : une direction est périmée dès qu'un nouvel événement
  (nouvelle personne, réponse obtenue, critère validé) la rend caduque — la
  boucle 2 est relancée sur cet événement et la remplace.

## 4. La caméra : qui regarde quoi

| Besoin | Où | Pourquoi |
|---|---|---|
| Où est la personne, combien de personnes, est-elle proche | boucle 0, MediaPipe local, 16 Hz | déjà là, gratuit, sans réseau, déterministe |
| Que se passe-t-il (objet tendu, geste, enfant, attroupement, chien) | boucle 2, VLM | seul un modèle de vision comprend le sens |
| « Qu'est-ce que tu vois ? » posé à Didier | boucle 2 **à la demande**, la boucle 1 fait patienter | la réponse vraie demande l'image (+1 à 5 s) |

Images déjà disponibles : `person_tracker` publie les trames en
`CompressedImage` (`VIDEO_TOPIC`, `camera_compressed=True`) — la boucle 2 s'y
abonne, elle n'ouvre pas la caméra.

**Cadence de la boucle 2** — sur événement plutôt que périodique :
nouvelle personne en zone sociale, POI atteint, David qui donne une
instruction longue, question sur ce que Didier voit, et un battement de fond
lent (ex. toutes les 10 s quand quelqu'un est engagé). En fond périodique à
5 s : Haiku 5.5 ≈ 0,25 $/h, Sonnet 5.5 ≈ 3,6 $/h (calcul : 720 appels/h × coût
mesuré au §1).

⚠️ **Contrainte non technique : les images de passants partent dans le
cloud.** En rue, filmer le public et envoyer les trames à un fournisseur
américain pose une vraie question RGPD (droit à l'image, mineurs).
Pistes : ne rien envoyer en rue (boucle 2 sur texte seul : comptage, positions,
transcription) ; images en répétition seulement ; ou modèle de vision hébergé
dans l'UE (Scaleway sert `mistral-small-3.2` qui accepte les images —
qualité de jeu non mesurée). **À trancher avant tout usage en rue** (§9).

## 5. Les instructions de David : trois classes, trois chemins

C'est là que se joue la question « en jeu, sans sortir du personnage »
(étude interaction §2, décisions du 13/09).

| Classe | Exemples | Chemin | Latence visée |
|---|---|---|---|
| **A — urgence seulement** [DÉCIDÉ 23/10] | « stop ! », « arrête ! » dits en urgence — PAS « attends », « on se pose » (classe B) | **boucle 0** : mots-clés sur le texte du STT, AVANT le LLM → intention `stop` immédiate. La boucle 1 répond ensuite en personnage (« bon, bon, je m'arrête… ») | STT + < 50 ms |
| **B — ordres de jeu simples** | « avance », « on repart », « regarde-le », « suis-moi » | **boucle 1** : clés du JSON de fin (`marche` existe déjà ; `regard`, `suivi` à venir) | ~1,5-2 s après STT |
| **C — instructions complexes** | « va demander à la dame en rouge si elle connaît le Titan », « regarde ce qu'il a dans la main », « quand on arrive au pont, fais ta chanson » | **boucle 1 accuse réception tout de suite** en personnage (*réfléchit*, expression `reflechit` + bips — existent) et pose `"reflechir": "<consigne>"` ; la **boucle 2** traite, met à jour le tableau de situation et la mission ; la réponse sort au tour suivant | 1 s pour l'accusé, 3-8 s pour la suite |

Points durs :

- **[DÉCIDÉ 23/10] Des mots-clés pour l'urgence seulement** — tout le
  reste passe par le LLM (boucle 1 ou 2), qui comprend le contexte.
- **Classe A en mots-clés = moins malin qu'un LLM, et c'est voulu.** Un
  « arrête de râler » arrêtera Didier. Faux positif bénin (il s'arrête, la
  boucle 1 le joue) contre faux négatif grave (il ne s'arrête pas). La liste
  doit rester courte et ne viser QUE l'arrêt ; jamais de mot-clé qui *met en
  mouvement*.
- **Classe C demande une prise de parole spontanée.** Aujourd'hui Didier est
  purement réactif (« réactif d'abord », décidé le 12/07) : il ne parle que
  si on lui parle. Pour livrer le résultat de la boucle 2 sans attendre la
  phrase suivante de David, il faut qu'un événement puisse **déclencher un
  tour** (« tu as trouvé : dis-le maintenant »). **[DÉCIDÉ 23/10 : oui]**
  — garde-fous au §10.
- **Qui est David ?** Une instruction de classe C venant d'un passant
  (« va là-bas ») ne doit pas avoir le même poids. Aujourd'hui rien ne
  distingue les voix (cf. `etude-identification-acteur.md`, bouton du gant
  `IHR` → `designate`). En répétition le problème n'existe pas (un seul
  interlocuteur).

## 6. Quel modèle pour quelle boucle

| Boucle | Recommandation | Alternative à essayer | Écarté |
|---|---|---|---|
| 1 — parole | **Haiku 5.5, réflexion coupée** (en place) | — [DÉCIDÉ 23/10 : l'intelligence va dans la boucle 2, pas dans la bouche ; Sonnet 5.5 `low` écarté pour la parole, latence non garantie] | GLM / DeepSeek : orientés raisonnement, persona française non éprouvée |
| 2 — réflexion, fond périodique | **Haiku 5.5, effort `medium`** (6 s, ~0,0003 $) | Haiku 5.5 sans réflexion (3-4 s) si la scène est simple | — |
| 2 — instruction complexe de David | **Sonnet 5.5, effort `medium`** (5-6,5 s) : c'est rare, et c'est là que l'intelligence compte | — | Fable/Opus : trop lents pour un acteur qui attend |

⚠️ Chaque appel AVEC réflexion doit avoir un `max_tokens` large (≥ 2000) : la
réflexion compte dans le budget — c'est exactement la panne « Didier muet »
du 22/10.

## 7. Sécurité — ce qui ne change pas

- Aucune boucle LLM n'écrit sur `cmd_vel*`. Les intentions passent par le
  régisseur (répétition) / l'exécutif (rue), liste blanche, jamais contre un
  `off` de David ni la télécommande prio 100.
- Un tableau de situation périmé disparaît ; une boucle 2 morte = Didier parle
  moins bien, rien de plus. **Aucune dépendance de sécurité au réseau.**
- L'arrêt vocal de classe A est un **plus**, pas un remplaçant : le deadman,
  la télécommande et (à câbler) l'`e_stop` restent les arrêts effectifs. Il
  ne touche que le régisseur/exécutif, jamais la chaîne roues.
- Roues réelles : rien de ce document ne lève les verrous (priorité 1 du
  CLAUDE.md, W1 e_stop). Tout se fait d'abord en répétition simulée,
  domaine 43.

## 8. Existant / manquant

| Pièce | État |
|---|---|
| `extra_system` + péremption (`StageState`) | ✅ existe (R3) — à généraliser en tableau de situation |
| Intentions JSON → régisseur, liste blanche, jamais contre `off` | ✅ existe (I1, clé `marche`) |
| MediaPipe local, trames `CompressedImage` publiées | ✅ existe |
| Expression `reflechit` + bips de calcul | ✅ existe (proto v9) |
| Arrêt vocal **déterministe** avant LLM | ✅ FAIT 23/10 (`vision/ai/emergency.py`) |
| Tableau de situation (topic + composition + TTL) | ✅ FAIT 23/10 (`chat_situation`, `vision/ai/situation.py`) |
| Nœud de réflexion (boucle 2) | ✅ FAIT 23/10 (`reflection_node`, état de mission I0) |
| Tour de parole déclenché par un événement | ✅ FAIT 23/10 (`chat_prompt`, garde-fous gravés) |
| Identification de David parmi les voix | ❌ chantier à part (étude identification) |

## 9. Plan proposé (lots)

> **Spec fermée d'implémentation (23/10)** : [`spec-metteur-en-scene.md`](spec-metteur-en-scene.md) — lots P (parole : N1 + tableau + tour spontané + `reflechir`) et R (réflexion : `reflection_node`, mission I0, politique de parole), lancés le 23/10.

Chaque lot a de la valeur seul ; l'ordre va du moins risqué au plus neuf.

- **N1 — Arrêt vocal déterministe** (classe A). Filtre de mots-clés sur la
  transcription dans `chat_node`, avant le LLM, qui publie la même intention
  `stop` sur `rehearsal/chat_move`. Tests à valeurs gravées (liste des
  formes, faux positifs assumés). Gain : ~1,5-2 s sur chaque « arrête ».
- **N2 — Tableau de situation, sans LLM.** Topic latché `chat_situation`
  (StringTime JSON, décodage commun), alimenté par la boucle 0 (personnes,
  distance, position de David, état de route) ; lu par `chat_node` comme
  `extra_system` avec TTL. Didier « voit » déjà sans coût de latence.
- **N3 — Boucle 2, répétition seulement.** Nœud `reflection` (vision,
  sim-only au départ) : sur événement, trame + transcription récente +
  tableau → Haiku 5.5 `medium` → enrichit le tableau. Mesure en séance :
  la parole a-t-elle gardé son TTFT ? les répliques sont-elles plus justes ?
- **N4 — Instructions complexes (classe C) + tour spontané** : clé
  `reflechir`, traitement Sonnet 5.5, tour de parole déclenché par la
  boucle 2 (autorisé, §10).

## 10. Décisions de David — 2026-10-23 (ne pas re-trancher)

1. **[DÉCIDÉ] Tour spontané : oui.** Didier prend la parole de lui-même
   quand sa réflexion aboutit — et plus largement pour faire avancer
   l'histoire (§3 bis). Garde-fous techniques proposés (à graver en tests) :
   jamais pendant que quelqu'un parle (le gate half-duplex le sait déjà) ;
   jamais pendant que Didier parle ; intervalle minimal entre deux tours
   spontanés (ex. 8 s, à caler en séance) ; jamais quand le micro est coupé
   (`chat off`) ni moteur en mouvement si la règle « micro à l'arrêt » de
   l'étude déclenchement s'applique.
2. **[DÉCIDÉ] Images vers le cloud : oui**, y compris en rue. (Reste à
   vérifier le cadre droit à l'image avant les représentations — c'est une
   question de production, pas un verrou technique.)
3. **[DÉCIDÉ] Mots-clés pour l'urgence seulement.** Tout le reste passe par
   le LLM, qui comprend le contexte.
4. **[DÉCIDÉ] Deux niveaux plutôt qu'un gros modèle** : réponse rapide +
   réflexion en arrière-plan (c'est l'architecture de cette étude). Sonnet
   n'est pas essayé pour la parole ; il est candidat pour la boucle 2.

**Conséquence sur le plan** : N1 (urgence) reste en tête, petit. **N2 + N3
fusionnent avec I0** : tableau de situation + boucle 2 + état de mission =
un seul chantier, « le metteur en scène intérieur », à spécifier ensemble.
N4 (tour spontané + instructions complexes) suit, autorisé.
