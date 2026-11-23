import pytest

from services.intent_v2 import parse_intent_ex
from services.recsys.api import recommend
from services.recsys.ignored import MAX_IGNORED, ignored_terms


def terms(q):
    return ignored_terms(parse_intent_ex(q)[1])


@pytest.mark.parametrize("q,expected", [
    ("convertible under 30 lakh", ["convertible"]),
    ("a 4x4 diesel suv", ["4x4 / AWD"]),
    ("all wheel drive suv", ["4x4 / AWD"]),
    ("off roader", ["off-road"]),
    ("V8 sports car", ["sports car", "V6 / V8 / V12"]),
    ("supercar under 50 lakh", ["supercar"]),
    ("estate car under 15 lakh", ["wagon"]),
    ("limo", ["limousine"]),
    ("caravan style camping car", ["camper"]),
    ("white hatchback under 8 lakh", ["colour"]),
    ("garage is small, tight parking space at home", ["size"]),   # "car under 4 m long" is now a length filter (PR 4)
    ("easy entry car for my parents", ["easy entry"]),
])
def test_lexicon_hits(q, expected):
    assert sorted(terms(q)) == sorted(expected)


@pytest.mark.parametrize("q", ["hybrid suv with sunroof", "automatic petrol under 10 lakh", "7 seater diesel with ADAS",
                               "hybrid", "sunroof", "automatic"])
def test_words_the_parser_used_are_not_reported(q):
    assert terms(q) == []


@pytest.mark.parametrize("q", ["gaadi lena hai chalega", "best gearbox for city", "good family car", "suv under 15 lakh",
                               "real estate agent needs a sedan", "vanilla flavoured coffee"])
def test_plain_and_hinglish_queries_report_nothing(q):
    assert terms(q) == []


def test_order_dedupe_and_cap():
    out = terms("convertible coupe roadster limousine van wagon convertible")
    assert out == ["convertible", "coupe", "roadster", "limousine"] and len(out) == MAX_IGNORED
    assert terms("cabriolet convertible") == ["convertible"]


def test_empty_residual():
    assert ignored_terms("") == [] and ignored_terms(None) == []


def test_api_field():
    assert recommend("convertible under 30 lakh")["ignored_terms"] == ["convertible"]
    assert recommend("suv under 15 lakh")["ignored_terms"] == []
    intent = parse_intent_ex("convertible under 30 lakh")[0]
    assert recommend("convertible under 30 lakh", intent=intent)["ignored_terms"] == []


def test_uncovered_brand_is_reported_unsupported():
    for brand in ["Ferrari", "Tesla", "Rolls-Royce", "Aston Martin", "McLaren", "VinFast"]:
        assert parse_intent_ex(f"{brand} under 10 lakh")[0]["unsupported_terms"] == [brand]
    assert recommend("Ferrari under 10 lakh")["unsupported_terms"] == ["Ferrari"]


def test_relaxation_alternatives():
    r = recommend("7 seater automatic diesel under 6 lakh with sunroof and ADAS")
    rx = r["relaxation"]
    alts = rx["alternatives"]
    assert alts and all(a["models"] > 0 for a in alts)
    assert not {a["key"] for a in alts} & set(rx["keys"])
    assert all(not a["key"].startswith("assumed:") for a in alts)


def test_no_relaxation_for_matching_query():
    assert "relaxation" not in recommend("suv under 15 lakh")
