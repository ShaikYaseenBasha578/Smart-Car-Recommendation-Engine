"""Presentation site: four self-contained HTML pages about the CarRec project.

    python -m kbpipe.dashboard --out knowledge_base/reports/kb_dashboard/index.html
    python -m kbpipe.dashboard --out-dir DIR [--recsys-dir DIR] [--app-base /]

Writes index.html (landing), pipeline.html (how the knowledge base is kept up to date), kb.html (what the knowledge base
holds and how far it can be trusted) and engine.html (the recommendation engine) into one folder.

Inputs, all read only: a COPY of the KB (made with kb.copy_for_read, which checks holders and hashes before and after),
the run folders under knowledge_base/runs/, the local history repository when readable, and the recommender checkout
(docs, config, evaluation results, review data, screenshots) when present. Every number on every page is computed here
from those inputs and the source of each is named beside it. Each page embeds its own CSS and JS and loads nothing from
the network. Output is deterministic apart from the "generated on" date.
"""
import argparse
import ast
import base64
import csv
import datetime
import glob
import html as htmllib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kbpipe import config, fields as F, kb  # noqa: E402

DEFAULT_COPY = "/tmp/carrec_audit/prod/dashboard_copy.db"
DEFAULT_RECSYS = "~/carrec_worktrees/recsys-v3"
PAGES = [("index.html", "Overview"), ("pipeline.html", "Pipeline"), ("kb.html", "Knowledge base"), ("engine.html", "Engine")]
CLASS_ORDER = ["aggregator", "brochure", "legacy"]
CLASS_LABEL = {"aggregator": "Two agreeing sites", "brochure": "OEM brochure", "legacy": "Legacy import"}
CLASS_EXPLAIN = {
    "aggregator": "Values that CarWale and CarDekho both state for the same variant, written by the pipeline.",
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
           "mo.name as _model", 'v."name" as _vname', "p.fuel_type as _fuel"]
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


# ---------------------------------------------------------------- how well each value is backed, price age, review backlog
SITES = {"carwale", "cardekho", "91wheels", "v3cars"}
EV_ORDER = ["brochure", "two_sites", "one_site", "import", "none"]
EV_LABEL = {"brochure": "Maker's brochure, page cited", "two_sites": "Agreed by two or more listing sites", "one_site": "One listing site only",
            "import": "June 2026 import only", "none": "No evidence row"}
EV_PLAIN = {"brochure": "A brochure PDF from the manufacturer states the value. The stored row names the file and page.",
            "two_sites": "Two or more listing sites (CarWale, CarDekho, 91wheels, v3cars) recorded the same value for this variant.",
            "one_site": "One listing site recorded it and nothing stronger exists. The value may be right; nothing else backs it.",
            "import": "Carried over from the original June 2026 import. That import recorded no web address, so there is no page to open.",
            "none": "The value is stored but no live evidence row points to it."}
EV_CLS = {"brochure": "ev-b", "two_sites": "ev-2", "one_site": "ev-1", "import": "ev-i", "none": "ev-n"}


def cell_evidence(c):
    """(variant_id, field) -> [set of source names, brochure page cited]. Live evidence only (quarantine honoured)."""
    if has(c, "v_live_evidence"):
        q = ("select e.variant_id, e.field_name, s.name, case when s.name='oem' and (o.source_url like '%#page=%' or o.raw_payload like '%\"page\":%') "
             "then 1 else 0 end from v_live_evidence e join source_observation o on o.id=e.observation_id join source s on s.id=e.source_id "
             "where e.decision in ('accepted','confirmed')")
    else:
        q = ("select e.variant_id, e.field_name, s.name, case when s.name='oem' and (o.source_url like '%#page=%' or o.raw_payload like '%\"page\":%') "
             "then 1 else 0 end from field_provenance e join source_observation o on o.id=e.source_observation_id join source s on s.id=o.source_id "
             "where e.decision in ('accepted','confirmed')")
    ev = {}
    for v, f, name, pg in rows(c, q):
        d = ev.setdefault((v, f), [set(), False])
        d[0].add(name)
        d[1] = d[1] or bool(pg)
    return ev


def classify_cell(entry):
    """Strongest evidence behind one stored value."""
    if not entry:
        return "none"
    s = entry[0]
    if "oem" in s:
        return "brochure"
    n = len(s & SITES)
    if n >= 2:
        return "two_sites"
    if n == 1:
        return "one_site"
    return "import" if "v6_migration" in s else "none"


def audit_definition(c):
    """The independent audit's counting rule: every non-blank cell of the raw variant table plus power, torque and engine size,
    evidence looked up on the variant's own id only (no edition inheritance, no quarantine mask on the values)."""
    try:
        vcols = [r[1] for r in c.execute("pragma table_info(variant)")]
        skip = {"id", "model_id", "generation_id", "powertrain_id", "name", "full_name", "is_discontinued", "v6_row_index", "created_at",
                "updated_at", "base_variant_id", "edition_classification", "adas_tier"}
        fields = [f for f in vcols if f not in skip]
        ptc = {r[1] for r in c.execute("pragma table_info(powertrain)")}
        pt = [f for f in ("engine_cc", "power_bhp", "torque_nm") if f in ptc]
        cev = cell_evidence(c)
        counts = {k: 0 for k in EV_ORDER}
        sql = "select v.*" + "".join(', p."%s" as "pt_%s"' % (f, f) for f in pt) + " from variant v join powertrain p on p.id=v.powertrain_id"
        for r in c.execute(sql):
            for f in fields + pt:
                val = r["pt_" + f] if f in pt else r[f]
                if val is None or val == "":
                    continue
                counts[classify_cell(cev.get((r["id"], f)))] += 1
        return {"total": sum(counts.values()), "classes": counts, "n_fields": len(fields) + len(pt)}
    except sqlite3.Error:
        return None


def parse_day(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def price_freshness(c, vrows, ref):
    """Per variant, the date of the latest price evidence from a listing site or brochure, against the page date."""
    ref_d = parse_day(ref)
    if has(c, "v_live_evidence"):
        q = ("select e.variant_id, substr(o.observed_at,1,10), s.name from v_live_evidence e join source_observation o on o.id=e.observation_id "
             "join source s on s.id=e.source_id where e.field_name='price_ex_showroom' and e.decision in ('accepted','confirmed')")
    else:
        q = ("select e.variant_id, substr(o.observed_at,1,10), s.name from field_provenance e join source_observation o on o.id=e.source_observation_id "
             "join source s on s.id=o.source_id where e.field_name='price_ex_showroom' and e.decision in ('accepted','confirmed')")
    per = {}
    for v, d, n in rows(c, q):
        per.setdefault(v, []).append((d, n))
    out = {"n": 0, "within30": 0, "within90": 0, "within180": 0, "older": 0, "import_only": 0, "no_evidence": 0, "price_missing": 0,
           "latest": None, "import_date": None, "import_age": None}
    for r in vrows:
        if r.get("price_ex_showroom") is None:
            out["price_missing"] += 1
            continue
        out["n"] += 1
        lst = per.get(r["id"]) or (per.get(r["base_variant_id"]) if r["base_variant_id"] else None) or []
        site = [d for d, n in lst if n != "v6_migration" and parse_day(d)]
        if site:
            d = max(site)
            out["latest"] = max(out["latest"] or d, d)
            age = max((ref_d - parse_day(d)).days, 0) if ref_d else None
            if age is None or age > 180:
                out["older"] += 1
            else:
                out["within180"] += 1
                if age <= 90:
                    out["within90"] += 1
                if age <= 30:
                    out["within30"] += 1
        elif lst:
            out["import_only"] += 1
            idates = [d for d, n in lst if parse_day(d)]
            if idates:
                out["import_date"] = max(out["import_date"] or max(idates), max(idates))
        else:
            out["no_evidence"] += 1
    if out["import_date"] and ref_d:
        out["import_age"] = max((ref_d - parse_day(out["import_date"])).days, 0)
    return out


def spec_run(runs):
    """Latest run of the listing-site pipeline that wrote to the knowledge base (brochure and review runs are separate)."""
    c = [r for r in runs if r["json"].get("write") and r["json"].get("full") and r["json"].get("discovery")
         and not r["name"].startswith(("brochure", "reviews", "audit"))]
    return c[-1] if c else None


def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def norm_val(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("true", "yes"):
            return 1.0
        if t in ("false", "no"):
            return 0.0
        try:
            return float(t)
        except ValueError:
            return t
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def backlog(c, runs, vrows):
    """What the latest listing-site run found and did not apply. 'Still pending' means the knowledge base does not hold the proposed value."""
    run = spec_run(runs)
    if not run:
        return None
    pend = read_json(os.path.join(run["dir"], "pending.json"))
    disc = read_json(os.path.join(run["dir"], "discovery.json")) or []
    if not pend or not isinstance(pend.get("items"), list):
        return None
    byname = {(r["make"], r["_model"], r["_vname"]): r for r in vrows}
    items = pend["items"]
    kinds = {}
    for i in items:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    cells = price_cells = fills = changes = unmatched = 0
    still = price_still = 0
    price_vars = set()
    unlisted = new_var = new_var_open = 0
    for i in items:
        for o in i.get("ops") or []:
            if o.get("op") == "cell":
                cells += 1
                isp = o.get("field") == "price_ex_showroom"
                price_cells += 1 if isp else 0
                if o.get("expect_old") is None:
                    fills += 1
                else:
                    changes += 1
                row = byname.get((o["make"], o["model"], o["variant"]))
                if row is None:
                    unmatched += 1
                    continue
                if norm_val(row.get(o["field"])) != norm_val(o["value"]):
                    still += 1
                    if isp:
                        price_still += 1
                        price_vars.add((o["make"], o["model"], o["variant"]))
            elif o.get("op") == "discontinue":
                unlisted += 1
            elif o.get("op") == "add_variant":
                new_var += 1
                if (o["make"], o["model"], o["name"]) not in byname:
                    new_var_open += 1
    model_names = {(r["make"], norm_name(r["_model"])) for r in vrows}
    missing = [d for d in disc if d.get("kind") == "NEW_MODEL" and (d["make"], norm_name(d["model"])) not in model_names]
    one_site = [d for d in disc if d.get("kind") == "ONE_SITE_ONLY" and (d["make"], norm_name(d["model"])) not in model_names]
    names = lambda ds: sorted("%s %s" % (d["make"], d["model"]) for d in ds)
    rj = run["json"]
    return {"run": run["name"], "date": run["started"][:10], "items": len(items), "kinds": kinds, "cells": cells, "price_cells": price_cells,
            "cell_fills": fills, "cell_changes": changes, "cells_still_pending": still, "price_still_pending": price_still,
            "price_variants_pending": len(price_vars), "cells_unmatched": unmatched, "unlisted_ops": unlisted,
            "unlisted_record": (rj.get("stats") or {}).get("kb_variants_not_listed"), "cells_record": (rj.get("stats") or {}).get("cells_for_review"),
            "new_variants": new_var, "new_variants_open": new_var_open, "missing_models": names(missing), "one_site_models": names(one_site),
            "facelift": sorted("%s %s" % (i["make"], i["model"]) for i in items if i["kind"] == "FACELIFT"),
            "discontinued_candidates": sorted("%s %s" % (i["make"], i["model"]) for i in items if i["kind"] == "DISCONTINUED_CANDIDATE"),
            "out_of_scope": names([d for d in disc if d.get("kind") == "OUT_OF_SCOPE"]),
            "price_cap": config.DEFAULTS.get("scope_max_base_price"),
            "marked_discontinued": one(c, "select count(*) from variant where is_discontinued=1")}


def duplicate_groups(c):
    q = ("select count(*), coalesce(sum(n),0) from (select count(*) n from variant where price_ex_showroom is not null and base_variant_id is null "
         "group by model_id, price_ex_showroom, powertrain_id, transmission having count(*)>1)")
    r = rows(c, q)
    return {"groups": r[0][0], "variants": r[0][1]} if r else None


def crash_gap(c):
    """Crash tests stored for a model that has no link to any variant of it, so the app shows the model as unrated."""
    if not (has(c, "safety_test") and has(c, "v_safety_applicability_q")):
        return None
    models = rows(c, "select mo.id, ma.name, mo.name, (select count(*) from variant v where v.model_id=mo.id), "
                     "(select count(*) from v_safety_applicability_q a where a.model_id=mo.id) from model mo join manufacturer ma on ma.id=mo.manufacturer_id")
    tests = rows(c, "select tested_vehicle_name, aop_stars, resolution_status from safety_test")
    total_var = sum(m[3] for m in models) or 1
    unrated_var = sum(m[3] for m in models if m[4] == 0)
    gap = []
    for mid, make, name, nv, linked in models:
        if linked:
            continue
        strip = set(norm_name(make).split()) | {"suzuki", "maruti"}
        hit = None
        for tname, stars, status in tests:
            for part in str(tname).split("/"):
                toks = [t for t in norm_name(part).split() if t not in strip]
                if toks and " ".join(toks) == norm_name(name):
                    hit = stars
            if hit is not None:
                break
        if hit is not None:
            gap.append({"model": "%s %s" % (make, name), "variants": nv, "stars": hit})
    return {"models": gap, "variants": sum(g["variants"] for g in gap), "unrated_variants": unrated_var, "total_variants": total_var,
            "tests": len(tests), "unlinked_tests": sum(1 for t in tests if t[2] != "RESOLVED")}


def third_party(c):
    out = {}
    r = rows(c, "select count(*), count(distinct model_id), sum(quote is not null and quote<>''), max(length(quote)), avg(length(quote)), "
                "sum(note is not null and note<>''), min(published_on), max(published_on) from professional_assessment where status='current'")
    if r:
        n, m, q, mx, av, notes, d0, d1 = r[0]
        out["expert"] = {"rows": n or 0, "models": m or 0, "quotes": q or 0, "quote_max": mx, "quote_mean": av, "notes": notes or 0, "from": d0, "to": d1}
    r = rows(c, "select count(*), count(distinct model_id) from owner_rating where status='current'")
    if r:
        out["owner"] = {"rows": r[0][0] or 0, "models": r[0][1] or 0}
    r = rows(c, "select count(*), count(distinct model_id), coalesce(sum(mentions<=3),0), coalesce(sum(mentions<5),0) from owner_theme")
    if r:
        out["themes"] = {"rows": r[0][0] or 0, "models": r[0][1] or 0, "le3": r[0][2] or 0, "lt5": r[0][3] or 0}
    return out


def audit_spot_check(path):
    """The independent reviewer's tally of 40 values judged from memory (read from the audit file when present)."""
    try:
        txt = open(path, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"Tally:\s*(\d+) look right,\s*(\d+) look wrong,\s*(\d+) I doubt", txt)
    return {"right": int(m.group(1)), "wrong": int(m.group(2)), "doubt": int(m.group(3))} if m else None


def date_block(c, runs):
    writes = [r for r in runs if r["json"].get("write")]
    spec = spec_run(runs)
    return {"last_write": writes[-1]["started"][:10] if writes else None, "last_write_run": writes[-1]["name"] if writes else None,
            "last_spec": spec["started"][:10] if spec else None, "last_spec_run": spec["name"] if spec else None,
            "newest_observation": one(c, "select max(substr(observed_at,1,10)) from source_observation", default=None)}


def planted_by_run(runs):
    out = []
    for r in runs:
        pl = read_jsonl(os.path.join(r["dir"], "verify", "planted.jsonl"))
        if pl:
            out.append({"name": r["name"], "n": len(pl), "caught": sum(1 for x in pl if x.get("verdict") == "mismatch"),
                        "error": sum(1 for x in pl if x.get("verdict") == "verifier_error")})
    return out


def values_and_coverage(c, vrows, fields):
    ev = evidence_sets(c)
    cev = cell_evidence(c)
    values = with_ev = with_url = 0
    classes = {k: 0 for k in EV_ORDER}
    by_field = {f: {k: 0 for k in EV_ORDER} for f in fields}
    brochure_page = 0
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
            entry = cev.get(key_own) or (cev.get(key_base) if r["base_variant_id"] else None)
            cls = classify_cell(entry)
            classes[cls] += 1
            by_field[f][cls] += 1
            if cls == "brochure" and entry[1]:
                brochure_page += 1
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
    return {"values": values, "with_evidence": with_ev, "with_url": with_url, "n_fields": len(fields), "classes": classes,
            "brochure_page": brochure_page, "by_field": by_field}, heat


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




# ---------------------------------------------------------------- more KB blocks
def read_tsv(path):
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f, delimiter="\t"))
    except (OSError, csv.Error):
        return []


def per_source_counts(c):
    """Rows stored per source: page observations plus the review, owner and safety rows that cite the source. Sources with none are left out."""
    out = []
    for r in rows(c, "select id, name, source_type, authority_tier from source order by authority_tier, id"):
        n = 0
        for t, col in [("source_observation", "source_id"), ("professional_assessment", "source_id"), ("owner_rating", "source_id"),
                       ("owner_theme", "source_id"), ("safety_test", "source_id")]:
            if has(c, t):
                n += one(c, 'select count(*) from "%s" where "%s"=?' % (t, col), (r[0],))
        if n:
            out.append({"name": r[1], "type": r[2], "tier": r[3], "observations": n})
    return out


def reviews_extra(c):
    """Owner themes grouped by direction, and a few expert notes with their source and date."""
    by_dir = {"positive": [], "negative": [], "mixed": []}
    for r in rows(c, "select coalesce(label, theme), direction, sum(mentions), count(distinct model_id) from owner_theme "
                     "group by 1,2 order by 3 desc, 1"):
        by_dir.setdefault(r[1], []).append({"theme": str(r[0]).replace("_", " "), "mentions": r[2], "models": r[3]})
    notes = [dict(r) for r in rows(
        c, "select ma.name as make, mo.name as model, p.source_aspect as aspect, p.score, p.scale_max, p.note, p.published_on, "
           "s.name as source from professional_assessment p join model mo on mo.id=p.model_id "
           "join manufacturer ma on ma.id=mo.manufacturer_id join source s on s.id=p.source_id "
           "where p.status='current' and p.note is not null and p.note<>'' and p.published_on is not null "
           "order by mo.name, p.source_aspect")]
    seen, uniq = set(), []
    for n in notes:
        if n["model"] not in seen:
            seen.add(n["model"])
            uniq.append(n)
    pick = [uniq[i * len(uniq) // 3] for i in range(3)] if len(uniq) >= 3 else uniq
    return {"themes_by_direction": by_dir, "notes": pick, "n_current": one(c, "select count(*) from professional_assessment where status='current'"),
            "n_notes": one(c, "select count(*) from professional_assessment where status='current' and note is not null and note<>''"),
            "n_theme_models": one(c, "select count(distinct model_id) from owner_theme")}


def find_payload_value(obj, words, prefer=None):
    """First (key, value) in a nested payload whose key contains every word (case-insensitive) and whose value is not empty.
    With prefer set, keys that also contain it win."""
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (str, int, float)) and str(v).strip() and all(w in str(k).lower() for w in words):
                    found.append((str(k), str(v)))
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    if prefer:
        for k, v in found:
            if prefer in k.lower():
                return k, v
    return found[0] if found else None


def provenance_example(c, vid):
    """Follow one stored value of one variant back to its evidence rows."""
    if not vid or not has(c, "field_provenance"):
        return None
    best = None
    for fld in ["mileage_arai_kmpl", "engine_cc", "ground_clearance_mm", "boot_space_litres", "seating_capacity", "airbags"]:
        ev = [dict(r) for r in c.execute(
            "select fp.field_name, fp.accepted_value, fp.decision, fp.decision_reason, fp.decided_at, o.id as obs, s.name as source, "
            "o.source_url, o.extraction_method, o.observed_at, o.raw_payload from field_provenance fp "
            "join source_observation o on o.id=fp.source_observation_id join source s on s.id=o.source_id "
            "where fp.variant_id=? and fp.field_name=? and fp.decision in ('accepted','confirmed') and o.source_url is not null "
            "and o.source_url<>'' order by fp.decided_at, fp.id", (vid, fld))]
        if len({e["source"] for e in ev}) >= 2:
            best = (fld, ev)
            break
    if not best:
        return None
    fld, ev = best
    table = F.FIELDS[fld][0]
    if table == "variant":
        stored = one(c, 'select "%s" from %s where id=?' % (fld, "v_variant_canonical_q" if has(c, "v_variant_canonical_q") else "variant"), (vid,), None)
    else:
        stored = one(c, 'select p."%s" from variant v join powertrain p on p.id=v.powertrain_id where v.id=?' % fld, (vid,), None)
    name = one(c, "select ma.name||' '||mo.name||' '||v.name from variant v join model mo on mo.id=v.model_id "
                  "join manufacturer ma on ma.id=mo.manufacturer_id where v.id=?", (vid,), "")
    words = {"mileage_arai_kmpl": ["mileage"], "engine_cc": ["displacement"], "ground_clearance_mm": ["ground"],
             "boot_space_litres": ["boot"], "seating_capacity": ["seating"], "airbags": ["airbag"]}[fld]
    out = []
    for e in ev[:4]:
        snippet = None
        try:
            snippet = find_payload_value(json.loads(e["raw_payload"] or "null"), words, "arai" if fld == "mileage_arai_kmpl" else None)
        except ValueError:
            pass
        out.append({k: e[k] for k in ("source", "source_url", "decision", "decision_reason", "decided_at", "obs", "observed_at",
                                      "extraction_method", "accepted_value")} | {"snippet": snippet})
    return {"variant_id": vid, "variant": name, "field": fld, "stored": stored, "evidence": out, "n_evidence": len(ev)}


# ---------------------------------------------------------------- pipeline walk
def trim_text(s, n=110):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def what_changed(r):
    j = r["json"]
    st = j.get("stage") or {}
    w = j.get("write")
    if not w:
        return "Dry run: staged and gated, the KB was not touched (%s operations staged)." % fmt(st.get("ops") or 0)
    g = gate_rows(j)
    grown = ["%s %s" % (t, ("+" if a - b >= 0 else "") + fmt(a - b)) for t, (b, a) in sorted(g.items()) if a != b and t != "source_observation"]
    cb, ca = j.get("coverage_before"), j.get("coverage_after")
    bits = []
    if cb and ca:
        bits.append("models %s to %s, variants %s to %s" % (fmt(cb["models"]), fmt(ca["models"]), fmt(cb["variants"]), fmt(ca["variants"])))
    if grown and not (cb and ca):
        bits.append("rows added: " + ", ".join(grown[:3]))
    bits.append("%s rows written" % fmt(w.get("rows") or 0))
    return "; ".join(bits).capitalize() + "."


def history_table(runs):
    out = []
    for r in runs:
        j = r["json"]
        gates = (j.get("stage") or {}).get("gates") or {}
        ok = sum(1 for v in gates.values() if v.get("ok"))
        out.append({"name": r["name"], "date": r["started"][:10], "kind": run_kind(r), "wrote": bool(j.get("write")),
                    "changed": what_changed(r),
                    "gates": ("%d of %d passed" % (ok, len(gates)) if gates else "no gate record") +
                             ("; re-run changed 0" if (j.get("stage") or {}).get("idempotent") else "")})
    return out


def pipeline_data(c, runs, trust, glance, kb_counts):
    spec = next((r for r in reversed(runs) if r["json"].get("write") and r["json"].get("discovery")), None) or \
        next((r for r in reversed(runs) if r["json"].get("discovery")), None)
    P = {"run": spec["name"] if spec else None, "date": spec["started"][:10] if spec else None}
    if not spec:
        return P
    j = spec["json"]
    st, fetch, gates = j.get("stats") or {}, j.get("fetch") or {}, (j.get("stage") or {}).get("gates") or {}
    P.update(discovery=j.get("discovery") or {}, stats=st, fetch=fetch, conflicts_total=j.get("conflicts"),
             processed=j.get("processed"), ops=(j.get("stage") or {}).get("ops"), idempotent=(j.get("stage") or {}).get("idempotent"),
             gates={k: v for k, v in gates.items()}, write=j.get("write"), review_items=j.get("review_items"))
    links = read_tsv(os.path.join(spec["dir"], "links.tsv"))
    reasons = {}
    for r in links:
        reasons[r["site_link_reason"]] = reasons.get(r["site_link_reason"], 0) + 1
    P["link_reasons"] = reasons

    def price(r, k):
        try:
            return float(r[k])
        except (KeyError, ValueError):
            return None
    linked = None
    for r in links:
        a, b = price(r, "carwale_price"), price(r, "cardekho_price")
        if r["carwale"] and r["cardekho"] and r["kb_variant_id"] and a and b and a != b and r["site_link_reason"] == "identity":
            linked = dict(r, diff=abs(a - b) / a)
            break
    P["link_ok"] = linked
    P["link_refused"] = next((r for r in links if r["carwale"] and not r["cardekho"] and r["site_link_reason"].startswith("no candidate")), None)
    conf = read_tsv(os.path.join(spec["dir"], "conflicts.tsv"))
    kinds = {}
    for r in conf:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    P["conflict_kinds"] = kinds
    P["conflict_high"] = sum(1 for r in conf if r.get("high") == "1")
    P["conflict_ex"] = next((r for r in conf if r["kind"] == "aggregator_vs_aggregator" and r["high"] == "1" and r["kb_value"] != ""), None) or \
        next((r for r in conf if r["kind"] == "aggregator_vs_aggregator"), None)
    P["conflict_ex2"] = next((r for r in conf if r["kind"] == "generic_vs_specific"), None)
    # one real value followed through extraction and provenance
    P["provenance"] = provenance_example(c, int(linked["kb_variant_id"])) if linked else None
    # verification examples
    if trust:
        run = next(r for r in runs if r["name"] == trust["run"])
        res = read_jsonl(os.path.join(run["dir"], "verify", "results.jsonl"))
        P["verify_ok"] = next((x for x in res if x["verdict"] == "match" and x["source_class"] == "brochure"), None) or \
            next((x for x in res if x["verdict"] == "match"), None)
        P["verify_bad"] = next((x for x in res if x["verdict"] == "mismatch" and x["source_class"] == "aggregator"), None) or \
            next((x for x in res if x["verdict"] == "mismatch"), None)
    # review layers: the latest written run that carries a text audit
    rv = next((r for r in reversed(runs) if r["json"].get("write") and r["json"].get("text") and r["name"].startswith("reviews")), None)
    if rv:
        rj = rv["json"]
        P["layers"] = {"run": rv["name"], "text": rj.get("text"), "numbers": rj.get("numbers_check"),
                       "gate": ((rj.get("stage") or {}).get("gates") or {}).get("reviews")}
    return P


# ---------------------------------------------------------------- recommender files
def parse_config_py(path):
    out = {}
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass
    return out


def csv_stats(path, model_col="model"):
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rs = list(csv.DictReader(f))
    except OSError:
        return None
    return {"rows": len(rs), "models": len({r.get(model_col) for r in rs if r.get(model_col)}), "cols": list(rs[0].keys()) if rs else [],
            "data": rs}


def downscale_jpeg(src, max_bytes=150000):
    """PNG to a JPEG under max_bytes using sips (macOS). Returns base64 text, or None."""
    if not shutil.which("sips"):
        return None
    tmp = tempfile.mkdtemp()
    try:
        for width, q in [(1000, 70), (960, 62), (900, 55), (820, 50), (720, 45)]:
            dst = os.path.join(tmp, "o.jpg")
            r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q), "-Z", str(width), src, "--out", dst],
                               capture_output=True)
            if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) <= max_bytes:
                with open(dst, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def load_eval(path):
    d = read_json(path)
    if not d or "summary" not in d:
        return None
    s = d["summary"]
    cs, rl, eh = s.get("constraint_satisfaction", {}), s.get("relaxed_responses", {}), s.get("empty_handling", {})
    up, sl = s.get("unknown_probe", {}), s.get("shortlist_agreement", {})
    return {"file": os.path.basename(path), "engine": d.get("engine"), "n_queries": d.get("n_queries"),
            "with_cars": cs.get("queries_with_cars"), "zero_viol": cs.get("queries_zero_violations"),
            "violating": [v["id"] for v in cs.get("violations", [])],
            "relaxed": rl.get("n"), "relaxed_truthful": rl.get("truthfully_labelled"), "relaxed_mislabelled": rl.get("mislabelled"),
            "empty_expected": eh.get("expect_empty_queries"), "empty_outcomes": eh.get("outcomes"),
            "shortlist_filled": sl.get("filled"), "recall8": sl.get("recall_at_8"), "mrr": sl.get("mrr"),
            "probe_n": up.get("n_probes"), "probe_returned": up.get("still_returned"), "probe_lacking_above": up.get("known_lacking_above"),
            "probe_newly_above": up.get("known_lacking_newly_above"),
            "para_jaccard": (s.get("paraphrase_consistency") or {}).get("mean_jaccard_top5")}


def engine_data(recsys_dir):
    root = os.path.expanduser(recsys_dir or "")
    if not root or not os.path.isdir(root):
        return {"found": False}
    E = {"found": True}
    E["config"] = parse_config_py(os.path.join(root, "services", "recsys", "config.py"))
    res_dir = os.path.join(root, "eval", "results")

    def pick(names):
        for n in names:
            e = load_eval(os.path.join(res_dir, n))
            if e:
                return e
        return None
    E["v3_main"] = pick(["final_v3_main.json", "themes_on_main.json", "newcat_b_main.json"])
    E["v3_held"] = pick(["final_v3_heldout.json", "themes_on_heldout.json", "newcat_b_heldout.json"])
    E["cur_main"] = pick(["final_current_main.json", "newcat_cur_new_main.json"])
    E["cur_held"] = pick(["final_current_heldout.json"])
    cat = csv_stats(os.path.join(root, "data", "catalogue_v3", "catalogue.csv"), "model")
    meta = read_json(os.path.join(root, "data", "catalogue_v3", "catalogue_meta.json")) or {}
    E["catalogue"] = {"rows": cat["rows"], "models": cat["models"]} if cat else None
    E["catalogue_models"] = sorted({r.get("model") for r in cat["data"] if r.get("model")}) if cat else []
    E["catalogue_fuel"] = meta.get("fuel_type_distribution")
    newr = [r for r in (cat["data"] if cat else []) if (r.get("variant_id") or "").isdigit() and int(r["variant_id"]) > 833]
    if newr:   # the rows added after the original 832 variants: how much of the fields once missing is now filled
        E["added_fill"] = {"rows": len(newr), **{c: sum(1 for r in newr if r.get(c)) / len(newr) for c in ("length_mm", "abs", "esc", "adas_available")}}
    if cat:
        E["blank_share"] = {col: sum(1 for r in cat["data"] if not (r.get(col) or "").strip()) / len(cat["data"]) for col in ("adas_available", "sunroof")
                            if col in cat["cols"]}
    # the later audit-style figure that counts a blank as not met, when its result file exists
    af = read_json(os.path.join(res_dir, "audit_fix_v3_main.json"))
    E["verified_satisfaction"] = None
    if isinstance(af, dict):
        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if "verified" in str(k).lower() and "satisf" in (str(k) + path).lower() and isinstance(v, dict):
                        return v
                    r = walk(v, path + "/" + str(k))
                    if r is not None:
                        return r
            return None
        E["verified_satisfaction"] = walk(af.get("summary", af))
    # was the second query set used again after the parser changed? (read only: local git history)
    first = git(root, "log", "--diff-filter=A", "--format=%H %cI", "--", "eval/heldout_queries.jsonl")
    if first and first.strip():
        sha, when = first.strip().splitlines()[-1].split()
        after = git(root, "log", "--format=%h", "%s..HEAD" % sha, "--", "services/intent_v2.py", "services/typos.py", "services/recsys/llm_parse.py")
        E["heldout_reuse"] = {"written": when[:10], "parser_commits_after": len([x for x in (after or "").split() if x]),
                              "result_files": len(glob.glob(os.path.join(res_dir, "*heldout*.json")))}
    # shortlist size
    sheet = csv_stats(os.path.join(root, "eval", "shortlist_sheet.csv"), "id")
    if sheet:
        E["shortlist"] = {"queries": sheet["rows"], "picks": sum(1 for r in sheet["data"] for k in r if k.startswith("car_") and r[k])}
    # review data facts
    a = csv_stats(os.path.join(root, "data", "assessments.csv"))
    if a:
        vals = [float(r["raw_score"]) / float(r["scale_max"]) * 10 for r in a["data"] if r.get("raw_score") and r.get("scale_max") and r.get("aspect") == "overall"]
        E["assess"] = {"rows": a["rows"], "models": a["models"], "with_note": sum(1 for r in a["data"] if r.get("note")),
                       "min10": min(vals) if vals else None, "max10": max(vals) if vals else None,
                       "model_names": sorted({r["model"] for r in a["data"]})}
    o = csv_stats(os.path.join(root, "data", "owner_ratings.csv"))
    if o:
        ov = [float(r["raw_score"]) for r in o["data"] if r.get("source_aspect") == "overall" and r.get("raw_score")]
        E["owner"] = {"mean_overall": (sum(ov) / len(ov)) if ov else None, "scale": 5, "rows": o["rows"], "models": o["models"], "low_conf_models": len({r["model"] for r in o["data"] if r.get("low_confidence") == "true"})}
    t = csv_stats(os.path.join(root, "data", "owner_themes.csv"))
    if t:
        E["themes"] = {"rows": t["rows"], "models": t["models"]}
    # documents
    docs = os.path.join(root, "docs")
    rev = ""
    try:
        rev = open(os.path.join(docs, "V3_REVIEW_2026-11-14.md"), encoding="utf-8").read()
    except OSError:
        pass
    E["docs_found"] = [n for n in ["RECOMMENDER_DESIGN_PLAN.md", "V3_REVIEW_2026-11-14.md", "V3_SHORTLIST_GAP_2026-11-15.md", "API_AND_DEPLOY.md"]
                       if os.path.exists(os.path.join(docs, n))]
    m = list(re.finditer(r"\|\s*Shortlist recall@8 / MRR\s*\|\s*([\d.]+) / ([\d.]+)\s*\|\s*n/a\s*\|\s*([\d.]+) / ([\d.]+)\s*\|", rev))
    if m:
        x = m[-1]
        E["final_doc"] = {"v3_recall": float(x.group(1)), "v3_mrr": float(x.group(2)), "cur_recall": float(x.group(3)), "cur_mrr": float(x.group(4))}
    api = ""
    try:
        api = open(os.path.join(docs, "API_AND_DEPLOY.md"), encoding="utf-8").read()
    except OSError:
        pass
    E["endpoints"] = [{"method": a, "path": b, "text": " ".join([x for x in re.split(r"(?<=[.])\s+", re.sub(r"`", "", d).strip())
                                                                  if not any(w in x for w in ("services.", "recsys", "data/", ".csv"))][:3])}
                      for a, b, d in re.findall(r"^\*\*(GET|POST) (\S+)\*\* - (.+)$", api, re.M)]
    # screenshots
    shots = []
    sdir = os.path.join(root, "docs", "screenshots")

    def newest(pattern):
        fs = sorted(glob.glob(os.path.join(sdir, "**", pattern), recursive=True), key=lambda p: (-os.path.getmtime(p), p))
        return fs[0] if fs else None
    for key, pat, cap in [("card", "*desktop_1280_card1_expanded*.png", "A result card, expanded, at desktop width."),
                          ("page", "family_suv_desktop.png", "The results page in dark theme: query, what was understood, then cards."),
                          ("phone", "*phone_390_card1_expanded*.png", "The same card at phone width.")]:
        p = newest(pat)
        b = downscale_jpeg(p) if p else None
        if b:
            shots.append({"key": key, "caption": cap, "b64": b, "bytes": len(base64.b64decode(b)), "file": os.path.basename(p)})
    E["shots"] = shots
    return E


# ---------------------------------------------------------------- shared look (the web app's tokens, no web fonts)
CSS = r'''
:root{
  color-scheme:light;
  --font:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans",sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --text-sm:.875rem;--text-base:1.0625rem;--text-lg:1.25rem;--text-xl:1.625rem;--leading:1.55;
  --s-1:4px;--s0:8px;--s1:16px;--s2:24px;--s3:32px;--s4:48px;--s5:64px;--s6:96px;
  --r-card:16px;--r-ctl:12px;--r-pill:999px;--page:1180px;
  --bg:#f7f5f0;--surface:#fff;--surface-2:#efebe3;--ink:#17181c;--ink-2:#44474f;--ink-3:#62656d;
  --line:#e2ddd2;--line-strong:#cbc5b8;--accent:#b4410f;--accent-hover:#983509;--accent-ink:#fff;--accent-soft:#fbeadf;
  --accent-text:#933208;--good:#1d6b40;--good-soft:#e1f1e7;--warn-soft:#f6f0e1;--warn-text:#6e5410;--danger:#a3241c;--danger-soft:#fbe6e3;
  --focus:#1f5fd6;--neutral:#8a8d94;
  --shadow:0 1px 2px rgb(23 24 28/.05),0 10px 28px -6px rgb(23 24 28/.12);
  --heat-lo:#f3eee4;--heat-hi:#b4410f;--heat-on-lo:#17181c;--heat-on-hi:#fff;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --bg:#121316;--surface:#1b1d21;--surface-2:#25272c;--ink:#f2f0eb;--ink-2:#cdc9c1;--ink-3:#a29f97;--line:#2e3036;--line-strong:#44474e;
  --accent:#f08a4b;--accent-hover:#f5a271;--accent-ink:#1c0e05;--accent-soft:rgb(240 138 75/.14);--accent-text:#f6ad80;
  --good:#6fd09b;--good-soft:rgb(111 208 155/.13);--warn-soft:rgb(230 196 110/.12);--warn-text:#e8cf8c;--danger:#f3a097;--danger-soft:rgb(243 160 151/.12);
  --focus:#8fb4ff;--neutral:#7d8088;--shadow:0 1px 2px rgb(0 0 0/.3),0 10px 28px -6px rgb(0 0 0/.45);--heat-lo:#25272c;--heat-hi:#9c4416;--heat-on-lo:#f2f0eb;--heat-on-hi:#f2f0eb}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#121316;--surface:#1b1d21;--surface-2:#25272c;--ink:#f2f0eb;--ink-2:#cdc9c1;--ink-3:#a29f97;--line:#2e3036;--line-strong:#44474e;
  --accent:#f08a4b;--accent-hover:#f5a271;--accent-ink:#1c0e05;--accent-soft:rgb(240 138 75/.14);--accent-text:#f6ad80;
  --good:#6fd09b;--good-soft:rgb(111 208 155/.13);--warn-soft:rgb(230 196 110/.12);--warn-text:#e8cf8c;--danger:#f3a097;--danger-soft:rgb(243 160 151/.12);
  --focus:#8fb4ff;--neutral:#7d8088;--shadow:0 1px 2px rgb(0 0 0/.3),0 10px 28px -6px rgb(0 0 0/.45);--heat-lo:#25272c;--heat-hi:#9c4416;--heat-on-lo:#f2f0eb;--heat-on-hi:#f2f0eb}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:88px}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);font-family:var(--font);
  font-size:var(--text-base);line-height:var(--leading);font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased;caret-color:var(--accent)}
::selection{background:var(--accent-soft);color:var(--ink)}
h1,h2,h3,h4,p,ul,ol,dl,dd,figure{margin:0}
ul,ol{padding:0;list-style:none}
a{color:var(--accent-text);text-underline-offset:.2em}
a:hover{color:var(--accent-hover)}
button{font:inherit;color:inherit;cursor:pointer}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:6px}
*{scrollbar-color:var(--line-strong) transparent}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.wrap{width:100%;max-width:var(--page);margin-inline:auto;padding-inline:var(--s1)}
@media (min-width:768px){.wrap{padding-inline:var(--s3)}}
/* header */
.site-header{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 92%,transparent);border-bottom:1px solid var(--line);backdrop-filter:saturate(1.4) blur(10px)}
.site-header .wrap{display:flex;align-items:center;justify-content:space-between;gap:var(--s1);min-height:64px;flex-wrap:wrap;padding-block:6px}
.logo{display:inline-flex;align-items:center;gap:var(--s0);font-weight:750;font-size:1.25rem;letter-spacing:-.02em;text-decoration:none;color:var(--ink)}
.logo svg{width:28px;height:28px;color:var(--accent)}
.hdr-right{display:flex;align-items:center;gap:var(--s0);flex-wrap:wrap}
.nav{display:flex;gap:var(--s-1);flex-wrap:wrap}
@media (max-width:760px){
  .site-header .wrap{flex-wrap:nowrap;gap:var(--s0);height:63px;min-height:0;padding-block:0}
  .logo{flex:none;font-size:1.125rem}
  .hdr-right{flex:1;min-width:0;flex-wrap:nowrap;gap:var(--s-1)}
  .nav{flex:1;min-width:0;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;
    -webkit-mask-image:linear-gradient(90deg,transparent,#000 12px,#000 calc(100% - 20px),transparent);mask-image:linear-gradient(90deg,transparent,#000 12px,#000 calc(100% - 20px),transparent);padding-inline:12px 20px}
  .nav::-webkit-scrollbar{display:none}
  .nav a{padding:var(--s0) 10px;font-size:.8125rem;flex:none}
  .hdr-right .btn{flex:none;min-height:40px;padding-inline:12px}
  .hdr-right .btn .lbl{display:none}
}
.nav a{padding:var(--s0) 12px;border-radius:var(--r-pill);font-size:var(--text-sm);font-weight:550;color:var(--ink-2);text-decoration:none;white-space:nowrap}
.nav a:hover{color:var(--ink);background:var(--surface-2)}
.nav a[aria-current="page"]{color:var(--ink);background:var(--surface-2);font-weight:700}
.nav a.back{color:var(--accent-text)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--s0);min-height:40px;padding:8px var(--s1);border:1px solid var(--line-strong);border-radius:var(--r-ctl);
  background:transparent;color:var(--ink-2);font-weight:550;font-size:var(--text-sm);text-decoration:none;white-space:nowrap;transition:border-color .15s,color .15s,background-color .15s}
.btn:hover{border-color:var(--ink-3);color:var(--ink)}
.btn-primary{background:var(--accent);border-color:transparent;color:var(--accent-ink);font-weight:650}
.btn-primary:hover{background:var(--accent-hover);color:var(--accent-ink);border-color:transparent}
/* page */
main{flex:1}
.page-head{padding-block:var(--s5) var(--s3)}
h1{font-size:clamp(2rem,1.2rem + 3.2vw,3.25rem);line-height:1.08;letter-spacing:-.03em;font-weight:780;text-wrap:balance}
.lede{margin-top:var(--s2);max-width:42em;color:var(--ink-2);font-size:var(--text-lg);line-height:1.5;text-wrap:pretty}
.meta{margin-top:var(--s2);display:flex;flex-wrap:wrap;gap:var(--s-1) var(--s2);font-size:var(--text-sm);color:var(--ink-3)}
.meta b{color:var(--ink-2);font-weight:650}
.section{padding-block:var(--s5) 0}
.section>.wrap>h2,.section h2{font-size:clamp(1.5rem,1.2rem + 1.3vw,2.25rem);line-height:1.15;letter-spacing:-.025em;font-weight:750;text-wrap:balance}
.section-lede{margin-top:var(--s1);max-width:42em;color:var(--ink-2);text-wrap:pretty}
h3{font-size:1.125rem;line-height:1.3;letter-spacing:-.01em;font-weight:700}
.sub{margin-top:var(--s4)}
.section-lede+*,.section .wrap>h2+*:not(.section-lede){margin-top:var(--s3)}
.sub h3{margin-bottom:var(--s0)}
.note{font-size:var(--text-sm);color:var(--ink-3);margin-top:var(--s1);max-width:62em}
.src{font-size:.8125rem;color:var(--ink-3);margin-top:var(--s0)}
.src b{color:var(--ink-2);font-weight:600}
.mono{font-family:var(--mono);font-size:.9em}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card);padding:var(--s2)}
.notice{padding:var(--s1) var(--s2);border-radius:var(--r-card);background:var(--accent-soft);color:var(--ink);max-width:62em}
.notice strong{font-weight:700}
.notice.warn{background:var(--warn-soft)}
.empty{padding:var(--s3);border:1px dashed var(--line-strong);border-radius:var(--r-card);color:var(--ink-2);background:var(--surface)}
.grid{display:grid;gap:var(--s2)}
.g2{grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr))}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card)}
/* facts list */
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:0 var(--s3)}
.facts>div{display:flex;align-items:baseline;gap:var(--s1);padding:12px 0;border-bottom:1px solid var(--line)}
.facts dt{order:2;color:var(--ink-2);font-size:var(--text-sm)}
.facts dd{order:1;min-width:5.5ch;font-size:1.375rem;font-weight:720;letter-spacing:-.02em;text-align:right;flex:none;width:7ch}
.facts.sm dd{font-size:1.125rem;width:10.5ch;white-space:nowrap}
/* landing cards */
.pcard{display:flex;flex-direction:column;gap:var(--s1);text-decoration:none;color:var(--ink);transition:border-color .15s,box-shadow .15s,transform .15s}
.pcard:hover{border-color:var(--accent);color:var(--ink);transform:translateY(-2px)}
.lbl{font-size:.875rem;font-weight:700;color:var(--ink-3);letter-spacing:0}
.pcard h2{font-size:var(--text-xl);letter-spacing:-.02em}
.pcard p{color:var(--ink-2);font-size:var(--text-base)}
.pcard .go{margin-top:auto;font-weight:650;color:var(--accent-text)}
/* svg */
svg{max-width:100%}
svg text{font-family:var(--font);fill:var(--ink)}
svg .t2{fill:var(--ink-2)} svg .t3{fill:var(--ink-3)}
svg .box{fill:var(--surface);stroke:var(--line-strong);stroke-width:1.5}
svg .box.acc{fill:var(--accent);stroke:var(--accent)}
svg .box.soft{fill:var(--accent-soft);stroke:var(--accent)}
svg .on-acc{fill:var(--accent-ink)}
svg .arrow{stroke:var(--ink-3);stroke-width:2;fill:none}
svg .arrow-head{fill:var(--ink-3)}
svg a:hover .box{stroke:var(--accent);stroke-width:2.5}
svg a:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
svg .dash{stroke-dasharray:5 4}
.ov-tall{display:none}
@media (max-width:760px){.ov-wide{display:none}.ov-tall{display:block}}
.bar{display:block;width:100%;height:14px}
.bar .m{fill:var(--accent)} .bar .bgt{fill:var(--line)}
.brow{display:grid;grid-template-columns:minmax(96px,170px) minmax(0,1fr) minmax(48px,auto);gap:var(--s0) var(--s1);align-items:center;padding:5px 0;font-size:var(--text-sm)}
.brow .l{color:var(--ink-2);overflow-wrap:anywhere}
.brow .v{text-align:right;font-weight:650}
.brow.cur .bar .m{fill:var(--neutral)}
.brow.wide{grid-template-columns:minmax(150px,300px) minmax(0,1fr) auto}
.brow .v{white-space:nowrap}
@media (max-width:640px){.brow.wide{grid-template-columns:minmax(0,1fr) auto}.brow.wide .bar{grid-column:1/-1;order:3}}
.legend{display:flex;flex-wrap:wrap;gap:var(--s-1) var(--s2);font-size:var(--text-sm);color:var(--ink-2);margin-bottom:var(--s1)}
.legend span{display:inline-flex;gap:7px;align-items:center}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid var(--line-strong)}
.sw.m{background:var(--accent)}.sw.bad{background:var(--ink)}.sw.unr{background:var(--line-strong)}.sw.ink{background:var(--neutral)}
.sw.cur{background:var(--neutral)}
/* tables */
table{border-collapse:collapse;width:100%}
.tbl{font-size:var(--text-sm);font-variant-numeric:tabular-nums}
.tbl th,.tbl td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
.tbl thead th{color:var(--ink-3);font-weight:650;font-size:.8125rem;border-bottom:1px solid var(--line-strong);white-space:nowrap}
.tbl td.n,.tbl th.n{text-align:right}
.tbl-wrap{overflow:auto;border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:var(--s-1)}
.tbl-wrap .tbl{min-width:560px}
.sortable thead th{padding:0;position:sticky;top:0;background:var(--surface);z-index:1}
.sortable thead button{all:unset;box-sizing:border-box;display:block;width:100%;padding:9px 12px;cursor:pointer;font-size:.8125rem;font-weight:650;color:var(--ink-3);white-space:nowrap}
.sortable thead th.n button{text-align:right}
.sortable thead button:hover{color:var(--ink)}
.sortable thead button:focus-visible{outline:3px solid var(--focus);outline-offset:-3px}
.sortable thead th[aria-sort="ascending"] button::after{content:" \25B2";font-size:.7em}
.sortable thead th[aria-sort="descending"] button::after{content:" \25BC";font-size:.7em}
.heat{min-width:680px;font-size:var(--text-sm);font-variant-numeric:tabular-nums}
.heat th,.heat td{padding:0;text-align:center;border:2px solid var(--surface)}
.heat thead th{padding:8px 4px;color:var(--ink-2);font-weight:600;font-size:.8125rem;text-transform:capitalize}
.heat tbody th{text-align:left;padding:0 12px 0 10px;white-space:nowrap;font-weight:600;background:var(--surface);position:sticky;left:0}
.heat tbody th small{display:block;color:var(--ink-3);font-weight:400;font-size:.75rem}
.heat td{height:40px;min-width:62px;font-weight:650}
.heat tr.all th,.heat tr.all td{border-top:6px solid var(--surface)}
.scale{display:flex;align-items:center;gap:10px;font-size:.8125rem;color:var(--ink-3);margin-top:var(--s1);flex-wrap:wrap}
.scale i{display:block;width:180px;height:12px;border-radius:3px;background:linear-gradient(90deg,var(--heat-lo),var(--heat-hi));border:1px solid var(--line-strong)}
/* pipeline walk */
.stage{padding-block:var(--s5) 0}
.stage-head{display:flex;align-items:center;gap:var(--s1)}
.stage-n{flex:none;display:grid;place-items:center;width:40px;height:40px;border-radius:50%;border:2px solid var(--accent);color:var(--accent-text);font-weight:750;background:var(--surface)}
.stage h2{font-size:clamp(1.5rem,1.2rem + 1.3vw,2.125rem);letter-spacing:-.025em;font-weight:750}
.stage .what{margin-top:var(--s1);font-size:var(--text-lg);max-width:40em;color:var(--ink);text-wrap:pretty}
.stage .why{margin-top:var(--s0);max-width:44em;color:var(--ink-2)}
.stage-body{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:var(--s3);margin-top:var(--s3);align-items:start}
@media (max-width:900px){.stage-body{grid-template-columns:minmax(0,1fr)}}
.nums{display:grid;gap:0}
.nums>div{padding:12px 0;border-bottom:1px solid var(--line)}
.nums>div:first-child{border-top:1px solid var(--line)}
.nums b{display:block;font-size:1.75rem;line-height:1.1;letter-spacing:-.02em;font-weight:750}
.nums span{display:block;font-size:var(--text-sm);color:var(--ink-2);margin-top:2px}
.nums em{display:block;font-style:normal;font-size:.8125rem;color:var(--ink-3);margin-top:2px}
.ex{display:grid;gap:var(--s1)}

.pair{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:var(--s1);align-items:stretch}
@media (max-width:700px){.pair{grid-template-columns:minmax(0,1fr)}.pair .mid{justify-self:start}}
.pair .mid{display:grid;place-items:center;font-size:var(--text-sm);color:var(--ink-3);font-weight:650}
.chip{display:inline-block;padding:2px 10px;border-radius:var(--r-pill);background:var(--surface-2);color:var(--ink-2);font-size:.8125rem;font-weight:600}
.chip.ok{background:var(--good-soft);color:var(--good)} .chip.no{background:var(--danger-soft);color:var(--danger)} .chip.hold{background:var(--warn-soft);color:var(--warn-text)}
.kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px var(--s1);font-size:var(--text-sm)}
.kv dt{color:var(--ink-3)} .kv dd{overflow-wrap:anywhere}
.checks{display:grid;gap:6px;font-size:var(--text-sm);margin-top:var(--s1)}
.checks li{display:flex;gap:var(--s0);align-items:baseline}
.checks .chip{flex:none;min-width:3.4em;text-align:center}
.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:var(--s1)}
.gate{padding:var(--s1) var(--s2);background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card)}
.gate h3{font-size:1.125rem;font-weight:700;margin-bottom:4px;display:flex;justify-content:space-between;gap:var(--s0);align-items:baseline}
.gate p{font-size:var(--text-sm);color:var(--ink-2)}
.steps{counter-reset:s;display:grid;gap:var(--s0)}
.steps li{counter-increment:s;display:grid;grid-template-columns:28px 1fr;gap:var(--s0);font-size:var(--text-sm);color:var(--ink-2);align-items:baseline}
.steps li::before{content:counter(s);display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:var(--surface-2);font-weight:700;color:var(--ink);font-size:.75rem}
.refuse{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:var(--s2)}
.refuse div{padding-top:var(--s1);border-top:2px solid var(--line-strong)}
.refuse h3{font-size:var(--text-base)}
.refuse p{font-size:var(--text-sm);color:var(--ink-2);margin-top:4px}
.flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--s1)}
@media (max-width:900px){.flow{grid-template-columns:minmax(0,1fr)}}
.trace{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--s1);align-items:start;overflow-wrap:anywhere}
@media (max-width:1000px){.trace{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:600px){.trace{grid-template-columns:minmax(0,1fr)}}
.trace .card{padding:var(--s1) var(--s2);font-size:var(--text-sm)}
.trace .lbl{margin-bottom:var(--s0)}
.trace .big{font-size:1.5rem;font-weight:750;letter-spacing:-.02em;margin:2px 0}
.trace ul li{padding:6px 0;border-top:1px solid var(--line)}
.trace ul li:first-child{border-top:0}
/* trust */
.trow{display:grid;grid-template-columns:minmax(0,220px) minmax(0,1fr) minmax(110px,150px);gap:6px var(--s1);align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}
.trow .tl b{display:block;font-weight:650}
.trow .tl span{display:block;font-size:.8125rem;color:var(--ink-3);line-height:1.35}
.trow .acc{text-align:right}.trow .acc b{font-size:1.15rem}.trow .acc span{display:block;font-size:.75rem;color:var(--ink-3)}
@media (max-width:760px){.trow{grid-template-columns:minmax(0,1fr)}.trow .acc{text-align:left}}
.stackbar{display:block;width:100%;height:24px}
.stackbar .m{fill:var(--accent)}.stackbar .bad{fill:var(--ink)}.stackbar .unr{fill:var(--line-strong)}.stackbar .ink{fill:var(--neutral)}
.covbar{display:flex;height:34px;border-radius:var(--r-ctl);overflow:hidden;gap:2px}
.covbar div{display:flex;align-items:center;padding:0 12px;font-size:var(--text-sm);font-weight:700;white-space:nowrap;overflow:hidden}
.cv-b{background:var(--accent);color:var(--accent-ink)}.cv-e{background:var(--accent-soft);color:var(--ink)}.cv-o{background:var(--surface-2);color:var(--ink)}.cv-n{background:var(--line);color:var(--ink-2)}
.themes{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:var(--s2) var(--s3)}
.notes{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:var(--s1)}
.notes figure{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card);padding:var(--s1) var(--s2)}
.notes blockquote{margin:var(--s0) 0;font-size:var(--text-base);color:var(--ink)}
.notes figcaption{font-size:.8125rem;color:var(--ink-3)}
/* engine */
.shots{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:var(--s3);align-items:start}
@media (max-width:900px){.shots{grid-template-columns:minmax(0,1fr)}}
.shotbox{position:relative;border:1px solid var(--line);border-radius:var(--r-card);overflow:hidden;background:#fff}
.shotbox img{display:block;width:100%;height:auto}
.pin{position:absolute;transform:translate(-50%,-50%);width:26px;height:26px;border-radius:50%;background:var(--accent);color:var(--accent-ink);display:grid;place-items:center;font-size:.8125rem;font-weight:750;border:2px solid #fff;box-shadow:0 1px 4px rgb(0 0 0/.4)}
.legendlist{display:grid;gap:var(--s1);counter-reset:p}
.legendlist li{display:grid;grid-template-columns:28px 1fr;gap:var(--s0);font-size:var(--text-sm);color:var(--ink-2)}
.legendlist li::before{counter-increment:p;content:counter(p);display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:var(--accent);color:var(--accent-ink);font-weight:750;font-size:.75rem}
.legendlist b{color:var(--ink)}
.limits li{padding:var(--s1) 0;border-bottom:1px solid var(--line);max-width:62em}
.limits li:first-child{border-top:1px solid var(--line)}
.limits b{font-weight:700}
.limits em{display:block;font-style:normal;font-size:.8125rem;color:var(--ink-3);margin-top:2px}
.api li{display:grid;grid-template-columns:70px minmax(0,1fr);gap:var(--s1);padding:var(--s1) 0;border-bottom:1px solid var(--line);font-size:var(--text-sm)}
.api .m{font-family:var(--mono);font-weight:700;color:var(--accent-text)}
/* evidence strength, plain statements */
.plain{font-size:var(--text-lg);line-height:1.5;max-width:42em;color:var(--ink);text-wrap:pretty}
.stackbar.evbar{height:36px;border-radius:var(--r-ctl)}
.stackbar .ev-b{fill:var(--good)}.stackbar .ev-2{fill:var(--accent)}.stackbar .ev-1{fill:var(--neutral)}.stackbar .ev-i{fill:var(--warn-text)}.stackbar .ev-n{fill:var(--line-strong)}
.sw.ev-b{background:var(--good)}.sw.ev-2{background:var(--accent)}.sw.ev-1{background:var(--neutral)}.sw.ev-i{background:var(--warn-text)}.sw.ev-n{background:var(--line-strong)}
.evrows{margin-top:var(--s2);border-top:1px solid var(--line)}
.evrow{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:var(--s1);padding:14px 0;border-bottom:1px solid var(--line);align-items:start}
.evrow .sw{margin-top:5px}
.evrow b{font-weight:680}
.evrow .d{display:block;margin-top:2px;color:var(--ink-2);font-size:var(--text-sm);max-width:52em}
.evrow .n{text-align:right;font-weight:720;font-size:1.125rem;white-space:nowrap}
.evrow .n small{display:block;color:var(--ink-2);font-weight:550;font-size:var(--text-sm)}
.notice ul{list-style:disc;padding-left:1.25rem;margin-top:var(--s0);display:grid;gap:6px}
.notice p+p,.notice p+ul{margin-top:var(--s0)}
.facts.sm dt{max-width:34em}
.facts.sm dd{width:auto;min-width:10.5ch}
.landing-ev{margin-top:var(--s5)}
/* footer */
.site-footer{margin-top:var(--s6);padding-block:var(--s3);border-top:1px solid var(--line);font-size:var(--text-sm);color:var(--ink-3)}
.site-footer .wrap{display:flex;flex-wrap:wrap;gap:var(--s0) var(--s3);justify-content:space-between}
.site-footer p{max-width:60em}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
'''

JS = r'''
(function(){
'use strict';
var root=document.documentElement,b=document.getElementById('themebtn'),modes=['auto','light','dark'],i=0;
try{var s=localStorage.getItem('carrec-theme');if(s&&modes.indexOf(s)>-1)i=modes.indexOf(s);}catch(e){}
function apply(){var m=modes[i];if(m==='auto')root.removeAttribute('data-theme');else root.setAttribute('data-theme',m);
  if(b)b.innerHTML='<span class="lbl">Theme: </span>'+m.charAt(0).toUpperCase()+m.slice(1);try{localStorage.setItem('carrec-theme',m);}catch(e){}}
if(b)b.addEventListener('click',function(){i=(i+1)%3;apply();});
apply();
var cur=document.querySelector('.nav a[aria-current]'),nv=document.querySelector('.nav');
if(cur&&nv&&nv.scrollWidth>nv.clientWidth){nv.scrollLeft=Math.max(0,cur.getBoundingClientRect().left-nv.getBoundingClientRect().left+nv.scrollLeft-nv.clientWidth/2+cur.offsetWidth/2);}
document.querySelectorAll('table.sortable').forEach(function(t){
  var heads=t.querySelectorAll('thead th');
  heads.forEach(function(th,ci){var btn=th.querySelector('button');if(!btn)return;
    btn.addEventListener('click',function(){
      var asc=th.getAttribute('aria-sort')!=='ascending';
      heads.forEach(function(h){h.removeAttribute('aria-sort');});
      th.setAttribute('aria-sort',asc?'ascending':'descending');
      var tb=t.tBodies[0],rs=Array.prototype.slice.call(tb.rows),num=th.classList.contains('n');
      rs.sort(function(a,c){
        var x=a.cells[ci].getAttribute('data-v'),y=c.cells[ci].getAttribute('data-v');
        if(x===null||x===''){return (y===null||y==='')?0:1;} if(y===null||y===''){return -1;}
        var r=num?(parseFloat(x)-parseFloat(y)):x.localeCompare(y);return asc?r:-r;});
      rs.forEach(function(r){tb.appendChild(r);});});});
});
})();
'''


# ---------------------------------------------------------------- html helpers
def E(s):
    return htmllib.escape("" if s is None else str(s), quote=True)


def fmt(n, d=0):
    if n is None:
        return "n/a"
    if isinstance(n, float) and d:
        return "{:,.{d}f}".format(n, d=d)
    return "{:,}".format(int(round(n)))


def pct(x, d=1):
    return "n/a" if x is None else "%.*f%%" % (d, x * 100)


def shorturl(u):
    """Address as text, without the scheme."""
    return re.sub(r"^https?://(www\.)?", "", str(u or ""))


def brochure_ref(ref):
    m = re.search(r"([^/\\]+\.pdf)\s*(p\d+)?", str(ref or ""))
    return (m.group(1) + (" " + m.group(2) if m.group(2) else "")) if m else shorturl(ref)


def rupees(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "n/a"
    return "Rs %s lakh" % ("%.2f" % (x / 100000)).rstrip("0").rstrip(".") if x >= 100000 else "Rs %s" % fmt(x)


def bar_row(label, frac, text, cls=""):
    w = max(0.0, min(1.0, frac or 0)) * 100
    return ('<div class="brow %s"><span class="l">%s</span><svg class="bar" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" '
            'aria-label="%s"><title>%s</title><rect class="bgt" width="100" height="10" rx="2"/><rect class="m" width="%.2f" height="10" rx="2"/></svg>'
            '<span class="v">%s</span></div>' % (cls, E(label), E(label + ": " + text), E(label + ": " + text), w, E(text)))


def stackbar(parts, label):
    """parts: [(count, class, name)]. One SVG bar, widths proportional."""
    tot = sum(p[0] for p in parts) or 1
    x, out = 0.0, []
    for n, cls, name in parts:
        if n:
            w = n / tot * 100
            out.append('<rect class="%s" x="%.3f" y="0" width="%.3f" height="10"><title>%s: %s</title></rect>' % (cls, x, max(w - 0.3, 0.1), E(name), fmt(n)))
            x += w
    return '<svg class="stackbar" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="%s">%s</svg>' % (E(label), "".join(out))


def logo_svg():
    return ('<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="9" fill="currentColor"/>'
            '<path d="M8 19.5l2-5.2c.4-1 1.3-1.6 2.3-1.6h7.4c1 0 1.9.6 2.3 1.6l2 5.2v3.3a1 1 0 0 1-1 1h-1.3a1 1 0 0 1-1-1v-1H11.3v1a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1z" fill="#fff"/>'
            '<circle cx="11.6" cy="18.6" r="1.3" fill="currentColor"/><circle cx="20.4" cy="18.6" r="1.3" fill="currentColor"/></svg>')


def arrow_h(x1, x2, y):
    return ('<path class="arrow" d="M%s %s H%s"/><path class="arrow-head" d="M%s %s l-9 -6 v12 z"/>' % (x1, y, x2 - 8, x2, y))


def arrow_v(x, y1, y2):
    return ('<path class="arrow" d="M%s %s V%s"/><path class="arrow-head" d="M%s %s l-6 -9 h12 z"/>' % (x, y1, y2 - 8, x, y2))


def shell(cur, title, body, ctx, desc=""):
    nav = []
    if ctx.get("app_base"):
        nav.append('<a class="back" href="%s">Back to CarRec</a>' % E(ctx["app_base"]))
    for fn, lab in PAGES:
        nav.append('<a href="%s"%s>%s</a>' % (fn, ' aria-current="page"' if fn == cur else "", lab))
    home = E(ctx["app_base"]) if ctx.get("app_base") else "index.html"
    m = ctx["meta"]
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>%s</title>\n<meta name="description" content="%s">\n<style>%s</style>\n</head>\n<body>\n'
            '<header class="site-header"><div class="wrap"><a class="logo" href="%s" aria-label="CarRec home">%s CarRec</a>'
            '<div class="hdr-right"><nav class="nav" aria-label="Project pages">%s</nav>'
            '<button class="btn" id="themebtn" type="button" aria-label="Change colour theme"><span class="lbl">Theme: </span>Auto</button></div></div></header>\n'
            '<main>\n%s\n</main>\n'
            '<footer class="site-footer"><div class="wrap"><p>Page generated on <b>%s</b> from knowledge base snapshot <span class="mono">%s</span>. This is the date the page was built, not the date the data was updated: '
            'the knowledge base was last written on <b>%s</b> and the listing-site pipeline last ran in full on <b>%s</b>. '
            'Figures are computed from the knowledge base, the pipeline run records and the recommender files, with the source named beside each; a few statements are marked as taken from an independent audit.</p>'
            '<p>CarRec project pages</p></div></footer>\n<script>%s</script>\n</body>\n</html>\n'
            % (E(title), E(desc), CSS, home, logo_svg(), "".join(nav), body, E(m["generated"]), E(m["kb_hash8"]), E(day_text(m["dates"]["last_write"])),
               E(day_text(m["dates"]["last_spec"])), JS))


def page_head(title, lede, ctx, extra=""):
    m = ctx["meta"]
    return ('<div class="page-head wrap"><h1>%s</h1><p class="lede">%s</p><div class="meta"><span>Page generated <b>%s</b></span>'
            '<span>Knowledge base last written <b>%s</b></span><span>Last full pipeline run <b>%s</b></span>'
            '<span>Snapshot <b class="mono">%s</b></span>%s</div></div>' % (E(title), E(lede), E(m["generated"]), E(day_text(m["dates"]["last_write"])),
                                                                         E(day_text(m["dates"]["last_spec"])), E(m["kb_hash8"]), extra))


def section(id_, title, lede, inner):
    return ('<section class="section" id="%s" aria-labelledby="h-%s"><div class="wrap"><h2 id="h-%s">%s</h2>%s%s</div></section>'
            % (id_, id_, id_, E(title), ('<p class="section-lede">%s</p>' % E(lede)) if lede else "", inner))


def src(text):
    return '<p class="src"><b>Source:</b> %s</p>' % E(text)


# ---------------------------------------------------------------- evidence, price and backlog views (shared by the pages)
def day_text(s):
    d = parse_day(s)
    return d.strftime("%d %b %Y").lstrip("0") if d else "n/a"


def evidence_sentence(g):
    cl, tot = g["classes"], g["values"] or 1
    return ("Of %s stored values, %s rest on a maker's brochure, %s on two or more listing sites, %s on one listing site, and %s only on the June 2026 import, "
            "which recorded no source address. %s have no live evidence row at all."
            % (fmt(tot), pct(cl["brochure"] / tot), pct(cl["two_sites"] / tot), pct(cl["one_site"] / tot), pct(cl["import"] / tot), pct(cl["none"] / tot)))


def verified_sentence(T):
    if not T:
        return "No independent check results were found, so no stored value can be called verified."
    o = T["overall"]
    d = o["match"] + o["mismatch"]
    return ("A value is called verified here only if an independent check re-read its source and found the same value. That is true of %s values, in a sample of %s cells (audit run %s): "
            "%s of %s decided cells agreed and %s could not be reached. The other stored values have not been independently checked, and a sample audit is not a guarantee for any of them."
            % (fmt(o["match"]), fmt(o["n"]), T["run"], fmt(o["match"]), fmt(d), fmt(o["unreachable"])))


def evidence_bar(g):
    cl, tot = g["classes"], g["values"] or 1
    label = "Stored values by strongest evidence: " + "; ".join("%s %s" % (EV_LABEL[k], pct(cl[k] / tot)) for k in EV_ORDER)
    return stackbar([(cl[k], EV_CLS[k], EV_LABEL[k]) for k in EV_ORDER], label).replace('class="stackbar"', 'class="stackbar evbar"')


def evidence_view(D):
    g, H, T = D["glance"], D["honest"], D["trust"]
    cl, tot = g["classes"], g["values"] or 1
    items = []
    for k in EV_ORDER:
        plain = EV_PLAIN[k]
        if k == "brochure":
            plain += " %s of these %s cells rest on rows that name the page." % (fmt(g["brochure_page"]), fmt(cl[k]))
        items.append('<li class="evrow"><i class="sw %s" aria-hidden="true"></i><div><b>%s</b><span class="d">%s</span></div><div class="n">%s<small>%s</small></div></li>'
                     % (EV_CLS[k], E(EV_LABEL[k]), E(plain), fmt(cl[k]), pct(cl[k] / tot)))
    out = ('<p class="plain">%s</p><div style="margin-top:var(--s2)">%s</div><ul class="evrows">%s</ul>' % (E(evidence_sentence(g)), evidence_bar(g), "".join(items)))
    out += '<div class="notice" style="margin-top:var(--s2)"><strong>What &ldquo;verified&rdquo; means here.</strong> %s</div>' % E(verified_sentence(T))
    ad = H.get("audit_def")
    if ad and ad["total"]:
        def rowtab(name, cls, total, nf):
            return "<tr><td>%s</td><td class=\"n\">%s</td>%s</tr>" % (E(name), fmt(total), "".join('<td class="n">%s</td>' % pct(cls[k] / total) for k in EV_ORDER))
        diff = max(abs(cl[k] / tot - ad["classes"][k] / ad["total"]) for k in EV_ORDER)
        out += ('<div class="sub"><h3>The same count under the independent audit&rsquo;s rule</h3><div class="tbl-wrap" tabindex="0" role="region" aria-label="Evidence breakdown under two counting rules"><table class="tbl" style="min-width:680px"><thead><tr><th>Counting rule</th><th class="n">Values</th>%s</tr></thead><tbody>%s%s</tbody></table></div>'
                '<p class="note">This page counts the %d tracked fields after quarantined cells are masked, and lets an edition variant inherit the evidence of its base trim. The audit counted %d columns of the raw tables and looked up evidence on each variant only. '
                'The two rules differ by at most %.1f percentage points in any class. Under the audit&rsquo;s rule the import-only share is %s and the brochure share %s.</p></div>'
                % ("".join('<th class="n">%s</th>' % E(EV_LABEL[k]) for k in EV_ORDER),
                   rowtab("This page", cl, tot, g["n_fields"]), rowtab("Audit rule", ad["classes"], ad["total"], ad["n_fields"]), g["n_fields"], ad["n_fields"], diff * 100,
                   pct(ad["classes"]["import"] / ad["total"]), pct(ad["classes"]["brochure"] / ad["total"])))
    wf = []
    for f, c_ in g["by_field"].items():
        n = sum(c_.values())
        if n >= 200:
            wf.append((c_["import"] / n, f, n, c_["import"]))
    wf.sort(reverse=True)
    if wf:
        out += ('<div class="sub"><h3>Fields that rest most often on the import alone</h3>%s<p class="note">Fields with at least 200 stored values, ranked by the share of those values whose only evidence is the import.</p></div>'
                % "".join(bar_row(f.replace("_", " "), sh, "%s of %s" % (pct(sh, 0), fmt(n)), "wide") for sh, f, n, k in wf[:6]))
    return out + src("live evidence rows by source (quarantined rows excluded) for every non-blank stored value, knowledge base snapshot; verification file of run %s" % (T["run"] if T else "n/a"))


def price_view(D):
    P, H = D["honest"]["price"], D["honest"]
    B, dt = H.get("backlog"), H["dates"]
    n = P["n"] or 1
    bars = "".join(bar_row(l, v / n, "%s (%s)" % (fmt(v), pct(v / n)), "wide") for l, v in [
        ("Price read from a site or brochure within 30 days", P["within30"]), ("within 90 days", P["within90"]), ("within 180 days", P["within180"]),
        ("Only the June import (no later price evidence)", P["import_only"]), ("No price evidence", P["no_evidence"])])
    dates = ('<dl class="facts sm" style="margin-top:var(--s2)"><div><dt>Page generated (the build date of this page, not a data date)</dt><dd>%s</dd></div>'
             '<div><dt>Last write to the knowledge base</dt><dd>%s</dd></div><div><dt>Last full run of the listing-site pipeline</dt><dd>%s</dd></div>'
             '<div><dt>Newest price evidence on any variant</dt><dd>%s</dd></div></dl>'
             % (E(day_text(D["meta"]["generated"])), E(day_text(dt["last_write"])), E(day_text(dt["last_spec"])), E(day_text(P["latest"]))))
    imp = ("The import is dated %s, %s days before this page was built." % (day_text(P["import_date"]), fmt(P["import_age"]))) if P["import_date"] else ""
    pend = ""
    if B:
        pend = ("<p class=\"plain\" style=\"margin-top:var(--s2)\">The pipeline has found %s changed prices on existing variants (run %s). None has been applied: changed prices wait for the owner&rsquo;s approval, so the stored price can differ from the current showroom price.</p>"
                % (fmt(B["price_still_pending"]), E(B["run"])))
    return ('<p class="plain">Prices are ex-showroom list prices and may be out of date. %s of %s variants (%s) have price evidence from a listing site or brochure within 180 days of the page date. '
            '%s variants (%s) rest only on the June 2026 import. %s</p><div style="margin-top:var(--s2)">%s</div>%s%s%s'
            % (fmt(P["within180"]), fmt(P["n"]), pct(P["within180"] / n), fmt(P["import_only"]), pct(P["import_only"] / n), imp, bars, pend, dates,
               src("price evidence rows (accepted or confirmed, quarantine excluded) joined to the date each page was read; pending changes from the review file of run %s" % (B["run"] if B else "n/a"))))


def gaps_view(D):
    H = D["honest"]
    B, dup, cg, sp = H.get("backlog"), H.get("duplicates"), H.get("crash"), H.get("spot")
    out = ""
    gaps = []
    if B:
        out += ('<dl class="facts sm"><div><dt>Cells where the sites differ from the knowledge base or could fill a blank, not applied</dt><dd>%s</dd></div>'
                '<div><dt>of those, price cells</dt><dd>%s</dd></div><div><dt>Variants the sites no longer list, not marked</dt><dd>%s</dd></div>'
                '<div><dt>New variants waiting for approval</dt><dd>%s</dd></div><div><dt>Models both sites list that are not in the knowledge base</dt><dd>%s</dd></div>'
                '<div><dt>Variants marked discontinued</dt><dd>%s</dd></div></dl>'
                % (fmt(B["cells_still_pending"]), fmt(B["price_still_pending"]), fmt(B["unlisted_ops"]), fmt(B["new_variants_open"]), fmt(len(B["missing_models"])),
                   fmt(B["marked_discontinued"])))
        out += src("review file of run %s (%s): each proposed value was compared with the knowledge base snapshot, and counted only if the knowledge base does not hold it" % (B["run"], B["date"]))
        gaps.append(("Changes to existing values are held, not applied.",
                     "The pipeline writes new variants and blanks only when two sites agree. A value that differs from the stored one waits for the owner: %s cells (%s of them prices) from run %s are in that queue, and none has been applied."
                     % (fmt(B["cells_still_pending"]), fmt(B["price_still_pending"]), B["run"]), "review file of that run"))
        gaps.append(("Variants missing from the listings can still be recommended.", "%s variants were not found in the current listings. They are recorded for review, not marked discontinued (%s are marked), so the engine can still recommend them. Some may only have been renamed." % (fmt(B["unlisted_ops"]), fmt(B["marked_discontinued"])), "review file; knowledge base snapshot"))
        if B["missing_models"]:
            gaps.append(("Models listed by both sites that the knowledge base lacks.", "%s models are listed as current on both CarWale and CarDekho but have no variants here: %s." % (fmt(len(B["missing_models"])), ", ".join(B["missing_models"])), "discovery file of run %s" % B["run"]))
        if B["out_of_scope"]:
            gaps.append(("Models left out by a price ceiling.", "The pipeline skips models whose base price is above Rs %s. Listed but not added for that reason: %s." % (fmt(B["price_cap"]), ", ".join(B["out_of_scope"])), "discovery file of run %s" % B["run"]))
        if B["one_site_models"]:
            gaps.append(("Models listed by one site only.", "%s names appear on CarDekho alone (for example tour and cargo versions); one site is not enough to add a model: %s." % (fmt(len(B["one_site_models"])), ", ".join(B["one_site_models"])), "discovery file of run %s" % B["run"]))
        if B["facelift"]:
            gaps.append(("Models that may describe an older version.", "CarWale gives a launch date later than the first data held for: %s. Their rows are held for review and may describe the earlier version." % ", ".join(B["facelift"]), "review file of run %s" % B["run"]))
        if B["discontinued_candidates"]:
            gaps.append(("Possibly discontinued.", "%s: one site no longer lists it and the other marks it discontinued. It is still in the knowledge base." % ", ".join(B["discontinued_candidates"]), "review file of run %s" % B["run"]))
    if dup and dup["groups"]:
        gaps.append(("Probable duplicate variants.", "%s groups (%s variants) share model, price, engine and gearbox. Some are real trims with one price; others are the same car stored under two naming styles, so the variant count is higher than the number of distinct cars." % (fmt(dup["groups"]), fmt(dup["variants"])), "knowledge base snapshot"))
    if cg and cg["models"]:
        gaps.append(("Crash ratings stored but not linked.", "%s models have a crash test in the database that is not linked to them, covering %s variants: %s. The app shows these as having no rating on record. %s of %s variants have no linked crash rating. Re-linking is a data change that has not been made." % (fmt(len(cg["models"])), fmt(cg["variants"]), ", ".join("%s (%s-star adult)" % (m["model"], m["stars"]) for m in cg["models"]), fmt(cg["unrated_variants"]), fmt(cg["total_variants"])), "crash-test and link tables, knowledge base snapshot"))
    t = H.get("third", {})
    ex = t.get("expert")
    if ex and ex.get("from"):
        gaps.append(("Expert scores are dated.", "Autocar India scores were published between %s and %s. A model changed after its review may be scored on the earlier car." % (day_text(ex["from"]), day_text(ex["to"])), "expert score rows"))
    th = t.get("themes")
    if th and th["rows"]:
        gaps.append(("Some owner themes rest on very few reviews.", "%s of %s owner theme rows rest on 3 or fewer mentions, and %s on fewer than 5, out of a sample of reviews per model." % (fmt(th["le3"]), fmt(th["rows"]), fmt(th["lt5"])), "owner theme table"))
    if sp:
        gaps.append(("An independent spot check found errors.", "A reviewer judged 40 stored values from memory, not from a source lookup: %s looked right, %s looked wrong and %s were doubtful. The reviewer saw the errors cluster in fields that rest on the import alone and in recently added models." % (fmt(sp["right"]), fmt(sp["wrong"]), fmt(sp["doubt"])), "independent audit file"))
    if gaps:
        out += '<ul class="limits" style="margin-top:var(--s2)">%s</ul>' % "".join("<li><b>%s</b> %s<em>%s</em></li>" % (E(a), E(b), E(c)) for a, b, c in gaps)
    return out


def notice_third_party(D, where):
    t = D["honest"].get("third", {})
    ex, ow, th = t.get("expert"), t.get("owner"), t.get("themes")
    parts = []
    if ex and ex["rows"]:
        parts.append("From Autocar India: %s expert scores for %s models, %s short summaries written in the project&rsquo;s own words, and %s short quotes (longest %s characters), each with a link to the page it came from." % (fmt(ex["rows"]), fmt(ex["models"]), fmt(ex["notes"]), fmt(ex["quotes"]), fmt(ex["quote_max"])))
    if ow and ow["rows"]:
        parts.append("From CarWale: owner ratings (%s rows for %s models)%s, with links to the review pages." % (fmt(ow["rows"]), fmt(ow["models"]), (" and %s themes distilled from sampled owner reviews, in the project&rsquo;s own words" % fmt(th["rows"])) if th and th["rows"] else ""))
    if not parts:
        return ""
    return ('<div class="notice"><strong>Third-party content.</strong> %s This content remains that of Autocar India and CarWale. The project is non-commercial. To ask for something to be removed, contact: see repository.</div>' % " ".join(parts))


# ---------------------------------------------------------------- landing page
def three_box(ctx, small=False):
    w, h = 1000, 150
    boxes = [("Pipeline", "Reads, checks, writes", "pipeline.html"), ("Knowledge base", "Values and their evidence", "kb.html"),
             ("Recommendation engine", "Ranks cars for a query", "engine.html")]
    out = []
    for i, (t, s, href) in enumerate(boxes):
        x = 10 + i * 340
        acc = " acc" if i == 1 else ""
        on = " on-acc" if i == 1 else ""
        out.append('<a href="%s" aria-label="%s: %s"><rect class="box%s" x="%d" y="20" width="300" height="110" rx="16"/>'
                   '<text class="%s" x="%d" y="70" text-anchor="middle" font-size="22" font-weight="750">%s</text>'
                   '<text class="%s" x="%d" y="102" text-anchor="middle" font-size="17">%s</text></a>'
                   % (href, E(t), E(s), acc, x, on.strip(), x + 150, E(t), on.strip() or "t2", x + 150, E(s)))
        if i < 2:
            out.append(arrow_h(x + 306, x + 334, 75))
    return ('<svg viewBox="0 0 %d %d" role="img" aria-labelledby="tb-t tb-d"><title id="tb-t">Pipeline, knowledge base, recommendation engine</title>'
            '<desc id="tb-d">The pipeline writes the knowledge base. The recommendation engine reads it.</desc>%s</svg>' % (w, h, "".join(out)))


def page_index(D, ctx):
    g, P, T, E_, H = D["glance"], D["pipeline"], D["trust"], D["engine"], D["honest"]
    wr = sum(1 for r in D["history"] if r["wrote"])
    fetch = P.get("fetch") or {}
    pages_read = (fetch.get("network", 0) + fetch.get("cache", 0)) if fetch else None
    gates = P.get("gates") or {}
    cl, tot = g["classes"], g["values"] or 1
    cards = []

    def facts(items):
        return '<dl class="facts sm">%s</dl>' % "".join('<div><dt>%s</dt><dd>%s</dd></div>' % (E(l), E(v)) for v, l in items)
    B = H.get("backlog")
    cards.append(('pipeline.html', "The pipeline",
                  "A scripted run that reads two car sites and manufacturer brochures, links what they say to each variant, and writes new variants and blanks that pass four checks. "
                  "Changes to values already stored wait for the owner.",
                  facts([(fmt(wr), "runs applied to the knowledge base"), (fmt(pages_read), "pages read in the latest run"),
                         (fmt(B["cells_still_pending"]) if B else "n/a", "proposed changes not applied")]),
                  "Walk through the pipeline"))
    o = T["overall"] if T else None
    cards.append(('kb.html', "The knowledge base",
                  "A database of new cars sold in India. Each stored value is shown with the strongest evidence behind it, and some rest only on an import with no recorded source.",
                  facts([(pct(cl["brochure"] / tot), "of values backed by a brochure page"), (pct(cl["import"] / tot), "of values with only the June 2026 import"),
                         ("%s of %s" % (fmt(o["match"]), fmt(o["n"])) if o else "n/a", "sampled values confirmed by a second check")]),
                  "See what it holds"))
    if E_.get("found") and E_.get("v3_main"):
        v = E_["v3_main"]
        eng = facts([(fmt(v["n_queries"]), "test queries, written by the project's author"), ("%s of %s" % (fmt(v["zero_viol"]), fmt(v["with_cars"])), "answers met every stated requirement, counting blank values as met"),
                     ("%.2f" % v["recall8"] if v.get("recall8") is not None else "n/a", "recall@8, 40 queries labelled by one person")])
    else:
        eng = '<p class="empty">Recommender data not found when this page was generated.</p>'
    cards.append(('engine.html', "The recommendation engine",
                  "Turns a plain-language request into a ranked list. A feature that is blank for a car does not rule it out, and the card says the value is unknown.",
                  eng, "See how it ranks"))
    cs = "".join('<a class="card pcard" href="%s"><h2>%s</h2><p>%s</p>%s<span class="go">%s &rarr;</span></a>' % (h, E(t), E(p), f, E(b)) for h, t, p, f, b in cards)
    P_ = H["price"]
    lede = ("CarRec recommends new cars sold in India from a knowledge base of %s variants. The strongest evidence for %s of the stored values is the June 2026 import, which recorded no source, "
            "and %s of %s variants have no price evidence newer than that import. A pipeline builds and updates the knowledge base, and a recommendation engine ranks cars from it. Each part has its own page."
            % (fmt(g["variants"]), pct(cl["import"] / tot), fmt(P_["import_only"]), fmt(P_["n"])))
    body = (page_head("CarRec", lede, ctx)
            + '<section class="section"><div class="wrap"><div class="panel" style="padding:24px 16px">%s</div></div></section>' % three_box(ctx)
            + '<section class="section"><div class="wrap"><div class="grid g3">%s</div>%s</div></section>'
            % (cs, '<p class="note">Figures: pipeline run records (run %s), the knowledge base snapshot, the audit run %s and the recommender evaluation files.</p>'
               % (E(P.get("run") or "n/a"), E(T["run"] if T else "n/a")))
            + section("evidence", "How well the stored values are backed", "", '<p class="plain">%s</p><div style="margin-top:var(--s2)">%s</div>'
                      '<div class="legend" style="margin-top:12px">%s</div><p class="note"><a href="kb.html#evidence">Breakdown, price age and known gaps on the knowledge base page</a></p>%s'
                      % (E(evidence_sentence(g)), evidence_bar(g),
                         "".join('<span><i class="sw %s"></i>%s %s</span>' % (EV_CLS[k], E(EV_LABEL[k]), pct(cl[k] / tot)) for k in EV_ORDER),
                         src("live evidence rows by source for every stored value, knowledge base snapshot")))
            + '<section class="section"><div class="wrap"><div class="notice"><strong>What &ldquo;verified&rdquo; means here.</strong> %s</div></div></section>' % E(verified_sentence(T)))
    return shell("index.html", "CarRec overview", body, ctx, "CarRec: a car knowledge base, the pipeline that maintains it and the engine that reads it, with the evidence behind each stated.")


# ---------------------------------------------------------------- pipeline page
STAGES = [("sources", "Sources"), ("discover", "Discover"), ("extract", "Extract"), ("link", "Link variants"), ("reconcile", "Reconcile"),
          ("gates", "Gates"), ("kb", "Knowledge base"), ("verify", "Verify")]


def overview_svg():
    n, bw, gap, h = len(STAGES), 128, 25, 120
    out = []
    for i, (sid, name) in enumerate(STAGES):
        x = i * (bw + gap)
        kbn = sid == "kb"
        words = name.split(" ")
        lines = words if len(words) > 1 else [name]
        cls = "box acc" if kbn else "box"
        tc = "on-acc" if kbn else ""
        ty = 62 if len(lines) == 1 else 54
        t = "".join('<text class="%s" x="%d" y="%d" text-anchor="middle" font-size="21" font-weight="750">%s</text>' % (tc, x + bw // 2, ty + 25 * j, E(l)) for j, l in enumerate(lines))
        out.append('<a href="#s-%s" aria-label="Stage %d: %s"><rect class="%s" x="%d" y="8" width="%d" height="104" rx="14"/>'
                   '<text class="%s" x="%d" y="34" text-anchor="middle" font-size="15" font-weight="700" opacity=".75">%d</text>%s</a>'
                   % (sid, i + 1, E(name), cls, x, bw, tc or "t3", x + bw // 2, i + 1, t))
        if i < n - 1:
            out.append(arrow_h(x + bw + 3, x + bw + gap - 2, 60))
    wide = ('<svg class="ov-wide" viewBox="-3 0 %d %d" role="img" aria-labelledby="ov-t ov-d"><title id="ov-t">Pipeline overview, eight stages in order</title>'
            '<desc id="ov-d">Sources, Discover, Extract, Link variants, Reconcile, Gates, Knowledge base, Verify. Each box links to its section below.</desc>%s</svg>'
            % (n * (bw + gap) - gap + 6, h, "".join(out)))
    # tall version for phones
    bh, g2, W = 54, 20, 320
    out2 = []
    for i, (sid, name) in enumerate(STAGES):
        y = 4 + i * (bh + g2)
        kbn = sid == "kb"
        out2.append('<a href="#s-%s" aria-label="Stage %d: %s"><rect class="%s" x="4" y="%d" width="%d" height="%d" rx="12"/>'
                    '<text class="%s" x="30" y="%d" text-anchor="middle" font-size="16" font-weight="700" opacity=".75">%d</text>'
                    '<text class="%s" x="52" y="%d" font-size="22" font-weight="750">%s</text></a>'
                    % (sid, i + 1, E(name), "box acc" if kbn else "box", y, W - 8, bh, "on-acc" if kbn else "t3", y + 33, i + 1,
                       "on-acc" if kbn else "", y + 34, E(name)))
        if i < len(STAGES) - 1:
            out2.append(arrow_v(W // 2, y + bh + 2, y + bh + g2 - 1))
    tall = ('<svg class="ov-tall" viewBox="0 0 %d %d" role="img" aria-label="Pipeline overview, eight stages in order, top to bottom">%s</svg>'
            % (W, 8 + len(STAGES) * (bh + g2), "".join(out2)))
    return wide + tall


def stage_block(i, sid, name, what, why, body, nums):
    nh = "".join('<div><b>%s</b><span>%s</span><em>%s</em></div>' % (E(v), E(l), E(s)) for v, l, s in nums if v is not None)
    return ('<section class="stage" id="s-%s" aria-labelledby="h-s-%s"><div class="wrap"><div class="stage-head"><span class="stage-n" aria-hidden="true">%d</span>'
            '<h2 id="h-s-%s">%s</h2></div><p class="what">%s</p><p class="why">%s</p><div class="stage-body"><div>%s</div><div class="nums" aria-label="Numbers from the latest run">%s</div></div></div></section>'
            % (sid, sid, i, sid, E(name), E(what), E(why), body, nh))


def kvlist(pairs):
    return '<dl class="kv">%s</dl>' % "".join("<dt>%s</dt><dd>%s</dd>" % (E(k), v) for k, v in pairs)


SOURCE_GIVES = {"oem": "Manufacturer brochure PDFs, read page by page", "carwale": "Specs and prices per version; owner ratings and reviews",
                "cardekho": "Specs and prices per variant", "91wheels": "Specs (earlier ingestion)", "v3cars": "Specs (earlier ingestion)",
                "v6_migration": "June 2026 import; no web address recorded", "bharat_ncap": "Crash-test results", "global_ncap": "Crash-test results"}


def page_pipeline(D, ctx):
    P, T, run = D["pipeline"], D["trust"], D["pipeline"].get("run")
    runlab = "run " + str(run)
    st, fetch, disc = P.get("stats") or {}, P.get("fetch") or {}, P.get("discovery") or {}
    blocks = []
    # 1 sources
    SRC_LABEL = {"oem": "OEM brochures", "carwale": "CarWale", "cardekho": "CarDekho", "91wheels": "91wheels", "v3cars": "v3cars", "v6_migration": "June 2026 import",
             "bharat_ncap": "Bharat NCAP", "global_ncap": "Global NCAP"}
    rows_ = "".join('<tr><td>%s</td><td>%s</td><td class="n">%s</td><td class="n">%s</td></tr>'
                    % (E(SRC_LABEL.get(s["name"], s["name"])), E(SOURCE_GIVES.get(s["name"]) or ("Expert scores and notes" if "Autocar" in s["name"] else "Owner ratings" if "user ratings" in s["name"] else s["type"].replace("_", " ").capitalize())),
                       E(s["tier"]), fmt(s["observations"])) for s in D["per_source"])
    b = ('<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Source</th><th>What it supplies</th><th class="n">Authority tier</th><th class="n">Rows stored</th></tr></thead><tbody>%s</tbody></table></div>'
         '<p class="note">Tier 1 outranks tier 2, and tier 2 outranks tier 3. A brochure outranks the two car sites. Every page read is stored as an observation with its address and time.</p>%s' % (rows_, src("source table; rows are page observations plus review, owner and crash-test rows citing the source, knowledge base snapshot")))
    obs_total = D["entities"].get("source_observation")
    blocks.append(stage_block(1, "sources", "Sources", "Say where each value may come from, and rank the places.",
                              "Car sites disagree and brochures are the manufacturer's own word. Ranking the sources in advance means a conflict is settled by a rule, not by whichever page was read last.", b,
                              [(fmt(obs_total), "page and brochure observations stored", "knowledge base snapshot"), (fmt(len(D["per_source"])), "sources registered", "knowledge base snapshot"),
                               (fmt(sum(s["observations"] for s in D["per_source"] if s["name"] == "oem")), "observations taken from brochures", "knowledge base snapshot")]))
    # 2 discover
    lab = {"EXISTING": "On both sites, already known", "NEW_MODEL": "New model", "NOT_ON_SALE": "Not on sale", "UPCOMING": "Upcoming",
           "OUT_OF_SCOPE": "Out of scope by price", "ONE_SITE_ONLY": "Listed on one site only", "REVIEW_MODEL": "Needs a human look", "DISCONTINUED_CANDIDATE": "Possibly discontinued"}
    mx = max(disc.values()) if disc else 1
    b = ('<div class="ex"><h3 class="lbl">How %s sorted every model it saw on the two sites</h3>%s</div>%s'
         % (E(runlab), "".join(bar_row(lab.get(k, k), v / mx, fmt(v)) for k, v in sorted(disc.items(), key=lambda kv: -kv[1])), src("discovery counts, " + runlab)))
    blocks.append(stage_block(2, "discover", "Discover", "Find out what is new, changed or gone before reading any page in detail.",
                              "A full read of every model is slow, and each site is limited to one request every few seconds. Sorting the listing first means an incremental run only touches models whose listing changed.", b,
                              [(fmt(disc.get("NEW_MODEL")), "new models found", runlab), (fmt(P.get("processed")), "models processed", runlab), (fmt(disc.get("OUT_OF_SCOPE")), "left out by the price ceiling", runlab)]))
    # 3 extract
    pv = P.get("provenance")
    ex = ""
    if pv:
        cards = []
        for e in pv["evidence"]:
            if e["snippet"] and e["source"] in ("carwale", "cardekho"):
                cards.append('<div class="card"><h3 class="lbl">%s page</h3>%s</div>' % (E("CarWale" if e["source"] == "carwale" else "CarDekho"),
                             kvlist([("Address", E(shorturl(e["source_url"]))), ("Key on page", E(e["snippet"][0])), ("Value on page", E(e["snippet"][1])),
                                     ("Method", E(re.sub(r"^kbpipe/[\d.]+ ", "", e["extraction_method"] or "")))])))
        if cards:
            ex = ('<div class="ex"><h3 class="lbl">Real case: %s, field <span class="mono">%s</span></h3><div class="grid g2">%s</div><p class="note">Both pages carry the figure in structured data embedded in the page, so it is read as data. No language model is involved in reading specs.</p></div>'
                  % (E(pv["variant"]), E(pv["field"]), "".join(cards[:2])))
    if not ex:
        ex = '<p class="empty">No extraction example could be built from this snapshot.</p>'
    blocks.append(stage_block(3, "extract", "Extract", "Read each page's embedded data and keep every value with its address, time and method.",
                              "Reading structured data is repeatable: the same page gives the same value. A value without an address cannot be checked later, and the June 2026 import has none.", ex + src("knowledge base snapshot, observation payloads for the variant shown"),
                              [(fmt((fetch.get("network") or 0) + (fetch.get("cache") or 0)) if fetch else None, "pages read", "%s (%s fetched, %s from cache)" % (runlab, fmt(fetch.get("network")), fmt(fetch.get("cache")))),
                               (fmt(fetch.get("failed")) if fetch else None, "page fetches that failed", runlab),
                               ("%.1f MB" % (fetch["bytes"] / 1e6) if fetch.get("bytes") else None, "downloaded", runlab)]))
    # 4 link
    ok, no = P.get("link_ok"), P.get("link_refused")
    lb = ""
    if ok:
        lb += ('<div class="ex"><h3 class="lbl">Linked</h3><div class="pair"><div class="card"><span class="chip">CarWale</span><p><b>%s</b></p>%s</div><div class="mid">same variant</div>'
               '<div class="card"><span class="chip">CarDekho</span><p><b>%s</b></p>%s</div></div>'
               '<div class="card"><p>Knowledge base variant: <b>%s %s %s</b></p><ul class="checks"><li><span class="chip ok">equal</span>Fuel: %s and %s</li>'
               '<li><span class="chip ok">equal</span>Gearbox class: %s and %s</li><li><span class="chip ok">%.2f%%</span>Price gap: %s and %s (limit %s%%)</li></ul></div></div>'
               % (E(ok["carwale"]), kvlist([("Price", E(rupees(ok["carwale_price"]))), ("Fuel", E(ok["carwale_fuel"])), ("Gearbox", E(ok["carwale_gearbox"]))]),
                  E(ok["cardekho"]), kvlist([("Price", E(rupees(ok["cardekho_price"]))), ("Fuel", E(ok["cardekho_fuel"])), ("Gearbox", E(ok["cardekho_gearbox"]))]),
                  E(ok["make"]), E(ok["model"]), E(ok["kb_variant"]), E(ok["carwale_fuel"]), E(ok["cardekho_fuel"]), E(ok["carwale_gearbox"]), E(ok["cardekho_gearbox"]),
                  ok["diff"] * 100, E(rupees(ok["carwale_price"])), E(rupees(ok["cardekho_price"])), "%g" % (config.DEFAULTS["link_price_tolerance"] * 100)))
    if no:
        lb += ('<div class="ex" style="margin-top:24px"><h3 class="lbl">Refused</h3><div class="card"><span class="chip no">not linked</span><p><b>%s %s</b>, CarWale version <b>%s</b> (%s)</p>'
               '<p class="note" style="margin-top:8px">Link log reason: &ldquo;%s&rdquo;. CarDekho has no variant with the same fuel, gearbox and trim words, so nothing from this listing was added. A guess would put another variant&rsquo;s numbers on this car.</p></div></div>'
               % (E(no["make"]), E(no["model"]), E(no["carwale"]), E(rupees(no["carwale_price"])), E(no["site_link_reason"])))
    if not lb:
        lb = '<p class="empty">No link examples in the run record.</p>'
    rs = P.get("link_reasons") or {}
    blocks.append(stage_block(4, "link", "Link variants", "Decide which CarWale version, which CarDekho variant and which knowledge base variant are the same car.",
                              "Both sites name trims differently. A wrong link would put one car's numbers on another, so a link needs equal fuel, gearbox class and trim words, and prices within %s%%." % ("%g" % (config.DEFAULTS["link_price_tolerance"] * 100)),
                              lb + src("links log, " + runlab),
                              [(fmt(st.get("variants_matched")), "variants linked across both sites and the knowledge base", runlab), (fmt(st.get("variants_not_added")), "versions not added (one site only, or identities differ)", runlab),
                               (fmt(rs.get("no candidate with the same identity")), "CarWale versions with no CarDekho candidate of the same identity", runlab)]))
    # 5 reconcile
    ce, ce2 = P.get("conflict_ex"), P.get("conflict_ex2")
    ladder = ('<svg viewBox="0 0 520 190" role="img" aria-labelledby="lad-t"><title id="lad-t">Which source wins</title>'
              '<rect class="box acc" x="4" y="4" width="512" height="48" rx="12"/><text class="on-acc" x="22" y="34" font-size="18" font-weight="700">1  OEM brochure value: decides</text>'
              '<rect class="box" x="4" y="64" width="512" height="48" rx="12"/><text x="22" y="94" font-size="18" font-weight="700">2  Two sites agree: may fill a blank or confirm</text>'
              '<rect class="box dash" x="4" y="124" width="512" height="48" rx="12"/><text x="22" y="154" font-size="18" font-weight="700">3  One site alone: decides nothing, cell stays blank</text></svg>')
    cx = ""
    if ce:
        cx += ('<div class="card"><span class="chip hold">not written</span><p style="margin-top:8px"><b>%s %s %s</b>, field <b>%s</b></p>%s<p class="note">The two sites state different values, so this run writes neither. The knowledge base keeps what it already holds and the disagreement is listed for review.</p></div>'
               % (E(ce["make"]), E(ce["model"]), E(ce["variant"]), E(ce["field"].replace("_", " ")), kvlist([("Values", E(ce["values"])), ("Knowledge base holds", E(ce["kb_value"] or "blank")), ("Logged resolution", E(ce["resolution"]))])))
    if ce2:
        cx += ('<div class="card"><span class="chip ok">resolved</span><p style="margin-top:8px"><b>%s %s %s</b>, field <b>%s</b></p>%s<p class="note">Both sites agree on the meaning; one label is only less specific. The specific label is kept.</p></div>'
               % (E(ce2["make"]), E(ce2["model"]), E(ce2["variant"]), E(ce2["field"].replace("_", " ")), kvlist([("Values", E(ce2["values"])), ("Logged resolution", E(ce2["resolution"]))])))
    b = '<div class="grid g2" style="align-items:start"><div class="ex"><h3 class="lbl">The rule</h3>%s</div><div class="ex"><h3 class="lbl">Two logged cases</h3>%s</div></div>%s' % (ladder, cx or '<p class="empty">No conflict log.</p>', src("conflict log and run record, " + runlab))
    blocks.append(stage_block(5, "reconcile", "Reconcile", "Compare what the sources say and apply the ranking.",
                              "One source can be wrong or stale. Requiring two to agree, or a brochure to decide, means a single page cannot change a value by itself. Two sites can still be wrong together.", b,
                              [(fmt(P.get("conflicts_total")), "disagreements logged", runlab + ", %s of them high-impact" % fmt(st.get("high_conflicts"))), (fmt(st.get("cells_confirmed")), "existing cells confirmed by both sites", runlab),
                               (fmt(st.get("cells_null_SINGLE_SOURCE")), "cells left blank because only one site had a value", runlab)]))
    # 6 gates
    gl = {"schema": ("Schema intact", "The database structure is unchanged and the integrity check passes."), "provenance": ("Every new value has provenance", "Each new or changed value has at least one evidence row."),
          "rows": ("No rows lost", "No table ends with fewer rows than it started with."), "explained": ("Every change explained", "Each changed row appears in the run log."),
          "reviews": ("Review rows have provenance", "Added when a run writes review scores.")}
    tiles = ""
    for k in ["schema", "provenance", "rows", "explained"]:
        gv = (P.get("gates") or {}).get(k)
        if not gv:
            continue
        det = gv["detail"][0] if k != "rows" else "%d tables compared, none shrank" % len(gv["detail"])
        tiles += '<div class="gate"><h3>%s <span class="chip %s">%s</span></h3><p>%s</p><p class="src">%s</p></div>' % (E(gl[k][0]), "ok" if gv["ok"] else "no", "pass" if gv["ok"] else "fail", E(gl[k][1]), E(det))
    lay = P.get("layers")
    extra = ""
    if lay and lay.get("gate"):
        extra = '<p class="note">Runs that write review scores add a fifth gate, &ldquo;%s&rdquo;: %s (%s).</p>' % (E(gl["reviews"][0]), E(lay["gate"]["detail"][0]), E(lay["run"]))
    b = '<div class="gates">%s</div>%s<p class="note">After the four gates pass, the same run is applied again to the result. It must change nothing. If any gate fails, nothing reaches the knowledge base.</p>%s' % (tiles or '<p class="empty">No gate record.</p>', extra, src("gate record, " + runlab))
    gvals = P.get("gates") or {}
    blocks.append(stage_block(6, "gates", "Gates", "Run four scripted checks on a staging copy before anything touches the real database.",
                              "The gates are scripted checks of form: structure, row counts, an evidence row for each new value and a log entry for each change. They do not test whether a value is right; the sample re-check in the last stage does that for a small share.", b,
                              [("%d of %d" % (sum(1 for v in gvals.values() if v.get("ok")), len(gvals)) if gvals else None, "gates passed", runlab), (fmt(P.get("ops")), "operations staged on the copy", runlab),
                               ("0 changes" if P.get("idempotent") else None, "made by the second, identical run", runlab)]))
    # 7 kb
    w = P.get("write") or {}
    b = ('<ol class="steps"><li>Check that no other process holds the database file.</li><li>Record the file hash.</li><li>Take a backup.</li><li>Write all changes in one transaction.</li>'
         '<li>Run the database integrity check.</li><li>Compare the result table by table with the staging copy.</li></ol>'
         '<p class="note">Rows are never deleted. A model or variant that is no longer listed is only flagged for review. %s</p>%s'
         % ("The latest run's result matched its staging copy exactly." if w.get("prod_equals_staging") else "", src("write record, " + runlab)))
    blocks.append(stage_block(7, "kb", "Knowledge base", "Write the staged changes in one transaction, after a backup.",
                              "If anything fails halfway the transaction rolls back, and the backup makes the last good state recoverable.", b,
                              [(fmt(w.get("rows")), "rows written", runlab), ("Passed" if w.get("integrity_check") == "ok" else E(w.get("integrity_check")) if w else None, "database integrity check result", runlab), (fmt(P.get("review_items")), "items left for a human decision", runlab)]))
    # 8 verify
    vo, vb = P.get("verify_ok"), P.get("verify_bad")

    def vcard(x, kind):
        if not x:
            return ""
        return ('<div class="card"><span class="chip %s">%s</span><p style="margin-top:8px"><b>%s</b>, %s</p>%s</div>'
                % ("ok" if kind == "ok" else "no", "supported" if kind == "ok" else "mismatch", E(x["car"]), E(x["field"].replace("_", " ")),
                   kvlist([("Knowledge base value", E(x["kb_value"])), ("Source says", E(x["source_value"])), ("Evidence text", E(trim_text(x["evidence"], 80))),
                           ("Source", E(brochure_ref(x["source_ref"]) if x["source_class"] == "brochure" else shorturl(x["source_ref"])))])))
    pl = D["honest"]["planted"]
    cfg_llm = config.DEFAULTS.get("llm", {})
    bk = cfg_llm.get("backends", {})
    same = False
    try:
        same = bk[cfg_llm["brochure_read"][0]]["kind"] == bk[cfg_llm["brochure_check"][0]]["kind"]
    except (KeyError, IndexError):
        pass
    plnote = ""
    if pl:
        plnote = (" Control test: wrong values were planted in the sample to see whether the checker flags them. %s."
                  % "; ".join("run %s: %s of %s flagged%s" % (x["name"], fmt(x["caught"]), fmt(x["n"]), (", %s returned a checker error and prove nothing" % fmt(x["error"])) if x["error"] else "") for x in pl))
    b = ('<div class="grid g2" style="align-items:start">%s%s</div><p class="note">Any difference counts as a mismatch, however small. Cells the checker could not reach are reported separately and are not counted as matches. '
         'The checker is a model, not a person%s.%s For old values it re-reads today&rsquo;s page, not the page the value came from.</p>%s'
         % (vcard(vo, "ok"), vcard(vb, "bad"), "; for brochures the reader and the first-choice checker are from the same maker, so they may share mistakes" if same else "",
            E(plnote), src("verification results, audit run %s" % (T["run"] if T else "n/a"))))
    if not (vo or vb):
        b = '<p class="empty">No verification results in the run folders.</p>'
    ov = T["overall"] if T else None
    blocks.append(stage_block(8, "verify", "Verify", "Have a second model re-read the source for a sample of stored values.",
                              "The model that extracted a value should not grade it, so a separate checker re-reads the page or brochure page and says whether the source supports the value. Only a sample is checked.", b,
                              [(fmt(T["n"]) if T else None, "cells re-checked", "audit run %s" % (T["run"] if T else "")), (pct(ov["accuracy"]) if ov else None, "match rate among decided cells (%s of %s)" % (fmt(ov["match"]), fmt(ov["match"] + ov["mismatch"])) if ov else "", "audit run; %s unreachable" % fmt(ov["unreachable"]) if ov else ""),
                               (pct(T["by_class"]["aggregator"]["accuracy"]) if T and "aggregator" in T["by_class"] else None, "match rate, values both sites agreed on", "audit run")]))
    # refuses
    wr = (D["honest"].get("backlog") or {})
    ua = config.DEFAULTS.get("user_agent", "")
    ref = ('<div class="refuse"><div><h3>One source alone decides nothing</h3><p>If only one site states a value and no brochure does, the cell stays blank and the reason is listed.</p></div>'
           '<div><h3>Rows are not deleted</h3><p>Rows are added or amended. A car that disappears from a listing is flagged for a human, not removed: %s variants are flagged this way and %s are marked discontinued.</p></div>'
           '<div><h3>No write without a backup and gates</h3><p>Every write follows the sequence above: staging copy, four gates, an identical re-run that changes nothing, backup, then one transaction.</p></div>'
           '<div><h3>A refusal is recorded, not retried</h3><p>When a review page refuses a request, the pipeline records the block and moves on. Gap: spec pages are fetched %swithout checking the site&rsquo;s robots.txt.</p></div></div>'
           % (fmt(wr.get("unlisted_ops")) if wr else "n/a", fmt(wr.get("marked_discontinued")) if wr else "n/a", "under a desktop-browser identity and " if ua.startswith("Mozilla") else ""))
    # evidence layers
    ly = P.get("layers") or {}
    txt, num = (ly.get("text") or {}), (ly.get("numbers") or {})
    ac, cw = txt.get("autocar") or {}, txt.get("carwale") or {}
    lanes = [("Specifications", "Two car sites and OEM brochures", "Structured page data, no language model. Brochures read page by page.",
              "Two sites must agree, or a brochure decides. A different model re-reads a random sample%s." % ((": %s of %s decided cells matched" % (fmt(ov["match"]), fmt(ov["match"] + ov["mismatch"]))) if ov else "")),
             ("Professional scores and notes", "Autocar India", "Scores read as page data. Notes written by one language model.",
              "A different model checks each note: %s of %s accepted%s." % (fmt(ac.get("ok")), fmt(ac.get("verified")), ("; scores re-read: %s of %s" % (fmt((num.get("autocar") or {}).get("ok")), fmt((num.get("autocar") or {}).get("checked")))) if num.get("autocar") else "")),
             ("Owner ratings and themes", "CarWale", "Ratings read as page data. Themes written by one model from a sample of reviews.",
              "A different model checks each theme: %s of %s accepted%s." % (fmt(cw.get("ok")), fmt(cw.get("verified")), ("; figures re-read: %s of %s" % (fmt((num.get("carwale") or {}).get("ok")), fmt((num.get("carwale") or {}).get("checked")))) if num.get("carwale") else ""))]

    def wrap(s, n):
        words, lines, cur = s.split(), [], ""
        for w_ in words:
            if len(cur) + len(w_) + 1 > n and cur:
                lines.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        return lines + [cur] if cur else lines
    parts = []
    for i, (name, a, b_, c_) in enumerate(lanes):
        y = 12 + i * 122
        for j, (x, w_, head, t) in enumerate([(0, 300, name, a), (340, 340, "Extracted how", b_), (720, 380, "Checked how", c_)]):
            lines = wrap(t, int(w_ / 8.2))[:5]
            parts.append('<rect class="box%s" x="%d" y="%d" width="%d" height="104" rx="12"/><text x="%d" y="%d" font-size="15" font-weight="750">%s</text>%s'
                         % (" soft" if j == 0 else "", x + 2, y, w_, x + 16, y + 28, E(head), "".join('<text class="t2" x="%d" y="%d" font-size="14">%s</text>' % (x + 16, y + 54 + 20 * k, E(l)) for k, l in enumerate(lines))))
        parts.append(arrow_h(304, 338, y + 52) + arrow_h(684, 718, y + 52))
    layers = ('<div class="scroll" tabindex="0" role="region" aria-label="Evidence layers diagram, scrolls sideways on narrow screens"><svg viewBox="0 0 1104 372" style="min-width:880px" role="img" aria-labelledby="ly-t">'
              '<title id="ly-t">The three evidence layers: where they come from, how they are extracted, how they are checked</title>%s</svg></div>' % "".join(parts))
    layers += src("run record of the latest review run that wrote text (%s), audit run %s" % (ly.get("run", "n/a"), T["run"] if T else "n/a"))
    # history
    hist = D["history"]

    def hrow(r):
        return '<tr><td>%s</td><td style="white-space:nowrap">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (E(r["name"]), E(r["date"]), E(r["kind"]), E(r["changed"]), E(r["gates"]))
    applied = [r for r in hist if r["wrote"]]
    dry = [r for r in hist if not r["wrote"]]
    th = "<thead><tr><th>Run</th><th>Date</th><th>Kind</th><th>What changed</th><th>Gates</th></tr></thead>"
    ht = ('<h3>Applied to the knowledge base</h3><div class="tbl-wrap" style="margin-top:8px"><table class="tbl" style="min-width:760px">%s<tbody>%s</tbody></table></div>' % (th, "".join(hrow(r) for r in applied)))
    if dry:
        ht += ('<details style="margin-top:24px"><summary><b>Dry runs and pilots (%d)</b>: staged and gated, the knowledge base was not touched</summary><div class="tbl-wrap" style="margin-top:8px"><table class="tbl" style="min-width:760px">%s<tbody>%s</tbody></table></div></details>'
               % (len(dry), th, "".join(hrow(r) for r in dry)))
    ht += src("run records, one folder per run")
    body = (page_head("The pipeline", "How the knowledge base is built and updated: eight stages, each with one case from the data and numbers from the latest run. New variants and blanks are written automatically after two sites agree; changes to stored values wait for the owner.", ctx)
            + '<section class="section"><div class="wrap"><div class="panel" style="padding:24px 16px 16px">%s</div>'
              '<p class="note">Select a stage to jump to it. Numbers in each section come from %s unless another run is named.</p></div></section>' % (overview_svg(), E(runlab))
            + "".join(blocks)
            + section("refuses", "What it is built to refuse", "Four rules in the code, and the gaps beside them.", ref)
            + section("layers", "The three evidence layers", "Specifications, professional opinion and owner opinion are stored apart and checked differently.", layers)
            + section("history", "Run history", "Every run leaves a folder with its record. Dates are run start dates.", ht))
    return shell("pipeline.html", "CarRec pipeline", body, ctx, "How the CarRec knowledge base is built and updated: eight stages, four gates and a sampled re-check.")


# ---------------------------------------------------------------- knowledge base page
ENTITY_GROUPS = [
    ("Catalogue", [("manufacturer", "make"), ("model", "refers to manufacturer"), ("generation", "refers to model"), ("variant", "refers to model, powertrain"),
                   ("powertrain", "engine, shared by variants"), ("warranty", "refers to manufacturer or model")]),
    ("Evidence and provenance", [("source", "where a value may come from"), ("source_observation", "one page read, with address and time"),
                                 ("field_provenance", "value, variant, observation, decision"), ("evidence_quarantine", "evidence set aside, never deleted"),
                                 ("evidence_amendment", "log of in-place fixes")]),
    ("Safety", [("safety_test", "one crash test, with its source"), ("safety_test_applicability", "which models a test applies to"), ("safety_rating", "earlier star ratings")]),
    ("Reviews", [("professional_assessment", "expert score and note per aspect"), ("owner_rating", "owner score per aspect"), ("owner_theme", "what owners mention, with counts")]),
]


def entity_svg(counts):
    colw, gap, bh, bg = 300, 14, 62, 10
    out = []
    maxn = max(len(g[1]) for g in ENTITY_GROUPS)
    H = 44 + maxn * (bh + bg)
    for gi, (gname, tabs) in enumerate(ENTITY_GROUPS):
        x = gi * (colw + gap)
        out.append('<text x="%d" y="24" font-size="17" font-weight="750">%s</text><line x1="%d" y1="34" x2="%d" y2="34" stroke="var(--line-strong)" stroke-width="2"/>' % (x + 2, E(gname), x + 2, x + colw))
        for i, (t, cap) in enumerate(tabs):
            y = 44 + i * (bh + bg)
            n = counts.get(t)
            out.append('<g><title>%s: %s rows. %s</title><rect class="box%s" x="%d" y="%d" width="%d" height="%d" rx="10"/>'
                       '<text x="%d" y="%d" font-size="14" font-weight="700" class="mono">%s</text><text x="%d" y="%d" font-size="15" font-weight="750" text-anchor="end">%s</text>'
                       '<text class="t2" x="%d" y="%d" font-size="13">%s</text></g>'
                       % (E(t), fmt(n), E(cap), " soft" if gi == 1 and t in ("field_provenance",) else "", x, y, colw, bh, x + 12, y + 25, E(t), x + colw - 12, y + 25,
                          fmt(n) if n is not None else "n/a", x + 12, y + 47, E(cap)))
    W = 4 * colw + 3 * gap
    return ('<svg viewBox="0 0 %d %d" style="min-width:960px" role="img" aria-labelledby="en-t en-d"><title id="en-t">Knowledge base tables in four groups, with row counts</title>'
            '<desc id="en-d">Catalogue, evidence and provenance, safety, and reviews. Each box names a table, its row count and what it refers to.</desc>%s</svg>' % (W, H, "".join(out)))


def hist_svg(points, step, scale_label, vmin_hint=None):
    vals = [p[1] for p in points]
    if not vals:
        return '<p class="empty">No scores.</p>'
    lo = math.floor(min(vals) / step) * step
    hi = math.floor(max(vals) / step) * step
    bins = []
    v = lo
    while v <= hi + 1e-9:
        bins.append(v)
        v += step
    cnt = {b: 0 for b in bins}
    for x in vals:
        cnt[lo + math.floor((x - lo) / step + 1e-9) * step] += 1
    mx = max(cnt.values()) or 1
    W, H, pad = 420, 190, 30
    bw = (W - 2 * pad) / len(bins)
    out = []
    for i, b in enumerate(bins):
        h = (H - 60) * cnt[b] / mx
        x = pad + i * bw
        out.append('<g><title>%s to %s: %d models</title><rect class="bar-m" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="var(--accent)"/>'
                   '<text x="%.1f" y="%.1f" font-size="13" text-anchor="middle" font-weight="650">%d</text><text class="t3" x="%.1f" y="%d" font-size="12" text-anchor="middle">%s</text></g>'
                   % (("%g" % b), ("%g" % (b + step)), cnt[b], x + 3, H - 30 - h, bw - 6, h, x + bw / 2, H - 34 - h, cnt[b], x + bw / 2, H - 12, ("%g" % b)))
    return ('<svg viewBox="0 0 %d %d" role="img" aria-label="Histogram of %s"><title>Histogram of %s</title>%s'
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(--line-strong)"/></svg>' % (W, H, E(scale_label), E(scale_label), "".join(out), pad, H - 30, W - pad, H - 30))


def trust_blocks(T, per_run):
    if not T:
        return '<p class="empty">No verification results were found in the run folders.</p>'
    legend = ('<div class="legend"><span><i class="sw m"></i>Source supports the value</span><span><i class="sw bad"></i>Source contradicts it (mismatch)</span>'
              '<span><i class="sw unr"></i>Source could not be reached or no longer states the field</span><span><i class="sw ink"></i>Checker error</span></div>')

    def row(name, sub, c):
        d = c["match"] + c["mismatch"]
        ci = c["ci"]
        return ('<div class="trow"><div class="tl"><b>%s</b><span>%s</span></div><div>%s</div><div class="acc"><b>%s</b><span>%s of %s decided%s</span><span>95%% range %s</span></div></div>'
                % (E(name), E(sub), stackbar([(c["match"], "m", "match"), (c["mismatch"], "bad", "mismatch"), (c["unreachable"], "unr", "unreachable"), (c["verifier_error"], "ink", "checker error")],
                                             "%s: %s match, %s mismatch, %s unreachable" % (name, c["match"], c["mismatch"], c["unreachable"])),
                   pct(c["accuracy"]) if d else "n/a", fmt(c["match"]), fmt(d), (", %s mismatch" % fmt(c["mismatch"])) + ((", %s unreachable" % fmt(c["unreachable"])) if c["unreachable"] else ""),
                   ("%s to %s" % (pct(ci[0], 0), pct(ci[1], 0))) if ci else "n/a"))
    o = T["overall"]
    h = "<h3>By where the value came from</h3>" + legend + "".join(row(CLASS_LABEL[k], CLASS_EXPLAIN[k], T["by_class"][k]) for k in CLASS_ORDER if k in T["by_class"])
    h += '<div class="sub"><h3>By kind of fact</h3>' + "".join(row(g.capitalize(), "", T["by_group"][g]) for g in T["groups"] if g in T["by_group"]) + "</div>"
    L = T["legacy"]
    sh = L["mismatch_price"] / L["mismatch_total"] if L["mismatch_total"] else 0
    h += ('<div class="sub notice"><strong>Reading the legacy figure.</strong> Legacy values scored %s (%s of %s). %s</div>'
          % (pct(L["all"]["accuracy"]), L["all"]["match"], L["all"]["match"] + L["all"]["mismatch"],
             ("Most mismatches are prices: %d of %d. Legacy prices were checked against today&rsquo;s page, so a mismatch can mean the car&rsquo;s price changed after June, not that the import was wrong. Prices matched %d of %d; without prices, legacy accuracy is %s (%d of %d)."
              % (L["mismatch_price"], L["mismatch_total"], L["price"]["match"], L["price"]["match"] + L["price"]["mismatch"], pct(L["non_price"]["accuracy"]),
                 L["non_price"]["match"], L["non_price"]["match"] + L["non_price"]["mismatch"])) if sh > 0.5 else ""))
    h += ('<div class="notice warn" style="margin-top:16px"><strong>Unreachable is not a match.</strong> %s of the %s sampled cells could not be checked, plus %s checker error(s). They are left out of every accuracy figure. Overall: %s (%s of %s decided; 95%% range %s to %s).</div>'
          % (fmt(o["unreachable"]), fmt(o["n"]), fmt(o["verifier_error"]), pct(o["accuracy"]), fmt(o["match"]), fmt(o["match"] + o["mismatch"]), pct(o["ci"][0], 0), pct(o["ci"][1], 0)))
    if T.get("legacy_cells"):
        h += ('<p class="note">The knowledge base held %s legacy cells, of which %s had a current page to check against. This is a sample of %s cells, stratified by source and kind of fact, not a census.</p>'
              % (fmt(T["legacy_cells"]), fmt(T["legacy_checkable"]), fmt(T["n"])))
    if len(per_run) > 1:
        h += ('<div class="sub"><h3>Every verification sample so far</h3><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Run</th><th class="n">Cells</th><th class="n">Match</th><th class="n">Mismatch</th><th class="n">Unreachable</th><th class="n">Checker errors</th><th class="n">Match rate</th></tr></thead><tbody>%s</tbody></table></div></div>'
              % "".join('<tr><td>%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td></tr>'
                        % (E(r["name"]), fmt(r["n"]), fmt(r["match"]), fmt(r["mismatch"]), fmt(r["unreachable"]), fmt(r["verifier_error"]), pct(r["accuracy"])) for r in per_run))
    return h + src("verification results of run %s (%s), written by the checker and read only here" % (T["run"], T["started"]))


def page_kb(D, ctx):
    g, T, rev, rx = D["glance"], D["trust"], D["reviews"], D["reviews_extra"]
    ent = D["entities"]
    facts = [(g["variants"], "variants"), (g["models"], "models"), (g["makes"], "manufacturers"), (g["powertrains"], "powertrains"), (g["values"], "filled values across %d fields" % g["n_fields"]),
             (g["classes"]["brochure"], "values backed by a brochure page"), (g["classes"]["import"], "values backed only by the June 2026 import"), (ent.get("source_observation"), "page and brochure observations"), (ent.get("field_provenance"), "provenance rows"),
             (ent.get("evidence_quarantine"), "evidence rows set aside (quarantined)"), (g["expert_rows"] + g["owner_rows"], "current review scores"), (ent.get("owner_theme"), "owner theme rows"),
             (ent.get("safety_test"), "crash tests recorded")]
    glance = '<dl class="facts">%s</dl>%s' % ("".join('<div><dt>%s</dt><dd>%s</dd></div>' % (E(l), fmt(v)) for v, l in facts), src("counts from the knowledge base snapshot; values are the non-blank cells of the %d tracked fields" % g["n_fields"]))
    # provenance trace
    pv = D["pipeline"].get("provenance")
    if pv:
        ev = pv["evidence"]
        evl = "".join('<li><b>%s</b> <span class="chip %s">%s</span><br>%s<br><span class="src">%s</span></li>'
                      % (E({"carwale": "CarWale", "cardekho": "CarDekho", "91wheels": "91wheels"}.get(e["source"], e["source"])), "ok" if e["decision"] == "confirmed" else "",
                         E(e["decision"]), E("Value %s" % e["accepted_value"]), E("%s, %s" % (shorturl(e["source_url"]), (e["decided_at"] or "")[:10]))) for e in ev)
        snip = next((e["snippet"] for e in ev if e["snippet"]), None)
        tr = ('<div class="trace"><div class="card"><h3 class="lbl">1. Source page</h3><p>%s</p><p class="note">Page text: %s</p></div>'
              '<div class="card"><h3 class="lbl">2. Observation stored</h3><p>The pipeline stores the page payload with its address, fetch time and method.</p><p class="note">Observation %s, read %s</p></div>'
              '<div class="card"><h3 class="lbl">3. Stored cell</h3><p><b>%s</b></p><div class="big">%s</div><p class="note">%s on variant %s</p></div>'
              '<div class="card"><h3 class="lbl">4. Its evidence rows (%s)</h3><ul>%s</ul></div></div>'
              % (E(shorturl(ev[1]["source_url"] if len(ev) > 1 else ev[0]["source_url"])), E("%s: %s" % snip) if snip else "n/a", fmt(ev[1]["obs"] if len(ev) > 1 else ev[0]["obs"]),
                 E((ev[1]["observed_at"] if len(ev) > 1 else ev[0]["observed_at"])[:10]), E(pv["variant"]), E(pv["stored"]), E(pv["field"].replace("_", " ")), fmt(pv["variant_id"]), fmt(pv["n_evidence"]), evl))
        tr += ('<p class="note">Reading it: this value has %s evidence rows from %s sources. Not every value has a trail this complete: the breakdown above shows how many rest on a single site or only on the import. '
           'If a source were later found wrong, its evidence rows can be set aside without deleting them.</p>' % (fmt(pv["n_evidence"]), fmt(len({e["source"] for e in ev})))) + src("knowledge base snapshot: field_provenance, source_observation and the variant row")
    else:
        tr = '<p class="empty">No example could be traced in this snapshot.</p>'
    # heatmap
    H = D["heat"]
    cells = ""
    for mi, mk in enumerate(H["makes"]):
        allr = mk == "All makes"
        cells += '<tr%s><th scope="row">%s<small>%s variants</small></th>' % (' class="all"' if allr else "", E(mk), fmt(H["n_variants"][mi]))
        for gi, gp in enumerate(H["groups"]):
            p = H["pct"][mi][gi]
            if p is None:
                cells += '<td title="No fields in this group apply">&ndash;</td>'
            else:
                cells += ('<td style="background:color-mix(in srgb,var(--heat-hi) %d%%,var(--heat-lo));color:%s" title="%s, %s: %s of values present">%s</td>'
                          % (round(p * 100), "var(--heat-on-hi)" if p > .55 else "var(--heat-on-lo)", E(mk), E(gp), "%.1f%%" % (p * 100), "%d%%" % round(p * 100)))
        cells += "</tr>"
    heat = ('<div class="panel scroll" tabindex="0" role="region" aria-label="Coverage heatmap, scrolls sideways on narrow screens"><div style="padding:10px"><table class="heat"><thead><tr><th><span class="sr">Manufacturer</span></th>%s</tr></thead><tbody>%s</tbody></table></div></div>'
            '<div class="scale"><span>0%%</span><i aria-hidden="true"></i><span>100%%</span><span>Stronger colour means more complete. Each cell prints its value; hover for the exact figure.</span></div>%s'
            % ("".join("<th>%s</th>" % E(x) for x in H["groups"]), cells, src("variant values read through the quarantine-masked view; efficiency counts a variant once if any efficiency figure is present")))
    # growth
    gr = D["growth"]
    gmax = max([x["variants"] or 0 for x in gr] or [1]) or 1
    rmax = max([x.get("review_rows") or 0 for x in gr] or [1]) or 1
    gv = "".join(bar_row("%s (%s models)" % (x["label"], fmt(x["models"])), (x["variants"] or 0) / gmax, "%s variants" % fmt(x["variants"]), "wide") for x in gr)
    gv2 = "".join(bar_row(x["label"], (x.get("review_rows") or 0) / rmax, fmt(x.get("review_rows") or 0), "wide") for x in gr if x.get("review_rows") is not None)
    growth = ('<div class="grid g2" style="gap:32px 48px"><div><h3>Variants, state by state</h3>%s</div><div><h3>Review rows (expert scores and owner ratings)</h3>%s</div></div>%s'
              % (gv or '<p class="empty">No history.</p>', gv2 or '<p class="empty">No review history.</p>',
                 src("knowledge base states recorded after each run" if D["meta"]["growth_source"] == "history" else "coverage figures in the run records")))
    # reviews
    cv = rev["coverage"]
    tot = cv["total"] or 1
    cov = ('<div class="covbar" role="img" aria-label="Models by review coverage">%s</div><div class="legend" style="margin-top:12px"><span><i class="sw m"></i>Both expert and owner scores: %d</span><span><i class="sw" style="background:var(--accent-soft)"></i>Expert only: %d</span>'
           '<span><i class="sw" style="background:var(--surface-2)"></i>Owner only: %d</span><span><i class="sw" style="background:var(--line)"></i>Neither: %d</span></div>'
           % ("".join('<div class="%s" style="flex:%d">%d</div>' % (c, max(n, 0), n) for n, c in [(cv["both"], "cv-b"), (cv["expert_only"], "cv-e"), (cv["owner_only"], "cv-o"), (cv["neither"], "cv-n")] if n), cv["both"], cv["expert_only"], cv["owner_only"], cv["neither"]))
    ex_o = next((r for r in rev["expert"]["rows"] if r["aspect"] == "overall"), None)
    ow_o = next((r for r in rev["owner"]["rows"] if r["aspect"] == "overall"), None)
    dist = ('<div class="grid g2" style="gap:32px 48px"><div><h3>Expert overall score</h3><p class="note" style="margin-top:0">Autocar India, out of %s, one bar per whole point (%d models)</p>%s</div>'
            '<div><h3>Owner overall rating</h3><p class="note" style="margin-top:0">CarWale, out of %s, one bar per quarter point (%d models)</p>%s</div></div>%s'
            % (fmt(rev["expert"]["scale_max"] or 10), len(ex_o["points"]) if ex_o else 0, hist_svg(ex_o["points"], 1, "expert overall scores") if ex_o else '<p class="empty">No data.</p>',
               fmt(rev["owner"]["scale_max"] or 5), len(ow_o["points"]) if ow_o else 0, hist_svg(ow_o["points"], .25, "owner overall ratings") if ow_o else '<p class="empty">No data.</p>',
               src("professional_assessment and owner_rating rows with status current, knowledge base snapshot")))
    trs = ""
    for t in rev["table"]:
        trs += ('<tr><td data-v="%s">%s</td><td data-v="%s">%s</td><td class="n" data-v="%s">%s</td><td class="n" data-v="%s">%s</td><td class="n" data-v="%s">%s</td><td class="n" data-v="%s">%s</td></tr>'
                % (E(t["make"]), E(t["make"]), E(t["model"]), E(t["model"]), t["variants"], t["variants"], "" if t["expert"] is None else t["expert"], "n/a" if t["expert"] is None else "%.1f" % t["expert"],
                   "" if t["owner"] is None else t["owner"], "n/a" if t["owner"] is None else "%.2f" % t["owner"], "" if t["count"] is None else t["count"], "n/a" if t["count"] is None else fmt(t["count"])))
    th = "".join('<th%s><button type="button">%s</button></th>' % (' class="n"' if n else "", l) for l, n in [("Make", 0), ("Model", 0), ("Variants", 1), ("Expert /10", 1), ("Owner /5", 1), ("Owner ratings", 1)])
    table = ('<div class="tbl-wrap" style="max-height:520px" tabindex="0" role="region" aria-label="Model scores table"><table class="tbl sortable"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
             '<p class="note">Select a column heading to sort. n/a means the source had no page or no score for that model.</p>' % (th, trs))
    td = rx["themes_by_direction"]
    cols = ""
    for d_, lab in [("positive", "Positive"), ("mixed", "Mixed"), ("negative", "Negative")]:
        items = td.get(d_, [])[:8]
        m_ = max([i["mentions"] for i in items] or [1])
        cols += '<div><h3>%s</h3>%s</div>' % (lab, "".join(bar_row(i["theme"], i["mentions"] / m_, "%s in %d %s" % (fmt(i["mentions"]), i["models"], "model" if i["models"] == 1 else "models")) for i in items) or '<p class="empty">None.</p>')
    themes = '<div class="themes">%s</div><p class="note">%s theme rows across %d models. A mention is one sampled review that raised the theme, checked by a second model; counts come from a sample of reviews per model, not all reviews.</p>%s' % (cols, fmt(rev["theme_rows"]), rx["n_theme_models"], src("owner_theme table, knowledge base snapshot"))
    notes = "".join('<figure><figcaption><b>%s %s</b> &middot; %s %s/%s</figcaption><blockquote>%s</blockquote><figcaption>%s, published %s</figcaption></figure>'
                    % (E(n["make"]), E(n["model"]), E(n["aspect"]), "%g" % n["score"], "%g" % n["scale_max"], E(n["note"]), E(n["source"]), E(n["published_on"])) for n in rx["notes"])
    notesh = ('<div class="notes">%s</div><p class="note">%s of the %s expert rows carry a note. Notes are written by one model from the review page and checked by another; the score beside each note is read as page data.</p>%s'
              % (notes or '<p class="empty">No notes yet.</p>', fmt(rx["n_notes"]), fmt(rx["n_current"]), src("professional_assessment, knowledge base snapshot")))
    cl_, tot_ = g["classes"], g["values"] or 1
    body = (page_head("The knowledge base", "A database of new cars sold in India. Each stored value is shown with the strongest evidence behind it: %s of values rest on a brochure page and %s only on an import that recorded no source. Prices may be out of date."
                      % (pct(cl_["brochure"] / tot_), pct(cl_["import"] / tot_)), ctx)
            + section("evidence", "How well each value is backed", "Every stored value, counted once by the strongest evidence behind it.", evidence_view(D))
            + section("prices", "How recent the prices are", "", price_view(D))
            + section("gaps", "Not yet applied, and known gaps", "What the pipeline has found but not written, and what the data is missing.", gaps_view(D))
            + section("glance", "At a glance", "What the database holds now.", glance)
            + section("contents", "What is in it", "The main tables in four groups, with row counts.", '<div class="panel scroll" tabindex="0" role="region" aria-label="Table diagram, scrolls sideways on narrow screens" style="padding:16px">%s</div>%s'
                      % (entity_svg(ent), src("row counts, knowledge base snapshot")))
            + section("provenance", "How provenance works", "One stored value, followed from the page it was read on to the cell it is stored in. This example has a full trail.", tr)
            + section("coverage", "Coverage", "How many values are filled, by manufacturer and kind of fact. A blank means no value was stored; it is unknown, not zero.", heat)
            + section("growth", "Growth over runs", "The size of the knowledge base after each recorded state.", growth)
            + section("trust", "Sample re-check", "A sample of stored values, stratified by source and kind of fact, was re-read against its source by a second model. All figures come from that verification file; cells that could not be checked are shown, not hidden. A sample says little about any one value.", trust_blocks(T, D["verify_runs"]))
            + section("reviews", "The reviews layer", "Expert scores and notes from Autocar India, and owner ratings and themes from CarWale. They are stored as their own evidence, apart from the specifications.",
                      '<div class="sub"><h3>Which models have scores</h3>%s%s</div><div class="sub">%s</div><div class="sub"><h3>Every model</h3>%s</div><div class="sub"><h3>Most common owner themes, by direction</h3>%s</div><div class="sub"><h3>Example expert notes</h3>%s</div>'
                      % (cov, src("model counts, knowledge base snapshot"), dist, table, themes, notesh))
            + '<section class="section" id="third-party"><div class="wrap">%s</div></section>' % notice_third_party(D, "kb"))
    return shell("kb.html", "CarRec knowledge base", body, ctx, "What the CarRec knowledge base holds, the evidence behind each value, how recent the prices are, and what is missing.")


# ---------------------------------------------------------------- recommendation engine page
def wrap_text(s, n):
    lines, cur = [], ""
    for w_ in str(s).split():
        if len(cur) + len(w_) + 1 > n and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = (cur + " " + w_).strip()
    return lines + ([cur] if cur else [])


def flow_svg(C):
    steps = [("Query", "Plain English or Hinglish, typed as the user likes"),
             ("Parse and repair", "Rules read budget, fuel, body, features; common typos are repaired"),
             ("Hard constraints", "Each stated must-have filters the catalogue; a blank value passes"),
             ("Score", "Weighted criteria across three evidence classes"),
             ("Diversify", "Best variant per model, then a re-rank so the list is not eight near-twins (max %s models)" % C.get("MAX_MODELS", "8")),
             ("Explain", "Up to %s reasons per car, each tagged with its evidence class" % C.get("MAX_REASONS", "4"))]
    bw, gap = 160, 28
    out = []
    for i, (t, cap) in enumerate(steps):
        x = i * (bw + gap)
        cls = "box acc" if t == "Score" else "box"
        on = "on-acc" if t == "Score" else ""
        ln = wrap_text(t, 12)
        out.append('<rect class="%s" x="%d" y="8" width="%d" height="84" rx="14"/>' % (cls, x, bw))
        for j, l in enumerate(ln):
            out.append('<text class="%s" x="%d" y="%d" text-anchor="middle" font-size="20" font-weight="750">%s</text>' % (on, x + bw // 2, 58 - (len(ln) - 1) * 12 + 25 * j, E(l)))
        for j, l in enumerate(wrap_text(cap, 24)[:6]):
            out.append('<text class="t2" x="%d" y="%d" font-size="14">%s</text>' % (x + 4, 118 + 18 * j, E(l)))
        if i < len(steps) - 1:
            out.append(arrow_h(x + bw + 3, x + bw + gap - 2, 50))
    gx = 2 * (bw + gap) + bw  # gap between constraints and score
    out.append('<path class="arrow dash" d="M%d 96 V232"/><path class="arrow-head" d="M%d 238 l-5 -8 h10 z"/>' % (gx + 8, gx + 8))
    out.append('<path class="arrow dash" d="M%d 238 V102"/><path class="arrow-head" d="M%d 96 l-5 8 h10 z"/>' % (gx + 20, gx + 20))
    out.append('<rect class="box soft" x="%d" y="240" width="330" height="62" rx="12"/><text x="%d" y="266" text-anchor="middle" font-size="16" font-weight="750">If nothing fits: relax</text>'
               '<text class="t2" x="%d" y="288" text-anchor="middle" font-size="13.5">drop the cheapest requirement, name it, retry</text>' % (gx + 14 - 165, gx + 14, gx + 14))
    W = 6 * bw + 5 * gap
    return ('<svg viewBox="-3 0 %d 316" style="min-width:900px" role="img" aria-labelledby="fl-t fl-d"><title id="fl-t">How a query becomes a ranked list</title>'
            '<desc id="fl-d">Query, parse and repair, hard constraints, score, diversify, explain. If no car passes the hard constraints, the engine relaxes the cheapest requirement and tries again.</desc>%s</svg>' % (W + 6, "".join(out)))


def eval_table(E_):
    vm, vh, cm, ch = E_.get("v3_main"), E_.get("v3_held"), E_.get("cur_main"), E_.get("cur_held")
    if not (vm and cm):
        return '<p class="empty">Evaluation result files not found.</p>', ""

    def cs(e):
        return "%s of %s (%s)" % (fmt(e["zero_viol"]), fmt(e["with_cars"]), pct(e["zero_viol"] / e["with_cars"])) if e and e.get("with_cars") else "n/a"

    def imp(e):
        o = e.get("empty_outcomes") or {}
        if e["engine"] == "v3":
            return "%s relaxed with the broken requirement named, %s mislabelled, %s returned cars unmarked" % (fmt(e["relaxed_truthful"]), fmt(e["relaxed_mislabelled"]), fmt(o.get("cars_returned_unmarked")))
        return "%s returned nothing, %s returned cars unmarked" % (fmt(o.get("empty")), fmt(o.get("cars_returned_unmarked")))

    def probe(e):
        return "%s of %s still returned; known-lacking car placed above it: %s (newly: %s)" % (fmt(e["probe_returned"]), fmt(e["probe_n"]), fmt(e["probe_lacking_above"]), fmt(e["probe_newly_above"]))
    r = [("Hard requirements met, main set (blank values count as met)", cs(cm), cs(vm), "%s queries, %s returned cars" % (fmt(vm["n_queries"]), fmt(vm["with_cars"]))),
         ("Hard requirements met, second set (blank values count as met)", cs(ch), cs(vh), "%s queries, %s returned cars" % (fmt(vh["n_queries"]) if vh else "n/a", fmt(vh["with_cars"]) if vh else "n/a")),
         ("Shortlist recall@8", "%.3f" % cm["recall8"], "%.3f" % vm["recall8"], "%s queries labelled by one person" % fmt(vm["shortlist_filled"])),
         ("Shortlist MRR", "%.3f" % cm["mrr"], "%.3f" % vm["mrr"], "same %s queries" % fmt(vm["shortlist_filled"])),
         ("Impossible requests", imp(cm), imp(vm), "%s queries" % fmt(vm["empty_expected"])),
         ("Unknown-value probe", probe(cm), probe(vm), "%s blanked cells; lower known-lacking is better" % fmt(vm["probe_n"]))]
    tb = ('<div class="tbl-wrap"><table class="tbl" style="min-width:760px"><thead><tr><th>Measure</th><th>Current engine</th><th>New engine (v3)</th><th>Sample</th></tr></thead><tbody>%s</tbody></table></div>'
          % "".join("<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td></tr>" % tuple(E(x) for x in row) for row in r))
    bars = ""
    for name, a, b in [("Hard requirements met, main (blanks count as met)", cm["zero_viol"] / cm["with_cars"], vm["zero_viol"] / vm["with_cars"]),
                       ("Hard requirements met, second set", (ch["zero_viol"] / ch["with_cars"]) if ch else None, (vh["zero_viol"] / vh["with_cars"]) if vh else None),
                       ("Shortlist recall@8", cm["recall8"], vm["recall8"]), ("Shortlist MRR", cm["mrr"], vm["mrr"])]:
        if a is None or b is None:
            continue
        bars += '<div class="sub" style="margin-top:16px"><h3 style="font-size:1rem">%s</h3>%s%s</div>' % (E(name), bar_row("Current engine", a, "%.3f" % a, "cur"), bar_row("New engine (v3)", b, "%.3f" % b))
    legend = '<div class="legend"><span><i class="sw cur"></i>Current engine</span><span><i class="sw m"></i>New engine (v3)</span></div>'
    return tb, legend + bars


def page_engine(D, ctx):
    E_ = D["engine"]
    head = page_head("The recommendation engine", "Turns a plain-language request into a ranked list of cars, with reasons. A value that is blank for a car is treated as unknown, not as no, so such a car can pass a stated requirement; its card then says the value is unknown.", ctx)
    if not E_.get("found"):
        body = head + '<section class="section"><div class="wrap"><div class="empty"><b>Data not found.</b> The recommender files (documents, configuration, evaluation results, review data and screenshots) were not available when this page was generated, so this page has no figures. The other pages are unaffected.</div></div></section>'
        return shell("engine.html", "CarRec engine", body, ctx, "The CarRec recommendation engine.")
    C = E_["config"]
    cw = C.get("CLASS_WEIGHTS") or {}
    parts = []
    # flow
    parts.append(section("flow", "From query to ranked list", "Six steps in code. A language model may help read the query, but it never picks or orders cars.",
                         '<div class="panel scroll" tabindex="0" role="region" aria-label="Flow diagram, scrolls sideways on narrow screens" style="padding:16px">%s</div>%s'
                         % (flow_svg(C), src("engine configuration and design plan; the optional language-model query reader is off unless a request asks for it"))))
    # scoring
    k = C.get("OWNER_SAMPLE_K", 50)
    cov = C.get("COVERAGE_PENALTY", .15)
    bp, bf = C.get("BLANK_PRIOR_BOOL_FACTOR", .7), C.get("BLANK_PRIOR_MARGIN", .15)
    tot = sum(cw.values()) or 1
    cwbar = ""
    if cw:
        x, segs = 0, []
        names = {"spec": "Specifications", "expert": "Expert scores", "owner": "Owner ratings"}
        for key, cls in [("spec", "m"), ("expert", "ink"), ("owner", "unr")]:
            w = cw.get(key, 0) / tot * 100
            segs.append('<rect class="%s" x="%.2f" y="0" width="%.2f" height="10"><title>%s: %.0f%%</title></rect>' % (cls, x, max(w - .4, .1), names[key], w))
            x += w
        cwbar = ('<svg class="stackbar" style="height:30px" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="Class weights">%s</svg>'
                 '<div class="legend" style="margin-top:12px"><span><i class="sw m"></i>Specifications %.0f%%</span><span><i class="sw ink"></i>Expert scores %.0f%%</span><span><i class="sw unr"></i>Owner ratings %.0f%%</span></div>'
                 % ("".join(segs), cw.get("spec", 0) / tot * 100, cw.get("expert", 0) / tot * 100, cw.get("owner", 0) / tot * 100))
    prior_x = lambda v: 40 + v * 420
    share = .5
    prior = share * bp
    line = ('<svg viewBox="0 0 500 110" role="img" aria-labelledby="bl-t"><title id="bl-t">A blank cell is scored between known no and known yes</title>'
            '<line x1="40" y1="50" x2="460" y2="50" stroke="var(--line-strong)" stroke-width="3"/>'
            '<circle cx="%d" cy="50" r="9" fill="var(--danger)"/><circle cx="%.1f" cy="50" r="9" fill="var(--neutral)"/><circle cx="%d" cy="50" r="9" fill="var(--accent)"/>'
            '<text x="%d" y="30" text-anchor="middle" font-size="14" font-weight="700">Known no</text><text x="%d" y="82" text-anchor="middle" class="t2" font-size="14">0</text>'
            '<text x="%.1f" y="30" text-anchor="middle" font-size="14" font-weight="700">Blank</text><text x="%.1f" y="82" text-anchor="middle" class="t2" font-size="14">%.2f</text>'
            '<text x="%d" y="30" text-anchor="middle" font-size="14" font-weight="700">Known yes</text><text x="%d" y="82" text-anchor="middle" class="t2" font-size="14">1</text></svg>'
            % (prior_x(0), prior_x(prior), prior_x(1), prior_x(0), prior_x(0), prior_x(prior), prior_x(prior), prior, prior_x(1) - 8, prior_x(1) - 8))
    w_big, w_small = 959 / (959 + k), 21 / (21 + k)
    sc = ('<div class="grid g2" style="gap:32px 48px">'
          '<div><h3>Weighted criteria, three evidence classes</h3><p style="margin-top:8px;color:var(--ink-2)">Each car gets a value from 0 to 1 on criteria such as value for budget, safety, running cost, comfort, space, performance and tech. These are combined within three classes, and the classes are combined with fixed weights.</p><div style="margin-top:16px">%s</div>%s</div>'
          '<div><h3>Unknown stays unknown</h3><p style="margin-top:8px;color:var(--ink-2)">A blank value is never shown as a fact. Inside the score it is valued below the typical car of its segment: for a yes/no feature, the share of segment cars that have it times %s. On top of that the overall score is multiplied by 1 &minus; %s &times; (share of weight that is unknown), so a car with gaps ranks slightly lower, not last.</p><div style="margin-top:16px">%s</div>'
          '<p class="note">Illustration for a segment in which half the cars have the feature. A known &ldquo;no&rdquo; is still worse than a blank. With 40%% of the weight unknown the factor is %.3f.</p></div></div>'
          '<div class="grid g2" style="gap:32px 48px;margin-top:40px"><div><h3>Segment-relative scoring</h3><p style="margin-top:8px;color:var(--ink-2)">Price, power and similar numbers are scored as a percentile among cars of the same body type, so a hatchback is not compared with a 7-seater on raw numbers. A segment with fewer than %s models is compared with the whole catalogue.</p></div>'
          '<div><h3>Thin evidence counts for less</h3><p style="margin-top:8px;color:var(--ink-2)">An owner rating is pulled toward the segment mean by count / (count + %s). A model with 959 ratings keeps %.0f%% of its own value; one with 21 ratings keeps %.0f%%.</p></div></div>%s'
          % (cwbar, src("class weights and constants read from the engine configuration"), E(bp), E(cov), line, 1 - cov * .4, E(C.get("MIN_SEGMENT_MODELS", 8)), E(k), w_big * 100, w_small * 100,
             src("engine configuration: CLASS_WEIGHTS, COVERAGE_PENALTY, BLANK_PRIOR_BOOL_FACTOR, MIN_SEGMENT_MODELS, OWNER_SAMPLE_K")))
    parts.append(section("scoring", "The scoring model in plain words", "", sc))
    # card
    shots = {s["key"]: s for s in E_.get("shots", [])}
    if shots:
        pins = [(1, 40.5, 4), (2, 40.5, 19), (3, 93, 22), (4, 5.5, 37.5), (5, 33.5, 37.5), (6, 63.5, 37.5), (7, 7.5, 84.5)]
        card = shots.get("card")
        left = ""
        if card:
            left = ('<div class="shotbox"><img alt="A result card for the Mahindra XUV 3XO with scores, reviewer notes, owner notes and a caveat" width="1000" src="data:image/jpeg;base64,%s">%s</div>'
                    % (card["b64"], "".join('<span class="pin" style="left:%d%%;top:%d%%" aria-hidden="true">%d</span>' % (x, y, n) for n, x, y in pins)))
        lg = ('<ol class="legendlist"><li><span><b>Variant and price.</b> The variant shown is the best-scoring one for this query, with the lowest price in the model alongside.</span></li>'
              '<li><span><b>Requirement status.</b> &ldquo;Meets all your requirements&rdquo;, or the requirement that was relaxed.</span></li>'
              '<li><span><b>Three bars.</b> Specifications fit the search; expert and owner bars show standing among rated models of the same body type, not absolute quality.</span></li>'
              '<li><span><b>Why this car.</b> Reasons built from the values used in scoring. Any criterion scored at or above the midpoint can appear as a reason.</span></li>'
              '<li><span><b>What reviewers say.</b> Stored note, score, source and date, with the quoted line and a link to the review.</span></li>'
              '<li><span><b>What owners say.</b> Theme, direction and how many of the sampled reviews raised it.</span></li>'
              '<li><span><b>Caveats.</b> Every negative theme and reported fault, shown whether or not the query asked about it.</span></li></ol>')
        extra = ""
        sm = []
        if shots.get("page"):
            sm.append('<figure><div class="shotbox"><img alt="The results page in dark theme" width="1000" loading="lazy" src="data:image/jpeg;base64,%s"></div><figcaption class="note">%s</figcaption></figure>' % (shots["page"]["b64"], E(shots["page"]["caption"])))
        if shots.get("phone"):
            sm.append('<figure style="max-width:320px"><div class="shotbox"><img alt="The same card at phone width" width="390" loading="lazy" src="data:image/jpeg;base64,%s"></div><figcaption class="note">%s</figcaption></figure>' % (shots["phone"]["b64"], E(shots["phone"]["caption"])))
        extra = '<div class="grid g2" style="margin-top:40px;align-items:start">%s</div>' % "".join(sm) if sm else ""
        parts.append(section("card", "What a result card shows", "Each line on a card is built from values the engine used, and names its source.",
                             '<div class="shots">%s<div>%s</div></div>%s%s' % (left, lg, extra, src("screenshots of the running application, downscaled"))))
    else:
        parts.append(section("card", "What a result card shows", "", '<p class="empty">No screenshots were found.</p>'))
    # evaluation
    tb, bars = eval_table(E_)
    used = [e["file"] for e in (E_.get("v3_main"), E_.get("v3_held"), E_.get("cur_main"), E_.get("cur_held")) if e]
    fd = E_.get("final_doc")
    fnote = ""
    if fd and not str((E_.get("v3_main") or {}).get("file", "")).startswith("final_"):
        fnote = (' The review&rsquo;s last section reports %.3f recall@8 and %.3f MRR for the default build and %.3f and %.3f for the current engine, measured on a later build whose result files are not among the saved ones; this page shows the saved files.'
                 % (fd["v3_recall"], fd["v3_mrr"], fd["cur_recall"], fd["cur_mrr"]))
    sl = E_.get("shortlist") or {}
    first_models = (D["growth"][0].get("models") if D.get("growth") else None)
    cat_models = (E_.get("catalogue") or {}).get("models")
    added = (cat_models - first_models) if (first_models and cat_models) else None
    hr = E_.get("heldout_reuse") or {}
    vs = E_.get("verified_satisfaction")
    vm_ = E_.get("v3_main") or {}
    if vs and all(isinstance(x, (int, float)) for x in vs.values()):
        vtxt = "A figure that counts a blank as not met: %s, beside the %s of %s above." % (
            ", ".join("%s %s" % (k.replace("_", " "), fmt(v) if float(v).is_integer() else "%.3f" % v) for k, v in vs.items()),
            fmt(vm_.get("zero_viol")), fmt(vm_.get("with_cars")))
    else:
        vtxt = "A figure that counts a blank as not met is being added and is not on this page yet, so the 100% in the table below says nothing about requirements that were blank."
    trust = ['The query sets and their labels were written by the project&rsquo;s author, who also built the engine. No second person labelled them, so there is no agreement figure between raters.']
    if hr:
        trust.append("The second query set was written on %s as a held-out set. The query parser was then changed in %s commits and the set was scored again; %s result files are named for it. It is no longer unseen: read it as a second development set."
                     % (E(day_text(hr["written"])), fmt(hr["parser_commits_after"]), fmt(hr["result_files"])))
    else:
        trust.append("The second query set was written as a held-out set; if the parser was changed afterwards and the set scored again, it is no longer unseen.")
    trust.append("Unknown values are not counted as violations in the hard-requirements figure, so a car with a blank for something the buyer asked for counts as meeting it. %s" % E(vtxt))
    trust.append("The shortlist measure has %s queries and %s picks, all by one person%s. One pick moves recall by about %.1f percentage points."
                 % (fmt(sl.get("queries")), fmt(sl.get("picks")), (", written before the %s models added since (%s now, %s then)" % (fmt(added), fmt(cat_models), fmt(first_models))) if added else "",
                    100.0 / sl["picks"] if sl.get("picks") else 0))
    trust.append("No user study and no click data exist. Nothing here measures whether people find the recommendations useful.")
    trust.append("Both engines are the project&rsquo;s own, run on the project&rsquo;s own queries. The tables show that the code does what it was written to do on these queries; they do not show that the recommendations are good.%s" % fnote)
    box = '<div class="notice warn"><strong>How far to trust these numbers.</strong><ul>%s</ul></div>' % "".join("<li>%s</li>" % t if "&rsquo;" in t else "<li>%s</li>" % t for t in trust)
    ev = ('%s<div style="margin-top:var(--s3)">%s</div>'
          '<div class="sub">%s</div><p class="src"><b>Files used:</b> %s. Both engines ran with the language-model query reader off, so results do not depend on a network call. The two engines are compared on the same catalogue of %s variants and %s models.</p>'
          % (box, tb, bars and ('<h3>Same numbers as bars</h3>' + bars), E(", ".join(used)), fmt((E_.get("catalogue") or {}).get("rows")), fmt(cat_models)))
    parts.append(section("evaluation", "What was measured", "The project's own tests of the current engine and the new one, on the same queries and catalogue. They are not proof of quality.", ev))
    # limits
    vm, vh = E_["v3_main"], E_["v3_held"]
    ass, own = E_.get("assess") or {}, E_.get("owner") or {}
    missing = sorted(set(E_.get("catalogue_models") or []) - set(ass.get("model_names") or []))
    lim = []
    if vm:
        lim.append(("The shortlist test is small and dated.", "%s queries, %s picks, labelled by one person against the older catalogue. The %s models added later were never on a label, so a new model that ranks first can count as a miss." % (fmt(sl.get("queries")), fmt(sl.get("picks")), fmt(added) if added else "newer"), "evaluation results; shortlist gap review"))
        lim.append(("The unknown-value probe is not met.", "When a feature is blanked on a good car, a car known to lack it ranks above it %s times out of %s probes (the target is 0)." % (fmt(vm["probe_newly_above"]), fmt(vm["probe_n"])), "evaluation results; review of 15 Nov"))
        lim.append(("Some impossible requests return cars.", "%s of %s requests labelled impossible still returned cars with no relaxation label in both engines. In each case the returned cars have a blank (unknown) value for the thing asked for, and a blank is unknown, not no, so it passes the filter; the test calls a request impossible by its known values only." % (fmt((vm.get("empty_outcomes") or {}).get("cars_returned_unmarked")), fmt(vm["empty_expected"])), "evaluation results; checked against the catalogue file"))
    if vh and vh.get("violating"):
        lim.append(("Parser misses remain.", "On the second set %d queries returned a car that breaks a stated requirement (%s); both engines share these parser misses. Unknown values never count as violations in this test." % (len(vh["violating"]), ", ".join(vh["violating"])), "evaluation results"))
    if ass:
        lim.append(("Review coverage is partial.", "%s of %s catalogue models have no expert rows and %s models have owner ratings under 30 reviews. They get no review reasons and are not penalised." % (fmt(len(missing)), fmt((E_.get("catalogue") or {}).get("models")), fmt(own.get("low_conf_models"))), "review data files"))
        if ass.get("min10") is not None:
            lim.append(("Expert scores are compressed.", "Overall expert scores run from %.0f to %.0f out of 10, so the engine compares cars; it does not rescale them." % (ass["min10"], ass["max10"]), "review data files"))
    af = E_.get("added_fill")
    if af:
        lim.append(("Newer models are scored on less.", "The %s variants added after the first 832 have length for %.0f%%, ABS for %.0f%%, ESC for %.0f%% and ADAS for %.0f%% of rows; the rest are unknown and are scored as unknown." % (fmt(af["rows"]), af["length_mm"] * 100, af["abs"] * 100, af["esc"] * 100, af["adas_available"] * 100), "catalogue file; review of 15 Nov"))
    else:
        lim.append(("Newer models are scored on less.", "The review notes say the models added most recently carry no dimension, ABS, ESC or ADAS values yet, so they are scored on more unknowns until the knowledge base is filled.", "review of 15 Nov"))
    bs = E_.get("blank_share") or {}
    if bs:
        lim.append(("A blank value passes a hard requirement.", "In the catalogue, ADAS is blank for %s of variants and sunroof for %s. A car with a blank still passes a request that needs the feature, and its card says the value is unverified. When no car has the feature confirmed, the unconfirmed cars are what is shown."
                    % (pct(bs.get("adas_available")), pct(bs.get("sunroof"))), "catalogue file; evaluation results"))
    cg = (D.get("honest") or {}).get("crash")
    fl, bm = C.get("CRASH_PRIOR_FLOOR_STARS"), C.get("CRASH_PRIOR_STARS_BELOW_MEDIAN")
    if fl is not None and bm is not None:
        lim.append(("A car with no crash rating can outscore one rated badly.", "An unrated car is scored from a prior of the segment median minus %s star, with a floor of %s stars, so at least %.1f of the crash criterion; a car rated 2 stars scores %.1f.%s"
                    % ("%g" % bm, "%g" % fl, fl / 5, 2 / 5, (" %s models whose crash test is stored but not linked to them (%s variants) are scored on the prior, and the app shows them as having no rating on record." % (fmt(len(cg["models"])), fmt(cg["variants"]))) if cg and cg["models"] else ""), "engine configuration; knowledge base snapshot"))
    pw = C.get("PRICE_CHEAP_WEIGHT")
    if pw is not None:
        lim.append(("A request for the cheapest car is not sorted by price.", "Price is one criterion among several; even when the query asks for cheap it carries a weight of %s, so the top result need not be the lowest-priced car." % ("%g" % pw), "engine configuration"))
    if own.get("mean_overall") is not None:
        lim.append(("Owner ratings are close together.", "Overall owner ratings average %.2f out of %d across the models that have one, so a line such as &ldquo;owners rate this 4.3/5&rdquo; says little on its own.".replace("&ldquo;", "\u201c").replace("&rdquo;", "\u201d") % (own["mean_overall"], own["scale"]), "review data files"))
    th = ((D.get("honest") or {}).get("third") or {}).get("themes")
    if th and th["rows"]:
        lim.append(("A caveat can rest on three reviews.", "%s of %s owner theme rows rest on 3 or fewer mentions, and caveats are built from them." % (fmt(th["le3"]), fmt(th["rows"])), "knowledge base snapshot"))
    lim.append(("Owner themes are a sample.", "Theme counts are mentions in a sample of reviews per model, not in all reviews, and a theme&rsquo;s effect on the score is capped by design.".replace("&rsquo;", "’"), "review of 15 Nov"))
    lim.append(("The language-model query reader is off by default.", "The design plan wanted it on; it is optional, needs a key, and falls back to the rules.", "review of 14 Nov; API notes"))
    lh = '<ul class="limits">%s</ul>' % "".join("<li><b>%s</b> %s<em>%s</em></li>" % (E(a), E(b), E(c)) for a, b, c in lim)
    parts.append(section("limits", "Known limits", "Taken from the review notes and the independent audit, and recomputed from the result files and the knowledge base where a number is shown.", lh))
    # api
    eps = E_.get("endpoints") or []
    if eps:
        ah = '<ul class="api">%s</ul>%s' % ("".join('<li><span class="m">%s</span><span><b class="mono">%s</b><br>%s</span></li>' % (E(e["method"]), E(e["path"]), E(trim_text(e["text"], 300))) for e in eps), src("API and deployment notes"))
        parts.append(section("api", "API endpoints", "The same engine is available as a small typed HTTP service beside the web app.", ah))
    parts.append('<section class="section" id="third-party"><div class="wrap">%s</div></section>' % notice_third_party(D, "engine"))
    body = head + "".join(parts)
    return shell("engine.html", "CarRec engine", body, ctx, "How the CarRec recommendation engine ranks cars, what its tests measured and where they fall short.")


# ---------------------------------------------------------------- build
FORBIDDEN = ["/Users/", "~/", "worktree", "feat/", "Claude", "Gemini", "Sonnet", "Opus", "Haiku", "Groq", "quota", "usage limit", "/tmp/", "kbpipe", "recsys", "carrec_"]


def check_public(name, html):
    for w in FORBIDDEN:
        i = html.find(w)
        if i >= 0:
            raise ValueError("%s mentions %r near: %s" % (name, w, re.sub(r"\s+", " ", html[max(0, i - 60):i + 60])))
    for m in re.finditer(r'(?:src|href)="([^"#][^"]*)"', html):
        u = m.group(1)
        if re.match(r"^(https?:|//)", u):
            raise ValueError("%s loads or links an external address: %s" % (name, u))


def build(db_path, runs_dir, history_repo, kb_sha1, date, recsys_dir=None, audit_report=None):
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
    pipe = pipeline_data(c, runs, trust, glance, kb_counts)
    extra = reviews_extra(c)
    per_src = per_source_counts(c)
    honest = {"audit_def": audit_definition(c), "price": price_freshness(c, vrows, date), "dates": date_block(c, runs),
              "backlog": backlog(c, runs, vrows), "duplicates": duplicate_groups(c), "crash": crash_gap(c), "third": third_party(c),
              "spot": audit_spot_check(audit_report) if audit_report else None, "planted": planted_by_run(runs),
              "import_note": one(c, "select notes from source where name='v6_migration'", default=None)}
    c.close()
    return {"meta": {"generated": date, "kb_hash8": kb_sha1[:8], "growth_source": "history" if hist else "runs", "dates": honest["dates"]},
            "glance": glance, "entities": kb_counts, "heat": heat, "growth": growth, "history": history_table(runs), "trust": trust, "verify_runs": per_run,
            "reviews": rev, "reviews_extra": extra, "pipeline": pipe, "per_source": per_src, "engine": engine_data(recsys_dir), "honest": honest}


def render_site(D, app_base=""):
    ctx = {"meta": D["meta"], "app_base": app_base or ""}
    pages = {"index.html": page_index(D, ctx), "pipeline.html": page_pipeline(D, ctx), "kb.html": page_kb(D, ctx), "engine.html": page_engine(D, ctx)}
    for n, h in pages.items():
        check_public(n, h)
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kbpipe.dashboard", description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="path of index.html; the other pages are written beside it")
    ap.add_argument("--out-dir", help="folder for the four pages (alternative to --out)")
    ap.add_argument("--db", help="a read copy of the KB. Default: make one from the production file with the holder and hash checks")
    ap.add_argument("--runs", help="runs folder (default: config runs_dir)")
    ap.add_argument("--history", help="history repo (default: config history_repo)")
    ap.add_argument("--recsys-dir", default=DEFAULT_RECSYS, help="recommender checkout (default: %(default)s); engine.html says so if absent")
    ap.add_argument("--app-base", default="", help="path of the web app (for example /); adds a Back to CarRec link")
    ap.add_argument("--no-local-notes", action="store_true", help="accepted for clarity: pages never carry local paths or internal tool names, and the build fails if one slips in")
    ap.add_argument("--audit-report", help="the independent audit file (read for its spot-check tally only); default: looked up beside the production file")
    ap.add_argument("--date", help="override the generated-on date (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    cfg = config.load()
    if a.db:
        db, sha = a.db, kb.sha1(a.db)
    else:
        db = DEFAULT_COPY
        sha = kb.copy_for_read(cfg["prod_db"], db)
    out_dir = a.out_dir or (os.path.dirname(os.path.abspath(a.out)) if a.out else os.path.join(config.ROOT, "knowledge_base", "reports", "kb_dashboard"))
    date = a.date or datetime.date.today().isoformat()
    audit = a.audit_report
    if audit is None:
        hits = sorted(glob.glob(os.path.join(os.path.dirname(os.path.expanduser(cfg["prod_db"])), "reports", "BLIND_AUDIT_*.md")))
        audit = hits[-1] if hits else None
    D = build(db, a.runs or cfg["runs_dir"], a.history or cfg["history_repo"], sha, date, a.recsys_dir, audit)
    pages = render_site(D, a.app_base)
    os.makedirs(out_dir, exist_ok=True)
    for fn, h in pages.items():
        with open(os.path.join(out_dir, fn), "w", encoding="utf-8") as f:
            f.write(h)
        print("wrote %s (%d bytes)" % (os.path.join(out_dir, fn), len(h.encode("utf-8"))))
    print("KB %s" % sha[:8])
    return 0


if __name__ == "__main__":
    sys.exit(main())
