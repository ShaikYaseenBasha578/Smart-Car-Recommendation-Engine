"""PR 4: parser misreadings, the car-length filter and the ground-clearance preference (rule parser, no LLM, no ML)."""

import math

import pytest

from services import typos
from services.filter_v2 import MAX_COLUMNS, filter_candidates
from services.intent_v2 import _typo_vocabulary, parse_intent, parse_intent_ex
from services.recsys import config
from services.recsys.api import requirement_phrases
from services.recsys.criteria import SPEC_CRITERIA, compute_criteria
from services.recsys.explain import explain
from services.recsys.ignored import ignored_terms
from services.recsys.relax import violations_for
from services.recsys.score import score_candidates
from services.recsys.weights import CONDITIONAL_CRITERIA, SOFT_PREFERENCE_PROFILES, build_weights
from tests.recsys_frames import make_frame
from tests.test_filter_v2 import frame, ids, intent

NAN = math.nan
NO_BUDGET = {"min": None, "max": None}


def parse(q):
    return parse_intent(q, use_ml=False)


def unused(q):
    out, residual = parse_intent_ex(q, use_ml=False)
    return ignored_terms(residual)


# ---------------------------------------------------------------- budget ceilings worded as a negation

@pytest.mark.parametrize("q", ["nothing above 13 lakh", "nothing over 13 lakh", "not above 13 lakh",
                               "kuch bhi 13 lakh se upar nahi"])
def test_negated_above_is_a_ceiling(q):
    assert parse(q)["budget"] == {"min": None, "max": 1_300_000}


def test_plain_above_stays_a_minimum():
    assert parse("above 13 lakh")["budget"] == {"min": 1_300_000, "max": None}
    assert parse("SUV over 13 lakh")["budget"] == {"min": 1_300_000, "max": None}


# ---------------------------------------------------------------- car length

@pytest.mark.parametrize("q", ["car under 4 metres", "less than 4 m long car", "my garage is only 4 metres long",
                               "under 4m", "below 4 meters", "within 4000 mm", "car length under 4 m",
                               "4 metre se kam", "sub-4m", "sub 4", "sub four metre"])
def test_length_phrases_become_max_length(q):
    got = parse(q)
    assert got["max_length_mm"] == 4000
    assert got["budget"] == NO_BUDGET           # the old misreading: "under 4 metres" as a Rs 4 lakh budget
    assert unused(q) == []                      # no "Didn't use: size" chip


@pytest.mark.parametrize("q", ["sub 4 metre SUV", "sub 4m compact SUV", "sub-4m SUV under 10 lakh"])
def test_sub_four_metre_suv(q):
    got = parse(q)
    assert got["max_length_mm"] == 4000 and got["body_types"] == ["suv"]
    assert unused(q) == []


def test_length_metres_convert_to_mm_and_keep_decimals():
    assert parse("under 3.8 metres")["max_length_mm"] == 3800
    assert parse("below 4.2 m")["max_length_mm"] == 4200


@pytest.mark.parametrize("q", ["under 4 lakh", "sub 4 lakh car", "under 4 L", "budget 4 lakh"])
def test_lakh_stays_a_budget(q):
    got = parse(q)
    assert got["max_length_mm"] is None and got["budget"]["max"] == 400_000


@pytest.mark.parametrize("q", ["4 seater car", "car with 4 airbags", "under 5", "sub 5 lakh", "wheelbase 2600 mm",
                               "ground clearance under 190 mm", "200 mm ground clearance", "boot 400 litres",
                               "4000 car", "under 4 mm"])
def test_a_number_without_a_length_unit_is_never_a_length(q):
    assert parse(q)["max_length_mm"] is None


def test_length_filter_checks_length_and_passes_a_blank_as_not_verified():
    df = frame({"length_mm": 3900.0}, {"length_mm": 4300.0}, {"length_mm": NAN},
               {"length_mm": NAN, "unverified_fields": frozenset({"length_mm"})})
    out = filter_candidates(intent(max_length_mm=4000.0), df)
    assert ids(out) == [1, 4]                    # known above the bound is out; blank + unverified passes, flagged
    assert out.loc[1, "matched"] == ["max_length_mm"] and out.loc[1, "unverified"] == []
    assert out.loc[4, "unverified"] == ["Unverified: length"]
    assert out.loc[4, "n_soft_flags"] == 1       # listed after cars whose length is confirmed


def test_length_requirement_phrase_violation_text_and_relaxation_move():
    assert "length of at most 4000 mm" in requirement_phrases(intent(max_length_mm=4000.0))
    assert MAX_COLUMNS["max_length_mm"] == ("length_mm", "length")
    row = frame({"length_mm": 4155.0}).loc[1]
    v = violations_for(row, intent(max_length_mm=4000.0), ["max_length_mm"])
    assert [x["text"] for x in v] == ["length 4155 mm vs at most 4000 mm wanted"]
    from services.recsys.relax import generate_moves
    assert "max_length_mm" in [m.key for m in generate_moves(intent(max_length_mm=4000.0))]


def test_length_filter_on_the_real_catalogue():
    from services.catalogue import get_catalogue
    df = get_catalogue()
    out = filter_candidates(intent(max_length_mm=4000.0), df)
    known = out["length_mm"].dropna()
    assert len(out) > 0 and (known <= 4000).all()
    assert out.loc[out["length_mm"].isna(), "unverified"].map(lambda u: "Unverified: length" in u).all()


# ---------------------------------------------------------------- typo guard

def test_trailer_is_not_triber():
    got = parse_intent_ex("car that can tow a trailer", use_ml=False)[0]
    assert got["models"] == [] and got["corrections"] == []


@pytest.mark.parametrize("word", ["trailer", "tailor", "tractor", "terrain", "trigger", "carry", "cruiser", "press"])
def test_plain_english_words_are_never_read_as_names(word):
    assert typos.closest_word(word, _typo_vocabulary()) is None


def test_real_misspellings_are_still_corrected():
    vocab = _typo_vocabulary()
    for wrong, right in [("automtic", "automatic"), ("diesl", "diesel"), ("sunrof", "sunroof"), ("triber", "triber")]:
        assert typos.closest_word(wrong, vocab) in (right, None)
    assert parse_intent_ex("automtic hatchback", use_ml=False)[0]["corrections"] == [{"from": "automtic", "to": "automatic"}]
    assert parse("tata curve")["models"]          # a model name that is also a common misspelling still works


def test_dictionary_word_needs_one_edit_and_the_same_first_two_letters(monkeypatch):
    vocab = {"sunroof": "sunroof", "name:wxyzzy": "name:wxyzzy", "wxyzzy": "name:wxyzzy"}
    monkeypatch.setattr(typos, "ENGLISH_WORDS", {"sunroofe", "snuroof", "sunrfoo", "wxyzzx"})
    assert typos.closest_word("sunroofe", vocab) == "sunroof"    # 1 edit, same first two letters
    assert typos.closest_word("wxyzzx", vocab) is None           # a dictionary word is never read as a name
    assert typos.closest_word("snuroof", vocab) is None          # 1 edit (swap) but the first two letters differ
    assert typos.closest_word("sunrfoo", vocab) is None          # 2 edits
    monkeypatch.setattr(typos, "ENGLISH_WORDS", set())
    assert typos.closest_word("snuroof", vocab) == "sunroof"     # a non-dictionary token keeps the old rule


# ---------------------------------------------------------------- negation

@pytest.mark.parametrize("q", ["sunroof bilkul nahi", "sunroof bilkul nahi chahiye"])
def test_bilkul_nahi_excludes_the_feature(q):
    got = parse(q)
    assert got["exclude_features"] == ["sunroof"] and got["required_features"] == []


@pytest.mark.parametrize("q", ["I can't drive a manual", "can't do manual", "cannot drive manual",
                               "i cant drive a manual gearbox"])
def test_cannot_drive_manual_means_automatic(q):
    assert parse(q)["transmission"] == {"family": "automatic", "include_types": [], "exclude_types": []}


def test_can_drive_manual_is_still_manual():
    assert parse("I can drive a manual")["transmission"]["family"] == "manual"
    assert parse("manual gearbox")["transmission"]["family"] == "manual"


@pytest.mark.parametrize("q", ["AMT nahi", "no AMT", "no AMT gearbox please"])
def test_no_amt_excludes_amt_only(q):
    assert parse(q)["transmission"] == {"family": None, "include_types": [], "exclude_types": ["amt"]}


def test_no_amt_with_an_automatic_request_keeps_the_family():
    assert parse("automatic but not AMT")["transmission"] == {"family": "automatic", "include_types": [],
                                                                  "exclude_types": ["amt"]}


def test_no_amt_lets_manual_cars_through():
    from services.filter_v2 import allowed_transmission_types
    allowed = allowed_transmission_types(parse("no AMT")["transmission"])
    assert "manual" in allowed and "amt" not in allowed


# ---------------------------------------------------------------- "fast charging" is not a wish for speed

def test_fast_charging_ev():
    got = parse("fast charging EV")
    assert got["fuel_types"] == ["electric"] and got["soft_preferences"] == []
    assert unused("fast charging EV") == ["fast charging"]


def test_fast_car_is_still_performance():
    assert parse("a fast car")["soft_preferences"] == ["performance"]
    assert parse("quick and peppy hatchback")["soft_preferences"] == ["performance"]


# ---------------------------------------------------------------- "X or Y" model lists

@pytest.mark.parametrize("q", ["nexon or punch under 10 lakh", "nexon ya punch", "punch or nexon", "punch aur nexon",
                               "tata nexon or punch", "nexon, punch"])
def test_two_models_joined_by_a_coordinator(q):
    assert parse(q)["models"] == ["Nexon", "Punch"]


def test_ambiguous_model_word_alone_is_still_not_a_model():
    assert parse("punch")["models"] == []
    assert parse("good city car")["models"] == []
    assert parse("nexon or city driving")["models"] == ["Nexon"]
    assert parse("bmw or punch")["models"] == []
    assert parse("creta or seltos")["models"] == ["Creta", "Seltos"]


# ---------------------------------------------------------------- ground clearance: no number is a soft preference

@pytest.mark.parametrize("q", ["high ground clearance", "good ground clearance", "zyada ground clearance",
                               "more ground clearance", "ground clearance zyada chahiye", "higher clearance SUV"])
def test_high_ground_clearance_is_a_soft_preference(q):
    got = parse(q)
    assert got["soft_preferences"] == ["ground_clearance"]
    assert got["min_ground_clearance_mm"] is None and got["max_ground_clearance_mm"] is None
    assert got["vague"] is False
    assert unused(q) == []                       # no "Didn't use: ground clearance" chip


def test_ground_clearance_with_a_number_stays_a_hard_minimum():
    got = parse("200 mm ground clearance")
    assert got["min_ground_clearance_mm"] == 200 and got["soft_preferences"] == []
    got = parse("high ground clearance of at least 200 mm")
    assert got["min_ground_clearance_mm"] == 200 and got["soft_preferences"] == []


@pytest.mark.parametrize("q", ["low ground clearance is fine", "ground clearance doesn't matter",
                               "no high ground clearance needed"])
def test_ground_clearance_phrases_that_ask_for_nothing_set_nothing(q):
    got = parse(q)
    assert got["soft_preferences"] == []
    assert got["min_ground_clearance_mm"] is None


def test_the_llm_prompt_list_is_untouched():
    from services import intent_v2
    assert "ground_clearance" not in intent_v2.SOFT_PREFERENCES
    assert intent_v2.SOFT_PREFERENCES == ["mileage", "space", "performance", "comfort", "safety", "features"]


def test_ground_clearance_weight_exists_only_when_asked_for():
    assert "ground_clearance" in SPEC_CRITERIA and CONDITIONAL_CRITERIA == ("ground_clearance",)
    base = build_weights(intent(use_case="family", soft_preferences=["space"]))
    assert base["raw"]["ground_clearance"] == 0.0 and base["criteria"]["ground_clearance"]["multiplier"] == 0.0
    on = build_weights(intent(soft_preferences=["ground_clearance"]))
    assert on["criteria"]["ground_clearance"]["multiplier"] == SOFT_PREFERENCE_PROFILES["ground_clearance"][
        "ground_clearance"] == 2
    assert on["raw"]["ground_clearance"] == 2.0 and on["criteria"]["ground_clearance"]["weight"] > 0
    assert on["criteria"]["space_practicality"]["multiplier"] == 1.0     # nothing else is boosted


def test_other_queries_weights_are_unchanged_by_the_new_criterion():
    w = build_weights(intent(use_case="family", soft_preferences=["space", "safety"]))
    others = {c: v["weight"] for c, v in w["criteria"].items() if c != "ground_clearance"}
    assert math.isclose(sum(v for c, v in others.items() if w["criteria"][c]["class"] == "spec"), 1.0)


def _gc_frame():
    rows = [dict(model=f"M{i}", ground_clearance_mm=160.0 + 10 * i, power_bhp=100.0, mileage_kmpl=18.0) for i in range(10)]
    return make_frame(rows)


def test_preference_ranks_taller_cars_higher_and_only_through_ground_clearance():
    from services.recsys.evidence import Evidence
    df = _gc_frame()
    ev = Evidence()
    plain = intent(soft_preferences=[])
    pref = intent(soft_preferences=["ground_clearance"])
    t_plain, _ = score_candidates(df, plain, build_weights(plain), ev)
    t_pref, _ = score_candidates(df, pref, build_weights(pref), ev)
    # plain: every car identical but for ground clearance inside space_practicality (1/6 of one criterion)
    spread_plain = t_plain["overall"].max() - t_plain["overall"].min()
    spread_pref = t_pref["overall"].max() - t_pref["overall"].min()
    assert spread_pref > 3 * spread_plain
    assert list(t_pref.sort_values("overall", ascending=False).index) == list(range(10, 0, -1))
    # no other criterion value moved
    crit = compute_criteria(df)
    for c in SPEC_CRITERIA:
        if c not in ("ground_clearance", "space_practicality"):
            assert crit.values[c].nunique() <= 1


def test_ground_clearance_reason_reads_well_and_is_absent_without_the_preference():
    from services.recsys.evidence import Evidence
    df = _gc_frame()
    ev = Evidence()
    pref = intent(soft_preferences=["ground_clearance"])
    w = build_weights(pref)
    table, _ = score_candidates(df, pref, w, ev)
    ex = explain(df.loc[10], table.loc[10], w, pref, ev)
    texts = [r["text"] for r in ex["reasons"]]
    assert any(t.startswith("Ground clearance: 250 mm, higher than about ") and t.endswith("similar SUV cars here")
               for t in texts), texts
    plain = intent()
    wp = build_weights(plain)
    tp, _ = score_candidates(df, plain, wp, ev)
    assert not any("Ground clearance" in r["text"] for r in explain(df.loc[10], tp.loc[10], wp, plain, ev)["reasons"])


def test_blank_ground_clearance_is_unknown_not_zero_under_the_preference():
    from services.recsys.evidence import Evidence
    rows = [dict(model=f"M{i}", ground_clearance_mm=170.0 + 10 * i) for i in range(8)] + [dict(model="Blank", ground_clearance_mm=NAN)]
    df = make_frame(rows)
    pref = intent(soft_preferences=["ground_clearance"])
    w = build_weights(pref)
    table, _ = score_candidates(df, pref, w, Evidence())
    assert "ground_clearance" in table.loc[9, "unknown_criteria"]
    assert table.loc[9, "overall"] < table.loc[8, "overall"]


# ---------------------------------------------------------------- end to end through recommend()

def test_weights_payload_and_card_criteria_hide_the_criterion_unless_asked():
    from services.recsys.api import recommend
    plain = recommend("SUV under 15 lakh")
    assert "ground_clearance" not in plain["weights"]
    assert all("ground_clearance" not in c["criteria"] for c in plain["recommendations"])
    on = recommend("high ground clearance SUV under 15 lakh")
    assert on["weights"]["ground_clearance"]["multiplier"] == 2 and on["weights"]["ground_clearance"]["weight"] > 0
    assert on["weights_profile"]["drivers"].count("preference: ground_clearance") == 1
    assert on["ignored_terms"] == []
    assert "ground_clearance" in on["recommendations"][0]["criteria"]


def test_length_query_end_to_end():
    from services.recsys.api import recommend
    r = recommend("sub 4 metre SUV under 10 lakh")
    assert r["intent"]["max_length_mm"] == 4000 and r["ignored_terms"] == []
    assert r["recommendations"]
    for c in r["recommendations"]:
        assert "length not verified" in c["not_verified"] or c["verified_match"] or c["violations"] == []


def test_length_requirement_is_echoed_in_what_we_understood():
    # a hard length limit must be visible in "What we understood" (it replaced the old "Didn't use: size" chip)
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "static" / "script.js").read_text()
    assert "max_length_mm: v => `Under ${Number((v / 1000).toFixed(2))} m long`" in js
    assert "Object.keys(MAX_LABELS).forEach(k => { if (it[k] != null) need(MAX_LABELS[k](it[k])); });" in js
