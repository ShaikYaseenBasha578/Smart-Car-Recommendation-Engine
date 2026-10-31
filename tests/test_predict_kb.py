"""End-to-end /predict checks for the KB path (DATA_SOURCE=kb), plus a legacy before/after table.

Run with -s to see the tables.
"""

import math

import pytest

from services.catalogue import get_catalogue
from services.filter_v2 import FEATURE_COLUMNS, MIN_COLUMNS, UNRATED_SAFETY_LABEL, allowed_transmission_types
from services.intent_v2 import parse_intent
from services.twins import complete_twin_pairs

QUERIES = [
    # the 12 Hinglish queries from Phase 2
    "15 lakh tak automatic chahiye, AMT nahi",
    "family ke liye 7 seater diesel",
    "sunroof wali SUV 12 lakh ke andar",
    "CNG gaadi under 8 lakh",
    "10 lakh ke aas paas petrol hatchback",
    "mujhe manual gaadi chahiye 6 lakh se kam",
    "papa ke liye automatic sedan, budget 15 lakh",
    "electric car chahiye 400 km range wali, 20 lakh tak",
    "Tata ya Mahindra ki SUV, 5 star safety honi chahiye",
    "diesel nahi chahiye, petrol automatic 10 se 12 lakh",
    "6 airbags wali gaadi 9 lakh tak",
    "clutchless gaadi chahiye",
    # required extras
    "automatic but not AMT",
    "BMW SUV",
    "something like Creta",
    "diesel nahi chahiye automatic SUV",
    "sedan with sunroof",
    "7 seater under 15 lakh",
    # more coverage
    "Hyundai Creta automatic",
    "spacious family car with good mileage",
    "SUV with ADAS and 360 camera under 25 lakh",
    "DCT petrol under 15 lakh",
    "CVT automatic hatchback",
    "200mm ground clearance SUV under 12 lakh",
    "EV under 15 lakh",
    "Scorpio N diesel automatic",
    "5 star safety sedan",
    "good car",
]

LEGACY_KEYS = {
    "Make": str, "Model": str, "Variant": str, "Ex-Showroom_Price": (int, float),
    "Displacement": (int, float, type(None)), "Power": (int, float, type(None)),
    "ARAI_Certified_Mileage": (int, float, type(None)), "Transmission": str, "Fuel_Type": str,
    "carImage": str, "carDekhoLink": str, "carWaleLink": str, "ranking_score": (int, float), "match_reasons": list,
}
NEW_KEYS = {"transmission_type", "transmission_label", "matched_features", "unverified", "safety",
            "matching_variant_count"}


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def predict(client, monkeypatch, query, source):
    monkeypatch.setenv("DATA_SOURCE", source)
    response = client.post("/predict", json={"query": query})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def nan(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def check_car(row, intent):
    """Assert no hard-constraint violation and no known-false / below-minimum constraint."""
    budget = intent["budget"]
    if budget["min"] is not None:
        assert row["price_ex_showroom"] >= budget["min"]
    if budget["max"] is not None:
        assert row["price_ex_showroom"] <= budget["max"]
    if intent["body_types"]:
        assert row["body_type"] in intent["body_types"]
    assert row["body_type"] not in intent["exclude_body_types"]
    if intent["fuel_types"]:
        assert row["fuel_type"] in intent["fuel_types"]
    assert row["fuel_type"] not in intent["exclude_fuel_types"]
    assert row["transmission_type"] in allowed_transmission_types(intent["transmission"])
    if intent["seats_min"] is not None:
        assert row["seats"] >= intent["seats_min"]
    if intent["models"] or intent["makes"]:
        assert row["model"] in intent["models"] or row["make"] in intent["makes"]

    for feature in intent["required_features"]:
        assert row[FEATURE_COLUMNS[feature][0]] is not False, feature
    for key, (col, _) in MIN_COLUMNS.items():
        if intent[key] is not None and not nan(row[col]):
            assert row[col] >= intent[key], key
    if intent["min_safety_stars"] is not None and not nan(row["safety_stars_adult"]):
        assert row["safety_stars_adult"] >= intent["min_safety_stars"]


@pytest.mark.parametrize("query", QUERIES)
def test_kb_predict(client, monkeypatch, query):
    data = predict(client, monkeypatch, query, "kb")
    intent = parse_intent(query)
    catalogue = get_catalogue().set_index(["model", "variant"], drop=False)

    assert data["parser_used"] == "intent_v2"
    assert set(data["data_as_of"]) == {"exported", "kb_phase"}
    assert data["unsupported_terms"] == intent["unsupported_terms"]

    recs = data["recommendations"]
    # 8 models, plus one extra slot per twin pair that appears in full
    assert len(recs) <= 8 + complete_twin_pairs([(r["Make"], r["Model"]) for r in recs])
    assert len({r["Model"] for r in recs}) == len(recs)  # one variant per model

    flags = []
    for car in recs:
        for key, types in LEGACY_KEYS.items():
            assert isinstance(car[key], types), (key, car[key])
        assert NEW_KEYS <= set(car)
        assert car["matching_variant_count"] >= 1

        row = catalogue.loc[(car["Model"], car["Variant"])]
        check_car(row, intent)
        assert car["transmission_type"] == row["transmission_type"]
        if intent["min_safety_stars"] is not None and nan(row["safety_stars_adult"]):
            assert UNRATED_SAFETY_LABEL in car["unverified"]
        flags.append(len(car["unverified"]))

    assert flags == sorted(flags), "results must be ordered by n_soft_flags"


def test_specific_semantics(client, monkeypatch):
    bmw = predict(client, monkeypatch, "BMW SUV", "kb")
    assert bmw["unsupported_terms"] == ["BMW"] and "BMW" in bmw["message"]
    body_of = dict(zip(get_catalogue()["model"], get_catalogue()["body_type"]))
    assert bmw["recommendations"] and all(body_of[r["Model"]] == "suv" for r in bmw["recommendations"])

    no_amt = predict(client, monkeypatch, "automatic but not AMT", "kb")
    assert no_amt["recommendations"]
    assert all(r["transmission_type"] not in ("amt", "manual", "imt") for r in no_amt["recommendations"])

    clutchless = predict(client, monkeypatch, "clutchless gaadi chahiye", "kb")
    assert {r["transmission_type"] for r in clutchless["recommendations"]} == {"imt"}
    assert all(r["transmission_label"] == "Manual (iMT, clutchless)" for r in clutchless["recommendations"])


def test_summary_tables(client, monkeypatch):
    kb_rows, legacy_rows = [], []
    empty = 0
    for query in QUERIES:
        kb = predict(client, monkeypatch, query, "kb")["recommendations"]
        legacy = predict(client, monkeypatch, query, "legacy").get("recommendations", [])
        empty += not kb
        kb_rows.append((
            query, len(kb), ", ".join(r["Model"] for r in kb[:3]),
            ",".join(sorted({r["transmission_type"] for r in kb})),
            "yes" if any(r["unverified"] for r in kb) else "no",
        ))
        legacy_rows.append((
            query, len(legacy), ", ".join(r["Model"] for r in legacy[:3]),
            len(kb), ", ".join(r["Model"] for r in kb[:3]),
        ))

    print("\n\nKB PATH\nquery | #results | top 3 models | transmission_types | any unverified?")
    for row in kb_rows:
        print(" | ".join(str(x) for x in row))
    print("\nLEGACY vs KB\nquery | legacy # | legacy top 3 | kb # | kb top 3")
    for row in legacy_rows:
        print(" | ".join(str(x) for x in row))
    print(f"\nkb empty results: {empty}/{len(QUERIES)}")

    assert empty / len(QUERIES) <= 0.20
