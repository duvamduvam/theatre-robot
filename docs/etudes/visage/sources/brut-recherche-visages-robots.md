<!-- Rapport brut d'un agent de recherche web, archivé tel que rendu le 22/11/2026. Matière première de etude-visage.md : non relu, non corrigé. -->

# Brut — recherche sur les visages de robot, émotions à basse résolution, rythmes du regard

# Rapport de collecte : visage de robot rendu, émotions à basse résolution, paramètres temporels

Date de consultation : 22/11/2026. Mandat ouvert, budget de 12 pages, atteint.

## 1. Couverture

**Pages réellement ouvertes et lues**
- Kalegina et al. 2018 : PDF, lu via l'outil Read, pages 5 à 9 du PDF (numérotées 100 à 104 dans les actes). Les pages 1 à 4 (abstract, étude 1 sur 157 robots) n'ont pas été lues.
- Feldmaier et al. (arXiv 1612.07303), version ar5iv.
- Mishra et al. (arXiv 2410.14337), version HTML.
- Page « Eye animation » de la documentation communautaire Vector (randym32).
- Microsoft Research, page de l'article d'Andrist 2014 (abstract seulement).
- TechCrunch, article de Brian Heater du 14/10/2016.
- The Robot Report, article de Steve Crowe du 27/06/2016.

**Pages en échec**
- Design News (HTTP 403) et Medium/Kickstarter (HTTP 403).
- PMC6291193 (Hömke et al., clignements) : blocage reCAPTCHA.
- Les PDF arXiv 2410.14337 et 1612.07303 étaient illisibles, d'où le passage par les versions HTML.

**Données issues seulement d'un résumé de moteur de recherche (page non ouverte, donc « non vérifié »)**
- Bentivoglio 1997 (taux de clignement) : lu sur le résumé de recherche de la page PubMed 9399231.
- Durées de clignement et étude Hömke 2018 / 2021.
- Durée des saccades (plusieurs fiches PMC et arXiv).
- Johnson 2013 (Nao, LED), Ghafurian 2022 (Miro), Reachy Mini 2026.
- Lèvres : Apple ICASSP 2023 et CVPR 2025.
- Citations Design News sur Cozmo.

**Non trouvé**
- Durées et fréquences chiffrées de détournement du regard (Andrist 2014 : seul l'abstract a été lu, sans chiffres).
- Étude comparant directement ouverture de bouche pilotée par l'amplitude et visèmes sur un personnage stylisé.
- Paramètres de clignement en parole vs écoute, mesurés spécifiquement.
- Étude de reconnaissance d'émotions sur des yeux en matrice LED 8x8.
- Taux de reconnaissance par émotion pour Cozmo.
- Étude de la forme de paupière sur des yeux abstraits.

## 2. Tableau de synthèse

| Fait | Valeur | Source | Statut |
|---|---|---|---|
| Kalegina 2018, étude 2 : 17 visages synthétiques, un trait changé à la fois par rapport au visage modal | N = 50 participants, 44 min en moyenne | PDF Kalegina | vérifié |
| Sans bouche, sans pupilles, avec paupières : significativement moins sympathiques | p<0,005 (** sur la figure 8 pour sans bouche et sans pupilles) | idem | vérifié |
| Sans bouche, sans pupilles : plus « machine » | significatif | idem | vérifié |
| Sourcils : jugés plus mûrs et plus intelligents | significatif pour « mûr » ; « le plus intelligent » affirmé dans le texte | idem | vérifié |
| Joues : plus féminin | ** | idem | vérifié |
| Joues, yeux rapprochés, cheveux, nez : plus enfantin | significatif | idem | vérifié |
| Aucun visage plus aimé que le visage de base | aucune différence significative positive | idem | vérifié |
| Reconnaissance émotions, visage complet vs région des yeux (humain, Furhat « Hayden » et « Titan ») | 64,4 % vs 51,3 % | Mishra et al. 2024 | vérifié |
| Taux de clignement : repos / conversation / lecture | 17 / 26 / 4,5 par minute | Bentivoglio 1997 | non vérifié (résumé de recherche) |
| Animations de Cozmo | 536 « selon le décompte d'Anki » | TechCrunch 2016 | vérifié |
| Durée de saccade | environ 21 + 2,2 ms/° ou 37 + 2,7 ms/° | fiches PMC/arXiv | non vérifié |

## 3. Sources

### Q1. Visages de robot rendus sur écran

**Kalegina, Schroeder, Allchin, Berlin, Cakmak (2018). « Characterizing the Design Space of Rendered Robot Faces », HRI '18, pp. 96-104, DOI 10.1145/3171221.3171286.**
URL : https://hcrlab.cs.washington.edu/assets/pdfs/2018/kalegina2018hri.pdf. Nature : article de recherche (PDF de l'éditeur de l'équipe), consulté le 22/11/2026. Lu : sections 4.3 à 7 seulement.

Étude 1 (jeu de 157 robots, 76 propriétés ; images statiques de 12 robots) :
- Les robots les plus amicaux sont Yumi, FURo-D, Buddy et Datou. Gongzi et Jibo sont les moins amicaux. Jibo n'a qu'un œil : « il n'y a pas grand-chose qui ressemble à un visage ».
- Plus sûrs : Datou et FURo-D. Le moins sûr est Gongzi, qualifié de « robot en colère » par 17 répondants sur 50.
- Corrélation réalisme / « ressemblance humaine » : R² = 0,75. Valerie est jugée significativement moins humaine que FURo-D (p<0,05), explication proposée : écran et orientation différents.
- Âge perçu : Buddy, Datou et Yumi sont les plus enfantins. Ce sont les trois seuls robots dessin animé avec yeux relativement détaillés et sourire. EMC et Valerie sont les plus mûrs.
- Effet « uncanny » : EMC et Valerie sont peu aimés, d'après les commentaires, même rendus à l'écran.

Étude 2 (17 visages dont le visage de base, N = 50, 68 % d'hommes, 22-64 ans). Test t apparié avec correction de Bonferroni sur 16 hypothèses par échelle :
- **Aucun visage n'est significativement plus sympathique** que le visage de base.
- **Sans bouche, sans pupilles, paupières, petits yeux, visage blanc, joues** : significativement moins appréciés. Les trois plus bas sont « sans bouche », « sans pupilles » et « paupières ».
- **Amicalité** : significativement plus basse pour sans bouche, sans pupilles et paupières.
- **Confiance** : plus basse pour sans bouche, sans pupilles et paupières. Le texte donne aussi comme moins dignes de confiance, par rapport au visage de base, les yeux rapprochés (« close eyes ») et les petits yeux.
- **Ressemblance humaine** : plus élevée pour oreilles, sourcils, cheveux, iris et nez. Plus « machine » pour sans bouche et sans pupilles. Les joues ne sont pas significatives.
- **Âge** : plus enfantin avec joues, yeux rapprochés, cheveux et nez. Plus mûr avec sourcils.
- **Genre** : joues, très féminin (**) ; visage blanc, deuxième plus féminin ; paupières et cheveux, plus masculin.
- **Intelligence** : plus élevée avec sourcils bas (près du haut de l'œil, pour éviter l'allure de visage de bébé). Moins élevée sans bouche, yeux rapprochés et joues.
- **Préférence globale** : le visage avec iris est le plus aimé, sans différence significative avec le visage de base.
- **Commentaires qualitatifs** : sans pupilles = « creepy », « dead eyes robot », « soulless robot ». Paupières = « sly », « smug » ; le texte attribue cela à un dessin où la paupière abaissée coupe le haut du cercle. Sans bouche = « surveillance ».
- **Choix de métier** : les visages les moins appréciés sont attribués à la sécurité.
- **Limites énoncées par les auteurs** : images statiques. Sans pupilles, le visage pourrait ne pas paraître « sans âme » s'il pouvait cligner. Jibo pourrait transmettre de l'émotion par le mouvement.

Contexte : parmi les 17 visages de l'étude 2, un seul (F16, visage blanc) a le fond blanc. Les yeux restent sur fond noir pour les autres.

**Mishra, Skantze, Hagoort, Verdonschot (2024, v2 mars 2025). « Perception of Emotions in Human and Robot Faces: Is the Eye Region Enough? »**
URL : https://arxiv.org/html/2410.14337. Nature : preprint arXiv, consulté le 22/11/2026. Le point est repris en Q2.

### Q2. Émotions à basse résolution, yeux seuls, Cozmo/Vector

**Mishra et al. 2024/2025** (même URL). Protocole : N = 305 (visage complet n = 153 ; yeux seuls n = 152), forcé sur 7 choix, vidéos muettes de 6-8 s, Furhat. Résultats :
- Visage complet : 64,4 % ; yeux seuls : 51,3 %. Étude antérieure à stimuli similaires : 49,1 %.
- Yeux seuls : reconnaissance significativement plus basse pour Titan (robot d'aspect mécanique) que pour l'humain (t = 7,020, p<0,001) et pour Hayden (t = 7,573, p<0,001).
- Visage complet meilleur que yeux seuls pour joie (t = 15,986), tristesse (t = 6,743) et neutre (t = 8,314), tous p<0,001. Pas de différence significative pour peur, colère, surprise, dégoût.
- Confusions : peur prise pour surprise, dégoût pris pour colère. Peur et dégoût mal reconnus dans les deux régions.
- Les pourcentages par émotion ne sont que dans la matrice de confusion (figure 3), non lisible ici.
- Limite : écran Furhat projeté, pas de LED basse résolution.

**Feldmaier, Marmat, Kuhn, Diepold. « Evaluation of a RGB-LED-based Emotion Display for Affective Agents » (arXiv 1612.07303, environ décembre 2016).**
URL : https://ar5iv.arxiv.org/html/1612.07303. Nature : preprint, consulté le 22/11/2026. Année déduite de l'identifiant arXiv.
- Affichage de 47 LED RGB sur un robot à deux roues. Combinaison couleur, évolution temporelle et mouvement.
- Pas de pourcentage de reconnaissance par émotion ; ce sont des notes moyennes 1 à 5 (N = 23) :

| Émotion | Éveil | Plaisir |
|---|---|---|
| Colère | 4,23 | 2,36 |
| Joie | 3,64 | 3,63 |
| Peur | 2,45 | 2,86 |
| Tristesse | 1,5 | 2,86 |

- Éveil bas (peur, tristesse) vs haut (colère, joie) : F[1,22] = 36,11, p<0,001. La valence (plaisir) est difficile à distinguer.
- La couleur n'est pas isolée comme facteur. Les auteurs notent que son interprétation est subjective et culturelle, et difficile à transmettre comparée à la fréquence de clignement.
- Ce n'est pas un affichage d'yeux.

**Non vérifié, simples résultats de recherche (aucune page ouverte)** :
- Johnson et al. 2013 (Springer, https://link.springer.com/doi/10.1007/s12369-013-0211-1) : Nao, motifs de LED autour des yeux, 12 motifs testés. Pourcentages non vus.
- Ghafurian et al. 2022 (https://uhra.herts.ac.uk/id/eprint/26122/1/Ghafurian_et_al_2022_Accepted_version.pdf) : Miro, étude vidéo, 116 participants, toutes les expressions reconnues au-dessus du hasard.
- Étude Epi : rouge fortement associé à la colère.
- Reachy Mini (https://arxiv.org/pdf/2605.12786), 2026 : exactitude globale 30,5 %.

**Cozmo / Anki (presse, pas de publication scientifique trouvée)**

*TechCrunch, Brian Heater, « Cozmo is an endearing little robot with growing up to do », 14/10/2016.* URL : https://techcrunch.com/?p=1401667. Presse, consulté le 22/11/2026.
- « The little robot was brought to life with 1.2 million lines of code creating 536 animations, by Anki's count » (citation partielle, selon l'outil).
- « The eyes are where Cozmo really shines. »
- Les yeux sont décrits comme « a few blue pixels on a black display ».

*The Robot Report, Steve Crowe, « Cozmo AI Robot Brings Wall-E to Life », 27/06/2016.* URL : https://www.therobotreport.com/cozmo-ai-robot-brings-wall-e-to-life/. Presse, consulté le 22/11/2026.
- Hanns Tappeiner (cofondateur et président d'Anki) : Cozmo avait des pupilles, qui montraient où il regardait, mais qui le rendaient trop humain. Citation : « He didn't feel robotic enough, so the animators changed the size and ratio of the eyes ».
- Tappeiner : « making eye contact with people very frequently is a very big deal ». À l'origine, Cozmo ne faisait contact visuel qu'au début d'un jeu, ce qui paraissait détaché.
- Tappeiner : outils sous Maya, « not to animate a movie, but an actual robot ».

*Documentation communautaire Vector (randym32), « Eye animation ».* URL : https://randym32.github.io/Anki.Vector.Documentation/tools/Eye%20animation.html. Tierce partie, pas Anki, consulté le 22/11/2026.
- Paramètres d'œil listés : sourcil, direction du regard, joues, ouverture (plissé, endormi), inclinaison de la tête, étirement/écrasement (écartement des yeux).
- Résolution d'écran : non indiquée sur la page.
- « A couple of dozen canned eye patterns » : inférence de l'auteur de la page, pas un compte documenté.
- Molly Wright (Digital Dream Labs), vidéo du 22/05/2020 : contrôle réduit à quatre axes (inquiet/curieux, en colère/content, fréquence de clignement lente/rapide, regard gauche/droite), avec interpolation entre préréglages. Rapporté par la page, vidéo non vue.

**Non vérifié (Design News, 403)** : https://www.designnews.com/testing-measurement/from-cozmo-to-vector-how-anki-designs-robots-with-emotional-intelligence. Seul le résumé de recherche dit : « hundreds of variations of something as small as the eyes ». Carlos Baena (ex-Pixar) est cité comme responsable des animations (sources : Designboom, Wikipedia, via recherche, pages non ouvertes). Aucun « Carl Schmidt » trouvé.

### Q3. Paramètres temporels

**Bentivoglio et al. (1997). « Analysis of blink rate patterns in normal subjects », Movement Disorders.**
URL : https://pubmed.ncbi.nlm.nih.gov/9399231/. **Non vérifié : page non ouverte, valeurs lues dans le résumé de recherche.**
- 150 volontaires sains (70 hommes, 80 femmes, âge moyen 35,9 ± 17,9 ans, plage 5-87). Trois tâches : repos, lecture, parole libre.
- Moyennes : 17 clignements/min au repos, 26 en conversation, 4,5 en lecture. Ordre le plus fréquent conversation > repos > lecture (101 sujets, 67,3 %).
- Pas de durée de clignement dans ces résultats.

**Hömke, Holler, Levinson (2017 et 2018 ; PLoS ONE 2018).** URLs : https://pmc.ncbi.nlm.nih.gov/articles/PMC6291193/ et https://www.mpi.nl/node/51648. **Non vérifié (reCAPTCHA).** Résumé de recherche :
- Dans un corpus de conversation, 410 ms sert de seuil entre les 25 % de clignements les plus longs d'un auditeur et le reste.
- En réalité virtuelle, l'avatar auditeur clignait « court » (208 ms) ou « long » (607 ms). Avec hochement et long clignement, les réponses des participants étaient en moyenne plus courtes d'environ 3 s. Les participants ne remarquaient pas la différence consciemment.
- PLoS ONE 2021 (https://doi.org/10.1371/journal.pone.0258322.g008) : selon le résumé, ce sont les mouvements faciaux complexes de la parole qui augmentent le clignement ; l'écoute et la simple vocalisation, non. **Non vérifié.**
- Durée moyenne de clignement : « 300-400 ms chez l'adulte » (résumé de recherche d'une page de vulgarisation, https://www.medicalnewstoday.com/articles/323963.php) ; « 100-150 ms » (Wikipédia, « Blink », citant un chercheur de l'UCL) et « 100-400 ms » (Harvard Database of Useful Biological Numbers). **Les valeurs se contredisent ; aucune n'a été vérifiée.**

**Saccades (non vérifié, fiches PMC/arXiv jamais ouvertes).**
- Ajustement linéaire durée/amplitude : 37 ms + 2,7 ms/° (revue citée, https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7166123/) ; 2,2 × amplitude + 21 ms (https://arxiv.org/pdf/1906.07183).
- Linéaire jusqu'à environ 80°, la plupart des saccades naturelles entre 15 et 20°.
- Microsaccades < 0,5° : 14 ms signalées.
- Exemple 10° : environ 50 ms, vitesse de pointe 300°/s (https://arxiv.org/pdf/2203.00488).

**Détournement du regard.** Andrist, Tan, Gleicher, Mutlu (2014), « Conversational Gaze Aversion for Humanlike Robots », HRI '14, pp. 25-32. URL : https://www.microsoft.com/en-us/research/?p=557574 (abstract lu, 22/11/2026).
- Robot NAO, 30 participants. Le système combine suivi de visage pour le regard mutuel, mouvement de tête au repos (« idle ») et détournements du regard voulus.
- Les participants percevaient les détournements comme volontaires. Le robot semblait plus réfléchi et mieux à même de gérer la prise de parole.
- Aucune durée ni fréquence chiffrée n'est donnée dans l'abstract. Non trouvé.
- IEEE Spectrum (https://spectrum.ieee.org/what-robot-behavior-makes-people-feel-uncomfortable) : un résultat inattendu sur le confort (pas d'augmentation observée avec NAO, alors que les personnages virtuels antérieurs en montraient une). Résumé de recherche, **non vérifié**.

**Synchro labiale (non vérifié, résumés de recherche).**
- Apple, « On the role of Lip Articulation in Visual Speech Perception » (ICASSP 2023), https://arxiv.org/abs/2203.10117 : les spectateurs préfèrent systématiquement une articulation des lèvres sur-articulée à une sous-articulée, sur des représentations en points de repère et des personnages incarnés.
- CVPR 2025, Chae-Yeon et al., « Perceptually Accurate 3D Talking Head Generation » (https://openaccess.thecvf.com/content/CVPR2025/papers/Chae-Yeon_Perceptually_Accurate_3D_Talking_Head_Generation_New_Definitions_Speech-Mesh_Representation_CVPR_2025_paper.pdf) : les participants préfèrent des mouvements de lèvres dont l'intensité correspond à la parole, même désynchronisés jusqu'au double du seuil, à des mouvements parfaitement synchronisés. Têtes 3D réalistes, pas stylisées.
- Aucune étude amplitude contre visèmes sur personnage stylisé trouvée.

## 4. Contradictions et incertitudes

- **Durée du clignement** : 100-150 ms (Wikipédia/UCL), 100-400 ms (Harvard), 300-400 ms (vulgarisation). Les trois proviennent de résumés de recherche, aucune de la littérature primaire ouverte.
- **Durée du clignement dans les études Hömke** : 208 ms (« court ») à 607 ms (« long ») sont des durées d'avatar manipulées, pas des durées humaines mesurées.
- **Kalegina, texte vs figure** : le texte dit « les paupières sont à l'origine d'une image suspecte » parce que la paupière coupe le cercle. Ce résultat porte sur un dessin particulier de paupière, pas sur toute paupière. Le visage « sourcils » est dit « le plus intelligent » dans le texte ; je n'ai pas relu les barres d'erreur au-delà de la figure 8.
- **Kalegina, images statiques** : l'étude porte sur des images fixes de robots à fond noir. Les auteurs signalent eux-mêmes que l'effet « sans pupilles » pourrait changer avec le clignement et le mouvement.
- **Mishra** : écran Furhat (rendu projeté), pas LED basse résolution. Les taux par émotion ne sont pas lus.
- **Aucune des sources lues** n'étudie des yeux en matrice 8x8 ou une bouche 24x16. Les sources les plus proches (Feldmaier : 47 LED, éveil seulement ; Johnson 2013 : LED autour des yeux de Nao) n'ont pas livré de taux de reconnaissance par émotion.
- **Anki** : le nombre « 536 animations » vient d'un article de presse de 2016, « selon le décompte d'Anki », sans publication d'Anki. Aucune publication scientifique d'Anki n'a été trouvée.
- **Pupilles** : Anki a retiré les pupilles de Cozmo (trop humain, selon Tappeiner dans The Robot Report). Kalegina 2018 montre le visage sans pupilles parmi les moins sympathiques et les moins dignes de confiance (images statiques, yeux de grande taille). Les deux faits sont rapportés, sans arbitrage.

Sources :
- [Kalegina et al. 2018 (PDF)](https://hcrlab.cs.washington.edu/assets/pdfs/2018/kalegina2018hri.pdf)
- [Mishra et al. 2024/2025](https://arxiv.org/html/2410.14337)
- [Feldmaier et al.](https://ar5iv.arxiv.org/html/1612.07303)
- [Documentation Vector, Eye animation](https://randym32.github.io/Anki.Vector.Documentation/tools/Eye%20animation.html)
- [TechCrunch, 14/10/2016](https://techcrunch.com/?p=1401667)
- [The Robot Report, 27/06/2016](https://www.therobotreport.com/cozmo-ai-robot-brings-wall-e-to-life/)
- [Andrist et al. 2014, Microsoft Research](https://www.microsoft.com/en-us/research/?p=557574)
- [Bentivoglio 1997, PubMed](https://pubmed.ncbi.nlm.nih.gov/9399231/)
- [Hömke et al., PMC6291193](https://pmc.ncbi.nlm.nih.gov/articles/PMC6291193/)
