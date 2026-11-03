# Protocole de mesures à l'oscilloscope (Hantek 6022BE piloté à distance)

*Écrit le 2026-11-03, suite à l'incident
[`../incidents/2026-11-03-led-5v-allumee-convertisseur-debranche.md`](../incidents/2026-11-03-led-5v-allumee-convertisseur-debranche.md).
Rien n'a encore été mesuré.*

**Principe** : David câble une fois des **points de test fixes** sur le robot, accroche les
sondes dessus, puis s'éloigne. Claude pilote l'oscilloscope (sigrok-cli sur un Pi dédié, en
SSH/Wi-Fi) et déclenche les mouvements du robot. Personne ne tient de pince pendant les prises.

## 1. Matériel et isolation

- **Hantek DSO-6022BE** (identifié le 03/11 : USB `04b4:6022`, haute vitesse). 2 voies,
  8 bits, couplage **DC seulement**. Prise USB rouge = alimentation d'appoint, n'isole rien.
- **Pi hôte dédié**, PAS celui du robot ni le PC de David. Alimenté par une **batterie USB**
  (ou un chargeur secteur, isolé lui aussi). Liaison avec le PC **en Wi-Fi uniquement** :
  c'est le Wi-Fi qui isole. Logiciel : `sigrok-cli` + `sigrok-firmware-fx2lafw`, driver
  `hantek-6xxx`.
- **Sondes en ×10** (commutateur sur la sonde) : sans ça, 24 V dépasse la plage d'entrée.
  Pour les petites tensions (masses, audio), ×1 si la plage le permet — Claude le dira.
- **Coupleur AC maison** (le 6022BE n'a pas de couplage AC) : un condensateur film 1 µF en
  série dans la ligne de sonde + 1 MΩ vers la masse côté oscillo. Sert à voir l'ondulation
  de quelques dizaines de mV posée sur un rail continu. À fabriquer sur un bout de
  plaque à bandes (pièces en stock).

## 2. Règles de sécurité (non négociables)

1. **La pince de masse de chaque sonde va au point de test `TP0` (« - » batterie), et
   nulle part ailleurs.** Les deux masses de l'oscillo sont reliées entre elles : une pince
   posée ailleurs crée un court-circuit à travers l'oscillo et le Pi hôte.
2. Une différence entre deux points se mesure avec **les deux voies** (CH1 − CH2), jamais
   avec la pince.
3. **Roues** : moteurs de roues coupés pour tous les tests, sauf T8, qui se fait **roues
   hors sol** (règle du projet, protocole caméra).
4. Les tests T2 et suivants demandent le **Pi 4 du robot**, gelé depuis la fumée du
   12/09 : ils ne se lancent qu'après T1 réussi (rail 5 V sain, pas de 5 V fantôme) et
   après le remède de l'incident du 03/11 (fils rouges des ASME retirés, masse de
   puissance du bras gauche refaite).

5. **Avant T0** : vérifier la continuité entre le « - » 5 V et `TP0`. Les convertisseurs
   SD-50 sont isolés (1500 VAC entrée/sortie) : si cette liaison n'existe pas, le rail 5 V
   flotte par rapport à `TP0` et les mesures de TP1 et TP2 n'ont pas de sens.

## 3. Points de test à câbler (une fois pour toutes)

Chaque point = un **fil soudé ou serré dans un bornier, terminé par une broche mâle
2,54 mm**, sur laquelle le grappin de la sonde s'accroche. Idéalement, toutes les broches
sur **une petite barrette étiquetée** fixée à un endroit accessible du torse.

**Une résistance de 1 kΩ en série** au départ de chaque fil de mesure (pas sur `TP0`) :
si un fil se décroche et touche quelque chose, il ne peut pas faire de court-circuit. Elle
ne fausse rien (l'oscillo présente 1 à 10 MΩ) jusqu'au MHz.

| Point | Où | Pourquoi |
|---|---|---|
| **TP0** | « - » batterie, au plus près du BMS (cosse + broche, fil épais, **sans** résistance) | Référence unique de toutes les mesures |
| TP1 | 5 V de la carte porteuse, côté Pi 4 | 5 V fantôme, creux au démarrage des bras |
| TP2 | 5 V du Pi 5 (vision/parole) | Ondulation, ronflement |
| TP3 | Broche GND du PCA9685 | Retour de courant moteur par la masse signal |
| TP4 | Rail 12 V (servos) | Creux et parasites des moteurs |
| TP5 | Rail 24 V batterie, après interrupteur | Creux au démarrage des roues |
| TP6 | Fil signal (blanc) du servo bras gauche, **côté servo** | Qualité du PWM qui arrive |
| TP7 | Masse du servo bras gauche, **côté servo** (« - » du connecteur 3 points) | Différence de masse aux deux bouts du fil noir (avec TP3) |
| TP8a / TP8b | Sortie audio vers la mixette : point chaud / masse (dérivation sur le jack, en Y) | Ronflement, sa fréquence, sa source |

Repère : un fil servo ou une broche Dupont supporte mal plus de 1 à 2 A. Si T2 montre plus
de ~100 mV sur TP3 pendant un mouvement, ça veut dire environ 2 A dans le fil noir.

## 4. Les tests, dans l'ordre

Pour chaque test : voies et points, ce que Claude fait, ce qui est attendu. Durée totale
estimée de la séance : 1 h 30, dont la moitié en câblage des points de test.

### T0 — Chaîne de mesure (robot éteint)

- CH1 et CH2 sur la **sortie de calibration** de l'oscillo (signal carré 1 kHz).
- Claude : acquisition, vérifie amplitude et fréquence, règle la compensation des sondes
  (David tourne la vis de la sonde si le carré est arrondi ou pointu).
- Attendu : carré propre sur les deux voies. Sinon on s'arrête là.

### T1 — 5 V fantôme et rail 5 V à vide (sans aucun Pi)

- CH1 = TP1, CH2 = TP4.
- Étapes : convertisseur 5 V débranché, 12 V branché ; puis convertisseur branché.
- Attendu : **TP1 = 0 V** convertisseur débranché (sinon un servo alimente encore le rail) ;
  TP1 entre 5,0 et 5,25 V convertisseur branché, ondulation < 50 mV (coupleur AC).
- C'est la mesure qui débloque le retour du Pi 4 (cf. fiche fumée du 12/09).

### T1b — Mouvement parasite à l'allumage (le « 360 » signalé par David)

- CH1 = TP4 (12 V, ×10), CH2 = TP6 (signal du servo concerné). Déclenchement sur le front
  montant du 12 V. Longue fenêtre : de la mise sous tension à la fin du démarrage des nœuds.
- Étapes : (a) sans Pi, PCA9685 alimenté ; (b) sans Pi, fil rouge du servo remis, pour voir
  l'effet du 5 V fantôme ; (c) avec le Pi 4, une fois T1 réussi.
- Attendu : signal plat tant que le Pi n'a pas configuré le PCA9685, puis impulsions à
  **50 Hz** de largeur stable. **Toute impulsion erratique, ou une fréquence à 60 Hz**
  (`wheels.py` règle la même puce à 60 Hz), désigne la cause. Signal propre et servo qui
  tourne quand même : le problème est dans le servo (réglages, capteur).
- **Sécurité** : personne ni câble dans la trajectoire du bras à chaque mise sous tension.

### T2 — Retour moteur par la masse signal (le cœur du problème)

- CH1 = TP3 (GND du PCA9685), CH2 = TP7 (masse côté servo). Plage la plus sensible.
- Claude : fait bouger le **bras gauche** (amplitude complète, aller-retour, 5 fois),
  puis le bras droit, puis la bouche. Déclenchement sur le front montant de CH1.
- Attendu : quelques mV. **Au-delà de ~50 mV en crête, le courant moteur passe par le
  fil noir** : la masse de puissance de ce servo est à reprendre avant toute autre chose.

### T3 — Tenue du 5 V du Pi 4 quand les bras démarrent

- CH1 = TP1, CH2 = TP4. Déclenchement sur **front descendant** de CH1 sous 4,9 V.
- Claude : les deux bras démarrent **en même temps**, à pleine vitesse (le pire cas),
  et lit en parallèle `vcgencmd get_throttled` sur le Pi 4.
- Attendu : TP1 ne descend **jamais sous 4,75 V** ; `get_throttled` reste à `0x0`. Le Pi 4
  signale la sous-tension vers 4,63 V : un creux juste au-dessus suffit à expliquer des
  redémarrages.

### T4 — Parasites du 12 V servos

- CH1 = TP4 (via coupleur AC), CH2 = TP6.
- Claude : séquence d'animation complète (bras + yeux + bouche + cou).
- Attendu : ondulation du 12 V bornée ; signal PWM à 50 Hz propre, niveau haut net
  (≥ 3 V si le PCA est en 3,3 V, ~5 V sinon), sans rebonds au front.

### T5 — Ronflement audio : fréquence et source

- CH1 = TP8a, CH2 = TP8b. Robot silencieux (aucune lecture audio), mixette branchée.
- Étapes, une acquisition chacune : (a) tout allumé ; (b) Pi 5 sur sa batterie au lieu du
  secteur ; (c) servos qui bougent ; (d) roues coupées / alimentées.
- Claude calcule le spectre de chaque prise (FFT sur le fichier exporté).
- Lecture : raies à **50/100 Hz** = secteur (boucle de masse) ; **kHz** = découpage d'une
  alimentation ; suit les mouvements = moteurs. CH2 seul montre le bruit de la masse audio
  par rapport à la batterie. Confirme ou corrige la source établie le 30/08 (alim du Pi 5).

### T6 — Ondulation du 5 V du Pi 5

- CH1 = TP2 (via coupleur AC), CH2 = TP8a.
- Claude : charge le Pi 5 (whisper + synthèse vocale) et compare repos / charge.
- Attendu : ondulation < 50 mV ; corrélation éventuelle avec le ronflement de T5.

### T7 — Vérification après remède (rejouée)

- T1 et T2 rejoués après chaque correction (fil rouge retiré, masse refaite). Les
  valeurs avant/après vont dans la fiche incident. C'est la preuve que le remède marche.

### T8 — Roues (en dernier, **roues hors sol**, protocole caméra)

- CH1 = TP5 (×10), CH2 = TP1. Déclenchement front descendant de CH1.
- Claude : démarrage franc, arrêt franc, inversion de sens, via la chaîne cmd_vel
  habituelle (aucun chemin parallèle).
- Attendu : creux du 24 V au démarrage chiffré ; **le 5 V du Pi 4 ne bouge pas** (c'est
  la raison d'être des deux convertisseurs séparés).

## 5. Ce que Claude produit

Pour chaque prise : le fichier de données (CSV/sigrok), une image de la trace, la valeur
qui compte et le verdict, rangés dans `photos/AAAA-MM-JJ-oscillo/` et résumés dans la
fiche incident concernée.

## 6. À préparer par David

- Pi hôte + batterie USB, sur le Wi-Fi de l'atelier, son adresse IP.
- La barrette de points de test (§3) avec ses résistances de 1 kΩ.
- Le coupleur AC (§1).
- Un séparateur jack en Y pour TP8.
