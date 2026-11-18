#!/usr/bin/env python3
"""Réglage SON + MICRO du banc PC (salle de répétition) — à lancer sur l'HÔTE.

    python3 machines/sim/banc-vision/audio_banc.py                # état : qui est branché à quoi
    python3 machines/sim/banc-vision/audio_banc.py choisir M50    # casque BT par nom (ou MAC)
    python3 machines/sim/banc-vision/audio_banc.py choisir defaut # suivre les réglages son d'Ubuntu
    python3 machines/sim/banc-vision/audio_banc.py choisir auto   # le meilleur micro/sortie présents
    python3 machines/sim/banc-vision/audio_banc.py choisir M50 --gain 0.3 --sans-redemarrer

POURQUOI : la tête de Didier (chat_node, conteneur didier-sim-vision) lit son micro
et parle par deux alias ALSA, `casque_mic` et `mixette`, définis dans
asound-pc.conf (monté sur /etc/asound.conf du conteneur). Jusqu'au 31/10 ils
visaient le M50 par une adresse MAC ÉCRITE EN DUR : un autre casque, ou le M50
déconnecté, donnait un Didier sourd et muet sans que rien ne le dise. Cet outil
rend la correspondance VISIBLE et la change en une commande.

`choisir <casque>` : connecte le casque (bluetoothctl), le passe en profil
CASQUE+MICRO (HFP — sans lui le micro du casque n'existe pas), réécrit les deux
lignes `device` d'asound-pc.conf avec les noms PipeWire RÉELS, puis redémarre le
conteneur vision (la tête rouvre micro et sortie au démarrage).
`choisir auto` (18/11, lancé par seance-chantiers.sh à chaque séance) : regarde ce qui
est RÉELLEMENT là et prend le meilleur. Micro : ReSpeaker (le micro du robot) >
micro d'un casque Bluetooth > micro du PC. Sortie : casque Bluetooth (pas de boucle
micro <-> haut-parleurs) > haut-parleurs du PC. Les casques appairés mais déconnectés
sont essayés un par un (quelques secondes chacun). Vécu le 18/11 : le M50 codé en dur
était éteint, PipeWire est retombé EN SILENCE sur le micro et les haut-parleurs du PC,
le micro entendait Didier et la transcription traînait — sans que rien ne le dise.
`choisir defaut` : `@DEFAULT_SOURCE@` / `@DEFAULT_SINK@` — Didier suit ce qui est
choisi dans Paramètres > Son d'Ubuntu (pratique, mais une séance de mesure peut
alors changer de micro si quelqu'un branche autre chose).

Rien ici ne touche au Pi ni au domaine ROS : banc PC uniquement.
"""
from __future__ import annotations

import argparse
import re
import struct
import subprocess
import sys
from pathlib import Path

CONF = Path(__file__).with_name("asound-pc.conf")
CONTAINER = "didier-sim-vision"   # L2b : service vision de machines/sim/docker-compose.yml
DEFAULT_IN, DEFAULT_OUT = "@DEFAULT_SOURCE@", "@DEFAULT_SINK@"

# Blocs d'asound-pc.conf dont on réécrit la ligne `device` (contrat du fichier).
BLOC_MICRO = "pcm.casque_mic_bt"
BLOC_SORTIE = "pcm.mixette"


# ─── logique PURE (testée : test/unit/test_audio_banc.py) ────────────

def lire_devices(conf_text: str) -> dict:
    """-> {"micro": nom, "sortie": nom} lus dans les blocs du contrat."""
    out = {}
    for cle, bloc in (("micro", BLOC_MICRO), ("sortie", BLOC_SORTIE)):
        m = re.search(re.escape(bloc) + r"\s*\{[^}]*?device\s+\"([^\"]*)\"", conf_text, re.S)
        out[cle] = m.group(1) if m else None
    return out


def ecrire_devices(conf_text: str, micro: str, sortie: str) -> str:
    """Remplace la ligne `device "..."` des deux blocs, rien d'autre. Lève
    ValueError si un bloc manque (le fichier ne respecte plus le contrat)."""
    for bloc, valeur in ((BLOC_MICRO, micro), (BLOC_SORTIE, sortie)):
        motif = re.compile(r"(" + re.escape(bloc) + r"\s*\{[^}]*?device\s+\")[^\"]*(\")", re.S)
        conf_text, n = motif.subn(lambda m: m.group(1) + valeur + m.group(2), conf_text, count=1)
        if n != 1:
            raise ValueError(f"bloc {bloc} avec une ligne device introuvable dans asound-pc.conf")
    return conf_text


def ecrire_gain(conf_text: str, gain: float) -> str:
    """Atténuation du micro (ttable du plugin route) — 0 < gain <= 1."""
    if not 0.0 < gain <= 1.0:
        raise ValueError(f"gain hors bornes ]0, 1] : {gain}")
    conf_text, n = re.subn(r"(ttable\.0\.0\s+)[0-9.]+", lambda m: m.group(1) + f"{gain:g}", conf_text, count=1)
    if n != 1:
        raise ValueError("ligne ttable.0.0 introuvable dans asound-pc.conf")
    return conf_text


def mac_cle(mac: str) -> str:
    """Forme comparable d'une MAC : PipeWire écrit 40:9C:… ou 40_9C_…"""
    return mac.upper().replace(":", "_")


def trouver_noeud(noms: list, mac: str) -> str | None:
    """Premier nœud PipeWire (sink/source, hors .monitor) qui porte la MAC."""
    cle = mac_cle(mac)
    for nom in noms:
        if not nom.endswith(".monitor") and cle in nom.upper().replace(":", "_"):
            return nom
    return None


def choisir_profil_hfp(profils: list) -> str | None:
    """Profil casque+micro : mSBC (16 kHz) d'abord, sinon CVSD, sinon tout
    profil « headset »/« hfp »."""
    for pref in ("headset-head-unit-msbc", "headset-head-unit", "headset-head-unit-cvsd"):
        if pref in profils:
            return pref
    for p in profils:
        if "headset" in p or "hfp" in p:
            return p
    return None


# Micro du robot (ReSpeaker XVF3800, carte ALSA « Array ») tel que PipeWire le nomme.
_RESPEAKER = re.compile(r"xvf|respeaker|array", re.I)


# Crête (|échantillon| max, s16) en dessous de laquelle un micro est MORT : entrée sans
# rien de branché ou gain à zéro. Mesuré le 18/11 sur ce PC : Scarlett 4i4 sans micro
# 2, carte USB générique 6, micro interne du PC au calme > 600.
CRETE_VIVANT = 30


def _rang_micro(nom: str) -> int:
    """Préférence entre micros VIVANTS : ReSpeaker < casque BT < USB externe < interne."""
    if _RESPEAKER.search(nom):
        return 0
    if nom.startswith("bluez_"):
        return 1
    if ".usb-" in nom:
        return 2
    return 3


def plan_auto(casques: list, sources: list, sinks: list, cretes: dict | None = None) -> tuple:
    """Choix automatique -> (micro, sortie, explication). `casques` = [(mac, nom)]
    des casques CONNECTÉS ; sources/sinks = noms PipeWire présents ; `cretes` =
    {source: crête mesurée} (None = pas de mesure, tout micro présent est
    supposé vivant). Le micro d'un casque n'existe qu'en profil HFP : l'appelant
    le pose avant (sinon ce casque ne sert que de sortie)."""
    noms_casques = {mac_cle(m): n for m, n in casques}
    micros = [s for s in sources if not s.endswith(".monitor")
              and (cretes is None or cretes.get(s, 0) >= CRETE_VIVANT)]
    morts = [s for s in sources if not s.endswith(".monitor") and s not in micros]
    sortie = quoi_sortie = None
    for mac, nom in casques:
        snk = trouver_noeud(sinks, mac)
        if snk:
            sortie, quoi_sortie = snk, f"casque {nom}"
            break
    if sortie is None:
        sortie, quoi_sortie = DEFAULT_OUT, "sortie son d'Ubuntu"
    if micros:
        micro = min(micros, key=_rang_micro)
        casque = next((n for k, n in noms_casques.items() if k in micro.upper().replace(":", "_")), None)
        quoi_micro = ["ReSpeaker (micro du robot)", f"micro du casque {casque}",
                      "micro USB", "micro interne du PC"][_rang_micro(micro)] + f" [{micro}]"
    else:
        micro, quoi_micro = DEFAULT_IN, "⚠️ AUCUN micro ne capte — défaut d'Ubuntu, Didier sera sans doute sourd"
    note = ""
    if _rang_micro(micro) >= 2 and sortie == DEFAULT_OUT:
        note = " — ⚠️ micro du PC et sortie hors casque : le micro peut entendre Didier"
    if morts:
        note += f" ; micros muets écartés : {', '.join(morts)}"
    return micro, sortie, f"micro = {quoi_micro} ; sortie = {quoi_sortie}{note}"


def resoudre_casque(appaires: list, cible: str) -> tuple | None:
    """(mac, nom) d'après un nom (insensible à la casse, sous-chaîne) ou une MAC."""
    c = cible.strip().lower()
    for mac, nom in appaires:
        if c == mac.lower():
            return mac, nom
    exacts = [(m, n) for m, n in appaires if n.lower() == c]
    if exacts:
        return exacts[0]
    partiels = [(m, n) for m, n in appaires if c in n.lower()]
    return partiels[0] if len(partiels) == 1 else None


# ─── I/O (hôte) ────────────────────────────────────────────────────────────

def sh(*cmd, check=False) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} : {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def casques_appaires() -> list:
    """[(mac, nom, connecté)] des appareils audio appairés."""
    res = []
    for ligne in sh("bluetoothctl", "devices", "Paired").splitlines():
        parts = ligne.split(" ", 2)
        if len(parts) < 3:
            continue
        info = sh("bluetoothctl", "info", parts[1])
        if "Icon: audio" in info:
            res.append((parts[1], parts[2], "Connected: yes" in info))
    return res


def noeuds(kind: str) -> list:
    return [l.split("\t")[1] for l in sh("pactl", "list", "short", kind).splitlines() if "\t" in l]


def etat() -> int:
    conf = lire_devices(CONF.read_text(encoding="utf-8"))
    sinks, sources = noeuds("sinks"), noeuds("sources")
    print("Casques Bluetooth appairés :")
    for mac, nom, co in casques_appaires():
        print(f"  {'● CONNECTÉ ' if co else '○ déconnecté'}  {nom:<20} {mac}")
    print("\nSorties son du PC :")
    for s in sinks:
        print(f"  {s}")
    print("Micros du PC :")
    for s in sources:
        if not s.endswith(".monitor"):
            print(f"  {s}")
    print("\nCe que Didier utilise (asound-pc.conf) :")
    ok = True
    for cle, liste, defaut in (("micro", sources, DEFAULT_IN), ("sortie", sinks, DEFAULT_OUT)):
        val = conf[cle]
        present = val == defaut or any(mac_cle(val or "x") in n.upper().replace(":", "_") or n == val for n in liste)
        ok &= present
        etiquette = "réglages Ubuntu" if val == defaut else ("PRÉSENT" if present else "ABSENT — Didier est sourd/muet de ce côté")
        print(f"  {cle:<7} {val}   [{etiquette}]")
    if not ok:
        print("\n→ connecte le casque puis : python3 machines/sim/banc-vision/audio_banc.py choisir <nom>")
    return 0 if ok else 1


def poser_hfp(mac: str) -> bool:
    """Passe la carte PipeWire du casque en profil casque+micro. False si absente/sans HFP."""
    carte = next((c for c in noeuds("cards") if mac_cle(mac) in c.upper().replace(":", "_")), None)
    if not carte:
        return False
    profil = choisir_profil_hfp(re.findall(r"^\t\t([\w-]+):", sh("pactl", "list", "cards"), re.M))
    if not profil:
        return False
    sh("pactl", "set-card-profile", carte, profil)
    return True


def crete(source: str, duree_s: float = 2.0) -> int:
    """|échantillon| max sur `duree_s` de capture (parecord, s16 mono 16 kHz)."""
    try:
        r = subprocess.run(["parecord", "-d", source, "--raw", "--format=s16le", "--rate=16000",
                            "--channels=1"], capture_output=True, timeout=duree_s + 0.3)
        brut = r.stdout
    except subprocess.TimeoutExpired as e:
        brut = e.stdout or b""
    brut = brut[19200:]  # 600 ms d'amorçage : parecord rend ~0,5 s de zéros à l'ouverture (18/11)
    n = len(brut) // 2
    return max((abs(v) for v in struct.unpack(f"<{n}h", brut[:2 * n])), default=0)


def connecter(mac: str, attente_s: float = 8.0) -> bool:
    try:
        subprocess.run(["bluetoothctl", "connect", mac], capture_output=True, timeout=attente_s)
    except subprocess.TimeoutExpired:
        pass
    return "Connected: yes" in sh("bluetoothctl", "info", mac)


def auto() -> tuple:
    """Constate ce qui est branché, tente les casques appairés, puis plan_auto."""
    casques = casques_appaires()
    connectes = [(m, n) for m, n, co in casques if co]
    if not connectes:
        for mac, nom, _ in casques:
            print(f"essai du casque {nom}…", flush=True)
            if connecter(mac):
                connectes = [(mac, nom)]
                break
    respeaker = any(_RESPEAKER.search(s) for s in noeuds("sources") if not s.endswith(".monitor"))
    if not respeaker:
        # Sans ReSpeaker, le micro vient du casque : profil HFP (sinon le casque reste
        # en A2DP, meilleure sortie, et le ReSpeaker écoute).
        for mac, _ in connectes:
            poser_hfp(mac)
        if connectes:
            subprocess.run(["sleep", "2"])   # PipeWire crée les nœuds HFP en différé
    sources = noeuds("sources")
    cretes = {s: crete(s) for s in sources if not s.endswith(".monitor")}
    return plan_auto(connectes, sources, noeuds("sinks"), cretes)


def choisir(cible: str, gain: float | None, redemarrer: bool) -> int:
    texte = CONF.read_text(encoding="utf-8")
    if cible.lower() == "auto":
        micro, sortie, pourquoi = auto()
        print(f"Choix automatique : {pourquoi}")
    elif cible.lower() in ("defaut", "défaut", "default"):
        micro, sortie = DEFAULT_IN, DEFAULT_OUT
        print("Didier suivra le micro et la sortie choisis dans les réglages son d'Ubuntu.")
    else:
        appaires = [(m, n) for m, n, _ in casques_appaires()]
        trouve = resoudre_casque(appaires, cible)
        if not trouve:
            print(f"casque « {cible} » introuvable ou ambigu parmi : {', '.join(n for _, n in appaires)}")
            return 2
        mac, nom = trouve
        print(f"Connexion de {nom} ({mac})…")
        sh("bluetoothctl", "connect", mac)
        carte = next((c for c in noeuds("cards") if mac_cle(mac) in c.upper().replace(":", "_")), None)
        if not carte:
            print("le casque n'apparaît pas dans PipeWire : allume-le / rapproche-le, puis recommence")
            return 3
        profils = re.findall(r"^\t\t([\w-]+):", sh("pactl", "list", "cards"), re.M)
        profil = choisir_profil_hfp(profils)
        if not profil:
            print("aucun profil casque+micro (HFP) proposé par ce casque : il n'a peut-être pas de micro")
            return 4
        sh("pactl", "set-card-profile", carte, profil, check=True)
        micro, sortie = trouver_noeud(noeuds("sources"), mac), trouver_noeud(noeuds("sinks"), mac)
        if not micro or not sortie:
            print(f"profil {profil} posé, mais micro={micro} sortie={sortie} : réessaie dans 2 s")
            return 5
        print(f"Profil {profil} : micro {micro}, sortie {sortie}")
    texte = ecrire_devices(texte, micro, sortie)
    if gain is not None:
        texte = ecrire_gain(texte, gain)
    CONF.write_text(texte, encoding="utf-8")
    print(f"asound-pc.conf mis à jour.")
    if redemarrer:
        print(f"Redémarrage de {CONTAINER} (la tête rouvre micro et sortie)…")
        sh("docker", "restart", CONTAINER)
    return etat()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("choisir", help="casque par nom/MAC, « auto » ou « defaut »")
    c.add_argument("casque")
    c.add_argument("--gain", type=float, default=None,
                   help="atténuation micro ]0,1] (0.15 réglé pour le M50 le 22/10)")
    c.add_argument("--sans-redemarrer", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "choisir":
        return choisir(a.casque, a.gain, not a.sans_redemarrer)
    return etat()


if __name__ == "__main__":
    sys.exit(main())
