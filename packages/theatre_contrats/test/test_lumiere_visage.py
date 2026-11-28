"""Le corps suit le visage, sauf commande explicite (theatre_contrats.lumiere_visage).
Valeurs attendues gravées en dur."""
from theatre_contrats.lumiere_visage import STOP, CorpsSuitVisage


def test_le_corps_suit_le_visage():
    a = CorpsSuitVisage()
    assert a.visage("joie") == "joie"
    assert a.visage("colere") == "colere"


def test_meme_lumiere_pas_rejouee():
    a = CorpsSuitVisage()
    assert a.visage("joie") == "joie"
    assert a.visage("joie") is None  # deux expressions liées à la même lumière : pas de saut


def test_expression_sans_corps_rend_le_repos():
    a = CorpsSuitVisage()
    a.visage("colere")
    assert a.visage(None) == STOP
    assert a.visage(None) is None  # déjà au repos : rien


def test_expression_sans_corps_ne_touche_pas_un_corps_que_le_visage_ne_tient_pas():
    a = CorpsSuitVisage()
    assert a.visage(None) is None
    assert a.visage("") is None


def test_commande_explicite_gagne_sur_le_visage():
    a = CorpsSuitVisage()
    a.commande("trip")                 # une séquence pose sa lumière
    assert a.visage("joie") is None    # le visage ne l'écrase pas
    assert a.visage(None) is None


def test_fin_de_commande_reprend_la_lumiere_du_visage_en_cours():
    a = CorpsSuitVisage()
    a.commande("scan")
    a.visage("amour")
    assert a.fin_commande() == "amour"
    assert a.fin_commande() is None    # déjà libéré


def test_fin_de_commande_sans_visage_lie_ne_rejoue_rien():
    a = CorpsSuitVisage()
    a.commande("scan")
    assert a.fin_commande() is None


def test_stop_et_repos_liberent_le_corps():
    for libere in ("stop", "default"):
        a = CorpsSuitVisage()
        a.commande("devil")
        a.commande(libere)
        assert a.visage("joie") == "joie"


def test_luminosite_n_est_pas_une_commande():
    a = CorpsSuitVisage()
    a.visage("joie")
    a.commande({"brightness": 0.3})
    assert a.visage("colere") == "colere"


def test_commande_explicite_oublie_la_lumiere_liee():
    """Après une commande explicite puis le repos, le visage repose sa lumière même si c'est
    la même qu'avant : le corps a changé entre-temps."""
    a = CorpsSuitVisage()
    assert a.visage("joie") == "joie"
    a.commande("trip")
    a.commande("stop")
    assert a.visage("joie") == "joie"
