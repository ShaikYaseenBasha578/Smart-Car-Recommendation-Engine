"""Blank handling 2026-11-15, change 1: a blank inside a criterion is valued at a conservative prior."""
import numpy as np
import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.recsys import config
from services.recsys.api import recommend
from services.recsys.criteria import SPEC_CRITERIA, TECH_BOOLS, Reference, compute_criteria
from services.recsys.evidence import Evidence
from services.recsys.score import score_candidates
from tests.recsys_frames import make_frame

NO_EVIDENCE = Evidence()


def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None, "soft_preferences": [],
            "cheap_intent": False}
    base.update(kw)
    return base


def tech_frame():
    """Ten background SUVs (about half of every tech feature True) plus X, Y, Z."""
    flags = {c: None for c in TECH_BOOLS}
    bg = []
    for i in range(10):
        bg.append(dict(model=f"G{i}", **{c: (i % 2 == 0) for c in TECH_BOOLS}))
    all_true = {c: True for c in TECH_BOOLS}
    most_true = {**all_true, "apple_carplay": False, "heads_up_display": False}
    x = dict(model="X", **{**flags, "adas_available": True})                 # one known True, the rest blank
    y = dict(model="Y", **all_true)                                          # the same feature True, the rest known True
    z = dict(model="Z", **most_true)                                         # most known True
    return make_frame(bg + [x, y, z])


@pytest.mark.parametrize("mode", ["segment", "flat"])
def test_one_known_true_and_the_rest_blank_scores_below_fully_known_true_and_below_most_true(monkeypatch, mode):
    monkeypatch.setattr(config, "BLANK_PRIOR_MODE", mode)
    df = tech_frame()
    v = compute_criteria(df).values["tech_assist"]
    x, y, z = v.iloc[-3:].tolist()
    assert x < y and x < z
    assert x > 0.0 and x < 0.75            # no longer anywhere near 1.0 (the old mean of the one known field was 1.0)
    table, _ = score_candidates(df, intent(), evidence=NO_EVIDENCE, reference=Reference(df))
    ox, oy, oz = (table.loc[df.index[-3 + i], "overall"] for i in range(3))
    assert ox < oy and ox < oz


def test_blank_prior_is_a_prior_not_a_fact_in_the_detail_and_still_unknown_for_coverage():
    df = tech_frame()
    res = compute_criteria(df)
    xid = df.index[-3]
    det = {d["field"]: d for d in res.detail[xid]["tech_assist"]}
    assert det["adas_available"]["score"] == 1.0 and "prior_score" not in det["adas_available"]
    assert det["camera_360"]["score"] is None and det["camera_360"]["raw"] is None
    assert 0.0 <= det["camera_360"]["prior_score"] < 0.5
    # 3.0 of the 10.5 field weight is known: the unknown fraction is unchanged by the prior
    assert res.unknown_frac.loc[xid, "tech_assist"] == pytest.approx(1 - 3.0 / sum(TECH_BOOLS.values()))
    table, _ = score_candidates(df, intent(), evidence=NO_EVIDENCE, reference=Reference(df))
    assert table.loc[xid, "partial_unknown"]["tech_assist"] == pytest.approx(1 - 3.0 / sum(TECH_BOOLS.values()))
    assert table.loc[xid, "unknown_share"] > table.loc[df.index[-2], "unknown_share"]


def test_prior_values_segment_and_flat(monkeypatch):
    df = tech_frame()
    ref = Reference(df)
    seg, allc = df["body_type"].astype(str), pd.Series("all", index=df.index)
    # camera_360: 12 known models (10 background alternating, Y and Z True), 7 True; X is blank -> share x 0.7
    p = ref.blank_prior("bool:camera_360", "bool", seg, allc).iloc[0]
    assert p == pytest.approx(0.7 * 7 / 12)
    monkeypatch.setattr(config, "BLANK_PRIOR_MODE", "flat")
    assert ref.blank_prior("bool:camera_360", "bool", seg, allc).iloc[0] == config.BLANK_PRIOR_FLAT == 0.35


def test_percentile_prior_is_the_segment_median_minus_the_margin():
    df = make_frame([dict(model=f"M{i}", power_bhp=80 + 10 * i) for i in range(11)]
                    + [dict(model="U", power_bhp=np.nan, torque_nm=np.nan)])
    res = compute_criteria(df)
    det = {d["field"]: d for d in res.detail[len(df)]["performance"]}
    # torque_nm is the same 150 on every other model: the segment median sits at the mid-rank percentile 0.5
    assert det["torque_nm"]["prior_score"] == pytest.approx(0.5 - config.BLANK_PRIOR_MARGIN)
    assert det["torque_nm"]["score"] is None


def test_all_unknown_criterion_does_not_beat_a_known_value_equal_to_the_segment_median():
    """running_cost: 11 petrol SUVs with known mileage, one with none, one at the segment median. The all-blank car
    drops out of nothing: its criterion is still unknown in `values`, but it is scored at the prior (below the median)."""
    rows = [dict(model=f"M{i}", mileage_kmpl=10.0 + i) for i in range(11)]
    rows += [dict(model="UNK", mileage_kmpl=np.nan), dict(model="MID", mileage_kmpl=15.0)]
    df = make_frame(rows)
    crit = compute_criteria(df)
    unk, mid = df.index[-2], df.index[-1]
    assert np.isnan(crit.values.loc[unk, "running_cost"])             # still unknown: explanations say so
    assert crit.scoring.loc[unk, "running_cost"] < crit.values.loc[mid, "running_cost"]
    assert crit.scoring.loc[unk, "running_cost"] == pytest.approx(0.5 - config.BLANK_PRIOR_MARGIN)
    assert crit.unknown_frac.loc[unk, "running_cost"] == 1.0
    table, _ = score_candidates(df, intent(soft_preferences=["mileage"]), evidence=NO_EVIDENCE, reference=Reference(df))
    assert table.loc[unk, "overall"] < table.loc[mid, "overall"]
    assert "running_cost" in table.loc[unk, "unknown_criteria"]


def test_old_fully_known_rows_score_exactly_as_the_weighted_mean_of_their_known_fields():
    """Where every field of a criterion is known, the criterion value is the old weighted mean of the field scores."""
    cat = get_catalogue()
    res = compute_criteria(cat, reference=Reference(cat))
    checked = 0
    for vid in cat.index[::5]:
        for crit in SPEC_CRITERIA:
            fields = [d for d in res.detail[vid][crit] if d["weight"] > 0]
            applicable = [d for d in fields if d["score"] is not None or "prior_score" in d or d["raw"] is not None]
            if res.unknown_frac.loc[vid, crit] > 0 or not fields:
                continue
            known = [d for d in fields if d["score"] is not None]
            if not known or any("prior_score" in d for d in fields):
                continue
            old = sum(d["weight"] * d["score"] for d in known) / sum(d["weight"] for d in known)
            assert res.values.loc[vid, crit] == pytest.approx(old, abs=1e-12)
            checked += 1
    assert checked > 500


def test_blank_cells_never_raise_a_car_above_the_same_car_with_the_cells_known_present():
    df = make_frame([dict(model=f"G{i}", sunroof=(i % 2 == 0), ventilated_front_seats=(i % 2 == 0),
                          cruise_control=(i % 2 == 0)) for i in range(10)]
                    + [dict(model="BLANK", sunroof=True), dict(model="KNOWN", sunroof=True, ventilated_front_seats=True,
                                                               cruise_control=True)])
    table, _ = score_candidates(df, intent(), evidence=NO_EVIDENCE, reference=Reference(df))
    assert table.loc[df.index[-2], "overall"] < table.loc[df.index[-1], "overall"]


def test_explanations_still_say_a_wholly_blank_criterion_is_not_available_and_never_show_the_prior():
    rows = [dict(model=f"M{i}", mileage_kmpl=10.0 + i, power_bhp=80 + 10 * i) for i in range(6)]
    rows.append(dict(model="UNK", mileage_kmpl=np.nan))
    r = recommend("SUV", evidence=Evidence(), catalogue=make_frame(rows))
    unk = next(c for c in r["recommendations"] if c["Model"] == "UNK")      # 7 models: all are shown
    assert "running_cost" not in unk["criteria"]                           # no value is shown for it
    assert any(u.startswith("Running cost") for u in unk["unknowns"])
    assert not any("prior" in u.lower() for c in r["recommendations"] for u in c["unknowns"] + c["match_reasons"])
