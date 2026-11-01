"""Additive /predict fields used by the result cards (KB path): mileage_km_per_kg, ev_range_km,
power_bhp, airbags, boot_space_litres. Each is the catalogue value of the returned variant, or None."""

import math

import pandas as pd
import pytest

from services.new_car_service import number_or_none

CARD_FIELDS = {
    "mileage_km_per_kg": (float, False),
    "ev_range_km": (int, True),
    "power_bhp": (float, False),
    "airbags": (int, True),
    "boot_space_litres": (int, True),
}


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(scope="module")
def catalogue():
    from services.catalogue import get_catalogue
    return get_catalogue()


def predict(client, monkeypatch, query):
    monkeypatch.setenv("DATA_SOURCE", "kb")
    response = client.post("/predict", json={"query": query})
    assert response.status_code == 200
    return response.get_json()["recommendations"]


def catalogue_row(catalogue, car):
    rows = catalogue[(catalogue["make"] == car["Make"]) & (catalogue["model"] == car["Model"])
                     & (catalogue["variant"] == car["Variant"])]
    assert len(rows) >= 1, car["Variant"]
    return rows.iloc[0]


@pytest.mark.parametrize("query", ["CNG gaadi under 8 lakh", "EV under 15 lakh", "sunroof wali SUV 12 lakh ke andar"])
def test_card_fields_match_the_catalogue(client, monkeypatch, catalogue, query):
    recs = predict(client, monkeypatch, query)
    assert recs
    for car in recs:
        row = catalogue_row(catalogue, car)
        for field, (kind, _) in CARD_FIELDS.items():
            assert field in car, field
            value, expected = car[field], row[field]
            if pd.isna(expected):
                assert value is None, (field, car["Model"])
            else:
                assert isinstance(value, kind), (field, value)
                assert math.isclose(value, float(expected)), (field, value, expected)


def test_every_ev_result_has_a_range(client, monkeypatch):
    recs = predict(client, monkeypatch, "EV under 15 lakh")
    assert recs and all(isinstance(car["ev_range_km"], int) and car["ev_range_km"] > 0 for car in recs)


def test_cng_results_carry_km_per_kg(client, monkeypatch):
    recs = predict(client, monkeypatch, "CNG gaadi under 8 lakh")
    assert any(car["mileage_km_per_kg"] for car in recs)


def test_existing_keys_unchanged(client, monkeypatch):
    car = predict(client, monkeypatch, "7 seater under 15 lakh")[0]
    for key in ("Make", "Model", "Variant", "Ex-Showroom_Price", "Power", "ARAI_Certified_Mileage",
                "Transmission", "Fuel_Type", "carImage", "carDekhoLink", "ranking_score", "match_reasons",
                "transmission_label", "matched_features", "unverified", "safety", "matching_variant_count"):
        assert key in car, key
    assert car["Power"] == car["power_bhp"]


def test_number_or_none():
    assert number_or_none(float("nan")) is None
    assert number_or_none(None) is None
    assert number_or_none(6.0, whole=True) == 6 and isinstance(number_or_none(6.0, whole=True), int)
    assert number_or_none(26.4) == 26.4
