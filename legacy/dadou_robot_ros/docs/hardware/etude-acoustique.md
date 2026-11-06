# Étude acoustique de Didier — pourquoi les enceintes ne donnent pas leur maximum

> Ouverte le 2026-11-06 sur la demande de David (« ce n'est pas optimisé au niveau des
> baffles »). **État : analyse SUR FICHES, avant photos et avant mesure.** Les ordres de
> grandeur ci-dessous sont des calculs, pas des relevés : ils disent où regarder, pas
> ce qu'on trouvera.

## 1. La chaîne

Pi 5 / récepteur HF → mixette `t.mix MicroMix 2USB` → ampli **Focal Impulse 4.320** →
2 × **Focal Universal ICU 570** + 1 grand haut-parleur central (**référence inconnue**),
montés sur la **porte audio** (panneau bois sur charnières).

Fiches officielles archivées, lues le 06/11 :
[`datasheets/focal-impulse-4320-notice.pdf`](datasheets/focal-impulse-4320-notice.pdf),
[`datasheets/focal-icu570-fiche.pdf`](datasheets/focal-icu570-fiche.pdf)
(copies Focal-JMlab hébergées par le distributeur ampire.de).

| | Valeur lue | Ce que ça implique ici |
|---|---|---|
| Impulse 4.320 — puissance | 4 × 55 W RMS (4 Ω, CEA), 2 × 160 W bridgé | ~220 W de sortie au maximum |
| Impulse 4.320 — fusible | **25 A** (15 A sur faisceau ISO), « 12V mobile applications » | il est fait pour tirer jusqu'à ~300 W sur une batterie de voiture |
| Impulse 4.320 — filtres | passe-haut **fixe 75 Hz** commutable sur 1/2 ; HPF/LPF/FULL **40-200 Hz** + **phase 0/180°** sur 3/4 | les réglages existent pour un haut-parleur de grave sur 3/4 |
| Impulse 4.320 — gain | sensibilité réglable **0,2 à 5 V** | se règle à la mesure, pas à l'oreille |
| ICU 570 | 5×7" coaxial, 4 Ω, **94 dB (2,83 V/1 m)**, 60 Hz-21 kHz, 70 W RMS | rendement correct : la puissance n'est pas le problème |
| ICU 570 — Thiele-Small | Fs 80 Hz, **Qts 0,79**, Vas 11,3 l | haut-parleur de **portière** : conçu pour un grand volume clos (la porte d'une voiture), pas pour un panneau ouvert |

## 2. Les suspects, par ordre de gain probable

### 2.1 L'alimentation : LE goulot, confirmé (cause des redémarrages du 06/11)

**Confirmé par David le 06/11 : l'ampli est sur la SD-50B-12** (4,2 A, 50 W, partagée avec
les petites charges), alors que sa notice le fusible à **25 A**. Au premier pic, la SD-50
plie, l'ampli se met en protection puis redémarre.

Ordre de grandeur, sur la fiche ICU 570 : 94 dB à 2 W. À 55 W, ~108 dB à 1 m par
haut-parleur ; avec ~10 W disponibles, ~101 dB. Soit **~7 dB perdus**, nettement moins fort
que ce que le matériel sait faire, et aucune marge pour les pics de la voix.

**Cible décidée côté refonte** (`plan-refonte-electrique.md`, « Convertisseur audio »,
conduite dans une autre conversation, ne pas la re-trancher ici) : une **SD-150B-12
dédiée à l'audio** (12,5 A, environ 150 W), avec le **gain de l'ampli réglé pour ne
jamais saturer**. Ce que ça donne côté son, en ordre de grandeur : environ 150 W en
entrée, soit une centaine de watts de sortie pour un ampli classe D, à partager entre
les haut-parleurs. On n'est plus qu'à **~2-3 dB** des 55 W par canal, et c'est le
réglage du gain qui fixe le plafond, plus l'alimentation. Pour de la voix, dont la
puissance moyenne est très inférieure aux crêtes, c'est suffisant.

→ Le réglage du gain (§2.3) devient donc une **condition de la SD-150** : il se fait à la
mesure, une fois le convertisseur posé, en vérifiant au multimètre (pince ou shunt) que
l'ampli reste sous ~12 A à plein volume.

### 2.2 Le montage sur panneau ouvert (« court-circuit acoustique »)

Un haut-parleur rayonne autant vers l'arrière que vers l'avant, en opposition de phase.
Sans caisson, les deux ondes s'annulent dès que la longueur d'onde dépasse le chemin
avant → arrière. Pour une porte de quelques dizaines de centimètres, la perte commence
vers **quelques centaines de hertz** et s'aggrave de 6 dB par octave en dessous. C'est
pile la zone de la voix : fondamentales autour de 100-250 Hz, et donc le « corps ».

Le Qts de 0,79 confirme que l'ICU 570 attend un **volume clos**, comme la portière
d'une voiture. **Le torse de Didier pourrait justement en être un** : avec Vas = 11,3 l,
un volume clos de ~50 l laisse le haut-parleur presque comme sur baffle infini
(Qtc ≈ 0,79 × √(1 + 11,3/50) ≈ 0,87, calcul à refaire avec le volume réel).

→ **La question décisive des photos** : quand la porte est fermée, l'arrière des
haut-parleurs donne-t-il sur un volume **fermé et étanche**, ou sur l'extérieur ou le
reste du robot ? Fermer ce volume (contreplaqué, joint mousse, laine dedans) pourrait être
le gain le moins cher de tout le chantier.

### 2.3 Les réglages de l'ampli

- **Passe-haut 75 Hz sur 1/2 : à activer.** Sur un montage non clos, le grave sous
  75 Hz ne s'entend pas et fait seulement débattre la membrane, ce qui coûte de la
  puissance et de la distorsion.
- **Haut-parleur central** : à quel canal est-il branché ? Si c'est un haut-parleur de
  grave, il devrait être sur 3/4 (ou 3/4 bridgé) en **LPF**, avec la coupure et la phase
  réglées à la mesure.
- **Gain** : à régler au signal de test, pour que l'ampli atteigne sa puissance juste
  avant que la mixette sature. Le banc d'août a déjà entendu une voix « saturée » : le
  réglage des niveaux d'un étage à l'autre est suspect.

### 2.4 La polarité

Les fils sont étiquetés au standard autoradio (`RR+`, `RR−`, `RL−`, `RF−`). Deux
haut-parleurs en opposition s'annulent dans le grave. On le vérifie à la pile de 1,5 V
(la membrane doit avancer sur chaque haut-parleur) ou à la mesure.

## 3. Ce qui manque pour conclure

1. ~~D'où l'ampli prend son 12 V~~ → SD-50B-12, confirmé le 06/11 (§2.1). Reste la
   section de son câble d'alimentation : la notice demande ≥ 3,3 mm² (12 AWG) jusqu'à 3 m.
2. ~~Dos de la porte, volume arrière~~ → relevé vidéo du 06/11 (§4).
   ~~Identité et branchement du haut-parleur central~~ → 10″ de caisson LD Systems,
   4 Ω, **bridgé sur 3/4 (`RL+`/`RR−`), conforme à la notice** (§6). Reste : la **position
   des commutateurs et boutons de l'ampli** (hors champ de la vidéo), qui sont la liste
   de contrôle du §6.
3. **Mesure** : balayage joué par le robot, enregistré au téléphone à 1 m dans l'axe,
   porte fermée, avant et après chaque correction. C'est elle qui valide chaque étape :
   pas de correction gardée sans courbe avant/après.

## 4. Relevé vidéo du 2026-11-06 (sans son)

Vidéo `VID_20261106_121544.mp4` (téléphone de David, 2 min 02, porte ouverte car Didier
est en chantier). Images clés archivées dans
[`../pictures/acoustique-2026-11-06/`](../pictures/acoustique-2026-11-06/), nommées
par seconde de la vidéo.

**Ce qu'on voit :**

- **Les trois haut-parleurs sont sur la porte**, qui est la face avant du torse en trois
  pans : les deux ICU 570 sur les **pans latéraux, tournés à ~45° vers les côtés**, la
  mixette en haut du pan central, et le **grand haut-parleur central** en bas, derrière
  une grille ronde en saillie (`t118`, `t92`).
- **L'ampli Focal est vissé sur la porte**, à côté de l'aimant du haut-parleur central,
  RCA rouge/blanc branchées. Faisceau haut-parleurs aux couleurs autoradio (vert,
  violet, blanc, gris), qui part vers les trois haut-parleurs (`t92`).
- L'isolateur rouge `Car Audio / HIFI` est **monté et câblé** sur la porte, sous l'ICU
  gauche. Il reste à vérifier sur quelle liaison il est.
- **Volume arrière = tout le torse**, porte fermée (David : « ça ferme complètement »).
  Il est partagé avec l'électronique (cartes, convertisseurs, nappes) et **ouvert en haut**
  tant que les caches du dessus ne sont pas remis. Les fentes verticales du pan central
  sont fermées par un diffuseur blanc (`t100`) : ce ne sont pas des fuites.
- **Grille du haut-parleur central** : deux fentes larges en haut, puis une **plaque
  pleine percée de 8 petits trous** qui masque la moitié basse du cône (`t106`, `t100`).

**Ce que ça change :**

1. **Le §2.2 se resserre.** Ce n'est pas un panneau ouvert : porte fermée, caches
   remis, les haut-parleurs chargent le volume du torse, donc un caisson clos de
   plusieurs dizaines de litres, ce que demande l'ICU 570. **Le gain ne viendra que si ce
   volume est étanche** : joints de la porte, haut du torse, passages de câbles vers la
   caisse basse et vers le cou. Toute fuite ramène une part du court-circuit acoustique.
   Autre point à surveiller : un torse plein de cartes et de fils libres **vibre et
   grésille** dès que le haut-parleur central pousse. À écouter au balayage.
2. **Nouveau suspect, la grille du haut-parleur central.** La moitié basse du cône ne
   rayonne que par huit petits trous. Une surface ouverte aussi réduite freine l'air et
   coupe l'aigu du haut-parleur central. Essai gratuit : **dévisser la plaque à trous** et
   comparer au balayage.
3. **Les ICU 570 visent les côtés, à ~45°.** Le tweeter coaxial est directif. Dans
   l'axe de Didier, le public reçoit donc moins des 2-5 kHz qui portent l'intelligibilité.
   C'est peut-être voulu (couverture large en déambulation). À trancher avec David, pas à
   corriger d'office.

## 5. Le bruit de la mixette sur le 5 V du convertisseur (06/11)

**Constat de David :** la mixette, alimentée par sa **petite batterie** (pack maison
scotché rouge, cellules vertes + modules USB, `t58`), est propre. Alimentée par le 5 V du
convertisseur (SD-50B-5), elle souffle ou ronfle trop. Pas d'enregistrement : la vidéo
n'a pas de son.

**Lecture, à prouver :** sur ce chemin, le Pi 5 joue par une carte USB C-Media, en jack
vers une entrée de la mixette. Le câble USB de la mixette ne sert donc qu'à
l'**alimenter**. Brancher ce câble sur le 5 V du convertisseur fait deux choses :

- il amène le **bruit de découpage** d'un 5 V chargé par le Pi et le reste ;
- il **referme une boucle de masse** : la masse de la mixette rejoint celle du Pi par
  le 5 V, en plus du blindage du jack C-Media, et celle de l'ampli par ses RCA.

La batterie ouvre cette boucle, d'où le silence. C'est la même famille de boucle que le
ronflement du 30/08.

**Piste cohérente avec la refonte :** mettre toute l'audio (ampli, mixette, TC Helicon)
dans **un seul domaine d'alimentation isolé**, la future SD-150B-12 audio
(`plan-refonte-electrique.md`), et alimenter la mixette en 5 V **depuis ce domaine**
(petit régulateur 12 → 5 V). Il ne reste alors qu'une liaison avec le Pi, le jack C-Media,
**et c'est là que l'isolateur à transformateurs a sa place**. À valider avant d'acheter
quoi que ce soit.

**Ce qui le prouverait (enregistrement, pas vidéo) :** enregistrer 10 s de silence à la
sortie de la mixette (ou au téléphone collé au haut-parleur central, volume fixe) dans
trois cas : batterie, 5 V du convertisseur, 5 V du convertisseur avec le jack C-Media
débranché. Le spectre tranche : des raies à **50/100 Hz** et leurs harmoniques signent
une boucle de masse, des raies en **kHz** ou un souffle large signent le découpage du
convertisseur. Si le bruit disparaît jack débranché, c'est la boucle.

## 6. Le haut-parleur central identifié par la mesure (06/11)

**Mesures de David :** **3,5 Ω** au multimètre entre les cosses, aimant de **12 cm**, largeur
totale **25 cm**. **Origine (David) : il vient du caisson de grave d'un système LD Systems**,
référence oubliée.

**Ce qu'on en déduit :**

- **3,5 Ω en continu = 4 Ω nominal.** C'est compatible avec toutes les configurations de
  l'Impulse 4.320, y compris le bridge, qui demande 4 Ω au minimum (notice p.22).
- **25 cm hors-tout = un 10 pouces.** Hypothèse, **non confirmée** : le caisson d'un
  LD Systems **DAVE 10**, un système de sonorisation compact avec caisson 10″ dont le
  haut-parleur est une fabrication propre de la marque (pages revendeurs, résultat de
  recherche non chargé). Le code `09…` de l'étiquette pourrait être un lot de 2009. Ça ne
  change pas le raisonnement.
- **C'est un haut-parleur de grave, fait pour être filtré** : dans un caisson de sono,
  il ne reçoit que le grave, sous ~100-150 Hz.
- **Branchement relevé par David : `RL+` et `RR−`.** C'est **exactement le bridge des
  voies arrière 3/4** de la fig. 9 de la notice (p. 22, schéma relu le 06/11 : `RR-` …
  `RL+` sous l'accolade BRIDGE de gauche). Le repère `FL+` vu sur la photo appartenait
  donc à un autre fil, qui passait près des cosses : **l'hypothèse « 10″ sur une voie
  avant sans passe-bas » est fausse**, corrigée ici. Le câblage est le bon : le 10″
  dispose de 2 × 160 W bridgés au catalogue (en 4 Ω, minimum requis en bridge) et du
  filtre réglable des voies 3/4.

**Ce qui reste à vérifier, ce sont les réglages, pas le câblage** (commutateurs et
boutons de l'ampli, notice p. 24-25) :

| Commande | Réglage attendu | Pourquoi |
|---|---|---|
| `X-OVER MODE` (3/4) | **LPF** | sur FULL ou HPF, le 10″ reçoit toute la voix : il la brouille et gaspille la puissance |
| `X-OVER FREQ` | ~100-120 Hz pour commencer (échelle 40-200) | au-dessus, il empiète sur la voix |
| `PHASE` (3/4) | 0 ou 180°, au balayage | pour que le grave et les ICU s'additionnent au raccord |
| `FRONT CH. (1/2)` | passe-haut 75 Hz **activé** | les ICU n'ont pas à faire le grave, le 10″ s'en charge |
| `INPUT SELECT` | selon les RCA branchées | si seule une paire de RCA arrive, le mode doit recopier l'entrée vers 3/4, sinon le 10″ est muet ou ne reçoit qu'une voie |
| `REAR GAIN (3/4)` | réglé au balayage avec `FRONT GAIN` | le 10″ bridgé est le **plus gros consommateur** de l'ampli : c'est lui qui fait plier la SD-50B-12 sur les graves (§2.1) |

**Pour une voix intelligible**, le 10″ n'apporte que le corps sous ~120 Hz. Les
2-5 kHz viennent des tweeters des ICU, d'où l'importance de leur orientation (§4,
point 3).
