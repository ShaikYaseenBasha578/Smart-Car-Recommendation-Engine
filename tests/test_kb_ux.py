import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.filter_v2 import REFERENCE_LENGTH_TOLERANCE, REFERENCE_PRICE_BAND
from services.new_car_service import MAX_KB_MODELS, MIN_MAKES_FOR_CAP, select_models
from services.twins import TWIN_GROUPS, complete_twin_pairs

NO_FILTER_INTENT = {"makes": [], "models": []}


def ranked(*cars):
    """A ranked frame from (make, model) pairs, best first."""
    return pd.DataFrame([{"make": make, "model": model} for make, model in cars])


FILLER = [(f"Make{i}", f"Model{i}") for i in range(20)]  # 20 distinct makes, no cap interplay


def names(selected):
    return [c["model"] for c in selected]


# --- twins: extra slot only ---

def test_no_twins_keeps_limit():
    assert len(select_models(ranked(*FILLER), NO_FILTER_INTENT)) == MAX_KB_MODELS


def test_one_twin_pair_adds_one_slot_in_natural_order():
    cars = [FILLER[0], ("Maruti Suzuki", "Fronx"), *FILLER[1:4], ("Toyota", "Urban Cruiser Taisor"), *FILLER[4:]]
    out = names(select_models(ranked(*cars), NO_FILTER_INTENT))
    assert len(out) == MAX_KB_MODELS + 1
    # natural rank order, separate cards, no adjacency forced
    assert out[:6] == ["Model0", "Fronx", "Model1", "Model2", "Model3", "Urban Cruiser Taisor"]


def test_two_twin_pairs_add_two_slots():
    cars = [("Maruti Suzuki", "Fronx"), ("Toyota", "Urban Cruiser Taisor"),
            ("Maruti Suzuki", "Grand Vitara"), ("Toyota", "Urban Cruiser Hyryder"), *FILLER]
    out = select_models(ranked(*cars), NO_FILTER_INTENT)
    assert len(out) == MAX_KB_MODELS + 2
    assert complete_twin_pairs([(c["make"], c["model"]) for c in out]) == 2


def test_half_a_pair_adds_nothing():
    cars = [("Maruti Suzuki", "Fronx"), ("Maruti Suzuki", "Baleno"), *FILLER]
    assert len(select_models(ranked(*cars), NO_FILTER_INTENT)) == MAX_KB_MODELS


def test_extra_slot_still_respects_make_cap():
    # Maruti already has 2 models; the extra slot must go to the next car of another make
    cars = [("Maruti Suzuki", "Fronx"), ("Maruti Suzuki", "Ertiga"), ("Toyota", "Urban Cruiser Taisor"),
            *FILLER[:5], ("Maruti Suzuki", "Baleno"), ("Kia", "Seltos")]
    out = names(select_models(ranked(*cars), NO_FILTER_INTENT))
    assert len(out) == 9 and out[-1] == "Seltos" and "Baleno" not in out


# --- per-make cap: off when fewer than MIN_MAKES_FOR_CAP makes match ---

def test_cap_off_with_few_makes():
    cars = [("Mahindra", f"M{i}") for i in range(4)] + [("Tata", "T0"), ("Tata", "T1")]
    assert MIN_MAKES_FOR_CAP == 4
    assert names(select_models(ranked(*cars), NO_FILTER_INTENT)) == ["M0", "M1", "M2", "M3", "T0", "T1"]


def test_cap_on_with_enough_makes():
    cars = [("Mahindra", f"M{i}") for i in range(4)] + [("Tata", "T0"), ("Kia", "K0"), ("Honda", "H0")]
    assert names(select_models(ranked(*cars), NO_FILTER_INTENT)) == ["M0", "M1", "T0", "K0", "H0"]


def test_twin_groups_exist_in_catalogue():
    pairs = set(zip(get_catalogue()["make"], get_catalogue()["model"]))
    for a, b in TWIN_GROUPS.items():
        assert a in pairs and b in pairs


# --- end to end ---

@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def predict(client, monkeypatch, query):
    monkeypatch.setenv("DATA_SOURCE", "kb")
    response = client.post("/predict", json={"query": query})
    assert response.status_code == 200
    return response.get_json()


@pytest.mark.parametrize("query,pairs", [
    ("petrol SUV under 15 lakh", 1),             # Fronx + Taisor
    ("toyota or maruti spacious family car", 2),  # Ertiga + Rumion, Fronx + Taisor
])
def test_twins_end_to_end(client, monkeypatch, query, pairs):
    recs = predict(client, monkeypatch, query)["recommendations"]
    present = [(r["Make"], r["Model"]) for r in recs]
    assert complete_twin_pairs(present) == pairs
    assert len(recs) == MAX_KB_MODELS + pairs
    assert len(set(present)) == len(present)  # twins stay separate cards


def test_like_creta(client, monkeypatch):
    data = predict(client, monkeypatch, "something like Creta")
    cat = get_catalogue()
    creta = cat.loc[cat["model"] == "Creta", "price_ex_showroom"]
    lo, hi = REFERENCE_PRICE_BAND[0] * creta.min(), REFERENCE_PRICE_BAND[1] * creta.max()
    by_variant = cat.set_index(["model", "variant"])

    recs = data["recommendations"]
    assert recs and all(r["Model"] != "Creta" for r in recs)
    for r in recs:
        row = by_variant.loc[(r["Model"], r["Variant"])]
        assert row["body_type"] == "suv"
        assert lo <= row["price_ex_showroom"] <= hi
        assert r["match_reasons"][0] == "Similar body type, size and price to Creta"
    assert "Exter" not in {r["Model"] for r in recs}


def test_like_creta_with_budget_uses_budget(client, monkeypatch):
    recs = predict(client, monkeypatch, "creta jaisi gaadi under 9 lakh")["recommendations"]
    assert recs and all(r["Ex-Showroom_Price"] <= 900_000 and r["Model"] != "Creta" for r in recs)
    assert all(r["match_reasons"][0] == "Similar body type and size to Creta" for r in recs)


def test_like_nexon_only_similar_length_suvs(client, monkeypatch):
    recs = predict(client, monkeypatch, "like Nexon")["recommendations"]
    cat = get_catalogue()
    nexon = cat.loc[cat["model"] == "Nexon", "length_mm"].median()
    lo, hi = (1 - REFERENCE_LENGTH_TOLERANCE) * nexon, (1 + REFERENCE_LENGTH_TOLERANCE) * nexon
    by_variant = cat.set_index(["model", "variant"])
    assert recs and all(r["Model"] != "Nexon" for r in recs)
    for r in recs:
        row = by_variant.loc[(r["Model"], r["Variant"])]
        assert row["body_type"] == "suv" and lo <= row["length_mm"] <= hi


def test_empty_state_relaxation_hints(client, monkeypatch):
    data = predict(client, monkeypatch, "CVT automatic hatchback")
    assert data["recommendations"] == []
    hints = data["relaxation_hints"]
    assert 1 <= len(hints) <= 3
    assert [h["would_return"] for h in hints] == sorted((h["would_return"] for h in hints), reverse=True)
    for h in hints:
        assert h["would_return"] > 0 and 1 <= len(h["top_models"]) <= 3 and isinstance(h["drop"], str)


def test_non_empty_result_has_no_hints(client, monkeypatch):
    assert "relaxation_hints" not in predict(client, monkeypatch, "sedan with sunroof")


def test_covered_makes_and_placeholder_images(client, monkeypatch):
    data = predict(client, monkeypatch, "Maruti hatchback")
    assert data["covered_makes"] == sorted(get_catalogue()["make"].unique())
    # each card: a brochure photo with its caption, or the hatchback silhouette without one
    recs = data["recommendations"]
    assert recs
    for r in recs:
        if r["imageAttribution"]:
            assert r["carImage"].endswith(".webp") and r["imageAttribution"] == "Maruti Suzuki brochure"
        else:
            assert r["carImage"] == "/static/car_images/placeholders/hatchback.svg"
    assert any(r["imageAttribution"] for r in recs)
    by_model = {r["Model"]: r for r in recs}
    for model in ("Baleno", "WagonR"):  # no brochure photo yet
        if model in by_model:
            assert by_model[model]["carImage"] == "/static/car_images/placeholders/hatchback.svg"
