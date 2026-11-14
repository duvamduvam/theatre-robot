"""JSON restants de la télécommande (L1d-5, décision 14) : la liste EXACTE des 10 fichiers.

Depuis L1d-5, 61 JSON de `json/` ont été supprimés (rien de lancé ne les lisait). Restent les
10 que lit `SmallGui` : 3 à la racine (`ControlJsonManager.__init__`) et 7 playlists
(`small_playlist.py`). Ils partent avec la télécommande à L4. Le test grave la LISTE, pas le
contenu : un fichier de plus ou de moins doit être un choix, pas un accident.

Passe de mutation — chaque ligne doit rougir :
  - recréer json/relays.json : test_liste_exacte
  - renommer lights_methods.json : test_liste_exacte et test_gestionnaire_se_construit
  - corrompre une playlist : test_chaque_playlist_se_charge
"""
import pathlib

import pytest

from controller.control_config import config
from controller.control_static import PLAYLISTS
from controller.files.control_json_manager import ControlJsonManager
from dadou_utils_ros.utils_static import JSON_DIRECTORY

JSON_DIR = pathlib.Path(__file__).resolve().parents[3] / "json"

RESTANTS = [
    "expressions.json",
    "lights_base.json",
    "lights_methods.json",
    "playlists/didier20_bis.json",
    "playlists/eternel-short.json",
    "playlists/eternel-short2.json",
    "playlists/grandlieu.json",
    "playlists/maker_fair.json",
    "playlists/playlist3.json",
    "playlists/pub1.json",
]


@pytest.fixture
def json_local(monkeypatch):
    # Sur l'hôte, le chemin par défaut est celui du Pi : on vise le dossier du dépôt.
    monkeypatch.setitem(config, JSON_DIRECTORY, str(JSON_DIR) + "/")


def test_liste_exacte():
    trouves = sorted(str(p.relative_to(JSON_DIR)) for p in JSON_DIR.rglob("*.json"))
    assert trouves == RESTANTS


def test_gestionnaire_se_construit(json_local):
    ControlJsonManager()


@pytest.mark.parametrize("playlist", [p for p in RESTANTS if p.startswith("playlists/")])
def test_chaque_playlist_se_charge(json_local, playlist):
    donnees = ControlJsonManager().open_json(PLAYLISTS + "/" + playlist.split("/")[1])
    assert isinstance(donnees, dict)
