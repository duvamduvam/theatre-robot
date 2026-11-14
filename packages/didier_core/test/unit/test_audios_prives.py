"""Audios privés (lot du 14/11, décision de David du 13/11) : les fichiers sonores de Didier
(dont des chansons du commerce) ne sont plus dans le dépôt PUBLIC. Ils vivent dans
$DIDIER_MEDIAS_PRIVES/audios/ (défaut ~/Nextcloud/dev/didier/medias-prives/audios), hors git ;
le dépôt n'en garde que le manifeste data/json/audios-prives.json (chemin, sha256, taille,
durée). Ce fichier grave les garde-fous anti-fuite :
 - aucun fichier dont le sha256 figure au manifeste n'est dans l'arbre de git (suivi, ou
   nouveau et non ignoré : le prochain `git add` le publierait), où qu'il soit, même renommé ;
 - data/medias/audios/ ne suit que son README ;
 - ni l'écrivain des données (porte sim, data_edit) ni le rapatriement n'écrivent sous
   medias/audios/ : leur table de cibles (donnees.KINDS) ne l'atteint pas.
L'historique git n'est PAS réécrit (décision de David) : les anciens commits portent encore
les fichiers, ce test ne parle que de l'arbre.
"""
import json
import os
import subprocess

import pytest

from theatre_contrats import donnees

MONO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))
DATA_ROOT = os.path.join(MONO, "data")
MANIFESTE = donnees.lire_manifeste_audios(DATA_ROOT)
DOSSIER_PRIVE = donnees.dossier_audios_prives()


def fichiers_de_l_arbre_git():
    """Chemins (relatifs à MONO) suivis par git ou nouveaux et non ignorés."""
    sortie = subprocess.run(
        ["git", "-C", MONO, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True, capture_output=True).stdout
    return sorted({c for c in sortie.decode("utf-8", "surrogateescape").split("\0") if c})


def test_le_manifeste_porte_les_254_audios_du_14_11():
    # Gravé le 14/11 (254 .mp3/.wav sortis du dépôt). Un audio ajouté : regraver ce nombre.
    assert len(MANIFESTE) == 254
    with open(os.path.join(DATA_ROOT, donnees.FICHIER_MANIFESTE_AUDIOS), encoding="utf-8") as f:
        assert json.load(f)["version"] == donnees.VERSION_MANIFESTE_AUDIOS


@pytest.mark.parametrize("relatif", sorted(MANIFESTE))
def test_chaque_entree_du_manifeste_est_bien_formee(relatif):
    entree = MANIFESTE[relatif]
    assert donnees.MOTIF_FICHIER_AUDIO.match(relatif)
    assert not relatif.startswith("/") and ".." not in relatif.split("/") and "\\" not in relatif
    assert set(entree) == {"sha256", "taille", "duree_s"}
    assert len(entree["sha256"]) == 64 and set(entree["sha256"]) <= set("0123456789abcdef")
    assert isinstance(entree["taille"], int) and entree["taille"] > 0


def test_aucun_audio_du_manifeste_dans_l_arbre_git():
    # Le sha seul fait foi (un fichier renommé ou déplacé se voit) ; la taille ne sert qu'à
    # ne hacher que les candidats (2 000 fichiers suivis, 254 tailles).
    shas = {e["sha256"] for e in MANIFESTE.values()}
    tailles = {e["taille"] for e in MANIFESTE.values()}
    fuites = []
    for relatif in fichiers_de_l_arbre_git():
        chemin = os.path.join(MONO, relatif)
        if os.path.isfile(chemin) and not os.path.islink(chemin) and os.path.getsize(chemin) in tailles:
            if donnees.sha256_fichier(chemin) in shas:
                fuites.append(relatif)
    assert fuites == [], "audio privé dans l'arbre git (dépôt PUBLIC) : {}".format(fuites)


def test_data_medias_audios_ne_suit_que_son_readme():
    suivis = [c for c in fichiers_de_l_arbre_git() if c.startswith("data/medias/audios/")]
    assert suivis == ["data/medias/audios/README.md"]


def test_ni_l_ecrivain_ni_le_rapatriement_n_ecrivent_sous_medias_audios():
    # Le rapatriement (deploy/rapatrier_editions.py) et data_edit_node n'écrivent que les
    # cibles de donnees.KINDS : aucune n'est un audio, aucune n'est sous medias/audios/.
    for cible in donnees.KINDS.values():
        assert not cible.startswith(donnees.DOSSIER_AUDIOS)
        assert not donnees.MOTIF_FICHIER_AUDIO.match(cible)


@pytest.mark.skipif(not os.path.isdir(DOSSIER_PRIVE), reason="dossier privé absent (CI GitHub)")
def test_le_dossier_prive_est_exactement_le_manifeste():
    # PC de David : chaque audio présent avec son sha, aucun hors manifeste (sinon régénérer :
    # python3 -m theatre_contrats.donnees manifeste-audios data, docs/operations.md).
    fautes, en_trop = donnees.ecarts_audios(MANIFESTE, donnees.sommes_du_dossier(DOSSIER_PRIVE))
    assert (fautes, en_trop) == ([], [])


EXTENSIONS_AUDIO = (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus")


def test_aucun_fichier_audio_suivi_nulle_part():
    """Gravé le 14/11 (décision de David : « tout déclarer ») : le dépôt public ne suit AUCUN
    fichier audio, quel que soit son dossier — le test du manifeste ne voyait pas les 140
    copies de la télécommande ni les 4 sorties de synthèse vocale qui n'y figuraient pas."""
    audios = [f for f in fichiers_de_l_arbre_git() if f.lower().endswith(EXTENSIONS_AUDIO)]
    assert audios == []
