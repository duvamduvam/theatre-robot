# Chantiers — tableau de bord

*Le point d'entrée du pilotage : statut, prochaine action et verrous de chaque
chantier. Créé le 2026-07-12 en dégraissant CLAUDE.md (qui était devenu un
journal de bord illisible).*

**Convention de tenue** (pour que ça ne se re-dégrade pas) :
- Chaque lot terminé met à jour **sa ligne** du tableau et **sa section** ici —
  pas CLAUDE.md (qui ne garde que les règles, commandes et priorités de tête).
- Le détail des décisions vit dans le **doc du chantier** (`etude-*.md`) ;
  ici, l'état et la prochaine action ; dans les **commits**, l'historique.
- Un chantier clos passe dans sa section avec la mention CLOS + date, et sort
  du tableau au bout d'un moment.

> ## 🔥 BLOCAGE ACTIF — le Pi 4 a fumé le 2026-09-12, cause NON identifiée
>
> David a vu fumer le **Pi 4 du robot** vers 22h45. La carte a été sortie du robot et
> réalimentée sur secteur indépendant ; **le reste du robot est hors tension**.
>
> **La carte passe tous les tests** (`throttled=0x0` y compris après 60 s à 4 cœurs
> pleins, 1800 MHz tenus, aucune erreur kernel, 29 min stables) — ce qui **innocente le
> chemin d'alimentation du SoC** mais n'explique pas la fumée. Suspects restants :
> périphérie (USB, Ethernet, **connecteur GPIO / 5 V**, donc l'interface robot).
>
> **Tant que la brûlure n'est pas localisée et le rail 5 V du robot mesuré
> (`firmware/pico_test_5v`), ne rien réalimenter et ne recoupler aucun Pi.** Cela gèle de
> fait tout travail sur le robot réel (chantiers 0 et 1).
>
> Post-mortem complet, relevés et pièges de diagnostic : **`incidents/2026-09-12-fumee-rpi4.md`**
> (⚠️ y lire le piège `fake-hwclock` : sans RTC, `uptime`, `who -b` et `docker ps` se
> contredisent après une coupure — seul `/proc/uptime` dit vrai).

## Vue d'ensemble

| Chantier | Statut | Prochaine action | Verrou / condition |
|---|---|---|---|
| **0. Conversation (chat_node V2)** | code COMPLET, validé sim ; jamais testé matériel ; **gate « source audio vivante » FAIT le 30/08** (dernier verrou de code levé — 198 tests vision) ; ⚠️ **NOUVEAU VERROU, ÉLECTRIQUE : ronflement secteur du Pi 5** (plancher −21,5 dBFS, l'entrée écrête ; un humain à 3 m est 11 dB SOUS le bruit) | **1) alimenter le Pi 5 sur batterie** (source confirmée le 30/08) — **EN COURS depuis le 12/09 : 2× Mean Well SD-50B-5 voulus (24 V batterie → 5 V 10 A) — ⛔ LIVRÉS EN SD-50C-24 (36-72 V → 24 V, constaté le 04/10) : NE PAS CÂBLER, retourner et recommander en B-5 ; en attendant, le `SD-50B-5` du stock (`t0532`, étiquette à relire) peut servir au Pi 5**, support imprimé à dessiner, cotes et pièges dans `docs/hardware/alim-5v-pi.md` ; **les 2 sont affectés (1 par Pi) → prévoir un 3e en rechange APRÈS le test, mais lire d'abord l'étiquette du `SD-50B-5` du stock (`t0532`)** — §8 ; ⚠️ le bénéfice n'existe que **chargeur secteur débranché** — puis **2)** protocole physique complet + les 2 cas que seul le réel tranche : David au HF pendant l'écoute, humain à 3 m toujours entendu | **ronflement d'abord — rien d'audio n'est mesurable avant** ; rebuild image ARM vision ; Pi 5 sur alim 27 W |
| **Suivi de personne (roues)** | ÉTUDE ÉCRITE le 14/09 — [`etude-suivi-personne.md`](etude-suivi-personne.md), **le seul chantier qui n'en avait pas** (construit d'un bloc le 11/07, 20 lignes de statut, hypothèses jamais écrites). Découverte centrale : **l'occlusion PARTIELLE est le mode dangereux** — la totale coupe la détection et le deadman arrête, la partielle laisse la détection vivante avec une boîte rétrécie, donc `follow_control` conclut « il s'éloigne » et **AVANCE**. Biais structurel : plus il y a de monde, plus Didier avance. Chiffré : `target_height=0,55` ⇒ **2,7 m** de distance de confort (jamais écrit avant) | **S0** : limite de vraisemblance ASYMÉTRIQUE (§4) — la hauteur qui monte passe libre, celle qui chute est bridée au plausible (−56 %/s max pour un humain à 1,5 m/s ; une occlusion fait des centaines de %/s : un ordre de grandeur les sépare). Logique pure, zéro capteur, zéro CPU | S0-S1 au banc, robot immobilisé. ⚠️ Rempart, **pas** une perception : ça empêche d'accélérer vers un obstacle invisible, ça ne le rend pas visible. Le suivi au sol en public reste suspendu à la perception d'obstacle (lidar, S3) et au `direction_sign` roues jamais tranché en réel |
| **Identification de l'acteur (regard)** | ÉTUDE ÉCRITE le 14/09 — [`etude-identification-acteur.md`](etude-identification-acteur.md), **rien d'acté, à valider par David**. Né du constat que `TargetPicker` choisit sur `score × aire` : en rue, Didier fixe **la personne la plus proche**, pas David — et ce ratage a lieu **déjà**, avec le gaze seul, roues à l'arrêt. Faciale et marqueurs **éliminés par la géométrie** (IPD 8,4 px à 3 m ; il faudrait un marqueur d'~1 m à 5 m). ⭐ La question de David « un moyen depuis la télécommande ? » a relégué les 4 pistes matérielles : le gant est **déjà** une carte RP2040 et `IHR` est un bouton câblé à commande **vide** | **I0** : bouton `IHR` → topic `designate` (une ligne de config, rien à fabriquer, a de la valeur seul) ; puis I1 signature de couleur en module pur | **aucun** pour I0-I2 (banc, robot immobilisé) ; l'essai réel attend le retour du robot. ⚠️ Ne débloque **PAS** les roues en rue : l'identité rend le comportement juste, pas sûr (occlusion → la boîte rétrécit → il ACCÉLÈRE vers l'obstacle) |
| **1. Test scénique au sol** | À FAIRE — première fois que cmd_vel roule au sol ; ⚠️ **lire d'abord « DANGER ACTIF — les 2 boutons du dos »** : le bouton « stop » ÉTEINT LE PI, donc **provoque un emballement** au lieu d'arrêter ; ⚠️ **03/09 : le robot est EN PIÈCES** (disque d'odométrie déposé, pignons/jantes/chaîne démontés, panneaux de torse retirés — `robot-embarque.md` §1.1) | **remonter et revérifier d'abord**, puis étiqueter les 2 boutons, puis séquence de spectacle complète, télécommande en main | — (c'est LUI le verrou des autres) ; **quelqu'un à portée de la coupure générale** |
| ⚠️ **Boutons du dos (stop/reset)** | **DANGER ACTIF découvert 30/08** — « stop » = `shutdown -h`, « reset » = `reboot` : aucun n'arrête les roues, les deux tuent le rempart logiciel | **étiqueter physiquement (coût nul)** puis réaffecter D16 → vrai `e_stop` (le verrou `twist_mux.yaml:39` n'attend qu'un publieur), D20 → extinction sur appui long | chemin roues ⇒ spec + protocole caméra + revue Opus |
| Interface web / télé-présence | W0 + console + W3-sim FAITS ; bringup réel actif (sans drive) ; ⚠️ **13/09 : un seul RJ45 branchable sur le RUT955** (support trop serré) → la 2ᵉ Pi n'est pas câblable, contrairement à ce qu'affirme `overview.md` | W1 : source e_stop + coup-de-poing sans fil | roues web réel ⟸ test scénique (1) + protocole caméra dédié ; **2 Pi en RJ45 ⟸ nouveau support routeur** (mesures d'atelier) |
| Télédiagnostic par agent IA | plan décidé ; étape 1 « trousse d'atelier » FAITE | étape 2 : boîte noire rosbag + bouton START | étape 3 ⟸ RAM du Pi 4 à relever (`ssh r 'cat /proc/meminfo'`) |
| Conversation en déambulation (intention + contenu) | plan DÉCIDÉ (grillé 12/07) ; D0 outillage + personas commutables FAITS 13/07 ; **13/09 : PREMIÈRE VRAIE CONVERSATION D'ATELIER** (banc PC, ReSpeaker du robot) — 4 défauts corrigés le jour même (redites = répliques stockées en `role=system` donc rejouées comme consignes ; bouche qui continuait après la réplique ; bips à −7 dBFS ; aucune observabilité → vumètre web `diag_port`) | ⚠️ **écrire `docs/etude-interaction.md`** (demandé par David) — le plan de juillet ne parle QUE du passant, **David n'y existe pas** alors qu'il est déjà une source de parole (ventriloquie HF) ; en attente de ses réponses dramaturgie | D1+ ⟸ protocole physique chat_node V2 (0) ; D6 ⟸ verrous roues ; ⚠️ 3 manques de fond relevés le 13/09 : sessions par rencontre §5.2 JAMAIS implémentées (une seule session par démarrage de node), `{"name"}` demandé au LLM mais jamais consommé, `EnergyVad` intenable en rue |
| **Rythme de la déambulation (chemin ↔ arrêts, jeux)** | GRILLÉ le 31/10 avec David — [`etude-interaction.md` §10](etude-interaction.md) : « le but n'est pas l'arrivée mais le chemin » ; arrêts par David (stop, 2 expressions secrètes relance/arrêt, hors dépôt) ou par Didier (1 lubie / 2 min, réclamée, refusable) ; relance autonome après 90 s de silence, seulement après SES arrêts ; 1er jeu « Va voir le… » (aller, pivoter face à l'objet, demi-tour si dépassé — SIM-ONLY) | §10.7 dans l'ordre : écoute garde « stop » (en revue 31/10) → mots secrets → lubies bornées → relance 90 s → « Va voir » sans pivot puis avec | pivot/demi-tour = chemin roues (sim + revue) ; réel ⟸ odométrie |
| **Niveaux de réflexion (parole réflexe ↔ caméra, mouvement, instructions)** | ÉTUDE ÉCRITE le 23/10 — [`etude-niveaux-reflexion.md`](etude-niveaux-reflexion.md), **4 décisions de David le 23/10 (§10)** : tour spontané OUI, images vers le cloud OUI, mots-clés pour l'urgence SEULEMENT, deux niveaux plutôt qu'un gros modèle (Sonnet écarté pour la parole). Sa remarque — « il faut que l'histoire avance » — fait de la boucle 2 le **gardien du fil dramatique** (§3 bis) : elle fusionne avec I0 (état de mission). Question de David : parler du tac au tac ET analyser caméra/mouvement/instructions. Réponse : 3 boucles qui ne s'attendent jamais (réflexes déterministes / parole Haiku 5.5 réflexion coupée / réflexion avec image, asynchrone) reliées par un **tableau de situation** latché et périmé, relu à chaque tour comme `extra_system`. Mesuré : image = +1 s au 1er mot, réflexion = 3-6 s ; Sonnet 5.5 `low` aussi rapide que Haiku mais réflexion non coupable. ⚠️ découverte : le « stop » vocal passe par le LLM en FIN de réplique (~5-7 s) | **CODE FAIT le 23/10** (vision 640f270, spec [`spec-metteur-en-scene.md`](spec-metteur-en-scene.md)) : arrêt d'urgence vocal avant LLM, tableau de situation, `reflection_node` (mission I0, Haiku 5.5 / Sonnet 5.5 sur demande), tours spontanés, clé `reflechir` ; un seul interrupteur `CHAT_REFLEXION` (vrai par défaut sur le banc PC). Banc réel + test de fumée ROS OK ; revue adversariale (1 bloquant : un tour spontané pouvait lever l'arrêt vocal par « go ») corrigée. **STT distant FAIT le 23/10** (vision f048938 : Voxtral via OpenRouter, repli auto sur whisper local — demandé par David : « être compris correctement »). **Suite = séance de répétition avec David** (qualité de jeu, fréquence des relances, sens gauche/droite de la caméra, **STT sur sa voix NORMALE** — le banc n'avait que sa voix de ventriloque) | aucun pour la sim ; rien ne lève les verrous roues |
| Voix de Didier (ventriloquie ↔ synthèse) | OUVERT 26/08 ; cadre + état de l'art posés, **arbitrage artistique suspendu** ; **26/08 : « l'effet robot » de prod est un ÉCRÊTEUR DUR à ±3000 (−20,8 dBFS) — facteur de crête 13,5 dB → 3,1 dB, confirmé à l'oreille** (étude §2) **V3 palier minimal FAIT 26/08** (5,2 min en personnage au SM58, pupitre `essais/voix/enregistre.py`) ; **CLONAGE FAIT le jour même** (accès HF gated OK, 3 états de voix bancés : réf 15 s int8 = RTF 0,43 et 6/6 au contrôle ASR ; réf 60 s moins stable ; ⚠️ le clonage coûte ×1,6 en RTF → Pi probablement > temps réel, à mesurer) ; **montage alternance David-réel/machine-clonée PRÊT** (`sorties/alternance-david-machine.wav`) | ✅ **VERDICT DAVID 26/08 : « oui, c'est bien ma voix »** (prouvé sur un texte INÉDIT de 99 s) → branche synthèse clonée VIABLE. **Mais : c'est sa voix NORMALE, pas la ventriloquie** — F0 clone 136,8 Hz vs référence 134,5 Hz, le clone est FIDÈLE, c'est la PRISE qui n'était pas en ventriloquie → **V3 bis : réenregistrer la référence en voix de personnage** (la ventriloquie est une technique vocale, donc elle appartient au corpus — pas un filtre à mettre en aval : §3 corrigé). Volume inégal = dynamique naturelle reproduite (clone 13,8 dB d'écart, l'humain 16,2) → remède AVAL `nivelle.py` (13,8 → 1,4 dB), à intégrer à la diffusion vision | **V3 bis (référence en ventriloquie, 60 s)**, puis **V0** banc octaver et V0b-Pi (avec état CLONÉ, pas Estelle). ⚠️ **03/09 : l'« octaver » est en fait un `TC HELICON` à molette `GENDER`** (référence lue, modèle exact non lisible — `robot-embarque.md` §1.3) : un processeur de FORMANTS, pas un doubleur d'octave, ce que le §3 de l'étude suppose. Préalables gratuits au banc V0 : lire le modèle et **photographier la position de toutes les molettes AVANT d'y toucher** (l'appareil est posé en vrac, non fixé) | V0/V0b en atelier ; **Kyutai sur ARM = inconnue qui décide de la forme du chantier** ; ne pas lancer l'enregistrement long avant V0b ; ⚠️ **le seuil d'écrêtage est ABSOLU : changer de TTS change la voix en silence** — relever le niveau d'entrée de l'effet à chaque bascule |
| Suivi de personne (roues) | validé sim 5/5, déployé, **SIM-ONLY** | — (attend ses verrous) | test scénique (1) PUIS protocole caméra (`direction_sign` inconnu) |
| Gaze V1 + arbitrage actionneurs | validé RÉEL 12/07 ; arbitrage déployé sur les 2 Pi | vérif visuelle : gaze ON pendant une séquence (la tête ne doit plus trembler) | — |
| Odométrie des roues (encodeurs) | **01/11 : indicateur de batterie proposé sur la carte (étude §6 ter, rien d'acté) — branche A0 = Bluetooth du BMS lu par le Pi (zéro matériel, à essayer en premier ; Victron écarté : muet hors secteur), A = Daly par 2 PC817 (lecture seule, liste blanche), branche B = tension côté puissance ; vérifs de David ce soir (cellules en série, réf BMS + port UART libre, masse du 12 V)** ; **disque IMPRIMÉ et monté le 19/08** (plaqué contre la couronne, rondelles — vigilances fluage/faux-rond au README plans) ; support capteurs : **v4 MORTE AU MONTAGE 19/08** (le palier occupe le volume), **direction v5 = pince sur la vis de suspension du palier** (double écrou, hors chemin d'effort) ; capteurs LJ12A3 reçus ; **02/09 : les 2 disques sont GARNIS de leurs 10 cibles** — montage conforme (sens, noyage, écrous non nylstop) **SAUF le métal : têtes marquées `A2-70` = INOX**, le piège du §« quatrième piège » | ~~① mesurer la portée~~ **FAIT 05/10 : inox ~1 mm, acier ~3 mm → rééquiper les 20 cibles en M8×16 tête H PLEINE acier zingué** (obligatoire) ; **①bis mesurer le faux-rond axial du disque** → décide l'entrefer (~1,5 mm si faux-rond ≤ 0,5 mm, sinon capteur M18 avant d'imprimer le berceau v5 — **2 × LJ18A3-8-Z/BX REÇUS 17/10 → berceau v5.1 REDESSINÉ en M18 le 17/10** (`patte-capteur.scad`, rendus `berceau-v5.1-m18-*`), disque 10 cibles CONSERVÉ sur décision de David malgré 3 gardes-fous du disque tombés en M18 (passés en avertissement) → **test banc AVANT impression** : `Z/BX` lu + LED externe (NPN), portée sur tête M8 acier (fixe `ENTREFER`, provisoire 4), LED qui s'éteint franchement entre deux têtes sur un tour (sinon 7 cibles) ; cotes catalogue du M18 à confirmer au pied à coulisse (bloc F de MESURES.md : corps 68, écrous minces 4 / 24 sur plats)) ; puis **berceau v5 DESSINÉ 20/08** (palier KP004, bloc E rempli) + **firmware Pico ÉCRIT et testé 20/08** (`firmware/pico_odometry/`, 35 tests) → valider `E4_VIS_DISQUE` (hyp. 25 mm, réglet — **disques en main, c'est le moment**) + vue de montage, **imprimer x2** ; côté élec : **décisions 02/09 actées ET plan de plaque REDESSINÉ/REVÉRIFIÉ** (RP2040-Zero, 1 JST-XH 4 pts/roue, 12 V dispo en bas, fixation sur le coffre des alims) → plan d'atelier `docs/pictures/odometrie/2026-09-02-implantation-stripboard-rp2040-zero.png` (plaque 26x29, ~66x74 mm), reste à **souder** (67 coupures, 10 straps) puis banc d'établi. **26/09 : « une carte du commerce ne fait-elle pas déjà ça ? » INSTRUIT** (étude §6 bis, 5 axes de recherche) → **rien à acheter** : le besoin (capteur industriel 12 V NPN + isolation galvanique + quadrature basse résolution) tombe dans un trou entre la robotique de loisir (jamais isolée, 12 V/3 A) et l'automatisme (196-336 €, souvent PNP, Modbus). Seule piste gardée en réserve pour l'étape 5 : **RoboClaw 2x30A, 152,50 € TTC Botland**, qui remplacerait le Cytron ET fermerait la boucle de vitesse en matériel — mais c'est le CHEMIN ROUES, et ses entrées encodeur ne sont pas isolées (les optos restent). **Le plan de la carte ne change pas.** La piste RoboClaw est instruite à part dans [`etude-driver-roues-asservi.md`](etude-driver-roues-asservi.md) — **ouverte le 26/09** : 1 RoboClaw 2x30A (152,50 € TTC) remplacerait les **2** Cytron MDS40B (88,30 € pièce, donc 176,60 €), supprimerait PCA9685 + ISO1540 + I²C du chemin roues, et apporterait **timeout et E-Stop MATÉRIELS** (la 1ʳᵉ réponse au « si `wheels_node` meurt, rien n'arrête les roues »). ⚠️ **Deux verrous** : (a) **le dimensionnement est devenu un arbitrage de PRIX** — le 2x30A à 152,50 € ne pèse que **60 g** pour 30/60 A (moins que l'existant : objection de David, fondée, et le 2x45A ne pèse que 2 g de plus), tandis que le **2x60A** a un **dissipateur d'usine, 300 g, 60/120 A** (au-dessus de l'existant), est **plus compact que les 2 Cytron réunies**, et coûte **250,86 € TTC franco** (RobotShop EU, relevé par David) — soit **~74 € de plus** que les 176,60 € du remplacement à l'identique, pas le double ; (b) **aucun driver ROS 2 n'a de plugin Gazebo**, donc « simulation d'abord » n'a pas de réponse évidente. ⚠️ L'USB **peut** piloter (Pololu) mais le fabricant le déconseille en milieu bruité (« *will likely disconnect and not automatically recover* »). 🔴 **COMPARATIF SÉRIEUX FAIT le 26/09 (§9 bis) → RECOMMANDATION RÉVISÉE : NE PAS CHANGER MAINTENANT.** Trois arguments pro-RoboClaw sont TOMBÉS à la lecture du manuel Cytron : (a) le **ronflement 60 Hz n'existe pas** — le Cytron FILTRE le PWM en tension et commute à 16 kHz régénérés (correction reportée dans `etude-chemin-commande-roues.md` §2.1) ; (b) le **PID 300 Hz est inutilisable au régime de jeu** (~10 impulsions/s à 0,2 m/s, soit ~29 cycles PID sur une mesure périmée) ; (c) le **Cytron tient MIEUX la chaleur** (dérating progressif, 35 A encore à >110 °C, ne coupe jamais — le RoboClaw tombe à 0 A à 100 °C). Et il est moins cher : **75 € pièce** chez Opencircuit (NL), donc **150 € les deux contre 250,86 €**. Ce qui RESTE au RoboClaw : timeout + E-Stop matériels, télémétrie (le Cytron est en **écriture seule**, aucun retour), encombrement (258 cm³ contre ~844), odométrie intégrée. ⚠️ **Découverte indépendante de toute décision** : le mode PWM du Cytron FILTRE l'entrée en tension et **aucune plage de fréquence n'est documentée** — à 60 Hz l'ondulation résiduelle pourrait faire trembler la consigne (ce qui expliquerait le `FREQUENCY = 500` mort dans `wheels.py`). **À écouter au test scénique.** ⭐ **La SEULE action à faire maintenant : au routage de la bande sécurité, sortir la bascule 74HC74 sur un CAVALIER 2 positions** (`OE` du PCA9685 **ou** connecteur E-Stop externe) — coût : un cavalier et deux pastilles ; bénéfice : la carte reste valable quel que soit le driver choisi plus tard. Pour mémoire (§6 quinquies) : architecture A en cible, C pour le banc, SI le RoboClaw est retenu un jour. 3 architectures instruites (§6 bis) : A = Packet Serial TTL (le plus propre, sort l'I²C du chemin roues, mais **oblige à refondre la chaîne de sécurité**) · B = USB seul (risque d'arrêt en plein jeu) · **C = mode RC piloté par le PCA9685 existant + USB en LECTURE SEULE** — 🟢 **chaîne de sécurité INCHANGÉE**, `RC Timeout` **100 ms matériel** (vs 400 ms logiciel), `Safe Start`, bridage de vitesse en dur, et les défauts §2.1 (ronflement 60 Hz) et §2.2 (DIR détourné) tombent d'eux-mêmes ; coût : ~164 niveaux de consigne au lieu de 4096, et `MCU Mode` OBLIGATOIRE (sinon auto-calibration de la plage en cours de spectacle). **Verrou de C à lever en 10 min sur banc : les compteurs d'encodeurs sont-ils lisibles par USB en mode RC ?** ⚠️ Et en mode RC **il n'y a PAS d'entrée E-Stop** (réservée au mode série) : l'arrêt passe par la coupure du `OE` → `RC Timeout`, donc `Idle Mode = Braking` devient une **condition de sécurité**, pas un réglage de confort. Brochage : odométrie sur **`EN1`/`EN2`** (pas sur S1-S5), **12 V capteurs toujours depuis le rail du robot** (le RoboClaw ne sort que du 5 V), carte optos **inchangée** sauf le rappel qui vise le 5 V au lieu du 3,3 V — et le RP2040-Zero devient inutile. Une **batterie logique séparée** est exigée sous forte charge dans tous les cas. **Pourquoi A en cible** : l'USB est un port d'ATELIER selon le concepteur (« *should be used for configuration and debugging* ») — or en mode RC c'est le SEUL chemin qui remonte les compteurs, donc un USB intermittent = **odométrie intermittente**, soit exactement ce qu'on cherche à obtenir. A porte commande ET lecture sur un seul lien fiable, et son E-Stop `S3 (Latching)` **freine** là où le `OE` coupe le PWM. ⭐ **Le moment est le bon et ne se représentera pas : la bande sécurité est PLACÉE MAIS PAS ROUTÉE** — changer le point d'accrochage maintenant coûte un dessin, après gravure il coûte une carte. Variante de la carte optos (RP2040 supprimé, rappel vers le 5 V, sortie vers EN1/EN2) proposée en §6 quater — **conditionnelle, le plan officiel ne change pas**. **Prochaine action gratuite : pince ampèremétrique sur un fil moteur PENDANT le test scénique au sol** — le courant réel des moteurs n'a jamais été mesuré | ⚠️ **03/09 : un disque garni de ses 10 cibles est DÉPOSÉ AU SOL** (`robot-embarque.md` §1.2, repère `t0169` — motif inconnu, à demander à David ; s'il est déposé pour ①, la pièce est en main, autant mesurer maintenant). ⚠️ **La transmission est par CHAÎNE à rouleaux + pignon** (jamais documentée ; une courroie crantée est vue ailleurs) → **compter les dents pignon moteur ET pignon roue** : sans le rapport de réduction, la conversion cibles → mètres est fausse. **cibles inox = ~1 mm mesuré (05/10) → remplacement acier ; acier = ~3 mm seulement → entrefer 2,5 à revoir** ; E4 hypothèse ; `PAL_BOSS_R` (21) non coté ; ~~12 V dispo en bas ?~~ OUI (02/09) ; sens de comptage à MESURER (protocole caméra) ; restent `ROUE_D` (hyp. 250) et entraxe roues (C2) |
| Chaîne de sécurité matérielle (main-carrier) | schéma révisé 14/07 ; **contrat figé en tests sur la branche `chaine-securite`** ; ⚠️ **le robot tourne sur STRIPBOARD DIY — watchdog, `OE` et coup-de-poing PHYSIQUEMENT INEXISTANTS** : aujourd'hui, si `wheels_node` meurt, **rien n'arrête les roues** (seul arrêt = coupure générale à la main) ; **chiffré le 26/09** — [`hardware/cout-cartes.md`](hardware/cout-cartes.md) : ≈ 110-150 € les 2 PCB nus (les 2 cartes dépassent 100×100, donc hors tarif forfaitaire) + ≈ 81 € de composants vérifiés, une quarantaine de références restant non chiffrées ; **26/09 : étude du passage sous 100×100** — [`hardware/etude-cartes-100x100.md`](hardware/etude-cartes-100x100.md) : 128,6 cm² d'encombrement réel (ombres des modules comprises) → **2 cartes** (sans le 2ᵉ PCA9685 ni la cascade PCF, 56/55 % d'occupation) ou **3 cartes** (tout gardé) ; nappe inter-cartes fail-safe net par net ; PCB 41 + ~80 $ → 20 $ ; **TRANCHÉ par David le 26/09 : 3 cartes (tout gardé), EMPILÉES — ordre M bas / L milieu / P haut, +5V des modules via L, R10 sur M** (étude §8) ; **BASCULE FAITE le 27/09** (dépôt `didier/pcb`, `kicad/`) : **les 4 cartes 100×100 sont prêtes à fabriquer** — ERC 0, DRC 0/0, silk 0, pile cohérente (`check_stack.py`), Gerber dans `kicad/fab/*.zip` ; P posée **tournée de 180°** (erreur d'alignement des nappes trouvée et corrigée), PTC de tête de nappe ajoutés par la revue de sûreté — [`etude-cartes-100x100.md`](hardware/etude-cartes-100x100.md) §10 | avant commande : cotes RCA + transfo, brochage G5V-2, entraxe HW-171, choix des 2 PTC, courant de la bobine 40 A ; puis devis réel (déposer les zip) ; **geste gratuit : mesurer au réglet le pas d'un bornier vert du stock** | carte non fabriquée ; pas de devis ferme tant que le routage n'est pas fini (les calculateurs exigent des gerbers) ; si empilé : hauteur du PCA9685 enfiché et filetage des entretoises à mesurer |
| **Architecture des actionneurs (bras, cou, yeux)** | **ANALYSE FAITE le 26/09** — [`etude-architecture-actionneurs.md`](etude-architecture-actionneurs.md). Verdict : l'architecture **est sérieuse** (rampe au `dt` réel, anti-spam I²C, deadman servo, 38 tests) — elle n'est pas à refaire, elle est **à instrumenter**. 3 faiblesses : boucle **ouverte de bout en bout** (aucune lecture de position/courant/couple/T°, donc **aucune détection de blocage** sur des bras annoncés à 380 kg·cm ≈ 37 N·m, près du public) ; 6 nœuds écrivent sur la même puce avec une **adresse 0x40 implicite** ; **aucune limite d'angle par servo**. | ✅ **① FAIT le 26/09 — et ça a révélé un ACTIF DORMANT** : `ASME-MR` = **Magnetic Encoding Series**, servo **POSITIONNEL** 360° à **capteur magnétique 12 bits** qui sait *« return angle information »*. La doc disait « continuous-rotation » : FAUX, corrigé dans `overview.md`. ⭐ **Donc le retour de position EXISTE DÉJÀ dans le matériel** — la boucle ouverte n'est pas une fatalité, c'est un câble qu'on n'a pas branché. **A′ = brancher et lire ce retour** (0 € si le câble est là) devient prioritaire sur l'achat d'un INA219 : consigne vs position réelle = détection de blocage gratuite. ⚠️ 3 points à lever **sur le robot, donc après le dégel** : modèle exact (`ASME-MR` ou `ASME-MRB` ?), le 2ᵉ connecteur visible sur la photo est-il raccordé, et quel protocole. ② adresses I²C explicites (2 lignes, **avant** la séparation 0x40/0x41) ③ limites d'angle par servo + test ④ mesure du courant servos (INA219 ~3 €) = le seul point de **sécurité** | aucun — ①②③ se font robot en pièces et ne touchent pas au chemin roues |
| Chemin de commande roues (PWM moteur) | **INSTRUIT et TRANCHÉ 30/08** — le Pico ne commandera pas ; le gain visé est déjà couvert par la chaîne de sécurité | réserver + documenter 4 GPIO sur la carte odométrie (gratuit) ; adresses I²C explicites | ⟸ routage de la bande sécurité (le vrai verrou) |
| **Télécommande USB RP2040** | ÉTUDE ÉCRITE le 14/09 — [`etude-telecommande-usb.md`](etude-telecommande-usb.md), rien de fabriqué. Née de 4 photos d'atelier d'un module joystick **`HW-504`** (réf lue ; ⚠️ `R5` NON peuplée ⇒ `SW` flottant ⇒ pull-up interne obligatoire ; ⚠️ la broche marquée `+5V` doit être alimentée en **3,3 V**, sinon les ADC du RP2040 prennent 5 V pour un max absolu de 3,63 V). Destination **double** : télécommande Pi 4 **et** simulation, **tout en série USB CDC**. ⚠️ **2 décisions RENVERSÉES le soir même du 14/09, par David** : (1) le **HID est écarté** — il ne servait qu'à piloter la sim sans code, ne servait PAS le menu, et portait la seule inconnue bloquante (aucun exemple officiel de HID+CDC sur RP2040, endpoints non chiffrés) ; (2) **le menu ne vit PAS dans le firmware mais CÔTÉ HÔTE** — « contrôler tous les éléments » implique un catalogue (animations, visages, lumières) qui vit côté robot ; le RP2040 devient un **terminal générique** qui affiche ce qu'on lui envoie, donc son firmware ne change plus quand le spectacle change. **OLED identifié** par photo : I²C 4 broches, pont d'adresse `0x78`/`0x7A` ⇒ 0x3C/0x3D. Carte : **XIAO RP2040** (USB-C, 4 ADC, en stock) — mais **11 broches seulement**, décompte sans marge. ⭐ **Le seul chantier qui avance sans le robot** (banc + sim), donc utile pendant le gel du Pi 4 **T1 FAIT le 14/09** (`302ef28`) : `firmware/remote_usb/remote_protocol.py` + `test_remote_protocol.py`, **678 tests** verts. Revue adversariale passée, 4 défauts réels corrigés — dont **le CRC que rien ne figeait** : muter le polynôme laissait les 63 tests verts (tout était recalculé avec la fonction testée), or le décodeur hôte s'écrira dans `dadou_control_ros`, **dépôt frère sans code partagé**, d'après le README → une dérive aurait refusé 100 % des trames, CI verte. Vecteurs gravés, vérifié par mutation. ⭐ **Le même trou était dans `test_odom_protocol.py`, protocole DÉJÀ EN SERVICE** — vecteur gravé là aussi. **Suite = T2** : `code.py`/`boot.py` (broches, ADC, pull-up du `SW`, émission 50 Hz) — demande la carte en main et le joystick câblé à l'air | **aucun** — le chantier n'a plus d'inconnue bloquante depuis l'abandon du HID. ⚠️ Le jour où il commande des roues RÉELLES il entre dans le chemin roues ⇒ sim + protocole caméra + revue Opus. **Reste ouvert** : `SW` du joystick câblé ou non (il coûte la dernière voie analogique), SSD1306 vs SH1106 (au 1ᵉʳ affichage), dalle OLED peut-être décollée, nb exact de XIAO |
| **Architecture globale multi-dépôts (cœur / lib / appareils / sim)** | **ÉTAPE 2 DÉCIDÉE le 01/11 au soir** (`/grill-me`, 9 axes, chaque arbitrage de David sur faits vérifiés) — [`etude-architecture-globale.md`](etude-architecture-globale.md) §5 ; **lots L0-L5 posés (§6)**. Décisions, à NE PAS re-trancher : `dadou_web` SUPPRIMÉ ; sono + DoubleLights **réécrits depuis le gabarit** (sono archivée sur GitHub public `dadou_sceno_ros`, audios hors dépôt) ; cible 2028+ = Didier autonomes partageant un état → seule garantie prise = **un nom par robot** (namespace, topics absolus interdits) ; **le robot publie, on édite À TRAVERS le robot** (la télécommande était l'éditeur : 8 modules écrivent du JSON, 71 copies divergentes, **~29 séquences n'existent QUE sur la télécommande**) ; **mono-dépôt `dadou`** (historiques conservés par `git subtree`), **génération 2 partout** + package `dadou_contrats`, rangement **`packages/` à plat + `machines/<hôte>/`**, noms `didier_*` / `<appareil>_*` / `dadou_*` ; télécommande **réécrite de zéro** (entrées/cœur/affichage), **Twist direct dès sa naissance** (sim + protocole caméra avant service, ancienne = repli documenté) ; sim = pilote matériel interchangeable + état publié rendu page scène, **un conteneur par machine, mêmes Dockerfiles que l'ARM** ; déploiement = rsync du sous-ensemble + sha publié, Ansible épuré (6 rôles orphelins + Jenkins/Sonar/`ci` supprimés) ; doc = vivante / `docs/etudes/` gelées / README-contrat par package, un seul CLAUDE.md ; CI = tests + build colcon + séance sim de fumée. David : valide chaque étape, tests physiques, compose en parallèle, ne code pas | **L0 Sauvegardes + squelette** : pousser 90 commits cœur / 31 vision / 3 télécommande, commiter contrôle (12 fichiers) / hardrive (3) / DEVICE_WORKSPACE (13), **rapatrier les ~29 séquences** dans `data/`, créer `dadou` par subtree, arborescence §5.5 posée, sim verte comme avant → **David valide l'arborescence SUR PIÈCE** | la sim ne doit jamais s'arrêter de marcher ; chemin roues intouché sauf L4 (protocole caméra) ; anciens dépôts archivés sur GitHub, jamais supprimés ; absorbe « UI télécommande » (ligne suivante) et « diagnostic utils partagé » |
| **Autonomie et improvisation (pourquoi et quand Didier agit)** | **ÉTUDE ÉCRITE le 01/11 soir** — [`etude-autonomie-improvisation.md`](etude-autonomie-improvisation.md), 4 collectes web + relecture adversariale (7 bloquants repris), **rien d'acté**. Demande de David : robot « plus autonome, qui prend ses décisions, qui improvise », **mouvement autonome = clé minimum**, cadre = destination + obstacles-partenaires, télécommande **macro seulement**, travail = timing (pourquoi/quand). **DÉCIDÉ en séance : capteur d'obstacle (« on le prendra »)**. Verdict de l'étude : dans tous les cas lus (2007-2025) l'humain garde le *quoi jouer*, l'autonomie qui marche est étroite (timing, regard) ; stratégie proposée **B = répertoire composé par David + sélecteur sans LLM (BT + score) + boucle 2 en metteur en scène + corps sûr** ; MAIS **3 préalables de sécurité manquent avant tout mouvement autonome** : source e-stop (W1 — le deadman ne protège plus quand c'est le robot qui émet), signal de vie de la télécommande (timeout 0,5 s → les prios basses reprennent la main), odométrie (bornes en m/s invérifiables, plancher PWM) ; 15/29 séquences rapatriées ont une piste roues → l'enveloppe doit filtrer TOUTES les entrées autonomes avant twist_mux | **David tranche les 10 questions du §8** (priorité vs 0-1 et L0-L5, W1/odométrie préalables, signal de vie, lidar vs ToF, rouvrir le 31/10 ?, un seul décideur du corps, py_trees/utility/hybride, L4 Twist vs console macro, désigner « là/lui », re-trancher le 13/09) → puis lots A-préalables → A0 corps sûr → A+ timing/regard → A1 sélecteur → A2 perception → A3 → A4 rue | chemin roues touché (A0) = sim + protocole caméra étendu d'une épreuve d'obstacle ; robot en pièces, cmd_vel jamais roulé au sol ; contredit « Didier n'est pas un robot autonome » (13/09) et frotte L4 (Twist) — à trancher, pas à glisser |
| **UI télécommande sans X11 (remplace tkinter)** | ⤴ **ABSORBÉ le 01/11 dans « Architecture globale »** (on ne tranche pas l'UI avant l'architecture). PROPOSÉ le 01/11, **rien d'acté ni de codé**. Revue du code tkinter de `dadou_control_ros` : les entrées (gamepad, gants, sliders) sont lues dans les `after()` Tk et la boucle Tk est pilotée par un timer ROS 10 Hz → **les roues dépendent de l'écran** (un `sleep`/chargement GUI fige la conduite ; deadman 400 ms rattrape). Architecture proposée, tout sur le Pi télécommande : `controller_inputs_node` headless (RP2040, gamepad, gants, sliders → ROS) + `controller_core` Python pur (menus/playlist/MODE, menu inerte si homme-mort tenu) + afficheurs : HDMI/DSI **tactile** en pygame SDL2 kmsdrm sans X11, LCD SPI 2,4" (boutons), vue web plus tard. **Objectif ajouté le 01/11 : afficher la télécommande dans la page scène** (`robot_web/static/scene.html`) → frontière headless/GUI = **topics ROS** : le cœur publie `remote/ui_state` (JSON du menu, latché) et écoute `remote/ui_action` ; écran du Pi et panneau web sont deux afficheurs du même état, le web_bridge n'ajoute que ces 2 topics à sa whitelist ; en sim le cœur tourne dans le conteneur sim (menu testable sans matériel). **Règle : une action d'origine web ne touche jamais les roues via le menu** (MODE, vitesse route) — roues web = `cmd_vel_web` prio 50 uniquement. Web SUR l'écran du Pi écarté (cage + Chromium plus lourd que X11+Tk). **Précisé le 01/11 : la Pi Zero 2 W est pour un DEUXIÈME GANT** (petit écran discret, moins d'info), le Pi 4 reste la télécommande principale → un cœur par appareil, espaces de noms séparés (`remote/…`, `glove2/…`) ; « moins d'info » = filtrage dans l'afficheur, pas dans le cœur. **Afficheur : essai comparatif pygame (SDL2 kmsdrm) vs WPE WebKit `cog` (navigateur DRM sans X11) décidé** — critères : RAM mesurée et réactivité du toucher sur la vraie carte ; si `cog` tient sur la Zero 2 W il gagne (une seule interface HTML pour le Pi et la page scène) | **Mesure RAM FAITE le 01/11** sur `control` (Pi 4, Pi OS trixie, 192.168.1.25, alias `c`) : conteneur télécommande **113 Mo PSS** (controller_node 99 Mo RSS avec tkinter) ; dockerd+containerd ~150 Mo RSS ; bureau labwc+Xwayland+panneau+portails **~490 Mo RSS** (tkinter s'affiche via Xwayland, pas de X11 pur) ; total 552/3795 Mo. ⚠️ `docker stats` affiche 0 o : comptabilité mémoire cgroup coupée sur le noyau Pi → sommer le PSS des PID de `docker top`. **Zero 2 W du gant installée le 01/11** (hôte `gr`, 192.168.1.123, Pi OS Lite trixie 64 bits) : **415 Mo visibles, 144 Mo utilisés au repos** (l'estimation de 80 Mo était fausse). Verdict : bureau IMPOSSIBLE ; sans bureau AVEC Docker ≈ 407/415 Mo (à la limite, sans marge) ; sans Docker ≈ 257 Mo → **Docker sur le gant penche vers NON**, à confirmer en mesurant le vrai node du gant. Schémas du plan : [`architecture-ui-telecommande.html`](architecture-ui-telecommande.html). Suite : lot 1 = extraction du node d'entrées | lot 1 = **chemin roues** → sim puis protocole caméra ; gant Zero 2 W : 512 Mo pour Docker+ROS 2 non mesuré, **Wi-Fi 2,4 GHz seul** (salle pleine = bande saturée, à tester en salle), 1 seul USB OTG (hub) ; pygame kmsdrm DANS Docker non vérifié |
| **Danse en cadence (chanson + gestes à la con)** | ÉTUDE ÉCRITE le 01/10 — [`etude-danse.md`](etude-danse.md), **rien d'acté**. Verdict : faisable, le lecteur de séquences fait déjà 80 % du travail ; ce qui manque = grille de beats précalculée (librosa : 3 chansons du corpus mesurées, 96-161 BPM, écart-type inter-beat 16-25 ms), écriture des figures **en temps musicaux** + compilateur vers le JSON existant (zéro changement embarqué), et **deux retards à mesurer** (démarrage du son — `playsound` dans un `Process`, aucun horodatage — et parcours des servos). ⚠️ Bras ASME annoncés **1 s/60° à 12 V** : le tempo se joue au cou, aux yeux et au visage, les bras marquent la mesure | **D0** outillage PC (`extract_beats.py`, `compile_dance.py`, tests à valeurs gravées, WAV) puis **D1** première danse en sim avec banc de calage automatique (`check-dance-timing.py`, vrai code) — les deux **sans le robot** | D2 (mesure du retard son, gigue, tension rail servo) ⟸ dégel du Pi 4 ; D4 déambulation ⟸ test scénique (1) ; ⚠️ **le cas visé est « danser EN SUIVANT »** (précisé par David le soir même, étude §7 bis) : le mux ne superpose pas, la cadence des roues se compose DANS `follow_control` (modulation bornée ≤ suivi, freeze sur le temps fort), l'odométrie calibre le retard roues mais ne résout que la MESURE (80-300 ms/impulsion), pas le temps → hérite de TOUS les verrous du suivi au sol ; une piste `wheels` de séquence ne sert qu'aux danses à l'arrêt |
| **Répétition simulée (rue + bugs + casque)** | ÉTUDE ÉCRITE le 07/10 — [`etude-repetition-simulee.md`](etude-repetition-simulee.md), **rien d'acté**. Demande de David : s'entraîner dans une ville simulée où Didier le suit, où les bugs tombent et où commence « la mauvaise foi », au casque Bluetooth. Verdict : les deux tiers existent (banc PC du 13/09 = vrai `chat_node` + vrai `person_tracker` + casque BT via PipeWire, corps Gazebo) ; manquent **une rue** (`stage.sdf` est un plancher nu), **un David virtuel vu par la vraie perception** (le tracker ne lit que `/dev/video0` → param `camera_topic`), **un régisseur de pannes** sim-only à deux canaux (technique : kill/drop/delay/bruit à l'EXTÉRIEUR du code de prod ; joué : instruction persona) dont David ignore le tirage, et le **persona mauvaise foi**. C'est le verrou de sortie de la phase C d'`etude-interaction.md` (« une déambulation se joue de bout en bout en sim avec David »). ⚠️ La sim entraîne le DUO et le réflexe « panne = jeu », pas le triangle avec de vrais passants (un passant LLM serait complaisant : 54 % des saluts de robot restent sans réponse en vrai) **VARIANTE RETENUE le 07/10 (§12)** : Didier **chemine seul** dans la rue (suiveur d'itinéraire sim-only sur le créneau prio 20 du mux, suivi de personne OFF), la perception regarde la **webcam réelle** (David devant l'écran), points d'intérêt → événements → instruction de jeu. R0/avatar passent en OPTION. **R1 CODE FAIT le 07/10** (`robot_rehearsal` + `rue.sdf` + vérité terrain gz, 30 tests gravés) ; **vérifié en sim** : trajet complet 0 → 59,6 m en 150 s, 9 POI enter/exit dans l'ordre, `finished` ; **protocole `validate-rehearsal-route.sh` : 6/6 le 2026-10-08** (départ 8,2 m en 20 s, télécommande prio 100 écrase, POI enter/exit, arrivée x = 59,5, « finished », zéro franc < 700 ms après `route off`) ; ⚠️ découverte : `/odom` DiffDrive ne voit pas une téléportation → le cheminement lit `/ground_truth/odom`. **profil fader télécommande FAIT le 08/10** (`dadou_control_ros` : `SLIDERS_PROFILE=repetition`, 13 tests gravés) → **R1 CLOS**. **R2 canal technique FAIT le 07-08/10** : régisseur (`director`, scénario YAML validé + graine → timeline déterministe, exclusion par cible, abort), relais de pannes sur `cmd_vel_follow` (drop/delay/freeze/zero, **chien de garde** : régisseur muet > 1 s → passant), pause/kill en liste blanche (jamais la chaîne de sécurité), `kill` de route_driver = respawn 5 s + `route on` (le reboot-prétexte), journal JSONL (`robot/diagnostic/journal.py`, format boîte noire) ; **V-R2 8/8** (chien de garde vérifié en gelant le régisseur pendant un `zero` : Didier repart < 2,5 s). 60 tests gravés R1+R2. **Revue adversariale FAITE le 08/10** : 4 invariants faux corrigés le jour même (relance après kill conditionnée à l'état route + à l'ordre de David, gardien SIGCONT détaché pour les pauses, durée max dans le relais, t_wall strict au journal) + garde-fou `ROS_DOMAIN_ID=43` dans les 3 nodes (refus vérifié en conteneur) + 9 trous de mutation fermés ; **V-R2 rejoué 8/8 après corrections**. **Démo du 08/10** (séance complète regardée en direct par David dans la fenêtre Gazebo, `docs/pictures/repetition-simulee/`) : a révélé un **vrai défaut** — la relance après reboot reposait sur un `route on` unique, perdu pendant la découverte DDS → corrigé en **boucle fermée** (état latché `route_state` publié par route_driver, ré-essai 1 s, `route_reenable` journalisé seulement à la confirmation ; vu en sim : 2 messages perdus, le 3e passe, Didier finit la rue). Outils de débrief embryonnaires : `conf/scripts/rehearsal/` (capture caméra + trajectoire, carte de séance). **R3 « Chantiers » FAIT le 14/10** (monde Nefs → Titan grise, 20 bugs + 30 lubies, persona mauvaisefoi, page scène `/scene`, V-R3 technique — détail §Répétition simulée ci-dessous). **I1 « mouvement à la voix » CODE FAIT le 22/10** (§13.11 : clé `marche` go/stop → `rehearsal/chat_move` → régisseur seul, par `route`/`route_speed`, jamais contre un `off` de David — cause latchée `route_state_cause` publiée par route_driver ; revue adversariale corrigée le 22/10 ; tests gravés + mutations dans les deux dépôts) — **à vérifier en sim**. **Corps qui suit la conversation (31/10-01/11, `spec-aller-voir.md`)** : M1 « aller voir » (manœuvre bornée), M2 gestes chiffrés (regarder tête PROD, tourner/avancer sim), **M3 « faire le tour de X » (01/11 : orbite sur la géométrie de collision SDF, 13 POI avec tour, vérifié en sim : tour complet des poubelles 14,9 m)**, **M4 tâche en cours (01/11 : une demande humaine enchaîne ses gestes d'elle-même jusqu'à « c'est fini » ; vérifié en sim)**. Bouche = GPT-6.1 Sol à l'essai (banc des modèles : `etude-niveaux-reflexion.md` §11). Reste : suites de gestes plus riches, image jointe à la bouche, prompt (vieux bloc GPT photo/nom). Suite = **V-R3 séance** avec David (+ vérif I1), puis I0, vitesse au **fader du boîtier déjà en stock** (profil « répétition » de la télécommande) + **vraie télécommande en `ROS_DOMAIN_ID=43` [DÉCIDÉ 07/10]** — ⚠️ avant le retour du robot : bandeau SIM/RÉEL sur la GUI de la télécommande, bascule explicite (une télécommande oubliée en 42 atteindrait le vrai Didier), R2 régisseur technique, R3 personnage (dépend d'I0), R4 enregistrement/débrief, R5 passant (optionnel) | **aucun côté robot** — tout se fait pendant le gel du Pi 4, domaine 43, zéro code de pannes dans le bringup. arbitrages §8 (2 tranchés le 07/10) ; voix §10 sans re-trancher V0 ; **§11 architecture + tests** : carte prod/sim-only (`robot_health` latché, presets voix, persona, journal = boîte noire → PROD ; `robot_rehearsal` autonome → SIM-ONLY, test anti-fuite), tests à valeurs gravées + mutation, vérifs V-R0…R3 rejouables |
| Pistes en veille | — | voir §Pistes en veille | — |

## 0. Conversation — protocole physique chat_node V2

Le code est COMPLET et commité (nuit du 10 au 11/07 : ~15 commits sur les
3 dépôts, validé en sim — bras+yeux bougent sur l'animation « parle », vu par
David dans Gazebo). Côté vision : chat_node (`chat_enabled:=true`, défaut
false), pipeline VAD→whisper→OpenRouter→piper→mixette, didascalies/émotions →
topics face+animation. Côté robot : fix MODE (dadou_utils_ros 5aefdf1 — le
mode random servo était mort depuis sept. 2025), expression « parle »,
séquence didier/parle.json.

### Banc PC mis en place le 2026-09-13 (Didier immobilisé, en attendant les SD-50B-5 — commande livrée en C-24, à refaire)

Perception + conversation avec le VRAI code du Pi 5 sur le PC (webcam +
Scarlett, conteneur vision x86 : `dadou_vision_ros/conf/docker/x86/`, le
Dockerfile-arm réutilisé tel quel), corps = Didier de Gazebo (domaine 43),
aperçu web du visage LED sur :8766 (nouveau `face_sim_node`, FACE=true —
les didascalies deviennent enfin visibles en sim). Mode d'emploi complet :
`docs/operations.md` §Banc PC. **Ce banc ne remplace PAS le protocole
physique** (seuils audio absolus, propres à chaque machine) : il sert à
travailler contenu et comportement (personas, didascalies, suivi) pendant
l'immobilisation. Découverte au passage : le build compose x86 de vision
casse sur le symlink `dadou_utils_ros` (« too many links ») → script
`build-x86.sh` (tar -h déréférencé), le Pi n'est pas concerné (rsync
matérialise le dossier).

### ⚠️ VERROU ÉLECTRIQUE découvert le 30/08 — le ronflement vient de l'alim du Pi 5

Constaté par David (« il y a un souffle super fort »), mesuré dans la foulée avec
le code de prod, et **tranché par David en trente secondes** : Pi 5 basculé sur
**batterie** → le bruit disparaît. C'était le test 2 que
`hardware/overview.md` §Audio chain noise prescrivait ; il est **positif**.

Ce n'était d'ailleurs pas un souffle mais un **ronflement secteur** : raie
dominante à **150 Hz** (3ᵉ harmonique du 50 Hz), rapport aigus/graves 0,04.

Pourquoi ça bloque le chantier, et pas seulement pour le confort :
plancher à **−21,5 dBFS** avec l'entrée qui **écrête**, alors qu'un humain à 3 m
mesure −32,4 → **la personne venue parler est 11 dB SOUS le bruit**. Whisper n'a
rien à transcrire, le seuil de la VAD (calibré UNE fois au démarrage) s'accroche
au ronflement, et le gate du 30/08 bloquerait 100 % des trames. **Le gate n'est
pas en cause : c'est l'état électrique.**

⚠️ **Piège de méthode payé au passage : couper n'est pas débrancher.** Mettre la
sortie du Pi en sourdine dans ALSA n'a retiré que **4,5 dB** — ce qui innocentait
presque le Pi, à tort. Une sourdine coupe le *signal* ; elle laisse la **masse**
passer par le blindage du câble, et c'est là que tout se joue.

**Suite** : Pi 5 sur la batterie du robot (DC-DC 5 V/5 A, il veut 27 W) — c'est
de toute façon l'état d'exploitation d'un robot mobile ; transformateur
d'isolement 1:1 pour les séances d'établi qui restent sur secteur ; et **jamais**
supprimer la terre de l'ampli pour tuer le ronflement. Détail, chiffres et
étage de gain à corriger ensuite : `hardware/overview.md` §Audio chain noise.

### 30/08, 23h25 — PREMIÈRE exécution du gate sur matériel : écourtée par l'alim

Déploiement complet fait (rsync Ansible groupe `vision`, sentinelle
`vision/CHANGE`, rebuild colcon vérifié pièce par pièce dans l'install space),
`chat_node` lancé à la main, ampli au niveau de jeu. **Le gate tourne.**

Ce qu'on a appris, et qui est acquis :

- **il fonctionne et il est LISIBLE** — les transitions journalisées donnent
  niveau, crête et cause à chaque bascule. L'exigence d'observabilité du §10.7
  a payé dès la première minute : sans elle, ce test ne disait rien ;
- il bloque sur la cause `niveau`, avec des valeurs **2963 à 4067** pour un
  seuil à 2800 : il *frôle*, il ne dépasse pas franchement ;
- les crêtes (8 000 à 16 000) restent **loin** de l'écrêtage (32 000) : la sono
  ne sature pas, contrairement à l'état sur secteur ;
- les tours finissent en `STT inexploitable : ''`.

⚠️ **INCONCLUSIF sur la seule question qui comptait**, et il faut le dire :
impossible de trancher entre « le gate bloque la voix de David » (le prix
documenté du seuil, §10.4) et « le plancher ampli allumé est trop haut ». La
mesure de silence qui aurait départagé les deux n'a pas pu être prise — **le
Pi 5 s'est éteint avant**.

### ⚠️ Les deux contraintes d'alimentation se CONTREDISENT — c'est ça, le vrai verrou

- **sur secteur** : ronflement à −21,5 dBFS, entrée qui écrête → le micro est
  inutilisable, la conversation est impossible ;
- **sur la batterie utilisée le 30/08** : ronflement réglé (−45,8 dBFS, 24 dB
  gagnés), mais le Pi 5 **tombe sous la charge** whisper + piper. Le drapeau
  `throttled=0x50000` (sous-tension déjà survenue) avait été relevé **avant**
  le test : l'avertissement était là, la chute l'a confirmé.

Il faut donc une source qui satisfasse les deux à la fois : **27 W tenus en
charge ET aucune référence secteur**. Deux pistes, dans cet ordre —
**DC-DC 5 V/5 A depuis la batterie du robot** (c'est l'état d'exploitation
normal d'un robot mobile, et ça règle le sujet définitivement), ou à défaut une
**batterie USB-C PD annoncée ≥ 30 W** pour les essais d'établi.

⚠️ Corollaire de méthode : **toute mesure audio doit être refaite dans l'état
d'alimentation définitif.** Les seuils du gate sont absolus ; ils ne veulent
rien dire tant que la source d'alimentation bouge.

**À faire sur le vrai matériel** : rebuild image ARM vision (voix piper +
whisper préchargés), Pi 5 avec ALIM 27 W (crash constaté sur USB-C PC),
sentinelles robot/change + vision/CHANGE, dérouler une conversation complète
au casque, vérifier gestes/bouche/arrêts propres (caméra à l'appui). Vérifier
aussi le gate d'arbitrage en conversation réelle (voir chantier gaze).

## 1. Test scénique en conditions réelles

Roues AU SOL, télécommande physique en main (boutons, slider, gants), une
séquence de spectacle complète — **première fois que le mode cmd_vel roule au
sol**. Vérifier aussi le sens de rotation gauche/droite (le protocole roues
hors sol ne l'a validé qu'en marche avant symétrique).

C'est le verrou de : roues web au réel (chantier web), suivi de personne au
réel.

### À TESTER — les deux boutons ajoutés le 2026-09-14

Code écrit et testé au banc (`designate` côté vision, `follow` côté
télécommande). **Rien n'a jamais été pressé sur le vrai gant.** Trois étages,
dans cet ordre — le premier ne touche aucun actionneur et peut se faire dès le
retour du robot.

**Étage 1 — « c'est moi » (IHR), roues à l'arrêt, zéro risque**

1. **La trame passe-t-elle ?** `ros2 topic echo designate` pendant que David
   appuie. ⚠️ C'est LE point à vérifier en premier : `PUBLISHER_LIST` est un
   filtre **silencieux** — un bouton mal câblé ne fait rien, sans erreur.
   Vérifier aussi que le gant physique envoie bien la touche `m` (IHR).
2. **IHR ne fait rien d'autre.** Le libellé "Inclino" était mort, mais
   c'est à confirmer sur le gant 9DOF réel : aucun effet parasite à l'appui.
3. **Le cas qui motive tout** : quelqu'un se met **plus près** que David.
   Sans appui, Didier doit regarder l'intrus (comportement actuel) ; David
   appuie, le regard passe sur lui **et y reste**. C'est la contre-preuve.
4. **Sortie et retour au même endroit** → ré-acquisition sans rien toucher.
5. **Retour par un autre côté** → PAS de ré-acquisition (regard au centre),
   David ré-appuie. C'est le comportement voulu, pas une panne.
6. **Pendant une séquence d'animation** : l'arbitrage doit toujours primer
   (le gaze se tait), l'appui ne doit pas le contourner.
7. **« Regard libre » (MODE, gamepad)** : relâche la désignation, Didier
   revient au regard libre (la personne la plus proche). ⚠️ **Ergonomie à
   arbitrer** : on arme au GANT et on relâche à la MANETTE, faute de second
   bouton libre sur le gant. À juger en jeu — si c'est bancal, il faudra
   libérer une touche du gant en déplaçant une autre fonction.

**Étage 2 — « suis-moi » (START/SELECT), roues HORS SOL, protocole caméra**

8. START → le suivi s'active (log `follow ON`) ; SELECT → **arrêt franc**,
   quel que soit l'état précédent. Tester SELECT alors que le suivi est déjà
   off (doit être inoffensif).
9. **`direction_sign` du suiveur** : jamais tranché en réel — même dette que
   le gaze avant le 12/07. David à droite ⇒ le robot doit tourner **vers** lui.
10. La télécommande écrase le suivi en plein mouvement (priorité 100 > 20),
    et le suivi ne reprend qu'au relâchement.
11. Kill de la chaîne en plein suivi → arrêt local (deadman 400 ms).

**Étage 3 — au sol, avec le reste de cette section**

12. Suivi réel, David marchant, **personne d'autre dans la pièce**.
13. **Le mode dangereux de [`etude-suivi-personne.md`](etude-suivi-personne.md)
    §3** : un complice masque les jambes de David. Aujourd'hui Didier doit
    **avancer** (c'est le défaut à constater, roues hors sol d'abord). C'est la
    mesure qui justifiera le correctif S0.

## Odométrie des roues

Plan : [`etude-odometrie.md`](etude-odometrie.md) (décidé 2026-07-14 — ne pas
re-trancher §3 à §6 ; inconnues §7).

**Le trou** : les roues n'ont AUCUN retour de rotation. Le moteur est un MY1016Z
**à balais** (la fiche matériel disait « brushless » — faux, corrigé le 14/07),
donc pas de capteurs Hall à dériver, et le SmartDrive40 n'expose aucune sortie
tachy. Conséquence : `/cmd_vel` est en **boucle ouverte** (des m/s qui sont du
PWM déguisé), et il n'y a pas de TF `odom` → `base_link`. C'est le verrou de
`ros2_control` ET de nav2. Ni le lidar ni la caméra ne le comblent.

**La solution retenue** : roue phonique lue par la FACE avec deux capteurs
inductifs `LJ12A3-4-Z/BX` (M12, NPN, 12 V) par roue → quadrature → PC817 → Pico
(PIO) → **USB** → nœud ROS.

⚠️ **Renversé le 20/08 (David)** : la carte va **en bas, près des roues**, et c'est
le câble **USB** qui remonte au Pi. Le §6 plaçait la carte côté Pi avec un lien
UART, pour ne pas faire porter la distance à un fil logique 3,3 V nu — juste, mais
l'USB est une paire différentielle blindée, bien plus robuste que ce fil, et on
raccourcit en prime les câbles capteurs. Le Nano (stock de David) a été écarté pour
UNE raison : les clones CH340 n'ont pas de numéro de série, donc pas de règle udev
stable. Conditions gravées : **bridage du câble USB à moins de 5 cm de la prise**,
**boîte imprimée fermée**, **les 4 PC817 restent**. Inconnue : 12 V dispo en bas ?

**Firmware ÉCRIT et testé le 20/08** : `firmware/pico_odometry/` (MicroPython).
Coupure de conception : `odom_protocol.py` (décodage quadrature + CRC + trames)
tourne à l'identique sur le Pico, dans le futur nœud ROS et dans **35 tests hôte** ;
`main.py` ne garde que le PIO. Écrire le décodeur en C aurait imposé de l'écrire
deux fois — le moyen canonique d'inverser un signe sans le voir.

**Fixation du disque — la COIFFE, confirmée le 17/08 au soir.** Une variante
« sandwich boulonné sur la couronne » a été explorée les 16 et 17/08 puis RANGÉE
(`../plans/odometrie/variante-sandwich-couronne/`, avec son NOTE.md) : le cercle des vis
mesuré à Ø 77 mettait la visserie trop près des cibles, on tombait à 8 cibles / 24,5 mm/front,
sous le seuil de 22 que l'étude §7 juge inasservissable. La coiffe donne 19,6 et elle est
déjà imprimée. **Le détour n'a pas été perdu** : il a produit 4 cotes MESURÉES qui renforcent
la coiffe — couronne 6 mm, chaîne 16 mm hors-tout (donc débord réel **5 mm**, contre 6
supposés « optimistes »), et surtout **obstacle carter à ~66 mm et non 63** (disque Ø 113
présenté : **≥ 10 mm d'air** relevés contre 6,5 au modèle). Les deux hypothèses les plus
inquiétantes du chantier étaient donc **pessimistes**.
⚠️ **Et une erreur trouvée au passage, qui vaut pour la coiffe aussi — la quadrature.** Toute
la doc prescrivait « capteur B réglé 7 mm plus bas que A » : FAUX, les capteurs étant
diamétralement opposés, ça donne un déphasage **rigoureusement nul** (les deux LED basculent
ensemble, plus de sens de rotation, et rien ne casse). Il faut les décaler **du même côté** de
l'axe, de `R·sin(pas/8)` chacun = **3,45 mm**. Corrigé dans `patte-capteur.scad`.

*(Le détail de la variante sandwich — pourquoi elle était séduisante, pourquoi elle
a échoué, et comment la réveiller — est dans son `NOTE.md`. Ne pas le recopier ici.)*

**16/08 — le disque Ø 155 CONTREDIT PAR LE RÉEL, redimensionné Ø 113.** Le premier jeu
imprimé (gabarit → jupe → disque, PETG) butait sur le **carter du réducteur** — jamais
mesuré — et la chaîne traverse son plan (photos de la collision :
`../plans/odometrie/photos/`). Cote relevée : axe → obstacle = **63 mm** (`OBSTACLE_R`).
Recalé le jour même : **10 cibles à R = 44, Ø 113 × 12, 19,6 mm/front** (M8/clé de 13
conservé : cible ≥ 3×Sn = 12 mm), garde-fou 5b désormais purement radial, et **empreinte
hexa des deux côtés** (tête indexée = cibles au même profil, serrage sans clé à tenir).
Le gabarit a rendu son verdict au passage : `JEU_HEX` 0.4 trop libre → **0.25**, à
revalider par le gabarit avant tout disque. Tout est régénéré, asserts verts.

**16/08 soir — fixation capteurs en v4 (montage de David, qui a retoqué mes v3.x
deux fois avec raison)** : **4 pattes identiques** (2/roue) vissées sous la caisse,
un capteur **de chaque côté du palier, à hauteur d'axe** — là il y a 30 mm de place,
donc **montage classique, un écrou M12 de chaque côté du voile** (les v3.x à 6 H
reposaient sur une erreur de signe : l'axe est 30 mm SOUS la caisse). On ne touche
plus aux boulons du palier, **la tôle pliée et son plan papier restent SANS OBJET**.
⚠️ La **quadrature est un réglage vertical** : capteur B 7 mm plus bas que A (un
quart de pas), calé aux LED — lumière verticale ±8 mm prévue pour. Détail : étude
§3 ter, rendus dans le dépôt plans (odometrie/rendus/).

**16/08 soir aussi — les capteurs LJ12A3 SONT ARRIVÉS** (photo : 2 écrous +
rondelle livrés avec) → **l'étape 1 (banc d'établi) est débloquée**. Et la
**couronne est déposée** : au réglet ~130-135 mm hors-tout, l'étude disait
« Ø 110 mesuré » → à re-mesurer posée à plat (gardes chaîne à recaler ; le disque
Ø 113 n'est pas concerné, son plafond est l'obstacle mesuré à 63 mm).

**Pièces dessinées** (`../plans/odometrie/`, dépôt plans) : roue phonique `disque-phonique.scad`
(coiffe, porte-cibles PETG + **10** têtes de vis M8 en acier ZINGUÉ — l'inductif ne voit que le
métal, et surtout PAS l'inox), pattes capteurs sous caisse (v4), et le banc d'établi. Géométrie
sous `assert()` : une cote fausse refuse de compiler.

~~Plan papier 1:1 du support tôle — fait le 15/08~~ — **SANS OBJET depuis la v3** (plus de
tôle). L'outillage reste dans le dépôt plans pour mémoire : `plan-decoupe-metal.py` savait
sortir une A4 1:1 auto-vérifiée, la méthode resservira si une pièce métal revient.

**Prochaine action — étape 1, sans robot, zéro risque** : commander les capteurs
(~15 €, cf. §9 — ⚠️ variante **NPN**, jamais PNP), imprimer le banc, passer la
réglette à la main devant les deux capteurs. Ça valide détection, entrefer, logique
inversée, quadrature et **le sens** (aller-retour), et tout le firmware Pico + le
nœud ROS se déboguent là.

**En parallèle, les mesures au pied à coulisse** (§7). Les six cotes bloquantes ont été
levées le 14/07 (dont la garde axe → châssis, 30 mm, qui plafonnait le rayon du disque).
Il reste **trois cotes de palier** — `D_BOULON`, `PAL_ENTRAXE`, `PAL_AXE_SEM` — qui ne
bloquent que la **tôle** : `D_BOULON` place les trous, et fausse de 3 mm elle rend la pièce
bonne à jeter. Le gabarit papier est fait pour ça : on le présente sur le robot avant de
toucher au métal.

Puis : étape 2 carte à trous au brochage définitif → étape 3 robot **roues hors
sol** + protocole caméra (on mesurera enfin la vraie vitesse pour un PWM donné,
première mesure objective du chemin roues) → étape 4 seulement, le PCB KiCad.

**Carte électronique FAITE et vérifiée** (14/07) :
`~/Nextcloud/dev/didier/pcb/kicad/wheel-odometry/` — schéma (ERC 0 violation,
netlist contrôlée), PCB placé, et **implantation stripboard vérifiée PAR
PROGRAMME**, net par net, contre la netlist. Lien vers le Pi en **UART**
(J6 : 5V/TX/RX/GND), pas USB — le micro-USB est le point faible d'une machine
qui part en tournée.

⚠️ **L'I²C est INTERDIT sur ce chantier.** `wheels_node.stop()` écrit le PWM par
le bus I²C : un esclave qui fige le bus empêcherait le robot de freiner (le
PCA9685 garderait sa dernière consigne = emballement). Raisonnement complet dans
l'étude — ne pas re-trancher.

**Verrous** : (a) les 5 cotes du §7, dont la **bloquante** — la garde axe →
châssis, qui plafonne le rayon du disque donc la résolution ; (b) **quel UART
côté Pi** : le primaire (GPIO14/15) est pris par la console et le Bluetooth, et
les GPIO libres sur la carte principale restent à vérifier.

**Aval** : `ros2_control` / `diff_drive_controller`, EKF (encodeurs + IMU pour
le yaw), nav2. Le BNO055 existe déjà dans le code (`robot/move/bno_055_extended.py`)
mais n'est appelé nulle part en prod — vérifier s'il est encore sur le robot.

## ⚠️ DANGER ACTIF — les 2 boutons du dos font l'INVERSE de ce qu'on croit (30/08)

**Découvert le 30/08 sur une remarque de David** (« j'ai deux boutons derrière, un
stop et un reset de Pi, il faudrait peut-être réaffecter les fonctions » — son
intuition était juste, la réalité est pire).

Ce que font vraiment les deux boutons (`dadou_utils_ros/utils/status.py`,
`Status.check_button` → `os.system`) :

| Bouton | GPIO | Commande réelle | Effet sur les roues |
|---|---|---|---|
| « **stop** » | `D16` (`SHUTDOWN_PIN`) | `sudo shutdown now -h` | **AUCUN — et pire** |
| « reset » | `D20` (`RESTART_PIN`) | `sudo reboot` | **AUCUN — et pire** |

`system_node` est bien lancé (`robot_app.launch.py:61-64`) : les deux boutons sont
**actifs sur le robot**. Appui maintenu 1 s (double lecture anti-rebond).

> ### ⚠️ Le bouton « stop » est un DÉCLENCHEUR D'EMBALLEMENT
> Il éteint le Pi → `wheels_node` meurt → le PCA9685 **garde sa dernière consigne**
> → **les roues continuent, et il ne reste plus aucun logiciel pour les arrêter.**
> Le bouton fait l'inverse de ce que son nom promet, et c'est le geste réflexe de
> quiconque panique. Idem pour « reset ».

**Règle d'exploitation, applicable TOUT DE SUITE, avant tout essai roues au sol
(donc avant le chantier 1)** :

- ❌ **NE JAMAIS appuyer sur « stop » ni « reset » pendant que les roues tournent.**
- ✅ Le seul arrêt réel aujourd'hui est la **coupure générale d'alimentation**.
- ✅ **Étiqueter physiquement les deux boutons** (« ARRÊT PI — PAS un arrêt d'urgence »)
  tant que la réaffectation n'est pas faite. Coût nul, supprime le piège immédiatement.

**Réaffectation proposée** (non tranchée — voir l'étude, chemin roues donc spec +
protocole caméra + revue Opus obligatoires) :

- **D16 (« stop ») → VRAI arrêt d'urgence** : coupure PWM roues immédiate **et**
  publication du verrou `e_stop` — qui est déclaré dans `twist_mux.yaml:39` et
  **n'attend qu'un publieur depuis le 11/07**. Ce bouton comblerait donc d'un coup
  le trou `e_stop` documenté, et supprimerait le piège. ⚠️ Un organe d'arrêt
  d'urgence ne doit JAMAIS être ambigu : pas d'appui court/long sur celui-là.
- **D20 (« reset ») → extinction propre du Pi sur appui LONG (3 s)** — il faut
  garder un moyen d'éteindre proprement (corruption de carte SD sinon). Le *reboot*
  disparaît : c'est le moins utile des trois, et il se fait en `ssh`.

⚠️ **Ça reste du logiciel** : si `system_node` meurt, le bouton ne répond plus. Ce
n'est donc PAS un substitut au coup-de-poing catégorie 0 de la carte main-carrier
ci-dessous — c'est une **mesure intérimaire**, qui a le mérite de transformer un
piège actif en garde-fou utile en attendant la carte.

### ✅ VÉRIFIÉ SUR LE ROBOT RÉEL le 30/08 — le diagnostic est confirmé

Fait sur Didier allumé, à la demande de David. **Le code déployé est identique au
dépôt** (`install/robot/lib/python3.12/site-packages/dadou_utils_ros/utils/status.py`) :
`SHUTDOWN_CMD = 'sudo shutdown now -h'`, `RESTART_CMD = 'sudo reboot'`,
`check_button` avec son `time.sleep(1)`. Le diagnostic ne vaut donc pas seulement
« dans le dépôt », il vaut sur la machine qui tourne.

**Câblage confirmé — la config dit vrai** (`pinctrl`, lecture des registres) :

| Bouton physique | Broche mesurée | Repos | Config |
|---|---|---|---|
| « stop » | **GPIO16** ✅ | `ip pu hi` | `robot_config.py:85` |
| « reset » | **GPIO20** ✅ | `ip pu hi` | `robot_config.py:86` |
| (LED d'état) | GPIO12 | `op`, alterne 2 Hz | `robot_config.py:87` |

Rappel vers le haut actif, l'appui tire à la masse — conforme à `Pull.UP` +
`if not button.value`.

⚠️ **Ce que la mesure a démontré, chiffres à l'appui.** Durées d'appui relevées :
**~3 s** et **~2 s** sur GPIO16, **~7 s** sur GPIO20 — toutes **au-dessus du seuil
de 1 s** de `check_button`. Autrement dit, ce seul test aurait **éteint le Pi deux
fois et l'aurait redémarré une fois** si `system_node` n'avait pas été arrêté au
préalable. Roues tournantes, chacun de ces appuis aurait produit l'emballement
décrit plus haut. Ce n'est plus une déduction : c'est mesuré.

**Recette de test SANS RISQUE, réutilisable** (l'improvisation ici coûte un Pi
éteint, voire pire) :

1. `pkill -f system_node` **dans le conteneur** → les 2 boutons deviennent inertes
   (aucun `respawn` au launch, `robot_app.launch.py:61-65`). ⚠️ `pkill -f` matche
   sa propre ligne de commande et se tue lui-même : vérifier la mort du nœud
   séparément, avec `ps aux | grep "[s]ystem_node"`.
2. Observer avec **`sudo pinctrl get 16,20`** *sur l'hôte* : Blinka attaque les
   registres en direct, la ligne n'est donc pas réclamée côté noyau et une lecture
   extérieure n'entre en conflit avec rien. (Format piégeux : `$5` porte la valeur
   pour une **entrée**, mais `$6` pour une **sortie** — un champ de plus.)
3. Relancer ensuite : `ros2 run robot system_node --ros-args -r __node:=system_node`
   en `docker exec -d`, puis **confirmer par la LED GPIO12 qui doit ré-alterner** —
   sans quoi on croit avoir remis le nœud alors qu'il a échoué au démarrage.

### Spec de réaffectation — FERMÉE le 30/08 (choix de David)

Boutons **atteignables à la main sans se pencher** (confirmé par David) : D16 est donc
un arrêt d'urgence réellement utilisable, pas un simple garde-fou de maintenance.

| Geste | Effet |
|---|---|
| **D16, appui court** | **ARRÊT D'URGENCE**, latché. Jamais d'appui long/court sur cet organe : un arrêt d'urgence n'est **jamais** ambigu. |
| **D20, appui court** (< 1 s) | **Réarmement** — geste explicite et *distinct* de l'arrêt. |
| **D20, appui long** (≥ 3 s) | Extinction propre du Pi (`shutdown now -h`). |
| ~~reboot~~ | **Supprimé** — le moins utile des trois, se fait en `ssh`. |

**Chemin de l'arrêt (deux voies, volontairement redondantes)** :

1. `system_node` publie `std_msgs/Bool(True)` sur `e_stop`, **latché
   `TRANSIENT_LOCAL` des DEUX côtés** (leçon déjà payée sur `animation_state` :
   un abonné qui démarre après le publieur rate un verrou non latché) → `twist_mux`
   applique son verrou priorité 255.
2. **`wheels_node` s'abonne AUSSI à `e_stop` en direct** → `wheels.stop()` immédiat,
   et refuse toute consigne tant que le verrou est actif. C'est la voie courte : elle
   ne dépend d'aucune sémantique de `twist_mux`.

⚠️ **Interdit de réutiliser `Status.check_button` tel quel** : il contient un
`time.sleep(1)` **bloquant** (double lecture anti-rebond). Sur un arrêt d'urgence, 1 s
= ~1 m parcouru à 1 m/s, et le tick 20 Hz de `system_node` est gelé pendant ce temps.
D16 doit déclencher sur le **premier front stable** (anti-rebond 2 ticks = 100 ms max).

**⚠️ Le contrat de RÉARMEMENT est déjà écrit et testé** — le reprendre à l'identique
depuis la branche `chaine-securite` (`test_safety_chain.py`), c'est le danger n°1 :

- `test_rearmement_sans_remise_a_zero_rejoue_l_ancien_pwm` → **remettre les registres
  PWM à zéro AVANT de lever le verrou**, sinon le robot rejoue l'ancienne consigne et
  **redémarre d'un coup** au réarmement ;
- `test_relacher_le_coup_de_poing_ne_rearme_pas` → **relâcher D16 ne réarme JAMAIS**.
- Conséquence rassurante : un réarmement accidentel seul ne produit aucun mouvement
  (pas de consigne = deadman = arrêt). C'est ce qui rend acceptable le court/long sur
  D20 — l'ambiguïté est sur le bouton *non* urgent, jamais sur l'arrêt.

**À VÉRIFIER EN SIM AVANT TOUT** (deux polarités, exactement le genre d'erreur
silencieuse qui a déjà coûté cher à ce projet) :

1. **Polarité du verrou `twist_mux`** : est-ce bien `true` = bloqué ?
2. **Comportement d'un verrou périmé** : avec `timeout: 0.0` le verrou ne périme
   jamais (voulu). Mais vérifier qu'un `e_stop` jamais publié = robot libre — c'est
   le mode de défaillance connu (`system_node` mort = bouton muet), à assumer
   explicitement, pas à découvrir.

**Point d'attention d'implémentation** : `SHUTDOWN_PIN`/`RESTART_PIN` sont des clés de
config définies **dans les deux dépôts** (`robot/robot_static.py:113` et
`dadou_utils_ros/utils_static.py`) — les chaînes doivent rester identiques. Renommer
en `E_STOP_PIN` impose donc de toucher **les deux dépôts dans le même lot** (la lib
partagée n'a pas de versionnage — cf. chantier « diagnostic utils partagé »).

**Gate obligatoire** : chemin roues ⇒ sim d'abord, **puis protocole caméra roues hors
sol** (`conf/scripts/validate-cmdvel-protocol.sh`), et revue Opus minimum. Le nouveau
protocole doit ajouter : appui D16 en plein mouvement → arrêt ; relâcher D16 → **pas**
de redémarrage ; D20 court → réarmement **sans à-coup**.

### Coup-de-poing déporté sur la paroi bois — contraintes d'achat (30/08)

David juge les boutons du dos **peu accessibles** et veut un coup-de-poing sur une
**paroi de bois de 18 mm**. Contraintes relevées, valables quel que soit le modèle :

⚠️ **18 mm est TROP ÉPAIS pour un bouton 22 mm standard** — ils admettent typiquement
**1 à 6 mm** de paroi (conçus pour de la tôle d'armoire). Deux issues : un **boîtier
en saillie** qui se visse *sur* la paroi et ignore l'épaisseur (recommandé : aucun
usinage, et c'est la forme la plus trouvable à l'aveugle sur un plateau), ou un
**lamage Forstner par l'arrière** (Ø 30-35, prof. ~13 mm) ne laissant que 5 mm au
droit du bouton, plus l'encoche anti-rotation.

**Exigences non négociables** : contact **NF** (jamais NO), **à accrochage avec
déverrouillage par rotation**, et **2 contacts** (1 NO + 1 NF, type `LA38-11ZS` ou
`XB2-BS542`) pour servir la chaîne de puissance ET la lecture GPIO `ESTOP_SENSE`
sans racheter le bouton. ⚠️ Le piège est **dans le sélecteur**, jamais dans le titre :
« Latching/**Self-reset** » — le *self-reset* est momentané, inutilisable. Même
mécanique que le piège NPN/PNP de l'étude odométrie.

⚠️⚠️ **LE CONTACT NF INVERSE LA LOGIQUE DU CODE — à ne pas rater.** Les boutons
actuels sont momentanés : repos = haut, appui = bas (`Pull.UP` + `if not
button.value`). Avec un **NF** câblé entre GPIO et masse c'est l'exact inverse :
**repos = BAS** (contact fermé), **appui OU FIL COUPÉ = HAUT**. Le code devra donc
tester `if button.value`. C'est ce qui rend le montage *fail-safe* — un fil arraché
provoque un arrêt au lieu de rendre le bouton muet — et c'est exactement le type
d'inversion silencieuse qui a déjà coûté cher à ce projet (cf. le déphasage nul des
capteurs d'odométrie). **Un test doit verrouiller cette polarité.**

⚠️ **Le bouton ne doit JAMAIS couper le courant moteur en direct** (~20 A, et le
continu arce bien plus que l'alternatif) : il commande la **bobine du contacteur
40 A** de la chaîne main-carrier, câblée de sorte que **perdre la bobine = couper**.

### SPEC FERMÉE — arbitrée par David le 30/08 (accessibilité confirmée)

David a tranché : **D16 → vrai `e_stop`, D20 → extinction sur appui long, reboot
supprimé**. Et il confirme que les deux boutons sont **atteignables à la main sans se
pencher** — donc D16 est un arrêt d'urgence *réellement utilisable*, pas un simple
garde-fou de maintenance.

**Faits établis qui contraignent la conception** (vérifiés le 30/08) :

- `Status` n'est utilisé **nulle part ailleurs** (ni dans `dadou_control_ros`) :
  modifier la lib partagée ne casse rien d'autre. *Vérifier à nouveau avant de
  toucher — la lib n'a pas de versionnage.*
- `Status.process()` est appelé au tick global **20 Hz** (`TICK_PERIOD_S = 0.05`) :
  latence de détection 50 ms, acceptable pour un e-stop.
- ⚠️ `Status.check_button` contient **`time.sleep(1)` bloquant** (double lecture
  anti-rebond). **Interdit sur le chemin e-stop** : 1 s = ~1 m parcouru à 1 m/s, et
  ça gèle `system_node` pendant ce temps. D16 doit déclencher sur **2 ticks
  consécutifs (~100 ms)**, sans `sleep`.
- `twist_mux.yaml:38-42` : verrou `e_stop`, **`timeout: 0.0`** (n'expire jamais) et
  `priority: 255`. Sémantique déjà latchée côté mux — le publieur doit s'y conformer.

**Contrat à respecter — repris tel quel de la branche `chaine-securite`** (c'est le
même danger, donc la même règle ; les tests existants en sont la spec) :

1. `test_relacher_le_coup_de_poing_ne_rearme_pas` → **relâcher D16 ne réarme JAMAIS.**
   Le réarmement est un **geste explicite et distinct**.
2. `test_rearmement_sans_remise_a_zero_rejoue_l_ancien_pwm` → ⚠️ **le piège mortel** :
   réarmer sans remettre les registres à zéro fait **rejouer l'ancien PWM** — le robot
   repart d'un coup, tout seul. Donc **remise à zéro AVANT tout réarmement.**

**Affectation retenue** :

| Geste | Effet |
|---|---|
| **D16 appui court** | `e_stop` **LATCHÉ** : `wheels.stop()` immédiat (registres à zéro) **+** publication `e_stop=True`. Jamais d'appui court/long sur cet organe. |
| **D16 relâché** | **rien** (contrat 1) |
| **D20 appui court** | **réarmement explicite** : registres à zéro d'abord (contrat 2), puis `e_stop=False` |
| **D20 appui long 3 s** | extinction propre du Pi (`shutdown -h`) |
| ~~reboot~~ | **supprimé** — se fait en `ssh` |

*Pourquoi le réarmement va sur D20 et pas sur D16* : un arrêt d'urgence ne doit jamais
être ambigu. On met donc la distinction court/long sur le bouton **non** urgent. Et un
réarmement accidentel seul ne produit **aucun mouvement** (registres à zéro + deadman :
sans nouvelle consigne, rien ne bouge).

**Chemin de coupure — deux voies, volontairement redondantes** :
`wheels_node` s'abonne à `e_stop` **directement** (`stop()` + refus des `cmd_vel` tant
que latché), *en plus* du verrou `twist_mux`. La voie directe ne dépend pas du mux ;
le mux protège les autres sources. ⚠️ **`TRANSIENT_LOCAL` des deux côtés** — leçon déjà
payée sur `animation_state` : sans ça, un nœud qui démarre après l'appui ne voit pas
l'e-stop et croit la voie libre.

**Validation obligatoire avant le sol** : tests unitaires (dont les 2 contrats
ci-dessus), puis **simulation**, puis **protocole caméra roues hors sol** — c'est le
chemin roues. Revue Opus minimum. Instantané commité avant de commencer.

## Chaîne de sécurité matérielle (carte main-carrier)

**Le trou (découvert 14/07)** : l'arrêt d'urgence de Didier est 100 % logiciel.
`wheels_node.stop()` écrit le PWM **par le bus I²C** — si le bus se fige ou si
le node meurt, le PCA9685 garde sa dernière consigne et les roues continuent,
pendant que le deadman 400 ms croit avoir freiné. Le protocole caméra du 04/07
a validé la mort de la chaîne *amont*, jamais celle de `wheels_node` lui-même.

**La parade (schéma main-carrier révisé 14/07, commit KiCad 4484d54)** :
watchdog matériel 74HC123 (250 ms, réarmé par un battement GPIO26 émis
seulement APRÈS chaque écriture I²C réussie) → ET par diodes avec la boucle
coup-de-poing → bascule D 74HC74 à `/CLR` dominant (maintenir ARM ne réarme
pas) → OE du PCA9685 roues. Coup-de-poing = catégorie 0 (relais 40 A,
purement électromécanique). Les deux PCA9685 sont séparés (roues 0x40,
servos 0x41 à venir) pour que couper les roues ne fige plus le visage.

**Contrat figé en tests — branche `chaine-securite`** (la carte n'existe pas
encore ; `main` reste le reflet du robot réel) : modèle exécutable de la carte
(`robot/tests/unit/safety_chain_model.py`) branché sur le **vrai** code
`Wheels`, 11 tests (`test_safety_chain.py`) couvrant mort du node, bus figé,
`/CLR` dominant, coup-de-poing, et LE piège du réarmement : sans remise à zéro
des registres, ARM rejoue l'ancien PWM. Les helpers `drive()`/`try_stop()` du
fichier de tests SONT la spec du futur node. Merger la branche quand la carte
sera fabriquée et le node écrit.

**Verrous** : bande sécurité du PCB placée mais **pas routée** (122 chevelus,
volontaire) ; encombrement 195×150 mm à confirmer dans le coffret avant
Gerbers ; le node (battement + `/e_stop` depuis ESTOP_SENSE GPIO23) n'existe
pas — volontaire aussi, les tests d'abord.

## Chemin de commande des roues (PWM moteur)

Étude : [`etude-chemin-commande-roues.md`](etude-chemin-commande-roues.md)
(**tranché le 2026-08-30 — ne pas re-trancher**). Pendant « commande » de
l'étude odométrie, qui ne traite que la « mesure ».

**Question de David** : puisqu'on ajoute un RP2040 pour l'odométrie, faut-il y
mettre aussi la commande des roues (l'I²C n'ayant « pas de vrai timing ») ?

**Réponse : non** — mais pas par dogme. Le bénéfice visé est **déjà obtenu** par
la chaîne de sécurité ci-dessus : le watchdog 74HC123 → `OE` agit *sous* le
logiciel ET *sous* l'I²C, ce qu'aucun firmware ne peut faire. Il ne resterait au
Pico que la boucle de vitesse locale — sujet de l'étape 5 (nav2), pas
d'aujourd'hui. Le GPIO du Pi est exclu séparément : il percerait l'**ISO1540**,
la seule barrière galvanique protégeant le SoC du domaine actionneurs.

**Ce que le relevé de code du 30/08 a établi** :

- ⚠️ **Roues et servos sont sur la MÊME puce PCA9685** (canaux 0-3 / 4-15 ;
  `PCA9685(i2c)` et `ServoKit(channels=16)` sans adresse → 0x40 tous les deux).
  Donc **une seule fréquence PWM**, et elle se joue à une course au démarrage
  entre **six** processus : `wheels_node` (60 Hz) et les **cinq** `servo_node`
  du launch (50 Hz chacun). Personne ne l'a décidée, et on ne peut pas la monter
  sans dégrader les servos. `FREQUENCY = 500` (`wheels.py:34`) n'est branché
  nulle part — c'est une trace, pas du code mort.
- ✅ **Effet de cette course : BÉNIGNE.** Une première rédaction du 30/08 en
  faisait un « danger opérationnel » à soupçonner devant une dérive des roues :
  ⚠️ **c'était faux et c'était une fausse piste de diagnostic**, corrigée le
  jour même après lecture du code de la lib. `reset()` n'efface pas les
  registres de consigne ; le setter de fréquence endort la puce ~5 ms
  (imperceptible sur 50 kg) ; et surtout **à rapport cyclique égal la tension
  moyenne est la même à 50 ou 60 Hz**, donc la vitesse ne change pas. À
  corriger par propreté, pas par urgence — détail et preuves dans l'étude §2.1.
- ⚠️ **Il n'y a PAS de problème de « timing I²C »** (la question d'origine) : la
  PCA9685 est un générateur PWM **matériel**, la forme d'onde est propre quoi
  que fasse Linux ; l'I²C ne porte que les changements de consigne, à 20 Hz, ce
  qui suffit. Le seul vrai point de qualité est la **fréquence porteuse**
  (60 Hz = ronflement et couple pulsé sur un moteur à balais) — **jamais
  constaté ni écouté sur Didier : à vérifier à l'oreille, roues hors sol.**
- ✅ **La séparation 0x40/0x41 prévue par la chaîne de sécurité règle ça
  gratuitement** (chaque puce retrouve sa fréquence). Bénéfice non répertorié :
  à exploiter délibérément au câblage — lire la fiche du SmartDrive40, puis
  **protocole caméra** (c'est le chemin roues).

**Prochaine action** (gratuite, sans attendre le test au sol) : réserver 4 GPIO
(2 PWM + 2 DIR) sur le Pico et les documenter dans le `DESIGN.md` de la carte
odométrie — **sans router d'étage de sortie** : une sortie de commande qui ne
passerait pas par `OE`/`/CLR` contournerait le watchdog.

## Interface web / télé-présence

Plan : [`etude-interface-web.md`](etude-interface-web.md) (décidé 2026-07-11 —
ne pas re-trancher, inconnues §9).

FAIT : **W0** vérifiée en sim le 11/07 (package `robot_web` autonome — node
rclpy+aiohttp, whitelist sans roues/e_stop, session exclusive + heartbeat, UI
vanilla — 511 tests, protocole WS validé de bout en bout, `WEB=true` port
8765 ; 8088 = Superset sur le PC de dev). **Console + W3-sim** le même jour :
console de régie (vidéo + pad + recherche), caméra gz → MJPEG `/video`,
pilotage pad/manette → `cmd_vel_web` (twist_mux prio 50, plafond dur 0,5 m/s
backend, zéro unique à l'arrêt — vérifié e2e jusqu'à `/cmd_vel`) ;
`WEB_DRIVE=true` requis (défaut false) + chaîne roues à la main
(docs/operations.md). **Bringup robot câblé** (web_bridge dans
robot_app.launch.py, contenus/supervision seulement — drive non passé donc
false) ; image ARM rebuildée (python3-aiohttp + python3-pil). **Console
enrichie le 12/07 (déployé + vérifié)** : alias mDNS `didier.local` (service
`avahi-alias-didier`, source `conf/systemd/`, install docs/operations.md —
`/etc/avahi/hosts` ne publie PAS sur le réseau) + toggle **Parole IA** (topic
`chat` en whitelist technique, ON/OFF → chat_node du Pi vision, même contrat
que `gaze`).

**Suite : W1** (source e_stop + coup-de-poing sans fil). Le passage des roues
web au ROBOT RÉEL reste conditionné au test scénique au sol (chantier 1) et à
un protocole caméra dédié.

### ⚠️ Verrou matériel découvert le 2026-09-13 : un seul RJ45 branchable

Le routeur embarqué est un **Teltonika RUT955** (modèle confirmé sur pièce ce
jour-là ; le relevé filmé du 03/09 n'avait lu que `RUT9…`). Son support actuel
est si serré qu'**un seul câble RJ45 peut être branché** — le câble jaune sort
du port en coude forcé, et David signale qu'il lui en faut **deux, pour la
deuxième Pi**.

Ça contredit une prémisse écrite : `hardware/overview.md` affirme que « les
deux Pi sont en RJ45 sur le routeur embarqué une fois correctement câblées » —
argument qui a servi à écarter l'objection « la vision est derrière le Wi-Fi »
pour le lidar 3D et la caméra de profondeur. **Le raisonnement reste valable,
mais sa prémisse n'est pas encore vraie sur le robot.**

Traitement : support imprimé de remplacement, étude et cotes dans
~/Nextcloud/dev/didier/plans/supports/support-teltonika-rut955/ (hors dépôt).
Plan constructeur officiel archivé, orientation retenue « comme aujourd'hui
mais mieux dégagé ». **Bloqué sur des mesures d'atelier** : enveloppe
disponible, support de fixation, dégagement devant la face avant — et
l'identification d'un boîtier noir `9-30 VDC` à bornier vert, vu à côté du
routeur et rattaché à aucun document.

## Télédiagnostic par agent IA

Plan : [`etude-telediagnostic.md`](etude-telediagnostic.md) (**décidé, grillé
le 2026-07-12** — ne pas re-trancher, décisions §8 : hybride embarqué host Pi
+ PC atelier, Opus sur abonnement, START télécommande → topic `incident`,
boîte noire segments SD 30 j sans caméra, remédiations autonomes encadrées).

FAIT : **étape 1 « trousse d'atelier »** le 12/07 —
`conf/scripts/collect-incident.sh` (host du Pi, best-effort, testé de bout en
bout contre la sim ; piège corrigé : `ros2 node list` vide au premier appel du
daemon → retente), skill `/diag` (`.claude/skills/diag/SKILL.md`), journal
[`incidents/`](incidents/README.md) (post-mortem obligatoire). Part avec le
rsync habituel, rien à déployer. **Utilisable dès maintenant** : panne →
`ssh r '~/ros2_ws/src/*/conf/scripts/collect-incident.sh'` → session Claude
+ `/diag`.

**Suite : étape 2 « boîte noire + bouton »** (§9 du plan) : enregistreur
rosbag par segments SD 60 s + purge 30 j dans le bringup, topic `incident`,
bouton START télécommande (libre — GPIO D21 + manette USB ; côté
dadou_control_ros : l'ajouter à `PUBLISHER_LIST`) + boutons logiciels,
marqueur `INCIDENT` dans robot.log, endpoints `/api/logs` + `/health` sur le
pont web, topic santé publié par system_node. Validation en sim d'abord.
**Préalables de l'étape 3 (agent embarqué)** : RAM du Pi 4
(`ssh r 'cat /proc/meminfo'` — non documentée nulle part), charge d'une
investigation vs tick 20 Hz, santé/espace SD, 4G partagé en salle.

## Conversation en déambulation (intention de communiquer + contenu)

Plan : [`etude-declenchement-conversation.md`](etude-declenchement-conversation.md)
(**DÉCIDÉ, grillé le 2026-07-12** — ne pas re-trancher, décisions §5, points
ouverts §8). Périmètre élargi au grill : déclenchement + contenu + robustesse
rue.

Décisions clés : opérateur à vue, robot peut rouler → **regard généreux en
roulant, micro seulement à l'arrêt** (gate `/cmd_vel`) ; ENGAGED = personne
en zone sociale ET (arrêt ≥ 3 s OU parole détectée) — le bruit sans personne
ne déclenche plus jamais ; sessions (clôture silence 12 s / perte 3 s,
cooldown 45 s) ; **réactif d'abord** (invitation par le corps : regard +
expressions + gimmick sonore + animation « invite », rejet encaissé en jeu) ;
persona à créer de zéro (atelier d'écriture, garde-fous = confiance au modèle
pour l'instant, répliques courtes et relanceuses) ; micro U20 et CPU Pi 5
mesurés avant tout achat (soupape whisper API) ; latence < 2 s au premier
son ; corpus complet type tournage (affichage + bouton garder/effacer,
effacement par défaut). Abordage mobile, proactif verbal et mémoire des gens
en D6, derrière les verrous roues.

**D0 outillage FAIT le 13/07** (dadou_vision_ros 53c6d13, 162 tests) : topic
`chat_state` latché (listening/thinking/speaking/off), rejeu VAD de prod sur
wav (`vad_replay`), scripts `enregistre-rue.sh` / `mesure-cpu-conversation.sh`
/ `calibre-distance.sh`. **Atelier persona FAIT le 13/07** (partie écriture +
commutation) : 3 personnalités commutables à tester — « bougon » (défaut) /
« naif » / « vantard » — socle + textes dans `vision/ai/personas.py` (repo
public, tranché §8), commutation à chaud topic `persona` (nouvelle session de
conversation à chaque bascule), sélecteur sur la console web.

### 2026-09-13 — première vraie conversation d'atelier, et ce qu'elle a révélé

Séance sur le banc PC (ReSpeaker du robot branché sur le PC, corps en sim).
David a conversé pour de bon avec Didier. Quatre défauts corrigés le jour
même (dépôt vision : 0b5e41f, 386d585) :

- **les redites** — `add_system_text()` stockait les répliques de Didier avec
  `role="system"` : elles arrivaient au LLM comme des CONSIGNES, qu'il
  ré-exécutait mot pour mot. Corrigé (`assistant` + requalification des
  entrées héritées à la lecture) ;
- **la bouche continuait après la réplique** — `speaking_stop()` coupe
  l'animation mais pas le visage, et l'expression « parle » est en
  `loop: true` ; rattrapage `idle()` ajouté (même trou que celui corrigé le
  12/07 sur les tours abandonnés) ;
- **bips trop forts** (14000 ≈ −7 dBFS) → 5000, et rendus réglables ;
- **aucune observabilité en direct** → vumètre web (`diag_port`, OFF par
  défaut) : niveau en dBFS, seuils VAD et gate tracés, témoin d'écrêtage,
  latences par étape du dernier tour.

**Découvertes à traiter — deux contrats MORTS et un manque de fond :**

1. ⚠️ **La synchronisation labiale n'existe pas.** Pendant la parole, le
   visage joue l'expression `parle` : une boucle fermée de 800 ms, sans
   aucun lien avec l'audio. Quatre expressions portent encore
   `"follow audio": true` (`speak`, `speak red`, `speak loop`, `sexy`) mais
   **aucun code ne lit ce drapeau** — vestige de l'ancienne base. Piste si
   on l'ouvre : piper rend le PCM AVANT lecture, on peut piloter l'ouverture
   de bouche sur son enveloppe. David a choisi le 13/09 de ne recaler que la
   FIN, pas d'ouvrir ce chantier.
2. ⚠️ **Le nom de l'interlocuteur est demandé mais jamais retenu.** Le prompt
   ordonne d'émettre `{"name": …}`, `NAME_KEY` existe dans le parseur, mais
   **rien ne le consomme** en V2. Le prénom ne survit que dans la fenêtre
   glissante.
3. ⚠️ **`history_limit = 12` messages (6 échanges)** — valeur par défaut du
   constructeur de `StreamingBrain`, jamais exposée en config. D'où « il
   repart du début » (constaté par David). Mais le vrai manque n'est pas ce
   nombre : **les sessions par rencontre décidées au §5.2 ne sont pas
   implémentées** — `chat_node` ouvre UNE session au démarrage du node. En
   déambulation, une mémoire continue unique mélangerait les passants.
4. ⚠️ **La fin de phrase ne tiendra pas en rue** (soulevé par David, et il a
   raison) : `EnergyVad` calibre son seuil UNE fois sur la médiane des
   1000 premières ms. Ça peine déjà en atelier calme. Leviers, dont deux
   déjà payés : la **DoA du ReSpeaker** croisée avec l'azimut caméra
   (inexploitée), une **VAD neuronale** type Silero, et **l'opérateur**.

**⇒ Chantier ouvert : PLAN D'INTERACTION** — [`etude-interaction.md`](etude-interaction.md),
**écrite le 13/09, en attente de la démolition de David** (rien n'y est
tranché sauf ses réponses de séance). Elle se place AU-DESSUS des deux études
existantes et part du **dossier de création du spectacle** (hors dépôt,
Nextcloud `créa/théâtre/spectacles/paradise-quest/`), pas du code : le
spectacle précède le robot conversationnel.

Le renversement qu'elle acte : **Didier n'est pas un robot autonome, c'est
l'instrument de jeu de David** (« tout ce projet est un prétexte pour que je
joue, moi »). Le cahier des charges de l'IA RÉTRÉCIT — détecter qu'on a
répondu plutôt que comprendre finement, faire avancer une mission écrite
plutôt que décider, être pilotable en jeu plutôt qu'autonome, tenir cinq
cases plutôt que deux heures de conversation.

Trois trouvailles qui viennent du dossier de création et changent la
faisabilité :
- la règle du **« oui, et »** (toute réponse d'un passant devient une avancée)
  est une **tolérance aux erreurs de compréhension** : un robot qui entend de
  travers est le numéro, pas la panne. La barre technique baisse d'un cran ;
- les **cinq critères** donnent les raisons concrètes d'avancer — la
  perception visuelle n'est PAS structurante, c'est un bonus ;
- les **cinq séquences écrites** sont l'interface de pilotage : reprendre la
  main = faire avancer la mission, en jeu, sans sortir du personnage.

⚠️ **Convergence à ne pas manquer** : le §7.2 du dossier de création (27/08)
exige un coup-de-poing physique atteignable par David comme condition
d'assurabilité d'une date — exactement le trou que le tableau de bord a
établi le 30/08 de son côté (`e_stop` sans publieur, boutons du dos
dangereux, carte non fabriquée). **Aucune déambulation publique avant que ce
point soit fermé**, et c'est antérieur à tout le chantier interaction.

**Plan d'implémentation en 4 phases** (§9 de l'étude), chacune avec son verrou
de sortie, sur le principe **mesurer avant de construire** :
**A** corpus de rue + rejeu chiffré (verrou : on sait de combien c'est mauvais,
en nombres) → **B** détection de VOIX au lieu de niveau (verrou : amélioration
mesurée sur le corpus) → **C** interaction I0 état de mission + jauge LED,
I1 déclenchement en jeu, I2 mémoire des guides, I4 garde-fous (verrou : une
déambulation jouée de bout en bout en sim) → **D** le réel.
**A, B et C se font entièrement sur le banc PC** : l'immobilisation du robot
ne bloque rien de ce qui reste à décider.

### Détection de parole — le point dur, instruit le 13/09

⚠️ **`EnergyVad` ne mesure QUE du volume** : seuil = plancher calibré UNE fois
au démarrage × 1,3, fin de phrase = 600 ms de silence continu. Deux
défaillances certaines en rue : un seuil figé devient faux dès qu'on change de
rue, et « 600 ms de silence » n'arrive jamais — donc la fin de phrase n'arrive
jamais. Ça peine déjà en atelier calme.

Remplacement par une **VAD neuronale** (§6 bis de l'étude, candidats sourcés
le 13/09) : **Silero par défaut** (MIT, ONNX, chemin ARM documenté) contre
**TEN** en challenger, départagés sur NOTRE corpus. Découverte qui rend ça
quasi gratuit : **onnxruntime 1.30.0 est DÉJÀ dans l'image vision** (apporté
par piper) — aucune dépendance nouvelle. Pièges notés : bloc d'entrée fixe
(512 éch. pour Silero contre nos trames de 480 → ré-assembleur à tester à
part, erreur silencieuse sinon) et versions à figer.

⚠️ **Correction de David** : la direction d'arrivée du son est un **bonus de
confiance, JAMAIS un veto** — le faisceau se verrouille sur la source
dominante, pas sur la parole. En filtre, elle fabriquerait une régression
déguisée en amélioration. Et le **socle plastique** dégrade probablement la
discrimination spatiale : à mesurer par le corpus, pas à débattre.

**MICRO CHANGÉ le 26/08** : le ReSpeaker XVF3800 est reçu et **testé au banc
sur le Pi 5** — driverless, 16 kHz natif, 21 dB de SNR à 3 m sur le robot au
repos, `faster-whisper base` transcrit à RTF 0,39, **et la DoA fonctionne**
(`xvf_host` installé dans `~/xvf_host/` sur le Pi vision, build `rpi_64bit`).
Détail et pièges dans `hardware/overview.md` §Microphone.

Ce que ça change pour D0 :
- **FAIT le 26/08** : l'alias `casque_mic` d'`/etc/asound.conf` pointe sur
  `CARD=Array` (nom d'alias conservé = contrat avec `vision_config.py`, donc
  aucun code touché et `dadou_vision_ros` reste gelé), vérifié DEPUIS le
  conteneur. Alias `webcam_mic` ajouté pour garder l'ancienne captation
  disponible en comparaison A/B. Mode d'emploi et piège du bind-mount :
  `operations.md` ;
- toute mesure D0 doit **nommer le modèle Whisper utilisé** — sur la prise à
  3 m, `base` était le maillon faible, pas le micro ;
- la DoA ouvre le recoupement micro × caméra pour l'attribution du locuteur :
  prendre la valeur 1 (faisceau focalisé), **jamais la valeur 2 qui est une
  constante à 90°**, et amortir la valeur 3 (bruitée). L'azimut absolu n'aura
  de sens qu'une fois la carte fixée (offset de montage à relever).

**Support 3D — étude faite le 27/08, dessin EN ATTENTE de 8 cotes.**
`plans/supports/support-respeaker-xvf3800/README.md` (hors dépôt, Nextcloud).
Trois pièces, berceau/platine séparés. Deux résultats à ne pas redécouvrir :
le **silentbloc caoutchouc amplifierait** le bruit des servos (f0 = 159 Hz sur
30 g → +4,7 dB à 200 Hz) — mousse souple + lest, f0 = 33 Hz ; et le **câble USB
tendu court-circuite le découplage** en silence.

**Emplacement arrêté : à plat sous l'arceau d'acier en T qui enjambe la tête.**
Une première idée (verticale sur le torse) a été écartée, et le pourquoi sert :
une antenne **plane** ne résout une direction que **dans son plan** — à la
verticale, l'azimut mêle gauche/droite et hauteur, il est **indéterminé pile en
face** et ambigu avant/arrière. Pas « moins précis » : faux tout en ayant l'air
juste, comme la `value 2` constante à 90°. L'arceau lève les deux conditions
d'un coup (antenne **horizontale**, repère **fixe** — c'est la tête qui pivote
dessous) : **la DoA est préservée**, et l'anneau LED redevient un signal honnête.
En prime : rien sous la carte (air libre 360°, les ports bottom-firing sont
servis sans rien faire), câble qui ne traverse aucune articulation, point le plus
éloigné des moteurs de roues. **Risque créé** : les servos des yeux sont sur la
même barre d'acier — brider au sommet, à mi-chemin des deux, et trancher par la
mesure.

Montage **SUR le dessus de la traverse** : l'axe de la tête occupe le dessous, et
le dessus ne coûte rien en hauteur (les yeux dépassent déjà de ~15 cm, l'empilage
fait ~40 mm). Capuchon anti-pluie obligatoire, transformé en **lanterne** (fente
360°). À contrôler : que le cercle des ports acoustiques soit plus large que la
semelle du T, sinon la barre bouche un micro.

**Prochaine action : David relève les 8 cotes de la carte + le profil du T +
le dépassement des yeux au-dessus de la traverse, avec photos quadrillées.**

⚠️ Trouvé le 26/08 : **la webcam du Pi 5 était débranchée** sans que rien ne
le signale — gaze, suivi de personne ET micro de conversation à terre en même
temps. Rebranchée le jour même. À retenir pour la boîte noire du
télédiagnostic : un contrôle « caméras/micros présents » coûte zéro.

**ÉCHO MESURÉ le 26/08, ampli branché — le half-duplex devient LE verrou.**
Didier a joué sa propre voix dans sa sono pendant que le micro écoutait, à
volume MODÉRÉ (donc tous les chiffres sont des planchers) : silence −60,0 dBFS,
Didier qui parle **−10,4 dBFS**, soit +49,5 dB — et **22 dB AU-DESSUS d'un
humain à 3 m** (−32,4). L'entrée micro **écrête** (crête −0,0 dBFS, 65
échantillons saturés), ce qui achève l'espoir d'un AEC utile : un AEC exige un
chemin linéaire. Et **Whisper a transcrit Didier lui-même** (7 segments) : le
mode de panne du 11/07 n'est plus une hypothèse, il est reproductible à la
demande. Détail : `hardware/overview.md` §Echo. Ce qui était alors la prochaine
action — implémenter le gate half-duplex, sans matériel, en écoutant « une
source audio est vivante » et non « piper joue » (le récepteur HF de
l'interprète sort par le même châssis) — **est fait, cf. juste dessous**.

✅ **FAIT le 30/08** (dadou_vision_ros `9f2dd02`, spec fermée
[`etude-declenchement-conversation.md`](etude-declenchement-conversation.md)
§10). Le relevé de code avait d'abord corrigé le diagnostic : un demi-gate
existait déjà (`mic.stop()` avant de parler + purge du ring buffer, verrouillés
par `test_mic.py:175`) — le lot était donc un **élargissement**, pas une
implémentation depuis zéro.

Nouveau : `vision/audio/live_audio_gate.py` (stdlib pur, horloge injectée) qui
bloque sur **niveau**, sur **écrêtage** (indépendamment du niveau) et sur
**séquence de spectacle**, avec maintien de 1 s ; plus la **queue acoustique**
armée avant chaque redémarrage du micro. Le gate est **en amont de la VAD** —
non négociable : la calibration de la VAD est à usage unique, une sono vivante
pendant sa fenêtre empoisonnerait son seuil à vie et rendrait Didier sourd sans
rien signaler. 198 tests (176 avant), `gate=None` = comportement historique
inchangé, donc lot réversible.

⚠️ **Un défaut de la SPEC rattrapé à la revue, à retenir** : la formule
prescrite pour le canal « spectacle » bloquait aussi quand le topic n'avait
**jamais** été reçu (`None`) — Pi robot éteint = Didier sourd définitivement et
en silence. Corrigé dans `arbitration.show_audio_live()`. Règle qui survit :
**ne jamais déduire un état actif de l'absence d'information.**

**Reste hors code**, pour le protocole physique : les deux cas que seul le réel
tranche — David parle au HF pendant que le micro écoute (doit bloquer), et un
humain à 3 m reste entendu (ne doit pas bloquer). Le seuil est adossé aux
mesures du 26/08 : **à recalibrer si le gain micro change**.

**Suite : la campagne D0** (robot allumé : mesure CPU en conversation,
enregistrements rue à rejouer, calibration distance) et la **validation des
textes par David** ;
reste D3 : bouton télécommande, multi-langues, chrono latence. Verrou de
D1+ : protocole physique chat_node V2 (chantier 0). Réussite finale = grille
chiffrée du test rue D5 (§7 du plan).

## Voix de Didier (continuité ventriloquie ↔ synthèse)

Plan : [`etude-voix-didier.md`](etude-voix-didier.md) (ouvert 2026-08-26).

Problème : l'IA arrive dans les réponses, mais la voix de la ventriloquie et
celle de piper n'ont rien à voir — le personnage tombe à chaque alternance.

Constat qui structure tout (câblage relevé 26/08) : **« la voix de Didier » =
la voix de David + l'octaver**, et le **Pi ne passe pas par l'octaver** (il
entre en direct dans la mixette). D'où le principe directeur (§3, ne pas
re-trancher) : **cloner avant les filtres, unifier après** — la continuité
vient du dernier étage commun, pas du clonage.

**Suite = deux lots parallèles et indépendants :**

- **V0 — banc d'écoute**, en atelier sans modification permanente (sortie Pi →
  octaver via un pad, 6 phrases, écoute en aveugle, **test en alternance** : la
  rupture ne s'entend qu'en juxtaposition). C'est V0 qui débloque
  l'**arbitrage artistique du §5, volontairement suspendu** : cloner la voix de
  David (A) ou pousser la robotisation jusqu'à rendre la source indifférente (B).
- **V0b — Kyutai Pocket TTS tourne-t-il sur le Pi 5 ?** L'inconnue la plus
  rentable du chantier (état de l'art du 26/08) : MIT, français natif, clonage
  **zero-shot depuis ~10 s** — mais aucune mesure sur ARM n'existe. S'il passe,
  il supprime le corpus d'une heure, le GPU loué et le fine-tune. Mesurer dans
  l'ordre : tourne sur ARM ? RTF sur Pi chargé ? tenue sur un énoncé de 30 s ?

Ensuite V1 câblage permanent (aiguillage A/B sur le relais existant), V2
accordage (voix piper la plus proche + pré-transposition F0), V3 enregistrement
**au dimensionnement conditionnel à V0b**, V4 fine-tune piper (filet de
sécurité, MIT, donne le timbre pas le jeu).

Deux garde-fous de séquencement :
- **Ne rien engager en clonage avant V0** — l'octaver écrase peut-être assez
  pour que l'écart résiduel ne s'entende pas.
- **Ne pas faire enregistrer 1-3 h à David avant V0b** — 10 s pourraient
  suffire. Seul le palier minimal (quelques minutes **en personnage**) est utile
  dans tous les cas.

Deux points structurants consignés dans l'étude, à ne pas perdre : l'octaver
unifie le **timbre mais pas la prosodie** (donc la garantie s'amincit sur les
énoncés longs, exactement là où on en a besoin), et **le corpus est le plafond
du clone** — enregistrer en lisant proprement donne un clone plat à vie ; il
faut jouer, pas lire.

## Suivi de personne aux roues

CODE COMPLET, VALIDÉ EN SIM 5/5 (11/07 soir) : chaîne `/vision/person_box`
(Pi vision : azimut + HAUTEUR de silhouette = proxy de distance monoculaire,
cf. dadou_vision_ros) → `person_follower` (logique pure
`robot/move/follow_control.py` testée : deadzones, plafonds durs ABS 0,5/1,0
bornant même les paramètres, slew, zéro franc sur perte de cible < 600 ms et
sur OFF, marche arrière interdite par défaut) → `cmd_vel_follow` → twist_mux
**prio 20** (remote 100 > web 50 > follow 20 > anim 10, contrat gelé
re-testé). Toggle topic `follow` "on"/"off", **OFF par défaut**, lancé À LA
MAIN, PAS dans le bringup. Validé sim : T1 désactivé=zéro mouvement,
T2 avance+rotation vers la personne (odom confirme le déplacement gz), T3 la
télécommande écrase et le suivi reprend, T4 perte=zéro franc puis silence,
T5 OFF=zéro unique. Code DÉPLOYÉ sur les Pi au déploiement complet du 12/07
(rsync Ansible + sentinelles).

**SIM-ONLY** : usage réel conditionné au test scénique au sol (chantier 1)
PUIS protocole caméra roues hors sol (`direction_sign` azimut→rotation
inconnu, comme l'était celui du gaze).

## Gaze V1 (cou + yeux) + arbitrage actionneurs

> ⚠️ **RECTIFICATIF 2026-09-14 — l'argument ci-dessous est FAUX.** David a établi que la
> caméra est **fixe sur le buste** (support devant la bouche) : elle ne tourne pas avec le
> cou. Il n'y a donc **aucune boucle fermée** et rien d'auto-validant. Ce que le protocole du
> 12/07 a réellement validé, c'est ce que David a **vu** en scène — ce qui suffit pour le
> signe, mais pas pour le gain. Conséquences consignées dans le code le même jour :
> `gaze_control.py` (le `gain=20` n'est pas « conservateur », c'est **l'étalonnage** azimut→
> angle réel, et il tombe juste : ±37° pour un champ caméra de ±38,5° — **ne pas le monter**)
> et `gaze_follower_node.py` (justification de `direction_sign` réécrite).
> **Bonne nouvelle en contrepartie** : l'azimut est déjà dans le repère du châssis, donc
> `person_follower` le consomme brut, sans transformation — le suivi roues est géométriquement
> sain. C'est un acquis à ne pas casser en motorisant un jour le support caméra.

**Gaze : PROTOCOLE CAMÉRA FAIT ET VALIDÉ le 12/07** sur le vrai robot, David
en scène. Résultats gravés en défauts du node : cou `direction_sign=+1`
(~~boucle fermée AUTO-VALIDANTE : la caméra est sur la tête, l'azimut converge
vers 0 — un mauvais signe aurait divergé en butée~~ — voir rectificatif ci-dessus),
amorti `ema_alpha=0.15` /
`slew_max=1.5` (les valeurs initiales 0.4/3.0 oscillaient : retard de phase
EMA×2 + slew + rampe servo), YEUX ajoutés (2e instance de GazeControl,
gain 49 = plein débattement 1-99 comme les séquences, `eye_direction_sign=-1`
— montage MIROIR du cou, validé visuellement). Toujours lancé À LA MAIN (pas
dans robot_bringup), toggle topic `gaze` "on"/"off".

**Arbitrage amont FAIT le 12/07** (lots A+B de
[`etude-arbitrage-actionneurs.md`](etude-arbitrage-actionneurs.md), contrat +
validation §8) : `animations_node` publie l'état latché `animation_state`
(nom ou "", time=remaining_ms, TRANSIENT_LOCAL des DEUX côtés — un abonné
volatile raterait le latch), le gaze et le chat (Pi vision, module pur
`vision/ai/arbitration.py`) se TAISENT quand une séquence a la main, avec
PÉREMPTION façon deadman (remaining+2 s) si animations_node meurt en pleine
séquence. Chat : rattrapage idle() après abandon STT (fini le visage coincé
sur « reflechit ») + stop ciblé (fini le stop GLOBAL qui tuait la séquence en
cours). Validé en sim 5/5 (latch, silence pendant séquence — contre-preuve
sans piste neck —, reprise, redémarrage en cours de séquence, péremption sur
kill). **DÉPLOYÉ ET VÉRIFIÉ sur les deux Pi le 12/07** : contrat joué en réel
("" latché au repos → "parle" time=4999 pendant une séquence de 5 s → "" au
retour), module arbitration + câblage péremption confirmés dans l'install du
Pi vision. Arbitrage aval par source différé (étude §5.3).

**Reste** : vérif VISUELLE comportementale à la prochaine session robot —
gaze ON pendant une séquence (la tête ne doit plus trembler), et le gate chat
en conversation réelle (avec le chantier 0).

## Danse en cadence (chanson + gestes à la con)

**Ouvert le 01/10/2026** sur une question de David (« faire danser Didier en déambulation,
chorégraphie pas forcément parfaite mais le tempo est crucial pour l'effet comique »).
Étude complète (code, docs, web) : [`etude-danse.md`](etude-danse.md). **Rien d'acté** :
les 5 questions du §6 attendent David.

Ce que l'étude établit :
- Le moteur existe (`Track` + `animations_node` + tick 20 Hz + arbitrage `animation_state`).
  Une danse = une séquence JSON ordinaire **compilée sur PC** à partir de figures écrites
  en mesures/temps et d'une grille de beats librosa. Aucun changement embarqué au lot 1.
- Le calage tient sous ±40 ms **si le démarrage du son est répétable** — et ça, personne
  ne l'a jamais mesuré (`SoundObject.play` = `default_timer()` avant le fork du
  `Process`, puis `playsound`/GStreamer). C'est la mesure qui décide (lot D2, après dégel).
- Les bras sont lents (ASME 380 kg·cm : 1 s/60° à 12 V, 0,5 s/60° à 24 V — tension du
  rail à relever) : ~30° par temps à 120 BPM. Le rythme = cou + yeux + flash visage
  (métronome visible) ; les bras tombent sur le temps fort. Anticipation calculée par le
  compilateur pour que le servo ARRIVE sur le temps.
- **Le cas visé (précisé par David le soir même) : danser EN SUIVANT** — suivi de personne
  + odométrie en service, roues comprises (étude §7 bis). `twist_mux` ne superpose pas deux
  sources (follow 20 > anim 10) : la cadence des roues se compose **dans** `follow_control`
  (zigzag borné, gain linéaire ≤ 1, freeze sur le temps fort), invariants gravés en tests.
  L'odométrie calibre le retard roues et contrôle l'amplitude, mais 10 cibles/tour = 80 à
  300 ms entre impulsions à 0,25 m/s : boucle par MESURE, pas par temps. Hérite de tous les
  verrous du suivi au sol. Se développe en sim dès maintenant (lot D4).
- Une piste `wheels` de séquence (prio 10) ne passe jamais pendant le suivi ou la conduite,
  et passerait au moment où ils se taisent : elle ne sert qu'aux danses **à l'arrêt** (D5).
  Amplitude des bras plafonnée, mesure de courant servos avant un essai long,
  `time.monotonic()` avant le réel.
- Droits : SACEM par l'organisateur (relevé de programme), droits voisins non tranchés
  pour la rue, pas de « synchro » hors audiovisuel — rien de bloquant techniquement.

**Suite** : D0 + D1 (PC + sim, sans robot — l'un des rares chantiers qui avance pendant
le gel) ; D4 danse en suivi en sim ; D2 mesures réelles au dégel ; réel après le test
scénique et les verrous du suivi.

## Répétition simulée — la rue, les bugs, le casque

**Étude écrite le 2026-10-07** : [`etude-repetition-simulee.md`](etude-repetition-simulee.md),
PROPOSITION, rien d'acté. Née de la demande de David du 07/10 (s'entraîner dans un
environnement urbain simulé, bugs déclenchés, histoire de la mauvaise foi, casque
Bluetooth) et de la séance d'intention des 30/09–01/10 dont elle ne cite que les
conclusions publiables (première marche = trajet vers le Hangar à Bananes, bugs =
routines de sécurité, Didier amoureux de tout, triangle, boss débordé).

Ce qui est ferme :
- **Le banc PC du 13/09 est la base** (vrai code Pi 5 sur le PC, casque BT déjà via
  PipeWire, corps Gazebo, domaine 43). Il manque la rue, le David virtuel, le régisseur
  de pannes, le persona mauvaise foi, l'enregistrement.
- **Gazebo Harmonic** (recherche du 07/10) : les `<actor>` sont visibles par la caméra
  RGB mais **sans physique ni pilotage dynamique documenté** → David = un **modèle
  piloté** à silhouette humaine (stick gauche), les acteurs servent de passants
  scriptés. **Aucun monde urbain prêt** pour Harmonic (citysim disparu, collection
  GPL-3.0 à ne pas embarquer) : la rue se construit à la main.
- **Le catalogue des erreurs** (étude §2) relie chaque panne réelle vécue (deadman, saut
  de cible, visage figé, servo mort, STT « Astérix », latence, reboot 40 s, sourd à
  3 m, bordure, manette) à son injection sim et à sa version jouée. Deux fusions à
  retenir : **le saut de cible EST la lubie**, **le reboot EST le prétexte B5** (EMI).
- `ros2_fault_injection` (MIT, Jazzy, 09/2026) existe pour Twist/Odometry ; nos types
  (PointStamped, StringTime, Image) demandent un relais maison ; kill via docker comme
  le télédiagnostic.

**Lot R3 « Chantiers » — FAIT le 14/10** (spec §13 de l'étude, implémentation
déléguée Opus/Sonnet sur spec fermée) : monde `chantiers.sdf` (Nefs → Mail des
Chantiers → quai des Antilles → **grue Titan grise**, 1 247 m réels compressés à
~145 m, Loire à droite, Hangar à Bananes à gauche — ⚠️ le relevé web a renversé
l'hypothèse : la grise est à la pointe ouest, la jaune au parc), **30 objets =
30 lubies** (POI à champ `lubie`, déclencheur `t: poi` tiré à la graine avec
`p: 0.4`, type `lubie` = consigne sur `chat_instruction` + `route_speed 0` →
Didier s'arrête devant l'objet, fermeture au fader/page ou à l'expiration),
**20 bugs réels** à `t: random` (dont 5 **pannes de conversation** publiées sur
`rehearsal/chat_fault` et exécutées par chat_node : latence Pi, contresens STT,
sourd, muet, hallucination whisper), persona **`mauvaisefoi`** (dépôt vision),
topics de régie du chat (`chat_text` clavier, `chat_instruction`,
`chat_transcript`), **page scène** `/scene` du pont web (caméra + visage LED +
conversation en direct + clavier + route/vitesse/séance si `REHEARSAL=true`).
Vérif : `validate-rehearsal-chantiers.sh` (V-R3 technique) + tests gravés dans
les deux dépôts. Textes (lubies, persona) = brouillons à valider par David.

**Revue adversariale (Opus) FAITE le 14/10**, corrigée le jour même : STOP
avant START n'annule plus la séance et START après la fin la rejoue (reset,
même graine) ; **fermeture d'une lubie au fader** = fin immédiate de la lubie
(vitesse externe ≠ de plus de 0,05 → `fault_stop closed_by: fader`, consigne
levée, cible `speed` libérée — sinon le final Titan pouvait sauter) ; la
vitesse rendue après une panne est **la dernière vitesse externe** (fader ou
page), plus un `restore` qui doublait la vitesse ; phantom = cible propre,
sans `pass` ; POI franchi avant START journalisé `poi_enter_ignored` (le
script et la page doivent envoyer START avant `route on`) ; tests du NODE
régisseur avec rclpy factice + noms de topics gravés côté vision (9 mutations
qui passaient inaperçues). Vérifié dans la sim : page `/scene` + vidéo +
visage servis, **bout en bout** texte tapé → persona mauvaisefoi → réplique
au transcript en 1,6 s (image vision rebâtie : il lui manquait `aiohttp`).

**Points ouverts, connus et acceptés (14/10)** :
- ⚠️ **Le CLI `ros2` perd des messages sur le PC de dev** (découverte DDS,
  erreurs multicast avec ~50 conteneurs) : la page et la télécommande
  (publieurs longue durée) passent, `ros2 topic pub -1` non — V-R3 envoie
  des salves et juge par l'effet (cf. operations.md).
- Si le **boîtier de faders ré-émet `route_speed` en continu**, il écrase
  l'arrêt de chaque lubie côté route_driver (dernier message gagne) : à
  vérifier à la première séance avec la vraie télécommande ; la page n'envoie
  qu'au changement.
- `chat_instruction` est **un seul emplacement** partagé page/régisseur : la
  fin d'une lubie (`""`) efface une consigne posée à la main ; péremption
  120 s silencieuse.
- `kill route_driver` pendant une lubie : il renaît à la vitesse du launch
  (0,5) → Didier roule pendant que la consigne le dit arrêté.
- La **page diag de chat_node** (`diag_port`, OFF par défaut) montre le vrai
  texte STT sous `garble`/`deaf` : ne pas l'ouvrir pendant une séance.
- `MicCapture` n'est pas sûr entre threads (course préexistante sur le
  toggle OFF ; le callback `chat_text` ne touche plus au micro).
- Le `feed` (transcript) est diffusé aux clients non authentifiés, comme
  `state` ; sans enjeu en sim.

Prochaine action : **V-R3 séance** (David au casque, page scène, persona
mauvaisefoi — textes des lubies et du persona à valider) et **vérification
en sim d'I1** (mouvement à la voix, CODE FAIT le 22/10 + revue adversariale
corrigée le même jour — cause latchée `route_state_cause`, « stop » toujours
republié, garde domaine 43 côté vision ; étude §13.11, limites listées là) ; puis **I0** (`etude-interaction` §9 : état de
mission).
Verrous : aucun côté robot. Les verrous roues (test scénique, W1,
coup-de-poing) ne bougent pas : la sim ne qualifie rien côté sécurité.

## Pistes en veille (pas urgentes, pas oubliées)

- **TRONC ARTICULÉ (tangage + roulis ±10-15°) — étude du 2026-10-25, rien d'acté** :
  [`etude-tronc.md`](etude-tronc.md). Recommandation : cardan + **2 vérins 24 V à
  potentiomètre, autobloquants** (100 € pièce, 300 N à 40 mm/s, lus le 25/10), commandés par
  le MDDS30 de rechange + un RP2040 ; ressorts de centrage en appoint ; respiration par un
  servo à part sur le PCA9685. Écartés : essuie-glaces (jeu, prix), servos et moteurs sans
  balais (réversibles : le buste tombe à la coupure), câbles/colonne souple (aucune preuve
  à 10-20 kg), pneumatique. **Cible = la v2 (concept triangle)** : ses 3 ancrages de
  vérins sous le cardan sont motorisés (3 vérins 100 mm à 110 €, étage élastique en série,
  ancrage bas z445→z468), schéma `pictures/tronc-v2-verins.svg`. ⚠️ Rouvre la décision
  « vérins à gaz passifs » du 16/07 — à trancher. **Révision du 25/10 (soir), §10 de
  l'étude** : vérins électriques trop lents pour l'expressivité (~25°/s contre 60-104°/s
  pour un humain détendu) → **2 moteurs réversibles rapides sur les axes du cardan +
  ressorts de centrage** (recommandé), ou vérins à gaz + 3 câbles (option, apporte la
  hauteur/respiration). **A RETENUE par David le 25/10** (mouvement > respiration) :
  schéma `pictures/tronc-v2-moteurs.svg` (colonne fixe, courroies 1:4, 4 ressorts,
  GO-M8010-6 ou Robstride 03). Reste : mesurer le bruit d'un moteur au banc.

- **COBOT DU COMMERCE SUR DIDIER — évalué le 2026-09-26, ÉCARTÉ.** Né d'une
  annonce AliExpress (bras collaboratif 6 axes, 5 kg, affiché **90,69 €**) que
  David a fait instruire « pour comprendre ». ⚠️ **Les 90,69 € sont un
  ACOMPTE** — le titre dit « prix d'acompte », la variante s'appelle
  « 5KG (Deposit) ». Le solde n'est **jamais** un champ de la page : vérifié,
  la fiche ne rend ses prix qu'en JavaScript (le HTML servi est une coquille),
  l'API `aeproductsourcesite` est fermée, l'annonce n'est pas indexée. Sur ce
  type d'annonce le prix s'obtient **par message au vendeur**, pas par lecture.
  **Ordre de grandeur réel** (comparables relevés le 26/09) : **10 356,82 €**
  (Acctek 5 kg / 922 mm, prix complet sur AliExpress DE), **8 100 $** (AUBO i5,
  Alibaba, à l'unité), jusqu'à 23 000 $ chez d'autres fournisseurs ⇒ **8 000 à
  15 000 € départ Chine**, + TVA 20 % et droits (~4,5 %) prélevés **sur le
  solde**, pas sur l'acompte.
  **Pourquoi c'est écarté — et ce n'est pas le prix** (datasheet AUBO i5s,
  modèle représentatif de la classe 5 kg) :
  ① **pic 2000 W** (200 W en moyenne) contre un **BMS Daly 30 A** sur 24 V,
  soit **720 W** au maximum que le pack laisse passer — via onduleur, ce pic
  appelle **~98 A** côté batterie. Pour situer : il vaut **4× toute la
  motorisation** du robot (2 × 250 W) ;
  ② l'alimentation est **100-240 V AC** ⇒ onduleur dans la caisse. Or la caisse
  **est l'enceinte acoustique** (`hardware/overview.md`) et le chantier
  ronflement a conclu le 30/08 « une seule batterie, **pas de référence
  secteur** » : l'onduleur rouvrirait exactement le verrou qu'on vient de
  fermer. **C'est rédhibitoire indépendamment de l'énergie** ;
  ③ **+39 kg** (bras 24 kg + control box 15 kg, 390×370×265 mm) sur un robot de
  50 kg — ce n'est plus adapter Didier, c'est refaire châssis, alim et
  motorisation autour du bras.
  **Ce qui passait, et qui surprend** : le **logiciel** (driver ROS 2 officiel
  `AuboRobot/aubo_ros2_driver`, plus un fork communautaire à branche Jazzy ; le
  cobot embarque son propre contrôleur temps réel, donc le tick 20 Hz de Didier
  suffit à lui envoyer des poses) et la **stabilité statique** (bras tendu avec
  5 kg au bout : ~137 N·m de moment de renversement ; à 89 kg de masse totale
  il ne faut qu'une demi-base de 16 cm). Le **dynamique** n'est pas instruit
  (3,4 m/s en bout d'outil, freinage du robot, scène en pente). Et la
  certification cobot **suppose une base FIXE** : cobot + base mobile + public
  sort du cadre ISO/TS 15066.
  ⭐ **La leçon réutilisable est un critère d'achat** : pour un bras sur Didier,
  ce qui décide n'est pas la charge utile mais l'**alimentation native**.
  Filtre à appliquer avant même de regarder un prix : **48 V DC** (pas de
  secteur, pas d'onduleur, pas de ronflement), pic **< 300 W** (le BMS 30 A est
  le plafond), masse **< 5 kg**.
  **Déclencheur de réveil** : un bras DC natif sous 300 W de pic — ou une
  refonte du pack et du BMS décidée pour une autre raison.

- **INVENTAIRE DU STOCK DE COMPOSANTS** — *3 vidéos dépouillées le 03/09* :
  `docs/hardware/inventaire-stock.md`. Motif du chantier : en deux heures, le
  stock avait démenti deux fois la liste de courses — les 74AHCT125 (achetés
  pour les rubans LED, ils règlent la piste *level shifter* laissée ouverte par
  l'incident visage du 13/07) puis les **PC817 DIP-4**, trouvés en quantité
  alors que l'étude s'apprêtait à les faire racheter. Acheter ce qu'on possède
  déjà coûte de l'argent, du délai, et **3,60 € de droits par catégorie** depuis
  juillet 2026.
  **Ce qui est fait — PASSE COMPLÈTE (03/09)** : dépouillement de **427 des 650
  images** d'une vidéo d'atelier de 10 min 50 s (muette) + une photo, en deux
  passes (130 images les plus nettes, puis les 297 restantes en lots temporels
  contigus — une sérigraphie illisible sur une image l'est parfois sur sa
  voisine). Table Markdown par famille : désignation, référence *lue*, boîtier,
  quantité minorante, repère, confiance. Le boîtier est bien la colonne qui
  décide. La nomenclature de l'odométrie y est confrontée ligne à ligne (§1.1) :
  4 lignes sur 12 deviennent des vérifications d'atelier, et le **RP2040-Zero**
  mérite un examen (des RP2040 en stock, mais aucun n'est un remplacement direct
  du plan de plaque). Deux pièces touchent d'autres chantiers : un **isolateur
  audio à transformateurs** (ronflement secteur) et un **BNO055 neuf**.
  **Plan de marquage et de rangement** : `docs/hardware/rangement-atelier.md`
  (établi 03/09, étiqueteuse Marklife P15).
  **DEUXIÈME ET TROISIÈME PASSES — le soir du 03/09**, David a refilmé les zones
  manquantes : une vidéo de **rattrapage** (7 min 39 → 161 images, préfixe `v2:`)
  et une vidéo **ciblée sur la boîte JST** (39 s → 31 images, préfixe `jst:`).
  Ajout méthode : filtre de **nouveauté par dHash** (un panoramique lent repasse
  sur la même scène pendant plusieurs secondes — sans ça on paie plusieurs fois
  la même étagère). Sur les JST, **deux agents aux lots recouvrants concordent**.
  **Ce que ça a levé** : ① la **boîte JST** — il existe bien des boîtiers
  **4 points (~25-35)** et **2 points (~40-55)** plus les embases mâles, donc la
  quantité des 3 lignes d'odométrie est couverte ; ② **`1N5819`** lu sur bande
  → rien à acheter ; ③ **`Teensy 3.2`** (version enfin lue) ; ④ le **bac de
  résistances existe** — ~20 sachets, **plusieurs centaines** de pièces ; ⑤ les
  « petites cartes bleues » sont des **cartes MCU/RP2040**, pas des alims.
  **Ce que ça n'a PAS levé, et pourquoi c'est instructif** : ⓐ **le PAS** — ni
  celui des JST (XH 2,5 vs Dupont 2,54 : indiscernables, et deux tailles
  cohabitent dans le même compartiment) ni celui des **borniers verts**, parce
  qu'**aucune des trois vidéos n'a jamais montré une règle dans le cadre** ;
  ⓑ les **valeurs** des résistances — 7 lisibles sur ~20 sachets, rubans tournés
  vers le fond, coupés par le cadre ou sous un doigt ; ⓒ les **céramiques**,
  toujours jamais filmées ; ⓓ tous les **contenants scellés**, refilmés fermés.
  **Leçon de tournage consignée** (§4) : la netteté ne suffit pas, c'est
  l'**orientation de l'étiquette** qui décide — plan fixe de 2 s, étiquette face
  caméra, règle dans le cadre dès qu'un pas compte. **Et ce qui est dans une
  boîte fermée ne se filme pas, ça s'ouvre.**
  ⚠️ **Garde-fou de synthèse ajouté** : les agents sont tenus aveugles au fichier
  (sinon ils « voient » ce qu'on leur suggère), donc **la synthèse doit
  confronter leurs rapports aux tables avant d'écrire**. Ça a évité de présenter
  comme neuf ce qui était acquis (alim USB, `DS3231`, `PCA9685`, Nano ELEGOO) et
  surtout deux **régressions** : les agents v2 ont dit « Cytron illisible » et
  « PCA9685 non lu » alors que la passe 1 les avait **lus** (`Cytron MDDS30`).
  Une passe plus récente n'est pas une passe mieux informée.
  **Suite, dans l'ordre** : (0) **ouvrir ce qui n'a jamais été ouvert** — colis
  scellés, boîtes Cytron, sachets ESD : c'est le seul travail qui *augmente*
  l'inventaire, et la vidéo n'y peut plus rien ; (1) **le test JST à 10 s** —
  enfoncer un contact de chaque casier dans un boîtier 4 points : s'il verrouille,
  trois lignes de commande tombent ; (2) **le pied à coulisse** sur les borniers
  verts ; (3) **refilmer le bac de résistances sachet par sachet**, ruban face
  caméra, pour chercher les 1,5 kΩ et 10 kΩ.
  **Bonne surprise structurelle** : tous les bacs ont un **porte-étiquette moulé
  d'origine, tous vides** — rien à acheter. Et le tri par famille existe déjà à
  la maille du bac : il n'y a quasiment pas de retri à faire, seulement à
  adresser.
- **INVENTAIRE DU ROBOT (le filmer)** — ouvert le 03/09, **PREMIÈRE PASSE FAITE
  le soir même** : `docs/hardware/robot-embarque.md` (vidéo de 3 min 05 s, 139
  images lues sur 185, 14 agents). Motif d'origine : le croisement de
  l'inventaire du stock avec les études avait déclaré « à acheter » deux pièces
  qui sont **sur le robot** — ReSpeaker XVF3800 et routeur 4G ; les trois
  gisements (stock / robot monté / pièces CAO) n'avaient jamais été posés comme
  tels. **Acquis de la passe** : références enfin lues du routeur
  (`TELTONIKA RUT9…`, qui manquait à `overview.md`), du driver roues
  (`SmartDrive 4.0 / DS40B`), du récepteur HF (`Shure BLX4`, 662-686 MHz), de
  l'« octaver » (**`TC HELICON`**, molette `GENDER` — ce n'est pas un simple
  octaveur, cf. chantier voix) et de toute la chaîne audio (Focal ICU S70,
  ampli Focal classe D, mixette `t.mix MicroMix 2USB`).
  ⚠️ **La vidéo montre le robot EN PIÈCES** : disque d'odométrie **déposé au
  sol**, pignons/jantes/chaîne démontés, panneaux de torse retirés → le test
  scénique au sol suppose d'abord un remontage et une revérification.
  **Restes, par ordre** : ① ~~étiquette `CHARGES LEAD ACID`~~ **RÉSOLU le soir
  même** — David a sorti l'appareil et l'a photographié : **Victron Blue Smart
  24 V/5 A**, `CHARGES LEAD ACID **OR LI-ION**`, il l'a basculé de `normal` en
  `li-ion` (`docs/pictures/charger-victron.jpg`). L'alerte tombe ; il reste une
  question de **justesse de charge** et une **incohérence dans `overview.md`**
  (« 18650, 8×5 » : un 8S NMC monte à 33,6 V, incompatible avec un chargeur
  24 V) → relever la tension réelle dans VictronConnect (Bluetooth, rien à
  démonter), compter les cellules en série, lire la chimie, vérifier le BMS ;
  ② demander pourquoi le disque d'odométrie est
  déposé ; ③ **compter les dents des pignons** (transmission par CHAÎNE, jamais
  documentée — sans le rapport de réduction l'odométrie sortira des distances
  fausses) ; ④ **refilmer la tête**, quasi absente des plans (donc ReSpeaker non
  observé, ce qui ne prouve rien). Post-mortem de l'erreur d'origine :
  `docs/hardware/croisement-etudes.md` §2.
- Calibrer `max_wheel_speed` réel (m/s à consigne 1.0) — mesurable à la
  caméra, distance/temps. Débloque le plafond de vitesse distant (web §2.3).
- Action ROS 2 `PlayAnimation` (les pistes roues des séquences passeront par
  cmd_vel_anim).
- Source unique des séquences JSON (côté robot, la télécommande interroge par
  service).
- Affiner l'URDF depuis les plans FreeCAD (~/Nextcloud/dev/didier/plans).
- Quirk latent à vérifier caméra un jour : en legacy, une paire [0,0] de
  séquence passe par update_cmd(0,0) → PWM au plancher MIN_PWM=5000 (rampage
  lent possible).
- Batterie : aucun capteur câblé — parqué vers le chantier élec (cartes PCB),
  décision télédiagnostic §8.
- ~~Micro réseau~~ — **SORTI DE LA VEILLE** : ReSpeaker XVF3800 acheté
  (66,39 €), **REÇU et testé au banc sur le Pi 5 le 26/08** (driverless UAC 2.0,
  16 kHz natif, 21 dB de SNR à 3 m, Whisper transcrit). Mesures et restes à
  faire : `hardware/overview.md` §Microphone. **DoA testée le 26/08 aussi**
  (`xvf_host`, build `rpi_64bit`). Restent : l'ÉCHO entier (half-duplex à
  implémenter, c'est ce qui a fait couper chat_node le 11/07) et le montage
  (découplage, ports acoustiques VERS LE BAS, offset d'azimut) — un chantier
  CAO à part entière.
- Détection d'obstacle (lidar 2D) — RPLIDAR C1 repéré (68,99 €) et contraintes de
  conception consignées dans `hardware/overview.md` §Distance & obstacle sensing
  (2026-07-13, RIEN acheté). Le trou n'est PAS la distance à la personne (déjà
  résolue par la hauteur de silhouette) mais l'obstacle qui n'est pas la personne.
  Points clés : pas besoin de 360° (arc AVANT suffit, secteur occulté à masquer),
  plan de scan BAS, barrière d'obstacle **appliquée EN LIGNE** sur le Pi 4 dans la
  chaîne cmd_vel, CPU négligeable hors nav2. Pas avant la priorité 1 (test au sol) :
  c'est lui qui dira si l'opérateur au deadman suffit.
  ⚠️ **Argument corrigé le 27/08** : cette ligne disait « jamais sur le Pi vision —
  une sécurité qui dépend du wifi n'en est pas une ». Prémisse FAUSSE : une fois
  correctement câblé, **les deux Pi sont en RJ45 sur le routeur embarqué, seule la
  télécommande est en wifi**. Ce qui compte n'est pas le média mais **la manière de
  tomber** : un garde-fou qui est un FILTRE en ligne est fail-safe (on le tue, la
  chaîne casse, le deadman met les zéros en 400 ms) ; un garde-fou qui se contente
  de PUBLIER un veto ne l'est pas (on le tue, aucun veto n'arrive jamais, et le
  robot cesse de voir les obstacles **en silence**). Règle qui survit : **exiger un
  battement de cœur positif** (« vivant et voie libre »), jamais déduire la
  sécurité de l'absence de veto.
- Caméra CSI (nappe) à la place de la webcam USB — module IMX219 130° repéré et
  critères de tri consignés dans `hardware/overview.md` §Vision & camera
  (2026-07-13, RIEN acheté). Gain réel : la webcam plafonne à 16,7 fps alors que
  MediaPipe ne prend que 24 % de CPU. Trois coûts à ne pas oublier : la webcam
  EST le micro de chat_node V2 (→ micro USB à acheter), la nappe FPC traverserait
  le cou mobile (fatigue mécanique), et `cv2.VideoCapture` ne voit pas une CSI
  sur Pi 5 → libcamera/Picamera2 dans le conteneur vision. Ne pas lancer avant
  les priorités 0 et 1.
  **31/08 : un ESSAI devient possible sans rien décider.** Une carte OV5647 5 MP
  à objectif M12 vissé était sur l'étagère (15 broches) ; nappe **SC1129
  Standard–Mini 300 mm commandée ×2** (Gotronic, 2,95 € pièce — la 2ᵉ est la
  rechange : un FPC casse au connecteur en donnant une panne *intermittente*).
  Ce que l'essai tranche, et rien d'autre : libcamera monte-t-il dans le
  conteneur vision, quelle latence, et **quel FOV réel** (l'objectif paraît très
  bombé — si fisheye, la correspondance boîte→cap de `person_follower` cesse
  d'être linéaire ; le M12 vissé rend ça réparable pour ~5 €). Il ne tranche PAS
  l'achat : l'OV5647 reste le capteur écarté sur la basse lumière.
  Protocole : compter les contacts (15 / 22), `rpicam-hello --list-cameras`,
  puis FOV au mètre ruban (2·atan(L/2D)) — **webcam USB laissée branchée**, elle
  est le micro. À noter : le coût « micro perdu » s'allège, le ReSpeaker XVF3800
  est reçu et testé au banc (voir plus haut) — mais son montage et l'écho
  restent entiers, donc ce n'est pas encore une porte ouverte.
  **02/09 : emplacement choisi + module mesuré, le support CAO est recoté.**
  L'emplacement voulu : le bout de la plaque blanche imprimée sous la tête
  (2 trous libres). Module photographié sur la feuille millimétrée : carte
  ~36 × 36, entraxe des 4 trous **29,0 × 28,7 mm** — le `.scad` de
  `plans/supports/support-camera-csi/` (conçu pour l'IMX219 25 × 24 jamais
  acheté) est recoté, STL régénérés (commit plans f1fe038). Découverte
  bloquante : le **connecteur FFC est côté objectif** (bord haut), cas non
  couvert par la conception — le capot doit être échancré avant impression.
  Débloquant : 6 cotes au pied à coulisse, listées dans le README du support.
