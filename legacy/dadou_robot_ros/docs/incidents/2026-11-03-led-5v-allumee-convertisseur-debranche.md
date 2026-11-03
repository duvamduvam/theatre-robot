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
