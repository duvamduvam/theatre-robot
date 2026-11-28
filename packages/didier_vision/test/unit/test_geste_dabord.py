"""Lot S2b (`docs/spec-S2-le-corps-raconte.md` §3) — lecture de la ligne `GESTE`.

Le repli est toujours « c'est une réplique » : au pire Didier parle comme avant le lot,
jamais un geste inventé à partir d'une ligne mal lue.
"""

import pytest

from didier_vision.ai.geste_dabord import (
    CLES_GESTE,
    LIGNE_MAX_CHARS,
    coupe_premiere_ligne,
    lire_ligne_geste,
)


class TestCoupePremiereLigne:
    def test_coupe_sur_le_premier_saut_de_ligne(self):
        assert coupe_premiere_ligne("GESTE {\"marche\": \"go\"}\nEt hop !") == (
            'GESTE {"marche": "go"}',
            "Et hop !",
        )

    def test_sans_saut_de_ligne_le_reste_est_vide(self):
        assert coupe_premiere_ligne("Bonjour David.") == ("Bonjour David.", "")

    def test_reste_multiligne_conserve(self):
        _, reste = coupe_premiere_ligne("a\nb\nc")
        assert reste == "b\nc"

    @pytest.mark.parametrize("mauvais", [None, 42, {}, []])
    def test_entree_non_texte(self, mauvais):
        assert coupe_premiere_ligne(mauvais) == ("", "")


class TestLigneGesteReconnue:
    def test_cas_nominal(self):
        assert lire_ligne_geste('GESTE {"marche": "go"}') == {"marche": "go"}

    def test_casse_et_espaces_tolerees(self):
        assert lire_ligne_geste('  Geste :  {"aller_voir": "banc"}  ') == {"aller_voir": "banc"}

    def test_deux_points_apres_le_marqueur(self):
        assert lire_ligne_geste('GESTE: {"avancer": 1.5}') == {"avancer": 1.5}

    @pytest.mark.parametrize("cle,valeur", [
        ("marche", "stop"),
        ("aller_voir", "grue"),
        ("faire_le_tour", "banc"),
        ("tourner", -90),
        ("avancer", 2.0),
        ("tourner_vers", "elephant"),
    ])
    def test_toutes_les_cles_de_geste(self, cle, valeur):
        assert lire_ligne_geste('GESTE %s' % __import__("json").dumps({cle: valeur})) == {cle: valeur}

    def test_cles_annexes_conservees(self):
        # "regarder" / "emotion" accompagnent le geste : on les transmet tels quels.
        params = lire_ligne_geste('GESTE {"marche": "pause", "regarder": 30, "emotion": "surprise"}')
        assert params == {"marche": "pause", "regarder": 30, "emotion": "surprise"}


class TestRepliSurReplique:
    """Tous les cas douteux -> None (= réplique ordinaire), jamais un geste inventé."""

    def test_replique_ordinaire(self):
        assert lire_ligne_geste("Bonjour David, tu vas bien ?") is None

    def test_marqueur_sans_json(self):
        assert lire_ligne_geste("GESTE") is None

    def test_json_illisible(self):
        assert lire_ligne_geste('GESTE {aller_voir: banc}') is None

    def test_json_tronque(self):
        assert lire_ligne_geste('GESTE {"marche": "go"') is None

    def test_json_qui_nest_pas_un_objet(self):
        assert lire_ligne_geste('GESTE ["marche"]') is None

    def test_objet_sans_cle_de_geste(self):
        assert lire_ligne_geste('GESTE {"emotion": "happy"}') is None

    def test_mot_geste_dans_une_vraie_replique(self):
        assert lire_ligne_geste("Mon geste préféré, c'est de tourner.") is None

    def test_ligne_trop_longue_ignoree(self):
        longue = 'GESTE {"marche": "go", "x": "' + "a" * LIGNE_MAX_CHARS + '"}'
        assert lire_ligne_geste(longue) is None

    @pytest.mark.parametrize("mauvais", [None, 42, {}, []])
    def test_entree_non_texte(self, mauvais):
        assert lire_ligne_geste(mauvais) is None


def test_cles_geste_couvrent_les_cles_de_mouvement_du_json_de_fin():
    """La ligne GESTE doit accepter au moins toutes les clés historiques (conversation.MOVE_KEYS)."""
    from didier_vision.ai.conversation import MOVE_KEYS

    assert set(MOVE_KEYS).issubset(set(CLES_GESTE))


# --------------------------------------------------------------------------------------
# Appel 2 : la réponse du corps, en clair (§3).
# --------------------------------------------------------------------------------------

from didier_vision.ai.geste_dabord import (  # noqa: E402
    ACCEPTE_PHRASE,
    ATTENTE_CORPS_S,
    REFUS_INCONNU,
    REFUS_PHRASES,
    SANS_REPONSE,
    consigne_appel_2,
    phrase_reponse_corps,
)


class TestPhraseReponseCorps:
    def test_accepte(self):
        assert phrase_reponse_corps({"effect": "accepted"}) == ACCEPTE_PHRASE

    @pytest.mark.parametrize("raison", sorted(REFUS_PHRASES))
    def test_chaque_raison_gravee_a_sa_phrase(self, raison):
        phrase = phrase_reponse_corps({"effect": "dropped", "reason": raison})
        assert phrase == REFUS_PHRASES[raison]
        assert phrase and not phrase.endswith(".")

    def test_raison_inconnue(self):
        assert phrase_reponse_corps({"effect": "dropped", "reason": "zzz"}) == REFUS_INCONNU

    def test_refus_sans_raison(self):
        assert phrase_reponse_corps({"effect": "dropped"}) == REFUS_INCONNU

    @pytest.mark.parametrize("sans_reponse", [None, "", 42, []])
    def test_sans_reponse_la_bouche_doute_jamais_accepte(self, sans_reponse):
        """Repli sûr : sans nouvelle du corps, jamais « accepté »."""
        phrase = phrase_reponse_corps(sans_reponse)
        assert phrase == REFUS_PHRASES[SANS_REPONSE]
        assert phrase != ACCEPTE_PHRASE


class TestConsigneAppel2:
    def test_contient_reponse_etat_et_consigne(self):
        texte = consigne_appel_2({"effect": "accepted"}, "Tu roules sur ta route.")
        assert texte.startswith("Ton corps répond : il accepte")
        assert "Tu roules sur ta route." in texte
        assert "ne dis jamais d'un mouvement qu'il est fait" in texte

    def test_le_mensonge_du_26_11_est_dit_a_la_bouche(self):
        """Séance du 26/11 : STOP console, « allez, go » -> « Ça y est, je fonce vers la grue ! »."""
        texte = consigne_appel_2({"effect": "dropped", "reason": "arrete"},
                                 "Tu es arrêté. Seul un go de David te relance.")
        assert "arrêté par David" in texte
        assert "GO à la console" in texte

    @pytest.mark.parametrize("vide", [None, "", "   ", 42])
    def test_etat_du_corps_absent_ou_vide(self, vide):
        texte = consigne_appel_2({"effect": "accepted"}, vide)
        assert "Ton corps répond" in texte and "  " not in texte

    def test_delai_de_garde_conforme_a_la_spec(self):
        assert ATTENTE_CORPS_S == 0.5


# --------------------------------------------------------------------------------------
# Lecture du flux de l'appel 1 (§3 « Latence »).
# --------------------------------------------------------------------------------------

from didier_vision.ai.geste_dabord import separe_geste_du_flux  # noqa: E402


class _FluxCompte:
    """Flux qui compte les deltas réellement tirés (preuve qu'on ne lit pas tout)."""

    def __init__(self, deltas):
        self._deltas = list(deltas)
        self.tires = 0

    def __iter__(self):
        for d in self._deltas:
            self.tires += 1
            yield d


class TestSepareGesteDuFlux:
    def test_tour_de_geste_rien_nest_dit(self):
        params, deltas = separe_geste_du_flux(iter(['GESTE {"marche"', ': "go"}\n', 'jamais dit']))
        assert params == {"marche": "go"}
        assert deltas is None

    def test_tour_ordinaire_le_flux_est_rejoue_a_lidentique(self):
        params, deltas = separe_geste_du_flux(iter(["Bon", "jour ", "David !"]))
        assert params is None
        assert "".join(deltas) == "Bonjour David !"

    def test_tour_ordinaire_ne_tamponne_que_le_debut(self):
        """Latence inchangée (§3) : on tranche sur les premiers caractères, pas sur tout le flux."""
        flux = _FluxCompte(["Bonjour", " David", ", tu", " vas bien ?"] + ["x"] * 50)
        params, deltas = separe_geste_du_flux(iter(flux))
        assert params is None
        assert flux.tires == 1, "un seul delta a suffi pour trancher"
        assert "".join(deltas).startswith("Bonjour David")

    def test_marqueur_tronque_en_plusieurs_deltas(self):
        params, _ = separe_geste_du_flux(iter(["G", "E", "S", "T", "E", ' {"avancer": 2}\n']))
        assert params == {"avancer": 2}

    def test_faux_positif_le_mot_geste_dans_une_replique(self):
        params, deltas = separe_geste_du_flux(iter(["Ge", "ste de la main, tu connais ?"]))
        assert params is None
        assert "".join(deltas) == "Geste de la main, tu connais ?"

    # Fumée du 28/11 : rejouer une ligne GESTE illisible comme réplique faisait PRONONCER
    # « GESTE ». Désormais : rien n'est dit, aucun geste ne part (ni par la ligne, ni par un
    # JSON de fin lu plus bas).
    @pytest.mark.parametrize("flux", [
        ['GESTE {casse\n', "la suite"],
        ["GESTE"],                                         # le mot seul, fin de flux
        ["GESTE\n", '{"faire_le_tour": "elephant"}'],      # JSON sur la ligne suivante
        ["Ges", "te", ":", " {aller_voir: banc}\n"],        # JSON non quoté, en morceaux
        ['GESTE {"emotion": "happy"}\n', "Bonjour."],       # aucune clé de geste
    ])
    def test_ligne_geste_illisible_rien_nest_dit(self, flux):
        params, deltas = separe_geste_du_flux(iter(flux))
        assert params is None
        assert "".join(deltas) == ""

    def test_flux_vide(self):
        params, deltas = separe_geste_du_flux(iter([]))
        assert params is None
        assert "".join(deltas) == ""

    def test_flux_plus_court_que_le_marqueur(self):
        params, deltas = separe_geste_du_flux(iter(["Oui"]))
        assert params is None
        assert "".join(deltas) == "Oui"

    def test_deltas_non_textuels_ignores(self):
        params, deltas = separe_geste_du_flux(iter([None, "Bonjour", 42, " David"]))
        assert params is None
        assert "".join(deltas) == "Bonjour David"

    def test_ligne_geste_sans_saut_de_ligne_final(self):
        params, _ = separe_geste_du_flux(iter(['GESTE {"aller_voir": "banc"}']))
        assert params == {"aller_voir": "banc"}


# --------------------------------------------------------------------------------------
# Barrière de la parole (fumée du 28/11 : « GESTE » prononcé).
# --------------------------------------------------------------------------------------

from didier_vision.ai.geste_dabord import est_ligne_geste, filtre_lignes_geste  # noqa: E402


class TestEstLigneGeste:
    @pytest.mark.parametrize("texte", [
        "GESTE", "geste", "  Geste  ", "GESTE {", 'GESTE {"aller_voir": "banc"}',
        'Geste: {"marche": "go"}', "GESTE.", "GESTE\n"])
    def test_lignes_du_protocole(self, texte):
        assert est_ligne_geste(texte) is True

    @pytest.mark.parametrize("texte", [
        "Geste de la main, tu connais ?", "Gestes lents.", "Mon geste préféré.", "", None,
        "D'accord, j'y vais."])
    def test_vraies_repliques(self, texte):
        assert est_ligne_geste(texte) is False


class TestFiltreLignesGeste:
    """Valeurs attendues GRAVÉES (jamais recalculées avec la fonction testée)."""

    @pytest.mark.parametrize("flux, attendu", [
        # L'appel 2 du 28/11 : la ligne entière, JSON compris, disparaît.
        (['GESTE {"aller_voir": "table_basse"}'], ""),
        (['GESTE {"aller_voir": "table_basse"}\n', "J'y vais !"], "J'y vais !"),
        # Découpée comme par l'API, le marqueur à cheval sur plusieurs deltas.
        (["G", "ES", "TE ", '{"faire_', 'le_tour": "elephant"}', "\nJe fais le tour."],
         "Je fais le tour."),
        # Plus bas dans une réplique, sur sa propre ligne.
        (["D'accord.\n", "geste", ' {"marche": "go"}\n', "En route."],
         "D'accord.\nEn route."),
        # Le mot seul, sans saut de ligne final.
        (["Bon.\n", "GESTE"], "Bon.\n"),
        # Vraies répliques : rendues à l'identique.
        (["Geste de la main, tu connais ?"], "Geste de la main, tu connais ?"),
        (["Ge", "ste", " de la main"], "Geste de la main"),
        (["Ges"], "Ges"),
        (["Bonjour ", "David !\n", "\n", "Ça va ?"], "Bonjour David !\n\nÇa va ?"),
        ([None, "Oui", 3], "Oui"),
        ([], ""),
    ])
    def test_filtre(self, flux, attendu):
        assert "".join(filtre_lignes_geste(iter(flux))) == attendu

    def test_le_texte_ordinaire_part_delta_par_delta(self):
        """Latence : une réplique ordinaire n'est pas tamponnée jusqu'au saut de ligne."""
        sortis = list(filtre_lignes_geste(iter(["Bonjour", " David", ", tu vas bien ?"])))
        assert sortis == ["Bonjour", " David", ", tu vas bien ?"]

    def test_fermer_le_filtre_ferme_le_flux_amont(self):
        ferme = []

        def _amont():
            try:
                yield "Bonjour"
                yield " David"
            finally:
                ferme.append(True)

        filtre = filtre_lignes_geste(_amont())
        assert next(filtre) == "Bonjour"
        filtre.close()
        assert ferme == [True], "arrêt vocal : la connexion LLM doit être libérée"
