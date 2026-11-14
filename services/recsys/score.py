"""Overall scoring (plan section 5).

  sub-score(class)  = weighted mean over the KNOWN criteria of that class (weights normalised within
                      the class by weights.py); None when the car has no known criterion in the class.
  overall_raw       = sum(CLASS_WEIGHTS[c] x sub[c]) / sum(CLASS_WEIGHTS[c]) over classes whose sub is not None.
  unknown_share     = (weight of unknown criteria + REQUIRED_ITEM_WEIGHT x unknown required items)
                      / (1 + REQUIRED_ITEM_WEIGHT x number of required items),
                      where criterion weights are CLASS_WEIGHTS x within-class weight, renormalised to 1
                      over the *active* classes only (classes with a known value for at least one car in
                      the candidate set; an empty review file therefore penalises nobody).
                      A required item known to be missing (possible only in relaxed results) counts
                      MISSING_MULTIPLIER times as an unknown one, so a blank never beats a known "no".
                      Inside a known criterion, the share of its field weight that is unknown (criteria.py
                      unknown_frac; e.g. no crash rating = 3 of 10 safety weight) times the criterion weight
                      is added too, so partial gaps are not free.
  overall           = overall_raw x (1 - COVERAGE_PENALTY x unknown_share)
No brand or model bonuses anywhere. A required feature that is unknown keeps the car in and flags it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.filter_v2 import FEATURE_COLUMNS, MIN_COLUMNS
from services.recsys import config
from services.recsys.common import is_unknown, num
from services.recsys.criteria import SPEC_CRITERIA, CriteriaResult, compute_criteria
from services.recsys.evidence import EXPERT_CRITERIA, OWNER_CRITERIA, Evidence, get_evidence
from services.recsys.weights import ALL_CRITERIA, CRITERION_CLASS, build_weights

CLASSES = ["spec", "expert", "owner"]
KMPL_UNTRUSTED_FUELS = {"cng"}  # a CNG row's kmpl cell is a km/kg figure: unknown as kmpl


def _intent_get(intent: Any, key: str, default: Any = None) -> Any:
    v = intent.get(key, default) if isinstance(intent, dict) else getattr(intent, key, default)
    return default if v is None else v


def required_items(row: pd.Series, intent: Any) -> Dict[str, str]:
    """{item: "met" | "unknown" | "missing"} for every required feature / minimum in the intent."""
    items: Dict[str, str] = {}
    unverified_fields = row.get("unverified_fields") if hasattr(row, "get") else None
    unverified_fields = unverified_fields if isinstance(unverified_fields, (set, frozenset)) else frozenset()
    for feature in _intent_get(intent, "required_features", []):
        if feature not in FEATURE_COLUMNS:
            continue
        col = FEATURE_COLUMNS[feature][0]
        v = row[col]
        if is_unknown(v) or col in unverified_fields:
            items[f"feature:{feature}"] = "unknown"
        else:
            items[f"feature:{feature}"] = "met" if v is True else "missing"
    for key, (col, _) in MIN_COLUMNS.items():
        threshold = _intent_get(intent, key)
        if threshold is None:
            continue
        v = num(row[col])
        if key == "min_mileage_kmpl" and row["fuel_type"] in KMPL_UNTRUSTED_FUELS:
            v = None
        items[key] = "unknown" if v is None else ("met" if v >= threshold else "missing")
    stars = _intent_get(intent, "min_safety_stars")
    if stars is not None:
        v = num(row["safety_stars_adult"])
        items["min_safety_stars"] = "unknown" if v is None else ("met" if v >= stars else "missing")
    return items


def active_classes(values: pd.DataFrame, norm_w: Dict[str, float]) -> List[str]:
    """Classes with a known value (and nonzero weight) for at least one car in the set."""
    active = []
    for cls in CLASSES:
        cols = [c for c in values.columns if CRITERION_CLASS[c] == cls and norm_w.get(c, 0) > 0]
        if cols and values[cols].notna().any().any():
            active.append(cls)
    return active


def score_candidates(cands: pd.DataFrame, intent: Any, weights: Optional[Dict[str, Any]] = None,
                     evidence: Optional[Evidence] = None, budget: Optional[dict] = None,
                     criteria: Optional[CriteriaResult] = None, reference: Any = None) -> Tuple[pd.DataFrame, CriteriaResult]:
    """Score every candidate row. Returns (table, criteria result).

    table columns: overall, spec, expert, owner, coverage, unknown_share, values {criterion: value|None},
    weights {criterion: global weight}, required {item: status}, flags [str], unknown_criteria [str].
    Sorted by overall desc then variant_id."""
    weights = weights or build_weights(intent)
    evidence = evidence if evidence is not None else get_evidence()
    budget = budget if budget is not None else _intent_get(intent, "budget", None)
    criteria = criteria or compute_criteria(cands, budget, reference)
    cols = ["overall", "spec", "expert", "owner", "coverage", "unknown_share", "values", "weights",
            "required", "flags", "unknown_criteria", "partial_unknown"]
    if len(cands) == 0:
        return pd.DataFrame(columns=cols), criteria

    values = pd.concat([criteria.values, evidence.values_for(cands)], axis=1)[ALL_CRITERIA]
    norm_w = {c: weights["criteria"][c]["weight"] for c in ALL_CRITERIA}
    active = active_classes(values, norm_w)
    class_share = {c: config.CLASS_WEIGHTS[c] for c in active}
    total_cw = sum(class_share.values()) or 1.0
    global_w = {c: (config.CLASS_WEIGHTS[CRITERION_CLASS[c]] / total_cw) * norm_w[c]
                if CRITERION_CLASS[c] in active else 0.0 for c in ALL_CRITERIA}

    records = []
    for idx, row in cands.iterrows():
        v = values.loc[idx]
        subs: Dict[str, Optional[float]] = {}
        for cls in CLASSES:
            cs = [c for c in ALL_CRITERIA if CRITERION_CLASS[c] == cls and norm_w[c] > 0 and not np.isnan(v[c])]
            wsum = sum(norm_w[c] for c in cs)
            subs[cls] = sum(norm_w[c] * v[c] for c in cs) / wsum if cs and wsum > 0 else None
        used = {c: config.CLASS_WEIGHTS[c] for c in CLASSES if subs[c] is not None}
        raw = sum(used[c] * subs[c] for c in used) / sum(used.values()) if used else None

        unknown_crit = [c for c in ALL_CRITERIA if global_w[c] > 0 and np.isnan(v[c])]
        # partly unknown criteria: {criterion: unknown fraction of its field weight}, only where a value exists
        partial = {}
        if criteria.unknown_frac is not None:
            for c in SPEC_CRITERIA:
                f = criteria.unknown_frac.loc[idx, c]
                if global_w[c] > 0 and not np.isnan(v[c]) and f > 1e-12:
                    partial[c] = float(f)
        unknown_w = sum(global_w[c] for c in unknown_crit) + sum(global_w[c] * f for c, f in partial.items())
        items = required_items(row, intent)
        item_unknown = sum(1.0 if s == "unknown" else config.MISSING_MULTIPLIER if s == "missing" else 0.0
                           for s in items.values())
        r = config.REQUIRED_ITEM_WEIGHT
        unknown_share = (unknown_w + r * item_unknown) / (1.0 + r * len(items))
        unknown_share = min(1.0, unknown_share)
        overall = None if raw is None else raw * (1.0 - config.COVERAGE_PENALTY * unknown_share)

        flags = [f"unknown_required:{k}" for k, s in items.items() if s == "unknown"]
        flags += [f"missing_required:{k}" for k, s in items.items() if s == "missing"]
        if is_unknown(row["safety_stars_adult"]):
            flags.append("unrated_safety")
        records.append({
            "overall": overall, **{c: subs[c] for c in CLASSES},
            "coverage": 1.0 - unknown_share, "unknown_share": unknown_share,
            "values": {c: (None if np.isnan(v[c]) else float(v[c])) for c in ALL_CRITERIA},
            "weights": dict(global_w), "required": items, "flags": flags, "unknown_criteria": unknown_crit,
            "partial_unknown": partial,
        })
    table = pd.DataFrame(records, index=cands.index, columns=cols)
    table["_vid"] = cands["variant_id"].to_numpy()
    table["_o"] = table["overall"].astype(float).fillna(-1.0)
    table = table.sort_values(["_o", "_vid"], ascending=[False, True]).drop(columns=["_o", "_vid"])
    return table, criteria
