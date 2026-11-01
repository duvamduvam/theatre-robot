# Firmware RP2040 — petite télécommande USB

Boîtier filaire à base de **Seeed XIAO RP2040** : un joystick analogique, un
poussoir d'homme-mort sous l'index, 4 boutons de menu et un écran OLED. Il émet
l'état des axes et des boutons vers l'hôte à 50 Hz, et affiche les lignes de
menu que l'hôte lui envoie. Étude complète :
[`../../docs/etude-telecommande-usb.md`](../../docs/etude-telecommande-usb.md).

> ⚠️ **La conduite est LOCALE et ne passe jamais par le menu ni par l'hôte**
> (étude §4.7). Lecture des axes, homme-mort, émission 50 Hz : tout se fait
> dans le RP2040, sans dépendre de l'écran, de l'état du menu ni de la santé du
> logiciel hôte. Si celui-ci plante, le menu gèle et l'écran ment — mais le
> boîtier continue d'émettre la vérité des axes et de l'homme-mort ; et s'il
> n'émet plus, le deadman 400 ms en aval arrête le robot. **Une panne
> d'affichage ne peut produire qu'un menu mort, jamais un mouvement.**
>
> ⚠️ Ce boîtier reste **filaire** : il ne remplace ni le coup-de-poing sans fil
> du chantier web (W1), ni la coupure générale.

## Les fichiers, et pourquoi ils sont séparés

| Fichier | Où il tourne | Testé ? |
|---|---|---|
| `remote_protocol.py` | **RP2040 + décodeur hôte + tests hôte** — trame, CRC, zone morte, drapeaux, règle du menu | ✅ une suite de tests hôte : `robot/tests/unit/test_remote_protocol.py` |
| `code.py` | RP2040 seul (broches, ADC, boucle 50 Hz, OLED) | ❌ **lot T2, pas encore écrit** |
| `boot.py` | RP2040 seul (déclaration USB CDC) | ❌ **lot T2, pas encore écrit** |

Même coupure que `firmware/pico_odometry`, pour la même raison : tout ce qui
peut être *faux* — le masque des boutons, le signe et la zone morte des axes,
les bornes, le CRC, et surtout la règle de sécurité du menu — vit dans le
fichier partagé, exercé par les tests du dépôt et par le code hôte. Le fichier
qui touche les broches ne garde que ce qu'aucun test hôte ne peut atteindre.

`remote_protocol.py` est écrit pour **CircuitPython** : pas d'annotations de
type, pas de dataclasses, pas d'enum, pas de f-strings, aucun import.

## Le protocole montant (boîtier → hôte)

```
R;<seq>;<x>;<y>;<flags>;<crc8>\n        50 Hz, émis SANS CONDITION
```

- **`seq`** : compteur 0..255 qui boucle, pour détecter les trames perdues.
- **`x`, `y`** : entiers signés **-1000..+1000**, zone morte déjà appliquée à
  bord (`apply_deadzone()`).
- **`flags`** : masque hexadécimal minuscule sur 2 chiffres —
  `0x01` homme-mort, `0x02` haut, `0x04` bas, `0x08` valider, `0x10` retour,
  `0x20` clic du manche (réservé, §4.4).
- **`crc8`** : CRC-8 (polynôme 0x07, init 0x00) sur `R;<seq>;<x>;<y>;<flags>`,
  soit tout ce qui précède le dernier « ; » — ni ce « ; », ni le « \n ».

**L'émission est inconditionnelle**, même manche au repos : c'est cette
répétition qui fait vivre le deadman aval. Un boîtier silencieux au repos
serait indistinguable d'un boîtier débranché.

**Pourquoi un CRC sur de l'USB, qui a déjà le sien ?** Le CRC de l'USB protège
le transport, pas le décodage : une trame tronquée à la reconnexion, un buffer
réassemblé de travers, et `x` prend une valeur *plausible*. Sur un chemin qui
commande 50 kg de roues, une valeur plausible et fausse est le pire cas.

**Toute trame malformée est REFUSÉE** — `decode_frame()` renvoie `None`, jamais
une valeur approchée, jamais un champ « rattrapé ». Refuser coûte une trame,
soit 20 ms ; la suivante arrive. Et si elles sont toutes refusées, l'absence de
commande valide fait tomber le deadman aval, qui arrête le robot. L'échec va du
bon côté. Seuls le `\r\n` et les espaces ASCII **en bord de ligne** sont
tolérés : rien n'est nettoyé à l'intérieur de la trame.

`decode_frame()` accepte **du texte OU des `bytes`/`bytearray`** : le décodeur
hôte lui passe directement ce qu'il lit sur le port, sans `.decode()` préalable.
Les octets sont convertis en **latin-1**, jamais en ASCII : latin-1 est bijectif
sur 0-255, donc il ne lève pas sur un octet corrompu > 0x7F — c'est-à-dire
précisément le cas pour lequel le CRC existe, et qui doit produire un refus, pas
une exception dans la boucle de lecture. Tout autre type d'entrée renvoie `None`
sans lever.

**Casse de l'hexadécimal** : l'encodeur n'émet QUE du minuscule (`3f`, jamais
`3F`) ; le décodeur, lui, accepte les deux en lecture. Cette tolérance est
assumée mais elle est à sens unique — un outil tiers branché sur le port ne doit
compter que sur du minuscule en réception, et le futur nœud hôte ne doit jamais
comparer les champs `flags`/`crc8` sous forme de texte.

### ⚠️ La règle de sécurité : `menu_enabled()`

**Le menu est inerte tant que l'homme-mort est tenu** (étude §4.4). Naviguer un
écran à deux mains pendant que 50 kg roulent, c'est l'accident : homme-mort
tenu ⇒ l'écran n'affiche que la conduite et les 4 touches ne produisent rien.

Cette règle vit dans `menu_enabled()` **et nulle part ailleurs**. L'écran, le
menu hôte et le firmware doivent tous l'obtenir de cette fonction : dupliquée,
elle finirait par diverger d'un côté, et ce côté-là serait dangereux. Un test
dédié balaie les 64 combinaisons de boutons pour le vérifier.

### ⚠️ La zone morte est RE-ÉTALÉE

`apply_deadzone(raw, center, span, deadzone)` : `raw`/`center` sont bruts,
`span` est la demi-course brute, `deadzone` est en **unités de sortie**
(0..1000). Au-delà de la zone morte, la sortie **repart de 0** au bord de
celle-ci et atteint ±1000 en butée. Sans ce re-étalement, le robot passerait
d'un arrêt à ~10 % de vitesse dès que le manche quitte la zone morte — un
à-coup de 50 kg à l'endroit précis où l'opérateur cherche la finesse.

Aucune de ces fonctions ne lève : `span` nul (paramètre pas encore calibré)
donne 0, une lecture aberrante sature, un axe hors borne est borné à
l'encodage. Une exception à 50 Hz couperait la boucle d'émission — donc la
seule preuve de vie du boîtier.

## Ce qui reste à faire

- [ ] **Lot T2 — `code.py` / `boot.py`** : broches, ADC, boucle 50 Hz, OLED,
      déclaration USB CDC. Ils importent `remote_protocol.py` — ne pas le
      recopier.
- [ ] **Calibration des axes** : `center` et `span` de chaque voie ne se
      décident pas, ils se **mesurent** sur le module monté (relevé des
      butées et du repos), comme le sens de comptage de l'odométrie.
- [ ] **Protocole descendant** (hôte → boîtier : effacer, écrire ligne N,
      surligner le curseur) — §4.6, à écrire avec le menu hôte.
- [ ] **Décodeur hôte** : nœud qui lit le port et publie `/cmd_vel_remote`
      (§4.2). Roues au sol ⇒ protocole caméra avant tout usage.
- [ ] **Règle udev** sur le numéro de série du RP2040, comme `/dev/didier-odom`.
