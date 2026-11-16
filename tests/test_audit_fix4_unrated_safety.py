"""Audit 2026-11-16, fix 4: untested is not tested-and-equal.

The unrated prior is one star below the segment median (floor 3 stars), minus a further half star, and never above
(median - half a star). On real data (segment medians are 5 stars everywhere) the crash-rating criterion value is
5 -> 1.0, 4 -> 0.8, unrated -> 0.7, 3 -> 0.6, 2 -> 0.4, 1 -> 0.2: unrated sits strictly below every car rated at or
above the median, and above only the cars genuinely rated lower than its prior."""
import numpy as np
import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.recsys.api import recommend
from services.recsys.criteria import catalogue_reference, compute_criteria
from tests.recsys_frames import make_frame


def safety_values(median_rating, ratings):
    """criterion 'safety' for otherwise identical cars; `median_rating` cars establish the segment median."""
    rows = [dict(model=f"ANCHOR{i}", safety_stars_adult=float(median_rating)) for i in range(9)]
    rows += [dict(model=f"T{i}", safety_stars_adult=np.nan if r is None else float(r)) for i, r in enumerate(ratings)]
    df = make_frame(rows)
    res = compute_criteria(df)
    return list(res.values["safety"].iloc[9:])


def test_ordering_on_a_five_star_median_segment():
    v = dict(zip(["5", "4", "3", "2", "1", "none"], safety_values(5, [5, 4, 3, 2, 1, None])))
    assert v["5"] > v["4"] > v["none"] > v["3"] > v["2"] > v["1"]


@pytest.mark.parametrize("median", [5, 4, 3, 2])
def test_unrated_scores_below_cars_rated_at_or_above_the_segment_median(median):
    v = safety_values(median, [median, 5, None])
    assert v[2] < v[0] and v[2] < v[1]


def test_real_catalogue_table_by_segment(capsys):
    cat = get_catalogue()
    ref = catalogue_reference(cat)
    seg = cat["body_type"].astype(str)
    for body in sorted(seg.unique()):
        rows = cat[seg == body].iloc[:1]
        probe = pd.concat([rows.assign(safety_stars_adult=r) for r in (5.0, 4.0, 3.0, 2.0, 1.0, np.nan)])
        probe.index = range(len(probe))
        vals = compute_criteria(probe, None, ref).values["safety"].tolist()
        assert vals[0] > vals[1] > vals[5] > vals[2] > vals[3] > vals[4], (body, vals)


def test_unrated_card_says_no_crash_test_rating_and_never_a_rating():
    cards = recommend("safe family SUV under 15 lakh")["recommendations"]
    unrated = [c for c in cards if c["safety"] is None]
    assert unrated
    for c in unrated:
        assert c["safety"] is None
        for r in c["reasons"]:
            if r["text"].startswith("Safety:"):
                assert "no crash-test rating" in r["text"] and "-star" not in r["text"]


def test_safe_query_ranks_a_rated_five_star_car_above_an_otherwise_identical_unrated_one():
    rows = [dict(model="UNRATED", safety_stars_adult=np.nan), dict(model="FIVE", safety_stars_adult=5.0)]
    rows += [dict(model=f"A{i}", safety_stars_adult=5.0, price_ex_showroom=2000000.0 + i) for i in range(9)]
    out = recommend("safe SUV", catalogue=make_frame(rows))["recommendations"]
    names = [c["Model"] for c in out]
    assert "FIVE" in names and (("UNRATED" not in names) or names.index("FIVE") < names.index("UNRATED"))
