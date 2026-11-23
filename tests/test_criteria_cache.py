"""The criteria cache (criteria.py: computed once per catalogue load, sliced per query) must give exactly what the
ordinary per-query path gives, for any candidate subset, with or without a budget, and must not be changed by the
queries that used it before."""

import numpy as np
import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.recsys import criteria as C


def _slow(df, budget, ref, whole):
    return C._build(df, budget, ref, whole)


def _same(a, b):
    for name in ("values", "scoring", "unknown_frac"):
        x, y = getattr(a, name), getattr(b, name)
        assert list(x.columns) == list(y.columns), name
        assert x.index.equals(y.index), name
        # exact, NaN in the same places: the cache is a speed change only
        np.testing.assert_array_equal(x.to_numpy(dtype=float), y.to_numpy(dtype=float), err_msg=name)
    # The per-row detail (built on demand; no API response carries it) lists one entry per field the frame needs. The
    # whole-catalogue cache always needs every fuel's mileage field, a CNG-only frame only km/kg, so the cache may list
    # extra fields, but only empty ones that do not apply to the row; every field both list must be identical.
    for i in list(a.values.index[:12]):
        for crit, slow_fields in b.detail[i].items():
            fast = {f["field"]: f for f in a.detail[i][crit]}
            for f in slow_fields:
                assert fast.pop(f["field"]) == f, (i, crit, f["field"])
            assert all(f["raw"] is None and f["score"] is None and "prior_score" not in f for f in fast.values()), (i, crit, fast)


@pytest.fixture(scope="module")
def cat():
    return get_catalogue()


@pytest.mark.parametrize("budget", [None, {"min": None, "max": 1000000}, {"min": None, "max": 2500000}])
@pytest.mark.parametrize("whole", [False, True])
def test_cached_path_equals_the_ordinary_path(cat, budget, whole):
    ref = C.catalogue_reference(cat)
    for mask in (cat["body_type"] == "suv", cat["fuel_type"] == "cng", cat["price_ex_showroom"] < 800000):
        sub = cat[mask.fillna(False)]
        fast = C.compute_criteria(sub, budget, ref, price_whole_catalogue=whole)
        _same(fast, _slow(sub, budget, ref, whole))


def test_cache_is_not_changed_by_earlier_queries(cat):
    ref = C.catalogue_reference(cat)
    sub = cat[cat["body_type"] == "hatchback"]
    first = C.compute_criteria(sub, None, ref)
    C.compute_criteria(cat[cat["body_type"] == "suv"], {"min": None, "max": 900000}, ref)   # a budget query in between
    again = C.compute_criteria(sub, None, ref)
    _same(first, again)


def test_a_frame_that_is_not_a_catalogue_subset_takes_the_ordinary_path(cat):
    ref = C.catalogue_reference(cat)
    edited = cat.head(30).copy()
    edited.loc[edited.index[0], "airbags"] = 99.0          # a value the catalogue does not hold
    assert not ref.covers(edited)
    _same(C.compute_criteria(edited, None, ref), _slow(edited, None, ref, False))
