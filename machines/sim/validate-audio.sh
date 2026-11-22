#!/bin/bash
# Onglet « Audio » de la page scène (22/11) — preuve REJOUABLE, SANS casque ni son réel, DANS le
# conteneur `monde` (domaine 43, réseau host : le pont web est sur 127.0.0.1:${WEB_PORT}). Une
# FAUSSE veille audio (aiohttp, 127.0.0.1:8767, le port que lit le pont) joue des états INJECTÉS
# et note les actions reçues ; la tête est jouée par des chat_state / chat_hearing publiés ici.
#   AU1  hello.audio_banc vrai en simulation
#   AU2  veille absente : verdict ko, service faux, message gravé
#   AU3  contrat de GET /api/audio : champs de la réponse, de l'entrée et des témoins
#   AU4  cas du 22/11 (M50 connecté, micro interne muet) : « casque connecté mais son micro… »
#   AU5  état sain : verdict ok, message gravé, vumètre 71 % pour une crête de 3277
#   AU6  témoins : chat_state speaking -> « Didier parle » ; chat_hearing gardé -> « m'entend »
#   AU7  la page sert l'onglet (ids) et son script interroge /api/audio
#   AU8  Tester le son (writer) : ack, et la veille a reçu POST /tester
#   AU9  un lecteur (sans la main) est refusé, rien n'arrive à la veille
#   AU10 Re-détecter : ack, un seul POST /redetecter, puis le pont publie chat off puis on
# rclpy seulement (jamais la CLI ros2, qui perd des messages sur ce PC). Ligne finale :
# « === AUDIO : N OK, K KO ». Sortie 0 = OK ; 1 = KO ; 2 = banc faux. Refus hors domaine 43.
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
NS="/${ROBOT_NAME:-didier}"
export NS
export WEB="http://127.0.0.1:${WEB_PORT:-8765}"
[ "${ROS_DOMAIN_ID:-}" = 43 ] || { echo "REFUS : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, ce script ne tourne qu'en simulation (43)"; exit 2; }

echo "=== onglet Audio sous $NS/ ($WEB) $(date +%T) ==="
python3 - <<'PY'
import asyncio, copy, json, os, sys, threading, time
import aiohttp
from aiohttp import web
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile
from theatre_interfaces.msg import StringTime

NS, WEB, PORT_VEILLE = os.environ["NS"], os.environ["WEB"], 8767
ok = ko = 0
def verdict(bon, texte):
    global ok, ko
    print(("  ✅ " if bon else "  ❌ ") + texte, flush=True)
    ok, ko = (ok + 1, ko) if bon else (ok, ko + 1)

M50 = {"nom": "M50", "connecte": True}
CASQUE = {"conf": "bluez_input.40_9C", "suit_ubuntu": False, "respeaker": False, "pipewire": "bluez_input.40_9C",
          "nom": "M50", "present": True, "muet": False, "casque": M50}
SAIN = {"v": 1, "micro": CASQUE, "sortie": dict(CASQUE, conf="bluez_output.40_9C.1", pipewire="bluez_output.40_9C.1"),
        "casques": [dict(M50, micro_present=True, sortie_present=True)], "photo_age_s": 0.5, "erreur_sonde": None,
        "niveau": {"crete": 3277, "crete_3s": 9000, "ecoute_s": 10.0, "muet_constate": False, "seuil_vivant": 30,
                   "erreur": None},
        "redetection": {"en_cours": False, "il_y_a_s": None, "code": None, "resume": None}, "derniere_action": None}
CAS_22_11 = copy.deepcopy(SAIN)
CAS_22_11["micro"] = {"conf": "@DEFAULT_SOURCE@", "suit_ubuntu": True, "respeaker": False,
                      "pipewire": "alsa_input.pci-0000_00_1f.3.analog-stereo", "nom": "Audio interne Stéréo analogique",
                      "present": True, "muet": True, "casque": None}

class Veille:
    def __init__(self):
        self.etat, self.appels, self.sondes_redet = copy.deepcopy(CAS_22_11), [], 0
    async def get_etat(self, _r):
        if self.etat["redetection"]["en_cours"]:
            self.sondes_redet += 1
            if self.sondes_redet >= 2:   # la re-détection se termine au 2e sondage du pont
                self.etat["redetection"] = {"en_cours": False, "il_y_a_s": 0.1, "code": 0, "resume": "ok"}
        return web.json_response(self.etat)
    async def tester(self, _r):
        self.appels.append("tester")
        return web.json_response({"ok": True, "message": "bip joué par la tête sur « M50 »"})
    async def redetecter(self, _r):
        self.appels.append("redetecter")
        self.etat["redetection"] = {"en_cours": True, "il_y_a_s": None, "code": None, "resume": None}
        return web.json_response({"ok": True, "message": "re-détection lancée"}, status=202)

rclpy.init()
node = rclpy.create_node("validate_audio", namespace=NS)
latch = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
pub_etat = node.create_publisher(StringTime, "chat_state", latch)
pub_entendu = node.create_publisher(StringTime, "chat_hearing", 10)
chat_recus = []
node.create_subscription(StringTime, "chat", lambda m: chat_recus.append(json.loads(m.msg)), 10)
arret = threading.Event()
threading.Thread(target=lambda: [rclpy.spin_once(node, timeout_sec=0.1) for _ in iter(arret.is_set, True)],
                 daemon=True).start()

def publier(pub, texte):
    pub.publish(StringTime(msg=texte, time=0, anim=False))

async def audio(s):
    async with s.get(WEB + "/api/audio") as r:
        return await r.json(content_type=None)

async def attendre(s, cond, delai=15.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        a = await audio(s)
        if cond(a):
            return a
        await asyncio.sleep(0.3)
    return a

async def reponse(ws):
    while True:
        m = await asyncio.wait_for(ws.receive_json(), 20)
        if m["type"] in ("ack", "err"):
            return m

async def client(s, auth=True):
    ws = await s.ws_connect(WEB + "/ws")
    hello = await asyncio.wait_for(ws.receive_json(), 10)
    if auth:
        await ws.send_json({"type": "auth", "token": None})
        hello = await asyncio.wait_for(ws.receive_json(), 10)
    return ws, hello

async def battre(ws):
    while True:
        await ws.send_json({"type": "hb", "t": int(time.time() * 1000)})
        await asyncio.sleep(1)

async def main():
    async with aiohttp.ClientSession() as s:
        ws, hello = await client(s)
        hb = asyncio.ensure_future(battre(ws))
        verdict(hello.get("audio_banc") is True and hello.get("writer") is True,
                "AU1 hello : audio_banc=%s, writer=%s" % (hello.get("audio_banc"), hello.get("writer")))
        a = await audio(s)
        verdict((a["service"], a["verdict"], a["message"]) == (False, "ko", "veille audio du banc injoignable : rien n'est vérifié"),
                "AU2 veille absente : %s / %s" % (a["verdict"], a["message"]))

        veille = Veille()
        app = web.Application()
        app.router.add_get("/etat", veille.get_etat)
        app.router.add_post("/tester", veille.tester)
        app.router.add_post("/redetecter", veille.redetecter)
        runner = web.AppRunner(app); await runner.setup()
        try:
            await web.TCPSite(runner, "127.0.0.1", PORT_VEILLE).start()
        except OSError as e:
            print("PRÉCONDITION : port %d pris (une vraie veille tourne ?) : %s" % (PORT_VEILLE, e), flush=True)
            sys.exit(2)

        a = await attendre(s, lambda a: a["service"])
        cles = {"service", "verdict", "message", "action", "autres", "entree", "sortie", "temoins", "redetection",
                "derniere_action"}
        entree = {"nom", "present", "muet", "suit_ubuntu", "casque", "casque_connecte", "pct", "pct_3s", "seuil_pct"}
        bon = set(a) == cles and set(a["entree"] or {}) == entree and set(a["temoins"]) == {"entend", "entendu", "parle", "chat_state"}
        verdict(bon, "AU3 contrat de /api/audio : %s" % sorted(a))
        verdict((a["verdict"], a["message"]) == ("ko", "casque « M50 » connecté mais son micro n'est pas utilisé"
                                                       " (Didier écoute « Audio interne Stéréo analogique »)"),
                "AU4 cas du 22/11 : %s / %s" % (a["verdict"], a["message"]))

        veille.etat = copy.deepcopy(SAIN)
        publier(pub_etat, "speaking")
        a = await attendre(s, lambda a: a["verdict"] == "ok" and a["temoins"]["parle"])
        verdict((a["verdict"], a["message"], a["entree"]["pct"]) == ("ok", "tout va bien : « M50 » → « M50 »", 71),
                "AU5 état sain : %s / %s / vumètre %s %%" % (a["verdict"], a["message"], a["entree"]["pct"]))
        publier(pub_entendu, json.dumps({"entendu": "bonjour Didier", "verdict": "gardé", "moteur": "distant"}))
        a = await attendre(s, lambda a: a["temoins"]["entend"] == "oui")
        verdict(a["temoins"]["parle"] is True and a["temoins"]["entend"] == "oui"
                and a["temoins"]["entendu"] == "bonjour Didier", "AU6 témoins : %s" % a["temoins"])

        async with s.get(WEB + "/scene") as r:
            page = await r.text()
        async with s.get(WEB + "/static/scene.js") as r:
            js = await r.text()
        ids = ["scene-audio", "audio-bandeau", "audio-verdict", "audio-vumetre-barre", "audio-temoin-entend",
               "audio-temoin-parle", "audio-tester", "audio-redetecter"]
        manquent = [i for i in ids if 'id="%s"' % i not in page]
        verdict(not manquent and '"/api/audio"' in js and 'type: "audio_banc"' in js,
                "AU7 page : onglet et %d éléments%s" % (len(ids), (" — manquent " + " ".join(manquent)) if manquent else ""))

        await ws.send_json({"type": "audio_banc", "action": "tester"})
        r = await reponse(ws)
        verdict(r == {"type": "ack", "topic": "audio_banc"} and veille.appels == ["tester"],
                "AU8 Tester le son : %s, veille %s" % (r, veille.appels))

        lecteur, _h = await client(s)
        await lecteur.send_json({"type": "audio_banc", "action": "tester"})
        r = await reponse(lecteur)
        await lecteur.close()
        verdict(r == {"type": "err", "reason": "écriture non détenue"} and veille.appels == ["tester"],
                "AU9 lecteur refusé : %s" % r)

        publier(pub_etat, "listening")
        await attendre(s, lambda a: a["temoins"]["chat_state"] == "listening")
        del chat_recus[:]
        await ws.send_json({"type": "audio_banc", "action": "redetecter"})
        r = await reponse(ws)
        fin = time.monotonic() + 20
        while time.monotonic() < fin and len(chat_recus) < 2:
            await asyncio.sleep(0.2)
        verdict(r == {"type": "ack", "topic": "audio_banc"} and veille.appels == ["tester", "redetecter"]
                and chat_recus == ["off", "on"],
                "AU10 Re-détecter : %s, veille %s, chat %s" % (r, veille.appels, chat_recus))
        hb.cancel()
        await ws.close()
        await runner.cleanup()

try:
    asyncio.run(main())
finally:
    arret.set()
    time.sleep(0.3)
    node.destroy_node()
    rclpy.shutdown()
print("=== AUDIO : %d OK, %d KO %s ===" % (ok, ko, time.strftime("%H:%M:%S")), flush=True)
sys.exit(0 if ko == 0 else 1)
PY
