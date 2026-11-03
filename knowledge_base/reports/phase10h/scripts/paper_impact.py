"""Phase 10H, read-only: would any paper v0 verdict, margin or grounded table change if the transmission (or, for 821
and 833, the engine) of editions 821/831/832/833 were unknown? Run from the repo root with CARREC_PAPER_KB=<snapshot copy>."""
import json, os, sys
sys.path.insert(0, "paper")
from oracle.feasibility import load_catalogue, satisfies, verify_frozen_db, DB_PATH
from prompts.build_prompts import load_catalogue_csv, configurations
EDS = (821, 831, 832, 833)
verify_frozen_db()
print("oracle DB:", DB_PATH)
cat = load_catalogue()
by_id = {r["variant_id"]: r for r in cat}
print({e: {k: by_id[e][k] for k in ("model", "fuel", "transmission", "seats", "price", "body_type", "model_excluded") if k in by_id[e]} for e in EDS})
queries = [json.loads(l) for l in open("paper/data/queries_v0.jsonl")]
hits = []
for q in queries:
    c = q["constraints"]
    for e in EDS:
        row = by_id[e]
        full = satisfies(row, c)
        wo_trans = satisfies(row, {k: v for k, v in c.items() if k != "transmission"})
        in_ids = e in (q.get("oracle_match_ids") or [])
        if not (full or in_ids or ("transmission" in c and wo_trans)): continue
        others = [r for r in cat if r["variant_id"] != e and satisfies(r, c)]
        others_ne = [r for r in others if not r.get("model_excluded")]
        if q["type"] == "feasible_control":
            flip = full and not others_ne and not row.get("model_excluded")
            note = f"{len(others_ne)} other non-excluded matches"
            cheapest = min((r["price"] for r in others_ne), default=None)
            margin = f"cheapest_other_price {q.get('cheapest_other_price')} -> without {e}: {cheapest}"
        else:
            flip = (not full) and wo_trans and "transmission" in c  # unknown transmission could satisfy -> infeasibility uncertain
            note = "matches all but transmission" if wo_trans and not full else ("MATCHES" if full else "")
            margin = ""
        hits.append((q["query_id"], q["type"], c, e, full, in_ids, note, flip, margin))
for h in hits: print(h)
print("verdict flips:", [h[:4] for h in hits if h[7]])
# margins: infeasible queries whose cheapest_other_price could be one of the editions under another transmission
rows = load_catalogue_csv()
for body in sorted({r["body_type"] for r in rows if int(r["variant_id"]) in EDS}):
    full_cfg = {g["key"]: (g["min_price"], g["max_price"], g["n_variants"]) for g in configurations(rows, body)}
    for e in EDS:
        if rows[[int(r["variant_id"]) for r in rows].index(e)]["body_type"] != body: continue
        wo = {g["key"]: (g["min_price"], g["max_price"], g["n_variants"]) for g in configurations([r for r in rows if int(r["variant_id"]) != e], body)}
        diff = {k: (full_cfg.get(k), wo.get(k)) for k in set(full_cfg) | set(wo) if full_cfg.get(k) != wo.get(k)}
        changed = {k: v for k, v in diff.items() if v[1] is None or v[0][:2] != v[1][:2]}
        print(f"G-{body} table without {e}: rows/ranges changed {changed if changed else 'none (only n_variants)'} | n_variants-only diffs {len(diff) - len(changed)}")
