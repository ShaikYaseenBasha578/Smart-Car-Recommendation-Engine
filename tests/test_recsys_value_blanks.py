"""Value-for-money blanks 2026-11-15: a derived criterion (features per lakh) values a blank feature cell at the
same conservative blank prior as the feature criteria, never as absent."""
import numpy as np
import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.recsys import config
from services.recsys.criteria import (COMFORT_BOOLS, VALUE_FEATURES, Reference, _fpr, compute_criteria)
from services.recsys.evidence import Evidence
from services.recsys.score import score_candidates
from tests.recsys_frames import make_frame

NO_EVIDENCE = Evidence()
PROBED = ["ventilated_front_seats", "cruise_control"]


def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None, "soft_preferences": [],
            "cheap_intent": False}
    base.update(kw)
    return base


def sedan_frame():
    """Ten background sedans (every value feature known, about half True) and three clones identical in everything
    but the two probed comfort cells: GOOD (True, True), BLANK (blank, blank), LACK (False, False)."""
    bg = [dict(model=f"G{i}", body_type="sedan", **{c: (i % 2 == 0) for c in VALUE_FEATURES}) for i in range(10)]
    common = {c: True for c in VALUE_FEATURES}
    clones = [dict(model="GOOD", body_type="sedan", **{**common, **{c: True for c in PROBED}}),
              dict(model="BLANK", body_type="sedan", **{**common, **{c: None for c in PROBED}}),
              dict(model="LACK", body_type="sedan", **{**common, **{c: False for c in PROBED}})]
    return make_frame(bg + clones)


def test_blank_feature_counts_at_the_blank_prior_in_features_per_lakh_not_as_absent():
    df = sedan_frame()
    ref = Reference(df)
    good, blank, lack = df.index[-3:]
    fpr = _fpr(df, ref)
    assert fpr[lack] < fpr[blank] < fpr[good]
    seg, allc = df["body_type"].astype(str), pd.Series("all", index=df.index)
    priors = sum(ref.blank_prior(f"bool:{c}", "bool", seg, allc)[blank] for c in PROBED)
    assert 0.0 < priors < 2.0
    assert fpr[blank] == pytest.approx((len(VALUE_FEATURES) - len(PROBED) + priors) / (df.loc[blank, "price_ex_showroom"] / 1e5))
    res = compute_criteria(df, reference=ref)
    v = res.values["value_for_budget"]
    assert v[lack] < v[blank] < v[good]


def test_ordering_known_good_above_unknown_above_known_lacking_on_the_sedan_case():
    df = sedan_frame()
    ref = Reference(df)
    good, blank, lack = df.index[-3:]
    table, crit = score_candidates(df, intent(soft_preferences=["comfort"]), evidence=NO_EVIDENCE, reference=ref)
    for c in ("value_for_budget", "comfort_features"):
        assert crit.scoring.loc[lack, c] < crit.scoring.loc[blank, c] < crit.scoring.loc[good, c]
    assert table.loc[lack, "overall"] < table.loc[blank, "overall"] < table.loc[good, "overall"]
    assert table.loc[blank, "unknown_share"] > table.loc[good, "unknown_share"] == table.loc[lack, "unknown_share"]


def test_a_blank_is_charged_to_the_coverage_factor_once_by_the_feature_criterion_not_again_by_value():
    df = sedan_frame()
    ref = Reference(df)
    good, blank, lack = df.index[-3:]
    res = compute_criteria(df, reference=ref)
    assert res.unknown_frac.loc[blank, "value_for_budget"] == 0.0           # the derived criterion adds no charge
    assert res.unknown_frac.loc[blank, "comfort_features"] == pytest.approx(
        (COMFORT_BOOLS["cruise_control"] + COMFORT_BOOLS["ventilated_front_seats"]) / sum(COMFORT_BOOLS.values()))
    table, _ = score_candidates(df, intent(soft_preferences=["comfort"]), evidence=NO_EVIDENCE, reference=ref)
    partial = table.loc[blank, "partial_unknown"]
    assert "comfort_features" in partial and "value_for_budget" not in partial
    # unknown stays above known-lacking in score even with the coverage charge
    assert table.loc[blank, "overall"] > table.loc[lack, "overall"]


def test_fully_known_rows_have_the_plain_known_count_per_lakh_and_the_same_percentile_as_before():
    cat = get_catalogue()
    ref = Reference(cat)
    new = _fpr(cat, ref)
    present = [c for c in VALUE_FEATURES if c in cat.columns]
    known = cat[present].apply(lambda col: col.map(lambda v: v is True or v is False)).all(axis=1)
    assert known.sum() >= 50
    sample = cat.index[known][::max(1, int(known.sum()) // 60)]
    old = (cat.loc[sample, present].apply(lambda col: col.map(lambda v: 1.0 if v is True else 0.0)).sum(axis=1)
           / (cat.loc[sample, "price_ex_showroom"] / 1e5))
    assert new[sample].to_numpy() == pytest.approx(old.to_numpy(), rel=1e-12)


def test_fully_known_hand_built_frame_scores_exactly_as_the_old_count():
    df = make_frame([dict(model=f"M{i}", price_ex_showroom=800000.0 + 50000 * i,
                          **{c: ((i + j) % 3 != 0) for j, c in enumerate(VALUE_FEATURES)}) for i in range(8)])
    ref = Reference(df)
    old_raw = pd.Series([sum(((i + j) % 3 != 0) for j in range(len(VALUE_FEATURES))) / ((800000.0 + 50000 * i) / 1e5)
                         for i in range(8)], index=df.index)
    assert _fpr(df, ref).to_numpy() == pytest.approx(old_raw.to_numpy(), rel=1e-12)
    res = compute_criteria(df, reference=ref)
    expected = ref.percentile("fpr", old_raw, df["body_type"].astype(str), pd.Series("all", index=df.index))
    assert res.values["value_for_budget"].to_numpy() == pytest.approx(expected.to_numpy(), rel=1e-12)
