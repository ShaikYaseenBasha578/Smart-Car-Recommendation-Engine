"""Optional LLM parser (plan section 4, "LLM parser (on)"). Off unless env LLM_PARSER=on.

The rule parser (services/intent_v2.py) is the only source of hard constraints by default. When the rules leave part of
the query unexplained, a small LLM is asked for ONE JSON object; each hard constraint it returns must quote the words
of the query that state it. `validate()` (pure) checks everything and `merge()` adds only what passed. Any failure
(timeout, quota, HTTP error, bad JSON, bad schema) leaves the rule intent untouched: the request never fails because
of the LLM.

"Unexplained" (see `unexplained_tokens`): the rule parser returns the RESIDUAL query, the typo-corrected lower-case text
with every span it consumed blanked (brands, models, features, numbers and budgets, gearbox, fuel, body, makes). From the
residual we remove known soft-preference and use-case phrases (they only set weights), then split into tokens. A token
is unexplained content when it is
  * a number left over (digits the number/budget rules did not take: "500 litres se zyada"), or
  * a modal negation (can't, cannot, won't ...: a limit the rules did not understand), or
  * a word of 3+ letters that is not in STOPWORDS (English function words, Hinglish fillers, request/framing words,
    unit words and plain negations that the rules handle themselves).
One such token is enough. Everything else (greetings, "chahiye", "batao", "car") is not.

Providers (env): LLM_PARSER_PROVIDER = gemini | openai (default: openai if LLM_PARSER_BASE_URL is set, else gemini).
  gemini: REST generateContent, model LLM_PARSER_MODEL (default gemini-3.5-flash-lite), key from LLM_PARSER_KEY_ENV
          (default GEMINI_API_KEY), JSON response mode.
  openai: OpenAI-compatible /chat/completions at LLM_PARSER_BASE_URL (e.g. https://api.groq.com/openai/v1), model
          LLM_PARSER_MODEL, key from the env var named by LLM_PARSER_KEY_ENV (e.g. GROQ_API_KEY).
Other env: LLM_PARSER_TIMEOUT (seconds, total, default 2.0), LLM_PARSER_DAILY_CAP (live calls per UTC day, default 400),
LLM_PARSER_CACHE_FILE (optional on-disk JSON cache of raw model answers, for evaluation runs).
Pacing: LLM_PARSER_RPM (live requests per minute, default 10, 0 = no local limit) is a token bucket; with no token the
request answers from the rules at once (fallback "rate_local"). After a 429 or 503 no call is made until Retry-After
(seconds or HTTP date), or a 30 s backoff doubling to 10 min, has passed (fallback "cooldown"); a success clears it.
Production never waits for either: only eval/run_eval.py (configure_eval) sleeps and retries.
Keys are read from the environment only and never logged.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from services import intent_v2 as iv

log = logging.getLogger("carrec.llm_parse")

DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_TIMEOUT = 2.0
DEFAULT_DAILY_CAP = 400
DEFAULT_RPM = 10          # conservative free-tier requests per minute; 0 turns the local limiter off
BACKOFF_START = 30.0      # seconds of cool-down after a 429/503 without Retry-After; doubles up to BACKOFF_MAX
BACKOFF_MAX = 600.0
RETRY_AFTER_MAX = 3600.0  # a larger Retry-After from the provider is clamped to this
LRU_SIZE = 2000
MAX_EVIDENCE_WORDS = 10

# --------------------------------------------------------------------------- vocabulary (closed)

MAKES = [label for label, _ in iv.MAKE_PATTERNS]
NUMERIC_FIELDS = {
    "min_airbags": int, "min_safety_stars": int, "min_boot_space_litres": int, "min_ground_clearance_mm": int,
    "min_ev_range_km": int, "min_mileage_kmpl": float, "min_mileage_km_per_kg": float,
    "max_ev_range_km": int, "max_ground_clearance_mm": int, "max_boot_space_litres": int,
    "max_mileage_kmpl": float, "max_mileage_km_per_kg": float,
}
BUDGET_FIELDS = ("budget_min", "budget_max", "budget_around")
LIST_FIELDS = {  # constraint field -> (vocabulary, intent key)
    "fuel_include": (iv.FUEL_TYPES, "fuel_types"), "fuel_exclude": (iv.FUEL_TYPES, "exclude_fuel_types"),
    "body_include": (iv.BODY_TYPES, "body_types"), "body_exclude": (iv.BODY_TYPES, "exclude_body_types"),
    "feature_include": (iv.FEATURES, "required_features"), "feature_exclude": (iv.FEATURES, "exclude_features"),
    "make_include": (MAKES, "makes"), "make_exclude": (MAKES, "exclude_makes"),
    "transmission_include": (iv.TRANSMISSION_TYPES, None), "transmission_exclude": (iv.TRANSMISSION_TYPES, None),
}
OPPOSITE = {"fuel_include": "fuel_exclude", "fuel_exclude": "fuel_include", "body_include": "body_exclude",
            "body_exclude": "body_include", "feature_include": "feature_exclude", "feature_exclude": "feature_include",
            "make_include": "make_exclude", "make_exclude": "make_include",
            "transmission_include": "transmission_exclude", "transmission_exclude": "transmission_include"}
ALL_FIELDS = (set(BUDGET_FIELDS) | set(NUMERIC_FIELDS) | set(LIST_FIELDS) | {"seats_min", "transmission_family"})
BUDGET_RUPEES = (50_000, 50_000_000)

# --------------------------------------------------------------------------- unexplained-content rule

STOPWORDS = set("""
a an the and or but nor so if then than that this these those it its is are was were be been being am do does did done
have has had having can could will would shall should may might must i me my mine we us our you your he she they them
their there here what which who whom whose when where why how not no yes any some all each every either neither both
of in on at by for with from to into onto over under about as like also just only very too really quite much many more
most less least few one ones another other such own same too again ever never always often sometimes already still yet
get got give gave find found show shown tell told want wanted wants need needed needs looking look looks suggest suggested
recommend recommended recommendation please pls kindly help helps hello hi hey thanks thank ok okay sir bro dude yaar
buy buying bought purchase purchasing car cars gaadi gadi gaadiyan vehicle vehicles option options model models variant
variants thing things something anything kind type types sort best better good great nice top new brand make makes
price prices cost lakh lakhs lac lacs crore crores thousand rupees rupee rs inr budget km kms kmpl mileage average
ke ka ki ko me mein se par pe hai hain ho hu hum hume humein mujhe mera meri mere main tum aap aapko apna apni
apne wala wali wale walo chahiye chaiye chahie chahta chahti chahiyega batao bataye bataiye bata dikhao dikha dijiye
do de dena karo kar kare karna kya kaun kaunsi kaunsa koi kuch kuchh aur ya bhi hi toh to bas sirf bhai
nahi nahin nhi mat na bina without avoid except excluding dont
ek yeh ye woh wo is us isme usme liye lie ke saath sath tak andar neeche upar zyada jyada kam
""".split())
MODAL_NEGATIONS = {"cant", "can't", "cannot", "wont", "won't", "shouldnt", "shouldn't", "couldnt", "couldn't",
                   "mustnt", "mustn't", "wouldnt", "wouldn't"}
_SOFT_SPANS = re.compile(iv.WORD.format("|".join(f"(?:{p})" for _, p in iv.SOFT_PREFERENCE_PATTERNS + iv.USE_CASE_PATTERNS)))
_RESIDUAL_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?|[a-z]+(?:'[a-z]+)?")


def unexplained_tokens(residual: str) -> List[str]:
    """Content tokens of the rule parser's residual that nothing explains (see the module docstring)."""
    text = _SOFT_SPANS.sub(" ", residual or "")
    out = []
    for tok in _RESIDUAL_TOKEN.findall(text):
        if tok[0].isdigit():
            out.append(tok)
        elif tok in MODAL_NEGATIONS:
            out.append(tok)
        elif len(tok) >= 3 and tok not in STOPWORDS:
            out.append(tok)
    return out


# --------------------------------------------------------------------------- stats

class Stats:
    """Thread-safe in-memory counters; `snapshot()` is what `stats()` returns."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self.counts: Counter = Counter()
            self.rejected: Counter = Counter()
            self.fallbacks: Counter = Counter()
            self.latencies: List[float] = []

    def inc(self, key: str, n: int = 1) -> None:
        with self._lock:
            self.counts[key] += n

    def reject(self, reason: str, n: int = 1) -> None:
        with self._lock:
            self.rejected[reason] += n

    def fallback(self, reason: str) -> None:
        with self._lock:
            self.fallbacks[reason] += 1

    def latency(self, ms: float) -> None:
        with self._lock:
            self.latencies.append(ms)
            del self.latencies[:-5000]

    @staticmethod
    def _pct(values: List[float], q: float) -> Optional[float]:
        if not values:
            return None
        s = sorted(values)
        return round(s[min(len(s) - 1, int(round(q * (len(s) - 1))))], 1)

    def snapshot(self) -> dict:
        with self._lock:
            c = self.counts
            return {
                "queries_seen": c["queries_seen"], "llm_considered": c["considered"], "llm_called": c["called"],
                "cache_hits": c["cache_hits"], "accepted_constraints": c["accepted"],
                "accepted_soft_preferences": c["accepted_soft"], "assumed_from_unevidenced": c["assumed"],
                "duplicates_of_rules": c["duplicates"], "responses_used": c["used"],
                "rejected_constraints": dict(self.rejected), "rejected_total": sum(self.rejected.values()),
                "fallbacks": dict(self.fallbacks), "fallbacks_total": sum(self.fallbacks.values()),
                "latency_ms_p50": self._pct(self.latencies, 0.5), "latency_ms_p95": self._pct(self.latencies, 0.95),
                "tokens_in": c["tokens_in"], "tokens_out": c["tokens_out"],
            }


_stats = Stats()


def stats() -> dict:
    return _stats.snapshot()


def reset_stats() -> None:
    _stats.reset()


# --------------------------------------------------------------------------- config / daily cap / caches

def _enabled() -> bool:
    return os.environ.get("LLM_PARSER", "off").strip().lower() == "on"


def _timeout() -> float:
    try:
        return float(os.environ.get("LLM_PARSER_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        return DEFAULT_TIMEOUT


def _daily_cap() -> int:
    try:
        return int(os.environ.get("LLM_PARSER_DAILY_CAP", DEFAULT_DAILY_CAP))
    except ValueError:
        return DEFAULT_DAILY_CAP


_cap_lock = threading.Lock()
_cap_state = {"day": None, "calls": 0}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _take_call_slot(today: Optional[str] = None) -> bool:
    """Count one live call against today's cap (UTC day, in-process). False when the cap is reached."""
    day = today or _today()
    with _cap_lock:
        if _cap_state["day"] != day:
            _cap_state.update(day=day, calls=0)
        if _cap_state["calls"] >= _daily_cap():
            return False
        _cap_state["calls"] += 1
        return True


def reset_cap() -> None:
    with _cap_lock:
        _cap_state.update(day=None, calls=0)


# --------------------------------------------------------------------------- pacing: token bucket + cool-down

def _rpm() -> float:
    try:
        return max(0.0, float(os.environ.get("LLM_PARSER_RPM", DEFAULT_RPM)))
    except ValueError:
        return float(DEFAULT_RPM)


def _now() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def parse_retry_after(value: Any, now: Optional[datetime] = None) -> Optional[float]:
    """Retry-After header: delta-seconds or an HTTP date. Seconds to wait (>= 0, clamped), or None when absent/bad."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        secs = float(text)
    except ValueError:
        try:
            when = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        secs = (when - (now or datetime.now(timezone.utc))).total_seconds()
    if secs != secs:  # NaN
        return None
    return min(max(secs, 0.0), RETRY_AFTER_MAX)


class TokenBucket:
    """Thread-safe token bucket: capacity = rpm tokens, refilled at rpm per minute. rpm <= 0 means unlimited."""

    def __init__(self, rpm: float, now: Optional[float] = None):
        self.rpm = rpm
        self._lock = threading.Lock()
        self._tokens = float(rpm)
        self._t = _now() if now is None else now

    def take(self, now: Optional[float] = None) -> float:
        """0.0 when a token was taken; otherwise the seconds until one will be available (nothing is taken)."""
        if self.rpm <= 0:
            return 0.0
        with self._lock:
            t = _now() if now is None else now
            self._tokens = min(float(self.rpm), self._tokens + max(0.0, t - self._t) * self.rpm / 60.0)
            self._t = t
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0
            return (1.0 - self._tokens) * 60.0 / self.rpm


_pace_lock = threading.Lock()
_bucket: Optional[TokenBucket] = None
_cool = {"until": 0.0, "backoff": 0.0}
_eval_cfg: Optional[dict] = None  # set by configure_eval(); None in production (never waits)


def _bucket_take() -> float:
    global _bucket
    rpm = _rpm()
    with _pace_lock:
        if _bucket is None or _bucket.rpm != rpm:
            _bucket = TokenBucket(rpm)
        b = _bucket
    return b.take()


def reset_pacing() -> None:
    global _bucket
    with _pace_lock:
        _bucket = None
        _cool.update(until=0.0, backoff=0.0)
        if _eval_cfg is not None:
            _eval_cfg.update(waited=0.0, last_call=None)


def cooldown_remaining() -> float:
    with _pace_lock:
        return max(0.0, _cool["until"] - _now())


def _note_failure(retry_after: Optional[float]) -> float:
    """Start a cool-down after a 429/503; returns its length in seconds."""
    with _pace_lock:
        if retry_after is not None:
            delay = retry_after
        else:
            _cool["backoff"] = min(BACKOFF_MAX, _cool["backoff"] * 2 if _cool["backoff"] else BACKOFF_START)
            delay = _cool["backoff"]
        _cool["until"] = _now() + delay
        return delay


def _note_success() -> None:
    with _pace_lock:
        _cool.update(until=0.0, backoff=0.0)


def configure_eval(pace: float = 0.0, max_wait: float = 1800.0) -> None:
    """Eval mode ONLY (eval/run_eval.py): wait out the limiter, cool-downs and a pause between live calls instead of
    falling back at once. `max_wait` is the total seconds the run may spend waiting; after that it falls back again."""
    global _eval_cfg
    _eval_cfg = {"pace": max(0.0, pace), "max_wait": max(0.0, max_wait), "waited": 0.0, "last_call": None}


def clear_eval() -> None:
    global _eval_cfg
    _eval_cfg = None


def eval_waited() -> float:
    return 0.0 if _eval_cfg is None else _eval_cfg["waited"]


def _pre_call_block() -> Optional[Tuple[str, float]]:
    """None when a live call may go out now (a limiter token is then taken); else (fallback reason, seconds to wait)."""
    left = cooldown_remaining()
    if left > 0:
        return "cooldown", left
    cfg = _eval_cfg
    if cfg is not None and cfg["pace"] > 0 and cfg["last_call"] is not None:
        gap = cfg["last_call"] + cfg["pace"] - _now()
        if gap > 0:
            return "pace", gap
    wait = _bucket_take()
    if wait > 0:
        return "rate_local", wait
    return None


def _eval_wait(seconds: float, counted: bool = True) -> bool:
    """Eval mode: sleep `seconds` if the wait budget allows. Always False in production."""
    cfg = _eval_cfg
    if cfg is None:
        return False
    if counted and cfg["waited"] + seconds > cfg["max_wait"]:
        return False
    if counted:
        cfg["waited"] += seconds
    _sleep(max(0.0, seconds))
    return True


def normalise_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").lower()).strip()


_lru: "OrderedDict[str, dict]" = OrderedDict()
_lru_lock = threading.Lock()
_disk: Dict[str, Any] = {"path": None, "data": {}}


def clear_cache() -> None:
    with _lru_lock:
        _lru.clear()
    _disk.update(path=None, data={})


def _disk_load(path: str) -> dict:
    if _disk["path"] != path:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            _disk.update(path=path, data=data if isinstance(data, dict) else {})
        except (OSError, ValueError):
            _disk.update(path=path, data={})
    return _disk["data"]


def _disk_store(path: str, key: str, entry: dict) -> None:
    with _lru_lock:
        data = _disk_load(path)
        data[key] = entry
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1, sort_keys=True, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as exc:
            log.warning("llm cache not written: %s", exc.__class__.__name__)


def cache_get(key: str) -> Optional[dict]:
    with _lru_lock:
        if key in _lru:
            _lru.move_to_end(key)
            return _lru[key]
        path = os.environ.get("LLM_PARSER_CACHE_FILE")
        if path:
            entry = _disk_load(path).get(key)
            if isinstance(entry, dict) and isinstance(entry.get("raw"), dict):
                _lru[key] = entry
                return entry
    return None


def cache_put(key: str, entry: dict) -> None:
    with _lru_lock:
        _lru[key] = entry
        _lru.move_to_end(key)
        while len(_lru) > LRU_SIZE:
            _lru.popitem(last=False)
    path = os.environ.get("LLM_PARSER_CACHE_FILE")
    if path:
        _disk_store(path, key, entry)


# --------------------------------------------------------------------------- prompt

def build_system_prompt() -> str:
    numeric = ", ".join(NUMERIC_FIELDS)
    return f"""You turn one car-buying query (English, Hinglish, possibly with typos) into constraints for a car search in India.
Answer with ONE JSON object and nothing else:
{{"constraints": [{{"field": <field>, "value": <value>, "evidence": <string>}}], "soft_preferences": [<word>]}}

Closed vocabulary. "field" must be one of:
- budget_max, budget_min, budget_around: value is a number of rupees (1 lakh = 100000, 1 crore = 10000000); "around/about X" is budget_around.
- fuel_include, fuel_exclude: one of {iv.FUEL_TYPES} (value is ONE word per constraint).
- body_include, body_exclude: one of {iv.BODY_TYPES}.
- transmission_family: "automatic" or "manual". transmission_include, transmission_exclude: one of {iv.TRANSMISSION_TYPES}.
- seats_min: integer, minimum number of seats.
- feature_include, feature_exclude: one of {iv.FEATURES}.
- make_include, make_exclude: one of {MAKES}.
- numeric minimums and maximums (value is a number): {numeric}. Mileage in kmpl is for petrol and diesel, in km/kg for CNG.
"soft_preferences" may only contain words from {iv.SOFT_PREFERENCES}.

Rules:
- Add a constraint ONLY when the user states it as a requirement. "evidence" must be the exact words copied from the query
  that state it (same spelling, including typos and Hinglish; at most {MAX_EVIDENCE_WORDS} words). If you cannot quote it, do not output it.
- Numbers must come from the evidence (digits or number words, with lakh/crore/k units). Never invent a number.
- Wishes such as "good mileage", "comfortable", "powerful" are NOT constraints: put them in soft_preferences.
- Do not guess what the user did not say. Do not output a constraint for a brand the list does not contain.
- Negations ("no sunroof", "not diesel", "diesel nahi") are *_exclude constraints.
- If the query states nothing you can quote, return {{"constraints": [], "soft_preferences": []}}.
Example: query "hatchbk jo 8 lakh se zyada na ho, sunroof ke bina" ->
{{"constraints": [{{"field": "budget_max", "value": 800000, "evidence": "8 lakh se zyada na ho"}}, {{"field": "body_include", "value": "hatchback", "evidence": "hatchbk"}}, {{"field": "feature_exclude", "value": "sunroof", "evidence": "sunroof ke bina"}}], "soft_preferences": []}}"""


# --------------------------------------------------------------------------- validation (pure)

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
                "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
                "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100}
_UNIT_VALUE = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "lkh": 1e5, "l": 1e5, "crore": 1e7, "crores": 1e7,
               "cr": 1e7, "k": 1e3, "thousand": 1e3}
_NUM_TOKEN = re.compile(r"(?<![a-z0-9.])(?:(\d[\d,]*(?:\.\d+)?)\s*(?:-\s*)?(lakhs?|lacs?|lkh|crores?|cr|thousand|k|l)?(?![a-z0-9])"
                        r"|([a-z]+)(?![a-z0-9])\s*(?:-\s*)?(lakhs?|lacs?|lkh|crores?|cr|thousand|k)?(?![a-z0-9]))", re.I)


def derivable_numbers(evidence: str) -> List[float]:
    """Numbers a reader can derive from the evidence: digits or number words, scaled by lakh/crore/k when a unit
    follows the number (or follows a later number of a range: "10-15 lakh")."""
    text = evidence.lower()
    found: List[Tuple[float, Optional[str]]] = []
    for m in _NUM_TOKEN.finditer(text):
        raw, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if raw[0].isdigit():
            value = float(raw.replace(",", ""))
        elif raw in NUMBER_WORDS:
            value = float(NUMBER_WORDS[raw])
        else:
            continue
        found.append((value, unit))
    units = [u for _, u in found]
    out: List[float] = []
    for i, (value, unit) in enumerate(found):
        unit = unit or next((u for u in units[i + 1:] if u), None)  # "10-15 lakh": the unit reaches back
        out.append(value * _UNIT_VALUE[unit] if unit else value)
    return out


def number_grounded(value: float, evidence: str) -> bool:
    return any(abs(value - cand) <= 1e-6 * max(1.0, abs(cand)) for cand in derivable_numbers(evidence))


class Rejection(Exception):
    def __init__(self, reason: str, retry_after: Optional[float] = None, cooldown: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after  # seconds from a Retry-After header, when the provider sent one
        self.cooldown = cooldown        # True for 429 / 503: stop calling for a while


def _wish_label(evidence: str) -> Optional[str]:
    for label, pattern in iv.SOFT_PREFERENCE_PATTERNS:
        if re.fullmatch(rf"\W*(?:{pattern})\W*", evidence.strip().lower()):
            return label
    return None


def _check_value(field: str, value: Any) -> Any:
    """Schema and vocabulary check; returns the cleaned value or raises Rejection."""
    if field in LIST_FIELDS:
        vocab = LIST_FIELDS[field][0]
        if not isinstance(value, str) or value not in vocab:
            raise Rejection("not_in_vocabulary")
        return value
    if field == "transmission_family":
        if value not in ("automatic", "manual"):
            raise Rejection("not_in_vocabulary")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Rejection("bad_value_type")
    if value != value or value <= 0:
        raise Rejection("bad_value_range")
    if field in BUDGET_FIELDS and not BUDGET_RUPEES[0] <= value <= BUDGET_RUPEES[1]:
        raise Rejection("bad_value_range")
    if field == "seats_min":
        if value != int(value) or not 2 <= value <= 12:
            raise Rejection("bad_value_range")
        return int(value)
    if field in NUMERIC_FIELDS:
        cast = NUMERIC_FIELDS[field]
        if field == "min_safety_stars" and not 1 <= value <= 5:
            raise Rejection("bad_value_range")
        if cast is int and value != int(value):
            raise Rejection("bad_value_type")
        return cast(value)
    return value


def _rules_conflict(field: str, value: Any, rules: dict) -> Optional[str]:
    """None when compatible; "duplicate" when the rules already have it; "contradicts_rules" otherwise."""
    trans = rules.get("transmission") or {}
    budget = rules.get("budget") or {}
    if field in LIST_FIELDS and field not in ("transmission_include", "transmission_exclude"):
        key = LIST_FIELDS[field][1]
        have = rules.get(key) or []
        opposite = rules.get(LIST_FIELDS[OPPOSITE[field]][1]) or []
        if value in opposite:
            return "contradicts_rules"
        if value in have:
            return "duplicate"
        if field.endswith("_include") and have:
            return "contradicts_rules"  # the rules already named a different choice: rules win
        return None
    if field in ("transmission_include", "transmission_exclude"):
        inc, exc = trans.get("include_types") or [], trans.get("exclude_types") or []
        same, other = (inc, exc) if field == "transmission_include" else (exc, inc)
        if value in other:
            return "contradicts_rules"
        if value in same:
            return "duplicate"
        return None
    if field == "transmission_family":
        have = trans.get("family")
        return None if not have else ("duplicate" if have == value else "contradicts_rules")
    if field in ("budget_min", "budget_max"):
        have = budget.get("min" if field == "budget_min" else "max")
        return None if have is None else ("duplicate" if abs(have - value) < 1 else "contradicts_rules")
    if field == "budget_around":
        if budget.get("min") is None and budget.get("max") is None:
            return None
        return "contradicts_rules"
    have = rules.get("seats_min" if field == "seats_min" else field)
    if have is None:
        return None
    return "duplicate" if abs(have - value) < 1e-9 else "contradicts_rules"


def validate(query: str, raw: Any, rules: dict) -> dict:
    """Pure. Returns {"accepted": [constraint], "rejected": [{field, value, reason}], "duplicates": n,
    "soft_preferences": [...], "assumed": {"body_types": [...], "fuel_types": [...]}}.

    A constraint is accepted only when: field and value are in the closed vocabulary; its evidence is a (case
    insensitive, whitespace-normalised) substring of the query, short, and not a mere wish; a numeric value is
    derivable from the evidence; it does not contradict the rules (rules win) or another accepted constraint."""
    result: Dict[str, Any] = {"accepted": [], "rejected": [], "duplicates": 0, "soft_preferences": [],
                              "assumed": {"body_types": [], "fuel_types": []}, "error": None}
    if not isinstance(raw, dict) or not isinstance(raw.get("constraints", []), list):
        result["error"] = "schema"
        return result
    q_norm = normalise_query(query)
    soft = list(result["soft_preferences"])

    def add_soft(label: Any) -> None:
        if label in iv.SOFT_PREFERENCES and label not in soft:
            soft.append(label)

    def reject(item: dict, reason: str) -> None:
        result["rejected"].append({"field": item.get("field"), "value": item.get("value"), "reason": reason})

    candidates = []
    for item in raw.get("constraints", []):
        if not isinstance(item, dict) or item.get("field") not in ALL_FIELDS:
            reject(item if isinstance(item, dict) else {}, "unknown_field")
            continue
        field = item["field"]
        try:
            value = _check_value(field, item.get("value"))
        except Rejection as exc:
            reject(item, exc.reason)
            continue
        evidence = item.get("evidence")
        ev_norm = normalise_query(evidence) if isinstance(evidence, str) else ""
        if not ev_norm or ev_norm not in q_norm:
            reject(item, "evidence_not_in_query" if ev_norm else "no_evidence")
            # unevidenced body/fuel guess: at most an "assumed" soft preference (never a filter)
            if field in ("fuel_include", "body_include"):
                kind = "fuel_types" if field == "fuel_include" else "body_types"
                if kind not in [k for k in ("fuel_types", "body_types")
                                if rules.get(LIST_FIELDS[field][1]) or rules.get(LIST_FIELDS[OPPOSITE[field]][1])]:
                    if value not in result["assumed"][kind]:
                        result["assumed"][kind].append(value)
            continue
        if len(ev_norm.split()) > MAX_EVIDENCE_WORDS:
            reject(item, "evidence_too_long")
            continue
        wish = _wish_label(ev_norm)
        if wish:
            reject(item, "wish_not_hard")
            add_soft(wish)
            continue
        if field in NUMERIC_FIELDS or field in BUDGET_FIELDS or field == "seats_min":
            if not number_grounded(float(value), ev_norm):
                reject(item, "number_not_in_evidence")
                continue
        conflict = _rules_conflict(field, value, rules)
        if conflict == "duplicate":
            result["duplicates"] += 1
            continue
        if conflict:
            reject(item, conflict)
            continue
        candidates.append({"field": field, "value": value, "evidence": ev_norm})

    # internal consistency: the same value both included and excluded -> reject both
    clash = {(c["field"], c["value"]) for c in candidates
             if c["field"] in OPPOSITE and any(o["field"] == OPPOSITE[c["field"]] and o["value"] == c["value"]
                                               for o in candidates)}
    for c in candidates:
        if (c["field"], c["value"]) in clash:
            reject(c, "self_contradiction")
        else:
            result["accepted"].append(c)
    # budget range must stay consistent with the rules' other bound and the other accepted bound
    budget = dict(rules.get("budget") or {})
    for c in [c for c in result["accepted"] if c["field"] in ("budget_min", "budget_max")]:
        budget["min" if c["field"] == "budget_min" else "max"] = c["value"]
    if budget.get("min") is not None and budget.get("max") is not None and budget["min"] >= budget["max"]:
        for c in [c for c in result["accepted"] if c["field"] in ("budget_min", "budget_max")]:
            result["accepted"].remove(c)
            reject(c, "inconsistent_budget")

    for label in raw.get("soft_preferences") or []:
        add_soft(label)
    result["soft_preferences"] = soft
    return result


# --------------------------------------------------------------------------- merge

def merge(rules: dict, verdict: dict) -> dict:
    """A copy of the rule intent plus the accepted constraints, soft preferences and assumed guesses."""
    out = copy.deepcopy(rules)
    out.setdefault("assumed", {"body_types": [], "fuel_types": []})
    trace = out.setdefault("trace", [])
    trans = out["transmission"]
    for c in verdict["accepted"]:
        field, value = c["field"], c["value"]
        if field == "budget_min":
            out["budget"]["min"] = int(value)
        elif field == "budget_max":
            out["budget"]["max"] = int(value)
        elif field == "budget_around":
            out["budget"]["min"] = round(value * (1 - iv.AROUND_BAND))
            out["budget"]["max"] = round(value * (1 + iv.AROUND_BAND))
        elif field == "seats_min" or field in NUMERIC_FIELDS:
            out[field] = value
        elif field == "transmission_family":
            trans["family"] = value
        elif field in ("transmission_include", "transmission_exclude"):
            key = "include_types" if field == "transmission_include" else "exclude_types"
            trans[key] = [t for t in iv.TRANSMISSION_TYPES if t in set(trans[key]) | {value}]
            if field == "transmission_include" and trans["family"] is None:
                trans["family"] = "manual" if value in ("manual", "imt") else "automatic"
        else:
            vocab, key = LIST_FIELDS[field]
            out[key] = [v for v in vocab if v in set(out[key]) | {value}]
            if field in ("fuel_include", "body_include"):  # an explicit statement replaces the ML guess
                out["assumed"]["fuel_types" if field == "fuel_include" else "body_types"] = []
        trace.append(f"llm: {field}={value} <- evidence '{c['evidence']}'")
    for label in verdict["soft_preferences"]:
        if label not in out["soft_preferences"]:
            out["soft_preferences"] = [s for s in iv.SOFT_PREFERENCES if s in set(out["soft_preferences"]) | {label}]
            trace.append(f"llm: soft preference {label}")
    for kind, values in verdict["assumed"].items():
        if values and not out["assumed"].get(kind):
            out["assumed"][kind] = list(values)
            trace.append(f"llm: assumed {kind}={values} (no usable evidence; soft only)")
    if verdict["accepted"]:
        out["vague"], out["unsupported_only"] = iv._classify_content(out)
    return out


# --------------------------------------------------------------------------- clients

class LLMError(Exception):
    """A failure to get an answer; `reason` is the fallback label (timeout, quota, http_error, no_key, ...)."""

    def __init__(self, reason: str, retry_after: Optional[float] = None, cooldown: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after  # seconds from a Retry-After header, when the provider sent one
        self.cooldown = cooldown        # True for 429 / 503: stop calling for a while


class ClientResult:
    def __init__(self, text: str, tokens_in: Optional[int] = None, tokens_out: Optional[int] = None, model: str = ""):
        self.text, self.tokens_in, self.tokens_out, self.model = text, tokens_in, tokens_out, model


UA = "carrec-recsys/1.0"


def _post_json(url: str, headers: dict, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA, **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        retry_after = parse_retry_after(exc.headers.get("Retry-After") if exc.headers is not None else None)
        raise LLMError("quota" if exc.code == 429 else "http_error", retry_after=retry_after,
                       cooldown=exc.code in (429, 503)) from None  # never echo headers/URL
    except (TimeoutError, OSError) as exc:  # URLError and socket.timeout are OSErrors
        raise LLMError("timeout" if "timed out" in str(exc).lower() else "network_error") from None
    except ValueError:
        raise LLMError("invalid_json") from None


def _run_with_deadline(fn: Callable[[], Any], seconds: float) -> Any:
    """Run fn in a daemon thread and give up after `seconds` in total (the socket timeout alone does not cover DNS)."""
    box: Dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised below in the caller
            box["error"] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise LLMError("timeout")
    if "error" in box:
        raise box["error"]
    return box["value"]


class GeminiClient:
    def __init__(self, model: str, key: str):
        self.model, self._key = model, key

    def complete(self, system: str, user: str, timeout: float) -> ClientResult:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
        data = _run_with_deadline(lambda: _post_json(url, {"x-goog-api-key": self._key}, body, timeout), timeout)
        try:
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            raise LLMError("invalid_json") from None
        usage = data.get("usageMetadata") or {}
        return ClientResult(text, usage.get("promptTokenCount"), usage.get("candidatesTokenCount"), self.model)


class OpenAICompatClient:
    def __init__(self, base_url: str, model: str, key: str):
        self.base_url, self.model, self._key = base_url.rstrip("/"), model, key

    def complete(self, system: str, user: str, timeout: float) -> ClientResult:
        body = {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        data = _run_with_deadline(lambda: _post_json(self.base_url + "/chat/completions",
                                                     {"Authorization": f"Bearer {self._key}"}, body, timeout), timeout)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("invalid_json") from None
        usage = data.get("usage") or {}
        return ClientResult(text, usage.get("prompt_tokens"), usage.get("completion_tokens"), self.model)


def make_client() -> Any:
    """Client from the environment; raises LLMError("no_key") when the key variable is unset."""
    base_url = os.environ.get("LLM_PARSER_BASE_URL", "").strip()
    provider = os.environ.get("LLM_PARSER_PROVIDER", "openai" if base_url else "gemini").strip().lower()
    model = os.environ.get("LLM_PARSER_MODEL", "").strip() or DEFAULT_MODEL
    key_env = os.environ.get("LLM_PARSER_KEY_ENV", "").strip() or ("GEMINI_API_KEY" if provider == "gemini" else "")
    key = os.environ.get(key_env, "") if key_env else ""
    if not key:
        raise LLMError("no_key")
    if provider == "gemini":
        return GeminiClient(model, key)
    if provider == "openai" and base_url:
        return OpenAICompatClient(base_url, model, key)
    raise LLMError("bad_config")


# --------------------------------------------------------------------------- orchestration

def _parse_model_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        obj = json.loads(text)
    except ValueError:
        raise LLMError("invalid_json") from None
    if not isinstance(obj, dict):
        raise LLMError("invalid_json")
    return obj


def _info(**kw: Any) -> dict:
    base = {"used": False, "accepted": [], "rejected": 0, "latency_ms": None, "reason": None, "cached": False}
    base.update(kw)
    return base


def refine(query: str, rules: dict, residual: str, client: Any = None) -> Tuple[dict, dict]:
    """(intent, llm info). `intent` is `rules` itself unless accepted LLM constraints / preferences were merged.
    Never raises because of the LLM."""
    _stats.inc("queries_seen")
    try:
        return _refine(query, rules, residual, client)
    except Exception as exc:  # noqa: BLE001 - the request must never fail because of the LLM
        _stats.fallback("internal_error")
        log.warning("llm parser internal error: %s", exc.__class__.__name__)
        return rules, _info(reason="internal_error")


def _refine(query: str, rules: dict, residual: str, client: Any) -> Tuple[dict, dict]:
    if client is None and not _enabled():
        return rules, _info(reason="off")
    tokens = unexplained_tokens(residual)
    if not tokens:
        return rules, _info(reason="explained")
    _stats.inc("considered")
    key = normalise_query(query)
    entry = cache_get(key)
    latency_ms: Optional[float] = None
    cached = entry is not None
    if cached:
        _stats.inc("cache_hits")
        raw = entry["raw"]
    else:
        res = None
        while res is None:
            block = _pre_call_block()
            if block is not None:
                reason, wait = block
                if _eval_wait(wait, counted=(reason != "pace")):
                    continue
                _stats.fallback(reason)
                return rules, _info(reason=reason)
            if not _take_call_slot():
                _stats.fallback("daily_cap")
                return rules, _info(reason="daily_cap")
            try:
                cl = client if client is not None else make_client()
                t0 = time.monotonic()
                _stats.inc("called")
                try:
                    res = cl.complete(build_system_prompt(), query, _timeout())
                finally:
                    latency_ms = (time.monotonic() - t0) * 1000.0
                    _stats.latency(latency_ms)
                    if _eval_cfg is not None:
                        _eval_cfg["last_call"] = _now()
                raw = _parse_model_json(res.text)
            except LLMError as exc:
                res = None
                if exc.cooldown:
                    delay = _note_failure(exc.retry_after)
                    if _eval_wait(delay):  # eval only: wait out the cool-down and ask the same query again
                        continue
                _stats.fallback(exc.reason)
                log.info("llm parser fallback: %s", exc.reason)
                return rules, _info(reason=exc.reason, latency_ms=None if latency_ms is None else round(latency_ms, 1))
        _note_success()
        for k, v in (("tokens_in", res.tokens_in), ("tokens_out", res.tokens_out)):
            if isinstance(v, int):
                _stats.inc(k, v)
        cache_put(key, {"raw": raw, "model": res.model, "tokens_in": res.tokens_in, "tokens_out": res.tokens_out})

    verdict = validate(query, raw, rules)
    if verdict["error"]:
        _stats.fallback("validation_failed")
        return rules, _info(reason="validation_failed", cached=cached,
                            latency_ms=None if latency_ms is None else round(latency_ms, 1))
    for r in verdict["rejected"]:
        _stats.reject(r["reason"])
        log.info("llm constraint rejected: %s %s", r["field"], r["reason"])
    _stats.inc("accepted", len(verdict["accepted"]))
    _stats.inc("accepted_soft", len(verdict["soft_preferences"]))
    _stats.inc("assumed", sum(len(v) for v in verdict["assumed"].values()))
    _stats.inc("duplicates", verdict["duplicates"])
    _stats.inc("used")
    merged = merge(rules, verdict)
    return merged, _info(
        used=True, cached=cached, accepted=[f"{c['field']}={c['value']}" for c in verdict["accepted"]],
        rejected=len(verdict["rejected"]), rejected_detail=verdict["rejected"],
        soft_preferences=verdict["soft_preferences"], latency_ms=None if latency_ms is None else round(latency_ms, 1))
