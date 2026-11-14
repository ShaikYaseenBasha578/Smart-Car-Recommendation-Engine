"""Intent -> weights over all criteria (plan sections 4-5).

Every criterion starts from a neutral base weight; each signal in the parsed intent (use case,
soft preferences, required features, minimums, a stated budget) multiplies the weights it concerns.
Weights are then normalised to sum to 1 *within each evidence class* (spec / expert / owner).
Class weights (0.60 / 0.25 / 0.15) live in config and are applied in score.py.

`weight_overrides` ({criterion: number | bool}) lets the UI switch chips: False or 0 switches a
criterion off; True resets it to the profile value; a positive number replaces its multiplier.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.recsys.criteria import SPEC_CRITERIA, SPEC_LABELS
from services.recsys.evidence import EXPERT_CRITERIA, OWNER_CRITERIA, criterion_label

ALL_CRITERIA = SPEC_CRITERIA + EXPERT_CRITERIA + OWNER_CRITERIA
MAX_MULTIPLIER = 4.0

CRITERION_CLASS: Dict[str, str] = {
    **{c: "spec" for c in SPEC_CRITERIA}, **{c: "expert" for c in EXPERT_CRITERIA},
    **{c: "owner" for c in OWNER_CRITERIA},
}
LABELS: Dict[str, str] = {**SPEC_LABELS, **{c: criterion_label(c) for c in EXPERT_CRITERIA + OWNER_CRITERIA}}

# neutral base: price, safety and running cost matter a little more than the rest; reviews are flat
NEUTRAL_BASE: Dict[str, float] = {
    "value_for_budget": 1.5, "safety": 1.5, "running_cost": 1.5, "comfort_features": 1.0,
    "space_practicality": 1.0, "performance": 1.0, "tech_assist": 1.0,
}

# multipliers per use case (names are what services.intent_v2.USE_CASE_PATTERNS emits)
USE_CASE_PROFILES: Dict[str, Dict[str, float]] = {
    "premium": {"comfort_features": 2, "tech_assist": 2, "performance": 1.5, "value_for_budget": 0.5,
                "running_cost": 0.6, "expert_refinement": 2, "expert_build_quality": 2,
                "expert_features_tech": 2, "owner_build_issues": 1.5},
    "parents": {"comfort_features": 2, "safety": 2, "space_practicality": 1.3, "expert_ride_comfort": 2,
                "expert_rear_seat_comfort": 2, "expert_city_driveability": 1.5, "expert_front_space": 1.5,
                "owner_reliability": 1.5, "owner_service_cost": 1.3},
    "family": {"safety": 2, "space_practicality": 2, "comfort_features": 1.5, "running_cost": 1.2,
               "expert_rear_seat_comfort": 2, "expert_boot_practicality": 2, "expert_ride_comfort": 1.5,
               "owner_reliability": 1.5, "owner_service_cost": 1.3, "owner_satisfaction": 1.2},
    "highway": {"performance": 2, "safety": 1.5, "comfort_features": 1.5, "expert_highway_stability": 2.5,
                "expert_engine_performance": 2, "expert_ride_comfort": 1.5, "expert_refinement": 1.5},
    "student": {"value_for_budget": 2, "running_cost": 2, "tech_assist": 1.2, "expert_value_for_money": 2,
                "expert_real_world_mileage": 1.5, "owner_service_cost": 2, "owner_resale": 1.5,
                "owner_reliability": 1.3},
    "budget": {"value_for_budget": 2.5, "running_cost": 2, "expert_value_for_money": 2.5,
               "expert_real_world_mileage": 1.5, "owner_service_cost": 2},
    "commute": {"running_cost": 2, "comfort_features": 1.3, "expert_city_driveability": 2,
                "expert_real_world_mileage": 1.5, "owner_service_cost": 1.3, "owner_reliability": 1.3},
    "city": {"running_cost": 1.5, "performance": 0.8, "expert_city_driveability": 2.5,
             "owner_real_world_mileage": 1.3},
    "enthusiast": {"performance": 3, "value_for_budget": 0.6, "running_cost": 0.5, "expert_handling": 2.5,
                   "expert_engine_performance": 2.5},
}
# multipliers per soft preference (intent_v2.SOFT_PREFERENCES)
SOFT_PREFERENCE_PROFILES: Dict[str, Dict[str, float]] = {
    "mileage": {"running_cost": 2, "expert_real_world_mileage": 2, "owner_real_world_mileage": 2},
    "space": {"space_practicality": 2, "expert_front_space": 1.5, "expert_rear_seat_comfort": 1.5,
              "expert_boot_practicality": 1.5},
    "performance": {"performance": 2, "expert_engine_performance": 2, "expert_handling": 1.5},
    "comfort": {"comfort_features": 2, "expert_ride_comfort": 2, "expert_rear_seat_comfort": 1.5},
    "safety": {"safety": 2.5},
    "features": {"tech_assist": 2, "comfort_features": 1.5, "expert_features_tech": 2},
}
COMFORT_FEATURES = {"sunroof", "ventilated_seats", "cruise_control"}
TECH_FEATURES = {"adas", "camera_360", "wireless_charging", "heads_up_display", "android_auto", "apple_carplay"}


def _get(intent: Any, key: str, default: Any = None) -> Any:
    if intent is None:
        return default
    if isinstance(intent, dict):
        v = intent.get(key, default)
    else:
        v = getattr(intent, key, default)
    return default if v is None else v


def _signals(intent: Any) -> List[tuple]:
    """(reason text, {criterion: multiplier}) for every signal found in the intent."""
    out: List[tuple] = []
    use_case = _get(intent, "use_case")
    if use_case in USE_CASE_PROFILES:
        out.append((f"use case: {use_case}", USE_CASE_PROFILES[use_case]))
    for pref in _get(intent, "soft_preferences", []):
        if pref in SOFT_PREFERENCE_PROFILES:
            out.append((f"preference: {pref}", SOFT_PREFERENCE_PROFILES[pref]))
    feats = set(_get(intent, "required_features", []))
    if feats & COMFORT_FEATURES:
        out.append(("asked for comfort features", {"comfort_features": 1.5}))
    if feats & TECH_FEATURES:
        out.append(("asked for tech features", {"tech_assist": 1.5}))
    if _get(intent, "min_safety_stars") is not None or _get(intent, "min_airbags") is not None:
        out.append(("asked for a safety minimum", {"safety": 1.5}))
    if any(_get(intent, k) is not None for k in ("min_mileage_kmpl", "min_mileage_km_per_kg", "min_ev_range_km")):
        out.append(("asked for a mileage/range minimum", {"running_cost": 1.5}))
    seats = _get(intent, "seats_min")
    if (seats is not None and seats >= 6) or _get(intent, "min_boot_space_litres") is not None:
        out.append(("asked for seats/boot space", {"space_practicality": 1.5}))
    if (_get(intent, "budget", {}) or {}).get("max") is not None:
        out.append(("stated a budget", {"value_for_budget": 1.3}))
    return out


def label_for(criterion: str) -> str:
    return LABELS.get(criterion, criterion)


def build_weights(intent: Any, weight_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Weights over every criterion.

    Returns {"profile": name, "drivers": [reason, ...], "raw": {crit: multiplier x base},
             "criteria": {crit: {"class", "label", "multiplier", "weight", "active", "why": [...]}}}
    where "weight" is normalised to sum 1 within the criterion's class (0 for all if the class is off)."""
    mult = {c: 1.0 for c in ALL_CRITERIA}
    why: Dict[str, List[str]] = {c: [] for c in ALL_CRITERIA}
    drivers: List[str] = []
    for reason, boosts in _signals(intent):
        drivers.append(reason)
        for crit, m in boosts.items():
            mult[crit] = min(MAX_MULTIPLIER, mult[crit] * m)
            why[crit].append(reason)

    off = set()
    for crit, val in (weight_overrides or {}).items():
        if crit not in mult:
            continue
        if val is False or (not isinstance(val, bool) and val is not None and float(val) <= 0):
            off.add(crit)
            why[crit].append("switched off")
        elif val is True or val is None:
            continue
        else:
            mult[crit] = min(MAX_MULTIPLIER, float(val))
            why[crit].append("set by you")

    raw = {c: (0.0 if c in off else mult[c] * NEUTRAL_BASE.get(c, 1.0)) for c in ALL_CRITERIA}
    totals: Dict[str, float] = {}
    for c, w in raw.items():
        totals[CRITERION_CLASS[c]] = totals.get(CRITERION_CLASS[c], 0.0) + w
    criteria = {}
    for c in ALL_CRITERIA:
        total = totals[CRITERION_CLASS[c]]
        criteria[c] = {
            "class": CRITERION_CLASS[c], "label": label_for(c), "multiplier": round(mult[c], 4),
            "weight": (raw[c] / total) if total > 0 else 0.0, "active": c not in off, "why": why[c],
        }
    profile = _get(intent, "use_case") if _get(intent, "use_case") in USE_CASE_PROFILES else "neutral"
    return {"profile": profile, "drivers": drivers, "raw": raw, "criteria": criteria}


def flat_weights(weights: Dict[str, Any]) -> Dict[str, float]:
    """{criterion: within-class normalised weight}."""
    return {c: v["weight"] for c, v in weights["criteria"].items()}
