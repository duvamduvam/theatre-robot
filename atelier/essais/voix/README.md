# Atelier voix — essais sur le PC, sans le robot

Bac d'essai du chantier voix ([`docs/etude-voix-didier.md`](../../../docs/etude-voix-didier.md)).
Sert à traiter, **sans le Pi ni le châssis**, la moitié « qualité » du lot V0b :
le français est-il bon, le clonage ressemble-t-il à David, et le modèle
tient-il un énoncé de 30 s ? Ne répond PAS aux questions « ça tourne sur ARM »
et « à quel RTF » — celles-là attendent le Pi.

## ⚠️ Rien de sonore ne sort d'ici

**Le dépôt est public.** Un échantillon de la voix de David est exactement ce
qu'il faut à un tiers pour la cloner. `audio/` et `sorties/` sont dans le
`.gitignore`, ainsi que toutes les extensions audio — **ne jamais les forcer
avec `git add -f`**. Si un enregistrement doit être partagé, il passe par un
canal privé, pas par le dépôt.

## Installation

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python \
  --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  torch pocket-tts soundfile
```

**Torch en CPU seul, délibérément** : la cible est un Raspberry Pi, pas une
RTX 4060. Mesurer sur GPU donnerait un chiffre flatteur et sans rapport avec
ce qui tournera dans le robot. Le GPU de la machine reste utile pour autre
chose — un éventuel fine-tune piper (lot V4), qui n'a donc plus besoin d'un
GPU loué.

## Ce qu'on cherche, dans l'ordre

1. **Le français existe-t-il vraiment ?** La documentation se contredit : le
   site officiel annonce six langues avec une voix française pré-faite
   (*Estelle*), la fiche Hugging Face dit « English only at the moment »
   (probablement périmée, le modèle est sorti en janvier 2026). **Ça s'écoute,
   ça ne se déduit pas.** Si le français est absent ou mauvais, tout le reste
   du pari Kyutai tombe et on se replie sur le fine-tune piper (V4).
2. **Le clonage ressemble-t-il à David ?** Zero-shot depuis l'échantillon de
   référence (ci-dessous).
3. **⚠️ La tenue sur 30 s** — le test que les démos de trois secondes ne font
   jamais, et le régime où les modèles autorégressifs décrochent (dérive de
   timbre, coupure prématurée). C'est LE critère pour Didier, qui doit pouvoir
   répondre long.
4. **RTF sur le CPU du PC** : sert de base d'extrapolation avant le Pi, et
   permet d'écrire le banc de samedi une bonne fois.

## L'enregistrement de référence (à faire par David)

### La consigne qui compte : JOUER, PAS LIRE

Un TTS reproduit le **registre** de ce qu'on lui donne, pas seulement le
timbre. L'instinct, devant un micro, est de lire proprement : articulé, posé,
neutre. Ça donne un clone propre, posé et neutre — **définitivement**. Sur
trois secondes ça passe ; sur vingt, c'est un lecteur de gare.

Donc : **Didier en personnage**, adressé à un passant imaginaire, avec
l'énergie de la rue. Les hésitations, les ruptures de rythme, les respirations
et les changements d'allure ne sont pas des défauts à corriger — ce sont eux
qu'on cherche à capter.

### Conditions techniques

- **Voix sèche** : aucun traitement, aucun effet, PAS d'octaver. On clone en
  amont des filtres, l'octaver s'applique après (principe §3 de l'étude).
- Pièce calme, peu réverbérante — la doc de Kyutai prévient que **la qualité
  de l'échantillon est reproduite** : une réverbération de salon sera clonée
  elle aussi.
- Distance au micro constante, WAV mono, 48 kHz (on rééchantillonnera), pas de
  MP3.
- Déposer dans `audio/` (ignoré par git).

### Le pupitre : `enregistre.py` (écrit le 26/08)

Ne pas utiliser `arecord` à la main : l'index de carte change avec l'ordre de
branchement (au moment d'écrire ceci, `plughw:1,0` était la webcam du PC, pas
la Scarlett…). Le pupitre trouve la Scarlett par sa description, enregistre en
S32_LE 48 kHz, et **contrôle chaque prise** (crête, saturation, plancher de
bruit) pour qu'une prise ratée se refasse dans la minute :

```bash
.venv/bin/python enregistre.py gain               # régler le gain : crêtes -12…-6 dBFS
.venv/bin/python enregistre.py prise reference    # une prise (Entrée pour arrêter)
.venv/bin/python enregistre.py prise phrase-1     # les prises s'incrémentent : -p1, -p2…
.venv/bin/python enregistre.py bilan              # toutes les prises + verdicts + total
```

Rien n'est jamais écrasé : refaire une prise du même nom crée `-p2`, `-p3`…
La meilleure gagne à l'écoute, les autres restent. ⚠️ Micro statique → penser
au **48 V** ET au bouton **INST/LINE** de la Scarlett (en INST, un statique
sort un signal fantômatique — le verdict « TROP FAIBLE » le détecte).

### Contenu à enregistrer

- **Une référence de clonage** : 30 à 60 s de parole continue en personnage.
  C'est le strict nécessaire pour le zero-shot.
- **Les 6 phrases de `phrases-v0.txt`**, une par une. Elles serviront au banc
  d'écoute V0 (comparaison ventriloquie / synthèse après l'octaver).
- **Le dialogue en alternance** du même fichier, en ne disant QUE les
  répliques marquées `[DAVID]` : la machine dira les autres, et c'est en
  juxtaposition que la rupture s'entend. Un extrait isolé passe toujours.

## Ce que ça prépare pour samedi

Arriver avec l'audio déjà fabriqué transforme la séance V0 en « brancher dans
l'octaver et écouter » — trente minutes au lieu d'une journée.

## Banc des costumes vocaux (01/11)

`costumes.py` décline une réplique de Didier en 14 traitements (étude
répétition simulée §10), avec la voix de prod `didier.onnx`. Il tourne dans le
conteneur vision PC (piper + modèle + `vision/audio/effects.py` y sont) — mode
d'emploi en tête du script. Sortie : `sorties/costumes/*.wav` (hors git).

`voix_kyutai.py` (01/11) : voix du catalogue Kyutai en français + variantes « lourdes » (référence descendue puis clonée). Venv `.venv` ci-dessus + `faster-whisper` pour le contrôle. Sortie `sorties/kyutai/`.
