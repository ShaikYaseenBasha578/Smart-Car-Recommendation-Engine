import json

import numpy as np
import pandas as pd

from services.recsys import config
from services.recsys.criteria import COMFORT_BOOLS, TECH_BOOLS
from services.recsys.evidence import ASSESSMENT_COLS, OWNER_COLS, Evidence
from services.recsys.explain import explain, match_label
from services.recsys.score import score_candidates
from services.recsys.weights import build_weights
from tests.recsys_frames import make_frame

NONE = Evidence()


def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None, "soft_preferences": []}
    base.update(kw)
    return base


def run(df, it, ev=NONE, vid=1):
    w = build_weights(it)
    table, _ = score_candidates(df, it, w, ev)
    return explain(df.loc[vid], table.loc[vid], w, it, ev), table.loc[vid], w


def background():
    return [dict(model=f"B{i}", power_bhp=70 + 12 * i, boot_space_litres=300 + 30 * i, mileage_kmpl=14 + i) for i in range(6)]


def test_label_thresholds():
    (t1, n1), (t2, n2), (t3, n3) = config.MATCH_LEVELS
    assert match_label(t1, 0) == n1
    assert match_label(t1 - 0.001, 0) == n2 and match_label(t2, 0) == n2
    assert match_label(t3, 0) == n3
    assert match_label(t3 - 0.001, 0) == config.MATCH_FLOOR_LABEL
    assert match_label(0.8, 2) == f"{n1} · 2 things unknown"
    assert match_label(0.8, 1) == f"{n1} · 1 thing unknown"
    assert match_label(0.9, 1, relaxed=True) == "Near match · 1 thing unknown"
    assert match_label(None, 0) == "No score"


def test_reasons_cite_only_fields_with_values_and_max_four():
    feats = {c: True for c in list(COMFORT_BOOLS) + list(TECH_BOOLS)}
    df = make_frame([dict(model="Star", safety_stars_adult=5.0, safety_testing_body="Global NCAP", **feats)] + background())
    ex, srow, _ = run(df, intent(required_features=["sunroof"], use_case="family"))
    assert 0 < len(ex["reasons"]) <= config.MAX_REASONS
    row = df.loc[1]
    for r in ex["reasons"]:
        assert r["evidence_class"] in ("spec", "expert", "owner") and r["text"]
        for f in r["fields"]:
            assert f in row.index and not (row[f] is None or (isinstance(row[f], float) and np.isnan(row[f])))
    assert ex["reasons"][0]["text"] == "Has sunroof, as you asked"


def test_nothing_is_cited_that_the_row_lacks():
    df = make_frame([dict(model="Blank")] + background())  # no safety, no features
    ex, _, _ = run(df, intent())
    row = df.loc[1]
    for r in ex["reasons"]:
        for f in r["fields"]:
            assert not pd.isna(row[f]) if not isinstance(row[f], (bool, np.bool_)) else True
    assert all("star" not in r["text"] for r in ex["reasons"])


def test_unknowns_listed_plainly():
    df = make_frame([dict(model="U", safety_stars_adult=np.nan, sunroof=None, mileage_kmpl=np.nan)] + background())
    ex, srow, _ = run(df, intent(required_features=["sunroof"]))
    assert "Crash rating: not available" in ex["unknowns"]
    assert "Sunroof: not confirmed in our data" in ex["unknowns"]
    assert "Running cost: no mileage or range figure on record" in ex["unknowns"]
    assert ex["n_unknown"] == len(ex["unknowns"]) and f"{ex['n_unknown']} things unknown" in ex["match_label"]


def test_expert_and_owner_reasons_carry_source_links():
    a = pd.DataFrame([dict(make="Acme", model="Star", aspect="ride_comfort", rating="5", quote="smooth",
                           source_name="S", source_url="http://review/1", published_on="", variant_scope="")],
                     columns=ASSESSMENT_COLS)
    o = pd.DataFrame([dict(make="Acme", model="Star", theme="reliability", label="", direction="positive",
                           mentions="30", posts_sampled="100", period="2026", sample_urls='["http://post/1"]',
                           source_name="r")], columns=OWNER_COLS)
    ev = Evidence(a, o)
    df = make_frame([dict(model="Star")] + background())
    ex, _, _ = run(df, intent(use_case="family"), ev)
    by_class = {r["evidence_class"]: r for r in ex["reasons"]}
    assert by_class["expert"]["source_url"] == "http://review/1" and "5.0/5" in by_class["expert"]["text"]
    assert by_class["expert"]["fields"] == ["expert_ride_comfort"]
    assert by_class["owner"]["source_url"] == "http://post/1" and "30 of 100" in by_class["owner"]["text"]
    assert "Expert ratings: none for this model yet" in run(df, intent(), ev, vid=2)[0]["unknowns"]


def test_no_review_note_when_no_evidence_exists_at_all():
    df = make_frame(background())
    ex, _, _ = run(df, intent())
    assert not any("Expert" in u or "Owner" in u for u in ex["unknowns"])


def test_explanations_json_serialisable():
    df = make_frame(background())
    ex, _, _ = run(df, intent())
    json.dumps(ex)
