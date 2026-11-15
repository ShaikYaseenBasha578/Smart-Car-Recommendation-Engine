import logging

import numpy as np
import pandas as pd

from services.recsys import config
from services.recsys.criteria import budget_fit, compute_criteria
from services.recsys.evidence import ASSESSMENT_COLS, OWNER_COLS, OWNER_RATING_COLS, Evidence
from tests.recsys_frames import make_frame


def _suvs(n=6, **kw):
    return make_frame([dict(model=f"M{i}", power_bhp=80 + 10 * i, **kw) for i in range(n)])


def test_all_unknown_fields_give_none_not_zero():
    df = make_frame([dict(model="A")] * 6)  # every comfort boolean is None
    res = compute_criteria(df)
    assert res.values["comfort_features"].isna().all()
    assert res.values["tech_assist"].isna().all()


def test_unknown_field_is_valued_at_a_prior_known_false_is_zero():
    """A blank is neither left out of the mean nor zero: it takes the segment share of True times 0.7."""
    bg = [dict(model=f"G{i}", auto_climate_control=True, rear_ac_vents=True) for i in range(8)]
    df = make_frame(bg + [dict(model="A", auto_climate_control=True, rear_ac_vents=None),
                          dict(model="B", auto_climate_control=True, rear_ac_vents=True),
                          dict(model="C", auto_climate_control=True, rear_ac_vents=False)])
    res = compute_criteria(df)
    a, b, c = res.values["comfort_features"].iloc[-3:].tolist()
    assert c < a < b            # known lacking < unknown < known present
    fields = {d["field"]: d for d in res.detail[len(bg) + 1]["comfort_features"]}
    rear = fields["rear_ac_vents"]
    assert rear["score"] is None and rear["raw"] is None          # never displayed as a known value
    assert rear["prior_score"] == pytest.approx(0.7 * 9 / 10)     # 9 of 10 known cells (model-weighted) are True x factor


def test_running_cost_never_compared_across_fuels():
    rows = [dict(model=f"P{i}", mileage_kmpl=10 + i) for i in range(5)]
    rows += [dict(model=f"D{i}", fuel_type="diesel", mileage_kmpl=30 + i) for i in range(5)]
    rows += [dict(model="C", fuel_type="cng", mileage_kmpl=np.nan, mileage_km_per_kg=26.0)]
    df = make_frame(rows)
    rc = compute_criteria(df).values["running_cost"]
    # the worst diesel (30 kmpl) is not better than the best petrol (14 kmpl) on raw numbers: both rank inside their own fuel
    assert rc.iloc[0] < 0.2 and rc.iloc[5] < 0.2           # lowest of each fuel
    assert rc.iloc[4] > 0.8 and rc.iloc[9] > 0.8           # highest of each fuel
    assert abs(rc.iloc[10] - 0.5) < 1e-9                   # lone CNG: neutral, not compared with petrol/diesel


def test_running_cost_uses_unit_of_the_fuel_and_unknown_is_none():
    df = make_frame([dict(model="C1", fuel_type="cng", mileage_kmpl=26.1, mileage_km_per_kg=np.nan),
                     dict(model="E1", fuel_type="electric", mileage_kmpl=np.nan, ev_range_km=400.0)])
    rc = compute_criteria(df).values["running_cost"]
    assert np.isnan(rc.iloc[0])   # CNG kmpl is never used as km/kg
    assert not np.isnan(rc.iloc[1])


def test_small_segment_falls_back_to_all_candidates():
    rows = [dict(model="H1", body_type="hatchback", power_bhp=60)] + [dict(model=f"S{i}", power_bhp=80 + 10 * i) for i in range(6)]
    res = compute_criteria(make_frame(rows))
    # lone hatchback is compared with all 7 candidates, so it is the lowest rather than neutral 0.5
    f = {d["field"]: d for d in res.detail[1]["performance"]}
    assert f["power_to_weight_bhp_per_tonne"]["score"] < 0.2


def test_budget_fit_does_not_reward_cheapest():
    assert budget_fit(1_000_000, 1_000_000) == 1.0
    assert budget_fit(800_000, 1_000_000) == 1.0
    assert budget_fit(300_000, 1_000_000) < budget_fit(800_000, 1_000_000)
    assert budget_fit(1_100_000, 1_000_000) < 1.0
    assert budget_fit(500_000, None) is None


def test_value_for_budget_without_budget_is_segment_relative_only():
    from services.recsys.criteria import VALUE_FEATURES
    df = _suvs(6, **{c: True for c in VALUE_FEATURES})
    res = compute_criteria(df)
    assert res.values["value_for_budget"].notna().all()
    assert [d["field"] for d in res.detail[1]["value_for_budget"] if d["score"] is not None] == ["features_per_lakh"]
    res2 = compute_criteria(df, {"min": None, "max": 1200000})
    assert "price_vs_budget" in [d["field"] for d in res2.detail[1]["value_for_budget"]]


def test_features_per_rupee_unknown_when_most_cells_blank():
    res = compute_criteria(_suvs(6, sunroof=True, esc=True))
    assert res.values["value_for_budget"].isna().all()


def test_safety_unrated_is_unknown_not_zero():
    df = make_frame([dict(model="A", safety_stars_adult=np.nan, esc=True, abs=True, tpms=True, hill_assist=True),
                     dict(model="B", safety_stars_adult=5.0, esc=True, abs=True, tpms=True, hill_assist=True)])
    s = compute_criteria(df).values["safety"]
    assert s.iloc[0] > 0.5 and s.iloc[1] > s.iloc[0] - 1e-9


# ---------------------------------------------------------------- evidence

def _assess(rows):
    base = dict(make="Acme", model="M0", aspect="ride_comfort", rating="4", quote="q", source_name="s",
                source_url="http://x/1", published_on="2026-01-01", variant_scope="")
    return pd.DataFrame([{**base, **r} for r in rows], columns=ASSESSMENT_COLS)


def _owner(rows):
    base = dict(make="Acme", model="M0", theme="reliability", label="", direction="positive", mentions="10",
                posts_sampled="100", period="2026", sample_urls='["http://o/1"]', source_name="reddit")
    return pd.DataFrame([{**base, **r} for r in rows], columns=OWNER_COLS)


def test_missing_and_empty_files(tmp_path):
    ev = Evidence.load(tmp_path / "nope.csv", tmp_path / "nope2.csv", tmp_path / "nope3.csv")
    assert ev.empty
    (tmp_path / "a.csv").write_text(",".join(ASSESSMENT_COLS) + "\n")
    (tmp_path / "o.csv").write_text(",".join(OWNER_COLS) + "\n")
    (tmp_path / "r.csv").write_text(",".join(OWNER_RATING_COLS) + "\n")
    ev = Evidence.load(tmp_path / "a.csv", tmp_path / "o.csv", tmp_path / "r.csv")
    assert ev.empty
    df = _suvs(2)
    assert ev.values_for(df).isna().all().all()


def test_repo_data_files_exist_with_headers():
    from services.recsys.evidence import (ASSESSMENTS_CSV, OWNER_RATING_COLS, OWNER_RATINGS_CSV, OWNER_THEMES_CSV,
                                          REVIEW_ASSESSMENT_COLS)
    # assessments.csv and owner_ratings.csv are the KB review export (scripts/export_reviews_from_kb.py)
    assert ASSESSMENTS_CSV.read_text().splitlines()[0].split(",") == REVIEW_ASSESSMENT_COLS
    assert OWNER_RATINGS_CSV.read_text().splitlines()[0].split(",") == OWNER_RATING_COLS
    assert OWNER_THEMES_CSV.read_text().strip().split(",") == OWNER_COLS


def test_expert_mean_rating_mapped_and_counted():
    ev = Evidence(_assess([dict(rating="5"), dict(rating="3", source_url="http://x/2")]))
    hit = ev.expert("Acme", "M0", "ride_comfort")
    assert hit["n_sources"] == 2 and abs(hit["value"] - 0.75) < 1e-9
    vals = ev.values_for(_suvs(1))
    assert abs(vals.iloc[0]["expert_ride_comfort"] - 0.75) < 1e-9
    assert np.isnan(vals.iloc[0]["expert_handling"])


def test_rows_outside_fixed_lists_are_rejected_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        ev = Evidence(_assess([dict(aspect="vibes"), dict(rating="9"), dict()]),
                      _owner([dict(theme="coolness"), dict(direction="sideways")]))
    assert len(ev.assessments) == 1 and len(ev.owner_themes) == 0
    assert sum("dropped" in r.message for r in caplog.records) == 4


def test_owner_theme_formula_and_minimum_sample():
    pos = Evidence(owner_themes=_owner([dict(mentions="25", posts_sampled="100")]))
    assert abs(pos.owner("Acme", "M0", "reliability")["value"] - 1.0) < 1e-9
    neg = Evidence(owner_themes=_owner([dict(direction="negative", mentions="25", posts_sampled="100")]))
    assert abs(neg.owner("Acme", "M0", "reliability")["value"] - 0.0) < 1e-9
    mixed = Evidence(owner_themes=_owner([dict(direction="mixed")]))
    assert abs(mixed.owner("Acme", "M0", "reliability")["value"] - 0.5) < 1e-9
    weak = Evidence(owner_themes=_owner([dict(mentions="1", posts_sampled="100")]))
    assert 0.5 < weak.owner("Acme", "M0", "reliability")["value"] < 0.6
    small = Evidence(owner_themes=_owner([dict(posts_sampled=str(config.OWNER_MIN_POSTS - 1), mentions="5")]))
    assert small.owner("Acme", "M0", "reliability") is None
    assert np.isnan(small.values_for(_suvs(1)).iloc[0]["owner_reliability"])


# ---------------------------------------------------------------- reference populations (segment-relative, stable)

def test_criterion_scores_do_not_move_with_an_unrelated_budget_filter():
    from services.catalogue import get_catalogue
    from services.recsys.criteria import catalogue_reference
    cat = get_catalogue()
    ref = catalogue_reference(cat)
    suvs = cat[cat["body_type"] == "suv"]
    cheap = suvs[suvs["price_ex_showroom"] <= 1_200_000]
    assert 0 < len(cheap) < len(suvs)
    a = compute_criteria(suvs, None, ref).values.loc[cheap.index]
    b = compute_criteria(cheap, None, ref).values
    pd.testing.assert_frame_equal(a, b)
    assert catalogue_reference(cat) is ref        # built once per catalogue load, then reused


def test_each_model_weighs_one_in_the_reference_not_each_variant():
    # model X has 30 variants at 10 kmpl, 9 other models have 1 variant each at 20 kmpl.
    # By variants X would hold 30 of 39 entries; per model it is 1 of 10.
    rows = [dict(model="X", variant=f"v{i}", mileage_kmpl=10.0) for i in range(30)]
    rows += [dict(model=f"Y{i}", mileage_kmpl=20.0) for i in range(9)]
    df = make_frame(rows)
    rc = compute_criteria(df).values["running_cost"]
    assert rc.iloc[0] == pytest.approx(0.05)      # (0 below + 0.5 x 1 equal) / 10 models
    assert rc.iloc[30] == pytest.approx(0.55)     # (1 below + 0.5 x 9 equal) / 10 models


def test_small_segment_falls_back_to_whole_reference_below_min_models():
    rows = [dict(model=f"H{i}", body_type="hatchback", power_bhp=50 + i) for i in range(config.MIN_SEGMENT_MODELS - 1)]
    rows += [dict(model=f"S{i}", power_bhp=100 + 10 * i) for i in range(config.MIN_SEGMENT_MODELS)]
    res = compute_criteria(make_frame(rows))
    f = {d["field"]: d for d in res.detail[1]["performance"]}
    assert f["power_to_weight_bhp_per_tonne"]["score"] < 0.2    # whole population, where hatchbacks are the weakest


import pytest  # noqa: E402
