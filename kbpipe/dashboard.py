"""Presentation dashboard: one self-contained HTML file about the knowledge base and the pipeline that maintains it.

    python -m kbpipe.dashboard --out knowledge_base/reports/kb_dashboard/index.html

Reads a read-only COPY of the KB (made with kb.copy_for_read, which checks holders and hashes before and after), the run
folders under knowledge_base/runs/ and, when readable, the local history repository. Every number on the page is computed
here from those inputs. The output embeds all data as JSON and all CSS and JS inline: no network request of any kind.
Output is deterministic apart from the "generated on" date.
"""
import argparse
import datetime
import json
import math
import os
import re
import sqlite3
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kbpipe import config, fields as F, kb  # noqa: E402

DEFAULT_COPY = "/tmp/carrec_audit/prod/dashboard_copy.db"
CLASS_ORDER = ["aggregator", "brochure", "legacy"]
CLASS_LABEL = {"aggregator": "Two agreeing sites", "brochure": "OEM brochure", "legacy": "Legacy import"}
CLASS_EXPLAIN = {
    "aggregator": "Values that CarWale and CarDekho both state for the same variant, written by kbpipe.",
    "brochure": "Values taken from a manufacturer brochure PDF, each citing its page.",
    "legacy": "Values from the June 2026 import. They recorded no web address, so they are checked against today's page for that variant.",
}


# ---------------------------------------------------------------- small helpers
def has(c, name):
    return c.execute("select 1 from sqlite_master where name=? and type in ('table','view')", (name,)).fetchone() is not None


def rows(c, sql, args=()):
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.Error:
        return []


def one(c, sql, args=(), default=0):
    r = rows(c, sql, args)
    return r[0][0] if r and r[0][0] is not None else default


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    return out


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- KB
def collect_kb(c):
    d = {}
    d["makes"] = one(c, "select count(*) from manufacturer")
    d["models"] = one(c, "select count(*) from model")
    d["variants"] = one(c, "select count(*) from variant")
    d["powertrains"] = one(c, "select count(*) from powertrain")

    src = "v_variant_canonical_q" if has(c, "v_variant_canonical_q") else "variant"
    vcols = {r[1] for r in c.execute("pragma table_info(%s)" % src)}
    pcols = {r[1] for r in c.execute("pragma table_info(powertrain)")}
    vf = [f for f in F.VARIANT_FIELDS if f in vcols]
    pf = [f for f in F.POWERTRAIN_FIELDS if f in pcols]
    fields = vf + pf
    sel = ["v.id", "v.base_variant_id" if "base_variant_id" in vcols else "null as base_variant_id", "ma.name as make",
           "p.fuel_type as _fuel"]
    sel += ['v."%s" as "%s"' % (f, f) for f in vf] + ['p."%s" as "%s"' % (f, f) for f in pf if f != "fuel_type"]
    if "fuel_type" in pf:
        sel.append('p.fuel_type as "fuel_type"')
    sql = ("select %s from %s v join model mo on mo.id=v.model_id join manufacturer ma on ma.id=mo.manufacturer_id "
           "left join powertrain p on p.id=v.powertrain_id order by v.id" % (", ".join(sel), src))
    vrows = [dict(r) for r in c.execute(sql)] if c.row_factory else None
    return d, vrows, fields


def evidence_sets(c):
    """(variant_id, field) -> True when a URL is recorded, False when evidence has none. Live evidence only (quarantine honoured)."""
    ev = {}
    if has(c, "v_live_evidence"):
        q = ("select e.variant_id, e.field_name, max(case when o.source_url is not null and o.source_url<>'' then 1 else 0 end) "
             "from v_live_evidence e join source_observation o on o.id=e.observation_id "
             "where e.decision in ('accepted','confirmed') group by 1,2")
    else:
        q = ("select e.variant_id, e.field_name, max(case when o.source_url is not null and o.source_url<>'' then 1 else 0 end) "
             "from field_provenance e join source_observation o on o.id=e.source_observation_id "
             "where e.decision in ('accepted','confirmed') group by 1,2")
    for v, f, u in rows(c, q):
        ev[(v, f)] = bool(u)
    return ev


def values_and_coverage(c, vrows, fields):
    ev = evidence_sets(c)
    values = with_ev = with_url = 0
    makes = sorted({r["make"] for r in vrows})
    slot = {m: {g: [0, 0] for g in F.GROUPS} for m in makes + ["All makes"]}
    for r in vrows:
        fuel = r.get("_fuel")
        for f in fields:
            if r.get(f) is None:
                continue
            values += 1
            key_own, key_base = (r["id"], f), (r["base_variant_id"], f)
            hit = ev.get(key_own, ev.get(key_base) if r["base_variant_id"] else None)
            if hit is not None:
                with_ev += 1
                with_url += 1 if hit else 0
        for g in F.GROUPS:
            gf = [f for f in fields if F.FIELDS[f][2] == g]
            if not gf:
                continue
            if g == "efficiency":
                n, k = 1, 1 if any(r.get(f) is not None for f in gf) else 0
            else:
                use = [f for f in gf if not (f == "fuel_tank_litres" and fuel == "Electric")]
                n, k = len(use), sum(1 for f in use if r.get(f) is not None)
            for m in (r["make"], "All makes"):
                slot[m][g][0] += k
                slot[m][g][1] += n
    nvar = {m: sum(1 for r in vrows if r["make"] == m) for m in makes}
    nvar["All makes"] = len(vrows)
    heat = {"groups": F.GROUPS, "makes": makes + ["All makes"],
            "pct": [[(slot[m][g][0] / slot[m][g][1]) if slot[m][g][1] else None for g in F.GROUPS] for m in makes + ["All makes"]],
            "n_variants": [nvar[m] for m in makes + ["All makes"]],
            "fields_per_group": {g: [f for f in fields if F.FIELDS[f][2] == g] for g in F.GROUPS}}
    return {"values": values, "with_evidence": with_ev, "with_url": with_url, "n_fields": len(fields)}, heat


def per_make(c):
    return [{"make": r[0], "models": r[1], "variants": r[2]} for r in rows(
        c, "select ma.name, count(distinct mo.id), count(v.id) from manufacturer ma left join model mo on mo.manufacturer_id=ma.id "
           "left join variant v on v.model_id=mo.id group by ma.id order by 3 desc, 1")]


ENTITY_TABLES = ["manufacturer", "model", "generation", "variant", "powertrain", "warranty", "source", "source_observation",
                 "field_provenance", "evidence_quarantine", "evidence_amendment", "safety_test", "safety_test_applicability",
                 "safety_rating", "professional_assessment", "owner_rating", "owner_theme"]


def reviews_block(c):
    out = {"expert_rows": 0, "expert_models": 0, "owner_rows": 0, "owner_models": 0, "owner_ratings_total": 0}
    have_pa, have_or = has(c, "professional_assessment"), has(c, "owner_rating")
    expert, owner = {}, {}
    if have_pa:
        for mid, a, s, mx in rows(c, "select model_id, source_aspect, score, scale_max from professional_assessment "
                                     "where status='current' order by observed_at, id"):
            expert[(mid, a)] = (s, mx)
    if have_or:
        for mid, a, s, mx, n in rows(c, "select model_id, source_aspect, score, scale_max, rating_count from owner_rating "
                                        "where status='current' order by observed_at, id"):
            owner[(mid, a)] = (s, mx, n)
    out["expert_rows"] = len(expert)
    out["owner_rows"] = len(owner)
    out["expert_models"] = len({m for m, _ in expert})
    out["owner_models"] = len({m for m, _ in owner})
    out["owner_ratings_total"] = sum((v[2] or 0) for (m, a), v in owner.items() if a == "overall")
    models = {r[0]: {"make": r[1], "model": r[2], "variants": r[3]} for r in rows(
        c, "select mo.id, ma.name, mo.name, (select count(*) from variant v where v.model_id=mo.id) "
           "from model mo join manufacturer ma on ma.id=mo.manufacturer_id order by ma.name, mo.name")}
    table = []
    for mid, m in models.items():
        e, o = expert.get((mid, "overall")), owner.get((mid, "overall"))
        table.append({"make": m["make"], "model": m["model"], "variants": m["variants"],
                      "expert": e[0] if e else None, "owner": o[0] if o else None, "count": o[2] if o else None})
    both = sum(1 for t in table if t["expert"] is not None and t["owner"] is not None)
    e_only = sum(1 for t in table if t["expert"] is not None and t["owner"] is None)
    o_only = sum(1 for t in table if t["expert"] is None and t["owner"] is not None)
    cover = {"both": both, "expert_only": e_only, "owner_only": o_only, "neither": len(table) - both - e_only - o_only, "total": len(table)}

    def aspects(store, with_scale):
        by = {}
        for (mid, a), v in store.items():
            if mid in models:
                by.setdefault(a, []).append([models[mid]["make"] + " " + models[mid]["model"], v[0]])
        order = sorted(by, key=lambda a: (a != "overall", a))
        res = [{"aspect": a, "points": sorted(by[a], key=lambda p: (p[1], p[0]))} for a in order]
        smax = max([v[1] for v in store.values()] or [0])
        allv = [p[1] for r in res for p in r["points"]]
        amin = math.floor(min(allv)) if allv else 0
        return {"rows": res, "scale_max": smax, "axis_min": amin}

    themes = []
    theme_rows = 0
    if has(c, "owner_theme"):
        theme_rows = one(c, "select count(*) from owner_theme")
        themes = [{"theme": r[0], "direction": r[1], "mentions": r[2], "models": r[3]} for r in rows(
            c, "select coalesce(label,theme), direction, sum(mentions), count(distinct model_id) from owner_theme "
               "group by 1,2 order by 3 desc, 1 limit 12")]
    return out, {"expert": aspects(expert, False), "owner": aspects(owner, True), "table": table, "coverage": cover,
                 "themes": themes, "theme_rows": theme_rows}


# ---------------------------------------------------------------- runs
def collect_runs(runs_dir):
    runs = []
    if not os.path.isdir(runs_dir):
        return runs
    for name in sorted(os.listdir(runs_dir)):
        j = read_json(os.path.join(runs_dir, name, "run.json"))
        if not j:
            continue
        runs.append({"name": name, "json": j, "started": j.get("started") or "", "dir": os.path.join(runs_dir, name)})
    runs.sort(key=lambda r: (r["started"], r["name"]))
    return runs


def gate_rows(j):
    """{table: (before, after)} from the 'rows' gate detail strings, e.g. 'model 62->90'."""
    out = {}
    g = ((j.get("stage") or {}).get("gates") or {}).get("rows") or {}
    for s in g.get("detail", []):
        m = re.match(r"^(\w+) (\d+)->(\d+)$", s)
        if m:
            out[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    return out


def run_kind(r):
    j = r["json"]
    if r["name"].startswith("reviews"):
        return "Review layers"
    if j.get("audit_scope") == "full" and j.get("full"):
        return "Full audit"
    return "Full run" if j.get("full") else "Incremental run"


def runs_table(runs):
    out = []
    for r in runs:
        j = r["json"]
        w = j.get("write")
        out.append({"name": r["name"], "started": r["started"][:10], "kind": run_kind(r),
                    "wrote": bool(w), "rows_written": (w or {}).get("rows"),
                    "stopped": j.get("stopped"), "idempotent": (j.get("stage") or {}).get("idempotent"),
                    "gates_ok": all(v.get("ok") for v in ((j.get("stage") or {}).get("gates") or {}).values()) if (j.get("stage") or {}).get("gates") else None})
    return out


def verify_counts(rows_):
    c = {"match": 0, "mismatch": 0, "unreachable": 0, "verifier_error": 0}
    for r in rows_:
        c[r.get("verdict")] = c.get(r.get("verdict"), 0) + 1
    c["n"] = len(rows_)
    d = c["match"] + c["mismatch"]
    c["accuracy"] = (c["match"] / d) if d else None
    c["ci"] = wilson(c["match"], d)
    return c


def trust_block(runs):
    best = None
    for r in runs:   # the latest run that carried a full audit sample; otherwise the one with the largest sample
        res = read_jsonl(os.path.join(r["dir"], "verify", "results.jsonl"))
        if not res:
            continue
        rank = (1 if r["json"].get("audit_scope") else 0, len(res) if not r["json"].get("audit_scope") else 0, r["started"])
        if best is None or rank >= best[0]:
            best = (rank, r, res)
    per_run = []
    for r in runs:
        res = read_jsonl(os.path.join(r["dir"], "verify", "results.jsonl"))
        if res:
            per_run.append(dict(name=r["name"], **verify_counts(res)))
    if not best:
        return None, per_run
    _, run, res = best
    by_class = {k: verify_counts([x for x in res if x.get("source_class") == k]) for k in CLASS_ORDER if any(x.get("source_class") == k for x in res)}
    by_group = {g: verify_counts([x for x in res if x.get("group") == g]) for g in F.GROUPS if any(x.get("group") == g for x in res)}
    grid = {}
    for k in by_class:
        for g in by_group:
            sub = [x for x in res if x.get("source_class") == k and x.get("group") == g]
            if sub:
                grid["%s/%s" % (k, g)] = verify_counts(sub)
    legacy = [x for x in res if x.get("source_class") == "legacy"]
    lp = [x for x in legacy if x.get("group") == "price"]
    lnp = [x for x in legacy if x.get("group") != "price"]
    leg = {"mismatch_total": sum(1 for x in legacy if x["verdict"] == "mismatch"),
           "mismatch_price": sum(1 for x in lp if x["verdict"] == "mismatch"),
           "all": verify_counts(legacy), "price": verify_counts(lp), "non_price": verify_counts(lnp)}
    planted = read_jsonl(os.path.join(run["dir"], "verify", "planted.jsonl"))
    pl = {"n": len(planted), "flagged": sum(1 for x in planted if x.get("verdict") == "mismatch")}
    j = run["json"]
    return {"run": run["name"], "started": run["started"][:10], "n": len(res), "overall": verify_counts(res), "by_class": by_class,
            "by_group": by_group, "grid": grid, "legacy": leg, "planted": pl,
            "class_order": CLASS_ORDER, "class_label": CLASS_LABEL, "class_explain": CLASS_EXPLAIN, "groups": F.GROUPS,
            "legacy_cells": (j.get("audit_legacy") or {}).get("cells"),
            "legacy_checkable": (j.get("audit_legacy") or {}).get("with_current_page")}, per_run


# ---------------------------------------------------------------- history repo
def git(repo, *args):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def collect_history(repo):
    """KB states from the local history repo (read only: git tag, log, show). Empty list when unreadable."""
    if not repo or not os.path.isdir(os.path.join(repo, ".git")):
        return []
    tags = git(repo, "tag", "--list", "kb-run-*")
    if not tags:
        return []
    items = []
    for t in tags.split():
        subj = git(repo, "log", "-1", "--format=%s", t)
        when = git(repo, "log", "-1", "--format=%cI", t)
        if not subj or not when:
            continue
        m = re.search(r"\(([0-9a-f]{40})\)", subj)
        items.append((when.strip(), t, subj.strip(), m.group(1) if m else None))
    items.sort()
    seen, out = set(), []
    for when, t, subj, sha in items:
        key = sha or t
        if key in seen:
            continue
        seen.add(key)
        counts = {}
        for tb in ("model", "variant", "professional_assessment", "owner_rating"):
            txt = git(repo, "show", "%s:tables/%s.jsonl" % (t, tb))
            counts[tb] = (len([ln for ln in txt.splitlines() if ln.strip()]) if txt is not None else None)
        base = t[len("kb-run-"):]
        label = ("After run " + base[:-6]) if base.endswith("-after") else ("Before run " + base)
        out.append({"tag": t, "date": when[:10], "label": label, "sha8": (sha or "")[:8], "models": counts["model"],
                    "variants": counts["variant"],
                    "review_rows": (counts["professional_assessment"] or 0) + (counts["owner_rating"] or 0)
                    if counts["professional_assessment"] is not None or counts["owner_rating"] is not None else None})
    return out


def growth_from_runs(runs):
    """Fallback and cross-check: coverage before/after from the run folders that wrote to the KB."""
    out = []
    for r in runs:
        j = r["json"]
        if not j.get("write"):
            continue
        g = gate_rows(j)
        cb, ca = j.get("coverage_before"), j.get("coverage_after")
        if cb and not out:
            out.append({"label": "Before run " + r["name"], "date": r["started"][:10], "models": cb["models"], "variants": cb["variants"],
                        "review_rows": 0, "sha8": (j["write"].get("sha1_before") or "")[:8]})
        if ca:
            m, v = ca["models"], ca["variants"]
        else:
            m, v = g.get("model", (None, None))[1], g.get("variant", (None, None))[1]
        rv = sum(g.get(t, (0, 0))[1] for t in ("professional_assessment", "owner_rating")) if g else 0
        out.append({"label": "After run " + r["name"], "date": r["started"][:10], "models": m, "variants": v, "review_rows": rv,
                    "sha8": (j["write"].get("sha1_after") or "")[:8]})
    return out


# ---------------------------------------------------------------- pipeline text and numbers
def pipeline_stages(runs, trust, glance, kb_counts):
    disc_run = next((r for r in reversed(runs) if r["json"].get("discovery")), None)
    write_run = next((r for r in reversed(runs) if r["json"].get("write") and r["json"].get("discovery")), None)
    dj = disc_run["json"] if disc_run else {}
    st = dj.get("stats") or {}
    gates = (dj.get("stage") or {}).get("gates") or {}
    fetch = dj.get("fetch") or {}

    def num(value, label, run):
        return {"value": value, "label": label, "run": run} if value is not None else None

    rn = disc_run["name"] if disc_run else None
    new_models = (dj.get("discovery") or {}).get("NEW_MODEL")
    pages = (fetch.get("network", 0) + fetch.get("cache", 0)) if fetch else None
    ok_gates = sum(1 for g in gates.values() if g.get("ok"))
    wj = write_run["json"] if write_run else {}
    S = [
        dict(id="sources", title=["Sources"], sub=["CarWale, CarDekho specs", "OEM brochure PDFs", "Autocar India scores", "CarWale owner ratings", "Owner-saved forum pages"],
             text="Specs and prices come from the CarWale and CarDekho model pages. OEM brochure PDFs are read page by page and outrank the sites. Autocar India supplies expert scores and CarWale supplies owner ratings and reviews. Forum pages the owner saves by hand are the source for owner themes; the tool never contacts that forum.",
             number=num(kb_counts.get("source_observation"), "source observations recorded in the KB", "KB copy")),
        dict(id="discovery", title=["Discovery"], sub=["What is new,", "changed or gone"],
             text="Reads each brand's listing on both sites and compares it with the KB. Every model is sorted as new, existing, no longer listed, upcoming or out of scope. An incremental run processes only models whose listing changed.",
             number=num(new_models, "new models found (%s models processed)" % (dj.get("processed")), rn)),
        dict(id="extraction", title=["Extraction"], sub=["Structured page data,", "no LLM for specs"],
             text="Reads the structured data both sites embed in each page. No language model is used for specs. Every value keeps its address, the time it was fetched and the method used.",
             number=num(pages, "pages read (%s fetched, %s from cache)" % (fetch.get("network"), fetch.get("cache")), rn)),
        dict(id="linking", title=["Variant linking"], sub=["Same fuel, gearbox,", "trim words; price", "within 0.5%"],
             text="A CarWale version is linked to a CarDekho variant, and both to a KB variant, only when fuel, gearbox class and trim words are equal and the ex-showroom prices are within 0.5%. A page that turns out to show a different variant than requested is discarded.",
             number=num(st.get("variants_matched"), "variants linked across both sites and the KB", rn)),
        dict(id="reconcile", title=["Reconciliation"], sub=["Brochure beats two", "agreeing sites; one", "site alone decides", "nothing"],
             text="An OEM brochure value outranks two agreeing sites. Two agreeing sites may fill a blank or confirm an existing value. One site alone decides nothing, so the cell stays blank and is listed with the reason. Every disagreement between sources is logged.",
             number=num(dj.get("conflicts"), "disagreements between sources logged", rn)),
        dict(id="staging", title=["Staging copy"], sub=["Changes go to a copy,", "never the live file"],
             text="Every change is first applied to a scratch copy of the KB. The live file is not opened for writing at this point.",
             number=num((dj.get("stage") or {}).get("ops"), "operations staged on the copy", rn)),
        dict(id="gates", title=["Four gates"], sub=["Schema, provenance,", "rows never dropped,", "every change explained"],
             text="Four scripted checks run on the copy: the schema is unchanged and the database is intact, every new or changed value has provenance, no table loses rows, and every changed row appears in the run log. A second run on the result must change nothing. If any gate fails, nothing reaches the KB.",
             number=num("%d of %d" % (ok_gates, len(gates)) if gates else None,
                        "gates passed%s" % ("; the idempotency re-run made 0 changes" if (dj.get("stage") or {}).get("idempotent") else ""), rn)),
        dict(id="kb", title=["Knowledge base"], sub=["Written in one", "transaction after", "a backup"],
             text="Only after the gates pass: a check that nothing else holds the file, a hash check, a backup, then one transaction, an integrity check and a table-by-table comparison with the staging copy. Rows are never deleted. A model or variant no longer listed is only flagged for the owner.",
             number=num((wj.get("write") or {}).get("rows"), "rows written, integrity check %s" % ((wj.get("write") or {}).get("integrity_check")), write_run["name"] if write_run else None)),
        dict(id="verify", title=["Independent", "verification"], sub=["A different model", "re-reads the source"],
             text="A different model from the one that extracted values re-reads the source page, or the cited brochure page, for a random sample of values and says whether the source supports each one. Its verdicts go to a file that nothing else edits, and all accuracy figures come from that file alone.",
             number=num(trust["n"] if trust else None, "cells re-checked; %s decided as match or mismatch" % (trust["overall"]["match"] + trust["overall"]["mismatch"] if trust else ""), trust["run"] if trust else None)),
        dict(id="review", title=["Owner review file"], sub=["Only what needs a", "human decision"],
             text="Anything the tool cannot decide goes into one review file with tick boxes: values both sites agree on but that differ from the KB, blanks both sites could fill, and models that look like a facelift or are no longer listed. Nothing in it is applied until the owner approves it.",
             number=num(dj.get("review_items"), "items waiting for the owner", rn)),
        dict(id="export", title=["Export"], sub=["Catalogue and scores", "for the engine"],
             text="A separate step, outside kbpipe, turns the KB into the data files the recommendation engine reads. kbpipe itself does not export or open pull requests.",
             number=None),
        dict(id="engine", title=["Recommendation", "engine"], sub=["Unknown values stay", "unknown"],
             text="The engine ranks cars from the KB's values and from the expert and owner scores. A value the KB does not hold is treated as unknown, not as a no.",
             number=num(glance["variants"], "variants across %s models available to it" % fmt(glance["models"]), "KB copy")),
    ]
    return S


def fmt(n):
    return "{:,}".format(n)


# ---------------------------------------------------------------- build
def build(db_path, runs_dir, history_repo, kb_sha1, date):
    c = sqlite3.connect("file:%s?immutable=1" % db_path, uri=True)
    c.row_factory = sqlite3.Row
    base, vrows, fields = collect_kb(c)
    vals, heat = values_and_coverage(c, vrows, fields)
    rev_glance, rev = reviews_block(c)
    kb_counts = {t: one(c, 'select count(*) from "%s"' % t, default=None) if has(c, t) else None for t in ENTITY_TABLES}
    glance = dict(base, **vals, **rev_glance)
    runs = collect_runs(runs_dir)
    trust, per_run = trust_block(runs)
    hist = collect_history(history_repo)
    growth = hist or growth_from_runs(runs)
    growth_src = "history" if hist else "runs"
    c.close()
    return {
        "meta": {"generated": date, "kb_hash8": kb_sha1[:8], "growth_source": growth_src,
                 "runs_used": [r["name"] for r in runs]},
        "glance": glance,
        "stages": pipeline_stages(runs, trust, glance, kb_counts),
        "entities": kb_counts,
        "per_make": per_make_safe(db_path),
        "heat": heat,
        "growth": growth,
        "runs": runs_table(runs),
        "trust": trust,
        "verify_runs": per_run,
        "reviews": rev,
    }


def per_make_safe(db_path):
    c = sqlite3.connect("file:%s?immutable=1" % db_path, uri=True)
    try:
        return per_make(c)
    finally:
        c.close()


def render(data, template=None):
    blob = json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    return (template or PAGE).replace("/*__DATA__*/", blob)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kbpipe.dashboard", description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(config.ROOT, "knowledge_base", "reports", "kb_dashboard", "index.html"))
    ap.add_argument("--db", help="a read copy of the KB. Default: make one from the production file with the holder and hash checks")
    ap.add_argument("--runs", help="runs folder (default: config runs_dir)")
    ap.add_argument("--history", help="history repo (default: config history_repo)")
    ap.add_argument("--date", help="override the generated-on date (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    cfg = config.load()
    if a.db:
        db, sha = a.db, kb.sha1(a.db)
    else:
        db = DEFAULT_COPY
        sha = kb.copy_for_read(cfg["prod_db"], db)
    date = a.date or datetime.date.today().isoformat()
    data = build(db, a.runs or cfg["runs_dir"], a.history or cfg["history_repo"], sha, date)
    html = render(data)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d bytes), KB %s" % (a.out, len(html.encode("utf-8")), sha[:8]))
    return 0


# ---------------------------------------------------------------- page
PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CarRec Knowledge Base</title>
<style>
/* Layout: one calm column on a cool grey ground. Sections are separated by space and a hairline, not boxed. The pipeline
   diagram is the only large object; the single accent (deep teal) marks the knowledge base and every measured value. */
:root{
  --bg:#f3f5f7; --surface:#ffffff; --ink:#111a24; --ink2:#44505d; --muted:#5f6b78; --line:#d8dee5; --line2:#e8ecf0;
  --accent:#0a6a75; --accent-ink:#ffffff; --accent-soft:#dcecee; --warn:#b4401a; --neutral:#7d8894;
  --heat-lo:#e9f2f3; --heat-hi:#064e58; --heat-on-lo:#111a24; --heat-on-hi:#ffffff; --focus:#0a6a75;
  --font:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --shadow:0 1px 2px rgba(17,26,36,.06);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0c1219; --surface:#141c25; --ink:#e8edf2; --ink2:#b0bac5; --muted:#8e9aa7; --line:#27323f; --line2:#1d2733;
  --accent:#5cc3ce; --accent-ink:#0c1219; --accent-soft:#143037; --warn:#f08c63; --neutral:#7d8894;
  --heat-lo:#15262c; --heat-hi:#7dd6df; --heat-on-lo:#e8edf2; --heat-on-hi:#0c1219; --focus:#5cc3ce; --shadow:none; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0c1219; --surface:#141c25; --ink:#e8edf2; --ink2:#b0bac5; --muted:#8e9aa7; --line:#27323f; --line2:#1d2733;
  --accent:#5cc3ce; --accent-ink:#0c1219; --accent-soft:#143037; --warn:#f08c63; --neutral:#7d8894;
  --heat-lo:#15262c; --heat-hi:#7dd6df; --heat-on-lo:#e8edf2; --heat-on-hi:#0c1219; --focus:#5cc3ce; --shadow:none; color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:16px;line-height:1.55;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 56px}
.wrap{max-width:1120px;margin:0 auto}
a{color:var(--accent)}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:3px}
h1,h2,h3{margin:0;line-height:1.15;text-wrap:balance;letter-spacing:-.01em}
h1{font-size:clamp(2rem,5vw,3.1rem);font-weight:720;letter-spacing:-.025em}
h2{font-size:clamp(1.4rem,3vw,1.8rem);font-weight:700}
h3{font-size:1.02rem;font-weight:650}
p{margin:0}
.lede{max-width:62ch;color:var(--ink2);font-size:1.12rem}
.num{font-variant-numeric:tabular-nums}
.mono{font-family:var(--mono)}
.eyebrow{font-size:.74rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:650}
header.top{padding-top:28px;padding-bottom:30px;border-bottom:1px solid var(--line)}
.topbar{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between;margin-bottom:40px}
nav ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.88rem}
nav a{color:var(--ink2);text-decoration:none;border-bottom:1px solid transparent}
nav a:hover{color:var(--ink);border-bottom-color:var(--accent)}
button.theme{font:inherit;font-size:.82rem;color:var(--ink2);background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:5px 13px;cursor:pointer}
button.theme:hover{border-color:var(--accent);color:var(--ink)}
.meta{display:flex;flex-wrap:wrap;gap:6px 22px;margin-top:22px;font-size:.88rem;color:var(--muted)}
.meta b{color:var(--ink);font-weight:600}
section{padding-top:64px}
.sec-head{display:grid;gap:8px;margin-bottom:26px;max-width:72ch}
.sec-head p{color:var(--ink2)}
/* glance */
.glance{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0;border-top:1px solid var(--line);border-left:1px solid var(--line);background:var(--surface)}
.stat{padding:18px 18px 16px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);display:grid;gap:3px;align-content:start}
.stat .v{font-size:clamp(1.7rem,3.4vw,2.35rem);font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1.05}
.stat .l{font-size:.86rem;color:var(--ink2)}
.stat .s{font-size:.76rem;color:var(--muted)}
.group-label{grid-column:1/-1;padding:9px 18px;font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:650;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--bg)}
/* diagram panels */
.panel{background:var(--surface);border:1px solid var(--line);border-radius:6px;box-shadow:var(--shadow)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.diagram{min-width:960px;padding:10px 6px 4px}
.diagram svg{display:block;width:100%;height:auto}
svg text{font-family:var(--font);fill:var(--ink)}
svg .t2{fill:var(--ink2)} svg .tm{fill:var(--muted)}
.node rect.box{fill:var(--surface);stroke:var(--line);stroke-width:1.5}
.node{cursor:pointer;outline:none}
.node:hover rect.box,.node:focus rect.box{stroke:var(--accent);stroke-width:2.5}
.node.sel rect.box{stroke:var(--accent);stroke-width:3}
.node.kbnode rect.box{fill:var(--accent);stroke:var(--accent)}
.node.kbnode text{fill:var(--accent-ink)!important}
.node .step{font-size:11px;font-weight:700;fill:var(--muted)}
.node:focus-visible rect.box{stroke-dasharray:none;stroke:var(--focus);stroke-width:3.5}
.edge{stroke:var(--ink2);stroke-width:1.6;fill:none}
.tag rect{fill:var(--surface);stroke:var(--accent);stroke-width:1.2;stroke-dasharray:4 3}
.tag text{font-size:12.5px;font-weight:600;fill:var(--ink)}
.tagline{stroke:var(--accent);stroke-width:1.2;stroke-dasharray:3 3;fill:none}
.stage-detail{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:20px 36px;padding:22px 24px;border-top:1px solid var(--line)}
.stage-detail h3{font-size:1.25rem;margin-bottom:6px}
.stage-detail .big{font-size:2.3rem;font-weight:720;letter-spacing:-.02em;color:var(--accent);line-height:1.05;font-variant-numeric:tabular-nums}
.stage-detail .biglabel{font-size:.9rem;color:var(--ink2)}
.stage-detail .src{font-size:.78rem;color:var(--muted);margin-top:4px}
.hint{font-size:.82rem;color:var(--muted);padding:10px 24px 0}
.rules{display:flex;flex-wrap:wrap;gap:8px 24px;padding:14px 24px 18px;border-top:1px solid var(--line);font-size:.88rem;color:var(--ink2)}
.rules b{color:var(--ink)}
/* bars */
.twocol{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:28px 40px}
.bars{display:grid;gap:7px}
.brow{display:grid;grid-template-columns:minmax(92px,128px) minmax(0,1fr) 54px;gap:10px;align-items:center;font-size:.88rem}
.brow .bl{color:var(--ink2);overflow-wrap:anywhere}
.brow .track{height:14px;background:var(--line2);border-radius:2px 7px 7px 2px;overflow:hidden}
.brow .fill{display:block;height:100%;background:var(--accent);border-radius:2px 7px 7px 2px}
.brow .bv{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.cap{font-size:.82rem;color:var(--muted);margin-top:10px;max-width:80ch}
.cap.ink{color:var(--ink2)}
/* heatmap */
table{border-collapse:collapse;width:100%}
.heat{min-width:640px;font-variant-numeric:tabular-nums;font-size:.86rem}
.heat th,.heat td{padding:0;text-align:center;border:2px solid var(--surface)}
.heat thead th{font-weight:600;color:var(--ink2);padding:8px 4px;font-size:.78rem;text-transform:capitalize}
.heat tbody th{text-align:left;font-weight:600;padding:0 12px 0 10px;white-space:nowrap;color:var(--ink);background:var(--surface);position:sticky;left:0}
.heat tbody th small{display:block;font-weight:400;color:var(--muted);font-size:.72rem}
.heat td{height:40px;font-weight:650;min-width:64px}
.heat tr.all td,.heat tr.all th{border-top:6px solid var(--surface)}
.scale{display:flex;align-items:center;gap:10px;font-size:.8rem;color:var(--muted);margin-top:12px}
.scale i{display:block;width:180px;height:12px;border-radius:2px;background:linear-gradient(90deg,var(--heat-lo),var(--heat-hi));border:1px solid var(--line)}
/* trust */
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.84rem;color:var(--ink2);margin-bottom:14px}
.legend span{display:inline-flex;gap:7px;align-items:center}
.sw{display:inline-block;width:14px;height:14px;border-radius:2px;border:1px solid var(--line)}
.sw.match,.seg.match{background:var(--accent)}
.sw.mismatch,.seg.mismatch{background:var(--warn)}
.sw.unreachable,.seg.unreachable{background:repeating-linear-gradient(135deg,var(--neutral) 0 3px,var(--surface) 3px 6px)}
.sw.verifier_error,.seg.verifier_error{background:var(--ink2)}
.trow{display:grid;grid-template-columns:minmax(0,210px) minmax(0,1fr) minmax(120px,150px);gap:6px 16px;align-items:center;padding:11px 0;border-bottom:1px solid var(--line2)}
.trow .tl b{display:block;font-weight:650}
.trow .tl span{font-size:.8rem;color:var(--muted);display:block;line-height:1.35}
.stack{display:flex;height:26px;border-radius:2px 8px 8px 2px;overflow:hidden;gap:2px;background:var(--surface)}
.seg{display:flex;align-items:center;justify-content:center;font-size:.74rem;font-weight:700;color:#fff;min-width:0;overflow:hidden;font-variant-numeric:tabular-nums}
.seg.match{color:var(--accent-ink)}
.seg.unreachable b{background:var(--surface);color:var(--ink);padding:1px 6px;border-radius:3px;font-weight:700}
.seg.verifier_error{color:var(--bg)}
.trow .acc{text-align:right;font-variant-numeric:tabular-nums}
.trow .acc b{font-size:1.15rem}
.trow .acc span{display:block;font-size:.74rem;color:var(--muted)}
.callout{border-left:3px solid var(--accent);padding:4px 0 4px 16px;color:var(--ink2);max-width:80ch}
.callout b{color:var(--ink)}
.mini{width:100%;font-size:.86rem;font-variant-numeric:tabular-nums}
.mini th,.mini td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line2)}
.mini th:first-child,.mini td:first-child{text-align:left}
.mini thead th{color:var(--muted);font-weight:600;font-size:.76rem;border-bottom:1px solid var(--line)}
/* reviews */
.stripnote{font-size:.82rem;color:var(--muted);margin:2px 0 10px}
.covbar{display:flex;height:30px;border-radius:2px 8px 8px 2px;overflow:hidden;gap:2px;margin:6px 0 8px}
.covbar div{display:flex;align-items:center;padding:0 10px;font-size:.8rem;font-weight:700;white-space:nowrap;overflow:hidden;font-variant-numeric:tabular-nums}
.cv-both{background:var(--accent);color:var(--accent-ink)}
.cv-e{background:var(--accent-soft);color:var(--ink);border:1px solid var(--accent)}
.cv-o{background:repeating-linear-gradient(135deg,var(--accent-soft) 0 4px,var(--surface) 4px 8px);color:var(--ink);border:1px solid var(--accent)}
.cv-n{background:var(--line2);color:var(--ink2)}
.tbl-wrap{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
.sortable{min-width:560px;font-size:.9rem;font-variant-numeric:tabular-nums}
.sortable th,.sortable td{padding:8px 12px;border-bottom:1px solid var(--line2);text-align:right;white-space:nowrap}
.sortable th:nth-child(-n+2),.sortable td:nth-child(-n+2){text-align:left}
.sortable thead th{position:sticky;top:0;background:var(--surface);z-index:1;border-bottom:1px solid var(--line);padding:0}
.sortable thead button{all:unset;box-sizing:border-box;cursor:pointer;display:block;width:100%;padding:9px 12px;font-size:.78rem;font-weight:650;color:var(--ink2);text-align:inherit}
.sortable thead button:hover{color:var(--ink)}
.sortable thead button:focus-visible{outline:3px solid var(--focus);outline-offset:-3px}
.sortable thead th[aria-sort="ascending"] button::after{content:" \25B2";font-size:.7em}
.sortable thead th[aria-sort="descending"] button::after{content:" \25BC";font-size:.7em}
.nodata{color:var(--muted)}
.themes{display:grid;gap:6px}
/* footer */
footer{margin-top:72px;border-top:1px solid var(--line);padding-top:32px}
.read{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:24px 36px}
.read h3{margin-bottom:6px}
.read p{font-size:.94rem;color:var(--ink2)}
/* tooltip */
#tip{position:fixed;z-index:50;pointer-events:none;background:var(--ink);color:var(--bg);font-size:.82rem;padding:6px 10px;border-radius:4px;max-width:280px;opacity:0;transition:opacity .08s;line-height:1.35}
#tip.on{opacity:1}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (max-width:760px){
  section{padding-top:48px}
  .stage-detail{grid-template-columns:minmax(0,1fr)}
  .trow{grid-template-columns:minmax(0,1fr)}
  .trow .acc{text-align:left}
  .stage-detail,.rules,.hint{padding-left:16px;padding-right:16px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<div class="wrap">
<header class="top" id="top">
  <div class="topbar">
    <nav aria-label="Sections"><ul>
      <li><a href="#glance">At a glance</a></li><li><a href="#pipeline">Pipeline</a></li><li><a href="#contents">What is in it</a></li>
      <li><a href="#coverage">Coverage</a></li><li><a href="#growth">Growth</a></li><li><a href="#trust">Trust</a></li>
      <li><a href="#reviews">Reviews</a></li><li><a href="#read">How to read this</a></li></ul></nav>
    <button class="theme" id="themebtn" type="button">Theme: auto</button>
  </div>
  <p class="eyebrow">Car data for India, with receipts</p>
  <h1 style="margin-top:10px">CarRec knowledge base</h1>
  <p class="lede" style="margin-top:16px">A verified, source-tracked database of new cars sold in India. It feeds a recommendation engine, and a scripted pipeline keeps it complete and current without inventing values.</p>
  <div class="meta"><span>Generated on <b id="m-date" class="num"></b></span><span>KB hash <b id="m-hash" class="mono"></b></span><span id="m-runs"></span></div>
</header>

<section id="glance" aria-labelledby="h-glance">
  <div class="sec-head"><h2 id="h-glance">At a glance</h2><p>What the database holds right now, counted from a read-only copy of the file.</p></div>
  <div class="glance" id="glance-grid"></div>
  <p class="cap" id="glance-note"></p>
</section>

<section id="pipeline" aria-labelledby="h-pipe">
  <div class="sec-head"><h2 id="h-pipe">How the knowledge base is kept up to date</h2>
    <p>Each box is one stage of a run. Select a stage, by click, tap or keyboard, to see what it does and one figure from a real run.</p></div>
  <div class="panel">
    <p class="hint">Reads left to right, then continues on the second row. The dashed labels are rules that hold at every run.</p>
    <div class="scroll" tabindex="0" role="region" aria-label="Pipeline diagram, scrolls sideways on narrow screens"><div class="diagram" id="pipe-svg"></div></div>
    <div class="stage-detail" id="stage-detail" aria-live="polite"></div>
  </div>
</section>

<section id="contents" aria-labelledby="h-ent">
  <div class="sec-head"><h2 id="h-ent">What is in the knowledge base</h2>
    <p>The main tables, in four groups, with the number of rows in each. Arrows run from the table that is referred to, to the table that refers to it.</p></div>
  <div class="panel"><div class="scroll" tabindex="0" role="region" aria-label="Table diagram, scrolls sideways on narrow screens"><div class="diagram" id="ent-svg" style="min-width:880px"></div></div></div>
  <p class="cap">A variant is one trim with one engine and gearbox, for example a specific petrol manual. A powertrain is an engine description shared by several variants. Every value on a variant can point back to the observations that support it.</p>
</section>

<section id="coverage" aria-labelledby="h-cov">
  <div class="sec-head"><h2 id="h-cov">Coverage</h2>
    <p>How complete the data is, by manufacturer and by kind of fact. A blank is a blank: it means the pipeline had no source it was allowed to trust.</p></div>
  <h3 style="margin-bottom:10px">Share of values present, by manufacturer and field group</h3>
  <div class="panel scroll" tabindex="0" role="region" aria-label="Heatmap of coverage"><div id="heat" style="padding:10px"></div></div>
  <div class="scale"><span>0%</span><i aria-hidden="true"></i><span>100%</span><span style="margin-left:8px">Stronger colour means more complete. Each cell prints its value.</span></div>
  <p class="cap" id="heat-note"></p>
  <div class="twocol" style="margin-top:36px">
    <div><h3 style="margin-bottom:12px">Models per manufacturer</h3><div class="bars" id="bars-models"></div></div>
    <div><h3 style="margin-bottom:12px">Variants per manufacturer</h3><div class="bars" id="bars-variants"></div></div>
  </div>
</section>

<section id="growth" aria-labelledby="h-growth">
  <div class="sec-head"><h2 id="h-growth">Growth</h2><p id="growth-intro"></p></div>
  <div class="twocol" id="growth-charts" style="gap:20px 28px"></div>
  <div class="scroll" style="margin-top:22px"><table class="mini" id="growth-table"></table></div>
  <h3 style="margin:34px 0 8px">Runs behind these figures</h3>
  <div class="scroll"><table class="mini" id="runs-table"></table></div>
</section>

<section id="trust" aria-labelledby="h-trust">
  <div class="sec-head"><h2 id="h-trust">Trust</h2><p id="trust-intro"></p></div>
  <div id="trust-body"></div>
</section>

<section id="reviews" aria-labelledby="h-rev">
  <div class="sec-head"><h2 id="h-rev">Reviews layer</h2>
    <p>Alongside the specs, the KB keeps what experts and owners think. Expert scores come from Autocar India (out of 10). Owner ratings come from CarWale (out of 5). Both are stored as scores per model, never mixed into spec values.</p></div>
  <h3>Which models have scores</h3>
  <div id="cov-bar"></div>
  <div class="twocol" style="margin-top:34px;gap:34px 44px">
    <div><h3>Expert scores by aspect</h3><p class="stripnote" id="expert-note"></p><div id="strip-expert"></div></div>
    <div><h3>Owner ratings by aspect</h3><p class="stripnote" id="owner-note"></p><div id="strip-owner"></div></div>
  </div>
  <h3 style="margin:44px 0 6px">Every model, sortable</h3>
  <p class="stripnote">Select a column heading to sort. Blank means the source had no page or no score for that model.</p>
  <div class="tbl-wrap" tabindex="0" role="region" aria-label="Model scores table"><table class="sortable" id="model-table"></table></div>
  <h3 style="margin:44px 0 8px">Owner themes</h3>
  <div id="themes"></div>
</section>

<footer id="read" aria-labelledby="h-read">
  <h2 id="h-read" style="margin-bottom:22px">How to read this</h2>
  <div class="read">
    <div><h3>Verified</h3><p>A value is verified when it traces to a source the pipeline is allowed to trust: an OEM brochure page, or two sites that agree on the same variant. A separate model then re-reads a random sample of those sources to check the stored value. Verified does not mean certain. Sites can copy each other, and the Trust section shows what the re-check found.</p></div>
    <div><h3>Unknown</h3><p>Unknown stays unknown. When no allowed source states a value, the cell is left empty and the reason is logged. It is never filled with a guess, an average or a value borrowed from a similar model. An empty cell is not a no: a feature the KB marks 0 was stated as absent, an empty cell was not stated at all.</p></div>
    <div><h3>This page</h3><p>Every figure is computed from a read-only copy of the database and from the run folders, and the source of each is named. Generated on <span class="num" id="f-date"></span> from KB hash <span class="mono" id="f-hash"></span>. Rebuilding it from the same inputs gives the same page apart from this date.</p></div>
  </div>
</footer>
</div>
<div id="tip" role="tooltip"></div>
<script id="data" type="application/json">/*__DATA__*/</script>
<script>
(function(){
'use strict';
var D=JSON.parse(document.getElementById('data').textContent);
function $(s,r){return (r||document).querySelector(s);}
function fmt(n){return n==null?'–':Number(n).toLocaleString('en-US');}
function pct(x,d){return x==null?'n/a':(x*100).toFixed(d==null?1:d)+'%';}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function el(id){return document.getElementById(id);}
var G=D.glance;

/* ---- theme */
(function(){
  var b=el('themebtn'),modes=['auto','light','dark'],i=0;
  try{var s=localStorage.getItem('kbdash-theme'); if(s&&modes.indexOf(s)>-1)i=modes.indexOf(s);}catch(e){}
  function apply(){var m=modes[i]; if(m==='auto')document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme',m); b.textContent='Theme: '+m;
    try{localStorage.setItem('kbdash-theme',m);}catch(e){} }
  b.addEventListener('click',function(){i=(i+1)%3;apply();rerender();});
  apply();
})();

/* ---- header and footer */
el('m-date').textContent=D.meta.generated; el('m-hash').textContent=D.meta.kb_hash8;
el('f-date').textContent=D.meta.generated; el('f-hash').textContent=D.meta.kb_hash8;
el('m-runs').textContent=D.meta.runs_used.length+' pipeline runs on record';

/* ---- glance */
(function(){
  var vs=G.values?G.with_evidence/G.values:null, vu=G.values?G.with_url/G.values:null;
  var items=[
    {g:'The catalogue'},
    {v:fmt(G.makes),l:'Manufacturers'},{v:fmt(G.models),l:'Models'},{v:fmt(G.variants),l:'Variants',s:'one trim, engine and gearbox each'},{v:fmt(G.powertrains),l:'Powertrains',s:'distinct engine descriptions'},
    {g:'The facts and where they come from'},
    {v:fmt(G.values),l:'Values recorded',s:'non-empty spec and feature cells across '+G.n_fields+' tracked fields'},
    {v:pct(vs,1),l:'Values with recorded source evidence',s:fmt(G.with_evidence)+' of '+fmt(G.values)+'; '+pct(vu,1)+' cite a web or PDF address'},
    {g:'Reviews'},
    {v:fmt(G.expert_rows),l:'Expert score rows',s:'across '+fmt(G.expert_models)+' models, out of 10'},
    {v:fmt(G.owner_rows),l:'Owner rating rows',s:'across '+fmt(G.owner_models)+' models, out of 5'},
    {v:fmt(G.owner_ratings_total),l:'Ratings behind the owner scores',s:'sum of each model’s overall rating count'}
  ];
  el('glance-grid').innerHTML=items.map(function(it){
    if(it.g)return '<div class="group-label">'+esc(it.g)+'</div>';
    return '<div class="stat"><span class="v">'+it.v+'</span><span class="l">'+esc(it.l)+'</span>'+(it.s?'<span class="s">'+esc(it.s)+'</span>':'')+'</div>';}).join('');
  el('glance-note').textContent='Values are counted from the canonical view of the KB (cells under quarantine are excluded; an edition inherits its base variant’s cells). A feature marked absent counts as a value; an empty cell does not.';
})();

/* ---- tooltip */
var tip=el('tip');
function showTip(t,x,y){tip.textContent=t;tip.classList.add('on');var w=tip.offsetWidth,h=tip.offsetHeight;var nx=Math.min(innerWidth-w-8,Math.max(8,x+12)),ny=y-h-12;if(ny<8)ny=y+16;tip.style.left=nx+'px';tip.style.top=ny+'px';}
function hideTip(){tip.classList.remove('on');}
document.addEventListener('mousemove',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');if(t)showTip(t.getAttribute('data-tip'),e.clientX,e.clientY);else hideTip();});
document.addEventListener('scroll',hideTip,true);

/* ---- pipeline diagram */
var NW=170,NH=140,GX=30,X0=20,YA=52,YB=272;
function nodePos(i){var row=i<6?0:1,col=i%6;return {x:X0+col*(NW+GX),y:row?YB:YA};}
var selStage='reconcile';
function pipeSvg(){
  var S=D.stages,p='';
  p+='<svg viewBox="0 0 1210 520" role="img" aria-labelledby="pt pd"><title id="pt">Pipeline stages</title><desc id="pd">Twelve stages from sources to the recommendation engine. Row one: sources, discovery, extraction, variant linking, reconciliation, staging copy. Row two: four gates, knowledge base, independent verification, owner review file, export, recommendation engine.</desc>';
  p+='<defs><marker id="ar" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--ink2)"/></marker></defs>';
  for(var i=0;i<S.length-1;i++){
    var a=nodePos(i),b=nodePos(i+1);
    if(i===5){var ax=a.x+NW/2,mid=(YA+NH+YB)/2;var bx=b.x+NW/2;p+='<path class="edge" marker-end="url(#ar)" d="M'+ax+' '+(a.y+NH)+'V'+mid+'H'+bx+'V'+(b.y-2)+'"/>';}
    else p+='<path class="edge" marker-end="url(#ar)" d="M'+(a.x+NW)+' '+(a.y+NH/2)+'H'+(b.x-2)+'"/>';
  }
  S.forEach(function(s,i){
    var q=nodePos(i),cx=q.x+NW/2,ty=q.y+26+(s.title.length>1?0:0);
    p+='<g class="node'+(s.id==='kb'?' kbnode':'')+(s.id===selStage?' sel':'')+'" tabindex="0" role="button" data-stage="'+s.id+'" aria-label="'+esc(s.title.join(' '))+'. Select for details.">';
    p+='<rect class="box" x="'+q.x+'" y="'+q.y+'" width="'+NW+'" height="'+NH+'" rx="6"/>';
    p+='<text class="step" x="'+(q.x+10)+'" y="'+(q.y+16)+'">'+(i+1)+'</text>';
    var y=q.y+36;
    s.title.forEach(function(t){p+='<text x="'+(q.x+NW/2)+'" y="'+y+'" text-anchor="middle" font-size="16" font-weight="700">'+esc(t)+'</text>';y+=19;});
    y+=6;
    s.sub.forEach(function(t){p+='<text class="t2" x="'+(q.x+NW/2)+'" y="'+y+'" text-anchor="middle" font-size="12.5">'+esc(t)+'</text>';y+=17;});
    p+='</g>';
  });
  // rule tags
  function tag(cx,y,w,txt,toY,fromY){var x=cx-w/2;return '<g class="tag"><rect x="'+x+'" y="'+y+'" width="'+w+'" height="26" rx="13"/><text x="'+cx+'" y="'+(y+17.5)+'" text-anchor="middle">'+esc(txt)+'</text></g><path class="tagline" d="M'+cx+' '+fromY+'V'+toY+'"/>';}
  var r4=nodePos(4);p+=tag(r4.x+NW/2,12,250,'Never fabricates: unknowns stay blank',YA-2,38);
  var g0=nodePos(6),k0=nodePos(7);
  p+=tag(g0.x+NW/2,YB+NH+28,176,'Never deletes rows',YB+NH+2,YB+NH+28);
  p+=tag(k0.x+NW/2,YB+NH+28,214,'Backup before every write',YB+NH+2,YB+NH+28);
  p+=tag(k0.x+NW/2+20,YB+NH+64,276,'Local git history of every KB state',YB+NH+54,YB+NH+64);
  p+='</svg>';
  return p;
}
function stageDetail(){
  var s=D.stages.filter(function(x){return x.id===selStage;})[0];if(!s)return;
  var n=s.number,h='<div><h3>'+esc(s.title.join(' '))+'</h3><p>'+esc(s.text)+'</p></div><div>';
  if(n)h+='<div class="big">'+(typeof n.value==='number'?fmt(n.value):esc(n.value))+'</div><div class="biglabel">'+esc(n.label)+'</div><div class="src">From '+(n.run==='KB copy'?'the KB copy this page was built from':'run '+esc(n.run))+'</div>';
  else h+='<div class="biglabel">No figure from the run folders for this stage.</div>';
  el('stage-detail').innerHTML=h+'</div>';
}
function bindPipe(){
  var host=el('pipe-svg');
  function pick(t){var g=t.closest('.node');if(!g)return;selStage=g.getAttribute('data-stage');host.querySelectorAll('.node').forEach(function(n){n.classList.toggle('sel',n===g);});stageDetail();}
  host.addEventListener('click',function(e){pick(e.target);});
  host.addEventListener('mouseover',function(e){pick(e.target);});
  host.addEventListener('focusin',function(e){pick(e.target);});
  host.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pick(e.target);}});
}
el('pipe-svg').innerHTML=pipeSvg();bindPipe();stageDetail();

/* ---- entity diagram */
function entSvg(){
  var E=D.entities;
  var BW=170,BH=54;
  var B={
    manufacturer:[30,60],model:[230,60],generation:[430,60],variant:[630,60],powertrain:[830,60],warranty:[130,142],
    evidence_amendment:[30,292],source:[230,292],source_observation:[430,292],field_provenance:[630,292],evidence_quarantine:[830,292],
    safety_test:[25,482],safety_test_applicability:[185,482],safety_rating:[415,482],
    professional_assessment:[625,482],owner_rating:[830,482],owner_theme:[975,482]};
  var bw={safety_test:140,safety_test_applicability:210,safety_rating:150,professional_assessment:190,owner_rating:130,owner_theme:115,warranty:170};
  function W(k){return bw[k]||BW;}
  function R(k){return [B[k][0]+W(k),B[k][1]+BH/2];} function L(k){return [B[k][0],B[k][1]+BH/2];}
  function T(k,dx){return [B[k][0]+W(k)/2+(dx||0),B[k][1]];} function Bt(k,dx){return [B[k][0]+W(k)/2+(dx||0),B[k][1]+BH];}
  function line(a,b,dash){return '<path class="'+(dash?'tagline':'edge')+'" '+(dash?'':'marker-end="url(#ar2)" ')+'d="M'+a[0]+' '+a[1]+'L'+b[0]+' '+b[1]+'"/>';}
  var p='<svg viewBox="0 0 1110 610" role="img" aria-labelledby="et ed"><title id="et">Main tables of the knowledge base</title><desc id="ed">Catalogue tables: manufacturer, model, generation, variant, powertrain, warranty. Evidence tables: source, source observation, field provenance, evidence quarantine, evidence amendment. Safety tables: safety test, safety test applicability, safety rating. Review tables: professional assessment, owner rating, owner theme.</desc>';
  p+='<defs><marker id="ar2" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--ink2)"/></marker></defs>';
  function band(x,y,w,h,t){return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="8" fill="none" stroke="var(--line)" stroke-width="1.5"/><text class="tm" x="'+(x+14)+'" y="'+(y+24)+'" font-size="12" font-weight="700" letter-spacing="1.2">'+t.toUpperCase()+'</text>';}
  p+=band(10,10,1090,206,'Catalogue')+band(10,236,1090,162,'Evidence and provenance')+band(10,418,585,176,'Safety')+band(610,418,490,176,'Reviews');
  var edges=[line(R('manufacturer'),L('model')),line(R('model'),L('generation')),line(R('generation'),L('variant')),line(L('powertrain'),R('variant')),
    line(Bt('manufacturer'),T('warranty',-30)),line(Bt('model'),T('warranty',30)),
    line(R('source'),L('source_observation')),line(R('source_observation'),L('field_provenance')),line(Bt('variant'),T('field_provenance')),
    line(L('evidence_quarantine'),R('field_provenance'),true),line(R('safety_test'),L('safety_test_applicability'))];
  p+=edges.join('');
  var labels={evidence_quarantine:'hides cells and evidence',evidence_amendment:'log of in-place fixes',source:'one row per site or agency',powertrain:'engine descriptions',source_observation:'one page read, as found',field_provenance:'which observation backs which cell'};
  Object.keys(B).forEach(function(k){
    var x=B[k][0],y=B[k][1],w=W(k),hot=(k==='variant'||k==='field_provenance');
    p+='<g><rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+BH+'" rx="5" fill="'+(hot?'var(--accent-soft)':'var(--surface)')+'" stroke="'+(hot?'var(--accent)':'var(--line)')+'" stroke-width="1.5"/>';
    p+='<text x="'+(x+10)+'" y="'+(y+21)+'" font-size="12" font-weight="700" class="mono">'+k+'</text>';
    p+='<text x="'+(x+10)+'" y="'+(y+41)+'" font-size="13" class="t2"><tspan font-weight="700" fill="var(--ink)" style="fill:var(--ink)">'+fmt(E[k])+'</tspan> rows</text></g>';
    if(labels[k]&&B[k][1]!==482)p+='<text class="tm" x="'+x+'" y="'+(y+BH+16)+'" font-size="11.5">'+esc(labels[k])+'</text>';
  });
  p+='<text class="tm" x="25" y="574" font-size="12">Applicability points at a model or family, never at a single variant.</text>';
  p+='<text class="tm" x="625" y="574" font-size="12">Scores and themes attach to a model and to the source they came from.</text>';
  return p+'</svg>';
}
el('ent-svg').innerHTML=entSvg();

/* ---- heatmap */
function heat(){
  var H=D.heat,h='<table class="heat"><caption class="sr">Percent of values present, by manufacturer and field group</caption><thead><tr><th scope="col"><span class="sr">Manufacturer</span></th>';
  H.groups.forEach(function(g){h+='<th scope="col">'+g+'</th>';});h+='</tr></thead><tbody>';
  H.makes.forEach(function(m,i){
    h+='<tr'+(m==='All makes'?' class="all"':'')+'><th scope="row">'+esc(m)+'<small>'+fmt(H.n_variants[i])+' variants</small></th>';
    H.pct[i].forEach(function(v,j){
      if(v==null){h+='<td>–</td>';return;}
      var t=Math.max(0,Math.min(1,v)),dark=t>=.62;
      h+='<td data-tip="'+esc(m+', '+H.groups[j]+': '+(v*100).toFixed(1)+'% of values present')+'" style="background:color-mix(in srgb,var(--heat-hi) '+(t*100).toFixed(1)+'%,var(--heat-lo));color:var(--heat-on-'+(dark?'hi':'lo')+')">'+Math.round(v*100)+'%</td>';});
    h+='</tr>';});
  el('heat').innerHTML=h+'</tbody></table>';
  var fg=D.heat.fields_per_group,lines=D.heat.groups.map(function(g){return g+': '+fg[g].join(', ');});
  el('heat-note').textContent='Percent of value slots filled, across all variants of the manufacturer. Efficiency counts a variant as covered when it has any of km/l, km/kg or electric range, since each car has only one of them. Fuel tank is not counted for electric cars. Fields per group: '+lines.join('; ')+'.';
}
heat();
function bars(id,key){
  var rows=D.per_make.slice().sort(function(a,b){return b[key]-a[key]||(a.make<b.make?-1:1);}),mx=Math.max.apply(null,rows.map(function(r){return r[key];}))||1;
  el(id).innerHTML=rows.map(function(r){return '<div class="brow" data-tip="'+esc(r.make+': '+fmt(r[key])+' '+key)+'"><span class="bl">'+esc(r.make)+'</span><span class="track"><span class="fill" style="width:'+(r[key]/mx*100).toFixed(1)+'%"></span></span><span class="bv">'+fmt(r[key])+'</span></div>';}).join('');
}
bars('bars-models','models');bars('bars-variants','variants');

/* ---- growth */
var MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function dshort(s){var p=s.split('-');return parseInt(p[2],10)+' '+MONTHS[parseInt(p[1],10)-1];}
function growth(){
  var pts=D.growth;
  el('growth-intro').textContent=pts.length?('The KB at each recorded state, in order. '+(D.meta.growth_source==='history'?'States are read from the local history repository, which stores a dump of every table before and after each write.':'States are taken from the run folders, because the history repository could not be read.')):'No growth data could be read.';
  var panels=[{k:'models',t:'Models'},{k:'variants',t:'Variants'}];
  if(pts.some(function(p){return p.review_rows;}))panels.push({k:'review_rows',t:'Review rows (expert and owner)'});
  var host=el('growth-charts');host.innerHTML='';
  panels.forEach(function(pn){var d=document.createElement('div');d.innerHTML='<h3>'+pn.t+'</h3><div class="gchart"></div>';host.appendChild(d);d._k=pn.k;});
  drawGrowth();
  var h='<thead><tr><th>State</th><th>Date</th><th>KB hash</th><th>Models</th><th>Variants</th><th>Review rows</th></tr></thead><tbody>';
  pts.forEach(function(p){h+='<tr><td>'+esc(p.label)+'</td><td>'+esc(p.date)+'</td><td class="mono">'+esc(p.sha8)+'</td><td>'+fmt(p.models)+'</td><td>'+fmt(p.variants)+'</td><td>'+(p.review_rows==null?'–':fmt(p.review_rows))+'</td></tr>';});
  el('growth-table').innerHTML=h+'</tbody>';
  var rh='<thead><tr><th>Run</th><th>Started (UTC)</th><th>Kind</th><th>Wrote to KB</th><th>Rows written</th><th>Gates</th></tr></thead><tbody>';
  D.runs.forEach(function(r){rh+='<tr><td>'+esc(r.name)+'</td><td>'+esc(r.started)+'</td><td>'+esc(r.kind)+'</td><td>'+(r.wrote?'yes':'no'+(r.stopped?' (dry run)':''))+'</td><td>'+(r.rows_written==null?'–':fmt(r.rows_written))+'</td><td>'+(r.gates_ok==null?'–':(r.gates_ok?'all passed':'failed'))+'</td></tr>';});
  el('runs-table').innerHTML=rh+'</tbody>';
}
function drawGrowth(){
  var pts=D.growth;
  document.querySelectorAll('#growth-charts > div').forEach(function(d){
    var k=d._k,host=d.querySelector('.gchart'),W=Math.max(280,host.clientWidth||d.clientWidth||320),H=190,L=44,Rm=18,Tp=26,Bm=34;
    var vals=pts.map(function(p){return p[k]==null?0:p[k];}),mx=Math.max.apply(null,vals)||1;
    var pw=Math.pow(10,Math.floor(Math.log10(mx*1.1))),m=mx*1.1/pw,steps=[1,1.2,1.5,2,2.5,3,4,5,6,8,10],top=pw*steps.filter(function(x){return x>=m-1e-9;})[0];
    var xs=function(i){return pts.length>1?L+(W-L-Rm)*i/(pts.length-1):L+(W-L-Rm)/2;},ys=function(v){return Tp+(H-Tp-Bm)*(1-v/top);};
    var s='<svg width="'+W+'" height="'+H+'" role="img" aria-label="'+esc(k.replace('_',' '))+' at each recorded KB state: '+esc(vals.map(fmt).join(', '))+'">';
    [0,.5,1].forEach(function(f){var y=ys(top*f);s+='<line x1="'+L+'" x2="'+(W-Rm)+'" y1="'+y+'" y2="'+y+'" stroke="var(--line2)"/><text class="tm" x="'+(L-6)+'" y="'+(y+4)+'" text-anchor="end" font-size="11">'+fmt(Math.round(top*f))+'</text>';});
    var path=pts.map(function(p,i){return (i?'L':'M')+xs(i)+' '+ys(vals[i]);}).join('');
    if(pts.length>1)s+='<path d="'+path+'" fill="none" stroke="var(--accent)" stroke-width="2.5"/>';
    pts.forEach(function(p,i){var x=xs(i),y=ys(vals[i]);
      s+='<circle cx="'+x+'" cy="'+y+'" r="5" fill="var(--accent)" stroke="var(--surface)" stroke-width="2" data-tip="'+esc(p.label+' ('+p.date+'): '+fmt(vals[i]))+'"/>';
      s+='<text x="'+x+'" y="'+(y-10)+'" text-anchor="'+(i===0?'start':i===pts.length-1?'end':'middle')+'" font-size="12" font-weight="700">'+fmt(vals[i])+'</text>';
      s+='<text class="tm" x="'+x+'" y="'+(H-12)+'" text-anchor="'+(i===0?'start':i===pts.length-1?'end':'middle')+'" font-size="11">'+(i+1)+'</text>';});
    s+='<text class="tm" x="'+L+'" y="'+(H-0)+'" font-size="10.5" dy="-1">State number, in order (see table)</text>';
    host.innerHTML=s+'</svg>';
  });
}
growth();

/* ---- trust */
var VERD=[['match','Match: the source states this value'],['mismatch','Mismatch: the source states a different value'],['unreachable','Unreachable: page gone, or it no longer states the field. Not counted as a match'],['verifier_error','Verifier error: no usable reply']];
function stack(c){
  var n=c.n||1;return '<div class="stack" role="img" aria-label="'+VERD.map(function(v){return c[v[0]]+' '+v[0].replace('_',' ');}).join(', ')+'">'+VERD.map(function(v){var k=c[v[0]];if(!k)return '';var w=k/n*100;
    return '<div class="seg '+v[0]+'" style="flex:'+k+' 1 0" data-tip="'+esc(v[1]+': '+k+' of '+c.n)+'">'+(w>=7?(v[0]==='unreachable'?'<b>'+k+'</b>':k):'')+'</div>';}).join('')+'</div>';
}
function accBlock(c){return '<div class="acc"><b>'+pct(c.accuracy,1)+'</b><span>'+c.match+' of '+(c.match+c.mismatch)+' decided'+(c.ci?'; 95% range '+pct(c.ci[0],0)+' to '+pct(c.ci[1],0):'')+'</span></div>';}
function trust(){
  var T=D.trust,host=el('trust-body');
  if(!T){el('trust-intro').textContent='No verification results were found in the run folders.';host.innerHTML='';return;}
  var o=T.overall;
  el('trust-intro').textContent='Results from run '+T.run+' (started '+T.started+'): a random sample of '+fmt(T.n)+' stored values, each sent back to its source and re-read by a model that did not extract it. Accuracy is match divided by match plus mismatch. Unreachable and verifier errors are shown, and are never counted as matches.';
  var h='<div class="legend" aria-label="Legend">'+VERD.map(function(v){return '<span><i class="sw '+v[0]+'"></i>'+esc(v[1])+'</span>';}).join('')+'</div>';
  h+='<h3 style="margin:6px 0 2px">By source class</h3>';
  T.class_order.filter(function(k){return T.by_class[k];}).forEach(function(k){var c=T.by_class[k];
    h+='<div class="trow"><div class="tl"><b>'+esc(T.class_label[k])+'</b><span>'+esc(T.class_explain[k])+' Sample: '+fmt(c.n)+'.</span></div>'+stack(c)+accBlock(c)+'</div>';});
  h+='<h3 style="margin:30px 0 2px">By field group</h3>';
  T.groups.filter(function(k){return T.by_group[k];}).forEach(function(k){var c=T.by_group[k];
    h+='<div class="trow"><div class="tl"><b style="text-transform:capitalize">'+esc(k)+'</b><span>Sample: '+fmt(c.n)+'</span></div>'+stack(c)+accBlock(c)+'</div>';});
  var L=T.legacy,sh=L.mismatch_total?L.mismatch_price/L.mismatch_total:0;
  h+='<div class="callout" style="margin-top:30px"><p><b>Reading the legacy figure.</b> Legacy values scored '+pct(L.all.accuracy,1)+' ('+L.all.match+' of '+(L.all.match+L.all.mismatch)+'). ';
  if(sh>0.5)h+='Most of its mismatches are prices: '+L.mismatch_price+' of '+L.mismatch_total+' ('+pct(sh,0)+'). Legacy prices were checked against today’s page, so a price mismatch can mean the car’s price changed after June, not that the import was wrong. Prices checked: '+(L.price.match+L.price.mismatch)+', matching: '+L.price.match+' ('+pct(L.price.accuracy,0)+'). Without prices, legacy accuracy is '+pct(L.non_price.accuracy,1)+' ('+L.non_price.match+' of '+(L.non_price.match+L.non_price.mismatch)+').';
  else h+='Price mismatches make up '+L.mismatch_price+' of its '+L.mismatch_total+' mismatches, so prices are not the main driver here.';
  h+='</p></div>';
  h+='<div class="callout" style="margin-top:14px"><p><b>Unreachable is not a match.</b> '+fmt(o.unreachable)+' of the '+fmt(o.n)+' sampled cells could not be checked (the page could not be read, or it no longer states that field), plus '+o.verifier_error+' verifier error'+(o.verifier_error===1?'':'s')+'. They are left out of every accuracy figure. Overall: '+pct(o.accuracy,1)+' ('+o.match+' of '+(o.match+o.mismatch)+' decided).'+(T.legacy_cells?' The KB held '+fmt(T.legacy_cells)+' legacy cells, of which '+fmt(T.legacy_checkable)+' belong to a variant linked to a current page and could be sampled.':'')+'</p></div>';
  if(T.planted&&T.planted.n)h+='<div class="callout" style="margin-top:14px"><p><b>Does the verifier catch errors?</b> '+T.planted.n+' deliberately wrong values were slipped into the sample. The verifier flagged '+T.planted.flagged+' of '+T.planted.n+' as mismatches.</p></div>';
  var vr=D.verify_runs;
  if(vr.length){h+='<h3 style="margin:32px 0 8px">Every verification on record</h3><div class="scroll"><table class="mini"><thead><tr><th>Run</th><th>Sampled</th><th>Match</th><th>Mismatch</th><th>Unreachable</th><th>Verifier errors</th><th>Accuracy</th></tr></thead><tbody>'+vr.map(function(r){return '<tr><td>'+esc(r.name)+'</td><td>'+fmt(r.n)+'</td><td>'+fmt(r.match)+'</td><td>'+fmt(r.mismatch)+'</td><td>'+fmt(r.unreachable)+'</td><td>'+fmt(r.verifier_error)+'</td><td>'+pct(r.accuracy,1)+'</td></tr>';}).join('')+'</tbody></table></div><p class="cap">Earlier runs verified only newly written values, and some verifier calls failed when free model quotas ran out. Those failures are listed, not counted.</p>';}
  host.innerHTML=h;
}
trust();

/* ---- reviews */
function covbar(){
  var C=D.reviews.coverage,t=C.total||1;
  var seg=[['cv-both','Both',C.both],['cv-e','Expert only',C.expert_only],['cv-o','Owner only',C.owner_only],['cv-n','Neither',C.neither]];
  el('cov-bar').innerHTML='<div class="covbar" role="img" aria-label="'+seg.map(function(s){return s[1]+' '+s[2];}).join(', ')+' of '+C.total+' models">'+seg.filter(function(s){return s[2]>0;}).map(function(s){return '<div class="'+s[0]+'" style="flex:'+s[2]+' 1 0" data-tip="'+esc(s[1]+': '+s[2]+' of '+t+' models')+'">'+(s[2]/t>0.08?esc(s[1])+' '+s[2]:s[2])+'</div>';}).join('')+'</div><p class="cap ink">Of '+fmt(C.total)+' models: '+fmt(C.both)+' have both an expert score and an owner rating, '+fmt(C.expert_only)+' only an expert score, '+fmt(C.owner_only)+' only an owner rating, and '+fmt(C.neither)+' neither. Expert pages that redirected or did not exist are simply missing.</p>';
}
covbar();
function quant(a,q){var s=a.slice().sort(function(x,y){return x-y;}),p=(s.length-1)*q,i=Math.floor(p),f=p-i;return s[i]+(s[i+1]!==undefined?(s[i+1]-s[i])*f:0);}
function hash(s){var h=0;for(var i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))|0;return Math.abs(h);}
function strip(id,block,unit,noteId){
  var host=el(id),W=Math.max(280,host.clientWidth||320),L=12,Rm=16,RH=56,AX=26;
  var rows=block.rows,min=block.axis_min,max=block.scale_max;
  if(!rows.length){host.innerHTML='<p class="nodata">No scores in the KB yet.</p>';return;}
  var H=rows.length*RH+AX+4,xs=function(v){return L+(W-L-Rm)*(v-min)/(max-min);};
  var s='<svg width="'+W+'" height="'+H+'" role="img" aria-label="Dot plot of '+esc(unit)+' by aspect, one row per aspect, one dot per model">';
  for(var t=min;t<=max;t++){var x=xs(t);s+='<line x1="'+x+'" x2="'+x+'" y1="0" y2="'+(H-AX)+'" stroke="var(--line2)"/><text class="tm" x="'+x+'" y="'+(H-10)+'" text-anchor="middle" font-size="11">'+t+'</text>';}
  rows.forEach(function(r,i){
    var y0=i*RH,vals=r.points.map(function(p){return p[1];}),cy=y0+RH-18,med=quant(vals,.5),q1=quant(vals,.25),q3=quant(vals,.75);
    var mean=vals.reduce(function(a,b){return a+b;},0)/vals.length;
    s+='<text x="'+L+'" y="'+(y0+14)+'" font-size="12.5" font-weight="'+(r.aspect==='overall'?'700':'500')+'">'+esc(r.aspect==='overall'?'Overall':r.aspect)+'</text>';
    s+='<text class="tm" x="'+(W-Rm)+'" y="'+(y0+14)+'" text-anchor="end" font-size="11.5">median '+med.toFixed(1)+', n='+vals.length+'</text>';
    s+='<line x1="'+xs(Math.min.apply(null,vals))+'" x2="'+xs(Math.max.apply(null,vals))+'" y1="'+cy+'" y2="'+cy+'" stroke="var(--line)" stroke-width="1"/>';
    s+='<rect x="'+xs(q1)+'" y="'+(cy-11)+'" width="'+Math.max(2,xs(q3)-xs(q1))+'" height="22" rx="3" fill="var(--accent-soft)"/>';
    r.points.forEach(function(p){var jy=((hash(p[0])%100)/100-.5)*14;
      s+='<circle cx="'+xs(p[1])+'" cy="'+(cy+jy)+'" r="3.1" fill="var(--accent)" fill-opacity=".6" data-tip="'+esc(p[0]+': '+p[1])+'"/>';});
    s+='<line x1="'+xs(med)+'" x2="'+xs(med)+'" y1="'+(cy-12)+'" y2="'+(cy+12)+'" stroke="var(--ink)" stroke-width="2.2"/>';
  });
  host.innerHTML=s+'</svg>';
  el(noteId).textContent='One dot per model, '+unit+'. Shaded box: middle half of the models. Black line: median. Axis runs from '+min+' to '+max+', so it does not start at zero.';
}
function drawStrips(){strip('strip-expert',D.reviews.expert,'score out of 10','expert-note');strip('strip-owner',D.reviews.owner,'rating out of 5','owner-note');}
drawStrips();
(function(){
  var cols=[['make','Make',0],['model','Model',0],['expert','Expert overall (of 10)',1],['owner','Owner overall (of 5)',1],['count','Owner ratings',1],['variants','Variants',1]];
  var rows=D.reviews.table.slice(),key='expert',dir=-1;
  function cmp(a,b){var x=a[key],y=b[key];if(x==null&&y==null)return a.model<b.model?-1:1;if(x==null)return 1;if(y==null)return -1;var r=typeof x==='string'?x.localeCompare(y):x-y;return r*dir||(a.model<b.model?-1:1);}
  function draw(){
    rows.sort(cmp);
    var h='<thead><tr>'+cols.map(function(c){return '<th scope="col" aria-sort="'+(c[0]===key?(dir>0?'ascending':'descending'):'none')+'"><button type="button" data-k="'+c[0]+'">'+c[1]+'</button></th>';}).join('')+'</tr></thead><tbody>';
    rows.forEach(function(r){h+='<tr><td>'+esc(r.make)+'</td><td>'+esc(r.model)+'</td><td>'+(r.expert==null?'<span class="nodata">–</span>':r.expert.toFixed(1))+'</td><td>'+(r.owner==null?'<span class="nodata">–</span>':r.owner.toFixed(2))+'</td><td>'+(r.count==null?'<span class="nodata">–</span>':fmt(r.count))+'</td><td>'+fmt(r.variants)+'</td></tr>';});
    var t=el('model-table');t.innerHTML=h+'</tbody>';
    t.querySelectorAll('button').forEach(function(b){b.addEventListener('click',function(){var k=b.getAttribute('data-k');if(k===key)dir=-dir;else{key=k;dir=(k==='make'||k==='model')?1:-1;}draw();var nb=el('model-table').querySelector('button[data-k="'+k+'"]');if(nb)nb.focus();});});
  }
  draw();
})();
(function(){
  var R=D.reviews,h=el('themes');
  if(!R.themes.length){h.innerHTML='<p class="callout">The owner-theme layer is in progress. The table exists in the KB and holds '+fmt(R.theme_rows)+' rows today. Themes will be extracted from owner reviews and from forum pages the owner saves by hand, and each one will be checked against its source text before it is written.</p>';return;}
  var mx=Math.max.apply(null,R.themes.map(function(t){return t.mentions;}))||1;
  h.className='bars';h.innerHTML=R.themes.map(function(t){return '<div class="brow" data-tip="'+esc(t.theme+' ('+t.direction+'): '+t.mentions+' mentions in '+t.models+' models')+'"><span class="bl">'+esc(t.theme)+'</span><span class="track"><span class="fill" style="width:'+(t.mentions/mx*100).toFixed(1)+'%"></span></span><span class="bv">'+fmt(t.mentions)+'</span></div>';}).join('');
})();

/* ---- re-render on resize and theme */
var rt;function rerender(){drawGrowth();drawStrips();}
addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(rerender,120);});
})();
</script>
</body>
</html>
'''

if __name__ == "__main__":
    sys.exit(main())
