# Croisement de l'inventaire avec les études (2026-09-03)

Passe faite après la passe complète du dépouillement : `docs/hardware/inventaire-stock.md`
confronté aux études du dépôt, pour chercher d'autres cas de **« on s'apprête à acheter ce
qu'on possède déjà »**. Le chantier est né de deux cas avérés (74AHCT125, PC817), un
troisième a été trouvé au dépouillement (RP2040).

> ⚠️ **Lire d'abord la §2** : cette passe a commis une erreur de cadrage (deux pièces
> déclarées « à acheter » alors qu'elles sont **sur le robot**). Elle est corrigée et
> expliquée, mais elle change la façon de lire tout le reste du document.

**Résultat global, dit franchement : aucun nouveau démenti de liste de courses.**
Sur les quatre études croisées, **zéro remplacement direct**. Ce n'est pas un échec — c'est
une information : les gros gisements d'économie étaient sur l'odométrie (seule étude à avoir
une vraie nomenclature d'achat), et ils ont été exploités. Ce que cette passe apporte est
ailleurs, et vaut la peine d'être lu : **trois mises en garde**, **une pièce à chercher**, et
**la liste de ce qu'il faudra vraiment acheter**.

---

## 1. ⚠️ Sécurité — le stock ne contient AUCUN arrêt d'urgence

C'est le résultat le plus important de cette passe, et il va à contre-courant de l'espoir de
départ.

`CLAUDE.md` note que **`e_stop` n'a aucune source** et que c'est à câbler. L'étude interface
web (§2, l. 28-32) demande un **coup-de-poing sans fil** coupant la puissance roues. On
pouvait espérer que le stock aide. **Il n'aide pas, et se croire couvert serait dangereux.**

**Le piège précis** : l'inventaire liste un « interrupteur-sectionneur à bouton rouge »
`YH02-A`, `AC-3 16A AC250V`, **`IEC60947-3`**, IP55 (repère `t0164`). Rouge, gros, d'aspect
rassurant. Mais :

- **La norme lue est la mauvaise.** `IEC 60947-3` = appareillage de **sectionnement**. Un
  organe d'arrêt d'urgence relève de **`IEC 60947-5-5`** (ouverture positive, verrouillage
  mécanique) et `EN ISO 13850` pour la fonction. **Aucune pièce du stock ne porte 60947-5-5.**
- **Calibre AC seulement** (`AC-3`, catégorie moteur alternatif), **aucune valeur DC lue**.
  Or la puissance roues est du **DC** (Cytron MDDS30, 7-35 V). Couper du DC inductif avec un
  contact dimensionné AC est le piège classique : sans passage par zéro, l'arc ne s'éteint
  pas, **le contact se soude — l'arrêt d'urgence ne coupe plus**.
- Accrochage et configuration NO/NF **non lus**. Et il est **filaire**, donc hors sujet pour
  la ligne « sans fil ».

**Même réserve sur les relais** (`c0372`-`c0376`, `t0481`) : calibre des contacts et tension
de bobine **non lus**, en sachets jamais ouverts. Un module relais logique typique tient
~10 A ; couper l'alimentation d'un robot de 50 kg via un driver 30 A est hors de ce domaine.
Un contact sous-dimensionné sur une chaîne d'arrêt = contact soudé = **arrêt inopérant**.

**Ce qui est quand même utile** : ces relais permettent de **maquetter le schéma sur banc**
(roues hors sol, protocole caméra) pour valider la logique **à manque de courant** — bobine
alimentée en marche normale, passage de puissance par le contact NO, de sorte que toute
perte (bouton enfoncé, pile morte, radio perdue, fil coupé) **retombe en ouverture**. Câblé
à l'envers, une pile morte donne un robot qui roule et un bouton qui ne fait rien.
Le schéma appartient à l'étude (§9.2) ; c'est signalé, pas décidé.

**À ne JAMAIS rapprocher d'une fonction d'arrêt d'urgence**, même sur un banc — la
ressemblance « bouton rouge » rend l'erreur facile : les poussoirs tactiles `t0017`/`t0506`
(momentanés, **50 mA**), les bascules `ZENGTAI` `t0166`, les rockers `c0423` (calibre non
lu), le bloc `I`/`O` `c0161`.

---

## 2. ⚠️ ERREUR DE CADRAGE DE CETTE PASSE — corrigée le 2026-09-03

**La première version de ce document affirmait que « le ReSpeaker n'apparaît nulle part dans
l'inventaire » et le donnait à chercher dans les colis scellés. C'était faux, et l'erreur
était de méthode.**

Le ReSpeaker XVF3800 est **documenté sur 140 lignes** dans `docs/hardware/overview.md`
(§ « Ordered 2026-08-12 »), il est **en service** (UAC 2.0 sans pilote, DoA via
`host_control`), et il a même **une pièce CAO dédiée** :
`~/Nextcloud/dev/didier/plans/supports/support-respeaker-xvf3800/`.

De même, ce document listait le **routeur 4G** comme « à acheter en entier ». David :
*« il y en a un dans le robot »*.

**La cause : le périmètre de l'inventaire n'avait pas été posé.** Les agents ont croisé le
stock avec les *études*, sans jamais ouvrir `overview.md` — qui est précisément l'inventaire
du matériel embarqué. Conclure « absent de l'inventaire du stock » donc « à acheter » est un
raisonnement faux, et c'est exactement le genre d'erreur que ce chantier existe pour éviter :
**il aurait fait racheter du matériel possédé.**

### Le projet a TROIS gisements de matériel, pas un

| Gisement | Où c'est écrit | État |
|---|---|---|
| **Le stock d'atelier** (bacs, tiroirs, colis) | `docs/hardware/inventaire-stock.md` | Dépouillé au 03/09, minorant |
| **Le matériel monté sur le robot** | `docs/hardware/overview.md` (961 l.) | Riche, mais **incomplet** — voir ci-dessous |
| **Ce qui a une pièce CAO** (donc possédé et intégré) | `~/…/didier/plans/` | Jamais croisé avec le reste |

**Règle à appliquer désormais — avant de conclure qu'une pièce manque, vérifier les TROIS.**
Une pièce absente du stock peut être simplement… déjà montée sur le robot.

### Conséquence : `overview.md` a des trous, et le robot n'a jamais été filmé

Le routeur 4G le prouve : il est **dans le robot** et **dans aucun document**. Ce n'est
donc pas seulement l'inventaire du stock qui est un minorant — `overview.md` aussi.

**Action ouverte** : filmer le robot comme l'atelier l'a été (David l'a lui-même proposé),
et compléter `overview.md`. Le même dépouillement s'applique, avec un avantage : le robot
est un objet fini, pas 200 bacs. Cadrage utile : baie électronique, cheminements, tout ce
qui porte une étiquette ou une LED, et **le dessous**.

---

## 3. Le FAN HAT Argon : la même pièce, trois avis opposés

Un `Argon Controllable FAN HAT` **neuf sous sachet** (`c0474`) a été rapproché
indépendamment par trois croisements. Les avis divergent, et c'est instructif :

| Étude | Intérêt | Réserve |
|---|---|---|
| Télédiagnostic | `ros2 bag` continu + Claude Code embarqué chauffent le Pi 4 | **Conflit de header 40 br.** : le GPIO porte déjà D16/D20/D21 et deux autres HAT (`SINTRON ST-009`, `clean Power GPIO-04`) |
| Voix | Le Pi 5 est en caisse close avec l'ampli, risque de throttling | Ajouter un ventilateur dans la caisse qui **porte le micro**, c'est injecter du bruit dans le problème qu'on résout |
| Conversation | — | ⚠️ **Contre-indication nette** : monté pendant la campagne D0, il relèverait le plancher de bruit et **fausserait la calibration du VAD** (seuils du §10.4 explicitement adossés à la chaîne actuelle) |

**Conclusion à retenir** : la pièce est là, gratuite, mais **elle ne doit pas être montée
pendant une campagne de mesure audio**. Compatibilité Pi 5 non établie non plus (le Pi 5 a
un connecteur ventilateur PWM dédié, géométrie différente).

---

## 4. Ce qui reste à acheter en entier — aucune contrepartie en stock

Dit explicitement pour que personne ne cherche deux fois :

⚠️ **Cette liste est à reprendre après le tournage du robot** (§2) : elle a été établie contre
le seul inventaire du stock, et elle a déjà produit deux faux « à acheter » (ReSpeaker,
routeur 4G). Ce qui suit ne vaut que **sauf présence sur le robot**.

| Besoin | Étude | Pourquoi rien en stock |
|---|---|---|
| ~~**Routeur 4G/5G**~~ | interface web §4 | ❌ **FAUX — David : « il y en a un dans le robot »**. Non documenté dans `overview.md` : à relever au tournage (modèle, bande, SIM/forfait, alimentation) |
| **Carte SD d'endurance** | télédiagnostic §6 | Aucune carte SD nue. Le `HW-125` est un **lecteur SPI pour microcontrôleur**, il ne stocke rien et ne remplace pas la carte de boot d'un Pi |
| **SBC / RAM Pi 4** | télédiagnostic §8 | Aucun Raspberry Pi 4/5 ni équivalent. Que des MCU (Pico, RP2040, Teensy, Arduino, ESP32). La RAM du Pi 4 est soudée de toute façon |
| ~~**Micro / array**~~ | conversation §5.5 | ❌ **FAUX** — le **ReSpeaker XVF3800** est en service et documenté (`overview.md`, + support CAO). Rien à acheter. *(Reste vrai : aucune capsule ni préampli en pièces détachées dans le stock, mais l'étude n'en demande pas.)* |
| **Accélérateur Hailo / Coral** | conversation §5.6 | Rien |
| **Fiches jack 3,5 mm à souder** | voix §6 | Les seuls 3,5 mm du stock sont **montés sur** l'isolateur `c0331` — pas des pièces détachées |
| **Coup-de-poing d'arrêt d'urgence** | interface web §2.2 | Voir §1 ci-dessus |

---

## 5. Ce qui devient actionnable sans rien acheter

- **Banc d'essai de portée radio, gratuit** : nRF24L01 (3-5, versions SMA et PCB), Dragino
  LoRa 868 + Heltec ESP32, plus les MCU aux deux bouts. L'étude web demande un « test de
  portée en salle » (l. 204) — il peut se faire ce week-end. ⚠️ Réserve de fond : l'étude
  exige un dispositif « indépendant de tout logiciel » ; **tout montage maison à base de ces
  modules EST du logiciel**. L'arbitrage produit du commerce vs maison appartient à l'étude.
  Réserve de bande : le 2,4 GHz est saturé en salle de spectacle (public + wifi du lieu) ; le
  868 a une **limite de rapport cyclique** mal adaptée à un lien devant émettre en continu.
- **Banc voix V0 montable sans achat** : fiches jack 6,35 TS/TRS (10-12), fil, gaine, et
  ~50 trimmers pour le pad d'atténuation — **sous réserve de lire leurs valeurs**, jamais
  filmées. Manque uniquement la fiche 3,5 mm côté Pi.
- **A/B manuel au banc** : 100+ micro-interrupteurs SPDT `t0173` permettent l'écoute alternée
  du §7-3 sans toucher aux relais ni au câblage — conforme au « aucune modification
  permanente » du lot V0.
- **Poussoir du bouton START** (télédiagnostic) : 40-60 poussoirs `OFF-(ON) 12VDC 0.05A`,
  cohérents avec une entrée GPIO. ⚠️ Le verrou de l'étude n'est **pas** la pièce, c'est
  qu'**aucun GPIO libre n'est documenté**. Et le sachet est de ceux qui mentent (voir §6).
- **Isolateur audio à transformateurs** (`c0331`) : essai de 10 min contre le ronflement,
  avant d'acheter une DI. Il éclate aussi L/R sur deux connecteurs, ce que demande le câble
  en Y du §6 voix. Ne couvre que le bruit passant par la masse audio.

---

## 6. Deux pièges confirmés par cette passe

1. **Les sachets mentent.** Le sachet `INTER À P…` qui contient les poussoirs est du même
   type que celui étiqueté « INTER A LEVIER » qui contenait des `SN74AHCT125N`. À ouvrir
   avant de s'y fier. (Règle de rangement associée : barrer l'étiquette d'un sachet
   réemployé — `rangement-atelier.md` §3.1e.)
2. **Les valeurs manquent partout.** Trimmers sans valeur, fusibles sans calibre, relais sans
   tension de bobine, cosses sans largeur, borniers sans pas. C'est le même angle mort que la
   « limite n° 2 » de l'inventaire. **Une pièce dont on ne connaît pas la valeur ne dispense
   pas d'acheter** — elle oblige juste à mesurer avant.

   > **Les trois vidéos du 03/09 ont confirmé que cet angle mort ne se ferme pas par
   > l'image.** On a filmé le bac de résistances sous trois angles pendant 40 % d'une vidéo :
   > la présence est acquise, les valeurs non. On a filmé les borniers verts dans cinq lots
   > différents : le pas reste inconnu. **Ce qui manque n'est pas de la pellicule, c'est un
   > pied à coulisse et des étiquettes retournées face caméra.**

---

## 7. Ce que ça ajoute à la liste atelier

À faire pendant l'étiquetage, le bac en main (s'ajoute à `inventaire-stock.md` §3) :

1. ✅ **Filmer le robot** (§2) — **FAIT le 03/09** : `docs/hardware/robot-embarque.md`.
2. **Lire sur le `YH02-A`** : accrochage ? contacts NO/NF ? **calibre DC** ? Trois questions
   qui décident s'il a une place quelconque dans un schéma (§1).
3. **Lire sur les modules relais** : calibre des contacts et tension de bobine (§1).
4. **Lire le calibre du coupe-circuit à goujons** `c0163`/`c0165` — c'est potentiellement le
   sectionneur de consignation du robot, gratuitement.
5. **Lire les valeurs des trimmers** `t0147` (~50) — débloque le pad du banc voix.
6. 🔸 **Le bac de résistances — filmé le 03/09, à moitié seulement.** Le bac **existe**
   (~20 sachets, plusieurs centaines de pièces) mais **7 valeurs seulement sont lisibles** :
   les rubans manuscrits étaient tournés vers le fond. À refilmer **sachet par sachet, ruban
   face caméra, 2 s par sachet**. Les **céramiques**, elles, n'ont toujours jamais été
   filmées. Reste le meilleur rapport effort/gain de la liste.
7. **Le test JST à dix secondes** (`inventaire-stock.md` §1.2) : enfoncer un contact de
   chaque casier dans un boîtier 4 points. S'il verrouille, **trois lignes** de la
   nomenclature d'odométrie tombent. C'est le geste le plus rentable de tout le chantier.
8. **Le pied à coulisse**, une fois sorti, règle d'un coup : le pas des **borniers verts**
   (300+ pièces inexploitables sans lui), celui des **boîtiers JST**, et le filetage des
   **entretoises laiton** (M2.5 vs M3). Trois angles morts, un seul outil.
