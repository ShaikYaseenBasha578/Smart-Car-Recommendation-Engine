"""The v3 results page: static/script.js renders the v3 /predict payload (engine "v3") into cards.

The page is drawn in the browser, so these tests run the real script.js in Node (vm, no DOM library) and check the
HTML string it produces. Skipped when node is not installed. With engine unset the old card builder must be used.
"""

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = """
const vm = require('vm'), fs = require('fs');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const ctx = vm.createContext({ console, URL, location: { origin: 'http://x', pathname: '/recommend', search: '' } });
vm.runInContext(fs.readFileSync(process.argv.at(-1), 'utf8'), ctx);
const box = { innerHTML: '' };
vm.runInContext('renderResults(box, data, true, "http://x/recommend?q=q")', Object.assign(ctx, { box, data: payload }));
process.stdout.write(box.innerHTML);
"""

SCRIPT_NOTE = "<script>alert(1)</script> & <b>bold</b>"


def expert(**kw):
    base = {"evidence_class": "expert", "source": "Autocar India", "source_aspect": "Ride Comfort And Handling",
            "score": 9.0, "scale_max": 10.0, "published_on": "2025-08-12", "note": "Soaks up rough roads.",
            "quote": {"text": "plush at low speed", "kind": "quotation", "source": "Autocar India",
                      "source_url": "https://www.autocarindia.com/cars/x/y/expert-reviews"},
            "source_url": "https://www.autocarindia.com/cars/x/y/expert-reviews", "fields": ["expert_ride_comfort"],
            "text": "unused"}
    return {**base, **kw}


def owner(**kw):
    base = {"evidence_class": "owner", "theme": "satisfaction", "label": None, "direction": "positive", "mentions": 11,
            "posts_sampled": 60, "share": 0.1833, "note": "Owners are happy.", "source": "CarWale",
            "source_url": "https://www.carwale.com/x/y/user-reviews/", "text": "unused"}
    return {**base, **kw}


def car(**kw):
    base = {
        "Make": "Tata", "Model": "Nexon", "Variant": "Smart", "Ex-Showroom_Price": 800000.0, "Transmission": "Manual",
        "Fuel_Type": "Petrol", "carImage": "/static/pic.avif", "carDekhoLink": "https://www.cardekho.com/tata/nexon",
        "ranking_score": 80.0, "matched_features": [], "unverified": [], "safety": None,
        "matching_variant_count": 2, "ev_range_km": None, "mileage_km_per_kg": None, "ARAI_Certified_Mileage": 19.0,
        "scores": {"overall": 0.8, "spec": 0.81, "expert": 0.74, "owner": 0.9, "coverage": 0.9},
        "reasons": [{"text": "Priced at 8 lakh, 80% of your 10 lakh budget", "evidence_class": "spec"}],
        "expert_notes": [expert()], "owner_notes": [owner()], "caveats": [], "violations": [], "not_verified": [],
        "also_available_from": None, "match_label": "Strong match",
    }
    return {**base, **kw}


def response(cars, **kw):
    base = {"engine": "v3", "recommendations": cars, "intent": {"budget": {"min": None, "max": 1000000},
            "body_types": ["suv"], "transmission": {"family": None}}, "data_as_of": {"exported": "2026-11-14", "kb_phase": "11Q"}}
    return {**base, **kw}


def render(payload):
    out = subprocess.run(["node", "-e", HARNESS, str(ROOT / "static" / "script.js")], input=json.dumps(payload),
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    return out.stdout


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


def links(html):
    p = Links()
    p.feed(html)
    return p.links


def test_expert_line_has_meta_note_and_quote_link():
    html = render(response([car()]))
    assert "What reviewers say" in html
    assert "Autocar India" in html and "Ride comfort and handling" in html and "9/10" in html and "Aug 2025" in html
    assert "Soaks up rough roads." in html
    assert "<blockquote" in html and "“plush at low speed”" in html
    review = [a for a in links(html) if "expert-reviews" in a.get("href", "")]
    assert len(review) == 1
    assert review[0]["target"] == "_blank" and review[0]["rel"] == "noopener noreferrer"
    assert "Read the review" in html


def test_at_most_two_expert_and_owner_lines():
    cars = [car(expert_notes=[expert(note=f"expert {i}") for i in range(4)],
                owner_notes=[owner(note=f"owner {i}") for i in range(4)])]
    html = render(response(cars))
    assert html.count("expert 0") == 1 and html.count("expert 1") == 1 and "expert 2" not in html
    assert "owner 1" in html and "owner 2" not in html


def test_owner_line_shows_verified_count_and_few_owners_label_under_15_percent():
    html = render(response([car(owner_notes=[owner(mentions=11, posts_sampled=60, share=0.1833),
                                             owner(theme="service_cost", mentions=6, posts_sampled=60, share=0.1, note="Cheap to service.")])]))
    assert "11 of 60 reviews, CarWale" in html and "6 of 60 reviews, CarWale" in html
    assert html.count("a few owners") == 1                      # only the 10% line
    assert "Owners are happy." in html and "Cheap to service." in html   # notes untouched, nothing hidden


def test_caveats_block_is_always_rendered_when_present_and_absent_otherwise():
    caveat = owner(theme="recurring_fault", label="music system faults", direction="negative", mentions=3,
                   posts_sampled=60, share=0.05, note="Infotainment hangs.", kind="reported_fault")
    html = render(response([car(caveats=[caveat])]))
    assert 'class="caveats"' in html and "Reported fault: music system faults" in html and "Infotainment hangs." in html
    assert "<details" not in html
    assert 'class="caveats"' not in render(response([car()]))


def test_no_data_states_for_reviews_and_meters():
    html = render(response([car(expert_notes=[], owner_notes=[], scores={"overall": 0.5, "spec": 0.5, "expert": None, "owner": None, "coverage": 0.5})]))
    assert "No expert review on file for this model." in html
    assert "No owner ratings available for this model." in html
    assert html.count("no data") >= 2
    assert 'aria-label="Expert: 0 out of 100"' not in html and 'aria-label="Owners: 0 out of 100"' not in html


def test_meters_show_numbers_and_captions():
    html = render(response([car()]))
    for needle in ("Specs", "Expert", "Owners", "Autocar India", "CarWale", ">81<", ">74<", ">90<"):
        assert needle in html


def test_review_text_is_escaped():
    evil = car(expert_notes=[expert(note=SCRIPT_NOTE, quote={"text": SCRIPT_NOTE, "kind": "quotation", "source": "x", "source_url": "https://a.example/r"})],
               owner_notes=[owner(note=SCRIPT_NOTE)], reasons=[{"text": SCRIPT_NOTE, "evidence_class": "spec"}],
               caveats=[owner(theme="build_issues", direction="negative", note=SCRIPT_NOTE, kind="negative_theme")],
               Variant=SCRIPT_NOTE)
    html = render(response([evil]))
    assert "<script>" not in html and "<b>bold</b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &lt;b&gt;bold&lt;/b&gt;" in html


def test_only_http_links_are_drawn():
    bad = expert(quote={"text": "q", "kind": "quotation", "source": "x", "source_url": "javascript:alert(1)"}, source_url="javascript:alert(1)")
    html = render(response([car(expert_notes=[bad])]))
    assert "javascript:" not in html and "Read the review" not in html


def test_match_wording_comes_from_data_not_great_match():
    html = render(response([car()]))
    assert "Meets all your requirements" in html and "Great match" not in html and "Good match" not in html
    relaxed = car(violations=[{"constraint": "budget", "text": "₹40,000 over budget", "amount": 40000, "unit": "INR"}])
    html = render(response([relaxed], relaxation={"message": "No cars match all your requirements.", "keys": ["budget"]}))
    assert "Meets 1 of 2 requirements" in html and "Not met: ₹40,000 over budget" in html
    assert "No cars match all your requirements." in html


def test_not_verified_tags_and_also_available_from():
    html = render(response([car(not_verified=["ground clearance not verified"],
                                also_available_from={"variant_id": 3, "variant": "Smart Lite", "Ex-Showroom_Price": 700000.0})]))
    assert "Ground clearance not verified" in html and "tag--unverified" in html
    assert "Also available from" in html and "Smart Lite" in html and "₹7 lakh" in html


def test_query_echo_marks_assumed_and_corrected_values():
    payload = response([car()], corrections=[{"from": "automatik", "to": "automatic"}], assumed={"body_types": ["suv"]},
                       assumed_options=[{"key": "assumed:body_types", "kind": "body_types", "values": ["suv"]}])
    html = render(payload)
    assert "What we understood" in html and "Under ₹10L" in html
    assert "automatik → automatic" in html and ">corrected<" in html and ">assumed<" in html
    assert 'data-drop-key="assumed:body_types"' in html


def test_sources_footer_names_both_sources():
    html = render(response([car()]))
    assert "Autocar India" in html.split('class="sources"')[1] and "CarWale user reviews" in html.split('class="sources"')[1]
    assert "Aug 2025" in html.split('class="sources"')[1] and "short summaries" in html


def test_old_engine_payload_uses_the_old_card_builder():
    html = render({"recommendations": [{"Make": "Tata", "Model": "Nexon", "Variant": "Smart", "Ex-Showroom_Price": 800000.0,
                                        "ranking_score": 80.0, "Fuel_Type": "Petrol", "Transmission": "Manual"}]})
    assert "Great match" in html and "car--v3" not in html and "What reviewers say" not in html and "sources" not in html
