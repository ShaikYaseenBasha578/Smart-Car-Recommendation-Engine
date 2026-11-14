"""When nothing fits (plan section 6): the smallest named relaxations that give results.

Candidate relaxations ("moves") each carry a cost that encodes the order of willingness:
    budget +5% / +10% / +20%   1.0 / 1.1 / 1.2      (smallest overshoot first)
    required feature / minimum 2.0 (each one dropped separately)
    gearbox type -> its family 3.0 (e.g. DCT -> any automatic)
    body type / excluded body  4.0
    fuel / excluded fuel       5.0
    transmission family        5.5
    named make / like-model    6.0, named model 6.5
    budget dropped entirely    8.0     (fallback only)
    seats_min lowered by k     9.0 + k (last resort only; never lowered unless nothing else works)
All single moves are tried, then all pairs of moves on different constraints. Among results, relaxations
with fewer constraints come first, then lower total cost; one that returns at least
MIN_MODELS_FOR_RELAXATION models is preferred over one that returns fewer. If no single or pair works, seats
moves are allowed (and the response says so); if still nothing, moves are applied cumulatively in cost order.
The filter itself is never re-implemented: every attempt calls filter_v2.filter_candidates on a modified intent.
"""

from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from services.filter_v2 import AUTOMATIC_TYPES, FEATURE_COLUMNS, MIN_COLUMNS, filter_candidates
from services.recsys import config
from services.recsys.common import is_unknown, num

TYPE_LABELS = {"manual": "manual", "imt": "iMT", "amt": "AMT", "dct": "DCT", "cvt": "CVT", "e_cvt": "e-CVT",
               "torque_converter": "torque converter", "single_speed_ev": "single-speed EV"}


def format_rupees(amount: float) -> str:
    amount = abs(float(amount))
    if amount < 100000:
        digits = f"{int(round(amount / 1000.0) * 1000):,}"
        return "₹" + digits
    return "₹" + f"{amount / 100000.0:.2f}".rstrip("0").rstrip(".") + " lakh"


@dataclass
class Move:
    key: str            # constraint id; at most one move per key in a relaxation
    cost: float
    label: str          # what is relaxed, in words
    apply: Callable[[dict], dict] = field(repr=False, default=lambda i: i)
    detail: Dict[str, Any] = field(default_factory=dict)

    def describe(self) -> Dict[str, Any]:
        return {"key": self.key, "label": self.label, "cost": self.cost, **self.detail}


def _with(intent: dict, **changes) -> dict:
    new = copy.deepcopy(intent)
    new.update(changes)
    return new


def _family(types: List[str]) -> Optional[str]:
    if all(t in AUTOMATIC_TYPES for t in types):
        return "automatic"
    if all(t not in AUTOMATIC_TYPES for t in types):
        return "manual"
    return None


def generate_moves(intent: dict, allow_seats: bool = False, fallback: bool = False) -> List[Move]:
    moves: List[Move] = []
    budget = intent.get("budget") or {}
    if budget.get("max") is not None:
        for i, step in enumerate(config.BUDGET_STEPS):
            new_max = round(budget["max"] * (1 + step))
            moves.append(Move(
                "budget", 1.0 + 0.1 * i, f"budget up {int(step * 100)}% (to {format_rupees(new_max)})",
                (lambda it, m=new_max: _with(it, budget={**(it.get("budget") or {}), "max": m})),
                {"step": step, "new_max": new_max}))
    if budget.get("min") is not None:
        moves.append(Move("budget_min", 1.5, "no minimum price",
                          lambda it: _with(it, budget={**(it.get("budget") or {}), "min": None})))
    for f in intent.get("required_features") or []:
        moves.append(Move(f"feature:{f}", 2.0, f"drop {FEATURE_COLUMNS[f][1]}",
                          (lambda it, f=f: _with(it, required_features=[x for x in it["required_features"] if x != f]))))
    for key, (_, label) in MIN_COLUMNS.items():
        if intent.get(key) is not None:
            moves.append(Move(key, 2.0, f"drop minimum {label}", (lambda it, key=key: _with(it, **{key: None}))))
    if intent.get("min_safety_stars") is not None:
        moves.append(Move("min_safety_stars", 2.0, "drop safety-star minimum",
                          lambda it: _with(it, min_safety_stars=None)))
    trans = intent.get("transmission") or {}
    if trans.get("include_types"):
        fam = _family(trans["include_types"])
        moves.append(Move("gearbox_type", 3.0, f"any {fam or 'transmission'} gearbox type",
                          (lambda it, fam=fam: _with(it, transmission={**it["transmission"], "family": fam,
                                                                         "include_types": []}))))
    elif trans.get("family"):
        moves.append(Move("transmission_family", 5.5, f"drop {trans['family']} requirement",
                          lambda it: _with(it, transmission={**it["transmission"], "family": None})))
    if intent.get("body_types"):
        moves.append(Move("body_type", 4.0, "any body type", lambda it: _with(it, body_types=[])))
    if intent.get("exclude_body_types"):
        moves.append(Move("exclude_body_type", 4.0, "allow excluded body type",
                          lambda it: _with(it, exclude_body_types=[])))
    if intent.get("fuel_types"):
        moves.append(Move("fuel", 5.0, "any fuel type", lambda it: _with(it, fuel_types=[])))
    if intent.get("exclude_fuel_types"):
        moves.append(Move("exclude_fuel", 5.0, "allow excluded fuel", lambda it: _with(it, exclude_fuel_types=[])))
    if intent.get("makes"):
        moves.append(Move("makes", 6.0, "other makes", lambda it: _with(it, makes=[])))
    if intent.get("models"):
        moves.append(Move("models", 6.5, "other models", lambda it: _with(it, models=[])))
    if intent.get("reference_models"):
        moves.append(Move("like_model", 6.0, "drop 'similar to' requirement",
                          lambda it: _with(it, reference_models=[])))
    if fallback and (budget.get("max") is not None):
        moves.append(Move("budget_dropped", 8.0, "no maximum budget",
                          lambda it: _with(it, budget={**(it.get("budget") or {}), "max": None})))
    seats = intent.get("seats_min")
    if allow_seats and seats is not None:
        for k in range(1, int(seats) - 1):  # down to 2 seats
            moves.append(Move("seats", 9.0 + k, f"{int(seats) - k}+ seats instead of {int(seats)}+",
                              (lambda it, k=k: _with(it, seats_min=int(it["seats_min"]) - k)),
                              {"seats_asked": int(seats), "seats_now": int(seats) - k}))
    return moves


def _apply(intent: dict, moves) -> dict:
    for m in moves:
        intent = m.apply(intent)
    return intent


def _combos(moves: List[Move], size: int):
    for combo in itertools.combinations(moves, size):
        if len({m.key for m in combo}) == size:
            yield combo


def _n_models(cands: pd.DataFrame) -> int:
    return int(cands[["make", "model"]].drop_duplicates().shape[0]) if len(cands) else 0


def _search(intent: dict, df: pd.DataFrame, moves: List[Move], must_include: Optional[str] = None):
    """Best (combo, intent, candidates) over singles then pairs, or None."""
    fallback_hit = None
    combos = [c for size in (1, 2) for c in _combos(moves, size)
              if must_include is None or any(m.key == must_include for m in c)]
    combos.sort(key=lambda c: (len(c), sum(m.cost for m in c), [m.key for m in c], [m.label for m in c]))
    for combo in combos:
        relaxed = _apply(intent, combo)
        cands = filter_candidates(relaxed, df)
        n = _n_models(cands)
        if n >= config.MIN_MODELS_FOR_RELAXATION:
            return combo, relaxed, cands
        if n >= 1 and fallback_hit is None:
            fallback_hit = (combo, relaxed, cands)
    return fallback_hit


def find_relaxation(intent: dict, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """The smallest named relaxation that returns cars, or None if nothing works at all."""
    note = None
    hit = _search(intent, df, generate_moves(intent))
    seats_relaxed = False
    if hit is None and intent.get("seats_min") is not None:
        hit = _search(intent, df, generate_moves(intent, allow_seats=True), must_include="seats")
        seats_relaxed = hit is not None
    if hit is None:  # cumulative: apply moves one constraint at a time, cheapest first
        chosen: List[Move] = []
        used = set()
        relaxed = intent
        for m in sorted(generate_moves(intent, allow_seats=True, fallback=True), key=lambda m: (m.cost, m.label)):
            if m.key in used:
                continue
            chosen.append(m)
            used.add(m.key)
            relaxed = _apply(intent, chosen)
            cands = filter_candidates(relaxed, df)
            if len(cands):
                hit = (tuple(chosen), relaxed, cands)
                seats_relaxed = "seats" in used
                note = "No single or paired relaxation works, so several constraints were relaxed together."
                break
    if hit is None:
        return None
    combo, relaxed, cands = hit
    labels = " and ".join(m.label for m in combo)
    message = "No cars match all your requirements. Showing the closest, with " + labels + "."
    if seats_relaxed:
        message += " Seating was lowered because nothing else gave results."
    if note:
        message += " " + note
    return {
        "moves": [m.describe() for m in combo], "keys": [m.key for m in combo], "intent": relaxed,
        "candidates": cands, "n_constraints": len(combo), "seats_relaxed": seats_relaxed,
        "cumulative": note is not None, "message": message,
    }


# ---------------------------------------------------------------- violations

def violations_for(row: pd.Series, original: dict, keys: List[str]) -> List[Dict[str, Any]]:
    """Exactly which relaxed constraint this car breaks, and by how much (only keys it really breaks)."""
    out: List[Dict[str, Any]] = []

    def add(key: str, text: str, amount: Optional[float] = None, unit: Optional[str] = None):
        out.append({"constraint": key, "text": text, "amount": amount, "unit": unit})

    price = num(row["price_ex_showroom"])
    budget = original.get("budget") or {}
    trans = original.get("transmission") or {}
    for key in keys:
        if key in ("budget", "budget_dropped") and budget.get("max") is not None and price is not None \
                and price > budget["max"]:
            add("budget", f"{format_rupees(price - budget['max'])} over budget", price - budget["max"], "INR")
        elif key == "budget_min" and budget.get("min") is not None and price is not None and price < budget["min"]:
            add(key, f"{format_rupees(budget['min'] - price)} under your minimum price", budget["min"] - price, "INR")
        elif key.startswith("feature:"):
            f = key.split(":", 1)[1]
            col, label = FEATURE_COLUMNS[f]
            if row[col] is False:
                add(key, f"no {label}")
        elif key in MIN_COLUMNS:
            col, label = MIN_COLUMNS[key]
            v, t = num(row[col]), original.get(key)
            if v is not None and t is not None and v < t:
                add(key, f"{label} {v:g} vs {t:g} wanted", t - v, col)
        elif key == "min_safety_stars":
            v, t = num(row["safety_stars_adult"]), original.get("min_safety_stars")
            if v is not None and t is not None and v < t:
                add(key, f"{int(v)}-star safety vs {t}-star wanted", t - v, "stars")
        elif key == "gearbox_type" and trans.get("include_types") and row["transmission_type"] not in trans["include_types"]:
            want = "/".join(TYPE_LABELS.get(t, t) for t in trans["include_types"])
            add(key, f"{TYPE_LABELS.get(row['transmission_type'], row['transmission_type'])} instead of {want}")
        elif key == "transmission_family" and trans.get("family") and row["transmission_family"] != trans["family"]:
            add(key, f"{row['transmission_family']}, not {trans['family']}")
        elif key == "body_type" and original.get("body_types") and row["body_type"] not in original["body_types"]:
            add(key, f"{row['body_type']}, not {'/'.join(original['body_types'])}")
        elif key == "exclude_body_type" and row["body_type"] in (original.get("exclude_body_types") or []):
            add(key, f"is a {row['body_type']}, which you excluded")
        elif key == "fuel" and original.get("fuel_types") and row["fuel_type"] not in original["fuel_types"]:
            add(key, f"{row['fuel_type']}, not {'/'.join(original['fuel_types'])}")
        elif key == "exclude_fuel" and row["fuel_type"] in (original.get("exclude_fuel_types") or []):
            add(key, f"is {row['fuel_type']}, which you excluded")
        elif key == "makes" and original.get("makes") and row["make"] not in original["makes"]:
            add(key, f"{row['make']}, not {'/'.join(original['makes'])}")
        elif key == "models" and original.get("models") and row["model"] not in original["models"]:
            add(key, f"{row['model']}, not the model you named")
        elif key == "like_model":
            add(key, "outside the size/price range of the model you named")
        elif key == "seats" and original.get("seats_min") is not None:
            s = num(row["seats"])
            if s is not None and s < original["seats_min"]:
                add(key, f"{int(s)} seats, {int(original['seats_min'])}+ asked", original["seats_min"] - s, "seats")
    return out
