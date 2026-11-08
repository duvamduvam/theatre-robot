# Étude — Didier interagit même en mouvement (08/11)

Née de la séance A1 au casque du 08/11 (`seances/2026-11-08-a1-casque.md`, « pas jouable ») :
Didier annonce qu'il part et ne bouge pas, dit que les poubelles sont à sa droite alors qu'elles
sont à 23 m devant, et s'exprime toutes les 3-10 s sans qu'on puisse le suivre. David : « tout
l'intérêt de la simulation, c'est quand même de bouger ».

## 1. Le problème en une phrase

**La bouche et le corps ne se parlent que dans un sens.** La bouche commande (go, stop, aller
voir, tourner) ; le corps obéit ou refuse, mais la bouche n'apprend ni l'état du corps, ni où il
est, ni ce qu'il y a autour. Elle comble les trous en inventant, parce qu'un LLM comble toujours.

## 2. Ce qui existe déjà (rien à réinventer)

| Le corps publie | Qui le lit aujourd'hui |
|---|---|
| `route_state` on/off + `route_state_cause` (boot, cmd…), latchés | réflexion : « Tu marches / Tu es arrêté » |
| `route_speed` 0..1 | réflexion (vitesse 0 = arrêté par le régisseur) |
| `rehearsal/state` (séance en attente / en cours / terminée), latché | la page seulement |
| `jeu/intention` : action, cible, pourquoi, **verrou** (STOP console posé), latché | la page seulement |
| `rehearsal/poi_event` enter/exit | réflexion : « Tu es devant : … » (30 s) |
| `rehearsal/objects` : 30 noms + description, **sans position** | bouche (liste « aller voir ») |
| `/ground_truth/odom` : position et cap vrais ; `chantiers.yaml` : x, y de chaque objet | régisseur seul |
| `route_goto_result` (arrivé / trop loin / route off) | bouche (fin d'un geste, lot M4) |

Côté écoute : depuis ce soir le micro reste ouvert pendant les gestes (`CHAT_MICRO_CONFIANCE`).
La règle de juillet « micro armé seulement à l'arrêt » (`etude-declenchement-conversation.md`
§5.2) visait les **passants** par le micro du châssis, avec le bruit des moteurs ; elle ne
s'applique pas à David au casque ni, demain, au bouton.

## 3. Ce qui manque — trois trous, par ordre de gravité

**A. La bouche ignore l'état du corps.** Elle dit « c'est parti » sous un STOP console, et ses
« go » tombent « hors séance » sans qu'elle le sache. Tout est déjà publié (`jeu/intention.verrou`,
`rehearsal/state`, `route_state_cause`) : il manque trois abonnements et trois phrases au tableau
de situation (« Ton corps est verrouillé : David t'a arrêté, seul son GO te libère » ; « La séance
n'est pas lancée : tes go sont ignorés »). Zéro nouveau topic.

**B. La bouche ignore l'espace.** Le régisseur sait tout (pose vraie, cap, position des 30
objets) et ne publie que les entrées/sorties de rayon. Proposition : un topic latché
`rehearsal/nearby` — les 3 objets les plus proches, chacun avec **côté relatif au cap** (devant,
gauche, droite, derrière) et **distance en mètres**, republié quand ça change (≥ 1 m ou changement
de côté), SIM-ONLY comme tout `rehearsal/*`. La bouche l'ajoute au tableau de situation
(« Autour de toi : poubelles de tri 23 m devant, un peu à gauche ; banc 8 m à droite ») et sa
consigne devient : **ne jamais situer un lieu absent du tableau** — « je ne sais pas où c'est »
est une réplique valable, en personnage. Sur le vrai robot, le même topic viendra un jour du
lidar et de la carte (lots A) ; d'ici là la bouche dira qu'elle ne sait pas, ce qui est vrai.

**C. Le rythme.** Une expression spontanée toutes les 3-10 s (l'ennui monte à 0,40 en quelques
secondes) : David ne peut pas placer une phrase, et Didier paraît mécanique. Réglage dans
`didier_jeu/config/reglages.yaml` (gravé en test), pas de code.

## 4. Ce qui ne change pas

- **Le sélecteur reste le seul décideur du corps** (décision du 02/11). La bouche ne lève pas un
  STOP console ; elle apprend qu'il existe et le dit.
- **Didier répond en marchant** sans s'arrêter : c'est déjà le cas (la conversation ne touche pas
  la route ; `stop` n'est envoyé que sur demande ou vraie raison). Les tours **spontanés** en
  marche restent limités à l'objet croisé (décision du 31/10).
- L'étude §10.10 (micro fermé sur le son) reste en veille pour les passants.

## 5. À trancher

| # | Question | Proposition |
|---|---|---|
| 1 | Qui raconte l'espace à la bouche ? | Le régisseur (`rehearsal/nearby`, sim) ; sur le robot, plus tard, la perception. La bouche ne devine jamais |
| 2 | Quelle précision ? | 4 côtés relatifs au cap + mètres arrondis ; 3 objets au plus (chaque caractère coûte de la latence à chaque réplique) |
| 3 | Didier doit-il dire qu'il est verrouillé quand on lui demande d'avancer ? | Oui, en personnage (« tu m'as arrêté, toi, appuie sur GO ») ; il ne se libère pas lui-même |
| 4 | Séance : la bouche la lance-t-elle quand on lui parle de partir ? | Non — c'est l'affaire de la page (refonte « cockpit », lot à part) ; la bouche dit seulement « la séance n'est pas lancée » |
| 5 | Rythme des spontanées | Une toutes les 30-60 s au repos, aucune quand David vient de parler (< 20 s) |

## 6. Lots (si les propositions tiennent)

- **M6 « le corps raconte »** (Opus, ~2 h) : A + B + C. Abonnements et tableau côté
  `didier_vision` (situation.py, reflection_node, personas), `rehearsal/nearby` côté
  `didier_rehearsal` (director ou route_driver : celui qui a déjà pose + objets), règle de prompt,
  réglages A1. Tests gravés : composition du tableau avec verrou/séance/nearby ; côté relatif
  (4 quadrants, cap tourné) ; republication seulement au changement. Vérif en sim : séance de
  10 min, Didier situe les poubelles juste et refuse de « partir » sous STOP.
- Ensuite, lot à part : la page scène pour **jouer** (cockpit → quelques commandes).
