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

def make_engine(name: str):
    if name == "current":
        from app import make_json_safe  # app.py is the owner of this helper
        from services import new_car_service as ncs

        def run(query: str) -> dict:
            with contextlib.redirect_stdout(io.StringIO()):
                return ncs.get_kb_recommendations(query, str(ROOT), make_json_safe)
        return run
    if name == "v3":
        try:
            from services.recsys.api import recommend
        except ImportError as exc:
            sys.exit(f"--engine v3: services.recsys.api.recommend is not available yet ({exc}). "
                     "It is being built separately; run with --engine current for now.")

        def run(query: str) -> dict:
            with contextlib.redirect_stdout(io.StringIO()):
                return recommend(query)
        return run
    sys.exit(f"unknown engine {name!r}")


def catalogue_row(car: dict):
    cat = get_catalogue()
    hit = cat[(cat["model"] == car.get("Model")) & (cat["variant"] == car.get("Variant"))]
    if hit.empty:
        hit = cat[(cat["model"] == car.get("Model"))]
    return None if hit.empty else hit.iloc[0]


def car_marked_relaxed(car: dict) -> bool:
    for key in ("relaxed", "relaxation", "broken_constraints", "violates", "breaks"):
        if car.get(key):
            return True
    return False


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

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
        rec = {
            "id": q["id"], "query": q["query"], "category": q["category"], "expect": q["expect"],
            "paraphrase_group": q.get("paraphrase_group"), "error": error,
            "n_returned": len(cars),
            "top_models": [c.get("Model") for c in cars[:8]],
            "message": resp.get("message"),
            "vague_flag": bool(resp.get("vague")),
            "assumed": resp.get("assumed"),
            "has_relaxation_hints": bool(resp.get("relaxation_hints")),
            "label": intent_to_label(resp["intent"]) if resp.get("intent") else None,
            "violations": [],
            "all_marked_relaxed": bool(cars) and all(car_marked_relaxed(c) for c in cars),
        }
        if not rec["all_marked_relaxed"]:
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
    return {"engine": engine_name, "n_queries": len(records), "summary": summary, "records": records}


def summarise(records: list[dict]) -> dict:
    # a. constraint satisfaction: over queries that returned cars (queries with no cars have nothing to violate)
    with_cars = [r for r in records if r["n_returned"] and not r["error"]]
    clean = [r for r in with_cars if not r["violations"]]
    by_cause = defaultdict(int)
    for r in with_cars:
        for kind in {v["constraint"].split(" ")[0] for v in r["violations"]}:
            by_cause[kind] += 1
    # b. parse accuracy
    parse = parse_accuracy(records)
    # c. empty handling
    empties = [r for r in records if r["expect"].get("expect_empty")]
    empty_outcomes = defaultdict(int)
    for r in empties:
        if r["n_returned"] == 0:
            empty_outcomes["no_cars" + ("_with_relaxation_hints" if r["has_relaxation_hints"] else "")] += 1
        elif r["all_marked_relaxed"]:
            empty_outcomes["cars_marked_relaxed"] += 1
        else:
            empty_outcomes["cars_returned_unmarked"] += 1
    non_empty_expected = [r for r in records if not r["expect"].get("expect_empty") and not r["expect"].get("unsupported_brand")]
    false_empty = [r["id"] for r in non_empty_expected if r["n_returned"] == 0 and not r["error"]]
    # d. vague / unsupported
    vague = [r for r in records if r["expect"].get("vague")]
    unsup = [r for r in records if r["expect"].get("unsupported_brand")]
    # e. paraphrase consistency
    groups = defaultdict(list)
    for r in records:
        if r["paraphrase_group"]:
            groups[r["paraphrase_group"]].append(r)
    jaccards = {}
    for gid, rs in groups.items():
        sets = [set(r["top_models"][:5]) for r in rs]
        pairs = [len(a & b) / len(a | b) if a | b else 1.0 for a, b in combinations(sets, 2)]
        jaccards[gid] = sum(pairs) / len(pairs) if pairs else None
    valid = [v for v in jaccards.values() if v is not None]
    return {
        "constraint_satisfaction": {
            "queries_with_cars": len(with_cars), "queries_zero_violations": len(clean),
            "share_zero_violations": len(clean) / len(with_cars) if with_cars else None,
            "violating_queries": len(with_cars) - len(clean),
            "by_constraint_kind": dict(sorted(by_cause.items(), key=lambda kv: -kv[1])),
            "violations": [{"id": r["id"], "query": r["query"], "n": len(r["violations"]), "examples": r["violations"][:3]}
                           for r in with_cars if r["violations"]],
        },
        "parse_accuracy": parse,
        "empty_handling": {"expect_empty_queries": len(empties), "outcomes": dict(empty_outcomes),
                           "false_empty_on_satisfiable_queries": false_empty},
        "vague_handling": {"n": len(vague),
                           "returned_cars": sum(1 for r in vague if r["n_returned"]),
                           "flagged_vague": sum(1 for r in vague if r["vague_flag"]),
                           "examples": [{"id": r["id"], "n_returned": r["n_returned"], "top": r["top_models"][:3],
                                         "flag": r["vague_flag"], "message": r["message"]} for r in vague]},
        "unsupported_brand_handling": {"n": len(unsup),
                                       "returned_cars": sum(1 for r in unsup if r["n_returned"]),
                                       "message_names_brand": sum(
                                           1 for r in unsup if r["message"] and any(
                                               b.lower() in r["message"].lower() for b in r["expect"]["unsupported_brand"])),
                                       "examples": [{"id": r["id"], "n_returned": r["n_returned"], "top": r["top_models"][:3],
                                                     "message": r["message"]} for r in unsup]},
        "paraphrase_consistency": {"groups": len(groups), "mean_jaccard_top5": sum(valid) / len(valid) if valid else None,
                                   "per_group": jaccards},
        "errors": [{"id": r["id"], "error": r["error"]} for r in records if r["error"]],
    }


# ---------------------------------------------------------------------------
# f. Unknown-handling probe
# ---------------------------------------------------------------------------

# (query, catalogue columns blanked on the top result). The first five make the feature a hard requirement;
# the last five make it a soft wish (the cars lacking it stay in the list), which is where "unknown scored
# as no" can show.
PROBES = [
    ("SUV with sunroof under 20 lakh", ["sunroof"]),
    ("SUV with ventilated seats", ["ventilated_front_seats"]),
    ("automatic SUV with 360 camera under 25 lakh", ["camera_360"]),
    ("petrol SUV with cruise control under 15 lakh", ["cruise_control"]),
    ("SUV with wireless charging under 20 lakh", ["wireless_charging"]),
    ("comfortable SUV under 20 lakh", ["ventilated_front_seats", "cruise_control"]),
    ("comfortable hatchback under 10 lakh", ["ventilated_front_seats", "cruise_control"]),
    ("comfortable sedan under 20 lakh", ["ventilated_front_seats", "cruise_control"]),
    ("loaded SUV under 25 lakh", ["sunroof", "adas_available", "camera_360", "ventilated_front_seats", "cruise_control",
                                  "wireless_charging", "heads_up_display", "android_auto", "apple_carplay"]),
    ("loaded sedan under 25 lakh", ["sunroof", "adas_available", "camera_360", "ventilated_front_seats", "cruise_control",
                                    "wireless_charging", "heads_up_display", "android_auto", "apple_carplay"]),
]


def unknown_probe(engine_name: str) -> dict:
    if engine_name != "current":
        return {"supported": False, "note": "probe patches services.new_car_service.get_catalogue; current engine only"}
    from app import make_json_safe
    from services import new_car_service as ncs

    original = get_catalogue()

    def run_with(frame, query):
        ncs.get_catalogue = lambda: frame
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return ncs.get_kb_recommendations(query, str(ROOT), make_json_safe)
        finally:
            ncs.get_catalogue = get_catalogue

    def lacks(row, cols):
        return all(row[c] is False and c not in row["unverified_fields"] for c in cols)

    results = []
    for query, cols in PROBES:
        before = run_with(original, query).get("recommendations") or []
        if not before:
            results.append({"query": query, "note": "no results before blanking"})
            continue
        top = before[0]
        top_row = catalogue_row(top)
        frame = original.copy()
        vid = int(top_row["variant_id"])
        for c in cols:
            frame.at[vid, c] = None  # the blank is planted at the top result's own variant
        after = run_with(frame, query).get("recommendations") or []
        models_after = [c["Model"] for c in after]
        new_rank = models_after.index(top["Model"]) + 1 if top["Model"] in models_after else None
        above = after[: (new_rank - 1) if new_rank else len(after)]
        lacking_above = [c["Model"] for c in above if (r := catalogue_row(c)) is not None and r["variant_id"] != vid
                         and lacks(r, cols)]
        results.append({
            "query": query, "blanked": cols, "top_before": f"{top['Model']} / {top['Variant']}",
            "rank_after": new_rank, "dropped_from_list": new_rank is None,
            "flagged_unverified_after": bool(new_rank and any(
                "Unverified" in u for u in after[new_rank - 1].get("unverified", []))),
            "known_lacking_cars_ranked_above": lacking_above,
            "scored_as_no": bool(lacking_above),
        })
    probed = [r for r in results if "scored_as_no" in r]
    return {"supported": True, "n_probes": len(probed),
            "scored_as_no": sum(1 for r in probed if r["scored_as_no"]),
            "dropped_from_list": sum(1 for r in probed if r["dropped_from_list"]),
            "results": results}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def print_table(result: dict) -> None:
    s = result["summary"]
    cs = s["constraint_satisfaction"]
    print(f"\nengine={result['engine']}  queries={result['n_queries']}")
    print("\n[a] Constraint satisfaction")
    print(f"  queries returning cars: {cs['queries_with_cars']}   with zero violations: {cs['queries_zero_violations']} "
          f"({pct(cs['share_zero_violations'])})")
    print(f"  violating queries by constraint kind: {cs['by_constraint_kind']}")
    for v in cs["violations"][:25]:
        ex = v["examples"][0]
        print(f"    {v['id']:<14} {v['n']:>3} viol  e.g. {ex['car']}: {ex['constraint']}  | {v['query']}")
    if len(cs["violations"]) > 25:
        print(f"    ... {len(cs['violations']) - 25} more in the JSON")
    print("\n[b] Parse accuracy per field (element precision / recall; exact match where stated or produced)")
    print(f"  {'field':<22}{'P':>8}{'R':>8}{'exact':>9}{'active':>8}")
    for f, st in s["parse_accuracy"].items():
        print(f"  {f:<22}{pct(st['precision']):>8}{pct(st['recall']):>8}{pct(st['exact_match']):>9}{st['active']:>8}")
    eh = s["empty_handling"]
    print(f"\n[c] Empty handling ({eh['expect_empty_queries']} over-constrained queries): {eh['outcomes']}")
    print(f"    satisfiable queries that came back empty: {len(eh['false_empty_on_satisfiable_queries'])} "
          f"{eh['false_empty_on_satisfiable_queries']}")
    vg, ub = s["vague_handling"], s["unsupported_brand_handling"]
    print(f"\n[d] Vague queries: {vg['n']}, returned cars: {vg['returned_cars']}, flagged vague: {vg['flagged_vague']}")
    print(f"    Unsupported-brand-only queries: {ub['n']}, returned cars: {ub['returned_cars']}, "
          f"message names the brand: {ub['message_names_brand']}")
    pc = s["paraphrase_consistency"]
    print(f"\n[e] Paraphrase consistency: {pc['groups']} groups, mean top-5 model Jaccard = "
          f"{'n/a' if pc['mean_jaccard_top5'] is None else round(pc['mean_jaccard_top5'], 3)}")
    up = s["unknown_probe"]
    if up.get("supported"):
        print(f"\n[f] Unknown-handling probe: {up['n_probes']} probes, blanked car overtaken by a known-lacking car "
              f"in {up['scored_as_no']}, dropped from list in {up['dropped_from_list']}")
        for r in up["results"]:
            if "scored_as_no" in r:
                print(f"    {r['query'][:48]:<48} top={r['top_before'][:30]:<30} rank_after={r['rank_after']} "
                      f"lacking_above={len(r['known_lacking_cars_ranked_above'])}")
    else:
        print(f"\n[f] Unknown-handling probe: {up['note']}")
    if s["errors"]:
        print(f"\nERRORS: {s['errors']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["current", "v3"], default="current")
    ap.add_argument("--out", help="write full JSON results here")
    ap.add_argument("--check-labels", action="store_true", help="only sanity-check the labels against the catalogue")
    args = ap.parse_args()

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
