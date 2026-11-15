"""KB review exports (assessments.csv, owner_ratings.csv): the exporter and the engine that reads them."""
import hashlib
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

from services.recsys import config
from services.recsys.api import recommend
from services.recsys.evidence import (OWNER_RATING_COLS, REVIEW_ASSESSMENT_COLS, Evidence, owner_scale_for_count)
from services.recsys.explain import explain
from services.recsys.score import score_candidates
from services.recsys.weights import build_weights
from tests.recsys_frames import make_frame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_reviews_from_kb as exporter  # noqa: E402


# ------------------------------------------------------------------ helpers

def intent(**kw):
    base = {"budget": {"min": None, "max": None}, "required_features": [], "use_case": None, "soft_preferences": [],
            "cheap_intent": False}
    base.update(kw)
    return base


def assess(rows):
    base = dict(model="A", aspect="ride_comfort", value="0.8", source="Autocar India", url="http://ac/a",
                published_on="2025-10-27", n_sources="1", raw_score="8", scale_max="10",
                source_aspect="Ride Comfort And Handling")
    return pd.DataFrame([{**base, **r} for r in rows], columns=REVIEW_ASSESSMENT_COLS)


def rate(rows):
    base = dict(model="A", aspect="service_cost", value="0.88", rating_count="386", low_confidence="false",
                source="CarWale", url="http://cw/a", observed_at="2026-11-14T00:00:00Z", raw_score="4.4",
                scale_max="5", source_aspect="After Sales Cost and Experience")
    return pd.DataFrame([{**base, **r} for r in rows], columns=OWNER_RATING_COLS)


def background(n=6):
    return [dict(model=f"B{i}", power_bhp=70 + 12 * i, mileage_kmpl=14 + i, boot_space_litres=300 + 30 * i,
                 airbags=2 + (i % 5), price_ex_showroom=800000 + 50000 * i) for i in range(n)]


def twins():
    return make_frame([dict(model="A"), dict(model="B")] + background())


def vid(df, model):
    return int(df.index[df["model"] == model][0])


# ------------------------------------------------------------------ exporter

def _kb(path, assessments, owners):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE model (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER);
        CREATE VIEW v_variant_canonical_q AS SELECT id, model_id FROM variant;
        CREATE TABLE professional_assessment (id INTEGER PRIMARY KEY, model_id INT, source_id INT, source_aspect TEXT,
            score REAL, scale_max REAL, source_url TEXT, published_on TEXT, observed_at TEXT, status TEXT);
        CREATE TABLE owner_rating (id INTEGER PRIMARY KEY, model_id INT, source_id INT, source_aspect TEXT,
            score REAL, scale_max REAL, rating_count INT, source_url TEXT, observed_at TEXT, status TEXT);
        INSERT INTO model VALUES (1, 'Nexon'), (2, 'Punch');
        INSERT INTO variant VALUES (1, 1), (2, 2);
        INSERT INTO source VALUES (1, 'Autocar India expert review'), (2, 'CarWale user ratings');
    """)
    con.executemany("INSERT INTO professional_assessment VALUES (?,?,?,?,?,?,?,?,?,?)", assessments)
    con.executemany("INSERT INTO owner_rating VALUES (?,?,?,?,?,?,?,?,?,?)", owners)
    con.commit()
    con.close()


def _sha(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def test_exporter_maps_labels_scales_flags_and_is_deterministic(tmp_path):
    db = tmp_path / "kb.db"
    _kb(db, [
        (1, 1, 1, "Performance And Refinement", 7.0, 10.0, "http://ac/n", "2025-07-04", "2026-11-14", "current"),
        (2, 1, 1, "Ride Comfort And Handling", 8.0, 10.0, "http://ac/n", None, "2026-11-14", "current"),
        (3, 1, 1, "overall", 8.0, 10.0, "http://ac/n", "2025-07-04", "2026-11-14", "current"),
        (4, 2, 1, "Value For Money", 9.0, 10.0, "http://ac/p", "2025-07-04", "2026-11-14", "superseded"),
    ], [
        (1, 1, 2, "After Sales Cost and Experience", 4.4, 5.0, 386, "http://cw/n", "2026-11-14T00:00:00Z", "current"),
        (2, 1, 2, "Design and Styling", 4.0, 5.0, 386, "http://cw/n", "2026-11-14T00:00:00Z", "current"),
        (3, 2, 2, "overall", 4.5, 5.0, 11, "http://cw/p", "2026-11-14T00:00:00Z", "current"),
    ])
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    assert exporter.main(["--db", str(db), "--out-dir", str(out1)]) == 0
    assert exporter.main(["--db", str(db), "--out-dir", str(out2)]) == 0
    for name in ("assessments.csv", "owner_ratings.csv"):
        assert _sha(out1 / name) == _sha(out2 / name)
    a = pd.read_csv(out1 / "assessments.csv", dtype=str, keep_default_na=False)
    assert list(a.columns) == exporter.ASSESSMENT_COLUMNS
    by = {(r.model, r.aspect): r for r in a.itertuples()}
    assert {k[1] for k in by} == {"engine_performance", "refinement", "ride_comfort", "handling", "overall"}
    assert by[("Nexon", "refinement")].value == "0.7" and by[("Nexon", "refinement")].source == "Autocar India"
    assert by[("Nexon", "handling")].published_on == "" and by[("Nexon", "handling")].raw_score == "8"
    assert not any(r.model == "Punch" for r in a.itertuples())              # superseded rows are not exported
    o = pd.read_csv(out1 / "owner_ratings.csv", dtype=str, keep_default_na=False)
    assert list(o.columns) == exporter.OWNER_COLUMNS
    ob = {(r.model, r.aspect): r for r in o.itertuples()}
    assert {("Nexon", "service_cost"), ("Nexon", "service_experience"), ("Nexon", "design"), ("Punch", "satisfaction")} == set(ob)
    assert ob[("Nexon", "service_cost")].value == "0.88" and ob[("Nexon", "service_cost")].low_confidence == "false"
    assert ob[("Punch", "satisfaction")].low_confidence == "true" and ob[("Punch", "satisfaction")].rating_count == "11"


def test_exporter_fails_on_an_unmapped_label_and_on_unknown_models(tmp_path):
    db = tmp_path / "kb.db"
    _kb(db, [(1, 1, 1, "Brand New Label", 7.0, 10.0, "u", None, "2026", "current")], [])
    assert exporter.main(["--db", str(db), "--out-dir", str(tmp_path / "o")]) == 1
    db2 = tmp_path / "kb2.db"
    _kb(db2, [], [])
    con = sqlite3.connect(db2)
    con.execute("DELETE FROM variant WHERE model_id = 1")
    con.execute("INSERT INTO owner_rating VALUES (1,1,2,'overall',4,5,50,'u','2026','current')")
    con.commit()
    con.close()
    assert exporter.main(["--db", str(db2), "--out-dir", str(tmp_path / "o2")]) == 1


def test_label_map_covers_the_spec_and_uses_only_engine_aspects():
    from services.recsys.evidence import ASPECTS, THEMES
    assert exporter.LABEL_MAP[("expert", "Performance And Refinement")] == ["engine_performance", "refinement"]
    assert exporter.LABEL_MAP[("expert", "Ride Comfort And Handling")] == ["ride_comfort", "handling"]
    assert exporter.LABEL_MAP[("owner", "After Sales Cost and Experience")] == ["service_cost", "service_experience"]
    for (kind, _), aspects in exporter.LABEL_MAP.items():
        for a in aspects:
            ok = (ASPECTS + ["overall"]) if kind == "expert" else (THEMES + sorted(exporter.UNUSED_IN_SCORING))
            assert a in ok, (kind, a)


def test_script_refuses_a_missing_db(tmp_path):
    assert exporter.main(["--db", str(tmp_path / "nope.db")]) == 2


# ------------------------------------------------------------------ engine: expert values

def test_expert_value_is_the_exported_value_and_other_aspects_stay_unknown():
    ev = Evidence(assess([dict(aspect="ride_comfort", value="0.8"), dict(aspect="handling", value="0.6")]))
    df = twins()
    vals = ev.values_for(df)
    a, b = vals.loc[vid(df, "A")], vals.loc[vid(df, "B")]
    assert a["expert_ride_comfort"] == pytest.approx(0.8) and a["expert_handling"] == pytest.approx(0.6)
    assert pd.isna(a["expert_refinement"]) and b.isna().all()
    hit = ev.expert("Whatever make", "A", "ride_comfort")       # review files carry no make
    assert hit["n_sources"] == 1


def test_overall_is_only_a_low_weight_fallback():
    # model A has an aspect row, model C only an overall row
    ev = Evidence(assess([dict(model="A", aspect="ride_comfort", value="0.8"),
                          dict(model="A", aspect="overall", value="0.5"),
                          dict(model="C", aspect="overall", value="0.9")]))
    df = make_frame([dict(model="A"), dict(model="C"), dict(model="D")] + background())
    vals = ev.values_for(df)
    a, c, d = (vals.loc[vid(df, m)] for m in "ACD")
    assert a["expert_ride_comfort"] == pytest.approx(0.8) and pd.isna(a["expert_handling"])   # overall not mixed in
    assert c["expert_handling"] == pytest.approx(0.9) and c["expert_ride_comfort"] == pytest.approx(0.9)
    assert d.isna().all()
    rel = ["ride_comfort", "handling"]
    full = Evidence(assess([dict(model="C", aspect=x, value="0.9") for x in rel])).expert_scale("", "C", rel)
    fallback = ev.expert_scale("", "C", rel)
    assert fallback == pytest.approx(full * config.OVERALL_FALLBACK_SCALE)
    assert ev.expert_scale("", "D", rel) is None


def test_thin_evidence_scaling_applies_to_review_rows():
    # the file has rows for three aspects; model A has two of them. front_space has no row for any model, so it cannot
    # be covered and is not counted in the denominator (change 3a): 2 of 3 relevant aspects, one source
    ev = Evidence(assess([dict(aspect="ride_comfort"), dict(aspect="handling"), dict(model="Z", aspect="refinement")]))
    assert ev.expert_scale("", "A", ["ride_comfort", "handling", "refinement", "front_space"]) == pytest.approx(2 / 3 * 0.5)


# ------------------------------------------------------------------ engine: owner ratings and shrinkage

def test_rating_count_shrinks_toward_the_segment_mean_and_orders_by_count():
    ev = Evidence(owner_ratings=rate([
        dict(model="Few", value="0.96", rating_count="11"),
        dict(model="Many", value="0.96", rating_count="1000"),
        dict(model="Low", value="0.60", rating_count="500"),
        dict(model="Mid", value="0.80", rating_count="500"),
    ]))
    few, many = ev.owner("", "Few", "service_cost"), ev.owner("", "Many", "service_cost")
    mean = (0.96 + 0.96 + 0.60 + 0.80) / 4
    w_few, w_many = 11 / 61, 1000 / 1050
    assert few["value"] == pytest.approx(w_few * 0.96 + (1 - w_few) * mean)
    assert many["value"] == pytest.approx(w_many * 0.96 + (1 - w_many) * mean)
    assert many["value"] > few["value"] > mean                  # same score, more ratings: closer to the raw score
    assert few["shrink_weight"] == pytest.approx(owner_scale_for_count(11))
    # a low raw score is lifted toward the mean in proportion to how few ratings it has
    thin_low = Evidence(owner_ratings=rate([dict(model="X", value="0.2", rating_count="10"),
                                            dict(model="Y", value="0.8", rating_count="500")]))
    assert thin_low.owner("", "X", "service_cost")["value"] > 0.2


def test_missing_count_uses_the_no_count_weight():
    ev = Evidence(owner_ratings=rate([dict(model="X", value="0.9", rating_count=""),
                                      dict(model="Y", value="0.5", rating_count="500")]))
    w = config.OWNER_NO_COUNT_SCALE
    assert ev.owner("", "X", "service_cost")["value"] == pytest.approx(w * 0.9 + (1 - w) * 0.7)


def test_segment_mean_is_by_body_type_when_the_segment_is_big_enough():
    models = {f"S{i}": "suv" for i in range(config.MIN_SEGMENT_MODELS)}
    models.update({"H1": "hatchback", "H2": "hatchback"})
    rows = [dict(model=m, value="0.9", rating_count="50") for m in models if m.startswith("S")]
    rows += [dict(model="H1", value="0.5", rating_count="50"), dict(model="H2", value="0.5", rating_count="50")]
    ev = Evidence(owner_ratings=rate(rows), segments=models)
    assert ev.owner("", "S0", "service_cost")["segment_mean"] == pytest.approx(0.9)
    # hatchbacks are too few for their own mean: the all-model mean is used
    assert ev.owner("", "H1", "service_cost")["segment_mean"] == pytest.approx((0.9 * 8 + 0.5 * 2) / 10)


def test_design_and_unknown_owner_aspects_are_not_scored():
    ev = Evidence(owner_ratings=rate([dict(aspect="design"), dict(aspect="vibes")]))
    assert ev.empty


def test_owner_class_scale_uses_the_rating_count():
    ev = Evidence(owner_ratings=rate([dict(model="A", rating_count="150")]))
    assert ev.owner_sample("", "A") == 150
    # change 3e: ratings are shrunk by their count (value), the class weight is not scaled by it a second time
    assert ev.owner_scale("", "A") == 1.0


# ------------------------------------------------------------------ empty files change nothing

def test_empty_review_files_reproduce_the_previous_results_exactly():
    base = recommend("family suv under 15 lakh with sunroof", evidence=Evidence())
    empty = recommend("family suv under 15 lakh with sunroof",
                      evidence=Evidence(assess([]), None, rate([]), segments={}))
    import json
    assert json.dumps(base, sort_keys=True) == json.dumps(empty, sort_keys=True)


# ------------------------------------------------------------------ a strong owner service rating gains on a service-cost query

def test_strong_after_sales_rating_gains_on_a_service_cost_query():
    df = twins()
    ratings = rate([dict(model="A", aspect="service_cost", value="0.96", rating_count="900"),
                    dict(model="A", aspect="service_experience", value="0.96", rating_count="900"),
                    dict(model="B", aspect="service_cost", value="0.60", rating_count="900"),
                    dict(model="B", aspect="service_experience", value="0.60", rating_count="900")]
                   + [dict(model=f"B{i}", aspect=a, value="0.78", rating_count="900")
                      for i in range(6) for a in ("service_cost", "service_experience")])
    ev = Evidence(owner_ratings=ratings)
    # "low maintenance / service cost" style: the budget profile boosts owner service cost, or the chip is turned up
    for it, overrides in ((intent(use_case="budget"), None), (intent(), {"owner_service_cost": 4.0})):
        w = build_weights(it, overrides)
        table, _ = score_candidates(df, it, w, ev)
        none_table, _ = score_candidates(df, it, build_weights(it, overrides), Evidence())
        gap = table.loc[vid(df, "A"), "overall"] - table.loc[vid(df, "B"), "overall"]
        assert gap > 0                                                  # strong service rating wins
        assert none_table.loc[vid(df, "A"), "overall"] == pytest.approx(none_table.loc[vid(df, "B"), "overall"])
        assert w["criteria"]["owner_service_cost"]["multiplier"] > 1


def test_a_thin_strong_rating_gains_less_than_a_thick_one():
    df = twins()

    def gap(count):
        ev = Evidence(owner_ratings=rate([dict(model="A", aspect="service_cost", value="0.96", rating_count=str(count)),
                                          dict(model="B", aspect="service_cost", value="0.60", rating_count=str(count))]
                                         + [dict(model=f"B{i}", aspect="service_cost", value="0.78", rating_count="900")
                                            for i in range(6)]))
        it = intent(use_case="budget")
        t, _ = score_candidates(df, it, build_weights(it), ev)
        return t.loc[vid(df, "A"), "overall"] - t.loc[vid(df, "B"), "overall"]

    assert gap(900) > gap(40) > gap(10) > 0


# ------------------------------------------------------------------ explanations

def _explain(ev, it, model="A"):
    df = twins()
    w = build_weights(it)
    table, _ = score_candidates(df, it, w, ev)
    v = vid(df, model)
    return explain(df.loc[v], table.loc[v], w, it, ev)


def test_expert_reason_cites_source_score_and_month():
    ev = Evidence(assess([dict(aspect="ride_comfort"), dict(aspect="handling", value="0.8")]))
    ex = _explain(ev, intent(use_case="family"))
    texts = [r["text"] for r in ex["reasons"] if r["evidence_class"] == "expert"]
    assert texts == ["Autocar India scores ride comfort and handling 8/10 (Oct 2025)"]      # one reason, not two
    r = next(r for r in ex["reasons"] if r["evidence_class"] == "expert")
    assert set(r["fields"]) == {"expert_ride_comfort", "expert_handling"} and r["source_url"] == "http://ac/a"


def test_expert_reason_without_a_date_has_no_date():
    ev = Evidence(assess([dict(aspect="ride_comfort", published_on="")]))
    ex = _explain(ev, intent(use_case="family"))
    assert [r["text"] for r in ex["reasons"] if r["evidence_class"] == "expert"] == \
        ["Autocar India scores ride comfort and handling 8/10"]


def test_owner_reason_cites_rating_source_and_count_and_low_confidence_is_worded_as_such():
    good = Evidence(owner_ratings=rate([dict(aspect="service_cost", value="0.88", rating_count="386")]))
    ex = _explain(good, intent(use_case="budget"))
    assert "Owners rate after sales cost and experience 4.4/5 (CarWale, 386 ratings)" in [r["text"] for r in ex["reasons"]]
    thin = Evidence(owner_ratings=rate([dict(aspect="service_cost", value="0.88", rating_count="11",
                                             low_confidence="true")]))
    ex = _explain(thin, intent(use_case="budget"))
    owner = [r["text"] for r in ex["reasons"] if r["evidence_class"] == "owner"]
    assert owner == ["Owners rate after sales cost and experience 4.4/5, but on only 11 ratings (CarWale, low confidence)"]


def test_overall_fallback_is_worded_as_an_overall_score():
    ev = Evidence(assess([dict(aspect="overall", value="0.8", source_aspect="overall")]))
    ex = _explain(ev, intent(use_case="family"))
    texts = [r["text"] for r in ex["reasons"] if r["evidence_class"] == "expert"]
    assert texts == ["Autocar India gives an overall score of 8/10 (Oct 2025)"]


def test_no_score_is_shown_for_a_model_without_a_row():
    ev = Evidence(assess([dict(model="A")]), owner_ratings=rate([dict(model="A")]))
    ex = _explain(ev, intent(use_case="family"), model="B")
    assert not any(r["evidence_class"] in ("expert", "owner") for r in ex["reasons"])
    assert "Expert ratings: none for this model yet" in ex["unknowns"]
    assert not any("/10" in r["text"] or "ratings)" in r["text"] for r in ex["reasons"])
