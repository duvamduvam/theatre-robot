# LED témoin 5 V allumée alors que le convertisseur 24 → 5 V est débranché

> **Diagnostic établi sur pièces (manuel constructeur), PAS encore mesuré au
> multimètre.** Deux mesures de dix secondes le confirment ou l'infirment (§Vérification).

- **Date/contexte** : 2026-11-03, 00h18, atelier, robot en pièces (gel du Pi 4 depuis
  le 12/09). David recâble l'alimentation. Vidéo de 52 s, muette (images clés dans
  `../hardware/photos/2026-11-03-led-5v/`, vidéo complète restée sur le téléphone).
- **Symptôme** (constaté par David) : le convertisseur 24 → 5 V n'est **pas branché**
  (bornier vert débrochable en main, image `f009`), pourtant la **LED 5 V de la carte
  porteuse s'allume** (`f007`, `f026`). Quand il débranche le **rail moteur 12 V**, la LED
  s'éteint. En isolant, c'est le **servo de la bouche** (ASME-MR) qui alimente le 5 V.
  Ces deux circuits ne sont pas censés être reliés.
- **Traces** : vidéo `VID_20261103_001821.mp4` (Xiaomi, DCIM) ; aucune trace logicielle,
  robot hors tension.

## Cause (établie sur le manuel, à confirmer par mesure)

**Le servo de la bouche est un petit BEC.** La carte rouge des servos ASME (famille
Wingxine : ASME-02/04/05/MR) embarque **son propre régulateur 5 V**, et le connecteur
3 points `S / + / -` peut **sortir ce 5 V sur la broche `+`**, selon un cavalier.
Manuel constructeur (`../hardware/datasheets/ASME-02-series-wingxine-manual.pdf`,
texte original) :

- *« Signal line "5V" output or floating select »* — c'est la fonction du **cavalier
  n° 1** de la carte (positions `NC` / `5V`), le petit cavalier jaune visible sur la
  photo produit `arm-motor.png`.
- En mode PWM, cavalier en `NC` : *« Because the servos is an independent power supply,
  no electricity from the signal line to go so "+" does not require wiring. »* — le fil
  rouge **ne doit pas être câblé**.
- *« WARNING: the servos output "+5 V" power supply can only meet the potentiometer used
  to supply power, prohibit the use of servos for [other purposes]. »* — ce 5 V est prévu
  pour un potentiomètre de consigne, rien d'autre.

Chaîne observée : rail 12 V → carte du servo bouche → son régulateur interne → broche
`+` du connecteur 3 points → fil rouge → rangée `V+` du PCA9685 (ou directement le 5 V
de la carte porteuse) → **rail 5 V du robot**, d'où la LED. Couper le 12 V coupe le
servo, donc le 5 V fantôme. Les deux circuits sont bien reliés : **par le fil rouge du
servo**, qu'un servo RC classique utilise comme entrée et que celui-ci utilise comme sortie.

Le cavalier est soit en position `5V`, soit la variante MR sort le 5 V d'office (ADIN
0-5 V) : à lire sur la carte.

## ⚠️ Constat aggravant (David, 2026-11-03) : le fil NOIR a fondu sur le PCA9685

En débranchant le connecteur 3 points de la bouche, David a eu du mal à l'extraire :
**le plastique côté fil noir (masse) a un peu fondu sur une broche du PCA9685.**
Une broche de connecteur Dupont fond à quelques ampères : **ce n'est pas le courant
du BEC** (prévu pour un potentiomètre, il s'effondrerait avant). C'est un **courant de
retour moteur qui passe par la masse du signal** : si la masse de puissance du servo
(bornier vert « - ») est mal serrée, oxydée ou trop fine, le moteur (380 kg·cm, plusieurs
ampères au démarrage) retourne au « - » de la batterie par le chemin le plus facile —
fil noir → GND du PCA9685 → masse de la carte porteuse → masse du convertisseur/des Pi.

Conséquences :
- **Les Pi sont sur ce chemin de retour.** Du courant moteur traversant les broches GND
  du GPIO du Pi 4 est une explication plausible de la fumée du 12/09 « côté connecteur
  GPIO », plus sérieuse que le BEC seul. Hypothèse, pas preuve.
- **Risque incendie** : un contact qui chauffe jusqu'à faire fondre le plastique, dans un
  robot en bois, près du public.

À faire AVANT toute remise sous tension :
1. **Ne pas remettre ce connecteur ni cette barrette** : remplacer le boîtier Dupont, et
   inspecter la broche GND du PCA9685 (noircie ? piste GND de la carte décollée ?).
   Continuité GND broche → GND bornier du PCA9685 : doit être ~0 Ω.
2. **Masse de puissance du servo bouche** : resserrer le bornier vert, vérifier section
   du fil et continuité jusqu'au « - » batterie/BMS (< 0,1 Ω attendu). C'est LA cause à
   trouver : un retour moteur sain ne passe pas par le fil signal.
3. Même inspection sur les connecteurs des **deux ASME des bras** et des **JX des yeux**
   (plastique déformé, broche décolorée).
4. Remède durable : le PCA9685 ne doit recevoir que `S` + une masse de **référence**.
   Masse de puissance des servos en étoile au « - » batterie, en fil de section moteur ;
   jamais de retour moteur par la carte porteuse.

## Pourquoi c'est grave (et peut-être pas nouveau)

- Deux régulateurs se disputent le même rail 5 V : le convertisseur principal et un
  régulateur de servo dimensionné pour un potentiomètre. Si **plusieurs ASME** (bouche,
  deux bras) ont le fil rouge câblé, ils sont tous en parallèle sur le rail.
- **Convertisseur principal coupé, le rail 5 V ne tombe pas** : Pi 4, PCA9685, LED du
  visage restent alimentés par un régulateur minuscule → tension qui s'effondre sous
  charge, Pi 4 en brown-out ou dans un état indéfini, impossible d'éteindre proprement.
  C'est exactement la zone de suspects de
  [`2026-09-12-fumee-rpi4.md`](2026-09-12-fumee-rpi4.md) (« côté connecteur GPIO / 5 V,
  l'interface avec le robot », rail 5 V jamais mesuré). Un régulateur 5 V de servo poussé
  au-delà de sa limite par le Pi 4 a de quoi chauffer ; **ça ne prouve rien**, mais la
  fumée est à inspecter aussi **côté carte du servo bouche**.
- Rail 5 V « présent » pendant une coupure = **faux signal de sécurité** pour tout
  protocole qui vérifie l'arrivée 5 V (témoin `firmware/pico_test_5v` compris).

## Vérification (dix secondes chacune, multimètre, robot sans Pi)

1. Convertisseur 5 V débranché, rail 12 V branché : **débrancher seulement le fil blanc
   (signal) de la bouche** → la LED doit rester allumée. **Débrancher seulement le fil
   rouge** → la LED doit s'éteindre. Si c'est l'inverse, la cause est un retour par la
   ligne signal (diode de protection du PCA9685) et non le BEC : moins grave, autre remède.
2. Connecteur 3 points de la bouche débranché, servo sous 12 V : mesurer `+` contre `-`
   → attendu **~5 V**. Lire la position du cavalier n° 1.
3. Même mesure sur les **deux ASME des bras** et la position de leur cavalier.

## Remède (après vérification)

- Sur **chaque ASME** : cavalier n° 1 en `NC` et **fil rouge non raccordé** (retiré du
  boîtier Dupont ou coupé), conformément au manuel. Seuls `S` et `-` vont au PCA9685.
- Mesurer ensuite que le rail 5 V tombe bien à 0 V convertisseur débranché, 12 V présent.
- Les servos JX des yeux (CLS-12V, 12 V sur le fil rouge) sont une autre famille : leur
  rouge est une **entrée** 12 V, à ne pas mettre sur la rangée `V+` si celle-ci est en 5 V.
  À vérifier dans la même séance.

## Prévention

- Graver dans `../hardware/overview.md` § servos : fil rouge des ASME = **sortie** 5 V
  (fait, même commit).
- Toute remise sous tension des Pi (protocole du 12/09) passe par la mesure **rail 5 V
  = 0 V convertisseur débranché**, avant la mesure « 5 V présent ».

## Mise à jour 2026-11-03, 00h55 — deux vidéos de plus (muettes)

- **La fiche déformée venait plutôt du BRAS GAUCHE**, pas de la bouche (David). Les trois
  ASME (bouche + 2 bras) ont la même carte : `ASME-MR`, sérigraphie « 360° Magnetic »
  (`../hardware/photos/2026-11-03-led-5v/a-f11.jpg`). Un bras porte bien plus de couple
  que la bouche : cohérent avec un **retour de courant moteur par le fil noir**.
- Fiche du bras gauche (`b-f19.jpg`) : dessus du boîtier **lustré et boursouflé** sur
  toute la longueur — le plastique a coulé en surface, pas seulement « un peu ».
- **Cavalier introuvable sur la vidéo** : la carte MR n'a pas le même dessin que la
  carte ASME-02 du manuel. On voit deux barrettes jaunes en bas à gauche (un double
  cavalier rose/bleu, un cavalier bleu seul), sérigraphie illisible. **Ne pas toucher
  aux cavaliers à l'aveugle** : ils règlent aussi le mode de commande (PWM / analogique).
- **Remède qui ne dépend d'aucun cavalier** : retirer le fil ROUGE de la fiche côté
  PCA9685 (soulever la languette du boîtier avec une aiguille, extraire le contact,
  isoler le bout à la gaine). Le manuel le dit : le « + » n'a pas à être câblé. À faire
  sur les **trois** ASME. Vérifier ensuite : LED 5 V éteinte convertisseur débranché.
- Fiche du bras gauche : à remplacer (boîtier neuf). La cause de la chauffe (masse de
  puissance au bornier vert) reste à trouver sur ce bras en premier.

## Mise à jour 2026-11-03 — fils 12 V volants (David)

David se rend compte que **les fils à brancher sur le 12 V pour le servo se baladaient**, et
ont pu toucher quelque chose. Sur la première vidéo (`f026.jpg`, aussi vue sur `f004`,
`f010`), deux fils rouges à bouts étamés nus pendent au bord de la carte : peut-être ceux-là,
**non confirmé**.

Ce que ça change :
- **Fiche déformée : troisième hypothèse, sérieuse.** Un contact accidentel a pu faire
  passer un fort courant bref par le fil noir. Et si le « - » de puissance d'un servo était
  débranché pendant que son « + » était alimenté, le fil noir était son **seul** retour :
  tout le courant moteur y passait. Ce serait le retour moteur déjà suspecté, avec une
  cause banale, et non une masse défaillante.
- **LED 5 V : le fantôme reste à prouver.** David l'a isolé de façon répétable sur un servo,
  ce qui va dans le sens du régulateur du servo plutôt que d'un contact au hasard. Mais la
  preuve reste la mesure : fil rouge seul retiré → LED éteinte.
- **Risque nouveau : du 12 V a pu toucher le 5 V ou un signal.** PCA9685, level shifters et
  carte porteuse sont à contrôler avant tout retour d'un Pi. Une fumée le 12/09 pour la même
  raison reste possible, seulement si les fils étaient déjà volants à cette date (à vérifier).

À faire : isoler chaque bout nu avant toute remise sous tension ; à 12 V coupé, mesurer
12 V ↔ 5 V et 5 V ↔ GND à l'ohmmètre (pas de court-circuit) ; garder les mesures de masse
prévues, qui restent valables.

## Mise à jour 2026-11-03 — pourquoi les fils étaient débranchés : le « 360 » à l'allumage

David avait débranché l'alimentation du servo parce que **souvent, à l'allumage, il faisait
un tour complet** (servo exact à confirmer). Défaut intermittent, jamais documenté, et
problème de sécurité à part entière : 380 kg·cm, environ 9 kg au bout d'un bras de 40 cm.

Pistes, aucune mesurée, classées :
1. **Ordre d'allumage + 5 V fantôme.** Le 12 V arrive avant que le Pi ait configuré le
   PCA9685. Le fil rouge d'un ASME peut alors alimenter le PCA9685 en sous-tension, avec un
   signal indéfini sur les servos. Intermittent, comme le symptôme.
2. **Course à la fréquence PWM** (déjà notée, `etude-architecture-actionneurs.md` §3.2) :
   `ServoKit` règle 50 Hz, `wheels.py` règle 60 Hz sur la même puce. À 60 Hz les impulsions
   sont 17 % plus courtes, ce qui sur un servo 360° fait un saut d'angle important.
3. **Écriture directe au démarrage** : `Servo.__init__` écrit `default_pos` sans rampe,
   position réelle inconnue (`etude-architecture-actionneurs.md` §3.1, point 2). Le servo
   rejoint le repos à pleine vitesse, peut-être par le long chemin.
4. **Réaction du servo à l'absence de signal** : non documentée pour l'ASME-MR.

Mesure : T1b de `../hardware/protocole-oscillo.md`. Retirer le fil rouge peut changer ce
comportement : à observer, trajectoire dégagée, avant de conclure.

## Mise à jour 2026-11-03 — le servo du « 360 » est le bras gauche ; essai décidé

David confirme : **le tour à l'allumage, c'est le bras gauche**, le même que la fiche
déformée et les fils volants. Lien possible, non mesuré : un tour qui finit en butée
bloque le moteur, qui tire alors son courant maximal.

Essai proposé par David, retenu : **5 V coupé, 12 V rebranché sur ce servo**. Conditions :
connecteur 3 points **entièrement débranché du PCA9685** (sinon le fil rouge réalimente le
PCA9685 et l'essai ne prouve rien), bouts nus isolés, polarité contrôlée au multimètre (le
manuel : inversion = servo grillé), 12 V sur l'entrée d'alimentation et **pas sur le bornier
M1/M2** (sortie moteur, sérigraphie visible sur `a-f11.jpg`), « - » raccordé avant le « + »,
trajectoire dégagée. Une dizaine d'allumages, le défaut étant intermittent.

Lecture : le bras tourne sans aucun signal → cause dans le servo (piste 4). Il reste immobile
→ cause côté signal ou démarrage (pistes 1 à 3), et on rebranche blanc + noir, rouge retiré.

## Résultat 2026-11-03 — essai 12 V sans signal

David : 12 V rebranché sur tous les servos, tous les connecteurs débranchés du PCA9685,
**5 redémarrages, rien ne bouge**. Le servo seul, sans signal, ne part donc pas (piste 4
affaiblie, pas éliminée : 5 essais sur un défaut intermittent). La cause probable est côté
signal ou démarrage (pistes 1 à 3). Suite : bras gauche seul, blanc + noir, rouge retiré,
5 V coupé (signal flottant), puis 5 V présent sans Pi (PCA9685 alimenté, non configuré).

David, même configuration (12 V présent, convertisseur 5 V débranché, câbles servos
débranchés du PCA9685) : **LED 5 V éteinte**. Le 5 V fantôme passe donc bien par les câbles
3 points. Reste à départager rouge et blanc : à l'essai suivant (blanc + noir, rouge
retiré), LED éteinte = fil rouge confirmé ; LED allumée = retour par la ligne signal.

## Résultat 2026-11-03 — fils rouges coupés et isolés

David : fils rouges coupés et protégés, blanc + noir branchés, convertisseur 5 V débranché :
**aucun mouvement, LED 5 V éteinte**. Le 5 V fantôme passait donc par le **fil rouge**, pas
par la ligne signal. Un signal flottant ne déclenche pas le tour. Suite : 5 V présent sans Pi.

## Note 2026-11-03 — borne FG et isolation du convertisseur

La borne du milieu du Mean Well SD-50 est **FG, masse de châssis, pas le 0 V** (fiche
technique ; `../hardware/alim-5v-pi.md` §3 et §7.4). Laissée non raccordée pour ces essais.

La fiche donne aussi **1500 VAC d'isolation entrée/sortie** : le « - » de sortie 5 V n'est
pas relié au « - » batterie par le convertisseur. À mesurer : continuité entre « - » sortie et
« - » entrée, câblage en place. Si elle est ouverte, les fils noirs des servos sont peut-être
le seul lien entre masses 5 V et 12 V. Et les noirs se rejoignent au PCA9685 : un servo sans
« - » de puissance peut renvoyer son courant moteur par son noir vers le noir d'un autre servo,
sans passer par le convertisseur. Hypothèse non mesurée, cohérente avec la fiche déformée.

## Correction 2026-11-03 — limite de 0,1 Ω non mesurable

Le multimètre de David (`OHMTEC 254089`) a une résolution de 0,1 Ω et une précision de
±(0,8 % + 3 digits) sur 200 Ω, et ses cordons ajoutent leur propre résistance : **la limite
« < 0,1 Ω » écrite plus haut n'est pas mesurable avec lui**. Méthode retenue : court-circuiter
les pointes, noter la valeur, la retrancher ; résultat attendu proche de 0, sous environ
0,5 Ω. Le bip de continuité sonne sous 50 Ω et ne qualifie pas une masse de puissance. Le vrai
contrôle d'une masse reste la chute de tension sous charge, en calibre 200 mV DC.

## Relevés ohmmètre 2026-11-03 (calibre 200 Ω, cordons 0,8 Ω)

| Points | Lecture | Lecture |
|---|---|---|
| Côté 24 V, « + » contre « - » | `1` seul à gauche | Circuit ouvert : pas de court-circuit |
| Côté 5 V (points présumés : « + » contre « - ») | 25, soit ~24 Ω cordons retranchés | Pas un court franc, mais bas pour un test à 700 mV : origine à localiser |

Non mesurés encore : « - » sortie 5 V contre « - » batterie, et 12 V contre 5 V. À localiser :
convertisseur déconnecté du rail, mesurer chaque côté séparément, batterie déconnectée.

Localisation (calibre 200 Ω) : convertisseur seul, sortie débranchée = **25** ; rail seul = **`1`**,
soit plus de 200 Ω sur ce calibre, pas forcément un circuit ouvert. Les 25 Ω viennent du
convertisseur (charge interne probable, non vérifiée), le rail n'a pas de court-circuit.

Convertisseur du rail 5 V : étiquette lue par David **`SD-50B-5`**, sortie à vide **5,07 V**. Bon
modèle, bonne tension, pour la première fois lus sur le robot.

Relevés câblage en place, interrupteur coupé (la batterie est câblée directement sur
l'interrupteur et ne se déconnecte pas), cordons 0,8 Ω : 5 V « + »/« - » = 25 ; « - » 5 V / « - » 24 V
= **2**, soit ~1,2 Ω ; « - » 24 V / « + » 24 V = `1`. Les masses sont reliées, mais 1,2 Ω n'est pas
une liaison franche. Question ouverte : ce lien passe-t-il par un fil noir de servo ? Contrôle :
débrancher la fiche du bras gauche et remesurer.

## Correction 2026-11-04 — la liaison de 1,2 Ω entre masses n'est pas reproduite

Nouvelle mesure de David, calibre 200 Ω, PCA9685 branché puis débranché : « - » 5 V / « - » 24 V
= **`1` dans les deux cas** ; « + » 12 V / « + » 5 V = `1` ; « + » 5 V / « + » 24 V = `1` ; 0 V à l'entrée
du convertisseur, interrupteur coupé.

**La conclusion « masses reliées par ~1,2 Ω » écrite plus haut est donc à retirer tant qu'elle
n'est pas reproduite.** La lecture de 2 contredit celle-ci à configuration annoncée égale : points
différents, mauvais contact, ou liaison intermittente. Le test « le fil noir du bras gauche est-il
le seul lien ? » ne conclut pas : le lien a disparu fiche branchée aussi. État retenu : sur ce
calibre, masses 5 V et 24 V séparées de plus de 200 Ω, cohérent avec un convertisseur isolé.
Pas de liaison 12 V vers 5 V ni 5 V vers 24 V côté « + ».

À mesurer : « - » 5 V / « - » 24 V sur un grand calibre, « - » 5 V / « - » 12 V fiche branchée et
débranchée, « - » 12 V / « - » 24 V.

Relevé 2026-11-04 : `1` partout, sauf **2,5 entre le « - » du rail 24 V et le « - » du rail 5/12 V**,
soit ~1,7 Ω cordons retranchés. David signale **plusieurs rails de distribution** : un rail
24 V, un rail 5/12 V, un rail 5/12/24 V (disposition non documentée, photo demandée). Lecture
provisoire : les mesures faites aux bornes et aux rails n'ont pas porté sur les mêmes points, ce
qui expliquerait 2 puis 1. Si les rails sont reliés par ~1,7 Ω, c'est une liaison résistive à
trouver : à 5 A elle ferait chuter plus de 8 V.

## Vidéo des rails, 2026-11-04 (muette, `rails-f04/f12/f19.jpg`)

Vu, sérigraphies illisibles donc polarités non confirmées : convertisseur à 5 vis, paire
jaune/noir sur la sortie, borne du milieu vide, paire rouge/noir sur l'entrée. Rails = cartes vertes
à fiches débrochables dans un cadre gris imprimé, bus rouge visible dans les fenêtres dessous.
Des fiches 3 points reçoivent noir + jaune + rouge.

**Suspect à contrôler** (`rails-f12.jpg`) : sur une fiche, deux fils noirs d'un câble double
montrent leur cuivre nu au ras du dessus, et un troisième bout noir à cuivre nu est recourbé à côté.
Possibles fils mal enfoncés ou non serrés : cela pourrait expliquer une liaison de masse résistive
ou intermittente. Non confirmé à l'image.

Contrôle David, 2026-11-04 : les fils noirs de `rails-f12.jpg` sont **bien serrés**. Suspect écarté,
le cuivre visible n'indique pas un mauvais contact. La liaison de ~1,7 Ω reste inexpliquée.

## Résultat 2026-11-04 — PCA9685 alimenté, sans Pi

David : 5 V mesuré au PCA9685 = **5,04 V** (5,07 V à vide au convertisseur). Bras gauche seul,
blanc + noir, rouge coupé : **5 allumages, aucun mouvement**.

Bilan des essais du tour à l'allumage, 5 allumages chacun, aucun mouvement : sans signal ;
signal flottant ; PCA9685 alimenté non configuré. Limite : tous ont été faits fils rouges
coupés. Le tour peut donc venir du fil rouge (piste 1, supprimée de fait) ou du démarrage du Pi
(pistes 2 et 3), non testé. Rebrancher le rouge pour trancher n'a pas d'intérêt.

Reste avant de rendre un Pi : inspection visuelle du Pi 4, remplacement de la fiche du bras
gauche, contrôle de sa masse de puissance, décision sur la liaison des masses.

## Relevés 2026-11-04 — masse de puissance du bras gauche : `1`

Calibre 200 Ω, cordons 0,8 Ω, interrupteur coupé :

| Points | Lecture | Lecture provisoire |
|---|---|---|
| « - » bornier du bras gauche / « - » rail 12 V, fiche débranchée | `1` | **Pas de liaison mesurée** : le « - » de puissance du bras serait ouvert (ou mauvais points) |
| « - » rail 24 V / « - » rail 5/12 V, 3 fiches débranchées | 0,7 | Égal aux cordons : rails reliés franchement |

Retirer des chemins parallèles ne peut pas faire baisser une résistance : passer de 2,5 à 0,7
montre que **les ~1,7 Ω étaient une erreur de contact des pointes**. Cette alerte est retirée.

Si le premier relevé se confirme, le fil noir du signal était le **seul retour** du moteur du bras
gauche : c'est l'explication directe de la fiche déformée. Conséquence sur les essais : sans fiche,
ce bras n'était peut-être pas alimenté, donc l'essai « sans signal » ne vaut pas pour lui. Contrôle
décisif : tension au bornier d'alimentation du bras, fiche débranchée, sous tension.
**Ne pas rebrancher la fiche du bras gauche avant ce contrôle.**

Contrôle décisif, 2026-11-04 : **0 V au bornier d'alimentation du bras gauche, 12 V au
convertisseur**, fiche débranchée. Coupure confirmée sur l'alimentation du servo, « + » ou « - »
à déterminer. L'essai « sans signal » ne vaut donc pas pour ce bras. Bouche et bras droit pas
encore contrôlés. Pi 4 : pas avant inspection, et d'abord sans aucune fiche servo, moteurs de
roues coupés.

## Pi 4 rebranché, 2026-11-04 : ne démarre pas, 8 flashs verts

Pi 4 sur le rail 5 V, fiches servos débranchées. Aucune réponse réseau (Wi-Fi, puis RJ45 : rien
d'affiché). David compte **environ 8 clignotements verts répétés**. Sur Pi 4, 8 flashs courts =
**défaut SDRAM** selon des sources secondaires (table officielle non relue). Causes citées :
alimentation, RAM endommagée, firmware. Compte à confirmer.

La carte passait tous les tests le 12/09 sur secteur : elle a pu s'abîmer depuis ou être mal
alimentée ici. Séparation : Pi hors robot, sur son alimentation secteur. Mêmes 8 flashs = carte
ou firmware ; démarrage normal = alimentation ou interface robot. **Pi coupé d'ici là.**

Suite, 2026-11-04 : Pi 4 hors robot sur secteur, sans GPIO : **toujours 8 flashs**, avec sa SD
puis avec une autre SD. Le rail du robot n'est donc pas la cause immédiate. Reste la récupération
du bootloader avant de conclure à une carte morte. SD d'origine conservée intacte, non formatée.
Une autre Pi branchée par David n'apparaît pas sur le réseau (aucun port SSH ouvert sur le /24).

## Autre Pi 4 en service, 2026-11-04

David a branché « l'ancienne Pi qui était dessus » avec une SD formatée, la SD d'origine n'étant
pas retrouvée. Lu en SSH : Pi 4 Model B Rev 1.5, 2 Go, série `10000000e79839cb`, Debian 13,
`robot.local` en 192.168.1.162 (RJ45) et .2 (Wi-Fi), `throttled=0x0`, 29,7 °C. Système vierge : ni
Docker, ni code, ni I²C activé. SD de 119 Go, taille proche de celle d'origine (117 Go le 12/09) :
**à vérifier que ce n'est pas la SD d'origine reformatée.** Le code reste dans le dépôt ; seuls l'état
local et les journaux du Pi seraient perdus. Déploiement à faire fiches servos débranchées et
moteurs de roues coupés.

## Pi 4 de remplacement réinstallé, 2026-11-04

`install-pios-lite.yml` réussi (Docker, I²C, service `robot`). Image du Hub écartée (Humble, 2024) ;
image Jazzy construite sur le Pi, Blinka épinglé en 10.1.0 avec gpiod et son backend PWM. Conteneur
stable, `restart=0`, nœuds lancés, `throttled=0x0`, 851 Mi utilisés et 993 Mi disponibles, Pi hors du
robot. `relays_node` meurt faute de PCF8574 à 0x21 : attendu sans matériel. Visage LED, servos,
roues et Blinka 10.1.0 non testés sur le matériel.

## Isolation du démarrage, 2026-11-04 (commit 7a0876b)

Panne rejouée sur le Pi, `gpiod` désinstallé dans un conteneur jetable : les 15 processus partent,
seul `system_node` meurt. `relays_node` reste vivant sans PCF8574, relais désactivés. Limite connue :
un nœud mort n'est pas relancé, et la mort de `wheels_node` ne stoppe pas les autres nœuds.

## Pi 4 de 4 Go, 2026-11-04 : instable

Série `10000000365ba865`. Sans HAT il a démarré une fois, sur la SD du Pi de 2 Go. `dockerd` y plantait
en SIGILL ; `/usr/bin/dockerd` relu 3 fois caches vidés a donné 2 empreintes différentes, alors qu'une
lecture correspond au paquet. Puis David voit les clignotements revenir. Mémoire suspecte, contact SD
non exclu : test en RAM interrompu, non mesuré. La SD a été éteinte brutalement (`orphan cleanup`) :
à contrôler dans le Pi de 2 Go.

Pi de 4 Go, 22h12 : `throttled=0x50005` stable, **sous-tension active** depuis 16 s après le boot,
CPU bridé à 600 MHz, 56 °C, Docker et conteneur actifs. Les défauts vus sur ce Pi (8 flashs, lectures
instables) peuvent venir de son alimentation : le verdict « mémoire suspecte » n'est plus retenu tant
qu'il n'est pas retesté sur une bonne alimentation. Test mémoire reporté : résultat non concluant sous
sous-tension, et risque pour la SD en cas de coupure.
