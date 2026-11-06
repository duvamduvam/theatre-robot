# Étude acoustique de Didier — pourquoi les enceintes ne donnent pas leur maximum

> Ouverte le 2026-11-06 sur la demande de David (« ce n'est pas optimisé au niveau des
> baffles »). **État : analyse SUR FICHES, avant photos et avant mesure.** Les ordres de
> grandeur ci-dessous sont des calculs, pas des relevés : ils disent où regarder, pas
> ce qu'on trouvera.

## 1. La chaîne

Pi 5 / récepteur HF → mixette `t.mix MicroMix 2USB` → ampli **Focal Impulse 4.320** →
2 × **Focal Universal ICU 570** + 1 grand haut-parleur central (**référence inconnue**),
montés sur la **porte audio** (panneau bois sur charnières).

Fiches officielles archivées, lues le 06/11 :
[`datasheets/focal-impulse-4320-notice.pdf`](datasheets/focal-impulse-4320-notice.pdf),
[`datasheets/focal-icu570-fiche.pdf`](datasheets/focal-icu570-fiche.pdf)
(copies Focal-JMlab hébergées par le distributeur ampire.de).

| | Valeur lue | Ce que ça implique ici |
|---|---|---|
| Impulse 4.320 — puissance | 4 × 55 W RMS (4 Ω, CEA), 2 × 160 W bridgé | ~220 W de sortie au maximum |
| Impulse 4.320 — fusible | **25 A** (15 A sur faisceau ISO), « 12V mobile applications » | il est fait pour tirer jusqu'à ~300 W sur une batterie de voiture |
| Impulse 4.320 — filtres | passe-haut **fixe 75 Hz** commutable sur 1/2 ; HPF/LPF/FULL **40-200 Hz** + **phase 0/180°** sur 3/4 | les réglages existent pour un haut-parleur de grave sur 3/4 |
| Impulse 4.320 — gain | sensibilité réglable **0,2 à 5 V** | se règle à la mesure, pas à l'oreille |
| ICU 570 | 5×7" coaxial, 4 Ω, **94 dB (2,83 V/1 m)**, 60 Hz-21 kHz, 70 W RMS | rendement correct : la puissance n'est pas le problème |
| ICU 570 — Thiele-Small | Fs 80 Hz, **Qts 0,79**, Vas 11,3 l | haut-parleur de **portière** : conçu pour un grand volume clos (la porte d'une voiture), pas pour un panneau ouvert |

## 2. Les suspects, par ordre de gain probable

### 2.1 L'alimentation — probablement LE goulot (et la cause des redémarrages du 06/11)

Le 12 V du robot est une **SD-50B-12 : 4,2 A, 50 W**, déjà partagée avec les servos
(`plan-refonte-electrique.md` §5 ter). L'ampli est fait pour en tirer jusqu'à **25 A**.
**Si l'ampli est sur cette SD-50B-12** (c'est la question ouverte de la refonte), il ne
dispose au mieux que de quelques dizaines de watts, partagés avec les bras. Au premier
pic, la SD-50 coupe puis redémarre, ce qui correspond au symptôme rapporté le 06/11.

Ordre de grandeur, sur la fiche ICU 570 : 94 dB à 2 W. À 55 W, on aurait ~108 dB à 1 m
par haut-parleur ; à ~10 W, ~101 dB. Un écart de **~7 dB**, soit un son nettement moins
fort que ce que le matériel sait faire, et sans aucune marge pour les pics de la voix.

→ **À vérifier en premier : d'où l'ampli tire son 12 V.** S'il est bien sur la SD-50B-12,
la refonte électrique doit lui donner une alimentation à lui, dimensionnée sur son
fusible. Ça rejoint l'option « audio sur un 12 V isolé ».

### 2.2 Le montage sur panneau ouvert (« court-circuit acoustique »)

Un haut-parleur rayonne autant vers l'arrière que vers l'avant, en opposition de phase.
Sans caisson, les deux ondes s'annulent dès que la longueur d'onde dépasse le chemin
avant → arrière. Pour une porte de quelques dizaines de centimètres, la perte commence
vers **quelques centaines de hertz** et s'aggrave de 6 dB par octave en dessous. C'est
pile la zone de la voix : fondamentales autour de 100-250 Hz, et donc le « corps ».

Le Qts de 0,79 confirme que l'ICU 570 attend un **volume clos**, comme la portière
d'une voiture. **Le torse de Didier pourrait justement en être un** : avec Vas = 11,3 l,
un volume clos de ~50 l laisse le haut-parleur presque comme sur baffle infini
(Qtc ≈ 0,79 × √(1 + 11,3/50) ≈ 0,87, calcul à refaire avec le volume réel).

→ **La question décisive des photos** : quand la porte est fermée, l'arrière des
haut-parleurs donne-t-il sur un volume **fermé et étanche**, ou sur l'extérieur ou le
reste du robot ? Fermer ce volume (contreplaqué, joint mousse, laine dedans) pourrait être
le gain le moins cher de tout le chantier.

### 2.3 Les réglages de l'ampli

- **Passe-haut 75 Hz sur 1/2 : à activer.** Sur un montage non clos, le grave sous
  75 Hz ne s'entend pas et fait seulement débattre la membrane, ce qui coûte de la
  puissance et de la distorsion.
- **Haut-parleur central** : à quel canal est-il branché ? Si c'est un haut-parleur de
  grave, il devrait être sur 3/4 (ou 3/4 bridgé) en **LPF**, avec la coupure et la phase
  réglées à la mesure.
- **Gain** : à régler au signal de test, pour que l'ampli atteigne sa puissance juste
  avant que la mixette sature. Le banc d'août a déjà entendu une voix « saturée » : le
  réglage des niveaux d'un étage à l'autre est suspect.

### 2.4 La polarité

Les fils sont étiquetés au standard autoradio (`RR+`, `RR−`, `RL−`, `RF−`). Deux
haut-parleurs en opposition s'annulent dans le grave. On le vérifie à la pile de 1,5 V
(la membrane doit avancer sur chaque haut-parleur) ou à la mesure.

## 3. Ce qui manque pour conclure

1. **D'où l'ampli prend son 12 V**, et la section de son câble d'alimentation.
2. Photos : dos de la porte audio, le volume derrière quand elle est fermée, l'étiquette
   du haut-parleur central, les commutateurs et boutons de l'ampli, et le câblage
   ampli → haut-parleurs.
3. **Mesure** : balayage joué par le robot, enregistré au téléphone à 1 m dans l'axe,
   porte fermée, avant et après chaque correction. C'est elle qui valide chaque étape :
   pas de correction gardée sans courbe avant/après.
