"""LLM parser pacing: token bucket, Retry-After, cool-down, eval-only waiting and resume. Fake clock and client; no
network, no key, no real sleep."""
import io
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from services.intent_v2 import parse_intent_ex
from services.recsys import llm_parse as L

ANSWER = {"constraints": []}


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class Fake:
    """Replays `script`: an LLMError instance is raised, anything else is the JSON answer. Last item repeats."""

    def __init__(self, *script):
        self.script, self.calls, self.timeouts = list(script) or [ANSWER], 0, []

    def complete(self, system, user, timeout):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        self.timeouts.append(timeout)
        if isinstance(item, Exception):
            raise item
        return L.ClientResult(json.dumps(item), 5, 3, "fake")


def throttled(retry_after=None, reason="quota"):
    return L.LLMError(reason, retry_after=retry_after, cooldown=True)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("LLM_PARSER", "LLM_PARSER_CACHE_FILE", "LLM_PARSER_DAILY_CAP", "LLM_PARSER_TIMEOUT", "LLM_PARSER_RPM"):
        monkeypatch.delenv(k, raising=False)
    clock = Clock()
    monkeypatch.setattr(L, "_now", clock.now)
    monkeypatch.setattr(L, "_sleep", clock.sleep)
    L.clear_eval(); L.reset_stats(); L.clear_cache(); L.reset_cap(); L.reset_pacing()
    yield clock
    L.clear_eval(); L.reset_stats(); L.clear_cache(); L.reset_cap(); L.reset_pacing()


def ask(i, client):
    q = f"zzz{i} 500 litres boot sedan"
    intent, residual = parse_intent_ex(q, use_ml=False)
    return L.refine(q, intent, residual, client=client)[1]


# ------------------------------------------------------------------ token bucket

def test_bucket_refuses_when_empty_and_refills(clean):
    b = L.TokenBucket(6, now=clean.t)  # 6 per minute = one token every 10 s, burst 6
    assert [b.take(clean.t) for _ in range(6)] == [0.0] * 6
    wait = b.take(clean.t)
    assert 9.9 < wait <= 10.0
    assert b.take(clean.t + 5) > 0           # half a token is not enough
    assert b.take(clean.t + 10) == 0.0        # one token is back
    assert L.TokenBucket(0).take() == 0.0     # rpm 0 = unlimited


def test_refine_falls_back_rate_local_without_calling_or_sleeping(monkeypatch, clean):
    monkeypatch.setenv("LLM_PARSER_RPM", "2")
    cl = Fake()
    reasons = [ask(i, cl)["reason"] for i in range(4)]
    assert cl.calls == 2
    assert reasons[2:] == ["rate_local", "rate_local"]
    assert L.stats()["fallbacks"] == {"rate_local": 2}
    assert clean.slept == []                  # production never waits
    clean.t += 31                             # one token refilled
    assert ask(9, cl)["reason"] != "rate_local" and cl.calls == 3


def test_default_rpm_is_conservative(monkeypatch):
    assert L._rpm() == L.DEFAULT_RPM == 10
    monkeypatch.setenv("LLM_PARSER_RPM", "junk")
    assert L._rpm() == 10


# ------------------------------------------------------------------ Retry-After

def test_retry_after_seconds():
    assert L.parse_retry_after("17") == 17.0
    assert L.parse_retry_after(" 2.5 ") == 2.5
    assert L.parse_retry_after("-4") == 0.0
    assert L.parse_retry_after("999999") == L.RETRY_AFTER_MAX
    for bad in (None, "", "soon", "nan"):
        assert L.parse_retry_after(bad) is None


def test_retry_after_http_date():
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)
    assert L.parse_retry_after(format_datetime(now + timedelta(seconds=45), usegmt=True), now=now) == 45.0
    assert L.parse_retry_after(format_datetime(now - timedelta(seconds=45), usegmt=True), now=now) == 0.0


@pytest.mark.parametrize("code,reason,cooldown", [(429, "quota", True), (503, "http_error", True), (500, "http_error", False)])
def test_post_json_reads_retry_after(monkeypatch, code, reason, cooldown):
    def boom(*a, **k):
        raise urllib.error.HTTPError("https://u", code, "x", {"Retry-After": "12"}, io.BytesIO(b""))
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(L.LLMError) as e:
        L._post_json("https://u", {"x-goog-api-key": "SECRET"}, {}, 1.0)
    assert (e.value.reason, e.value.cooldown, e.value.retry_after) == (reason, cooldown, 12.0)
    assert "SECRET" not in str(e.value) and "https://u" not in str(e.value)


# ------------------------------------------------------------------ cool-down

def test_cooldown_blocks_calls_then_clears_on_success(monkeypatch, clean):
    monkeypatch.setenv("LLM_PARSER_RPM", "0")
    cl = Fake(throttled(retry_after=20), ANSWER)
    assert ask(0, cl)["reason"] == "quota"                  # the 429 itself
    assert 19 < L.cooldown_remaining() <= 20
    assert ask(1, cl)["reason"] == "cooldown" and cl.calls == 1   # no call during the cool-down
    clean.t += 21
    assert L.cooldown_remaining() == 0
    assert ask(2, cl)["reason"] is None and cl.calls == 2   # call goes out again, succeeds
    assert L._cool == {"until": 0.0, "backoff": 0.0}
    assert L.stats()["fallbacks"] == {"quota": 1, "cooldown": 1}
    assert clean.slept == []


def test_default_backoff_doubles_to_cap_and_success_resets(monkeypatch, clean):
    monkeypatch.setenv("LLM_PARSER_RPM", "0")
    cl = Fake(throttled())  # always 429, no Retry-After
    seen = []
    for i in range(8):
        ask(i, cl)
        seen.append(L._cool["backoff"])
        clean.t += L.cooldown_remaining() + 1
    assert seen == [30, 60, 120, 240, 480, 600, 600, 600]
    cl.script = [ANSWER]
    cl.calls = 0
    ask(99, cl)
    assert L._cool["backoff"] == 0.0


# ------------------------------------------------------------------ timeout budget

def test_request_never_exceeds_timeout_budget(monkeypatch, clean):
    monkeypatch.setenv("LLM_PARSER_TIMEOUT", "1.5")
    monkeypatch.setenv("LLM_PARSER_RPM", "1")
    cl = Fake()
    ask(0, cl)
    assert cl.timeouts == [1.5]                              # the provider call gets the existing timeout, nothing more
    assert ask(1, cl)["reason"] == "rate_local"              # limiter refuses at once instead of waiting
    assert clean.slept == [] and cl.calls == 1


# ------------------------------------------------------------------ eval mode: wait, retry, resume

def test_eval_waits_out_429_and_retries_same_query(clean):
    L.configure_eval(pace=0, max_wait=100)
    monkey_rpm_off = None  # noqa: F841
    cl = Fake(throttled(retry_after=7), ANSWER)
    info = ask(0, cl)
    assert info["reason"] is None and cl.calls == 2
    assert clean.slept == [7] and L.eval_waited() == 7
    assert L.stats()["fallbacks_total"] == 0


def test_eval_gives_up_after_max_total_wait(clean):
    L.configure_eval(pace=0, max_wait=10)
    cl = Fake(throttled(retry_after=8))
    info = ask(0, cl)                       # waits 8, retries, 429 again, 8 more would exceed 10
    assert info["reason"] == "quota" and cl.calls == 2 and L.eval_waited() == 8
    assert ask(1, cl)["reason"] == "cooldown"   # budget spent: immediate fallback, no more sleeping
    assert clean.slept == [8]


def test_eval_pace_spaces_live_calls(clean):
    L.configure_eval(pace=5, max_wait=100)
    cl = Fake()
    for i in range(3):
        ask(i, cl)
    assert cl.calls == 3 and clean.slept == [5, 5]
    assert L.eval_waited() == 0             # pacing is not counted against the 429 wait budget


def test_eval_rate_limit_waits_for_token(monkeypatch, clean):
    monkeypatch.setenv("LLM_PARSER_RPM", "1")
    L.configure_eval(pace=0, max_wait=100)
    cl = Fake()
    ask(0, cl)
    assert ask(1, cl)["reason"] is None and cl.calls == 2
    assert 59 < clean.slept[0] <= 60


def test_eval_resume_uses_cache(monkeypatch, tmp_path, clean):
    cache = tmp_path / "cache.json"
    monkeypatch.setenv("LLM_PARSER_CACHE_FILE", str(cache))
    monkeypatch.setenv("LLM_PARSER_RPM", "0")
    L.configure_eval(pace=0, max_wait=0)    # no waiting allowed: the run stops answering after the first 429
    cl = Fake(ANSWER, ANSWER, throttled(retry_after=50))
    first = [ask(i, cl)["reason"] for i in range(4)]
    assert first == [None, None, "quota", "cooldown"] and cl.calls == 3
    assert len(json.loads(cache.read_text())) == 2          # answered queries are on disk
    # a new process: memory cleared, cool-down over; the same command continues
    L.clear_cache(); L.reset_stats(); L.reset_pacing(); L.reset_cap()
    cl2 = Fake(ANSWER)
    second = [ask(i, cl2) for i in range(4)]
    assert [i["cached"] for i in second] == [True, True, False, False]
    assert cl2.calls == 2                                    # only the two unanswered queries went out
    assert L.stats()["cache_hits"] == 2


def test_production_never_waits_on_429(clean):
    cl = Fake(throttled(retry_after=5))
    assert ask(0, cl)["reason"] == "quota"
    assert clean.slept == [] and cl.calls == 1
