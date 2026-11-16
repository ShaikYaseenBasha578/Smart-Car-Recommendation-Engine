"""`kbpipe update`: the whole update (KB and app) as one resumable chain of stages. See knowledge_base/reports/KB_UPDATE_COMMAND_PLAN.md.

This module is the runner: the stage list, the state file, stop / resume / redo / skip rules. What each stage does lives in
update_stages.py (stages 1-7 and 12, which call the existing pipeline functions) and appstages.py (stages 8-11, the app repository).

Rules (plan section 3):
  * a failed gate stops the update at that stage; later stages stay pending and do not run;
  * a stage that is done is never repeated on --resume (only --redo <stage> repeats it; the final report is always rewritten);
  * a usage-limit or quota stop is recorded as stopped_on_limit with when/how to resume; every LLM answer is cached, so a resume repeats no call;
  * --no-write: every stage runs against staging copies; no KB write, no push, no pull request.
"""
import json
import os
import time
import traceback
from datetime import datetime, timezone

from . import fetch, kb, llm

PENDING, DONE, FAILED, SKIPPED, LIMIT = "pending", "done", "failed", "skipped", "stopped_on_limit"


class Stage:
    def __init__(self, name, num, title, fn, quick_skip=False, always=False):
        self.name, self.num, self.title, self.fn, self.quick_skip, self.always = name, num, title, fn, quick_skip, always


def default_stages():
    from . import appstages, update_stages as S
    return [Stage("preflight", 1, "Preflight", S.preflight),
            Stage("specs", 2, "Specs: new models and variants, prices and specs", S.specs),
            Stage("brochures", 3, "Brochures for new and blank-heavy models", S.brochures, quick_skip=True),
            Stage("reviews", 4, "Reviews: expert scores and owner ratings", S.reviews_numbers),
            Stage("text", 5, "Review text: notes and owner themes", S.reviews_text, quick_skip=True),
            Stage("saved", 6, "Saved Team-BHP pages", S.saved_pages, quick_skip=True),
            Stage("audit", 7, "Audit of what changed", S.audit),
            Stage("export", 8, "Export catalogue and review files to the app", appstages.export),
            Stage("checks", 9, "App checks: tests, evaluation, golden files", appstages.checks),
            Stage("pages", 10, "Project pages", appstages.pages),
            Stage("pr", 11, "Branch, commit, push, pull request", appstages.pull_request),
            Stage("summary", 12, "Final report", S.summary, always=True)]


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve(tokens, stages, flag):
    """['specs', '4'] -> {'specs', 'reviews'}. Raises ValueError on an unknown name."""
    by_name = {s.name: s.name for s in stages}
    by_num = {str(s.num): s.name for s in stages}
    out = set()
    for t in tokens or []:
        for x in str(t).split(","):
            x = x.strip().lower()
            if not x:
                continue
            if x not in by_name and x not in by_num:
                raise ValueError("%s: unknown stage %r (stages: %s)" % (flag, x, ", ".join(s.name for s in stages)))
            out.add(by_name.get(x) or by_num[x])
    return out


class Ctx:
    """What a stage sees."""

    def __init__(self, cfg, update_dir, opts, state, echo, stages):
        self.cfg, self.update_dir, self.opts, self.state, self.echo, self.stages = cfg, update_dir, opts, state, echo, stages
        self.no_write = bool(opts.get("no_write"))
        self.label = state["label"]

    def entry(self, name):
        return self.state["stages"].get(name) or {}

    def data(self, name):
        return self.entry(name).get("data") or {}

    def sub_label(self, name):
        return "%s_%s" % (self.label, name)

    def sub_dir(self, name):
        return os.path.join(self.cfg["runs_dir"], self.sub_label(name))

    @property
    def current_db(self):
        """The KB state the next stage reads. Real mode: the production file (copied by the stage, never opened for writing here).
        --no-write: the latest staging copy, so each stage sees what the earlier ones would have written."""
        return self.state.get("current_db") or self.cfg["prod_db"]

    def stage_cfg(self):
        return dict(self.cfg, prod_db=self.current_db) if self.no_write else self.cfg

    def set_current_db(self, path):
        if self.no_write and path and os.path.exists(path):
            self.state["current_db"] = path

    def log(self, msg):
        self.echo(msg)


def _save(update_dir, state):
    p = os.path.join(update_dir, "state.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True, default=str)
    os.replace(tmp, p)


def load_state(update_dir):
    with open(os.path.join(update_dir, "state.json")) as f:
        return json.load(f)


def latest_update_dir(cfg):
    runs = cfg["runs_dir"]
    c = [d for d in (os.listdir(runs) if os.path.isdir(runs) else []) if d.startswith("update_") and os.path.exists(os.path.join(runs, d, "state.json"))]
    c.sort(key=lambda d: os.path.getmtime(os.path.join(runs, d, "state.json")))
    return os.path.join(runs, c[-1]) if c else None


def resume_command(state):
    return "./bin/kbpipe update --resume --label %s" % state["label"]


LIMIT_ADVICE = ("Wait until the allowance refreshes (free Gemini/Groq quotas reset daily; a Claude usage limit resets at the time its message gives, "
                "see /usage), then run:  %s   Every LLM answer so far is cached, so nothing already paid for is repeated.")


def _kb_sha(cfg):
    try:
        return kb.sha1(cfg["prod_db"])
    except OSError:
        return None


def run(cfg, opts, stages=None, echo=print, sha_fn=None):
    """Run (or resume) an update. Returns (state, exit_code).  exit: 0 all requested stages ok, 1 a stage failed, 2 usage error, 3 stopped on a limit."""
    stages = stages if stages is not None else default_stages()
    sha_fn = sha_fn or (lambda: _kb_sha(cfg))
    try:
        only = resolve(opts.get("only_stages"), stages, "--only-stages")
        skip = resolve(opts.get("skip_stages"), stages, "--skip-stages")
        redo = resolve(opts.get("redo"), stages, "--redo")
    except ValueError as e:
        echo("error: %s" % e)
        return None, 2
    runs = cfg["runs_dir"]
    if opts.get("resume"):
        update_dir = os.path.join(runs, opts["label"]) if opts.get("label") else latest_update_dir(cfg)
        if not update_dir or not os.path.exists(os.path.join(update_dir, "state.json")):
            echo("error: nothing to resume (no %s)" % (os.path.join(update_dir, "state.json") if update_dir else "update_* folder with a state.json in " + runs))
            return None, 2
        state = load_state(update_dir)
        base = dict(state.get("opts") or {})
        for k, v in opts.items():       # a flag given now replaces the stored one; booleans only ever switch on
            if k in ("resume", "label", "only_stages", "redo"):
                continue
            if v not in (None, False, [], ()):
                base[k] = v
        opts = dict(opts, **{k: base.get(k) for k in ("no_write", "quick", "no_pr", "no_verify", "max_models", "skip_stages")})
        skip = resolve(opts.get("skip_stages"), stages, "--skip-stages")
        state["opts"] = {k: opts.get(k) for k in ("no_write", "quick", "no_pr", "no_verify", "max_models", "skip_stages")}
        state.setdefault("resumes", []).append({"at": utc(), "kb_sha1": sha_fn()})
    else:
        base = os.path.join(runs, opts.get("label") or "update_%s" % datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        update_dir, n = base, 1
        while os.path.exists(os.path.join(update_dir, "state.json")):
            if opts.get("label"):
                echo("error: %s already exists. Continue it with --resume --label %s, or pick another --label." % (update_dir, opts["label"]))
                return None, 2
            n += 1
            update_dir = "%s_%d" % (base, n)
        os.makedirs(update_dir, exist_ok=True)
        state = {"version": 1, "label": os.path.basename(update_dir), "created": utc(), "kb_sha1_start": sha_fn(),
                 "opts": {k: opts.get(k) for k in ("no_write", "quick", "no_pr", "no_verify", "max_models", "skip_stages")},
                 "stages": {s.name: {"num": s.num, "title": s.title, "status": PENDING} for s in stages}, "halt": None}
    for s in stages:
        state["stages"].setdefault(s.name, {"num": s.num, "title": s.title, "status": PENDING})
    ctx = Ctx(cfg, update_dir, opts, state, echo, stages)
    mode = "NO-WRITE (nothing is written to the KB, nothing pushed, no pull request)" if ctx.no_write else "WRITE"
    echo("update %s  mode: %s%s" % (state["label"], mode, "  quick" if opts.get("quick") else ""))
    state["halt"] = None
    _save(update_dir, state)
    rc, halted = 0, False
    for st in stages:
        e = state["stages"][st.name]
        if only and st.name not in only:
            continue
        if st.name in redo and e.get("status") != PENDING:
            e["previous"] = {k: e.get(k) for k in ("status", "started", "finished", "result", "run_dir")}
            for k in ("status", "started", "finished", "result", "run_dir", "data", "kb_sha1_before", "kb_sha1_after", "warnings", "seconds"):
                e.pop(k, None)
            e["status"] = PENDING
        reason = None
        if st.name in skip:
            reason = "skipped by --skip-stages"
        elif opts.get("quick") and st.quick_skip:
            reason = "skipped by --quick"
        if reason:
            if e.get("status") != DONE:
                e.update(status=SKIPPED, result=reason)
            echo("[%2d %-10s] %s" % (st.num, st.name, reason))
            _save(update_dir, state)
            continue
        if e.get("status") == DONE and not st.always:
            echo("[%2d %-10s] done earlier; not repeated (%s)" % (st.num, st.name, e.get("result", "")))
            continue
        if halted:
            if e.get("status") in (SKIPPED,):
                e["status"] = PENDING
            continue
        e.update(status="running", started=utc(), kb_sha1_before=sha_fn())
        e.pop("finished", None)
        _save(update_dir, state)
        echo("[%2d %-10s] %s ..." % (st.num, st.name, st.title))
        t0 = time.time()
        try:
            res = st.fn(ctx) or {}
        except llm.QuotaExhausted as ex:
            res = {"status": LIMIT, "result": "usage limit: %s" % str(ex)[:300]}
        except kb.Stop as ex:
            res = {"status": FAILED, "result": "stopped: %s" % ex}
        except Exception as ex:   # a stage must never take the runner down; the traceback goes to the stage log
            with open(os.path.join(update_dir, "errors.log"), "a") as f:
                f.write("== %s %s\n%s\n" % (utc(), st.name, traceback.format_exc()))
            res = {"status": FAILED, "result": "crashed: %s: %s (traceback in %s)" % (type(ex).__name__, str(ex)[:200], os.path.join(update_dir, "errors.log"))}
        status = res.get("status", DONE)
        e.update(status=status, finished=utc(), seconds=round(time.time() - t0, 1), result=res.get("result", ""), kb_sha1_after=sha_fn())
        for k in ("run_dir", "data", "warnings"):
            if res.get(k) is not None:
                e[k] = res[k]
        echo("[%2d %-10s] %s: %s  (%.0f s)" % (st.num, st.name, status, e["result"], e["seconds"]))
        for w in e.get("warnings") or []:
            echo("             warning: %s" % w)
        if status == LIMIT:
            state["halt"] = {"stage": st.name, "kind": LIMIT, "why": e["result"], "resume": resume_command(state),
                             "advice": LIMIT_ADVICE % resume_command(state)}
            echo("STOPPED on a usage limit at stage %d (%s). %s" % (st.num, st.name, state["halt"]["advice"]))
            halted, rc = True, 3
        elif status == FAILED:
            state["halt"] = {"stage": st.name, "kind": FAILED, "why": e["result"], "resume": resume_command(state)}
            echo("STOPPED at stage %d (%s): %s\nLater stages did not run. After fixing the cause: %s" % (st.num, st.name, e["result"], resume_command(state)))
            halted, rc = True, 1
        _save(update_dir, state)
        if halted and st.name != "summary":
            # the report is still written for what ran, so the owner sees where it stopped
            summ = next((s for s in stages if s.always), None)
            if summ and (not only or summ.name in only):
                try:
                    r2 = summ.fn(ctx) or {}
                    state["stages"][summ.name].update(status=PENDING, result=r2.get("result", ""), data=r2.get("data"), run_dir=r2.get("run_dir"))
                except Exception:
                    pass
            _save(update_dir, state)
            break
    _save(update_dir, state)
    return state, rc
