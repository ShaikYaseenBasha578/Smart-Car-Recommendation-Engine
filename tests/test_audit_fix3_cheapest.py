"""Audit 2026-11-16, fix 3: an explicit superlative ("cheapest", "lowest price", "sabse sasti") is an ordering
instruction: the cheapest variant of each model, models in ascending price, on the real catalogue."""
import pytest

from services.catalogue import get_catalogue
from services.intent_v2 import parse_intent
from services.recsys.api import recommend

SUPERLATIVES = ["cheapest car in India", "cheapest car", "sabse sasti car", "lowest price car", "sabse sasta gaadi"]


@pytest.mark.parametrize("q", SUPERLATIVES)
def test_superlative_sets_price_order(q):
    assert parse_intent(q)["price_order"] is True


@pytest.mark.parametrize("q", ["cheapest to maintain SUV", "cheapest to run hatchback", "affordable family car",
                               "budget SUV under 15 lakh", "cheaper than Creta", "SUV under 10 lakh"])
def test_other_wording_is_not_an_ordering_instruction(q):
    assert parse_intent(q)["price_order"] is False


@pytest.mark.parametrize("q", SUPERLATIVES)
def test_pure_cheapest_returns_the_catalogues_cheapest_variants_ascending_one_per_model(q):
    cat = get_catalogue()
    cards = recommend(q)["recommendations"]
    prices = [c["Ex-Showroom_Price"] for c in cards]
    assert prices[0] == cat["price_ex_showroom"].min()
    assert prices == sorted(prices)
    models = [(c["Make"], c["Model"]) for c in cards]
    assert len(set(models)) == len(models)
    for c in cards:      # each card is its model's cheapest variant in the whole catalogue
        same = cat[(cat["make"] == c["Make"]) & (cat["model"] == c["Model"])]
        assert c["Ex-Showroom_Price"] == same["price_ex_showroom"].min()
    # and they are the cheapest models: no model outside the list has a cheaper cheapest variant
    cheapest_by_model = cat.groupby(["make", "model"])["price_ex_showroom"].min().sort_values()
    assert prices[-1] <= cheapest_by_model.iloc[len(cards)]


def test_cheapest_within_a_constraint_is_cheapest_inside_it():
    cat = get_catalogue()
    cards = recommend("cheapest SUV under 15 lakh")["recommendations"]
    prices = [c["Ex-Showroom_Price"] for c in cards]
    assert prices == sorted(prices)
    suv = cat[(cat["body_type"] == "suv") & (cat["price_ex_showroom"] <= 1500000)]
    assert prices[0] == suv["price_ex_showroom"].min()
    assert all(c["Ex-Showroom_Price"] <= 1500000 for c in cards)
