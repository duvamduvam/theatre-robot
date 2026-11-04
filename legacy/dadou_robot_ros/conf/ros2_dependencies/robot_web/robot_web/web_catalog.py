"""Catalogue des boutons de l'UI web, logique 100% PURE (pathlib + json
stdlib uniquement -- aucun import rclpy/aiohttp/robot/dadou_utils_ros, même
garde-fou AST que web_protocol.py).

Chaque entrée associe un LIBELLÉ (affiché) à une VALEUR (publiée telle quelle
sur le topic, sérialisée ensuite par json.dumps côté node -- exactement comme
la télécommande, voir docs/interfaces.md). Les valeurs à publier sont celles
RÉELLEMENT consommées par le code robot (vérifié en lisant robot/actions/*.py,
pas supposées) :

 - "faces"        : clés de expressions.json (Face.update fait
                     self.sequences_name[msg[FACE]], la clé EST la valeur) ;
 - "audios"       : champ "path" de chaque entrée de audios.json
                     (AudioManager.update, branche `AUDIO in msg` : appelle
                     play_sound(msg[AUDIO]) avec un CHEMIN, pas la clé --
                     contrairement à faces/robot_lights). Les entrées à path
                     vide (ex. "stop", qui n'existe que pour le mapping
                     clavier legacy KEY) sont exclues : publier "" casserait
                     play_sound() sans rien jouer ; le bouton STOP CONTENUS
                     couvre déjà l'arrêt audio (stop_all_commands()) ;
 - "animations"   : noms de séquences sous json/sequences/** (sans extension,
                     AnimationManager les indexe par basename via
                     AbstractJsonActions.load_multi_files_sequences -- un nom
                     dupliqué entre deux sous-dossiers écrase le premier à la
                     lecture, limite EXISTANTE non corrigée ici, cf.
                     test_sequences_assets.py) ;
 - "relays"       : clés de relays.json (Relay.update indexe par nom, même
                     mécanique que faces) ;
 - "robot_lights" : clés de robot_lights.json -- PAS lights.json, qui décrit
                     un autre projet de séquences (config[JSON_LIGHTS] =
                     'robot_lights.json' dans robot/robot_config.py, c'est le
                     fichier réellement chargé par Lights pour le topic
                     robot_lights).
 - "visuals"      : noms de visuals.json (`{"visual": [{"name", "path"}]}`) --
                     la 6e famille du catalogue publié par catalogue_node (L1c) ;
                     la page web ne la consomme pas encore.

Fichier manquant/illisible -> entrée vide + WARNING loggué, JAMAIS d'exception
(le robot doit pouvoir tourner sans catalogue complet, ex. json/ pas encore
monté/synchronisé).
"""

import json
import logging
import pathlib

logger = logging.getLogger(__name__)


def _load_json_dict(path: pathlib.Path) -> dict:
    """Charge un fichier JSON en dict ; {} + WARNING si absent/illisible."""
    try:
        with path.open() as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("catalogue web : %s illisible (%s)", path, e)
        return {}

    if not isinstance(data, dict):
        logger.warning("catalogue web : %s n'est pas un objet JSON", path)
        return {}
    return data


def _build_faces(json_dir: pathlib.Path) -> list:
    return sorted(_load_json_dict(json_dir / "expressions.json").keys())


def _build_relays(json_dir: pathlib.Path) -> list:
    return sorted(_load_json_dict(json_dir / "relays.json").keys())


def _build_robot_lights(json_dir: pathlib.Path) -> list:
    return sorted(_load_json_dict(json_dir / "robot_lights.json").keys())


def _build_visuals(json_dir: pathlib.Path) -> list:
    """Noms triés de visuals.json["visual"] ; [] + WARNING si absent, illisible
    ou mal formé (même contrat « jamais d'exception » que les autres familles)."""
    visuals = _load_json_dict(json_dir / "visuals.json").get("visual")
    if not isinstance(visuals, list):
        logger.warning("catalogue web : visuals.json sans liste \"visual\"")
        return []
    return sorted({v["name"] for v in visuals
                   if isinstance(v, dict) and isinstance(v.get("name"), str)})


def _build_audios(json_dir: pathlib.Path) -> list:
    """[{"label": clé, "value": path}] -- entrées à path vide exclues (voir
    docstring de module : "stop" n'est pas une valeur AUDIO publiable)."""
    audios = _load_json_dict(json_dir / "audios.json")
    entries = []
    for label, entry in sorted(audios.items()):
        path = entry.get("path") if isinstance(entry, dict) else None
        if path:
            entries.append({"label": label, "value": path})
    return entries


def _build_animations(json_dir: pathlib.Path) -> list:
    sequences_dir = json_dir / "sequences"
    if not sequences_dir.is_dir():
        logger.warning("catalogue web : %s absent", sequences_dir)
        return []
    # set() : un même nom peut exister dans deux sous-dossiers (limite connue
    # d'AnimationManager, cf. docstring) -- on ne publie chaque nom qu'une fois.
    names = {p.stem for p in sequences_dir.glob("**/*.json")}
    return sorted(names)


def build_catalog(json_dir: pathlib.Path) -> dict:
    """Construit le catalogue complet consommé par GET /api/catalog."""
    json_dir = pathlib.Path(json_dir)
    return {
        "faces": _build_faces(json_dir),
        "audios": _build_audios(json_dir),
        "animations": _build_animations(json_dir),
        "relays": _build_relays(json_dir),
        "robot_lights": _build_robot_lights(json_dir),
        "visuals": _build_visuals(json_dir),
    }


def read_deploy_sha(path: str) -> str:
    """Sha git déployé, lu dans le fichier écrit par Ansible au rsync.

    Fichier absent, vide ou illisible -> "dev" (sim, poste de dev : jamais de
    fichier). Le suffixe "-dirty" éventuel est conservé tel quel : il dit que
    l'arbre rsyncé n'était pas un commit propre.
    """
    if not path:
        return "dev"
    try:
        contenu = pathlib.Path(path).read_text().strip()
    except OSError:
        return "dev"
    return contenu or "dev"
