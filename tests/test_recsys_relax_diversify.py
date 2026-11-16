import pandas as pd
import pytest

from services.recsys import config
from services.recsys.diversify import best_variant_per_model, diversify, mmr_select, similarity
from services.recsys.relax import find_relaxation, format_rupees, generate_moves, violations_for
from tests.recsys_frames import make_frame

LAKH = 100000.0


def base_intent(**kw):
    it = {"budget": {"min": None, "max": None}, "body_types": [], "fuel_types": [],
          "transmission": {"family": None, "include_types": [], "exclude_types": []}, "seats_min": None,
          "makes": [], "required_features": [], "min_airbags": None, "min_safety_stars": None,
          "min_boot_space_litres": None, "min_ground_clearance_mm": None, "min_ev_range_km": None,
          "min_mileage_kmpl": None, "min_mileage_km_per_kg": None, "use_case": None,
          "exclude_fuel_types": [], "exclude_body_types": [], "models": [], "reference_models": [],
          "unsupported_terms": [], "soft_preferences": []}
    it.update(kw)
    return it


@pytest.fixture(autouse=True)
def one_model_is_enough(monkeypatch):
    monkeypatch.setattr(config, "MIN_MODELS_FOR_RELAXATION", 1)


def cars(*specs):
    return make_frame([dict(model=f"M{i}", **s) for i, s in enumerate(specs)])


def test_format_rupees():
    assert format_rupees(40000) == "₹40,000"
    assert format_rupees(120000) == "₹1.2 lakh"
    assert format_rupees(1250000) == "₹12.5 lakh"


def test_single_budget_relaxation_names_size():
    df = cars(dict(price_ex_showroom=9.4 * LAKH, sunroof=True))
    it = base_intent(budget={"min": None, "max": 9 * LAKH}, body_types=["suv"], required_features=["sunroof"])
    r = find_relaxation(it, df)
    assert r["keys"] == ["budget"] and r["n_constraints"] == 1
    assert r["moves"][0]["step"] == 0.05
    v = violations_for(r["candidates"].iloc[0], it, r["keys"])
    assert [x["text"] for x in v] == ["₹40,000 over budget"] and v[0]["amount"] == pytest.approx(40000)


def test_smallest_budget_step_is_chosen():
    df = cars(dict(price_ex_showroom=9.7 * LAKH), dict(price_ex_showroom=10.6 * LAKH))
    r = find_relaxation(base_intent(budget={"min": None, "max": 9 * LAKH}), df)
    assert r["moves"][0]["step"] == 0.10 and len(r["candidates"]) == 1


def test_order_of_willingness_budget_then_features_then_gearbox_then_body_then_fuel():
    # each car can be reached by exactly one single relaxation; the cheapest (most willing) must win
    it = base_intent(budget={"min": None, "max": 9 * LAKH}, body_types=["suv"], fuel_types=["petrol"],
                     required_features=["sunroof"], transmission={"family": "automatic", "include_types": ["dct"],
                                                                  "exclude_types": []})
    reach = {
        "budget": dict(price_ex_showroom=9.3 * LAKH, sunroof=True, transmission_type="dct", transmission_family="automatic"),
        "feature:sunroof": dict(price_ex_showroom=8 * LAKH, sunroof=False, transmission_type="dct", transmission_family="automatic"),
        "gearbox_type": dict(price_ex_showroom=8 * LAKH, sunroof=True, transmission_type="amt", transmission_family="automatic"),
        "body_type": dict(price_ex_showroom=8 * LAKH, sunroof=True, transmission_type="dct", transmission_family="automatic", body_type="hatchback"),
        "fuel": dict(price_ex_showroom=8 * LAKH, sunroof=True, transmission_type="dct", transmission_family="automatic", fuel_type="diesel"),
    }
    ok = dict(price_ex_showroom=8 * LAKH, sunroof=True, transmission_type="dct", transmission_family="automatic")
    order = ["fuel", "body_type", "gearbox_type", "feature:sunroof", "budget"]
    # add one car per reason, removing the cheaper ones step by step
    for i in range(len(order)):
        present = order[i:]
        df = cars(*[reach[k] for k in present])
        r = find_relaxation(it, df)
        assert r["keys"] == [present[-1]], (present, r["keys"])


def test_pair_relaxation_when_no_single_works():
    df = cars(dict(price_ex_showroom=9.8 * LAKH, sunroof=False))
    it = base_intent(budget={"min": None, "max": 9 * LAKH}, required_features=["sunroof"])
    r = find_relaxation(it, df)
    assert sorted(r["keys"]) == ["budget", "feature:sunroof"] and r["n_constraints"] == 2
    texts = sorted(x["text"] for x in violations_for(r["candidates"].iloc[0], it, r["keys"]))
    assert texts == ["no sunroof", "₹80,000 over budget"]


def test_single_preferred_over_pair_and_nothing_relaxed_unnamed():
    df = cars(dict(price_ex_showroom=9.3 * LAKH, sunroof=True), dict(price_ex_showroom=9.8 * LAKH, sunroof=False))
    it = base_intent(budget={"min": None, "max": 9 * LAKH}, required_features=["sunroof"])
    r = find_relaxation(it, df)
    assert r["n_constraints"] == 1
    for _, row in r["candidates"].iterrows():
        broken = {v["constraint"] for v in violations_for(row, it, r["keys"])}
        assert broken <= set(r["keys"])
    # unchanged constraints still hold in the relaxed intent
    assert r["intent"]["required_features"] == ["sunroof"]


def test_enough_models_is_only_a_tie_break_within_half_a_cost_point(monkeypatch):
    monkeypatch.setattr(config, "MIN_MODELS_FOR_RELAXATION", 3)
    # budget +5% (cost 1.0) gives 1 model, +10% (cost 1.1) gives 3: within 0.5, so the larger result wins
    df = cars(dict(price_ex_showroom=9.3 * LAKH), dict(price_ex_showroom=9.8 * LAKH),
              dict(price_ex_showroom=9.85 * LAKH))
    r = find_relaxation(base_intent(budget={"min": None, "max": 9 * LAKH}), df)
    assert r["keys"] == ["budget"] and r["moves"][0]["step"] == 0.10 and len(r["candidates"]) == 3


def test_cheaper_relaxation_wins_even_with_fewer_models_when_cost_differs_by_more_than_the_tie(monkeypatch):
    monkeypatch.setattr(config, "MIN_MODELS_FOR_RELAXATION", 3)
    # fuel change (5.0) would give 3 models, budget +5% (1.0) gives 1: costs differ by 4, cheapest wins
    df = cars(dict(price_ex_showroom=9.3 * LAKH), dict(price_ex_showroom=9.0 * LAKH, fuel_type="diesel"),
              dict(price_ex_showroom=8.9 * LAKH, fuel_type="diesel"), dict(price_ex_showroom=8.8 * LAKH, fuel_type="diesel"))
    it = base_intent(budget={"min": None, "max": 9 * LAKH}, fuel_types=["petrol"], body_types=["suv"])
    df.loc[df["model"] == "M0", "body_type"] = "suv"
    r = find_relaxation(it, df)
    assert r["keys"] == ["budget"]


def test_total_cost_beats_fewer_constraints():
    """budget +5% and one dropped feature (1.0 + 2.0 = 3.0) is preferred over switching fuel (5.0)."""
    # A: petrol, 9.4L, no sunroof -> needs budget +5% and the feature dropped (3.0)
    # B: diesel, 8L, with sunroof -> needs only the fuel switch (5.0)
    df = cars(dict(price_ex_showroom=9.4 * LAKH, sunroof=False),
              dict(price_ex_showroom=8.0 * LAKH, fuel_type="diesel", sunroof=True))
    it = base_intent(budget={"min": None, "max": 9 * LAKH}, fuel_types=["petrol"], required_features=["sunroof"])
    r = find_relaxation(it, df)
    assert sorted(r["keys"]) == ["budget", "feature:sunroof"]
    assert sum(m["cost"] for m in r["moves"]) == pytest.approx(3.0)


def test_far_flag_when_more_than_three_constraints_relaxed():
    df = cars(dict(price_ex_showroom=30 * LAKH, sunroof=False, adas_available=False, camera_360=False,
                   cruise_control=False, body_type="sedan", fuel_type="diesel"))
    it = base_intent(budget={"min": None, "max": 5 * LAKH}, body_types=["suv"], fuel_types=["petrol"],
                     required_features=["sunroof", "adas", "camera_360", "cruise_control"])
    r = find_relaxation(it, df)
    assert r["cumulative"] and r["far"] and len(r["keys"]) > 3
    assert "nothing close" in r["message"].lower() and "nearest" in r["message"].lower()


def test_not_far_when_small_relaxation_works():
    df = cars(dict(price_ex_showroom=9.3 * LAKH))
    r = find_relaxation(base_intent(budget={"min": None, "max": 9 * LAKH}), df)
    assert r["far"] is False


def test_exclusions_and_upper_bounds_are_relaxable_with_truthful_violations():
    df = cars(dict(sunroof=True, make="Acme"), dict(sunroof=False, make="Other", ground_clearance_mm=210.0))
    it = base_intent(exclude_features=["sunroof"], exclude_makes=["Other"], max_ground_clearance_mm=200.0)
    # M1 breaks the make and the clearance bound, M0 the sunroof exclusion; nothing passes the original intent
    from services.filter_v2 import filter_candidates
    assert filter_candidates(it, df).empty
    r = find_relaxation(it, df)
    assert r is not None and set(r["keys"]) <= {"exclude_feature:sunroof", "exclude_makes", "max_ground_clearance_mm"}
    for _, row in r["candidates"].iterrows():
        viol = violations_for(row, it, r["keys"])
        named = {v["constraint"] for v in viol}
        broken = set()
        if row["sunroof"] is True:
            broken.add("exclude_feature:sunroof")
        if row["make"] == "Other":
            broken.add("exclude_makes")
        if row["ground_clearance_mm"] > 200:
            broken.add("max_ground_clearance_mm")
        assert named == broken & set(r["keys"])
        assert all(v["text"] for v in viol)


def test_seats_not_lowered_unless_nothing_else_works():
    five = dict(seats=5.0, price_ex_showroom=9.3 * LAKH)
    seven = dict(seats=7.0, price_ex_showroom=9.3 * LAKH, model="Seven")
    it = base_intent(budget={"min": None, "max": 9 * LAKH}, seats_min=7)
    r = find_relaxation(it, make_frame([dict(model="Five", **five), dict(**seven)]))
    assert r["keys"] == ["budget"] and not r["seats_relaxed"]
    assert all(r["candidates"]["seats"] >= 7)
    # only 5-seaters exist, nothing is within +20% either way: seats must be lowered and the response says so
    df = make_frame([dict(model="Five", seats=5.0, price_ex_showroom=8 * LAKH)])
    r = find_relaxation(it, df)
    assert r["seats_relaxed"] and "seats" in r["keys"] and "Seating was lowered" in r["message"]
    v = violations_for(r["candidates"].iloc[0], it, r["keys"])
    assert v[0]["text"] == "5 seats, 7+ asked"


def test_gearbox_relaxes_within_family_only():
    it = base_intent(transmission={"family": "automatic", "include_types": ["dct"], "exclude_types": []})
    df = cars(dict(transmission_type="manual", transmission_family="manual"),
              dict(transmission_type="amt", transmission_family="automatic"))
    r = find_relaxation(it, df)
    assert r["keys"] == ["gearbox_type"] and list(r["candidates"]["transmission_type"]) == ["amt"]
    v = violations_for(r["candidates"].iloc[0], it, r["keys"])
    assert v[0]["text"] == "AMT instead of DCT"


def test_min_value_violation_has_amount():
    it = base_intent(min_boot_space_litres=400)
    df = cars(dict(boot_space_litres=350.0))
    r = find_relaxation(it, df)
    v = violations_for(r["candidates"].iloc[0], it, r["keys"])
    assert v[0]["amount"] == 50 and "350" in v[0]["text"]


def test_nothing_possible_returns_none():
    assert find_relaxation(base_intent(budget={"min": None, "max": 1}), cars(dict())[0:0]) is None


def test_moves_never_include_seats_by_default():
    assert not any(m.key == "seats" for m in generate_moves(base_intent(seats_min=7)))


# ------------------------------------------------------------------ diversify

def sframe(specs):
    rows = [{k: v for k, v in s.items() if k != "_s"} for s in specs]
    df = make_frame(rows)
    df["overall"] = [s["_s"] for s in specs]
    return df


def test_best_scoring_variant_per_model_not_lowest_id():
    df = sframe([dict(model="A", variant="base", _s=0.5), dict(model="A", variant="top", _s=0.9),
                 dict(model="B", variant="only", _s=0.6)])
    best = best_variant_per_model(df)
    assert best.loc[best["model"] == "A", "variant"].iloc[0] == "top"
    assert len(best) == 2
    assert best.iloc[0]["model"] == "A"


def _run_len(makes):
    longest = cur = 0
    prev = None
    for m in makes:
        cur = cur + 1 if m == prev else 1
        longest, prev = max(longest, cur), m
    return longest


def test_mmr_reduces_same_make_runs():
    specs = [dict(make="X", model=f"X{i}", _s=0.95 - 0.01 * i, price_ex_showroom=(10 + 0.1 * i) * LAKH) for i in range(6)]
    specs += [dict(make=f"Y{i}", model=f"Y{i}", _s=0.90 - 0.005 * i, price_ex_showroom=(10 + i) * LAKH) for i in range(5)]
    specs.append(dict(make="Z", model="Z0", _s=0.30, price_ex_showroom=30 * LAKH))  # a weak car stretches the scale
    df = sframe(specs)
    plain = best_variant_per_model(df)
    base = list(plain.head(8)["make"])
    mmr = [r["make"] for r in diversify(df, base_intent())]
    assert len(mmr) == 8
    assert _run_len(mmr) < _run_len(base)
    assert mmr.count("X") < base.count("X")
    assert mmr[0] == "X"  # the best car is still first


def test_display_is_sorted_by_score_while_mmr_decides_the_selection():
    specs = [dict(make="X", model=f"X{i}", _s=0.95 - 0.01 * i, price_ex_showroom=(10 + 0.1 * i) * LAKH) for i in range(6)]
    specs += [dict(make=f"Y{i}", model=f"Y{i}", _s=0.90 - 0.005 * i, price_ex_showroom=(10 + i) * LAKH) for i in range(5)]
    specs.append(dict(make="Z", model="Z0", _s=0.30, price_ex_showroom=30 * LAKH))
    out = diversify(sframe(specs), base_intent())
    scores = [float(r["overall"]) for r in out]
    assert scores == sorted(scores, reverse=True)
    # MMR pulled a lower-scored car into the selection ahead of a higher-scored one ...
    order = [int(r["selection_order"]) for r in out]
    assert sorted(order) == list(range(1, len(out) + 1)) and order != sorted(order)
    # ... but the display still never shows a weaker match above a stronger one
    assert out[0]["selection_order"] == 1


def test_mmr_skipped_when_make_named():
    specs = [dict(make="X", model=f"X{i}", _s=0.95 - 0.01 * i, price_ex_showroom=10 * LAKH) for i in range(9)]
    df = sframe(specs)
    out = diversify(df, base_intent(makes=["X"]))
    assert [r["model"] for r in out] == [f"X{i}" for i in range(8)]
    out = diversify(df, base_intent(models=["X1"]))
    assert [r["model"] for r in out] == [f"X{i}" for i in range(8)]


def test_similarity_components():
    a = make_frame([dict(make="A", price_ex_showroom=10 * LAKH), dict(make="A", price_ex_showroom=10 * LAKH),
                    dict(make="B", body_type="hatchback", price_ex_showroom=20 * LAKH)])
    assert similarity(a.iloc[0], a.iloc[1]) == pytest.approx(1.0)
    assert similarity(a.iloc[0], a.iloc[2]) == pytest.approx(0.0)


def test_twins_flag():
    specs = [dict(make="Toyota", model="Glanza", _s=0.99, price_ex_showroom=8 * LAKH, body_type="hatchback"),
             dict(make="Maruti Suzuki", model="Baleno", _s=0.98, price_ex_showroom=8 * LAKH, body_type="hatchback")]
    specs += [dict(make=f"M{i}", model=f"N{i}", _s=0.9 - 0.01 * i, price_ex_showroom=(5 + 2 * i) * LAKH, body_type="suv") for i in range(10)]
    df = sframe(specs)
    assert len(diversify(df, base_intent(makes=["Toyota", "Maruti Suzuki"], ), use_twins=True)) == 9
    assert len(diversify(df, base_intent(makes=["Toyota", "Maruti Suzuki"]), use_twins=False)) == 8
    assert len(diversify(df, base_intent(), use_twins=False)) == 8


def test_relaxed_labels_name_only_stated_constraints_synthetic_frame():
    """Regression: a figure with a measurement unit used to become a phantom budget minimum, so the relaxed result
    named a violation of something the user never asked for. On a hand-built frame the relaxation must name exactly
    the constraint that is really broken (here: the stated fuel)."""
    from tests.recsys_frames import make_frame
    from services.recsys.api import recommend
    frame = make_frame([dict(model="A", fuel_type="petrol", fuel_raw="Petrol", price_ex_showroom=900000.0),
                        dict(model="B", fuel_type="petrol", fuel_raw="Petrol", price_ex_showroom=1100000.0)])
    r = recommend("diesel car under 12 lakh, we drive about 60 km a day", catalogue=frame)
    assert r["intent"]["budget"]["min"] is None and r["intent"]["budget"]["max"] == 1_200_000
    assert r.get("relaxation") and r["relaxation"]["keys"] == ["fuel"]
    for car in r["recommendations"]:
        assert [v["constraint"] for v in car["violations"]] == ["fuel"]
