"""Design change 3: expert / owner class weights scale with how much evidence the car has."""
import json
from pathlib import Path

import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.recsys import config
from services.recsys.api import recommend
from services.recsys.evidence import ASPECTS, ASSESSMENT_COLS, OWNER_COLS, Evidence, owner_scale_for_count
from services.recsys.score import score_candidates
from services.recsys.weights import build_weights
from tests.recsys_frames import make_frame

# One snapshot per catalogue size N: golden_empty_evidence.json for the original 832-variant catalogue
# (CARREC_CATALOGUE_DIR=data), golden_empty_evidence_<N>.json for any other size (e.g. _1464). A snapshot differs between
# sizes only because added models are candidates and move the segment reference populations; same code, same queries.
# A catalogue with no snapshot yet must not break collection and must not skip: the test below fails with a clear message
# (the data pipeline regenerates the file when only this test fails and the catalogue changed).
_CATALOGUE_SIZE = len(get_catalogue())
_GOLDEN_NAME = "golden_empty_evidence.json" if _CATALOGUE_SIZE == 832 else f"golden_empty_evidence_{_CATALOGUE_SIZE}.json"
_GOLDEN_PATH = Path(__file__).parent / "data" / _GOLDEN_NAME
GOLDEN = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else None


def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None, "soft_preferences": [],
            "cheap_intent": False}
    base.update(kw)
    return base


def assess(rows):
    base = dict(make="Acme", model="A", aspect="ride_comfort", rating="5", quote="", source_name="mag1",
                source_url="http://x/1", published_on="2026", variant_scope="")
    return pd.DataFrame([{**base, **r} for r in rows], columns=ASSESSMENT_COLS)


def owners(rows):
    base = dict(make="Acme", model="A", theme="reliability", label="", direction="positive", mentions="30",
                posts_sampled="100", period="2026", sample_urls="[]", source_name="reddit")
    return pd.DataFrame([{**base, **r} for r in rows], columns=OWNER_COLS)


def twins(**kw):
    """Two cars identical in every spec cell (models A and B) on a varied background."""
    bg = [dict(model=f"B{i}", power_bhp=70 + 12 * i, mileage_kmpl=14 + i, boot_space_litres=300 + 30 * i,
               airbags=2 + (i % 5), price_ex_showroom=800000 + 50000 * i) for i in range(6)]
    return make_frame([dict(model="A", **kw), dict(model="B", **kw)] + bg)


def vid(df, model):
    return int(df.index[df["model"] == model][0])


# ------------------------------------------------------------------ scales

def test_expert_scale_is_aspect_coverage_times_source_factor():
    # model Z gives the data file rows for 8 aspects; only those can be covered (change 3a): the others are not counted
    ev = Evidence(assess([dict(aspect=a) for a in ASPECTS[:4]] + [dict(model="Z", aspect=a) for a in ASPECTS[:8]]))
    rel = ASPECTS[:4]
    assert ev.expert_scale("Acme", "A", rel) == pytest.approx(0.5)                 # 4/4 x 1/2
    assert ev.expert_scale("Acme", "A", ASPECTS[:8]) == pytest.approx(0.5 * 0.5)   # 4/8 x 1/2
    assert ev.expert_scale("Acme", "A", list(ASPECTS)) == pytest.approx(0.5 * 0.5)  # 13 asked, 8 have data: still 4/8
    two = Evidence(assess([dict(aspect="ride_comfort"), dict(aspect="ride_comfort", source_name="mag2", source_url="u2")]))
    assert two.expert_scale("Acme", "A", ["ride_comfort"]) == pytest.approx(2 / 3)
    three = Evidence(assess([dict(source_name=f"m{i}", source_url=f"u{i}") for i in range(3)]))
    assert three.expert_scale("Acme", "A", ["ride_comfort"]) == pytest.approx(0.75)
    assert ev.expert_scale("Acme", "Nope", rel) is None                              # no row: not scaled, redistributed


def test_owner_scale_is_sample_size_over_sample_size_plus_k():
    assert config.OWNER_SAMPLE_K == 50
    assert owner_scale_for_count(50) == pytest.approx(0.5)
    assert owner_scale_for_count(450) == pytest.approx(0.9)
    assert owner_scale_for_count(None) == 0.5 == config.OWNER_NO_COUNT_SCALE
    ev = Evidence(owner_themes=owners([dict(posts_sampled="150")]))
    assert ev.owner_scale("Acme", "A") == pytest.approx(0.75)
    assert ev.owner_scale("Acme", "Nope") is None


def test_owner_sample_uses_largest_theme_total_not_the_sum_over_themes():
    ev = Evidence(owner_themes=owners([dict(theme="reliability", posts_sampled="100"),
                                       dict(theme="resale", posts_sampled="100"),
                                       dict(theme="resale", posts_sampled="60", source_name="forum")]))
    assert ev.owner_sample("Acme", "A") == 160


# ------------------------------------------------------------------ class weights per car

def test_class_weights_sum_to_one_in_every_case_and_freed_weight_goes_to_spec():
    df = twins()
    cases = {
        "none": Evidence(),
        "expert only": Evidence(assess([dict(aspect="ride_comfort")])),
        "owner only": Evidence(owner_themes=owners([dict()])),
        "both": Evidence(assess([dict(aspect="ride_comfort")]), owners([dict()])),
    }
    for name, ev in cases.items():
        table, _ = score_candidates(df, intent(), evidence=ev)
        for idx, cw in table["class_weights"].items():
            assert sum(cw.values()) == pytest.approx(1.0), (name, cw)
            assert all(v >= 0 for v in cw.values())
    table, _ = score_candidates(df, intent(), evidence=cases["both"])
    cw = table.loc[vid(df, "A"), "class_weights"]
    base = {c: config.CLASS_WEIGHTS[c] / sum(config.CLASS_WEIGHTS.values()) for c in config.CLASS_WEIGHTS}
    ex_scale = 1.0 * 0.5               # the one aspect the file has a row for is covered (change 3a), one source
    ow_scale = 100 / 150
    assert cw["expert"] == pytest.approx(base["expert"] * ex_scale)
    assert cw["owner"] == pytest.approx(base["owner"] * ow_scale)
    assert cw["spec"] == pytest.approx(1 - cw["expert"] - cw["owner"])
    assert cw["spec"] > base["spec"]                               # the freed weight returned to the spec class
    # change 3b: the car without evidence is scored at the segment mean of the reviewed cars (here car A) with the same
    # class weights as they have, instead of having the classes redistributed to spec
    assert table.loc[vid(df, "B"), "class_weights"] == pytest.approx(cw)
    assert table.loc[vid(df, "B"), "neutral_classes"] == ["expert", "owner"]


def test_relevant_aspects_follow_the_query_profile():
    """Change 3c: the relevant aspects are the ones (with data) whose spec criteria carry query weight. Switching running
    cost off removes real_world_mileage from them, so covering the other two is full coverage."""
    rows = [dict(aspect=a) for a in ("rear_seat_comfort", "boot_practicality")] + [dict(model="Z", aspect="real_world_mileage")]
    ev = Evidence(assess(rows))
    df = twins()
    it = intent(use_case="family")
    fam, _ = score_candidates(df, it, build_weights(it), ev)
    off, _ = score_candidates(df, it, build_weights(it, {"running_cost": False}), ev)
    base_e = config.CLASS_WEIGHTS["expert"] / (config.CLASS_WEIGHTS["expert"] + config.CLASS_WEIGHTS["spec"])
    assert fam.loc[vid(df, "A"), "class_weights"]["expert"] == pytest.approx(base_e * (2 / 3) * 0.5)
    assert off.loc[vid(df, "A"), "class_weights"]["expert"] == pytest.approx(base_e * 1.0 * 0.5)


def test_one_glowing_single_source_expert_row_cannot_outrank_an_identical_car_by_much():
    """Car A has one 5/5 expert row (one aspect, one source); car B is identical in every spec cell without evidence.
    Scaled, A's expert weight is (1/13 x 1/2) of its share; unscaled it would be the whole share."""
    df = twins()
    ev = Evidence(assess([dict(aspect="ride_comfort", rating="5")]))
    table, _ = score_candidates(df, intent(), evidence=ev)
    a, b = table.loc[vid(df, "A")], table.loc[vid(df, "B")]
    cw = a["class_weights"]
    spec_sub = a["spec"]
    # most A can gain through the class weights: scaled expert weight x (1 - its spec value)
    gain_bound = cw["expert"] * (1.0 - spec_sub)
    # plus the existing coverage factor (A has 1 of 13 expert aspects known, B none): COVERAGE_PENALTY x share difference
    cov_bound = config.COVERAGE_PENALTY * (b["unknown_share"] - a["unknown_share"])
    assert a["overall"] - b["overall"] <= gain_bound + cov_bound + 1e-9
    assert a["overall"] - b["overall"] < 0.02
    # unscaled (the pre-change behaviour) the same row would give a much larger edge
    unscaled = (config.CLASS_WEIGHTS["expert"] / sum(config.CLASS_WEIGHTS[c] for c in ("spec", "expert"))) * (1.0 - spec_sub)
    assert unscaled >= 2 * gain_bound - 1e-9          # one source halves the weight (the aspect is the only one with data)


def test_full_evidence_car_with_three_sources_gets_three_quarters_of_the_class_weight():
    df = twins()
    rows = [dict(aspect=a, source_name=f"m{i}", source_url=f"u{i}") for a in ASPECTS for i in range(3)]
    table, _ = score_candidates(df, intent(), evidence=Evidence(assess(rows)))
    base_e = config.CLASS_WEIGHTS["expert"] / (config.CLASS_WEIGHTS["expert"] + config.CLASS_WEIGHTS["spec"])
    assert table.loc[vid(df, "A"), "class_weights"]["expert"] == pytest.approx(base_e * 0.75)


# ------------------------------------------------------------------ empty files = before

@pytest.mark.parametrize("q", sorted(GOLDEN) if GOLDEN is not None else [None])
def test_empty_evidence_gives_the_same_results_as_before_this_change(q):
    assert GOLDEN is not None, (f"no golden snapshot for a catalogue of {_CATALOGUE_SIZE} variants "
                                f"(tests/data/{_GOLDEN_NAME})")
    r = recommend(q, evidence=Evidence())
    got = [{"variant_id": c["variant_id"], "scores": c["scores"], "ranking_score": c["ranking_score"],
            "criteria": c["criteria"]} for c in r["recommendations"]]
    assert got == GOLDEN[q]
    assert all(c["class_weights"] == {"spec": 1.0} for c in r["recommendations"])
