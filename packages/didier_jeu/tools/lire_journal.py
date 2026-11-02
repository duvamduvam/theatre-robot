#!/usr/bin/env python3
"""Rend un journal JSONL du sélecteur de jeu lisible par un humain (David).

QUOI : une ligne par événement, horodatée en secondes depuis le démarrage, avec
       l'action, la cible, le POURQUOI et les jauges (ennui, curiosité, lubie,
       fatigue) — le « pourquoi et quand Didier agit » tel qu'il s'est joué.
POURQUOI : la porte artistique d'A1 (spec §6) est la RELECTURE du journal par
       David, pas les 13 épreuves techniques. Un JSONL de 245 lignes imbriquées
       ne se relit pas ; ce tableau, si.
Usage : lire_journal.py <fichier_jeu.jsonl> [--md]   (--md = tableau Markdown)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

JAUGES = ("ennui", "curiosite", "lubie", "fatigue", "pression_route")


def _jauges(p: dict) -> str:
    j = p.get("pulsions") or {}
    return " ".join(f"{k[:3]}={j.get(k, 0):.1f}" for k in JAUGES if k in j)


def _ligne(r: dict, t0: int) -> tuple[str, str, str, str]:
    t = (r["t_mono_ms"] - t0) / 1000.0
    typ = r["type"]
    p = r.get("payload") or {}
    cible = p.get("cible") or p.get("piste") or ""
    if typ == "decision":
        action = p.get("action", "?")
        if p.get("sequence"):
            action += f" ({p['sequence']})"
        if p.get("maintien"):
            action = "garde " + action
        return f"{t:7.1f}", "DÉCIDE", f"{action} {cible}".strip(), f"{p.get('pourquoi', '')} — {_jauges(p)}"
    if typ == "fin":
        return f"{t:7.1f}", "fin", f"{p.get('action', '')} {cible}".strip(), p.get("pourquoi", "") or p.get("raison", "")
    if typ == "offre":
        return f"{t:7.1f}", "offre", f"{p.get('kind', '')} {cible}".strip(), p.get("pourquoi", "")
    if typ == "arret_didier":
        return f"{t:7.1f}", "ARRÊT (Didier)", cible, p.get("pourquoi", "")
    if typ in ("relais_stop", "relais_go"):
        return f"{t:7.1f}", typ.replace("relais_", "relais ").upper(), cible, p.get("pourquoi", "")
    if typ == "console":
        return f"{t:7.1f}", "CONSOLE (David)", f"{p.get('cmd', '')} {cible}".strip(), p.get("pourquoi", "")
    if typ == "naissance_piste":
        return f"{t:7.1f}", "personne", cible, p.get("pourquoi", "")
    return f"{t:7.1f}", typ, cible, p.get("pourquoi", "")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rows = [json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
    md = "--md" in sys.argv
    t0 = rows[0]["t_mono_ms"]
    if md:
        print("| t (s) | quoi | action / cible | pourquoi — jauges |\n|---|---|---|---|")
    for r in rows:
        t, quoi, action, pourquoi = _ligne(r, t0)
        if md:
            print(f"| {t} | {quoi} | {action} | {pourquoi.replace('|', '/')} |")
        else:
            print(f"{t} {quoi:16s} {action:40s} {pourquoi}")


if __name__ == "__main__":
    main()
