"""LLM parser: validation, merge, fallbacks, cache, cap, stats. A fake client; no network, no key."""
import json
import threading

import pytest

from services.intent_v2 import parse_intent_ex
from services.recsys import llm_parse as L


class Fake:
    def __init__(self, answer=None, error=None, text=None):
        self.answer, self.error, self.text, self.calls = answer, error, text, 0

    def complete(self, system, user, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return L.ClientResult(self.text if self.text is not None else json.dumps(self.answer), 11, 7, "fake")


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("LLM_PARSER", "LLM_PARSER_CACHE_FILE", "LLM_PARSER_DAILY_CAP", "LLM_PARSER_TIMEOUT"):
        monkeypatch.delenv(k, raising=False)
    L.reset_stats(); L.clear_cache(); L.reset_cap()
    yield
    L.reset_stats(); L.clear_cache(); L.reset_cap()


def rules(q):
    return parse_intent_ex(q, use_ml=False)


def run(q, answer=None, client=None, **kw):
    intent, residual = rules(q)
    client = client or Fake(answer)
    out, info = L.refine(q, intent, residual, client=client)
    return out, info, client


def c(field, value, evidence):
    return {"field": field, "value": value, "evidence": evidence}


# ------------------------------------------------------------------ unexplained rule

def test_unexplained_rule():
    assert L.unexplained_tokens(rules("petrol automatic hatchback under 9 lakh chahiye")[1]) == []
    assert L.unexplained_tokens(rules("comfortable family car, good mileage, batao yaar")[1]) == []  # soft / use-case words
    assert "500" in L.unexplained_tokens(rules("boot mein kam se kam 500 litres wali sedan chahiye")[1])
    assert "can't" in L.unexplained_tokens(rules("a car I can't live without for 8 lakh")[1])
    assert L.unexplained_tokens(rules("cheapest suv")[1]) == []  # "cheap" inside a word must not leave "est"
    assert L.unexplained_tokens("") == [] and L.unexplained_tokens(None) == []


# ------------------------------------------------------------------ validate (pure)

Q = "need something with a rear camera mount and boot mein kam se kam 500 litres, no CVT"


def test_accepts_grounded_numeric_and_merges():
    q = "boot mein kam se kam 500 litres wali sedan chahiye"
    out, info, cl = run(q, {"constraints": [c("min_boot_space_litres", 500, "boot mein kam se kam 500 litres")]})
    assert out["min_boot_space_litres"] == 500 and out["body_types"] == ["sedan"]
    assert info["used"] and info["accepted"] == ["min_boot_space_litres=500"] and info["rejected"] == 0
    assert out["vague"] is False and any(t.startswith("llm:") for t in out["trace"])


def test_evidence_must_be_substring_case_insensitive():
    q = "boot mein kam se kam 500 litres wali sedan chahiye"
    out, info, _ = run(q, {"constraints": [c("min_boot_space_litres", 500, "BOOT MEIN  KAM SE KAM 500 LITRES")]})
    assert out["min_boot_space_litres"] == 500
    L.clear_cache()
    out, info, _ = run(q, {"constraints": [c("min_boot_space_litres", 500, "at least five hundred litres")]})
    assert out["min_boot_space_litres"] is None and info["rejected"] == 1
    assert info["rejected_detail"][0]["reason"] == "evidence_not_in_query"
    L.clear_cache()
    out, info, _ = run(q, {"constraints": [{"field": "min_boot_space_litres", "value": 500}]})
    assert info["rejected_detail"][0]["reason"] == "no_evidence"


def test_number_must_come_from_evidence():
    q = "boot space bada chahiye, sedan"
    out, info, _ = run(q, {"constraints": [c("min_boot_space_litres", 500, "boot space bada")]})
    assert out["min_boot_space_litres"] is None and info["rejected_detail"][0]["reason"] == "number_not_in_evidence"


@pytest.mark.parametrize("evidence,value,ok", [
    ("12 lakh", 1_200_000, True), ("12 lakh", 12, False), ("1.5 crore", 15_000_000, True), ("85k", 85_000, True),
    ("10-15 lakh", 1_000_000, True), ("ten lakh", 1_000_000, True), ("seven", 7, True), ("8,00,000", 800_000, True),
    ("12 lakh", 1_300_000, False), ("six seats", 7, False),
])
def test_number_grounding(evidence, value, ok):
    assert L.number_grounded(value, evidence) is ok


def test_budget_unit_derivation_through_validate():
    q = "kuch bhi chalega bas 12 lakh se upar nahi, xyzzy"
    v = L.validate(q, {"constraints": [c("budget_max", 1_200_000, "12 lakh se upar nahi")]}, rules("xyzzy")[0])
    assert [x["field"] for x in v["accepted"]] == ["budget_max"]
    v = L.validate(q, {"constraints": [c("budget_max", 12, "12 lakh se upar nahi")]}, rules("xyzzy")[0])
    assert v["rejected"][0]["reason"] in ("bad_value_range", "number_not_in_evidence")


def test_vocabulary_and_schema():
    q = "i want a plane, flying 500 mph"
    r = rules(q)[0]
    for bad, reason in [(c("fuel_include", "kerosene", "plane"), "not_in_vocabulary"),
                        (c("colour", "red", "plane"), "unknown_field"),
                        (c("seats_min", "seven", "plane"), "bad_value_type"),
                        (c("seats_min", 40, "plane"), "bad_value_range"),
                        (c("make_include", "Boeing", "plane"), "not_in_vocabulary")]:
        v = L.validate(q, {"constraints": [bad]}, r)
        assert not v["accepted"] and v["rejected"][0]["reason"] == reason
    assert L.validate(q, ["x"], r)["error"] == "schema"
    assert L.validate(q, {"constraints": "no"}, r)["error"] == "schema"


def test_contradiction_with_rules_rules_win():
    q = "no diesel please, bhai boot mein kam se kam 500 litres"
    intent, residual = rules(q)
    assert intent["exclude_fuel_types"] == ["diesel"]
    out, info = L.refine(q, intent, residual, client=Fake({"constraints": [
        c("fuel_include", "diesel", "diesel"), c("min_boot_space_litres", 500, "500 litres")]}))
    assert out["fuel_types"] == [] and out["exclude_fuel_types"] == ["diesel"]
    assert out["min_boot_space_litres"] == 500
    assert info["rejected"] == 1 and info["rejected_detail"][0]["reason"] == "contradicts_rules"
    assert L.stats()["rejected_constraints"] == {"contradicts_rules": 1}


def test_different_value_than_rules_scalar_rejected_and_duplicate_ignored():
    q = "diesel suv under 20 lakh, need 7 people, bhai xyzzy"
    intent, residual = rules(q)
    v = L.validate(q, {"constraints": [c("budget_max", 1_500_000, "20 lakh"),
                                       c("budget_max", 2_000_000, "20 lakh"),
                                       c("seats_min", 7, "7 people")]}, intent)
    assert v["duplicates"] >= 1
    assert v["rejected"][0]["reason"] == "number_not_in_evidence" or v["rejected"][0]["reason"] == "contradicts_rules"


def test_wishes_never_hard():
    q = "petrol hatchback with good mileage, comfortable, xyzzy"
    intent, residual = rules(q)
    v = L.validate(q, {"constraints": [c("min_mileage_kmpl", 25, "good mileage"),
                                       c("min_safety_stars", 5, "comfortable")],
                       "soft_preferences": ["mileage", "comfort", "teleportation"]}, intent)
    assert not v["accepted"]
    assert {r["reason"] for r in v["rejected"]} <= {"number_not_in_evidence", "wish_not_hard"}
    assert v["soft_preferences"] == ["mileage", "comfort"]
    # a wish phrased as a constraint with a matching evidence is converted into a soft preference
    v = L.validate("need good mileage", {"constraints": [c("fuel_include", "diesel", "good mileage")]}, rules("need good mileage")[0])
    assert v["rejected"][0]["reason"] == "wish_not_hard" and "mileage" in v["soft_preferences"]


def test_unevidenced_body_guess_is_at_most_assumed():
    q = "something sturdy for the hills xyzzy"
    out, info, _ = run(q, {"constraints": [c("body_include", "suv", "rugged mountain car")]})
    assert out["body_types"] == [] and out["assumed"]["body_types"] == ["suv"]
    assert info["rejected_detail"][0]["reason"] == "evidence_not_in_query"
    # ...but not when the rules already know the body type
    q = "sedan something sturdy for the hills xyzzy"
    out, info, _ = run(q, {"constraints": [c("body_include", "suv", "rugged")]})
    assert out["assumed"]["body_types"] == []


def test_self_contradiction_and_inconsistent_budget():
    q = "xyzzy 5 lakh to 3 lakh sunroof"
    v = L.validate(q, {"constraints": [c("fuel_include", "cng", "xyzzy"), c("fuel_exclude", "cng", "xyzzy")]}, rules(q)[0])
    assert not v["accepted"] and {r["reason"] for r in v["rejected"]} == {"self_contradiction"}
    q2 = "need something under 3 lakh xyzzy more than 5 lakh"
    v = L.validate("xyzzy at least 5 lakh, xyzzy 3 lakh max", {"constraints": [
        c("budget_min", 500_000, "at least 5 lakh"), c("budget_max", 300_000, "3 lakh max")]},
        rules("xyzzy")[0])
    assert not v["accepted"] and {r["reason"] for r in v["rejected"]} == {"inconsistent_budget"}


def test_evidence_too_long_rejected():
    q = "one two three four five six seven eight nine ten eleven twelve seats"
    v = L.validate(q, {"constraints": [c("seats_min", 7, q)]}, rules(q)[0])
    assert v["rejected"][0]["reason"] == "evidence_too_long"


def test_merge_transmission_and_lists_use_canonical_order():
    q = "xyzzy bina cvt, aur sunroof"
    intent, residual = rules(q)
    out, info = L.refine(q, intent, residual, client=Fake({"constraints": [
        c("transmission_exclude", "cvt", "bina cvt"), c("make_include", "Tata", "xyzzy")]}))
    assert "cvt" in out["transmission"]["exclude_types"]
    # the rule intent object itself is not mutated
    assert intent["makes"] == [] and out["makes"] == ["Tata"]


# ------------------------------------------------------------------ fallbacks: the request never fails

@pytest.mark.parametrize("client,reason", [
    (Fake(error=L.LLMError("timeout")), "timeout"),
    (Fake(error=L.LLMError("quota")), "quota"),
    (Fake(error=L.LLMError("http_error")), "http_error"),
    (Fake(text="this is not json"), "invalid_json"),
    (Fake(text="[1, 2]"), "invalid_json"),
    (Fake(answer={"constraints": "nope"}), "validation_failed"),
])
def test_fallback_keeps_rule_intent(client, reason):
    q = "bhai boot mein kam se kam 500 litres wali sedan chahiye"
    intent, residual = rules(q)
    out, info = L.refine(q, intent, residual, client=client)
    assert out is intent and not info["used"] and info["reason"] == reason
    assert L.stats()["fallbacks"] == {reason: 1}


def test_unexpected_exception_is_a_fallback_too():
    class Boom:
        def complete(self, *a):
            raise RuntimeError("boom")
    q = "bhai boot mein kam se kam 500 litres sedan"
    intent, residual = rules(q)
    out, info = L.refine(q, intent, residual, client=Boom())
    assert out is intent and info["reason"] == "internal_error"


def test_json_in_code_fence_is_accepted():
    q = "boot mein kam se kam 500 litres wali sedan chahiye"
    text = "```json\n" + json.dumps({"constraints": [c("min_boot_space_litres", 500, "500 litres")]}) + "\n```"
    out, info, _ = run(q, client=Fake(text=text))
    assert out["min_boot_space_litres"] == 500


# ------------------------------------------------------------------ gating, cache, cap, stats

def test_off_by_default_zero_calls(monkeypatch):
    called = []
    monkeypatch.setattr(L, "make_client", lambda: called.append(1) or Fake({}))
    q = "boot mein kam se kam 500 litres wali sedan chahiye"
    intent, residual = rules(q)
    out, info = L.refine(q, intent, residual)
    assert out is intent and info["reason"] == "off" and called == []
    assert L.stats()["llm_called"] == 0 and L.stats()["queries_seen"] == 1
    monkeypatch.setenv("LLM_PARSER", "off")
    L.refine(q, intent, residual)
    assert called == []


def test_on_but_query_fully_explained_makes_no_call(monkeypatch):
    monkeypatch.setenv("LLM_PARSER", "on")
    cl = Fake({"constraints": []})
    monkeypatch.setattr(L, "make_client", lambda: cl)
    q = "petrol automatic hatchback under 9 lakh"
    intent, residual = rules(q)
    out, info = L.refine(q, intent, residual)
    assert cl.calls == 0 and info["reason"] == "explained" and L.stats()["llm_considered"] == 0


def test_on_without_key_falls_back(monkeypatch):
    monkeypatch.setenv("LLM_PARSER", "on")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    q = "boot mein kam se kam 500 litres wali sedan chahiye"
    intent, residual = rules(q)
    out, info = L.refine(q, intent, residual)
    assert out is intent and info["reason"] == "no_key" and L.stats()["fallbacks"] == {"no_key": 1}


def test_cache_hit_in_memory_normalised_key():
    q = "boot mein kam se kam 500 litres wali sedan chahiye"
    ans = {"constraints": [c("min_boot_space_litres", 500, "500 litres")]}
    cl = Fake(ans)
    intent, residual = rules(q)
    L.refine(q, intent, residual, client=cl)
    out, info = L.refine("  BOOT mein   kam se kam 500 litres wali SEDAN chahiye ", intent, residual, client=cl)
    assert cl.calls == 1 and info["cached"] and out["min_boot_space_litres"] == 500
    s = L.stats()
    assert s["llm_called"] == 1 and s["cache_hits"] == 1


def test_disk_cache_survives_clear(monkeypatch, tmp_path):
    path = tmp_path / "cache.json"
    monkeypatch.setenv("LLM_PARSER_CACHE_FILE", str(path))
    q = "boot mein kam se kam 500 litres wali sedan chahiye"
    intent, residual = rules(q)
    L.refine(q, intent, residual, client=Fake({"constraints": [c("min_boot_space_litres", 500, "500 litres")]}))
    assert json.loads(path.read_text())[L.normalise_query(q)]["raw"]["constraints"]
    L.clear_cache()
    cl2 = Fake({"constraints": []})
    out, info = L.refine(q, intent, residual, client=cl2)
    assert cl2.calls == 0 and info["cached"] and out["min_boot_space_litres"] == 500


def test_lru_is_bounded():
    for i in range(L.LRU_SIZE + 5):
        L.cache_put(f"q{i}", {"raw": {}})
    assert len(L._lru) == L.LRU_SIZE and L.cache_get("q0") is None and L.cache_get(f"q{L.LRU_SIZE + 4}")


def test_daily_cap(monkeypatch):
    monkeypatch.setenv("LLM_PARSER_DAILY_CAP", "2")
    cl = Fake({"constraints": []})
    results = []
    for i in range(4):
        q = f"zzz{i} 500 litres boot sedan"
        intent, residual = rules(q)
        results.append(L.refine(q, intent, residual, client=cl)[1])
    assert cl.calls == 2 and [r["reason"] for r in results[2:]] == ["daily_cap", "daily_cap"]
    assert L.stats()["fallbacks"] == {"daily_cap": 2}
    # a new UTC day resets the count
    assert L._take_call_slot("2999-01-01") is True


def test_stats_counters_and_latency():
    cl = Fake({"constraints": [c("feature_include", "sunroof", "xyzzy"), c("fuel_include", "kerosene", "x")],
               "soft_preferences": ["comfort"]})
    q = "xyzzy sedan"
    intent, residual = rules(q)
    L.refine(q, intent, residual, client=cl)
    L.refine("petrol suv", rules("petrol suv")[0], rules("petrol suv")[1], client=cl)
    s = L.stats()
    assert s["queries_seen"] == 2 and s["llm_considered"] == 1 and s["llm_called"] == 1
    assert s["accepted_constraints"] == 1 and s["accepted_soft_preferences"] == 1
    assert s["rejected_constraints"] == {"not_in_vocabulary": 1}
    assert s["tokens_in"] == 11 and s["tokens_out"] == 7
    assert s["latency_ms_p50"] is not None and s["latency_ms_p95"] is not None
    L.reset_stats()
    assert L.stats()["queries_seen"] == 0


def test_stats_thread_safe():
    def work():
        for _ in range(500):
            L._stats.inc("queries_seen")
            L._stats.reject("x")
    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    s = L.stats()
    assert s["queries_seen"] == 4000 and s["rejected_total"] == 4000


# ------------------------------------------------------------------ clients (no network: transport stubbed)

def test_openai_and_gemini_clients_parse_responses(monkeypatch):
    seen = {}

    def fake_post(url, headers, body, timeout):
        seen["url"], seen["headers"], seen["body"] = url, headers, body
        if "generativelanguage" in url:
            return {"candidates": [{"content": {"parts": [{"text": "{\"constraints\": []}"}]}}],
                    "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2}}
        return {"choices": [{"message": {"content": "{\"constraints\": []}"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 1}}

    monkeypatch.setattr(L, "_post_json", fake_post)
    r = L.GeminiClient("m", "KEY").complete("sys", "hello", 2.0)
    assert (r.tokens_in, r.tokens_out) == (5, 2) and seen["body"]["generationConfig"]["temperature"] == 0
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json" and "KEY" not in seen["url"]
    r = L.OpenAICompatClient("https://x.test/v1/", "gpt", "KEY").complete("sys", "hello", 2.0)
    assert (r.tokens_in, r.tokens_out) == (3, 1) and seen["url"] == "https://x.test/v1/chat/completions"
    assert seen["body"]["temperature"] == 0 and seen["headers"]["Authorization"] == "Bearer KEY"


def test_make_client_from_env(monkeypatch):
    for k in ("LLM_PARSER_BASE_URL", "LLM_PARSER_KEY_ENV", "LLM_PARSER_MODEL", "LLM_PARSER_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    cl = L.make_client()
    assert isinstance(cl, L.GeminiClient) and cl.model == "gemini-3.5-flash-lite"
    monkeypatch.setenv("LLM_PARSER_BASE_URL", "https://api.example.test/openai/v1")
    monkeypatch.setenv("LLM_PARSER_KEY_ENV", "MY_KEY")
    monkeypatch.setenv("LLM_PARSER_MODEL", "openai/gpt-oss-120b")
    with pytest.raises(L.LLMError):
        L.make_client()  # MY_KEY unset
    monkeypatch.setenv("MY_KEY", "k2")
    cl = L.make_client()
    assert isinstance(cl, L.OpenAICompatClient) and cl.model == "openai/gpt-oss-120b"


def test_http_errors_map_to_reasons(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    def raise_429(*a, **k):
        raise urllib.error.HTTPError("https://u", 429, "Too Many", {}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", raise_429)
    with pytest.raises(L.LLMError) as e:
        L._post_json("https://u", {}, {}, 1.0)
    assert e.value.reason == "quota"

    def raise_500(*a, **k):
        raise urllib.error.HTTPError("https://u", 500, "x", {}, io.BytesIO(b""))
    monkeypatch.setattr(urllib.request, "urlopen", raise_500)
    with pytest.raises(L.LLMError) as e:
        L._post_json("https://u", {}, {}, 1.0)
    assert e.value.reason == "http_error"


def test_total_deadline_enforced():
    import time
    with pytest.raises(L.LLMError) as e:
        L._run_with_deadline(lambda: time.sleep(1.0), 0.05)
    assert e.value.reason == "timeout"


def test_prompt_contains_closed_vocabulary_and_evidence_rule():
    p = L.build_system_prompt()
    for word in ("petrol", "hatchback", "e_cvt", "ventilated_seats", "Maruti Suzuki", "min_boot_space_litres", "evidence"):
        assert word in p


# ------------------------------------------------------------------ api wiring

def test_api_response_has_llm_block_and_never_fails(monkeypatch):
    from services.recsys.api import recommend
    r = recommend("petrol automatic hatchback under 9 lakh")
    assert r["llm"]["used"] is False and r["llm"]["reason"] == "off" and "corrections" in r
    monkeypatch.setenv("LLM_PARSER", "on")
    monkeypatch.setattr(L, "make_client", lambda: Fake(error=L.LLMError("timeout")))
    r = recommend("boot mein kam se kam 500 litres wali sedan chahiye")
    assert r["recommendations"] and r["llm"]["reason"] == "timeout" and r["llm"]["used"] is False
    monkeypatch.setattr(L, "make_client", lambda: Fake({"constraints": [c("min_boot_space_litres", 500, "500 litres")]}))
    L.clear_cache()
    r = recommend("boot mein kam se kam 500 litres wali sedan chahiye")
    assert r["llm"]["used"] and r["llm"]["accepted"] == ["min_boot_space_litres=500"]
    assert r["intent"]["min_boot_space_litres"] == 500
    assert all((car["boot_space_litres"] or 500) >= 500 for car in r["recommendations"])
