# Deux Pi abîmés en branchant la nappe GPIO de l'ancienne carte du robot

> Fiche écrite le 2026-11-06 à partir de la conversation du 04/11 au soir (session
> `a9ff7639`), à la demande de David. **Cause non établie.** Aucune mesure du câblage de la
> nappe n'a été faite depuis.

- **Date/contexte** : 2026-11-04, 21 h 30 - 22 h 15, atelier. Remise en route du robot après
  le redéploiement (lot L1). Pi alimentés par le chargeur USB-C Dell, hors du rail robot ; la
  nappe 40 fils relie le GPIO du Pi à l'ancienne carte principale du robot (plaque à pastilles
  avec l'isolateur I²C violet).
- **Symptôme** :
  1. Pi 4 **4 Go**, nappe branchée dans un sens choisi d'après une mesure de 5 V sur la nappe :
     la **LED 12 V du robot s'éteint** tant que la nappe est branchée et revient quand on la
     retire. Ensuite le Pi ne démarre plus : **LED rouge et verte fixes**, rien sur le réseau.
  2. Pi 4 **2 Go**, nappe branchée **dans l'autre sens** : **fumée**, **câble d'alimentation du
     Pi chaud**. Le Pi redémarre ensuite (démarrage difficile), puis passe les tests hors robot :
     aucune sous-tension, processeur à 1,8 GHz, mémoire sans erreur, conteneur stable. **Broches
     GPIO non testées.**
  3. Une 3ᵉ Pi (modèle non relevé) ne démarrait déjà pas avant la nappe (mêmes LED fixes) :
     **pas liée** à cet incident.
- **Traces** : photos de la nappe, `../hardware/photos/2026-11-04-nappe-gpio/` ; état des Pi,
  `../hardware/inventaire-stock.md` (lignes Pi 4 2 Go et 4 Go).
- **Investigation** : aucune. Les deux tests proposés par l'agent pour trouver le sens étaient
  **faux** : le 5 V cherché sur la nappe n'existe pas sans Pi (le côté Pi de l'isolateur I²C
  est alimenté par le Pi), et le sens « fil marron côté SD » n'était qu'une convention.
  L'agent l'a reconnu le soir même.
- **Cause** : non établie. Ce que les faits montrent : **les deux sens ont provoqué une
  panne**, donc le sens n'est pas seul en cause ; la LED 12 V qui s'éteint montre que la nappe
  **tire sur l'alimentation du robot** ; le câble du Pi qui chauffe montre qu'un **fort courant
  est passé entre l'alimentation du Pi et celle du robot**. Hypothèses, non vérifiées :
  - le 5 V du robot arrive sur les broches 2/4 de la nappe et se retrouve en parallèle du
    chargeur du Pi ; or ce rail 5 V est lui-même suspect (incident du 03/11 : le fil rouge
    d'un servo ASME l'alimente depuis le 12 V) ;
  - un court-circuit ou un fil inversé sur l'ancienne carte, qui met une tension sur une
    broche de masse ou un signal du Pi dans un sens ou dans l'autre.
- **Remède** : nappe débranchée, interdite sur tout Pi. Pi 4 Go à tenter de sauver par la
  récupération du bootloader (Raspberry Pi Imager), non faite à ce jour.
- **Prévention** :
  - **ne plus jamais brancher un Pi sur l'ancienne carte** : la refonte la remplace ;
  - la nouvelle carte Sécurité ne fait **pas** passer le 5 V par la nappe (broches 2 et 4 non
    connectées, `pcb/kicad/carrier_design.py`) ; son connecteur est détrompé **côté carte seulement** : le connecteur du Pi est nu, et la nappe retournée côté Pi mettait la broche 39 (GND) sur le 5 V du Pi (relecture du 06/11 ; correction : J1.39 non connectée) ;
  - avant tout Pi sur une carte neuve : continuité broche par broche hors tension, puis la
    carte témoin RP2040 (`firmware/pico_test_5v`) à la place du Pi, sous alimentation limitée
    en courant ; enfin le Pi ;
  - **un sens de connecteur ne se déduit jamais d'une convention** : il se prouve hors tension,
    à la continuité, ou par un détrompeur mécanique.
