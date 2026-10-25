# Étude — articuler le tronc de Didier (2026-10-25)

> **Statut : ÉTUDE, rien d'acté.** Recherche web du 25/10 (4 collectes parallèles + passe
> ciblée), croisée avec le stock (`.iaction/connaissances/inventaire-stock.md`).
> Tous les prix cités ont été **lus sur la page** à la date indiquée ; ceux qui ne
> viennent que d'un extrait de moteur de recherche sont marqués *(extrait)* et ne
> doivent pas entrer dans une commande sans relecture.

## 0. Cible : la PROCHAINE version (Didier v2, concept « robot triangle »)

> Précisé par David le 25/10 : l'étude vise la **v2**, pas le Didier actuel. Les §4.2,
> 4.3 et 9 ci-dessous (2 vérins sur un cardan, MDDS30 de rechange, peser/couper le
> torse actuel) sont **remplacés** par cette section. Le reste (familles écartées,
> ressorts, respiration, sécurité) tient toujours.

**Schéma** : `docs/pictures/tronc-v2-verins.svg`, généré par
`docs/outils/schema_tronc_v2.py` (cotes copiées du concept, cinématique calculée —
relancer le script si le concept change).

**La v2 a déjà la place.** Le concept (`~/Nextcloud/dev/didier/plans/concepts/triangle-3roues`)
pose le corps sur une **colonne télescopique** (±40 mm) terminée par un **cardan Ø110**,
avec **3 ancrages de vérins** entre les pointes du caisson (r405) et le dessous du corps
(r215, z705). Il n'y a rien à inventer, seulement à **motoriser ces 3 vérins** :

- **3 vérins = 3 mouvements** : hauteur (les 3 ensemble), tangage (V0 avant contre
  V120 + V240), roulis (V120 contre V240) ;
- ⚠️ **Ça rouvre une décision du 16/07.** Le concept a acté des vérins **à gaz,
  passifs**, parce qu'un vérin électrique autobloquant n'a aucune souplesse et se
  fait marteler par les chocs de la scène (seuils, appuis). Le plan-de-route avait
  posé la condition d'un retour à l'actif : **un étage élastique en série**
  (silentbloc ou ressort précontraint à l'ancrage), **jamais le vérin seul**. La
  proposition la respecte ;
- le **vérin** : 24 V, **course 100 mm**, potentiomètre 10 kΩ, autobloquant, IP65,
  modèle 0041502-2 — **110,00 €** (alu), lu le 25/10 :
  <https://verinelectrique.fr/products/verin-electrique-2000n-100mm-actionneur-lineaire-avec-potentiometre>.
  Entraxe des œils : **235 mm rentré / 335 mm sorti**, œils Ø6. Expédié de **Hong
  Kong** (3 à 7 jours ouvrés) ; la page annonce **~20 % de droits à l'import**.
  Choisir la variante **300 N à 40 mm/s** au moment de la commande ;
- **cinématique** (calculée par le script) : entre les ancrages actuels il y a
  322 mm, soit le vérin **presque à fond**. Il faut donc monter l'ancrage bas de
  **z445 à z468**, ce qui centre dans la course la plage utilisée à ±15°. Résultat :
  à ±15°, le vérin va de 241 à 329 mm, et il reste ±6 mm pour la hauteur ; à ±10°,
  il va de 252 à 311 mm, et il reste ±17 mm. La hauteur ±40 du concept et la
  pleine inclinaison ne sont **pas cumulables** : le logiciel bornera la somme ;
- la version **150 mm** (285/435, 115,00 €) a été essayée : son ancrage bas
  tomberait à z370, **sous le dessus du caisson** (z440). Elle ne loge pas ;
- **effort** : la colonne ne porte que le cisaillement et la torsion. Le **poids du
  corps** (10-20 kg) passe donc **par les vérins**. Avec ~190 N répartis sur 3 vérins
  inclinés d'environ 36°, plus le couple de bascule repris sur 21,5 cm, on reste
  sous ~200 N par vérin au pire (ordre de grandeur, à refaire au bilan de masse),
  pour 300 N disponibles ;
- **commande** : 3 canaux de pont en H (le MDDS30 n'en a que 2 ⇒ un driver de plus,
  à choisir) et 3 entrées ADC (RP2040). Un nœud `torso` à deadman, comme la note
  sécurité des anneaux tournants l'exige pour tout actionneur de cette classe ;
- **budget vérins** : 3 × 110,00 € = 330 € + droits, contre 45 à 105 € pour les vérins
  à gaz du plan-de-route.

## 1. Cahier des charges (David, 25/10)

| Critère | Valeur |
|---|---|
| Mouvements | **tangage** (pencher avant/arrière) + **roulis** (pencher sur les côtés) ; ondulation/respiration en bonus. Pas de rotation demandée |
| Amplitude | **petite : ±10-15°** |
| Masse au-dessus de l'articulation | **10 à 20 kg** (torse, bras, tête, électronique) — **non pesée** |
| Exigences | résistant (spectacle, chocs), pas cher, réactif — une latence est acceptable |

## 2. Ordres de grandeur (calcul, pas de source)

Hypothèse : centre de gravité du haut du corps à `h` = 30-40 cm au-dessus du pivot.

- **Couple statique** à tenir : `m·g·h·sin θ`. Pire cas (20 kg, 40 cm, 15°) :
  **20,3 N·m par axe**. Cas léger (10 kg, 30 cm, 10°) : 5,1 N·m. Prévoir une marge ×1,5
  pour la dynamique et les chocs.
- **C'est un pendule inversé** : la gravité aggrave l'inclinaison. Un actionneur
  réversible (servo, moteur sans balais, pas-à-pas sans courant) **laisse tomber le
  buste en butée** en cas de coupure. D'où le critère n° 1 ci-dessous.
- **Déplacement du centre de gravité du robot entier** à 15° : 20 kg × 0,35 m × sin 15°
  / 50 kg ≈ **3,6 cm**. Négligeable à l'arrêt ; à surveiller en roulant et au freinage
  (le buste penché en avant, Didier qui freine : les deux effets s'ajoutent).

## 3. Les familles examinées

| Famille | Verdict | Pourquoi |
|---|---|---|
| **Vérins électriques à vis trapézoïdale (Acme) avec potentiomètre** | ✅ **RETENU** | Autobloquants (tiennent sans courant), force largement suffisante, position absolue, 24 V, IP65, ~100 € pièce |
| Vérin DIY pas-à-pas NEMA17 + vis trapézoïdale imprimé 3D | 🟡 **Plan B économique** | Le moins cher et le plus silencieux (driver pas-à-pas silencieux), autobloquant avec une vis à petit pas. Mais **pas de position absolue** (il faut une prise d'origine par fin de course), perte de pas sous choc, robustesse artisanale. Force « 450 N » annoncée *(extrait, probots.co.in)* ; prix non relevés |
| Moteurs d'essuie-glace + potentiomètre (classique des simulateurs de course 2 axes) | ❌ | Couples catalogue de 3,5 à 7 N·m *(extrait)*, 10-23 N·m selon les forums (aucune fiche constructeur) ; neufs 88 à 217 € *(extrait)* donc pas moins chers qu'un vérin ; **jeu et usure rapide** rapportés par xsimulator (les gens ajoutent des ressorts de précharge) ; bruyants ; potentiomètre et accouplement à bricoler sur des arbres cannelés |
| Gros servos (RS485 24 V 120 kg·cm, Feetech STS3250…) | ❌ | 120 kg·cm = 11,8 N·m **bloqué** (le couple continu est bien plus bas) < 20 N·m ; réversibles ; aucun retour de fiabilité trouvé. RobotShop : 69,52 $ affiché pour le 120 kg·cm le 25/10, avec un faux prix barré (347,59 $) — prix douteux |
| Actionneurs de robotique à moteur sans balais (Robstride 02, CubeMars) | ❌ | 6 N·m nominal (17 en crête), 219,95 € l'axe (openelab, 25/10), 48 V nominal, **réversibles** : buste en butée à la coupure |
| Pas-à-pas NEMA23 + réducteur planétaire 20:1 | ❌ | 35 N·m nominal, mais 139,99 $ le réducteur **seul** (VXB, 25/10) + moteur + driver ; doit rester alimenté pour tenir |
| Câbles/tendons, colonne souple (ressort, élastomère, sandow) | ❌ comme actionnement | Aucune source ne montre une colonne souple qui porte 10-20 kg : le torse à câbles de référence (LARMbot, PMC9502744) mesure 26 cm et tire 1,3 N par câble, avec des pertes de tension. Le caoutchouc flue sous charge statique. **Mais les ressorts ont un rôle d'appoint** (§5) |
| Muscles pneumatiques (Festo DMSP) | ❌ | Compresseur, vannes, **bruit**, deux muscles par axe ; ~200 £ le plus petit (Hydraquip, 25/10) |

## 4. Recommandation

**Une articulation à 2 axes (cardan) + 2 vérins électriques 24 V à potentiomètre : un
devant pour le tangage, un sur le côté pour le roulis.**

### 4.1 Le vérin

Référence trouvée : vérin 50 mm de course à potentiomètre, verinelectrique.fr, lu le
25/10 ([page](https://www.verinelectrique.fr/products/verin-electrique-2000n-50mm-actionneur-lineaire-avec-potentiometre)) :

- **100,00 €** (alu) / 122,00 € (inox), TVA non précisée ;
- 12/24/36/48 V — **prendre 24 V** (le rail existe) ;
- le couple force-vitesse se **choisit à la commande** : **300 N à 40 mm/s** est le bon
  point (250 N à 55 mm/s si on veut plus vif) ;
- potentiomètre 10 kΩ, **autobloquant**, IP65, 46 à 56 dB, **cycle de service 20 %,
  5 min en continu au maximum**.

Concurrent noté : MPP-CCS (motionproplus), 200 N à 50 mm/s, < 45 dB, 129,00 € HT, lu le
25/10 — plus silencieux, mais **sans retour de position** sur la page : écarté tant
qu'une version à potentiomètre n'est pas trouvée.

À vérifier avant la commande : longueur rétractée (encombrement dans la caisse), pays
d'expédition (droits si hors UE), présence de fins de course internes.

### 4.2 La géométrie

- Course 50 mm pour ±15° ⇒ **bras de levier ≈ 9,7 cm** (`L = course / (2·sin 15°)`).
- Force demandée au pire cas : 20,3 N·m / 0,097 m ≈ **210 N** pour 300 N disponibles
  (marge ×1,4 sans ressorts, ~×5 avec, §5).
- Vitesse : 40 mm/s ⇒ ~24°/s : **±15° balayés en 1,3 s**, un geste de 10° en 0,4 s.
  Ce n'est pas nerveux, c'est **posé** — compatible avec « une latence acceptable ».
- **Rotules aux deux bouts de chaque vérin** : la charge latérale détruit un vérin bien
  avant la surcharge axiale (blog Firgelli, sim racing 3 axes). Le cardan porte le
  poids ; les vérins ne portent que le couple.
- **Butées mécaniques à ±17°** (au-delà de la course logicielle) : en cas de
  potentiomètre arraché, c'est elles qui arrêtent, pas le moteur.

Le cardan : un croisillon de transmission (agricole/auto) ou deux axes croisés sur
paliers à roulement. Il doit porter 100-200 N axial + les chocs. **Prix non relevés** —
le seul lu (cardan double 16 mm, Simply Bearings, 77,54 £ HT) est un modèle de
transmission d'arbre, pas le bon type.

### 4.3 Commande — rien à acheter

- **Cytron MDDS30** (en stock, 2 canaux = 2 vérins) ⚠️ c'est la **rechange des roues** :
  l'utiliser ici supprime la rechange.
- **RP2040** (en stock) : 2 entrées ADC lisent les potentiomètres, boucle de position
  locale ; liaison série vers le Pi comme l'odométrie.
- Côté ROS : un nœud `torso` à **deadman** (commande périmée ⇒ moteurs coupés, le vérin
  autobloquant garde la pose), branché sur l'arbitrage `animation_state` comme le cou.
- **Simulation d'abord** : 2 articulations dans l'URDF, protocole caméra sur le vrai
  robot avant toute séance avec l'acteur.

## 5. Ressorts de centrage — l'appoint qui change tout

Des ressorts entre la base et le torse qui **rappellent au centre** compensent la
gravité. Si leur raideur angulaire `k_θ` vaut un peu plus que `m·g·h`, le buste devient
**passivement stable** et le vérin ne fournit plus que la différence :

- pire cas (`m·g·h` = 78,5 N·m/rad), ressorts à `k_θ` ≈ 100 N·m/rad : à 15°, le vérin
  ne fournit plus que **~6 N·m au lieu de 20** ;
- réalisation : 4 ressorts de compression en croix, à 12 cm du pivot ⇒ ~3,5 N/mm chacun
  (`k_θ = 2·k·r²` par axe), environ 31 mm de débattement à 15° ;
- ⚠️ **à régler sur la masse RÉELLE** : des ressorts calculés pour 20 kg sur un buste de
  10 kg tireraient trop (18 N·m à 15°) — on aurait déplacé le problème. **Peser d'abord.**

Bénéfices : vérins à 20 % de leur force (moins de chauffe malgré le cycle de 20 %, moins
de bruit, durée de vie). Sans effet sur la sécurité à la coupure : le vérin autobloquant
fige déjà la pose. Optionnel si le buste pesé fait ≤ 12 kg.

## 6. Respiration et ondulation — un actionneur à part

**Ne pas la confier aux vérins** : un mouvement permanent viole le cycle de service de
20 %. Les réalisations trouvées *(extraits ; hackster, robotshop)* : un petit servo
avec une came excentrique qui soulève un panneau de poitrine, ou des demi-coques
écartées par une crémaillère. Pour Didier : **un servo sur le PCA9685 existant**
derrière un panneau de torse — zéro électronique nouvelle. L'« ondulation » ample reste
possible avec les vérins, ponctuellement (quelques degrés, pas en boucle).

## 7. Sécurité

- **Coupure** : vérin autobloquant ⇒ la pose est figée, pas de chute du buste.
- **Perte de liaison** : deadman du nœud `torso` (moteurs coupés, pose figée).
- **Pincement** : l'interstice torse/base s'ouvre et se ferme de ~5 cm au bord (20 cm de demi-largeur × sin 15°), à
  hauteur des mains de l'acteur ⇒ **soufflet ou jupe souple** obligatoire.
- **Roues** : interdire ou réduire l'inclinaison au-delà d'un seuil de vitesse (le
  freinage buste en avant cumule les deux effets). Règle à poser dans la spec, à
  valider au protocole caméra.

## 8. Budget connu (prix lus le 25/10)

| Poste | Prix |
|---|---|
| 2 vérins 24 V, 50 mm, potentiomètre | 2 × 100,00 € (TVA non précisée) |
| Driver + microcontrôleur | 0 € (stock — mais coûte la rechange MDDS30) |
| Cardan, 4 rotules, ressorts, butées, soufflet | **non relevé** |

## 9. Ce qui reste à lever, dans l'ordre (v2)

1. **Trancher actif/passif** pour la v2 (décision du 16/07 à rouvrir ou non, §0).
2. **Choisir l'étage élastique** de l'ancrage bas (silentbloc, ressort précontraint) :
   raideur assez forte pour ne pas faire tanguer le corps, assez souple pour
   absorber un seuil.
3. **Reporter l'ancrage bas z468** dans `caisson.py` (chape de vérin) et
   `robot_triangle.py`, puis vérifier l'enveloppe basse des bras (contrainte
   z≈672, qui dépend de la trajectoire des vérins).
4. **Driver 3 voies** et budget actionneurs (le concept compte déjà 11 actionneurs).
5. Spec fermée : nœud `torso`, mélange hauteur/tangage/roulis, bornes logicielles,
   deadman, règle « pas d'inclinaison pleine en roulant ».
