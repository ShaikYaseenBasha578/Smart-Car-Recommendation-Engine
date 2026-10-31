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
        "use_case": None,
        "exclude_fuel_types": [],
        "exclude_body_types": [],
        "models": [],
        "reference_models": [],
        "unsupported_terms": [],
        "soft_preferences": [],
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
    ("no AMT please", expected(transmission=trans("automatic", exclude=["amt"]))),
    ("avoid AMT", expected(transmission=trans("automatic", exclude=["amt"]))),
    ("automatic but not AMT", expected(transmission=trans("automatic", exclude=["amt"]))),
    ("electric SUV", expected(fuel_types=["electric"], body_types=["suv"])),
    ("I need a car to drive at the office", expected(use_case="commute")),
    ("something I can park at the mall", expected()),
    ("need at least 5 seats", expected(seats_min=5)),
    ("automatic or manual both fine", expected()),
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
    ("ADAS with adaptive cruise control", expected(required_features=["adas", "cruise_control"])),
    ("level 2 ADAS and panoramic sunroof", expected(required_features=["sunroof", "adas"])),
    ("360 camera and ventilated seats", expected(required_features=["camera_360", "ventilated_seats"])),
    ("wireless charging, HUD, android auto and carplay",
     expected(required_features=["wireless_charging", "heads_up_display", "android_auto", "apple_carplay"])),
    ("no sunroof needed", expected()),
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
    ("good car", expected()),
    ("best car for me", expected()),
    ("I want a car", expected()),
    ("which car should I buy?", expected()),
    ("suggest something nice", expected()),
    ("", expected()),
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
    ("mercedes or audi sedan", expected(unsupported_terms=["Audi", "Mercedes-Benz"], body_types=["sedan"])),
    ("Mini Cooper", expected(unsupported_terms=["Mini"])),
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
