"""v3 entry point: query -> parse -> filter -> (relax) -> score -> diversify -> explain.

recommend() returns the same card keys as the /predict response of the kb path (so the existing front end
keeps working) plus: engine, weights, per-car scores / reasons / unknowns / violations / match_label, and a
top-level `relaxation` when the filter returned nothing and a named relaxation was used.
Everything is JSON-serialisable (NaN -> None). No network and no LLM unless env LLM_PARSER=on (services/recsys/llm_parse.py).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from services.catalogue import get_catalogue, get_meta
from services.filter_v2 import FEATURE_COLUMNS, MIN_COLUMNS, filter_candidates
from services.images import find_car_image, image_attribution
from services.intent_v2 import parse_intent_ex
from services.recsys import config, llm_parse
from services.recsys.common import is_unknown, num, to_jsonable
from services.recsys.criteria import catalogue_reference
from services.recsys.diversify import diversify
from services.recsys.evidence import Evidence, get_evidence
from services.recsys.explain import explain
from services.recsys.relax import find_relaxation, violations_for
from services.recsys.score import score_candidates
from services.recsys.weights import build_weights

APP_ROOT = Path(__file__).resolve().parents[2]
UNRATED_SAFETY_LABEL = "No Bharat NCAP rating on record"
TRANSMISSION_LABELS = {
    "manual": "Manual", "imt": "Manual (iMT, clutchless)", "amt": "Automatic (AMT)", "dct": "Automatic (DCT)",
    "cvt": "Automatic (CVT)", "e_cvt": "Automatic (e-CVT)", "torque_converter": "Automatic (torque converter)",
    "single_speed_ev": "Automatic (single-speed EV)",
}
SCORE_DECIMALS = 4


def _slug(value: Any) -> str:
    return "unknown" if is_unknown(value) else str(value).lower().replace(" ", "-")


def _cardekho(make, model):
    return f"https://www.cardekho.com/{_slug(make)}/{_slug(model)}"


def _carwale(make, model):
    return f"https://www.carwale.com/{_slug(make)}-cars/{_slug(model)}"


def _num_or_none(value, whole=False):
    v = num(value)
    if v is None:
        return None
    return int(v) if whole else float(v)


def _safety_summary(car) -> Optional[dict]:
    if is_unknown(car["safety_stars_adult"]):
        return None
    return {
        "stars_adult": int(car["safety_stars_adult"]),
        "stars_child": None if is_unknown(car["safety_stars_child"]) else int(car["safety_stars_child"]),
        "testing_body": car["safety_testing_body"],
        "year": None if is_unknown(car["safety_test_year"]) else int(car["safety_test_year"]),
    }


# ---------------------------------------------------------------- dropping constraints ("drop" argument)

def _drop_table(intent: dict) -> List[Tuple[str, str, dict]]:
    """(key, label, intent without that constraint) for every active constraint; same keys as /predict `drop`."""
    def without(**changes):
        new = copy.deepcopy(intent)
        new.update(changes)
        return new

    rows: List[Tuple[str, str, dict]] = []
    b = intent.get("budget") or {}
    if b.get("min") is not None or b.get("max") is not None:
        rows.append(("budget", "budget", without(budget={"min": None, "max": None})))
    if intent.get("body_types"):
        rows.append(("body_type", "body type", without(body_types=[])))
    if intent.get("exclude_body_types"):
        rows.append(("exclude_body_type", "excluded body type", without(exclude_body_types=[])))
    if intent.get("fuel_types"):
        rows.append(("fuel", "fuel type", without(fuel_types=[])))
    if intent.get("exclude_fuel_types"):
        rows.append(("exclude_fuel", "excluded fuel", without(exclude_fuel_types=[])))
    t = intent.get("transmission") or {}
    if t.get("family") or t.get("include_types") or t.get("exclude_types"):
        rows.append(("transmission", "transmission", without(transmission={"family": None, "include_types": [],
                                                                         "exclude_types": []})))
    if intent.get("seats_min") is not None:
        rows.append(("seats", f"{intent['seats_min']}+ seats", without(seats_min=None)))
    if intent.get("makes"):
        rows.append(("makes", " / ".join(intent["makes"]), without(makes=[])))
    if intent.get("models"):
        rows.append(("models", " / ".join(intent["models"]), without(models=[])))
    if intent.get("reference_models"):
        rows.append(("like_model", "similar to " + ", ".join(intent["reference_models"]), without(reference_models=[])))
    for f in intent.get("required_features") or []:
        rows.append((f"feature:{f}", FEATURE_COLUMNS[f][1],
                     without(required_features=[x for x in intent["required_features"] if x != f])))
    for key, (_, label) in MIN_COLUMNS.items():
        if intent.get(key) is not None:
            rows.append((key, f"minimum {label}", without(**{key: None})))
    if intent.get("min_safety_stars") is not None:
        rows.append(("min_safety_stars", "safety-star minimum", without(min_safety_stars=None)))
    for kind in ("body_types", "fuel_types"):  # ML guesses ("assumed: SUV"): the UI's off switch
        guess = (intent.get("assumed") or {}).get(kind)
        if guess:
            rest = {k: v for k, v in intent["assumed"].items() if k != kind}
            rows.append((f"assumed:{kind}", f"assumed {kind.replace('_types', '')} {'/'.join(guess)}",
                         without(assumed={**rest, kind: []})))
    return rows


def apply_drops(intent: dict, drop_keys) -> Tuple[dict, List[dict]]:
    if isinstance(drop_keys, str):
        drop_keys = [drop_keys]
    dropped = []
    for key in dict.fromkeys(drop_keys or []):
        match = next(((label, new) for k, label, new in _drop_table(intent) if k == key), None)
        if match:
            intent = match[1]
            dropped.append({"key": key, "label": match[0]})
    return intent, dropped


# ---------------------------------------------------------------- response pieces

def unsupported_only_message(terms: List[str], covered_makes: List[str]) -> str:
    """Same wording as the current kb path (services.new_car_service.get_kb_recommendations)."""
    return (", ".join(terms) + " isn't in our catalogue, so there is nothing to recommend for it. "
            "Tell us a budget, body type or fuel and we will search the brands we cover: "
            + ", ".join(covered_makes) + ".")


VAGUE_MESSAGE = ("Your query didn't say what you are looking for, so this is a general shortlist, not personalised. "
                 "Tell us a budget and what the car is for (family, city, highway, first car...) to narrow it down.")
VAGUE_LABEL = "General pick, not personalised"


def _assumed_matches(cands: pd.DataFrame, assumed: dict) -> Dict[Any, List[str]]:
    """{row index: ["body suv", ...]} for rows matching an ML-assumed body type / fuel."""
    checks = [(f"{kind.replace('_types', '')} {v}", col, v)
              for kind, col in (("body_types", "body_type"), ("fuel_types", "fuel_type"))
              for v in (assumed or {}).get(kind) or []]
    return {idx: [name for name, col, v in checks if row[col] == v] for idx, row in cands.iterrows()}


def _filters_summary(intent: dict) -> dict:
    keys = ["budget", "body_types", "fuel_types", "transmission", "seats_min", "makes", "models",
            "required_features", "exclude_body_types", "exclude_fuel_types"]
    return {k: intent.get(k) for k in keys if intent.get(k) not in (None, [], {})}


def _weights_payload(weights: dict) -> dict:
    return {c: {"weight": round(v["weight"], 6), "label": v["label"], "class": v["class"],
                "active": v["active"], "multiplier": v["multiplier"], "why": v["why"]}
            for c, v in weights["criteria"].items()}


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None or is_unknown(value) else round(float(value), SCORE_DECIMALS)


def _card(car: pd.Series, srow: pd.Series, ex: dict, variant_counts: pd.Series, app_root: str,
          violations: List[dict]) -> dict:
    unverified = list(car["unverified"]) if "unverified" in car.index and isinstance(car["unverified"], list) else []
    if "unrated_safety" in car.index and car["unrated_safety"]:
        unverified.append(UNRATED_SAFETY_LABEL)
    overall = None if is_unknown(srow["overall"]) else float(srow["overall"])
    return {
        # keys shared with the current /predict card
        "Make": car["make"], "Model": car["model"], "Variant": car["variant"],
        "Ex-Showroom_Price": _num_or_none(car["price_ex_showroom"]),
        "Displacement": _num_or_none(car["engine_cc"]), "Power": _num_or_none(car["power_bhp"]),
        "ARAI_Certified_Mileage": _num_or_none(car["mileage_kmpl"]),
        "Transmission": None if is_unknown(car["transmission_family"]) else str(car["transmission_family"]).title(),
        "Fuel_Type": car["fuel_raw"],
        "carImage": find_car_image(app_root, car["make"], car["model"], car["body_type"]),
        "carDekhoLink": _cardekho(car["make"], car["model"]),
        "carWaleLink": _carwale(car["make"], car["model"]),
        "ranking_score": None if overall is None else round(overall * 100, 2),
        "match_reasons": [r["text"] for r in ex["reasons"]],
        "transmission_type": car["transmission_type"],
        "transmission_label": TRANSMISSION_LABELS.get(car["transmission_type"]),
        "matched_features": [item.split(":", 1)[1] for item, s in srow["required"].items()
                             if s == "met" and item.startswith("feature:")],
        "unverified": unverified,
        "safety": _safety_summary(car),
        "imageAttribution": image_attribution(app_root, car["make"], car["model"]),
        "matching_variant_count": int(variant_counts[car["model"]]),
        "mileage_km_per_kg": _num_or_none(car["mileage_km_per_kg"]),
        "ev_range_km": _num_or_none(car["ev_range_km"], whole=True),
        "power_bhp": _num_or_none(car["power_bhp"]),
        "airbags": _num_or_none(car["airbags"], whole=True),
        "boot_space_litres": _num_or_none(car["boot_space_litres"], whole=True),
        # v3 additions
        "variant_id": int(car["variant_id"]),
        "selection_order": int(car["selection_order"]) if "selection_order" in car.index else None,
        "scores": {"overall": _round(overall), "spec": _round(srow["spec"]), "expert": _round(srow["expert"]),
                   "owner": _round(srow["owner"]), "coverage": _round(srow["coverage"])},
        "class_weights": {c: _round(v) for c, v in srow["class_weights"].items()},
        "criteria": {c: _round(v) for c, v in srow["values"].items() if v is not None},
        "reasons": ex["reasons"],
        "unknowns": ex["unknowns"],
        "violations": violations,
        "match_label": ex["match_label"],
        "flags": list(srow["flags"]),
        # requested features this variant is not known to have (named so the user sees what the cheapest fit lacks)
        "missing_features": [item.split(":", 1)[1] for item, st in srow["required"].items()
                             if item.startswith("feature:") and st != "met"],
    }


def recommend(query: str, drop=None, weight_overrides: Optional[Dict[str, Any]] = None,
              app_root_path: Optional[str] = None, evidence: Optional[Evidence] = None,
              catalogue: Optional[pd.DataFrame] = None, intent: Optional[dict] = None) -> dict:
    """The whole v3 pipeline for one query. `intent` may be supplied to skip parsing (tests, other callers)."""
    df = catalogue if catalogue is not None else get_catalogue()
    ev = evidence if evidence is not None else get_evidence()
    app_root = str(app_root_path or APP_ROOT)
    meta = get_meta()

    if intent is not None:
        parsed, llm_info = intent, {"used": False, "accepted": [], "rejected": 0, "latency_ms": None,
                                    "reason": "intent_supplied", "cached": False}
    else:
        parsed, residual = parse_intent_ex(query)
        # optional LLM parser (env LLM_PARSER=on): only adds evidence-quoted constraints for what the rules left unexplained
        parsed, llm_info = llm_parse.refine(query, parsed, residual)
    intent, dropped = apply_drops(parsed, drop)

    response: Dict[str, Any] = {
        "engine": "v3",
        "parser_used": "intent_v2",
        "intent": intent,
        "filters": _filters_summary(intent),
        "recommendations": [],
        "data_as_of": {"exported": meta["export_utc"][:10], "kb_phase": meta["kb_latest_phase"]},
        "unsupported_terms": intent.get("unsupported_terms", []),
        "llm": {k: v for k, v in llm_info.items() if k != "rejected_detail"},
        "corrections": list(intent.get("corrections") or []),  # typos read as vocabulary words ("automtic" -> "automatic")
        "covered_makes": sorted(df["make"].unique().tolist()),
    }
    assumed = {k: v for k, v in (intent.get("assumed") or {}).items() if v} if isinstance(intent.get("assumed"), dict) else {}
    vague = bool(intent.get("vague"))
    if assumed:
        # soft only: a bounded boost (config.ASSUMED_BOOST on the 0-1 overall score) to cars that match; never a filter.
        # `assumed_options` carries the drop key that switches each guess off (same `drop` argument as constraints).
        response["assumed"] = assumed
        response["assumed_boost"] = config.ASSUMED_BOOST
        response["assumed_options"] = [{"key": f"assumed:{k}", "kind": k, "values": v} for k, v in assumed.items()]
    if drop is not None:
        response["dropped"] = dropped

    unsupported_note = ""
    if intent.get("unsupported_terms"):
        unsupported_note = (", ".join(intent["unsupported_terms"])
                            + " isn't in our catalogue, so that part of your query was ignored.")

    if intent.get("unsupported_only"):
        # the whole query is about a brand we don't carry: say so and stop, don't rank something unrelated
        response["message"] = unsupported_only_message(intent.get("unsupported_terms") or [], response["covered_makes"])
        response["weights"] = _weights_payload(build_weights(intent, weight_overrides))
        return to_jsonable(response)

    response["vague"] = vague
    cands = filter_candidates(intent, df)
    relaxation = None
    relaxed_keys: List[str] = []
    if cands.empty:
        relaxation = find_relaxation(intent, df)
        if relaxation is None:
            response["message"] = " ".join(filter(None, [unsupported_note, "No cars match all your requirements."]))
            response["relaxation_hints"] = []
            response["weights"] = _weights_payload(build_weights(intent, weight_overrides))
            return to_jsonable(response)
        cands = relaxation["candidates"]
        relaxed_keys = relaxation["keys"]

    # vague query: neutral default weights, no overrides, no assumed boost: the list is explicitly not personalised
    weights = build_weights({} if vague else intent, None if vague else weight_overrides)
    # scored against the ORIGINAL intent: a relaxed car's overshoot / missing feature stays visible to the score
    table, _ = score_candidates(cands, intent, weights, ev, budget=intent.get("budget"),
                                reference=catalogue_reference(df))
    matches = _assumed_matches(cands, {} if vague else assumed)
    if any(matches.values()):
        table["overall"] = [None if is_unknown(o) else min(1.0, float(o) + config.ASSUMED_BOOST * bool(matches[i]))
                            for i, o in table["overall"].items()]
    scored = cands.join(table)
    scored["assumed_match"] = pd.Series({i: bool(m) for i, m in matches.items()}).reindex(scored.index).fillna(False)
    variant_counts = cands["model"].value_counts()
    chosen = diversify(scored, intent)

    cards = []
    for car in chosen:
        srow = table.loc[car.name]
        ex = explain(car, srow, weights, intent, ev, relaxed=bool(relaxation))
        viol = violations_for(car, intent, relaxed_keys) if relaxation else []
        card = _card(car, srow, ex, variant_counts, app_root, viol)
        card["assumed_match"] = matches.get(car.name, [])
        if vague:
            card["match_label"] = VAGUE_LABEL
            card["personalised"] = False
        cards.append(card)

    response["recommendations"] = cards
    response["weights"] = _weights_payload(weights)
    response["weights_profile"] = {"profile": weights["profile"], "drivers": weights["drivers"]}
    response["classes"] = dict(config.CLASS_WEIGHTS)
    if vague:
        response["personalised"] = False
        response["shortlist_label"] = VAGUE_LABEL
        response["message"] = " ".join(filter(None, [unsupported_note, VAGUE_MESSAGE]))
    if relaxation:
        response["relaxation"] = {"moves": relaxation["moves"], "keys": relaxed_keys, "far": relaxation["far"],
                                  "seats_relaxed": relaxation["seats_relaxed"], "message": relaxation["message"]}
        response["message"] = " ".join(filter(None, [unsupported_note, relaxation["message"]]))
    elif unsupported_note:
        response["message"] = unsupported_note + " Showing the closest matches."
    return to_jsonable(response)
