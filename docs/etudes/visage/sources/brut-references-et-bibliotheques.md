<!-- Rapport brut d'un agent de recherche web, archivé tel que rendu le 22/11/2026. Matière première de etude-visage.md : non relu, non corrigé. -->

# Brut — références de visages expressifs et bibliothèques d'yeux

**Rapport de collecte. Consultations du 22/11/2026.**

## 1. Couvert et non couvert

Le mandat dépasse le plafond de 12 pages. J'ai ouvert 11 pages (dont un 404) et lancé 11 recherches. Une recherche ne donne que des extraits, donc c'est de la matière de second niveau. Les pages ouvertes ont été lues par un modèle de résumé : les phrases entre guillemets sont à vérifier sur la source avant citation.

**Couvert, avec page ouverte :** FluxGarage RoboEyes, Adafruit Learning System (Teensy), liunix61/esp32-eyes, ProtosoftToasterOS, ProtOpenSource, guide Vector (randym32), Core77 (Cozmo/EVE), IEEE Spectrum (157 visages), page Adafruit Monster M4sk.

**Couvert par extraits de recherche seulement (page non ouverte) :** WALL-E/EVE, EMO, Mirokaï, BDX, Hoffman/anticipation, vallée dérangeante, Lecoq.

**Non couvert, aucune source ni recherche :** Eilik (la recherche n'a rien donné), Looi, Jibo (hors un chiffre de l'étude de 157 visages), Buddy (idem), casques Daft Punk, Baymax, Bellabot/Pudu. Pas non plus de source sur le point fixe ni sur « le regard précède le geste ». Pas de source sur les conventions de dessin protogen au pixel. Pas de dépôt ni de licence pour Otto/Zowi, pour le dépôt Adafruit « Uncanny Eyes » ni pour les projets NeoMatrix 8x8/16x16. Pas de lecture des 12 principes de Disney eux-mêmes.

## 2. Tableau de synthèse

| Sujet | Fait | Source (type) |
|---|---|---|
| RoboEyes | GPL-3.0, Adafruit GFX, taille d'œil réglée par `begin(largeur, hauteur)`, humeurs, clignement auto, 8 directions, transitions lissées | page GitHub officielle |
| esp32-eyes (fork liunix61) | OLED 128x64, 18 émotions, clignement et regard aléatoires, une seule émotion à la fois, licence non lisible | page GitHub |
| ProtosoftToasterOS | MIT, MAX7219 8x8, 7 modules par côté | page GitHub |
| ProtOpenSource | ESP32, 5 états de bouche, licence non indiquée | doc GitHub |
| Monster M4sk | 2 TFT IPS 240x240, licence non indiquée | page Adafruit |
| Étude de 157 visages d'écran | yeux circulaires les plus fréquents, ~10 % d'yeux humains | article IEEE Spectrum, 03/04/2018 |
| Cozmo/Vector | yeux animés, paramètres interpolés, sans bouche dans les extraits | doc communautaire randym32 + presse |

## 3. Sources, une par une

### Q3 — Bibliothèques open source

**FluxGarage RoboEyes** — https://github.com/FluxGarage/RoboEyes (page officielle du dépôt)
- Licence : GPL-3.0 (fichier LICENSE.txt, texte non reproduit sur la page).
- Résolution : non précisée. Le sujet « oled-display-ssd1306 » suggère le SSD1306, mais « 128x64 » n'est pas écrit. La taille se règle par `begin()` ; basé sur Adafruit GFX.
- Forme d'œil réglable en pixels : largeur, hauteur, rayon des coins, espacement. Mode cyclope.
- Humeurs : par défaut, heureux, fatigué, en colère.
- Animations : clignement auto, mode idle (repositionnement aléatoire), rire (secousses verticales), confusion (secousses horizontales), curiosité, gouttes de sueur, tremblement H/V, ouverture/fermeture de chaque œil.
- Regard : 8 directions + centre. Transitions d'état lissées.
- API : `begin, update, drawEyes, setMood, setPosition, setCuriosity, setSweat, open, close, setHFlicker, setVFlicker, anim_confused, anim_laugh, blink, setAutoblinker, setIdleMode`.
- Date du dernier commit non visible. Le dépôt annonce une nouvelle version majeure en préparation, pull requests suspendues.

**esp32-eyes (fork liunix61)** — https://github.com/liunix61/esp32-eyes (page GitHub)
- Fork de `playfultechnology/esp32-eyes`, lui-même très inspiré de `luisllamasbinaburo/ESP32_Faces`. Passage de TFT (eSPI) à OLED (u8g2).
- Licence : un fichier LICENSE existe, type non lisible. Licence amont non vérifiée.
- OLED 128x64. Clignement auto (`RandomBlink`) ou `DoBlink()`. Regard aléatoire ou `LookAt(x, y)` avec x, y dans [-1, 1].
- 18 émotions (`FaceEmotions.hpp`), chacune un préréglage (hauteur, pente, rayon, décalage) dans `EyePresets.h`. Une seule émotion à la fois, sans mélange. Seules Glee et Anger sont nommées.
- Le texte de la recherche dit « inspiré de Cozmo ». Le même dépôt est cité sur le résultat de recherche.

**Adafruit Teensy 3.1 animated eyes** — https://learn.adafruit.com/animated-electronic-eyes-using-teensy-3-1 (guide Adafruit, sans date visible)
- Un écran par œil : OLED 1,5" ou TFT 1,44". Résolution en pixels non donnée. Licence du code non mentionnée.
- Clignement et clin d'œil par boutons optionnels. Mouvement par joystick optionnel. Pupille dilatable, photorésistance optionnelle. Le logiciel « peut gérer ces effets de façon autonome ».
- Le dépôt « Uncanny Eyes » lui-même : l'URL tentée a renvoyé 404, donc non vérifié.

**Adafruit Monster M4sk** — https://learn.adafruit.com/adafruit-monster-m4sk-eyes (page Adafruit)
- Deux TFT IPS 240x240, chacun sur son bus SPI. Code Arduino seulement (pas CircuitPython).
- « 2 yeux à graphismes configurables », animation 3D des globes. Clignement, suivi, paupières, licence et date : non mentionnés.

**ProtosoftToasterOS** — https://github.com/BadgerCode/ProtosoftToasterOS (page GitHub)
- Licence MIT. Matrices MAX7219 8x8 : par côté 2 modules pour l'œil, 4 pour la bouche, 1 pour le nez (14 au total). Une bande de 15 LED RGB par côté, capteur IR « boop », Arduino (exemple Nano Every), FastLED.
- Expressions et clignements dans `ToasterOS/Protogen_Faces.h`, dessinées dans `face-demo.html`. Conventions de dessin non détaillées. `FlipX/FlipY` pour l'orientation des panneaux.

**ProtOpenSource** — https://github.com/PanickingLynx/ProtOpenSource/blob/master/doc/DOCUMENTATION.md (doc GitHub)
- ESP32, affichage sur le 2e cœur, micro sur ADC (`MIC_PIN`). Sprites exportés de LED Matrix Studio en tableaux d'octets PROGMEM (format FastLED). 5 états de bouche (fermée + 4 ouvertures). Une matrice dessinée puis reproduite en miroir. Pilote non mentionné. Licence non indiquée.

**Autres projets cités par les recherches (non ouverts, non vérifiés) :**
- https://github.com/jujojujo2003/UncannyEyesESP32
- https://github.com/thelastoutpostworkshop/ESP32LCDRound240x240Eyes
- https://projecthub.arduino.cc/tanmay_wankar/abbc33b9-9695-4064-935e-b2d713090a80 (« Grobot Animations », MIT selon l'extrait)
- https://components.espressif.com/components/espp/expressive_eyes/versions/1.2.1/readme
- https://github.com/SukunDev/ESP32-Pet-Robot
- https://learn.adafruit.com/matrix-portal-creature-eyes?view=all
- https://github.com/stef1949/lumifur_controller (extrait de recherche : expressions numérotées 1 à 8)
- https://fpga.mit.edu/videos/2024/team39/report.pdf (extrait : deux panneaux HUB75 Waveshare 64x32 derrière une visière teintée)
- Une recherche cite https://learn.adafruit.com/adafruit-protomatter-rgb-matrix-library comme pilote HUB75.

### Q1 — Robots à visage-écran

**Guide Vector (randym32)** — https://randym32.github.io/Anki.Vector.Documentation/guides/Vector character design guide.html (documentation communautaire non officielle, date non vue)
- La section « Eyes » ne donne que les ressources utilisées par Anki, selon Mooly Segal : le livre de Jason Osipa sur le rigging des yeux et des visages, et les articles de Keith Lango « The Eyes Have It ».
- Rythme des saccades : plus lent = état « méthodique, pensif » (selon un billet cité). Aucune forme, couleur ni résolution.

**Page « Eye animation »** — https://randym32.github.io/Anki.Vector.Documentation/tools/Eye animation.html (documentation communautaire)
- Paramètres contrôlés : forme relative de l'œil, ouverture (plissé, endormi), squash/stretch (écartement des yeux), sourcil, paupière.
- Les animateurs utilisent surtout des préréglages (environ deux douzaines). Le système interpole chaque paramètre entre images sur une durée donnée.
- Démo « JoystickNSliders » (animatrice Molly Wright, Digital Dream Labs) : 4 axes (inquiet/curieux, en colère/content, fréquence de clignement, regard gauche-droite).
- Résolution et couleurs : non donnés.

**Presse Cozmo/Vector** — résultat de recherche, pages non ouvertes
- https://www.designnews.com/testing-measurement/from-cozmo-to-vector-how-anki-designs-robots-with-emotional-intelligence : yeux sans pupille qui changent de forme (« se compriment en fentes » quand il est content). Cozmo avait au début des pupilles, qui aidaient à repérer le regard, puis elles ont été retirées. Animateur Carlos Baena (ex-Pixar). Équipe issue de Pixar et DreamWorks. Outils écrits dans Maya pour animer un robot réel.
- Aucune déclaration d'Anki sur l'absence de bouche trouvée.

**Core77, 01/07/2016** — https://www.core77.com/posts/54328/Whats-theOne-Design-Element-That-Can-Make-a-Robot-Lovable (article de blog, ouvert)
- Thèse de l'auteure Rain Noe : « With the eyes. » Les yeux d'EVE « convey mood, intent, emotion and personality ». Cozmo et EVE sont comparés. Aucun concepteur n'est cité par son nom.

**WALL-E / EVE** — résultat de recherche, pages non ouvertes
- https://awn.com/animationworld/ibot-and-rust-bucket-interview-wall-e-designer-jay-shuster : Stanton voulait des yeux en forme de lentille de jumelles, car la forme porte déjà l'expression et donne un air enfantin. Ralph Eggleston : cela donnait plus de matière aux animateurs.
- Simplicité préférée dans les performances, car trop de mouvements rendraient le robot humain. WALL-E = boîte, EVE = œuf (même recherche).
- Ben Burtt : film « non verbal », pas muet (https://designingsound.org/2009/09/ben-burtt-special-wall-e-the-definitive-interview/).
- Pas de source sur l'absence de bouche de WALL-E.

**EMO (Living.AI)** — blog commercial d'un revendeur (non primaire) : https://keyirobot.com/blogs/buying-guide/inside-emo-robots-expressive-design-and-how-it-connects-with-you
- Visage sur écran LED, « plus de 1000 expressions et mouvements ». Aucune interview de concepteur trouvée. Ne pas confondre avec le robot Emo de Columbia (autre robot, 26 actionneurs).
- Eilik : rien trouvé.

**Mirokaï (Enchanted Tools)** — presse, non primaire
- https://www.electronicdesign.com/technologies/embedded/video/55278100/enchanted-tools-mirokai-cobot-is-designed-to-interact-with-people : visage par projection ; l'écran permet des expressions difficiles à obtenir sur un visage articulé.
- https://www.foxnews.com/tech/robot-animated-face-here-make-customer-service-better : apparence inspirée de l'anime.
- https://www.globalspec.com/FeaturedProducts/Detail/Maxon/Miroka_a_revolution_in_robotics/341270/0 : animateurs et designers industriels ont conçu le visage de Miroki.
- https://cyberguy.com/ROBOT-TECH/ROBOT-ANIMATED-FACE-MAKE-CUSTOMER-SERVICE-BETTER/ : histoire écrite avec le studio Gaumont.
- Aucune justification officielle trouvée.

**BDX (Disney)** — résultat de recherche, pages non ouvertes
- https://thewaltdisneycompany.com/news/behind-the-bdx-droids/ et https://la.disneyresearch.com/bdx-droids/ : tête à 4 degrés de liberté (haut, bas, côté, inclinaison), inspirée de BD-1 (Star Wars Jedi: Fallen Order). Disney dit que chaque choix (proportions, inclinaison de la tête, pose des pieds) sert la crédibilité.
- https://wdwnt.com/2025/04/video-disney-research-trains-bdx-droids-in-autonomous-human-interaction : humeurs heureux/triste/en colère/timide, reconnues par les utilisateurs.
- Rien sur les yeux ou le visage lumineux.

**Étude de 157 visages d'écran** — https://spectrum.ieee.org/what-people-see-in-157-robot-faces (article IEEE Spectrum du 03/04/2018, page ouverte). Étude : Kalegina et al., « Characterizing the Design Space of Rendered Robot Faces », HRI 2018. PDF non ouvert : https://hcrlab.cs.washington.edu/assets/pdfs/2018/kalegina2018hri.pdf
- Sur 157 visages : plus d'un tiers sont noirs. La plupart ont une bouche, peu ont nez, joues ou sourcils. Yeux circulaires les plus fréquents, environ 10 % d'yeux de forme humaine.
- Sondage 1 (50 participants, 12 visages réels) : plus sympathiques Yumi, FURo-D, Buddy, Datou ; moins sympathiques Jibo et Gongzi. Le moins apprécié : Jibo.
- Sondage 2 (visage de référence modifié) : l'absence de bouche, l'absence de pupilles et les paupières réduisent sympathie et confiance. Le visage avec sourcils est jugé le plus intelligent et mature. Le visage avec iris est le plus aimé. Aucun visage n'est significativement plus sympathique que la référence.
- Les pourcentages détaillés ne sont pas donnés par l'article.

### Q2 — Lisibilité scénique

**Lecoq / masque** — extraits de recherche, pages non ouvertes. Aucune source sur le point fixe ni sur le regard.
- Le masque neutre est le point central de la pédagogie de Lecoq (https://totaltheatre.org.uk/archive/node/1638).
- Le masque est « l'instrument privilégié d'une pédagogie de la distance » par l'effacement de la subjectivité (Guy Freixe, cité par l'extrait ; PDF non ouvert : https://releve.erudit.org/fr/revues/annuaire/2018-n63-64-annuaire05147/1067746ar.pdf).
- Selon une analyse sur Copeau (même famille d'extraits), le masque retire la parole et un geste lisible à visage nu peut devenir illisible masqué.

**Principes d'animation et robots** — extraits de recherche, non ouverts
- Gielniak et Thomaz (Georgia Tech) : exagération et anticipation appliquées au mouvement de robots ; l'exagération possible sur un robot physique est limitée par couple et vitesse : https://sites.cc.gatech.edu/social-machines/papers/gielniak12_hri_exaggeration.pdf
- Revue systématique des techniques d'animation en IHR (27 études) : https://ar5iv.arxiv.org/html/1812.06784
- Hoffman et Breazeal, lampe AUR, anticipation et fluidité d'équipe : https://hrc2.github.io/assets/pdfs/papers/HoffmanBreazealAuRo10.pdf (journal Autonomous Robots, 2010) ; thèse MIT 2007 : https://dspace.mit.edu/bitstream/1721.1/41705/2/221976393-MIT.pdf
- Étude 2019 sur le profil « slow in, slow out » : https://uhra.herts.ac.uk/id/eprint/14207/1/roman_2019.pdf
- Rien trouvé sur « le regard précède le geste » ni sur Disney Research appliqué aux 12 principes.

**Vallée dérangeante, visages stylisés** — extraits de recherche, non ouverts
- MacDorman et al. : une disparité de taille et de texture entre yeux et visage rend un personnage particulièrement étrange. Un papier lié à Harvard (https://dash.harvard.edu/server/api/core/bitstreams/7312037d-08ab-6bd4-e053-0100007fdf3b/content) note qu'un visage à yeux simplifiés est jugé plus étrange qu'un visage photoréaliste et qu'un dessin au trait.
- Une réplication (« Evaluating the replicability of the uncanny valley effect », 2018) et une revue récente jugent les preuves équivoques. Les URL exactes ne figurent pas dans les extraits.
- Autres pistes : https://www.scientificamerican.com/article/robot-cartoons-cute/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC6260244 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC4264966.

## 4. Contradictions et incertitudes

- **Pupilles de Cozmo.** Les extraits de presse disent que Cozmo avait des pupilles qui aidaient à lire le regard, puis qu'elles ont été retirées. L'étude de Kalegina trouve que l'absence de pupilles réduit sympathie et confiance, et que le visage à iris est le plus aimé. Deux sources distinctes, non réconciliées. Je ne tranche pas.
- **Licences non lues.** Les licences des forks esp32-eyes, ProtOpenSource et Monster M4sk ne sont pas lisibles dans les pages ouvertes. Celle de RoboEyes est GPL-3.0 d'après la page ; elle contraint la redistribution de code dérivé.
- **Dates.** Les pages RoboEyes, esp32-eyes, Adafruit et randym32 n'ont pas de date visible. La doc randym32 est un site communautaire, pas Anki. Les sources sur EMO, Mirokaï et Cozmo sont de la presse ou des blogs de revendeurs, pas des interviews de concepteurs.
- **Résolution de RoboEyes.** Elle n'est pas écrite sur la page ; seule l'interface `begin(largeur, hauteur)` est documentée.
- **Matrices 8x8.** Je n'ai pas trouvé de dépôt dédié aux yeux sur NeoMatrix 8x8 ou 16x16 ni à Otto/Zowi. Rien n'est vérifié sur ces deux points.
