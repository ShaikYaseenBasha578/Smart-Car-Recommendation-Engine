"""Design change 2: price criterion, cheap-intent parsing, and the displayed variant per model."""
import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.intent_v2 import CHEAP_INTENT_PATTERN, parse_intent
from services.recsys import config
from services.recsys.api import recommend
from services.recsys.criteria import SPEC_CRITERIA, compute_criteria
from services.recsys.diversify import displayed_variant_per_model
from services.recsys.evidence import Evidence
from services.recsys.score import score_candidates
from services.recsys.weights import CRITERION_CLASS, build_weights
from tests.recsys_frames import make_frame

NO_EVIDENCE = Evidence()
LAKH = 100000.0


def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None, "soft_preferences": [],
            "cheap_intent": False}
    base.update(kw)
    return base


# ------------------------------------------------------------------ parser: one list of cheap / value wording

CHEAP_QUERIES = ["cheapest car", "cheap SUV", "budget car for city", "low cost sedan", "affordable hatchback",
                 "value for money SUV", "paisa vasool gaadi", "sasta hatchback", "sabse sasti car", "kam daam ki gaadi",
                 "kifayati car", "budget friendly suv", "CHEAPEST automatic SUV", "low-cost family car",
                 "sasti si automatic"]


@pytest.mark.parametrize("q", CHEAP_QUERIES)
def test_cheap_wording_sets_cheap_intent(q):
    assert parse_intent(q)["cheap_intent"] is True


@pytest.mark.parametrize("q", ["my budget is 10 lakh", "budget 12 lakh suv", "SUV under 15 lakh", "family car",
                               "within my budget", "petrol hatchback", "SUV with sunroof under 15 lakh"])
def test_budget_amounts_and_plain_queries_are_not_cheap_intent(q):
    assert parse_intent(q)["cheap_intent"] is False


def test_cheap_intent_is_one_list_in_the_parser():
    import services.intent_v2 as iv
    assert dict(iv.USE_CASE_PATTERNS)["budget"] == CHEAP_INTENT_PATTERN
    assert not parse_intent("cheapest car")["vague"]


# ------------------------------------------------------------------ weights

def spec_weights(w):
    return {c: v["weight"] for c, v in w["criteria"].items() if v["class"] == "spec"}


def test_price_default_weight_without_budget():
    w = build_weights(intent(use_case="family"))
    assert w["criteria"]["price"]["weight"] == pytest.approx(config.PRICE_DEFAULT_WEIGHT)
    assert sum(spec_weights(w).values()) == pytest.approx(1.0)


def test_price_weight_large_with_cheap_intent_and_named_in_drivers():
    w = build_weights(intent(cheap_intent=True))
    assert w["criteria"]["price"]["weight"] == pytest.approx(config.PRICE_CHEAP_WEIGHT)
    assert any("price prioritised" in d for d in w["drivers"])
    assert sum(spec_weights(w).values()) == pytest.approx(1.0)
    b = build_weights(intent(cheap_intent=True, budget={"min": None, "max": 10 * LAKH}))
    assert b["criteria"]["price"]["weight"] == pytest.approx(config.PRICE_CHEAP_WEIGHT)


def test_budget_without_cheap_intent_leaves_weights_as_before():
    """price weight 0; the other spec weights are exactly the pre-change normalised multipliers."""
    w = build_weights(intent(use_case="family", budget={"min": None, "max": 12 * LAKH}))
    assert w["criteria"]["price"]["weight"] == 0.0
    base = {"value_for_budget": 1.5 * 1.3, "safety": 1.5 * 2, "running_cost": 1.5 * 1.2, "comfort_features": 1.5,
            "space_practicality": 2.0, "performance": 1.0, "tech_assist": 1.0}
    total = sum(base.values())
    for c, v in base.items():
        assert w["criteria"][c]["weight"] == pytest.approx(v / total)


def test_price_can_be_switched_off_and_weights_stay_normalised():
    w = build_weights(intent(), {"price": False})
    assert w["criteria"]["price"]["weight"] == 0.0 and sum(spec_weights(w).values()) == pytest.approx(1.0)
    for cls in ("spec", "expert", "owner"):
        assert sum(v["weight"] for v in w["criteria"].values() if v["class"] == cls) == pytest.approx(1.0)


# ------------------------------------------------------------------ criterion

def test_price_criterion_is_lower_is_better_and_relative_to_the_segment():
    rows = [dict(model=f"S{i}", body_type="suv", price_ex_showroom=(8 + i) * LAKH) for i in range(9)]
    rows += [dict(model=f"H{i}", body_type="hatchback", price_ex_showroom=(4 + 0.5 * i) * LAKH) for i in range(9)]
    df = make_frame(rows)
    v = compute_criteria(df).values["price"]
    assert v.iloc[0] > v.iloc[8]                       # cheaper suv scores higher than the dearest suv
    assert v.iloc[0] == pytest.approx(v.iloc[9])       # cheapest of each segment scores the same: relative to the segment
    assert v.iloc[9] > 0.9 and v.iloc[8] < 0.1


def test_price_criterion_unknown_stays_unknown():
    df = make_frame([dict(model="A", price_ex_showroom=float("nan")), dict(model="B")])
    v = compute_criteria(df).values["price"]
    assert pd.isna(v.iloc[0]) and not pd.isna(v.iloc[1])


def test_price_is_part_of_the_spec_class():
    assert "price" in SPEC_CRITERIA and CRITERION_CLASS["price"] == "spec"


# ------------------------------------------------------------------ displayed variant (hand-built)

def _scored(rows):
    df = make_frame(rows)
    table, _ = score_candidates(df, intent(required_features=["sunroof"]), evidence=NO_EVIDENCE)
    return df.join(table)


def test_displayed_variant_is_cheapest_with_all_requested_features_not_the_top_trim():
    s = _scored([
        dict(model="A", variant="base", price_ex_showroom=8 * LAKH, sunroof=False),
        dict(model="A", variant="mid", price_ex_showroom=10 * LAKH, sunroof=True),
        dict(model="A", variant="top", price_ex_showroom=14 * LAKH, sunroof=True, adas_available=True, camera_360=True),
    ])
    out = displayed_variant_per_model(s)
    assert list(out["variant"]) == ["mid"]


def test_displayed_variant_without_requested_features_is_simply_the_cheapest():
    df = make_frame([dict(model="A", variant="top", price_ex_showroom=14 * LAKH, adas_available=True),
                     dict(model="A", variant="base", price_ex_showroom=8 * LAKH, adas_available=False)])
    table, _ = score_candidates(df, intent(), evidence=NO_EVIDENCE)
    assert list(displayed_variant_per_model(df.join(table))["variant"]) == ["base"]


def test_displayed_variant_with_two_features_none_has_both_takes_most_then_cheapest():
    df = make_frame([
        dict(model="A", variant="v1", price_ex_showroom=9 * LAKH, sunroof=True, adas_available=None),
        dict(model="A", variant="v2", price_ex_showroom=8 * LAKH, sunroof=True, adas_available=None),
        dict(model="A", variant="v3", price_ex_showroom=7 * LAKH, sunroof=None, adas_available=None),
    ])
    table, _ = score_candidates(df, intent(required_features=["sunroof", "adas"]), evidence=NO_EVIDENCE)
    assert list(displayed_variant_per_model(df.join(table))["variant"]) == ["v2"]


# ------------------------------------------------------------------ integration on the real catalogue

def _cheapest_models_by_min_price():
    c = get_catalogue()
    return c.groupby(["make", "model"])["price_ex_showroom"].min().sort_values()


def test_sunroof_under_15_lakh_shows_the_cheapest_qualifying_variant_per_model():
    r = recommend("SUV with sunroof under 15 lakh", evidence=NO_EVIDENCE)
    cat = get_catalogue()
    assert r["recommendations"]
    for card in r["recommendations"]:
        qual = cat[(cat["make"] == card["Make"]) & (cat["model"] == card["Model"]) & (cat["body_type"] == "suv")
                   & (cat["sunroof"] == True) & (cat["price_ex_showroom"] <= 15 * LAKH)]  # noqa: E712
        assert card["Ex-Showroom_Price"] == qual["price_ex_showroom"].min(), card["Model"]
        assert "sunroof" in card["matched_features"] and card["missing_features"] == []
        # score and shown price come from the same variant
        assert card["variant_id"] in set(qual["variant_id"])
        assert card["Ex-Showroom_Price"] <= 15 * LAKH
    # not the dearest trim: at least one model has a dearer qualifying variant than the one shown
    assert any(
        cat[(cat["make"] == c["Make"]) & (cat["model"] == c["Model"]) & (cat["sunroof"] == True)
            & (cat["price_ex_showroom"] <= 15 * LAKH)]["price_ex_showroom"].max() > c["Ex-Showroom_Price"]  # noqa: E712
        for c in r["recommendations"])


def test_budget_query_without_cheap_intent_keeps_weights_and_shows_cheapest_variants():
    r = recommend("petrol SUV under 12 lakh", evidence=NO_EVIDENCE)
    assert r["weights"]["price"]["weight"] == 0.0
    cat = get_catalogue()
    for card in r["recommendations"]:
        qual = cat[(cat["make"] == card["Make"]) & (cat["model"] == card["Model"]) & (cat["fuel_type"] == "petrol")
                   & (cat["body_type"] == "suv") & (cat["price_ex_showroom"] <= 12 * LAKH)]
        assert card["Ex-Showroom_Price"] == qual["price_ex_showroom"].min()


def test_cheapest_car_returns_the_lowest_priced_cars_first():
    r = recommend("cheapest car", evidence=NO_EVIDENCE)
    order = {k: i for i, k in enumerate(_cheapest_models_by_min_price().index)}
    ranks = [order[(c["Make"], c["Model"])] for c in r["recommendations"]]
    prices = [c["Ex-Showroom_Price"] for c in r["recommendations"]]
    assert ranks[0] == 0                                    # the lowest-priced model in the catalogue is first
    assert sum(1 for x in ranks if x < 16) >= 6, ranks      # most of the list is among the 16 cheapest models
    assert max(prices) < 9 * LAKH
    assert r["weights"]["price"]["weight"] == pytest.approx(config.PRICE_CHEAP_WEIGHT)
    assert any("Price prioritised" in x["text"] for x in r["recommendations"][0]["reasons"])


def test_cheapest_automatic_suv_is_ascending_price_dominant():
    r = recommend("cheapest automatic SUV", evidence=NO_EVIDENCE)
    cat = get_catalogue()
    cards = r["recommendations"]
    assert len(cards) >= 5
    for c in cards:
        row = cat[cat["variant_id"] == c["variant_id"]].iloc[0]
        assert row["body_type"] == "suv" and row["transmission_family"] == "automatic"
    prices = [c["Ex-Showroom_Price"] for c in cards]
    suv_auto = cat[(cat["body_type"] == "suv") & (cat["transmission_family"] == "automatic")]
    model_min = suv_auto.groupby(["make", "model"])["price_ex_showroom"].min().sort_values()
    # the cheapest automatic SUV models make up the list, and price falls toward the top of the ranking
    assert sum(1 for c in cards if model_min.index.get_loc((c["Make"], c["Model"])) < 12) >= len(cards) - 2
    top3, bottom3 = prices[:3], prices[-3:]
    assert sum(top3) / 3 < sum(bottom3) / 3 or sum(top3) / 3 < model_min.median()
    assert cards[0]["Ex-Showroom_Price"] <= model_min.iloc[5]
