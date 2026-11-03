"""Probe app behaviour for the NULL-power variants (run from the app worktree)."""
import contextlib, io, json, math
from app import app
from services.catalogue import get_catalogue

c = app.test_client()
def get(p):
    with contextlib.redirect_stdout(io.StringIO()): return c.get(p)
def post(q):
    with contextlib.redirect_stdout(io.StringIO()): return c.post("/predict", json={"query": q}).get_json()
df = get_catalogue()
print("catalogue power NaN rows:", sorted(df.loc[df["power_bhp"].isna(), "variant_id"].astype(int)))
for path, vid in (("/api/car/maruti-suzuki/grand-vitara", 548), ("/api/car/maruti-suzuki/victoris", 567)):
    r = get(f"{path}?variant_id={vid}"); d = r.get_json()
    eng = {i["label"]: i for i in d["specs"][0]["items"]}
    sel = next(v for v in d["variants"] if v["variant_id"] == vid)
    print(path, vid, r.status_code, "Power item:", eng["Power"], "| unverified:", sel["unverified"], "| summary:", d.get("summary", "")[:200])
    assert eng["Power"]["status"] == "unverified" and eng["Power"]["value_display"] is None
print("page routes:", get("/car/maruti-suzuki/grand-vitara").status_code, get("/car/maruti-suzuki/victoris").status_code)
for q in ("Grand Vitara CNG", "Victoris strong hybrid", "CNG SUV under 15 lakh", "hybrid SUV under 20 lakh",
          "powerful SUV under 20 lakh", "SUV with at least 100 bhp under 20 lakh", "performance car under 25 lakh"):
    d = post(q); recs = d.get("recommendations", [])
    hits = [(x["Model"], x["Variant"], x.get("Power")) for x in recs if x["Model"] in ("Grand Vitara", "Victoris")]
    zeros = [x for x in recs if x.get("Power") == 0]
    txt = json.dumps(d)
    print(f"{q!r}: {len(recs)} recs; GV/Victoris: {hits}; Power==0: {len(zeros)}; NaN in JSON: {'NaN' in txt}")
    assert not zeros and "NaN" not in txt
