"""Per-criterion values in [0, 1] (or unknown) for every candidate row (plan section 5).

Method, stated once:
  * A *field score* is either
      - numeric field  -> mid-rank percentile in a REFERENCE population: the same body_type over the whole
        catalogue (running_cost: the same body_type and fuel_type; never across fuel types), built once
        per catalogue load (Reference), cached, and used for every query, so a variant's score does not
        move when a filter is added. The population has one entry per model per distinct value, each model
        weighing 1 in total, so a model with 40 variants does not dominate. A segment with fewer than
        MIN_SEGMENT_MODELS models with a known value falls back to the whole catalogue (running_cost: all
        models of the same fuel). Percentile, not min-max: outliers (a 600 bhp car) would squash
        everyone else under min-max, and percentile needs no hand-set point values.
      - boolean field  -> 1.0 if True, 0.0 if known False. These are absolute (a feature either
        is there or not); relative scaling of a yes/no makes no sense.
      - crash stars    -> stars / 5 when rated (absolute).
  * A *criterion value* is the weighted mean of its KNOWN field scores. It is None only when no
    field is known. A blank is never 0 and never "absent". Each criterion also returns its
    *unknown fraction*: the share of its applicable field weight that is unknown for the row. score.py
    adds (unknown fraction x criterion weight) to the unknown weight behind the coverage factor, so a
    car with a missing crash rating is not ranked above an otherwise identical rated car.
  * Every criterion returns its per-field detail (raw value, score, weight) for explanations.

Returns a CriteriaResult: .values (DataFrame, NaN = unknown), .unknown_frac (DataFrame in [0, 1]; 1 where
the whole criterion is unknown) and .detail
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

# name, raw, score (NaN unknown), weight, basis, applicable (None = every row). A field that does not apply to
# a row (e.g. the km/kg field of a petrol car) is neither known nor unknown for it.
Field = Tuple[str, pd.Series, pd.Series, float, str, Optional[pd.Series]]


@dataclass
class CriteriaResult:
    values: pd.DataFrame
    detail: Dict[Any, Dict[str, List[dict]]]
    unknown_frac: Optional[pd.DataFrame] = None


def _bool_score(series: pd.Series) -> pd.Series:
    return series.map(lambda v: np.nan if is_unknown(v) else (1.0 if v is True or v == 1 else 0.0)).astype(float)


class _Pop:
    """Weighted sorted values of one reference group (one weight-1 share per model)."""

    def __init__(self, values: np.ndarray, weights: np.ndarray, n_models: int):
        order = np.argsort(values, kind="stable")
        self.values = values[order]
        self.cum = np.concatenate([[0.0], np.cumsum(weights[order])])
        self.total = float(self.cum[-1])
        self.n_models = n_models

    def rank(self, x: np.ndarray) -> np.ndarray:
        """Mid-rank percentile: (weight below + half the weight equal) / total weight."""
        if self.total <= 0:
            return np.full(len(x), 0.5)
        lo = np.searchsorted(self.values, x, side="left")
        hi = np.searchsorted(self.values, x, side="right")
        return (self.cum[lo] + 0.5 * (self.cum[hi] - self.cum[lo])) / self.total


def _make_pops(raw: pd.Series, groups: pd.Series, models: pd.Series) -> Dict[Any, _Pop]:
    known = raw.notna()
    frame = pd.DataFrame({"g": groups[known].astype(str), "m": models[known], "v": raw[known].astype(float)})
    frame = frame.drop_duplicates()                     # one entry per model per distinct value
    frame["w"] = 1.0 / frame.groupby(["g", "m"])["v"].transform("size")   # every model weighs 1 in total
    return {g: _Pop(sub["v"].to_numpy(), sub["w"].to_numpy(), int(sub["m"].nunique()))
            for g, sub in frame.groupby("g")}


def _fpr(df: pd.DataFrame) -> pd.Series:
    """Known-true feature count per lakh of price, only when enough feature cells are known."""
    price = df["price_ex_showroom"].map(num)
    present = [c for c in VALUE_FEATURES if c in df.columns]
    flags = df[present].apply(lambda col: col.map(lambda v: np.nan if is_unknown(v) else (1.0 if v is True else 0.0)))
    known_share = flags.notna().mean(axis=1)
    true_count = flags.fillna(0.0).sum(axis=1)
    return (true_count / (price / 100000.0)).where(price.notna() & (price > 0) & (known_share >= config.MIN_FEATURE_KNOWN_SHARE))


def _running_cost_raw(df: pd.DataFrame) -> Tuple[List[Optional[str]], pd.Series]:
    cols, raw = [], []
    for _, row in df.iterrows():
        c, v = _running_cost_column(row)
        cols.append(c)
        raw.append(v)
    return cols, pd.Series(raw, index=df.index, dtype=float)


def _p2w(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
    power = df["power_bhp"].map(num)
    weight = df["kerb_weight_kg"].map(num)
    p2w = (power / weight * 1000.0).where(power.notna() & weight.notna())  # bhp per tonne
    # when kerb weight is unknown fall back to raw power, so a missing weight does not hide the car's power
    return power, p2w, power.where(p2w.isna())


def _slot_inputs(df: pd.DataFrame) -> Dict[str, Tuple[pd.Series, pd.Series, pd.Series]]:
    """{slot: (raw values, segment group, fallback group)} for every percentile-scored field."""
    seg = df["body_type"].astype(str)
    allc = pd.Series("all", index=df.index)
    out = {}
    for col in ("airbags", "boot_space_litres", "wheelbase_mm", "seats", "ground_clearance_mm", "torque_nm"):
        out[col] = (df[col].map(num).astype(float), seg, allc)
    _, p2w, power_only = _p2w(df)
    out["p2w"], out["power_only"] = (p2w, seg, allc), (power_only, seg, allc)
    out["fpr"] = (_fpr(df), seg, allc)
    _, rc_raw = _running_cost_raw(df)
    out["running_cost"] = (rc_raw, seg + "|" + df["fuel_type"].astype(str), df["fuel_type"].astype(str))
    return out


class Reference:
    """Percentile reference populations, per slot and segment (plan section 5: relative to the segment).

    Built once from the full catalogue and reused for every query; see the module docstring."""

    def __init__(self, df: pd.DataFrame):
        models = df["make"].astype(str) + " " + df["model"].astype(str)
        self.pops: Dict[str, Dict[str, Dict[Any, _Pop]]] = {}
        for slot, (raw, seg, fb) in _slot_inputs(df).items():
            self.pops[slot] = {"seg": _make_pops(raw, seg, models), "fb": _make_pops(raw, fb, models)}

    def percentile(self, slot: str, values: pd.Series, groups: pd.Series, fallback: pd.Series) -> pd.Series:
        """Percentile of each known value in its segment population (fallback population when the segment has
        fewer than MIN_SEGMENT_MODELS models); NaN stays NaN."""
        values = values.astype(float)
        out = pd.Series(np.nan, index=values.index, dtype=float)
        known = values.notna()
        if not known.any():
            return out
        pops = self.pops[slot]
        frame = pd.DataFrame({"v": values[known], "g": groups[known].astype(str), "f": fallback[known].astype(str)})
        for (g, f), sub in frame.groupby(["g", "f"]):
            pop = pops["seg"].get(g)
            if pop is None or pop.n_models < config.MIN_SEGMENT_MODELS:
                pop = pops["fb"].get(f)
            out[sub.index] = pop.rank(sub["v"].to_numpy()) if pop is not None else 0.5
        return out


_REFERENCE_CACHE: Dict[int, Tuple[pd.DataFrame, Reference]] = {}


def catalogue_reference(catalogue: pd.DataFrame) -> Reference:
    """The Reference of a catalogue frame, built on first use and cached (one build per catalogue load)."""
    hit = _REFERENCE_CACHE.get(id(catalogue))
    if hit is None or hit[0] is not catalogue:
        hit = (catalogue, Reference(catalogue))
        _REFERENCE_CACHE[id(catalogue)] = hit
    return hit[1]


def _weighted_mean(fields: List[Field], index: pd.Index) -> Tuple[pd.Series, pd.Series, Dict[Any, List[dict]]]:
    """Weighted mean of the known field scores per row, the unknown fraction (unknown share of the applicable
    field weight), and the per-row field detail."""
    num_sum = pd.Series(0.0, index=index)
    den = pd.Series(0.0, index=index)
    applicable_w = pd.Series(0.0, index=index)
    detail: Dict[Any, List[dict]] = {i: [] for i in index}
    for name, raw, score, weight, basis, applicable in fields:
        known = score.notna()
        applies = pd.Series(True, index=index) if applicable is None else applicable.astype(bool)
        known = known & applies
        num_sum[known] += weight * score[known]
        den[known] += weight
        applicable_w[applies] += weight
        for i in index:
            detail[i].append({
                "field": name,
                "raw": None if is_unknown(raw[i]) else raw[i],
                "score": None if is_unknown(score[i]) else float(score[i]),
                "weight": weight,
                "basis": basis,
            })
    value = (num_sum / den).where(den > 0)
    unknown_frac = (1.0 - den / applicable_w).where(applicable_w > 0, 1.0).where(den > 0, 1.0).clip(0.0, 1.0)
    return value, unknown_frac, detail


# ---------------------------------------------------------------------------
# criteria
# ---------------------------------------------------------------------------

def _safety(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    fields: List[Field] = []
    stars = df["safety_stars_adult"].map(num)
    fields.append(("safety_stars_adult", stars, (stars / 5.0).clip(0, 1), 3.0, "absolute (stars/5); unrated = unknown", None))
    airbags = df["airbags"].map(num)
    fields.append(("airbags", airbags, ref.percentile("airbags", airbags, seg, allc), 2.0, "segment percentile", None))
    for col, w in SAFETY_BOOLS.items():
        fields.append((col, df[col], _bool_score(df[col]), w, "absolute (has it = 1)", None))
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


def _running_cost(df: pd.DataFrame, ref: Reference) -> List[Field]:
    """km/l (petrol/diesel/hybrid), km/kg (CNG), range (EV): percentile inside the same fuel only.
    Segment = body_type + fuel_type; fallback = same fuel_type across the catalogue; never other fuels."""
    cols, raw_s = _running_cost_raw(df)
    inputs = _slot_inputs_rc(df)
    score = ref.percentile("running_cost", raw_s, *inputs)
    named = pd.Series([c or "mileage_kmpl" for c in cols], index=df.index)
    # field name differs per fuel, so keep one field per distinct column
    fields: List[Field] = []
    for col in ("mileage_kmpl", "mileage_km_per_kg", "ev_range_km"):
        mask = named == col
        if mask.any():
            fields.append((col, raw_s.where(mask), score.where(mask), 1.0, "percentile within same fuel type", mask))
    return fields


def _slot_inputs_rc(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return df["body_type"].astype(str) + "|" + df["fuel_type"].astype(str), df["fuel_type"].astype(str)


def _comfort(df: pd.DataFrame) -> List[Field]:
    return [(c, df[c], _bool_score(df[c]), w, "absolute (has it = 1)", None) for c, w in COMFORT_BOOLS.items()]


def _tech(df: pd.DataFrame) -> List[Field]:
    return [(c, df[c], _bool_score(df[c]), w, "absolute (has it = 1)", None) for c, w in TECH_BOOLS.items()]


def _space(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    fields: List[Field] = []
    for col, w in (("boot_space_litres", 2.0), ("wheelbase_mm", 2.0), ("seats", 1.0), ("ground_clearance_mm", 1.0)):
        raw = df[col].map(num)
        fields.append((col, raw, ref.percentile(col, raw, seg, allc), w, "segment percentile", None))
    return fields


def _performance(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    power, p2w, power_only = _p2w(df)
    p2w_score = ref.percentile("p2w", p2w, seg, allc)
    torque = df["torque_nm"].map(num)
    gear = df["transmission_type"].map(lambda t: GEARBOX_SCORE.get(t, np.nan) if not is_unknown(t) else np.nan)
    # power-to-weight and raw power are one slot: raw power stands in only when kerb weight is unknown
    p2w_applies = ~(p2w.isna() & power.notna())
    return [
        ("power_to_weight_bhp_per_tonne", p2w, p2w_score, 3.0, "segment percentile", p2w_applies),
        ("power_bhp", power_only, ref.percentile("power_only", power_only, seg, allc), 3.0, "segment percentile (weight unknown)",
         power_only.notna()),
        ("torque_nm", torque, ref.percentile("torque_nm", torque, seg, allc), 2.0, "segment percentile", None),
        ("transmission_type", df["transmission_type"], gear.astype(float), 1.0, "fixed ordinal by gearbox type", None),
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


def _value(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, budget: Optional[dict], ref: Reference) -> List[Field]:
    price = df["price_ex_showroom"].map(num)
    fields: List[Field] = []
    bmax = (budget or {}).get("max")
    if bmax is not None:
        fit = price.map(lambda p: np.nan if is_unknown(p) else budget_fit(p, bmax))
        fields.append(("price_vs_budget", price, fit.astype(float), 1.0, "price / stated maximum budget", None))
    # features per rupee: known-true count per lakh, only when enough feature cells are known
    fpr = _fpr(df)
    fields.append(("features_per_lakh", fpr, ref.percentile("fpr", fpr, seg, allc), 1.0, "segment percentile", None))
    return fields


def compute_criteria(df: pd.DataFrame, budget: Optional[dict] = None,
                     reference: Optional[Reference] = None) -> CriteriaResult:
    """Spec criteria for every row of `df`. Percentiles come from `reference` (the full-catalogue populations;
    api.py always passes it). Without one, the populations are built from `df` itself (hand-built frames)."""
    index = df.index
    if len(df) == 0:
        empty = pd.DataFrame(columns=SPEC_CRITERIA, dtype=float)
        return CriteriaResult(empty, {}, empty.copy())
    seg = df["body_type"].astype(str)
    allc = pd.Series("all", index=index)
    ref = reference if reference is not None else Reference(df)

    builders: Dict[str, List[Field]] = {
        "value_for_budget": _value(df, seg, allc, budget, ref),
        "safety": _safety(df, seg, allc, ref),
        "running_cost": _running_cost(df, ref),
        "comfort_features": _comfort(df),
        "space_practicality": _space(df, seg, allc, ref),
        "performance": _performance(df, seg, allc, ref),
        "tech_assist": _tech(df),
    }
    values = pd.DataFrame(index=index, columns=SPEC_CRITERIA, dtype=float)
    unknown_frac = pd.DataFrame(index=index, columns=SPEC_CRITERIA, dtype=float)
    detail: Dict[Any, Dict[str, List[dict]]] = {i: {} for i in index}
    for crit in SPEC_CRITERIA:
        value, ufrac, per_row = _weighted_mean(builders[crit], index)
        values[crit] = value
        unknown_frac[crit] = ufrac
        for i in index:
            detail[i][crit] = per_row[i]
    return CriteriaResult(values, detail, unknown_frac)
