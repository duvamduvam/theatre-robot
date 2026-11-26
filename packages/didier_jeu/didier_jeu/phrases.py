"""Les phrases du journal « pourquoi » — lisibles par David, pas par un
technicien (revue A1, point 6) : « il s'ennuie (0,40) → une expression
spontanée ». Chiffres entre parenthèses, virgule décimale ; jamais d'état
interne brut (pas d'`animation_state ''`, pas de « 0 offre(s) tuée(s) »).
UNE seule source pour le journal ET l'intention affichée.
"""


def n(x: float) -> str:
    """0.4 -> « 0,40 »."""
    return f"{x:.2f}".replace(".", ",")


def s(x: float) -> str:
    """Durée en secondes : 2.25 -> « 2,2 s »."""
    return f"{x:.1f} s".replace(".", ",")


def demande(d) -> str:
    """Une demande de mouvement (payload chat_move) en mots."""
    if d == "go":
        return "repartir"
    if not isinstance(d, dict):
        return repr(d)
    cmd = d.get("cmd")
    if cmd == "aller_voir":
        return f"aller voir « {d.get('objet')} »"
    if cmd == "tour_de":
        return f"faire le tour de « {d.get('objet')} »"
    if cmd == "tourner":
        return f"tourner de {d.get('angle_deg')}°"
    if cmd == "avancer":
        return f"avancer de {d.get('metres')} m"
    return repr(d)


def action(nom: str, cible=None, detail=None) -> str:
    """Ce que Didier fait, en mots."""
    detail = detail or {}
    return {
        "rien": "rester tranquille",
        "regarder": "la regarder",
        "accueil": "la saluer",
        "spontanee": "une expression spontanée",
        "approcher": "s'approcher d'elle",
        "lubie": f"réclamer de s'arrêter devant « {cible} »",
        "bouche": f"faire ce qu'il a dit ({demande(detail.get('demande'))})",
        "aller_voir": f"aller voir « {cible} »",
        "repartir": "repartir",
    }.get(nom, nom)


def offre(o, valeur: float) -> str:
    if o.kind == "personne":
        return f"une personne, {o.piste} (offre {n(valeur)})"
    return f"il passe près de « {o.piste} » (offre {n(valeur)})"


PULSIONS = {"ennui": "il s'ennuie", "curiosite": "curiosité", "lubie": "lubie",
            "pression_route": "assez attendu en silence", "fatigue": "fatigue"}


def pulsion(nom: str, valeur: float) -> str:
    return f"{PULSIONS.get(nom, nom)} ({n(valeur)})"


# Qui porte une demande de marche (lot S1 : son ORIGINE, plus le canal qui l'a apportée).
QUI = {"david": "David", "didier": "Didier"}


def qui(origine: str) -> str:
    return QUI.get(origine, origine)
