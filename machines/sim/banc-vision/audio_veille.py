#!/usr/bin/env python3
"""Veille audio du banc PC — petit service HÔTE de la séance, lu par la page scène (onglet Audio).

    python3 machines/sim/banc-vision/audio_veille.py            # 127.0.0.1:8767
    AUDIO_VEILLE_PORT=8770 python3 machines/sim/banc-vision/audio_veille.py

POURQUOI (22/11, David en séance : « je ne sais jamais si je suis branché et si le son entre et
sort, je perds du temps inutilement ») : le micro et la sortie de la tête sont des nœuds
PipeWire et des casques Bluetooth de l'HÔTE. Aucun conteneur ne voit bluetoothctl, et donner au
pont web (conteneur robot) l'accès à la session son ou à Docker serait un privilège nouveau.
Ce service tourne donc sur le PC, à côté de `audio_banc.py` dont il RÉUTILISE tout (contrat
d'asound-pc.conf, listes PipeWire, casques appairés, seuil de micro vivant, choix automatique),
et ne sert qu'en local (127.0.0.1) ; le pont web (réseau host) le relaie à la page.

Ce qu'il CONSTATE, jamais ce qu'il suppose :
  - GET  /etat        micro et sortie RÉELLEMENT écrits dans asound-pc.conf, résolus (défaut
                      d'Ubuntu compris), présents ou non dans PipeWire, coupés (mute) ou non, le
                      casque Bluetooth qui les porte et s'il est connecté ; niveau du micro
                      mesuré EN CONTINU (parecord sur le nœud même que lit la tête) ;
  - POST /tester      un bip court joué PAR LA CHAÎNE DE LA VOIX : `aplay -D mixette` DANS le
                      conteneur de la tête (même alias, même asound.conf que chat_node) ;
  - POST /redetecter  `audio_banc.py choisir auto --sans-redemarrer` en tâche de fond (la tête
                      n'est pas redémarrée : arecord/aplay sont relancés à chaque tour et relisent
                      asound.conf — le pont rouvre le micro par Parole OFF puis ON).
Aucune écriture hors de ce que fait déjà `audio_banc.py choisir`. Banc PC uniquement.
"""
from __future__ import annotations

import io
import json
import math
import os
import signal
import struct
import subprocess
import sys
import threading
import time
import wave
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

Json = dict[str, Any]   # un objet JSON (état rendu au pont, nœud PipeWire…)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audio_banc as ab  # noqa: E402  (même dossier : la logique du choix n'est écrite qu'une fois)

PORT_DEFAUT = 8767          # 8765 = pont web, 8766 = aperçu du visage
SONDE_PERIODE_S = 2.0       # bluetoothctl + pactl : assez frais pour « je viens de l'allumer »
TAUX = 16000                # même format que la tête (mic.py : S16_LE, 16 kHz, mono)
TRAME_OCTETS = 1600         # 50 ms de s16 mono à 16 kHz
AMORCAGE_S = 0.6            # parecord rend ~0,5 s de zéros à l'ouverture (audio_banc.crete, 18/11)
FENETRE_S = 5.0             # historique du vumètre gardé
INSTANT_S = 0.15            # « niveau maintenant » = crête des 150 dernières ms
MUET_S = 3.0                # « micro plat » = sous CRETE_VIVANT pendant 3 s
RESUME_MAX = 600            # caractères de sortie de `choisir auto` rendus à la page


# ─── logique PURE (testée : packages/didier_vision/test/unit/test_audio_veille.py) ───

def crete_s16(brut: bytes) -> int:
    """|échantillon| max d'un bloc s16le (octet impair final ignoré)."""
    n = len(brut) // 2
    return max((abs(v) for v in struct.unpack(f"<{n}h", brut[:2 * n])), default=0)


class Fenetre:
    """Crêtes horodatées du micro (horloge INJECTÉE : testable sans attendre)."""

    def __init__(self, duree_s: float = FENETRE_S) -> None:
        self._duree_s = duree_s
        self._points: deque[tuple[float, int]] = deque()

    def ajouter(self, t: float, crete: int) -> None:
        self._points.append((t, crete))
        while self._points and self._points[0][0] < t - self._duree_s:
            self._points.popleft()

    def crete_depuis(self, maintenant: float, duree_s: float) -> int | None:
        """Crête max sur les `duree_s` dernières secondes ; None si aucun point."""
        vus = [c for t, c in self._points if t >= maintenant - duree_s]
        return max(vus) if vus else None

    def vider(self) -> None:
        self._points.clear()


def lire_noeuds_pactl(texte: str) -> dict[str, Json]:
    """`LANG=C pactl list sinks|sources` -> {nom: {"description", "muet"}}.
    (Le JSON de pactl 17 casse sur les descriptions accentuées : vécu le 22/11.)"""
    noeuds: dict[str, Json] = {}
    courant: Json | None = None
    for ligne in texte.splitlines():
        cle, _, valeur = ligne.strip().partition(": ")
        if cle == "Name":
            courant = {"description": None, "muet": None}
            noeuds[valeur.strip()] = courant
        elif courant is not None and cle == "Description":
            courant["description"] = valeur.strip()
        elif courant is not None and cle == "Mute":
            courant["muet"] = valeur.strip() == "yes"
    return noeuds


def decrire_cote(conf: str | None, symbole_defaut: str, defaut_reel: str | None,
                 noeuds: dict[str, Json], casques: list[tuple[str, str, bool]]) -> Json:
    """Un côté (micro ou sortie) tel que la tête l'utilise RÉELLEMENT.
    `conf` = ligne device d'asound-pc.conf ; `symbole_defaut` = @DEFAULT_SOURCE@/@DEFAULT_SINK@ ;
    `defaut_reel` = ce que PipeWire désigne aujourd'hui par ce symbole ; `noeuds` = présents
    (hors .monitor) ; `casques` = [(mac, nom, connecté)] appairés."""
    suit_ubuntu = conf == symbole_defaut
    pipewire = defaut_reel if suit_ubuntu else conf
    infos = noeuds.get(pipewire or "")
    casque = None
    if pipewire:
        for mac, nom, connecte in casques:
            if ab.mac_cle(mac) in pipewire.upper().replace(":", "_"):
                casque = {"nom": nom, "connecte": connecte}
                break
    nom_lisible = (infos or {}).get("description") or (casque or {}).get("nom") or pipewire
    return {
        "respeaker": bool(pipewire and ab._RESPEAKER.search(pipewire)),
        "conf": conf,
        "suit_ubuntu": suit_ubuntu,
        "pipewire": pipewire,
        "nom": nom_lisible,
        "present": infos is not None,
        "muet": (infos or {}).get("muet"),
        "casque": casque,
    }


def decrire_casques(casques: list[tuple[str, str, bool]], sources: list[str], sinks: list[str]) -> list[Json]:
    """Casques appairés, et pour chacun si PipeWire a son entrée (micro, profil HFP) et sa
    sortie : de quoi dire « casque connecté mais son micro n'est pas utilisé » (22/11)."""
    return [{"nom": nom, "connecte": co,
             "micro_present": co and ab.trouver_noeud(sources, mac) is not None,
             "sortie_present": co and ab.trouver_noeud(sinks, mac) is not None}
            for mac, nom, co in casques]


def etat_niveau(fenetre: Fenetre, maintenant: float, ouvert_depuis: float | None,
                erreur: str | None) -> Json:
    """Le vumètre : crête instantanée, crête des 3 dernières s, et depuis quand on écoute.
    `muet_constate` n'est vrai qu'après MUET_S d'écoute réelle (pas au démarrage)."""
    ecoute_s = None if ouvert_depuis is None else max(0.0, maintenant - ouvert_depuis - AMORCAGE_S)
    crete_3s = fenetre.crete_depuis(maintenant, MUET_S)
    muet = (ecoute_s is not None and ecoute_s >= MUET_S
            and (crete_3s or 0) < ab.CRETE_VIVANT)
    return {
        "crete": fenetre.crete_depuis(maintenant, INSTANT_S),
        "crete_3s": crete_3s,
        "ecoute_s": None if ecoute_s is None else round(ecoute_s, 1),
        "muet_constate": muet,
        "seuil_vivant": ab.CRETE_VIVANT,
        "erreur": erreur,
    }


def bip_wav(frequence: float = 880.0, duree_s: float = 0.35, taux: int = TAUX,
            amplitude: float = 0.3) -> bytes:
    """WAV mono s16 d'un bip sinusoïdal, attaque et chute de 20 ms (pas de « clic »)."""
    n = int(taux * duree_s)
    rampe = max(1, int(taux * 0.02))
    echantillons = []
    for i in range(n):
        enveloppe = min(1.0, i / rampe, (n - 1 - i) / rampe)
        echantillons.append(int(32767 * amplitude * enveloppe * math.sin(2 * math.pi * frequence * i / taux)))
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(struct.pack(f"<{n}h", *echantillons))
    return tampon.getvalue()


def resume_sortie(texte: str, maximum: int = RESUME_MAX) -> str:
    """La fin de la sortie de `choisir auto` (c'est là qu'est le choix et l'état)."""
    texte = texte.strip()
    return texte if len(texte) <= maximum else "…" + texte[-(maximum - 1):]


# ─── I/O (hôte) ────────────────────────────────────────────────────────────

def _pactl_c(*args: str) -> str:
    env = dict(os.environ, LANG="C", LC_ALL="C")
    r = subprocess.run(["pactl", *args], capture_output=True, text=True, env=env, timeout=5)
    return r.stdout


def _sans_monitor(noeuds: dict[str, Json]) -> dict[str, Json]:
    return {n: i for n, i in noeuds.items() if not n.endswith(".monitor")}


def sonder() -> Json:
    """Une photo de l'audio du banc (quelques appels pactl/bluetoothctl, < 1 s)."""
    conf = ab.lire_devices(ab.CONF.read_text(encoding="utf-8"))
    casques = ab.casques_appaires()
    sources = _sans_monitor(lire_noeuds_pactl(_pactl_c("list", "sources")))
    sinks = lire_noeuds_pactl(_pactl_c("list", "sinks"))
    return {
        "micro": decrire_cote(conf["micro"], ab.DEFAULT_IN, _pactl_c("get-default-source").strip() or None,
                              sources, casques),
        "sortie": decrire_cote(conf["sortie"], ab.DEFAULT_OUT, _pactl_c("get-default-sink").strip() or None,
                               sinks, casques),
        "casques": decrire_casques(casques, list(sources), list(sinks)),
    }


class Vumetre(threading.Thread):
    """parecord EN CONTINU sur le nœud du micro de la tête ; relancé si le nœud change ou meurt.
    PipeWire accepte plusieurs lecteurs : la tête n'en est pas gênée."""

    def __init__(self) -> None:
        super().__init__(daemon=True, name="vumetre")
        self.lock = threading.Lock()
        self.fenetre = Fenetre()
        self.ouvert_depuis: float | None = None
        self.erreur: str | None = None
        self._cible: str | None = None
        self._proc: subprocess.Popen[bytes] | None = None

    def viser(self, source: str | None) -> None:
        if source == self._cible:
            return
        self._cible = source
        self._fermer()

    def _fermer(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def instant(self) -> Json:
        with self.lock:
            return etat_niveau(self.fenetre, time.monotonic(), self.ouvert_depuis, self.erreur)

    def run(self) -> None:
        while True:
            cible = self._cible
            if not cible:
                with self.lock:
                    self.ouvert_depuis, self.erreur = None, "aucun micro à écouter"
                    self.fenetre.vider()
                time.sleep(0.5)
                continue
            proc = subprocess.Popen(
                ["parecord", "-d", cible, "--raw", "--format=s16le", f"--rate={TAUX}",
                 "--channels=1", "--latency-msec=50"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._proc = proc
            with self.lock:
                self.ouvert_depuis, self.erreur = time.monotonic(), None
                self.fenetre.vider()
            debut = time.monotonic()
            while self._proc is proc and proc.stdout is not None:
                bloc = proc.stdout.read(TRAME_OCTETS)
                if len(bloc) < TRAME_OCTETS:
                    break
                maintenant = time.monotonic()
                if maintenant - debut >= AMORCAGE_S:
                    with self.lock:
                        self.fenetre.ajouter(maintenant, crete_s16(bloc))
            if proc.poll() is None:
                proc.terminate()
            proc.wait()
            if self._cible == cible and self._proc is proc:
                # Mort toute seule (nœud disparu, casque éteint) : on le dit, on réessaie.
                err = (proc.stderr.read().decode(errors="replace").strip() if proc.stderr else "")
                with self.lock:
                    self.ouvert_depuis = None
                    self.erreur = f"le micro ne s'ouvre pas ({err or 'flux coupé'})"[:200]
                time.sleep(1.0)


class Veille:
    """État partagé du service : dernière sonde, vumètre, dernière action."""

    def __init__(self, sonde: Callable[[], Json] = sonder) -> None:
        self._sonde = sonde
        self.lock = threading.Lock()
        self.photo: Json | None = None
        self.photo_t: float | None = None
        self.erreur_sonde: str | None = None
        self.vumetre = Vumetre()
        self.redetection: Json = {"en_cours": False, "fin_t": None, "code": None, "resume": None}
        self.derniere_action: Json | None = None

    def boucle_sonde(self) -> None:
        while True:
            try:
                photo = self._sonde()
                with self.lock:
                    self.photo, self.photo_t, self.erreur_sonde = photo, time.monotonic(), None
                self.vumetre.viser(photo["micro"]["pipewire"] if photo["micro"]["present"] else None)
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                with self.lock:
                    self.erreur_sonde = str(e)[:200]
            time.sleep(SONDE_PERIODE_S)

    def etat(self) -> Json:
        maintenant = time.monotonic()
        with self.lock:
            photo, photo_t, erreur = self.photo, self.photo_t, self.erreur_sonde
            redet = dict(self.redetection)
            action = dict(self.derniere_action) if self.derniere_action else None
        fin_t = redet.pop("fin_t")
        redet["il_y_a_s"] = None if fin_t is None else round(maintenant - fin_t, 1)
        if action is not None:
            action["il_y_a_s"] = round(maintenant - action.pop("t"), 1)
        return {
            "v": 1,
            **(photo or {"micro": None, "sortie": None, "casques": []}),
            "photo_age_s": None if photo_t is None else round(maintenant - photo_t, 1),
            "erreur_sonde": erreur,
            "niveau": self.vumetre.instant(),
            "redetection": redet,
            "derniere_action": action,
        }

    def _noter(self, action: str, ok: bool, message: str) -> Json:
        with self.lock:
            self.derniere_action = {"action": action, "ok": ok, "message": message, "t": time.monotonic()}
        return {"ok": ok, "message": message}

    def tester(self) -> Json:
        """Bip par `aplay -D mixette` DANS la tête : la chaîne exacte de la voix de Didier."""
        try:
            r = subprocess.run(["docker", "exec", "-i", ab.CONTAINER, "aplay", "-q", "-D", "mixette", "-"],
                               input=bip_wav(), capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as e:
            return self._noter("tester", False, f"bip non joué : {e}")
        if r.returncode != 0:
            err = r.stderr.decode(errors="replace").strip() or f"code {r.returncode}"
            return self._noter("tester", False, f"bip non joué par la tête : {err[:200]}")
        with self.lock:
            sortie = (self.photo or {}).get("sortie") or {}
        return self._noter("tester", True, f"bip joué par la tête sur « {sortie.get('nom') or '?'} »")

    def redetecter(self) -> Json:
        with self.lock:
            if self.redetection["en_cours"]:
                return {"ok": False, "message": "re-détection déjà en cours"}
            self.redetection = {"en_cours": True, "fin_t": None, "code": None, "resume": None}
        threading.Thread(target=self._redetecter, daemon=True, name="redetection").start()
        return {"ok": True, "message": "re-détection lancée"}

    def _redetecter(self) -> None:
        try:
            r = subprocess.run([sys.executable, str(Path(ab.__file__)), "choisir", "auto", "--sans-redemarrer"],
                               capture_output=True, text=True, timeout=180)
            code, sortie = r.returncode, r.stdout + r.stderr
        except (OSError, subprocess.TimeoutExpired) as e:
            code, sortie = -1, f"échec : {e}"
        with self.lock:
            self.redetection = {"en_cours": False, "fin_t": time.monotonic(), "code": code,
                                "resume": resume_sortie(sortie)}


def fabriquer_gestionnaire(veille: Veille) -> type[BaseHTTPRequestHandler]:
    class Gestionnaire(BaseHTTPRequestHandler):
        def _json(self, code: int, corps: Json) -> None:
            data = json.dumps(corps, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 (nom imposé par http.server)
            if self.path == "/etat":
                self._json(200, veille.etat())
            else:
                self._json(404, {"erreur": "inconnu"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/tester":
                self._json(200, veille.tester())
            elif self.path == "/redetecter":
                rep = veille.redetecter()
                self._json(202 if rep["ok"] else 409, rep)
            else:
                self._json(404, {"erreur": "inconnu"})

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # 4 requêtes/s du pont : pas de journal par requête

    return Gestionnaire


def main() -> int:
    port = int(os.environ.get("AUDIO_VEILLE_PORT", PORT_DEFAUT))
    veille = Veille()
    veille.vumetre.start()
    threading.Thread(target=veille.boucle_sonde, daemon=True, name="sonde").start()
    # 127.0.0.1 SEULEMENT : /redetecter et /tester agissent sur le son du PC ; seul le pont
    # web (réseau host, droits d'écriture vérifiés) les relaie.
    serveur = ThreadingHTTPServer(("127.0.0.1", port), fabriquer_gestionnaire(veille))
    # SIGTERM (seance-chantiers.sh --stop) : sortie propre, le parecord du vumètre est fermé.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print(f"veille audio du banc sur http://127.0.0.1:{port}/etat", flush=True)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        veille.vumetre.viser(None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
