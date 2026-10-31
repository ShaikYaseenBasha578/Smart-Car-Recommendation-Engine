"""Badge-engineered twins: the same car sold under two brands.

Twins are ranked as fully separate cars. The only effect: for every twin pair with BOTH
models in the final results, the result limit grows by one (see new_car_service).

TWIN_GROUPS holds confirmed pairs only. detect_twin_candidates() lists possible further
pairs for human review; its output is never applied automatically.
"""

from __future__ import annotations

import pandas as pd

# confirmed pairs: (make, model) -> (make, model)
TWIN_GROUPS = {
    ("Toyota", "Urban Cruiser Taisor"): ("Maruti Suzuki", "Fronx"),
    ("Toyota", "Glanza"): ("Maruti Suzuki", "Baleno"),
    ("Toyota", "Urban Cruiser Hyryder"): ("Maruti Suzuki", "Grand Vitara"),
    ("Toyota", "Rumion"): ("Maruti Suzuki", "Ertiga"),
}


def complete_twin_pairs(selected: list[tuple[str, str]]) -> int:
    """How many TWIN_GROUPS pairs have both (make, model) members in `selected`."""
    present = set(selected)
    return sum(1 for a, b in TWIN_GROUPS.items() if a in present and b in present)


def detect_twin_candidates(df: pd.DataFrame, price_tolerance: float = 0.15) -> list[dict]:
    """Different make, same body_type, an identical engine_cc+power_bhp+torque_nm on >=1 variant,
    and model price ranges within price_tolerance. For review only."""
    confirmed = {frozenset(p) for p in TWIN_GROUPS.items()}
    models = (
        df.groupby(["make", "model"])
        .agg(body_type=("body_type", "first"), price_min=("price_ex_showroom", "min"),
             price_max=("price_ex_showroom", "max"))
        .reset_index()
    )
    engines = (
        df.dropna(subset=["engine_cc", "power_bhp", "torque_nm"])
        .groupby(["make", "model"])
        .apply(lambda g: set(zip(g["engine_cc"], g["power_bhp"], g["torque_nm"])), include_groups=False)
        .to_dict()
    )

    def close(a, b):
        return abs(a - b) <= price_tolerance * max(a, b)

    found = []
    rows = models.to_dict("records")
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["make"] == b["make"] or a["body_type"] != b["body_type"]:
                continue
            ka, kb = (a["make"], a["model"]), (b["make"], b["model"])
            shared = engines.get(ka, set()) & engines.get(kb, set())
            if not shared or not (close(a["price_min"], b["price_min"]) or close(a["price_max"], b["price_max"])):
                continue
            found.append({
                "a": f"{a['make']} {a['model']}",
                "b": f"{b['make']} {b['model']}",
                "body_type": a["body_type"],
                "shared_engines": sorted(shared),
                "price_a": (a["price_min"], a["price_max"]),
                "price_b": (b["price_min"], b["price_max"]),
                "confirmed": frozenset([ka, kb]) in confirmed,
            })
    return found
