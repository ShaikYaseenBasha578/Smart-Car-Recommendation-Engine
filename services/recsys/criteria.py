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
      - price          -> 1 - segment percentile of the ex-showroom price (lower is better).
      - crash stars    -> stars / 5 when rated (absolute). Unrated: one star below the segment median of the known
        ratings (floor 3 stars) stands in as a prior (value only; the star still counts as unknown for coverage, nothing shows a rating).
  * A *criterion value* is sum(weight x (known field score, or the blank prior if unknown)) / total applicable
    weight. A blank is never 0 and never "absent": it is valued at a conservative prior (config.BLANK_PRIOR_*:
    per field, the segment median of the known values minus a margin, or for a yes/no feature the segment share
    of True among the known cells times a factor), so a criterion that is mostly blank cannot score near 1.0
    and a wholly blank one cannot beat a weak known value. `values` is NaN where NO field is known (the car's
    criterion is unknown: explanations say so); `scoring` carries the prior-based value there, and score.py uses
    it. A prior is never displayed as a fact (detail carries it as `prior_score`, `score` stays None). Each
    criterion also returns its *unknown fraction*: the share of its applicable field weight that is unknown for
    the row. score.py adds (unknown fraction x criterion weight) to the unknown weight behind the coverage
    factor, so a car with a missing crash rating is not ranked above an otherwise identical rated car.
  * Every criterion returns its per-field detail (raw value, score, weight) for explanations.

Returns a CriteriaResult: .values (DataFrame, NaN = unknown), .unknown_frac (DataFrame in [0, 1]; 1 where
the whole criterion is unknown) and .detail
({index: {criterion: [{field, raw, score, weight, basis}, ...]}}).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.recsys import config
from services.recsys.common import is_unknown, num, pct_rank

SPEC_CRITERIA = [
    "value_for_budget", "safety", "running_cost", "comfort_features",
    "space_practicality", "performance", "tech_assist", "price",
]
SPEC_LABELS = {
    "value_for_budget": "Value for money",
    "safety": "Safety",
    "running_cost": "Running cost",
    "comfort_features": "Comfort features",
    "space_practicality": "Space & practicality",
    "performance": "Performance",
    "tech_assist": "Tech & driver assist",
    "price": "Price (lower is better)",
}

# boolean columns (catalogue name -> weight inside the criterion)
SAFETY_BOOLS = {"esc": 2.0, "abs": 1.0, "tpms": 1.0, "hill_assist": 1.0}
COMFORT_BOOLS = {"auto_climate_control": 2.0, "rear_ac_vents": 2.0, "cruise_control": 1.5,
                 "sunroof": 1.0, "ventilated_front_seats": 1.5}
TECH_BOOLS = {"adas_available": 3.0, "camera_360": 2.0, "connected_car_features": 1.5,
              "wireless_charging": 1.0, "android_auto": 1.0, "apple_carplay": 1.0,
              "heads_up_display": 1.0}
# features that count in the features-per-rupee ratio (a blank counts at its blank prior, see _fpr)
VALUE_FEATURES = sorted(set(COMFORT_BOOLS) | set(TECH_BOOLS) | {"esc", "rear_camera", "rear_parking_sensors"})
# gearbox for performance: fixed ordinal (small weight): quick-shifting boxes score higher
GEARBOX_SCORE = {"dct": 1.0, "single_speed_ev": 1.0, "torque_converter": 0.9, "manual": 0.6, "imt": 0.6,
                 "e_cvt": 0.4, "cvt": 0.4, "amt": 0.2}

# name, raw, score (NaN unknown), weight, basis, applicable (None = every row), prior (rows whose score is a neutral
# prior, not evidence: they feed the criterion value but still count as unknown; None = no prior), blank (the value a
# row's unknown score is valued at, from config.BLANK_PRIOR_*; None = the field drops out when unknown).
# A field that does not apply to a row (e.g. the km/kg field of a petrol car) is neither known nor unknown for it.
Field = Tuple[str, pd.Series, pd.Series, float, str, Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]


@dataclass
class CriteriaResult:
    values: pd.DataFrame                              # NaN where no field of the criterion is known
    detail: Dict[Any, Dict[str, List[dict]]]
    unknown_frac: Optional[pd.DataFrame] = None
    scoring: Optional[pd.DataFrame] = None            # values with the blank priors filled in (what score.py uses)


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

    def median(self) -> float:
        """Weighted (lower) median: the smallest value with at least half the total weight at or below it."""
        i = int(np.searchsorted(self.cum[1:], 0.5 * self.total - 1e-12, side="left"))
        return float(self.values[min(i, len(self.values) - 1)])

    def mean(self) -> float:
        return float(np.dot(self.values, np.diff(self.cum)) / self.total) if self.total > 0 else float("nan")

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


def _fpr(df: pd.DataFrame, ref: "Reference") -> pd.Series:
    """Feature count per lakh of price, only when enough feature cells are known. A known-True cell counts 1, a
    known-False cell 0, and a blank cell counts the same conservative blank prior as in the feature criteria (the
    segment share of True x config.BLANK_PRIOR_BOOL_FACTOR), never 0: a blank is not "absent"."""
    price = df["price_ex_showroom"].map(num)
    present = [c for c in VALUE_FEATURES if c in df.columns]
    flags = df[present].apply(lambda col: col.map(lambda v: np.nan if is_unknown(v) else (1.0 if v is True else 0.0)))
    known_share = flags.notna().mean(axis=1)
    seg, allc = df["body_type"].astype(str), pd.Series("all", index=df.index)
    for c in present:
        flags[c] = flags[c].fillna(ref.blank_prior(f"bool:{c}", "bool", seg, allc))
    count = flags.sum(axis=1)
    return (count / (price / 100000.0)).where(price.notna() & (price > 0) & (known_share >= config.MIN_FEATURE_KNOWN_SHARE))


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
    out["price"] = (df["price_ex_showroom"].map(num).astype(float), seg, allc)
    out["price_all"] = (df["price_ex_showroom"].map(num).astype(float), allc, allc)
    out["stars"] = ((df["safety_stars_adult"].map(num).astype(float) / 5.0).clip(0, 1), seg, allc)
    _, rc_raw = _running_cost_raw(df)
    out["running_cost"] = (rc_raw, seg + "|" + df["fuel_type"].astype(str), df["fuel_type"].astype(str))
    # yes/no features (share of True among the known cells, per segment) and the gearbox ordinal: blank priors only
    for col in sorted(set(SAFETY_BOOLS) | set(COMFORT_BOOLS) | set(TECH_BOOLS) | set(VALUE_FEATURES)):
        out[f"bool:{col}"] = (_bool_score(df[col]), seg, allc)
    out["gear"] = (df["transmission_type"].map(lambda t: GEARBOX_SCORE.get(t, np.nan) if not is_unknown(t) else np.nan
                                              ).astype(float), seg, allc)
    return out


class Reference:
    """Percentile reference populations, per slot and segment (plan section 5: relative to the segment).

    Built once from the full catalogue and reused for every query; see the module docstring."""

    def __init__(self, df: pd.DataFrame):
        self.source = df          # the catalogue this reference was built from (see cached_criteria)
        self._criteria_cache: Dict[bool, "CriteriaResult"] = {}
        self._value_fields: Optional[List[Field]] = None
        models = df["make"].astype(str) + " " + df["model"].astype(str)
        self.pops: Dict[str, Dict[str, Dict[Any, _Pop]]] = {}
        for slot, (raw, seg, fb) in _slot_inputs(df).items():
            self.pops[slot] = {"seg": _make_pops(raw, seg, models), "fb": _make_pops(raw, fb, models)}
        # features per lakh counts blank feature cells at their blank priors, so it is built after the yes/no slots
        seg, allc = df["body_type"].astype(str), pd.Series("all", index=df.index)
        fpr = _fpr(df, self)
        self.pops["fpr"] = {"seg": _make_pops(fpr, seg, models), "fb": _make_pops(fpr, allc, models)}

    def covers(self, df: pd.DataFrame) -> bool:
        """True when every row of `df` is, label for label and value for value, a row of the catalogue this reference
        was built from (a filtered candidate frame). Only then may criteria computed once for the whole catalogue be
        reused: a hand-built or edited frame takes the ordinary path."""
        src = self.source
        if len(df) == 0 or not df.index.is_unique or not df.index.isin(src.index).all():
            return False
        cols = [c for c in df.columns if c in src.columns]
        return bool(df[cols].equals(src.loc[df.index, cols]))

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


    def median(self, slot: str, groups: pd.Series, fallback: pd.Series) -> pd.Series:
        """Median of the known values of the row's segment population (fallback population for a segment with
        fewer than MIN_SEGMENT_MODELS models); NaN when neither population has a value."""
        out = pd.Series(np.nan, index=groups.index, dtype=float)
        pops = self.pops[slot]
        frame = pd.DataFrame({"g": groups.astype(str), "f": fallback.astype(str)})
        for (g, f), sub in frame.groupby(["g", "f"]):
            pop = pops["seg"].get(g)
            if pop is None or pop.n_models < config.MIN_SEGMENT_MODELS:
                pop = pops["fb"].get(f)
            if pop is not None and pop.total > 0:
                out[sub.index] = pop.median()
        return out


    def mean(self, slot: str, groups: pd.Series, fallback: pd.Series) -> pd.Series:
        """Model-weighted mean of the known values of the row's segment population (same fallback as median)."""
        out = pd.Series(np.nan, index=groups.index, dtype=float)
        pops = self.pops[slot]
        frame = pd.DataFrame({"g": groups.astype(str), "f": fallback.astype(str)})
        for (g, f), sub in frame.groupby(["g", "f"]):
            pop = pops["seg"].get(g)
            if pop is None or pop.n_models < config.MIN_SEGMENT_MODELS:
                pop = pops["fb"].get(f)
            if pop is not None and pop.total > 0:
                out[sub.index] = pop.mean()
        return out

    def blank_prior(self, slot: str, kind: str, groups: pd.Series, fallback: pd.Series) -> pd.Series:
        """The value a blank field is valued at (config.BLANK_PRIOR_*), per row, never above the segment's own typical
        known value. kind: "pct" (slot holds raw values, scored as a percentile: percentile of the segment median
        minus the margin), "ord" (slot holds scores: segment median minus the margin) or "bool" (segment share of True
        times the factor). A segment with no known value gets the flat prior."""
        flat = pd.Series(config.BLANK_PRIOR_FLAT, index=groups.index, dtype=float)
        if config.BLANK_PRIOR_MODE == "flat":
            return flat
        if kind == "bool":
            p = self.mean(slot, groups, fallback) * config.BLANK_PRIOR_BOOL_FACTOR
        else:
            med = self.median(slot, groups, fallback)
            base = self.percentile(slot, med, groups, fallback) if kind == "pct" else med
            p = base - config.BLANK_PRIOR_MARGIN
        return p.clip(0.0, 1.0).fillna(flat)


_REFERENCE_CACHE: Dict[int, Tuple[pd.DataFrame, Reference]] = {}


def catalogue_reference(catalogue: pd.DataFrame) -> Reference:
    """The Reference of a catalogue frame, built on first use and cached (one build per catalogue load)."""
    hit = _REFERENCE_CACHE.get(id(catalogue))
    if hit is None or hit[0] is not catalogue:
        hit = (catalogue, Reference(catalogue))
        _REFERENCE_CACHE[id(catalogue)] = hit
    return hit[1]


def _weighted_mean(fields: List[Field], index: pd.Index
                   ) -> Tuple[pd.Series, pd.Series, pd.Series, Dict[Any, List[dict]]]:
    """(criterion value NaN where nothing is known, scoring value with the blank priors, unknown fraction, per-row
    field detail). The scoring value is sum(weight x (known score or blank prior)) / total applicable weight; a
    field with no blank prior (None) drops out of it when unknown. The unknown fraction is the unknown share of
    the applicable field weight, a blank prior or not."""
    num_sum = pd.Series(0.0, index=index)       # known fields and stand-in priors (crash stars)
    den = pd.Series(0.0, index=index)
    blank_num = pd.Series(0.0, index=index)     # blank-prior fields
    blank_den = pd.Series(0.0, index=index)
    applicable_w = pd.Series(0.0, index=index)
    known_den = pd.Series(0.0, index=index)   # weight of fields known from evidence (priors excluded)
    kept = []
    for name, raw, score, weight, basis, applicable, prior, blank in fields:
        applies = pd.Series(True, index=index) if applicable is None else applicable.astype(bool)
        known = score.notna() & applies
        unknown = applies & score.isna()
        is_prior = pd.Series(False, index=index) if prior is None else (prior.astype(bool) & known)
        num_sum[known] += weight * score[known]
        den[known] += weight
        known_den[known & ~is_prior] += weight
        applicable_w[applies] += weight
        blank_used = pd.Series(False, index=index) if blank is None else (unknown & blank.notna())
        if blank is not None:
            blank_num[blank_used] += weight * blank[blank_used]
            blank_den[blank_used] += weight
        kept.append((name, raw, score, weight, basis, is_prior, blank, blank_used))
    total = den + blank_den
    scoring = ((num_sum + blank_num) / total).where(total > 0)
    # a prior alone never makes a criterion known
    value = scoring.where(known_den > 0)
    unknown_frac = (1.0 - known_den / applicable_w).where(applicable_w > 0, 1.0).where(known_den > 0, 1.0).clip(0.0, 1.0)

    def row_detail(i) -> List[dict]:
        """Per-field detail of one row, built on demand (only tests and callers that ask for a row need it)."""
        out = []
        for name, raw, score, weight, basis, is_prior, blank, blank_used in kept:
            stand_in = score[i] if is_prior[i] else (blank[i] if blank_used[i] else None)
            out.append({
                "field": name,
                "raw": None if is_unknown(raw[i]) else raw[i],
                "score": None if is_unknown(score[i]) or is_prior[i] else float(score[i]),
                "weight": weight,
                "basis": basis,
                **({"prior_score": float(stand_in)} if stand_in is not None and not is_unknown(stand_in) else {}),
            })
        return out

    return value, scoring, unknown_frac, row_detail


class LazyDetail(Mapping):
    """{row index: {criterion: [field detail dicts]}}, each row built the first time it is read."""

    def __init__(self, index: pd.Index, makers: Dict[str, Any]):
        self._index = index
        self._makers = makers
        self._cache: Dict[Any, Dict[str, List[dict]]] = {}

    def __getitem__(self, i):
        if i not in self._cache:
            if i not in self._index:
                raise KeyError(i)
            self._cache[i] = {crit: maker(i) for crit, maker in self._makers.items()}
        return self._cache[i]

    def __iter__(self):
        return iter(self._index)

    def __len__(self):
        return len(self._index)


# ---------------------------------------------------------------------------
# criteria
# ---------------------------------------------------------------------------

def _safety(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    fields: List[Field] = []
    stars = df["safety_stars_adult"].map(num).astype(float)
    known = (stars / 5.0).clip(0, 1)
    # unrated: the value in the criterion is the segment median of the known crash ratings (neutral prior), but the
    # star still counts as unknown for the coverage factor, and no rating is shown or implied anywhere
    # prior = ONE STAR BELOW the segment median of known ratings, floored at 3 stars (config), so an unrated car never
    # outranks an otherwise identical rated car at the median
    med = ref.median("stars", seg, allc) * 5.0
    cut = config.CRASH_PRIOR_UNTESTED_DISCOUNT_STARS
    prior_stars = (med - config.CRASH_PRIOR_STARS_BELOW_MEDIAN).clip(lower=config.CRASH_PRIOR_FLOOR_STARS) - cut
    prior = (np.minimum(prior_stars, med - cut).clip(lower=0.0) / 5.0).where(known.isna())
    fields.append(("safety_stars_adult", stars, known.fillna(prior), 3.0,
                   "absolute (stars/5); unrated = one star below the segment median (floor 3), minus a further half star for being untested (always below the median), as a prior, still unknown for coverage",
                   None, prior.notna(), None))
    airbags = df["airbags"].map(num)
    fields.append(("airbags", airbags, ref.percentile("airbags", airbags, seg, allc), 2.0, "segment percentile", None, None,
                   ref.blank_prior("airbags", "pct", seg, allc)))
    for col, w in SAFETY_BOOLS.items():
        fields.append((col, df[col], _bool_score(df[col]), w, "absolute (has it = 1)", None, None,
                       ref.blank_prior(f"bool:{col}", "bool", seg, allc)))
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
    blank = ref.blank_prior("running_cost", "pct", *inputs)
    named = pd.Series([c or "mileage_kmpl" for c in cols], index=df.index)
    # field name differs per fuel, so keep one field per distinct column
    fields: List[Field] = []
    for col in ("mileage_kmpl", "mileage_km_per_kg", "ev_range_km"):
        mask = named == col
        if mask.any():
            fields.append((col, raw_s.where(mask), score.where(mask), 1.0, "percentile within same fuel type", mask, None, blank))
    return fields


def _slot_inputs_rc(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return df["body_type"].astype(str) + "|" + df["fuel_type"].astype(str), df["fuel_type"].astype(str)


def _bool_fields(df: pd.DataFrame, bools: Dict[str, float], seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    return [(c, df[c], _bool_score(df[c]), w, "absolute (has it = 1)", None, None,
             ref.blank_prior(f"bool:{c}", "bool", seg, allc)) for c, w in bools.items()]


def _comfort(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    return _bool_fields(df, COMFORT_BOOLS, seg, allc, ref)


def _tech(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    return _bool_fields(df, TECH_BOOLS, seg, allc, ref)


def _space(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    fields: List[Field] = []
    for col, w in (("boot_space_litres", 2.0), ("wheelbase_mm", 2.0), ("seats", 1.0), ("ground_clearance_mm", 1.0)):
        raw = df[col].map(num)
        fields.append((col, raw, ref.percentile(col, raw, seg, allc), w, "segment percentile", None, None,
                       ref.blank_prior(col, "pct", seg, allc)))
    return fields


def _performance(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference) -> List[Field]:
    power, p2w, power_only = _p2w(df)
    p2w_score = ref.percentile("p2w", p2w, seg, allc)
    torque = df["torque_nm"].map(num)
    gear = df["transmission_type"].map(lambda t: GEARBOX_SCORE.get(t, np.nan) if not is_unknown(t) else np.nan)
    # power-to-weight and raw power are one slot: raw power stands in only when kerb weight is unknown
    p2w_applies = ~(p2w.isna() & power.notna())
    return [
        ("power_to_weight_bhp_per_tonne", p2w, p2w_score, 3.0, "segment percentile", p2w_applies, None,
         ref.blank_prior("p2w", "pct", seg, allc)),
        ("power_bhp", power_only, ref.percentile("power_only", power_only, seg, allc), 3.0, "segment percentile (weight unknown)",
         power_only.notna(), None, None),
        ("torque_nm", torque, ref.percentile("torque_nm", torque, seg, allc), 2.0, "segment percentile", None, None,
         ref.blank_prior("torque_nm", "pct", seg, allc)),
        ("transmission_type", df["transmission_type"], gear.astype(float), 1.0, "fixed ordinal by gearbox type", None, None,
         ref.blank_prior("gear", "ord", seg, allc)),
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
        fields.append(("price_vs_budget", price, fit.astype(float), 1.0, "price / stated maximum budget", None, None, None))
    # features per rupee: known-true count per lakh, only when enough feature cells are known
    fpr = _fpr(df, ref)
    fields.append(("features_per_lakh", fpr, ref.percentile("fpr", fpr, seg, allc), 1.0, "segment percentile", None, None,
                   ref.blank_prior("fpr", "pct", seg, allc)))
    return fields


def _price(df: pd.DataFrame, seg: pd.Series, allc: pd.Series, ref: Reference, whole_catalogue: bool = False) -> List[Field]:
    """Price relative to the car's segment (same reference populations): 1 - percentile, so the cheapest variant
    of a segment scores near 1 and the dearest near 0. Not a budget fit; weights.py decides how much it counts.
    `whole_catalogue` (cheap wording and no body type named, so the candidates span segments): the percentile is
    taken over the whole catalogue, so "cheapest car" ranks by absolute price, not by rank inside each body type."""
    price = df["price_ex_showroom"].map(num).astype(float)
    slot, basis = ("price_all", "whole-catalogue") if whole_catalogue else ("price", "segment")
    return [("price_ex_showroom", price, 1.0 - ref.percentile(slot, price, seg, allc), 1.0,
             f"1 - {basis} percentile of price (lower is better)", None, None, None)]


def _build(df: pd.DataFrame, budget: Optional[dict], ref: Reference, price_whole_catalogue: bool,
           value_fields: Optional[List[Field]] = None) -> CriteriaResult:
    """The criteria of every row of `df` (the work of compute_criteria). `value_fields`, when given, replaces the
    value_for_budget builder (compute_criteria passes the cached budget-free fields, see there)."""
    index = df.index
    seg = df["body_type"].astype(str)
    allc = pd.Series("all", index=index)
    builders: Dict[str, List[Field]] = {
        "value_for_budget": value_fields if value_fields is not None else _value(df, seg, allc, budget, ref),
        "safety": _safety(df, seg, allc, ref),
        "running_cost": _running_cost(df, ref),
        "comfort_features": _comfort(df, seg, allc, ref),
        "space_practicality": _space(df, seg, allc, ref),
        "performance": _performance(df, seg, allc, ref),
        "tech_assist": _tech(df, seg, allc, ref),
        "price": _price(df, seg, allc, ref, price_whole_catalogue),
    }
    return _assemble(index, builders)


def _assemble(index: pd.Index, builders: Dict[str, List[Field]]) -> CriteriaResult:
    values = pd.DataFrame(index=index, columns=SPEC_CRITERIA, dtype=float)
    scoring = pd.DataFrame(index=index, columns=SPEC_CRITERIA, dtype=float)
    unknown_frac = pd.DataFrame(index=index, columns=SPEC_CRITERIA, dtype=float)
    makers: Dict[str, Any] = {}
    for crit in SPEC_CRITERIA:
        value, scored, ufrac, per_row = _weighted_mean(builders[crit], index)
        values[crit] = value
        scoring[crit] = scored
        unknown_frac[crit] = ufrac
        makers[crit] = per_row
    return CriteriaResult(values, LazyDetail(index, makers), unknown_frac, scoring)


def _slice(res: CriteriaResult, index: pd.Index) -> CriteriaResult:
    """The rows `index` of a whole-catalogue result. Every number is computed row by row from that row's own fields
    and the catalogue-wide reference populations, so a row's value does not depend on which other rows are in the frame."""
    return CriteriaResult(res.values.loc[index], LazyDetail(index, res.detail._makers),
                          res.unknown_frac.loc[index], res.scoring.loc[index])


def _cached_criteria(df: pd.DataFrame, budget: Optional[dict], ref: Reference,
                     price_whole_catalogue: bool) -> Optional[CriteriaResult]:
    """compute_criteria for a candidate subset of the reference's catalogue from criteria computed ONCE for the whole
    catalogue (per Reference, i.e. per catalogue load, and per price_whole_catalogue) instead of per query: the
    per-row field scores, blank priors and weighted means are what cost 0.5 s on a broad query and none of them
    depends on the query. Only the budget does: it enters through the price_vs_budget field of value_for_budget,
    so that one criterion is rebuilt for the subset (budget field first, then the cached features-per-lakh field,
    the same field order as _value) and everything else is sliced. None when `df` is not such a subset."""
    if not ref.covers(df):
        return None
    full = ref._criteria_cache.get(price_whole_catalogue)
    if full is None:
        src = ref.source
        if ref._value_fields is None:   # budget-free value_for_budget fields (features per lakh), shared by both keys
            ref._value_fields = _value(src, src["body_type"].astype(str), pd.Series("all", index=src.index), None, ref)
        full = _build(src, None, ref, price_whole_catalogue, ref._value_fields)
        ref._criteria_cache[price_whole_catalogue] = full
    res = _slice(full, df.index)
    bmax = (budget or {}).get("max")
    if bmax is None:
        return res
    price = df["price_ex_showroom"].map(num)
    fit = price.map(lambda p: np.nan if is_unknown(p) else budget_fit(p, bmax))
    fpr_field = tuple(x.loc[df.index] if isinstance(x, pd.Series) else x for x in ref._value_fields[0])
    fields: List[Field] = [("price_vs_budget", price, fit.astype(float), 1.0, "price / stated maximum budget",
                            None, None, None), fpr_field]
    value, scored, ufrac, per_row = _weighted_mean(fields, df.index)
    crit = "value_for_budget"
    res.values[crit] = value
    res.scoring[crit] = scored
    res.unknown_frac[crit] = ufrac
    res.detail._makers = dict(res.detail._makers, **{crit: per_row})
    return res


def compute_criteria(df: pd.DataFrame, budget: Optional[dict] = None,
                     reference: Optional[Reference] = None, price_whole_catalogue: bool = False) -> CriteriaResult:
    """Spec criteria for every row of `df`. Percentiles come from `reference` (the full-catalogue populations;
    api.py always passes it). Without one, the populations are built from `df` itself (hand-built frames)."""
    index = df.index
    if len(df) == 0:
        empty = pd.DataFrame(columns=SPEC_CRITERIA, dtype=float)
        return CriteriaResult(empty, {}, empty.copy(), empty.copy())
    if reference is not None:
        hit = _cached_criteria(df, budget, reference, price_whole_catalogue)
        if hit is not None:
            return hit
    ref = reference if reference is not None else Reference(df)
    return _build(df, budget, ref, price_whole_catalogue)
