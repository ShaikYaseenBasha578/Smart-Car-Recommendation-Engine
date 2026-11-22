"""Grounded-explanation evaluation (plan C). Runs queries with RAG_EXPLAIN=on and reports how many generated explanations
pass the deterministic checker, why the others fail, and writes a blind-review sheet for a human / fresh-agent check.

    # offline smoke test, no provider, no key (a mock writes sentences from the facts):
    .venv/bin/python eval/rag_eval.py --mock --queries eval/queries.jsonl eval/heldout_queries.jsonl --out /tmp/rag_eval.json

    # real run, paced, resumable (NOT run in CI; needs GEMINI_API_KEY or LLM_PARSER_BASE_URL + LLM_PARSER_KEY_ENV).
    # One call per query; answers are cached in --cache after every live call, so re-running the same command resumes.
    .venv/bin/python eval/rag_eval.py --pace 6 --max-wait 1800 --cache eval/results/rag_cache.json \\
        --queries eval/queries.jsonl eval/heldout_queries.jsonl --out /tmp/rag_eval.json \\
        --sheet /tmp/rag_blind_sheet.csv --key /tmp/rag_blind_key.csv --sheet-size 50

Outputs: a console summary and (--out) JSON with: checker pass rate per car and per query (a query passes when every shown
car passed), the whole-call fallback reasons, the per-car failure reasons, and the cache/live-call counts.
The blind sheet (CSV: opaque id, query, car, sentence, cited facts) carries no pass/fail and is shuffled; the key CSV maps each
opaque id to the query id, car id, checker verdict and reasons. Review the sheet first, open the key afterwards.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

DEFAULT_QUERIES = [ROOT / "eval" / "queries.jsonl", ROOT / "eval" / "heldout_queries.jsonl"]


class MockClient:
    """Offline stand-in for the provider: per car, copies the price fact and one other fact word for word, each cited.
    It exercises the whole path (prompt, parsing, checker, fallback) and is the cheapest possible 'model'."""

    def __init__(self):
        self.calls = 0

    def complete(self, system, user, timeout):
        from services.recsys import llm_parse
        self.calls += 1
        data = json.loads(user)
        cars = []
        for c in data["cars"]:
            facts = c["facts"]
            pick = [f for f in facts if f["text"].startswith("Ex-showroom price")][:1]
            pick += [f for f in facts if f["text"].startswith(("Mileage", "Power", "Airbags", "Seats", "Range"))][:2]
            cars.append({"id": c["id"], "sentences": [f"{f['text']}. [{f['id']}]" for f in pick] or ["Not on record. [f1]"]})
        return llm_parse.ClientResult(json.dumps({"cars": cars}), 0, 0, "mock")


def load_queries(paths):
    out = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                q = json.loads(line)
                q["_file"] = Path(p).name
                out.append(q)
    return out


def run(queries, client=None, progress=False):
    """[(query record, rag trace record or None, response summary)] after running every query with RAG on."""
    from eval.run_eval import make_engine
    from services.recsys import rag_explain
    rag_explain.CLIENT_OVERRIDE = client
    rag_explain.TRACE = []
    rag_explain.reset_stats()
    engine = make_engine("v3")
    rows = []
    for i, q in enumerate(queries, 1):
        before = len(rag_explain.TRACE)
        try:
            resp = engine(q["query"])
            err = None
        except Exception as exc:  # a crash is a result, not a reason to stop
            resp, err = {}, f"{type(exc).__name__}: {exc}"
        trace = rag_explain.TRACE[before] if len(rag_explain.TRACE) > before else None
        rows.append({"q": q, "trace": trace, "rag": resp.get("rag"), "n_cars": len(resp.get("recommendations") or []),
                     "error": err})
        if progress:
            print(f"[{i}/{len(queries)}] {q['id']} cars={rows[-1]['n_cars']} "
                  f"{'-' if not resp.get('rag') else resp['rag']['status'] + ' ' + str(resp['rag']['reason'] or '')}", flush=True)
    return rows


def latency_summary(attempted):
    """p50 / p95 / max of the live (uncached) provider calls, and how many would have missed common timeouts. Cached
    answers have no latency. The eval runs with a long timeout, so these are the times a production budget must cover."""
    ms = sorted(r["rag"]["latency_ms"] for r in attempted if not r["rag"]["cached"] and r["rag"].get("latency_ms") is not None)
    if not ms:
        return {"calls": 0}
    pick = lambda q: ms[min(len(ms) - 1, int(round(q * (len(ms) - 1))))]
    return {"calls": len(ms), "p50": pick(0.5), "p95": pick(0.95), "max": ms[-1],
            "over_ms": {str(t): sum(1 for m in ms if m > t) for t in (2000, 4000, 6000, 8000)}}


def summarise(rows):
    attempted = [r for r in rows if r["rag"]]
    car_total = car_pass = 0
    whole = Counter()
    reasons = Counter()
    q_pass = q_partial = q_fallback = 0
    per_query = []
    for r in attempted:
        cars = r["rag"]["cars"]
        n, p = len(cars), sum(1 for c in cars.values() if c["passed"])
        car_total += n
        car_pass += p
        if r["rag"]["reason"] and r["rag"]["status"] == "fallback":
            whole[r["rag"]["reason"]] += 1
        for c in cars.values():
            for why in c["reasons"]:
                reasons[why.split(":")[0]] += 1
        if p == n and n:
            q_pass += 1
        elif p:
            q_partial += 1
        else:
            q_fallback += 1
        per_query.append({"id": r["q"]["id"], "cars": n, "passed": p, "status": r["rag"]["status"], "reason": r["rag"]["reason"]})
    return {
        "queries": len(rows), "queries_with_cars": len(attempted), "errors": sum(1 for r in rows if r["error"]),
        "cars_total": car_total, "cars_passed": car_pass, "car_pass_rate": round(car_pass / car_total, 4) if car_total else None,
        "queries_all_cars_passed": q_pass, "queries_some_cars_passed": q_partial, "queries_no_car_passed": q_fallback,
        "query_pass_rate": round(q_pass / len(attempted), 4) if attempted else None,
        "whole_call_fallback_reasons": dict(whole), "car_failure_reasons": dict(reasons.most_common()),
        "cached_answers": sum(1 for r in attempted if r["rag"]["cached"]),
        "live_latency_ms": latency_summary(attempted),
        "per_query": per_query,
    }


def blind_sheet(rows, size, seed):
    """(sheet rows, key rows). Every sentence the model produced (also those the checker rejected) is a candidate; the
    sample is shuffled and given opaque ids. The sheet has no verdict."""
    from services.recsys import rag_explain
    cands = []
    for r in rows:
        t = r["trace"]
        if not t:
            continue
        for car in t["cars"]:
            facts = {f[0]: f[2] for f in car["facts"]}
            sentences = car["sentences"]
            if sentences is None and isinstance(car["raw"], list):
                sentences, _ = rag_explain.parse_sentences(car["raw"])
                sentences = [{"text": s, "cites": c} for s, c in sentences or []]
            for s in sentences or []:
                cited = " || ".join(f"{c}: {facts[c]}" for c in s["cites"] if c in facts)
                cands.append(({"query": r["q"]["query"], "car": car["car"], "sentence": s["text"], "cited_facts": cited},
                              {"query_id": r["q"]["id"], "variant_id": car["id"], "checker_passed": car["passed"],
                               "reasons": "; ".join(car["reasons"])}))
    rng = random.Random(seed)
    rng.shuffle(cands)
    cands = cands[:size]
    sheet, key = [], []
    for i, (row, k) in enumerate(cands, 1):
        sid = f"S{rng.randrange(10**6):06d}-{i:03d}"
        sheet.append({"id": sid, **row})
        key.append({"id": sid, **k})
    return sheet, key


def write_csv(path, rows, fields):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queries", nargs="+", default=[str(p) for p in DEFAULT_QUERIES], help="query files (JSON lines)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N queries (0 = all)")
    ap.add_argument("--mock", action="store_true", help="offline: a mock provider writes the sentences from the facts")
    ap.add_argument("--pace", type=float, default=0.0, metavar="SECONDS", help="minimum seconds between live calls (eval only)")
    ap.add_argument("--max-wait", type=float, default=1800.0, metavar="SECONDS", help="total wait on 429 / rate limits")
    ap.add_argument("--cache", default=str(ROOT / "eval" / "results" / "rag_cache.json"), help="answer cache (resume file)")
    ap.add_argument("--out", help="write the summary JSON here")
    ap.add_argument("--sheet", help="blind review sheet CSV")
    ap.add_argument("--key", help="key CSV for the sheet (kept apart)")
    ap.add_argument("--sheet-size", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    os.environ["RAG_EXPLAIN"] = "on"
    os.environ.setdefault("LLM_PARSER", "off")            # the query parser stays on the rules; only the explanations use the LLM
    os.environ["LLM_PARSER_TIMEOUT"] = os.environ.get("LLM_PARSER_TIMEOUT", "20")
    if args.mock:
        os.environ["LLM_PARSER_RPM"] = "0"                # no local limiter, no daily cap for the mock
        os.environ["LLM_PARSER_DAILY_CAP"] = "1000000"
    else:
        os.environ["LLM_PARSER_CACHE_FILE"] = args.cache
        from services.recsys import llm_parse
        llm_parse.configure_eval(pace=args.pace, max_wait=args.max_wait)
    queries = load_queries(args.queries)
    if args.limit:
        queries = queries[:args.limit]
    rows = run(queries, MockClient() if args.mock else None, progress=True)
    summary = summarise(rows)
    from services.recsys import rag_explain
    summary["stats"] = rag_explain.stats()
    print(json.dumps({k: v for k, v in summary.items() if k != "per_query"}, indent=1))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(summary, indent=1), encoding="utf-8")
        print(f"wrote {args.out}")
    if args.sheet or args.key:
        sheet, key = blind_sheet(rows, args.sheet_size, args.seed)
        if args.sheet:
            write_csv(args.sheet, sheet, ["id", "query", "car", "sentence", "cited_facts"])
        if args.key:
            write_csv(args.key, key, ["id", "query_id", "variant_id", "checker_passed", "reasons"])
        print(f"sheet rows: {len(sheet)}")
    return summary


if __name__ == "__main__":
    main()
