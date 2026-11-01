# Télédiagnostic par agent IA — plan du chantier

*Étude du 2026-07-12, grillée le jour même. Statut : **plan décidé** (décisions
en §8, toutes tranchées par David). Historique : la v1 proposait un agent côté
PC via VPN ; David a challengé (« pourquoi du VPN, je veux un agent sur la
RPi ») → v2 instruite à fond (docs officielles + inventaire des deux dépôts),
puis grill complet.*

## 1. Le besoin

En déambulation (robot au milieu du public, David occupé à jouer), des pannes
surviennent qu'on ne peut pas régler sur place : visage figé, servo muet, node
crashé, audio silencieux… Et elles sont souvent **fugaces** : le temps de
rentrer, plus rien à voir. Un **agent IA embarqué investigue** — déclenché
depuis la télécommande — capture l'état, explique, et répare ce qu'il a le
droit de réparer.

## 2. Ce que l'agent peut lire aujourd'hui (état des lieux)

Inventaire du code au 2026-07-12 :

| Point de lecture | Contenu | Limite |
|---|---|---|
| `robot.log` (sur la carte SD du Pi, **hors conteneur** — survit à un crash du conteneur ; rotation quotidienne) | erreurs de payload, entrées de chaque node, commandes web, alertes système (CPU > 80 %, mémoire, disque, température > 55 °C) | niveau INFO figé ; très verbeux (~16 Mo/jour) |
| `docker logs dadou-robot-container` | la sortie ROS — dont **tout le pont web** (il logge par `get_logger()`, PAS dans robot.log) | **deux journaux séparés**, piège connu |
| Message `state` du pont web (port 8765, toutes les 2 s) | **liste des nodes vivants** (seul moyen de voir un node crashé), dernier message + âge par topic de contenu | rien sur CPU/température/batterie, rien sur la chaîne roues |
| Le graphe ROS en direct | `ros2 topic echo/hz/list` dans le conteneur | temps réel seulement — rien après coup |

**Les trous** (balayage complet du code) :
1. **Zéro rosbag** dans tout le repo : aucun enregistrement des événements ROS.
   L'incident fugace est irrécupérable. C'est LE chaînon manquant → §6.
2. **Zéro topic de santé** : les alertes CPU/température finissent dans le
   fichier log et nulle part ailleurs ; batterie sans capteur (code commenté).
3. **Exceptions invisibles** : les nodes principaux avalent leurs exceptions
   (log puis on continue) ; `twist_deadman`, `person_follower` et
   `gaze_follower` **meurent** sur exception — visibles seulement par leur
   absence dans `state`.
4. Pièges pour l'agent : mDNS `.local` instable (IP : robot .2, vision .151),
   payload non-JSON refusé, `chat_node` qui écrase `face`, deux configs de
   logging dont une obsolète (`conf/logging/*.conf` n'est plus chargée).

## 3. Architecture (décidée : hybride)

### Le malentendu VPN, dissipé

**Un VPN ne sert qu'à ENTRER sur le robot depuis l'extérieur.** L'agent
embarqué n'a besoin que de SORTIR en HTTPS vers `api.anthropic.com` (port 443,
seul point de contact requis — doc officielle). En déambulation, un partage de
connexion du téléphone suffit. Le VPN Headscale du chantier web reste utile
pour la télé-présence ; **le diagnostic embarqué n'en dépend pas**.

### Terrain : agent embarqué sur le Pi robot

Claude Code s'installe **sur le host du Pi, HORS du conteneur ROS** (binaire
natif ARM64, supporté officiellement, prérequis 4 Go de RAM — RAM du Pi à
vérifier, §8 préalables). Hors conteneur c'est voulu : **l'agent doit survivre
à la mort du conteneur** — c'est précisément une des pannes à diagnostiquer.
Depuis le host il voit robot.log, `docker logs`, et entre dans le conteneur
par `docker exec` pour l'introspection ROS.

- **Lancement** : un service systemd du host guette le signal (§5) et lance
  `claude -p "investigue" …` en mode non-interactif. Garde-fous natifs :
  limite de tours, plafond de coût, timeout shell, sortie JSON.
- **Authentification (décidé)** : **l'abonnement Claude de David** — token
  OAuth longue durée généré par `claude setup-token` (sur le PC), déposé sur
  le Pi en variable d'env (`CLAUDE_CODE_OAUTH_TOKEN`), hors repo. Coût
  marginal nul ; les investigations consomment le quota de l'abonnement
  (négligeable à quelques investigations par semaine).
  *Écarté : la clé OpenRouter du chat_node — l'endpoint compatible existe,
  mais le prompt caching n'y fonctionne pas : en agentique (chaque tour
  renvoie le contexte) l'investigation coûterait 5-10× plus cher, plus 5,5 %
  de frais. Le chat_node, lui, reste sur OpenRouter (requêtes courtes, rien
  ne change).*
- **Modèle (décidé)** : **Opus** par défaut.
- **Verrouillage PAR CONFIG** (pas par consigne) : liste blanche d'outils et
  de motifs de commandes (`tail`, `grep`, `ros2 topic echo`, `docker logs`…),
  interdiction d'écrire hors de son dossier de rapports — plus les
  remédiations décidées en §7.

### Atelier : session Claude sur le PC (comme aujourd'hui)

Pour l'analyse approfondie, les correctifs et l'archéologie git (le `.git`
n'est pas rsyncé sur le Pi — l'agent embarqué n'a pas l'historique). Accès SSH
en LAN. Les deux agents partagent les mêmes fondations : skill `/diag`,
journal d'incidents, format de rapport.

## 4. Le contexte de l'agent (la question « RAG ? »)

Fait vérifié : le déploiement Ansible rsync **tout le checkout** sur le Pi —
`docs/`, `CLAUDE.md`, le code, les JSON. L'agent embarqué a donc le même
corpus que celui du PC (sauf `.git`). Claude Code cherche nativement par
grep/lecture ciblée : à cette échelle (quelques centaines de Ko de docs),
**un RAG vectoriel n'apporterait rien** — de l'infrastructure pour un gain
nul. À réévaluer seulement si le corpus change d'ordre de grandeur.

Le contexte **métier de panne**, lui, se construit avec deux fichiers :
1. **Le skill `/diag`** : carte des points de lecture (§2), commandes exactes,
   pièges connus, droits et interdits (§7). Le « briefing » de tout agent,
   embarqué ou PC.
2. **Le journal d'incidents** (`docs/incidents/`) : chaque investigation se
   termine par un court post-mortem (symptôme, cause, remède, date). L'agent
   suivant les lit — c'est la mémoire de panne du robot, et le vrai « RAG »
   utile. Rsyncé avec le reste ; les post-mortems du terrain remontent au
   repo à la main (ou par le rsync retour à prévoir).

## 5. Déclencheurs (décidés : les quatre, dans cet ordre)

1. **Bouton START de la télécommande** (V1) — libre sur le GPIO (D21) ET sur
   la manette USB (START/SELECT/MODE libres tous les trois ; vérifié dans
   `dadou_control_ros`). **Appui long ~2 s** contre la fausse manip. Publie le
   topic `incident` — à créer : l'ajouter à `PUBLISHER_LIST` (la télécommande
   ne publie que ses 14 topics whitelistés).
2. **Bouton logiciel « incident »** (V1) — dans la barre de menu de la GUI
   télécommande et dans la console web (backstage, atelier).
3. **Bouton physique sur le robot** (après vérif matérielle) — le mécanisme
   logiciel existe (`Status.check_button`, comme extinction D16 /
   redémarrage D20) mais **aucun GPIO libre n'est documenté** : à identifier
   sur le matériel d'abord. Et penser à le placer hors de portée du public.
4. **Vocal** (« Didier, note le problème ») — parqué derrière chat_node V2
   (priorité 0) ; l'infrastructure `incident` sera prête à l'accueillir.

Déclencheurs automatiques (capture seule, pas d'investigation lancée toute
seule) : node disparu du graphe (le pont web le voit), alertes système
répétées → marqueur + dump, l'humain décide s'il investigue.

## 6. La boîte noire (décidée : segments SD, un mois, sans caméra)

`ros2 bag record` en continu, **par segments sur la carte SD** (tranches de
60 s), purge au-delà de **30 jours** — la rétention des logs texte est alignée
sur 30 jours au passage (aujourd'hui 100). Survit à tout, y compris un crash
du conteneur en plein enregistrement ; l'usure SD est le prix assumé de cette
robustesse. Topics enregistrés (légers, quelques centaines de Mo/mois) :
`cmd_vel*`, `e_stop`, `animation`, `face`, `audio`, `robot_lights`, servos,
`gaze`/`follow`, `/vision/person*`, `incident`, futur topic santé.
**La caméra n'est PAS enregistrée** (décidé — ~0,5 Go/h et usure en
proportion ; les détections `/vision/person*` suffisent à dire ce que le
robot percevait).

### Deuxième usage, apparu le 2026-08-26 : l'étude d'APRÈS-SHOW

La boîte noire n'a pas été pensée que pour l'après-incident. Le chantier voix
([`etude-voix-didier.md`](etude-voix-didier.md) §7, lot V0b) a besoin de savoir
si le TTS tient sur le Pi 5 **une fois la charge vision présente** — donc de la
**courbe** d'une représentation entière, pas d'un instantané. Or aujourd'hui
`robot.log` ne trace que des dépassements de seuil et `collect-incident.sh`
n'est qu'une photo : ni l'un ni l'autre ne répond.

Ça précise le contenu du **topic santé** déjà listé ci-dessus (§2 le pointe
comme un manque : « zéro topic de santé », les alertes finissent dans le log et
nulle part ailleurs). À 1 Hz, il doit porter : CPU **par cœur** (un pic sur un
cœur n'a pas le même sens qu'une charge répartie), fréquence, température,
**masque `get_throttled`**, RAM disponible, et de quoi attribuer la charge
(vision / parole). Un seul producteur, trois consommateurs : l'enregistrement,
la console web et l'agent embarqué.

⚠️ **`get_throttled` est latché** (bits 16-19 = sous-tension ou throttling
survenus depuis le boot). C'est le seul indicateur qui dit encore la vérité sur
un robot refroidi — donc dans le cas normal d'une collecte faite *après* coup.
Il a été ajouté à `collect-incident.sh` le 26/08 ; il manquait.

En attendant le topic santé, `conf/scripts/log-charge.sh` produit la même série
temporelle en CSV depuis le host (lecture `/proc`, sans fork par échantillon).
C'est un dépannage assumé, pas la cible : il ne voit pas les topics ROS et il
faut le lancer à la main.

L'appui sur START écrit aussi un marqueur `INCIDENT` horodaté dans robot.log :
bags, logs et rapport sont corrélables. En complément,
`conf/scripts/collect-incident.sh` rassemble tout (tail des logs, état du
graphe, températures, disque, extrait de bag) en un tarball horodaté — le
format d'entrée standard de toute investigation, humaine ou IA.

## 7. Droits de l'agent (décidés : remédiations autonomes encadrées)

La lecture est libre (dans la liste blanche de commandes). Pour l'action,
David a tranché **contre** la confirmation systématique : c'est précisément
en représentation, quand il ne peut pas confirmer, qu'il a besoin de l'agent.
**L'agent répare donc de façon autonome**, dans un cadre strict :

- **Actions autorisées** (liste blanche, rien d'autre) : restart du conteneur
  robot, restart du conteneur vision, relance de la chaîne drive. Toutes sont
  **sûres côté roues** : un conteneur qui tombe = deadman = arrêt (validé par
  crash-test `docker kill`). Jamais aucune publication sur un topic de
  mouvement.
- **Seulement sur composant constaté mort** (node absent du graphe, conteneur
  unhealthy, flux tari) — jamais sur soupçon : le remède pire que le mal
  (redémarrer un robot qui marchait, en public) est le risque n°1.
- **Anti-boucle** : un seul restart par incident. Si ça n'a pas réglé le
  problème, l'agent rapporte au lieu de recommencer.
- **Annonce avant action** : une phrase au topic `audio` (« je redémarre dans
  cinq secondes ») — le black-out scénique de ~40 s est signalé, pas subi.
- Budget par investigation borné + timeout ; token d'abonnement révocable.

## 8. Décisions (grillées le 2026-07-12) et préalables

| # | Décision | Choix |
|---|---|---|
| 1 | Où tourne l'agent | **Hybride** : embarqué sur le host du Pi (terrain) + session PC (atelier) |
| 2 | Modèle & facturation | **Opus**, sur **l'abonnement Claude** (token `claude setup-token` sur le Pi) ; OpenRouter écarté (pas de caching → 5-10× plus cher) |
| 3 | Déclencheurs | **Les quatre**, ordonnés : START télécommande + bouton GUI/console (V1) → bouton physique robot (après vérif GPIO) → vocal (après chat_node V2) |
| 4 | Restitution | **Console web** (panneau Diagnostic) + **voix** (résumé une phrase ; rapport long hors public) + **notification téléphone** (ntfy auto-hébergé ou équivalent, à chiffrer) |
| 5 | Boîte noire | **Segments SD en continu, rétention 30 jours, sans caméra** ; logs texte alignés à 30 jours |
| 6 | Remédiations | **Autonomes y compris en représentation**, encadrées : liste blanche de restarts, composant mort constaté, anti-boucle, annonce vocale |
| 7 | Batterie | **Parquée** vers le chantier élec (cartes PCB) ; le topic santé l'accueillera quand le capteur existera |

**Préalables factuels avant construction** :
- RAM du Pi 4 : `ssh r 'cat /proc/meminfo'` (non documentée nulle part — si
  2 Go, redimensionner l'ambition embarquée).
- Charge d'une investigation pendant le tick 20 Hz : à mesurer (`nice` prévu).
- Espace libre et santé de la carte SD (l'enregistrement continu s'y ajoute).
- Qualité du partage 4G téléphone en condition de salle.

## 9. Ordre de construction

Chaque étape est utile seule ; on peut s'arrêter à n'importe laquelle :

1. **Trousse d'atelier** — **FAITE le 2026-07-12** :
   `conf/scripts/collect-incident.sh` (testé de bout en bout contre la sim —
   host, best-effort, retente sur `node list` vide au premier appel du daemon),
   skill `/diag` (`.claude/skills/diag/`), journal `docs/incidents/`.
   Dès la prochaine déambulation : retour, session Claude sur le PC,
   investigation sur les traces existantes. Zéro déploiement sur le robot
   (le script part avec le rsync habituel).
2. **Boîte noire + bouton** — enregistreur par segments dans le bringup,
   purge 30 jours, topic `incident`, bouton START télécommande + boutons
   logiciels, marqueur robot.log, endpoints de lecture sur le pont web
   (`/api/logs`, `/health`), topic santé publié par system_node. Validé en
   sim d'abord (domain 43), comme tout.
3. **Agent embarqué** — Claude Code sur le host du Pi (préalables §8 levés),
   token d'abonnement, service de déclenchement, permissions verrouillées,
   remédiations §7, rapport console + voix + notification. Répétition
   générale en atelier : provoquer une panne connue, appuyer sur START, lire
   le rapport, vérifier le restart autonome et son annonce.
4. **Itinérance** — partage 4G du téléphone (puis routeur 4G du flight case
   quand le chantier web l'apportera) ; test en condition réelle de salle.
