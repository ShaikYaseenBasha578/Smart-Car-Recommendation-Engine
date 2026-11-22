"""PR G: front-end bugs and correctness (search box fit, card variant links, reasons, violation wording, unknown word,
mileage precision, Compare name, skip links). The script runs in Node (vm, no DOM library); skipped when node is missing."""

import contextlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from services.car_detail import mileage_display, spec_item
from services.catalogue import get_catalogue

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "script.js").read_text()
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = """
const vm = require('vm'), fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const ctx = vm.createContext({ console, URL, URLSearchParams, location: { origin: 'http://x', pathname: '/recommend', search: '' } });
vm.runInContext(fs.readFileSync(process.argv.at(-1), 'utf8'), ctx);
ctx.input = input;
process.stdout.write(JSON.stringify(vm.runInContext(input.expr, ctx)));
"""


def js(expr, **data):
    out = subprocess.run(["node", "-e", HARNESS, str(ROOT / "static" / "script.js")], input=json.dumps({"expr": expr, **data}),
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def card(**kw):
    base = {"Make": "Tata", "Model": "Nexon", "Variant": "Smart", "Ex-Showroom_Price": 800000.0, "Fuel_Type": "Petrol",
            "Transmission": "Manual", "ranking_score": 80.0, "variant_id": 71, "reasons": [], "expert_notes": [], "owner_notes": [],
            "caveats": [], "violations": [], "not_verified": [], "scores": {}, "ARAI_Certified_Mileage": 19.0}
    return {**base, **kw}


def render_card(c, intent=None):
    return js("buildV3Card(input.car, 0, 1, true, input.intent)", car=c, intent=intent)


BUDGET = {"budget": {"min": None, "max": 1000000}}
SPEC = "spec"


def reason(text, fields=None):
    return {"text": text, "evidence_class": SPEC, "fields": fields or ["x"]}


# ------------------------------------------------------------------ #1 search box fit
def test_every_assignment_to_a_search_box_value_is_followed_by_a_fit():
    lines = JS.splitlines()
    sets = [i for i, l in enumerate(lines) if re.search(r'(getElementById\("userQuery"\)|\binput)\.value = ', l)]
    assert len(sets) >= 5          # first load, popstate, new search, suggestion pick (+ its follow-up reset)
    for i in sets:
        assert "fitSearchBox(" in " ".join(lines[i:i + 3]), lines[i]


# ------------------------------------------------------------------ #4 card variant in the links
@needs_node
def test_v3_card_carries_its_variant_id_and_the_title_link_uses_it():
    assert 'data-variant-id="71"' in render_card(card())
    assert "data-variant-id" not in render_card(card(variant_id=None))
    href = js("""(() => { const a = {}; const el = { dataset: { makeSlug: 'tata', modelSlug: 'nexon', variantId: '71' }, querySelector: () => a };
        linkCarTitles({ querySelectorAll: () => [el] }, 'suv under 10 lakh', []); return a.href; })()""")
    assert href.startswith("/car/tata/nexon?") and "variant_id=71" in href and "q=suv+under+10+lakh" in href


@needs_node
def test_panel_full_details_link_uses_the_variant_the_panel_shows():
    data = {"make": "Tata", "model": "Nexon", "summary": "s", "variants": [], "selected_variant_id": 71, "specs": [],
            "data_as_of": None}
    html = js("renderDetail(input.data, { make: 'tata', model: 'nexon', q: 'suv', drop: [], variantId: 71 })", data=data)
    assert 'class="btn btn-primary detail-full" href="/car/tata/nexon?q=suv&amp;variant_id=71"' in html
    # the panel asks the API for the card's own variant
    assert "variantId: Number(card.dataset.variantId) || null" in JS.split("function toggleDetail")[1].split("\n}\n")[0]


def test_api_honours_variant_id_with_a_query_for_a_non_cheapest_variant():
    from app import app
    app.config["TESTING"] = True
    client = app.test_client()
    cat = get_catalogue()
    rows = cat[(cat["make"] == "Tata") & (cat["model"] == "Nexon")].sort_values(["price_ex_showroom", "variant_id"])
    pick = int(rows["variant_id"].iloc[-1])
    assert pick != int(rows["variant_id"].iloc[0])
    with contextlib.redirect_stdout(io.StringIO()):
        data = client.get(f"/api/car/tata/nexon?variant_id={pick}&q=suv+under+20+lakh").get_json()
    assert data["selected_variant_id"] == pick


# ------------------------------------------------------------------ #5 reasons
@needs_node
def test_reviews_toggle_no_longer_covers_reasons():
    html = render_card(card(reasons=[reason(f"r{i}") for i in range(4)], expert_notes=[]), BUDGET)
    reasons = html.split('aria-label="Why this car"')[1].split("</section>")[0]
    assert "data-more hidden" not in reasons and reasons.count("data-more-reason hidden") == 2
    assert "data-reviews-toggle" not in html                      # only reasons: nothing sits behind the reviews toggle
    assert "data-more hidden" not in html
    assert "toggleReviews" in JS and 'querySelectorAll("[data-more]")' in JS.split("function toggleReviews")[1].split("\n}\n")[0]


@needs_node
def test_more_reasons_button_only_above_two_reasons_with_the_right_count():
    for n, extra in ((1, 0), (2, 0), (3, 1), (4, 2)):
        html = render_card(card(reasons=[reason(f"r{i}") for i in range(n)]), BUDGET)
        if not extra:
            assert "data-reasons-toggle" not in html
            continue
        assert f'data-more-count="{extra}"' in html and f">+{extra} more reason{'s' if extra > 1 else ''}</button>" in html
        btn = html.split("data-reasons-toggle")[1].split(">")[0]
        ident = re.search(r'aria-controls="([^"]+)"', btn).group(1)
        assert 'aria-expanded="false"' in btn and f'<ul class="reasons reasons--v3" id="{ident}">' in html


def shown_reasons(html):
    ul = html.split('class="reasons reasons--v3"')[1].split("</ul>")[0]
    items = [li.split("</li>")[0] for li in ul.split("<li")[1:]]
    return [re.sub(r"<[^>]+>", "", li.split(">", 1)[1]) for li in items if "hidden" not in li.split(">", 1)[0]]


def test_budget_reason_is_identified_by_its_fields():
    budget = {"text": "Priced at 8 lakh, 80% of your 10 lakh budget", "evidence_class": "spec", "fields": ["price_ex_showroom"]}
    assert js("isBudgetReason(input.r)", r=budget) is True
    price = {"text": "8 lakh, cheaper than", "evidence_class": "spec", "fields": ["price_ex_showroom", "body_type"]}
    assert js("isBudgetReason(input.r)", r=price) is False


@needs_node
def test_budget_reason_moves_into_the_shown_two_when_the_search_has_a_budget():
    budget = {"text": "Priced at 8 lakh, 80% of your 10 lakh budget", "evidence_class": "spec", "fields": ["price_ex_showroom"]}
    reasons = [reason("a"), reason("b"), budget, reason("d")]
    assert shown_reasons(render_card(card(reasons=reasons), BUDGET)) == ["a", budget["text"]]
    # already shown: order untouched
    kept = [budget, reason("b"), reason("c")]
    assert shown_reasons(render_card(card(reasons=kept), BUDGET)) == [budget["text"], "b"]
    # no budget in the search: order is unchanged
    assert shown_reasons(render_card(card(reasons=reasons), {"budget": {"min": None, "max": None}})) == ["a", "b"]
    assert shown_reasons(render_card(card(reasons=reasons), None)) == ["a", "b"]


# ------------------------------------------------------------------ #12 violation wording
VIOLATIONS = [
    ("suv, not sedan", "SUV, not a sedan"),
    ("sedan, not suv", "Sedan, not an SUV"),
    ("hatchback, not mpv", "Hatchback, not an MPV"),
    ("suv, not hatchback/sedan", "SUV, not hatchback or sedan"),
    ("manual, not automatic", "Manual, not automatic"),
    ("automatic, not manual", "Automatic, not manual"),
    ("diesel, not petrol/cng", "Diesel, not petrol or CNG"),
    ("petrol, not diesel", "Petrol, not diesel"),
    ("cng, not electric/hybrid", "CNG, not electric or hybrid"),
    ("compact_suv, not sedan", "Compact suv, not a sedan"),
    ("Mahindra, not Tata", "Mahindra, not Tata"),
    ("Mahindra, not Tata/Kia", "Mahindra, not Tata/Kia"),
    ("Nexon, not the model you named", "Nexon, not the model you named"),
    ("priced above your budget", "priced above your budget"),
    ("", ""),
]


@needs_node
@pytest.mark.parametrize("raw,shown", VIOLATIONS)
def test_human_violation(raw, shown):
    assert js("humanViolation(input.t)", t=raw) == shown


@needs_node
def test_every_catalogue_value_has_a_display_word_and_the_pill_uses_it():
    cat = get_catalogue()
    for col in ("body_type", "fuel_type", "transmission_family"):
        for v in cat[col].dropna().unique():
            assert js("Object.prototype.hasOwnProperty.call(TERM_WORDS, input.v)", v=v) is True, (col, v)
    label = js("v3MatchLabel(input.car, 2, true)", car=card(violations=[{"text": "suv, not sedan"}, {"text": "diesel, not petrol/cng"}]))
    assert label["detail"] == ["Not met: SUV, not a sedan", "Not met: Diesel, not petrol or CNG"]


# ------------------------------------------------------------------ #11 one word for unknown, one mileage precision
@needs_node
def test_card_says_not_verified_for_unknown_facts_including_cng():
    html = render_card(card(Transmission=None, Fuel_Type=None, ARAI_Certified_Mileage=None))
    assert html.count("Not verified") >= 3 and "Not listed" not in html and "not listed" not in html
    cng = render_card(card(Fuel_Type="CNG", mileage_km_per_kg=None))
    assert "Not verified" in cng and "not listed" not in cng


def test_variant_mileage_on_the_car_page_says_not_verified():
    assert js("variantMileage(input.v)", v={"mileage_display": {"value": None, "unit": "km/kg"}}) == "Not verified"
    assert js("variantMileage(input.v)", v={"mileage_display": {"value": None, "unit": "kmpl"}}) == "Not verified"


@pytest.mark.parametrize("fuel,col,value,expect", [
    ("petrol", "mileage_kmpl", 24.08, "24.1 kmpl"), ("petrol", "mileage_kmpl", 26.0, "26 kmpl"),
    ("diesel", "mileage_kmpl", 19.04, "19 kmpl"), ("cng", "mileage_km_per_kg", 26.6, "26.6 km/kg (CNG)"),
    ("cng", "mileage_km_per_kg", 33.54, "33.5 km/kg (CNG)"), ("electric", "ev_range_km", 465.4, "465 km")])
def test_mileage_display_is_one_decimal_and_ev_range_whole(fuel, col, value, expect):
    row = {"fuel_type": fuel, "mileage_kmpl": None, "mileage_km_per_kg": None, "ev_range_km": None, col: value}
    assert mileage_display(row)["value"] == expect


def test_spec_list_mileage_rounds_to_one_decimal_but_the_api_keeps_the_raw_number():
    row = {"fuel_type": "petrol", "mileage_kmpl": 24.08, "unverified_fields": set()}
    assert spec_item(row, "mileage_kmpl", "Mileage (ARAI)", " kmpl")["value_display"] == "24.1 kmpl"
    row = {"fuel_type": "cng", "mileage_km_per_kg": 26.6, "unverified_fields": set()}
    assert spec_item(row, "mileage_km_per_kg", "CNG mileage (ARAI)", " km/kg")["value_display"] == "26.6 km/kg"


# ------------------------------------------------------------------ #20 Compare button name
@needs_node
def test_compare_button_has_one_accessible_name():
    html = render_card(card())
    btn = html.split('class="btn btn-quiet btn-compare"')[1].split("</button>")[0]
    assert 'aria-label="Compare Tata Nexon Smart"' in btn and 'aria-pressed="false"' in btn
    assert "sr-only" not in btn and '<span class="compare-text">Compare</span>' in btn


# ------------------------------------------------------------------ #18 skip links
@pytest.mark.parametrize("path,text,target", [
    ("/recommend", "Skip to results", "results"), ("/car/tata/nexon", "Skip to details", "car-detail"),
    ("/compare?ids=1,2", "Skip to the comparison", "comparison"), ("/compare", "Skip to the comparison", "comparison")])
def test_first_link_is_the_skip_link_and_its_target_exists(path, text, target):
    from app import app
    app.config["TESTING"] = True
    with contextlib.redirect_stdout(io.StringIO()):
        body = app.test_client().get(path).data.decode()
    after = body.split("<body>")[1]
    first = re.search(r"<a\b[^>]*>", after).group(0)
    assert 'class="skip-link"' in first and f'href="#{target}"' in first
    assert f">{text}</a>" in after
    assert re.search(rf'id="{target}"[^>]*tabindex="-1"|id="{target}"[^>]*role="region"[^>]*tabindex="0"', body)


def test_homepage_has_no_skip_link():
    from app import app
    with contextlib.redirect_stdout(io.StringIO()):
        assert "skip-link" not in app.test_client().get("/").data.decode()
