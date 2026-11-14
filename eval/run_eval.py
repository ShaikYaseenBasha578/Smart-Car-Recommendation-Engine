#!/usr/bin/env python3
"""Evaluation runner for the car recommendation engine. See eval/README.md.

    .venv/bin/python eval/run_eval.py [--engine current|v3] [--out eval/results/<name>.json]
    .venv/bin/python eval/run_eval.py --check-labels     # label sanity check, no engine run

No network, no LLM. The engine is called in-process.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_SOURCE", "kb")

import pandas as pd  # noqa: E402

from services.catalogue import get_catalogue  # noqa: E402

QUERIES_PATH = ROOT / "eval" / "queries.jsonl"
AROUND_TOLERANCE = 0.20  # "around 10 lakh" is checked as 8 to 12 lakh

FEATURE_COLUMNS = {
    "sunroof": "sunroof", "adas": "adas_available", "camera_360": "camera_360",
    "ventilated_seats": "ventilated_front_seats", "cruise_control": "cruise_control",
    "wireless_charging": "wireless_charging", "heads_up_display": "heads_up_display",
    "android_auto": "android_auto", "apple_carplay": "apple_carplay",
}
NUMERIC_COLUMNS = ["airbags", "safety_stars_adult", "ev_range_km", "ground_clearance_mm",
                   "boot_space_litres", "mileage_kmpl", "mileage_km_per_kg"]
# a CNG row's mileage_kmpl cell holds a km/kg figure (see services/ranking_adapter.py): unknown as kmpl
KMPL_UNTRUSTED_FUELS = {"cng"}

PARSE_FIELDS = [
    "budget_min", "budget_max", "fuel_include", "fuel_exclude", "body_include", "body_exclude",
    "transmission_family", "transmission_include", "transmission_exclude", "seats_min",
    "required_features", "excluded_features", "makes_include", "makes_exclude", "models_include",
    "reference_models", "numeric_min", "numeric_max", "unsupported_brand",
]


def load_queries() -> list[dict]:
    with QUERIES_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _nan(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


# ---------------------------------------------------------------------------
# a. Constraint checking against the catalogue (independent of the parser)
# ---------------------------------------------------------------------------

def violations(row, expect: dict) -> list[str]:
    """Hard constraints in `expect` that catalogue row `row` breaks. Unknown values never violate."""
    out = []
    price = row["price_ex_showroom"]
    if expect.get("budget_min") is not None and not _nan(price) and price < expect["budget_min"]:
        out.append(f"budget_min {expect['budget_min']}")
    if expect.get("budget_max") is not None and not _nan(price) and price > expect["budget_max"]:
        out.append(f"budget_max {expect['budget_max']}")
    if expect.get("budget_around") is not None and not _nan(price):
        v = expect["budget_around"]
        if not (v * (1 - AROUND_TOLERANCE) <= price <= v * (1 + AROUND_TOLERANCE)):
            out.append(f"budget_around {v}")
    if expect.get("fuel_include") and row["fuel_type"] not in expect["fuel_include"]:
        out.append(f"fuel_include {expect['fuel_include']}")
    if row["fuel_type"] in (expect.get("fuel_exclude") or []):
        out.append(f"fuel_exclude {row['fuel_type']}")
    if expect.get("body_include") and row["body_type"] not in expect["body_include"]:
        out.append(f"body_include {expect['body_include']}")
    if row["body_type"] in (expect.get("body_exclude") or []):
        out.append(f"body_exclude {row['body_type']}")
    if expect.get("transmission_family") and row["transmission_family"] != expect["transmission_family"]:
        out.append(f"transmission_family {expect['transmission_family']}")
    if expect.get("transmission_include") and row["transmission_type"] not in expect["transmission_include"]:
        out.append(f"transmission_include {expect['transmission_include']}")
    if row["transmission_type"] in (expect.get("transmission_exclude") or []):
        out.append(f"transmission_exclude {row['transmission_type']}")
    if expect.get("seats_min") is not None and not _nan(row["seats"]) and row["seats"] < expect["seats_min"]:
        out.append(f"seats_min {expect['seats_min']}")

    unverified = row["unverified_fields"]
    for feature in expect.get("required_features") or []:
        col = FEATURE_COLUMNS[feature]
        if row[col] is False and col not in unverified:
            out.append(f"required_feature {feature} (known absent)")
    for feature in expect.get("excluded_features") or []:
        col = FEATURE_COLUMNS[feature]
        if row[col] is True and col not in unverified:
            out.append(f"excluded_feature {feature} (known present)")

    makes, models = expect.get("makes_include") or [], expect.get("models_include") or []
    if makes or models:
        model_makes = set(get_catalogue().loc[get_catalogue()["model"].isin(models), "make"])
        free_makes = [m for m in makes if m not in model_makes]
        if not (row["model"] in models or row["make"] in free_makes):
            out.append(f"make/model include {makes + models}")
    if row["make"] in (expect.get("makes_exclude") or []):
        out.append(f"makes_exclude {row['make']}")
    if row["model"] in (expect.get("reference_models") or []):
        out.append(f"reference model {row['model']} returned")

    for bound, sign in (("numeric_min", 1), ("numeric_max", -1)):
        for col, limit in (expect.get(bound) or {}).items():
            value = row[col]
            if col == "mileage_kmpl" and row["fuel_type"] in KMPL_UNTRUSTED_FUELS:
                continue
            if _nan(value):
                continue
            if (value - limit) * sign < 0:
                out.append(f"{bound} {col} {limit} (has {value:g})")
    return out


def matching_rows(expect: dict) -> int:
    cat = get_catalogue()
    return sum(1 for _, row in cat.iterrows() if not violations(row, expect))


def check_labels(queries) -> int:
    """Label sanity: expect_empty queries match no catalogue row; every other constrained query matches some."""
    bad = 0
    for q in queries:
        e = q["expect"]
        n = matching_rows(e)
        if e.get("expect_empty") and n:
            print(f"LABEL PROBLEM {q['id']}: marked empty but {n} catalogue rows satisfy it: {q['query']}")
            bad += 1
        elif not e.get("expect_empty") and not e.get("vague") and not e.get("unsupported_brand") and n == 0:
            print(f"LABEL PROBLEM {q['id']}: no catalogue row satisfies it: {q['query']}")
            bad += 1
    print(f"label check: {len(queries)} queries, {bad} problems")
    return bad


# ---------------------------------------------------------------------------
# b. Mapping: parser intent object -> neutral label form (the ONE place that knows the parser's shape)
# ---------------------------------------------------------------------------

def intent_to_label(intent: dict | None) -> dict:
    """Parser intent (services/intent_v2.parse_intent) -> the neutral `expect` form. Hard constraints only;
    soft preferences and `assumed` guesses are deliberately not mapped. Missing keys read as 'not stated'."""
    if not intent:
        return {}
    g = intent.get
    trans = g("transmission") or {}
    numeric_min, numeric_max = {}, {}
    for key, col in (("min_airbags", "airbags"), ("min_safety_stars", "safety_stars_adult"),
                     ("min_ev_range_km", "ev_range_km"), ("min_ground_clearance_mm", "ground_clearance_mm"),
                     ("min_boot_space_litres", "boot_space_litres"), ("min_mileage_kmpl", "mileage_kmpl"),
                     ("min_mileage_km_per_kg", "mileage_km_per_kg")):
        if g(key) is not None:
            numeric_min[col] = g(key)
    for key, col in (("max_ev_range_km", "ev_range_km"), ("max_ground_clearance_mm", "ground_clearance_mm"),
                     ("max_boot_space_litres", "boot_space_litres"), ("max_mileage_kmpl", "mileage_kmpl"),
                     ("max_mileage_km_per_kg", "mileage_km_per_kg")):
        if g(key) is not None:
            numeric_max[col] = g(key)
    budget = g("budget") or {}
    return {
        "budget_min": budget.get("min"), "budget_max": budget.get("max"),
        "fuel_include": g("fuel_types") or [], "fuel_exclude": g("exclude_fuel_types") or [],
        "body_include": g("body_types") or [], "body_exclude": g("exclude_body_types") or [],
        "transmission_family": trans.get("family"),
        "transmission_include": trans.get("include_types") or [],
        "transmission_exclude": trans.get("exclude_types") or [],
        "seats_min": g("seats_min"),
        "required_features": g("required_features") or [],
        "excluded_features": g("exclude_features") or [],
        "makes_include": g("makes") or [], "makes_exclude": g("exclude_makes") or [],
        "models_include": g("models") or [], "reference_models": g("reference_models") or [],
        "numeric_min": numeric_min, "numeric_max": numeric_max,
        "unsupported_brand": g("unsupported_terms") or [],
    }


def _as_set(field: str, value):
    if value is None or value == [] or value == {}:
        return set()
    if isinstance(value, dict):
        return {(k, float(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return set(value)
    return {value}


def _expected_for(field: str, expect: dict, got: dict):
    """Expected set for a field. 'around' budgets are judged by bracket, so they adopt the parser's value if it brackets."""
    if field in ("budget_min", "budget_max") and expect.get("budget_around") is not None:
        v = expect["budget_around"]
        gv = got.get(field)
        if field == "budget_min":
            ok = gv is not None and 0.7 * v <= gv <= 0.95 * v
        else:
            ok = gv is not None and 1.05 * v <= gv <= 1.3 * v
        return {gv} if ok else {("around", v)}
    return _as_set(field, expect.get(field))


def parse_accuracy(records: list[dict]) -> dict:
    """Per field: element precision / recall and exact-match rate over queries where the field is stated or produced."""
    stats = {f: {"tp": 0, "fp": 0, "fn": 0, "active": 0, "exact": 0} for f in PARSE_FIELDS}
    for rec in records:
        if rec.get("label") is None:
            continue
        got, expect = rec["label"], rec["expect"]
        for f in PARSE_FIELDS:
            exp_set, got_set = _expected_for(f, expect, got), _as_set(f, got.get(f))
            s = stats[f]
            s["tp"] += len(exp_set & got_set)
            s["fp"] += len(got_set - exp_set)
            s["fn"] += len(exp_set - got_set)
            if exp_set or got_set:
                s["active"] += 1
                s["exact"] += exp_set == got_set
    out = {}
    for f, s in stats.items():
        p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else None
        r = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else None
        out[f] = {**s, "precision": p, "recall": r,
                  "exact_match": s["exact"] / s["active"] if s["active"] else None}
    return out


# ---------------------------------------------------------------------------
# Engine access
# ---------------------------------------------------------------------------

def make_engine(name: str, catalogue=None):
    """run(query) -> response dict. `catalogue` (a catalogue DataFrame) replaces the real one for that engine:
    v3 takes it as recommend(catalogue=...), the current engine through services.new_car_service.get_catalogue."""
    if name == "current":
        from app import make_json_safe  # app.py is the owner of this helper
        from services import new_car_service as ncs

        def run(query: str) -> dict:
            original = ncs.get_catalogue
            if catalogue is not None:
                ncs.get_catalogue = lambda: catalogue
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    return ncs.get_kb_recommendations(query, str(ROOT), make_json_safe)
            finally:
                ncs.get_catalogue = original
        return run
    if name == "v3":
        try:
            from services.recsys.api import recommend
        except ImportError as exc:
            sys.exit(f"--engine v3: services.recsys.api.recommend is not available ({exc}).")

        def run(query: str) -> dict:
            with contextlib.redirect_stdout(io.StringIO()):
                return recommend(query, catalogue=catalogue)
        return run
    sys.exit(f"unknown engine {name!r}")


def catalogue_row(car: dict):
    cat = get_catalogue()
    vid = car.get("variant_id")
    if vid is not None and vid in cat.index:
        return cat.loc[vid]
    hit = cat[(cat["model"] == car.get("Model")) & (cat["variant"] == car.get("Variant"))]
    if hit.empty:
        hit = cat[(cat["model"] == car.get("Model"))]
    return None if hit.empty else hit.iloc[0]


def car_marked_relaxed(car: dict) -> bool:
    for key in ("relaxed", "relaxation", "broken_constraints", "violates", "breaks"):
        if car.get(key):
            return True
    return False


def is_relaxed_response(resp: dict) -> bool:
    """A v3 response with a top-level `relaxation` and per-car `violations` is a deliberately relaxed result."""
    cars = resp.get("recommendations") or []
    return bool(resp.get("relaxation")) and bool(cars) and all("violations" in c for c in cars)


# ---------------------------------------------------------------------------
# a2. Label truthfulness of relaxed results
# ---------------------------------------------------------------------------

_NUMERIC_V3_KEYS = {"airbags": "airbags", "safety_stars_adult": "safety_stars", "ev_range_km": "ev_range_km",
                    "ground_clearance_mm": "ground_clearance_mm", "boot_space_litres": "boot_space_litres",
                    "mileage_kmpl": "mileage_kmpl", "mileage_km_per_kg": "mileage_km_per_kg"}


def canonical_actual(violation: str) -> str | None:
    """eval-checker violation string -> canonical constraint id shared with the engine's names."""
    kind, _, rest = violation.partition(" ")
    first = rest.split(" ")[0]
    if kind.startswith("budget"):
        return "budget"
    if kind.startswith("fuel"):
        return "fuel"
    if kind.startswith("body"):
        return "body"
    if kind == "transmission_family":
        return "transmission_family"
    if kind.startswith("transmission"):
        return "gearbox"
    if kind == "seats_min":
        return "seats"
    if kind == "required_feature":
        return f"feature:{first}"
    if kind == "excluded_feature":
        return f"exclude_feature:{first}"
    if kind.startswith("make") or kind == "makes_exclude":
        return "make"
    if kind == "reference":
        return None  # "like X" size/price bands are not checkable from the label; skipped on both sides
    if kind in ("numeric_min", "numeric_max"):
        return ("min:" if kind == "numeric_min" else "max:") + _NUMERIC_V3_KEYS.get(first, first)
    return violation


def canonical_named(constraint: str) -> str | None:
    """engine violation key -> canonical constraint id."""
    if constraint.startswith("budget"):
        return "budget"
    if constraint in ("fuel", "exclude_fuel"):
        return "fuel"
    if constraint in ("body_type", "exclude_body_type"):
        return "body"
    if constraint in ("makes", "models", "exclude_makes"):
        return "make"
    if constraint == "gearbox_type":
        return "gearbox"
    if constraint == "like_model":
        return None
    if constraint.startswith("min_") and constraint != "min_safety_stars":
        return "min:" + constraint[4:]
    if constraint == "min_safety_stars":
        return "min:safety_stars"
    if constraint.startswith("max_"):
        return "max:" + constraint[4:]
    return constraint  # transmission_family, seats, feature:x, exclude_feature:x


def label_truthfulness(cars: list[dict], expect: dict) -> dict:
    """Every hard constraint a car really breaks (catalogue check) must be named in its `violations`, and nothing
    else may be named. Returns {"truthful": bool, "cars": [problem, ...]}."""
    problems = []
    for car in cars:
        row = catalogue_row(car)
        if row is None:
            problems.append({"car": f"{car.get('Model')} {car.get('Variant')}", "missing": ["not in catalogue"], "extra": []})
            continue
        actual = {c for c in map(canonical_actual, violations(row, expect)) if c}
        named = {c for c in (canonical_named(v["constraint"]) for v in car.get("violations") or []) if c}
        missing, extra = sorted(actual - named), sorted(named - actual)
        if missing or extra:
            problems.append({"car": f"{row['model']} / {row['variant']}", "missing": missing, "extra": extra})
    return {"truthful": not problems, "cars": problems}


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def intent_fingerprint(intent: dict | None) -> str:
    """Everything the ranking depends on that the parser decides: hard constraints, use case, soft prefs, assumed."""
    if not intent:
        return ""
    return json.dumps({
        "label": intent_to_label(intent), "use_case": intent.get("use_case"),
        "soft": sorted(intent.get("soft_preferences") or []),
        "assumed": {k: sorted(v) for k, v in (intent.get("assumed") or {}).items() if v},
    }, sort_keys=True, default=str)


def evaluate(engine_name: str, queries: list[dict]) -> dict:
    run = make_engine(engine_name)
    records = []
    for q in queries:
        try:
            resp = run(q["query"])
            error = None
        except Exception as exc:  # a crash is a result, not a reason to stop
            resp, error = {}, f"{type(exc).__name__}: {exc}"
        cars = resp.get("recommendations") or []
        relaxed_resp = is_relaxed_response(resp)
        rec = {
            "id": q["id"], "query": q["query"], "category": q["category"], "expect": q["expect"],
            "paraphrase_group": q.get("paraphrase_group"), "error": error,
            "n_returned": len(cars),
            "top_models": [c.get("Model") for c in cars[:8]],
            "top_cars": [f"{c.get('Make')} {c.get('Model')}" for c in cars[:8]],
            "message": resp.get("message"),
            "vague_flag": bool(resp.get("vague")),
            "not_personalised_flag": resp.get("personalised") is False,
            "assumed": resp.get("assumed"),
            "has_relaxation_hints": bool(resp.get("relaxation_hints")),
            "label": intent_to_label(resp["intent"]) if resp.get("intent") else None,
            "intent_fp": intent_fingerprint(resp.get("intent")),
            "violations": [],
            "relaxed_response": relaxed_resp,
            "label_check": None,
            "all_marked_relaxed": relaxed_resp or (bool(cars) and all(car_marked_relaxed(c) for c in cars)),
        }
        if relaxed_resp:
            rec["label_check"] = label_truthfulness(cars, q["expect"])
        elif not rec["all_marked_relaxed"]:
            for car in cars:
                row = catalogue_row(car)
                if row is None:
                    rec["violations"].append({"car": f"{car.get('Model')} {car.get('Variant')}", "constraint": "not in catalogue"})
                    continue
                for v in violations(row, q["expect"]):
                    rec["violations"].append({"car": f"{row['model']} / {row['variant']}", "constraint": v})
        records.append(rec)

    summary = summarise(records)
    summary["unknown_probe"] = unknown_probe(engine_name)
    summary["shortlist_agreement"] = shortlist_agreement(records)
    return {"engine": engine_name, "n_queries": len(records), "summary": summary, "records": records}


def rbo(a: list, b: list, p: float = 0.9) -> float:
    """Extrapolated rank-biased overlap (Webber et al. 2010) of two ranked lists, truncated to the shorter length."""
    a, b = list(dict.fromkeys(a)), list(dict.fromkeys(b))
    k = min(len(a), len(b))
    if k == 0:
        return 1.0 if not a and not b else 0.0
    x = [len(set(a[:d]) & set(b[:d])) for d in range(1, k + 1)]
    s = sum(x[d - 1] / d * p ** d for d in range(1, k + 1))
    return x[k - 1] / k * p ** k + (1 - p) / p * s


def _paraphrase_stats(groups: dict) -> dict:
    j, t1, r = [], [], []
    for rs in groups.values():
        for x, y in combinations(rs, 2):
            a, b = set(x["top_models"][:5]), set(y["top_models"][:5])
            j.append(len(a & b) / len(a | b) if a | b else 1.0)
            t1.append(1.0 if x["top_models"][:1] == y["top_models"][:1] else 0.0)
            r.append(rbo(x["top_models"][:8], y["top_models"][:8]))
    mean = lambda v: sum(v) / len(v) if v else None  # noqa: E731
    return {"groups": len(groups), "pairs": len(j), "mean_jaccard_top5": mean(j), "top1_agreement": mean(t1),
            "rbo_p0.9_top8": mean(r)}


def summarise(records: list[dict]) -> dict:
    # a. constraint satisfaction: over NON-relaxed responses that returned cars (relaxed ones are judged on labels)
    with_cars = [r for r in records if r["n_returned"] and not r["error"] and not r["relaxed_response"]]
    clean = [r for r in with_cars if not r["violations"]]
    by_cause = defaultdict(int)
    for r in with_cars:
        for kind in {v["constraint"].split(" ")[0] for v in r["violations"]}:
            by_cause[kind] += 1
    relaxed = [r for r in records if r["relaxed_response"]]
    mislabelled = [r for r in relaxed if not r["label_check"]["truthful"]]
    # b. parse accuracy
    parse = parse_accuracy(records)
    # c. empty / over-constrained handling
    empties = [r for r in records if r["expect"].get("expect_empty")]
    empty_outcomes = {"empty": 0, "relaxed_truthfully_labelled": 0, "relaxed_but_mislabelled": 0, "cars_returned_unmarked": 0}
    empty_detail = defaultdict(list)
    for r in empties:
        if r["n_returned"] == 0:
            k = "empty"
        elif r["relaxed_response"]:
            k = "relaxed_truthfully_labelled" if r["label_check"]["truthful"] else "relaxed_but_mislabelled"
        elif r["all_marked_relaxed"]:
            k = "relaxed_but_mislabelled"  # marked, but not in the checkable v3 form
        else:
            k = "cars_returned_unmarked"
        empty_outcomes[k] += 1
        empty_detail[k].append(r["id"])
    non_empty_expected = [r for r in records if not r["expect"].get("expect_empty") and not r["expect"].get("unsupported_brand")]
    false_empty = [r["id"] for r in non_empty_expected if r["n_returned"] == 0 and not r["error"]]
    # d. vague / unsupported
    vague = [r for r in records if r["expect"].get("vague")]
    unsup = [r for r in records if r["expect"].get("unsupported_brand")]
    # e. paraphrase consistency (top-5 Jaccard, top-1 agreement, RBO p=0.9 on top-8), all groups and split by
    # whether the three wordings parsed to an identical intent
    groups = defaultdict(list)
    for r in records:
        if r["paraphrase_group"]:
            groups[r["paraphrase_group"]].append(r)
    identical = {g: rs for g, rs in groups.items() if len({r["intent_fp"] for r in rs}) == 1}
    differing = {g: rs for g, rs in groups.items() if g not in identical}
    per_group = {}
    for gid, rs in groups.items():
        pairs = [len(set(x["top_models"][:5]) & set(y["top_models"][:5])) / (len(set(x["top_models"][:5]) | set(y["top_models"][:5])) or 1)
                 for x, y in combinations(rs, 2)]
        per_group[gid] = sum(pairs) / len(pairs) if pairs else None
    para_all = _paraphrase_stats(groups)
    return {
        "constraint_satisfaction": {
            "scope": "non-relaxed responses only",
            "queries_with_cars": len(with_cars), "queries_zero_violations": len(clean),
            "share_zero_violations": len(clean) / len(with_cars) if with_cars else None,
            "violating_queries": len(with_cars) - len(clean),
            "by_constraint_kind": dict(sorted(by_cause.items(), key=lambda kv: -kv[1])),
            "violations": [{"id": r["id"], "query": r["query"], "n": len(r["violations"]), "examples": r["violations"][:3]}
                           for r in with_cars if r["violations"]],
        },
        "relaxed_responses": {
            "n": len(relaxed), "truthfully_labelled": len(relaxed) - len(mislabelled), "mislabelled": len(mislabelled),
            "mislabelled_cases": [{"id": r["id"], "query": r["query"], "problems": r["label_check"]["cars"][:4]}
                                  for r in mislabelled],
        },
        "parse_accuracy": parse,
        "empty_handling": {"expect_empty_queries": len(empties), "outcomes": empty_outcomes,
                           "ids": dict(empty_detail),
                           "false_empty_on_satisfiable_queries": false_empty},
        "vague_handling": {"n": len(vague),
                           "returned_cars": sum(1 for r in vague if r["n_returned"]),
                           "flagged_vague": sum(1 for r in vague if r["vague_flag"]),
                           "labelled_not_personalised": sum(1 for r in vague if r["not_personalised_flag"]),
                           "examples": [{"id": r["id"], "n_returned": r["n_returned"], "top": r["top_models"][:3],
                                         "flag": r["vague_flag"], "message": r["message"]} for r in vague]},
        "unsupported_brand_handling": {"n": len(unsup),
                                       "returned_cars": sum(1 for r in unsup if r["n_returned"]),
                                       "message_names_brand": sum(
                                           1 for r in unsup if r["message"] and any(
                                               b.lower() in r["message"].lower() for b in r["expect"]["unsupported_brand"])),
                                       "examples": [{"id": r["id"], "n_returned": r["n_returned"], "top": r["top_models"][:3],
                                                     "message": r["message"]} for r in unsup]},
        "paraphrase_consistency": {
            **para_all,  # mean_jaccard_top5 kept at top level for older result files
            "identical_parse": {"n_groups": len(identical), **_paraphrase_stats(identical)},
            "differing_parse": {"n_groups": len(differing), **_paraphrase_stats(differing)},
            "per_group": per_group,
            "groups_identical_parse": sorted(identical),
        },
        "errors": [{"id": r["id"], "error": r["error"]} for r in records if r["error"]],
    }


# ---------------------------------------------------------------------------
# f. Unknown-handling probe (engine independent: the modified catalogue goes in through make_engine(catalogue=))
# ---------------------------------------------------------------------------

ALL_FEATURE_COLS = ["sunroof", "adas_available", "camera_360", "ventilated_front_seats", "cruise_control",
                    "wireless_charging", "heads_up_display", "android_auto", "apple_carplay"]
# (query, catalogue columns blanked on the model under test). Hard-required features first, then soft wishes
# (cars lacking the feature stay in the list, which is where "unknown scored as no" can show).
PROBES = [
    ("SUV with sunroof under 20 lakh", ["sunroof"]),
    ("SUV with ventilated seats", ["ventilated_front_seats"]),
    ("automatic SUV with 360 camera under 25 lakh", ["camera_360"]),
    ("petrol SUV with cruise control under 15 lakh", ["cruise_control"]),
    ("SUV with wireless charging under 20 lakh", ["wireless_charging"]),
    ("SUV with adas under 25 lakh", ["adas_available"]),
    ("sedan with heads up display", ["heads_up_display"]),
    ("comfortable SUV under 20 lakh", ["ventilated_front_seats", "cruise_control"]),
    ("comfortable hatchback under 10 lakh", ["ventilated_front_seats", "cruise_control"]),
    ("comfortable sedan under 20 lakh", ["ventilated_front_seats", "cruise_control"]),
    ("loaded SUV under 25 lakh", ALL_FEATURE_COLS),
    ("loaded sedan under 25 lakh", ALL_FEATURE_COLS),
    ("loaded hatchback under 12 lakh", ALL_FEATURE_COLS),
    ("premium SUV under 30 lakh", ["sunroof", "camera_360", "adas_available", "ventilated_front_seats"]),
    ("feature rich family MPV", ALL_FEATURE_COLS),
]
PROBE_TOP_N = 5


def unknown_probe(engine_name: str) -> dict:
    original = get_catalogue()
    base_run = make_engine(engine_name)

    def lacks(row, cols):
        return all(row[c] is False and c not in row["unverified_fields"] for c in cols)

    def lacking_above(cars, upto, cols, model):
        return [c["Model"] for c in cars[:upto] if c["Model"] != model and (r := catalogue_row(c)) is not None
                and lacks(r, cols)]

    results = []
    for query, cols in PROBES:
        before = base_run(query).get("recommendations") or []
        if not before:
            results.append({"query": query, "note": "no results before blanking"})
            continue
        for rank0, top in enumerate(before[:PROBE_TOP_N], start=1):
            frame = original.copy()
            mask = (frame["make"] == top["Make"]) & (frame["model"] == top["Model"])
            for c in cols:
                frame.loc[mask, c] = None  # the blank is planted on every variant of this model
            after = make_engine(engine_name, frame)(query).get("recommendations") or []
            models_after = [c["Model"] for c in after]
            new_rank = models_after.index(top["Model"]) + 1 if top["Model"] in models_after else None
            above_before = lacking_above(before, rank0 - 1, cols, top["Model"])
            above_after = lacking_above(after, (new_rank - 1) if new_rank else len(after), cols, top["Model"])
            newly = [m for m in above_after if m not in above_before]
            results.append({
                "query": query, "blanked": cols, "model": top["Model"], "rank_before": rank0,
                "rank_after": new_rank, "still_returned": new_rank is not None,
                "rank_change": None if new_rank is None else new_rank - rank0,
                "known_lacking_cars_above_after": above_after,
                "known_lacking_cars_above_before": above_before,
                "known_lacking_newly_above": newly,
                "scored_as_no": bool(above_after) and new_rank is not None,
            })
    probed = [r for r in results if "model" in r]
    kept = [r for r in probed if r["still_returned"]]
    return {
        "supported": True, "n_queries": len(PROBES), "n_probes": len(probed),
        "still_returned": len(kept), "dropped_from_list": len(probed) - len(kept),
        "rank_worse": sum(1 for r in kept if r["rank_change"] > 0),
        "rank_better": sum(1 for r in kept if r["rank_change"] < 0),
        "rank_same": sum(1 for r in kept if r["rank_change"] == 0),
        "known_lacking_above": sum(1 for r in probed if r["scored_as_no"]),
        "known_lacking_newly_above": sum(1 for r in kept if r["known_lacking_newly_above"]),
        "results": results,
    }


# ---------------------------------------------------------------------------
# g. Shortlist agreement (owner-labelled sheet)
# ---------------------------------------------------------------------------

SHEET_PATH = ROOT / "eval" / "shortlist_sheet.csv"


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def shortlist_agreement(records: list[dict], sheet: Path = SHEET_PATH) -> dict:
    import csv
    if not sheet.exists():
        return {"filled": 0, "note": "no shortlists filled in yet"}
    by_id = {r["id"]: r for r in records}
    gold = {}
    with sheet.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            cars = [_norm(row.get(f"car_{i}") or "") for i in range(1, 6)]
            cars = [c for c in cars if c]
            if cars and row["id"] in by_id:
                gold[row["id"]] = cars
    if not gold:
        return {"filled": 0, "note": "no shortlists filled in yet"}
    recalls, rrs = [], []
    for qid, cars in gold.items():
        top = [_norm(c) for c in by_id[qid]["top_cars"][:8]]
        recalls.append(len(set(cars) & set(top)) / len(set(cars)))
        rrs.append(next((1.0 / (i + 1) for i, c in enumerate(top) if c in cars), 0.0))
    return {"filled": len(gold), "recall_at_8": sum(recalls) / len(recalls), "mrr": sum(rrs) / len(rrs)}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def num3(x):
    return "n/a" if x is None else f"{x:.3f}"


def print_table(result: dict) -> None:
    s = result["summary"]
    cs = s["constraint_satisfaction"]
    print(f"\nengine={result['engine']}  queries={result['n_queries']}")
    print("\n[a] Constraint satisfaction (non-relaxed responses only)")
    print(f"  queries returning cars: {cs['queries_with_cars']}   with zero violations: {cs['queries_zero_violations']} "
          f"({pct(cs['share_zero_violations'])})")
    print(f"  violating queries by constraint kind: {cs['by_constraint_kind']}")
    for v in cs["violations"][:25]:
        ex = v["examples"][0]
        print(f"    {v['id']:<14} {v['n']:>3} viol  e.g. {ex['car']}: {ex['constraint']}  | {v['query']}")
    if len(cs["violations"]) > 25:
        print(f"    ... {len(cs['violations']) - 25} more in the JSON")
    rr = s.get("relaxed_responses", {})
    print(f"  relaxed responses (judged on labels): {rr.get('n', 0)}, truthful {rr.get('truthfully_labelled', 0)}, "
          f"mislabelled {rr.get('mislabelled', 0)}")
    for m in rr.get("mislabelled_cases", [])[:15]:
        print(f"    {m['id']:<14} {m['problems'][0]}  | {m['query']}")
    print("\n[b] Parse accuracy per field (element precision / recall; exact match where stated or produced)")
    print(f"  {'field':<22}{'P':>8}{'R':>8}{'exact':>9}{'active':>8}")
    for f, st in s["parse_accuracy"].items():
        print(f"  {f:<22}{pct(st['precision']):>8}{pct(st['recall']):>8}{pct(st['exact_match']):>9}{st['active']:>8}")
    eh = s["empty_handling"]
    print(f"\n[c] Over-constrained handling ({eh['expect_empty_queries']} queries): {eh['outcomes']}")
    print(f"    satisfiable queries that came back empty: {len(eh['false_empty_on_satisfiable_queries'])} "
          f"{eh['false_empty_on_satisfiable_queries']}")
    vg, ub = s["vague_handling"], s["unsupported_brand_handling"]
    print(f"\n[d] Vague queries: {vg['n']}, returned cars: {vg['returned_cars']}, flagged vague: {vg['flagged_vague']}, "
          f"labelled not personalised: {vg.get('labelled_not_personalised', 'n/a')}")
    print(f"    Unsupported-brand-only queries: {ub['n']}, returned cars: {ub['returned_cars']}, "
          f"message names the brand: {ub['message_names_brand']}")
    pc = s["paraphrase_consistency"]
    print(f"\n[e] Paraphrase consistency ({pc['groups']} groups; top-5 Jaccard / top-1 agreement / RBO p=0.9 top-8)")
    for name, d in (("all groups", pc), ("identical parse", pc.get("identical_parse")), ("differing parse", pc.get("differing_parse"))):
        if d:
            print(f"    {name:<16} groups={d.get('n_groups', d['groups']):>3}  {num3(d['mean_jaccard_top5'])} / "
                  f"{num3(d.get('top1_agreement'))} / {num3(d.get('rbo_p0.9_top8'))}")
    up = s["unknown_probe"]
    if up.get("supported") and "still_returned" in up:
        print(f"\n[f] Unknown-handling probe: {up['n_probes']} probes (top {PROBE_TOP_N} models of {up['n_queries']} queries), "
              f"still returned {up['still_returned']}, dropped {up['dropped_from_list']}, rank worse {up['rank_worse']}, "
              f"same {up['rank_same']}, better {up['rank_better']}, known-lacking car above {up['known_lacking_above']} "
              f"(newly above: {up['known_lacking_newly_above']})")
    elif up.get("supported"):
        print(f"\n[f] Unknown-handling probe (old format): {up['n_probes']} probes, overtaken {up['scored_as_no']}")
    else:
        print(f"\n[f] Unknown-handling probe: {up['note']}")
    sl = s.get("shortlist_agreement") or {}
    if sl.get("filled"):
        print(f"\n[g] Shortlist agreement ({sl['filled']} queries): recall@8 {num3(sl['recall_at_8'])}, MRR {num3(sl['mrr'])}")
    else:
        print("\n[g] Shortlist agreement: no shortlists filled in yet")
    if s["errors"]:
        print(f"\nERRORS: {s['errors']}")


def flat_metrics(result: dict) -> dict:
    s = result["summary"]
    cs, rr, eh = s["constraint_satisfaction"], s.get("relaxed_responses") or {}, s["empty_handling"]
    pc, up, sl = s["paraphrase_consistency"], s["unknown_probe"], s.get("shortlist_agreement") or {}
    oc = eh["outcomes"]
    out = {
        "constraint satisfaction (non-relaxed)": pct(cs["share_zero_violations"]),
        "  queries with cars / violating": f"{cs['queries_with_cars']} / {cs['violating_queries']}",
        "relaxed responses (truthful/mislabelled)": f"{rr.get('truthfully_labelled', 0)}/{rr.get('mislabelled', 0)}" if rr else "-",
        "over-constrained: empty": oc.get("empty", oc.get("no_cars", 0) + oc.get("no_cars_with_relaxation_hints", 0)),
        "over-constrained: relaxed, truthful": oc.get("relaxed_truthfully_labelled", "-"),
        "over-constrained: relaxed, mislabelled": oc.get("relaxed_but_mislabelled", oc.get("cars_marked_relaxed", "-")),
        "over-constrained: cars unmarked": oc.get("cars_returned_unmarked", 0),
        "satisfiable queries returned empty": len(eh["false_empty_on_satisfiable_queries"]),
        "vague: cars / flagged": f"{s['vague_handling']['returned_cars']} / {s['vague_handling']['flagged_vague']}",
        "vague: labelled not personalised": s["vague_handling"].get("labelled_not_personalised", "-"),
        "unsupported: cars / names brand": f"{s['unsupported_brand_handling']['returned_cars']} / "
                                          f"{s['unsupported_brand_handling']['message_names_brand']}",
        "paraphrase Jaccard top5 (all)": num3(pc["mean_jaccard_top5"]),
        "paraphrase top-1 agreement (all)": num3(pc.get("top1_agreement")),
        "paraphrase RBO p0.9 top8 (all)": num3(pc.get("rbo_p0.9_top8")),
    }
    for tag, key in (("identical parse", "identical_parse"), ("differing parse", "differing_parse")):
        d = pc.get(key)
        out[f"paraphrase J/top1/RBO ({tag}, {d['n_groups']} grp)" if d else f"paraphrase ({tag})"] = (
            f"{num3(d['mean_jaccard_top5'])}/{num3(d['top1_agreement'])}/{num3(d['rbo_p0.9_top8'])}" if d else "-")
    if "still_returned" in up:
        out.update({
            "unknown probe: probes": up["n_probes"], "  still returned": up["still_returned"],
            "  dropped": up["dropped_from_list"], "  rank worse": up["rank_worse"],
            "  known-lacking car above": up["known_lacking_above"],
            "  known-lacking newly above": up["known_lacking_newly_above"],
        })
    else:
        out["unknown probe"] = "old format / n/a"
    out["shortlist recall@8 / MRR"] = (f"{num3(sl['recall_at_8'])} / {num3(sl['mrr'])}" if sl.get("filled")
                                       else "no shortlists filled in yet")
    return out


def print_compare(path_a: str, path_b: str) -> None:
    a, b = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (path_a, path_b))
    fa, fb = flat_metrics(a), flat_metrics(b)
    names = [f"{a['engine']} ({Path(path_a).name})", f"{b['engine']} ({Path(path_b).name})"]
    w = max(len(k) for k in {**fa, **fb}) + 2
    print(f"{'metric':<{w}}{names[0]:<34}{names[1]}")
    for k in dict.fromkeys([*fa, *fb]):
        print(f"{k:<{w}}{str(fa.get(k, '-')):<34}{str(fb.get(k, '-'))}")


def main() -> None:
    global QUERIES_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["current", "v3"], default="current")
    ap.add_argument("--out", help="write full JSON results here")
    ap.add_argument("--queries", default=str(QUERIES_PATH), help="query file (JSON lines), default eval/queries.jsonl")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"), help="print a side-by-side table of two result files")
    ap.add_argument("--check-labels", action="store_true", help="only sanity-check the labels against the catalogue")
    args = ap.parse_args()

    if args.compare:
        print_compare(*args.compare)
        return
    QUERIES_PATH = Path(args.queries)
    queries = load_queries()
    if args.check_labels:
        sys.exit(1 if check_labels(queries) else 0)

    result = evaluate(args.engine, queries)
    print_table(result)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
