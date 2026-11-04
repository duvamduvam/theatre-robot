# Plan de vérification des 5 cartes avant commande (2026-11-05)

Demande de David : « un plan solide pour revérifier les cartes et limiter les risques ».
Panier JLCPCB prêt (5 cartes, 32,92 € avant TVA et douane), **rien n'est commandé**.

Le risque n'est pas l'argent (3,57 € la carte) : c'est de souder une carte fausse, de
perdre trois semaines, ou — pour L et P — de monter une chaîne de sécurité qui ne coupe
pas. Le plan va donc du moins cher au plus cher : la machine, puis le papier, puis une
relecture indépendante, puis le banc.

## 1. Ce que la machine a vérifié le 05/11 — FAIT

| Contrôle | Résultat |
|---|---|
| Les Gerber du panier sont ceux des `.kicad_pcb` actuels (ré-export, comparé fichier par fichier) | identiques, 5 cartes × 10 fichiers |
| ERC, toutes sévérités | 0 sur les 5 |
| DRC, erreurs | 0 violation, 0 pastille non connectée sur les 5 |
| DRC, avertissements | uniquement de la sérigraphie (recouvrements, bord de fente) |
| Parité schéma ↔ PCB indépendante (netlist exportée du schéma, comparée broche par broche, noms de nets ignorés) | 0 écart : 30 / 28 / 5 / 27 / 36 nets |
| Pile M / L / P (`check_stack.py`) | 0 défaut |
| Odométrie ↔ plaque à bandes (`check_stripboard.py`) | 0 écart sur 80 broches |
| Perçage mini / piste mini | 0,30 mm (vias) / 0,20 mm — dans le défaut du calculateur JLCPCB (0,3 mm) |

Les avertissements « parité » de KiCad (`net_conflict`, des centaines) ne sont que le
préfixe `/` des noms de nets générés : c'est pour ça que la comparaison indépendante a été
écrite. **Limite de tout ce tableau** : il prouve que les cartes sont cohérentes avec leurs
schémas, pas que les schémas sont justes ni que les pièces rentrent.

> **05/11, après ce tableau** : la carte L a reçu deux sorties Dupont du bus I²C du Pi
> (J13, J14). Contrôles refaits sur L : aucune pastille existante ne change de net, aucune
> piste existante ne disparaît, ERC 0, DRC 0, parité 0 écart, pile 0 défaut. Le panier porte
> les nouveaux Gerber de L. **Commande suspendue par David le 05/11 : les vérifications
> d'abord.**

## 2. BLOQUANT trouvé — carte P : les pistes des départs 10 A sont trop étroites

Mesuré dans `carrier-p.kicad_pcb` : aucun plan de cuivre sur les rails de puissance
(seul GND en a), tout passe en pistes.

| Rail | Fusible | Piste la plus étroite | Tient en 1 oz (ΔT 10 / 20 °C) | À courant de fusible |
|---|---|---|---|---|
| `12V_BRAS` (F7) | 10 A | 2,0 mm | 3,9 / 5,4 A | **≈ +80 °C** |
| `VSERVO_F`, `VSERVO` (F2) | 10 A | 2,0 mm | 3,9 / 5,4 A | **≈ +80 °C** |
| tronc `+12V` (alimente F7, F8, F4 et JP1→F2) | 10+5+5+10 A | 1,5 à 2,5 mm | 3,2 à 4,6 A | non protégé par ses fusibles |
| tronc `+5V` (alimente F1, F3, F6) | 3+5+5 A | 2,0 mm | 3,9 / 5,4 A | idem |
| départs 5 A (LED, 12V aux, 24V) | 5 A | 1,5 mm | 3,2 / 4,3 A | ≈ +27 °C, acceptable |

Calcul : IPC-2221, couche externe, `I = 0,048 · ΔT^0,44 · A^0,725`. Il faudrait 4,7 mm
(ΔT 20 °C) à 7,2 mm (ΔT 10 °C) pour 10 A en 1 oz. La formule est prudente et un fusible
n'est pas une charge permanente — mais un fusible est là pour protéger ce qui le suit, et
les bras ASME-MR sont donnés « jusqu'à ~10 A pic pièce » : un moteur calé à 8 A ne fera pas
sauter un 10 A temporisé et chauffera la piste. La carte unique de juillet avait du cuivre
large ; le découpage en 100 × 100 l'a perdu sans que personne ne le recalcule.

Trois sorties, à choisir **avant** de commander P :

| | Coût | Ce que ça demande |
|---|---|---|
| **A. Élargir** : plans de cuivre sur les rails 10 A et les troncs | 0 € | reprendre `carrier-p/generate_pcb.py`, relancer tous les contrôles ; P est dense, la place n'est pas garantie |
| **B. Cuivre 2 oz** pour P seule | **+32,49 €** (lu au calculateur le 05/11) | rien ; 2,0 mm en 2 oz ≈ +26 °C à 10 A |
| **C. Fusibles calés sur les pistes** (F7 et F2 en 5 A) | 0 € | n'est juste que si les courants réels le permettent — jamais mesurés |

Recommandation : tenter A ; si la place manque, B. C seule revient à déplacer le problème.

## 3. Gabarits papier 1:1 — toi, pièces en main (≈ 30 min)

`didier/pcb/kicad/gabarits/*.pdf` : pastilles, sérigraphie et contour à l'échelle 1.
Imprimer à 100 %, **mesurer d'abord le côté de la carte au réglet** (100 mm, 92 × 84 pour
l'odométrie) : si l'imprimante thermique déforme, tout le reste est faux. Puis poser chaque
pièce sur ses pastilles. C'est le seul contrôle qui confronte les empreintes au stock.

| Carte | À poser | Pourquoi |
|---|---|---|
| P, L | un bornier vert débrochable 2 et 6 points | le pas du stock n'a jamais été mesuré (5,08 / 3,81 / 3,5 ?) ; empreintes en 5,08 |
| P | un porte-fusible 5×20, un bornier à vis bleu, un condensateur 470 µF | empreinte Keystone 3512, pas 23,62 mm |
| P | un module INA226 **CJMCU-226** (6 broches) si tu en as | les supports M7/M8 attendent ce brochage ; taille supposée 26 × 20 |
| M | PCA9685, PCF8574 HW-171 | entraxe 35,56 mm du HW-171 « à vérifier » depuis juillet |
| L | un support DIP-14 et DIP-16, la nappe GPIO, un ISO1540 | |
| L | **le câble du BNO055 sur J10** | écart trouvé le 05/11 : `main-carrier/DESIGN.md` dit Qwiic = **JST-SH 1,0 mm**, l'empreinte posée est une **JST-PH 2,0 mm** (`jstph4`). Un câble Qwiic n'y entre pas. L'accès au bus du Pi pour l'INA226 est réglé le 05/11 par deux barrettes Dupont **J13/J14** (3V3 · SDA · SCL · GND) ; l'empreinte de J10, elle, reste à trancher |
| audio | une RCA, le transfo 600:600, un relais G5V-2 et un G5LE | empreintes RCA et transfo **provisoires** ; brochage G5V-2 à lire sur la fiche Omron |
| odométrie | un JST 4 points et 2 points de ta boîte, un PC817, le RP2040-Zero sur ses deux barrettes, la PTC, le TVS, le 100 µF | pas XH 2,50 non confirmé ; entraxe du Zero 15,24 |

Chaque pièce qui ne tombe pas = une empreinte à corriger avant commande. Me donner la
cote mesurée, pas « ça ne va pas ».

## 4. Relecture indépendante — avant commande

Les cartes L et P portent la chaîne d'arrêt des roues ; l'odométrie a été dessinée en une
soirée. Un agent **relecteur** (revue adversariale, ne corrige pas) relit, sans mon
raisonnement sous les yeux : la table de L net par net contre le contrat de la branche
`chaine-securite`, les nappes (que coupe chaque débranchement), et les ajouts de
l'odométrie (U6, U7, J7), seuls hors du contrôle plaque ↔ PCB.

## 5. Commander

Quand 2, 3 et 4 sont soldés. Les réserves du 27/09 non couvertes par les gabarits restent
à lever : choix des deux PTC de nappe (maintien ≥ 0,5 A, ≤ 0,4 Ω sur le +5V) et courant
de la bobine du relais 40 A — elles ne changent pas le cuivre, donc ne bloquent pas la
commande. Vérifier à l'étape de paiement, avant de valider : TVA, droits, et que le mode
de port est bien DDP.

## 6. À réception — du sûr vers le risqué

1. **Carte nue** : continuité au multimètre entre rails (aucun court-circuit +5V/GND,
   +12V/GND) ; odométrie : **circuit ouvert entre GND et GNDPWR**.
2. **Soudée, hors robot, alim de labo limitée à 100 mA** : chaque carte seule ; tensions
   aux bornes des supports **avant** d'enficher un module ou un circuit.
3. **Pile M + L + P sur table**, sans moteurs : débrancher chaque nappe, constater OE haut
   et la retombée de la sortie relais.
4. **Sur le robot, roues hors sol, protocole caméra** (règle du projet, non négociable) :
   forward, e-stop, kill de la chaîne, **et débrancher chaque nappe en plein mouvement**.
5. Sol : seulement après 4, et après le test scénique (priorité 1 de `chantiers.md`).

On garde l'ancienne carte montée et fonctionnelle tant que 4 n'est pas vert : le retour
arrière doit rester un rebranchement.

## 7. Ce que ce plan ne couvre pas

La tenue mécanique dans le robot (hauteurs d'étage jamais mesurées), le bruit audio réel de
`audio-relays` (c'est son objectif n° 1, il ne se vérifie qu'à l'oreille), et la justesse
des schémas eux-mêmes au-delà de la relecture.
