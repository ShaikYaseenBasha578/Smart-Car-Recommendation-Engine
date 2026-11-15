"""Blank handling and review application 2026-11-15, change 3: how review scores are applied.

(a) expert scale denominator counts only aspects the data has; (b) unreviewed models take the segment mean; (c) aspects
count in proportion to the query weight of the criteria they map to, overall rows only without a preference; (d) one source
label that feeds two aspects counts once; (e) owner evidence is discounted once (value shrinkage, no second class scale)."""
import json

import pandas as pd
import pytest

from services.recsys import config
from services.recsys.api import recommend
from services.recsys.evidence import (ASPECTS, OWNER_RATING_COLS, REVIEW_ASSESSMENT_COLS, Evidence,
                                      owner_scale_for_count)
from services.recsys.score import score_candidates
from services.recsys.weights import build_weights, has_preferences, review_aspect_weights
from tests.recsys_frames import make_frame


def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None, "soft_preferences": [],
            "cheap_intent": False}
    base.update(kw)
    return base


LABELS = {"ride_comfort": "Ride Comfort And Handling", "handling": "Ride Comfort And Handling",
          "engine_performance": "Performance And Refinement", "refinement": "Performance And Refinement",
          "front_space": "Interior Space And Comfort", "rear_seat_comfort": "Interior Space And Comfort",
          "real_world_mileage": "Mileage / Range And Efficiency", "features_tech": "Features And Safety",
          "value_for_money": "Value For Money", "build_quality": "Exterior Design And Engineering",
          "overall": "overall"}


def assess(spec):
    """spec: {model: {aspect: value}} -> review-layout frame."""
    rows = [dict(model=m, aspect=a, value=str(v), source="Autocar India", url="http://ac/x", published_on="2025-10-27",
                 n_sources="1", raw_score=str(round(v * 10, 2)), scale_max="10", source_aspect=LABELS.get(a, a))
            for m, aspects in spec.items() for a, v in aspects.items()]
    return pd.DataFrame(rows, columns=REVIEW_ASSESSMENT_COLS)


def rate(spec, counts=None):
    """spec: {model: {theme: value}} -> owner-rating frame."""
    label = {"service_cost": "After Sales Cost and Experience", "service_experience": "After Sales Cost and Experience",
             "comfort": "Comfort and Space", "satisfaction": "overall", "performance": "Performance"}
    rows = [dict(model=m, aspect=a, value=str(v), rating_count=str((counts or {}).get(m, 400)), low_confidence="false",
                 source="CarWale", url="http://cw/x", observed_at="2026-11-14T00:00:00Z", raw_score=str(round(v * 5, 2)),
                 scale_max="5", source_aspect=label.get(a, a))
            for m, themes in spec.items() for a, v in themes.items()]
    return pd.DataFrame(rows, columns=OWNER_RATING_COLS)


def frame(*models):
    return make_frame([dict(model=m) for m in models])


def vid(df, model):
    return int(df.index[df["model"] == model][0])


ALL10 = ["ride_comfort", "handling", "engine_performance", "refinement", "front_space", "rear_seat_comfort",
         "real_world_mileage", "features_tech", "value_for_money", "build_quality"]


# ------------------------------------------------------------------ (a) the scale denominator

def test_expert_scale_denominator_counts_only_aspects_with_data_a():
    ev = Evidence(assess({"A": {a: 0.8 for a in ALL10}}))
    assert ev.data_aspects == set(ALL10)
    # 13 engine aspects, 3 of which no model has data for: a fully rated car is not capped at 10/13 x 1/2
    assert ev.expert_scale("", "A", list(ASPECTS)) == pytest.approx(0.5)
    assert ev.expert_scale("", "A", ["highway_stability"]) == 0.0           # nothing it could be rated on


def test_a_fully_rated_car_gets_the_whole_single_source_expert_class_weight_a():
    ev = Evidence(assess({"A": {a: 0.8 for a in ALL10}, "B": {a: 0.8 for a in ALL10}}))
    df = frame("A", "B")
    it = intent(use_case="family")
    table, _ = score_candidates(df, it, build_weights(it), ev)
    a = table.loc[vid(df, "A")]
    nominal = config.CLASS_WEIGHTS["expert"] / (config.CLASS_WEIGHTS["expert"] + config.CLASS_WEIGHTS["spec"])
    assert a["class_weights"]["expert"] == pytest.approx(nominal * 0.5 * (1.0))      # n/(n+1) only, not x 10/13


# ------------------------------------------------------------------ (b) unreviewed models

def reviewed_set(**extra):
    return {"R1": {a: 0.9 for a in ALL10}, "R2": {a: 0.5 for a in ALL10}, "R3": {a: 0.7 for a in ALL10}, **extra}


def test_unreviewed_model_takes_the_segment_mean_and_is_not_below_or_above_it_for_being_reviewed_b():
    ev = Evidence(assess(reviewed_set()))
    df = frame("R1", "R2", "R3", "U")
    it = intent(soft_preferences=["comfort"])
    table, _ = score_candidates(df, it, build_weights(it), ev)
    u = table.loc[vid(df, "U")]
    assert u["expert"] == pytest.approx((0.9 + 0.5 + 0.7) / 3)
    assert u["neutral_classes"] == ["expert"]
    assert table.loc[vid(df, "R1"), "neutral_classes"] == []
    ov = {m: table.loc[vid(df, m), "overall"] for m in ("R1", "R2", "R3", "U")}
    assert ov["R2"] < ov["U"] < ov["R1"]                       # reviewed below the mean < unreviewed < reviewed above it
    # the model reviewed exactly at the mean differs from the unreviewed one only by the coverage factor
    r3 = table.loc[vid(df, "R3")]
    assert r3["class_weights"] == pytest.approx(u["class_weights"])
    assert r3["unknown_share"] < u["unknown_share"]
    assert ov["R3"] / (1 - config.COVERAGE_PENALTY * r3["unknown_share"]) == pytest.approx(
        ov["U"] / (1 - config.COVERAGE_PENALTY * u["unknown_share"]))


def test_neutral_value_is_per_class_expert_and_owner_separately_b():
    ev = Evidence(assess(reviewed_set()),
                  owner_ratings=rate({"R1": {"comfort": 0.95}, "R2": {"comfort": 0.55}, "U": {}}),
                  segments={})
    df = frame("R1", "R2", "R3", "U")
    it = intent(soft_preferences=["comfort"])
    table, _ = score_candidates(df, it, build_weights(it), ev)
    u = table.loc[vid(df, "U")]
    assert u["neutral_classes"] == ["expert", "owner"]
    assert u["expert"] == pytest.approx(0.7)
    # R1 / R2 owner values are shrunk toward their own mean (0.75) by 400 / 450; the neutral value is the mean of those
    r1, r2 = (table.loc[vid(df, m), "owner"] for m in ("R1", "R2"))
    assert u["owner"] == pytest.approx((r1 + r2) / 2)
    # R3 has expert rows only: its owner class is neutral too
    assert table.loc[vid(df, "R3"), "neutral_classes"] == ["owner"]


def test_unreviewed_card_says_no_review_is_available_and_shows_no_score_b():
    spec = {f"R{i}": {a: 0.5 + 0.05 * i for a in ALL10} for i in range(6)}
    ev = Evidence(assess(spec), owner_ratings=rate({f"R{i}": {"comfort": 0.6 + 0.05 * i} for i in range(6)}), segments={})
    df = frame(*[f"R{i}" for i in range(6)], "U")
    r = recommend("comfortable SUV", evidence=ev, catalogue=df)
    u = next(c for c in r["recommendations"] if c["Model"] == "U")
    assert u["scores"]["expert"] is None and u["scores"]["owner"] is None
    assert "Expert ratings: none for this model yet" in u["unknowns"]
    assert "Owner ratings: none for this model yet" in u["unknowns"]
    assert not any(x["evidence_class"] in ("expert", "owner") for x in u["reasons"])
    rev = next(c for c in r["recommendations"] if c["Model"] == "R3")
    assert rev["scores"]["expert"] is not None and rev["scores"]["owner"] is not None
    assert "Expert ratings: none for this model yet" not in rev["unknowns"]


# ------------------------------------------------------------------ (c) relevance

def two_sided():
    return Evidence(assess({"A": {"real_world_mileage": 0.9, "ride_comfort": 0.3},
                            "B": {"real_world_mileage": 0.3, "ride_comfort": 0.9}}))


def test_aspects_count_in_proportion_to_the_query_weight_of_their_criteria_c():
    ev = two_sided()
    mileage = review_aspect_weights(build_weights(intent(soft_preferences=["mileage"])))["expert"]
    comfort = review_aspect_weights(build_weights(intent(soft_preferences=["comfort"])))["expert"]
    assert mileage["real_world_mileage"] > comfort["real_world_mileage"]
    assert comfort["ride_comfort"] > mileage["ride_comfort"]
    a_m, b_m = (ev.class_sub("expert", "", m, mileage) for m in "AB")
    a_c, b_c = (ev.class_sub("expert", "", m, comfort) for m in "AB")
    assert a_m > b_m and b_c > a_c                              # the same reviews rank the other way round
    w = build_weights(intent(soft_preferences=["mileage"]))["criteria"]
    expected = ((mileage["real_world_mileage"] * 0.9 + mileage["ride_comfort"] * 0.3)
                / (mileage["real_world_mileage"] + mileage["ride_comfort"]))
    assert a_m == pytest.approx(expected) and w["running_cost"]["weight"] > w["comfort_features"]["weight"]


def test_an_aspect_mapped_only_to_criteria_without_weight_contributes_nothing_c():
    ev = two_sided()
    it = intent(soft_preferences=["comfort"])
    aw = review_aspect_weights(build_weights(it, {"running_cost": False}))["expert"]    # running cost switched off
    assert "real_world_mileage" not in aw and "ride_comfort" in aw
    assert ev.class_sub("expert", "", "A", aw) == pytest.approx(0.3)                    # ride comfort only
    assert ev.class_sub("expert", "", "B", aw) == pytest.approx(0.9)


def test_a_query_without_preferences_uses_the_overall_rows_only_c():
    ev = Evidence(assess({"A": {"real_world_mileage": 0.9, "ride_comfort": 0.9, "overall": 0.4},
                          "B": {"real_world_mileage": 0.2, "ride_comfort": 0.2, "overall": 0.8}}),
                  owner_ratings=rate({"A": {"comfort": 0.95, "satisfaction": 0.5},
                                      "B": {"comfort": 0.55, "satisfaction": 0.9}}), segments={})
    for it in (intent(), intent(budget={"min": None, "max": 1200000}), {}):            # a budget alone is no preference
        w = build_weights(it)
        assert not has_preferences(w)
        assert review_aspect_weights(w) == {"expert": None, "owner": None}
    assert ev.class_sub("expert", "", "A", None) == pytest.approx(0.4)
    assert ev.class_sub("expert", "", "B", None) == pytest.approx(0.8)
    shrunk = {m: ev.owner("", m, "satisfaction")["value"] for m in "AB"}
    assert ev.class_sub("owner", "", "A", None) == pytest.approx(shrunk["A"])
    assert ev.class_sub("owner", "", "B", None) == pytest.approx(shrunk["B"])
    pref = review_aspect_weights(build_weights(intent(use_case="family")))
    assert ev.class_sub("expert", "", "A", pref["expert"]) > 0.8                        # with a preference the aspects count


def test_no_preference_without_an_overall_row_falls_back_to_the_aspects_at_equal_weight_c():
    ev = Evidence(assess({"A": {"real_world_mileage": 0.9, "ride_comfort": 0.5}}))
    assert ev.class_sub("expert", "", "A", None) == pytest.approx(0.7)


def test_preference_detection():
    assert has_preferences(build_weights(intent(use_case="family")))
    assert has_preferences(build_weights(intent(soft_preferences=["safety"])))
    assert has_preferences(build_weights(intent(required_features=["sunroof"])))
    assert has_preferences(build_weights(intent(cheap_intent=True)))
    assert not has_preferences(build_weights(intent(budget={"min": None, "max": 1000000})))


# ------------------------------------------------------------------ (d) one source label counts once

def test_two_aspects_fed_by_one_source_label_count_once_d():
    ev = Evidence(assess({"A": {"engine_performance": 0.9, "refinement": 0.9, "handling": 0.3}}))
    equal = {"engine_performance": 1.0, "refinement": 1.0, "handling": 1.0}
    # old: (0.9 + 0.9 + 0.3) / 3 = 0.7. Now the "Performance And Refinement" pair is one observation: (0.9 + 0.3) / 2
    assert ev.class_sub("expert", "", "A", equal) == pytest.approx(0.6)
    # the pair's weight is the mean of its members' weights, not the sum
    assert ev.class_sub("expert", "", "A", {"engine_performance": 3.0, "refinement": 1.0, "handling": 2.0}) == \
        pytest.approx((2.0 * 0.9 + 2.0 * 0.3) / 4.0)
    # a pair with one member weighted 0 counts with the other member's weight
    assert ev.class_sub("expert", "", "A", {"engine_performance": 1.0, "handling": 1.0}) == pytest.approx(0.6)


def test_owner_labels_that_feed_two_themes_count_once_d():
    ev = Evidence(owner_ratings=rate({"A": {"service_cost": 0.9, "service_experience": 0.9, "comfort": 0.3}},
                                     counts={"A": 100000}), segments={})
    w = {"service_cost": 1.0, "service_experience": 1.0, "comfort": 1.0}
    assert ev.class_sub("owner", "", "A", w) == pytest.approx(0.6, abs=0.001)         # (0.9 + 0.3) / 2, nearly unshrunk


# ------------------------------------------------------------------ (e) owner evidence discounted once

def test_owner_ratings_are_shrunk_by_count_but_the_class_weight_is_not_scaled_again_e():
    ev = Evidence(owner_ratings=rate({"Few": {"comfort": 0.96}, "Many": {"comfort": 0.96}, "Low": {"comfort": 0.5}},
                                     counts={"Few": 20, "Many": 900, "Low": 900}), segments={})
    few = ev.owner("", "Few", "comfort")
    assert few["shrink_weight"] == pytest.approx(owner_scale_for_count(20))           # the value is still shrunk
    assert few["value"] < ev.owner("", "Many", "comfort")["value"]
    assert ev.owner_scale("", "Few") == 1.0 and ev.owner_scale("", "Many") == 1.0       # no second discount
    df = frame("Few", "Many")
    it = intent(soft_preferences=["comfort"])
    table, _ = score_candidates(df, it, build_weights(it), ev)
    assert table.loc[vid(df, "Few"), "class_weights"]["owner"] == pytest.approx(
        table.loc[vid(df, "Many"), "class_weights"]["owner"])


# ------------------------------------------------------------------ empty review files: nothing changes

@pytest.mark.parametrize("q", ["family SUV under 15 lakh", "comfortable sedan", "SUV", "diesel SUV with sunroof under 20 lakh",
                               "good mileage city car"])
def test_empty_review_files_give_the_same_results_as_no_evidence_at_all(q):
    base = recommend(q, evidence=Evidence())
    empty = recommend(q, evidence=Evidence(assess({}), None, rate({}), segments={}))
    assert json.dumps(base, sort_keys=True) == json.dumps(empty, sort_keys=True)
    assert all(c["class_weights"] == {"spec": 1.0} for c in base["recommendations"])
