"""Tests de didier_vision/ai/reflection_policy.py — horloge injectée, valeurs gravées."""
import pytest

from didier_vision.ai.reflection_policy import (DeepRequests, Job, ReflectionScheduler,
                                         SpontaneousPolicy)


# -- ReflectionScheduler ----------------------------------------------------

def test_rien_ne_se_passe_sans_evenement():
    assert ReflectionScheduler().next_job(0.0, False) is None


def test_david_attend_le_debounce():
    sched = ReflectionScheduler()
    sched.notify("david", 10.0)
    assert sched.next_job(10.5, False) is None
    assert sched.next_job(10.99, False) is None
    assert sched.next_job(11.0, False) == Job(deep=False, reason="david")


def test_nouvelle_ligne_david_repousse_le_debounce():
    sched = ReflectionScheduler()
    sched.notify("david", 10.0)
    sched.notify("david", 10.8)
    assert sched.next_job(11.5, False) is None
    assert sched.next_job(11.8, False) is not None


def test_intervalle_minimal_entre_deux_departs():
    sched = ReflectionScheduler()
    sched.notify("poi", 0.0)
    assert sched.next_job(0.0, False) == Job(deep=False, reason="poi")
    sched.notify("poi", 1.0)
    assert sched.next_job(3.9, False) is None
    assert sched.next_job(4.0, False) == Job(deep=False, reason="poi")


def test_david_respecte_aussi_l_intervalle():
    sched = ReflectionScheduler()
    sched.notify("poi", 0.0)
    sched.next_job(0.0, False)
    sched.notify("david", 1.0)
    assert sched.next_job(3.0, False) is None   # debounce passé, intervalle non
    assert sched.next_job(4.0, False) is not None


def test_didier_seul_ne_declenche_rien():
    sched = ReflectionScheduler()
    sched.notify("poi", 0.0)
    sched.next_job(0.0, False)                  # un départ à t=0
    sched.notify("didier", 1.0)
    assert sched.next_job(5.0, False) is None   # intervalle OK, mais rien à traiter
    assert sched.next_job(19.9, False) is None
    # Revue adversariale du 23/10 (I4) : la ligne "didier" n'engage plus —
    # aucun battement, même après heartbeat_s.
    assert sched.next_job(20.0, False) is None
    assert sched.next_job(50.0, False) is None


def test_reflect_est_profond_et_prioritaire():
    sched = ReflectionScheduler()
    sched.notify("poi", 0.0)
    sched.next_job(0.0, False)
    sched.notify("david", 0.5)
    sched.notify("reflect", 0.6)
    # 0,1 s après le dernier départ, david en debounce : le profond part quand même.
    assert sched.next_job(0.7, False) == Job(deep=True, reason="reflect")
    # ...et consomme les événements en attente.
    assert sched.next_job(10.0, False) is None


def test_en_vol_attente_puis_une_seule_relance():
    sched = ReflectionScheduler()
    sched.notify("poi", 0.0)
    assert sched.next_job(0.0, False) is not None
    sched.notify("poi", 1.0)
    sched.notify("instruction", 2.0)
    sched.notify("person_appeared", 3.0)
    assert sched.next_job(5.0, True) is None            # en vol : jamais
    job = sched.next_job(6.0, False)
    assert job == Job(deep=False, reason="poi+person_appeared+instruction")
    assert sched.next_job(12.0, False) is None          # UNE relance, pas trois


def test_reflect_devance_un_ordinaire_en_vol():
    # 01/11 : la demande ne fait plus la queue derrière un ordinaire (4-9 s).
    sched = ReflectionScheduler()
    sched.notify("reflect", 0.0)
    assert sched.next_job(1.0, True, deep_in_flight=False) == Job(deep=True, reason="reflect")


def test_reflect_attend_la_fin_d_un_profond_en_vol():
    sched = ReflectionScheduler()
    sched.notify("reflect", 0.0)
    assert sched.next_job(1.0, True, deep_in_flight=True) is None
    assert sched.next_job(2.0, False) == Job(deep=True, reason="reflect")


def test_ordinaire_jamais_pendant_un_profond_en_vol():
    sched = ReflectionScheduler()
    sched.notify("poi", 0.0)
    assert sched.next_job(10.0, True, deep_in_flight=True) is None


def test_battement_seulement_si_engage():
    sched = ReflectionScheduler()
    assert sched.next_job(100.0, False) is None          # personne, rien dit
    # Revue adversariale du 23/10 (I4) : Didier qui parle seul n'engage pas.
    sched.notify("didier", 100.0)
    assert sched.next_job(100.0, False) is None
    assert sched.next_job(130.0, False) is None
    sched.notify("david", 130.0)                         # engagé par David
    assert sched.next_job(131.0, False) == Job(deep=False, reason="david")
    assert sched.next_job(150.9, False) is None
    assert sched.next_job(151.0, False) == Job(deep=False, reason="heartbeat")


def test_didier_seul_ne_reentretient_pas_l_engagement():
    # Revue adversariale du 23/10 (I4), scénario : une phrase de David puis
    # silence ; chaque battement fait parler Didier (ligne "didier"). Avant :
    # l'engagement se ré-armait sur ses propres lignes, battement éternel
    # (30 tours en 10 min). Maintenant : plus rien après engaged_window_s.
    sched = ReflectionScheduler()
    sched.notify("david", 0.0)
    jobs = []
    for i in range(2, 1201):                             # t = 1,0 … 600,0 s, pas 0,5
        t = i * 0.5
        job = sched.next_job(t, False)
        if job is not None:
            jobs.append((t, job.reason))
            sched.notify("didier", t + 0.2)              # Didier parle à chaque fois
    assert jobs == [(1.0, "david"), (21.0, "heartbeat"), (41.0, "heartbeat")]


def test_battement_s_arrete_quand_l_engagement_expire():
    sched = ReflectionScheduler()
    sched.notify("david", 0.0)
    sched.next_job(1.0, False)                           # départ sur david
    assert sched.next_job(21.0, False) is not None       # engagé (21 s < 60 s)
    assert sched.next_job(61.0, False) is None           # ligne vieille de 61 s
    assert sched.next_job(500.0, False) is None


def test_personne_vue_engage():
    sched = ReflectionScheduler()
    sched.person_seen(0.0)
    assert sched.next_job(0.0, False) == Job(deep=False, reason="heartbeat")
    sched.person_seen(79.0)
    assert sched.next_job(80.0, False) is not None
    assert sched.next_job(141.0, False) is None


def test_pas_de_battement_pendant_un_debounce_david():
    sched = ReflectionScheduler()
    sched.notify("poi", 0.0)
    sched.next_job(0.0, False)
    sched.notify("david", 20.0)
    assert sched.next_job(20.5, False) is None           # ni david (debounce) ni battement
    assert sched.next_job(21.0, False) == Job(deep=False, reason="david")


def test_evenement_inconnu_leve():
    with pytest.raises(ValueError):
        ReflectionScheduler().notify("n_importe_quoi", 0.0)


def test_parametres_personnalises():
    sched = ReflectionScheduler(min_interval_s=1.0, heartbeat_s=5.0, debounce_s=0.0,
                                engaged_window_s=10.0)
    sched.notify("david", 0.0)
    assert sched.next_job(0.0, False) is not None
    assert sched.next_job(5.0, False) is not None
    assert sched.next_job(11.0, False) is None


# -- SpontaneousPolicy ------------------------------------------------------

def _allow(**overrides):
    args = dict(result_parler=True, deep=False, chat_state="listening", now_s=100.0,
                last_transcript_s=90.0, last_spontaneous_s=80.0, moving=False)
    args.update(overrides)
    return SpontaneousPolicy().allow(**args)


def test_politique_cas_nominal():
    assert _allow() is True


def test_politique_parler_faux():
    assert _allow(result_parler=False) is False


@pytest.mark.parametrize("state", ["thinking", "speaking", "off", "", "Listening"])
def test_politique_etat_du_chat(state):
    assert _allow(chat_state=state) is False


def test_politique_silence_minimal():
    assert _allow(last_transcript_s=96.1) is False      # 3,9 s
    assert _allow(last_transcript_s=96.0) is True       # 4,0 s pile
    assert _allow(last_transcript_s=None) is True       # jamais rien dit


def test_politique_reponse_a_une_demande_toujours_envoyee():
    # Révisé le 23/10 (banc ROS) : la réponse à une demande de Didier part
    # même si le LLM dit parler=False, pendant que Didier parle encore, juste
    # après une réplique et juste après un tour spontané — le côté parole
    # choisit le moment (emplacement unique, TTL, silence).
    assert _allow(deep=True, result_parler=False, chat_state="speaking",
                  last_transcript_s=99.9, last_spontaneous_s=99.0, moving=True) is True
    assert _allow(deep=False, last_transcript_s=98.5) is False


def test_politique_ecart_entre_tours_spontanes():
    assert _allow(last_spontaneous_s=88.1) is False     # 11,9 s
    assert _allow(last_spontaneous_s=88.0) is True      # 12,0 s pile
    assert _allow(last_spontaneous_s=None) is True


def test_politique_pas_de_tour_ordinaire_en_marche():
    # Règle « micro à l'arrêt » du 23/10 (revue I2/M3), levée le 31/10 pour
    # la SEULE remarque sur un objet croisé (tests ci-dessous) : sans objet
    # déclencheur, toujours muet en marche.
    assert _allow(moving=True) is False
    assert _allow(moving=False) is True
    # Le profond (réponse à une demande) passe toujours, même en marche.
    assert _allow(moving=True, deep=True) is True


# Décision de David du 31/10 (dadou_robot_ros docs/etude-interaction.md
# §10.2 « En marche ») : une remarque courte par objet croisé, une seule.

def test_politique_en_marche_entree_poi_autorisee():
    assert _allow(moving=True, passing_poi="anneaux") is True


def test_politique_en_marche_battement_refuse():
    # Le battement (et tout déclencheur sans objet) n'apporte pas de POI.
    assert _allow(moving=True, passing_poi=None) is False


def test_politique_en_marche_une_seule_remarque_par_objet():
    policy = SpontaneousPolicy()
    args = dict(result_parler=True, deep=False, chat_state="listening", now_s=100.0,
                last_transcript_s=90.0, last_spontaneous_s=80.0, moving=True)
    assert policy.already_remarked("anneaux") is False
    assert policy.allow(**args, passing_poi="anneaux") is True
    assert policy.already_remarked("anneaux") is True
    assert policy.allow(**args, passing_poi="anneaux") is False     # 2e passage
    assert policy.allow(**args, passing_poi="lampadaire") is True   # autre objet
    policy.reset_remarks()                                          # route restart
    assert policy.allow(**args, passing_poi="anneaux") is True


def test_politique_en_marche_refus_ne_consomme_pas_l_objet():
    # Refusé pour une autre raison (Didier parle) : l'objet reste à commenter.
    policy = SpontaneousPolicy()
    args = dict(result_parler=True, deep=False, now_s=100.0, last_transcript_s=90.0,
                last_spontaneous_s=80.0, moving=True, passing_poi="anneaux")
    assert policy.allow(**args, chat_state="speaking") is False
    assert policy.already_remarked("anneaux") is False
    assert policy.allow(**args, chat_state="listening") is True


def test_politique_a_l_arret_inchange_et_sans_memoire():
    # À l'arrêt, l'objet ne change rien et n'est pas consommé : la mémoire
    # ne compte que les remarques EN MARCHE.
    policy = SpontaneousPolicy()
    args = dict(result_parler=True, deep=False, chat_state="listening", now_s=100.0,
                last_transcript_s=90.0, last_spontaneous_s=80.0, moving=False)
    assert policy.allow(**args, passing_poi=None) is True
    assert policy.allow(**args, passing_poi="anneaux") is True
    assert policy.already_remarked("anneaux") is False
    assert _allow(moving=False, chat_state="speaking", passing_poi="anneaux") is False


@pytest.mark.parametrize("state", ["thinking", "speaking", "off", ""])
def test_politique_en_marche_etat_du_chat(state):
    assert _allow(moving=True, passing_poi="anneaux", chat_state=state) is False


def test_politique_en_marche_garde_silence_et_ecart():
    assert _allow(moving=True, passing_poi="anneaux", last_transcript_s=96.1) is False
    assert _allow(moving=True, passing_poi="anneaux", last_spontaneous_s=88.1) is False
    assert _allow(moving=True, passing_poi="anneaux", result_parler=False) is False


# -- DeepRequests -----------------------------------------------------------

def test_demande_profonde_en_echec_reessayee_une_seule_fois():
    # Revue adversariale du 23/10 (I5) : un job profond en échec perdait la
    # demande alors que Didier avait promis de revenir avec la réponse.
    deep = DeepRequests()
    assert deep.take() == (None, False)
    deep.submit("que vois-tu ?")
    assert deep.take() == ("que vois-tu ?", False)
    assert deep.take() == (None, False)                  # consommée
    assert deep.failed("que vois-tu ?", was_retry=False) is True   # remise en attente
    assert deep.take() == ("que vois-tu ?", True)        # le nouvel essai
    assert deep.failed("que vois-tu ?", was_retry=True) is False   # abandon
    assert deep.take() == (None, False)


def test_demande_plus_recente_prime_sur_le_nouvel_essai():
    deep = DeepRequests()
    deep.submit("a")
    deep.take()
    deep.submit("b")                                     # arrivée pendant le vol de "a"
    assert deep.failed("a", was_retry=False) is False    # "a" abandonnée, "b" attend
    assert deep.take() == ("b", False)
    assert deep.failed(None, was_retry=False) is False   # job profond sans demande


# --- Flights : ordinaire devancé par une demande profonde (01/11) ---

def test_flights_ordinaire_devance_par_un_profond():
    from didier_vision.ai.reflection_policy import Flights
    f = Flights()
    ordinaire, profond = Job(deep=False, reason="david"), Job(deep=True, reason="reflect")
    t_ord = f.start(ordinaire)
    assert f.any and not f.deep
    t_deep = f.start(profond)                 # part PENDANT l'ordinaire
    assert f.deep
    assert f.superseded(profond, t_deep) is False
    f.finish(profond)
    f.finish(ordinaire)
    assert f.superseded(ordinaire, t_ord) is True      # jeté
    assert not f.any


def test_flights_ordinaire_seul_n_est_pas_devance():
    from didier_vision.ai.reflection_policy import Flights
    f = Flights()
    profond = Job(deep=True, reason="reflect")
    f.start(profond)
    f.finish(profond)
    ordinaire = Job(deep=False, reason="david")
    t_ord = f.start(ordinaire)                # profond fini AVANT son départ
    f.finish(ordinaire)
    assert f.superseded(ordinaire, t_ord) is False


def test_flights_refuse_les_doublons():
    import pytest
    from didier_vision.ai.reflection_policy import Flights
    f = Flights()
    f.start(Job(deep=True, reason="reflect"))
    with pytest.raises(ValueError):
        f.start(Job(deep=True, reason="reflect"))
    with pytest.raises(ValueError):
        f.start(Job(deep=False, reason="david"))
