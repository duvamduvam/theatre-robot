# Plan de vérification des 5 cartes avant commande (2026-11-05)

> Ce plan est l'étape 4 de [`plan-refonte-electrique.md`](plan-refonte-electrique.md), qui prime.
> Il remplace notamment « garder l'ancienne carte montée », impossible si tout le câblage change.

Demande de David : « un plan solide pour revérifier les cartes et limiter les risques ».
Panier JLCPCB prêt (5 cartes, 32,92 € avant TVA et douane), **rien n'est commandé**.

Le risque n'est pas l'argent (3,57 € la carte) : c'est de souder une carte fausse, de
perdre trois semaines, ou — pour L et P — de monter une chaîne de sécurité qui ne coupe
pas. Le plan va donc du moins cher au plus cher : la machine, puis le papier, puis une
relecture indépendante, puis le banc.

## Noms des cartes

| Nom | Dossier KiCad | Ancienne lettre | Rôle |
|---|---|---|---|
| **Puissance** | `carrier-p` | P | fusibles, borniers d'alimentation, mesure de courant |
| **Sécurité** | `carrier-l` | L | raccord du Pi, chien de garde, verrou d'armement, arrêt des roues |
| **Moteurs** | `carrier-m` | M | commande des roues et des servos (PCA9685), extension PCF8574 |
| **Audio** | `audio-relays` | — | relais audio, départs 12 V |
| **Odométrie** | `odometry` | — | lecture de la rotation des roues |

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

## 1 bis. Implantation décidée le 05/11 : haut P+L, zone audio M+audio

David veut deux cartes en haut et deux vers l'audio, nappe de moins de 30 cm, répartition
laissée à l'agent. Plan : `plan-pile-cartes.png`. Ce choix annule le §4 de l'étude 100×100
pour M (la pile à trois) ; P sur L ne bouge pas. L'odométrie reste sur le coffre des alims.

Pourquoi celle-là : la seule liaison longue est L↔M, dont la coupure est sûre (R10 sur M
coupe les PWM) ; P, ses fusibles et ses 10 A restent loin de l'audio ; J11 (I²C vers
`audio-relays`) arrive à côté de sa cible. Mettre P près de l'audio aggravait la ronflette ;
éloigner L des deux autres doublait les nappes longues.

Conséquences :

| Sujet | Effet |
|---|---|
| Cartes | **aucune à refaire** ; seule la sérigraphie « BAS DE LA PILE » de M est à corriger |
| +5V et GND de la nappe, 30 cm de 28 AWG (≈ 0,213 Ω/m) | 32 mΩ (2 fils) + 21 mΩ (3 fils) : 16 mV à 0,3 A, négligeable |
| I²C 5 V sur 30 cm | à contrôler à l'oscillo au banc (fronts) ; un Hantek est disponible |
| **OE_WHEELS (broche 7) voisin de SCL (broche 6)**, sans masse entre eux | **à corriger** : voir ci-dessous |
| Fils V+ 10 A vers les PCA9685 | plus longs et **près de l'audio** : courants de servos pulsés. Paire torsadée, passés loin de MIC et du transfo |
| Coupure de la nappe | nouveau mode de panne réaliste (câble long dans le robot) : à inclure au protocole caméra |

**OE_WHEELS** : R10 (10 kΩ) tient OE haut quand Q1 est ouvert, donc le signal de sûreté est à
haute impédance, le long du fil d'horloge I²C actif en permanence. Sans risque sur 3 cm, à
ne pas laisser sur 30 cm. Correction proposée : échanger les broches 7 et 8 de la nappe L↔M
(GND en 7, OE en 8, la 9 est libre), ce qui met une masse entre SCL et OE. Touche la route
d'OE sur L et M, donc les deux cartes repassent tous les contrôles et la relecture.

### Hauteur de la pile de 3 (estimation du 05/11, rien n'est mesuré)

Lu dans les modèles 3D KiCad : supports 8,5 mm, IDC 9,1 mm, MSTBA 8,6 mm, bornier MKDS
13,8 mm. Le reste est **estimé** (modules, fiches, câbles) : à remplacer par des mesures.

| Tranche | Sans fiches | Avec fiches et fils |
|---|---|---|
| Pattes sous M + M | 4,6 | 4,6 |
| M → L (PCA9685 enfiché : support 8,5 + carte 1,6 + picots servos ≈ 8,5) | ≈ 20 | ≈ 30 avec les fiches servos |
| L + L → P (IDC et ISO1540 enfiché) | ≈ 17 | ≈ 22 |
| P + au-dessus de P (bornier, condensateurs, fiches) | ≈ 17 | ≈ 22 |
| **Total pile de 3** | **≈ 6 cm** | **≈ 8 cm** |
| Pile P + L seule | ≈ 4 cm | ≈ 5 cm |

Emprise : 100 × 100 mm plus les fiches et les fils sur les bords, à prévoir largement.
**Accès** : dans la pile, M est au fond et ses fiches servos sont sous L, il faut démonter
pour y toucher. C'est l'argument pour sortir M de la pile. Si la place le permet, M **à côté**
de la pile du haut garde l'accès et tient les fils 10 A loin de l'audio : mieux que la zone
audio, à vérifier sur le robot.

## 2. BLOQUANT trouvé — carte P : les pistes des départs 10 A sont trop étroites — ✅ LEVÉ le 05/11

> ✅ **Levé le 05/11 au soir par la sortie A** (élargir), sans cuivre 2 oz ni surcoût : chaque
> rail a reçu une plage de cuivre, aucune pastille n'a bougé. Un contrôle neuf,
> `carrier-p/check_power.py`, mesure le goulot de cuivre de 35 trajets et le convertit en
> ampères : 19 étaient sous leur exigence, **0 aujourd'hui**. ERC, DRC, sérigraphie, parité
> et pile à 0. **Trois limites restent**, détaillées dans `pcb/kicad/carrier-p/DESIGN.md` :
> fusibles amont à poser au coffre (15 A sur le 12 V, 10 A sur le 5 V), cavaliers JP1 et JP3
> limités à 3 A, col de 5,4 mm sur le 12 V vers l'ouest. **Gerber du panier à remplacer par
> `fab/carrier-p.zip`.** Le tableau ci-dessous décrit la carte d'AVANT.

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

**05/11, après le relevé filmé — C est écartée, et le tronc +5 V est à traiter comme le 12 V.**
Un fusible tient 1,5 fois son calibre pendant une heure : un 5 A ne protège pas une piste
donnée pour 3,9 à 5,4 A. Et la source du 5 V est lue : SD-50B-5, 10 A, que la fiche Mean Well
laisse monter à 105-150 % avant de décrocher. L'arrivée J20 n'a qu'une broche +5 V. Détail :
[`releve-2026-11-05.md`](releve-2026-11-05.md) §4.4.

## 2 bis. Vérifications ajoutées par le relevé du 05/11 — avant commande

Détail et preuves dans [`releve-2026-11-05.md`](releve-2026-11-05.md) §4.

| # | Vérification | Carte ou achat concerné |
|---|---|---|
| 1 | ✅ **Erreur confirmée puis CORRIGÉE le 05/11** : supports de l'isolateur I²C passés de 10,16 à **12,70 mm**, ordre VCC·SCL·SDA·GND, détrompage sérigraphié ; ERC, DRC, sérigraphie, parité, pile à 0, plus `carrier-l/check_iso1540.py` (cotes gravées du module). **Restent : module posé sur le gabarit régénéré, relecture du §4, et Gerber du panier à remplacer par `fab/carrier-l.zip`** | Sécurité |
| 2 | ~~Fiches du robot~~ ✅ **clos le 05/11** : pas de 5,08, fiches simples sans vis latérales, corps large de n × 5,08 mm (fiche technique KF2EDGWB fournie par David) — elles tiennent côte à côte sur J20 et J36. Commander les embases dans la même série 2EDG 5,08 | Puissance, Sécurité |
| 3 | **PCA9685 à acheter** : la ligne de `cout-cartes.md` est un shield, il faut un module au format du `HW-170` (62,2 × 25,4). **INA226** : brochage CJMCU-226 à confirmer sur la référence choisie | liste d'achats |
| 4 | **Second PCA9685** : cavalier 0x41, `i2cdetect`, « kill de la chaîne » module par module ; l'entrée de coupure du module servos est à la masse, il n'est pas dans la chaîne d'arrêt. Fréquence PWM des roues à relever avant et après | Moteurs, protocole caméra |
| 5 | **Relais 40 A sur un 12 V qui décroche** : refermetures répétées sur les condensateurs des drivers. À donner à la relecture du §4 et à provoquer au banc | Sécurité |
| 6 | **Hors cartes** : fusible général, distribution 24 V fusiblée, alimentation 12 V du VoiceTone C1 | cahier de câblage, achats |

## 2 ter. Relecture indépendante du 06/11 — un lot de corrections avant commande

Les deux cartes modifiées le 05/11 ont été relues par un agent distinct. **Résultat : ni
Sécurité ni Puissance ne sont commandables en l'état.** Détail et décisions dans
`pcb/kicad/carrier-l/DESIGN.md` et `pcb/kicad/carrier-p/DESIGN.md`, sections « Relecture
indépendante du 2026-11-06 ».

- **Sécurité** : WD_OK sans tirage (une broche ou une diode ouverte = « tout va bien ») ;
  nappe retournée côté Pi = masse sur le 5 V du Pi (probable mécanisme de l'incident du
  04/11). Plus R14, HEARTBEAT, 74HCT123, broches 7/8 de la nappe, relecture d'OE.
- **Puissance** : plages à 0,3-0,45 mm de pastilles d'une autre tension (pont de soudure =
  12/24 V sur le 5 V) ; exception d'échauffement injustifiée ; 24 V sans vrai fusible ;
  12 V de la sécurité partagé avec les départs bras.

Décisions attendues de David avant le lot : entrée 12 V séparée pour la sécurité sur la
carte Puissance (recommandé) ; calibre de F5.

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
