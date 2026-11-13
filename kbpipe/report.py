"""Run outputs: RUN_SUMMARY.md, REVIEW_<run>.md, conflicts.tsv, flags.tsv, the human agreement sheet, the changelog entry.
Every number printed here is read from the run's own files or computed from the database by `coverage`."""
import csv
import json
import os
import random

from . import fields as F


def coverage(conn):
    q = lambda s: conn.execute(s).fetchone()[0]
    by = {r[0]: {"models": r[1], "variants": r[2]} for r in conn.execute(
        "select coalesce(mo.body_type,'?'), count(distinct mo.id), count(v.id) from model mo left join variant v on v.model_id=mo.id group by 1")}
    filled = {}
    cols = [r[1] for r in conn.execute("pragma table_info(variant)")]
    n = q("select count(*) from variant")
    for f in F.VARIANT_FIELDS:
        if f in cols:
            filled[f] = q('select count(*) from variant where "%s" is not null' % f)
    return {"makes": q("select count(*) from manufacturer"), "models": q("select count(*) from model"), "variants": n,
            "discontinued": q("select count(*) from variant where is_discontinued=1"), "by_body_type": by,
            "cells_filled": sum(filled.values()), "cells_possible": n * len(filled),
            "provenance_rows": q("select count(*) from field_provenance"),
            "observations": q("select count(*) from source_observation"),
            "cells_with_url_evidence": q(
                "select count(*) from (select distinct p.variant_id, p.field_name from field_provenance p "
                "join source_observation o on o.id=p.source_observation_id where p.decision in ('accepted','confirmed') "
                "and o.source_url is not null and o.source_url<>'')")}


def write_tables(run_dir, P):
    with open(os.path.join(run_dir, "conflicts.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["make", "model", "variant", "field", "kind", "high", "kb_value", "values", "resolution"])
        for c in P["conflicts"]:
            w.writerow([c["make"], c["model"], c["variant"], c["field"], c["kind"], int(c["high"]), c.get("kb_value"),
                        "; ".join("%s=%s" % (v["source"], v["value"]) for v in c["values"]), c["resolution"]])
    if P.get("links"):
        with open(os.path.join(run_dir, "links.tsv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(P["links"][0].keys()), delimiter="\t")
            w.writeheader()
            w.writerows(P["links"])
    with open(os.path.join(run_dir, "flags.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["make", "model", "variant", "field", "why", "detail"])
        for x in P["flags"]:
            w.writerow([x["make"], x["model"], x["variant"], x["field"], x["why"], x.get("detail", "")])


def write_review(run_dir, run_id, review):
    path = os.path.join(run_dir, "REVIEW_%s.md" % run_id)
    L = ["# Review for run %s" % run_id, "",
         "Only what needs you. Nothing below has been applied. To decide an item, put an `x` in ONE of its two boxes, save,",
         "then run `kbpipe apply-review %s`. Unticked items stay pending." % os.path.relpath(path), "",
         "%d item(s), highest impact first." % len(review), ""]
    for r in sorted(review, key=lambda r: -r["impact"]):
        L.append("## %s · %s · %s" % (r["id"], r["kind"], r["title"]))
        L.append(r["why"])
        if r["ops"]:
            L.append("- [ ] approve %s  (applies %d change(s))" % (r["id"], len(r["ops"])))
            L.append("- [ ] reject %s" % r["id"])
        else:
            L.append("- No automatic action. Default: %s. Tell me what to do, or leave it." % r["default"])
        L.append("")
    with open(path, "w") as f:
        f.write("\n".join(L))
    return path


def human_sheet(run_dir, rows, cfg):
    """30 random audited cells with a blank column for the owner's verdict."""
    rows = [r for r in rows if r["verdict"] in ("match", "mismatch")]
    if not rows:
        return None
    rng = random.Random(cfg["seed"] + 1)
    rows = sorted(rows, key=lambda r: (str(r["variant_id"]), r["field"]))
    rng.shuffle(rows)
    path = os.path.join(run_dir, "human_check.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["car", "field", "definition", "kb_value", "source_link", "verifier_verdict", "verifier_evidence",
                    "your_verdict (match/mismatch/cannot tell)"])
        for r in rows[:cfg["human_sheet_n"]]:
            w.writerow([r["car"], r["field"], F.DEFINITIONS.get(r["field"], ""), r["kb_value"], r["source_ref"], r["verdict"],
                        r["evidence"] or r["source_value"], ""])
    return path


def agreement(path):
    """Owner-vs-verifier agreement from a filled sheet: raw agreement and Cohen's kappa."""
    pairs = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            mine = (r.get("your_verdict (match/mismatch/cannot tell)") or "").strip().lower()
            if mine in ("match", "mismatch"):
                pairs.append((r["verifier_verdict"].strip().lower(), mine))
    n = len(pairs)
    if not n:
        return {"n": 0}
    agree = sum(a == b for a, b in pairs)
    pa = agree / float(n)
    pe = sum((sum(a == k for a, _ in pairs) / float(n)) * (sum(b == k for _, b in pairs) / float(n)) for k in ("match", "mismatch"))
    return {"n": n, "agree": agree, "agreement": round(pa, 4), "kappa": round((pa - pe) / (1 - pe), 4) if pe < 1 else None,
            "verifier_match_you_mismatch": sum(a == "match" and b == "mismatch" for a, b in pairs),
            "verifier_mismatch_you_match": sum(a == "mismatch" and b == "match" for a, b in pairs)}


def _acc(a):
    if not a or a.get("accuracy") is None:
        return "no checked cells"
    return "%.1f%% (%d of %d; %d unreachable, %d verifier errors)" % (
        100 * a["accuracy"], a["match"], a["match"] + a["mismatch"], a["unreachable"], a["verifier_error"])


def write_summary(cfg, run_dir, R, P, items, sheet):
    L = ["# Run %s" % R["run"], ""]
    src = lambda name: "`%s`" % os.path.join(os.path.basename(run_dir), name)
    if R.get("stopped"):
        L += ["**Stopped / not merged:** %s" % R["stopped"], ""]
    cb, ca = R.get("coverage_before"), R.get("coverage_after")
    if cb and ca:
        L += ["## Coverage (before → after)", "Source: database counts in %s." % src("run.json"), "",
              "- Models: %d → %d. Variants: %d → %d. Marked discontinued: %d → %d." % (
                  cb["models"], ca["models"], cb["variants"], ca["variants"], cb["discontinued"], ca["discontinued"]),
              "- Filled cells: %d → %d of %d possible." % (cb["cells_filled"], ca["cells_filled"], ca["cells_possible"]),
              "- Cells with at least one URL-backed evidence row: %d → %d." % (cb["cells_with_url_evidence"], ca["cells_with_url_evidence"]),
              "", "| Segment | Models | Variants |", "|---|---|---|"]
        for k in sorted(set(cb["by_body_type"]) | set(ca["by_body_type"])):
            b, a = cb["by_body_type"].get(k, {"models": 0, "variants": 0}), ca["by_body_type"].get(k, {"models": 0, "variants": 0})
            L.append("| %s | %d → %d | %d → %d |" % (k, b["models"], a["models"], b["variants"], a["variants"]))
        L.append("")
    if R.get("discovery"):
        d, s = R["discovery"], R.get("stats", {})
        L += ["## Discovery and changes", "Source: %s, %s." % (src("discovery.json"), src("run.json")), "",
              "- On sale on both sites and already in the KB: %d. New models found: %d. Out of scope by price: %d." % (
                  d.get("EXISTING", 0), d.get("NEW_MODEL", 0), d.get("OUT_OF_SCOPE", 0)),
              "- Models processed this run: %d. Unchanged and skipped: %d. Deferred to the next run: %d." % (
                  R.get("processed", 0), R.get("skipped_unchanged", 0), len(R.get("deferred", []))),
              "- Models added: %d. Variants added: %d. Cells written: %d. Existing cells confirmed by both sites: %d." % (
                  s.get("models_added", 0), s.get("variants_added", 0), s.get("cells_written", 0), s.get("cells_confirmed", 0)),
              "- Variants not added because only one site lists them or the sites disagree on identity: %d." % s.get("variants_not_added", 0),
              "- Existing cells where both sites differ from the KB or could fill a blank (in review, not applied): %d." % s.get("cells_for_review", 0),
              "- KB variants not found in the current listing (in review, not marked): %d. Discontinued-model candidates: %d." % (
                  s.get("kb_variants_not_listed", 0), d.get("DISCONTINUED_CANDIDATE", 0)), ""]
    v = R.get("verify")
    if v:
        L += ["## Verification", "Source: %s only (written by the verifier, read-only)." % src("verify/results.jsonl"), "",
              "- Overall: %s. Sample size %d." % (_acc(v["overall"]), v["overall"]["n"])]
        if R.get("audit_incomplete"):
            L.append("- **The audit did not finish:** %s" % R["audit_incomplete"])
        al = R.get("audit_legacy")
        if al:
            L.append("- Legacy values (June 2026 import, no URL on record): %d cells, of which %d belong to a variant linked to a current page and could be sampled. They are checked against today's page, so a mismatch can also mean the car changed." % (al["cells"], al["with_current_page"]))
        for c, a in v["by_source_class"].items():
            L.append("- Source class %s: %s." % (c, _acc(a)))
        L += ["", "| Field type | Accuracy | Checked | Match | Mismatch | Unreachable | Verifier errors |", "|---|---|---|---|---|---|---|"]
        low = []
        for g, a in v["by_group"].items():
            acc = "n/a" if a["accuracy"] is None else "%.1f%%" % (100 * a["accuracy"])
            L.append("| %s | %s | %d | %d | %d | %d | %d |" % (g, acc, a["match"] + a["mismatch"], a["match"], a["mismatch"], a["unreachable"], a["verifier_error"]))
            if a["accuracy"] is not None and a["accuracy"] < cfg["verify_bar"]:
                low.append(g)
        L.append("")
        L.append("**Below the %d%% bar:** %s." % (100 * cfg["verify_bar"], ", ".join(low)) if low else "No field type is below the %d%% bar." % (100 * cfg["verify_bar"]))
        if R.get("stopped_groups"):
            L.append("**Stopped during the run:** " + "; ".join("%s (%s)" % kv for kv in R["stopped_groups"].items()) + ".")
        L += ["", "By field type and source class:", "", "| Stratum | Accuracy | Checked |", "|---|---|---|"]
        for k, a in sorted(v["by_group_and_class"].items()):
            L.append("| %s | %s | %d |" % (k, "n/a" if a["accuracy"] is None else "%.1f%%" % (100 * a["accuracy"]), a["match"] + a["mismatch"]))
        pl = R.get("planted") or {}
        if pl.get("planted"):
            L += ["", "Planted-error control (%s): %d values the verifier had confirmed were re-submitted with a wrong value; it called %d of %d a mismatch." % (
                src("verify/planted.jsonl"), pl["planted"], pl["caught"], pl["judged"])]
        L += ["", "Human agreement sheet: %s. Fill the last column, then run `kbpipe agreement <file>`." % (src("human_check.csv") if sheet else "not produced (no checked cells)"), ""]
    if P:
        cf = P.get("conflicts", [])
        top = {}
        for c in cf:
            top[c["field"]] = top.get(c["field"], 0) + 1
        res = {}
        for c in cf:
            res[c["resolution"]] = res.get(c["resolution"], 0) + 1
        L += ["## Conflicts", "Source: %s." % src("conflicts.tsv"), "",
              "- %d conflict(s); %d above the disagreement threshold." % (len(cf), sum(c["high"] for c in cf)),
              "- Resolution: %s." % ("; ".join("%s: %d" % kv for kv in sorted(res.items(), key=lambda kv: -kv[1])) or "none"),
              "- Most frequent fields: %s." % (", ".join("%s (%d)" % kv for kv in sorted(top.items(), key=lambda kv: -kv[1])[:8]) or "none"), ""]
        fl = {}
        for x in P.get("flags", []):
            fl[x["why"]] = fl.get(x["why"], 0) + 1
        L += ["## Cells left blank", "Source: %s." % src("flags.tsv"), ""] + ["- %s: %d" % kv for kv in sorted(fl.items(), key=lambda kv: -kv[1])] + [""]
        rv = sorted(P.get("review", []), key=lambda r: -r["impact"])
        L += ["## Waiting for you", "%d item(s) in %s. Top of the list:" % (len(rv), src("REVIEW_%s.md" % R["run"])), ""]
        L += ["- %s (%s): %s" % (r["id"], r["kind"], r["title"]) for r in rv[:12]] + [""]
    if R.get("stage"):
        g = R["stage"].get("gates", {})
        L += ["## Gates", "Source: %s." % src("run.json"), ""] + [
            "- %s: %s — %s" % (k, "pass" if x["ok"] else "FAIL", "; ".join(str(d) for d in x["detail"][:3])) for k, x in g.items()]
        L += ["- idempotency re-run: %s" % ("0 changes" if R["stage"].get("idempotent") else "FAILED"), ""]
    if R.get("write"):
        w = R["write"]
        L += ["## Write", "- KB SHA-1 %s → %s. Backup: `%s`. History tag: `%s`. integrity_check: %s. Prod equals staging: %s." % (
            w["sha1_before"], w["sha1_after"], os.path.basename(w["backup"]), w["history_tag"], w["integrity_check"], w["prod_equals_staging"]), ""]
    ll, ft = R.get("llm") or {}, R.get("fetch") or {}
    L += ["## Cost and runtime", "- LLM calls: %d (%s). Cost: Rs 0 (free tier)." % (
        ll.get("calls", 0), ", ".join("%s: %d" % kv for kv in (ll.get("by_model") or {}).items()) or "none"),
          "- Pages fetched: %d from the network, %d from cache, %d failed." % (ft.get("network", 0), ft.get("cache", 0), ft.get("failed", 0)),
          "- Runtime: %.0f minutes." % (R.get("runtime_seconds", 0) / 60.0), ""]
    with open(os.path.join(run_dir, "RUN_SUMMARY.md"), "w") as f:
        f.write("\n".join(L))


def append_changelog(cfg, R, P):
    s, w, v = R.get("stats", {}), R["write"], (R.get("verify") or {}).get("overall") or {}
    entry = ["", "## kbpipe %s — %s — automated enrichment run" % (R["run"], R["started"][:10]),
             "**Why:** scheduled pipeline run (discovery, extraction from CarWale and CarDekho, reconciliation, verification).",
             "**What changed:** %d models and %d variants added; %d cells written from two agreeing sites; %d existing cells given confirming evidence. Schema: none." % (
                 s.get("models_added", 0), s.get("variants_added", 0), s.get("cells_written", 0), s.get("cells_confirmed", 0)),
             "**Verifier:** %s." % _acc(v),
             "**Not done / held:** %d review item(s) in runs/%s/REVIEW_%s.md." % (R.get("review_items", 0), R["run"], R["run"]),
             "**Prod SHA-1:** `%s…` → `%s…`. Backup `%s`, history tag `%s`." % (
                 w["sha1_before"][:8], w["sha1_after"][:8], os.path.basename(w["backup"]), w["history_tag"]), ""]
    with open(cfg["changelog"], "a") as f:
        f.write("\n".join(entry))
