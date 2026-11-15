"""Template explanations built only from numbers used in scoring (plan section 8).

Up to MAX_REASONS reasons per car, each {text, evidence_class, fields, source_url?}; every `fields`
entry is a catalogue column (spec) or an evidence criterion name. Required features the car meets come
first, then the criteria with the highest weight x value. Unknowns are listed plainly. The match label is
built from the overall score (MATCH_LEVELS) and the number of unknown things.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from services.filter_v2 import FEATURE_COLUMNS, MIN_COLUMNS
from services.recsys import config
from services.recsys.common import is_unknown, num
from services.recsys.criteria import COMFORT_BOOLS, SPEC_LABELS, TECH_BOOLS
from services.recsys.evidence import ASPECTS, THEMES, Evidence, criterion_label
from services.recsys.relax import format_rupees

BOOL_LABELS = {
    "esc": "ESC", "abs": "ABS", "tpms": "tyre-pressure monitoring", "hill_assist": "hill assist",
    "auto_climate_control": "auto climate control", "rear_ac_vents": "rear AC vents",
    "cruise_control": "cruise control", "sunroof": "sunroof", "ventilated_front_seats": "ventilated seats",
    "adas_available": "ADAS", "camera_360": "360° camera", "connected_car_features": "connected-car features",
    "wireless_charging": "wireless charging", "android_auto": "Android Auto", "apple_carplay": "Apple CarPlay",
    "heads_up_display": "heads-up display",
}
UNKNOWN_TEXT = {
    "running_cost": "Running cost: no mileage or range figure on record",
    "comfort_features": "Comfort features: not on record",
    "tech_assist": "Tech and driver-assist features: not on record",
    "space_practicality": "Space: dimensions not on record",
    "performance": "Performance: power and torque not on record",
    "safety": "Safety equipment: not on record",
    "value_for_budget": "Value for money: not enough feature data to compare",
}


def match_label(overall: Optional[float], n_unknown: int, relaxed: bool = False) -> str:
    if overall is None:
        base = "No score"
    elif relaxed:
        base = "Near match"
    else:
        base = config.MATCH_FLOOR_LABEL
        for threshold, name in config.MATCH_LEVELS:
            if overall >= threshold:
                base = name
                break
    if n_unknown:
        return f"{base} · {n_unknown} thing{'s' if n_unknown != 1 else ''} unknown"
    return base


def _true_features(row: pd.Series, cols) -> List[str]:
    return [c for c in cols if row[c] is True]


def _spec_reason(crit: str, row: pd.Series, value: float, intent: Any) -> Optional[dict]:
    """Template reason for one spec criterion, only from fields present in the row."""
    if crit == "safety":
        parts, fields = [], []
        if not is_unknown(row["safety_stars_adult"]):
            body = row["safety_testing_body"] if not is_unknown(row["safety_testing_body"]) else None
            parts.append(f"{int(row['safety_stars_adult'])}-star adult crash rating" + (f" ({body})" if body else ""))
            fields += ["safety_stars_adult"] + (["safety_testing_body"] if body else [])
        if not is_unknown(row["airbags"]):
            parts.append(f"{int(row['airbags'])} airbags")
            fields.append("airbags")
        if row["esc"] is True:
            parts.append("ESC")
            fields.append("esc")
        return {"text": "Safety: " + ", ".join(parts), "fields": fields} if parts else None
    if crit == "running_cost":
        fuel = row["fuel_type"]
        col, unit = {"cng": ("mileage_km_per_kg", "km/kg"), "electric": ("ev_range_km", "km range")}.get(
            fuel, ("mileage_kmpl", "km/l"))
        v = num(row[col])
        if v is None:
            return None
        pct = int(round(value * 100))
        return {"text": f"Running cost: {v:g} {unit}, ahead of about {pct}% of similar {fuel} cars here",
                "fields": [col, "fuel_type"]}
    if crit == "value_for_budget":
        bmax = ((intent.get("budget") if isinstance(intent, dict) else None) or {}).get("max")
        p = num(row["price_ex_showroom"])
        if p is None:
            return None
        if bmax:
            return {"text": f"Priced at {format_rupees(p)}, {int(round(p / bmax * 100))}% of your {format_rupees(bmax)} budget",
                    "fields": ["price_ex_showroom"]}
        return {"text": f"Priced at {format_rupees(p)} with a good feature count for that money",
                "fields": ["price_ex_showroom"]}
    if crit == "price":
        p = num(row["price_ex_showroom"])
        if p is None:
            return None
        pct = int(round(value * 100))
        cheap = bool(intent.get("cheap_intent") if isinstance(intent, dict) else getattr(intent, "cheap_intent", False))
        lead = "Price prioritised, as you asked: " if cheap else ""
        return {"text": f"{lead}{format_rupees(p)}, cheaper than about {pct}% of similar {row['body_type']} cars here",
                "fields": ["price_ex_showroom", "body_type"]}
    if crit == "comfort_features":
        have = _true_features(row, COMFORT_BOOLS)
        return {"text": "Comfort: " + ", ".join(BOOL_LABELS[c] for c in have), "fields": have} if have else None
    if crit == "tech_assist":
        have = _true_features(row, TECH_BOOLS)
        return {"text": "Tech: " + ", ".join(BOOL_LABELS[c] for c in have), "fields": have} if have else None
    if crit == "space_practicality":
        parts, fields = [], []
        for col, fmt in (("boot_space_litres", "{:g} L boot"), ("wheelbase_mm", "{:g} mm wheelbase"),
                         ("seats", "{:g} seats")):
            v = num(row[col])
            if v is not None:
                parts.append(fmt.format(v))
                fields.append(col)
        return {"text": "Space: " + ", ".join(parts), "fields": fields} if parts else None
    if crit == "performance":
        parts, fields = [], []
        for col, fmt in (("power_bhp", "{:g} bhp"), ("torque_nm", "{:g} Nm")):
            v = num(row[col])
            if v is not None:
                parts.append(fmt.format(v))
                fields.append(col)
        return {"text": "Performance: " + ", ".join(parts), "fields": fields} if parts else None
    return None


def _month_year(text: Optional[str]) -> Optional[str]:
    """'2025-10-27' / '2025-10' -> 'Oct 2025'; anything else (or empty) -> None."""
    try:
        return datetime.strptime(str(text)[:7], "%Y-%m").strftime("%b %Y")
    except (TypeError, ValueError):
        return None


def _review_reason(crit: str, d: dict) -> dict:
    """Reason from a review-file row: the source, its own label, the raw score and (experts) the review date."""
    what = str(d["source_aspect"]).lower()
    raw, top = f"{d['raw_score']:g}", f"{d['scale_max']:g}"
    if crit.startswith("expert_"):
        date = _month_year(d.get("published_on"))
        when = f" ({date})" if date else ""
        if d.get("fallback"):
            text = f"{d['source']} gives an overall score of {raw}/{top}{when}"
        else:
            text = f"{d['source']} scores {what} {raw}/{top}{when}"
        return {"text": text, "evidence_class": "expert", "fields": [crit], "source_url": d["source_url"]}
    score = f"{d['raw_score']:.1f}/{top}"
    n = d.get("rating_count")
    if d.get("low_confidence"):
        basis = "number of ratings not stated" if n is None else f"only {n} rating{'s' if n != 1 else ''}"
        text = f"Owners rate {what} {score}, but on {basis} ({d['source']}, low confidence)"
    else:
        text = f"Owners rate {what} {score} ({d['source']}, {n} ratings)"
    return {"text": text, "evidence_class": "owner", "fields": [crit], "source_url": d["source_url"]}


def _evidence_reason(crit: str, make: str, model: str, value: float, ev: Evidence) -> Optional[dict]:
    d = ev.detail_for(make, model, crit)
    if d is None:
        return None
    if d.get("kind") in ("review", "rating"):
        return _review_reason(crit, d)
    if crit.startswith("expert_"):
        what = criterion_label(crit).split(": ", 1)[1]
        n = d["n_sources"]
        return {"text": f"Experts rate {what} {d['mean_rating']:.1f}/5 ({n} source{'s' if n != 1 else ''})",
                "evidence_class": "expert", "fields": [crit], "source_url": d["source_url"]}
    what = criterion_label(crit).split(": ", 1)[1]
    label = f" ({d['label']})" if d.get("label") else ""
    verb = {"positive": "positively", "negative": "negatively", "mixed": "both ways"}[d["direction"]]
    period = f", {d['period']}" if d.get("period") else ""
    return {"text": f"Owners mention {what}{label} {verb}: {d['mentions']} of {d['posts_sampled']} posts sampled{period}",
            "evidence_class": "owner", "fields": [crit], "source_url": d["source_url"]}


def _item_label(item: str) -> str:
    """Human label of a required item key (feature:x, min_*)."""
    if item.startswith("feature:"):
        return FEATURE_COLUMNS[item.split(":", 1)[1]][1]
    if item in MIN_COLUMNS:
        return MIN_COLUMNS[item][1]
    return "crash rating" if item == "min_safety_stars" else item


def not_verified_labels(row: pd.Series) -> List[str]:
    """Plain labels of the requirements this car passes only because the field is blank, e.g. "ground clearance not
    verified", "sunroof absence not verified" (an excluded feature), "crash rating not verified"."""
    out: List[str] = []
    unverified = row.get("unverified") if hasattr(row, "get") else None
    for u in unverified if isinstance(unverified, list) else []:
        label = str(u).split(": ", 1)[-1]
        out.append(f"{label[3:]} absence not verified" if label.startswith("no ") else f"{label} not verified")
    if bool(row.get("unrated_safety", False)) if hasattr(row, "get") else False:
        out.append("crash rating not verified")
    return list(dict.fromkeys(out))


def unknowns_for(row: pd.Series, score_row: pd.Series, weights: Dict[str, Any], evidence: Evidence) -> List[str]:
    out: List[str] = []
    for item, status in score_row["required"].items():
        if status == "unknown":
            out.append(f"{_item_label(item)[0].upper() + _item_label(item)[1:]}: not confirmed in our data")
    # requirements the car passes only because the field is blank that the score table does not list (excluded
    # features, maximums): the filter's own list
    unverified = row.get("unverified") if hasattr(row, "get") else None
    for u in unverified if isinstance(unverified, list) else []:
        label = str(u).split(": ", 1)[-1]
        out.append(f"{label[0].upper() + label[1:]}: not confirmed in our data")
    if is_unknown(row["safety_stars_adult"]) and weights["criteria"]["safety"]["active"]:
        out.append("Crash rating: not available")
    for crit in score_row["unknown_criteria"]:
        if crit in UNKNOWN_TEXT:
            out.append(UNKNOWN_TEXT[crit])
    has_expert = any(c.startswith("expert_") and v is not None for c, v in score_row["values"].items())
    has_owner = any(c.startswith("owner_") and v is not None for c, v in score_row["values"].items())
    any_expert = any(c.startswith("expert_") for c in score_row["unknown_criteria"]) or has_expert
    any_owner = any(c.startswith("owner_") for c in score_row["unknown_criteria"]) or has_owner
    if any_expert and not has_expert and not evidence.empty:
        out.append("Expert ratings: none for this model yet")
    if any_owner and not has_owner and not evidence.empty:
        out.append("Owner ratings: none for this model yet")
    return list(dict.fromkeys(out))


def explain(row: pd.Series, score_row: pd.Series, weights: Dict[str, Any], intent: Any,
            evidence: Evidence, relaxed: bool = False) -> Dict[str, Any]:
    """{"reasons": [...], "unknowns": [...], "match_label": str, "n_unknown": int}"""
    candidates: List[tuple] = []
    for item, status in score_row["required"].items():
        if status == "met" and item.startswith("feature:"):
            col, label = FEATURE_COLUMNS[item.split(":", 1)[1]]
            candidates.append((1e9, {"text": f"Has {label}, as you asked", "evidence_class": "spec", "fields": [col]}))
    for crit, value in score_row["values"].items():
        if value is None:
            continue
        w = score_row["weights"].get(crit, 0.0)
        if w <= 0 or value < 0.5:
            continue
        if crit in SPEC_LABELS:
            r = _spec_reason(crit, row, value, intent)
            if r:
                r.update(evidence_class="spec", source_url=None)
                cheap = intent.get("cheap_intent") if isinstance(intent, dict) else getattr(intent, "cheap_intent", False)
                # when price was asked for it leads the reasons (after the features the car has)
                candidates.append((5e8 if crit == "price" and cheap else w * value, r))
        else:
            r = _evidence_reason(crit, row["make"], row["model"], value, evidence)
            if r:
                candidates.append((w * value, r))
    candidates.sort(key=lambda t: -t[0])
    # order: up to 2 required features the car meets, then the best expert and owner reason (their per-criterion
    # weights are small, so they would otherwise never show), then everything else by weight x value
    required = [c for c in candidates if c[0] >= 1e9][:2]
    best_expert = next((c for c in candidates if c[1]["evidence_class"] == "expert"), None)
    best_owner = next((c for c in candidates if c[1]["evidence_class"] == "owner"), None)
    head = required + [c for c in (best_expert, best_owner) if c is not None]
    ordered = head + [c for c in candidates if not any(c is h for h in head)]
    # one score can back several criteria (e.g. ride and handling): show it once, listing every field it backs
    merged: Dict[str, dict] = {}
    for _, r in ordered:
        if r["text"] in merged:
            merged[r["text"]]["fields"] = list(dict.fromkeys(merged[r["text"]]["fields"] + r["fields"]))
        else:
            merged[r["text"]] = {"text": r["text"], "evidence_class": r["evidence_class"], "fields": list(r["fields"]),
                                 "source_url": r.get("source_url")}
    reasons = list(merged.values())[:config.MAX_REASONS]
    unknowns = unknowns_for(row, score_row, weights, evidence)
    overall = None if is_unknown(score_row["overall"]) else float(score_row["overall"])
    return {"reasons": reasons, "unknowns": unknowns, "n_unknown": len(unknowns),
            "match_label": match_label(overall, len(unknowns), relaxed)}
