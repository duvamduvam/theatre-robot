# Outils d'atelier

Petits utilitaires hors robot, utiles pour documenter le matériel.

## Feuille millimétrée (photos de matériel)

Fond quadrillé à imprimer pour photographier une pièce, une carte ou un
connecteur **avec une échelle** : on peut relire une cote sur la photo des mois
plus tard, sans avoir à ressortir la pièce.

- `feuille-millimetree-A4.pdf` — **profil bureau** (laser/jet d'encre ≥ 600 dpi,
  couleur). Page 1 portrait (grille 180 × 260 mm), page 2 paysage (270 × 170 mm).
- `feuille-millimetree-A4-thermique.pdf` — **profil thermique** : c'est celui à
  utiliser sur l'imprimante de l'atelier (Xprinter P83, thermique directe
  203 dpi monochrome). Mêmes grilles.
- `feuille-millimetree-A3.pdf` — profil bureau en A3 (la thermique de
  l'atelier ne fait pas d'A3 : à faire tirer ailleurs).
- `feuille-millimetree.py` — le générateur (Python 3, aucune dépendance).

**Quelle page prendre ?** Page 1 = portrait, page 2 = paysage. Même grille,
choisir selon la pièce à photographier.

### Pourquoi un profil « thermique » séparé

Une thermique directe à 203 dpi n'a ni couleur ni demi-teintes, et son point
fait 0,125 mm. Le profil adapte trois choses, qui dépendent ensemble de la
machine :

| Réglage | Bureau | Thermique | Raison |
|---|---|---|---|
| Palette | bleu | **noir pur** | un aplat non noir passerait au tramage, qui hache les traits fins en pointillé |
| Épaisseurs 1/5/10 mm | 0,18 / 0,4 / 0,7 pt | **1 / 2 / 3 points machine** | un trait plus fin qu'un point n'est pas rendu de façon fiable ; la hiérarchie repose alors sur l'épaisseur seule |
| Corps de texte | 5 / 6 pt | **7 / 7,5 pt** | 5 pt à 203 dpi = 14 px de haut, illisible |

**Limite mesurée, et elle est irréductible :** à 203 dpi, 1 mm vaut 7,99 points.
Le pas millimétrique est donc **irrégulier de ±0,06 mm** (mesuré : min 0,938,
max 1,064, médian 1,001 mm). L'échelle d'ensemble, elle, reste juste — 180 mm
de grille mesurés à 179,93 mm, soit 0,04 % d'erreur. Autrement dit : **bon pour
mesurer, un peu grossier à l'œil.** Pour du fin (pas de vis, connecteur), une
impression laser du profil bureau reste supérieure.

Deux réserves propres au papier thermique, à connaître avant d'en faire un fond
d'atelier durable : il est **brillant** (reflets sur les photos, surtout avec du
métal — éclairage diffus obligatoire) et il **s'efface** avec le temps, la
chaleur et la lumière. À réimprimer quand il pâlit ; ne pas le laisser au soleil.

### Impression — le seul piège

**Imprimer à « taille réelle » / 100 %, jamais « ajuster à la page ».** Le
pilote réduit sinon de ~4 % pour rentrer dans les marges, et le millimétrage
devient faux *sans que rien ne le signale*. D'où la barre témoin en bas de
page : elle doit mesurer exactement 100 mm au réglet. Si ce n'est pas le cas,
la feuille est bonne à jeter.

### Protocole photo

1. Poser la pièce sur la feuille, à plat, sans masquer les 4 mires noires.
2. Photographier **à l'aplomb** (l'appareil au-dessus du centre) : une prise de
   biais fausse les distances lues, la grille sert alors seulement à corriger.
3. Les 4 mires sont des points de référence à distance connue (rappelée en bas
   de page) : elles permettent de redresser la perspective a posteriori.
4. Lumière rasante = ombres portées qui décalent les bords apparents ;
   préférer un éclairage diffus.

### Régénérer / adapter

```bash
python3 feuille-millimetree.py                          # A4 bureau, portrait + paysage
python3 feuille-millimetree.py --profil thermique       # A4 pour la thermique 203 dpi
python3 feuille-millimetree.py --format A3              # A3
python3 feuille-millimetree.py --format A5 --orientation portrait
python3 feuille-millimetree.py --couleur gris           # force la palette
python3 feuille-millimetree.py --sortie /tmp/essai.pdf
```

Impression sur la thermique de l'atelier, tramage désactivé (il n'a rien à
faire sur du trait pur) :

```bash
lp -d Xlife_P83C -o media=A4 -o HalftoneType=None -o Darkness=Dark \
   -o fit-to-page=false docs/outils/feuille-millimetree-A4-thermique.pdf
```

Le PDF est vectoriel (écrit octet par octet, sans bibliothèque) : il reste net
à n'importe quelle résolution d'imprimante. Les réglages fins — marge,
palettes, épaisseurs de trait, taille des mires — sont des constantes en tête
du script, chacune commentée avec la contrainte qui l'a fixée.
