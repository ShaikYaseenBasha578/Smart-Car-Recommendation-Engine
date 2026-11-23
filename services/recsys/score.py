"""Overall scoring (plan section 5).

  sub-score(class)  = weighted mean over the criteria of that class (weights normalised within the class by
                      weights.py); a spec criterion with blank fields is valued with the blank priors
                      (criteria.py, config.BLANK_PRIOR_*), including one whose fields are all blank; None when the
                      car has no criterion with a value in the class.
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
Review classes (2026-11-15): the expert / owner sub-score is computed from the evidence (Evidence.class_sub): each aspect
counts in proportion to the query weight of the spec criteria it maps to (aspects with no weight not at all; a query with
no preference uses only the overall rows), aspects one source label feeds count once. A model with no row in a class
takes the segment mean of the reviewed models' sub-score and class scale (Evidence.neutral_class), so being reviewed is
not rewarded in itself; its unknown criteria still feed the coverage factor and no score is shown.
Thin evidence counts for less (class_weights below): per car the expert / owner class weight (after redistribution
over the classes the car has) is multiplied by Evidence.expert_scale / owner_scale (config EXPERT_SOURCE_K,
OWNER_SAMPLE_K) and the freed weight goes to the spec class, so the class weights of a car always sum to 1. A car with
no evidence in a class has that class redistributed as before; a car with no expert/owner evidence is unchanged.
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
from services.recsys.evidence import ASPECTS, EXPERT_CRITERIA, OWNER_CRITERIA, Evidence, get_evidence
from services.recsys.weights import ALL_CRITERIA, CRITERION_CLASS, build_weights, review_aspect_weights

CLASSES = ["spec", "expert", "owner"]
KMPL_UNTRUSTED_FUELS = {"cng"}  # a CNG row's kmpl cell is a km/kg figure: unknown as kmpl


def _intent_get(intent: Any, key: str, default: Any = None) -> Any:
    v = intent.get(key, default) if isinstance(intent, dict) else getattr(intent, key, default)
    return default if v is None else v


def _required_plan(intent: Any) -> Tuple[List[str], List[Tuple[str, str, float]], Any]:
    """What `intent` requires, read once per query: ([feature names that have a column], [(key, column, threshold)] for
    the minimums that are set, min_safety_stars or None). required_items applies it to a row."""
    feats = [f for f in _intent_get(intent, "required_features", []) if f in FEATURE_COLUMNS]
    mins = []
    for key, (col, _) in MIN_COLUMNS.items():
        threshold = _intent_get(intent, key)
        if threshold is not None:
            mins.append((key, col, threshold))
    return feats, mins, _intent_get(intent, "min_safety_stars")


def _items_for(plan: Tuple[List[str], List[Tuple[str, str, float]], Any], val: Any, unverified_fields: Any) -> Dict[str, str]:
    """{item: "met" | "unknown" | "missing"} for one row, `val(column)` giving the row's cell."""
    feats, mins, stars = plan
    items: Dict[str, str] = {}
    for feature in feats:
        col = FEATURE_COLUMNS[feature][0]
        v = val(col)
        if is_unknown(v) or col in unverified_fields:
            items[f"feature:{feature}"] = "unknown"
        else:
            items[f"feature:{feature}"] = "met" if v is True else "missing"
    for key, col, threshold in mins:
        v = num(val(col))
        if key == "min_mileage_kmpl" and val("fuel_type") in KMPL_UNTRUSTED_FUELS:
            v = None
        items[key] = "unknown" if v is None else ("met" if v >= threshold else "missing")
    if stars is not None:
        v = num(val("safety_stars_adult"))
        items["min_safety_stars"] = "unknown" if v is None else ("met" if v >= stars else "missing")
    return items


def required_items(row: pd.Series, intent: Any) -> Dict[str, str]:
    """{item: "met" | "unknown" | "missing"} for every required feature / minimum in the intent."""
    unverified_fields = row.get("unverified_fields") if hasattr(row, "get") else None
    unverified_fields = unverified_fields if isinstance(unverified_fields, (set, frozenset)) else frozenset()
    return _items_for(_required_plan(intent), row.__getitem__, unverified_fields)


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
    weights {criterion: global weight}, required {item: status}, flags [str], unknown_criteria [str], neutral_classes
    [str] (review classes the car has no row in, scored at the segment mean: never shown as its own score).
    Sorted by overall desc then variant_id."""
    weights = weights or build_weights(intent)
    evidence = evidence if evidence is not None else get_evidence()
    budget = budget if budget is not None else _intent_get(intent, "budget", None)
    # cheap wording and no body type named: candidates span segments, so price is ranked across the whole catalogue
    cheap_across = bool(_intent_get(intent, "cheap_intent", False)) and not _intent_get(intent, "body_types", [])
    criteria = criteria or compute_criteria(cands, budget, reference, price_whole_catalogue=cheap_across)
    cols = ["overall", "spec", "expert", "owner", "coverage", "unknown_share", "values", "weights",
            "required", "flags", "unknown_criteria", "partial_unknown", "class_weights", "neutral_classes"]
    if len(cands) == 0:
        return pd.DataFrame(columns=cols), criteria

    values = pd.concat([criteria.values, evidence.values_for(cands)], axis=1)[ALL_CRITERIA]
    # what the sub-scores are computed from: the same, plus the blank priors of the spec criteria (a criterion whose
    # fields are all blank is still unknown in `values`, but is scored at its prior, never dropped from the mean)
    scoring = values.copy()
    if criteria.scoring is not None:
        scoring[SPEC_CRITERIA] = criteria.scoring[SPEC_CRITERIA].reindex(values.index)
    norm_w = {c: weights["criteria"][c]["weight"] for c in ALL_CRITERIA}
    active = active_classes(values, norm_w)
    class_share = {c: config.CLASS_WEIGHTS[c] for c in active}
    total_cw = sum(class_share.values()) or 1.0
    global_w = {c: (config.CLASS_WEIGHTS[CRITERION_CLASS[c]] / total_cw) * norm_w[c]
                if CRITERION_CLASS[c] in active else 0.0 for c in ALL_CRITERIA}

    # how the review classes are scored (weights.review_aspect_weights): None = no preference, overall rows only;
    # else {aspect: query weight}. The aspects that count for the thin-evidence scale are the ones with weight.
    aw = review_aspect_weights(weights)
    relevant_aspects = [config.EXPERT_OVERALL_ASPECT] if aw["expert"] is None else [a for a in ASPECTS if a in aw["expert"]]

    # one model has many variants: the evidence lookups depend only on (make, model[, body type]), so each is made once
    memo: Dict[tuple, Any] = {}

    def once(key: tuple, fn):
        if key not in memo:
            memo[key] = fn()
        return memo[key]

    # The per-row loop below ran on iterrows() and dict-of-dicts (a Series built per row, ~0.3 s for the whole catalogue).
    # It now reads plain lists / arrays taken from the frame once; every per-row number is computed by the same
    # operations in the same order.
    n = len(cands)
    nan_mat = values[ALL_CRITERIA].to_numpy(dtype=float)
    scoring_mat = scoring[ALL_CRITERIA].to_numpy(dtype=float)
    col_pos = {c: j for j, c in enumerate(ALL_CRITERIA)}

    def class_subs(cls: str) -> List[Optional[float]]:
        """sub-score of one class for every row: sum(w x value) / sum(w) over the criteria of the class with a value.
        Accumulated column by column in ALL_CRITERIA order (adding 0.0 where a criterion is NaN changes nothing), which is
        the order and the float arithmetic of the sequential sum() it replaces."""
        mat = scoring_mat if cls in active else nan_mat
        num_acc = np.zeros(n)
        w_acc = np.zeros(n)
        any_cs = np.zeros(n, dtype=bool)
        for c in ALL_CRITERIA:
            if CRITERION_CLASS[c] == cls and norm_w[c] > 0:
                x = mat[:, col_pos[c]]
                known = ~np.isnan(x)
                num_acc += np.where(known, norm_w[c] * np.where(known, x, 0.0), 0.0)
                w_acc += np.where(known, norm_w[c], 0.0)
                any_cs |= known
        ok = any_cs & (w_acc > 0)
        out = np.divide(num_acc, w_acc, out=np.zeros(n), where=ok)
        return [float(v) if k else None for v, k in zip(out.tolist(), ok.tolist())]

    class_sub_rows = {cls: class_subs(cls) for cls in CLASSES}
    makes, models = cands["make"].tolist(), cands["model"].tolist()
    body_types = cands["body_type"].tolist()
    stars_col = cands["safety_stars_adult"].tolist()
    plan = _required_plan(intent)
    plan_cols = {c: cands[c].to_numpy(dtype=object) for c in
                 ([FEATURE_COLUMNS[f][0] for f in plan[0]] + [col for _, col, _ in plan[1]]
                  + (["fuel_type"] if any(k == "min_mileage_kmpl" for k, _, _ in plan[1]) else [])
                  + (["safety_stars_adult"] if plan[2] is not None else []))}
    unverified_col = cands["unverified_fields"].tolist() if "unverified_fields" in cands.columns else None
    nan_rows = np.isnan(nan_mat).tolist()
    value_rows = nan_mat.tolist()
    unknown_cols = [c for c in ALL_CRITERIA if global_w[c] > 0]
    spec_pos = [(c, col_pos[c]) for c in SPEC_CRITERIA if global_w[c] > 0]
    unknown_frac_mat = (criteria.unknown_frac[SPEC_CRITERIA].to_numpy(dtype=float).tolist()
                        if criteria.unknown_frac is not None else None)
    spec_col = {c: j for j, c in enumerate(SPEC_CRITERIA)}
    records = []
    for k in range(n):
        subs: Dict[str, Optional[float]] = {cls: class_sub_rows[cls][k] for cls in CLASSES}
        make, model = makes[k], models[k]
        # expert / owner sub-scores come from the evidence directly: aspects weighted by the query, one source label
        # counted once, and a model with no row in the class takes the segment mean of the reviewed models
        scale_override: Dict[str, float] = {}
        for cls in ("expert", "owner"):
            if cls not in active:
                continue
            sub = once(("sub", cls, make, model),
                       lambda: evidence.class_sub(cls, make, model, aw[cls]))
            if sub is None:
                neutral = once(("neutral", cls, str(body_types[k])),
                               lambda: evidence.neutral_class(cls, str(body_types[k]), aw[cls],
                                                              relevant_aspects if cls == "expert" else []))
                sub, scale_override[cls] = neutral if neutral is not None else (None, None)
            if cls == "owner" and sub is not None:   # themes: a capped adjustment, 0 for a model with none
                sub = min(1.0, max(0.0, sub + once(("theme", model),
                                                   lambda: evidence.theme_adjustment(model, aw["owner"]))))
            subs[cls] = sub
        used = {c: config.CLASS_WEIGHTS[c] for c in CLASSES if subs[c] is not None}
        cw = {c: used[c] / sum(used.values()) for c in used}
        if subs["spec"] is not None and len(used) > 1:
            scale = {"expert": scale_override["expert"] if "expert" in scale_override
                     else once(("escale", make, model),
                               lambda: evidence.expert_scale(make, model, relevant_aspects)),
                     "owner": scale_override["owner"] if "owner" in scale_override
                     else once(("oscale", make, model),
                               lambda: evidence.owner_scale(make, model))}
            for c in ("expert", "owner"):
                if c in cw:
                    cw[c] *= 1.0 if scale[c] is None else scale[c]
            cw["spec"] = 1.0 - sum(v for c, v in cw.items() if c != "spec")
        if list(used) == ["spec"]:
            raw = subs["spec"]
        else:
            raw = sum(cw[c] * subs[c] for c in cw) if used else None

        nan_k = nan_rows[k]
        unknown_crit = [c for c in unknown_cols if nan_k[col_pos[c]]]
        # partly unknown criteria: {criterion: unknown fraction of its field weight}, only where a value exists
        partial = {}
        if unknown_frac_mat is not None:
            uf = unknown_frac_mat[k]
            for c, j in spec_pos:
                f = uf[spec_col[c]]
                if not nan_k[j] and f > 1e-12:
                    partial[c] = float(f)
        unknown_w = sum(global_w[c] for c in unknown_crit) + sum(global_w[c] * f for c, f in partial.items())
        uf_fields = unverified_col[k] if unverified_col is not None else None
        items = _items_for(plan, (lambda col, k=k: plan_cols[col][k]),
                           uf_fields if isinstance(uf_fields, (set, frozenset)) else frozenset())
        item_unknown = sum(1.0 if s == "unknown" else config.MISSING_MULTIPLIER if s == "missing" else 0.0
                           for s in items.values())
        r = config.REQUIRED_ITEM_WEIGHT
        unknown_share = (unknown_w + r * item_unknown) / (1.0 + r * len(items))
        unknown_share = min(1.0, unknown_share)
        overall = None if raw is None else raw * (1.0 - config.COVERAGE_PENALTY * unknown_share)

        flags = [f"unknown_required:{key}" for key, s in items.items() if s == "unknown"]
        flags += [f"missing_required:{key}" for key, s in items.items() if s == "missing"]
        if is_unknown(stars_col[k]):
            flags.append("unrated_safety")
        vals_k = value_rows[k]
        records.append({
            "overall": overall, **{c: subs[c] for c in CLASSES},
            "coverage": 1.0 - unknown_share, "unknown_share": unknown_share,
            "values": {c: (None if nan_k[j] else float(vals_k[j])) for c, j in col_pos.items()},
            "weights": dict(global_w), "required": items, "flags": flags, "unknown_criteria": unknown_crit,
            "partial_unknown": partial, "class_weights": cw, "neutral_classes": sorted(scale_override),
        })
    table = pd.DataFrame(records, index=cands.index, columns=cols)
    table["_vid"] = cands["variant_id"].to_numpy()
    table["_o"] = table["overall"].astype(float).fillna(-1.0)
    table = table.sort_values(["_o", "_vid"], ascending=[False, True]).drop(columns=["_o", "_vid"])
    return table, criteria
