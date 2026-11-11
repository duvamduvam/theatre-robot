# Visage LED glitché « comme deux signaux entrelacés » dès le démarrage

- **Date/contexte** : 2026-07-13, ~00h15-01h15, atelier. Constaté par David au
  boot du robot ; présent en continu, surtout visible sur l'expression du
  visage. Impression de « deux programmes lancés en même temps ».
- **Symptôme** : le visage bascule/papillote entre deux motifs, pixels
  aléatoires, dès le démarrage et en continu. Mesure caméra (Creality sur PC,
  analyse frame par frame) : clignotement chaotique des trois zones (yeux,
  bouche), aucune stabilité > 66 ms, alors que l'expression `default` doit
  tenir chaque frame plusieurs secondes.
- **Traces** : captures `glitch2/3.mp4` (session), robot.log RAS (aucune
  erreur — la corruption est sous le niveau applicatif).
- **Investigation** (dans l'ordre, tout écarté factuellement) :
  1. Deux programmes ? Non — un conteneur, un `ros2 launch`, un processus par
     node, aucun doublon dans `ros2 node list`.
  2. Éditeurs de `face` : seulement `animations_node` + `web_bridge` ;
     `chat_node` bien coupé. Un seul message `face` au boot.
  3. Conflit PWM audio (GPIO18 = PWM0 partagé avec l'audio analogique) : non —
     `snd_bcm2835` absent, aucune carte son.
  4. Chevauchement zones LED : non — visage 0-511, corps 513-673.
  5. **Corrélation décisive** : corps en `devil` (statique, ~1 rendu/s) →
     quasi stable ; corps en `chase` (20 rendus/s) → chaos. La corruption est
     proportionnelle au nombre de trames envoyées.
  6. Test A/B : réintroduction du sleep Blinka dans `FastNeoPixel` sur le Pi →
     **glitch disparu instantanément**, chase active (pire cas), confirmé œil
     + caméra (zones stables, comptes de pixels 3× plus hauts = visage entier).
- **Cause** : `FastNeoPixel` (déployé le 2026-07-11) supprimait le
  `time.sleep(~31 ms)` post-`show()` du driver Blinka en pariant que le C de
  `rpi_ws281x` attend seul la fin du transfert DMA. Faux en pratique (Pi 4,
  rpi-ws281x 5.0.0) : sans cette attente de fin de trame, la trame suivante
  part trop tôt, le ruban latche en cours d'émission et interprète la suite
  comme une nouvelle trame → deux « signaux » entrelacés.
- **Remède (2 temps — le 1er a échoué, instructif)** :
  1. Tentative « retour au neopixel stock Blinka » : ÉCHEC — ruban quasi noir,
     2 pixels égarés, AUCUNE erreur (node vivant, logs normaux). La résolution
     de backend de Blinka est cassée dans le conteneur (script de test stock
     suspendu > 2 min). C'est la raison d'être — non documentée jusqu'ici —
     de l'écriture vendorisée de FastNeoPixel (accès direct `_rpi_ws281x`).
  2. Remède FINAL : `FastNeoPixel` conservé (écriture vendorisée) avec le
     sleep de fin de trame RÉTABLI. Le tick global reste à 20 Hz :
     lights_node s'auto-limite (show bloquant ~31 ms), les autres nodes ne
     sont pas affectés. Au passage : keyframes de l'expression `default`
     recalées sur la sémantique « affichée jusqu'à t » (les micro-mouvements
     étaient devenus des affichages de 2 s depuis le fix Track du 11/07).
- **Prévention** : test AST inversé (le sleep de `_fast_neopixel_write` est
  désormais OBLIGATOIRE), commentaires bloquants dans `fast_neopixel.py`,
  `lights_node.py` et `robot_static.py` ; toute optimisation du chemin LED
  repasse par une validation caméra (mesure frame par frame, pas l'œil seul).
  Un ruban noir SANS erreur logguée = penser au backend Blinka (stock cassé
  dans le conteneur).
- **Résiduel connu (hors incident)** : quelques ratés épars subsistent même à
  ~1 rendu/s — interférences électriques sur le fil de données selon David
  (« ça a toujours fait ça »). Piste matérielle (level shifter 3,3→5 V,
  longueur/blindage du fil) à traiter un jour côté hardware.
  **MàJ 2026-09-02 : le composant est déjà à l'atelier.** David a un lot de
  `SN74AHCT125N` (DIP-16, quadruple buffer 3 états) — c'est LE level shifter
  canonique du WS2812 attaqué en 3,3 V. Photo :
  `docs/pictures/odometrie/2026-09-02-lot-74ahct125-pas-des-optos.jpg`.
  ⚠️ **Trier AHC`T` / AHC** : seuls les AHC**T** ont des seuils TTL
  (`Vih` = 2,0 V) et lisent donc un 3,3 V à coup sûr ; les AHC sans T exigent
  0,7 × VCC = 3,5 V. Le lot contient les deux.
- **Pièges relevés en passant** : `ros2 topic pub --once` part dès la PREMIÈRE
  souscription matchée (souvent `web_bridge`) — le message peut rater
  `lights_node` ; publier deux fois ou vérifier robot.log. Après un boot du Pi
  (pas de RTC), `docker inspect StartedAt` peut dater d'avant le recalage NTP
  → faux « Up 10 hours ».
