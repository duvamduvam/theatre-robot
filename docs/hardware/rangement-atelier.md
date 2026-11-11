# Rangement de l'atelier : marquage des bacs et améliorations

Proposition établie le 2026-09-03, **à partir de ce qui a été observé** dans la vidéo
d'atelier du 02/09 (427 images dépouillées) — pas à partir d'un modèle théorique de
rangement. Chaque recommandation cite ce qui la justifie.

Le constat de départ tient en une phrase : **le tri existe déjà, l'adresse manque.**
Ce n'est pas un atelier en désordre — c'est un atelier bien trié dont le classement ne
vit que dans la tête de David.

---

## 1. Cinq faits qui commandent tout le reste

**1. Le support d'étiquette existe déjà, partout, et il est vide.**
Une dizaine d'agents l'ont relevé indépendamment : **tous** les bacs à bec (gris, orange,
rouges) et **tous** les tiroirs portent un **porte-étiquette moulé d'origine** en façade —
une glissière ou un renfoncement rectangulaire sous le bec. **Aucun n'est renseigné.**
Il n'y a donc rien à acheter, rien à bricoler, et rien à coller sur du plastique gras :
l'étiquette se glisse.

**2. Un étiquetage a déjà existé, et il n'a pas tenu.**
Plusieurs bacs portent des **restes de bande blanche arrachée** ou de l'**adhésif jauni**
dans le logement. C'est l'information la plus utile du lot : la question n'est pas
« comment étiqueter », c'est **« pourquoi le précédent n'a pas survécu »**. Une étiquette
collée à nu sur un bac manipulé se décolle, se salit, s'arrache. Le porte-étiquette moulé
répond exactement à ça — à condition de s'en servir.

**3. Le tri par famille est déjà fait, à la maille du bac.**
Un bac = une famille, et c'est cohérent sur la plupart des travées : un bac de fourches
optiques, un bac de WAGO, un bac de borniers verts, un bac de DC-DC, un bac de capteurs.
**Il n'y a donc quasiment pas de retri à faire** — ce qui change complètement le coût du
chantier. On étiquette ce qui est là, on ne réorganise pas.

**4. Il y a de la place, beaucoup.**
Au moins **douze contenants** ont été relevés vides ou remplis à moins de moitié : un bac
orange entièrement vide, un bac rouge à 2 %, un coffret à compartiments vide à 85 %, la
mallette « câblage » avec 5 cases libres, plusieurs bacs de borniers à une seule couche.
**Aucun achat de rangement n'est justifié.**

**5. La géométrie n'est pas stable.**
Des **cales en carton et des chutes de contreplaqué** sont glissées sous et entre les bacs
pour rattraper le jeu. Le pas vertical est irrégulier, les bacs se déplacent. C'est le seul
point qui doit être traité **avant** de figer une grille d'adressage : une adresse
positionnelle qui bouge est pire que pas d'adresse.

---

## 2. Le marquage

### 2.1 Ce que la Marklife P15 sait faire, et son défaut

La P15 est une étiqueteuse **thermique directe** Bluetooth, sur rouleaux d'environ 12 à
15 mm de large (à confirmer sur tes rouleaux). Pas d'encre, pas de ruban : la tête chauffe
un papier qui noircit.

⚠️ **Le défaut à connaître avant de lancer 200 étiquettes** : le thermique direct
**pâlit**. Chaleur, UV, frottement, solvants, plastifiants — au bout de quelques mois à
quelques années, une étiquette thermique posée à nu dans un atelier devient grise puis
illisible. C'est très probablement ce qui est arrivé au marquage précédent.

**Trois parades, toutes gratuites :**
- **Glisser l'étiquette dans le porte-étiquette moulé**, jamais la coller à nu sur le bac.
  Elle est alors protégée du frottement, et remplaçable en deux secondes.
- **Ne pas exposer au soleil direct** les travées concernées (le mur est contre une
  fenêtre ? à vérifier).
- **Garder la source dans le dépôt** (voir §2.4) : une étiquette illisible se réimprime,
  elle ne se re-devine pas. C'est ça, la vraie assurance.

Si un jour une travée pâlit malgré tout, la réponse n'est pas de changer de méthode mais
de réimprimer la travée — cinq minutes, puisque les textes sont versionnés.

### 2.2 Ce qu'on écrit sur l'étiquette

**Les deux à la fois : l'adresse ET le contenu.** C'est le point de conception important.

```
┌──────────────────────────────┐
│ B4-07                        │   ← adresse, gros, lisible à 2 m
│ BORNIERS VERTS débroch. 5,08 │   ← contenu, petit, lisible à bout de bras
└──────────────────────────────┘
```

- **L'adresse seule** (`B4-07`) obligerait à consulter l'inventaire pour savoir ce qu'il y a
  dedans. Insupportable au quotidien.
- **Le contenu seul** (`BORNIERS VERTS`) ne permet pas de faire le lien avec l'inventaire,
  ni de dire « c'est en B4-07 » à quelqu'un — ni à une IA.
- **Les deux** : on trouve à l'œil, et l'inventaire reste raccordé au réel.

Format d'adresse proposé : `<meuble><rangée>-<position>`, la position comptée **de gauche
à droite en se tenant face au meuble**. Exemple : `B4-07` = meuble B, 4ᵉ rangée en partant
du haut, 7ᵉ bac en partant de la gauche.

**Pas de QR code au début.** La P15 sait en imprimer, mais un QR sur un bac de borniers
oblige à sortir le téléphone pour savoir ce qu'il y a dedans, alors qu'un mot suffit.
Le QR redeviendra intéressant plus tard, sur les **contenants opaques** (sachets ESD,
colis) où il n'y a rien à voir de l'extérieur.

**Écrire le boîtier quand il décide.** `BORNIERS VERTS 5,08` vaut infiniment mieux que
`BORNIERS`. C'est la règle du chantier inventaire : le boîtier est la colonne qui compte.
Quand le pas n'est pas encore mesuré, écrire `pas ?` — c'est une information, pas un aveu.

### 2.3 Ordre de pose, par rentabilité décroissante

**Phase 0 — vider le sol (avant toute étiquette).**
Le stock invisible est le plus coûteux : on rachète ce qu'on ne voit pas. Sont posés au sol,
jamais ouverts : **4 à 6 colis d'expédition scellés**, **3 boîtes bleues Cytron**, un
**cageot de sachets ESD**, plusieurs cartons. Les ouvrir et les ranger est le seul geste qui
*augmente* réellement l'inventaire. Les boîtes Cytron sont prioritaires : Cytron fabrique des
drivers de moteurs, c'est le chemin roues.

**Phase 1 — stabiliser, puis étiqueter les ~20 bacs des chantiers en cours.**
D'abord retirer les cales carton et fiabiliser les rangées (sinon l'adresse ment).
Puis étiqueter uniquement ce qui sert aujourd'hui : fourches optiques, borniers verts,
WAGO, DC-DC, connectique JST, matrices LED, cartes RP2040/Pico, alimentations, capteurs.
C'est là que l'inventaire évite des achats **cette semaine**.
Ça valide aussi le format d'étiquette sur un échantillon avant de le graver sur 200 bacs.

**Phase 2 — adressage complet, travée par travée.**
Une travée à la fois, en filmant chaque travée **de face, à plat, bac par bac** au passage :
c'est ce qui manque à l'inventaire actuel et ça ne coûte rien de plus puisque tu es devant.

### 2.4 Le lien avec l'inventaire — c'est là que ça se joue

L'inventaire actuel (`inventaire-stock.md`) a une colonne « repère » qui pointe vers **une
seconde de vidéo**. C'est provisoire et ça se périmera au premier rangement.

**Dès qu'une étiquette est posée, la colonne « repère » devient une adresse.** Le fichier
cesse alors d'être un dépouillement pour devenir un vrai inventaire : consultable,
vérifiable, et surtout **corrigeable sans revoir la vidéo**.

Proposition concrète : tenir la source des étiquettes dans le dépôt, en un fichier plat
`docs/hardware/etiquettes.csv` — `adresse ; texte ; famille`. Il sert à trois choses :
réimprimer une travée qui a pâli, retrouver ce qu'on a écrit, et **permettre à l'IA de
répondre « tu en as, c'est en B4-07 »** au lieu de « tu en as quelque part ».

---

## 3. Améliorations de rangement

Classées par rapport valeur/effort, en ne proposant **que** ce que les images justifient.

### 3.1 Gratuit et immédiat

**a) Séparer le secteur de la très basse tension.** ⚠️ Point de sécurité.
Des **condensateurs 220 µF / 250 V** (6 exemplaires) et un **condensateur X2 secteur** ont
été trouvés dans des bacs de composants basse tension, à portée de pioche. Un 250 V qui
part dans un montage 12 V par erreur, ou qu'on manipule chargé, ce n'est pas anodin.
→ Un bac dédié, étiqueté **`⚡ SECTEUR — NE PAS PIOCHER`**, à l'écart des bacs de
composants courants.

**b) Réunir les cartes-présentoirs avec leurs boîtes.**
Les cartes du kit **BOJACK** (tableau des 24 valeurs) et du kit **VE TERMINALS** traînent au
sol, **séparées de leur contenant**. Ces cartes portent toute la nomenclature : séparées,
l'information est perdue et on rachètera des condensateurs qu'on a. → Découper la carte et
la glisser sous le couvercle, ou la scotcher dessus.

**c) Généraliser les deux bonnes pratiques que tu appliques déjà.**
Elles sont dans tes propres boîtes, il n'y a qu'à les étendre :
- **Nomenclature sur le couvercle** (kit BOJACK) : lisible sans ouvrir.
- **Étiquettes manuscrites collées à l'intérieur, sur les cloisons** (boîte de jacks DC :
  `2.1*5.5`, `2.5*5.5`). Indécollables au transport, lisibles à l'ouverture. C'est le seul
  endroit du stock où une cote critique est écrite noir sur blanc — et c'est exactement le
  genre d'information qui manque partout ailleurs (pas des borniers, pas des JST).

**d) Poser les cloisons dans les bacs gris.**
Les bacs ont des **rails internes moulés** prévus pour des cloisons, et **aucune n'est
installée**. Un bac = une famille aujourd'hui ; avec deux cloisons, un bac = trois familles
sans acheter un bac de plus. Cible immédiate : le bac « matrices LED + cartes rouges »
(saturé, deux familles distinctes) et le bac « câblage + modules capteurs » (le plus
mélangé du meuble).

**e) Barrer l'étiquette d'un sachet qu'on réemploie.**
Le piège documenté du stock : un sachet marqué « INTER A LEVIER » contient des
`SN74AHCT125N` ; un sachet « DTS62K poussoirs » contient des résistances ; un sachet
Briksmax contient de la visserie ; un sachet « adaptateur SMA » contient une carte.
→ Règle : **quand on vide un sachet pour le réutiliser, on barre l'ancienne étiquette au
marqueur.** Deux secondes, et ça supprime une classe entière d'erreurs — y compris pour
l'IA, qui lit ces étiquettes et se fait piéger.

### 3.2 Petit effort, gros gain

**f) Formaliser un bac « ARRIVAGE — à ranger ».**
Aujourd'hui, ce qui arrive reste au sol devant les étagères, et y bloque l'accès à la rangée
basse. Ce n'est pas un défaut de discipline : il manque juste une destination. Un bac vide
(il y en a douze) étiqueté `ARRIVAGE` donne au colis un endroit où être en attendant, et
signale d'un coup d'œil ce qui reste à traiter.

**g) Ouvrir et adresser les sachets ESD opaques.**
Plusieurs bacs entiers et un cageot n'en contiennent que. Un sachet ESD signale en général
un composant qui valait la peine d'être protégé — c'est-à-dire exactement ce qu'on
rachèterait. C'est le plus gros trou noir de l'inventaire.

**h) Traiter les cartes de récupération comme un stock à part.**
8 à 12 cartes prototypes câblées à la main et plusieurs bacs de cartes d'appareils
dessoudées occupent des bacs adressables. Ce n'est pas du stock de composants, c'est du
**gisement de récupération** : valeur réelle (borniers, IDC, LED, plaques) mais délai de
mise en œuvre non nul. → Les regrouper sous une adresse `RÉCUP`, et libérer les bacs.

### 3.3 À faire au passage, pendant l'étiquetage

Cinq mesures au pied à coulisse règlent à elles seules la moitié des « confiance basse » de
l'inventaire. À faire **le bac dans la main**, pas en séance dédiée :

| Mesure | Sur quoi | Pourquoi c'est bloquant |
|---|---|---|
| **Pas des borniers verts** | 5,08 / 3,81 / 3,5 mm | **300+ pièces** aujourd'hui inexploitables pour un achat |
| **Pas des JST blancs** | XH 2,5 vs PH 2,0 | 3 lignes de la commande odométrie en dépendent |
| **Filetage des entretoises** | M2,5 ou M3 | boîte de 200+ inutilisable sans ça |
| **Largeur des cosses faston** | 4,8 ou 6,35 mm | 100+ cosses + autant d'isolants |
| **Cote des jacks DC** | 5,5×2,1 ou 5,5×2,5 | **déjà fait** — c'est le modèle à suivre |

La dernière ligne est là pour montrer que la méthode marche déjà chez toi : la boîte de
jacks est le seul contenant du stock dont on peut commander la contrepartie sans rien
remesurer.

---

## 4. Ce que ça coûte, honnêtement

- **Phase 0** (vider le sol) : une petite heure, et c'est celle qui rapporte le plus.
- **Phase 1** (~20 bacs, chantiers en cours) : une heure environ, mesures comprises.
- **Phase 2** (adressage complet, ~200 contenants) : à ~20 s l'étiquette, environ 1 h 10 de
  pose — mais le vrai coût n'est pas la pose, c'est **décider quoi écrire**, donc ouvrir et
  regarder. Compter une demi-journée, étalée travée par travée. Rien n'oblige à tout faire
  d'un coup : l'adressage est utile dès la première travée.

Aucun achat n'est nécessaire : les porte-étiquettes, les rails de cloison, les bacs vides et
l'étiqueteuse sont déjà là.
