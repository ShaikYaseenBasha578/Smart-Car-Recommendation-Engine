"""Stand-alone audit with resume.

`run()` samples cells from a read copy of the KB (stratified, seeded), sends them to the verifier and appends every verdict to
<run folder>/verify/results.jsonl.  The sample is a pure function of the KB state and the seed, and verify.run skips every
(variant, field) already in results.jsonl, so an interrupted audit continues from its own results: pass `resume=<run folder>`
(CLI: kbpipe run --audit full --resume-audit <run folder>) and no cell is checked twice.

Used by `kbpipe update` stage 7, and by `kbpipe run --resume-audit`."""
import csv
import json
import os
import shutil
from datetime import datetime, timezone

from . import fetch, kb, llm, report, verify


def _links_lookup(folder):
    """kb_variant_id -> [cardekho_url, carwale_url] from <folder>/links.tsv (legacy cells have no URL of their own)."""
    p = os.path.join(folder, "links.tsv") if folder else None
    by = {}
    if p and os.path.exists(p):
        with open(p, newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r.get("kb_variant_id") not in (None, ""):
                    by[r["kb_variant_id"]] = [r.get("cardekho_url", ""), r.get("carwale_url", "")]
    return lambda cell: by.get(cell["variant_id"], [])


def changed_pids(*run_dirs):
    """field_provenance row ids inserted by the given runs (their apply_log.tsv)."""
    out = set()
    for d in run_dirs:
        p = os.path.join(d or "", "apply_log.tsv")
        if d and os.path.exists(p):
            with open(p) as f:
                next(f, None)
                for line in f:
                    t = line.rstrip("\n").split("\t")
                    if len(t) >= 3 and t[0] == "field_provenance" and t[2] == "insert":
                        out.add(int(t[1]))
    return out


def _db_for(cfg, run_dir, db):
    """The KB state to sample from. Explicit `db` wins. In a resumed folder: the staging copy if the run never wrote to prod
    (prod still equals the folder's before.db), else a fresh read copy of prod."""
    if db:
        return db
    before, staging = os.path.join(run_dir, "before.db"), os.path.join(run_dir, "staging.db")
    if os.path.exists(before) and os.path.exists(staging):
        try:
            if kb.sha1(cfg["prod_db"]) == kb.sha1(before):
                return staging
        except OSError:
            pass
    dest = os.path.join(run_dir, "audit_kb.db")
    kb.copy_for_read(cfg["prod_db"], dest)
    return dest


def run(cfg, scope="changed", run_dir=None, label=None, resume=None, db=None, links_dir=None, pids=None, no_verify_backend=None,
        fetcher=None, echo=print):
    """Returns R: {"run_dir", "scope", "cells", "checked_now", "already_done", "verify", "stopped_on_limit", "stopped"}.
    scope: full | changed.  `pids` limits "changed" to those field_provenance ids (the update passes the ids its own runs inserted)."""
    if resume:
        run_dir = os.path.abspath(os.path.expanduser(resume))
        if not os.path.isdir(os.path.join(run_dir, "verify")):
            raise kb.Stop("nothing to resume: %s has no verify/ folder" % run_dir)
        try:
            with open(os.path.join(run_dir, "audit.json")) as f:
                scope = json.load(f).get("scope", scope)
        except (OSError, ValueError):
            pass
    else:
        base = os.path.join(cfg["runs_dir"], label or datetime.now(timezone.utc).strftime("audit_%Y-%m-%d"))
        run_dir, n = base, 1
        while os.path.exists(os.path.join(run_dir, "audit.json")):
            n += 1
            run_dir = "%s_%d" % (base, n)
        os.makedirs(run_dir, exist_ok=True)

    def log(stage, *msg):
        line = "%s [%s] %s" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), stage, " ".join(str(m) for m in msg))
        echo(line)
        with open(os.path.join(run_dir, "run.log"), "a") as f:
            f.write(line + "\n")

    R = {"run_dir": run_dir, "scope": scope, "resumed": bool(resume), "cells": 0, "checked_now": 0, "already_done": 0,
         "stopped_on_limit": None, "stopped": None}
    vdir = os.path.join(run_dir, "verify")
    done_before = {(r["variant_id"], r["field"]) for r in verify.load(vdir)}
    src_db = _db_for(cfg, run_dir, db)
    aconn = kb.ro(src_db)
    pop = verify.population(aconn, only_run_methods=(scope == "changed"))
    if scope == "changed":
        pop = [r for r in pop if (r["pid"] in pids if pids is not None else str(r["extraction_method"]).endswith("_json"))]
    lookup = _links_lookup(links_dir or run_dir)
    cells, strata = verify.sample(pop, cfg["audit_per_stratum"], cfg["seed"], legacy_lookup=lookup)
    R["cells"], R["strata"] = len(cells), strata
    R["already_done"] = sum(1 for c in cells if (c["variant_id"], c["field_name"]) in done_before)
    with open(os.path.join(run_dir, "audit.json"), "w") as f:
        json.dump({"scope": scope, "seed": cfg["seed"], "cells": len(cells), "started": fetch.now_iso(), "db": os.path.basename(src_db)}, f)
    log("audit", "%s audit: %d cells from %d strata; %d already have a verdict%s" % (
        scope, len(cells), len(strata), R["already_done"], " (resumed)" if resume else ""))
    if cells and no_verify_backend is None:
        vt = {"text": llm.get(cfg, "verify", run_dir), "image": llm.get(cfg, "verify_image", run_dir)}
        fetcher = fetcher or fetch.Fetcher(cfg, log=log)
        try:
            R["checked_now"] = len(verify.run(cells, cfg, fetcher, vt, vdir, log, legacy_lookup=lookup, batch="audit"))
        except llm.QuotaExhausted as e:
            R["stopped_on_limit"] = str(e)
            log("audit", "stopped on a usage limit: %s. Resume: kbpipe run --audit %s --resume-audit %s" % (e, scope, run_dir))
        rows = verify.load(vdir)
        if not R["stopped_on_limit"] and rows and cfg.get("planted_errors", 20) and not os.path.exists(os.path.join(vdir, "planted.jsonl")):
            try:
                R["planted"] = verify.planted(cells, rows, cfg.get("planted_errors", 20), cfg, fetcher, vt, vdir, log, legacy_lookup=lookup)
            except llm.QuotaExhausted as e:
                R["stopped_on_limit"] = str(e)
        R["fetch"], R["robots_blocked"] = fetcher.stats, sorted({u for u, w in getattr(fetcher, "blocks", []) if w == "robots"})
    rows = [r for r in verify.load(vdir) if r.get("batch") == "audit"]
    R["verify"] = verify.summarise(rows)
    R["finished"] = fetch.now_iso()
    with open(os.path.join(run_dir, "audit_result.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    if os.path.exists(os.path.join(run_dir, "run.json")) and R["stopped_on_limit"] is None:   # resumed pipeline run: refresh its audit numbers
        try:
            with open(os.path.join(run_dir, "run.json")) as f:
                RJ = json.load(f)
            RJ.pop("audit_incomplete", None)
            RJ["verify_audit_only"] = R["verify"]
            with open(os.path.join(run_dir, "run.json"), "w") as f:
                json.dump(RJ, f, indent=1, default=str)
        except (OSError, ValueError):
            pass
    return R
