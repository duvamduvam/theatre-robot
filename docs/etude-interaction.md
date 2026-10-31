# Plan d'interaction — David, Didier et le public

*Ouverte le 2026-09-13, à la demande de David (« on doit faire un plan
d'interaction, c'est important »), après la première vraie conversation
d'atelier entre lui et Didier.*

> **Ce document est une PROPOSITION.** Rien n'y est tranché tant que David ne
> l'a pas démonté. Les passages marqués **[DÉCIDÉ 13/09]** sont les seuls
> acquis : ce sont ses réponses de la séance, pas mes conclusions.

> ⚠️ **Ce dépôt est PUBLIC.** Le dossier de création du spectacle vit hors
> dépôt (Nextcloud, `créa/théâtre/spectacles/paradise-quest/`). Cette étude
> n'en cite que ce qui justifie une décision technique. Si David juge qu'une
> citation est de trop, elle saute — c'est son texte, pas le mien.

---

## 0. Pourquoi cette étude existe

Deux études encadrent déjà la parole de Didier :
[`etude-declenchement-conversation.md`](etude-declenchement-conversation.md)
(quand et comment il engage un passant) et
[`etude-voix-didier.md`](etude-voix-didier.md) (avec quelle voix). Elles sont
bonnes, et leurs décisions tiennent.

Mais elles ont le même angle mort : **elles ne parlent que du passant.** David
n'y existe pas — alors qu'il est sur scène, qu'il joue, et qu'il est déjà une
source de parole. Or il a dit le 13/09 la phrase qui commande tout le reste :

> « Je suis un personnage pour le public. Tout ce projet en entier est un
> prétexte pour que je joue, moi. »

Cette étude se place donc **au-dessus** des deux autres : elle arbitre le
partage entre David, Didier et le public. Elle ne re-tranche rien de ce qui
l'est déjà (§2).

Sa source première n'est pas le code : c'est la **note de création** du
spectacle (dossier hors dépôt, état du 2026-08-27). Le spectacle existait
avant le robot conversationnel ; c'est à l'IA de servir la dramaturgie, pas
l'inverse.

---

## 1. Le renversement — Didier n'est pas un robot autonome

Tout le travail conversationnel jusqu'ici visait, implicitement, un robot
capable de tenir seul un échange : détecter qu'on lui parle, comprendre,
répondre. C'est la cible qui a rendu la séance du 13/09 frustrante — David a
constaté qu'il avait « du mal à voir comment ça pourrait être le robot
au-delà des interactions en petit groupe ».

**Il a raison, et la bonne réponse n'est pas de renforcer le robot : c'est de
changer de cible.** Didier est un **instrument de jeu**. La question n'est
plus « comment le rendre capable de converser seul », mais « que doit-il
savoir faire pour que David joue avec lui devant un public ».

Conséquence immédiate sur le cahier des charges de l'IA — il **rétrécit** :

| On croyait devoir | En fait il faut |
|---|---|
| comprendre finement ce qu'on lui dit | détecter qu'on lui a répondu, et dans quel registre |
| décider seul où aller | faire avancer une mission dont les étapes sont écrites |
| être autonome | être pilotable *en jeu*, sans sortie de personnage |
| tenir 2 h de conversation | tenir cinq cases et une liste de noms |

---

## 2. Ce qui est déjà tranché — ne pas re-trancher

**Dans la note de création (dossier du spectacle, 27/08)** :

- **« Deux boulets, la rue est l'oracle »** : David et Didier sont tous deux
  incompétents, le public détient la connaissance, ils n'avancent que sur les
  indications des passants. C'est une inversion de hiérarchie voulue.
- **La règle du « oui, et »** : *toute* réponse d'un passant devient une
  avancée — la blague prise au premier degré, le refus salué comme « une
  indication très dense ». « Le passant ne doit jamais avoir le sentiment de
  s'être trompé. »
- **Cinq critères, cinq mouvements** : Didier possède cinq critères
  (*love, tenderness, friendship, speed, strong*) et aucune valeur ; chaque
  rencontre en valide un ; une **jauge visible** progresse ; cinq séquences
  écrites servent de filets.
- **La validation comme moteur d'agrégation** : qui donne une indication
  reçoit une contrepartie visible (grade, numéro) et devient partie prenante.
- **La fin** : les cinq critères réunis, les coordonnées du paradis sont
  *ici, maintenant, avec ces gens-là* — « le paradis est littéralement fait
  de ce qu'ils ont dit ».

**Dans les études existantes du dépôt** : la FSM d'engagement et ses seuils
(§5.2 de l'étude déclenchement), le « réactif d'abord », le gate half-duplex,
la latence cible < 2 s, les personas commutables.

**Décidé par David le 13/09, en séance** :

- **[DÉCIDÉ 13/09] Il est un personnage pour le public**, pas un servant
  invisible.
- **[DÉCIDÉ 13/09] Aucune écoute préalable.** Il ne peut pas entendre les
  répliques avant le public : ça exige de sortir du jeu pour se concentrer,
  et surtout ça ne servirait à rien — *« je fais quoi si la sortie ne me
  plaît pas ? Je coupe tout, j'envoie un texto ? Non, c'est trop compliqué,
  j'assume. »* Un contrôle qu'on ne peut pas actionner n'est pas un contrôle.
- **[DÉCIDÉ 13/09] Aucune frontière jeu / régie.** Tout pilotage doit être
  intégré au jeu : *« si je dois sortir du jeu pour changer les instructions,
  c'est compliqué »*.
- **[DÉCIDÉ 13/09] Il doit pouvoir reprendre la main** si Didier « fait
  n'importe quoi » — mais en jeu, donc.
- **[DÉCIDÉ 13/09] Didier parle aux autres, pas seulement à David.** Il doit
  donc entendre le public : le problème de captation ne se dissout pas.
- **[DÉCIDÉ 13/09] Le paradis ne se trouve pas.** Et la raison est le fond du
  spectacle, dans les mots de David : *« le paradis est diabolique plutôt, il
  nous détache de l'instant dans l'espoir d'un autre instant plus adapté à la
  perception de nous-même »*. La fin de la note de création dit la même chose
  par l'autre bout : les coordonnées sont ici et maintenant.

---

## 3. Les trois décisions demandées

### 3.1 Déclenchement de la parole — une réplique, jamais un bouton

**Proposition.** Didier ne décide pas seul quand il parle. David lui donne la
parole **en s'adressant à lui à voix haute, en personnage** : « Alors Didier,
qu'est-ce que t'en dis ? », « Didier, demande-lui. »

Pourquoi c'est le bon mécanisme, et pas un pis-aller :

- c'est **déjà du théâtre** — le public lit une relance de jeu, pas une
  commande ; l'exigence « intégré au jeu » est satisfaite par construction ;
- la réplique **cadre** la réponse en même temps qu'elle la déclenche : ce que
  David dit oriente ce que Didier répond. Il pilote en jouant ;
- ça **supprime la question la plus dure** côté David : plus besoin de deviner
  quand *lui* a fini de parler, puisque c'est lui qui rend la parole ;
- ça **ne coûte rien de plus** à David, qui devrait de toute façon dire une
  réplique à cet endroit-là — point important au vu de la charge déjà lourde
  identifiée au §7.7 de la note de création (« le troisième larron »).

⚠️ **Le piège à ne pas reproduire.** Un mot-clé de réveil rigide (« Didier ! »
et rien d'autre) ferait exactement ce que David refuse : sortir du jeu, sous
un déguisement. Le déclencheur doit accepter **la variété d'une réplique
jouée**, donc être reconnu par le sens et non par la forme exacte. C'est un
travail de reconnaissance souple, pas une comparaison de chaîne.

**Reprise en main — même mécanisme, autre intention.** Reprendre la main, ce
n'est pas couper : c'est **faire avancer la mission**. « Bon, Didier, critère
suivant » est à la fois une réplique et une transition d'état. La structure
en cinq mouvements est donc **l'interface de pilotage** : les cinq filets de
sécurité de la note de création deviennent littéralement les cinq commandes.

### 3.2 Mémoire — cinq cases et des noms, pas une fenêtre glissante

**Le désaccord du 13/09 n'était pas sur la taille de la mémoire, il était sur
sa nature.** David : *« pourquoi doit-on avoir une limite ? Si je déambule
2 h, ça va être juste. »* Il a raison sur le constat (6 échanges, c'est
absurdement court) et le remède n'est pas d'allonger la fenêtre.

Ce que le spectacle exige réellement de la mémoire, c'est **ce que la finale
restitue** : qui a donné quoi, pour quel critère. Une structure minuscule :

```
mission:
  critères: love / tenderness / friendship / speed / strong
  pour chacun : valeur donnée, par qui (prénom, signalement), numéro de guide
  direction courante (la dernière indication reçue)
```

Trois propriétés qui découlent de la dramaturgie, pas de la technique :

- **permanente sur toute la déambulation** — c'est le fil du spectacle ;
- **minuscule** — quelques dizaines de mots, donc gratuite en latence, alors
  qu'un historique de 2 h se paierait à *chaque* réplique (l'historique est
  renvoyé en entier à chaque tour : c'est là qu'était la vraie raison de la
  limite) ;
- **distincte de la conversation en cours**, qui, elle, reste volatile et
  meurt avec la rencontre — conforme aux sessions déjà décidées au §5.2 de
  l'étude déclenchement (et jamais implémentées : `chat_node` n'ouvre
  aujourd'hui qu'une seule session, au démarrage du node).

Conséquence heureuse : la jauge visible réclamée par la note de création
**est** cet état, affiché. Didier a un visage et un corps en LED — elle peut
y vivre sans matériel supplémentaire.

⚠️ Un contrat mort à réveiller ou à enterrer : le prompt demande déjà à
Didier d'émettre `{"name": …}` quand on se présente, et `NAME_KEY` existe
dans le parseur — **rien ne le consomme**. C'est exactement la brique qu'il
faut pour la liste des guides.

### 3.3 La réponse non comprise — le « oui, et » devient un contrat technique

C'est la trouvaille de la séance, et elle est dans le dossier depuis le 27/08
sans qu'on l'ait vue : **la règle du « oui, et » est une tolérance aux erreurs
de compréhension.** Le tableau de la note de création ne demande jamais à
Didier de comprendre juste — il demande de *faire quelque chose* de n'importe
quelle réponse.

Donc, comme règle d'écriture du personnage :

- une transcription douteuse **n'est pas un échec, c'est une matière** : un
  robot qui entend « c'est fermé » là où on a dit « au fournil » est le
  numéro, pas la panne ;
- **ne jamais faire répéter plus d'une fois.** Faire répéter est l'aveu du
  dispositif ; c'est aussi ce qui met le passant en faute, ce que la règle
  d'or interdit ;
- **rien n'est jamais une mauvaise réponse** — y compris pour le silence et
  le refus, qui ont déjà leur réplique écrite.

⚠️ Ce que ça ne dispense PAS de faire : **détecter qu'une réponse a eu lieu,
et quand elle se termine.** C'est le point sur lequel David m'a repris à
juste titre — la tolérance porte sur le *contenu*, jamais sur la *détection*.
Voir §6.

---

## 4. Ce que ça change dans le code

Rien de ce qui suit n'est à faire avant validation de l'étude. C'est la
traduction, pour mesurer le coût.

1. **Deux boucles au lieu d'une.** Aujourd'hui `ConversationEngine.run_once`
   est un cycle unique et bloquant : écouter → transcrire → répondre. Il faut
   séparer une **perception continue** (qui tourne toujours) d'un **acte de
   parole** (déclenché). C'est le changement structurel principal.
2. **Un état de mission**, porté par un module pur et testé (patron du dépôt :
   la logique sans ROS, le node autour), publié en topic latché pour la jauge
   et la console, et alimenté par les transitions de §3.1.
3. **Sessions par rencontre** — décidées en juillet, jamais faites.
4. **Consommer `{"name"}`** pour la liste des guides (§3.2).
5. **Deux entrées audio** (§6) : `MicCapture` n'ouvre aujourd'hui qu'un seul
   périphérique.
6. **La jauge sur le visage/corps LED** — chemin existant (`robot_lights`,
   expressions), aucune électronique à ajouter.

---

## 5. Garde-fous — puisqu'il n'y a pas d'écoute préalable

L'étude de juillet avait explicitement reporté la question : « confiance au
modèle pour l'instant, à réévaluer après les premières sorties ». Deux
éléments nouveaux justifient de la rouvrir **avant** la première sortie :
David découvrira chaque réplique en même temps que le public
(**[DÉCIDÉ 13/09]**), et l'objectif du spectacle est de tenir un **groupe**,
pas un passant isolé — ce qui multiplie le coût d'un dérapage.

Ce qui protège, par ordre d'efficacité réelle :

1. **la brièveté** — une réplique de deux phrases dérape moins qu'une tirade,
   et se rattrape en jeu ;
2. **le cadre de mission** — Didier a toujours une question à poser, il
   improvise donc *dans* une séquence à objectif connu, pas dans le vide ;
3. **la règle d'or du dossier** — viser le dispositif, jamais les gens ; le
   passant n'est jamais en faute. C'est une règle de sécurité autant que de
   politesse ;
4. **la reprise en main en jeu** (§3.1), qui est le vrai filet ;
5. le persona lui-même, qui porte déjà des esquives (opinions absurdes sur
   des sujets sans enjeu) — utile, mais c'est le plus faible des cinq, et il
   ne faut pas lui faire porter la sécurité à lui seul.

⚠️ **Point à trancher par David** : les enfants. Le dossier prévoit que la
distance se joue (« Didier a peur qu'on le touche, il recule ») plutôt
qu'elle ne s'impose. Si l'IA parle aux enfants, le registre doit être verrouillé
au-delà de ce que fait le socle actuel des personas.

---

## 6. Les deux oreilles

**Le problème ne se dissout pas** (correction de David, 13/09) : Didier parle
aux passants, donc il doit les entendre. Mais les deux oreilles n'ont pas le
même cahier des charges.

| | Entendre David | Entendre le public |
|---|---|---|
| Distance | proche | 2-4 m, en cortège |
| Bruit | maîtrisé | rue, foule |
| Ce qu'il faut en tirer | **le sens** (c'est un pilotage) | **qu'on a répondu**, et le registre |
| Difficulté | faible **si** canal dédié | élevée, durablement |

**Côté David.** Son micro HF actuel sert la ventriloquie, dont il souhaite
plutôt se séparer — mais *abandonner la ventriloquie et donner une oreille
propre au Pi sont deux décisions distinctes*. Le Pi accepte n'importe quelle
carte son USB sans pilote (c'est déjà le cas du ReSpeaker). Deux chemins :

- **sans rien acheter** : dériver la sortie ligne du récepteur HF vers
  l'adaptateur USB C-Media déjà en stock — ça teste l'idée avant d'engager
  quoi que ce soit ;
- **proprement** : un système micro sans fil dont le récepteur *est* une carte
  son USB, branché directement sur le Pi.

⚠️ Correction d'une erreur que j'ai écrite en séance : **la mixette reste
indispensable** — elle porte la sortie (enceintes, niveaux, mélange). Un micro
USB sur le Pi n'enlève rien à la chaîne son.

⚠️ Question ouverte si l'on garde le HF : ce micro porterait *deux* voix —
celle de David en personnage, et Didier ventriloqué. Il faut savoir comment
les séparer (canal, coupure de l'octaver, ou David ne parle jamais « en
David » dans ce micro).

**Côté public.** Rien ne rendra la captation facile. Deux leviers déjà payés
et inexploités : une **VAD neuronale** à la place du seuil d'énergie actuel
(§6 bis), et la **direction d'arrivée du son** du ReSpeaker.

⚠️ **La direction est un BONUS DE CONFIANCE, jamais un VETO** — correction
apportée par David le 13/09, et elle est juste. Le faisceau du XVF3800 se
verrouille sur la source **dominante**, pas sur la parole : un scooter plus
fort qu'un passant, et l'angle part sur le scooter. S'en servir comme filtre
(« je rejette ce qui ne vient pas de la bonne direction ») fabriquerait une
nouvelle façon de rater des phrases valides — donc **une régression déguisée
en amélioration**. La règle : la direction peut RENFORCER une détection
(parole + ça vient de la personne regardée → on y va franchement), elle ne
doit jamais en ANNULER une.

⚠️ **Le socle plastique est suspect, et c'est mesurable** (objection de David,
13/09) : un réseau de micros a besoin d'un champ libre : un support fermé crée
des réflexions qui dégradent d'abord la **discrimination spatiale**, donc
précisément la direction. La fiche matériel note déjà la fixation comme
question ouverte (découplage, garde d'air, décalage d'azimut fixe). Le corpus
de rue (§6 ter) est ce qui tranchera, au lieu d'en débattre.

---

## 6 bis. Remplacer la détection de NIVEAU par une détection de VOIX

**L'état actuel, sans ménagement.** `EnergyVad` ne mesure qu'une énergie. Son
seuil est le plancher de bruit **calibré une seule fois au démarrage × 1,3**,
et la fin de phrase est déclarée après **600 ms de silence continu**. Aucune
notion de voix : un klaxon franchit le seuil comme une phrase. En rue, deux
modes de défaillance certains — un seuil figé au démarrage devient faux dès
qu'on change de rue, et « 600 ms de silence » n'arrive jamais, donc **la fin
de phrase n'arrive jamais**.

**Ce qu'on remplace, et ce qu'on garde.** Le module fait DEUX choses collées :
le *verdict par trame* (faux) et la *machine à états* IDLE↔SPEECH avec ses
trois trames de confirmation, ses 600 ms de fin et son pré-roll de 450 ms
(bonne, testée, et elle encode des leçons réelles — le pré-roll existe parce
que les débuts de phrase se perdaient). **Seul le verdict change.**

Découpage à respecter pour ne pas perdre la testabilité en CI (patron du
dépôt : la logique pure d'un côté, l'I/O de l'autre) :

- un **détecteur** `is_speech(frame) -> probabilité` — impur, fait tourner le
  modèle, isolé ;
- une **machine à états** qui ne reçoit qu'une probabilité — pure, testable
  sans aucun modèle, et c'est l'actuelle, à peine retouchée.

`EnergyVad` devient alors *une* implémentation du détecteur parmi deux, ce qui
rend le A/B trivial sur le même corpus.

**Trois gains concrets, dont un inattendu :**

1. **La calibration disparaît.** Plus de « médiane des 1000 premières ms »,
   donc plus le robot calibré près d'un carrefour qui reste sourd.
2. **Le seuil devient absolu et transférable.** Un seuil de probabilité vaut
   dans toutes les villes ; le seuil de niveau, lui, est attaché à une chaîne
   d'acquisition ET à un lieu — piège payé le 13/09 avec un casque Bluetooth
   qui mettait le bruit de pièce à RMS 3000-9000 pour un seuil à 2800.
3. **La fluidité s'améliore aussi** (plainte de David le matin même) : « fin
   de phrase » ne veut plus dire « niveau bas » mais « pas de voix », ce qui
   existe même dans le bruit. Le délai de fin peut donc descendre sans risque.

**⚠️ Le gate anti-larsen, lui, RESTE sur le niveau — et c'est correct.** Il
pose une question de *volume* (« ma sono est-elle vivante ? »), pas de
*nature*. Et il le doit : la voix de Didier EST de la parole — une VAD
neuronale dirait « parole ! » sur sa propre voix. Les deux questions se
séparent proprement ; les confondre est précisément le défaut qu'on corrige.

### Candidats — faits sourcés le 2026-09-13

| | Silero VAD | TEN VAD | WebRTC VAD |
|---|---|---|---|
| Licence | **MIT** | Apache 2.0 « avec conditions additionnelles » (à lire mot pour mot) | non vérifiée |
| Neuronal | oui | oui | **non** (algorithme classique) |
| Modèle | ~2 Mo, ONNX + torch JIT | lib 306 Ko (Linux x64), modèle ONNX ouvert | extension C |
| Fréquence | 8 et 16 kHz | 16 kHz seulement | 8/16/32/48 kHz |
| **Bloc d'entrée** | **512 éch. @16 kHz, FIXE depuis la V5** | 160 ou 256 éch. (10 / 16 ms) | 10/20/30 ms |
| Sortie | probabilité par bloc | score 0–1 (seuil 0,5) | booléen |
| ARM / Pi | ONNX documenté comme le chemin hors x86 | **aucun binaire Linux ARM trouvé** (x64, Android, iOS, macOS) | compilable, non confirmé sur Pi 5 |

Détection annoncée à 5 % de fausses alertes : **WebRTC 50 %, Silero 87,7 %**.
⚠️ **Ce chiffre vient du blog d'un éditeur concurrent qui vend son propre VAD**
— cité parce que c'est la seule mesure tierce chiffrée trouvée, pas parce
qu'il fait autorité. La même source donne ~43 % de CPU pour Silero sur un Pi
Zero ; un Pi 5 est d'un autre ordre, mais **c'est à mesurer chez nous**, le
Pi 5 faisant déjà tourner whisper et piper (`mesure-cpu-conversation.sh`).

**Observation d'intégration.** Nos trames font **480 échantillons** (30 ms à
16 kHz, `MicCapture(frame_ms=30)`). Silero en veut **512** → ré-assembleur à
cheval sur les trames, et c'est un **piège silencieux** : mal découpé,
certains modèles ne protestent pas et rendent des résultats dégradés. TEN
accepte un pas de **160** → notre trame en contient exactement trois, le
découpage tombe juste. Ce n'est pas décisif seul, mais ça se paie en bugs.

**Proposition** : **Silero par défaut** (licence la plus propre, chemin ARM
documenté, onnxruntime **déjà présent dans l'image en 1.30.0** — apporté par
piper, donc zéro dépendance nouvelle), **TEN en challenger**, départagés sur
NOTRE corpus — pas sur des comparatifs où chacun mesure son propre produit.

**Deux précautions à graver** : **figer la version** (Silero a changé sa
taille de fenêtre entre versions et rendu onnxruntime optionnel en cours de
route — deux ruptures qui casseraient en silence), et **tester le
ré-assemblage des blocs comme une unité à part entière**.

---

## 6 ter. Comment mesurer sans public — le corpus de rue

L'objection de David : *« je ne vois pas bien comment tester petit à petit,
surtout sans public et pas avec les mêmes conditions sonores »*. Elle se
dénoue en séparant ce qui a besoin du **public** de ce qui a besoin du
**bruit** : le problème de détection n'a besoin que du second.

L'outillage existe et n'a **jamais servi** : script d'enregistrement en rue et
rejeu d'un fichier dans la VAD **de production** (lot D0, 13/07). Il lui
manque de **compter**.

⚠️ **Cadre légal — on n'enregistre pas les conversations des passants.** Le
§5.7 de l'étude déclenchement impose un dispositif type tournage (affichage
visible, accord demandé après l'échange, effacement par défaut) : hors
spectacle, on ne l'a pas. Et c'est heureux, car pour **mesurer** une détection
il faut connaître la vérité terrain — donc de la parole qu'on a provoquée.
Ce qu'on enregistre : l'**ambiance** (c'est elle qu'on vient chercher) et de
la **parole volontaire**, la sienne ou celle d'un complice.

**Protocole (première campagne : festival, 13/09 après-midi).** ReSpeaker
dans son support imprimé, à la hauteur qu'il aura sur Didier. Quatre ambiances
(coin calme / foule / près d'une sono / en marchant), et pour chacune :
annonce à voix haute du contexte (l'enregistrement se documente lui-même),
30 s de silence (le plancher décide de tout), puis de la parole à 1, 2, 3 et
4 m en annonçant la distance, et enfin des **réponses courtes du type que
Didier recevra** (« par là », « c'est fermé », un refus, une blague).
**Prises longues et continues** : le seuil actuel se calibrant au démarrage,
une prise longue montre *à quel moment* il devient sourd — une prise courte le
cacherait. Dire aussi l'orientation du micro (c'est ce qui permettra de juger
le socle).

⚠️ Le corpus doit être enregistré avec le **montage définitif** : micro tenu à
la main, on mesurerait une autre machine que celle qui jouera.

**Et un troisième levier, qui est du jeu.** Si Didier entend mal les
étrangers, le montrer plutôt que le cacher : **David relaie.** Il répète, il
traduit, il s'agace. Le public lit un vieux robot un peu sourd — un caractère,
pas une panne — et l'objection que David soulevait lui-même (« deux niveaux de
compréhension, c'est moins lisible pour le public ») tombe, parce qu'elle
n'est illisible que tant qu'elle est dissimulée.

---

## 7. Ce qui reste ouvert

- **Le commentaire du monde** (le bâtiment bizarre, le sol irrégulier). David
  n'a pas tranché s'il est déclenché ou spontané. L'étude note seulement qu'il
  n'est **pas structurant** : les raisons concrètes d'avancer viennent des
  cinq critères, pas de la perception. C'est un bonus, à ouvrir quand le reste
  tient. Techniquement il faudrait un chemin image → langage (il existe à
  moitié dans l'ancien code GPT-4o, jamais relié à la conversation actuelle),
  et il devra consommer le flux JPEG déjà publié par le suivi de personne —
  **surtout pas rouvrir la caméra**, tenue en exclusif.
- **La voix** reste suspendue au lot V0 du chantier voix. Si David abandonne
  la ventriloquie, cet arbitrage change de nature : ce n'est plus « assurer la
  continuité entre deux sources » mais « choisir la voix de Didier ». À
  reprendre là-bas, pas ici.
- **L'écriture des cinq séquences** (note de création §8) : c'est elle qui
  dira ce que Didier doit savoir dire à chaque mouvement.
- **Le troisième larron** (note de création §7.7). Si un régisseur existe, une
  partie du pilotage peut lui revenir — ce qui changerait §3.1.

---

## 8. Convergence à signaler — la note de création et le tableau de bord disent la même chose

Le §7.2 de la note de création (27/08) exige « un arrêt d'urgence physique
(coup de poing) accessible sur le robot, atteignable par David en un geste »
comme condition pour qu'une date soit assurable.

Le tableau de bord du dépôt (30/08, indépendamment) a établi que **`e_stop`
n'a aucun publieur**, que les deux boutons du dos font l'inverse de ce que
leur nom promet (ils éteignent le Pi, donc provoquent un emballement), et que
la carte qui porterait le coup-de-poing n'est pas fabriquée.

Les deux documents décrivent le même trou par les deux bouts. **Aucune
déambulation publique n'est possible avant que ce point soit fermé** — c'est
antérieur à tout ce que cette étude propose.

---

## 9. Plan d'implémentation

Quatre phases, chacune avec un **verrou de sortie** : on ne passe à la suivante
qu'une fois qu'il est franchi. Le principe qui les ordonne : **mesurer avant
de construire**, parce qu'aujourd'hui tout le monde argumente à l'intuition.

### Phase A — mesurer (rien à construire, ou presque)

1. **Corpus de rue** (§6 ter) — première campagne au festival du 13/09.
2. **Rejeu chiffré** : l'outil existe (rejeu d'un wav dans la VAD de prod, lot
   D0 du 13/07, jamais servi) ; il lui manque de **compter** — phrases
   détectées, fausses alertes, fins de phrase ratées, latence de fin, par prise.

> **Verrou de sortie : on sait de combien c'est mauvais, en nombres.**

### Phase B — la détection (banc + corpus, aucun robot)

1. Découpage détecteur / machine à états (§6 bis), `EnergyVad` devenant une
   implémentation parmi deux.
2. **Silero et TEN comparés sur le MÊME corpus.** On garde celui qui gagne à
   la mesure, jamais celui qui gagne au comparatif de son propre éditeur.
   Ré-assemblage des blocs testé à part (480 → 512).
3. Direction en **bonus de confiance, jamais en veto** (§6).
4. **Questions fermées** dans l'écriture du personnage : gain de robustesse
   qui ne coûte pas une ligne de code — « c'est par là ? » appelle un mot
   fort et un geste, « vous êtes heureux ? » appelle trois phrases hésitantes.
5. Coût CPU mesuré sur le Pi 5, qui fait déjà tourner whisper et piper
   (`mesure-cpu-conversation.sh`).

> **Verrou de sortie : une amélioration MESURÉE sur le corpus, pas une
> impression.**

### Phase C — l'interaction (banc PC, pendant l'immobilisation de Didier)

| Lot | Contenu |
|---|---|
| **I0** | État de mission (module pur + topic latché) et **jauge sur le visage LED** — colonne vertébrale, et visible tout de suite |
| **I1** | Déclenchement de parole en jeu + transitions de mission par réplique (§3.1) |
| **I2** | Mémoire des guides (`{"name"}` enfin consommé) + sessions par rencontre |
| **I4** | Contrat « oui, et » dans l'écriture (§3.3) + garde-fous (§5) |

> **Verrou de sortie : une déambulation se joue de bout en bout en
> simulation, avec David.**

### Phase D — le réel (bloquée par le retour de Didier)

Montage définitif du ReSpeaker puis **re-mesure du corpus** (le socle, §6) ;
**I3** deuxième oreille et arbitrage des deux entrées ; répétition à froid
dans la rue, sans public ; puis petit public.

### ⚠️ Le verrou qui domine tout

**Aucune sortie publique avant que le coup-de-poing existe** (§8). Il ne dépend
d'aucune des quatre phases et il est antérieur à toutes.

### Ce qui se fait pendant l'immobilisation du robot

Phases **A**, **B** et **C** entièrement — corpus, détection, interaction. Seule
la phase D attend le matériel. Autrement dit : l'immobilisation ne bloque rien
de ce qui reste à décider.

---

## 10. Le rythme de la déambulation — le chemin et les arrêts [DÉCIDÉ 31/10]

*Grillé avec David le 2026-10-31, après une séance « Chantiers » jouée seul à
la page scène. Les réponses ci-dessous sont les siennes ; les mécanismes
proposés pour les servir sont à valider au code.*

### 10.1 Le constat (séance du 31/10)

David : « il faut qu'on trouve l'équilibre entre le chemin et les arrêts,
juste s'avancer n'est pas suffisant ». Les **trois défauts à la fois** :

- **la marche est vide** — hors séance, Didier traverse les 30 objets sans
  s'y intéresser (`poi_enter_ignored : before_start`) ;
- **les arrêts sont subis** — Didier s'est arrêté de lui-même (clé `marche:
  stop` sans limite de fréquence), puis restait figé (le « go » vocal est
  refusé hors séance) ;
- **David n'a aucune prise** — il ne choisit ni où Didier va, ni où il
  s'arrête.

**Principe [DÉCIDÉ 31/10] : le but n'est pas l'arrivée mais le chemin.** Un
arrêt intéressant peut durer **15 minutes** ; aucun minuteur ne doit couper
une scène qui vit. Critère de réussite : **une séance en sim sans ennui**.

### 10.2 Qui décide d'un arrêt [DÉCIDÉ 31/10]

| Source | Règle |
|---|---|
| **David** | arrête et relance quand il veut : « stop » en clair (urgence), Route OFF, curseur — et les **deux mots secrets** (§10.3) |
| **Didier** (lubie) | **au plus un arrêt de lui-même toutes les 2 min** (≈ 6 sur la traversée), qu'il **réclame d'abord en mots** (« attends, le pigeon ! ») ; **refusable** : si David dit non, il râle mais continue |
| **Jeu « Va voir le… »** | David nomme un objet, Didier y va (§10.4) |
| **Régisseur** | reste pour les **pannes** ; les lubies ne sont plus des arrêts imposés tirés au sort, ce sont les demandes de Didier ci-dessus |

### 10.3 Les mots secrets — signaux de comédien [DÉCIDÉ 31/10]

Un « go » ou un « stop » s'entend : le public voit la ficelle. David dispose
de **deux expressions secrètes**, glissées dans une phrase normale :

- une **de relance** — Didier conclut son arrêt en une réplique (« bon, j'ai
  assez vu ce chat ») puis repart ;
- une **d'arrêt en jeu** — Didier s'arrête et trouve une raison en personnage
  (« tiens, qu'est-ce que c'est que ça ? »).

Paire retenue le 31/10 parmi trois propositions (des expressions de deux mots
ou plus : bien plus robustes au déclenchement accidentel qu'un mot isolé).
**Les valeurs ne sont PAS écrites ici** (dépôt public) : elles vivent dans la
configuration locale du banc. Détection **déterministe** sur la
transcription, comme l'arrêt d'urgence (`vision/ai/emergency.py`) — jamais
laissée au LLM. Didier ne doit jamais les prononcer (interdit dans son
prompt). « Stop » en clair reste l'arrêt d'urgence, inchangé.

### 10.4 Le jeu « Va voir le… » — premier jeu [DÉCIDÉ 31/10]

1. David nomme un objet du chemin avec ses mots (« le panneau violet »).
2. Didier le reconnaît parmi les points d'intérêt de l'itinéraire.
3. Il **roule jusqu'à l'objet**, s'arrête à sa hauteur, puis **pivote face à
   lui** — la caméra (fixée au buste) le voit de face, la réflexion le
   regarde, Didier le commente ou part dans sa lubie.
4. Objet **déjà dépassé** : Didier **fait demi-tour** et y retourne.
5. Au départ, il se réaligne sur le chemin.

⚠️ **Pivot sur place et demi-tour sont des mouvements NOUVEAUX du chemin
roues** : conception, revue adversariale, validation en sim. Ils sont
**SIM-ONLY** : le cheminement lit la vérité terrain de Gazebo, le vrai robot
n'a pas encore d'odométrie — rien de ceci ne passe au réel avant elle.

### 10.5 La relance [DÉCIDÉ 31/10]

- David relance quand il veut (mot de relance, « go », curseur).
- **Didier repart de lui-même si la scène meurt : 90 s sans que David lui
  parle** — la réflexion peut le proposer plus tôt si l'objet est épuisé,
  mais le départ effectif attend ce seuil.
- **Seulement après un arrêt de SON fait** (lubie, « va voir ») : après un
  « stop » ou le mot d'arrêt de David, il reste arrêté jusqu'à une relance
  de David. ⚠️ Cela assouplit la règle de la revue du 23/10 (B1 : un tour
  spontané n'émet jamais « go ») : l'exception doit être étroite, testée, et
  repasser en revue adversariale.

### 10.6 Vérification [DÉCIDÉ 31/10]

Une séance « Chantiers » de 15 min jouée par David, jugée sur :

- **son verdict à chaud** — trois notes sur 5 : la marche (vide ?), les arrêts
  (subis ?), sa prise sur le jeu. C'est le critère qui tranche ;
- **les mesures du journal du régisseur** (`log/rehearsal/*.jsonl`) — part du
  temps en marche / à l'arrêt, arrêts par source (David, Didier, va voir),
  durée de chacun, nombre de fois où David a dû forcer (Route OFF, curseur).

### 10.7 À faire, dans l'ordre

1. **Prérequis livré le 31/10** : « stop » entendu pendant que Didier parle
   (écoute garde, vision — en revue/correction ce jour), sinon aucune de ces
   règles n'est jouable en marche.
2. Mots secrets (vision : détection déterministe + prompt ; config du banc).
3. Lubies réclamées et refusables, plafond 1 / 2 min (prompt + régisseur).
4. Relance autonome à 90 s, étroite (vision + régisseur, revue adversariale).
5. « Va voir le… » sans pivot ni demi-tour d'abord (arrêt à hauteur) — jouable
   vite ; puis pivot, puis demi-tour (chemin roues, sim, revue).
6. Outil de mesure de séance sur le journal JSONL + séance de vérification.

### 10.8 Ouvert

- Reconnaissance de l'objet nommé : liste d'alias par POI écrite à la main,
  ou laissée à la réflexion (qui voit l'image) ? À trancher au lot 5.
- Comportement si deux demandes se croisent (Didier réclame une lubie pendant
  un « va voir »).
- Le monde Chantiers n'a **aucun passant modélisé** : en source caméra
  Gazebo, personne n'est jamais détecté (séance R0 de l'étude répétition
  jamais faite).
