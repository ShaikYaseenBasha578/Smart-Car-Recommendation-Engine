"""The v3 results page: static/script.js renders the v3 /predict payload (engine "v3") into cards.

The page is drawn in the browser, so these tests run the real script.js in Node (vm, no DOM library) and check the
HTML string it produces. Skipped when node is not installed. With engine unset the old card builder must be used.
"""

import json
import re
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


def test_no_data_states_for_reviews_and_owners():
    # something sits behind the toggle (a caveat), so the panel exists and names what is missing
    caveat = owner(theme="recurring_fault", label="clutch judder", direction="negative", mentions=3, posts_sampled=60,
                   share=0.05, note="Judder.", kind="reported_fault")
    html = render(response([car(expert_notes=[], owner_notes=[], caveats=[caveat],
                                scores={"overall": 0.5, "spec": 0.5, "expert": None, "owner": None, "coverage": 0.5})]))
    assert "No expert review on file for this model." in html
    assert "No owner ratings available for this model." in html


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
    # personalised card: named once, as a pill under the match label, not repeated as a chip
    assert "Not verified: ground clearance" in html and "Ground clearance not verified" not in html
    assert "Also available from" in html and "Smart Lite" in html and "₹7 lakh" in html


def test_not_verified_chip_only_on_general_picks():
    html = render(response([car(not_verified=["ground clearance not verified"])], personalised=False))
    assert "Ground clearance not verified" in html and "tag--unverified" in html


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


# ------------------------------------------------------------------ second pass: ratings line, collapsed reviews

def standing(**kw):
    base = {"value": 75, "band": "top", "segment": "suv", "n_models": 40, "rating": 4.6, "scale_max": 5.0,
            "rating_count": 1068, "after_sales": 4.4, "source": "CarWale",
            "caption": "4.6/5 from 1068 ratings · above average among SUVs",
            "summary": "Owners rate it 4.6/5 overall, after-sales cost 4.4/5 (CarWale, 1068 ratings)"}
    return {**base, **kw}


def expert_standing(**kw):
    base = {"value": 57, "band": "upper", "segment": "suv", "n_models": 40, "score": 8.0, "scale_max": 10.0,
            "source": "Autocar India", "caption": "Autocar India 8/10 overall · above average among SUVs"}
    return {**base, **kw}


def with_standing(**kw):
    return car(owner_standing=standing(band="upper"), expert_standing=expert_standing(), **kw)


def text(fragment):
    """Visible text of an HTML fragment."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment)).strip()


def ratings_line(html):
    m = re.search(r'<p class="ratings">(.*?)</p>', html, re.S)
    return text(m.group(1)) if m else None


def test_no_score_bars_and_no_specs_fit_number_in_the_card():
    html = render(response([with_standing(), car()]))
    for gone in ("Specs", "fit to your search", "meter", "Match breakdown", "Expert and Owners show standing", ">81<"):
        assert gone not in html
    css = (ROOT / "static" / "style.css").read_text()
    assert ".meter" not in css


def test_ratings_line_gives_raw_values_source_and_standing_in_words():
    html = render(response([with_standing()]))
    assert ratings_line(html) == ("Reviewers: 8/10 (Autocar India, above average for SUVs) · "
                                  "Owners: 4.6/5 from 1,068 ratings (above average)")
    assert html.count('class="ratings"') == 1 and 'class="ratings"' in html.split('class="v3-fit"')[1]   # in the collapsed card


def test_ratings_line_is_one_part_when_the_other_is_missing_and_absent_when_both_are():
    assert ratings_line(render(response([car(owner_standing=standing(band="upper"), expert_standing=None)]))) == \
        "Owners: 4.6/5 from 1,068 ratings (above average)"
    assert ratings_line(render(response([car(owner_standing=None, expert_standing=expert_standing())]))) == \
        "Reviewers: 8/10 (Autocar India, above average for SUVs)"
    no_overall = expert_standing(score=None, scale_max=None, value=None, band="no_overall")
    assert ratings_line(render(response([car(owner_standing=standing(rating=None), expert_standing=no_overall)]))) is None
    assert 'class="ratings"' not in render(response([car()]))                    # no standing objects at all: no line


def test_ratings_line_makes_no_standing_claim_for_small_segments_or_few_ratings():
    small = standing(value=None, band="small_segment", caption="4.6/5 from 1068 ratings · only 7 rated sedans, too few to compare")
    low = standing(value=None, band="low_confidence", rating=4.4, rating_count=12, caption="4.4/5 from only 12 ratings · too few to compare")
    for st, expect in ((small, "Owners: 4.6/5 from 1,068 ratings"), (low, "Owners: 4.4/5 from only 12 ratings")):
        line = ratings_line(render(response([car(owner_standing=st, expert_standing=None)])))
        assert line == expect
        assert not re.search(r"best-rated|average|lowest-rated|too few", line)


def test_ratings_line_top_and_bottom_bands_keep_the_wording():
    top = standing(band="top", caption="4.8/5 from 900 ratings · among the best-rated SUVs", rating=4.8, rating_count=900)
    assert ratings_line(render(response([car(owner_standing=top, expert_standing=None)]))) == \
        "Owners: 4.8/5 from 900 ratings (among the best-rated SUVs)"


def test_ratings_line_is_escaped():
    html = render(response([car(expert_standing=expert_standing(source="<script>alert(1)</script>"), owner_standing=None)]))
    assert "<script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def many_lines():
    return with_standing(expert_notes=[expert(note="expert 0"), expert(note="expert 1")],
                         owner_notes=[owner(note="owner 0"), owner(theme="service_cost", note="owner 1")],
                         reasons=[{"text": f"reason {i}", "evidence_class": "spec"} for i in range(4)])


def hidden_texts(html):
    """Texts of the elements carrying data-more + hidden (what the collapsed card hides)."""
    out = []
    for chunk in html.split("data-more hidden")[1:]:
        out.append(chunk.split("</li>")[0].split("</blockquote>")[0])
    return out


def test_toggle_is_a_real_button_collapsed_by_default_with_aria():
    html = render(response([many_lines()]))
    assert 'data-reviews="collapsed"' in html
    btn = html.split("<button type=\"button\" class=\"btn btn-quiet btn-reviews\" data-reviews-toggle")[1].split("</button>")[0]
    assert 'aria-expanded="false"' in btn
    ident = btn.split('aria-controls="')[1].split('"')[0]
    assert f'id="{ident}"' in html and re.search(rf'id="{ident}" data-more hidden', html)  # aria-controls names the hidden panel
    assert "<details" not in html and "<div data-reviews-toggle" not in html


def test_toggle_label_counts_the_items_behind_it():
    # 2 expert lines + 2 owner lines + 2 extra "why" bullets = 6
    html = render(response([many_lines()]))
    assert "Reviews and owner feedback (6)" in html and "Show more from reviews" not in html
    caveat = owner(theme="recurring_fault", label="clutch judder", direction="negative", mentions=3, posts_sampled=60,
                   share=0.05, note="Judder.", kind="reported_fault")
    one = render(response([car(expert_notes=[expert()], owner_notes=[], caveats=[caveat])]))   # 1 expert + 1 caveat
    assert "Reviews and owner feedback (2)" in one
    only_summary = render(response([car(expert_notes=[], owner_notes=[], owner_standing=standing())]))
    assert "Reviews and owner feedback (1)" in only_summary                                   # the ratings summary counts


def test_reviewers_owners_and_caveats_sit_behind_the_toggle_and_the_card_shows_two_why_bullets():
    caveat = owner(theme="recurring_fault", label="clutch judder", direction="negative", mentions=3, posts_sampled=60,
                   share=0.05, note="Judder at low speed.", kind="reported_fault")
    html = render(response([{**many_lines(), "caveats": [caveat]}]))
    panel = html.split('class="v3-more"')[1]
    assert "data-more hidden" in html.split('class="v3-more"')[1][:60]
    for needle in ("What reviewers say", "What owners say", 'aria-label="Caveats from owners"', "expert 1", "owner 0", "Judder at low speed."):
        assert needle in panel
    before = html.split('class="v3-more"')[0]
    for needle in ("What reviewers say", "What owners say", "expert 0", "owner 0", "Judder at low speed.", 'aria-label="Caveats from owners"'):
        assert needle not in before
    visible_why = before.split('aria-label="Why this car"')[1].split("</section>")[0]
    assert visible_why.count("<li>") == 2 and visible_why.count("data-more hidden") == 2     # reasons 3 and 4 wait behind the toggle


def test_card_has_at_most_one_caveat_line_and_it_is_a_single_pill():
    faults = [owner(theme="recurring_fault", label=lab, direction="negative", mentions=3, posts_sampled=60, share=0.05,
                    note=f"Note {lab}.", kind="reported_fault") for lab in ("fit and finish", "clutch judder", "ac cooling")]
    html = render(response([car(caveats=faults)]))
    assert html.count('class="caveat-pill"') == 1
    pill = re.search(r'<p class="caveat-pill" title="([^"]*)">', html).group(1)
    assert pill == "Owners report: fit and finish (+2 more)"
    assert html.index('class="caveat-pill"') < html.index('class="v3-more"')                  # shown in the collapsed card
    assert html.split('class="v3-more"')[0].count("Note clutch judder.") == 0                 # the notes are not
    assert 'class="caveat-pill"' not in render(response([car()]))


def test_full_caveats_are_behind_the_toggle_while_the_pill_stays_visible():
    caveat = owner(theme="recurring_fault", label="clutch judder", direction="negative", mentions=3, posts_sampled=60,
                   share=0.05, note="Judder at low speed.", kind="reported_fault")
    html = render(response([with_standing(expert_notes=[expert(), expert(note="e2")], caveats=[caveat])]))
    block = html.split('aria-label="Caveats from owners"')[1].split("</section>")[0]
    assert "Reported fault: clutch judder" in block and "Judder at low speed." in block
    assert html.index('class="caveat-pill"') < html.index("data-reviews-toggle") < html.index('aria-label="Caveats from owners"')


def test_no_toggle_and_no_panel_when_nothing_sits_behind_it():
    bare = car(expert_notes=[], owner_notes=[], caveats=[], reasons=[{"text": "one", "evidence_class": "spec"}])
    html = render(response([bare]))
    assert "data-reviews-toggle" not in html and "data-reviews=" not in html and "data-more" not in html
    assert "Reviews and owner feedback" not in html and 'class="v3-more"' not in html


def test_a_long_note_is_in_the_dom_in_full_and_no_longer_clamped():
    long_note = "Words " * 40
    html = render(response([car(expert_notes=[expert(quote=None, note=long_note)], owner_notes=[owner(note="Short.")])]))
    assert long_note.strip() in html
    css = (ROOT / "static" / "style.css").read_text()
    assert "line-clamp" not in css


def test_owner_summary_line_replaces_an_empty_owner_block():
    html = render(response([with_standing(owner_notes=[])]))
    block = html.split('aria-label="What owners say"')[1].split("</section>")[0]
    assert "Owners rate it 4.6/5 overall, after-sales cost 4.4/5 (CarWale, 1068 ratings)" in block
    assert "No owner review themes" not in block and "No owner ratings" not in block


def test_owner_summary_not_shown_when_lines_exist_and_no_ratings_still_says_so():
    html = render(response([with_standing()]))
    assert "Owners rate it 4.6/5 overall" not in html
    none = render(response([car(owner_notes=[], scores={"overall": 0.5, "spec": 0.5, "expert": 0.7, "owner": None, "coverage": 0.5})]))
    assert "No owner ratings available for this model." in none


def test_toggle_script_flips_state_without_persisting_it():
    js = (ROOT / "static" / "script.js").read_text()
    body = js.split("function toggleReviews(button)")[1].split("\n}\n")[0]
    assert "aria-expanded" in body and "hidden" in body
    assert "localStorage" not in body and "sessionStorage" not in body


def test_old_engine_html_has_none_of_the_new_markup():
    html = render({"recommendations": [{"Make": "Tata", "Model": "Nexon", "Variant": "Smart", "Ex-Showroom_Price": 800000.0,
                                        "ranking_score": 80.0, "Fuel_Type": "Petrol", "Transmission": "Manual"}]})
    for needle in ("data-reviews", "meter-cap", "meters-note", "data-more"):
        assert needle not in html


# ------------------------------------------------------------------ UI quick wins (PR A)

def test_data_stamp_has_no_pipeline_id_in_its_text():
    html = render(response([car()], data_as_of={"exported": "2026-11-22", "kb_phase": "kbpipe-ev_range_2026-11-22-review"}))
    stamp = re.search(r'<p class="data-stamp"([^>]*)>([^<]*)</p>', html)
    assert stamp.group(2) == "Prices and specs updated 22 Nov 2026"
    assert "kbpipe" not in stamp.group(2) and "knowledge base" not in stamp.group(2)
    assert 'title="Data run: kbpipe-ev_range_2026-11-22-review"' in stamp.group(1)   # still there for debugging


def test_top_pick_only_when_nothing_unmet_or_unverified():
    assert ">Top pick<" in render(response([car()]))
    unmet = car(violations=[{"constraint": "seats", "text": "5 seats, 7+ asked", "amount": 2, "unit": "seats"}])
    unverified = car(not_verified=["ground clearance not verified"])
    for weak in (unmet, unverified):
        html = render(response([weak]))
        assert 'class="rank rank--close">Closest match<' in html and "Top pick" not in html
    html = render(response([car(), car(Model="Punch")]))          # only rank 1 is badged
    assert html.count('class="rank') == 1


def test_closest_match_pill_is_quieter_in_css():
    css = (ROOT / "static" / "style.css").read_text()
    assert ".rank--close { background: var(--surface-2); color: var(--ink-2); }" in css


def test_exclusions_are_echoed_as_chips():
    intent = {"budget": {"min": None, "max": None}, "body_types": [], "transmission": {"family": None}, "seats_min": 7,
              "fuel_types": ["diesel"], "exclude_makes": ["Mahindra"], "exclude_features": ["sunroof"]}
    html = render(response([car()], intent=intent))
    echo = html.split('<ul class="echo-list">')[1].split("</ul>")[0]
    assert "No Mahindra" in echo and "No sunroof" in echo


def test_view_details_is_primary_and_on_road_price_is_a_text_link_under_the_price():
    html = render(response([car()]))
    assert '<button type="button" class="btn btn-primary" data-detail' in html
    price = html.split('<p class="car-price">')[1].split("</p>")[0]
    assert 'class="price-link"' in price and "On-road price on CarDekho" in price and 'target="_blank"' in price
    assert "Check on-road price" not in html
    assert 'class="price-link"' not in render(response([car(carDekhoLink=None)]))


def test_car_name_links_to_the_car_page():
    html = render(response([car(Make="Maruti Suzuki", Model="Grand Vitara")]))
    assert '<h3 class="car-title"><a href="/car/maruti-suzuki/grand-vitara">Maruti Suzuki Grand Vitara</a></h3>' in html


def test_owner_note_already_in_caveats_is_not_repeated_under_what_owners_say():
    fault = owner(theme="service_experience", direction="negative", mentions=4, posts_sampled=31, note="Slow service.")
    other = owner(theme="satisfaction", note="Owners are happy.")
    html = render(response([car(owner_notes=[fault, other], caveats=[fault])]))
    block = html.split('aria-label="What owners say"')[1].split("</section>")[0]
    assert "Slow service." not in block and "Owners are happy." in block
    assert html.count("Slow service.") == 1
    only = render(response([car(owner_notes=[fault], caveats=[fault])]))          # nothing else to show: falls back, no repeat
    assert only.split('aria-label="What owners say"')[1].split("</section>")[0].count("Slow service.") == 0


def test_suggestion_chips_no_longer_auto_rotate():
    js = (ROOT / "static" / "script.js").read_text()
    assert "setInterval" not in js and "SUGGESTION_ROTATE_MS" not in js
    assert "data-more-ideas" in js                                                  # the manual button stays


def test_status_sentence_for_the_hidden_status_line():
    status = """
const vm = require('vm'), fs = require('fs');
const ctx = vm.createContext({ console, URL, location: { origin: 'http://x', pathname: '/recommend', search: '' } });
vm.runInContext(fs.readFileSync(process.argv.at(-1), 'utf8'), ctx);
process.stdout.write(JSON.stringify(vm.runInContext(
  '[searchStatusText({recommendations: new Array(8), relaxation: {}}, true, "7 seater diesel, no Mahindra"),'
  + 'searchStatusText({recommendations: new Array(1)}, true, "x"), searchStatusText({recommendations: []}, true, "q"), searchStatusText({}, false, "q")]', ctx)));
"""
    out = subprocess.run(["node", "-e", status, str(ROOT / "static" / "script.js")], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["8 cars found for 7 seater diesel, no Mahindra. Nothing matched every requirement.",
                                      "1 car found for x.", "No cars found for q.", "The search didn't go through."]


def test_loading_skeleton_is_static_under_reduced_motion_and_has_no_hard_coded_count():
    js = (ROOT / "static" / "script.js").read_text()
    assert "1,556" not in js and "1556" not in js and "dataset" in js.split("function showSearchLoading")[1][:400]
    css = (ROOT / "static" / "style.css").read_text()
    assert "@media (prefers-reduced-motion: no-preference)" in css and "animation: shimmer" in css
    assert css.count("animation: shimmer") == 1 and css.split("animation: shimmer")[0].rsplit("@media", 1)[1].startswith(" (prefers-reduced-motion: no-preference)")


def test_interactive_borders_use_the_darker_control_token():
    css = (ROOT / "static" / "style.css").read_text()
    assert "--line-ctl: #8f897c" in css and "--line-ctl: #6a6d75" in css
    for rule in (".chip-btn {", ".btn-quiet {", ".hint-btn {"):
        block = css.split(rule)[1].split("}")[0]
        assert "var(--line-ctl)" in block and "--line-strong" not in block


# ------------------------------------------------------------------ PR B: vague queries and citations
REFINER_PHRASES = ["under 10 lakh", "family 7 seater", "city automatic", "best mileage"]


def test_vague_query_replaces_the_notice_body_with_four_refiner_buttons():
    html = render(response([car(match_label="General pick, not personalised", personalised=False)], personalised=False, vague=True,
                          message="Your query didn't say what you are looking for, so this is a general shortlist"))
    assert "Your query didn't say" not in html and "Please note" not in html
    buttons = re.findall(r'<button type="button" class="refiner" data-refine="([^"]+)">([^<]+)</button>', html)
    assert [b[0] for b in buttons] == REFINER_PHRASES
    assert [b[1] for b in buttons] == ["Under ₹10 lakh", "Family / 7 seats", "City / automatic", "Best mileage"]
    assert html.count("General pick, not personalised") >= 1                              # the card label is unchanged
    assert "refiner" not in render(response([car()], message="Please note this"))          # a normal result has none


def test_refiners_rerun_the_current_query_through_runsearch_and_are_real_buttons_40px_tall():
    js = (ROOT / "static" / "script.js").read_text()
    handler = js.split('const refine = e.target.closest("[data-refine]");')[1].split("const copy")[0]
    assert "runSearch(`${turn.dataset.q} ${refine.dataset.refine}`" in handler
    css = (ROOT / "static" / "style.css").read_text()
    rule = css.split(".refiner {")[1].split("}")[0]
    assert re.search(r"min-height: (4\d|[5-9]\d)px", rule)
    assert ":focus-visible" in css.split(".refiner")[0] or "focus-visible { outline" in css      # the global focus ring covers buttons


def test_every_refiner_phrase_is_understood_by_the_parser():
    from services.recsys.api import recommend
    from services.recsys.evidence import Evidence
    assert recommend("good car", evidence=Evidence()).get("vague") is True                     # the starting point is vague
    seen = {}
    for phrase in REFINER_PHRASES:
        out = recommend(f"good car {phrase}", evidence=Evidence())
        assert not out.get("vague"), phrase                                                # the added phrase makes the search personalised
        seen[phrase] = out["intent"]
    assert seen["under 10 lakh"]["budget"]["max"] == 1000000
    assert seen["family 7 seater"].get("seats_min") == 7 and seen["family 7 seater"].get("use_case") == "family"
    assert seen["city automatic"]["transmission"]["family"] == "automatic" and seen["city automatic"].get("use_case") == "city"
    assert "mileage" in seen["best mileage"].get("soft_preferences", [])


RAG = {"sentences": [{"text": "It has the sunroof you asked for.", "cites": ["f1", "f2"]},
                     {"text": "Autocar India rates the ride highly.", "cites": ["f3"]}],
       "facts": {"f1": {"label": "Sunroof: yes", "source": "Tata brochure", "source_url": "https://example.com/b.pdf", "date": "2025-08"},
                 "f2": {"label": "Price 8 lakh", "source": "Tata brochure", "source_url": "", "date": "2025-08"},
                 "f3": {"label": "Ride 8/10", "source": "Autocar India", "source_url": "", "date": "2025-08"}}}


def test_cited_explanation_stays_in_the_collapsed_card_and_its_sources_count_behind_the_toggle():
    html = render(response([car(explanation_rag=RAG)]))
    before, after = html.split('class="v3-more"')[0], html.split('class="v3-more"')[1]
    assert before.count('data-cite') == 3 and "It has the sunroof you asked for." in before
    assert '<ol class="why-sources" data-more hidden>' in before                    # sources open with the toggle
    assert "Priced at 8 lakh" not in before.split('<ol class="why-sources"')[0]      # the template bullet is not shown next to it
    assert "Reviews and owner feedback (6)" in html                                  # 3 sources + 1 template bullet + 1 expert + 1 owner
    assert "What reviewers say" in after


def test_citation_click_keeps_the_citation_in_view_and_focuses_the_source():
    js = (ROOT / "static" / "script.js").read_text()
    body = js.split("function followCite(link)")[1].split("\n}\n")[0]
    assert "getBoundingClientRect().top" in body and "scrollBy(0, drift)" in body          # the clicked citation stays put
    assert "focus({ preventScroll: true })" in body                                           # focus moves without the browser's own scroll
    assert 'scrollIntoView({ block: "nearest"' in body                                       # the source is scrolled only as far as needed


# ------------------------------------------------------------------ PR C: details panel and car page
DETAIL_HARNESS = """
const vm = require('vm'), fs = require('fs');
const ctx = vm.createContext({ console, URL, URLSearchParams, setTimeout, location: { origin: 'http://x', pathname: '/car/tata/nexon', search: '' },
  window: { matchMedia: () => ({ matches: false }) }, history: { replaceState(a, b, url) { ctx.__urls.push(url); } }, __urls: [] });
vm.runInContext(fs.readFileSync(process.argv.at(-1), 'utf8'), ctx);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
ctx.input = input;
const out = vm.runInContext(input.code, ctx);
Promise.resolve(out).then(v => process.stdout.write(JSON.stringify(v)));
"""

SPEC_ITEMS = [{"label": l, "value_display": "v", "status": "ok"} for l in
              ["Engine", "Power", "Gearbox", "Fuel", "Mileage (ARAI)", "Seats", "Boot space", "Airbags", "Sunroof", "ADAS", "Torque", "Length"]]


def detail_data(n=12, matching=3, selected=1, **kw):
    variants = [{"variant_id": i, "variant": f"Var {i}", "price": 800000 + i * 1000, "matches_query": i <= matching,
                 "transmission_label": "Manual", "fuel_label": "Petrol", "mileage_display": {"value": "19 kmpl", "unit": "kmpl"}}
                for i in range(1, n + 1)]
    base = {"make": "Tata", "model": "Nexon", "image": "/x.png", "summary": "A compact SUV.", "variants": variants,
            "selected_variant_id": selected, "price_range": None, "cardekho_link": "https://x.test", "data_as_of": None,
            "specs": [{"group": "Engine & performance", "items": SPEC_ITEMS[:6] + [SPEC_ITEMS[10]]},
                      {"group": "Dimensions & capacity", "items": SPEC_ITEMS[6:7] + [SPEC_ITEMS[11]]},
                      {"group": "Comfort & convenience", "items": [SPEC_ITEMS[8]]},
                      {"group": "Safety", "items": [SPEC_ITEMS[7], SPEC_ITEMS[9]]}, {"group": "Warranty", "items": []}],
            "safety": None, "reviews": None}
    return {**base, **kw}


def run_detail(code, **data):
    out = subprocess.run(["node", "-e", DETAIL_HARNESS, str(ROOT / "static" / "script.js")], input=json.dumps({"code": code, **data}),
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def render_detail(data, opts):
    return run_detail("renderDetail(input.data, input.opts)", data=data, opts=opts)


def test_inline_panel_has_only_summary_key_specs_and_a_full_details_link_that_carries_the_search():
    html = render_detail(detail_data(selected=5), {"make": "tata", "model": "nexon", "q": "automatic SUV & sunroof", "drop": ["adas", "budget"]})
    assert "<h3>Summary</h3>" in html and "<h3>Key specs</h3>" in html
    assert "Variants" not in html and "<table" not in html and "variant-pick" not in html
    for hidden in ("Torque", "Length", "Specifications", "<h3>Safety</h3>", "Warranty"):
        assert hidden not in html
    for shown in ("Engine", "Power", "Gearbox", "Mileage (ARAI)", "Seats", "Boot space", "Airbags", "Sunroof", "ADAS"):
        assert f"<dt>{shown}</dt>" in html
    href = [l for l in links(html) if "detail-full" in (l.get("class") or "")][0]["href"]
    assert "Full details →" in html
    assert href.startswith("/car/tata/nexon?")
    from urllib.parse import parse_qs, urlparse
    assert parse_qs(urlparse(href).query) == {"q": ["automatic SUV & sunroof"], "drop": ["adas,budget"], "variant_id": ["5"]}


def test_car_page_section_order_is_summary_specs_safety_warranty_then_variants():
    html = render_detail(detail_data(), {"make": "tata", "model": "nexon", "q": "", "standalone": True})
    order = [html.index(f"<h2>{h}</h2>") for h in ("Summary", "Specifications", "Safety", "Warranty", "Variants")]
    assert order == sorted(order)
    assert html.index('id="detail-specs"') < html.index('id="detail-variants"')


def rows(html):
    return re.findall(r'<tr data-variant-id="(\d+)"([^>]*)>', html)


def visible_ids(html):
    return [i for i, attrs in rows(html) if " hidden" not in attrs]


def test_variant_table_without_a_query_shows_the_first_eight_and_a_show_all_toggle():
    html = render_detail(detail_data(n=20), {"make": "tata", "model": "nexon", "q": "", "standalone": True})
    assert len(rows(html)) == 20 and len(visible_ids(html)) == 8
    assert re.search(r'<button type="button" class="btn btn-quiet variants-toggle"[^>]*aria-expanded="false"[^>]*>Show all 20 variants</button>', html)
    few = render_detail(detail_data(n=6, matching=0), {"make": "tata", "model": "nexon", "q": "", "standalone": True})
    assert len(visible_ids(few)) == 6 and "variants-toggle" not in few


def test_variant_table_with_a_query_shows_only_matching_variants_up_to_eight():
    opts = {"make": "tata", "model": "nexon", "q": "suv", "standalone": True}
    html = render_detail(detail_data(n=20, matching=3), opts)
    assert visible_ids(html) == ["1", "2", "3"] and "Show all 20 variants" in html
    assert 'data-match-mode="true"' in html and "3 of 20 variants match your search." in html
    many = render_detail(detail_data(n=30, matching=15), opts)
    assert len(visible_ids(many)) == 8 and all(int(i) <= 15 for i in visible_ids(many))
    none = render_detail(detail_data(n=12, matching=0), opts)                  # nothing matches: the first eight of all, said plainly
    assert len(visible_ids(none)) == 8 and "None of the 12 variants match your search." in none and 'data-match-mode="false"' in none


def test_selected_variant_stays_visible_when_it_is_outside_the_first_rows():
    html = render_detail(detail_data(n=20, matching=3, selected=17), {"make": "tata", "model": "nexon", "q": "suv", "standalone": True})
    assert len(visible_ids(html)) <= 8 and "17" in visible_ids(html)


def test_show_all_toggle_expands_in_place_and_goes_back_to_matching_only():
    code = """(() => {
      const mk = () => ({ hidden: true }), extra = [mk(), mk()];
      const wrap = { scrollTop: 50, querySelectorAll: () => extra };
      const attrs = { 'aria-expanded': 'false' };
      const button = { dataset: { total: '20', matchMode: 'true' }, textContent: 'Show all 20 variants', parentElement: { querySelector: () => wrap },
        getAttribute: k => attrs[k], setAttribute: (k, v) => { attrs[k] = v; } };
      const log = [];
      toggleVariants(button); log.push([button.textContent, attrs['aria-expanded'], extra.map(e => e.hidden)]);
      toggleVariants(button); log.push([button.textContent, attrs['aria-expanded'], extra.map(e => e.hidden), wrap.scrollTop]);
      return log; })()"""
    first, second = run_detail(code)
    assert first == ["Show matching only", "true", [False, False]]
    assert second == ["Show all 20 variants", "false", [True, True], 0]


def test_table_wrap_scrolls_on_its_own_so_the_sticky_header_works():
    css = (ROOT / "static" / "style.css").read_text()
    rule = css.split(".table-wrap {")[1].split("}")[0]
    assert "max-height: 420px" in rule and "overflow: auto" in rule
    assert "position: sticky" in css.split(".variants th {")[1].split("}")[0]


PICK_HARNESS = """(async () => {
  const log = [], el = () => ({ attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } });
  const status = Object.assign(el(), { textContent: '', innerHTML: '', className: '' });
  const region = Object.assign(el(), { innerHTML: '' });
  const rowEl = id => { const r = el(), control = Object.assign(el(), { textContent: 'Var ' + id, focused: 0, focus(o) { this.focused++; this.opt = o; } });
    Object.assign(r, { dataset: { variantId: String(id) }, control, spinners: 0, classes: new Set(),
      firstElementChild: { insertAdjacentHTML(w, h) { r.spinners++; r.spinnerHtml = h; } },
      querySelector(sel) { return sel === '.variant-pick' ? control : (sel === '.spinner' && r.spinners ? { remove() { r.spinners = 0; } } : null); },
      classList: { toggle(c, on) { on ? r.classes.add(c) : r.classes.delete(c); } } }); return r; };
  const rows = [rowEl(1), rowEl(2)];
  const body = { dataset: { selected: '1' },
    querySelector: s => s === '#pick-status' ? status : s === '#detail-specs' ? region : null,
    querySelectorAll: s => s === 'tr[aria-busy]' ? rows.filter(r => r.attrs['aria-busy']) : rows };
  const opts = { make: 'tata', model: 'nexon', q: 'suv', drop: [] };
  let release;
  globalThis.fetch = (url) => { log.push(['fetch', url]); return new Promise((res, rej) => { release = (ok) => ok
      ? res({ ok: true, status: 200, json: async () => Object.assign(input.data, { selected_variant_id: 2 }) })
      : res({ ok: false, status: 500, json: async () => ({ error: 'boom' }) }); }); };
  const done = pickVariant(body, opts, rows[1]);
  const busy = { rowBusy: rows[1].attrs['aria-busy'], spinner: rows[1].spinners, spinnerSmall: /spinner--sm/.test(rows[1].spinnerHtml || ''),
    status: status.textContent, regionBusy: region.attrs['aria-busy'], focused: rows[1].control.focused, regionHtmlBefore: region.innerHTML };
  release(input.ok);
  await done;
  return { log, busy, after: { rowBusy: rows[1].attrs['aria-busy'] ?? null, spinner: rows[1].spinners, regionBusy: region.attrs['aria-busy'] ?? null, status: status.innerHTML,
    statusText: status.textContent, cls: status.className, focused: rows[1].control.focused, preventScroll: rows[1].control.opt.preventScroll,
    selected: body.dataset.selected, region: region.innerHTML.slice(0, 80), regionHasVariants: /variants-table|<table/.test(region.innerHTML),
    cur: rows.map(r => r.attrs['aria-current'] || null), classes: rows.map(r => [...r.classes]), pressed: rows.map(r => r.control.attrs['aria-pressed']), urls: __urls } };
})()"""


def test_picking_a_variant_marks_the_row_busy_then_redraws_only_the_spec_sections():
    r = run_detail(PICK_HARNESS, data=detail_data(selected=2), ok=True)
    assert r["busy"] == {"rowBusy": "true", "spinner": 1, "spinnerSmall": True, "status": "Loading specs for Var 2…",
                         "regionBusy": "true", "focused": 1, "regionHtmlBefore": ""}               # feedback before the fetch resolves
    a = r["after"]
    assert a["rowBusy"] is None and a["spinner"] == 0 and a["regionBusy"] is None                  # never left busy
    assert a["status"] == 'Showing specs for Var 2 <a href="#detail-specs" data-jump-specs>Jump to specs ↓</a>'
    assert a["focused"] == 2 and a["preventScroll"] is True                                          # focus is on the row's control
    assert str(a["selected"]) == "2" and a["cur"] == [None, "true"] and a["pressed"] == ["false", "true"]
    assert a["region"].startswith('<section class="detail-section"><h2>Specifications</h2>') and a["regionHasVariants"] is False
    assert a["urls"] == ["/car/tata/nexon?q=suv&variant_id=2"]                                      # replaceState keeps q and gains variant_id
    assert r["log"][0] == ["fetch", "/api/car/tata/nexon?variant_id=2"]                    # no q: the server does not re-rank for a spec swap


def test_a_failed_variant_fetch_clears_the_spinner_and_says_so_in_the_status_line():
    r = run_detail(PICK_HARNESS, data=detail_data(selected=2), ok=False)
    a = r["after"]
    assert a["rowBusy"] is None and a["spinner"] == 0 and a["regionBusy"] is None
    assert a["statusText"] == "Couldn't load the specs for Var 2. Select it again to retry." and "pick-status--error" in a["cls"]
    assert str(a["selected"]) == "1" and a["urls"] == [] and a["focused"] == 2


def test_variant_spinner_is_16px_and_static_under_reduced_motion_and_the_status_is_one_live_line():
    css = (ROOT / "static" / "style.css").read_text()
    assert "width: 16px; height: 16px" in css.split(".spinner--sm {")[1].split("}")[0]
    assert re.search(r"@media \(prefers-reduced-motion: reduce\) \{ \.spinner--sm \{ animation: none; \} \}", css)
    html = render_detail(detail_data(), {"make": "tata", "model": "nexon", "q": "", "standalone": True})
    assert html.count('role="status"') == 1 and 'id="pick-status"' in html


def test_car_page_with_a_search_shows_reviewer_owner_and_caveat_blocks_under_summary():
    reviews = {"expert_notes": [expert()], "owner_notes": [owner()], "caveats": [owner(theme="recurring_fault", label="Clutch", direction="negative", note="Slow service.")],
               "expert_standing": None, "owner_standing": None, "scores": {"expert": 0.7, "owner": 0.8}}
    opts = {"make": "tata", "model": "nexon", "q": "suv", "standalone": True}
    html = render_detail(detail_data(reviews=reviews), opts)
    assert html.index("<h2>Summary</h2>") < html.index("What reviewers say") < html.index("What owners say") < html.index("Caveats") < html.index("<h2>Specifications</h2>")
    assert "Soaks up rough roads." in html and "Owners are happy." in html and "Slow service." in html
    assert "<h4>" not in html                                                                       # headings step h2 to h3
    assert "What reviewers say" not in render_detail(detail_data(reviews=reviews), {**opts, "q": ""})  # no search, no blocks
    assert "What reviewers say" not in render_detail(detail_data(reviews=None), opts)                # model not on the card list
    assert "What reviewers say" not in render_detail(detail_data(reviews=reviews), {"make": "tata", "model": "nexon", "q": "suv"})  # inline panel


# ---- didn't-use chips, relaxed notice with alternatives, uncovered brand notice

def test_ignored_terms_chip():
    html = render(response([car()], ignored_terms=["convertible", "4x4 / AWD"]))
    import html as H
    text = H.unescape(html)
    assert html.count("echo--ignored") == 2 and "Didn't use: convertible" in text and "Didn't use: 4x4 / AWD" in text
    assert "We can't filter on this yet, so it didn't change the results." in text
    assert "echo-off" not in html.split("echo--ignored")[1].split("</li>")[0]
    assert "echo--ignored" not in render(response([car()], ignored_terms=[]))


RELAX = {"moves": [{"key": "fuel", "label": "any fuel type"}, {"key": "seats", "label": "5+ seats instead of 7+"}],
         "keys": ["fuel", "seats"], "far": False, "seats_relaxed": True,
         "message": "No car is confirmed to have all of: x. Showing the closest. Not confirmed in our data for the cars shown: sunroof, ADAS.",
         "alternatives": [{"key": "feature:sunroof", "label": "sunroof", "models": 3}, {"key": "budget", "label": "budget", "models": 1}]}


def test_relaxed_notice_pills_and_alternatives():
    html = render(response([car()], relaxation=RELAX, message="m"))
    assert "No car matches everything you asked for." in html
    assert html.count('class="relax-pill"') == 2 and "any fuel type" in html and "5+ seats instead of 7+" in html
    assert "Not confirmed for the cars shown: sunroof, ADAS." in html
    assert "Or drop one requirement instead:" in html
    assert 'data-drop-key="feature:sunroof"' in html and "sunroof <span" in html and "3 models" in html
    assert 'data-drop-key="budget"' in html and "1 model<" in html


def test_relaxed_notice_far_and_no_alternatives():
    html = render(response([car()], relaxation={**RELAX, "far": True, "alternatives": []}))
    assert "Nothing close exists in our catalogue; these are the nearest cars." in html
    assert "Or drop one requirement" not in html


def test_relaxed_notice_old_shape_still_renders():
    html = render(response([car()], relaxation={"message": "Old message here", "keys": []}))
    assert "Old message here" in html


def test_uncovered_brand_notice_with_budget():
    intent = {"budget": {"min": None, "max": 1000000}, "body_types": [], "transmission": {"family": None}}
    html = render(response([car()], intent=intent, unsupported_terms=["Ferrari"]))
    import html as H
    text = H.unescape(html)
    assert "We don't cover Ferrari." in text and "Showing cars under ₹10L instead." in text


def test_uncovered_brand_notice_nothing_understood():
    intent = {"budget": {"min": None, "max": None}, "body_types": [], "transmission": {"family": None}}
    html = render(response([car()], intent=intent, unsupported_terms=["Ferrari"]))
    assert "Showing general picks instead." in html and "We don" in html
