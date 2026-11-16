"""Autocar notes and owner themes: scoring (capped adjustment) and template explanations."""
import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from services.recsys import config
from services.recsys.api import recommend
from services.recsys.evidence import EXPORT_THEME_COLS, Evidence, theme_strength
from services.recsys.explain import explain
from services.recsys.score import score_candidates
from services.recsys.weights import build_weights
from tests.test_recsys_reviews import assess, intent, rate, twins, vid


def themes(rows):
    base = dict(model="A", theme="service_cost", label="", direction="positive", mentions="14", posts_sampled="60",
                share="0.2333", note="Some owners describe servicing as affordable.",
                sample_urls='["http://cw/a/1", "http://cw/a/2"]', source="CarWale", period="")
    return pd.DataFrame([{**base, **r} for r in rows], columns=EXPORT_THEME_COLS)


RIDE = "Composed over ruts; light steering."
MILEAGE = "Diesel is most frugal at about 21.8 kmpl."


def expert_rows(model="A"):
    return assess([
        dict(model=model, aspect="ride_comfort", source_aspect="Ride Comfort And Handling", value="0.8", note=RIDE,
             quote="Ride comfort remains a core strength."),
        dict(model=model, aspect="handling", source_aspect="Ride Comfort And Handling", value="0.8", note=RIDE,
             quote="Ride comfort remains a core strength."),
        dict(model=model, aspect="real_world_mileage", source_aspect="Mileage / Range And Efficiency", value="0.7",
             raw_score="7", note=MILEAGE, quote=""),
    ]).assign(note=lambda d: [RIDE, RIDE, MILEAGE], quote=lambda d: ["Ride comfort remains a core strength."] * 2 + [""])


def _ex(ev, it, model="A"):
    df = twins()
    w = build_weights(it)
    table, _ = score_candidates(df, it, w, ev)
    v = vid(df, model)
    return explain(df.loc[v], table.loc[v], w, it, ev)


def _ev(**kw):
    return Evidence(kw.pop("a", None), kw.pop("t", None), kw.pop("r", None), segments={})


# ------------------------------------------------------------------ scoring

def test_empty_themes_reproduce_the_results_exactly():
    base = recommend("family suv under 15 lakh with sunroof", evidence=Evidence())
    empty = recommend("family suv under 15 lakh with sunroof", evidence=Evidence(None, themes([]), None, segments={}))
    assert json.dumps(base, sort_keys=True) == json.dumps(empty, sort_keys=True)


def test_theme_strength_grows_with_share_and_sample_and_saturates():
    assert theme_strength(0, 60) == 0
    assert theme_strength(6, 60) < theme_strength(12, 60) < theme_strength(15, 60) == theme_strength(30, 60)
    assert theme_strength(3, 20) < theme_strength(9, 60)           # same share, thinner sample
    assert theme_strength(60, 60) == pytest.approx(60 / (60 + config.OWNER_SAMPLE_K))


def test_adjustment_is_signed_bounded_and_neutral_without_themes():
    ev = _ev(t=themes([dict(direction="positive", mentions="60"), dict(model="B", direction="negative", mentions="60")]))
    aw = {"service_cost": 1.0}
    assert ev.theme_adjustment("A", aw) > 0 > ev.theme_adjustment("B", aw)
    assert abs(ev.theme_adjustment("A", aw)) <= config.THEME_ADJUST_CAP
    assert ev.theme_adjustment("C", aw) == 0.0                      # no themes: neutral
    assert ev.theme_adjustment("A", {"reliability": 1.0}) == 0.0    # theme not relevant to the query
    mixed = _ev(t=themes([dict(direction="mixed", mentions="30")]))
    assert mixed.theme_adjustment("A", aw) == 0.0


def test_a_theme_gap_moves_the_score_but_never_past_the_cap():
    df = twins()
    it = intent(use_case="budget")
    ratings = rate([dict(model=m, aspect="service_cost", value="0.8", rating_count="300") for m in ("A", "B")])
    base, _ = score_candidates(df, it, build_weights(it), _ev(r=ratings))
    ev = _ev(r=ratings, t=themes([dict(direction="negative", mentions="60", theme="service_cost"),
                                  dict(model="B", direction="positive", mentions="60", theme="service_cost")]))
    t, _ = score_candidates(df, it, build_weights(it), ev)
    a0, b0 = base.loc[vid(df, "A"), "owner"], base.loc[vid(df, "B"), "owner"]
    a1, b1 = t.loc[vid(df, "A"), "owner"], t.loc[vid(df, "B"), "owner"]
    assert a1 < a0 and b1 > b0
    assert abs(a1 - a0) <= config.THEME_ADJUST_CAP + 1e-9 and abs(b1 - b0) <= config.THEME_ADJUST_CAP + 1e-9


def test_theme_counts_only_when_its_criterion_has_query_weight():
    df = twins()
    ratings = rate([dict(model="A", aspect="service_cost", value="0.8", rating_count="300")])
    ev0, ev1 = _ev(r=ratings), _ev(r=ratings, t=themes([dict(theme="resale", direction="negative", mentions="30")]))
    it = intent(use_case="enthusiast")
    w = build_weights(it)
    w["criteria"]["value_for_budget"]["weight"] = 0.0
    w["criteria"]["price"]["weight"] = 0.0                          # resale maps to value_for_budget and price only
    t0, _ = score_candidates(df, it, w, ev0)
    t1, _ = score_candidates(df, it, w, ev1)
    assert t0.loc[vid(df, "A"), "owner"] == pytest.approx(t1.loc[vid(df, "A"), "owner"])


# ------------------------------------------------------------------ expert lines

def test_ride_query_picks_the_ride_note_and_mileage_query_the_mileage_note():
    ev = _ev(a=expert_rows())
    ride = _ex(ev, intent(soft_preferences=["comfort"]))["expert_lines"]
    assert ride[0]["note"] == RIDE
    assert ride[0]["text"] == f"Autocar India, ride comfort and handling 8/10 (Oct 2025): {RIDE}"
    mil = _ex(ev, intent(soft_preferences=["mileage"]))["expert_lines"]
    assert mil[0]["note"] == MILEAGE                                # mileage outranks ride in a mileage query
    assert mil[0]["text"].startswith("Autocar India, mileage / range and efficiency 7/10 (Oct 2025): ")


def test_quote_is_a_separate_marked_field_with_the_source_url():
    ev = _ev(a=expert_rows())
    line = _ex(ev, intent(soft_preferences=["comfort"]))["expert_lines"][0]
    assert line["quote"] == {"text": "Ride comfort remains a core strength.", "kind": "quotation",
                             "source": "Autocar India", "source_url": "http://ac/a"}
    assert "core strength" not in line["text"]
    assert _ex(ev, intent(soft_preferences=["mileage"]))["expert_lines"][0]["quote"] is None


def test_at_most_two_expert_lines_and_the_score_reason_is_not_repeated():
    ex = _ex(_ev(a=expert_rows()), intent(soft_preferences=["comfort", "mileage"]))
    assert len(ex["expert_lines"]) <= config.MAX_EXPERT_LINES
    shown = {f for ln in ex["expert_lines"] for f in ln["fields"]}
    assert not any(r["evidence_class"] == "expert" and set(r["fields"]) <= shown for r in ex["reasons"])


def test_no_note_no_line_and_no_fabrication_for_a_model_without_rows():
    ev = _ev(a=expert_rows("A"), t=themes([dict(model="A")]))
    ex = _ex(ev, intent(soft_preferences=["comfort"]), model="B")
    assert ex["expert_lines"] == [] and ex["owner_lines"] == [] and ex["caveats"] == []
    assert "Expert ratings: none for this model yet" in ex["unknowns"]
    plain = _ev(a=assess([dict(model="A")]))                        # a row without a note
    assert _ex(plain, intent(soft_preferences=["comfort"]))["expert_lines"] == []


def test_note_text_is_identical_to_the_csv_cell():
    path = Path(__file__).resolve().parents[1] / "data" / "assessments.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    row = next(r for r in rows if r["note"] and r["aspect"] == "ride_comfort")
    ev = Evidence.load(assessments_path=path, owner_path=Path("/nonexistent"), ratings_path=Path("/nonexistent"),
                       segments={})
    notes = {n["source_aspect"]: n["note"] for n in ev.expert_notes(row["model"])}
    assert notes[row["source_aspect"]] == row["note"]


# ------------------------------------------------------------------ owner lines, wording, caveats

def _owner(rows, it=None, model="A"):
    ev = _ev(t=themes(rows), r=rate([dict(model="A")]))
    return _ex(ev, it or intent(use_case="budget"), model=model)


def test_wording_follows_the_share_and_uses_the_stored_counts():
    some = _owner([dict(mentions="14")])["owner_lines"][0]
    assert some["text"].startswith("Some owners are positive about service cost (14 of 60 reviews, CarWale)")
    assert some["text"].endswith(": Some owners describe servicing as affordable.")
    many = _owner([dict(mentions="20")])["owner_lines"][0]["text"]
    assert many.startswith("Many owners") and "(20 of 60 reviews, CarWale)" in many
    assert _owner([dict(mentions="30")])["owner_lines"][0]["text"].startswith("Many owners")   # exactly half is not "most"
    assert _owner([dict(mentions="31")])["owner_lines"][0]["text"].startswith("Most owners")
    assert _owner([dict(mentions="14", direction="negative")])["owner_lines"][0]["text"].startswith(
        "Some owners are negative about service cost")
    mixed = _owner([dict(mentions="10", direction="mixed")])["owner_lines"][0]["text"]
    assert mixed.startswith("Owners have mixed views on service cost (10 of 60 reviews, CarWale)")
    assert "Most" not in some["text"].split(":")[0]


def test_every_line_carries_source_and_links():
    line = _owner([dict()])["owner_lines"][0]
    assert line["source"] == "CarWale" and line["source_url"] == "http://cw/a/1"
    assert line["source_urls"] == ["http://cw/a/1", "http://cw/a/2"] and line["note"]


def test_negative_recurring_fault_always_surfaces_even_if_the_query_did_not_ask():
    fault = dict(theme="recurring_fault", label="music system faults", direction="negative", mentions="3",
                 note="Owners report repeated music system faults.")
    others = [dict(theme="service_cost", mentions="20"), dict(theme="reliability", mentions="25"),
              dict(theme="satisfaction", mentions="30")]
    ex = _owner(others + [fault], intent(use_case="budget"))
    texts = [x["text"] for x in ex["owner_lines"]]
    assert len(texts) == config.MAX_OWNER_LINES
    assert texts[0].startswith("Reported fault: music system faults (3 of 60 reviews, CarWale)")
    ex2 = _owner([fault], intent(soft_preferences=["performance"]))      # fault has no weight in this query
    assert ex2["owner_lines"][0]["text"].startswith("Reported fault: music system faults")
    assert ex2["caveats"][0]["kind"] == "reported_fault" and ex2["caveats"][0]["source_url"]


def test_negative_themes_become_caveats_positive_ones_do_not():
    ex = _owner([dict(theme="service_cost", mentions="10"),
                 dict(theme="build_issues", direction="negative", mentions="6", label="panel gaps")])
    assert [c["theme"] for c in ex["caveats"]] == ["build_issues"] and ex["caveats"][0]["kind"] == "negative_theme"
    assert _owner([dict(mentions="10")])["caveats"] == []


def test_irrelevant_positive_theme_is_not_shown():
    from services.recsys.explain import owner_lines
    ev = _ev(t=themes([dict(theme="resale", mentions="20")]))
    assert owner_lines("A", {"performance": 1.0}, ev)[0] == []         # resale has no weight in this query
    assert len(owner_lines("A", {"resale": 0.2}, ev)[0]) == 1


def test_card_exposes_notes_caveats_and_reasons_include_the_lines():
    from services.catalogue import get_catalogue
    ev = Evidence.load(segments={})
    res = recommend("comfortable family SUV under 15 lakh", evidence=ev)
    assert res["recommendations"]
    for c in res["recommendations"]:
        assert {"expert_notes", "owner_notes", "caveats"} <= set(c)
        for ln in c["expert_notes"] + c["owner_notes"]:
            assert ln["text"] in c["match_reasons"] and ln["source"] and ln["text"]
