"""Grounded explanations (plan C): facts, checker, per-car and whole-call fallback, RAG off = unchanged response.
Mocked clients only: no network, no key, no real sleep."""
import copy
import json

import pytest

from services.catalogue import get_catalogue
from services.recsys import llm_parse as L
from services.recsys import rag_explain as R
from services.recsys.api import recommend
from services.recsys.evidence import Evidence
from services.recsys.facts import build_facts, facts_hash, numeric_tokens, token_matches

NO_EVIDENCE = Evidence()
NAMES = {"makes": ["Hyundai", "Maruti Suzuki", "Tata", "Honda"], "models": ["Creta", "Nexon", "Brezza", "City", "Punch"]}

CARD = {
    "variant_id": 7, "Make": "Hyundai", "Model": "Creta", "Variant": "SX 1.5 Petrol", "Ex-Showroom_Price": 1250000.0,
    "Displacement": 1497.0, "power_bhp": 113.0, "ARAI_Certified_Mileage": 17.4, "mileage_km_per_kg": None,
    "ev_range_km": None, "airbags": 6, "boot_space_litres": 433, "Fuel_Type": "Petrol",
    "transmission_label": "Automatic (CVT)", "matched_features": ["sunroof"], "not_verified": ["ground clearance not verified"],
    "missing_features": [], "unknowns": ["Owner ratings: none for this model yet"],
    "safety": {"stars_adult": 5, "stars_child": 4, "testing_body": "Bharat NCAP", "year": 2024},
    "expert_notes": [{"text": "Autocar India, ride 8/10 (Oct 2025): Soft ride, good in town.", "note": "Soft ride, good in town.",
                      "source": "Autocar India", "source_aspect": "Ride", "published_on": "2025-10-27",
                      "source_url": "https://example.test/creta", "quote": None}],
    "owner_notes": [{"text": "Many owners are positive about comfort (30 of 90 reviews, CarWale)", "source": "CarWale",
                     "source_url": "https://example.test/c"}],
    "caveats": [], "expert_standing": None, "owner_standing": None,
    "reasons": [{"text": "Running cost: 17.4 km/l, ahead of about 70% of similar petrol cars here", "evidence_class": "spec",
                 "fields": []}],
}


def facts():
    return build_facts(CARD, None, ["under ₹15 lakh", "sunroof"])


def ctx(fs=None):
    return R.CarContext("7", "Hyundai", "Creta", fs if fs is not None else facts())


def fid(fs, needle):
    return next(f.id for f in fs if needle in f.text)


def check(sentences, fs=None, names=NAMES):
    c = ctx(fs)
    return R.check_car(sentences, c, names)


# ------------------------------------------------------------------ facts

def test_facts_deterministic_and_ids_stable():
    a, b = facts(), facts()
    assert [(f.id, f.kind, f.text) for f in a] == [(f.id, f.kind, f.text) for f in b]
    assert [f.id for f in a] == [f"f{i}" for i in range(1, len(a) + 1)]
    assert facts_hash(a) == facts_hash(b)
    assert a[0].kind == "identity"


def test_facts_only_what_engine_has_and_unknowns_are_facts():
    fs = facts()
    texts = " | ".join(f.text for f in fs)
    assert "1497 cc" in texts and "113 bhp" in texts and "17.4 km/l" in texts and "Airbags: 6 airbags" in texts
    assert "adult 5 stars" in texts and "Bharat NCAP" in texts
    assert "Unknown: ground clearance not verified" in texts
    assert "Unknown: Owner ratings: none for this model yet" in texts
    assert "Torque" not in texts and "Wheelbase" not in texts           # no cell, no fact
    card = copy.deepcopy(CARD)
    card.update(ARAI_Certified_Mileage=None, safety=None, airbags=None)
    t2 = [f for f in build_facts(card, None, [])]
    assert any(f.text == "Unknown: mileage" for f in t2)
    assert any(f.kind == "unknown_ncap" for f in t2)
    assert any(f.text == "Unknown: airbag count" for f in t2)


def test_facts_sources_and_urls():
    fs = facts()
    expert = next(f for f in fs if f.kind == "expert")
    assert expert.url == "https://example.test/creta" and expert.source == "Autocar India" and expert.date == "2025-10-27"
    assert next(f for f in fs if f.kind == "owner").url == "https://example.test/c"


def test_numeric_tokens_normalise_money():
    toks = {(v, c) for v, c, _ in numeric_tokens("Priced at ₹12.5 lakh, about ₹12,50,000 or 1,250,000")}
    assert (1250000.0, "money") in toks
    assert token_matches(numeric_tokens("12.5 lakh")[0], [(1250000.0, "money")])
    assert token_matches(numeric_tokens("12.50 lakh")[0], [(1250000.0, "money")])
    assert not token_matches(numeric_tokens("12 lakh")[0], [(1250000.0, "money")])
    assert token_matches(numeric_tokens("five stars")[0], [(5.0, "stars")])
    assert not token_matches(numeric_tokens("6 airbags")[0], [(6.0, "seats")])


# ------------------------------------------------------------------ checker: accepts

def test_checker_accepts_correct_text():
    fs = facts()
    price, ncap, mil = fid(fs, "Ex-showroom"), fid(fs, "Crash-test"), fid(fs, "Mileage")
    out, why = check([f"It costs ₹12.5 lakh, inside your budget. [{price}]",
                      f"It has a 5 stars adult crash-test rating from Bharat NCAP. [{ncap}]",
                      f"It returns 17.4 km/l on the ARAI test. [{mil}]"], fs)
    assert why == [] and len(out) == 3 and out[0]["cites"] == [price]
    assert "[" not in out[0]["text"]


def test_checker_accepts_5_stars_phrasing_and_split_sentences():
    fs = facts()
    ncap = fid(fs, "Crash-test")
    out, why = check([f"Scores 5 stars for adults in Bharat NCAP tests. [{ncap}]"], fs)
    assert why == [] and out
    price = fid(fs, "Ex-showroom")
    out, why = check([f"Priced at ₹12.5 lakh. [{price}] Ex-showroom. [{price}]"], fs)
    assert why == [] and len(out) == 2


def test_checker_accepts_unknown_statement():
    fs = facts()
    unk = fid(fs, "ground clearance")
    out, why = check([f"Ground clearance is not confirmed in our data. [{unk}]"], fs)
    assert why == [], why


def test_crash_rating_unknown_may_be_stated():
    card = {**CARD, "safety": None, "unknowns": ["Crash rating: not available"], "not_verified": ["crash rating not verified"]}
    fs = build_facts(card, None, [])
    unk = [f for f in fs if "Crash rating: not available" in f.text][0]
    out, why = check([f"No crash-test rating is on record for it. [{unk.id}]"], fs)
    assert why == [], why
    other = fid(fs, "Ex-showroom")
    out, why = check([f"No crash-test rating is on record for it. [{other}]"], fs)
    assert out is None


def test_checker_accepts_object_sentences_and_own_name_digits():
    fs = facts()
    price = fid(fs, "Ex-showroom")
    out, why = check([{"text": "The Hyundai Creta costs ₹12.5 lakh.", "cites": [price]}], fs)
    assert why == []
    c = R.CarContext("9", "Mahindra", "XUV700", [build_facts({**CARD, "Make": "Mahindra", "Model": "XUV700"}, None, [])[1]])
    out, why = R.check_car([f"The XUV700 costs ₹12.5 lakh. [{c.facts[0].id}]"], c, NAMES)
    assert why == [], why


# ------------------------------------------------------------------ checker: rejects

def test_rejects_wrong_number():
    fs = facts()
    out, why = check([f"It costs ₹13.5 lakh. [{fid(fs, 'Ex-showroom')}]"], fs)
    assert out is None and any(w.startswith("number_not_in_cited") for w in why)
    out, why = check([f"It returns 19 km/l. [{fid(fs, 'Mileage')}]"], fs)
    assert out is None and any(w.startswith("number_not_in_cited") for w in why)


def test_rejects_number_present_in_another_fact_only():
    fs = facts()
    # 6 airbags is a real fact, but the sentence cites the mileage fact
    out, why = check([f"It has 6 airbags. [{fid(fs, 'Mileage')}]"], fs)
    assert out is None and any(w.startswith("number_not_in_cited") for w in why)
    ok, why2 = check([f"It has 6 airbags. [{fid(fs, 'Airbags:')}]"], fs)
    assert why2 == [] and ok


def test_rejects_unit_mismatch():
    fs = facts()
    out, why = check([f"It has 6 seats. [{fid(fs, 'Airbags:')}]"], fs)
    assert out is None and any(w.startswith("number_not_in_cited") for w in why)


def test_rejects_invented_feature_and_missing_citation():
    fs = facts()
    price = fid(fs, "Ex-showroom")
    out, why = check([f"It has a panoramic sunroof and ventilated seats."], fs)
    assert out is None and "no_citation" in why
    out, why = check([f"It has ventilated seats. [{price}]"], fs)
    assert out is None and any(w.startswith("feature_not_in_cited") for w in why)
    out, why = check([f"It runs on diesel. [{price}]"], fs)
    assert out is None and any(w.startswith("attribute_not_in_facts") for w in why)


def test_rejects_unknown_fact_id_and_other_car_names():
    fs = facts()
    price = fid(fs, "Ex-showroom")
    out, why = check([f"It costs ₹12.5 lakh. [f99]"], fs)
    assert out is None and any(w.startswith("unknown_fact_id") for w in why)
    out, why = check([f"A better value than the Nexon at ₹12.5 lakh. [{price}]"], fs)
    assert out is None and any(w.startswith("other_car_name:Nexon") for w in why)
    out, why = check([f"Tata build quality at ₹12.5 lakh. [{price}]"], fs)
    assert out is None and any(w.startswith("other_car_name") for w in why)
    # a common-word model is only a name when written as one, mid-sentence
    ok, why = check([f"Good for city driving at ₹12.5 lakh. [{price}]"], fs)
    assert why == [], why
    out, why = check([f"Costs ₹12.5 lakh, more than the Honda City. [{price}]"], fs)
    assert out is None


def test_rejects_safety_claim_without_ncap_fact():
    fs = facts()
    air = fid(fs, "Airbags")
    out, why = check([f"A safe family car with 6 airbags. [{air}]"], fs)
    assert out is None and "safety_claim_without_ncap_fact" in why
    out, why = check([f"It has a 5-star crash rating. [{air}]"], fs)
    assert out is None and "safety_claim_without_ncap_fact" in why


def test_rejects_comparison_unless_fact_compares():
    fs = facts()
    mil = fid(fs, "Mileage")
    out, why = check([f"It is the best in its class at 17.4 km/l. [{mil}]"], fs)
    assert out is None and any(w.startswith("comparison_not_in_facts") for w in why)
    score = fid(fs, "ahead of about")
    ok, why = check([f"Its 17.4 km/l is ahead of about 70% of similar petrol cars here. [{score}]"], fs)
    assert why == [] and ok


def test_rejects_absence_claim_without_unknown_fact():
    fs = facts()
    air = fid(fs, "Airbags")
    out, why = check([f"It has 6 airbags but lacks a sunroof. [{air}]"], fs)
    assert out is None and any(w.startswith("absence_claim") for w in why)


def test_rejects_too_many_sentences_too_long_and_bad_shape():
    fs = facts()
    price = fid(fs, "Ex-showroom")
    s = f"It costs ₹12.5 lakh. [{price}]"
    out, why = check([s, s, s, s], fs)
    assert out is None and any(w.startswith("sentence_count") for w in why)
    out, why = check([("It costs ₹12.5 lakh " + "and that is good " * 20 + f"[{price}]")], fs)
    assert out is None and "too_long" in why
    for bad in (None, [], "text", [3], [{"text": "x"}]):
        out, why = check(bad, fs)
        assert out is None and why[0].startswith("shape")


# ------------------------------------------------------------------ whole response / per-car fallback

def two_contexts():
    f1 = build_facts(CARD, None, [])
    other = {**CARD, "variant_id": 8, "Model": "Nexon", "Make": "Tata", "Ex-Showroom_Price": 900000.0}
    f2 = build_facts(other, None, [])
    return {"7": R.CarContext("7", "Hyundai", "Creta", f1), "8": R.CarContext("8", "Tata", "Nexon", f2)}, f1, f2


def test_check_response_per_car_and_whole_shape():
    cts, f1, f2 = two_contexts()
    good7 = [f"It costs ₹12.5 lakh. [{fid(f1, 'Ex-showroom')}]"]
    bad8 = [f"It costs ₹7 lakh. [{fid(f2, 'Ex-showroom')}]"]
    res, whole = R.check_response({"cars": [{"id": 7, "sentences": good7}, {"id": "8", "sentences": bad8}]}, cts, NAMES)
    assert whole is None and res["7"]["passed"] and not res["8"]["passed"]
    res, whole = R.check_response({"cars": [{"id": "7", "sentences": good7}]}, cts, NAMES)
    assert whole is None and res["7"]["passed"] and res["8"]["reasons"] == ["missing_car"]
    for raw in ({"cars": [{"id": "7", "sentences": good7}, {"id": "99", "sentences": good7}]},
                {"cars": [{"id": "7", "sentences": good7}, {"id": "7", "sentences": good7}]}, {"nope": 1}, [], None):
        res, whole = R.check_response(raw, cts, NAMES)
        assert whole and not any(r["passed"] for r in res.values())


# ------------------------------------------------------------------ the call: end to end with fake clients

class Echo:
    """Answers from the facts in the prompt: one correct sentence per car citing its price fact."""

    def __init__(self, break_car=None):
        self.calls, self.break_car = 0, break_car

    def complete(self, system, user, timeout):
        self.calls += 1
        data = json.loads(user)
        cars = []
        for c in data["cars"]:
            price = next(f for f in c["facts"] if f["text"].startswith("Ex-showroom price"))
            text = price["text"].split(" (")[0].replace("Ex-showroom price", "It is priced")
            sentence = f"{text}. [{price['id']}]"
            if c["id"] == self.break_car:
                sentence = f"It is priced at ₹1 lakh. [{price['id']}]"
            cars.append({"id": c["id"], "sentences": [sentence]})
        return L.ClientResult(json.dumps({"cars": cars}), 10, 10, "fake")


class Failing:
    def __init__(self, exc):
        self.exc, self.calls = exc, 0

    def complete(self, system, user, timeout):
        self.calls += 1
        raise self.exc


class Raw:
    def __init__(self, text):
        self.text = text

    def complete(self, system, user, timeout):
        return L.ClientResult(self.text)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv("LLM_PARSER_CACHE_FILE", raising=False)
    monkeypatch.delenv("RAG_EXPLAIN", raising=False)
    monkeypatch.setattr(L, "_sleep", lambda s: None)
    L.clear_cache(), L.reset_cap(), L.reset_pacing(), L.clear_eval(), R.reset_stats()
    R.CLIENT_OVERRIDE = None
    R.TRACE = None
    yield
    R.CLIENT_OVERRIDE = None
    R.TRACE = None
    L.clear_cache(), L.reset_cap(), L.reset_pacing(), L.clear_eval()


QUERY = "family suv under 15 lakh with sunroof"


def run(client, monkeypatch, query=QUERY):
    monkeypatch.setenv("RAG_EXPLAIN", "on")
    R.CLIENT_OVERRIDE = client
    return recommend(query, evidence=NO_EVIDENCE)


def test_rag_on_adds_explanation_only_for_passing_cars(monkeypatch):
    base = recommend(QUERY, evidence=NO_EVIDENCE)
    first = base["recommendations"][0]["variant_id"]
    resp = run(Echo(break_car=str(first)), monkeypatch)
    assert resp["rag"]["status"] == "ok"
    cards = resp["recommendations"]
    assert "explanation_rag" not in cards[0] and resp["rag"]["cars"][str(first)]["passed"] is False
    assert all("explanation_rag" in c for c in cards[1:])
    e = cards[1]["explanation_rag"]
    assert e["sentences"][0]["cites"] and set(e["facts"]) == {c for s in e["sentences"] for c in s["cites"]}
    assert all("label" in v and "source_url" in v for v in e["facts"].values())
    # template fields untouched
    for a, b in zip(base["recommendations"], cards):
        assert {k: v for k, v in b.items() if k != "explanation_rag"} == a


def test_rag_off_response_unchanged(monkeypatch):
    base = recommend(QUERY, evidence=NO_EVIDENCE)
    fake = Echo()
    R.CLIENT_OVERRIDE = fake
    monkeypatch.setenv("RAG_EXPLAIN", "off")
    off = recommend(QUERY, evidence=NO_EVIDENCE)
    assert json.dumps(off, sort_keys=True) == json.dumps(base, sort_keys=True)
    assert "rag" not in off and fake.calls == 0
    assert not any("explanation_rag" in c for c in off["recommendations"])


@pytest.mark.parametrize("exc,reason", [
    (L.LLMError("timeout"), "timeout"),
    (L.LLMError("quota", retry_after=30, cooldown=True), "quota"),
    (L.LLMError("http_error"), "http_error"),
])
def test_whole_call_falls_back_to_templates(monkeypatch, exc, reason):
    base = recommend(QUERY, evidence=NO_EVIDENCE)
    resp = run(Failing(exc), monkeypatch)
    assert resp["rag"]["status"] == "fallback" and resp["rag"]["reason"] == reason
    assert not any("explanation_rag" in c for c in resp["recommendations"])
    assert [c["match_reasons"] for c in resp["recommendations"]] == [c["match_reasons"] for c in base["recommendations"]]


def test_bad_json_and_bad_shape_fall_back(monkeypatch):
    resp = run(Raw("not json at all"), monkeypatch)
    assert resp["rag"]["reason"] == "invalid_json" and not any("explanation_rag" in c for c in resp["recommendations"])
    L.clear_cache()
    resp = run(Raw(json.dumps({"cars": [{"id": "999999", "sentences": ["x [f1]"]}]})), monkeypatch)
    assert resp["rag"]["reason"] == "shape:extra_car" and not any("explanation_rag" in c for c in resp["recommendations"])


def test_cooldown_and_rate_limit_skip_the_call(monkeypatch):
    c = Echo()
    L._note_failure(60.0)
    resp = run(c, monkeypatch)
    assert c.calls == 0 and resp["rag"]["reason"] == "cooldown"
    L.reset_pacing()
    monkeypatch.setenv("LLM_PARSER_RPM", "1")
    run(c, monkeypatch, "family suv under 15 lakh")
    L.clear_cache()
    resp = run(c, monkeypatch, "petrol hatchback under 8 lakh")
    assert resp["rag"]["reason"] == "rate_local"


def test_daily_cap(monkeypatch):
    monkeypatch.setenv("LLM_PARSER_DAILY_CAP", "0")
    resp = run(Echo(), monkeypatch)
    assert resp["rag"]["reason"] == "daily_cap"


def test_no_key_falls_back(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PARSER_BASE_URL", raising=False)
    monkeypatch.setenv("RAG_EXPLAIN", "on")
    resp = recommend(QUERY, evidence=NO_EVIDENCE)
    assert resp["rag"]["reason"] == "no_key" and not any("explanation_rag" in c for c in resp["recommendations"])


def test_cache_hit_costs_no_second_call(monkeypatch):
    c = Echo()
    run(c, monkeypatch)
    resp = run(c, monkeypatch)
    assert c.calls == 1 and resp["rag"]["cached"] is True and resp["rag"]["status"] == "ok"


def test_cached_answer_is_rechecked(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PARSER_CACHE_FILE", str(tmp_path / "c.json"))
    c = Echo()
    run(c, monkeypatch)
    cached = next(iter(json.loads((tmp_path / "c.json").read_text()).values()))
    assert "raw" in cached
    L.clear_cache()
    resp = run(c, monkeypatch)                         # from the disk cache
    assert c.calls == 1 and resp["rag"]["cached"] is True


def test_timeout_setting_is_passed_to_client(monkeypatch):
    seen = []

    class Spy(Echo):
        def complete(self, system, user, timeout):
            seen.append(timeout)
            return super().complete(system, user, timeout)

    monkeypatch.setenv("LLM_PARSER_TIMEOUT", "3.5")
    run(Spy(), monkeypatch)
    assert seen == [3.5]
    L.clear_cache()
    monkeypatch.setenv("RAG_EXPLAIN_TIMEOUT", "6")
    run(Spy(), monkeypatch)
    assert seen[-1] == 6.0


def test_one_call_per_query_for_all_cars(monkeypatch):
    c = Echo()
    resp = run(c, monkeypatch)
    assert c.calls == 1 and len(resp["rag"]["cars"]) == len(resp["recommendations"]) > 1


def test_prompt_contains_only_given_facts():
    cts, f1, _ = two_contexts()
    user = json.loads(R.build_user_prompt("q", cts))
    assert [c["id"] for c in user["cars"]] == ["7", "8"]
    assert {f["id"] for f in user["cars"][0]["facts"]} == {f.id for f in f1}
    assert "English" in R.build_system_prompt() and "[f2,f5]" in R.build_system_prompt()


def test_price_fact_carries_catalogue_source():
    price = [f for f in facts() if f.kind == "price"]
    assert len(price) == 1 and price[0].source == "CarRec catalogue"
    assert price[0].public()["source"] == "CarRec catalogue"


def test_eval_latency_summary_counts_live_calls_only():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("rag_eval", Path(__file__).resolve().parents[1] / "eval" / "rag_eval.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    rows = [{"rag": {"cached": False, "latency_ms": ms}} for ms in (1000, 3000, 5000, 9000)]
    rows.append({"rag": {"cached": True, "latency_ms": None}})
    s = ev.latency_summary(rows)
    assert s["calls"] == 4 and s["max"] == 9000 and s["p50"] in (3000, 5000)
    assert s["over_ms"] == {"2000": 3, "4000": 2, "6000": 1, "8000": 1}
    assert ev.latency_summary([{"rag": {"cached": True, "latency_ms": None}}]) == {"calls": 0}


def test_rejects_sentence_citing_only_the_query():
    fs = facts()
    q = fid(fs, "Your query asked for")
    out, why = check([f"It meets your requirement for an SUV under ₹15 lakh. [{q}]"], fs)
    assert out is None and "query_only_citation" in why


def test_fit_claim_needs_every_requirement_met():
    fs = facts()
    price, q = fid(fs, "Ex-showroom"), fid(fs, "Your query asked for")
    p = next(f for f in fs if f.id == price).text.split(": ", 1)[1].split(" (")[0]
    sent = [f"At {p} ex-showroom it fits your request. [{price},{q}]"]
    unmet = R.check_car(sent, R.CarContext("7", "Hyundai", "Creta", fs, fully_met=False), NAMES)
    assert unmet[0] is None and "fit_claim_with_unmet_requirement" in unmet[1]
    met = R.check_car(sent, R.CarContext("7", "Hyundai", "Creta", fs, fully_met=True), NAMES)
    assert met[0] is not None, met[1]

