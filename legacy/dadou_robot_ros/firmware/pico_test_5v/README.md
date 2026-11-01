# Témoin d'arrivée 5 V — carte sacrifiable

Une RP2040-Zero branchée sur le rail 5 V du robot, qui clignote tant que le
rail tient. But : **ne pas découvrir un défaut d'alimentation avec un Raspberry
Pi au bout du fil.** Une Zero coûte quelques euros, un Pi 4 + sa carte SD et
son système, non.

> Ce firmware ne commande RIEN et n'est relié à rien d'autre que le rail testé.
> Il n'a aucune part dans la chaîne roues.

## Lire la LED

La carte n'a **pas** de LED sur GP25 — c'est celle du Pico officiel. Elle porte
une **WS2812 RGB sur GP16** (piège déjà consigné dans
[`../pico_odometry/README.md`](../pico_odometry/README.md) § variante Zero).

| Ce qu'on voit | Ce que ça veut dire |
|---|---|
| **5 flashs blancs rapides** | la carte **vient de démarrer** |
| **rouge**, battement « toc-toc » | tourne depuis moins de 10 s |
| **orange** | moins d'une minute |
| **jaune** | moins de cinq minutes |
| **vert** | **plus de cinq minutes sans redémarrer** — le rail tient |
| **violet** | tension sortie de la plage Pi (pont diviseur seulement, voir plus bas) — **mémorisé** : reste violet même si c'est revenu bon |
| noir, ou clignotement rouge/jaune codé | carte non alimentée, ou erreur CircuitPython |

Le **double flash à 1 Hz** prouve en plus que le programme *tourne* : une LED
fixe ne distingue pas un programme vivant d'un programme figé.

**C'est le retour au rouge qui est le signal utile.** Un rail qui s'effondre
sous un appel de courant fait redémarrer la carte : la couleur retombe. On
branche, on va faire autre chose, on revient : si c'est **vert**, le rail a
tenu cinq minutes au moins.

## ⚠️ Ce que ce test NE prouve PAS

**« Ça clignote » ≠ « bon pour un Raspberry Pi ».** Le régulateur de la Zero
tient encore sous 3 V d'entrée : la carte clignotera parfaitement sur un rail
à **3,8 V**, qui ferait planter un Pi 4 (il exige **4,75-5,25 V**, et râle déjà
sous 4,63 V).

Ce montage prouve la **présence** et la **stabilité** du rail. Pour sa
**valeur**, il faut un multimètre — ou le pont diviseur ci-dessous.

## Câblage

| Carte | Rail du robot |
|---|---|
| pastille `5V` | + 5 V |
| pastille `GND` | masse |

⛔ **Trois façons de tuer la carte en une seconde :**

1. **Brancher sans avoir mesuré le rail au multimètre d'abord.** Si ce qu'on
   croit être du 5 V est du 12 V, la carte part en fumée — et on n'aura rien
   appris qu'un multimètre n'aurait dit gratuitement. *Le témoin sert à
   surveiller la durée et la stabilité, pas à découvrir la tension.*
2. **Inverser + et masse.** Repérer les pastilles avant de souder.
3. **Brancher l'USB du PC en même temps que le rail robot.** Sur une Zero, la
   pastille `5V` est reliée **directement** à VBUS : deux sources 5 V se
   retrouveraient face à face. (Le Pico officiel, lui, tolère ça sur VSYS grâce
   à sa diode — pas la Zero.) **Un seul des deux à la fois.**

## Mettre à jour le programme

La carte se monte comme une clé USB **`CIRCUITPY`**. Le programme est le
fichier `code.py` à sa racine : on l'édite directement dessus, ou on recopie
celui d'ici. CircuitPython redémarre le programme à chaque sauvegarde.

```bash
cp firmware/pico_test_5v/code.py /run/media/$USER/CIRCUITPY/code.py && sync
```

`code.py` démarre tout seul à la mise sous tension, sans PC : c'est ce qu'on
veut sur le robot.

### Pourquoi CircuitPython ici, alors que l'odométrie est en MicroPython

Parce que déposer un fichier en MicroPython passe par le **port série**
(`mpremote`), et que le compte n'est pas dans le groupe `dialout` (`/dev/ttyACM0`
est `root:dialout`) : il faudrait `sudo` puis une reconnexion de session.
CircuitPython expose un volume USB : un `cp` suffit, sans droits particuliers.

Pour un outil d'établi qu'on veut pouvoir bricoler à une main, ça vaut
l'entorse. **Ce choix ne doit pas contaminer `pico_odometry`**, qui reste en
MicroPython pour une bonne raison : son décodeur de quadrature est le *même
fichier* que celui qu'exécutent le nœud ROS et les tests du dépôt.

Pour rendre le port série accessible un jour (le futur nœud d'odométrie en
aura besoin) :

```bash
sudo usermod -aG dialout $USER   # prend effet à la reconnexion de session
```

## Option : mesurer vraiment la tension

La Zero n'a **aucun pont diviseur interne** vers le rail (le Pico officiel en a
un sur VSYS, lu par ADC3 — pas elle). Sans pont externe, lire l'ADC ne
mesurerait qu'une broche flottante, donc le programme préfère **ne rien
afficher plutôt qu'une tension inventée**.

Pour l'activer, un pont de deux résistances **égales** entre le rail et la
masse, point milieu sur **GP26** :

```
  rail 5 V ──[ R ]──┬──[ R ]── GND        R = 100 kΩ (il y en a au stock,
                    │                          inventaire § 2.2)
                   GP26
```

Puis dans `code.py` : `DIVISEUR = 2.0`.

⛔ **Jamais le 5 V directement sur une broche** : les entrées du RP2040 sont en
3,3 V. C'est toute la raison d'être du pont.

La LED passe alors au **violet mémorisé** dès que la tension sort de
4,75-5,25 V, et le minimum atteint est rapporté sur le port série
(`t=120s  5.03 V  mini=4.81 V  ok`) — c'est le **mini** qui révèle un creux
passager sous appel de courant.

> Le rapport de pont dépend des résistances réellement posées : avec deux
> valeurs différentes, `DIVISEUR = (R_haute + R_basse) / R_basse`. Une tolérance
> de 5 % sur les résistances, c'est ±0,25 V à 5 V — de quoi rendre l'alerte
> injuste. Pour un verdict serré, mesurer les deux résistances à l'ohmmètre et
> calculer le rapport réel.
