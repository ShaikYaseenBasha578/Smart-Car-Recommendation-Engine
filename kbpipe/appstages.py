"""Stages 8-11 of `kbpipe update`: the app repository (config key app_repo).

The app worktree itself is never touched. Every run works in its own clone of the app repository under <cache_dir>/update_ws/<label>/app
(a `git clone --local`), whose branch data/kb-update-<date> starts at origin/main. Stage 8 exports into the clone, stage 9 tests it,
stage 10 regenerates the project pages into it, stage 11 commits only data, golden files and project pages and (outside --no-write)
pushes the branch and opens a pull request. Nothing is ever force-pushed, committed to main or merged.

Pushing and opening the pull request go through `PUBLISHER` (git push / gh), a small object tests replace with a fake."""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone

from . import kb
from .update import DONE, FAILED, SKIPPED

# files a KB update may commit (stage 11); anything else that changed in the clone stops the stage
DATA_FILES = ["data/catalogue_v3/catalogue.csv", "data/catalogue_v3/catalogue_meta.json", "data/assessments.csv",
              "data/owner_ratings.csv", "data/owner_themes.csv"]
PAGE_GLOB = "project_pages/"
GOLDEN_GLOB = "tests/data/golden_"


def sh(args, cwd=None, timeout=3600, env=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class Publisher:
    """The only code that talks to GitHub. Tests substitute a fake with the same two methods."""

    def push(self, ws, branch):
        rc, out = sh(["git", "push", "-u", "origin", branch], cwd=ws)       # never --force
        if rc:
            raise RuntimeError("git push failed: %s" % out.strip()[-400:])
        return out

    def open_pr(self, ws, branch, base, title, body):
        rc, out = sh(["gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body", body], cwd=ws)
        if rc:
            raise RuntimeError("gh pr create failed: %s" % out.strip()[-400:])
        m = re.search(r"https://\S+", out)
        return m.group(0) if m else out.strip()


PUBLISHER = Publisher()


# ---------------------------------------------------------------- helpers
def app_repo(ctx):
    return os.path.abspath(os.path.expanduser(ctx.cfg["app_repo"]))


def app_python(ctx):
    p = os.path.join(app_repo(ctx), ".venv", "bin", "python")
    return ctx.cfg.get("app_python") or (p if os.path.exists(p) else "python3")


def tracked_changes(repo):
    rc, out = sh(["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"])
    return out.strip().splitlines() if rc == 0 else ["(git status failed: %s)" % out.strip()]


def ws_dir(ctx):
    return os.path.join(ctx.cfg["cache_dir"], "update_ws", ctx.label, "app")


def branch_name(ctx):
    day = re.sub(r"[^0-9-]", "", ctx.state["created"][:10])
    return "data/kb-update-%s" % day


def ensure_workspace(ctx):
    """Clone of the app repository on a fresh branch from origin/main. Real mode fetches origin first; --no-write uses the origin/main
    the app repository last fetched (no network). Returns the path."""
    ws, src = ws_dir(ctx), app_repo(ctx)
    branch = ctx.state.get("app_branch") or branch_name(ctx)
    if os.path.isdir(os.path.join(ws, ".git")):
        return ws
    os.makedirs(os.path.dirname(ws), exist_ok=True)
    rc, out = sh(["git", "clone", "--local", "--quiet", "--no-checkout", src, ws])
    if rc:
        raise RuntimeError("cannot clone %s: %s" % (src, out.strip()[-300:]))
    if ctx.no_write:
        rc, out = sh(["git", "fetch", "--quiet", src, "+refs/remotes/origin/main:refs/remotes/origin/main"], cwd=ws)
    else:
        rc, url = sh(["git", "-C", src, "remote", "get-url", "origin"])
        if rc == 0 and url.strip():
            sh(["git", "remote", "set-url", "origin", url.strip()], cwd=ws)    # push goes to the real origin, not to the local app folder
        rc, out = sh(["git", "fetch", "--quiet", "origin"], cwd=ws)
    if rc:
        raise RuntimeError("cannot update origin/main: %s" % out.strip()[-300:])
    rc, out = sh(["git", "checkout", "--quiet", "-b", branch, "origin/main"], cwd=ws)
    if rc:
        raise RuntimeError("cannot create branch %s from origin/main: %s" % (branch, out.strip()[-300:]))
    ctx.state["app_branch"] = branch
    return ws


def kb_read_copy(ctx):
    """The stages' own copy of the KB: a hash-checked copy of prod (real) or of the latest staging copy (--no-write)."""
    dest = os.path.join(ctx.update_dir, "app", "kb_read_copy.db")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if ctx.no_write and ctx.current_db != ctx.cfg["prod_db"]:
        shutil.copyfile(ctx.current_db, dest)
    else:
        kb.copy_for_read(ctx.cfg["prod_db"], dest)
    return dest


def run_eval(ctx, ws, out):
    rc, text = sh([app_python(ctx), "eval/run_eval.py", "--engine", "v3", "--out", out], cwd=ws, timeout=3600)
    return rc, text


def eval_metrics(path):
    try:
        with open(path) as f:
            s = json.load(f)["summary"]
    except (OSError, ValueError, KeyError):
        return {}
    sl = s.get("shortlist_agreement") or {}
    return {"zero_violations": "%s of %s" % (s["constraint_satisfaction"]["queries_zero_violations"], s["constraint_satisfaction"]["queries_with_cars"]),
            "verified": "%s of %s" % ((s.get("verified_satisfaction") or {}).get("queries_verified"), (s.get("verified_satisfaction") or {}).get("queries_with_cars")),
            "recall_at_8": round(sl["recall_at_8"], 4) if sl.get("filled") else "no shortlists", "mrr": round(sl["mrr"], 4) if sl.get("filled") else "no shortlists"}


# ---------------------------------------------------------------- 8
def export(ctx):
    bad = None
    try:
        ws = ensure_workspace(ctx)
    except RuntimeError as e:
        return {"status": FAILED, "result": str(e)}
    py, app_dir = app_python(ctx), os.path.join(ctx.update_dir, "app")
    os.makedirs(app_dir, exist_ok=True)
    sh(["git", "reset", "--hard", "--quiet", "origin/main"], cwd=ws)       # a redo starts from a clean tree
    sh(["git", "clean", "-fdq", "--", "data", "project_pages", "tests/data"], cwd=ws)
    copy = kb_read_copy(ctx)
    base_json = os.path.join(app_dir, "eval_before.json")
    data = {"workspace": ws, "branch": ctx.state["app_branch"], "kb_copy": copy}
    if not ctx.opts.get("skip_baseline"):     # evaluation and golden test on the untouched origin/main checkout, for the before/after
        rc, text = run_eval(ctx, ws, base_json)
        data["eval_before"] = eval_metrics(base_json) if rc == 0 else {}
        rc2, t2 = sh([py, "-m", "pytest", "tests/test_recsys_thin_evidence.py", "-q", "-x", "-p", "no:cacheprovider"], cwd=ws)
        data["baseline_golden_ok"] = rc2 == 0
        with open(os.path.join(app_dir, "baseline_golden.log"), "w") as f:
            f.write(t2)
    steps = [("catalogue", [py, "scripts/export_catalogue_from_kb.py", "--kb", copy, "--out-dir", "data/catalogue_v3"]),
             ("reviews", [py, "scripts/export_reviews_from_kb.py", "--db", copy, "--out-dir", "data"])]
    notes = []
    for name, cmd in steps:
        rc, out = sh(cmd, cwd=ws)
        with open(os.path.join(app_dir, "export_%s.log" % name), "w") as f:
            f.write(out)
        if rc:
            return {"status": FAILED, "data": data, "run_dir": app_dir, "result": "the %s exporter refused (exit %d), nothing was force-written: %s" % (
                name, rc, out.strip().splitlines()[-1][:200] if out.strip() else "no output")}
        notes.append(out.strip().splitlines()[-1] if name == "catalogue" else "; ".join(l for l in out.strip().splitlines() if l.endswith("rows") or "rows," in l)[:160])
    rc, st = sh(["git", "status", "--porcelain"], cwd=ws)
    changed = [l[3:] for l in st.splitlines()]
    data["changed_files"] = changed
    return {"status": DONE, "data": data, "run_dir": app_dir,
            "result": "exported into the workspace (%d file(s) differ from origin/main: %s)" % (len(changed), ", ".join(changed) or "none")}


# ---------------------------------------------------------------- 9
def _detect_dump(raw, obj):
    for ind in (1, 2, None):
        for ea in (True, False):
            for sk in (False, True):
                for end in ("\n", ""):
                    if json.dumps(obj, indent=ind, sort_keys=sk, ensure_ascii=ea) + end == raw:
                        return dict(indent=ind, sort_keys=sk, ensure_ascii=ea), end
    return None, None


def golden_name(n):
    """Golden snapshot file for a catalogue of n variants (same rule as tests/test_recsys_thin_evidence.py)."""
    n = int(n)
    return "golden_empty_evidence.json" if n == 832 else "golden_empty_evidence_%d.json" % n


def golden_template(data_dir, name):
    """The existing golden file to copy the query set and dump format from: the file `name` if present, else the
    golden_empty_evidence_<n>.json with the largest n, else golden_empty_evidence.json. None if there is none."""
    if os.path.exists(os.path.join(data_dir, name)):
        return name
    sized = []
    for f in os.listdir(data_dir) if os.path.isdir(data_dir) else []:
        m = re.fullmatch(r"golden_empty_evidence_(\d+)\.json", f)
        if m:
            sized.append((int(m.group(1)), f))
    if sized:
        return max(sized)[1]
    return "golden_empty_evidence.json" if os.path.exists(os.path.join(data_dir, "golden_empty_evidence.json")) else None


REGEN = r'''
import json, sys
from pathlib import Path
from services.catalogue import get_catalogue
from services.recsys.api import recommend
from services.recsys.evidence import Evidence
n = len(get_catalogue())
# argv: dump kwargs (json), line ending, output file name, template file name (existing golden file with the query set)
kw, end, out_name, tmpl_name = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
p = Path("tests/data") / out_name
old = json.loads((Path("tests/data") / tmpl_name).read_text())
new = {}
for q in sorted(old):
    r = recommend(q, evidence=Evidence())
    new[q] = [{"variant_id": c["variant_id"], "scores": c["scores"], "ranking_score": c["ranking_score"], "criteria": c["criteria"]} for c in r["recommendations"]]
p.write_text(json.dumps(new, **kw) + end)
print(str(p))
'''


def _failed_tests(out):
    return sorted(set(re.findall(r"^FAILED (\S+)", out, re.M)) | set(re.findall(r"^ERROR (\S+)", out, re.M)))


def _pytest(ctx, ws, log):
    rc, out = sh([app_python(ctx), "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", "-rfE"], cwd=ws, timeout=3600)
    with open(log, "w") as f:
        f.write(out)
    last = [l for l in out.strip().splitlines() if l.strip()]
    return rc, out, (last[-1].strip("= ") if last else "no output")


def checks(ctx):
    ws = ctx.data("export").get("workspace") or ws_dir(ctx)
    if not os.path.isdir(os.path.join(ws, ".git")):
        return {"status": FAILED, "result": "no app workspace: stage 8 has not run (run it, or --redo export)"}
    app_dir = os.path.join(ctx.update_dir, "app")
    log1 = os.path.join(app_dir, "tests.log")
    rc, out, tally = _pytest(ctx, ws, log1)
    data = {"tests_log": log1, "tests": tally, "golden_regenerated": [], "eval_before": ctx.data("export").get("eval_before")}
    if rc:
        failed = _failed_tests(out)
        golden_only = failed and all("test_recsys_thin_evidence.py::test_empty_evidence_gives_the_same_results" in t for t in failed)
        catalogue_moved = bool(sh(["git", "diff", "--name-only", "--", "data/catalogue_v3/catalogue.csv"], cwd=ws)[1].strip())
        base_ok = ctx.data("export").get("baseline_golden_ok")
        if not (golden_only and catalogue_moved and base_ok):
            why = ("%d failing test(s), not only the golden snapshot: %s" % (len(failed), ", ".join(failed[:4])) if not golden_only else
                   "golden snapshot differs but the catalogue did not change" if not catalogue_moved else
                   "golden snapshot differs and the untouched origin/main checkout did not pass it first (baseline unknown)")
            return {"status": FAILED, "data": data, "run_dir": app_dir, "result": "app tests failed (%s); golden files NOT regenerated: %s" % (tally, why)}
        # attributable to the catalogue: regenerate the snapshot for this catalogue size and show the diff
        raw_name = sh([app_python(ctx), "-c", "from services.catalogue import get_catalogue;print(len(get_catalogue()))"], cwd=ws)[1].strip().splitlines()[-1]
        gname = golden_name(raw_name)
        tmpl = golden_template(os.path.join(ws, "tests", "data"), gname)
        if not tmpl:
            return {"status": FAILED, "data": data, "result": "no golden file exists in tests/data to take the query set and format from; add one by hand"}
        raw = open(os.path.join(ws, "tests", "data", tmpl)).read()
        kw, end = _detect_dump(raw, json.loads(raw))
        if kw is None:
            return {"status": FAILED, "data": data, "result": "cannot reproduce the format of tests/data/%s; regenerate it by hand" % tmpl}
        rc2, out2 = sh([app_python(ctx), "-c", REGEN, json.dumps(kw), end, gname, tmpl], cwd=ws)
        if rc2:
            return {"status": FAILED, "data": data, "result": "golden regeneration failed: %s" % out2.strip()[-200:]}
        stat = sh(["git", "diff", "--stat", "--", "tests/data/%s" % gname], cwd=ws)[1].strip() or "new file tests/data/%s (format and queries taken from %s)" % (gname, tmpl)
        data["golden_regenerated"] = ["tests/data/%s" % gname]
        data["golden_diff_stat"] = stat
        log2 = os.path.join(app_dir, "tests_after_golden.log")
        rc, out, tally = _pytest(ctx, ws, log2)
        data["tests_log"], data["tests"] = log2, tally + " (after regenerating %s)" % gname
        if rc:
            return {"status": FAILED, "data": data, "run_dir": app_dir, "result": "tests still fail after regenerating the golden file: %s" % ", ".join(_failed_tests(out)[:4])}
    after = os.path.join(app_dir, "eval_after.json")
    rc, text = run_eval(ctx, ws, after)
    data["eval_after"] = eval_metrics(after) if rc == 0 else {}
    data["eval_files"] = after
    if rc:
        return {"status": FAILED, "data": data, "run_dir": app_dir, "result": "evaluation failed: %s" % text.strip()[-200:]}
    b, a = data.get("eval_before") or {}, data["eval_after"]
    return {"status": DONE, "data": data, "run_dir": app_dir,
            "result": "tests %s%s; evaluation zero-violation queries %s -> %s, verified %s -> %s" % (
                tally, ("; golden regenerated: " + ", ".join(data["golden_regenerated"])) if data["golden_regenerated"] else "",
                b.get("zero_violations", "n/a"), a.get("zero_violations"), b.get("verified", "n/a"), a.get("verified"))}


# ---------------------------------------------------------------- 10
def pages(ctx):
    from . import dashboard
    ws = ctx.data("export").get("workspace") or ws_dir(ctx)
    if not os.path.isdir(os.path.join(ws, ".git")):
        return {"status": FAILED, "result": "no app workspace: stage 8 has not run"}
    out_dir = os.path.join(ctx.update_dir, "app", "pages")
    os.makedirs(out_dir, exist_ok=True)
    db = ctx.data("export").get("kb_copy") or kb_read_copy(ctx)
    dashboard.main(["--db", db, "--out-dir", out_dir, "--app-base", "/", "--recsys-dir", ws, "--runs", ctx.cfg["runs_dir"],
                    "--history", ctx.cfg["history_repo"], "--date", ctx.state["created"][:10]])
    rc, out = sh([app_python(ctx), "scripts/sync_project_pages.py", "--src", out_dir], cwd=ws)
    if rc:
        return {"status": FAILED, "result": "sync_project_pages.py failed: %s" % out.strip()[-200:]}
    return {"status": DONE, "run_dir": out_dir, "data": {"pages_dir": out_dir}, "result": "project pages regenerated and synced into the workspace (%s)" % out.strip().splitlines()[-1][:120]}


# ---------------------------------------------------------------- 11
def _allowed(path):
    return path in DATA_FILES or path.startswith(PAGE_GLOB) or (path.startswith(GOLDEN_GLOB) and path.endswith(".json"))


def pr_body(ctx, files):
    ck, ex = ctx.data("checks"), ctx.data("export")
    b, a = ck.get("eval_before") or {}, ck.get("eval_after") or {}
    L = ["Generated by `kbpipe update %s` (KB SHA-1 %s). **Not merged**: merging is the deploy, and stays your decision." % (ctx.label, str(ctx.entry("export").get("kb_sha1_before") or ctx.state.get("kb_sha1_start"))[:8]), "",
         "## What changed", ""] + ["- `%s`" % f for f in files] + ["", "## Checks", "",
         "- App tests: %s" % ck.get("tests", "n/a"),
         "- Evaluation, queries with zero constraint violations: %s -> %s" % (b.get("zero_violations", "n/a"), a.get("zero_violations", "n/a")),
         "- Evaluation, verified satisfaction: %s -> %s" % (b.get("verified", "n/a"), a.get("verified", "n/a")),
         "- Shortlist recall@8 / MRR: %s / %s -> %s / %s" % (b.get("recall_at_8", "n/a"), b.get("mrr", "n/a"), a.get("recall_at_8", "n/a"), a.get("mrr", "n/a"))]
    if ck.get("golden_regenerated"):
        L += ["", "## Golden files regenerated (only the catalogue moved)", ""] + ["- `%s`" % g for g in ck["golden_regenerated"]] + ["", "```", ck.get("golden_diff_stat", ""), "```"]
    L += ["", "## Update stages", ""] + ["- %s %s: %s" % (s.name, ctx.entry(s.name).get("status"), (ctx.entry(s.name).get("result") or "")[:160]) for s in ctx.stages if s.name != "summary" and ctx.entry(s.name).get("status") not in (None, "pending")]
    return "\n".join(L)


def pull_request(ctx):
    src = app_repo(ctx)
    dirty = tracked_changes(src)
    if dirty:
        return {"status": FAILED, "result": "refused: the app worktree %s has uncommitted changes to tracked files (%s). Commit or stash them, then resume with --redo pr." % (src, "; ".join(dirty[:4]))}
    ws = ctx.data("export").get("workspace") or ws_dir(ctx)
    if not os.path.isdir(os.path.join(ws, ".git")):
        return {"status": FAILED, "result": "no app workspace: stage 8 has not run"}
    branch = ctx.state.get("app_branch") or branch_name(ctx)
    rc, cur = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ws)
    if cur.strip() in ("main", "master"):
        return {"status": FAILED, "result": "refused: the workspace is on %s; commits to main are never made" % cur.strip()}
    rc, st = sh(["git", "status", "--porcelain"], cwd=ws)
    changed = [l[3:].strip() for l in st.splitlines()]
    # a catalogue_meta.json that only carries a new timestamp is not a change worth a pull request
    if changed and all(c == "data/catalogue_v3/catalogue_meta.json" for c in changed):
        sh(["git", "checkout", "--", "data/catalogue_v3/catalogue_meta.json"], cwd=ws)
        changed = []
    stray = [c for c in changed if not _allowed(c)]
    if stray:
        return {"status": FAILED, "result": "refused: files outside data, golden files and project pages changed: %s" % ", ".join(stray[:5])}
    ahead = int(sh(["git", "rev-list", "--count", "origin/main..HEAD"], cwd=ws)[1].strip() or 0)
    if not changed and not ahead:
        return {"status": DONE, "result": "the app already has this data; no branch or pull request needed", "data": {"url": None}}
    files = sorted(set(changed) | set(sh(["git", "diff", "--name-only", "origin/main..HEAD"], cwd=ws)[1].split()))
    if changed:
        sh(["git", "add", "--"] + changed, cwd=ws)       # explicit paths only, never -A
        msg = "data: KB update %s\n\nGenerated by kbpipe update %s. Data files, golden files and project pages only." % (ctx.state["created"][:10], ctx.label)
        rc, out = sh(["git", "commit", "--quiet", "-m", msg], cwd=ws)
        if rc:
            return {"status": FAILED, "result": "git commit failed: %s" % out.strip()[-200:]}
    sha = sh(["git", "rev-parse", "--short", "HEAD"], cwd=ws)[1].strip()
    data = {"branch": branch, "commit": sha, "files": files, "url": None}
    if ctx.no_write:
        return {"status": DONE, "data": data, "result": "no-write: committed %d file(s) to %s in the scratch workspace only (%s); nothing pushed, no pull request" % (len(files), branch, sha)}
    if ctx.opts.get("no_pr"):
        return {"status": DONE, "data": data, "result": "--no-pr: committed %d file(s) to %s locally (%s) in %s; not pushed" % (len(files), branch, sha, ws)}
    try:
        PUBLISHER.push(ws, branch)
        data["url"] = PUBLISHER.open_pr(ws, branch, "main", "data: KB update %s" % ctx.state["created"][:10], pr_body(ctx, files))
    except RuntimeError as e:
        return {"status": FAILED, "data": data, "result": "%s (the commit is kept in %s; resume with --redo pr)" % (e, ws)}
    return {"status": DONE, "data": data, "result": "pull request opened: %s (not merged)" % data["url"]}
