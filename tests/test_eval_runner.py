import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
E = importlib.util.module_from_spec(spec)
sys.modules["run_eval"] = E
spec.loader.exec_module(E)


def test_rbo_bounds_and_order_sensitivity():
    assert E.rbo(list("abcdefgh"), list("abcdefgh")) == pytest.approx(1.0)
    assert E.rbo(list("abcdefgh"), list("ijklmnop")) == 0.0
    top_swap = E.rbo(list("abcdefgh"), list("bacdefgh"))
    tail_swap = E.rbo(list("abcdefgh"), list("abcdefhg"))
    assert tail_swap > top_swap > 0.8


def test_label_truthfulness_flags_missing_and_extra():
    cat = E.get_catalogue()
    row = cat[(cat["body_type"] == "suv") & cat["price_ex_showroom"].notna()].iloc[0]
    car = {"variant_id": int(row["variant_id"]), "Model": row["model"], "Variant": row["variant"]}
    expect = {"body_include": ["hatchback"], "budget_max": 1}          # this car breaks body and budget
    honest = dict(car, violations=[{"constraint": "body_type"}, {"constraint": "budget"}])
    assert E.label_truthfulness([honest], expect)["truthful"]
    silent = dict(car, violations=[{"constraint": "budget"}])
    bad = E.label_truthfulness([silent], expect)
    assert not bad["truthful"] and bad["cars"][0]["missing"] == ["body"]
    over = dict(car, violations=[{"constraint": "body_type"}, {"constraint": "budget"}, {"constraint": "fuel"}])
    assert E.label_truthfulness([over], expect)["cars"][0]["extra"] == ["fuel"]


def test_is_relaxed_response():
    assert E.is_relaxed_response({"relaxation": {"keys": ["budget"]}, "recommendations": [{"violations": []}]})
    assert not E.is_relaxed_response({"recommendations": [{"violations": []}]})
    assert not E.is_relaxed_response({"relaxation": {"keys": []}, "recommendations": [{"Model": "x"}]})


def test_shortlist_agreement(tmp_path):
    sheet = tmp_path / "s.csv"
    sheet.write_text("id,query,car_1,car_2,car_3,car_4,car_5,notes\nq1,x,,,,,,\nq2,y,Tata Nexon,kia seltos,,,,\n")
    recs = [{"id": "q1", "top_cars": []}, {"id": "q2", "top_cars": ["Hyundai Creta", "Tata  Nexon", "Kia Seltos"]}]
    out = E.shortlist_agreement(recs, sheet)
    assert out["filled"] == 1 and out["recall_at_8"] == 1.0 and out["mrr"] == pytest.approx(0.5)
    sheet.write_text("id,query,car_1,car_2,car_3,car_4,car_5,notes\nq1,x,,,,,,\n")
    assert E.shortlist_agreement(recs, sheet) == {"filled": 0, "note": "no shortlists filled in yet"}


@pytest.mark.parametrize("engine", ["current", "v3"])
def test_engine_seam_accepts_a_modified_catalogue(engine):
    """The unknown probe's seam: the same blanking works on both engines (a blanked sunroof is no longer 'present')."""
    cat = E.get_catalogue()
    q = "SUV with sunroof under 20 lakh"
    before = E.make_engine(engine)(q)["recommendations"]
    top = before[0]
    frame = cat.copy()
    frame.loc[(frame["make"] == top["Make"]) & (frame["model"] == top["Model"]), "sunroof"] = None
    after = E.make_engine(engine, frame)(q)["recommendations"]
    assert after  # still answers on the modified frame
    if engine == "v3":
        hit = [c for c in after if c["Model"] == top["Model"]]
        assert not hit or any("sunroof" in u.lower() for u in hit[0]["unverified"] + [x if isinstance(x, str) else str(x) for x in hit[0]["unknowns"]])
    from services.catalogue import get_catalogue
    assert get_catalogue()["sunroof"].notna().sum() == cat["sunroof"].notna().sum()  # the real catalogue untouched


def test_label_truthfulness_body_derived_from_reference_model():
    cat = E.get_catalogue()
    ref = cat[cat["body_type"] == "suv"].iloc[0]["model"]
    mpv = cat[(cat["body_type"] == "mpv") & cat["price_ex_showroom"].notna()].iloc[0]
    car = {"variant_id": int(mpv["variant_id"]), "Model": mpv["model"], "Variant": mpv["variant"],
           "violations": [{"constraint": "body_type"}]}
    expect = {"reference_models": [ref]}   # the user stated no body type
    assert E.label_truthfulness([car], expect)["truthful"]            # naming it is true: an MPV is not the SUV's body
    same = cat[(cat["body_type"] == "suv") & cat["price_ex_showroom"].notna()].iloc[1]
    liar = {"variant_id": int(same["variant_id"]), "Model": same["model"], "Variant": same["variant"],
            "violations": [{"constraint": "body_type"}]}
    assert not E.label_truthfulness([liar], expect)["truthful"]       # naming it for a same-body car is still wrong
