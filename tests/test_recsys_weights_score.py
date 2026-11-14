import pandas as pd
import pytest

from services.intent_v2 import USE_CASE_PATTERNS, SOFT_PREFERENCES
from services.recsys import config
from services.recsys.criteria import COMFORT_BOOLS, SAFETY_BOOLS, TECH_BOOLS, compute_criteria
from services.recsys.evidence import ASSESSMENT_COLS, OWNER_COLS, Evidence
from services.recsys.score import score_candidates
from services.recsys.weights import (ALL_CRITERIA, CRITERION_CLASS, SOFT_PREFERENCE_PROFILES,
                                     USE_CASE_PROFILES, build_weights)
from tests.recsys_frames import make_frame

NO_EVIDENCE = Evidence()


def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None,
            "soft_preferences": []}
    base.update(kw)
    return base


def rank_of(table, vid):
    return list(table.index).index(vid)


FULL = {c: True for c in list(COMFORT_BOOLS) + list(TECH_BOOLS) + list(SAFETY_BOOLS)}


def spread_cars(n=6):
    """a varied background so percentiles and ranks have something to compare with"""
    return [dict(model=f"B{i}", power_bhp=70 + 12 * i, mileage_kmpl=14 + i, boot_space_litres=300 + 30 * i,
                 airbags=2 + (i % 5), price_ex_showroom=800000 + 50000 * i) for i in range(n)]


# ------------------------------------------------------------------ weights

def test_weights_normalise_within_each_class():
    w = build_weights(intent(use_case="family", soft_preferences=["space", "safety"]))
    for cls in ("spec", "expert", "owner"):
        assert abs(sum(v["weight"] for c, v in w["criteria"].items() if v["class"] == cls) - 1) < 1e-9
    assert set(w["criteria"]) == set(ALL_CRITERIA)
    assert all(v["label"] for v in w["criteria"].values())


def test_every_parser_use_case_and_preference_has_a_profile():
    assert {label for label, _ in USE_CASE_PATTERNS} <= set(USE_CASE_PROFILES)
    assert set(SOFT_PREFERENCES) <= set(SOFT_PREFERENCE_PROFILES)


def test_family_raises_safety_and_space_over_neutral():
    n, f = build_weights(intent()), build_weights(intent(use_case="family"))
    assert f["criteria"]["safety"]["weight"] > n["criteria"]["safety"]["weight"]
    assert f["criteria"]["space_practicality"]["weight"] > n["criteria"]["space_practicality"]["weight"]
    assert n["profile"] == "neutral" and f["profile"] == "family"


def test_weight_overrides_switch_chips():
    base = build_weights(intent(use_case="family"))
    off = build_weights(intent(use_case="family"), {"safety": False, "performance": 0})
    assert off["criteria"]["safety"]["weight"] == 0 and not off["criteria"]["safety"]["active"]
    assert abs(sum(v["weight"] for v in off["criteria"].values() if v["class"] == "spec") - 1) < 1e-9
    boosted = build_weights(intent(), {"performance": 3})
    assert boosted["criteria"]["performance"]["weight"] > base["criteria"]["performance"]["weight"]
    assert build_weights(intent(), {"safety": True, "bogus": 2})["criteria"]["safety"]["active"]


# ------------------------------------------------------------------ score

def test_unknown_required_feature_is_not_scored_as_absent():
    df = make_frame([dict(model="Lacks", sunroof=False), dict(model="Blank", sunroof=None)] + spread_cars(4))
    it = intent(required_features=["sunroof"])
    table, _ = score_candidates(df, it, evidence=NO_EVIDENCE)
    assert rank_of(table, 2) < rank_of(table, 1)
    assert table.loc[2, "overall"] > table.loc[1, "overall"]
    assert "unknown_required:feature:sunroof" in table.loc[2, "flags"]
    assert "missing_required:feature:sunroof" in table.loc[1, "flags"]


def test_unknown_required_feature_is_flagged_but_not_last():
    df = make_frame([dict(model="Blank", **{**FULL, "sunroof": None})] + spread_cars(5))
    table, _ = score_candidates(df, intent(required_features=["sunroof"]), evidence=NO_EVIDENCE)
    assert rank_of(table, 1) < len(df) - 1
    assert table.loc[1, "coverage"] < 1.0


def test_car_with_gaps_ranks_slightly_lower_not_last():
    cars = spread_cars(5) + [dict(model="Full", **FULL), dict(model="Gaps", **{k: None for k in FULL})]
    df = make_frame(cars)
    table, _ = score_candidates(df, intent(), evidence=NO_EVIDENCE)
    full_id, gap_id = 6, 7
    assert table.loc[gap_id, "overall"] < table.loc[full_id, "overall"]
    assert table.loc[gap_id, "coverage"] < table.loc[full_id, "coverage"]
    assert rank_of(table, gap_id) < len(df) - 1
    assert table.loc[gap_id, "overall"] > 0.8 * table.loc[full_id, "overall"] - 0.25


def test_coverage_penalty_is_mild():
    df = make_frame(spread_cars(4) + [dict(model="Gaps", **{k: None for k in FULL})])
    table, _ = score_candidates(df, intent(), evidence=NO_EVIDENCE)
    row = table.loc[5]
    assert row["overall"] >= row["spec"] * (1 - config.COVERAGE_PENALTY) - 1e-12


def test_subscores_renormalise_when_expert_owner_missing():
    df = make_frame(spread_cars(5))
    table, _ = score_candidates(df, intent(), evidence=NO_EVIDENCE)
    assert table["expert"].isna().all() and table["owner"].isna().all()
    for _, r in table.iterrows():
        assert r["overall"] == pytest.approx(r["spec"] * (1 - config.COVERAGE_PENALTY * r["unknown_share"]))


def test_empty_evidence_files_do_not_change_the_ranking():
    df = make_frame(spread_cars(6))
    it = intent(use_case="family")
    a, _ = score_candidates(df, it, evidence=NO_EVIDENCE)
    empty = Evidence(pd.DataFrame(columns=ASSESSMENT_COLS), pd.DataFrame(columns=OWNER_COLS))
    b, _ = score_candidates(df, it, evidence=empty)
    assert list(a.index) == list(b.index)
    assert a["overall"].tolist() == b["overall"].tolist()


def _evidence(rating_a, rating_b, owner=None):
    rows = [dict(make="Acme", model="A", aspect="ride_comfort", rating=str(rating_a), quote="q", source_name="s",
                 source_url="http://x/a", published_on="", variant_scope=""),
            dict(make="Acme", model="B", aspect="ride_comfort", rating=str(rating_b), quote="q", source_name="s",
                 source_url="http://x/b", published_on="", variant_scope="")]
    return Evidence(pd.DataFrame(rows, columns=ASSESSMENT_COLS), owner)


def test_higher_expert_rating_on_heavily_weighted_aspect_raises_rank():
    df = make_frame([dict(model="A"), dict(model="B")])
    it = intent(use_case="parents")  # ride_comfort carries a 2x multiplier
    table, _ = score_candidates(df, it, evidence=_evidence(5, 2))
    assert table.index[0] == 1 and table.loc[1, "expert"] > table.loc[2, "expert"]
    table, _ = score_candidates(df, it, evidence=_evidence(2, 5))
    assert table.index[0] == 2
    # switching the aspect off removes its effect
    w = build_weights(it, {"expert_ride_comfort": False})
    table, _ = score_candidates(df, it, weights=w, evidence=_evidence(5, 2))
    assert table.loc[1, "overall"] == pytest.approx(table.loc[2, "overall"])


def test_owner_themes_below_minimum_sample_are_ignored():
    df = make_frame([dict(model="A"), dict(model="B")])
    row = dict(make="Acme", model="A", theme="reliability", label="", direction="negative", mentions="20",
               posts_sampled=str(config.OWNER_MIN_POSTS - 1), period="", sample_urls="[]", source_name="r")
    ev = Evidence(owner_themes=pd.DataFrame([row], columns=OWNER_COLS))
    table, _ = score_candidates(df, intent(), evidence=ev)
    assert table["owner"].isna().all()
    assert table.loc[1, "overall"] == pytest.approx(table.loc[2, "overall"])
    row["posts_sampled"] = "100"
    ev = Evidence(owner_themes=pd.DataFrame([row], columns=OWNER_COLS))
    table, _ = score_candidates(df, intent(), evidence=ev)
    assert table.loc[1, "owner"] < 0.1


def test_expert_data_for_few_models_does_not_make_unreviewed_cars_last():
    df = make_frame(spread_cars(5) + [dict(model="Reviewed")])
    ev = Evidence(pd.DataFrame([dict(make="Acme", model="Reviewed", aspect="handling", rating="2", quote="q",
                                     source_name="s", source_url="u", published_on="", variant_scope="")],
                               columns=ASSESSMENT_COLS))
    table, _ = score_candidates(df, intent(), evidence=ev)
    assert table["overall"].notna().all() and table["expert"].notna().sum() == 1


def test_scores_are_deterministic_and_in_range():
    df = make_frame(spread_cars(6))
    a, _ = score_candidates(df, intent(use_case="city"), evidence=NO_EVIDENCE)
    b, _ = score_candidates(df, intent(use_case="city"), evidence=NO_EVIDENCE)
    assert a["overall"].tolist() == b["overall"].tolist() and list(a.index) == list(b.index)
    assert a["overall"].between(0, 1).all()
    assert abs(sum(a.iloc[0]["weights"].values()) - 1) < 1e-9


# ------------------------------------------------------------------ unknown inside a criterion stays unknown

def _star_cars():
    """Four otherwise identical cars on a varied background: 5-star, 4-star, 1-star and unrated."""
    same = dict(esc=True, abs=True, tpms=True, hill_assist=True)
    cars = [dict(model="Rated5", safety_stars_adult=5.0, **same), dict(model="Rated4", safety_stars_adult=4.0, **same),
            dict(model="Rated1", safety_stars_adult=1.0, **same), dict(model="Unrated", safety_stars_adult=float("nan"), **same)]
    return make_frame(cars + spread_cars()), {c["model"]: i for i, c in enumerate(cars, start=1)}


SAFETY_QUERY = dict(use_case="family", soft_preferences=["safety"])


def _overall(df, vid, drop_partial=False):
    crit = compute_criteria(df)
    if drop_partial:
        crit.unknown_frac = None   # the pre-fix behaviour: only wholly unknown criteria reach the coverage factor
    table, _ = score_candidates(df, intent(**SAFETY_QUERY), evidence=NO_EVIDENCE, criteria=crit)
    return table, {m: float(table.loc[v, "overall"]) for m, v in vid.items()}


def test_unrated_car_does_not_outscore_the_5_star_car_on_a_safety_query():
    df, vid = _star_cars()
    table, o = _overall(df, vid)
    assert o["Unrated"] < o["Rated5"]
    # the unknown share of safety (stars = 3 of 10 field weight) reaches the coverage factor
    assert abs(table.loc[vid["Unrated"], "partial_unknown"]["safety"] - 0.3) < 1e-9
    assert table.loc[vid["Unrated"], "coverage"] < table.loc[vid["Rated4"], "coverage"]
    assert "safety" not in table.loc[vid["Rated4"], "partial_unknown"]
    assert "unrated_safety" in table.loc[vid["Unrated"], "flags"]


# ------------------------------------------------------------------ unknown crash rating gets a neutral prior (design change 1)

def _segment_cars(body, bg_stars):
    """The four star cars (5, 4, 1, unrated) in segment `body`, plus rated background models with the given stars
    (varied otherwise, so the percentile fields have something to compare with)."""
    same = dict(esc=True, abs=True, tpms=True, hill_assist=True, body_type=body)
    cars = [dict(model=f"{body}-Rated5", safety_stars_adult=5.0, **same),
            dict(model=f"{body}-Rated4", safety_stars_adult=4.0, **same),
            dict(model=f"{body}-Rated1", safety_stars_adult=1.0, **same),
            dict(model=f"{body}-Unrated", safety_stars_adult=float("nan"), **same)]
    bg = [dict(model=f"{body}-B{i}", body_type=body, safety_stars_adult=float(st), power_bhp=70 + 12 * i,
               mileage_kmpl=14 + i % 6, boot_space_litres=300 + 30 * i, airbags=2 + i % 5,
               price_ex_showroom=800000 + 50000 * i) for i, st in enumerate(bg_stars)]
    return cars + bg


def _two_segment_frame():
    """suv segment: known stars {5, 4, 1, 4x5, 3, 5, 2} -> median 4. hatchback: background all 3 -> median 3.
    estate: background all 5 -> median 5."""
    rows = (_segment_cars("suv", [4, 4, 4, 4, 4, 3, 5, 2]) + _segment_cars("hatchback", [3] * 8)
            + _segment_cars("estate", [5] * 8))
    return make_frame(rows), {r["model"]: i for i, r in enumerate(rows, start=1)}


def _star_scores(df, vid, body):
    table, _ = score_candidates(df, intent(**SAFETY_QUERY), evidence=NO_EVIDENCE)
    return table, {k.split("-", 1)[1]: float(table.loc[v, "overall"]) for k, v in vid.items()
                   if k.startswith(body + "-") and k.split("-", 1)[1] in ("Rated5", "Rated4", "Rated1", "Unrated")}


@pytest.mark.parametrize("body", ["suv", "hatchback"])
def test_unrated_ordering_5_over_4_over_unrated_over_1(body):
    """Safety-weighted query, otherwise identical cars, segment median 4 (suv) and 3 (hatchback)."""
    df, vid = _two_segment_frame()
    table, o = _star_scores(df, vid, body)
    assert o["Rated5"] > o["Rated4"] > o["Unrated"] > o["Rated1"], o


def test_unrated_prior_is_one_star_below_the_median_and_still_unknown_for_coverage():
    df, vid = _two_segment_frame()
    table, _ = _star_scores(df, vid, "suv")
    crit = compute_criteria(df)
    uid, r4 = vid["suv-Unrated"], vid["suv-Rated4"]
    # median 4 -> prior would be 3 stars: the unrated car's safety value is below the 4-star twin's
    assert crit.values.loc[uid, "safety"] < crit.values.loc[r4, "safety"]
    # ... and the star field is still unknown (3 of 10 of the safety field weight), and the car is flagged
    assert crit.unknown_frac.loc[uid, "safety"] == pytest.approx(0.3)
    assert table.loc[uid, "partial_unknown"]["safety"] == pytest.approx(0.3)
    assert table.loc[uid, "coverage"] < table.loc[r4, "coverage"]
    assert "unrated_safety" in table.loc[uid, "flags"]
    # nothing displays or implies a rating: the detail carries no star score for the unrated car
    star = next(d for d in crit.detail[uid]["safety"] if d["field"] == "safety_stars_adult")
    assert star["raw"] is None and star["score"] is None and star["prior_score"] == pytest.approx(0.6)


@pytest.mark.parametrize("body,prior", [("suv", 0.6), ("hatchback", 0.6), ("estate", 0.8)])
def test_prior_is_one_star_below_the_median_with_a_floor_of_three(body, prior):
    """median 4 -> 3 stars; median 3 -> 2 floored to 3; median 5 -> 4 (equal to a 4-star car before the charge)."""
    df, vid = _two_segment_frame()
    crit = compute_criteria(df)
    star = next(d for d in crit.detail[vid[f"{body}-Unrated"]]["safety"] if d["field"] == "safety_stars_adult")
    assert star["prior_score"] == pytest.approx(prior)
    table, o = _star_scores(df, vid, body)
    assert o["Rated5"] > o["Rated4"] > o["Unrated"] > o["Rated1"]


def test_estate_unrated_is_equal_to_the_4_star_car_before_the_coverage_charge_and_below_after():
    df, vid = _two_segment_frame()
    table, o = _star_scores(df, vid, "estate")
    assert table.loc[vid["estate-Unrated"], "spec"] == pytest.approx(table.loc[vid["estate-Rated4"], "spec"])
    assert o["Unrated"] < o["Rated4"]


def test_unrated_prior_uses_only_the_crash_rating_field():
    """Other unknown safety fields stay unknown: no prior for airbags or ESC."""
    rows = _segment_cars("suv", [4] * 8)
    rows[3]["airbags"] = float("nan")
    rows[3]["esc"] = None
    df = make_frame(rows)
    crit = compute_criteria(df)
    uid = 4
    # stars (3) + airbags (2) + esc (2) unknown of 10 field weight -> 0.7 unknown
    assert crit.unknown_frac.loc[uid, "safety"] == pytest.approx(0.7)


def test_whole_catalogue_median_for_a_tiny_segment():
    rows = _segment_cars("suv", [4] * 8) + [dict(model="Lonely", body_type="coupe", safety_stars_adult=float("nan"))]
    df = make_frame(rows)
    crit = compute_criteria(df)
    star = next(d for d in crit.detail[len(rows)]["safety"] if d["field"] == "safety_stars_adult")
    # the coupe segment has no rated model: falls back to the whole catalogue (median 4, prior 3 stars)
    assert star["prior_score"] == pytest.approx(0.6)


def test_one_star_versus_unrated_numbers():
    """Safety-weighted query on the single-segment frame: 5-star > 4-star > unrated > 1-star."""
    df, vid = _star_cars()
    table, o = _overall(df, vid)
    assert o["Rated5"] > o["Rated4"] > o["Unrated"] > o["Rated1"], o


def test_fully_unknown_criterion_stays_fully_unknown():
    df = make_frame([dict(model="A")] + spread_cars())
    table, crit = score_candidates(df, intent(), evidence=NO_EVIDENCE)
    assert "comfort_features" in table.loc[1, "unknown_criteria"]
    assert "comfort_features" not in table.loc[1, "partial_unknown"]
    assert crit.unknown_frac.loc[1, "comfort_features"] == 1.0


# ------------------------------------------------------------------ real catalogue: crash-rating ordering per segment

def real_segment_scores(body):
    """Four copies of one real variant of segment `body` (identical in every cell except the crash rating), scored
    against the real catalogue's reference on a safety-weighted query. Returns ({label: overall}, segment median)."""
    from services.catalogue import get_catalogue
    from services.recsys.criteria import catalogue_reference
    cat = get_catalogue()
    seg = cat[cat["body_type"] == body]
    base = seg.sort_values("variant_id").iloc[len(seg) // 2].copy()
    rows = []
    for k, (label, stars) in enumerate([("5", 5.0), ("4", 4.0), ("unrated", float("nan")), ("1", 1.0)]):
        r = base.copy()
        r["safety_stars_adult"] = stars
        r["variant_id"] = 900000 + k
        r["model"] = f"Probe-{label}"
        r.name = 900000 + k
        rows.append(r)
    cands = pd.DataFrame(rows)
    table, _ = score_candidates(cands, intent(**SAFETY_QUERY), evidence=NO_EVIDENCE, reference=catalogue_reference(cat))
    per_model = seg.groupby(["make", "model"])["safety_stars_adult"].first().dropna().astype(float)
    return {lab: float(table.loc[900000 + k, "overall"]) for k, lab in enumerate(["5", "4", "unrated", "1"])}, per_model


def _rated_segments():
    from services.catalogue import get_catalogue
    cat = get_catalogue()
    return sorted(b for b, g in cat.groupby("body_type") if g["safety_stars_adult"].notna().any())


@pytest.mark.parametrize("body", _rated_segments())
def test_real_catalogue_ordering_5_over_4_over_unrated_over_1(body):
    o, known = real_segment_scores(body)
    assert o["5"] > o["4"] > o["unrated"] > o["1"], (body, o, "segment median of known ratings:", known.median())
