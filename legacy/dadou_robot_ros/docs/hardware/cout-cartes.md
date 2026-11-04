# Ce que coûtent les cartes électroniques de Didier (chiffrage du 2026-09-26)

> **Mise à jour du 27/09** : la bascule sous 100 × 100 est FAITE —
> **4 cartes** de 100 × 100 (audio + la porteuse en 3), Gerber prêts dans
> `didier/pcb/kicad/fab/`. Le poste PCB passe de 41 $ + ~80 $ à **4 × 5 $ les
> cinq** (pages PCBWay du 26/09). Les §2.x ci-dessous décrivent la situation
> AVANT bascule ; l'étude : [`etude-cartes-100x100.md`](etude-cartes-100x100.md) §10.

> **Devis réels du 04/11** : les 4 zip de `didier/pcb/kicad/fab/` ont été déposés dans
> les calculateurs, sans compte et sans rien commander (navigateur headless, profil
> vierge). Options par défaut : 2 couches, 1,6 mm, cuivre 35 µm/1 oz, vert.
>
> | | JLCPCB | Aisler (Europe) |
> |---|---|---|
> | Carte, 5 pièces | **4,00 $** les 4 cartes lues à l'identique (2,00 $ via l'app JLCONE) | **54,06 € HT / 64,33 € TTC** (carrier-m seule) |
> | Carte, 3 pièces | — (minimum 5) | **34,03 € HT / 40,50 € TTC** |
> | Port vers la France, 1 carte (0,29 kg) | Global Standard 7,60 $ (10-12 j) · EuroPacket 16,11 $ · DHL Express (DDP) 23,44 $ · FedEx (DDP) 23,79 $ | « Shipping worldwide for free » (page d'accueil) |
> | Port, poids de 20 cartes (0,82 kg) | Global Standard 14,14 $ · EuroPacket 23,86 $ · DHL (DDP) 26,88 $ · FedEx (DDP) 27,64 $ | idem |
> | **Les 4 designs, 5 pièces** | **16 $ + 14,14 à 26,88 $ de port = 30 à 43 $**, hors TVA et droit de 3 € | **≈ 257 € TTC** (4 × 64,33) |
> | Les 4 designs, 3 pièces | — | **≈ 162 € TTC** (4 × 40,50) |
>
> **Ce qui n'est PAS établi** : le panier JLCPCB exige un compte, donc ni la TVA, ni le
> droit de douane, ni les frais UE du 01/11 n'ont été vus ; rien ne prouve non plus que
> le 4,00 $ s'applique aux 4 designs d'une même commande ni que Global Standard
> (≤ 1,5 kg, ≤ 150 $) est DDP. Le poids groupé est une approximation : 4 × 0,29 kg font
> 1,16 kg, au-dessus des 0,82 kg lus, donc le port réel peut dépasser ces chiffres.
> Aisler : prix lu sur carrier-m seule, TVA allemande 19 % affichée, multiplié par 4 sans
> vérifier de remise ou de frais par commande. Le §4 ci-dessous (110-150 €) est périmé.

> **Mise à jour du 05/11 : 5ᵉ carte au panier** (`odometry`, 92 × 84 mm, violet, HASL au
> plomb) : +3,57 €, port inchangé à 23,99 € (0,97 kg), **sous-total 32,92 €**, avant TVA et
> douane, non commandé. Gravée avant validation sur robot, par décision de David.

> **Panier JLCPCB lu le 04/11/2026** (compte achats@duvam.net, non commandé) :
> 4 cartes × 5, 1,6 mm, **HASL au plomb**, une couleur par carte (M vert, L bleu,
> P rouge, audio noir) : 4 × 3,57 € = **14,28 €**, port estimé **23,99 €**
> (0,83 kg ; égal au DHL Express lu en $, mode non affiché au panier), coupon
> **−8,93 €**, **sous-total 29,35 €**. Départ estimé le 08/11. La couleur et le
> HASL au plomb sont sans surcoût ; sans plomb +1,16 €/carte, ENIG +15,80 €/carte.
> Bleu, rouge et noir : 3 jours de production au lieu de 2. L'offre à ~4 $ se
> cumule bien sur 4 cartes. **Toujours non vus** (avant l'étape de paiement) :
> TVA, droit de 3 €/catégorie, frais de gestion douanière du 01/11.
> ⚠️ La finition par défaut est **OSP** : à changer pour une soudure à la main.

> **Devis réel du 04/11/2026** (calculateur public JLCPCB, Gerber de `fab/*.zip`
> déposés, sans compte, panier non atteint). Les 4 cartes sont reconnues en
> 2 couches, 100 × 100 mm ; options par défaut (FR-4, 1,6 mm, vert, **OSP**,
> cuivre 1 oz), 5 pièces, production 2 jours.
>
> | Poste | Montant lu |
> |---|---|
> | Chaque carte, 5 pièces (« Special Offer ») | **4,00 $** (2,00 $ via l'appli JLCONE) |
> | Port France, Global Standard Direct Line, 10-12 j | **14,14 $** |
> | Port France, DHL Express (DDP), 2-4 j | **26,88 $** |
> | Port France, FedEx Express (DDP), 3-5 j | **27,64 $** |
> | Port France, EuroPacket, 6-9 j | **23,86 $** |
>
> **Total : 30,14 $ au plus bas (Direct Line), 42,88 $ en DHL DDP.** Le port est
> mesuré sur une carte à 20 pièces (0,82 kg), en substitut du poids de 4 × 5.
> **Non vérifié, faute de panier** : l'offre à 4 $ cumulée sur 4 cartes dans une
> même commande (sans elle, 20 pièces d'une carte = 23,30 $ dont 4 $ de frais
> d'ingénierie), la TVA, le droit de 3 €/catégorie, et les frais de gestion
> douanière UE du 01/11/2026. Direct Line n'est pas marqué DDP.
> ⚠️ Le calculateur chiffre le port vers les **États-Unis par défaut** (26,86 $) :
> passer la destination sur France avant de lire.
> Aisler : seule une page ancienne est lisible (12 € + 0,067 €/cm² × 3 pièces,
> exemple de la page incohérent avec sa table) — non retenu comme prix actuel.
> PCBWay : calculateur non piloté, pas de nouveau chiffre.

Première estimation chiffrée de la fabrication des cartes du robot. Elle complète
[`inventaire-stock.md`](inventaire-stock.md) (ce qu'on possède) et
[`croisement-etudes.md`](croisement-etudes.md) (ce qu'il faut acheter) par la
question qui manquait : **combien**.

> **Règle appliquée ici, sans exception** : aucun prix n'est écrit de mémoire.
> Chaque montant porte sa source et sa date ; **ce qui n'a pas pu être lu est
> écrit « non chiffré »** plutôt que comblé par un ordre de grandeur. C'est la
> leçon du 05/09 (30-40 € annoncés pour un kit à 97 €).

---

## 1. Combien de cartes, et lesquelles

Relevé dans les fichiers KiCad eux-mêmes le 26/09 (contour `Edge.Cuts` mesuré,
empreintes comptées), pas dans la doc — qui est périmée sur deux points.

| Carte | Contour **mesuré** | Couches | Empreintes | État de routage | À fabriquer ? |
|---|---|---|---|---|---|
| `main-carrier` | **195 × 150 mm** (292,5 cm²) | 2 | 83 | 259 pistes, 25 vias ; **bande sécurité non routée** (122 chevelus) | **OUI** |
| `audio-relays` | **150 × 100 mm** (150,0 cm²) | 2 | 53 | **0 piste** — placement seul | **OUI** |
| `wheel-odometry` | 120 × 101 mm (121,2 cm²) | 2 | 32 | placée, non routée | **non** — remplacée par un stripboard (décision du 02/09) |
| `main-raspberry` | 65 × 56 mm (36,4 cm²) | 4 | 11 | — | **non** — approche abandonnée, remplacée par `main-carrier` |

**Donc deux cartes**, et le chiffrage ne porte que sur elles.

⚠️ **Ni l'une ni l'autre n'est prête pour la fabrication.** `audio-relays` n'a
pas une seule piste tracée ; `main-carrier` a sa bande sécurité en chevelu. Le
coût immédiat de ce chantier n'est donc **pas de l'argent, c'est du travail** :
tant que le routage n'est pas fini, il n'y a pas de gerbers, donc pas de devis
réel — seulement l'estimation ci-dessous.

---

## 2. Les PCB nus

### 2.1 Le fait qui pilote tout : les deux cartes dépassent 100 × 100 mm

C'est le seuil au-delà duquel les fabricants chinois quittent leur tarif
forfaitaire. L'effet est **brutal**, et il est enfin documenté par une source
primaire lisible — les deux seules pages statiques par taille de PCBWay :

| Format | 2 couches, 5 pièces | Source (consultée le 26/09/2026) |
|---|---|---|
| 100 × 100 mm (100 cm²) | **5,00 $** | pcbway.com/pcb_prototype/2_Layer_pcb/100x100mm.html |
| 150 × 100 mm (150 cm²) | **41,00 $** | pcbway.com/pcb_prototype/2_Layer_pcb/150x100mm.html |

**+50 % de surface, ×8 de prix.** Le 150 × 100 est exactement le format
d'`audio-relays` : ces 41 $ ne sont pas une extrapolation, c'est son prix affiché.

Réserve à connaître : sur ces pages, l'épaisseur par défaut est confirmée
(« 1.6mm (Default) ») et le cuivre 1 oz l'est sur la page 100×100, mais **la
finition cochée par défaut n'est pas confirmée** comme HASL standard. À vérifier
au panier.

### 2.2 JLCPCB : un angle mort documentaire

Le candidat par défaut est celui sur lequel on a le moins de chose. Leur page
d'aide officielle ne publie que deux seuils : surcoût « grande carte » au-delà de
**650 cm²** ou 60 cm de long (aucune de nos cartes ne les atteint), et rien du
tout sur le prix de base entre 100 × 100 mm et 650 cm² — **soit exactement la
zone où vivent nos deux cartes**. Aucun retour d'expérience daté 2025-2026 avec
un montant à l'écran n'a été retrouvé ; le forum EEVblog qui semblait prometteur
bloque l'accès automatisé (403).

⚠️ Le « 2 $ les 5 » qui circule ne vaut **que** pour ≤ 100 × 100 mm, et les tiers
qui le citent ne sont même pas d'accord entre eux (2 $, 3 $, 3,50 $ selon les
pages). À ne pas utiliser comme référence.

### 2.3 L'Europe : Aisler, et pourquoi l'écart se resserre

Aisler (Pays-Bas) publie une structure de prix simple : **un frais fixe par
commande + un tarif au cm²**. La page produit actuelle confirme aujourd'hui la
structure et le point décisif — *« A fixed job fee applies per order »*, donc le
frais fixe est payé **une fois pour toute la commande**, pas par carte.

Les montants, en revanche, datent d'un post du forum officiel du **27/08/2023**
(2 couches HASL Budget : **12,00 € fixe + 0,067 €/cm²**, par lots de 3) et n'ont
pas pu être reconfirmés en 2026 : la page actuelle affiche seulement « Starting
at just €14,20 ». **Le calcul ci-dessous est donc à revérifier au devis.**

| Carte | Calcul | 3 exemplaires |
|---|---|---|
| `audio-relays` | 150,0 cm² × 0,067 € = 10,05 €/carte | 30,15 € |
| `main-carrier` | 292,5 cm² × 0,067 € = 19,60 €/carte | 58,79 € |
| Frais fixe de commande | 12,00 €, une seule fois | 12,00 € |
| | | **≈ 101 € HT** |

Autre fabricant européen dont un prix a pu être lu : **Multi-CB** (Allemagne),
35,00 € pour **une** carte 80 × 100 mm en 4 jours, **port France 4,95 €** — le
seul port chiffré de toute la collecte, tous fabricants confondus.

### 2.4 Chine ou Europe : le calcul honnête

Pour la Chine, il faut ajouter ce que le prix affiché ne contient pas :

- **TVA 20 %**, collectée au checkout via IOSS pour les commandes ≤ 150 € ;
- **le droit de douane forfaitaire de 3 € par catégorie tarifaire** (code SH),
  en vigueur depuis le **01/07/2026** sur les colis ≤ 150 € hors UE
  (service-public.gouv.fr). **L'IOSS ne le couvre pas** : sans option DDP, le
  transporteur le réclame à la livraison, avec ses propres frais de débours ;
- **l'option DDP de JLCPCB**, qui règle le problème mais coûte *« 2 à 10 % du
  montant avancé, minimum 12 € à 45 € »* (leur FAQ douane UE) — sur une commande
  de cette taille, **le minimum écrase le pourcentage** ;
- **les frais de gestion douanière UE annoncés pour le 01/11/2026** : montant
  **toujours non publié** au 26/09/2026, confirmé par deux sources primaires
  indépendantes (service-public.gouv.fr et JLCPCB).

Mise en regard, à surfaces égales :

| | Chine (PCBWay) | Europe (Aisler) |
|---|---|---|
| `audio-relays` | 41 $ / 5 ex. *(prix lu)* | 30,15 € / 3 ex. |
| `main-carrier` | **non chiffré** — voir ci-dessous | 58,79 € / 3 ex. |
| Frais fixes | port (non chiffré) + 3 € douane + DDP min. 12 € | 12 € de job fee + port UE |
| TVA | 20 % au checkout | incluse/ajoutée selon régime |

Pour `main-carrier`, aucun prix n'existe : PCBWay n'a **pas** de page statique
au-delà de 150 × 100 (les sept autres tailles testées renvoient une erreur
serveur — leur catalogue 2 couches ne contient que ces deux formats). Le seul
calcul possible est le mien : 41 $ × (292,5 / 150) ≈ **80 $ les 5**. Ce n'est
**pas un prix**, c'est une règle de trois, et elle est fragile — le seul saut
observé (5 $ → 41 $) n'est justement pas proportionnel à la surface.

> **Ce qu'il faut en retenir** : une fois le port, la TVA, les 3 € de douane et
> les ~12 € de frais de dossier ajoutés, **l'écart Chine/Europe se referme
> largement** sur une commande unique de deux cartes. L'Europe a en prime
> l'avantage de ne pas dépendre des frais douaniers du 01/11/2026, dont personne
> ne connaît encore le montant.

### 2.5 Le levier de prix le plus rentable du chantier

`audio-relays` fait 150 × 100 mm. **Sous 100 × 100 mm, elle passerait de 41 $ à
5 $ les cinq** — un facteur 8, sur la seule base de son contour. Elle porte 53
empreintes dont 4 RCA, 4 relais et un transfo : ce n'est pas gagné, mais c'est
la question la moins chère à se poser avant de router (elle n'a aucune piste :
le moment est idéal, il n'y a rien à refaire).

Pour `main-carrier` (83 empreintes, 195 × 150), une seule carte 100 × 100 est
exclue — mais **un découpage en deux ou trois cartes ≤ 100 × 100 est faisable** :
c'est l'objet de [`etude-cartes-100x100.md`](etude-cartes-100x100.md) (demande
de David le jour même), qui règle au passage le porte-à-faux des 45 mm ajoutés
à droite.

---

## 3. Les composants

Les prix ci-dessous ont tous été lus sur une fiche produit, le 26/09/2026.
**Ils ne couvrent pas toute la nomenclature** — voir §3.3, qui est aussi
important que le tableau.

### 3.1 Ce qui a été chiffré

| Pièce | Qté | Prix unitaire lu | Total | Source |
|---|---|---|---|---|
| Relais Omron G5V-2 (DPDT 5 V) | 2 | 2,50 € TTC | 5,00 € | Gotronic (art. 06330) |
| Relais Omron G5LE-1 (SPDT 5 V) | 2 | 1,68 € HT | 4,03 € TTC | Distronic |
| Transfo d'isolation 600:600 Ω CI | 1 | 2,20 € TTC | 2,20 € | Gotronic TI600 |
| Fiches débrochables 5,08 mm (2/3/6 pôles) | 13 | 0,42 / 0,62 / 0,66 € | ≈ 6,10 € | Reichelt, série CamdenBoss CTB9209 |
| Adafruit **ISO1540** (isolateur I²C) | 2 | 10,29 € TTC | 20,58 € | Mchobby.be |
| Module **INA226** | 2 | 9,20 € TTC | 18,40 € | Gotronic (INA226-1A) |
| Module **PCA9685** | 1 *(1 déjà en stock)* | 24,50 € TTC | 24,50 € | Gotronic ADA1411 — **shield Adafruit, majorant** : un breakout générique coûte bien moins, non chiffré |
| | | | **≈ 81 €** | |

Deux réserves sur ce tableau : les deux relais sont vendus sous une désignation
catalogue simplifiée (« G5V2-5 », « G5LE-5 »), **pas sous le part number Omron
complet** — fiche technique à vérifier avant commande ; et les prix Reichelt
affichent la TVA allemande à 19 %, donc le TTC réel pour la France sera un peu
au-dessus.

### 3.2 Ce que le stock couvre déjà (rien à acheter)

Croisé avec [`inventaire-stock.md`](inventaire-stock.md) :

- **1 × `SN74AHCT125N`** (une seule puce, 4 portes) — en stock (6 à 8, DIP-14, référence lue) ;
- **fusibles verre 5×20** — 150 à 250 en stock (les *porte*-fusibles, eux, sont
  à acheter) ;
- **électrolytiques 470 µF / 100 µF** — kit BOJACK 630 pièces ;
- **résistances 1/4 W** — plusieurs centaines, mais **seulement 7 valeurs lues
  sur 20 sachets** : à fouiller avant de commander (2 minutes d'atelier) ;
- **barrettes sécables 2,54 mm** — 30 à 50, couvrent les 14 supports et barrettes
  des deux cartes ;
- **poussoir 6 mm, LED, petites diodes** — présents, calibres à confirmer ;
- **connecteurs IDC 2,54 mm + nappe arc-en-ciel** (~50 + plusieurs mètres,
  `t0363`/`t0420`) et **nappes GPIO 40 c. déjà serties** (2-3, `t0047`) —
  *ajouté le 30/09, oublié au premier croisement* : couvre la nappe du Pi et,
  si les tailles 2×8 sont dans le lot, les **deux nappes de la pile** (4 embases
  + 4 fiches 2×8, absentes de la première liste car nées de la bascule 100×100) ;
- **supports tulipe DIP** (~10-20, `t0004`) — nombre de points non lisible à
  l'image, mais le lot couvre très probablement les 3 supports ;
- ⚠️ **les 300+ borniers débrochables verts du stock** pourraient couvrir tout le
  poste connectique de puissance — **mais leur pas n'a jamais été mesuré**
  (5,08 ? 3,81 ? 3,5 ?). Les cartes sont dessinées en 5,08. **Un réglet sur un
  bornier tranche un poste entier de la commande.**

### 3.3 Ce qui n'a PAS pu être chiffré — le trou est réel

Les distributeurs les plus complets ont bloqué la collecte (Mouser et Farnell en
403/timeout, TME en devise US, LCSC en JavaScript). Restent non chiffrés :

| Pièce | Qté | Carte |
|---|---|---|
| Embases mâles CI débrochables 5,08 mm (le pendant des fiches du §3.1) | 19 | les deux |
| Embases RCA à souder sur CI | 4 | audio-relays |
| Porte-fusibles CI 5×20 mm | 9 | main-carrier (8) + audio (1) |
| `74HC123` DIP-16 / `74HC74` DIP-14 | 1 + 1 *(le schéma en montre 3 + 3 : ce sont les unités d'un symbole multi-unités, pas des puces)* | main-carrier |
| `PCF8574P` DIP-16 | 1 | audio-relays |
| PTC radiaux (tête de nappe, ajoutés le 27/09) | 2 | carrier-p |
| ~~Supports tulipe DIP-14 / DIP-16~~ → **stock probable** (§3.2) | 2 + 1 | L, audio |
| ~~Connecteur IDC 2×20 + nappe 40 c.~~ → **stock** (§3.2), comme les IDC 2×8 de la pile si la taille y est | 1 + 4 | L, M, P |
| `L7805CV` / `L7809CV` | 2 | audio-relays |
| Module PCF8574 (type HW-171) | 1 à 2 | main-carrier |
| `2N7000`, `BAT85` ×2, zener 5V1, `BC327` ×4, céramiques 100 nF / 1 µF | ~15 | les deux |

**Conséquence assumée : le total composants n'est pas donné ici.** Le socle lu
vaut ≈ 81 € ; le reste est une quarantaine de pièces de petite connectique et de
logique traversante que je n'ai pas lues, et je ne les invente pas.

---

## 4. Où on en est, et ce qui donnerait le vrai chiffre

**Ordre de grandeur défendable aujourd'hui** :

- **PCB nus** : ≈ **100 € HT** pour 3 exemplaires de chaque en Europe (calcul
  Aisler, montants 2023 à revérifier), ou ≈ 121 $ + port + TVA + ~15 € de
  douane/dossier pour 5 de chaque en Chine — **les deux arrivent dans la même
  zone, autour de 110 à 150 €** une fois tout compté.
- **Composants** : **≈ 81 € vérifiés**, plus une quarantaine de références non
  chiffrées.

Trois actions, par rapport qualité/prix décroissant :

1. **Mesurer le pas d'un bornier vert du stock** (2 minutes, un réglet). S'il
   est en 5,08, un poste entier de la commande disparaît — 19 embases + 13
   fiches. C'est le geste le plus rentable du chantier, et il ne coûte rien.
2. **Passer sous 100 × 100** — `audio-relays` sans sacrifice, `main-carrier` en
   2 ou 3 cartes : étudié dans [`etude-cartes-100x100.md`](etude-cartes-100x100.md),
   décisions en attente de David.
3. **Finir le routage, sortir les gerbers, déposer le zip dans les
   calculateurs.** C'est la seule façon d'avoir un prix ferme : les calculateurs
   sont en JavaScript, donc illisibles autrement — constat déjà fait le 13/09 et
   reconfirmé aujourd'hui, fabricant par fabricant. Et monter le panier réel chez
   Gotronic + Reichelt donnera le total composants exact en une demi-heure, là où
   une troisième passe de collecte web resterait partielle.

**Et le rappel qui prime sur le prix** : `main-carrier` porte la chaîne de
sécurité matérielle (watchdog, `OE`, coup-de-poing) qui, aujourd'hui, **n'existe
physiquement pas** — le robot tourne sur stripboard. Ces ~200 € ne sont pas une
dépense de confort.
