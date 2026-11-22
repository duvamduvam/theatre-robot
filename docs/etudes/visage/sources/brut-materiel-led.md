<!-- Rapport brut d'un agent de recherche web, archivé tel que rendu le 22/11/2026. Matière première de etude-visage.md : non relu, non corrigé. -->

# Brut — matériel LED et lisibilité de jour

# Rapport de collecte : visage LED en plein jour

Date de consultation de toutes les sources : 22/11/2026. Plafond de 12 pages atteint. Je m'arrête donc, et le tableau de couverture ci-dessous dit ce qui manque.

## 1. Ce que j'ai couvert / ce que je n'ai pas couvert

**Ouvert et lu (source primaire)** :
- Samsung Insights (nits)
- README hzeller (GitHub)
- Adafruit : acrylique 4749, guide Pi 5, 64x32 P3 (2279), NeoPixel flexible 16x16 (2547), guide diffuseur MatrixPortal
- Waveshare P3 64x32
- Daktronics (distance de vision)

**Ouvert mais inexploitable** :
- Catalogue PDF Hikvision : contenu vide à l'extraction.
- plexiglas-shop.com : redirection vers `https://www.polyvantis-shop.com/lu/products/pl9h04-sc-3-00.html?lang=0`, non suivie faute de budget.
- store.makerplane.org : erreur DNS.

**Vu uniquement dans des résumés de résultats de recherche, page non ouverte (donc « non vérifié » au sens strict)** :
- Les valeurs de luminosité Hikvision et la FAQ Made-in-China.
- Les fiches techniques WS2812B (mcd).
- Les transmissions PLEXIGLAS LED.
- Les prix GC9A01 (Pi Hut, Core Electronics, Switch Science).
- Les prix des écrans 5" haute luminosité (Orient Display, MakerPlane, New Haven).
- Les règles de distance de Christie, Samsung, Planar et Barco.
- Le fil Discourse hzeller et le message de Hackster sur l'état alpha de Piomatter.

**Non trouvé / non couvert** :
- Luminance mesurée en cd/m² d'une matrice WS2812B/SK6812 (aucune mesure publiée trouvée).
- Luminance des HUB75 P2.5, P3, P4 et P5 en intérieur et en extérieur, en source primaire.
- Ni prix ni fiche pour les panneaux HUB75 32x32 ou flexibles, la WS2812 16x16 rigide, les écrans ronds 2,1", 2,8" et 3,4" et le 5" HDMI Waveshare.
- Pimoroni, Kubii et AliExpress : aucune page marchande lue.
- Chemcast Black LED : aucune page trouvée.
- Distance LED-diffuseur : aucune source chiffrée.
- Perte de luminance du film de diffusion, du PETG ou PLA blanc imprimé et de la grille séparatrice.
- Retours de makers sur le sujet.
- Seule la face noire de PLEXIGLAS a été abordée, et seulement via un résumé de recherche.

## 2. Tableau de synthèse

| Donnée | Valeur | Statut | Source |
|---|---|---|---|
| Écran intérieur autonome | 350-500 nits | lu | Samsung (03/11/2021) |
| Enseigne côté rue/trottoir | « 8 à 12 fois » l'intérieur, soit ≈ 2 800-6 000 nits | calcul du lecteur de la page, pas une valeur citée | Samsung |
| Menu drive-in | « push 4 000 nits » | lu | Samsung |
| Soleil direct | pas de chiffre ; « washed out and unviewable » si trop faible | lu | Samsung |
| Panneau 64x32 P3 Adafruit 2279 | 2000 mcd par LED, 5 V ~4 A tout allumé, 191×96×15 mm, 44,95 $ (USD présumé, devise non nommée par la page) | lu | Adafruit |
| Panneau 64x32 P3 Waveshare | 64×32, pas 3 mm, 192×96 mm, 5 V 2,5 A, ≤12 W, 1/16 scan, HUB75, 22,99-25,99 USD, luminosité « adjustable » sans chiffre | lu | Waveshare |
| NeoPixel flexible 16x16 Adafruit 2547 | 160×160×2 mm, 84,95 $ (1-9), pas non indiqué, LED WS2812B ou SK6812 | lu | Adafruit |
| Acrylique noir diffusant Adafruit 4749 | 10,2"×5,1" (260×130 mm), 2,6 mm, 5,95 $ (1-9), rupture de stock | lu | Adafruit |
| Pi 5 + hzeller | support ajouté, mais « not officially supported as of 2025/11 » | lu | GitHub hzeller |
| Pi 5 + Piomatter | Pi 5 uniquement, Bonnet ou HAT RGB Matrix | lu | Guide Adafruit Pi 5 |
| Règle de distance Daktronics | distance optimale (pieds) ≈ 3 × pas (mm) | lu | Daktronics |

## 3. Une section par source

### Samsung Insights — page officielle d'un fabricant, billet daté
URL : https://insights.samsung.com/2019/09/12/fighting-the-bright-outdoor-displays-propel-businesses-forward
- Date affichée : 03/11/2021, par Dave Haynes. L'URL contient pourtant 2019 : incohérence d'URL à signaler.
- Écran autonome en intérieur : « 350-500 nits ».
- Enseignes en vitrine, trottoir ou place : « eight to 12 times that brightness level ».
- Menus drive-in : « push 4,000 nits ».
- Soleil direct de mi-après-midi : l'écran sera « washed out and unviewable if the brightness isn't high enough ». Aucun chiffre explicite pour l'ombre ou pour le soleil direct.
- Unité : nits (cd/m²). Il s'agit d'écrans LCD/affichage numérique, pas de matrices LED nues.
- Un résumé de recherche a aussi cité une fiche AliExpress (> 5 000 nits pour la lisibilité en plein jour). C'est une affirmation de vendeur, page non ouverte : https://www.aliexpress.com/s/wiki-ssr/article/p5-led-display

### GitHub hzeller/rpi-rgb-led-matrix — dépôt officiel
URL : https://github.com/hzeller/rpi-rgb-led-matrix
- Le README dit : « Raspberry Pi 5 support has now been added. »
- Option `--led-rp1-pio=0` : backend RP1 RIO, par défaut, « higher CPU usage but much faster performance ».
- Option `--led-rp1-pio=1` : backend RP1 PIO, « very minimal CPU usage ».
- Section matériel : « Rpi5 is not officially supported as of 2025/11, but see #1603 ».
- Date de dernier commit non visible ; 1 267 commits.
- Le README contient donc deux phrases qui se nuancent. Voir la section 4.

### Adafruit, guide « RGB Matrix Panels With Raspberry Pi 5 » — documentation officielle
URL : https://learn.adafruit.com/rgb-matrix-panels-with-raspberry-pi-5/overview
- « This guide and library support the Raspberry Pi 5 only. »
- Matériel : Pi 5, RGB Matrix Bonnet ou HAT (un seul suffit), panneaux HUB75.
- Chaque panneau peut tirer jusqu'à 4 A pleine charge. Deux panneaux sur une alim 4 A, « still plenty bright for indoor projects ».
- Rien sur le taux de rafraîchissement, la charge CPU ou le statut alpha dans cette page. La mention « alpha » vient d'un résumé de recherche Hackster non ouvert : https://www.hackster.io/news/adafruit-s-piomatter-library-brings-hub75-rgb-led-matrix-support-to-the-raspberry-pi-5-s-rp1-chip-70bfb3c3bdd8

### Adafruit 2279, panneau 64x32 P3 — page marchande officielle
URL : https://www.adafruit.com/product/2279
- Prix : 44,95 $ à l'unité (40,46 $ par 10-99). Devise non nommée par la page ; USD présumé, HT/TTC non précisé.
- Dimensions : 191 × 96 × 15 mm, environ 189 g.
- Pas : 3 mm. Alimentation : « 5V regulated power input @ ~4A (with all LEDs on) ».
- Luminosité : « 2000 mcd LEDs on 3mm pitch » (intensité par LED, pas une luminance en cd/m²).
- Usage : « Indoor display, wide visibility », sans indice de protection extérieure.

### Waveshare RGB Matrix P3 64x32 — page marchande officielle
URL : https://www.waveshare.com/rgb-matrix-p3-64x32.htm
- 64×32 = 2 048 LED RGB, pas 3 mm, 192×96 mm.
- Prix : 22,99 à 25,99 USD. La page liste deux versions (Standard et GOB) sans dire laquelle correspond à quel prix. HT/TTC non précisé.
- Alimentation 5 V / 2,5 A, puissance ≤ 12 W. Interface HUB75, entrée et sortie en chaîne.
- Scan 1/16. Rafraîchissement non indiqué. Luminosité : « adjustable brightness », sans chiffre.
- Waveshare propose aussi P2.5, P4 et P5 (pages wiki, non ouvertes).

### Adafruit 2547, NeoPixel flexible 16x16 — page marchande officielle
URL : https://www.adafruit.com/product/2547
- Prix : 84,95 $ (1-9 unités), 76,46 $ (10-99). Devise non nommée.
- 160 × 160 × 2 mm, 256 LED. Pas non indiqué sur la page.
- LED « WS2812B ou SK6812 », décrites comme de même luminosité, couleur et protocole.
- Courant : « over 15A » théorique tout en blanc. Adafruit recommande de rester sous 5 A (le PCB flexible peut ne pas supporter plus).
- Aucun chiffre de lumen ou de nit.

### Adafruit 4749, acrylique noir diffusant — page marchande officielle
URL : https://www.adafruit.com/products/4749
- 10,2" × 5,1" (260 × 130 mm), épaisseur 2,6 mm, « special cast acrylic ».
- Prix : 5,95 $ (1-9 unités), 5,36 $ (10-99). Statut : rupture de stock au moment de la lecture. Devise non nommée.
- Texte du vendeur : contrairement à l'acrylique fumé ou teinté, il « sharpens the pixels and reduces the glare », et les couleurs sont « vivid and readable indoors and out ».
- Aucune transmission, aucun contraste chiffré. Il s'agit de revendications commerciales.

### Adafruit, guide diffuseur MatrixPortal — documentation officielle
URL : https://learn.adafruit.com/adafruit-matrixportal-m4/led-matrix-diffuser
- Poser l'acrylique directement sur la matrice, face mate vers l'extérieur, papier retiré des deux faces.
- Fixation par adhésif aux quatre coins et au milieu des grands côtés.
- Il réduit l'éblouissement et les reflets spéculaires de la grille plastique, et protège les LED, « indoors and out ».
- Rien sur la distance aux LED, le contraste chiffré, la perte de luminosité ni la durabilité extérieure.

### Daktronics, base de connaissances — page d'un fabricant
URL : https://www.daktronics.com/en-us/support/kb/000030569
- Distance optimale (en pieds) ≈ 3 × pas (en mm) ; exemple : 10 mm donne environ 30 ft.
- Pas de distance minimale explicite.
- Règle de taille de texte : au moins 1 pouce de hauteur par 25 pieds de distance.
- Pas de date affichée ; pied de page © 2026.

### Données vues en résumé de recherche seulement (pages non ouvertes, non vérifié)
- **WS2812B, intensité lumineuse (mcd)**, trois jeux de valeurs selon la révision :
  - Ancien : R 390-420, V 660-720, B 180-200 mcd.
  - Worldsemi V1.0 (2016), à 20 mA : R 550-700, V 1100-1400, B 200-400 mcd.
  - Copies Watterott/Espressif à 12 mA : R 300-500, V 600-1000, B 200-300 mcd. L'exemplaire Espressif concerne le WS2812B-Mini (3535), pas un 5050.
  - URL candidates : https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/8880/WS2812B.pdf, https://learn.watterott.com/kb/ws281x/WS2812B-v5.pdf, https://dl.espressif.com/dl/schematics/WS2812B-Mini-V3.pdf
  - Ce sont des mcd par LED, pas des cd/m² de matrice. Aucune mesure de luminance publiée n'a été trouvée.
- **HUB75 professionnels (Hikvision, catalogue)** : P3.0 et P4.0 intérieur 600 nits ; extérieur P3.0 et P4.0 4 500 nits, IP65 en façade. URL : https://www.hikvision.com/content/dam/hikvision/en/brochures-download/product-leaflet/LED-Catalogue-leaflet-printing.pdf. Le PDF a été ouvert mais est revenu vide : non vérifié.
- **FAQ fabricant Made-in-China** : intérieur 800-1 500 nits, extérieur 5 000-8 000 nits (revendication de vendeur, page non ouverte). URL : https://m.made-in-china.com/amp/product/RGB-Pattern-APP-Programmable-LED-Matrix-Panel-Customized-LED-Sign-2210281205.html
- **Règles de distance** (non ouvertes) :
  - Christie : ~1 m de distance minimale par mm de pas.
  - Samsung : 1 mm de pas = 8 ft.
  - Planar : pas × 10 = distance en ft.
  - Barco : distance optimale en m = 2 × pas commercial en mm.
  - URLs : https://www.christiedigital.com/spotlight/how-to-choose-the-right-pixel-pitch/, https://insights.samsung.com/2021/06/16/what-is-pixel-pitch-understanding-led-displays, https://www.planar.com/blog/2025/what-is-pixel-pitch-and-why-does-it-matter/, https://barco.com/news/2020-03-11-ledtalks-what-is-pixelpitch
- **PLEXIGLAS LED noir/blanc (transmission D65, 3 mm)** : 7H25 GT environ 13 % (brillant) ; 9H04 SC environ 18 % (satiné) ; 9M500 SC environ 15 % ; 9H001 environ 17 %. Noir à la lumière du jour, garantie 10 ans « black stays black ». Aucun contraste ou lisibilité au soleil chiffré. URLs : https://www.plexiglas-shop.com/pl/products/pl7h25-gt-3-00.html, https://www.zenit.cz/public/media/Plasty/Zenit_Technicky_List_Plasty_Plexiglas_LED_9H001_AJ.pdf. La page 9H04 SC a été tentée : redirection non suivie.
- **Prix GC9A01 1,28" rond 240×240** :
  - Pi Hut 16,20 £ TTC (non-touch), https://thepihut.com/products/round-1-28-lcd-display-module-240x240-ips-65k-rgb
  - Core Electronics 31,50 AUD TTC (avec tactile), https://core-electronics.com.au/128inch-round-lcd-display-module-with-touch-240240-pixels.html
  - Switch Science 2 739 ¥ TTC, https://www.switch-science.com/collections/waveshare/products/7347
  - Aucune luminance ni consommation lue.
- **Écrans 5" HDMI haute luminosité** :
  - Orient Display 5,0" 800×480, 1 000 nits, 61,19 $, https://www.orientdisplay.com/?p=451321
  - MakerPlane 5", 1 100 cd/m², 139,95 $ (compatibilité Pi 3/4 mentionnée, pas Pi 5), https://store.makerplane.org/5-sunlight-readable-touchscreen-hdmi-display-for-raspberry-pi. La page n'a pas pu être ouverte (erreur DNS).
  - New Haven 5" 89,20 $ (900 nits sur la version allemande), https://newhavendisplay.com/5-0-inch-ips-capacitive-hdmi-tft-module
  - Un « typique 300-400 nits » est cité pour un écran non modifié.
  - Résolution, consommation et interface : non lus.

## 4. Contradictions et incertitudes

1. **hzeller et Pi 5.** Le README affiche à la fois « support has now been added » avec deux backends (RIO par défaut, PIO à faible charge CPU) et « not officially supported as of 2025/11, but see #1603 ». Je rapporte les deux sans trancher. Les résumés de recherche (Discourse, ancienne copie du README) parlaient d'un Pi 5 non supporté : sources probablement antérieures, non vérifiées.
2. **Date Samsung.** L'URL dit 2019, la page affiche le 03/11/2021.
3. **Unités mélangées.** Adafruit annonce 2 000 mcd par LED. Les fabricants d'afficheurs annoncent des nits par module. Les mcd des WS2812B varient selon la révision et le courant de test. Aucune de ces valeurs ne se convertit directement en cd/m² de matrice sans connaître le pas, le courant et la surface émissive.
4. **Règles de distance incohérentes entre elles.** Daktronics : 3 ft par mm. Samsung : 8 ft par mm. Planar : 10 ft par mm. Christie : 1 m par mm (une autre de ses tables utilise 3 m). Barco : 2 m par mm. Les unités et les facteurs diffèrent, et aucune source ne donne de distance maximale.
5. **Nits « ombre » et « plein soleil »** : aucune page lue ne donne de seuil chiffré pour l'ombre ou le ciel couvert. La valeur « 2 800-6 000 » est un calcul sur la formulation de Samsung, pas une citation.
6. **Prix** : devises non nommées sur les pages Adafruit (USD présumé). HT/TTC non précisé sauf mention « TTC » (Pi Hut, Core Electronics, Switch Science, vues en résumé). Les prix sont des instantanés du 22/11/2026, non tarifés en régime de volume sauf indication.
7. **Waveshare** : deux versions (Standard et GOB) pour une fourchette de prix, sans correspondance explicite.
8. **Mandat non couvert** : la distance LED-diffuseur, la perte de luminance de chaque matériau et la raison physique du gain de contraste d'une face noire n'ont aucune source chiffrée dans ce rapport. Seul l'argumentaire vendeur Adafruit (« sharpens the pixels and reduces the glare ») a été lu.

Sources :
- [Samsung Insights, écrans extérieurs](https://insights.samsung.com/2019/09/12/fighting-the-bright-outdoor-displays-propel-businesses-forward)
- [hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix)
- [Adafruit, guide Pi 5](https://learn.adafruit.com/rgb-matrix-panels-with-raspberry-pi-5/overview)
- [Adafruit 2279](https://www.adafruit.com/product/2279)
- [Adafruit 2547](https://www.adafruit.com/product/2547)
- [Adafruit 4749](https://www.adafruit.com/products/4749)
- [Adafruit, guide diffuseur](https://learn.adafruit.com/adafruit-matrixportal-m4/led-matrix-diffuser)
- [Waveshare P3 64x32](https://www.waveshare.com/rgb-matrix-p3-64x32.htm)
- [Daktronics, distance de vision](https://www.daktronics.com/en-us/support/kb/000030569)
