# Carte de la séance : rue vue de dessus, POI, trajectoire, pannes du journal,
# et vitesse /cmd_vel dans le temps. Entrées : out/traj.json, out/journal.jsonl.
import json, sys, yaml
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
D = sys.argv[1]; ROUTE = sys.argv[2]
traj = json.load(open(f"{D}/traj.json"))
ev = [json.loads(l) for l in open(f"{D}/journal.jsonl")]
route = yaml.safe_load(open(ROUTE))
t0 = next(e["t_mono_ms"] for e in ev if e["type"] == "scenario_start") / 1000
# décalage entre l'horloge de l'enregistreur et celle du journal : le départ
# (premier mouvement) de l'enregistreur ≈ scenario_start.
start_rec = next(t for t, x, y, c in traj if c > 0.01)
faults = {}
for e in ev:
    if e["type"] in ("fault_start", "fault_stop"):
        fid = e["payload"]["id"]; faults.setdefault(fid, {"type": e["payload"]["type"]})
        faults[fid][e["type"][6:]] = e["t_mono_ms"] / 1000 - t0 + start_rec
# lubie/chat ajoutés au lot R3 (14/10) pour ne pas planter sur un journal « chantiers » ;
# ⚠️ le FOND dessiné ci-dessous est celui de rue.sdf (hangar, trottoir) — pour le monde
# chantiers la trajectoire et la frise restent justes, le décor non (à généraliser).
COL = {"speed": "#d98e04", "relay": "#c0392b", "pause": "#7d3c98", "kill": "#111111", "instruction": "#1e8449",
       "lubie": "#e91e63", "chat": "#2980b9"}
LAB = {"batterie": "batterie faible", "freeze1": "gel consigne", "visage_fige": "visage figé", "zero1": "arrêt net",
       "lubie": "lubie (instruction)", "reboot": "reboot", "acoups": "à-coups", "liaison": "perte liaison", "retard": "réagit en retard"}
fig, (ax, bx) = plt.subplots(2, 1, figsize=(14, 7.5), gridspec_kw={"height_ratios": [1.1, 1]})
ax.add_patch(Rectangle((-5, -1.5), 70, 3, color="#cfcfcf")); ax.add_patch(Rectangle((-5, -8.5), 70, 7, color="#555"))
ax.add_patch(Rectangle((-5, 1.5), 70, 0.4, color="#d8c7a0")); ax.add_patch(Rectangle((62, -8), 8, 8, color="#8a8a8a"))
ax.text(66, -4, "HANGAR\nà bananes", ha="center", va="center", color="yellow", fontsize=9, weight="bold")
ax.add_patch(Rectangle((25, 1.4), 6, 0.3, color="#e07b39")); 
for p in route["pois"]:
    ax.plot(p["x"], p["y"], "o", color="#2471a3", ms=5); ax.text(p["x"], p["y"] + 0.55, p["name"].replace("_", " "), fontsize=7, ha="center", color="#1a5276")
xs = [x for _, x, _, _ in traj]; ys = [y for _, _, y, _ in traj]
ax.plot(xs, ys, "-", color="#222", lw=1.6, label="trajet de Didier")
for fid, f in faults.items():
    if "start" not in f: continue
    pts = [(x, y) for t, x, y, _ in traj if f["start"] <= t <= f.get("stop", f["start"]) + 0.5]
    if pts:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], lw=5, alpha=0.7, color=COL[f["type"]])
        ax.annotate(LAB.get(fid, fid), pts[0], xytext=(pts[0][0], -3.2 - 1.3 * (list(faults).index(fid) % 3)),
                    fontsize=8, color=COL[f["type"]], arrowprops=dict(arrowstyle="-", color=COL[f["type"]], lw=0.7))
ax.set_xlim(-5, 70); ax.set_ylim(-8.5, 3.2); ax.set_aspect("equal"); ax.set_title("La rue vue de dessus — trajet réel de Didier et pannes tombées (scénario « demo »)")
ax.set_xlabel("m"); ax.set_yticks([])
ts = [t for t, *_ in traj]; cs = [c for *_, c in traj]
bx.plot(ts, cs, color="#222", lw=1.2)
for fid, f in faults.items():
    if "start" in f:
        e = max(f.get("stop", f["start"]), f["start"] + 1.2)
        bx.axvspan(f["start"], e, color=COL[f["type"]], alpha=0.25); bx.text(f["start"], 0.43, LAB.get(fid, fid), rotation=90, fontsize=8, va="top", color=COL[f["type"]])
bx.set_ylim(-0.02, 0.45); bx.set_xlabel("temps (s)"); bx.set_ylabel("vitesse /cmd_vel (m/s)")
bx.set_title("Vitesse réellement envoyée aux roues (après mux et deadman)")
plt.tight_layout(); plt.savefig(f"{D}/carte_seance.png", dpi=110)
print("ok", {k: (round(v.get('start', -1), 1), round(v.get('stop', -1), 1)) for k, v in faults.items()})
