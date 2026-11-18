"""The run: discovery -> extraction -> reconciliation -> verification -> gates -> write -> report."""
import csv
import json
import os
import random
import time
from datetime import datetime, timezone

from . import __version__, brochure, discover, extract, fetch, gates, kb, llm, match, plan, report, verify, write
from . import fields as F


def _run_dir(cfg, label=None):
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = os.path.join(cfg["runs_dir"], label or day)
    d, n = base, 1
    while os.path.exists(os.path.join(d, "RUN_SUMMARY.md")):
        n += 1
        d = "%s_%d" % (base, n)
    os.makedirs(d, exist_ok=True)
    return d, os.path.basename(d)


def _state(cfg, new=None):
    p = os.path.join(cfg["cache_dir"], "state.json")
    if new is not None:
        with open(p, "w") as f:
            json.dump(new, f, indent=0, sort_keys=True)
        return new
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def _planned_cells(ops, obs, start):
    """Cells the plan would write (new values), in the shape verify.check_cell expects."""
    out = []
    for op in ops[start:]:
        if op["op"] != "cell" or op["reason"] in ("AGGREGATORS_CONFIRM",):
            continue
        ev = next((e for e in op["evidence"] if e["decision"] == "accepted"), None)
        if not ev:
            continue
        o = obs[ev["obs"]]
        out.append({"variant_id": "%s|%s|%s" % (op["make"], op["model"], op["variant"]), "field_name": op["field"],
                    "full_name": "%s %s %s" % (op["make"], op["model"], op["variant"]), "value": op["value"],
                    "group": F.FIELDS[op["field"]][2], "cls": "brochure" if o["source"] == "oem" else "aggregator",
                    "source": o["source"], "source_url": o["url"],
                    "raw_payload": o["payload"] if isinstance(o["payload"], str) else json.dumps(o["payload"])})
    return out


def run(cfg, full=False, max_models=None, only=None, no_write=False, no_verify=False, audit=None, label=None, echo=print):
    t0 = time.time()
    run_dir, run_id = _run_dir(cfg, label)
    lines = []

    def log(stage, *msg):
        line = "%s [%s] %s" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), stage, " ".join(str(m) for m in msg))
        lines.append(line)
        echo(line)
        with open(os.path.join(run_dir, "run.log"), "a") as f:
            f.write(line + "\n")

    R = {"run": run_id, "version": __version__, "started": fetch.now_iso(), "full": full, "stopped": None, "write": None,
         "stage": None, "verify_batches": [], "stopped_groups": {}, "llm": {}}
    try:
        sha = kb.copy_for_read(cfg["prod_db"], os.path.join(run_dir, "before.db"))
    except kb.Stop as e:
        R["stopped"] = str(e)
        log("stop", e)
        report.write_summary(cfg, run_dir, R, {}, [], None)
        return R
    R["sha1_before"] = sha
    before = os.path.join(run_dir, "before.db")
    conn = kb.ro(before)
    first_run = conn.execute("select count(*) from source_observation where extraction_method like 'kbpipe%'").fetchone()[0] == 0
    R["coverage_before"] = report.coverage(conn)
    fetcher = fetch.Fetcher(cfg, log=log)
    state = _state(cfg)

    # 1 discovery
    lst, failed = discover.listings(cfg, fetcher, log)
    items = discover.classify(cfg, conn, lst, failed)
    with open(os.path.join(run_dir, "discovery.json"), "w") as f:
        json.dump(items, f, indent=1, default=str)
    R["discovery"] = {}
    for it in items:
        R["discovery"][it["kind"]] = R["discovery"].get(it["kind"], 0) + 1
    log("discover", json.dumps(R["discovery"], sort_keys=True))

    # 2+3 extraction and reconciliation, with verification every N models
    P = plan.new()
    P["run"] = run_id
    todo = [it for it in items if it["kind"] in ("EXISTING", "NEW_MODEL") and (not only or it["model"] in only)]
    todo.sort(key=lambda it: (it["kind"] != "NEW_MODEL", it["make"], it["model"]))
    cap_new = cfg["max_new_models_per_run"]
    vdir = os.path.join(run_dir, "verify")
    vt = None if no_verify else {"text": llm.get(cfg, "verify", run_dir), "image": llm.get(cfg, "verify_image", run_dir)}
    rng = random.Random(cfg["seed"])
    processed, skipped_unchanged, new_done, deferred, legacy_url, ops_mark, since = 0, 0, 0, [], {}, 0, 0
    new_state = dict(state)
    bundles_meta = {}
    for it in todo:
        if max_models is not None and processed >= max_models:
            deferred.append(it)
            continue
        if it["kind"] == "NEW_MODEL" and new_done >= cap_new:
            deferred.append(it)
            continue
        key = "%s/%s" % (it["make"], it["key"])
        b = extract.model_bundle(it, cfg, fetcher, log, state)
        for p in b["problems"]:
            log("extract", "%s %s: %s" % (it["make"], it["model"], p))
        if not b["versions"]:
            P["review"].append({"kind": "SOURCE_UNREADABLE", "make": it["make"], "model": it["model"], "impact": 30,
                                "title": "%s %s could not be read" % (it["make"], it["model"]),
                                "why": "; ".join(b["problems"])[:400], "ops": [], "default": "hold"})
            continue
        if not full and not b["changed"] and state.get(key, {}).get("applied"):
            skipped_unchanged += 1
            continue
        n_ops = len(P["ops"])
        kept = {g for g in R["stopped_groups"]}
        brochure.enrich(it, b, conn, cfg, fetcher, log, run_dir)   # OEM brochure evidence onto each version's "brochure" list
        brochure.confirm_links(b)                                  # record (never block) "brochure confirms" on battery and hybrid links
        plan.plan_model(it, b, conn, cfg, P)
        for g in kept:   # a stopped field group is not extracted any further
            _drop_group(P, P["ops"][n_ops:], g, "verification fell below the bar earlier in this run")
        processed += 1
        since += 1
        new_done += it["kind"] == "NEW_MODEL"
        bundles_meta[key] = {"fingerprint": b["fingerprint"], "processed_at": fetch.now_iso(), "applied": False, "linker": match.LINKER_VERSION}
        log("extract", "%s %s: %d versions, %d linked on both sites" % (
            it["make"], it["model"], len(b["versions"]), sum(1 for v in b["versions"] if v["fields_cd"])))
        if vt and since >= cfg["verify_every_models"]:
            since = 0
            ops_mark = _verify_batch(cfg, P, ops_mark, fetcher, vt, vdir, R, rng, log)
    if vt and since:
        ops_mark = _verify_batch(cfg, P, ops_mark, fetcher, vt, vdir, R, rng, log)
    plan.finish(P)
    R["processed"], R["skipped_unchanged"], R["deferred"] = processed, skipped_unchanged, [
        "%s %s" % (d["make"], d["model"]) for d in deferred]
    for d in deferred:
        if d["kind"] == "NEW_MODEL":
            P["review"].append({"id": "D-%s" % d["key"], "kind": "DEFERRED_MODEL", "make": d["make"], "model": d["model"], "impact": 40,
                                "title": "%s %s is on sale but was not processed in this run" % (d["make"], d["model"]),
                                "why": "run limit reached (max_new_models_per_run or --max-models); the next run picks it up",
                                "ops": [], "default": "next run"})
    for it in items:
        if it["kind"] in ("REVIEW_MODEL", "ONE_SITE_ONLY", "DISCONTINUED_CANDIDATE", "UNKNOWN") or it.get("facelift"):
            if it["kind"] == "ONE_SITE_ONLY" and not it["in_kb"] and not (it.get("cw") and it["cw"]["status"] == "current"):
                continue   # listed by CarDekho only (fleet and commercial versions): reported in discovery.json, not a review item
            P["review"].append({
                "id": "M-%s-%s" % (it["make"].split()[0], it["key"]),
                "kind": "FACELIFT" if (it.get("facelift") and it["kind"] == "EXISTING") else it["kind"], "make": it["make"],
                "model": it["model"], "impact": 60 if it["in_kb"] else 20,
                "title": "%s %s: %s" % (it["make"], it["model"], it.get("facelift") or it["reason"]),
                "why": it["reason"], "ops": [], "default": "hold"})
    R["stats"] = P["stats"]

    # outputs of reconciliation
    cs = {"run": run_id, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "observations": {}, "ops": P["ops"]}
    used = {e["obs"] for op in P["ops"] for e in op.get("evidence", [])}
    cs["observations"] = {k: v for k, v in P["obs"].items() if k in used}
    with open(os.path.join(run_dir, "changeset.json"), "w") as f:
        json.dump(cs, f, default=str)
    report.write_tables(run_dir, P)
    pend_obs = {e["obs"] for r in P["review"] for op in r["ops"] for e in op.get("evidence", [])}
    with open(os.path.join(run_dir, "pending.json"), "w") as f:
        json.dump({"run": run_id, "observations": {k: v for k, v in P["obs"].items() if k in pend_obs}, "items": P["review"]}, f, default=str)
    report.write_review(run_dir, run_id, P["review"])

    # 5 gates on staging, then the write
    after_db = before
    if cs["ops"]:
        ok, st = write.stage(cfg, cs, run_dir, before, log)
        R["stage"] = {k: v for k, v in st.items() if k not in ("staging", "before")}
        log("gates", "staging %s: %s" % ("passed" if ok else "FAILED", json.dumps({k: v["ok"] for k, v in st.get("gates", {}).items()})))
        if ok and not no_write:
            try:
                R["write"] = write.promote(cfg, cs, run_dir, st, log)
                after_db = st["staging"]
                for k in bundles_meta:
                    bundles_meta[k]["applied"] = True
                log("write", "KB updated: %s -> %s" % (R["write"]["sha1_before"][:8], R["write"]["sha1_after"][:8]))
            except (kb.Stop, Exception) as e:
                R["stopped"] = "write stopped: %s" % e
                log("stop", R["stopped"])
        elif ok:
            after_db = st["staging"]
            R["stopped"] = "--no-write: staged and gated, the KB was not touched"
        else:
            R["stopped"] = "gates failed on staging; nothing was merged (%s)" % (st.get("error") or
                           "; ".join("%s: %s" % (k, v["detail"][0]) for k, v in st["gates"].items() if not v["ok"]) or "not idempotent")
    else:
        for k in bundles_meta:
            bundles_meta[k]["applied"] = True
        log("write", "nothing to write")
    new_state.update(bundles_meta)
    if not no_write:
        _state(cfg, new_state)

    # 4 final audit (stratified), from the post-run database
    aconn = kb.ro(after_db)
    R["coverage_after"] = report.coverage(aconn)
    do_audit = audit if audit is not None else ("full" if (first_run or full) else "changed")
    cells, lookup = [], None
    if vt and do_audit != "none":
        pop = verify.population(aconn, only_run_methods=(do_audit == "changed"))
        if do_audit == "changed":
            pop = [r for r in pop if str(r["extraction_method"]).endswith("_json") and R["write"]]
        by_kb = {l["kb_variant_id"]: [l["cardekho_url"], l["carwale_url"]] for l in P["links"] if l["kb_variant_id"] != ""}

        def lookup(cell):
            return by_kb.get(cell["variant_id"], [])
        cells, strata = verify.sample(pop, cfg["audit_per_stratum"], cfg["seed"], legacy_lookup=lookup)
        leg = [r for r in pop if r["cls"] == "legacy"]
        R["audit_scope"], R["audit_strata"] = do_audit, strata
        R["audit_legacy"] = {"cells": len(leg), "with_current_page": sum(1 for r in leg if any(lookup(r)))}
        log("verify", "final audit: %d cells from %d strata (population %d)" % (len(cells), len(strata), len(pop)))
        try:
            verify.run(cells, cfg, fetcher, vt, vdir, log, legacy_lookup=lookup, batch="audit")
        except llm.QuotaExhausted as e:
            R["audit_incomplete"] = str(e)
            log("verify", "audit stopped early: %s. Continue with: kbpipe run --audit %s --resume-audit %s" % (e, do_audit, run_dir))
    rows = verify.load(vdir)
    if vt and rows and cfg.get("planted_errors", 20):
        try:
            allc = (cells if (do_audit != "none") else []) + _planned_cells(P["ops"], P["obs"], 0)
            R["planted"] = verify.planted(allc, rows, cfg.get("planted_errors", 20), cfg, fetcher, vt, vdir, log,
                                          legacy_lookup=lookup if do_audit != "none" else None)
            log("verify", "planted-error control: %s" % json.dumps(R["planted"]))
        except llm.QuotaExhausted as e:
            R["planted"] = {"error": str(e)}
    R["verify"] = verify.summarise(rows)
    R["verify_audit_only"] = verify.summarise([r for r in rows if r.get("batch") == "audit"])
    sheet = report.human_sheet(run_dir, rows, cfg)
    if vt:
        calls = vt["text"].calls + vt["image"].calls
        R["llm"] = {"calls": len(calls), "by_model": {}, "seconds": round(sum(c["seconds"] for c in calls), 1), "cost_inr": 0}
        for c in calls:
            R["llm"]["by_model"][c["model"]] = R["llm"]["by_model"].get(c["model"], 0) + 1
    R["fetch"] = fetcher.stats
    R["robots_blocked"] = sorted({u for u, why in getattr(fetcher, "blocks", []) if why == "robots"})
    if R["robots_blocked"]:
        log("fetch", "robots.txt disallows %d address(es) the pipeline needs; nothing was written for them (see run.json robots_blocked)" % len(R["robots_blocked"]))
    R["runtime_seconds"] = round(time.time() - t0, 1)
    R["review_items"] = len(P["review"])
    R["conflicts"] = len(P["conflicts"])
    with open(os.path.join(run_dir, "run.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    report.write_summary(cfg, run_dir, R, P, items, sheet)
    if R["write"]:
        report.append_changelog(cfg, R, P)
    log("done", "%s  (%.0f s)" % (os.path.join(run_dir, "RUN_SUMMARY.md"), time.time() - t0))
    return R


def _verify_batch(cfg, P, mark, fetcher, vt, vdir, R, rng, log):
    cells = _planned_cells(P["ops"], P["obs"], mark)
    mark = len(P["ops"])
    if not cells:
        return mark
    n = max(cfg["verify_batch_min"], int(len(cells) * cfg["verify_batch_fraction"]))
    by = {}
    for c in cells:
        by.setdefault(c["group"], []).append(c)
    pick = []
    for g in sorted(by):                                 # stratified by field group, proportional with a floor
        rows = by[g]
        rng.shuffle(rows)
        pick += rows[:max(3, int(round(n * len(rows) / float(len(cells)))))]
    bno = len(R["verify_batches"]) + 1
    try:
        res = verify.run(pick, cfg, fetcher, vt, vdir, log, batch="batch%d" % bno)
    except llm.QuotaExhausted as e:
        log("verify", "batch %d not verified: %s" % (bno, e))
        R["verify_batches"].append({"batch": bno, "error": str(e)})
        return mark
    s = verify.summarise(res)
    R["verify_batches"].append({"batch": bno, "cells_new": len(cells), "sampled": len(res), "overall": s["overall"], "by_group": s["by_group"]})
    for g, a in s["by_group"].items():
        if a["accuracy"] is not None and (a["match"] + a["mismatch"]) >= cfg["verify_stop_min_n"] and a["accuracy"] < cfg["verify_bar"]:
            R["stopped_groups"][g] = "batch %d: %d of %d matched" % (bno, a["match"], a["match"] + a["mismatch"])
            log("verify", "field group %s stopped: %s" % (g, R["stopped_groups"][g]))
            keys = {c["variant_id"] for c in cells}
            _drop_group(P, [op for op in P["ops"] if "%s|%s|%s" % (op.get("make"), op.get("model"), op.get("variant", op.get("name"))) in keys],
                        g, R["stopped_groups"][g])
            mark = len(P["ops"])
    log("verify", "batch %d: %s" % (bno, json.dumps(s["overall"])))
    return mark


def _drop_group(P, ops, group, why):
    """Remove one field group's new values from `ops` (a slice of P["ops"]). Identity fields stay: without fuel and
    gearbox a variant cannot exist. Values that live on add_variant (drivetrain, engine figures) are blanked too."""
    for op in list(ops):
        if op["op"] == "add_variant":
            if group == "drivetrain":
                op["drivetrain"] = None
            if group == "engine":
                op["powertrain"].update(engine_cc=None, power_bhp=None, torque_nm=None)
        elif op["op"] == "cell" and F.FIELDS[op["field"]][2] == group and op["field"] not in ("fuel_type", "transmission") \
                and op["reason"] != "AGGREGATORS_CONFIRM":
            P["ops"].remove(op)
            P["flags"].append({"make": op["make"], "model": op["model"], "variant": op["variant"], "field": op["field"],
                               "why": "FIELD_GROUP_STOPPED", "detail": why})
