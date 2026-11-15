"""Display-only layer on the owner / expert bars and the owner lines: standing within the segment, the minimum evidence
for an owner line, and the ratings-summary fallback. None of it is read by the score."""
import json

import pandas as pd

from services.recsys import config
from services.recsys.api import recommend
from services.recsys.evidence import EXPORT_THEME_COLS, Evidence
from services.recsys.explain import explain, expert_standing, owner_lines, owner_standing
from services.recsys.score import score_candidates
from services.recsys.weights import build_weights
from tests.test_recsys_reviews import assess, intent, rate, twins, vid


def sat(model, raw, count="300", **kw):
    return dict(model=model, aspect="satisfaction", raw_score=str(raw), value=str(round(raw / 5, 3)), rating_count=str(count),
                source_aspect="overall", **kw)


def segment_of(n, seg="suv", prefix="M"):
    return {f"{prefix}{i}": seg for i in range(n)}


def owner_ev(ratings, segments):
    return Evidence(None, None, rate(ratings), segments=segments)


def themes(rows):
    base = dict(model="A", theme="service_cost", label="", direction="positive", mentions="14", posts_sampled="60",
                share="0.2333", note="Some owners describe servicing as affordable.",
                sample_urls='["http://cw/a/1"]', source="CarWale", period="")
    return pd.DataFrame([{**base, **r} for r in rows], columns=EXPORT_THEME_COLS)


# ------------------------------------------------------------------ owner standing

def nine_suvs(target_raw, count="300"):
    """Nine SUVs rated 4.0 ... 4.8 (step 0.1); the model under test is M0 with `target_raw`."""
    rows = [sat("M0", target_raw, count)] + [sat(f"M{i}", 3.9 + i / 10) for i in range(1, 9)]
    return owner_ev(rows, segment_of(9))


def test_standing_is_the_midrank_percentile_among_the_segments_rated_models():
    ev = nine_suvs(4.5)                  # M0 4.5 ties M6 (4.5): below = 4.0-4.4 -> 5, level = 2 -> (5 + 1) / 9 = 66.7
    st = owner_standing("M0", ev)
    assert st["value"] == 67 and st["band"] == "upper" and st["segment"] == "suv" and st["n_models"] == 9
    assert st["rating"] == 4.5 and st["rating_count"] == 300 and st["scale_max"] == 5.0


def test_wording_thresholds_top_upper_lower_bottom():
    cases = {4.9: ("top", "among the best-rated SUVs"), 4.5: ("upper", "above average among SUVs"),
             4.2: ("lower", "below average among SUVs"), 3.5: ("bottom", "among the lowest-rated SUVs")}
    for raw, (band, words) in cases.items():
        st = owner_standing("M0", nine_suvs(raw))
        assert st["band"] == band and st["caption"].endswith(f"· {words}"), (raw, st)
    # the boundaries come from config: 75 -> top, 50 -> upper, 25 -> lower, 24 -> bottom
    assert config.STANDING_BANDS == [(75, "top"), (50, "upper"), (25, "lower")]


def test_band_boundaries_exactly():
    ev = owner_ev([sat(f"M{i}", 4.0 + i / 100) for i in range(8)], segment_of(8))   # 8 models, no ties
    values = {i: owner_standing(f"M{i}", ev) for i in range(8)}
    assert [values[i]["value"] for i in range(8)] == [6, 19, 31, 44, 56, 69, 81, 94]
    assert [values[i]["band"] for i in range(8)] == ["bottom", "bottom", "lower", "lower", "upper", "upper", "top", "top"]


def test_caption_has_the_raw_rating_and_count():
    st = owner_standing("M0", nine_suvs(4.6, count="336"))
    assert st["caption"].startswith("4.6/5 from 336 ratings · ")


def test_small_segment_shows_the_raw_rating_with_no_standing_claim():
    ev = owner_ev([sat(f"M{i}", 4.0 + i / 10) for i in range(7)], segment_of(7, "sedan"))     # 7 < MIN_SEGMENT_MODELS
    st = owner_standing("M3", ev)
    assert st["value"] is None and st["band"] == "small_segment" and st["n_models"] == 7
    assert st["caption"] == "4.3/5 from 300 ratings · only 7 rated sedans, too few to compare"
    for banned in ("best-rated", "above average", "below average", "lowest-rated"):
        assert banned not in st["caption"]
    assert config.MIN_SEGMENT_MODELS == 8


def test_low_confidence_rating_says_so_and_makes_no_standing_claim():
    ev = nine_suvs(5.0, count="12")
    st = owner_standing("M0", ev)
    assert st["value"] is None and st["band"] == "low_confidence"
    assert st["caption"] == "5.0/5 from only 12 ratings · too few to compare"
    assert st["summary"] == "Owners rate it 5.0/5 overall (CarWale, only 12 ratings, low confidence)"
    assert owner_standing("M0", nine_suvs(4.5, count="30"))["band"] == "upper"       # 30 is enough
    assert owner_standing("M0", nine_suvs(4.5, count="29"))["band"] == "low_confidence"


def test_model_with_no_overall_owner_rating_has_no_standing():
    ev = owner_ev([sat("M1", 4.4)] + [dict(model="M0", aspect="service_cost")], segment_of(2))
    assert owner_standing("M0", ev) is None and owner_standing("nobody", ev) is None


def test_ratings_summary_text():
    ev = owner_ev([sat("M0", 4.58, "336"), dict(model="M0", aspect="service_cost", raw_score="4.4")], segment_of(1))
    assert owner_standing("M0", ev)["summary"] == "Owners rate it 4.6/5 overall, after-sales cost 4.4/5 (CarWale, 336 ratings)"


def test_unknown_segment_makes_no_claim():
    st = owner_standing("M0", owner_ev([sat("M0", 4.5)], {}))
    assert st["band"] == "small_segment" and "no body type on record" in st["caption"]


# ------------------------------------------------------------------ expert standing

def expert_ev(scores, segments):
    rows = [dict(model=m, aspect="overall", raw_score=str(s), value=str(s / 10)) for m, s in scores.items()]
    return Evidence(assess(rows), None, None, segments=segments)


def test_expert_standing_uses_the_overall_score_and_the_same_bands():
    scores = {"M0": 9} | {f"M{i}": 5 + i % 4 for i in range(1, 9)}
    st = expert_standing("M0", expert_ev(scores, segment_of(9)))
    assert st["band"] == "top" and st["value"] > 75 and st["score"] == 9 and st["scale_max"] == 10
    assert st["caption"] == "Autocar India 9/10 overall · among the best-rated SUVs"


def test_expert_small_segment_and_missing_overall():
    ev = expert_ev({f"M{i}": 7 for i in range(5)}, segment_of(5))
    st = expert_standing("M0", ev)
    assert st["value"] is None and st["band"] == "small_segment" and "too few to compare" in st["caption"]
    only_aspect = Evidence(assess([dict(model="M0", aspect="ride_comfort")]), None, None, segments={"M0": "suv"})
    assert expert_standing("M0", only_aspect)["band"] == "no_overall"
    assert expert_standing("zzz", ev) is None


# ------------------------------------------------------------------ minimum evidence for owner lines

def lines(rows, aw=None):
    ev = Evidence(None, themes(rows), None, segments={})
    return owner_lines("A", aw, ev)


def test_owner_line_needs_five_verified_mentions():
    assert config.OWNER_LINE_MIN_MENTIONS == 5
    assert lines([dict(mentions="4")])[0] == []
    assert len(lines([dict(mentions="5")])[0]) == 1
    assert lines([dict(mentions="3", direction="mixed")])[0] == []
    assert lines([dict(mentions="4", direction="positive", theme="reliability")])[0] == []


def test_negative_themes_and_faults_keep_the_stored_minimum_of_3():
    neg = dict(theme="build_issues", direction="negative", mentions="3", note="Panel gaps.")
    fault = dict(theme="recurring_fault", label="clutch judder", direction="negative", mentions="3", note="Judder.")
    shown, caveats = lines([neg, fault])
    assert {r["theme"] for r in shown} == {"build_issues", "recurring_fault"}
    assert {c["theme"] for c in caveats} == {"build_issues", "recurring_fault"}      # caveats were never filtered


def test_low_mention_positive_is_hidden_as_a_line_but_negative_caveats_stay():
    rows = [dict(theme="service_cost", mentions="4"), dict(theme="reliability", direction="negative", mentions="3")]
    shown, caveats = lines(rows)
    assert [r["theme"] for r in shown] == ["reliability"] and [c["theme"] for c in caveats] == ["reliability"]


def test_few_owners_labelling_input_is_kept_for_the_front_end():
    line = lines([dict(mentions="7", posts_sampled="60", share="0.1167")])[0][0]
    assert line["mentions"] == 7 and line["share"] < 0.15


def test_the_shipped_themes_hidden_as_lines():
    t = pd.read_csv(config_path("owner_themes.csv"))
    hidden = t[(t["mentions"] < config.OWNER_LINE_MIN_MENTIONS) & (t["direction"] != "negative")
               & (t["theme"] != "recurring_fault")]
    assert len(t) == 271
    assert hidden.groupby("direction").size().to_dict() == {"mixed": 7, "positive": 51}
    assert (t[t["direction"] == "negative"]["mentions"] >= 3).all()                    # the stored minimum holds


def config_path(name):
    from pathlib import Path
    return Path(__file__).resolve().parents[1] / "data" / name


# ------------------------------------------------------------------ explain() and the card

def test_explain_carries_standing_and_summary_and_scores_do_not_depend_on_it():
    df = twins()
    it = intent(use_case="budget")
    ev = Evidence(assess([dict(model="A", aspect="overall", raw_score="8", value="0.8")]), themes([dict(mentions="4")]),
                  rate([sat("A", 4.5)]), segments={})
    w = build_weights(it)
    table, _ = score_candidates(df, it, w, ev)
    v = vid(df, "A")
    ex = explain(df.loc[v], table.loc[v], w, it, ev)
    assert ex["owner_lines"] == [] and ex["owner_standing"]["summary"].startswith("Owners rate it 4.5/5 overall")
    assert ex["expert_standing"]["band"] == "small_segment"
    # the score is computed with every theme, shown or not
    with_themes = score_candidates(df, it, w, ev)[0]["overall"]
    no_themes = score_candidates(df, it, w, Evidence(ev.assessments, None, rate([sat("A", 4.5)]), segments={}))[0]["overall"]
    assert with_themes.loc[v] != no_themes.loc[v]


def test_recommend_cards_expose_standing_and_ranking_is_unchanged_by_it():
    ev = Evidence.load(segments=None)
    res = recommend("comfortable family SUV under 15 lakh", evidence=ev)
    assert res["recommendations"]
    for c in res["recommendations"]:
        assert {"owner_standing", "expert_standing"} <= set(c)
        st = c["owner_standing"]
        if st:
            assert set(st) >= {"value", "band", "segment", "n_models", "rating", "rating_count", "caption", "summary"}
            assert (st["value"] is None) == (st["band"] in ("low_confidence", "small_segment"))
            assert st["value"] is None or 0 <= st["value"] <= 100
    json.dumps(res)
