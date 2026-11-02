"""PULSIONS : ennui, curiosité, lubie, fatigue — et la « pression de route ».

Toutes bornées dans [0, 1]. Chiffres : reglages.yaml `pulsions` (spec §3 et
§8.1). Horloge injectée : avancer(dt, ...) à chaque tick.

- ennui : +montee_par_s / s quand RIEN ne se passe (aucune offre vivante,
  aucune action engagée) ; 0 à toute action ; plafond.
- curiosité : saute à `saut` à la naissance d'une PISTE ; −retombee_par_s / s.
- lubie : +par_poi par POI entré ; −retombee_par_s / s ; plafond.
- fatigue : +par_deplacement par action de déplacement ; −retombee_par_s / s ;
  au-dessus de seuil_interdit, tout déplacement est interdit.
- pression de route : ne monte QUE pendant un arrêt décidé par Didier
  (jamais après un stop/off de David) : temps écoulé / reprise.delai_s. Elle
  ne coupe rien ; à 1, Didier propose de repartir et envoie « go ».
"""


def _borne(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


class Pulsions:
    def __init__(self, reglages):
        r = reglages
        self.ennui_montee = r.get("pulsions.ennui.montee_par_s")
        self.ennui_plafond = r.get("pulsions.ennui.plafond")
        self.curiosite_saut = r.get("pulsions.curiosite.saut")
        self.curiosite_retombee = r.get("pulsions.curiosite.retombee_par_s")
        self.lubie_par_poi = r.get("pulsions.lubie.par_poi")
        self.lubie_retombee = r.get("pulsions.lubie.retombee_par_s")
        self.lubie_plafond = r.get("pulsions.lubie.plafond")
        self.fatigue_par_deplacement = r.get("pulsions.fatigue.par_deplacement")
        self.fatigue_retombee = r.get("pulsions.fatigue.retombee_par_s")
        self.fatigue_seuil = r.get("pulsions.fatigue.seuil_interdit")
        self.ennui = 0.0
        self.curiosite = 0.0
        self.lubie = 0.0
        self.fatigue = 0.0
        self.pression_route = 0.0

    def avancer(self, dt: float, calme: bool) -> None:
        if calme:
            self.ennui = min(self.ennui_plafond, self.ennui + self.ennui_montee * dt)
        self.curiosite = _borne(self.curiosite - self.curiosite_retombee * dt)
        self.lubie = _borne(self.lubie - self.lubie_retombee * dt)
        self.fatigue = _borne(self.fatigue - self.fatigue_retombee * dt)

    def sur_action(self, deplacement: bool) -> None:
        self.ennui = 0.0
        if deplacement:
            self.fatigue = _borne(self.fatigue + self.fatigue_par_deplacement)

    def sur_piste_nee(self) -> None:
        self.curiosite = _borne(self.curiosite_saut)

    def sur_poi(self) -> None:
        self.lubie = min(self.lubie_plafond, _borne(self.lubie + self.lubie_par_poi))

    def deplacement_interdit(self) -> bool:
        return self.fatigue > self.fatigue_seuil

    def jauges(self) -> dict:
        return {"ennui": round(self.ennui, 2), "curiosite": round(self.curiosite, 2),
                "lubie": round(self.lubie, 2), "fatigue": round(self.fatigue, 2),
                "pression_route": round(self.pression_route, 2)}
