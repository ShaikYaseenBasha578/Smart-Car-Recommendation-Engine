"""Audit 2026-11-16, fix 1: a blank must not pass a requirement silently.

No car is "confirmed" on a requirement whose value is blank; the banner names every unmet and every unverified
requirement; a card with any unmet or unverified requirement never says it meets everything."""
import numpy as np

from services.intent_v2 import parse_intent
from services.recsys.api import recommend, requirement_phrases
from services.recsys.evidence import Evidence
from services.recsys.explain import match_label
from tests.recsys_frames import make_frame

NO_EVIDENCE = Evidence()
SUNROOF_BLANK = frozenset({"sunroof"})


def run(query, rows):
    return recommend(query, evidence=NO_EVIDENCE, catalogue=make_frame(rows), intent=parse_intent(query))


def blank_rows(n=3):
    return [dict(model=f"B{i}", sunroof=np.nan, unverified_fields=SUNROOF_BLANK) for i in range(n)]


def test_all_blank_feature_says_no_car_is_confirmed_and_no_card_is_a_match():
    r = run("SUV with sunroof", blank_rows())
    assert r["recommendations"]
    assert r["message"].startswith("No car is confirmed to have all of:") and "sunroof" in r["message"]
    assert r["no_confirmed"]["not_verified"] == ["sunroof not verified"]
    for c in r["recommendations"]:
        assert c["verified_match"] is False
        assert c["not_verified"] == ["sunroof not verified"]
        assert "match" not in c["match_label"].lower().replace("not confirmed", "")
        assert c["match_label"].startswith("Requirements not confirmed")


def test_verified_car_is_a_match_and_ranks_above_blank_ones_without_a_banner():
    rows = blank_rows(2) + [dict(model="YES", sunroof=True)]
    r = run("SUV with sunroof", rows)
    cards = r["recommendations"]
    assert cards[0]["Model"] == "YES" and cards[0]["verified_match"] is True
    assert "no_confirmed" not in r
    assert all(c["verified_match"] is False for c in cards[1:])


def test_relaxed_banner_names_the_relaxation_and_the_unverified_requirements():
    rows = [dict(model=f"S{i}", seats=5, sunroof=np.nan, unverified_fields=SUNROOF_BLANK, price_ex_showroom=450000.0)
            for i in range(2)]
    r = run("7 seater under 5 lakh with sunroof", rows)
    msg = r["message"]
    assert msg.startswith("No car is confirmed to have all of:")
    assert "7+ seats" in msg and "sunroof" in msg
    assert "5+ seats instead of 7+" in msg                       # the unmet one
    assert "Not confirmed in our data for the cars shown: sunroof" in msg   # the unverified one
    assert r["relaxation"]["message"] == msg  # same text in both places
    for c in r["recommendations"]:
        assert [v["constraint"] for v in c["violations"]] == ["seats"]
        assert c["not_verified"] == ["sunroof not verified"] and c["verified_match"] is False


def test_real_catalogue_celerio_case_is_never_a_confirmed_match():
    r = recommend("7 seater under 5 lakh with ADAS and sunroof")
    assert r["recommendations"]
    assert r["message"].startswith("No car is confirmed to have all of:")
    for c in r["recommendations"]:
        assert not c["verified_match"]
        assert "sunroof not verified" in c["not_verified"] and "ADAS not verified" in c["not_verified"]
        assert [v["constraint"] for v in c["violations"]] == ["seats"]


def test_real_catalogue_budget_ventilated_360_adas_has_no_match_label_on_any_card():
    r = recommend("budget 10-12 lakh, ventilated seats, 360 camera, ADAS")
    assert r["message"].startswith("No car is confirmed")
    assert all(not c["verified_match"] and c["not_verified"] for c in r["recommendations"])


def test_match_label_never_calls_an_unverified_car_a_match():
    assert match_label(0.9, 0, relaxed=False, n_unverified=1).startswith("Requirements not confirmed")
    assert match_label(0.9, 0, relaxed=False).startswith("Strong match") or match_label(0.9, 0).endswith("match")


def test_requirement_phrases_cover_each_hard_requirement():
    p = requirement_phrases(parse_intent("7 seater petrol automatic SUV under 20 lakh with sunroof and ADAS"))
    joined = " | ".join(p)
    for needle in ("20 lakh", "7+ seats", "suv", "petrol", "sunroof", "ADAS"):
        assert needle in joined
