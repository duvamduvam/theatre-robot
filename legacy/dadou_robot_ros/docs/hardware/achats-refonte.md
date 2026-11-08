# Achats de la refonte électrique — analyse complète (2026-11-08)

**À quoi sert ce fichier.** Une seule liste pour toutes les commandes de la refonte, croisée
avec le stock (`inventaire-stock.md`), le cahier de câblage (`cablage/cahier-cablage.csv`,
74 fils, 0 erreur au `check_cablage.py`), les cartes (`plan-verification-cartes.md`,
`cout-cartes.md`), les boîtes de distribution (`plans/elec/bornier-distribution`) et
l'odométrie (`../etude-odometrie.md` §9). Règles : rien ne se commande avant la ligne
correspondante du stock ; **une commande par fournisseur** ; les prix ne sont écrits que s'ils
ont été lus, avec leur date. « Prix non lu » veut dire non lu, pas « petit ».

## 1. Ce qui bloque encore la commande principale

| # | Verrou | Qui le lève | Ce qu'il débloque |
|---|---|---|---|
| V1 | **Corrections des cartes Sécurité et Puissance** (relecture du 06/11 : WD_OK sans tirage, nappe retournable, plages à 0,3 mm d'une autre tension, 24 V sans vrai fusible…), puis gabarits 1:1 posés, `check_stack.py`, Gerber refaits (ceux du panier JLCPCB sont périmés) | session de conception, Opus minimum | la commande JLCPCB et la liste des modules |
| V2 | **Mesures M1-M13** de l'étude intérieur : 66 longueurs de fils, référence du relais 40 A et courant de bobine, alimentation du BLX4, polarité du jack VoiceTone, courant du klaxon, courant réel des roues | David, sur le robot | sections finales, fusible général, câble au mètre |
| V3 | **Vérifications d'atelier** (§4) : calibres des fusibles verre, nombre d'embases 2 points, cosses, fil, entretoises | David, 20 min | une dizaine de lignes qui tombent ou restent |
| V4 | **Réception des porte-fusibles** : filetage et écrou à mesurer, bande d'essai imprimée | David | l'impression des deux boîtes |

Tant que V1 n'est pas levé, **aucune carte ni aucun module de carte ne se commande** : la
relecture a déjà changé des empreintes une fois (isolateur I²C, 05/11).

## 2. Les commandes, dans l'ordre

### Commande 1 — AliExpress, maintenant (petit matériel décidé)

| Pièce | Qté | État | Prix lu |
|---|---|---|---|
| Porte-fusibles 5×20 de panneau, rouge, lot de 5 (article 1005007910707716) | 4 lots (16 + 4 de rechange) | **retenu par David le 07/11, pas payé** | 2,45 € le lot (capture du 07/11, promo jusqu'au 18/11, 13 lots dispo) |
| Kit de fusibles 5×20 **rapides**, 150 pièces, 15 valeurs de 0,1 à 30 A dont 2, 3, 5, 8, 10 et 15 A, 10 de chaque (proposé par David le 08/11) | 1 | couvre tous les calibres des deux boîtes, rechange comprise ; la boîte du stock est mélangée et illisible. ⚠️ Tous rapides : en entrée des Mean Well (P10-P13), le courant d'appel n'est pas publié pour les versions 24 V ; rapides : bons pour 12 emplacements sur 16 | 5,79 € (capture du 08/11, promo jusqu'au 18/11) |
| Fusibles 5×20 **temporisés T5A**, céramique, lot de 10 : AliExpress 1005007520792851 (ATOPELEC), variante 5A, retenu par David le 08/11 | 1 lot | entrées SD-50B-5 ×2 et SD-50B-12 : un rapide peut sauter sur la pointe d'allumage, non publiée pour les versions 24 V. Refuser « F » / « fast » | 1,43 € le lot (capture du 08/11) |
| Fusibles 5×20 **temporisés T10A**, céramique, lot de 10 : AliExpress 1005007520792851 (ATOPELEC), variante 10A, retenu par David le 08/11 | 1 lot | entrée SD-150B-12, même raison | 1,43 € le lot (capture du 08/11) |
| Fusibles à lame 25 A (SmartDrive ×2, ampli ×1) + rechange | 6 | à acheter, aucun en stock | non lu |
| Porte-fusibles à lame **en ligne** pour les deux SmartDrive (l'ampli a déjà le sien, sur la porte) : AliExpress 1005006286934036, « Waterproof Auto Fuse Holder », 32 V, variantes **Medium 1 Pair** (taille standard ATO, à confirmer à réception : lame de 19 mm), **25 ampères**, **12 AWG** ; retenu le 08/11 | 1 paire | variantes vérifiées sur la capture : Medium 1 Pair, 25 A, 12 AWG, max. 20 par acheteur | 6,39 € la paire (capture du 08/11) |
| ~~Coup-de-poing~~ **EN STOCK** (vidéo de David du 08/11) : boîtier jaune en saillie « EMERGENCY STOP », champignon rouge à flèches de rotation, blocs Techpushbutton **ZB2-BE102C (1-2, NF)** et **ZB2-BE101C (3-4, NO)**, Ith 10 A, AC15 240 V 3 A. Conforme à la spec du 30/08, accrochage à confirmer à la main (reste enfoncé, se libère en tournant). Calibre donné en alternatif seulement : il commande la bobine du relais et `ESTOP_SENSE`, il ne coupe jamais les 40 A | 0 | — | — |
| ~~Bouton d'armement~~ **EN STOCK** : l'inventaire liste ~5-10 blocs marche/arrêt de panneau (`I` vert / `O` rouge, c0161) et ~40-60 poussoirs momentanés. Le `I` vert d'un bloc marche/arrêt sert de bouton d'armement | 0 | — | — |
| ~~Cosses à œillet jaunes~~ **EN STOCK** (photo du 08/11) : ~10-15 jaunes préisolées 4-6 mm², plus des cosses tubulaires nues SC16-6, SC10-6 et probablement SC6 pour les 6 mm². À vérifier : diamètre des trous (M5/M6) et nombre suffisant pour ~20 extrémités | 0 | — | — |

Hors UE : 3,60 € de droits par catégorie, donc grouper en une fois.

#### Panier AliExpress du 08/11 — prêt, **NON PAYÉ** (connexion bloquée : code par mail jamais reçu)

Relevé sur la capture du panier de David, 5 articles, promo jusqu'au 18/11 à 23 h 59. Plusieurs
articles sont marqués « Presque épuisé » : si un lien ne donne plus la variante, revenir ici.

| Article | Variante à choisir | Qté | Prix |
|---|---|---|---|
| Porte-fusibles 5×20 de panneau — https://fr.aliexpress.com/item/1005007910707716.html | noir, 5X20MM | 4 lots de 5 | 1,94 € le lot |
| Kit de 150 fusibles 5×20 rapides, 15 valeurs 0,1-30 A (vendeur Shop1100353140) | — | 1 | 5,79 € |
| Fusibles céramique temporisés — https://fr.aliexpress.com/item/1005007520792851.html | 5A | 1 lot de 10 | 1,43 € |
| Fusibles céramique temporisés — même annonce | 10A | 1 lot de 10 | 1,43 € |
| Porte-fusibles à lame en ligne étanches — https://fr.aliexpress.com/item/1005006286934036.html | Medium 1 Pair, 25 ampères, 12 AWG | 1 paire | 6,39 € |
| **Sous-total 22,80 €, livraison 2,62 € (fusibles T, vendeur international), total estimé 25,42 €** | | | |

Pas encore dans le panier : lames ATO 25 A de rechange (optionnel). Cosses : en stock (photo du 08/11).

### Commande 2 — un seul distributeur UE, après V1 et V2 (cartes, modules, alimentation, câble)

| Pièce | Qté | Pourquoi / piège | Prix lu |
|---|---|---|---|
| **Mean Well SD-150B-12** | 1 | audio seul ; décidé le 06/11, l'ampli fait décrocher la SD-50B-12. **Ne dépend pas des cartes : achetable dès maintenant.** Écarté le 08/11 : AliExpress « Power Wizard Store » (57,39 € + 24,91 € de port, aucun avis, risque de copie). **Retenu le 08/11 : alimentatorishop.com (Italie)**, page lue sur la capture de David : Mean Well SD-150B-12, 80 en stock, 59,92 € HT, **73,10 € TTC**, express TNT 6,50 € (gratuit dès 300 € HT), livraison annoncée le 16/11 | 73,10 € TTC + 6,50 € de port |
| **Lidar 2D 360° : RPLIDAR C1 (Slamtec)** — c'est pour lui qu'est dessiné le support `plans/supports/support-lidar-c1` | 1 | décidé le 02/11 ; **ne dépend ni des cartes ni des mesures : achetable dès maintenant**, chez n'importe quel vendeur (il sert d'abord en sim et au banc). Le LD19 lu le 01/11 (130,90 €, RobotShop EU, en rupture) n'est plus le modèle retenu | **prix du C1 non lu** |
| ISO1540 (isolateur I²C) | 2 | carte Sécurité ; empreinte corrigée le 05/11 (12,70 mm) | 10,29 € pièce (26/09, Mchobby) |
| INA226, **format CJMCU-226 à 6 broches** | 2 (+1 à bornier pour le 24 V, option) | supports M7/M8 de Puissance ; **pas** le Gotronic INA226-1A sans vérifier le brochage ; sort d'usine en 0x40 = adresse du PCA9685 des roues, donc sur le bus du Pi uniquement | 9,20 € (26/09, brochage douteux) |
| PCA9685, **format HW-170 (62,2 × 25,4)** | 1 | **pas** le shield ADA1411 de `cout-cartes.md` | non lu |
| Relais Omron G5V-2 ×2, G5LE-1 ×2 | 4 | cartes | 2,50 € / 1,68 € HT (26/09) |
| PTC radiaux de tête de nappe (maintien ≥ 0,5 A, ≤ 0,4 Ω) | 2 | Puissance ; choix non fait | non lu |
| Embases 2EDG 5,08 **coudées**, même série que les fiches KF2EDGWB | 19 | pour que l'accouplement soit celui qui tient déjà sur le robot | non lu |
| Petite logique et connectique des cartes : 74HC123, 74HC74, PCF8574P, L7805CV, L7809CV, 2N7000, BAT85 ×2, zener 5V1, BC327 ×4, embases RCA CI ×4, porte-fusibles CI 5×20 ×9, module PCF8574 HW-171, 100 nF / 1 µF | ~40 | liste de `cout-cartes.md` §3.3, **jamais chiffrée** ; 1 µF absent du kit MLCC commandé | non lu |
| **Câble 6 mm²** rouge et noir (pack → fusible → relais → barres, G01) | ~3 m | stock : « un fil ≥ 4 mm² » non identifié → à vérifier, sinon acheter | non lu |
| **Câble 4 mm²** orange et noir (SmartDrive), violet (ampli, 12 AWG selon Focal) | ~5 m | idem | non lu |
| Fil **orange** et **violet** 1,5 / 0,75 mm² (code couleur du cahier : 6 fils orange, 5 violets) | 2 bobines | les 8 bobines du stock ont une section non lue et ces couleurs ne sont pas confirmées | non lu |
| Fusible général 40 A + porte-fusible (lame MIDI ou verre 6×32 selon support) | 1 + rechange | calibre à confirmer sur le courant des roues, **jamais mesuré** (V2) | non lu |
| Visserie des boîtes : vis laiton M5 + écrous + **rondelles larges Ø15** (6 paires de cosses), vis M6 + écrou pour l'étoile, vis à bois Ø4 × 20 | ~30 | le calcul de plaque impose la rondelle large (18 MPa sans, 7 avec) | non lu |
| Câble de commande **blindé à embouts** pour les deux SmartDrive | 2 | remplace le câble réseau dégainé (anomalie 1 du relevé) | non lu |

### Commande 3 — JLCPCB, après V1

5 cartes, 5 exemplaires chacune : 32,92 € avant TVA et douane (lu le 05/11), finition **HASL**
et non OSP, mode de port DDP à vérifier au paiement. Les Gerber du panier sont périmés :
repartir de `pcb/kicad/fab/`. Le panier est à David, ne pas y toucher.

### Hors commande — matière et impression, après les mesures

| Poste | État |
|---|---|
| **PMMA coulé 5 mm** pour les étages : découpe laser chez eMode (Cholet), matière Plexi Cindar lue le 05/11 à 62,22 € TTC/m² soit ≈ 11 € pour 0,177 m² | après M1-M5 et un gabarit carton ; **une plaque d'essai d'abord** |
| PETG pour les boîtes (2 pièces de 126 × 133 et 86 × 89, 30 mm), joues de la SD-150, platine relais, tiroir du pack, support VoiceTone | stock de filament non inventorié |

## 3. Rien à acheter — le stock couvre

PC817 DIP-4 · 1N5819 · SN74AHCT125N · résistances 10 k et 2 k · supports tulipe (DIP-10 à
couper) · barrettes sécables · boîtiers JST 2 et 4 points (pas à vérifier, §4) · RP2040-Zero ×2 ·
fiches vertes KF2EDGWB 5,08 du faisceau · nappes IDC et GPIO · Wago 221 · embouts VE 0,5 et
0,75 · gaine thermo et manchons · jacks DC · isolateur audio à transformateurs · mini-voltmètre
pour J32 (essayé le 06/11, 27,2 V lus) · fusibles verre 5×20 (150 à 250, **calibres à lire**).

Commandé le 05/10, à pointer à réception : TVS P6KE15A, PTC RXEF050, kit MLCC 10 pF-100 nF.

## 4. Vérifications d'atelier qui changent la liste (V3)

1. **Calibres des fusibles verre 5×20** du stock : boîte mélangée (vidéo du 08/11), remplacée par le kit de la commande 1. Il en faut 2, 3, 5, 10 et 15 A. ⚠️ Le cahier
   prévoit **7,5 A pour les ASME : rare en 5×20** (valeurs courantes 5 / 6,3 / 8 / 10 A) →
   passer les trois lignes P07-P09 à **8 A**. Avis : passer P17/P18 (12 V contrôle) de 15 à
   **10 A**, la SD-50B-12 ne sort que 4,2 A et le porte-fusible retenu tient 10 A.
2. **Embases 2 points à brides** (celles de la boîte grise) : il en faut **19** (15 coffre +
   4 moteurs). Les 3 et 4 points n'entrent pas dans les découpes.
3. **Section du fil ≥ 4 mm²** du stock et **couleurs des 8 bobines** : décide le câble à acheter.
4. **Entretoises laiton** : M2.5 ou M3 (cartes 100 × 100 en M3).
5. **JST** : un contact enfoncé dans un boîtier 4 points tranche XH / 2,54 en dix secondes.
6. **LED 3 mm** (odométrie, 4) : le stock n'a identifié que du 5 mm.
7. **Cosses faston** : largeur 4,8 ou 6,35 (klaxon, interrupteurs).
8. **Vis à bois Ø4 × 20** et filament PETG : quantité.

## 5. Décisions qui changent une ligne

| Décision | Effet sur la liste |
|---|---|
| Barre moins moteurs vers le pack (avis) ou vers l'étoile (étude §6) | 1 câble 4 mm² de plus ou de moins, et sa longueur |
| 3ᵉ INA226 pour lire le 24 V sur J32 (branche C de l'odométrie, non validée) | +1 module à bornier, +1 kΩ en série |
| Alimentation 12 V du VoiceTone : départ fusiblé du bloc 12 V audio (cahier P30) ou sortie filtrée de la carte Audio (`audio-relays/DESIGN.md`) | un porte-fusible et une embase de plus ou de moins |
| Relais 40 A : garder l'existant (référence non lue, M13) ou remplacer | 0 ou 1 relais + bobine à mesurer |

## 6. Ce que cette analyse ne donne pas

Le **total**. Sur une trentaine de lignes, une dizaine ont un prix lu, et deux postes lourds
n'en ont pas : la SD-150B-12 et la logique des cartes. Donner un chiffre ici serait l'inventer ;
il se lira au moment de remplir les paniers, après V1 et V2.
