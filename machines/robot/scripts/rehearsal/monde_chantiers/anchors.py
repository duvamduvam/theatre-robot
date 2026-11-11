"""Ancres des 30 POI : (nom, côté/latéral du déclencheur, rayon). Latéral <= rayon - 1."""
import math
SGN = 1
TH = math.radians(35.0); COSA, SINA = math.cos(TH), math.sin(TH)
C_X = 70.0
def world(s, v):
    if s <= C_X:
        return (s, SGN*v)
    d = s - C_X
    return (C_X + d*COSA + v*SINA, -SGN*d*SINA + v*SGN*COSA)
# latéral signé : - = côté bâtiments (v<0), + = côté Loire (v>0)
POIS = [("nefs",-2.0,4),("elephant",1.4,2.5),("carrousel",2.0,4),("table_basse",-1.4,2.5),("poster_bizarre",1.4,2.5),
("poubelle_tri",-1.4,2.5),("pigeon",1.4,2.5),("banc",-1.4,2.5),("flaque",0.0,2.5),("terrasse",-1.9,3),("grue_jaune",2.0,4),
("cale",1.9,3),("velo_cadenas",-1.4,2.5),("panneau_info",1.4,2.5),("rails",0.0,2.5),("lampadaire",-1.4,2.5),("anneaux",1.4,2.5),
("bollard",1.4,2.5),("loire",1.4,2.5),("plot_chantier",-1.4,2.5),("chien",1.4,2.5),("caisse_bois",-1.4,2.5),
("hangar_bananes",-1.9,3),("tas_de_sable",1.4,2.5),("horloge_arretee",-1.4,2.5),("bouche_incendie",1.4,2.5),
("pelouse",-1.9,3),("conteneur_rouge",1.4,2.5),("tag_mur",-1.4,2.5),("titan_grise",0.0,6)]
GAP = 4.6
def compute():
    out=[]; prev=None
    for i,(n,va,r) in enumerate(POIS):
        assert abs(va) <= r - 1.0, n
        if i < 15:
            s = 4.0 + 4.6*i
        else:
            gap = 8.0 if n == "titan_grise" else GAP
            s = max(prev["s"] + gap, 70.05)   # départ : au moins le gap en s
            while True:
                x,y = world(round(s,2), va)
                if x - prev["x"] >= gap and round(s,2) - prev["s"] >= gap: break
                s += 0.05
        s = round(s,2); x,y = world(s, va)
        prev = dict(name=n, s=s, va=va, x=round(x,2), y=round(y,2), r=r)
        out.append(prev)
    return out
if __name__ == "__main__":
    out = compute()
    for o in out: print(o)
    print("dx", [round(b["x"]-a["x"],2) for a,b in zip(out,out[1:])])
    print("ds", [round(b["s"]-a["s"],2) for a,b in zip(out,out[1:])])
