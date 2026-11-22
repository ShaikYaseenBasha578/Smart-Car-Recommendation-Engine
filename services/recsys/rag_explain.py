"""Grounded, cited explanations (plan C). Off unless env RAG_EXPLAIN=on; when off nothing here runs and the response is
exactly what it was before.

Flow for one query: services/recsys/facts.py lists, per shown car, the facts the engine actually has (ids f1..fN). ONE LLM
call (JSON mode, the same provider, pacing, daily cap and answer cache as the LLM parser in llm_parse.py) writes 1-3 short
sentences per car, each ending with the fact ids it rests on, like "[f2,f5]". `check_car` (pure, deterministic) then
decides, per car, whether that text may be shown. A car whose text fails keeps the template explanation, and so does every
car when the call is skipped or fails (timeout, quota, cool-down, local rate limit, daily cap, no key, bad JSON). The
request never waits longer than the LLM timeout (RAG_EXPLAIN_TIMEOUT, else LLM_PARSER_TIMEOUT, default 2 s) and the
template fields of the response are never changed: the page adds `explanation_rag` to a card only when that car passed.

The checker rules (all must hold for a car; any failure -> that car falls back; reasons are recorded):
  shape            the car's entry has a list of 1-3 sentences, each a string (or {"text","cites"}), at most 240 characters
  citation         every sentence cites at least one fact id, and every id exists for THAT car
  number           every number (value and, when written, unit) occurs in the cited facts' numeric tokens; lakh / crore / "₹"
                   are normalised to rupees (a figure in lakh may carry two decimals), thousands separators are ignored,
                   spelled numbers ("five stars") count; the car's own make and model are removed first ("XUV700")
  name             no other make or model of the catalogue is named
  safety           safety / crash / NCAP / star wording only if a cited fact is the crash-test row (or its "unknown" row)
  comparison       a comparative or superlative word (best, better, than, most, top...) only if a cited fact contains that word
  feature          a named feature (sunroof, ADAS, cruise control...) must appear in a cited fact; fuel, gearbox and body
                   words must appear in some fact of the car
  absence          "lacks", "without", "missing"... only if a cited fact is an "Unknown: ..." fact or contains the word
Whole response: the JSON must be an object {"cars": [{"id": ..., "sentences": [...]}]}; a car id that was not shown, or
the same id twice, rejects the whole response (every car falls back); a shown car with no entry falls back on its own.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.recsys import llm_parse
from services.recsys.explain import BOOL_LABELS
from services.recsys.facts import (COMPARING_KINDS, NCAP_KINDS, Fact, build_facts, facts_hash, numeric_tokens,
                                   token_matches)

log = logging.getLogger("carrec.rag_explain")

PROMPT_VERSION = "rag1"
MAX_SENTENCES = 3
MAX_SENTENCE_CHARS = 240
CITE_RE = re.compile(r"\[\s*(f\d+(?:\s*,\s*f\d+)*)\s*\]", re.IGNORECASE)
SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9₹\"“])|(?<=\])\s+(?=[A-Z0-9₹\"“])")

# a model name that is also an everyday word is matched only as written (capitalised) and not as a sentence's first word
COMMON_WORD_MODELS = {"city", "safari", "punch", "compass", "polo", "rapid", "jazz", "brio", "zest", "bolt", "vento",
                      "star", "prime", "legend", "sense", "fusion", "wave", "ace", "one", "go", "tour", "alto", "aura"}

SAFETY_RE = re.compile(r"\b(safe\w*|safety|ncap|crash\w*|collision|stars?)\b|\d\s*-\s*stars?", re.IGNORECASE)
COMPARATIVE_RE = re.compile(
    r"\b(best|better|cheapest|cheaper|highest|lowest|most|top|leading|leader|class-leading|outperform\w*|beats?|rivals?|"
    r"than|segment|fastest|safest|biggest|largest|smallest|finest|superior|unmatched|unrivalled|unrivaled|ahead|compared|"
    r"competitors?|alternatives?|unlike|whereas)\b|\bother cars\b", re.IGNORECASE)
ABSENCE_RE = re.compile(r"\b(lacks?|lacking|without|missing|absent|doesn't|does not|do not|isn't|is not|not have|"
                        r"no)\b", re.IGNORECASE)
FEATURE_TERMS = sorted({v.lower() for v in BOOL_LABELS.values()} | {
    "sunroof", "cruise control", "adas", "360", "ventilated", "wireless charging", "head-up", "heads-up", "android auto",
    "carplay", "apple carplay", "connected-car", "turbo", "paddle shifters", "isofix", "autonomous braking",
    "parking sensors", "rear camera", "reverse camera", "touchscreen", "air purifier", "leather"}, key=len, reverse=True)
ATTRIBUTE_TERMS = ["petrol", "diesel", "cng", "electric", "hybrid", "automatic", "manual", "dct", "cvt", "amt", "imt",
                   "suv", "hatchback", "sedan", "mpv", "pickup", "4x4", "awd"]


def _word_re(term: str) -> "re.Pattern":
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE)


# ---------------------------------------------------------------- config

def enabled() -> bool:
    return os.environ.get("RAG_EXPLAIN", "off").strip().lower() == "on"


def _timeout() -> float:
    try:
        return float(os.environ.get("RAG_EXPLAIN_TIMEOUT", "")) if os.environ.get("RAG_EXPLAIN_TIMEOUT") else llm_parse._timeout()
    except ValueError:
        return llm_parse._timeout()


CLIENT_OVERRIDE: Any = None          # tests / eval: an object with complete(system, user, timeout)
TRACE: Optional[list] = None         # eval: a list that receives one record per query

_stats_lock = threading.Lock()
_stats: Counter = Counter()


def stats() -> dict:
    with _stats_lock:
        return dict(_stats)


def reset_stats() -> None:
    with _stats_lock:
        _stats.clear()


def _inc(key: str, n: int = 1) -> None:
    with _stats_lock:
        _stats[key] += n


# ---------------------------------------------------------------- the checker (pure)

class CarContext:
    """What the checker knows about one shown car."""

    def __init__(self, car_id: str, make: str, model: str, facts: List[Fact]):
        self.car_id, self.make, self.model = str(car_id), make, model
        self.facts = facts
        self.by_id = {f.id: f for f in facts}


def parse_sentences(items: Any) -> Tuple[Optional[List[Tuple[str, List[str]]]], Optional[str]]:
    """[(text without citations, [cited ids])] from the model's list, or (None, reason). Elements may be strings ending
    with "[f1,f2]" or {"text", "cites"}; a string that holds several sentences is split so each needs its own citation."""
    if not isinstance(items, list) or not items:
        return None, "shape:no_sentences"
    out: List[Tuple[str, List[str]]] = []
    for it in items:
        if isinstance(it, dict):
            text, cites = it.get("text"), it.get("cites")
            if not isinstance(text, str) or not isinstance(cites, list) or not all(isinstance(c, str) for c in cites):
                return None, "shape:bad_sentence_object"
            text = text.strip()
            inline = [c.strip().lower() for m in CITE_RE.findall(text) for c in m.split(",")]
            clean = re.sub(r"\s+([.,;:!?])", r"\1", CITE_RE.sub("", text)).strip()
            out.append((clean, list(dict.fromkeys([c.strip().lower() for c in cites] + inline))))
            continue
        if not isinstance(it, str):
            return None, "shape:bad_sentence_type"
        raw = it.strip().replace("Rs. ", "Rs ")
        parts: List[str] = []
        for piece in SPLIT_RE.split(raw):
            piece = piece.strip()
            if not piece:
                continue
            if parts and CITE_RE.fullmatch(piece):          # a bare "[f1,f2]" belongs to the sentence before it
                parts[-1] += " " + piece
            else:
                parts.append(piece)
        for p in parts:
            cites = [c.strip().lower() for m in CITE_RE.findall(p) for c in m.split(",")]
            clean = re.sub(r"\s+([.,;:!?])", r"\1", CITE_RE.sub("", p)).strip()
            out.append((clean, list(dict.fromkeys(cites))))
    return out, None


def _strip_names(text: str, ctx: CarContext, with_variant: bool = False) -> str:
    own = [ctx.make, ctx.model] + [w for w in re.split(r"[\s-]+", f"{ctx.make} {ctx.model}") if len(w) >= 4]
    for name in sorted({n for n in own if n}, key=len, reverse=True):
        text = _word_re(name).sub(" ", text)
    return text


def other_names(names: Dict[str, Iterable[str]], ctx: CarContext) -> List[str]:
    """Makes and models of the catalogue that are not this car's own."""
    own = {w.lower() for w in re.split(r"[\s-]+", f"{ctx.make} {ctx.model}") if w} | {ctx.make.lower(), ctx.model.lower()}
    out: List[str] = []
    for kind in ("makes", "models"):
        for n in names.get(kind) or []:
            n = str(n)
            candidates = [n] + ([w for w in re.split(r"\s+", n) if len(w) >= 4] if kind == "makes" else [])
            for c in candidates:
                if c.lower() not in own and c not in out:
                    out.append(c)
    return sorted(out, key=len, reverse=True)


def check_sentence(text: str, cites: List[str], ctx: CarContext, names: Dict[str, Iterable[str]]) -> List[str]:
    """Failure reasons for one sentence (empty list = passes)."""
    why: List[str] = []
    if not cites:
        return ["no_citation"]
    bad = [c for c in cites if c not in ctx.by_id]
    if bad:
        why.append("unknown_fact_id:" + ",".join(bad))
    cited = [ctx.by_id[c] for c in cites if c in ctx.by_id]
    if not cited:
        return why
    if len(text) > MAX_SENTENCE_CHARS:
        why.append("too_long")
    lower = text.lower()
    cited_text = " ".join(f.text for f in cited).lower()

    body = _strip_names(text, ctx)
    ftokens = [t for f in cited for t in f.tokens]
    for tok in numeric_tokens(body):
        if not token_matches(tok, ftokens):
            why.append(f"number_not_in_cited:{tok[0]:g}" + (f" {tok[1]}" if tok[1] else ""))

    for n in other_names(names, ctx):
        if n.lower() in COMMON_WORD_MODELS:
            m = re.search(r"(?<![A-Za-z0-9])" + re.escape(n.capitalize()) + r"(?![A-Za-z0-9])", body)
            hit = bool(m) and not (m.start() == 0 or not body[:m.start()].strip())
        else:
            hit = bool(_word_re(n).search(body))
        if hit:
            why.append(f"other_car_name:{n}")
            break

    if SAFETY_RE.search(text) and not any(f.kind in NCAP_KINDS for f in cited):
        why.append("safety_claim_without_ncap_fact")

    for m in COMPARATIVE_RE.finditer(text):
        if not _word_re(m.group(0).lower()).search(cited_text):
            why.append(f"comparison_not_in_facts:{m.group(0).lower()}")
            break

    all_text = " ".join(f.text for f in ctx.facts).lower()
    for term in FEATURE_TERMS:
        if _word_re(term).search(lower) and not _word_re(term).search(cited_text):
            why.append(f"feature_not_in_cited:{term}")
            break
    for term in ATTRIBUTE_TERMS:
        if _word_re(term).search(lower) and not _word_re(term).search(all_text):
            why.append(f"attribute_not_in_facts:{term}")
            break

    am = ABSENCE_RE.search(text)
    if am and not any(f.kind.startswith("unknown") or f.text.lower().startswith("unknown") for f in cited) \
            and not _word_re(am.group(0).lower()).search(cited_text):
        why.append(f"absence_claim:{am.group(0).lower()}")
    return why


def check_car(entry: Any, ctx: CarContext, names: Dict[str, Iterable[str]]) -> Tuple[Optional[List[dict]], List[str]]:
    """(sentences [{"text","cites"}] when the car passes else None, failure reasons)."""
    sentences, err = parse_sentences(entry)
    if err:
        return None, [err]
    if not 1 <= len(sentences) <= MAX_SENTENCES:
        return None, [f"sentence_count:{len(sentences)}"]
    reasons: List[str] = []
    for i, (text, cites) in enumerate(sentences):
        if not text:
            reasons.append("empty_sentence")
            continue
        reasons += check_sentence(text, cites, ctx, names)
    if reasons:
        return None, list(dict.fromkeys(reasons))
    return [{"text": t, "cites": c} for t, c in sentences], []


def check_response(raw: Any, contexts: Dict[str, CarContext], names: Dict[str, Iterable[str]]
                   ) -> Tuple[Dict[str, dict], Optional[str]]:
    """({car id: {"passed", "reasons", "sentences", "raw"}}, whole-response failure reason or None)."""
    results = {cid: {"passed": False, "reasons": ["missing_car"], "sentences": None, "raw": None} for cid in contexts}
    if not isinstance(raw, dict) or not isinstance(raw.get("cars"), list):
        return results, "shape:no_cars_list"
    seen = set()
    entries: Dict[str, Any] = {}
    for e in raw["cars"]:
        if not isinstance(e, dict) or "id" not in e:
            return results, "shape:bad_car_entry"
        cid = str(e["id"])
        if cid in seen:
            return results, "shape:duplicate_car"
        seen.add(cid)
        if cid not in contexts:
            return results, "shape:extra_car"
        entries[cid] = e
    for cid, e in entries.items():
        items = e.get("sentences")
        sentences, reasons = check_car(items, contexts[cid], names)
        results[cid] = {"passed": sentences is not None, "reasons": reasons, "sentences": sentences,
                        "raw": items if isinstance(items, list) else None}
    return results, None


# ---------------------------------------------------------------- prompt

def build_system_prompt() -> str:
    return f"""You write short explanations for a car recommendation site in India.
You get the buyer's query and, for each shown car, a list of facts, each with an id (f1, f2...).
For EACH car write 2 to 3 short, plain sentences saying why it fits THIS query. Use ONLY the given facts of that car.
Rules:
- Each sentence ends with the ids of the facts it uses in square brackets, like [f2,f5]. A sentence without ids is dropped.
- Copy numbers exactly as the facts write them (price, mileage, power, airbags...) and use only numbers that are in the facts you cite.
- Never compare a car with other cars and never name another car or brand, unless a cited fact itself makes the comparison.
- Say anything about crash tests, stars or safety only if you cite the crash-test fact.
- If something the query asked for is "Unknown" in the facts, you may say it is not confirmed; never guess or fill it in.
- No marketing words, no advice, no facts from memory. The query may be Hinglish: always answer in English.
Answer with ONE JSON object and nothing else:
{{"cars": [{{"id": "<car id exactly as given>", "sentences": ["Sentence one. [f1,f3]", "Sentence two. [f4]"]}}]}}
One entry per car given, no extra cars."""


def build_user_prompt(query: str, contexts: Dict[str, CarContext]) -> str:
    payload = {"query": query, "cars": [
        {"id": cid, "car": f"{c.make} {c.model}", "facts": [{"id": f.id, "text": f.text} for f in c.facts]}
        for cid, c in contexts.items()]}
    return json.dumps(payload, ensure_ascii=False)


def cache_key(contexts: Dict[str, CarContext], intent: Any) -> str:
    ids = ",".join(sorted(contexts))
    ih = hashlib.sha1(json.dumps(intent, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    fh = hashlib.sha1("|".join(f"{cid}:{facts_hash(c.facts)}" for cid, c in sorted(contexts.items())).encode()).hexdigest()[:16]
    return f"rag:{PROMPT_VERSION}:{ids}:{ih}:{fh}"


# ---------------------------------------------------------------- the call (provider, pacing, cap, cache of llm_parse)

def _generate(query: str, contexts: Dict[str, CarContext], intent: Any, client: Any) -> Tuple[Optional[dict], dict]:
    """(raw answer or None, info). Never raises; `info["reason"]` names why there is no answer."""
    info: Dict[str, Any] = {"cached": False, "latency_ms": None, "reason": None}
    key = cache_key(contexts, intent)
    entry = llm_parse.cache_get(key)
    if entry is not None:
        _inc("cache_hits")
        info["cached"] = True
        return entry["raw"], info
    system, user = build_system_prompt(), build_user_prompt(query, contexts)
    res = None
    t_start = time.monotonic()
    while res is None:
        block = llm_parse._pre_call_block()
        if block is not None:
            reason, wait = block
            if llm_parse._eval_wait(wait, counted=(reason != "pace")):
                continue
            info["reason"] = reason
            return None, info
        if not llm_parse._take_call_slot():
            info["reason"] = "daily_cap"
            return None, info
        try:
            cl = client if client is not None else llm_parse.make_client()
            t0 = time.monotonic()
            _inc("called")
            try:
                res = cl.complete(system, user, _timeout())
            finally:
                info["latency_ms"] = round((time.monotonic() - t0) * 1000.0, 1)
                if llm_parse._eval_cfg is not None:
                    llm_parse._eval_cfg["last_call"] = llm_parse._now()
            raw = llm_parse._parse_model_json(res.text)
        except llm_parse.LLMError as exc:
            res = None
            if exc.cooldown:
                delay = llm_parse._note_failure(exc.retry_after)
                if llm_parse._eval_wait(delay):
                    continue
            info["reason"] = exc.reason
            return None, info
    llm_parse._note_success()
    for k, v in (("tokens_in", res.tokens_in), ("tokens_out", res.tokens_out)):
        if isinstance(v, int):
            _inc(k, v)
    llm_parse.cache_put(key, {"raw": raw, "model": res.model, "tokens_in": res.tokens_in, "tokens_out": res.tokens_out})
    return raw, info


# ---------------------------------------------------------------- entry point used by api.recommend

def _names(catalogue) -> Dict[str, List[str]]:
    if catalogue is None:
        return {"makes": [], "models": []}
    return {"makes": sorted(str(m) for m in catalogue["make"].dropna().unique()),
            "models": sorted(str(m) for m in catalogue["model"].dropna().unique())}


def public_explanation(sentences: List[dict], ctx: CarContext) -> dict:
    cited = list(dict.fromkeys(c for s in sentences for c in s["cites"]))
    return {"sentences": [{"text": s["text"], "cites": list(s["cites"])} for s in sentences],
            "facts": {c: ctx.by_id[c].public() for c in cited}}


def attach(cards: List[dict], rows: List[Any], intent: Any, requirements: List[str], query: str, catalogue=None,
           client: Any = None) -> dict:
    """Add `explanation_rag` to every card whose generated text passed the checker. Returns the `rag` info block for the
    response. Never raises and never touches any other card field."""
    info: Dict[str, Any] = {"status": "fallback", "reason": None, "cached": False, "latency_ms": None, "cars": {}}
    try:
        if not cards:
            info["reason"] = "no_cars"
            return info
        contexts: Dict[str, CarContext] = {}
        for card, row in zip(cards, rows):
            cid = str(card["variant_id"])
            contexts[cid] = CarContext(cid, str(card["Make"]), str(card["Model"]), build_facts(card, row, requirements))
        names = _names(catalogue)
        use_client = client if client is not None else CLIENT_OVERRIDE
        raw, gen = _generate(query, contexts, intent, use_client)
        info.update(cached=gen["cached"], latency_ms=gen["latency_ms"])
        results: Dict[str, dict] = {}
        if raw is None:
            info["reason"] = gen["reason"] or "no_answer"
            results = {cid: {"passed": False, "reasons": [info["reason"]], "sentences": None, "raw": None} for cid in contexts}
            _inc("fallback_" + str(info["reason"]))
        else:
            results, whole = check_response(raw, contexts, names)
            if whole:
                info["reason"] = whole
                for r in results.values():
                    r["reasons"] = [whole]
                _inc("fallback_" + whole)
        passed = 0
        for card in cards:
            cid = str(card["variant_id"])
            res = results[cid]
            info["cars"][cid] = {"passed": res["passed"], "reasons": res["reasons"]}
            _inc("cars_seen")
            if res["passed"]:
                passed += 1
                _inc("cars_passed")
                card["explanation_rag"] = public_explanation(res["sentences"], contexts[cid])
            else:
                for r in res["reasons"]:
                    _inc("fail_" + r.split(":")[0])
        if raw is not None and not info["reason"]:
            info["status"] = "ok"
        info["passed"] = passed
        if TRACE is not None:
            TRACE.append({"query": query, "status": info["status"], "reason": info["reason"],
                          "cars": [{"id": cid, "car": f"{c.make} {c.model}", "facts": [(f.id, f.kind, f.text, f.url) for f in c.facts],
                                    "raw": results[cid]["raw"], "passed": results[cid]["passed"],
                                    "reasons": results[cid]["reasons"], "sentences": results[cid]["sentences"]}
                                   for cid, c in contexts.items()]})
        return info
    except Exception as exc:  # noqa: BLE001 - the request must never fail because of the explanations
        log.warning("rag explain internal error: %s", exc.__class__.__name__)
        for card in cards:
            card.pop("explanation_rag", None)
        info.update(status="fallback", reason="internal_error", cars={})
        return info
