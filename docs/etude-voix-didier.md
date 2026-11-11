# La voix de Didier — continuité entre ventriloquie et synthèse

*Étude ouverte le 2026-08-26. Le **cadre technique** ci-dessous (§3, §4, §6)
est posé et argumenté ; l'**arbitrage artistique** (§5) est explicitement
SUSPENDU au résultat du lot V0 — David tranche après avoir écouté, pas avant.
Ne pas re-trancher §3 (le principe directeur) sans argument nouveau.*

## 1. Le problème

L'IA arrive dans les réponses de Didier, et la pertinence de ces réponses sera
un travail long. Pendant toute cette phase — probablement des mois — le
spectacle alternera **deux sources de parole** :

- la **ventriloquie** : David parle dans un micro HF, sa voix sort du châssis ;
- la **synthèse** : le Pi 5 fait parler piper depuis le pipeline de
  conversation (VAD → whisper → LLM → TTS, voir
  [`etude-declenchement-conversation.md`](etude-declenchement-conversation.md)).

Or **les deux voix n'ont rien à voir**. Le public ne pardonne pas ça : un
personnage qui change de voix au milieu d'un échange n'est plus un personnage,
c'est un dispositif. Toute la crédibilité construite par la ventriloquie tombe
à la première réplique machine — et symétriquement, la moindre bonne réponse
de l'IA est gâchée par le fait qu'elle sort d'une autre bouche.

La question posée : *peut-on fabriquer une voix synthétique à partir de la
mienne, après les filtres ?*

## 2. État des lieux — comment la voix est réellement fabriquée

Relevé du 2026-08-26 (câblage confirmé par David) :

```
micro HF ──► récepteur HF ──► OCTAVER ──► mixette ──┐
                                                     ├──► ampli ──► châssis
Pi 5 (piper, bruitages) ─────────────────► mixette ──┘
```

Deux faits décisifs :

1. **« La voix de Didier » n'est pas la voix de David.** C'est *sa voix passée
   dans l'octaver*. Le personnage vit dans l'étage d'effet, pas dans le larynx.
   Voir [`hardware/overview.md`](hardware/overview.md) §« Echo » (l. 299, 311) :
   le châssis contient récepteur HF + octaver, et la sortie de la voix de
   l'interprète peut survenir à tout moment pendant un spectacle.
2. **Le Pi ne passe PAS par l'octaver.** Il entre en direct dans la mixette.
   C'est là, et seulement là, qu'est l'écart de timbre qu'on entend.

À noter aussi, parce que ça sert la suite : l'étage d'effet est **déjà
commutable par relais depuis le Pi** — `robot/actions/relays.py:105`
(`pitched_voice` / `normal_voice`, relais `effect`, sortie `voice_out`). La
plomberie de commande existe ; il manque le chemin audio.

Et le pipeline est déjà **half-duplex par architecture** (overview.md §297 :
Didier EST la sono, le micro n'est armé que quand Didier se tait). Donc
**ventriloquie et synthèse ne parlent jamais en même temps** — ce qui autorise
une commutation là où il faudrait sinon un mélangeur (§6).

### ⚠️ MESURÉ le 26/08 — « l'effet robot » est un ÉCRÊTEUR DUR, et il est en prod

Écoute au banc (ampli branché) : David trouve la voix « assez saturée, pas
évidente à comprendre ». Ce n'était ni l'ampli, ni le TTS. Mesure sur les deux
versions que le proto conserve — avant effets (`_raw`) et après (`_fx`) :

| fichier | crête | RMS | **facteur de crête** |
| --- | --- | --- | --- |
| `say0_raw` (sortie piper brute) | −0,0 dBFS | −13,5 dBFS | **13,5 dB** |
| `say0_fx` (après l'effet) | −4,3 dBFS | −7,4 dBFS | **3,1 dB** |

Aucun échantillon écrêté dans le `_fx` : ce n'est pas une saturation numérique
de sortie, c'est la **dynamique qui est détruite**. 3 dB de facteur de crête,
c'est presque un signal carré. **Vérifié à l'oreille** : rejoué en `_raw` par
la même chaîne, David répond « nettement plus propre, plus compréhensible »,
« c'est vachement mieux ».

Le code explique tout (`dadou_vision_ros`, `vision/audio/effects.py`, appelé
par `vision/ai/tts.py::apply_robotic_effect`) :

```python
tremolo = 1.0 + depth * sin(2π · rate · t / sample_rate)   # depth=0.7, rate=35 Hz
audio   = clip(audio * tremolo, -3000, 3000)               # ← ÉCRÊTAGE DUR
```

**Le seuil de 3000 est un ABSOLU sur une échelle de 32768, soit −20,8 dBFS.**
Une sortie piper dont le RMS est à −13,5 dBFS (≈ 6900 LSB) passe donc
l'essentiel de son énergie *au-dessus* du seuil : la quasi-totalité de la forme
d'onde est mise au carré. L'« effet robot » n'est pas un trémolo avec une
pointe de distorsion — **c'est un écrêteur, avec un trémolo devant**.

Trois conséquences, dans l'ordre d'importance :

1. **C'est du code de PRODUCTION, pas du proto.** Le chemin de prod appelle
   `clip=3000, regain_to=3000` (facteur de regain = 1, donc pas de reprise de
   niveau) ; le proto, lui, remonte ensuite à 20000. Même distorsion, niveaux
   différents. La voix du robot en spectacle passe par cet écrêteur.
2. **L'effet dépend du NIVEAU d'entrée, et personne ne le sait.** Le seuil
   étant absolu, un TTS qui sort 6 dB plus fort donne un personnage plus
   distordu, sans qu'une seule ligne de code ait changé. **C'est un piège
   direct pour le lot V0b** (bascule vers un autre TTS) : changer de moteur
   change la voix de Didier par un chemin que rien ne documente. Tout
   changement de TTS doit s'accompagner d'un relevé du niveau d'entrée de
   l'effet.
3. **Ça pèse sur l'arbitrage artistique du §5.** Une partie de ce qu'on prend
   pour « la voix du robot » est en réalité de la distorsion d'écrêtage — et
   une partie de la mauvaise intelligibilité aussi. Avant de juger un clone,
   il faut savoir ce qu'on lui fait subir en aval. Cohérent avec le principe
   directeur du §3 : **cloner AVANT les filtres**.

Rien n'est corrigé ici : c'est un constat. La décision (garder l'écrêtage comme
signature sonore, le normaliser en relatif, ou l'adoucir) est **artistique** et
appartient à David, avec le §5.

## 3. Le principe directeur — cloner AVANT les filtres, unifier APRÈS

Réponse à la question littérale : **non, on ne clone pas la voix filtrée — et
c'est une bonne nouvelle.**

Un octaver est un processus **chaotique sur la parole** : il suit le
fondamental, donc il décroche sur les fricatives (`s`, `f`, `ch`), glisse sur
les attaques, et produit des artefacts qui ne se reproduisent pas deux fois à
l'identique. Un modèle TTS entraîné sur cette sortie apprendrait ce bruit comme
s'il était du timbre, et le restituerait **moyenné** : on perdrait exactement
le grain qui fait le personnage, tout en héritant d'un modèle plus difficile à
entraîner (données incohérentes = convergence molle).

L'architecture correcte est l'inverse :

```
David (voix sèche)  ──┐
                      ├──► MÊME étage d'effet ──► ampli ──► châssis
piper (voix clonée) ──┘
```

**La continuité ne vient pas du clonage : elle vient du dernier étage commun.**
C'est le seul endroit de la chaîne où l'identité peut être *garantie* au lieu
d'être *approchée*. Le clonage, lui, ne fait que réduire l'écart en entrée de
cet étage. Conséquence de méthode : **le lot V0 (faire passer piper par
l'octaver existant) doit précéder toute dépense de clonage**, parce qu'il est
possible que l'octaver écrase assez pour que l'écart résiduel ne s'entende pas.

## 4. Le clonage — les options, et celle qui gagne

*État de l'art relevé par recherche web le 2026-08-26. Recherche documentaire,
**aucun test physique** — les incertitudes sont listées en fin de section et
ne doivent pas être lues comme des faits.*

### 4.1 Le vrai axe : dérive contre platitude

Didier ne fait pas que des répliques courtes : une conversation demande des
réponses de **10 à 30 s**. C'est ce régime qui départage les modèles, et il les
départage sur un axe qu'on ne voit pas sur des démos de 3 secondes :

- **Les modèles non autorégressifs (piper / VITS) ne dérivent jamais.** Ils
  sortent la même chose à la seconde 25 qu'à la seconde 2. Leur défaut est
  ailleurs : ils sont **plats**. VITS n'expose aucune variable d'émotion ou de
  style à l'inférence — plusieurs comparatifs 2026 qualifient piper de
  *fast-and-robotic*.
- **Les modèles autorégressifs expressifs jouent mieux et décrochent sur la
  durée.** C'est documenté, pas théorique : dérive de timbre sur XTTS
  (issues #4172, #3432) et Fish Speech (#597, non résolue), découpage manuel
  obligatoire au-delà de 300–500 mots sur F5-TTS (#395, #811), et sur
  Chatterbox une **fin d'énoncé déclenchée prématurément qui coupe en plein
  milieu** (#519, #587).

Autrement dit : **le besoin de Didier tombe pile dans le trou.** Les énoncés
longs sont exactement le régime où l'expressivité coûte la fiabilité. Tout
choix de modèle est un arbitrage sur cet axe, pas une question de qualité
générale.

### 4.2 Les candidats

| Modèle | Licence commerciale | Français | Matériel | Temps réel Pi 5 | Clonage | Tenue 10-30 s |
|---|---|---|---|---|---|---|
| **Piper** | **MIT** — libre | voix FR officielles (`fr_FR-siwis`, `tom`) | CPU seul | **oui** (référence embarquée) | fine-tune requis | stable mais **plate** |
| **Kyutai Pocket TTS** | code **MIT**, poids **CC-BY-4.0** (commercial OK avec attribution) | FR réel mais **variante `french_24l`, NON distillée, « preview »** | 2 cœurs CPU ; 6× temps réel **mesuré sur MacBook Air M4 (donc ARM)** | portages ARM communautaires + voie `sherpa-onnx` | **zero-shot** depuis un wav | à mesurer (banc V0b) |
| Chatterbox Multilingual | **MIT** | FR listé (23 langues) | GPU conseillé | non | zero-shot 5-10 s | **coupe en plein milieu** (#519) |
| Zonos | Apache 2.0 | FR listé | ~2× temps réel sur RTX 4090 | non | zero-shot 10-30 s | émotion 8D mais « entangled » |
| CosyVoice2-EU | Apache 2.0 (non relu) | FR via fork académique **stade précoce** | GPU | non | zero-shot 3 s | anti-répétition intégré, hallucinations résiduelles |
| XTTS v2 | ⛔ **CPML non-commercial** | 1 des 17 langues | GPU 4-6 Go | non | zero-shot 6 s | dérive documentée |
| F5-TTS | code MIT, ⛔ **poids CC-BY-NC** | pas de modèle FR officiel | GPU | non | zero-shot 3 s | découpage manuel requis |
| Fish Speech / S1 | ⛔ **non-commercial** | FR revendiqué | GPU | non | zero-shot | dérive après quelques minutes |
| ElevenLabs / Cartesia (cloud) | payant | non vérifié | réseau | — | instantané | latence 75-190 ms |

⛔ **Piège de licence, décisif si le spectacle est payant.** XTTS v2, les poids
officiels de F5-TTS et Fish Speech S1 sont **non commerciaux**. Coqui a fermé
en janvier 2024 : pour XTTS il n'existe même plus de licence commerciale à
acheter. Ces trois-là sont hors-jeu, quelle que soit leur qualité. Revérifier à
chaque changement de version — les termes bougent.

### 4.3 Ce que ça donne pour Didier

**Aucun candidat ne coche tout** (français de qualité + clonage + temps réel
sur Pi 5 + licence propre + tenue sur 10-30 s). D'où une cascade, pas un choix :

1. **Kyutai Pocket TTS est le pari le plus intéressant** — labo français,
   licence propre (code MIT, poids CC-BY-4.0 : commercial autorisé avec
   attribution), et **clonage zero-shot depuis un simple wav**.

   **Vérifié à la main le 26/08 (installé et mesuré, pas lu)** — deux
   corrections aux craintes initiales, dans les deux sens :
   - ✅ *Le risque ARM est plus faible que redouté.* Le modèle anglais fait
     **100 M de paramètres** (et non 1,6 Md), ce qui vide largement l'argument
     de la bande passante mémoire ; et le « 6× temps réel sur 2 cœurs » est
     mesuré **sur un MacBook Air M4, donc sur de l'ARM** — le chemin de code
     ARM existe, c'est même la mesure vitrine. Portages communautaires
     (Raspberry Pi, Jetson) signalés, et `sherpa-onnx` offre une seconde voie
     sans PyTorch. Reste l'écart M4 ⟷ Cortex-A76 (~3-4× en calcul, ~7× en
     bande passante).
   - ⛔ *Mais le français n'est PAS le modèle rapide.* Le FR n'existe qu'en
     variante **`french_24l`**, que l'outil lui-même annonce comme *« bigger
     models, not distilled yet and here only as preview »*. **Le « 100 M / 6×
     temps réel » vaut pour l'anglais distillé, pas pour ce qu'on ferait
     parler à Didier.** C'est le vrai risque du pari Kyutai, il n'apparaît dans
     aucune communication — seulement dans l'aide de la ligne de commande.

   Reste vrai, et c'est ce qui justifie le lot : s'il passe sur le Pi, il
   supprime d'un coup le corpus d'une heure, le GPU loué et le fine-tune.
2. **Le fine-tune piper reste le filet de sécurité** : MIT sans ambiguïté,
   temps réel quasi certain, et il produit un `.onnx` qui *remplace* la voix
   actuelle sans toucher au code. Résultat attendu : **le timbre de David, pas
   son jeu**. Corpus 1–3 h en partant du checkpoint FR `siwis-medium` (le
   plancher communautaire descend à quelques minutes, la référence LJSpeech est
   à ~24 h) ; GPU loué ~0,30 $/h, quelques heures.
3. **Ajouter un calculateur seulement en dernier recours.** Jetson Orin Nano
   Super : 249 $, 67 TOPS, 7-25 W. Mais les retours de terrain (forum NVIDIA,
   05/2026) montrent que **personne n'y a encore une combinaison propre
   « clonage + temps réel + faible latence »** : piper et Kokoro y tournent
   facilement mais sans clonage, Chatterbox tourne avec une latence importante.
   À traiter comme un chantier d'intégration, pas comme un achat qui résout.

**Cloud écarté comme solution principale** (dépendance réseau en rue), avec une
réserve : Cartesia publie un SDK on-device en Apache 2.0 (`cartesia-ai/edge`),
à regarder si le Pi 5 seul échoue — support ARM non confirmé.

### 4.4 Incertitudes de cette section (à ne pas prendre pour des faits)

- **Aucun benchmark RTF contrôlé** comparant plusieurs moteurs sur un **même
  Pi 5 physique** n'existe : les chiffres piper qui circulent varient d'un
  facteur ~40 selon la source et ne sont pas comparables entre eux.
- Le « 6× temps réel CPU » de Kyutai n'a été vérifié sur **aucun ARM**.
- **Aucun benchmark de qualité française indépendant** (hors communication des
  projets eux-mêmes) pour Kyutai, XTTS, Fish, Chatterbox, Zonos, CosyVoice2-EU.
- Licence Apache 2.0 de CosyVoice2 annoncée par sources secondaires, fichier
  LICENSE non relu.
- Coût réel en euros d'un fine-tune piper sur 1-3 h : **extrapolé**, non sourcé.
- Support ARM de Cartesia Edge : non confirmé.
- Mini-PC type N100 pour du clonage temps réel : aucune donnée trouvée.

## 5. L'arbitrage artistique — SUSPENDU au lot V0

Deux directions s'excluent, et le choix n'est pas technique :

- **A — rapprocher la machine de David.** On clone, Didier garde sa chair, ses
  nuances, sa chaleur. La continuité reste *approchée* : elle dépend de la
  qualité du clone et se dégrade sur les phrases longues.
- **B — éloigner les deux vers un commun robotique.** On pousse le traitement
  (vocodeur en plus de l'octaver) jusqu'à ce que la source devienne
  indifférente : humain et machine passent au même moule, la continuité est
  garantie **par construction**. Prix : Didier perd en chair.

**Décision reportée après écoute (V0).** C'est le bon ordre : la question
« combien d'écart reste-t-il après l'octaver ? » a une réponse mesurable, et
elle change l'arbitrage.

### Ce qui va mordre avant le timbre

Trois points que ni A ni B ne règlent :

- **⚠️ La portée réelle du §3 : l'octaver unifie le TIMBRE, pas la prosodie.**
  Il ne masque ni le rythme, ni le placement des respirations, ni l'intention.
  Or plus l'énoncé est long, plus c'est la prosodie qui porte l'identité et
  moins le timbre compte. **La garantie « par construction » du §3 s'amincit
  donc exactement là où Didier en a le plus besoin** — sur les réponses de
  conversation. Le principe reste juste, il couvre moins de terrain qu'il n'y
  paraît. Aucune solution retenue à ce stade (§8).
- **⚠️ Le corpus est le plafond du clone.** Un TTS reproduit le **registre** de
  ce sur quoi il a été entraîné, pas seulement le timbre — c'est le problème
  de désentanglement timbre/prosodie des modèles VITS. L'instinct, en
  enregistrant un jeu de données, est de lire proprement : articulé, posé,
  neutre. Résultat : un clone propre, posé et neutre, **définitivement**. Sur
  3 s ça passe ; sur 20 s c'est un lecteur de gare. La séance V3 doit donc
  capter **Didier en personnage** — adressé à un passant imaginaire, énergie de
  la rue, hésitations, ruptures de rythme, respirations — et non David au
  micro. Aucun modèle et aucun budget GPU ne rattrape un corpus plat.
- **La latence.** Une réponse LLM met des secondes ; la ventriloquie est
  instantanée. La rupture de *rythme* est un signal aussi fort que la rupture
  de timbre. Déjà traité en partie côté conversation (streaming par phrase,
  piper in-process) — mais c'est le même problème de continuité.

### Un levier gratuit : le texte pilote la prosodie

Sur les énoncés longs, c'est le **LLM** qui écrit la réplique, et la forme du
texte contraint la diction du TTS plus qu'on ne le croit : phrases courtes,
ponctuation franche, pas de subordonnées à rallonge, hésitations écrites
explicitement dans la réplique. **Contraindre le style de sortie du LLM
améliore la diction quel que soit le modèle vocal, pour zéro euro et zéro
latence.** Ça se joue dans le prompt système du chat (`vision/ai/personas.py`),
pas dans la chaîne audio — donc c'est applicable avant même l'arbitrage §5.

## 6. Le câblage — faire passer le Pi par l'octaver

Trois montages possibles ; le half-duplex (§2) en rend un nettement meilleur.

**Option 1 — commutateur A/B piloté par le relais existant. RECOMMANDÉE.**
Puisque les deux sources ne parlent jamais en même temps, aucun mélange n'est
nécessaire : un simple aiguillage devant l'octaver suffit, et le Pi **sait déjà
piloter des relais** (`relays.py`). L'état du commutateur devient en prime la
lecture fiable du « une source est vivante » qu'appelle overview.md l. 311.

**Option 2 — insert / départ auxiliaire de la mixette.** Si la mixette a un
insert ou un aux send + retour, on y place l'octaver et les deux voies y
passent. Avantage : adaptation de niveau gérée par la console. Inconvénient :
ça **modifie le chemin de la ventriloquie**, qui marche aujourd'hui — on
touche à l'existant qui tourne, pour servir le nouveau. À n'envisager que si
l'option 1 coince.

**Option 3 — refaire l'octaver en logiciel** sur le Pi (sox / rubberband /
LADSPA), câblage inchangé. C'est de loin le plus maintenable : réglable,
versionné, testable sans matériel. Mais ce n'est **pas le même** octaver, donc
l'égalité de timbre n'est plus garantie par construction — elle redevient un
travail d'imitation. Candidat sérieux **après** V0, pas pendant.

### Deux pièges de câblage

- **Adaptation de niveau.** L'octaver attend probablement du niveau instrument
  (il est alimenté par un récepteur HF) ; la sortie du DAC USB est du niveau
  ligne, et stéréo. Il faut sommer en mono et atténuer (pad résistif passif, ou
  boîtier de reamp). Ne pas attaquer une pédale en ligne : ça sature.
- **⚠️ Tous les sons du Pi ne doivent PAS être pitchés.** Klaxon, bruitages,
  musique doivent rester secs. Deux parades : le relais `effect` déjà en place
  (commuté par réplique), ou — plus simple et sans logique — **séparer les bus
  gauche/droite** de la sortie stéréo : voix à gauche → octaver, bruitages à
  droite → mixette en direct. Un seul câble en Y, aucune commande.

## 7. Lots V0 → V4

**V0 — banc d'écoute (atelier, aucune modification permanente).** Un câble, un
pad, la sortie du Pi dans l'entrée de l'octaver existant. Protocole :

1. **6 phrases représentatives**, choisies pour attaquer l'octaver là où il
   décroche : une salutation, une question, une réplique longue, une avec des
   chiffres, une saturée de sifflantes, une à attaques explosives (`p`/`t`/`k`).
2. Chaque phrase enregistrée **au même point** (sortie mixette) en trois
   versions : (a) David en ventriloquie, (b) piper voix 1, (c) piper voix 2 —
   **toutes post-octaver**. Normaliser en sonie avant écoute, sinon on compare
   des volumes.
3. **Le test décisif est l'alternance**, pas l'écoute isolée : monter une
   réplique où David et la machine se répondent phrase à phrase. La rupture ne
   s'entend qu'en juxtaposition — un extrait isolé passe toujours.
4. Écoute **en aveugle** par au moins deux personnes ne connaissant pas
   l'ordre, notation 1–5 sur « est-ce le même personnage ? ».
5. Consigner au §9. **C'est ce lot qui débloque l'arbitrage §5.**

**V0b — banc Kyutai Pocket TTS. Le lot a DEUX MOITIÉS, et une seule a besoin du
Pi** — découpage fait le 26/08, quand il est apparu que tout le volet qualité
se traite sur le PC. Atelier : `essais/voix/` (README, `bench.py`,
`phrases-v0.txt`).

**V0b-PC — FAIT le 2026-08-26.** Installé (`pip install pocket-tts`, torch CPU,
Python 3.12), modèle `french_24l`, voix intégrée *Estelle*, 4 fils d'exécution
pour approcher un Pi 5. Mesuré par `bench.py` sur les 6 phrases :

| | RTF médian | TTFA | Réponse longue |
|---|---|---|---|
| float | 0,46 | 0,16-0,27 s | 33,8 s produits, **pas de troncature** |
| **int8** (`--quantize`) | **0,27** | **0,10-0,14 s** | 30,2 s produits, **pas de troncature** |

Trois enseignements :
- **La quantification int8 fait gagner ~1,7×** — c'est la configuration à
  emmener sur le Pi. (Son coût en QUALITÉ reste à écouter : le banc mesure le
  temps, pas le timbre.)
- **Le chargement du modèle ne coûte que 2,3 s** une fois en cache : la
  contrainte « in-process » déjà apprise sur piper reste tenable.
- **⚠️ Aucune coupure prématurée sur un énoncé de 30 s.** C'est le mode de
  défaillance qui disqualifie Chatterbox (§4.1) et il ne s'est pas produit ici.
  Le point dur des réponses longues n'est donc PAS la troncature sur ce
  modèle — reste la monotonie, qui elle ne se mesure pas (§5).

Extrapolation prudente vers le Pi 5 : un Cortex-A76 étant ~3-4× plus lent par
cœur, RTF ≈ 0,8-1,1 — **à cheval sur le temps réel**, donc à mesurer et non à
deviner. Le TTFA, lui, garde une marge confortable, et c'est lui qui décide du
ressenti (§4.1).

**V0b-PC, volet CLONAGE — FAIT le 2026-08-26** (l'après-midi même de la séance
V3 : la boucle enregistrement → clone a tenu dans la journée). Accès au modèle
gated obtenu (compte HF Dave945, conditions Kyutai acceptées, jeton local).
`bench.py --voice audio/reference-p1.wav`, trois états de voix comparés :

| état de voix | RTF médian (PC) | complétude ASR (6 phrases) |
|---|---|---|
| référence 60 s, float | 0,88 | 4/6 — sifflantes partent en vrille, fin de la 6 avalée |
| référence 15 s, float | 0,75 | 5/6 — une coupure sur les plosives |
| référence 15 s, **int8** | **0,43** | **6/6** |

Enseignements, avec le niveau de confiance qui va avec :

- **⚠️ Le clonage coûte ~1,6× en RTF** par rapport à la voix intégrée (0,43
  contre 0,27 en int8). L'extrapolation Pi passe de « à cheval sur le temps
  réel » à **probablement > 1 en clonage** — la mesure V0b-Pi devient encore
  plus décisive, et doit se faire AVEC un état de voix cloné, pas avec Estelle.
- **La référence longue n'aide pas, elle nuit** (tendance sur 1 run) : 60 s
  d'état de voix = RTF plus haut ET plus d'accidents que 15 s. À confirmer,
  mais le réglage de départ est : **référence 15-30 s**, pas la totale.
- **Ces « complétudes » sont un contrôle ASR automatique** (whisper small
  relit les synthèses — `essais/voix/verifie_completude.py`), pas un
  jugement de qualité : la ressemblance, la diction des chiffres (suspecte
  dans les transcriptions) et la monotonie restent à l'oreille de David.
- Au passage, ce contrôle a attrapé un **bug du banc** (corrigé) : les lignes
  de continuation des répliques `[MACHINE]` multi-lignes fuyaient dans le
  texte de la phrase 6 — les « troncatures » du premier run étaient du texte
  parasite, pas un défaut du modèle.

#### ✅ VERDICT DE DAVID le 26/08 : « oui, c'est bien ma voix »

Écouté sur les KRK. Le jalon du chantier est franchi : **le clonage zero-shot
rend la voix de David**, et ce n'est pas un effet de reconnaissance de ses
propres prises — la démonstration a été faite sur un **texte inédit** de
99 s (`essais/voix/texte-demo-2min.txt`, écrit ce jour, jamais prononcé,
truffé exprès de mots absents des prises : parapluie, boulangerie, Perpignan,
quatre-vingt-treize). David avait justement posé la bonne question sceptique
(« ça ne vient pas d'enregistrement préexistant ? ») : non — la référence ne
sert que d'empreinte de timbre, l'audio est généré échantillon par échantillon.

Conséquence pour l'arbitrage §5 : **la branche « synthèse clonée » est
viable**, elle n'est plus une hypothèse. Ce qui reste à juger à l'oreille
n'est plus le timbre mais la **constance** (David a signalé « il y avait des
morceaux bien », donc une qualité inégale, non encore caractérisée : début de
bloc ? dérive de fin ? chiffres et noms propres ?).

#### ⚠️ Retour de David, et les deux mesures qui l'expliquent (26/08)

**« C'est ma voix NORMALE, pas la ventriloquie. »** Mesure F0 (autocorrélation,
`essais/voix/mesure_voix.py`) :

| | F0 médian | étendue p10-p90 |
|---|---|---|
| `reference-p1` (la prise de David) | **134,5 Hz** | 81,5 Hz |
| clone float | 136,8 Hz | 58,0 Hz |
| clone int8 | 139,1 Hz | 60,7 Hz |

**Le clone reproduit la hauteur de la référence à ~2 % près : il est fidèle.**
Ce n'est donc PAS un défaut du modèle — **c'est la prise de référence qui
était en voix normale**. La séance V3 a capté « David en personnage » au sens
du jeu (adresse, énergie, rythme) mais **pas la technique vocale de la
ventriloquie**.

**Correction du principe §3, et elle est importante** : « cloner AVANT les
filtres » visait l'**octaver**. Mais la ventriloquie n'est pas un filtre,
c'est une **technique vocale** — elle appartient donc au CORPUS, pas à l'aval.
La chaîne cible est : *ventriloquie de David* → clone → octaver. On avait
cloné un cran trop tôt. ⚠️ **Toute reprise du corpus (V3 bis, et le palier
complet si on y va) doit être enregistrée en voix de ventriloquie.**

Bénéfice collatéral : le §8 demandait « F0 moyen de la voix de ventriloquie à
mesurer ». On tient déjà la **voix normale à 134,5 Hz** ; il manque la
ventriloquie, que la prochaine prise donnera — et l'écart entre les deux sera
la cible de la pré-transposition du lot V2.

**« Le volume de voix est parfois inégal. »** Écart de niveau entre phrases :

| | écart max entre phrases |
|---|---|
| clone int8 | 13,8 dB |
| clone float | 14,9 dB |
| **`reference-p1` (l'humain)** | **16,2 dB** |

**Là encore le modèle ne dérègle rien : il reproduit fidèlement la dynamique
naturelle de David** (qui est même un peu plus contrastée). Mais Didier joue
DANS LA RUE et il EST la sono : une phrase 15 dB plus bas est perdue pour le
public. C'est donc un besoin de **diffusion**, à traiter en aval — surtout pas
en demandant à David de parler « plus régulièrement », ce qui aplatirait le
jeu (le piège du §5).

Remède écrit et vérifié : `essais/voix/nivelle.py` — découpe sur les silences,
ramène chaque phrase à un RMS cible, gain plafonné et transitions en fondu de
30 ms. **13,8 dB → 1,4 dB** sur la démo int8 (plafond desserré à +20 dB,
légitime sur une source synthétique qui n'a pas de bruit de fond ; garder
+12 dB par défaut pour de l'audio capté). À intégrer au pipeline de diffusion
côté vision, pas au corpus.

Deux versions du même texte sont sur disque pour trancher le coût de l'int8 :
`sorties/demo-texte-inedit-float.wav` (99 s, RTF 0,73) et
`-int8.wav` (95 s, **RTF 0,42**). Génération **bloc par bloc**
(`demo_texte.py`), comme le fera la prod qui diffuse phrase par phrase : ça
borne la dérive autorégressive et un bloc raté ne contamine pas les suivants.

**Montage d'écoute prêt** : `essais/voix/sorties/alternance-david-machine.wav`
(40,9 s) — les répliques `[DAVID]` sont les prises réelles de la séance V3,
les `[MACHINE]` sont dites par le clone (état 60 s), RMS égalisés, 24 kHz.
C'est le test décisif du banc V0 (§7), prêt avant même le passage par
l'octaver. Les jeux à comparer : `sorties/clone-david-{60s,15s,15s-int8}/`
contre `sorties/estelle/` et contre les prises réelles d'`audio/`.

**V0b-Pi — SAMEDI.** Le même `bench.py`, sur le Pi 5, dans cet ordre :
1. **Est-ce que ça s'installe et tourne sur ARM ?** (binaire, seule question
   bloquante) ;
2. **RTF et TTFA réels**, en int8, sur *nos* phrases — et sur le Pi **chargé
   comme en spectacle** (whisper + vision tournent aussi), pas au repos ;
3. Relever `log-charge.sh` en parallèle, châssis fermé.
Échec sur (1) ou (2) ⟹ repli sur le fine-tune piper (V4), sans regret — et
sans avoir enregistré 3 h de corpus pour rien (d'où V3 conditionnel).

**Budget de charge du Pi 5 — outil : `conf/scripts/log-charge.sh`** (série
temporelle CSV à 1 Hz, lue dans `/proc` sans fork, plus attribution par
conteneur avec `DOCKER=1` ; mode d'emploi dans
[`operations.md`](operations.md#load-study-over-a-whole-show-log-chargesh)).
Il existe parce que `robot.log` ne trace que des **dépassements de seuil** et
que `collect-incident.sh` ne donne qu'une **photo** : ni l'un ni l'autre ne
produit la courbe nécessaire au dimensionnement.

**À mesurer avec D0, pas séparément.** Le lot D0 de
[`etude-declenchement-conversation.md`](etude-declenchement-conversation.md)
prévoit déjà « CPU Pi 5 en conversation complète » : V0b s'y rattache au lieu
d'ouvrir un front. Ce qu'il faut y ajouter, et qui n'y est pas :

- **Le pic est `max(whisper, TTS)`, pas leur somme.** Le half-duplex
  (overview.md §297, adopté pour l'écho) l'impose : micro armé ⟹ Didier muet,
  Didier parle ⟹ micro désarmé. Les deux gros consommateurs sont **mutuellement
  exclusifs** — c'est un acquis d'architecture, à ne pas perdre de vue en
  dimensionnant.
- **La captation micro n'est PAS le coût.** Le ReSpeaker fait beamforming et
  DoA sur sa puce (calcul déchargé) et le VAD est à énergie. Le coût, c'est
  whisper.
- **Le risque est la vidéo, parce qu'elle est CONTINUE.** Parole et écoute sont
  des rafales de quelques secondes ; la perception tourne en permanence. Une
  charge permanente à 60 % coûte plus cher en marge thermique et en tête qu'une
  pointe à 100 % pendant 3 s. Mesurer la charge **avec la charge vision cible**,
  pas sur un Pi au repos.
- **⚠️ Mesurer châssis FERMÉ.** Le Pi 5 est dans une caisse close qui contient
  un ampli. Un banc qui passe sur un bureau ventilé peut throttler en rue, en
  été. C'est la mesure qui compte, l'autre ne prouve rien.
- **Mode de défaillance à surveiller — il n'est pas « c'est lent »** : c'est la
  **boucle de gaze qui perd ses tours pendant que Didier parle**, donc la tête
  qui se fige en pleine réplique. Scéniquement pire qu'une voix plus pauvre.
  Parade : réserver les cœurs (parole / perception) au lieu de compter sur
  l'ordonnanceur.
- **Le Pi 4 est hors-jeu** pour accueillir le TTS — pas par manque de
  puissance, mais parce qu'il porte la chaîne roues à 20 Hz. Aucune charge
  variable et gourmande sur la machine qui tient le mouvement.

Si le budget ne rentre pas : la réponse est un **troisième calculateur** (§4.3),
avec le découpage perception / parole — pas un grignotage d'optimisations.
Avant d'en arriver là, deux leviers gratuits côté vidéo : détecter à **5-10 Hz**
et non 30 (largement assez pour suivre un marcheur, avec du suivi entre deux
détections), et utiliser l'ISP et le décodage matériel du Pi 5 plutôt que de
refaire au CPU.

**V1 — câblage permanent** (option 1 du §6) + garde-fou bruitages non pitchés.

**V2 — accordage sans clonage** : choisir la voix piper française dont la
tessiture est la plus proche de celle de David, et **pré-transposer** la sortie
piper pour qu'elle entre dans l'octaver au même F0 que la voix de David (une
ligne de `sox`/`rubberband`) — l'octaver suit le fondamental, donc à F0 égal il
décroche de la même façon sur les deux sources. V1 + V2 sont probablement
l'essentiel du résultat.

**V3 — enregistrement de la voix de David. ⚠️ Dimensionnement CONDITIONNEL à
V0b — ne pas bloquer un après-midi avant d'avoir le résultat.** Si le zero-shot
de Kyutai passe, **10 s de référence suffisent** là où le fine-tune demande
1 à 3 h. Deux paliers :

- **Palier minimal — ✅ FAIT le 26/08** (pupitre `essais/voix/enregistre.py` :
  Scarlett trouvée par description, S32_LE 48 kHz, contrôle de chaque prise —
  jamais le ReSpeaker, dont le DSP cuirait du traitement dans un corpus qui
  doit rester sec). **5,2 min en personnage au SM58** (48 V coupé, gain réglé
  crêtes ≈ −15 dBFS, planchers −77…−94 dBFS, zéro échantillon saturé) :
  - `reference-p1` — 60,8 s continues, 76 % de parole, silence max 1,4 s :
    LA référence zero-shot, validée à l'oreille par David ;
  - les 6 phrases du banc (`phrase-1…6`) + les 4 répliques `[DAVID]` du
    dialogue en alternance (`dialogue-1…4`) : tout le programme du README.
  Les wav restent dans `essais/voix/audio/` (gitignoré, dépôt public). Deux
  prises marquées TROP FAIBLE restent sur disque (réglages) — ignorer.
  **Prochain geste (V0b-PC, qualité) : cloner sur `reference-p1` et écouter.**
- **Palier complet, seulement si on part sur le fine-tune** : banque de 80 à
  150 répliques (accueils, esquives, « laisse-moi réfléchir », relances) —
  1 à 3 h, voix sèche, même micro, même pièce, transcriptions, segments de
  3 à 10 s. Double intérêt : ces phrases passe-partout sortiront dans **la
  vraie voix** pendant que l'IA répond encore mal, **et** le corpus EST le jeu
  de données de V4. Un après-midi, deux livrables.

Dans les deux paliers, l'exigence du §5 prime sur la propreté : **jouer, pas
lire**. C'est le plafond de tout le reste.

**V4 — fine-tune piper** sur le corpus V3 (checkpoint FR `siwis-medium`, GPU
loué). **Filet de sécurité**, à n'engager que si V0b échoue ou si V0→V2 laisse
un écart que l'arbitrage §5 refuse d'absorber. Résultat attendu, sans
illusion : **le timbre de David, pas son jeu** (§4.3).

## 8. Points encore ouverts (assumés, pas oubliés)

- **Modèle exact de l'octaver** à relever (analogique ou numérique, niveau
  d'entrée attendu, latence) — conditionne le pad du §6 et l'option 3.
- **La mixette a-t-elle un insert / aux send ?** — conditionne l'option 2.
- **F0 moyen de la voix de ventriloquie de David** à mesurer — c'est la cible
  de la pré-transposition du lot V2.
- **La prosodie** : aucune approche retenue (§5). À rouvrir si V0 montre que le
  timbre n'est pas le facteur limitant — ce qui est probable sur les énoncés
  longs, puisque l'octaver n'unifie pas la prosodie.
- **Licences** des checkpoints si le spectacle devient payant (§4.2) : XTTS,
  poids F5-TTS et Fish Speech sont **hors-jeu** (non commerciaux).
- **Kyutai sur ARM** : la seule question qui décide de la forme du chantier —
  V0b-PC l'a rendue plausible (§7), V0b-Pi la tranchera samedi.
- **⚠️ La QUALITÉ n'a été jugée par personne.** Le banc du 26/08 mesure des
  temps ; il ne dit rien du français produit, de la ressemblance avec David, ni
  de la monotonie sur 25 s. Aucun chiffre ne remplacera une écoute — et c'est
  le critère qui décide, pas le RTF.
- **Coût en qualité de la quantification int8** : gain de vitesse mesuré
  (~1,7×), dégradation non évaluée.
- **Le français `french_24l` est une preview non distillée.** Il progressera
  (distillation annoncée), mais **on ne peut pas engager un spectacle sur une
  promesse** : ce qui compte est ce qu'il vaut aujourd'hui.

## 9. Journal des mesures et décisions

- **2026-08-26** — Ouverture. Câblage relevé auprès de David : HF → octaver →
  mixette ; **Pi → mixette en direct** (ne passe pas par l'octaver). Principe
  directeur arrêté (§3 : cloner avant les filtres, unifier après). Arbitrage
  artistique (§5) explicitement suspendu au lot V0.
- **2026-08-26 (suite)** — David objecte, à raison, que la banque de répliques
  ne peut pas être la destination : **le robot doit pouvoir répondre long**.
  Trois conséquences, après recherche d'état de l'art :
  - **Correction de la portée du §3** : l'octaver unifie le timbre, **pas la
    prosodie** — la garantie s'amincit précisément sur les énoncés longs (§5).
  - **Le vrai axe de choix est dérive ⟷ platitude** (§4.1), pas la qualité
    générale : les modèles expressifs décrochent sur 10-30 s (bugs documentés),
    piper ne décroche jamais mais ne joue pas. Le besoin de Didier tombe dans
    le trou.
  - **Nouveau candidat de tête : Kyutai Pocket TTS** (MIT, FR natif, zero-shot
    ~10 s) — mais **inconnu sur ARM**. D'où le lot **V0b**, parallèle à V0 :
    s'il passe, il supprime V3 complet et V4. V3 est donc **repassé en
    dimensionnement conditionnel** pour ne pas faire enregistrer 3 h qui
    seraient inutiles.
- **2026-08-26 (banc V0b-PC)** — Pocket TTS installé et MESURÉ sur le PC, le
  Pi n'étant pas disponible avant samedi. Deux de mes craintes ARM tombent
  (modèle à 100 M et non 1,6 Md ; le « 6× temps réel » est mesuré sur un M4,
  donc déjà sur ARM), mais une inconnue non documentée apparaît, visible
  seulement dans l'aide de la CLI : **le français n'existe qu'en `french_24l`,
  variante non distillée et annoncée « preview »** — le chiffre vitrine ne
  vaut donc pas pour la langue de Didier. Mesures : RTF médian 0,46 en float,
  **0,27 en int8**, TTFA 0,10-0,27 s, et **aucune coupure prématurée sur un
  énoncé de 30 s**. Extrapolation Pi : RTF ≈ 0,8-1,1, à cheval — donc à
  mesurer. **La qualité n'a été jugée par personne : ça s'écoute.**
- **2026-11-01 — Banc « nouvelles voix » Kyutai, SANS David.** Au banc des
  costumes (étude répétition §10), David retient les deux rendus « texte qui
  bafouille » et constate que des effets ne font pas une voix. Il demande des
  voix Kyutai **plus lourdes**, **sans banque de données et sans sa voix**
  (« je ne veux pas ma voix »), et rappelle que **Didier a aujourd'hui une voix
  de FEMME** (piper `siwis`). `essais/voix/voix_kyutai.py` : 27 voix du
  catalogue Pocket TTS parlant français (WAV hors git, `sorties/kyutai/`) +
  « lourdes » = référence d'origine descendue de 4 ou 7 demi-tons PUIS clonée
  (le modèle génère nativement grave, pas d'effet en sortie). Mesures F0
  (autocorrélation, pour classer) : femmes les plus graves alba ≈ 128 Hz,
  eponine/caro_davy ≈ 146, vera ≈ 168 ; lourdes −4 → 108-141 Hz, −7 → 81-112.
  Contrôle whisper `small` : ⚠️ **le nom « Didier » est souvent mangé**
  (« Edidier », « Titié », « dédié ») et **les références −7 font sauter des
  morceaux de phrase** (alba, charles, peter_yearsley) — le −4 est la limite
  utilisable ; Kyutai ajoute de lui-même des « euh » (déglingo gratuit, mais
  non contrôlé). ⚠️ Le conteneur vision PC est mort (137) pendant le banc,
  probablement OOM (RAM PC partagée) — rien relancé d'office.
