"""Banc des modèles de la BOUCHE de Didier, dans SON contexte (01/11).

POURQUOI : les classements publics (artificialanalysis…) mesurent des tâches
longues à réflexion poussée — latences de 30 à 700 s. La bouche de Didier
doit : répondre en < 1 s au premier mot, 25 mots max, en français, dans le
personnage, et finir par le JSON qui pilote le corps (émotion + geste juste).
Seul un banc sur NOS prompts le dit.

MÊME CODE QUE LA PROD : prompt système composé par personas.compose_system_prompt
(move=True, partenaire David), ligne d'objets par personas.objects_prompt,
tableau de situation + REFLECT_TEMPLATE comme chat_node, requête et flux par
StreamingBrain, JSON lu par emotion_parser.extract_emotion_json, nombres par
conversation._gesture_number. Seul l'historique ChatDB est remplacé par une
liste en mémoire (ne pas polluer db/chat.db de la répétition).

Usage (dans le conteneur vision, workspace sourcé) :
    python3 tools/banc_bouche.py --objects /tmp/banc_objects.json --runs 2 \
        --out /tmp/banc_bouche.json [--models a,b,c]
Coût : ~14 scénarios × runs × modèles appels courts (quelques centimes).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time

from vision.ai import llm_stream, personas
from vision.ai.conversation import LOOK_WORDS, TURN_WORDS, _gesture_number
from vision.ai.emotion_parser import extract_emotion_json
from vision.ai.llm_stream import StreamingBrain
from vision.nodes.chat_node import LLM_API_KEY_NAME

BASE_URL = "https://openrouter.ai/api/v1"
MAX_TOKENS = 600  # large : on mesure aussi qui déborde, pas qui est coupé

# Candidats : (modèle OpenRouter, réglages de réflexion à essayer DANS
# L'ORDRE — le premier accepté par le fournisseur est gardé). Haiku/Sonnet :
# réglages de prod (cf. vision_config).
CANDIDATES = {
    "anthropic/claude-haiku-5.5": [{"reasoning": {"enabled": False}}],
    "anthropic/claude-sonnet-5.5": [{"reasoning": {"effort": "minimal"}}],
    "openai/gpt-6-luna": [{"reasoning": {"effort": "minimal"}}, {"reasoning": {"enabled": False}}, None],
    # Sol : ajouté à la demande de David (même tarif que Sonnet, score proche
    # au classement ; sa latence publique est mesurée en réflexion haute).
    "openai/gpt-6.1-sol": [{"reasoning": {"effort": "minimal"}}, {"reasoning": {"enabled": False}}, None],
    # Astra : demandé par David (01/11) — 5× le prix de Sonnet PAR JETON ;
    # le « coût par tâche » du classement reflète leurs jetons, pas les nôtres.
    "openai/gpt-6-astra": [{"reasoning": {"effort": "minimal"}}, {"reasoning": {"enabled": False}}, None],
    "openai/gpt-6.1-terra": [{"reasoning": {"effort": "minimal"}}, {"reasoning": {"enabled": False}}, None],
    "google/gemini-3.8-flash": [{"reasoning": {"enabled": False}}, {"reasoning": {"effort": "minimal"}}, None],
    "google/gemini-3.5-flash-lite": [{"reasoning": {"enabled": False}}, {"reasoning": {"effort": "minimal"}}, None],
    "mistralai/mistral-medium-3-5": [None],
    "mistralai/mistral-small-2603": [None],
    "x-ai/grok-4.7": [{"reasoning": {"enabled": False}}, {"reasoning": {"effort": "minimal"}}, None],
    "deepseek/deepseek-v4.1-flash": [{"reasoning": {"enabled": False}}, None],
}

SITUATION = ("Didier est arrêté sur le quai, David à côté de lui ; rue calme, "
             "quelques passants au loin.")

# (phrase de David, attendu). Attendu = fonction(params) -> bool sur le JSON.
# Phrases réelles des séances du 31/10-01/11 ou très proches.
def _turn(params, pred):
    a = _gesture_number(params.get("tourner"), TURN_WORDS) if "tourner" in params else None
    return a is not None and pred(a)


def _no_move(params):
    return not any(k in params for k in ("marche", "aller_voir", "tourner", "avancer"))


SCENARIOS = [
    ("Regarde à droite, qu'est-ce qu'il y a ?", "tourner<0",
     lambda p: _turn(p, lambda a: a < 0)),
    ("Tourne-toi.", "tourner",
     lambda p: _turn(p, lambda a: abs(a) >= 45)),
    ("Allez, avance un peu.", "avancer ≤2 m",
     lambda p: (m := _gesture_number(p.get("avancer"))) is not None and 0 < m <= 2),
    ("Va voir les anneaux.", "aller_voir anneaux",
     lambda p: str(p.get("aller_voir", "")).strip().lower() == "anneaux"),
    ("Stop, arrête-toi !", "marche stop",
     lambda p: str(p.get("marche", "")).strip().lower() == "stop"),
    ("Allez, on repart.", "marche go",
     lambda p: str(p.get("marche", "")).strip().lower() == "go"),
    ("C'est quoi ce panneau à droite ?", "tourner<0 ou reflechir",
     lambda p: _turn(p, lambda a: a < 0) or bool(p.get("reflechir"))),
    ("Fais demi-tour.", "tourner ±180",
     lambda p: _turn(p, lambda a: abs(a) >= 150)),
    ("Regarde-moi quand je te parle.", "regarder",
     lambda p: "regarder" in p and _gesture_number(p["regarder"], LOOK_WORDS) is not None),
    ("Recule un peu.", "aucun geste (il ne recule pas)", _no_move),
    ("Fais le tour de la flaque.", "un geste (aller_voir/tourner/avancer)",
     lambda p: any(k in p for k in ("aller_voir", "tourner", "avancer"))),
    ("Tu cherches quoi, au juste ?", "aucun geste", _no_move),
    ("Attention, on ne va pas dans la Loire non plus.", "aucun geste", _no_move),
    ("Un peu plus à gauche.", "tourner>0 ou regarder>0",
     lambda p: _turn(p, lambda a: a > 0)
     or ("regarder" in p and (_gesture_number(p["regarder"], LOOK_WORDS) or 0) > 0)),
]

_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_DIDASCALIE = re.compile(r"\*[^*]*\*")


# Image jointe au tour (piste « la bouche lit l'image au fur et à mesure »,
# David 01/11) : JPEG base64 posé ici avant un tour, None = texte seul. Passe
# par l'historique pour réutiliser la requête de StreamingBrain telle quelle.
_IMAGE_B64 = None

# Questions sur une image Gazebo connue (vue1.jpg : panneau violet à cadre
# vert devant, grue jaune à gauche, eau à droite, quai gris ; PERSONNE, ni
# lampadaire ni anneaux). `doit` : au moins un mot attendu ; les inventions
# se jugent à la relecture (une négation « je ne vois personne » est juste).
IMAGE_SCENARIOS = [
    ("Qu'est-ce que tu vois devant toi ?", ("panneau", "violet", "pancarte", "affiche")),
    ("Il y a quelqu'un par ici ?", ("personne", "pas âme", "seul", "vide")),
    ("C'est quoi le truc jaune à gauche ?", ("grue", "échafaud", "structure", "métal", "portique", "tour")),
    ("Tu vois les anneaux d'ici ?", ("non", "pas", "nulle")),
]


class _MemoryHistory:
    """Remplace ChatDB : même interface, rien sur disque."""

    def __init__(self):
        self._items = []

    def add_user_text(self, text):
        if _IMAGE_B64 is not None:
            self._items.append({"role": "user", "content": [
                {"type": "text", "text": text},
                {"type": "image_url",
                 "image_url": {"url": "data:image/jpeg;base64," + _IMAGE_B64}}]})
            return
        self._items.append({"role": "user", "content": text})

    def add_assistant_text(self, text):
        self._items.append({"role": "assistant", "content": text})

    def get_history(self):
        return list(self._items)


class _MemoryChatDB:
    @staticmethod
    def create(_):
        return _MemoryHistory()


# Consigne CANDIDATE pour une bouche qui voit (pas encore en prod) : sans
# elle, REFLECT_TEMPLATE dit « ce que tu vois -> délègue », et les modèles
# obéissants (Sol, Terra) répondent « je regarde » au lieu de décrire
# l'image pourtant jointe (banc du 01/11) — on mesurerait l'obéissance.
IMAGE_RULE = """
Tes yeux : l'image jointe au dernier message de David est ce que ta caméra voit À CET INSTANT, droit devant toi. Quand on te demande ce que tu vois, réponds d'après elle, tout de suite, sans déléguer : ne cite RIEN qui n'y est pas (ni personne, ni objet), et si ce qu'on te demande n'y est pas, dis-le. Ce qui est hors de l'image (derrière toi, sur les côtés), tu ne le vois pas.
"""
_SUFFIX = personas.REFLECT_TEMPLATE


def _brain(model, extra_body, objects):
    brain = StreamingBrain(
        model=model, base_url=BASE_URL, api_key_name=LLM_API_KEY_NAME,
        system_prompt=personas.compose_system_prompt("bougon", "David", move=True),
        max_tokens=MAX_TOKENS, extra_body=extra_body,
        situation_suffix=_SUFFIX)
    brain.set_objects_prompt(personas.objects_prompt(objects))
    return brain


def _one(model, extra_body, objects, phrase):
    brain = _brain(model, extra_body, objects)
    t0 = time.monotonic()
    first = None
    text = ""
    for delta in brain.stream_reply(phrase, situation=SITUATION):
        if first is None and delta.strip():
            first = time.monotonic() - t0
        text += delta
    return first, time.monotonic() - t0, text


def _pick_setting(model, objects):
    """Premier réglage de réflexion accepté (une réplique test)."""
    last = None
    for extra in CANDIDATES[model]:
        try:
            _one(model, extra, objects, "Bonjour Didier.")
            return extra, None
        except Exception as exc:  # noqa: BLE001 - on note et on essaie le suivant
            last = str(exc)[:200]
    return "ÉCHEC", last


def _score(text, check):
    spoken, params = extract_emotion_json(text)
    params = params or {}
    spoken_clean = _DIDASCALIE.sub("", spoken or "").strip()
    words = len(spoken_clean.split())
    return {
        "json_ok": bool(params) and "emotion" in params,
        "geste_ok": bool(params) and check(params),
        "mots": words,
        "court": words <= 25,
        "emoji": bool(_EMOJI.search(text)),
        "params": params,
        "dit": spoken_clean,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objects", required=True)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--out", default="/tmp/banc_bouche.json")
    ap.add_argument("--models", default=",".join(CANDIDATES))
    ap.add_argument("--image", help="JPEG : passe aux questions sur image (IMAGE_SCENARIOS)")
    ap.add_argument("--suite", action="store_true",
                    help="conversation CONTINUE (historique gardé) : mesure des tics répétés")
    args = ap.parse_args()
    if args.suite:
        return _main_suite(args)
    if args.image:
        return _main_image(args)
    llm_stream.ChatDB = _MemoryChatDB  # historique en mémoire (cf. docstring)
    objects = [(o["name"], o["desc"]) for o in json.load(open(args.objects))]

    results = {}
    for model in args.models.split(","):
        setting, err = _pick_setting(model, objects)
        rows = []
        if setting != "ÉCHEC":
            for phrase, attendu, check in SCENARIOS:
                for _ in range(args.runs):
                    try:
                        first, total, text = _one(model, setting, objects, phrase)
                        row = {"phrase": phrase, "attendu": attendu, "ttft": first,
                               "total": total, **_score(text, check)}
                    except Exception as exc:  # noqa: BLE001
                        row = {"phrase": phrase, "attendu": attendu, "erreur": str(exc)[:200]}
                    rows.append(row)
        results[model] = {"reglage": setting, "erreur": err, "tours": rows}
        ok = [r for r in rows if "erreur" not in r]
        if ok:
            ttfts = [r["ttft"] for r in ok if r["ttft"] is not None]
            print(f"{model:32s} réglage={json.dumps(setting)} "
                  f"1er mot méd={statistics.median(ttfts):.2f}s max={max(ttfts):.2f}s "
                  f"geste={sum(r['geste_ok'] for r in ok)}/{len(ok)} "
                  f"json={sum(r['json_ok'] for r in ok)}/{len(ok)} "
                  f"court={sum(r['court'] for r in ok)}/{len(ok)} "
                  f"erreurs={len(rows) - len(ok)}", flush=True)
        else:
            print(f"{model:32s} INUTILISABLE : {err}", flush=True)
        json.dump(results, open(args.out, "w"), ensure_ascii=False, indent=1)


# Tics surveillés (personas.py, règle des tics : ≤ 1 réplique sur 5).
TICS = ("bon sang de boulon", "contre tout", "de mon temps")


def _main_suite(args):
    """Les SCENARIOS enchaînés dans UNE conversation (historique gardé, comme
    en séance), `runs` fois : part des répliques avec un tic, et nombre de
    paires de répliques CONSÉCUTIVES qui en portent un (« jamais deux de
    suite »)."""
    llm_stream.ChatDB = _MemoryChatDB
    objects = [(o["name"], o["desc"]) for o in json.load(open(args.objects))]
    results = {}
    for model in args.models.split(","):
        setting, err = _pick_setting(model, objects)
        if setting == "ÉCHEC":
            print(f"{model:32s} SUITE INUTILISABLE : {err}", flush=True)
            continue
        lines, ttfts = [], []
        for _ in range(args.runs):
            brain = _brain(model, setting, objects)
            tics = []
            for phrase, _attendu, _check in SCENARIOS:
                t0 = time.monotonic()
                first, text = None, ""
                for delta in brain.stream_reply(phrase, situation=SITUATION):
                    if first is None and delta.strip():
                        first = time.monotonic() - t0
                    text += delta
                ttfts.append(first)
                spoken = _DIDASCALIE.sub("", extract_emotion_json(text)[0] or "").strip()
                tics.append(any(t in spoken.lower() for t in TICS))
                lines.append(spoken)
            results.setdefault(model, []).append(tics)
        flat = [t for run in results[model] for t in run]
        pairs = sum(a and b for run in results[model] for a, b in zip(run, run[1:]))
        print(f"{model:32s} SUITE tics={sum(flat)}/{len(flat)} ({100 * sum(flat) // len(flat)} %) "
              f"deux-de-suite={pairs} 1er mot méd={statistics.median(ttfts):.2f}s", flush=True)
        json.dump({"tics": results, "dernieres": lines}, open(args.out, "w"),
                  ensure_ascii=False, indent=1)


def _main_image(args):
    """Questions sur image : temps au premier mot AVEC l'image jointe, mot
    attendu présent, réplique gardée pour relecture (inventions)."""
    import base64
    global _IMAGE_B64, _SUFFIX
    llm_stream.ChatDB = _MemoryChatDB
    _SUFFIX = personas.REFLECT_TEMPLATE + IMAGE_RULE
    objects = [(o["name"], o["desc"]) for o in json.load(open(args.objects))]
    results = {}
    for model in args.models.split(","):
        _IMAGE_B64 = None   # réglage choisi sur une réplique texte (cf. _pick_setting)
        setting, err = _pick_setting(model, objects)
        _IMAGE_B64 = base64.b64encode(open(args.image, "rb").read()).decode()
        rows = []
        if setting == "ÉCHEC":
            print(f"{model:32s} IMAGE INUTILISABLE : {err}", flush=True)
            continue
        for phrase, doit in IMAGE_SCENARIOS:
            for _ in range(args.runs):
                try:
                    first, total, text = _one(model, setting, objects, phrase)
                    spoken, _params = extract_emotion_json(text)
                    spoken = _DIDASCALIE.sub("", spoken or "").strip()
                    rows.append({"phrase": phrase, "ttft": first, "total": total,
                                 "attendu_ok": any(w in spoken.lower() for w in doit),
                                 "dit": spoken})
                except Exception as exc:  # noqa: BLE001
                    rows.append({"phrase": phrase, "erreur": str(exc)[:200]})
        results[model] = rows
        ok = [r for r in rows if "erreur" not in r]
        if ok:
            ttfts = [r["ttft"] for r in ok if r["ttft"] is not None]
            print(f"{model:32s} IMAGE 1er mot méd={statistics.median(ttfts):.2f}s "
                  f"max={max(ttfts):.2f}s attendu={sum(r['attendu_ok'] for r in ok)}/{len(ok)} "
                  f"erreurs={len(rows) - len(ok)}", flush=True)
        else:
            print(f"{model:32s} IMAGE INUTILISABLE : {rows[0].get('erreur')}", flush=True)
        json.dump(results, open(args.out, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
