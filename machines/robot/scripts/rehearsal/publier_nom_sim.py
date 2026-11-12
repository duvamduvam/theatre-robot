#!/usr/bin/env python3
"""Publie un nom mDNS pour la SALLE DE RÉPÉTITION (PC de dev) sans avahi-utils
ni sudo : on parle directement au démon avahi par D-Bus (EntryGroup.AddAddress).

    python3 machines/robot/scripts/rehearsal/publier_nom_sim.py             # didier-sim.local -> IP du PC
    python3 machines/robot/scripts/rehearsal/publier_nom_sim.py autre.local 192.168.1.18

⚠️ JAMAIS « didier.local » : c'est le nom du VRAI robot (alias publié par le Pi,
conf/systemd/avahi-alias-didier.service) et la télécommande le vise. Un PC qui
répondrait aussi à ce nom mélangerait sim et réel — le script le refuse.

Le nom vit tant que ce processus vit (l'EntryGroup est lié à sa connexion
D-Bus) : Ctrl-C ou kill = le nom disparaît du réseau.
"""
import socket
import subprocess
import sys

import dbus
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

INTERDIT = {"didier.local"}
IF_UNSPEC, PROTO_INET = -1, 0   # avahi : toutes interfaces, IPv4
# AVAHI_PUBLISH_NO_REVERSE : sans lui, avahi publie aussi l'enregistrement
# inverse IP -> nom, qui EXISTE déjà (sitrix.local) -> « Local name collision »
# (vécu le 2026-10-31). On ne veut que nom -> IP.
PUBLISH_NO_REVERSE = 16


def ip_du_pc() -> str:
    return subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split()[0]


def main():
    nom = sys.argv[1] if len(sys.argv) > 1 else "didier-sim.local"
    ip = sys.argv[2] if len(sys.argv) > 2 else ip_du_pc()
    if nom in INTERDIT:
        sys.exit(f"refus : « {nom} » est le nom du VRAI robot — prends didier-sim.local")
    socket.inet_aton(ip)   # lève si l'IP est invalide
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    server = dbus.Interface(bus.get_object("org.freedesktop.Avahi", "/"), "org.freedesktop.Avahi.Server")
    group = dbus.Interface(bus.get_object("org.freedesktop.Avahi", server.EntryGroupNew()),
                           "org.freedesktop.Avahi.EntryGroup")
    group.AddAddress(IF_UNSPEC, PROTO_INET, dbus.UInt32(PUBLISH_NO_REVERSE), nom, ip)
    group.Commit()
    print(f"publié : {nom} -> {ip} (Ctrl-C pour retirer)", flush=True)
    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
