"""Per-criterion values in [0, 1] (or unknown) for every candidate row (plan section 5).

Method, stated once:
  * A *field score* is either
      - numeric field  -> mid-rank percentile within the row's segment (same body_type; for
        running_cost the same fuel_type as well, and never across fuel types). A segment with
        fewer than MIN_GROUP_SIZE known values falls back to all candidates (running_cost: all
        candidates of the same fuel). Percentile, not min-max: outliers (a 600 bhp car) would
        squash everyone else under min-max, and percentile needs no hand-set point values.
      - boolean field  -> 1.0 if True, 0.0 if known False. These are absolute (a feature either
        is there or not); relative scaling of a yes/no makes no sense.
      - crash stars    -> stars / 5 when rated (absolute).
  * A *criterion value* is the weighted mean of its KNOWN field scores. It is None only when no
    field is known. A blank is never 0 and never "absent".
  * Every criterion returns its per-field detail (raw value, score, weight) for explanations.

Returns a CriteriaResult: .values (DataFrame, NaN = unknown) and .detail
({index: {criterion: [{field, raw, score, weight, basis}, ...]}}).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.recsys import config
from services.recsys.common import is_unknown, num, pct_rank

SPEC_CRITERIA = [
    "value_for_budget", "safety", "running_cost", "comfort_features",
    "space_practicality", "performance", "tech_assist",
]
SPEC_LABELS = {
    "value_for_budget": "Value for money",
    "safety": "Safety",
    "running_cost": "Running cost",
    "comfort_features": "Comfort features",
    "space_practicality": "Space & practicality",
    "performance": "Performance",
    "tech_assist": "Tech & driver assist",
}

# boolean columns (catalogue name -> weight inside the criterion)
SAFETY_BOOLS = {"esc": 2.0, "abs": 1.0, "tpms": 1.0, "hill_assist": 1.0}
COMFORT_BOOLS = {"auto_climate_control": 2.0, "rear_ac_vents": 2.0, "cruise_control": 1.5,
                 "sunroof": 1.0, "ventilated_front_seats": 1.5}
TECH_BOOLS = {"adas_available": 3.0, "camera_360": 2.0, "connected_car_features": 1.5,
              "wireless_charging": 1.0, "android_auto": 1.0, "apple_carplay": 1.0,
              "heads_up_display": 1.0}
# features that count in the features-per-rupee ratio
VALUE_FEATURES = sorted(set(COMFORT_BOOLS) | set(TECH_BOOLS) | {"esc", "rear_camera", "rear_parking_sensors"})
# gearbox for performance: fixed ordinal (small weight): quick-shifting boxes score higher
GEARBOX_SCORE = {"dct": 1.0, "single_speed_ev": 1.0, "torque_converter": 0.9, "manual": 0.6, "imt": 0.6,
                 "e_cvt": 0.4, "cvt": 0.4, "amt": 0.2}

Field = Tuple[str, pd.Series, pd.Series, float, str]  # name, raw, score (NaN unknown), weight, basis


@dataclass
class CriteriaResult:
    values: pd.DataFrame
    detail: Dict[Any, Dict[str, List[dict]]]


def _bool_score(series: pd.Series) -> pd.Series:
    return series.map(lambda v: np.nan if is_unknown(v) else (1.0 if v is True or v == 1 else 0.0)).astype(float)


def _segment_percentile(values: pd.Series, groups: pd.Series, fallback: pd.Series) -> pd.Series:
    """Percentile of each known value within its group (fallback group when < MIN_GROUP_SIZE known)."""
    values = values.astype(float)
    out = pd.Series(np.nan, index=values.index, dtype=float)
    known = values.notna()
    by_group = {g: values[(groups == g) & known].tolist() for g in groups.unique()}
    by_fb = {g: values[(fallback == g) & known].tolist() for g in fallback.unique()}
    for idx in values.index[known]:
        peers = by_group[groups[idx]]
        if len(peers) < config.MIN_GROUP_SIZE:
            peers = by_fb[fallback[idx]]
        out[idx] = pct_rank(values[idx], peers)
    return out


def _weighted_mean(fields: List[Field], index: pd.Index) -> Tuple[pd.Series, Dict[Any, List[dict]]]:
    """Weighted mean of the known field scores per row, plus the per-row field detail."""
    num_sum = pd.Series(0.0, index=index)
    den = pd.Series(0.0, index=index)
    detail: Dict[Any, List[dict]] = {i: [] for i in index}
    for name, raw, score, weight, basis in fields:
        known = score.notna()
        num_sum[known] += weight * score[known]
        den[known] += weight
        for i in index:
            detail[i].append({
                "field": name,
                "raw": None if is_unknown(raw[i]) else raw[i],
                "score": None if is_unknown(score[i]) else float(score[i]),
                "weight": weight,
                "basis": basis,
            })
    value = (num_sum / den).where(den > 0)
    return value, detail


# ---------------------------------------------------------------------------
# criteria
# ---------------------------------------------------------------------------

def _safety(df: pd.DataFrame, seg: pd.Series, allc: pd.Series) -> List[Field]:
    fields: List[Field] = []
    stars = df["safety_stars_adult"].map(num)
    fields.append(("safety_stars_adult", stars, (stars / 5.0).clip(0, 1), 3.0, "absolute (stars/5); unrated = unknown"))
    airbags = df["airbags"].map(num)
    fields.append(("airbags", airbags, _segment_percentile(airbags, seg, allc), 2.0, "segment percentile"))
    for col, w in SAFETY_BOOLS.items():
        fields.append((col, df[col], _bool_score(df[col]), w, "absolute (has it = 1)"))
    return fields


def _running_cost_column(row) -> Tuple[Optional[str], Optional[float]]:
    fuel = row["fuel_type"]
    if fuel == "cng":
        col = "mileage_km_per_kg"
    elif fuel == "electric":
        col = "ev_range_km"
    elif fuel in ("petrol", "diesel", "hybrid"):
        col = "mileage_kmpl"
    else:
        return None, None
    return col, num(row[col])


def _running_cost(df: pd.DataFrame, fuel_group: pd.Series) -> List[Field]:
    """km/l (petrol/diesel/hybrid), km/kg (CNG), range (EV): percentile inside the same fuel only.
    Segment = body_type + fuel_type; fallback = same fuel_type across all candidates; never other fuels."""
    cols, raw = [], []
    for _, row in df.iterrows():
        c, v = _running_cost_column(row)
        cols.append(c)
        raw.append(v)
    raw_s = pd.Series(raw, index=df.index, dtype=float)
    seg = df["body_type"].astype(str) + "|" + df["fuel_type"].astype(str)
    score = _segment_percentile(raw_s, seg, fuel_group)
    named = pd.Series([c or "mileage_kmpl" for c in cols], index=df.index)
    # field name differs per fuel, so keep one field per distinct column
    fields: List[Field] = []
    for col in ("mileage_kmpl", "mileage_km_per_kg", "ev_range_km"):
        mask = named == col
        if mask.any():
            fields.append((col, raw_s.where(mask), score.where(mask), 1.0, "percentile within same fuel type"))
    return fields


def _comfort(df: pd.DataFrame) -> List[Field]:
    return [(c, df[c], _bool_score(df[c]), w, "absolute (has it = 1)") for c, w in COMFORT_BOOLS.items()]


def _tech(df: pd.DataFrame) -> List[Field]:
    return [(c, df[c], _bool_score(df[c]), w, "absolute (has it = 1)") for c, w in TECH_BOOLS.items()]


def _space(df: pd.DataFrame, seg: pd.Series, allc: pd.Series) -> List[Field]:
    fields: List[Field] = []
    for col, w in (("boot_space_litres", 2.0), ("wheelbase_mm", 2.0), ("seats", 1.0), ("ground_clearance_mm", 1.0)):
        raw = df[col].map(num)
        fields.append((col, raw, _segment_percentile(raw, seg, allc), w, "segment percentile"))
    return fields


def _performance(df: pd.DataFrame, seg: pd.Series, allc: pd.Series) -> List[Field]:
    power = df["power_bhp"].map(num)
    weight = df["kerb_weight_kg"].map(num)
    p2w = (power / weight * 1000.0).where(power.notna() & weight.notna())  # bhp per tonne
    p2w_score = _segment_percentile(p2w, seg, allc)
    # when kerb weight is unknown fall back to raw power, so a missing weight does not hide the car's power
    power_only = power.where(p2w.isna())
    torque = df["torque_nm"].map(num)
    gear = df["transmission_type"].map(lambda t: GEARBOX_SCORE.get(t, np.nan) if not is_unknown(t) else np.nan)
    return [
        ("power_to_weight_bhp_per_tonne", p2w, p2w_score, 3.0, "segment percentile"),
        ("power_bhp", power_only, _segment_percentile(power_only, seg, allc), 3.0, "segment percentile (weight unknown)"),
        ("torque_nm", torque, _segment_percentile(torque, seg, allc), 2.0, "segment percentile"),
        ("transmission_type", df["transmission_type"], gear.astype(float), 1.0, "fixed ordinal by gearbox type"),
    ]


def budget_fit(price: Optional[float], budget_max: Optional[float]) -> Optional[float]:
    """How the price sits inside a stated maximum budget. Not a 'cheaper is better' score:
    price/max >= 0.70 uses the budget fully (1.0); below that it falls linearly to a floor of 0.5, so a
    car far under budget is never better than one that fills it; over budget (relaxed results) loses
    BUDGET_OVER_SLOPE per 100% over."""
    if price is None or budget_max is None or budget_max <= 0:
        return None
    r = price / budget_max
    if r > 1.0:
        return max(0.0, 1.0 - config.BUDGET_OVER_SLOPE * (r - 1.0))
    if r >= config.BUDGET_FULL_FIT_FROM:
        return 1.0
    return config.BUDGET_FIT_FLOOR + (1.0 - config.BUDGET_FIT_FLOOR) * (r / config.BUDGET_FULL_FIT_FROM)


def _value(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, budget: Optional[dict]) -> List[Field]:
    price = df["price_ex_showroom"].map(num)
    fields: List[Field] = []
    bmax = (budget or {}).get("max")
    if bmax is not None:
        fit = price.map(lambda p: np.nan if is_unknown(p) else budget_fit(p, bmax))
        fields.append(("price_vs_budget", price, fit.astype(float), 1.0, "price / stated maximum budget"))
    # features per rupee: known-true count per lakh, only when enough feature cells are known
    present = [c for c in VALUE_FEATURES if c in df.columns]
    flags = df[present].apply(lambda col: col.map(lambda v: np.nan if is_unknown(v) else (1.0 if v is True else 0.0)))
    known_share = flags.notna().mean(axis=1)
    true_count = flags.fillna(0.0).sum(axis=1)
    fpr = (true_count / (price / 100000.0)).where(price.notna() & (price > 0) & (known_share >= config.MIN_FEATURE_KNOWN_SHARE))
    fields.append(("features_per_lakh", fpr, _segment_percentile(fpr, seg, allc), 1.0, "segment percentile"))
    return fields


def compute_criteria(df: pd.DataFrame, budget: Optional[dict] = None) -> CriteriaResult:
    """Spec criteria for every row of `df` (the comparison set = these candidates)."""
    index = df.index
    if len(df) == 0:
        return CriteriaResult(pd.DataFrame(columns=SPEC_CRITERIA, dtype=float), {})
    seg = df["body_type"].astype(str)
    allc = pd.Series("all", index=index)
    fuel_group = df["fuel_type"].astype(str)

    builders: Dict[str, List[Field]] = {
        "value_for_budget": _value(df, seg, allc, budget),
        "safety": _safety(df, seg, allc),
        "running_cost": _running_cost(df, fuel_group),
        "comfort_features": _comfort(df),
        "space_practicality": _space(df, seg, allc),
        "performance": _performance(df, seg, allc),
        "tech_assist": _tech(df),
    }
    values = pd.DataFrame(index=index, columns=SPEC_CRITERIA, dtype=float)
    detail: Dict[Any, Dict[str, List[dict]]] = {i: {} for i in index}
    for crit in SPEC_CRITERIA:
        value, per_row = _weighted_mean(builders[crit], index)
        values[crit] = value
        for i in index:
            detail[i][crit] = per_row[i]
    return CriteriaResult(values, detail)
