#!/usr/bin/env python3
"""Dump ids, order, scores and messages of the v3 engine for every query of a query file, with per-query latency.

    .venv/bin/python eval/dump_ranking.py --out /tmp/before.json [--queries eval/queries.jsonl]
    .venv/bin/python eval/dump_ranking.py --diff before.json after.json     # empty = identical (floats within 1e-9)

Used to prove that a performance change leaves the results identical. Offline, no LLM. Reports cold start (process start
to the first answer) and peak RSS of the process."""
from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import sys
import time
from pathlib import Path

T0 = time.perf_counter()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_SOURCE", "kb")
os.environ["LLM_PARSER"] = "off"


def _clean(value):
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def dump(queries_path: Path, out: Path) -> None:
    from services.recsys.api import recommend
    queries = [json.loads(line) for line in queries_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records, times, cold = [], [], None
    for q in queries:
        t = time.perf_counter()
        resp = recommend(q["query"])
        dt = time.perf_counter() - t
        if cold is None:
            cold = time.perf_counter() - T0
        times.append(dt)
        records.append({
            "id": q["id"], "query": q["query"], "message": resp.get("message"),
            "cars": [{"variant_id": c["variant_id"], "model": c["Model"], "scores": c["scores"],
                      "criteria": c["criteria"], "class_weights": c["class_weights"], "match_label": c["match_label"],
                      "not_verified": c["not_verified"], "unknowns": c["unknowns"], "reasons": c["reasons"],
                      "violations": c["violations"], "selection_order": c["selection_order"],
                      "also": c["also_available_from"]} for c in resp["recommendations"]],
        })
    ordered = sorted(times)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * len(ordered))) - 1)]
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024
    stats = {"n_queries": len(times), "median_s": statistics.median(times), "p95_s": p95, "max_s": max(times),
             "mean_s": statistics.mean(times), "cold_start_to_first_answer_s": cold, "peak_rss_mb": rss_mb}
    out.write_text(json.dumps({"stats": stats, "records": records}, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(stats, indent=1))


def _diff(a, b, path="", tol=1e-9):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                yield f"{path}/{k}: only in one"
            else:
                yield from _diff(a[k], b[k], f"{path}/{k}", tol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            yield from _diff(x, y, f"{path}[{i}]", tol)
    elif isinstance(a, float) and isinstance(b, float):
        if abs(a - b) > tol and not (a != a and b != b):
            yield f"{path}: {a} vs {b}"
    elif a != b:
        yield f"{path}: {a!r} vs {b!r}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default=str(ROOT / "eval" / "queries.jsonl"))
    ap.add_argument("--out")
    ap.add_argument("--diff", nargs=2)
    args = ap.parse_args()
    if args.diff:
        a, b = (json.loads(Path(p).read_text())["records"] for p in args.diff)
        diffs = list(_diff(a, b))
        print(f"{len(diffs)} differences")
        for d in diffs[:30]:
            print(" ", d)
        return 1 if diffs else 0
    dump(Path(args.queries), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
