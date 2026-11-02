| t (s) | quoi | action / cible | pourquoi — jauges |
|---|---|---|---|
|     0.0 | demarrage |  | sélecteur de jeu démarré (SIM-ONLY, domaine 43) |
|     1.7 | offre | objet titan_grise | poi_event enter titan_grise : offre objet, lubie +0.5 |
|     7.2 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.2 fat=0.0 pre=0.0 |
|    13.2 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|    17.2 | DÉCIDE | spontanee (little-move) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|    22.2 | fin | spontanee | séquence little-move terminée (animation_state '') |
|    26.3 | DÉCIDE | spontanee (little-neck) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|    31.3 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|    35.4 | DÉCIDE | spontanee (little-neck2) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|    40.4 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|    44.4 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|    49.4 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|    53.4 | DÉCIDE | spontanee (aurore) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|    59.6 | offre | objet nefs | poi_event enter nefs : offre objet, lubie +0.5 |
|    60.4 | fin | spontanee | séquence aurore terminée (animation_state '') |
|    60.9 | DÉCIDE | lubie nefs | offre:objet nefs 0.46 + lubie 0.43 ; gain 1 — enn=0.0 cur=0.0 lub=0.4 fat=0.0 pre=0.0 |
|    63.9 | ARRÊT (Didier) | nefs | lubie nefs non refusée en 3 s : stop demandé au régisseur |
|    67.0 | fin | lubie nefs | échéance de lubie |
|    71.0 | DÉCIDE | spontanee (michel-sardou) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.1 |
|    79.0 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|    83.1 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.2 |
|    91.1 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|    95.2 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.3 |
|   103.2 | fin | spontanee | séquence quand-on-voit terminée (animation_state '') |
|   107.2 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.5 |
|   113.2 | fin | spontanee | séquence quoi-ma-geule terminée (animation_state '') |
|   117.2 | DÉCIDE | spontanee (eye-left) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.6 |
|   119.2 | fin | spontanee | séquence eye-left terminée (animation_state '') |
|   125.7 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.65 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.7 |
|   131.7 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|   135.8 | DÉCIDE | spontanee (little-move) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.8 |
|   140.8 | fin | spontanee | séquence little-move terminée (animation_state '') |
|   143.2 | personne | p1 | nouvelle piste p1 (aucune piste depuis plus de 2 s) |
|   143.5 | DÉCIDE | regarder p1 | offre:personne p1 0.62 + curiosite 0.92 ; gain 1 — enn=0.0 cur=0.9 lub=0.0 fat=0.0 pre=0.9 |
|   144.7 | annulation | p1 | ignore p1 |
|   144.7 | CONSOLE (David) | ignore p1 | ignore p1 : 0 offre(s) tuée(s), rien vers elle 30 s |
|   148.7 | DÉCIDE | spontanee (little-neck) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.9 |
|   153.7 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|   157.2 | DÉCIDE | repartir | pression_route 1.00 ; gain 2 — enn=0.0 cur=0.0 lub=0.0 fat=0.3 pre=1.0 |
|   159.3 | fin | repartir | échéance de repartir |
|   165.6 | DÉCIDE | spontanee (little-neck2) | ennui 0.63 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   170.6 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|   171.8 | offre | objet elephant | poi_event enter elephant : offre objet, lubie +0.5 |
|   177.7 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.2 fat=0.0 pre=0.0 |
|   180.9 | offre | objet carrousel | poi_event enter carrousel : offre objet, lubie +0.5 |
|   182.7 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|   183.1 | DÉCIDE | lubie carrousel | offre:objet carrousel 0.21 + lubie 0.43 ; gain 1 — enn=0.0 cur=0.0 lub=0.4 fat=0.0 pre=0.0 |
|   186.2 | ARRÊT (Didier) | carrousel | lubie carrousel non refusée en 3 s : stop demandé au régisseur |
|   189.2 | fin | lubie carrousel | échéance de lubie |
|   193.2 | DÉCIDE | spontanee (aurore) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.1 |
|   200.2 | fin | spontanee | séquence aurore terminée (animation_state '') |
|   204.2 | DÉCIDE | spontanee (michel-sardou) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.2 |
|   212.2 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|   216.2 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.3 |
|   224.2 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|   228.3 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.5 |
|   233.2 | CONSOLE (David) | va_la table_basse | va là : table_basse |
|   233.6 | annulation |  | interrompu par aller_voir (ordre_macro) |
|   233.6 | DÉCIDE | aller_voir table_basse | console ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.3 pre=0.5 |
|   246.9 | offre | objet table_basse | poi_event enter table_basse : offre objet, lubie +0.5 |
|   249.7 | fin | aller_voir table_basse | route_goto_result arrived (arrived) |
|   251.7 | CONSOLE (David) | reviens | reviens : rejoindre la route |
|   252.2 | DÉCIDE | repartir | console ; gain 2 — enn=0.0 cur=0.0 lub=0.2 fat=0.3 pre=0.7 |
|   254.3 | fin | repartir | échéance de repartir |
|   258.4 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   264.4 | fin | spontanee | séquence quoi-ma-geule terminée (animation_state '') |
|   266.9 | offre | objet poster_bizarre | poi_event enter poster_bizarre : offre objet, lubie +0.5 |
|   271.5 | DÉCIDE | spontanee (eye-left) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.3 fat=0.0 pre=0.0 |
|   273.5 | fin | spontanee | séquence eye-left terminée (animation_state '') |
|   279.9 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.64 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   280.8 | offre | objet poubelle_tri | poi_event enter poubelle_tri : offre objet, lubie +0.5 |
|   285.9 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|   290.0 | DÉCIDE | spontanee (little-move) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   294.5 | offre | objet pigeon | poi_event enter pigeon : offre objet, lubie +0.5 |
|   295.0 | fin | spontanee | séquence little-move terminée (animation_state '') |
|   301.5 | DÉCIDE | spontanee (little-neck) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   306.5 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|   309.1 | offre | objet banc | poi_event enter banc : offre objet, lubie +0.5 |
|   309.6 | DÉCIDE | lubie banc | offre:objet banc 0.67 + lubie 0.48 ; gain 1 — enn=0.0 cur=0.0 lub=0.5 fat=0.0 pre=0.0 |
|   312.6 | ARRÊT (Didier) | banc | lubie banc non refusée en 3 s : stop demandé au régisseur |
|   315.6 | fin | lubie banc | échéance de lubie |
|   319.7 | DÉCIDE | spontanee (little-neck2) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.1 |
|   324.7 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|   328.7 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.2 |
|   333.7 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|   337.8 | DÉCIDE | spontanee (aurore) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.3 |
|   344.8 | fin | spontanee | séquence aurore terminée (animation_state '') |
|   345.1 | RELAIS GO |  | go de console relayé : verrou levé |
|   348.9 | DÉCIDE | spontanee (michel-sardou) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   350.2 | RELAIS GO |  | go de console relayé : verrou levé |
|   353.1 | RELAIS STOP |  | stop de console relayé sans arbitrage ; verrou jusqu'au go |
|   356.9 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|   361.0 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   369.0 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|   373.1 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   381.1 | fin | spontanee | séquence quand-on-voit terminée (animation_state '') |
|   383.2 | personne | p2 | nouvelle piste p2 (aucune piste depuis plus de 2 s) |
|   383.6 | DÉCIDE | regarder p2 | offre:personne p2 0.60 + curiosite 0.90 ; gain 1 — enn=0.0 cur=0.9 lub=0.0 fat=0.0 pre=0.0 |
|   386.6 | fin | regarder p2 | échéance de regarder |
|   390.7 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   396.7 | fin | spontanee | séquence quoi-ma-geule terminée (animation_state '') |
|   400.7 | DÉCIDE | spontanee (eye-left) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   402.7 | fin | spontanee | séquence eye-left terminée (animation_state '') |
|   409.2 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.65 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   413.2 | RELAIS GO |  | go de console relayé : verrou levé |
|   414.6 | offre | objet flaque | poi_event enter flaque : offre objet, lubie +0.5 |
|   415.2 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|   421.5 | DÉCIDE | spontanee (little-move) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   426.5 | fin | spontanee | séquence little-move terminée (animation_state '') |
|   429.9 | offre | objet terrasse | poi_event enter terrasse : offre objet, lubie +0.5 |
|   430.3 | DÉCIDE | lubie terrasse | offre:objet terrasse 0.68 + lubie 0.47 ; gain 1 — enn=0.0 cur=0.0 lub=0.5 fat=0.0 pre=0.0 |
|   433.4 | ARRÊT (Didier) | terrasse | lubie terrasse non refusée en 3 s : stop demandé au régisseur |
|   436.4 | fin | lubie terrasse | échéance de lubie |
|   440.5 | DÉCIDE | spontanee (little-neck) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.1 |
|   445.5 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|   449.5 | DÉCIDE | spontanee (little-neck2) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.2 |
|   454.5 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|   458.5 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.3 |
|   463.5 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|   467.6 | DÉCIDE | spontanee (aurore) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.4 |
|   474.6 | fin | spontanee | séquence aurore terminée (animation_state '') |
|   478.6 | DÉCIDE | spontanee (michel-sardou) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.5 |
|   486.6 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|   490.7 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.6 |
|   498.7 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|   502.8 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.8 |
|   503.1 | RELAIS STOP |  | stop de bouche relayé sans arbitrage ; verrou jusqu'au go |
|   510.8 | fin | spontanee | séquence quand-on-voit terminée (animation_state '') |
|   513.2 | RELAIS GO |  | go de bouche relayé : verrou levé |
|   514.8 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   519.3 | offre | objet grue_jaune | poi_event enter grue_jaune : offre objet, lubie +0.5 |
|   520.8 | fin | spontanee | séquence quoi-ma-geule terminée (animation_state '') |
|   526.2 | DÉCIDE | spontanee (eye-left) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   528.2 | fin | spontanee | séquence eye-left terminée (animation_state '') |
|   534.6 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.64 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   538.0 | offre | objet cale | poi_event enter cale : offre objet, lubie +0.5 |
|   540.6 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|   544.9 | DÉCIDE | spontanee (little-move) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   549.9 | fin | spontanee | séquence little-move terminée (animation_state '') |
|   554.0 | DÉCIDE | spontanee (little-neck) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   554.1 | offre | objet velo_cadenas | poi_event enter velo_cadenas : offre objet, lubie +0.5 |
|   559.0 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|   563.0 | DÉCIDE | spontanee (little-neck2) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   568.0 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|   569.5 | offre | objet panneau_info | poi_event enter panneau_info : offre objet, lubie +0.5 |
|   569.9 | DÉCIDE | lubie panneau_info | offre:objet panneau_info 0.68 + lubie 0.47 ; gain 1 — enn=0.0 cur=0.0 lub=0.5 fat=0.0 pre=0.0 |
|   572.9 | ARRÊT (Didier) | panneau_info | lubie panneau_info non refusée en 3 s : stop demandé au régisseur |
|   576.0 | fin | lubie panneau_info | échéance de lubie |
|   580.0 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.1 |
|   585.0 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|   589.0 | DÉCIDE | spontanee (aurore) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.2 |
|   596.0 | fin | spontanee | séquence aurore terminée (animation_state '') |
|   600.0 | DÉCIDE | spontanee (michel-sardou) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.3 |
|   608.0 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|   612.1 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.4 |
|   620.1 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|   624.2 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.6 |
|   632.2 | fin | spontanee | séquence quand-on-voit terminée (animation_state '') |
|   636.2 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.7 |
|   642.2 | fin | spontanee | séquence quoi-ma-geule terminée (animation_state '') |
|   646.3 | DÉCIDE | spontanee (eye-left) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.8 |
|   648.3 | fin | spontanee | séquence eye-left terminée (animation_state '') |
|   654.6 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.63 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.9 |
|   660.6 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|   663.4 | DÉCIDE | repartir | pression_route 1.00 ; gain 2 — enn=0.0 cur=0.0 lub=0.0 fat=0.3 pre=1.0 |
|   665.5 | fin | repartir | échéance de repartir |
|   671.9 | DÉCIDE | spontanee (little-move) | ennui 0.64 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   672.3 | offre | objet rails | poi_event enter rails : offre objet, lubie +0.5 |
|   676.9 | fin | spontanee | séquence little-move terminée (animation_state '') |
|   681.0 | DÉCIDE | spontanee (little-neck) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   686.0 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|   690.1 | DÉCIDE | spontanee (little-neck2) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   693.7 | offre | objet lampadaire | poi_event enter lampadaire : offre objet, lubie +0.5 |
|   695.1 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|   695.5 | DÉCIDE | lubie lampadaire | offre:objet lampadaire 0.32 + lubie 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.4 fat=0.0 pre=0.0 |
|   698.6 | ARRÊT (Didier) | lampadaire | lubie lampadaire non refusée en 3 s : stop demandé au régisseur |
|   701.5 | fin | lubie lampadaire | échéance de lubie |
|   705.6 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.1 |
|   710.6 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|   714.7 | DÉCIDE | spontanee (aurore) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.2 |
|   721.7 | fin | spontanee | séquence aurore terminée (animation_state '') |
|   725.8 | DÉCIDE | spontanee (michel-sardou) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.3 |
|   733.8 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|   737.8 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.4 |
|   745.8 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|   749.8 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.6 |
|   757.8 | fin | spontanee | séquence quand-on-voit terminée (animation_state '') |
|   761.9 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.7 |
|   767.9 | fin | spontanee | séquence quoi-ma-geule terminée (animation_state '') |
|   771.9 | DÉCIDE | spontanee (eye-left) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.8 |
|   773.9 | fin | spontanee | séquence eye-left terminée (animation_state '') |
|   780.3 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.64 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.9 |
|   786.3 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|   788.9 | DÉCIDE | repartir | pression_route 1.00 ; gain 2 — enn=0.0 cur=0.0 lub=0.0 fat=0.3 pre=1.0 |
|   790.9 | fin | repartir | échéance de repartir |
|   797.3 | DÉCIDE | spontanee (little-move) | ennui 0.64 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   799.0 | offre | objet anneaux | poi_event enter anneaux : offre objet, lubie +0.5 |
|   802.3 | fin | spontanee | séquence little-move terminée (animation_state '') |
|   806.4 | DÉCIDE | spontanee (little-neck) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   811.4 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|   815.5 | DÉCIDE | spontanee (little-neck2) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   817.1 | offre | objet bollard | poi_event enter bollard : offre objet, lubie +0.5 |
|   820.5 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|   824.6 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   829.6 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|   833.7 | DÉCIDE | spontanee (aurore) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   835.0 | offre | objet loire | poi_event enter loire : offre objet, lubie +0.5 |
|   840.7 | fin | spontanee | séquence aurore terminée (animation_state '') |
|   844.7 | DÉCIDE | spontanee (michel-sardou) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   852.7 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|   856.8 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   858.3 | offre | objet plot_chantier | poi_event enter plot_chantier : offre objet, lubie +0.5 |
|   864.8 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|   868.8 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   872.6 | offre | objet chien | poi_event enter chien : offre objet, lubie +0.5 |
|   876.8 | fin | spontanee | séquence quand-on-voit terminée (animation_state '') |
|   880.8 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.1 fat=0.0 pre=0.0 |
|   886.8 | fin | spontanee | séquence quoi-ma-geule terminée (animation_state '') |
|   890.8 | DÉCIDE | spontanee (eye-left) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
|   892.8 | fin | spontanee | séquence eye-left terminée (animation_state '') |
|   896.6 | offre | objet caisse_bois | poi_event enter caisse_bois : offre objet, lubie +0.5 |
|   897.1 | DÉCIDE | lubie caisse_bois | offre:objet caisse_bois 0.67 + lubie 0.47 ; gain 1 — enn=0.0 cur=0.0 lub=0.5 fat=0.0 pre=0.0 |
|   900.2 | ARRÊT (Didier) | caisse_bois | lubie caisse_bois non refusée en 3 s : stop demandé au régisseur |
|   903.1 | fin | lubie caisse_bois | échéance de lubie |
|   907.2 | DÉCIDE | spontanee (c-est-qui-le-con) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.1 |
|   913.2 | fin | spontanee | séquence c-est-qui-le-con terminée (animation_state '') |
|   917.3 | DÉCIDE | spontanee (little-move) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.2 |
|   922.3 | fin | spontanee | séquence little-move terminée (animation_state '') |
|   926.3 | DÉCIDE | spontanee (little-neck) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.3 |
|   931.3 | fin | spontanee | séquence little-neck terminée (animation_state '') |
|   935.4 | DÉCIDE | spontanee (little-neck2) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.4 |
|   940.4 | fin | spontanee | séquence little-neck2 terminée (animation_state '') |
|   944.5 | DÉCIDE | spontanee (neck-side-to-side) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.5 |
|   949.5 | fin | spontanee | séquence neck-side-to-side terminée (animation_state '') |
|   953.5 | DÉCIDE | spontanee (aurore) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.6 |
|   960.5 | fin | spontanee | séquence aurore terminée (animation_state '') |
|   964.5 | DÉCIDE | spontanee (michel-sardou) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.7 |
|   972.5 | fin | spontanee | séquence michel-sardou terminée (animation_state '') |
|   976.6 | DÉCIDE | spontanee (pour-votre-securite) | ennui 0.41 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.8 |
|   984.6 | fin | spontanee | séquence pour-votre-securite terminée (animation_state '') |
|   988.6 | DÉCIDE | spontanee (quand-on-voit) | ennui 0.40 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=1.0 |
|   996.6 | fin | spontanee | séquence quand-on-voit terminée (animation_state '') |
|   997.0 | DÉCIDE | repartir | pression_route 1.00 ; gain 2 — enn=0.0 cur=0.0 lub=0.0 fat=0.3 pre=1.0 |
|   999.1 | fin | repartir | échéance de repartir |
|  1005.4 | DÉCIDE | spontanee (quoi-ma-geule) | ennui 0.63 ; gain 1 — enn=0.0 cur=0.0 lub=0.0 fat=0.0 pre=0.0 |
