"""GET /api/car/<make_slug>/<model_slug>: slugs, variant selection, matches_query, spec grouping."""

import contextlib
import io
import re
from pathlib import Path
from urllib.parse import quote

import pytest

from services.car_detail import SPEC_GROUPS, get_car_detail
from services.catalogue import get_catalogue
from services.filter_v2 import filter_candidates
from services.intent_v2 import parse_intent
from services.new_car_service import apply_drops, safe_slug

GROUPS = ["Engine & performance", "Dimensions & capacity", "Comfort & convenience", "Technology", "Safety", "Warranty"]
MODELS = get_catalogue()[["make", "model"]].drop_duplicates().values.tolist()


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def get(client, path):
    with contextlib.redirect_stdout(io.StringIO()):
        return client.get(path)


def predict(client, query, drop=None):
    body = {"query": query} if drop is None else {"query": query, "drop": drop}
    with contextlib.redirect_stdout(io.StringIO()):
        return client.post("/predict", json=body).get_json()


def test_every_model_resolves_by_slug():
    cat = get_catalogue()
    n_models = 62 if len(cat) == 832 else int(cat[["make", "model"]].drop_duplicates().shape[0])   # original, or the default
    assert len(MODELS) == n_models
    slugs = {(safe_slug(mk), safe_slug(md)) for mk, md in MODELS}
    assert len(slugs) == n_models
    for make, model in MODELS:
        detail = get_car_detail(safe_slug(make), safe_slug(model))
        assert (detail["make"], detail["model"]) == (make, model)
        assert len(detail["variants"]) == int(((get_catalogue()["model"] == model)).sum())


def test_unknown_slug_is_404_json(client):
    r = get(client, "/api/car/bmw/x5")
    assert r.status_code == 404 and "error" in r.get_json()
    assert get(client, "/api/car/tata/not-a-car").status_code == 404


def test_slugs_are_case_insensitive(client):
    assert get(client, "/api/car/Maruti-Suzuki/Grand-Vitara").status_code == 200


def test_without_query_cheapest_variant_is_selected(client):
    d = get(client, "/api/car/hyundai/exter").get_json()
    cheapest = min(d["variants"], key=lambda v: (v["price"], v["variant_id"]))
    assert d["selected_variant_id"] == cheapest["variant_id"]
    assert d["query"] is None and not any(v["matches_query"] for v in d["variants"])


def test_variant_id_wins_and_bad_ids_fall_back(client):
    d = get(client, "/api/car/hyundai/exter").get_json()
    other = d["variants"][-1]["variant_id"]
    assert get(client, f"/api/car/hyundai/exter?variant_id={other}").get_json()["selected_variant_id"] == other
    # a variant of another model is ignored
    nexon_id = get(client, "/api/car/tata/nexon").get_json()["variants"][0]["variant_id"]
    assert get(client, f"/api/car/hyundai/exter?variant_id={nexon_id}").get_json()["selected_variant_id"] == d["selected_variant_id"]


@pytest.mark.parametrize("query,drop", [
    ("sunroof wali SUV 12 lakh ke andar", None),
    ("CNG gaadi under 8 lakh", None),
    ("DCT petrol under 15 lakh", None),
    ("7 seater under 15 lakh", None),
    ("CVT automatic hatchback", ["body_type"]),
])
def test_default_variant_is_the_card_variant_and_matches_follow_filter_v2(client, query, drop):
    data = predict(client, query, drop)
    intent, _ = apply_drops(parse_intent(query), drop)
    passing = filter_candidates(intent, get_catalogue())
    assert data["recommendations"]
    for car in data["recommendations"]:
        path = f"/api/car/{safe_slug(car['Make'])}/{safe_slug(car['Model'])}?q={quote(query)}"
        if drop:
            path += "&drop=" + ",".join(drop)
        d = get(client, path).get_json()
        selected = next(v for v in d["variants"] if v["variant_id"] == d["selected_variant_id"])
        assert selected["variant"] == car["Variant"]
        want = set(passing.loc[passing["model"] == car["Model"], "variant_id"].astype(int))
        assert {v["variant_id"] for v in d["variants"] if v["matches_query"]} == want
        assert d["query"]["matching_variant_count"] == len(want) == car["matching_variant_count"]


def test_spec_groups_and_statuses(client):
    d = get(client, "/api/car/skoda/slavia").get_json()
    assert [g["group"] for g in d["specs"]] == GROUPS
    for group in d["specs"]:
        for item in group["items"]:
            assert item["status"] in {"ok", "unverified", "not_applicable"}
            assert (item["value_display"] is not None) == (item["status"] == "ok")
    assert [g for g, _ in SPEC_GROUPS] == GROUPS


def test_not_applicable_on_an_ev(client):
    d = get(client, "/api/car/tata/punch-ev").get_json()
    engine = {i["label"]: i for i in d["specs"][0]["items"]}
    assert engine["Engine"]["status"] == "not_applicable"
    assert engine["Fuel tank"]["status"] == "not_applicable"
    assert engine["Range (claimed)"]["status"] == "ok" and engine["Range (claimed)"]["value_display"].endswith(" km")
    assert all(v["mileage_display"]["label"] == "Range" for v in d["variants"])


def test_kmpl_not_applicable_on_cng():
    df = get_catalogue()
    cng = df[df["fuel_type"] == "cng"]
    assert not cng.empty and not any("mileage_kmpl" in f for f in cng["unverified_fields"])
    row = cng.iloc[0]
    d = get_car_detail(safe_slug(row["make"]), safe_slug(row["model"]), variant_id=int(row["variant_id"]))
    engine = {i["label"]: i for i in d["specs"][0]["items"]}
    assert engine["Mileage (ARAI)"] == {"label": "Mileage (ARAI)", "value_display": None, "status": "not_applicable",
                                        "note": "Not applicable: CNG is rated in km/kg"}
    known = cng[cng["mileage_km_per_kg"].notna()].iloc[0]
    d = get_car_detail(safe_slug(known["make"]), safe_slug(known["model"]), variant_id=int(known["variant_id"]))
    engine = {i["label"]: i for i in d["specs"][0]["items"]}
    assert engine["CNG mileage (ARAI)"]["value_display"].endswith(" km/kg")


def test_unverified_status_follows_unverified_fields():
    df = get_catalogue()
    row = df[df["unverified_fields"].map(lambda f: "heads_up_display" in f)].iloc[0]
    d = get_car_detail(safe_slug(row["make"]), safe_slug(row["model"]), variant_id=int(row["variant_id"]))
    tech = {i["label"]: i for i in d["specs"][3]["items"]}
    assert tech["Heads-up display"] == {"label": "Heads-up display", "value_display": None, "status": "unverified"}
    selected = next(v for v in d["variants"] if v["variant_id"] == int(row["variant_id"]))
    assert "Heads-up display" in selected["unverified"]


def test_cng_mileage_uses_km_per_kg_and_never_kmpl(client):
    d = get(client, "/api/car/maruti-suzuki/ertiga").get_json()
    for v in d["variants"]:
        if v["fuel_type"] == "cng":
            assert v["mileage_kmpl"] is None  # the KB's kmpl cell on CNG rows is not a kmpl figure
            shown = v["mileage_display"]["value"]
            assert shown is None or shown.endswith("km/kg (CNG)")


def test_permalink_page_route(client):
    r = get(client, "/car/skoda/slavia?q=DCT%20petrol%20under%2015%20lakh")
    assert r.status_code == 200 and b'id="car-detail"' in r.data and b"initCarPage" in r.data
    assert get(client, "/car/bmw/x5").status_code == 404


def test_warranty_row_shows_only_brochure_cited_figures():
    df = get_catalogue()
    def item(model, label, fuel=None):
        rows = df[(df["model"] == model) & (df["fuel_type"] == fuel if fuel else True)]
        row = rows.iloc[0]
        d = get_car_detail(safe_slug(row["make"]), safe_slug(row["model"]), variant_id=int(row["variant_id"]))
        return next(i for i in d["specs"][5]["items"] if i["label"] == label)
    assert item("Grand Vitara", "Standard warranty")["value_display"] == "3 years / 100,000 km"
    assert item("Elevate", "Standard warranty")["value_display"] == "3 years / unlimited km"
    assert item("Slavia", "Standard warranty")["value_display"] == "4 years / 100,000 km"
    # the make-wide Hyundai row is contradicted by two brochures, so only model rows with a citation show
    assert item("Grand i10 Nios", "Standard warranty")["value_display"] == "3 years / 100,000 km"
    assert item("Exter", "Standard warranty")["value_display"] == "3 years / unlimited km"
    assert item("Creta", "Standard warranty") == {"label": "Standard warranty", "value_display": None, "status": "unverified"}
    assert item("Nexon EV", "Battery warranty")["value_display"] == "8 years / 160,000 km"
    assert item("Nexon EV", "Standard warranty")["value_display"] == "3 years / 125,000 km"
    assert item("Creta", "Battery warranty")["status"] == "not_applicable"


def test_unknown_car_page_is_a_real_404_with_its_own_copy_and_title(client):
    r = get(client, "/car/tata/nonexistent")
    assert r.status_code == 404
    body = r.data.decode()
    assert "<title>Car not found | CarRec</title>" in body
    assert "We don&#39;t have that car" in body or "We don't have that car" in body
    assert "Search cars" in body and "Something went wrong" not in body


def test_car_page_title_is_rendered_by_the_server_and_has_no_live_region(client):
    body = get(client, "/car/skoda/slavia").data.decode()
    assert "<title>Skoda Slavia | CarRec</title>" in body
    assert "aria-live" not in body


def test_results_page_has_one_status_line_and_no_live_thread(client):
    body = get(client, "/recommend").data.decode()
    assert 'id="results"' in body and 'role="status"' in body and 'id="search-status"' in body
    assert "aria-live" not in body
    assert re.search(r'data-variant-count="\d+"', body)


def test_detail_sections_are_h2_on_the_car_page_and_h3_in_the_inline_panel():
    script = """
const vm = require('vm'), fs = require('fs');
const ctx = vm.createContext({ console, URL, URLSearchParams, location: { origin: 'http://x', pathname: '/car/a/b', search: '' } });
vm.runInContext(fs.readFileSync(process.argv.at(-1), 'utf8'), ctx);
const data = { make: 'A', model: 'B', image: '/x.png', summary: 's', variants: [{variant_id: 1, variant: 'V', price: 1, matches_query: false, transmission_label: 'MT', fuel_label: 'Petrol', mileage_display: {value: '1 kmpl'}}],
  selected_variant_id: 1, specs: [{group: 'Safety', items: []}, {group: 'Technology', items: [{label: 'x', value_display: 'y', status: 'ok'}]}], safety: null, price_range: null, cardekho_link: 'https://x.test', data_as_of: null };
ctx.d = data;
process.stdout.write(JSON.stringify([vm.runInContext('renderDetail(d, {standalone: true, q: ""})', ctx), vm.runInContext('renderDetail(d, {q: ""})', ctx)]));
"""
    import json, shutil, subprocess
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    out = subprocess.run(["node", "-e", script, str(ROOT / "static" / "script.js")], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    page, panel = json.loads(out.stdout)
    assert "<h2>Summary</h2>" in page and "<h3>Technology</h3>" in page and "<h3>Summary</h3>" not in page
    assert "<h3>Summary</h3>" in panel and "<h2>" not in panel
