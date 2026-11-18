"""Stages 1-7, 12 and 13 of `kbpipe update`. Each takes the runner's Ctx and returns {"status", "result", "run_dir", "data", "warnings"}.
They call the existing functions (pipeline.run, reviews.run, audit.run ...) directly; none of them shells out."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone

from . import audit as audit_mod
from . import fields as F
from . import kb, pipeline, reviews, verify
from .update import DONE, FAILED, LIMIT, SKIPPED

LIMIT_WORDS = re.compile(r"quota|usage limit|rate limit|budget|exhaust|out of", re.I)


def _read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _fold(R, ctx, kind):
    """Common reading of a pipeline.run / reviews.run result. Returns (status, note) or None when the stage is fine."""
    s = R.get("stopped")
    if not s:
        return None
    if s.startswith("--no-write"):
        return None
    return (LIMIT if LIMIT_WORDS.search(s) else FAILED), s


def _blocked(R):
    return sorted(set(R.get("robots_blocked") or [u for u, why in (R.get("blocks") or []) if why == "robots"]))


def _robots_warning(R):
    b = _blocked(R)
    return ["robots.txt disallows %d address(es) this stage needs; nothing was fetched or written for them, and no other identity was tried: %s" % (
        len(b), ", ".join(b[:3]) + (" ..." if len(b) > 3 else ""))] if b else []


def _staging(R, ctx):
    p = (R.get("stage") or {}).get("staging") if isinstance(R.get("stage"), dict) else None
    return p


# ------------------------------------------------------------------ 1
def preflight(ctx):
    cfg = ctx.cfg
    sha = kb.preflight(cfg["prod_db"], for_write=not ctx.no_write)
    warn, data = [], {"kb_sha1": sha}
    free = shutil.disk_usage(os.path.dirname(cfg["cache_dir"]) or "/").free
    need = 6 * os.path.getsize(cfg["prod_db"]) + (2 << 30)
    data["disk_free_gb"] = round(free / 2 ** 30, 1)
    if free < need:
        return {"status": FAILED, "result": "disk: %.1f GB free, %.1f GB needed for copies and staging" % (free / 2 ** 30, need / 2 ** 30), "data": data}
    if not ctx.no_write:
        dest = os.path.join(cfg["backup_dir"], "pre_update_%s_%s.db" % (ctx.label, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
        kb.backup(cfg["prod_db"], dest)
        data["backup"] = dest
    budget = _read_json(os.path.join(cfg["cache_dir"], "llm_budget.json"), {})
    day = time.strftime("%Y-%m-%d", time.gmtime())
    q = {}
    for name, spec in cfg["llm"]["backends"].items():
        used = budget.get("%s/%s" % (name, day), 0)
        if used:
            q[name] = "%d of %d calls today" % (used, spec.get("daily_calls", 0))
            if spec.get("daily_calls") and used > 0.8 * spec["daily_calls"]:
                warn.append("%s is at %d of %d daily calls" % (name, used, spec["daily_calls"]))
    data["llm_budget_today"] = q
    if not ctx.opts.get("quick"):
        for k in ("GEMINI_API_KEY", "GROQ_API_KEY"):
            if not os.environ.get(k):
                warn.append("%s is not set (stages that use the free-tier verifier will stop)" % k)
        if not shutil.which("claude"):
            warn.append("the claude command is not on PATH (brochure and text stages need it)")
    app = os.path.expanduser(cfg["app_repo"])
    if not os.path.isdir(os.path.join(app, ".git")) and not os.path.isfile(os.path.join(app, ".git")):
        warn.append("app_repo %s is not a git checkout; stages 8-11 will fail" % app)
    else:
        dirty = subprocess.run(["git", "-C", app, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout.strip()
        if dirty:
            warn.append("the app worktree %s has uncommitted changes to tracked files; stage 11 will refuse until they are committed or stashed" % app)
    ctx.state["kb_sha1_preflight"] = sha
    return {"status": DONE, "result": "KB free, SHA-1 %s, %.0f GB free%s" % (sha[:8], free / 2 ** 30, "" if ctx.no_write else ", backup written"),
            "data": data, "warnings": warn}


# ------------------------------------------------------------------ 2
def _pipeline_stage(ctx, name, cfg, only=None, full=False, no_verify=True):
    R = pipeline.run(cfg, full=full, max_models=ctx.opts.get("max_models"), only=only, no_write=ctx.no_write,
                     no_verify=no_verify, audit="none", label=ctx.sub_label(name), echo=ctx.echo)
    return R


def op_kinds(changeset_path):
    """Count a change-set's operations by what they do to the KB: fill a blank, change a stored value, only add evidence
    to a value already stored (a confirmation), or something else (new variant, new model, ...)."""
    cs = _read_json(changeset_path, {}) or {}
    out = {"filled": 0, "changed": 0, "confirmed": 0, "other": 0}
    for o in cs.get("ops") or []:
        if o.get("op") != "cell":
            out["other"] += 1
        elif o.get("expect_old") is None:
            out["filled"] += 1
        elif str(o.get("expect_old")) == str(o.get("value")):
            out["confirmed"] += 1
        else:
            out["changed"] += 1
    return out


NEW_MODEL_WORDS = "found on both sites but not in the KB"


def _summarise_pipeline(R, ctx, name):
    """One line a person can read without knowing the internals: what discovery found, and what this stage did to the KB."""
    folder = os.path.join(ctx.cfg["runs_dir"], R["run"])
    disc = dict(R.get("discovery") or {})
    rj = _read_json(os.path.join(folder, "run.json"), {}) or {}
    cb, ca = rj.get("coverage_before") or {}, rj.get("coverage_after") or {}
    added_models = (ca.get("models", 0) - cb.get("models", 0)) if cb and ca else 0
    added_variants = (ca.get("variants", 0) - cb.get("variants", 0)) if cb and ca else 0
    parts = []
    if disc.get("NEW_MODEL"):
        parts.append("%d model(s) %s (%d added)" % (disc.pop("NEW_MODEL"), NEW_MODEL_WORDS, max(added_models, 0)))
    if disc.get("EXISTING"):
        parts.append("%d already in the KB" % disc.pop("EXISTING"))
    rest = ", ".join("%s %d" % (k.lower().replace("_", " "), v) for k, v in sorted(disc.items()) if v)
    found = "discovery: %s%s" % ("; ".join(parts) or "nothing new", ("; other listings: " + rest) if rest else "")
    k = op_kinds(os.path.join(folder, "changeset.json"))
    wrote = R.get("write")
    what = "%d model(s) read; %d blank cell(s) filled, %d stored value(s) changed, %d confirmed by fresh evidence%s" % (
        R.get("processed", 0), k["filled"], k["changed"], k["confirmed"],
        (", %d variant(s) added" % added_variants) if added_variants > 0 else "")
    if wrote:
        b, a = wrote["sha1_before"][:8], wrote["sha1_after"][:8]
        kbtxt = "KB %s -> %s" % (b, a) if b != a else "KB unchanged (%s): everything was already there" % b
    elif (R.get("stopped") or "").startswith("write stopped"):
        kbtxt = "write did not finish: %s" % R["stopped"][15:]
    else:
        kbtxt = "staged only, KB not written" if sum(k.values()) else "nothing to write"
    return folder, "%s. %s. %s" % (found, what, kbtxt)


def specs(ctx):
    cfg = dict(ctx.stage_cfg())
    cfg["brochure"] = dict(cfg.get("brochure", {}), enabled=False)   # brochures are stage 3
    R = _pipeline_stage(ctx, "specs", cfg, no_verify=bool(ctx.opts.get("no_verify")))
    folder, res = _summarise_pipeline(R, ctx, "specs")
    st = _fold(R, ctx, "specs")
    blocked = _blocked(R)
    # a source whose every brand page is refused by robots.txt is unreadable: say so plainly and stop
    from .sources import carwale, cardekho
    dead = [m.NAME for m in (carwale, cardekho) if blocked and all(m.brand_url(mk) in blocked for mk in cfg["scope_makes"])]
    data = {"run": R["run"], "ops": (R.get("stage") or {}).get("ops", 0), "wrote": bool(R.get("write")),
            "new_models": (R.get("discovery") or {}).get("NEW_MODEL", 0), "review_items": R.get("review_items", 0), "robots_blocked": blocked}
    ctx.set_current_db(_staging(R, ctx))
    if dead:
        return {"status": FAILED, "run_dir": folder, "data": data, "warnings": _robots_warning(R),
                "result": "robots.txt disallows every brand page of %s for this tool's identity; nothing was read or written for it" % ", ".join(dead)}
    if st:
        return {"status": st[0], "run_dir": folder, "data": data, "result": st[1][:300], "warnings": _robots_warning(R)}
    return {"status": DONE, "run_dir": folder, "result": res, "data": data, "warnings": _robots_warning(R)}


# ------------------------------------------------------------------ 3
def blank_heavy(db, threshold, limit):
    """Models whose variants leave more than `threshold` of the variant cells blank, worst first (read-only)."""
    c = kb.ro(db)
    cols = [r[1] for r in c.execute("pragma table_info(variant)")]
    fs = [f for f in F.VARIANT_FIELDS if f in cols]
    if not fs:
        return []
    expr = "+".join('(v."%s" is null)' % f for f in fs)
    rows = c.execute("select mo.name, sum(%s)*1.0/(count(*)*%d) as blank from variant v join model mo on mo.id=v.model_id "
                     "where v.base_variant_id is null group by mo.id having blank > ? order by blank desc limit ?" % (expr, len(fs)),
                     (threshold, limit)).fetchall()
    c.close()
    return [(r[0], round(r[1], 3)) for r in rows]


def brochures(ctx):
    up = ctx.cfg.get("update", {})
    new = []
    d = _read_json(os.path.join(ctx.sub_dir("specs"), "discovery.json"), [])
    new = sorted({it["model"] for it in d if it.get("kind") == "NEW_MODEL"})
    sparse = blank_heavy(ctx.current_db if ctx.no_write else _copy_prod(ctx, "blank_scan.db"), up.get("blank_threshold", 0.5), up.get("brochure_blank_models", 10))
    models = new + [m for m, _ in sparse if m not in new]
    if not models:
        return {"status": DONE, "result": "no new models and none with many blanks; nothing to read", "data": {"models": []}}
    cfg = dict(ctx.stage_cfg())
    cfg["brochure"] = dict(cfg.get("brochure", {}), enabled=True)
    R = _pipeline_stage(ctx, "brochures", cfg, only=models, full=True, no_verify=True)
    folder, res = _summarise_pipeline(R, ctx, "brochures")
    bro = _read_json(os.path.join(folder, "brochure", "summary.json"), {})
    limited = [k for k, v in bro.items() if "LLM quota or usage limit" in str(v.get("status") or "")]
    kept = sum((v.get("cells_kept") or 0) for v in bro.values())
    data = {"run": R["run"], "models": models, "cells_kept": kept, "ops": (R.get("stage") or {}).get("ops", 0)}
    ctx.set_current_db(_staging(R, ctx))
    st = _fold(R, ctx, "brochures")
    if limited:
        return {"status": LIMIT, "run_dir": folder, "data": data, "result": "brochure layer stopped on an LLM limit after %d of %d model(s) (%s)" % (len(bro) - len(limited), len(models), bro[limited[0]]["status"][:120])}
    if st:
        return {"status": st[0], "run_dir": folder, "data": data, "result": st[1][:300]}
    return {"status": DONE, "run_dir": folder, "data": data, "result": "brochures read for %d model(s) (%d not yet in the KB, %d with many blank cells); %d cell value(s) read and confirmed by the checker. %s" % (len(models), len(new), len(models) - len(new), kept, res)}


def _copy_prod(ctx, name):
    dest = os.path.join(ctx.update_dir, name)
    kb.copy_for_read(ctx.cfg["prod_db"], dest)
    return dest


# ------------------------------------------------------------------ 4, 5, 6
def _reviews_stage(ctx, name, no_text):
    cfg = ctx.stage_cfg()
    R = reviews.run(cfg, no_write=ctx.no_write, label=ctx.sub_label(name), no_text=no_text, echo=ctx.echo)
    folder = os.path.join(ctx.cfg["runs_dir"], R["run"])
    ctx.set_current_db(_staging(R, ctx))
    ts = R.get("text_stopped")
    nc = {k: "%d of %d re-checked values agree" % (v.get("ok", 0), v.get("checked", 0)) for k, v in (R.get("numbers_check") or {}).items()}
    data = {"run": R["run"], "models": len(R.get("models") or {}), "numbers_check": R.get("numbers_check"), "text": R.get("text"),
            "ops": (R.get("stage") or {}).get("ops", 0), "wrote": bool(R.get("write")), "llm_calls": R.get("llm_calls", 0)}
    warn = _robots_warning(R)
    if ts:
        status = LIMIT if LIMIT_WORDS.search(str(ts.get("why", ""))) else FAILED
        return {"status": status, "run_dir": folder, "data": data, "warnings": warn,
                "result": "text stopped (%s: %s) at %s; %d model(s) not reached" % (ts["role"], str(ts["why"])[:120], ts["at"], len(R.get("not_reached") or []))}
    st = _fold(R, ctx, name)
    if st:
        return {"status": st[0], "run_dir": folder, "data": data, "result": st[1][:300], "warnings": warn}
    return {"status": DONE, "run_dir": folder, "data": data, "warnings": warn,
            "result": "%d model(s) read, %d change(s) %s; %s" % (data["models"], data["ops"], "written" if data["wrote"] else "staged", "; ".join(nc.values()) or "no numbers re-check")}


def reviews_numbers(ctx):
    return _reviews_stage(ctx, "reviews", no_text=True)


def reviews_text(ctx):
    return _reviews_stage(ctx, "text", no_text=False)


def _saved_new_files(cfg):
    folder = os.path.expanduser(cfg["reviews"]["saved_pages_dir"])
    done = _read_json(os.path.join(cfg["cache_dir"], "saved_pages_imported.json"), {})
    new = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith((".html", ".htm")):
                with open(os.path.join(folder, fn), "rb") as f:
                    h = hashlib.sha1(f.read()).hexdigest()
                if done.get(fn) != h:
                    new.append((fn, h))
    return folder, new


def saved_pages(ctx):
    folder, new = _saved_new_files(ctx.cfg)
    if not new:
        return {"status": DONE, "result": "no new saved pages in %s; nothing to read" % folder, "data": {"new_files": 0}}
    R = reviews.import_saved(ctx.stage_cfg(), folder, no_write=ctx.no_write, label=ctx.sub_label("saved"), ask=None, echo=ctx.echo)
    folder_run = os.path.join(ctx.cfg["runs_dir"], R["run"])
    st = _fold(R, ctx, "saved")
    ctx.set_current_db(_staging(R, ctx))
    if st:
        return {"status": st[0], "run_dir": folder_run, "result": st[1][:300], "data": {"new_files": len(new)}}
    if R.get("write"):
        p = os.path.join(ctx.cfg["cache_dir"], "saved_pages_imported.json")
        done = _read_json(p, {})
        done.update(dict(new))
        with open(p, "w") as f:
            json.dump(done, f, indent=1)
    return {"status": DONE, "run_dir": folder_run, "data": {"new_files": len(new)},
            "result": "%d new saved page(s) read; %s" % (len(new), "written" if R.get("write") else "staged only")}


# ------------------------------------------------------------------ 7
def audit(ctx):
    if ctx.opts.get("no_verify"):
        return {"status": SKIPPED, "result": "--no-verify: no verifier calls, so nothing to audit"}
    dirs = [ctx.sub_dir(n) for n in ("specs", "brochures", "reviews", "text", "saved")]
    pids = audit_mod.changed_pids(*dirs)
    if not pids:
        return {"status": DONE, "result": "nothing was added to the KB's evidence in this update, so there is nothing to audit", "data": {"cells": 0}}
    prev = ctx.entry("audit").get("data") or {}
    resume = prev.get("run_dir") if ctx.entry("audit").get("status") in (LIMIT, FAILED) and prev.get("run_dir") else None
    db = ctx.current_db if ctx.no_write else None
    R = audit_mod.run(ctx.cfg, scope="changed", label=ctx.sub_label("audit"), resume=resume, db=db or _copy_prod(ctx, "audit_kb.db"),
                      links_dir=ctx.sub_dir("specs"), pids=pids, echo=ctx.echo)
    ov = (R.get("verify") or {}).get("overall") or {}
    data = {"run_dir": R["run_dir"], "cells": R["cells"], "checked_now": R["checked_now"], "overall": ov, "by_group": (R.get("verify") or {}).get("by_group")}
    warn = _robots_warning(R)
    if R.get("stopped_on_limit"):
        return {"status": LIMIT, "run_dir": R["run_dir"], "data": data, "warnings": warn,
                "result": "audit stopped on a limit after %d of %d cells (%s); resume continues from results.jsonl" % (R["already_done"] + R["checked_now"], R["cells"], R["stopped_on_limit"][:100])}
    bar = ctx.cfg["verify_bar"]
    low = [g for g, a in ((R.get("verify") or {}).get("by_group") or {}).items() if a.get("accuracy") is not None and a["match"] + a["mismatch"] >= ctx.cfg["verify_stop_min_n"] and a["accuracy"] < bar]
    if ov.get("accuracy") is not None and ov["accuracy"] < bar or low:
        return {"status": FAILED, "run_dir": R["run_dir"], "data": data, "warnings": warn,
                "result": "audit below the %.0f%% bar: overall %s, groups below the bar: %s" % (100 * bar, ov.get("accuracy"), ", ".join(low) or "none")}
    return {"status": DONE, "run_dir": R["run_dir"], "data": data, "warnings": warn,
            "result": "%d cell(s) audited, accuracy %s (match %d, mismatch %d, unreachable %d)" % (R["cells"], ov.get("accuracy"), ov.get("match", 0), ov.get("mismatch", 0), ov.get("unreachable", 0))}


# ------------------------------------------------------------------ 12
# ------------------------------------------------------------------ 12
def images(ctx):
    """Photo candidates from the makers' brochures on disk for catalogue models that have no photo. Local files only: nothing is
    fetched, no model is called, and nothing is written outside the run folder. A person picks; `python -m kbpipe.images --apply`
    then writes the app's image and manifest row."""
    try:
        from . import images as I
    except ImportError as ex:
        return {"status": SKIPPED, "result": "skipped: %s is not installed (pip install -r kbpipe/requirements.txt)" % (getattr(ex, "name", None) or ex),
                "warnings": ["photo candidates were not prepared: %s" % ex]}
    ws = ctx.data("export").get("workspace")
    repo = ws if ws and os.path.isdir(ws) else os.path.expanduser(ctx.cfg["app_repo"])
    if not os.path.exists(I.manifest_path(repo)):
        return {"status": SKIPPED, "result": "skipped: no data/image_manifest.csv in %s" % repo}
    if not I.models_without_image(repo):
        return {"status": DONE, "result": "every catalogue model has a photo", "data": {"models": 0}}
    out = I.stage(ctx.cfg, ctx.update_dir, catalogue_repo=repo)
    folder = out["run_dir"]
    data = {"models": out["models"], "need_human": out["need_human"], "no_candidate": out["no_candidate"], "no_brochure": out["no_brochure"],
            "contact_sheet": os.path.join(folder, "contact_sheet.html"), "picks": os.path.join(folder, "picks.json")}
    return {"status": DONE, "run_dir": folder, "data": data,
            "result": "%d model(s) have candidates for you to pick from; %d have a brochure with no usable picture; %d have no brochure on disk" % (
                len(out["need_human"]), len(out["no_candidate"]), len(out["no_brochure"]))}


def _tsv_count(path, col):
    out = {}
    try:
        with open(path) as f:
            hdr = next(f).rstrip("\n").split("\t")
            i = hdr.index(col)
            for line in f:
                t = line.rstrip("\n").split("\t")
                if len(t) > i:
                    out[t[i]] = out.get(t[i], 0) + 1
    except (OSError, ValueError, StopIteration):
        pass
    return out


def _cs_counts(path):
    cs = _read_json(path, {})
    c = {}
    for op in cs.get("ops", []):
        k = op.get("op")
        if k == "cell":
            k = "cell:%s" % op.get("reason", "")
            if op.get("field") == "price_ex_showroom" and op.get("expect_old") is not None:
                c["price changes"] = c.get("price changes", 0) + 1
        c[k] = c.get(k, 0) + 1
    return c


def summary(ctx):
    L = ["# Update %s" % ctx.label, "", "Started %s. Mode: %s%s. KB SHA-1 at start: `%s`." % (
        ctx.state.get("created"), "no-write (nothing written, pushed or opened)" if ctx.no_write else "write",
        ", quick" if ctx.opts.get("quick") else "", str(ctx.state.get("kb_sha1_start"))[:8]), ""]
    rel = lambda p: os.path.relpath(p, os.path.dirname(ctx.cfg["runs_dir"])) if p and p.startswith(os.path.dirname(ctx.cfg["runs_dir"])) else (p or "")
    L += ["## Stages", "", "| # | Stage | Status | Result | Source |", "|---|---|---|---|---|"]
    names = [s.name for s in ctx.stages]
    for s in ctx.stages:
        e = ctx.entry(s.name)
        L.append("| %d | %s | %s | %s | %s |" % (s.num, s.name, e.get("status", "pending"), (e.get("result") or "").replace("|", "/")[:200],
                                                 "`%s`" % rel(e.get("run_dir")) if e.get("run_dir") else "`state.json`"))
    L.append("")
    # what was added
    L += ["## What changed in the KB", ""]
    any_run = False
    for n in ("specs", "brochures", "reviews", "text", "saved"):
        d = ctx.sub_dir(n)
        rj = _read_json(os.path.join(d, "run.json"))
        if not rj:
            continue
        any_run = True
        cb, ca = rj.get("coverage_before"), rj.get("coverage_after")
        cs = _cs_counts(os.path.join(d, "changeset.json"))
        pre = "`%s`" % rel(os.path.join(d, "run.json"))
        if cb and ca:
            L.append("- **%s** (source: %s): models %d -> %d, variants %d -> %d, filled cells %d -> %d. Change-set (source: `%s`): %s." % (
                n, pre, cb["models"], ca["models"], cb["variants"], ca["variants"], cb["cells_filled"], ca["cells_filled"],
                rel(os.path.join(d, "changeset.json")), (lambda k: "%d blank cell(s) filled, %d stored value(s) changed, %d confirmed by fresh evidence, %d other" % (
                    k["filled"], k["changed"], k["confirmed"], k["other"]))(op_kinds(os.path.join(d, "changeset.json"))) if cs else "no operations"))
        else:
            L.append("- **%s** (source: %s): %d change(s) %s." % (n, pre, (rj.get("stage") or {}).get("ops", 0), "written" if rj.get("write") else "staged"))
        by_src = {}
        for op in _read_json(os.path.join(d, "changeset.json"), {}).get("ops", []):
            for ev in op.get("evidence", []) or []:
                o = (_read_json(os.path.join(d, "changeset.json"), {}).get("observations") or {}).get(ev.get("obs"), {})
                if ev.get("decision") == "accepted" and o.get("source"):
                    by_src[o["source"]] = by_src.get(o["source"], 0) + 1
        if by_src:
            L.append("  - cells by accepted source: %s (source: `%s`)" % (", ".join("%s %d" % kv for kv in sorted(by_src.items())), rel(os.path.join(d, "changeset.json"))))
    if not any_run:
        L.append("No stage that changes the KB has run yet.")
    L.append("")
    # verification
    L += ["## Verification", ""]
    a = ctx.data("audit")
    if a.get("cells") is not None and a.get("overall"):
        ov = a["overall"]
        L.append("- Audit of this update (bar %.0f%%; source: `%s`): %s over %d cells (match %d, mismatch %d, unreachable %d, verifier errors %d)." % (
            100 * ctx.cfg["verify_bar"], rel(os.path.join(a.get("run_dir", ""), "audit_result.json")),
            "%.1f%%" % (100 * ov["accuracy"]) if ov.get("accuracy") is not None else "no accuracy yet", a["cells"], ov.get("match", 0),
            ov.get("mismatch", 0), ov.get("unreachable", 0), ov.get("verifier_error", 0)))
    else:
        L.append("- Audit: %s" % (ctx.entry("audit").get("result") or "not run"))
    for n in ("reviews", "text"):
        d = ctx.data(n)
        for src, t in (d.get("numbers_check") or {}).items():
            if t.get("checked"):
                L.append("- Review numbers, %s (bar %.0f%%; source: `%s`): %d of %d re-checked values agree." % (
                    src, 100 * ctx.cfg["reviews"]["numbers_bar"], rel(os.path.join(ctx.sub_dir(n), "run.json")), t["ok"], t["checked"]))
        for src, t in (d.get("text") or {}).items():
            if t.get("verified"):
                L.append("- Review text, %s (bar %.0f%%; source: `%s`): %d of %d checked claims supported." % (
                    src, 100 * ctx.cfg["reviews"]["verify_bar"], rel(os.path.join(ctx.sub_dir(n), "run.json")), t["ok"], t["verified"]))
    L.append("")
    # evaluation
    ev = ctx.data("checks")
    L += ["## App evaluation (before -> after)", ""]
    if ev.get("eval_before") or ev.get("eval_after"):
        b, af = ev.get("eval_before") or {}, ev.get("eval_after") or {}
        for k, lab in (("zero_violations", "constraint satisfaction (queries with zero violations)"), ("verified", "verified satisfaction"),
                       ("recall_at_8", "shortlist recall@8"), ("mrr", "shortlist MRR")):
            L.append("- %s: %s -> %s (source: `%s`)" % (lab, b.get(k, "n/a"), af.get(k, "n/a"), rel(ev.get("eval_files", ""))))
        L.append("- App tests: %s (source: `%s`)" % (ev.get("tests", "n/a"), rel(ev.get("tests_log", ""))))
        if ev.get("golden_regenerated"):
            L.append("- Golden files regenerated: %s" % ", ".join(ev["golden_regenerated"]))
    else:
        L.append("- %s" % (ctx.entry("checks").get("result") or "not run"))
    L.append("")
    # withheld
    L += ["## Withheld and why", ""]
    flags = {}
    for n in ("specs", "brochures"):
        for k, v in _tsv_count(os.path.join(ctx.sub_dir(n), "flags.tsv"), "why").items():
            flags[k] = flags.get(k, 0) + v
    if flags:
        L.append("- Cells left blank (source: `flags.tsv` of the specs and brochure runs): %s." % ", ".join("%s %d" % kv for kv in sorted(flags.items(), key=lambda kv: -kv[1])[:8]))
    else:
        L.append("- No flags file yet.")
    items = ctx.data("specs").get("review_items")
    L += ["", "## What needs you", ""]
    revs = [n for n in ("specs", "brochures", "reviews", "text", "saved") if os.path.exists(os.path.join(ctx.sub_dir(n), "pending.json"))]
    for n in revs:
        pend = _read_json(os.path.join(ctx.sub_dir(n), "pending.json"), {})
        mdf = [f for f in os.listdir(ctx.sub_dir(n)) if f.startswith("REVIEW_")]
        if mdf:
            L.append("- %s: %d review item(s) in `%s` (source: `%s`). Tick them, then run `kbpipe apply-review <file>` and `%s`." % (
                n, len(pend.get("items") or []), rel(os.path.join(ctx.sub_dir(n), mdf[0])), rel(os.path.join(ctx.sub_dir(n), "pending.json")), "./bin/kbpipe update --resume --redo export --label %s" % ctx.label))
    im = ctx.data("images")
    if im.get("need_human"):
        L.append("- Photos: %d model(s) have brochure pictures to choose from. Open `%s`, set \"choice\" to 1, 2 or 3 in `%s` (leave null to keep the placeholder), "
                 "then run `python -m kbpipe.images --apply %s` and open a pull request for the app." % (
                     len(im["need_human"]), rel(im["contact_sheet"]), rel(im["picks"]), im["picks"]))
    if im.get("no_brochure") or im.get("no_candidate"):
        L.append("- Photos: no brochure picture for %s; they keep the placeholder." % ", ".join((im.get("no_brochure") or []) + (im.get("no_candidate") or [])))
    if not revs and not im.get("need_human"):
        L.append("- No review file was produced yet.")
    L += ["", "## Pull request", ""]
    pr = ctx.data("pr")
    L.append("- %s" % (pr.get("url") or ctx.entry("pr").get("result") or "not reached"))
    L += ["", "## Warnings", ""]
    ws = [(n, w) for n in names for w in (ctx.entry(n).get("warnings") or [])]
    L += ["- %s: %s" % w for w in ws] or ["- none"]
    halt = ctx.state.get("halt")
    L += ["", "## Stopped?", ""]
    if halt:
        L += ["- Stage **%s** %s: %s" % (halt["stage"], halt["kind"], halt["why"]), "- Resume with exactly: `%s`" % halt["resume"]]
        if halt.get("advice"):
            L.append("- %s" % halt["advice"])
    else:
        pend = [s.name for s in ctx.stages if ctx.entry(s.name).get("status") in ("pending", "running") and s.name != "summary"]
        if pend:
            L.append("- Not run yet: %s. Continue with: `%s`" % (", ".join(pend), "./bin/kbpipe update --resume --label %s" % ctx.label))
        else:
            L.append("- Nothing stopped.")
    path = os.path.join(ctx.update_dir, "UPDATE_SUMMARY.md")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    ctx.echo("\n".join(L))
    return {"status": DONE, "result": "written", "run_dir": ctx.update_dir, "data": {"path": path}}
