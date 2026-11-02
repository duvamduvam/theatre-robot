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
