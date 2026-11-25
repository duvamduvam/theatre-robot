"""Onglet « Audio » de la page scène (22/11) : verdict pur (didier_web.panneau_audio) et
relais du pont (GET /api/audio, message audio_banc) devant une FAUSSE veille audio de l'hôte.

Valeurs GRAVÉES (jamais recalculées avec la fonction testée) : le message que David lit et
l'action qu'on lui propose sont le contrat de l'onglet.
"""

import asyncio
import copy
import json

import pytest

from didier_web import panneau_audio as pa
from didier_web.web_protocol import AUDIO_BANC_ACTIONS, ProtocolError, parse_client_message

# Une veille « tout va bien » : micro du casque M50 connecté, sortie sur le même casque.
HOTE_OK = {
    "v": 1,
    "micro": {"conf": "bluez_input.40_9C", "suit_ubuntu": False, "pipewire": "bluez_input.40_9C",
              "nom": "M50", "present": True, "muet": False, "casque": {"nom": "M50", "connecte": True}},
    "sortie": {"conf": "bluez_output.40_9C.1", "suit_ubuntu": False, "pipewire": "bluez_output.40_9C.1",
               "nom": "M50", "present": True, "muet": False, "casque": {"nom": "M50", "connecte": True}},
    "casques": [{"nom": "M50", "connecte": True, "micro_present": True, "sortie_present": True}],
    "photo_age_s": 0.4,
    "erreur_sonde": None,
    "niveau": {"crete": 3277, "crete_3s": 32767, "ecoute_s": 12.0, "muet_constate": False,
               "seuil_vivant": 30, "erreur": None},
    "redetection": {"en_cours": False, "il_y_a_s": None, "code": None, "resume": None},
    "derniere_action": None,
}


def hote(**changements):
    """HOTE_OK modifié : clés « micro.present » etc. pour descendre d'un niveau."""
    h = copy.deepcopy(HOTE_OK)
    for cle, valeur in changements.items():
        bloc, _, champ = cle.partition("__")
        if champ:
            h[bloc][champ] = valeur
        else:
            h[bloc] = valeur
    return h


# --- vumètre ---------------------------------------------------------------------------

@pytest.mark.parametrize("crete,attendu", [(None, None), (0, 0), (-5, 0), (1, 0), (30, 13),
                                           (3277, 71), (32767, 100), (40000, 100)])
def test_pourcent_echelle_en_db(crete, attendu):
    assert pa.pourcent(crete) == attendu


# --- verdict ---------------------------------------------------------------------------

def test_tout_va_bien():
    s = pa.synthese(HOTE_OK, "listening", None, None)
    assert (s["verdict"], s["message"], s["action"], s["autres"]) == (
        "ok", "tout va bien : « M50 » → « M50 »", "", [])
    assert s["entree"] == {"nom": "M50", "present": True, "muet": False, "suit_ubuntu": False,
                           "casque": "M50", "casque_connecte": True, "pct": 71, "pct_3s": 100, "seuil_pct": 13}
    assert s["sortie"]["casque"] == "M50" and s["service"] is True


def test_veille_injoignable():
    s = pa.synthese(None, "listening", None, None)
    assert (s["verdict"], s["service"], s["entree"], s["sortie"]) == ("ko", False, None, None)
    assert s["message"] == "veille audio du banc injoignable : rien n'est vérifié"
    assert s["action"] == ("relance la séance (seance-chantiers.sh) ou lance sur le PC : "
                           "python3 machines/sim/banc-vision/audio_veille.py")


def test_casque_eteint_dit_de_l_allumer():
    h = hote(micro__present=False, sortie__present=False,
             micro__casque={"nom": "M50", "connecte": False}, sortie__casque={"nom": "M50", "connecte": False})
    s = pa.synthese(h, "listening", None, None)
    assert (s["verdict"], s["message"], s["action"]) == (
        "ko", "casque « M50 » déconnecté (micro absent)",
        "allume le casque (ou rapproche-le du PC), puis « Re-détecter »")
    assert s["autres"] == ["casque « M50 » déconnecté (sortie absent)"]


def test_casque_connecte_sans_micro_hfp():
    s = pa.synthese(hote(micro__present=False), "listening", None, None)
    assert s["message"] == "micro du casque « M50 » absent (casque en écoute seule)"
    assert s["action"] == "« Re-détecter » : il repasse le casque en mode casque + micro"


def test_micro_filaire_debranche():
    s = pa.synthese(hote(micro__present=False, micro__casque=None, micro__nom="Scarlett 4i4", casques=[]),
                    "listening", None, None)
    assert (s["message"], s["action"]) == ("micro « Scarlett 4i4 » débranché", "rebranche-le, puis « Re-détecter »")


def test_micro_coupe_muet():
    s = pa.synthese(hote(micro__muet=True), "listening", None, None)
    assert (s["verdict"], s["message"]) == ("ko", "micro « M50 » coupé (muet) dans le réglage son")


def test_sortie_coupee_muette():
    s = pa.synthese(hote(sortie__muet=True), "listening", None, None)
    assert (s["verdict"], s["message"]) == ("ko", "sortie « M50 » coupée (muette) dans le réglage son")


def test_micro_plat_est_une_attention():
    s = pa.synthese(hote(niveau__muet_constate=True), "listening", None, None)
    assert (s["verdict"], s["message"]) == ("attention", "micro plat depuis 3 s : aucun son n'entre")


def test_micro_qui_ne_s_ouvre_pas():
    s = pa.synthese(hote(niveau__erreur="le micro ne s'ouvre pas (flux coupé)"), "listening", None, None)
    assert (s["verdict"], s["message"], s["action"]) == ("ko", "le micro ne s'ouvre pas (flux coupé)", "« Re-détecter »")


def test_parole_off_et_tete_muette():
    assert pa.synthese(HOTE_OK, "off", None, None)["message"] == "Parole OFF : Didier n'écoute pas"
    s = pa.synthese(HOTE_OK, None, None, None)
    assert (s["verdict"], s["message"]) == ("ko", "la tête ne dit rien (aucun état de conversation reçu)")


def test_sans_casque_le_micro_peut_entendre_didier():
    s = pa.synthese(hote(micro__casque=None, sortie__casque=None, casques=[]), "listening", None, None)
    assert (s["verdict"], s["message"]) == ("attention", "pas de casque : le micro peut entendre Didier")


# Constat de la séance du 22/11 à 19h56, tel que la veille le rendait.
INTERNE_MUET = {"conf": "@DEFAULT_SOURCE@", "suit_ubuntu": True,
                "pipewire": "alsa_input.pci-0000_00_1f.3.analog-stereo", "nom": "Audio interne Stéréo analogique",
                "present": True, "muet": True, "casque": None, "respeaker": False}


def test_cas_du_22_11_casque_connecte_micro_interne_muet():
    s = pa.synthese(hote(micro=INTERNE_MUET, niveau__muet_constate=True, niveau__crete=0), "listening", None, None)
    assert (s["verdict"], s["message"], s["action"]) == (
        "ko", "casque « M50 » connecté mais son micro n'est pas utilisé (Didier écoute « Audio interne Stéréo analogique »)",
        "« Re-détecter » : le micro du casque sera choisi")
    assert s["autres"] == ["micro « Audio interne Stéréo analogique » coupé (muet) dans le réglage son",
                           "micro plat depuis 3 s : aucun son n'entre"]


def test_casque_connecte_en_ecoute_seule_et_micro_interne():
    h = hote(micro=INTERNE_MUET, casques=[{"nom": "M50", "connecte": True, "micro_present": False,
                                           "sortie_present": True}])
    assert pa.synthese(h, "listening", None, None)["message"].startswith("casque « M50 » connecté mais son micro")
    # Casque connecté sans aucun nœud, tout sur le PC : la cause est le casque, pas « pas de casque ».
    h = hote(micro=INTERNE_MUET, sortie__casque=None, casques=[{"nom": "M50", "connecte": True,
                                                                "micro_present": False, "sortie_present": False}])
    s = pa.synthese(h, "listening", None, None)
    assert s["message"].startswith("casque « M50 » connecté mais son micro")
    assert "pas de casque : le micro peut entendre Didier" not in s["autres"]


def test_respeaker_avec_casque_connecte_ok():
    h = hote(micro__casque=None, micro__respeaker=True, micro__nom="reSpeaker")
    assert pa.synthese(h, "listening", None, None)["verdict"] == "ok"


def test_casque_connecte_mais_sortie_sur_le_pc():
    s = pa.synthese(hote(sortie__casque=None, sortie__nom="Audio interne"), "listening", None, None)
    assert (s["verdict"], s["message"]) == (
        "ko", "casque « M50 » connecté mais la voix de Didier n'y va pas (elle sort sur « Audio interne »)")


def test_micro_du_casque_et_haut_parleurs_du_pc_ok():
    """Même règle que audio_banc.plan_auto : l'alerte « boucle » vise le micro du PC hors casque."""
    h = hote(sortie__casque=None, sortie__nom="Audio interne",
             casques=[{"nom": "M50", "connecte": True, "micro_present": True, "sortie_present": False}])
    assert (pa.synthese(h, "listening", None, None)["verdict"],) == ("ok",)


def test_redetection_en_cours_passe_avant_les_attentions_apres_les_ko():
    h = hote(redetection={"en_cours": True, "il_y_a_s": None, "code": None, "resume": None})
    assert pa.synthese(h, "off", None, None)["verdict"] == "attente"
    h["sortie"]["muet"] = True
    s = pa.synthese(h, "off", None, None)
    assert s["verdict"] == "ko"
    assert s["autres"] == ["re-détection du micro et de la sortie en cours…", "Parole OFF : Didier n'écoute pas"]


def test_etat_illisible_avant_la_premiere_sonde():
    s = pa.synthese(hote(micro=None, sortie=None), "listening", None, None)
    assert s["message"] == "état du son illisible (première mesure pas encore faite)"


# --- témoins ---------------------------------------------------------------------------

def test_temoins():
    garde = {"entendu": "bonjour Didier", "verdict": "gardé", "moteur": "distant"}
    assert pa.temoins("speaking", garde, 2.0) == {
        "entend": "oui", "entendu": "bonjour Didier", "parle": True, "chat_state": "speaking"}
    assert pa.temoins("listening", dict(garde, verdict="jeté"), 6.0)["entend"] == "jete"
    # Trop vieux (> 6 s) : plus « m'entend ».
    assert pa.temoins("listening", garde, 6.1) == {
        "entend": "non", "entendu": None, "parle": False, "chat_state": "listening"}
    assert pa.temoins(None, None, None)["entend"] == "non"


@pytest.mark.parametrize("etat,attendu", [("listening", True), ("thinking", True), ("speaking", True),
                                          ("off", False), (None, False), ("inconnu", False)])
def test_rouvrir_le_micro_seulement_si_la_parole_est_on(etat, attendu):
    assert pa.faut_rouvrir_micro(etat) is attendu


# --- protocole -------------------------------------------------------------------------

def test_actions_audio_identiques_des_deux_cotes():
    assert AUDIO_BANC_ACTIONS == pa.ACTIONS == {"tester", "redetecter"}


def test_parse_audio_banc():
    assert parse_client_message('{"type":"audio_banc","action":"tester"}') == {
        "type": "audio_banc", "action": "tester"}
    for mauvais in ('{"type":"audio_banc"}', '{"type":"audio_banc","action":"rm -rf"}',
                    '{"type":"audio_banc","action":["tester"]}'):
        with pytest.raises(ProtocolError):
            parse_client_message(mauvais)


# --- le pont devant une fausse veille --------------------------------------------------
# Les fixtures `pont` et l'usine de nœud factice viennent de test_web_protocol.py.

from test.unit.test_web_protocol import _creer_noeud, _ecrivain, _WsFactice, pont  # noqa: E402,F401


class _FausseVeille:
    """Serveur aiohttp qui joue audio_veille.py : /etat, /tester, /redetecter."""

    def __init__(self):
        self.etat = copy.deepcopy(HOTE_OK)
        self.appels = []
        self.redetection_rendue = 0

    def app(self):
        from aiohttp import web

        async def etat(_req):
            self.appels.append("GET /etat")
            if self.etat["redetection"]["en_cours"]:
                # La re-détection se termine au 2e sondage.
                self.redetection_rendue += 1
                if self.redetection_rendue >= 2:
                    self.etat["redetection"] = {"en_cours": False, "il_y_a_s": 0.1, "code": 0, "resume": "ok"}
            return web.json_response(self.etat)

        async def tester(_req):
            self.appels.append("POST /tester")
            return web.json_response({"ok": True, "message": "bip joué par la tête sur « M50 »"})

        async def redetecter(_req):
            self.appels.append("POST /redetecter")
            self.etat["redetection"] = {"en_cours": True, "il_y_a_s": None, "code": None, "resume": None}
            return web.json_response({"ok": True, "message": "re-détection lancée"}, status=202)

        app = web.Application()
        app.router.add_get("/etat", etat)
        app.router.add_post("/tester", tester)
        app.router.add_post("/redetecter", redetecter)
        return app


async def _reponse(ws, n):
    """Attend la n-ième réponse : le relais vers la veille tourne dans une tâche à part."""
    for _ in range(300):
        if len(ws.envoyes) >= n:
            return ws.envoyes[n - 1]
        await asyncio.sleep(0.01)
    raise AssertionError("pas de réponse n°{}".format(n))


def _scenario(pont, noeud, veille, corps):
    """Lance la fausse veille sur un port libre, pointe le nœud dessus, joue `corps(client)`."""
    from aiohttp.test_utils import TestClient, TestServer

    async def tout():
        async with TestServer(veille.app()) as serveur_veille:
            noeud.audio_banc_url = "http://127.0.0.1:{}".format(serveur_veille.port)
            app = pont.build_app(noeud)
            async with TestServer(app) as serveur, TestClient(serveur) as client:
                await corps(client, app)

    asyncio.run(tout())


def test_api_audio_relaie_la_veille_et_la_tete(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, domaine="43")
    assert noeud.hello_message("c1")["audio_banc"] is True
    noeud.abonnements["chat_state"][1](types_msg("speaking"))
    noeud.abonnements["chat_hearing"][1](types_msg(json.dumps({"entendu": "salut", "verdict": "gardé"})))
    veille = _FausseVeille()

    async def corps(client, _app):
        rep = await client.get("/api/audio")
        assert rep.status == 200
        s = await rep.json()
        assert (s["verdict"], s["message"]) == ("ok", "tout va bien : « M50 » → « M50 »")
        assert s["temoins"] == {"entend": "oui", "entendu": "salut", "parle": True, "chat_state": "speaking"}
        assert s["entree"]["pct"] == 71

    _scenario(pont, noeud, veille, corps)


def test_api_audio_veille_absente_le_dit(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, domaine="43", audio_banc_port=9)   # port fermé

    async def corps(client, _app):
        s = await (await client.get("/api/audio")).json()
        assert (s["verdict"], s["service"]) == ("ko", False)

    from aiohttp.test_utils import TestClient, TestServer

    async def tout():
        async with TestServer(pont.build_app(noeud)) as serveur, TestClient(serveur) as client:
            await corps(client, None)

    asyncio.run(tout())


def test_api_audio_absente_sur_le_robot(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, domaine="42")
    assert noeud.hello_message("c1")["audio_banc"] is False
    from aiohttp.test_utils import TestClient, TestServer

    async def tout():
        async with TestServer(pont.build_app(noeud)) as serveur, TestClient(serveur) as client:
            assert (await client.get("/api/audio")).status == 404

    asyncio.run(tout())


def test_tester_le_son_writer_seul(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, domaine="43")
    veille = _FausseVeille()
    ws = _WsFactice()

    async def corps(_client, app):
        assert noeud.sessions.authenticate("lecteur", None, 0.0)  # premier : writer
        assert noeud.sessions.authenticate("autre", None, 0.0) and not noeud.sessions.is_writer("autre")
        await pont.handle_client_message(noeud, app, "autre", ws, '{"type":"audio_banc","action":"tester"}')
        assert ws.envoyes == [{"type": "err", "reason": "écriture non détenue"}]
        assert veille.appels == []
        await pont.handle_client_message(noeud, app, "lecteur", ws, '{"type":"audio_banc","action":"tester"}')
        assert await _reponse(ws, 2) == {"type": "ack", "topic": "audio_banc"}
        assert veille.appels == ["POST /tester"]

    _scenario(pont, noeud, veille, corps)


def test_redetecter_puis_rouvre_le_micro_de_la_tete(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, domaine="43")
    monkeypatch.setattr(pont, "AUDIO_BANC_SONDE_S", 0.01)
    monkeypatch.setattr(pont, "AUDIO_BANC_PAUSE_MICRO_S", 0.01)
    noeud.abonnements["chat_state"][1](types_msg("listening"))
    veille = _FausseVeille()
    ws = _WsFactice()

    async def corps(_client, app):
        _ecrivain(noeud)
        await pont.handle_client_message(noeud, app, "c1", ws, '{"type":"audio_banc","action":"redetecter"}')
        # Une 2e demande (double clic) est refusée aussitôt, sans déranger la veille.
        await pont.handle_client_message(noeud, app, "c1", ws, '{"type":"audio_banc","action":"redetecter"}')
        assert ws.envoyes[0] == {"type": "err", "reason": "re-détection déjà en cours"}
        assert await _reponse(ws, 2) == {"type": "ack", "topic": "audio_banc"}
        for _ in range(200):
            if not noeud.redetection_en_cours:
                break
            await asyncio.sleep(0.01)
        assert veille.appels.count("POST /redetecter") == 1
        assert [m.msg for m in noeud.publishers["chat"].messages] == ['"off"', '"on"']

    _scenario(pont, noeud, veille, corps)


def test_veille_injoignable_refuse_et_libere_la_redetection(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, domaine="43", audio_banc_port=9)   # port fermé
    ws = _WsFactice()
    from aiohttp.test_utils import TestServer

    async def tout():
        app = pont.build_app(noeud)
        async with TestServer(app):
            _ecrivain(noeud)
            await pont.handle_client_message(noeud, app, "c1", ws, '{"type":"audio_banc","action":"redetecter"}')
            assert await _reponse(ws, 1) == {"type": "err", "reason": "audio : veille audio du banc injoignable"}
            assert noeud.redetection_en_cours is False

    asyncio.run(tout())


def test_redetecter_ne_rallume_pas_une_parole_off(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, domaine="43")
    monkeypatch.setattr(pont, "AUDIO_BANC_SONDE_S", 0.01)
    noeud.abonnements["chat_state"][1](types_msg("off"))
    veille = _FausseVeille()
    ws = _WsFactice()

    async def corps(_client, app):
        _ecrivain(noeud)
        await pont.handle_client_message(noeud, app, "c1", ws, '{"type":"audio_banc","action":"redetecter"}')
        for _ in range(200):
            if not noeud.redetection_en_cours:
                break
            await asyncio.sleep(0.01)
        assert not noeud.redetection_en_cours
        assert noeud.publishers["chat"].messages == []

    _scenario(pont, noeud, veille, corps)


def types_msg(brut):
    import types
    return types.SimpleNamespace(msg=brut, time=0, anim=False)


# --- S0 (25/11) : phrases jetées de suite ------------------------------------------------

def _jete(n, crete):
    return {"entendu": "", "verdict": "jeté : rien de compréhensible", "jetes_de_suite": n, "crete": crete}


def test_trois_phrases_jetees_et_son_plat():
    s = pa.synthese(HOTE_OK, "listening", _jete(3, 4), 1.0)
    assert s["verdict"] == "ko"
    assert s["message"] == "3 phrases de suite jetées : le son capté est plat (crête 4)"


def test_trois_phrases_jetees_avec_du_son():
    s = pa.synthese(HOTE_OK, "listening", _jete(5, 412), 1.0)
    assert s["verdict"] == "ko"
    assert s["message"] == "5 phrases de suite jetées : du son arrive (crête 412) mais rien n'est compris"


@pytest.mark.parametrize("entendu", [None, _jete(2, 0), _jete(None, 0), {"verdict": "gardé", "entendu": "salut"}])
def test_pas_d_alerte_sous_trois_jetees(entendu):
    assert pa.synthese(HOTE_OK, "listening", entendu, 1.0)["verdict"] == "ok"


def test_veille_injoignable_reste_premiere_meme_avec_des_jetees():
    s = pa.synthese(None, "listening", _jete(4, 0), 1.0)
    assert s["message"].startswith("veille audio du banc injoignable")
