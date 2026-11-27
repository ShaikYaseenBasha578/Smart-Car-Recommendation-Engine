import csv
from pathlib import Path

import pytest

from services.intent_v2 import BODY_TYPES, FEATURES, FUEL_TYPES, SOFT_PREFERENCES, TRANSMISSION_TYPES, parse_intent

ROOT = Path(__file__).resolve().parents[1]

L = 100_000  # one lakh
AUTO = {"family": "automatic", "include_types": [], "exclude_types": []}
MANUAL = {"family": "manual", "include_types": [], "exclude_types": []}
NO_TRANS = {"family": None, "include_types": [], "exclude_types": []}


def expected(**fields):
    base = {
        "budget": {"min": None, "max": None},
        "corrections": [],
        "body_types": [],
        "fuel_types": [],
        "transmission": NO_TRANS,
        "seats_min": None,
        "makes": [],
        "required_features": [],
        "min_airbags": None,
        "min_safety_stars": None,
        "min_boot_space_litres": None,
        "min_ground_clearance_mm": None,
        "min_ev_range_km": None,
        "min_mileage_kmpl": None,
        "min_mileage_km_per_kg": None,
        "max_ev_range_km": None,
        "max_ground_clearance_mm": None,
        "max_boot_space_litres": None,
        "max_mileage_kmpl": None,
        "max_mileage_km_per_kg": None,
        "max_length_mm": None,
        "use_case": None,
        "cheap_intent": False,
        "price_order": False,
        "exclude_features": [],
        "exclude_makes": [],
        "exclude_fuel_types": [],
        "exclude_body_types": [],
        "models": [],
        "reference_models": [],
        "unsupported_terms": [],
        "soft_preferences": [],
        "assumed": {"body_types": [], "fuel_types": []},
        "vague": False,
        "unsupported_only": False,
    }
    for key, value in fields.items():
        assert key in base, key
        base[key] = value
    return base


def trans(family=None, include=(), exclude=()):
    return {"family": family, "include_types": list(include), "exclude_types": list(exclude)}


def budget(lo=None, hi=None):
    return {"min": lo, "max": hi}


CASES = [
    # --- transmission ---
    ("automatic SUV", expected(transmission=AUTO, body_types=["suv"])),
    ("auto gearbox hatchback", expected(transmission=AUTO, body_types=["hatchback"])),
    ("petrol AT under 10 lakh", expected(transmission=AUTO, fuel_types=["petrol"], budget=budget(hi=10 * L))),
    ("an AT car for city", expected(transmission=AUTO, use_case="city")),
    ("AMT car", expected(transmission=trans("automatic", ["amt"]))),
    ("DSG sedan", expected(transmission=trans("automatic", ["dct"]), body_types=["sedan"])),
    ("dual clutch gearbox", expected(transmission=trans("automatic", ["dct"]))),
    ("CVT or IVT", expected(transmission=trans("automatic", ["cvt", "e_cvt"]))),
    ("torque converter automatic", expected(transmission=trans("automatic", ["torque_converter"]))),
    ("TC gearbox diesel", expected(transmission=trans("automatic", ["torque_converter"]), fuel_types=["diesel"])),
    ("iMT hatchback", expected(transmission=trans("manual", ["imt"]), body_types=["hatchback"])),
    ("manual diesel", expected(transmission=MANUAL, fuel_types=["diesel"])),
    ("stick shift please", expected(transmission=MANUAL)),
    ("MT variant", expected(transmission=MANUAL)),
    ("no AMT please", expected(transmission=trans(None, exclude=["amt"]))),   # PR 4: "no AMT" drops AMT only
    ("avoid AMT", expected(transmission=trans(None, exclude=["amt"]))),
    ("automatic but not AMT", expected(transmission=trans("automatic", exclude=["amt"]))),
    ("electric SUV", expected(fuel_types=["electric"], body_types=["suv"])),
    ("I need a car to drive at the office", expected(use_case="commute")),
    ("something I can park at the mall", expected(vague=True)),
    ("need at least 5 seats", expected(seats_min=5)),
    ("automatic or manual both fine", expected(vague=True)),
    # --- Hinglish ---
    ("15 lakh tak automatic chahiye, AMT nahi",
     expected(budget=budget(hi=15 * L), transmission=trans("automatic", exclude=["amt"]))),
    ("family ke liye 7 seater diesel", expected(seats_min=7, fuel_types=["diesel"], use_case="family")),
    ("sunroof wali SUV 12 lakh ke andar",
     expected(required_features=["sunroof"], body_types=["suv"], budget=budget(hi=12 * L))),
    ("CNG gaadi under 8 lakh", expected(fuel_types=["cng"], budget=budget(hi=8 * L))),
    ("10 lakh ke aas paas petrol hatchback",
     expected(budget=budget(850_000, 1_150_000), fuel_types=["petrol"], body_types=["hatchback"])),
    ("mujhe manual gaadi chahiye 6 lakh se kam", expected(transmission=MANUAL, budget=budget(hi=6 * L))),
    ("papa ke liye automatic sedan, budget 15 lakh",
     expected(transmission=AUTO, body_types=["sedan"], budget=budget(hi=15 * L), use_case="parents")),
    ("electric car chahiye 400 km range wali, 20 lakh tak",
     expected(fuel_types=["electric"], min_ev_range_km=400, budget=budget(hi=20 * L))),
    ("Tata ya Mahindra ki SUV, 5 star safety honi chahiye",
     expected(makes=["Mahindra", "Tata"], body_types=["suv"], min_safety_stars=5)),
    ("diesel nahi chahiye, petrol automatic 10 se 12 lakh",
     expected(fuel_types=["petrol"], exclude_fuel_types=["diesel"], transmission=AUTO, budget=budget(10 * L, 12 * L))),
    ("6 airbags wali gaadi 9 lakh tak", expected(min_airbags=6, budget=budget(hi=9 * L))),
    ("clutchless gaadi chahiye", expected(transmission=trans("manual", ["imt"]))),
    # --- features / numeric ---
    ("6 airbags", expected(min_airbags=6)),
    ("5-star rated family car", expected(min_safety_stars=5, use_case="family")),
    ("EV with 400 km range", expected(fuel_types=["electric"], min_ev_range_km=400)),
    ("200mm ground clearance", expected(min_ground_clearance_mm=200)),
    ("boot 400 litres", expected(min_boot_space_litres=400)),
    ("20+ kmpl mileage", expected(min_mileage_kmpl=20.0)),
    # CNG mileage is its own unit and field
    ("CNG car 25 km/kg", expected(fuel_types=["cng"], min_mileage_km_per_kg=25.0)),
    ("cng with 25 km per kg", expected(fuel_types=["cng"], min_mileage_km_per_kg=25.0)),
    ("mileage 28 km/kg", expected(min_mileage_km_per_kg=28.0)),
    ("above 26.5 kmpkg", expected(min_mileage_km_per_kg=26.5)),
    # upper bounds are honoured (step 2b); never read as a minimum
    ("under 30 km/kg", expected(max_mileage_km_per_kg=30.0)),
    ("mileage under 30 km/kg", expected(max_mileage_km_per_kg=30.0)),
    ("CNG with at most 26 km/kg", expected(fuel_types=["cng"], max_mileage_km_per_kg=26.0)),
    ("mileage between 18 and 22 kmpl", expected(min_mileage_kmpl=18.0, max_mileage_kmpl=22.0)),
    ("mileage under 15 kmpl", expected(max_mileage_kmpl=15.0)),
    ("ground clearance below 180 mm", expected(max_ground_clearance_mm=180.0)),
    ("ground clearance under 190 mm hatchback", expected(body_types=["hatchback"], max_ground_clearance_mm=190.0)),
    ("hatchback with boot space under 300 litres", expected(body_types=["hatchback"], max_boot_space_litres=300.0)),
    ("EV range below 350 km", expected(max_ev_range_km=350.0)),
    ("20 kmpl petrol or 28 km/kg cng", expected(fuel_types=["petrol", "cng"], min_mileage_kmpl=20.0,
                                                 min_mileage_km_per_kg=28.0)),
    ("ADAS with adaptive cruise control", expected(required_features=["adas", "cruise_control"])),
    ("level 2 ADAS and panoramic sunroof", expected(required_features=["sunroof", "adas"])),
    ("360 camera and ventilated seats", expected(required_features=["camera_360", "ventilated_seats"])),
    ("wireless charging, HUD, android auto and carplay",
     expected(required_features=["wireless_charging", "heads_up_display", "android_auto", "apple_carplay"])),
    # negated features are exclusions (step 2a), not dropped
    ("no sunroof needed", expected(exclude_features=["sunroof"])),
    ("no sunroof", expected(exclude_features=["sunroof"])),
    ("without ADAS under 15 lakh", expected(exclude_features=["adas"], budget=budget(hi=15 * L))),
    ("sunroof nahi chahiye", expected(exclude_features=["sunroof"])),
    ("SUV without sunroof and without ventilated seats",
     expected(body_types=["suv"], exclude_features=["sunroof", "ventilated_seats"])),
    ("sunroof but no ADAS", expected(required_features=["sunroof"], exclude_features=["adas"])),
    # negated makes are exclusions (step 2a)
    ("not Tata", expected(exclude_makes=["Tata"])),
    ("hybrid not Toyota", expected(fuel_types=["hybrid"], exclude_makes=["Toyota"])),
    ("diesel not wanted", expected(exclude_fuel_types=["diesel"])),
    ("Maruti nahi chahiye", expected(exclude_makes=["Maruti Suzuki"])),
    ("no Hyundai or Kia", expected(exclude_makes=["Hyundai", "Kia"])),
    ("SUV under 15 lakh, not Mahindra", expected(body_types=["suv"], budget=budget(hi=15 * L), exclude_makes=["Mahindra"])),
    ("7 seater with 6 airbags under 20 lakh", expected(seats_min=7, min_airbags=6, budget=budget(hi=20 * L))),
    # --- budget ---
    ("under 10 lakh", expected(budget=budget(hi=10 * L))),
    ("SUV between 8 and 12 lakh", expected(body_types=["suv"], budget=budget(8 * L, 12 * L))),
    ("10-15 lakh sedan", expected(body_types=["sedan"], budget=budget(10 * L, 15 * L))),
    ("1 to 1.5 crore", expected(budget=budget(10_000_000, 15_000_000))),
    ("around 10 lakh", expected(budget=budget(850_000, 1_150_000))),
    ("under 800k", expected(budget=budget(hi=800_000))),
    ("budget 12.5L", expected(budget=budget(hi=1_250_000))),
    ("above 20 lakh", expected(budget=budget(lo=20 * L))),
    ("Rs 7,50,000 max", expected(budget=budget(hi=750_000))),
    ("1.2L turbo petrol", expected(fuel_types=["petrol"])),
    # --- vague: no invented constraints ---
    ("good car", expected(vague=True)),
    ("best car for me", expected(vague=True)),
    ("I want a car", expected(vague=True)),
    ("which car should I buy?", expected(vague=True)),
    ("suggest something nice", expected(vague=True)),
    ("", expected(vague=True)),
    # --- v2.1: exclusions ---
    ("diesel nahi chahiye automatic SUV",
     expected(exclude_fuel_types=["diesel"], transmission=AUTO, body_types=["suv"])),
    ("no SUV, sedan or hatchback", expected(exclude_body_types=["suv"], body_types=["hatchback", "sedan"])),
    ("avoid diesel and CNG", expected(exclude_fuel_types=["diesel", "cng"])),
    ("petrol car but not a hatchback", expected(fuel_types=["petrol"], exclude_body_types=["hatchback"])),
    # --- v2.1: models ---
    ("scorpio n diesel", expected(models=["Scorpio-N"], fuel_types=["diesel"])),
    ("xuv 3xo or xuv3xo AMT", expected(models=["XUV 3XO"], transmission=trans("automatic", ["amt"]))),
    ("Hyundai Creta automatic", expected(models=["Creta"], makes=["Hyundai"], transmission=AUTO)),
    ("innova for family", expected(models=["Innova Crysta", "Innova Hycross"], use_case="family")),
    ("honda city or verna", expected(models=["City", "Verna"], makes=["Honda"])),
    ("car for city driving", expected(use_case="city")),
    ("something like Creta", expected(body_types=["suv"], reference_models=["Creta"])),
    ("creta jaisi gaadi under 15 lakh", expected(body_types=["suv"], reference_models=["Creta"], budget=budget(hi=15 * L))),
    ("Nexon EV vs Punch EV", expected(models=["Nexon EV", "Punch EV"])),
    # --- v2.1: unsupported brands ---
    ("BMW SUV", expected(unsupported_terms=["BMW"], body_types=["suv"])),
    ("Jeep Compass", expected(unsupported_terms=["Jeep"], unsupported_only=True)),
    ("mercedes or audi sedan", expected(unsupported_terms=["Audi", "Mercedes-Benz"], body_types=["sedan"])),
    ("Mini Cooper", expected(unsupported_terms=["Mini"], unsupported_only=True)),
    ("mini SUV under 8 lakh", expected(body_types=["suv"], budget=budget(hi=8 * L))),
    # --- v2.1: soft preferences (never hard constraints) ---
    ("good mileage hatchback", expected(soft_preferences=["mileage"], body_types=["hatchback"])),
    ("spacious car for big family", expected(soft_preferences=["space"], use_case="family")),
    ("powerful and fun to drive", expected(soft_preferences=["performance"], use_case="enthusiast")),
    ("comfortable and safe car for parents", expected(soft_preferences=["comfort", "safety"], use_case="parents")),
    ("fully loaded feature rich SUV", expected(soft_preferences=["features"], body_types=["suv"])),
    # --- seats as a verb (paper queries_v0 phrasing) ---
    ("I need a manual SUV under 3 lakh that seats 6. What should I buy?",
     expected(transmission=MANUAL, body_types=["suv"], budget=budget(hi=3 * L), seats_min=6)),
    ("Looking for a van that seats 9. Which car would you recommend?", expected(body_types=["van"], seats_min=9)),
    ("Can you suggest a petrol sedan that seats 5 under ₹3,00,000?",
     expected(fuel_types=["petrol"], body_types=["sedan"], seats_min=5, budget=budget(hi=300_000))),
    ("MPV that seats at least 7", expected(body_types=["mpv"], seats_min=7)),
    ("seating for 8", expected(seats_min=8)),
]


@pytest.mark.parametrize("query,want", CASES, ids=[c[0] or "<empty>" for c in CASES])
def test_parse_intent(query, want):
    got = parse_intent(query)
    trace = got.pop("trace")
    assert got == want, trace


def test_output_vocab_matches_catalogue():
    with (ROOT / "data" / "catalogue.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert set(BODY_TYPES) == {r["body_type"] for r in rows}
    assert set(FUEL_TYPES) == {r["fuel_type"] for r in rows}
    assert set(TRANSMISSION_TYPES) == {r["transmission_type"] for r in rows}
    makes = {r["make"] for r in rows}
    models = {r["model"] for r in rows}
    for query, _ in CASES:
        out = parse_intent(query)
        assert set(out["makes"]) <= makes
        assert set(out["models"]) <= models
        assert not set(out["unsupported_terms"]) & makes
        assert set(out["required_features"]) <= set(FEATURES)
        assert set(out["soft_preferences"]) <= set(SOFT_PREFERENCES)


def test_rules_only_mode_has_no_ml_trace():
    out = parse_intent("family ke liye 7 seater diesel", use_ml=False)
    assert out["use_case"] == "family"
    assert not any(" <- ml " in t for t in out["trace"])


# ---------------------------------------------------------------- negated ceilings and boot-space minimums

@pytest.mark.parametrize("query", [
    "I can't go above 8 lakh", "cannot go above 8 lakh", "can't exceed 8 lakh", "I can't go over 8 lakh",
    "I won't spend more than 8 lakh", "not more than 8 lakh", "no more than 8 lakh",
    "8 lakh se upar nahi ja sakta", "8 lakh se upar nahi jaunga", "8 lakh se zyada nahi chahiye",
    "8 lakh se kam",
])
def test_negated_or_ceiling_phrasings_set_a_maximum_never_a_minimum(query):
    budget = parse_intent(query)["budget"]
    assert budget == {"min": None, "max": 8 * L}


@pytest.mark.parametrize("query", ["above 8 lakh", "more than 8 lakh", "8 lakh se upar", "at least 8 lakh"])
def test_plain_lower_bound_words_are_still_a_minimum(query):
    assert parse_intent(query)["budget"] == {"min": 8 * L, "max": None}


@pytest.mark.parametrize("query,litres", [
    ("500 litres se zyada boot", 500), ("500 litre se zyada ka boot", 500), ("boot 400 litre se zyada", 400),
    ("boot space more than 450 litres", 450), ("at least 400 L boot", 400), ("boot space at least 450 litres", 450),
])
def test_boot_space_minimum_is_parsed(query, litres):
    out = parse_intent(query)
    assert out["min_boot_space_litres"] == litres
    assert out["max_boot_space_litres"] is None
    assert out["budget"] == {"min": None, "max": None}     # the litres are not read as a price


def test_boot_space_se_kam_is_a_maximum_and_ceiling_plus_boot_combine():
    out = parse_intent("boot 400 litre se kam")
    assert out["max_boot_space_litres"] == 400 and out["min_boot_space_litres"] is None
    out = parse_intent("can't go above 8 lakh, boot space more than 450 litres")
    assert out["budget"] == {"min": None, "max": 8 * L} and out["min_boot_space_litres"] == 450


def _filters(query):
    o = parse_intent(query)
    return {k: o[k] for k in ("makes", "exclude_makes", "body_types", "exclude_body_types", "fuel_types", "exclude_fuel_types")}


def test_not_after_a_term_followed_by_a_new_term_does_not_negate_the_first_term():
    out = parse_intent("Tata SUV not diesel under 15 lakh")
    assert out["makes"] == ["Tata"] and out["body_types"] == ["suv"]
    assert out["exclude_fuel_types"] == ["diesel"] and out["fuel_types"] == []
    assert out["exclude_makes"] == [] and out["exclude_body_types"] == []
    assert out["budget"] == {"min": None, "max": 15 * L}
    out = parse_intent("Hyundai sedan not petrol")
    assert out["makes"] == ["Hyundai"] and out["body_types"] == ["sedan"] and out["exclude_fuel_types"] == ["petrol"]
    assert out["exclude_makes"] == [] and out["exclude_body_types"] == []
    out = parse_intent("SUV not diesel under 15 lakh")
    assert out["body_types"] == ["suv"] and out["exclude_body_types"] == [] and out["exclude_fuel_types"] == ["diesel"]


def test_automatic_not_amt_excludes_amt_and_keeps_the_automatic_family():
    t = parse_intent("automatic not AMT")["transmission"]
    assert t["family"] == "automatic" and t["exclude_types"] == ["amt"]


@pytest.mark.parametrize("query,field,value", [
    ("diesel not wanted", "exclude_fuel_types", ["diesel"]),
    ("diesel not at all", "exclude_fuel_types", ["diesel"]),
    ("no diesel SUV", "exclude_fuel_types", ["diesel"]),
    ("SUV, diesel nahi", "exclude_fuel_types", ["diesel"]),
    ("avoid diesel and CNG", "exclude_fuel_types", ["diesel", "cng"]),
    ("not Tata", "exclude_makes", ["Tata"]),
    ("hybrid not Toyota", "exclude_makes", ["Toyota"]),
])
def test_genuine_negations_still_negate(query, field, value):
    assert _filters(query)[field] == value


def test_amt_wali_nahi_chahiye_and_hybrid_not_toyota_keep_the_right_side():
    assert parse_intent("AMT wali nahi chahiye")["transmission"]["exclude_types"] == ["amt"]
    assert _filters("hybrid not Toyota")["fuel_types"] == ["hybrid"]


def test_a_recognised_term_between_the_negation_word_and_a_term_blocks_the_negation():
    out = parse_intent("no diesel SUV")
    assert out["body_types"] == ["suv"] and out["exclude_body_types"] == [] and out["exclude_fuel_types"] == ["diesel"]
    out = parse_intent("no diesel SUV under 12 lakh")
    assert out["body_types"] == ["suv"] and out["exclude_body_types"] == [] and out["budget"]["max"] == 12 * L
    out = parse_intent("no sunroof SUV")
    assert out["body_types"] == ["suv"] and out["exclude_body_types"] == [] and out["exclude_features"] == ["sunroof"]
    out = parse_intent("avoid diesel and CNG SUV")
    assert out["exclude_fuel_types"] == ["diesel", "cng"] and out["body_types"] == ["suv"] and out["exclude_body_types"] == []


@pytest.mark.parametrize("query,field,value", [
    ("avoid diesel and CNG", "exclude_fuel_types", ["diesel", "cng"]),
    ("no diesel or CNG", "exclude_fuel_types", ["diesel", "cng"]),
    ("not Tata or Mahindra", "exclude_makes", ["Mahindra", "Tata"]),
])
def test_coordinated_negations_still_reach_every_term(query, field, value):
    assert _filters(query)[field] == value


def test_prefix_negation_of_amt_still_works():
    assert parse_intent("no AMT")["transmission"]["exclude_types"] == ["amt"]
    assert parse_intent("do not want an AMT")["transmission"]["exclude_types"] == ["amt"]
    out = parse_intent("without AMT Creta")
    assert out["transmission"]["exclude_types"] == ["amt"] and out["models"] == ["Creta"]


@pytest.mark.parametrize("query,make", [("SUV diesel nahi", []), ("SUV diesel nahi chahiye", []), ("Tata SUV diesel nahi", ["Tata"])])
def test_postfix_nahi_after_a_later_term_negates_only_that_term(query, make):
    out = parse_intent(query)
    assert out["exclude_fuel_types"] == ["diesel"] and out["body_types"] == ["suv"] and out["exclude_body_types"] == []
    assert out["makes"] == make and out["exclude_makes"] == []


@pytest.mark.parametrize("query,fuels", [
    ("diesel nahi", ["diesel"]), ("diesel aur CNG nahi", ["cng", "diesel"]), ("diesel ya CNG nahi chahiye", ["cng", "diesel"]),
    ("SUV, diesel nahi", ["diesel"]),
])
def test_postfix_nahi_still_reaches_coordinated_terms(query, fuels):
    assert sorted(parse_intent(query)["exclude_fuel_types"]) == fuels
    assert parse_intent(query)["fuel_types"] == []


# ------------------------------------------------------------------ PR K: a negated gearbox type never adds a family

import pytest as _pytest_k
from services.intent_v2 import parse_intent_ex as _pk_parse


@_pytest_k.mark.parametrize("q,family,exclude", [
    ("kuch bhi chalega bas CVT nahi, 12 lakh tak", None, ["cvt", "e_cvt"]),
    ("no DCT please", None, ["dct"]),
    ("automatic but no CVT", "automatic", ["cvt", "e_cvt"]),
    ("no manual", "automatic", []),
    ("AMT nahi", None, ["amt"]),
])
def test_negated_gearbox_type_keeps_family_open(q, family, exclude):
    t = _pk_parse(q, use_ml=False)[0]["transmission"]
    assert t["family"] == family
    assert t["exclude_types"] == exclude


def test_cvt_nahi_budget_and_positive_dct_family():
    assert _pk_parse("kuch bhi chalega bas CVT nahi, 12 lakh tak", use_ml=False)[0]["budget"]["max"] == 1200000
    assert _pk_parse("DCT car", use_ml=False)[0]["transmission"]["family"] == "automatic"
