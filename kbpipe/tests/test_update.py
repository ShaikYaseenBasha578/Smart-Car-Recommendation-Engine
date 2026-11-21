"""kbpipe update: runner rules (stop, resume, redo, skip, only, limit), --no-write spies, stage 11 against a fake publisher and a real
throwaway git repository, audit resume, and the spec fetcher's robots handling."""
import json
import os
import subprocess
import types

import pytest

from kbpipe import appstages, audit, fetch, llm, update, update_stages, verify, write
from kbpipe.update import DONE, FAILED, LIMIT, PENDING, SKIPPED, Stage


# ------------------------------------------------------------------ runner
def fake_stages(calls, behave=None):
    behave = behave or {}

    def mk(name, num, **kw):
        def fn(ctx):
            calls.append(name)
            b = behave.get(name)
            if callable(b):
                return b(ctx)
            return b or {"status": DONE, "result": "ok %s" % name}
        return Stage(name, num, name.title(), fn, **kw)
    return [mk("preflight", 1), mk("specs", 2), mk("brochures", 3, quick_skip=True), mk("reviews", 4), mk("text", 5, quick_skip=True),
            mk("audit", 7), mk("export", 8), mk("pr", 11), mk("summary", 12, always=True)]


def opts(**kw):
    base = dict(no_write=False, resume=False, only_stages=None, skip_stages=None, max_models=None, no_pr=False, quick=False,
                redo=None, label="u1", no_verify=False)
    base.update(kw)
    return base


def run(cfg, calls, behave=None, **kw):
    return update.run(cfg, opts(**kw), stages=fake_stages(calls, behave), echo=lambda *_: None, sha_fn=lambda: "abc123")


def test_all_stages_run_in_order_and_state_round_trips(cfg):
    calls = []
    state, rc = run(cfg, calls)
    assert rc == 0 and calls == ["preflight", "specs", "brochures", "reviews", "text", "audit", "export", "pr", "summary"]
    on_disk = update.load_state(os.path.join(cfg["runs_dir"], "u1"))
    assert on_disk == json.loads(json.dumps(state, default=str))
    e = on_disk["stages"]["specs"]
    assert e["status"] == DONE and e["started"] and e["finished"] and e["kb_sha1_before"] == "abc123" and e["kb_sha1_after"] == "abc123"


def test_failed_gate_stops_and_later_stages_do_not_run(cfg):
    calls = []
    state, rc = run(cfg, calls, {"reviews": {"status": FAILED, "result": "gate: schema changed"}})
    assert rc == 1
    assert calls[:4] == ["preflight", "specs", "brochures", "reviews"] and "audit" not in calls and "export" not in calls and "pr" not in calls
    assert state["stages"]["audit"]["status"] == PENDING and state["stages"]["reviews"]["status"] == FAILED
    assert state["halt"]["stage"] == "reviews" and "--resume --label u1" in state["halt"]["resume"]


def test_resume_never_repeats_done_stages_and_retries_the_failed_one(cfg):
    calls = []
    run(cfg, calls, {"reviews": {"status": FAILED, "result": "x"}})
    calls.clear()
    state, rc = update.run(cfg, opts(resume=True), stages=fake_stages(calls), echo=lambda *_: None, sha_fn=lambda: "abc123")
    assert rc == 0
    assert calls == ["reviews", "text", "audit", "export", "pr", "summary"]       # preflight, specs, brochures were done: not repeated
    assert state["halt"] is None and len(state["resumes"]) == 1


def test_resume_without_label_takes_the_latest_update(cfg):
    run(cfg, [], label="update_2026-01-01")
    calls = []
    _, rc = update.run(cfg, opts(resume=True, label=None), stages=fake_stages(calls), echo=lambda *_: None, sha_fn=lambda: "x")
    assert rc == 0 and calls == ["summary"]      # everything else done; the report is always rewritten


def test_resume_with_nothing_to_resume(cfg):
    _, rc = update.run(cfg, opts(resume=True, label="nope"), stages=fake_stages([]), echo=lambda *_: None, sha_fn=lambda: "x")
    assert rc == 2


def test_redo_repeats_only_that_stage(cfg):
    calls = []
    run(cfg, calls)
    calls.clear()
    state, _ = update.run(cfg, opts(resume=True, redo=["specs"]), stages=fake_stages(calls), echo=lambda *_: None, sha_fn=lambda: "x")
    assert calls == ["specs", "summary"]
    assert state["stages"]["specs"]["previous"]["status"] == DONE


def test_skip_stages_only_stages_and_quick(cfg):
    calls = []
    state, _ = run(cfg, calls, skip_stages=["reviews,audit"], quick=True, label="a")
    assert calls == ["preflight", "specs", "export", "pr", "summary"]
    assert state["stages"]["reviews"]["status"] == SKIPPED and state["stages"]["brochures"]["result"] == "skipped by --quick"
    calls.clear()
    state, _ = run(cfg, calls, only_stages=["specs", "4"], label="b")
    assert calls == ["specs", "reviews"]
    assert state["stages"]["export"]["status"] == PENDING          # untouched, not marked skipped
    calls.clear()
    update.run(cfg, opts(resume=True, label="b"), stages=fake_stages(calls), echo=lambda *_: None, sha_fn=lambda: "x")
    assert calls == ["preflight", "brochures", "text", "audit", "export", "pr", "summary"]


def test_unknown_stage_name_is_a_usage_error(cfg):
    _, rc = run(cfg, [], only_stages=["bogus"])
    assert rc == 2


def test_existing_label_without_resume_is_refused(cfg):
    run(cfg, [])
    _, rc = run(cfg, [])
    assert rc == 2


def test_stopped_on_limit_is_recorded_with_resume_advice_and_exit_3(cfg):
    calls = []

    def boom(ctx):
        raise llm.QuotaExhausted("claude_sonnet: daily call budget (1000) reached")
    state, rc = run(cfg, calls, {"text": boom})
    assert rc == 3 and state["stages"]["text"]["status"] == LIMIT
    h = state["halt"]
    assert h["kind"] == LIMIT and "./bin/kbpipe update --resume --label u1" in h["advice"] and "cached" in h["advice"]
    assert "audit" not in calls
    # also when the stage itself returns the status
    state, rc = run(cfg, [], {"reviews": {"status": LIMIT, "result": "text stopped"}}, label="u2")
    assert rc == 3 and state["halt"]["stage"] == "reviews"


def test_crashing_stage_is_failed_not_fatal(cfg):
    def boom(ctx):
        raise ValueError("bad")
    state, rc = run(cfg, [], {"specs": boom})
    assert rc == 1 and state["stages"]["specs"]["status"] == FAILED and "ValueError" in state["stages"]["specs"]["result"]
    assert os.path.exists(os.path.join(cfg["runs_dir"], "u1", "errors.log"))


def test_no_write_flag_reaches_every_stage_and_is_kept_on_resume(cfg):
    seen = []

    def spy(ctx):
        seen.append(ctx.no_write)
        return {"status": DONE, "result": "x"}
    run(cfg, [], {n: spy for n in ("specs", "reviews", "pr")}, no_write=True)
    assert seen == [True, True, True]
    seen.clear()
    update.run(cfg, opts(resume=True, redo=["specs"]), stages=fake_stages([], {"specs": spy}), echo=lambda *_: None, sha_fn=lambda: "x")
    assert seen == [True]      # the stored no_write survives --resume


# ------------------------------------------------------------------ --no-write never reaches a write path (real stage functions, spies)
def test_no_write_never_calls_a_write_path(cfg, monkeypatch, tmp_path):
    def forbid(*a, **k):
        raise AssertionError("write path called under --no-write")
    monkeypatch.setattr(write, "promote", forbid)
    monkeypatch.setattr(appstages.PUBLISHER, "push", forbid)
    monkeypatch.setattr(appstages.PUBLISHER, "open_pr", forbid)
    got = {}

    def fake_pipeline(cfg_, **kw):
        got.setdefault("pipeline", []).append(kw)
        return {"run": kw["label"], "stopped": "--no-write: staged and gated, the KB was not touched", "write": None, "discovery": {"EXISTING": 3},
                "processed": 3, "stage": {"ops": 2}}

    def fake_reviews(cfg_, **kw):
        got.setdefault("reviews", []).append(kw)
        return {"run": kw["label"], "stopped": None, "write": None, "models": {}, "numbers_check": {}, "stage": None}
    monkeypatch.setattr(update_stages.pipeline, "run", fake_pipeline)
    monkeypatch.setattr(update_stages.reviews, "run", fake_reviews)
    ctx = update.Ctx(cfg, str(tmp_path), opts(no_write=True), {"label": "u", "stages": {}, "created": "2026-11-17T00:00:00Z"}, lambda *_: None, [])
    r = update_stages.specs(ctx)
    assert r["status"] == DONE and got["pipeline"][0]["no_write"] is True and got["pipeline"][0]["audit"] == "none"
    r = update_stages.reviews_numbers(ctx)
    assert r["status"] == DONE and got["reviews"][0]["no_write"] is True and got["reviews"][0]["no_text"] is True
    r = update_stages.reviews_text(ctx)
    assert got["reviews"][1]["no_write"] is True and got["reviews"][1]["no_text"] is False


def test_stage_results_are_mapped(cfg, monkeypatch, tmp_path):
    ctx = update.Ctx(cfg, str(tmp_path), opts(), {"label": "u", "stages": {}, "created": "2026-11-17T00:00:00Z"}, lambda *_: None, [])
    mk = lambda stopped, **x: (lambda cfg_, **kw: dict({"run": kw["label"], "stopped": stopped, "write": None, "discovery": {}, "processed": 0, "stage": None}, **x))
    monkeypatch.setattr(update_stages.pipeline, "run", mk("gates failed on staging; nothing was merged (schema)"))
    assert update_stages.specs(ctx)["status"] == FAILED
    monkeypatch.setattr(update_stages.pipeline, "run", mk("LLM quota exhausted"))
    assert update_stages.specs(ctx)["status"] == LIMIT
    monkeypatch.setattr(update_stages.reviews, "run", lambda cfg_, **kw: {"run": "r", "stopped": None, "write": None, "models": {}, "numbers_check": {},
                                                                          "text_stopped": {"role": "writer", "why": "daily call budget reached", "at": "Nexon"}, "not_reached": ["a"]})
    r = update_stages.reviews_text(ctx)
    assert r["status"] == LIMIT and "Nexon" in r["result"]


def test_robots_blocked_source_is_reported_and_stops_the_stage(cfg, monkeypatch, tmp_path):
    from kbpipe.sources import carwale
    urls = [carwale.brand_url(m) for m in cfg["scope_makes"]]
    monkeypatch.setattr(update_stages.pipeline, "run", lambda cfg_, **kw: {"run": "r", "stopped": None, "write": None, "discovery": {"UNKNOWN": 9},
                                                                           "processed": 0, "stage": None, "robots_blocked": urls})
    ctx = update.Ctx(cfg, str(tmp_path), opts(), {"label": "u", "stages": {}, "created": "2026-11-17T00:00:00Z"}, lambda *_: None, [])
    r = update_stages.specs(ctx)
    assert r["status"] == FAILED and "robots.txt" in r["result"] and "carwale" in r["result"]
    # one blocked page is only a warning
    monkeypatch.setattr(update_stages.pipeline, "run", lambda cfg_, **kw: {"run": "r", "stopped": None, "write": None, "discovery": {}, "processed": 0,
                                                                           "stage": None, "robots_blocked": urls[:1]})
    r = update_stages.specs(ctx)
    assert r["status"] == DONE and r["warnings"]


# ------------------------------------------------------------------ audit resume
FETCHER = types.SimpleNamespace(stats={}, blocks=[])


def test_audit_resume_continues_from_results_without_rechecking(cfg, monkeypatch, tmp_path):
    import sqlite3
    db = str(tmp_path / "x.db")
    sqlite3.connect(db).close()
    cells = [{"variant_id": i, "field_name": "price_ex_showroom", "group": "price", "cls": "aggregator", "full_name": "c%d" % i, "value": 1,
              "source": "carwale", "source_url": "u%d" % i, "pid": i, "extraction_method": "kbpipe_json"} for i in range(1, 7)]
    monkeypatch.setattr(verify, "population", lambda conn, only_run_methods=False: list(cells))
    monkeypatch.setattr(llm, "get", lambda cfg_, role, run_dir=None, **k: object())
    checked = []

    def fake_check(cell, cfg_, fetcher, backends, legacy_lookup=None):
        if len(checked) == 3 and not fake_check.resumed:
            raise llm.QuotaExhausted("gemini_alt: daily call budget reached")
        checked.append(cell["variant_id"])
        return {"variant_id": cell["variant_id"], "field": cell["field_name"], "group": "price", "source_class": "aggregator", "verdict": "match"}
    fake_check.resumed = False
    monkeypatch.setattr(verify, "check_cell", fake_check)
    cfg["audit_per_stratum"], cfg["planted_errors"] = 100, 0
    R1 = audit.run(cfg, scope="full", label="aud", db=db, fetcher=FETCHER, echo=lambda *_: None)
    assert R1["stopped_on_limit"] and R1["checked_now"] == 3 and R1["cells"] == 6
    fake_check.resumed = True
    R2 = audit.run(cfg, resume=R1["run_dir"], db=db, fetcher=FETCHER, echo=lambda *_: None)
    assert R2["resumed"] and R2["already_done"] == 3 and R2["checked_now"] == 3 and not R2["stopped_on_limit"]
    assert sorted(checked) == [1, 2, 3, 4, 5, 6]                       # no cell twice
    rows = verify.load(os.path.join(R1["run_dir"], "verify"))
    assert len(rows) == 6 and R2["verify"]["overall"]["match"] == 6


def test_audit_changed_pids_come_from_apply_logs(tmp_path):
    d = tmp_path / "r"
    d.mkdir()
    (d / "apply_log.tsv").write_text("table\trowid\taction\tdetail\nvariant\t5\tinsert\tx\nfield_provenance\t11\tinsert\ty\nfield_provenance\t12\tupdate\tz\n")
    assert audit.changed_pids(str(d), str(tmp_path / "missing")) == {11}


# ------------------------------------------------------------------ robots handling of the spec fetcher
ROBOTS = "User-agent: *\nDisallow: /api/*\nDisallow: /find-car/\nCrawl-delay: 9\n\nUser-agent: kbpipe\nDisallow: /private$\n"


class FakeResp:
    def __init__(self, body, status=200):
        self.body, self.status, self.headers = body.encode(), status, {}

    def read(self):
        return self.body

    def geturl(self):
        return "u"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_net(monkeypatch, routes):
    import urllib.error
    sent = []

    def urlopen(req, timeout=0):
        sent.append((req.full_url, req.headers.get("User-agent")))
        path = "/" + req.full_url.split("/", 3)[3]
        for k, v in routes.items():
            if path == k:
                if isinstance(v, int):
                    raise urllib.error.HTTPError(req.full_url, v, "x", {}, None)
                return FakeResp(v)
        raise urllib.error.HTTPError(req.full_url, 404, "x", {}, None)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    return sent


def test_default_user_agent_is_truthful(cfg):
    ua = cfg["user_agent"]
    assert ua.startswith("kbpipe/") and "Mozilla" not in ua and "Chrome" not in ua and "@" not in ua


def test_spec_fetch_obeys_robots_and_never_changes_identity(cfg, monkeypatch):
    sent = fake_net(monkeypatch, {"/robots.txt": ROBOTS, "/hyundai-cars/": "<html>brand</html>", "/api/x": "secret", "/find-car/a": "z", "/private": "p"})
    f = fetch.Fetcher(cfg)
    body, meta = f.get("https://www.example.com/hyundai-cars/")
    assert body and "brand" in body
    assert f.get("https://www.example.com/api/x") == (None, None)            # wildcard rule for *
    assert f.get("https://www.example.com/find-car/a") == (None, None)
    assert f.get("https://www.example.com/private") == (None, None)          # rule for this tool's own name
    fetched = [u for u, _ in sent]
    assert "https://www.example.com/api/x" not in fetched and "https://www.example.com/private" not in fetched
    assert {ua for _, ua in sent} == {cfg["user_agent"]}                     # one identity, always the configured one
    assert [w for _, w in f.blocks] == ["robots"] * 3
    assert f.stats["failed"] == 3


def test_crawl_delay_larger_than_spacing_is_honoured(cfg, monkeypatch):
    fake_net(monkeypatch, {"/robots.txt": ROBOTS, "/hyundai-cars/": "<html>x</html>", "/tata-cars/": "<html>y</html>"})
    f = fetch.Fetcher(cfg)
    f.get("https://www.example.com/hyundai-cars/")
    assert f.crawl_delay("https://www.example.com/") == 9.0 and f.gap_for == 9.0
    f2 = fetch.Fetcher(dict(cfg, min_seconds_between_requests=20))
    f2.get("https://www.example.com/tata-cars/")
    assert f2.gap_for == 20


def test_missing_robots_allows_but_unreadable_robots_fails_closed(cfg, monkeypatch):
    fake_net(monkeypatch, {"/page": "ok"})                                   # robots.txt 404
    assert fetch.Fetcher(cfg).get("https://a.example.com/page")[0] == "ok"
    fake_net(monkeypatch, {"/robots.txt": 500, "/page": "ok"})
    assert fetch.Fetcher(cfg).get("https://b.example.com/page") == (None, None)


def test_cached_pages_do_not_need_robots(cfg, monkeypatch):
    sent = fake_net(monkeypatch, {"/robots.txt": ROBOTS, "/hyundai-cars/": "<html>x</html>"})
    f = fetch.Fetcher(cfg)
    f.get("https://www.example.com/hyundai-cars/")
    n = len(sent)
    f.get("https://www.example.com/hyundai-cars/")
    assert len(sent) == n


# ------------------------------------------------------------------ stage 11 against a fake publisher and a real git repository
def git(*a, cwd=None):
    r = subprocess.run(["git"] + list(a), cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def app(tmp_path):
    up = tmp_path / "upstream"
    up.mkdir()
    git("init", "-q", "-b", "main", cwd=up)
    git("config", "user.email", "t@t", cwd=up), git("config", "user.name", "t", cwd=up)
    for p, t in {"data/catalogue_v3/catalogue.csv": "a\n", "data/catalogue_v3/catalogue_meta.json": "{}\n", "data/assessments.csv": "x\n",
                 "project_pages/index.html": "<p>1</p>", "tests/data/golden_empty_evidence_1464.json": "{}\n", "README.md": "r\n"}.items():
        (up / p).parent.mkdir(parents=True, exist_ok=True)
        (up / p).write_text(t)
    git("add", "-A", cwd=up), git("commit", "-qm", "init", cwd=up)
    local = tmp_path / "app"
    git("clone", "-q", str(up), str(local))
    git("config", "user.email", "t@t", cwd=local), git("config", "user.name", "t", cwd=local)
    return up, local


class FakePublisher:
    def __init__(self):
        self.calls = []

    def push(self, ws, branch):
        self.calls.append(("push", branch))

    def open_pr(self, ws, branch, base, title, body):
        self.calls.append(("pr", branch, base, title, body))
        return "https://github.example/pr/1"


def pr_ctx(cfg, app, tmp_path, no_write=False, no_pr=False, created="2026-11-17T01:00:00Z"):
    up, local = app
    cfg = dict(cfg, app_repo=str(local), cache_dir=str(tmp_path / "cache"))
    st = {"label": "u1", "created": created, "stages": {}}
    ctx = update.Ctx(cfg, str(tmp_path / "u"), opts(no_write=no_write, no_pr=no_pr), st, lambda *_: None, [])
    os.makedirs(ctx.update_dir, exist_ok=True)
    ws = appstages.ensure_workspace(ctx)
    st["stages"]["export"] = {"data": {"workspace": ws}}
    st["stages"]["checks"] = {"data": {"tests": "10 passed", "eval_before": {"zero_violations": "1 of 2"}, "eval_after": {"zero_violations": "2 of 2"},
                                       "golden_regenerated": ["tests/data/golden_empty_evidence_1464.json"], "golden_diff_stat": "1 file"}}
    return ctx, ws


def test_stage11_commits_only_allowed_files_pushes_and_opens_pr_via_the_fake(cfg, app, tmp_path, monkeypatch):
    fake = FakePublisher()
    monkeypatch.setattr(appstages, "PUBLISHER", fake)
    ctx, ws = pr_ctx(cfg, app, tmp_path)
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=ws) == "data/kb-update-2026-11-17"
    (open(os.path.join(ws, "data/assessments.csv"), "w")).write("new\n")
    open(os.path.join(ws, "project_pages/index.html"), "w").write("<p>2</p>")
    open(os.path.join(ws, "tests/data/golden_empty_evidence_1464.json"), "w").write('{"q": 1}\n')
    r = appstages.pull_request(ctx)
    assert r["status"] == DONE and r["data"]["url"] == "https://github.example/pr/1"
    assert [c[0] for c in fake.calls] == ["push", "pr"] and fake.calls[0][1] == "data/kb-update-2026-11-17" and fake.calls[1][2] == "main"
    assert "Not merged" in fake.calls[1][4] and "golden_empty_evidence_1464.json" in fake.calls[1][4] and "1 of 2" in fake.calls[1][4]
    files = git("diff", "--name-only", "origin/main..HEAD", cwd=ws).split()
    assert sorted(files) == ["data/assessments.csv", "project_pages/index.html", "tests/data/golden_empty_evidence_1464.json"]
    assert git("rev-parse", "main", cwd=app[1]) == git("rev-parse", "main", cwd=app[0])          # main untouched everywhere


def test_stage11_refuses_stray_files_dirty_app_and_main(cfg, app, tmp_path, monkeypatch):
    fake = FakePublisher()
    monkeypatch.setattr(appstages, "PUBLISHER", fake)
    ctx, ws = pr_ctx(cfg, app, tmp_path)
    open(os.path.join(ws, "app.py"), "w").write("# edited\n")
    r = appstages.pull_request(ctx)
    assert r["status"] == FAILED and "app.py" in r["result"] and not fake.calls
    # dirty app worktree (tracked file edited, not committed)
    open(os.path.join(app[1], "README.md"), "w").write("dirty\n")
    os.remove(os.path.join(ws, "app.py"))
    r = appstages.pull_request(ctx)
    assert r["status"] == FAILED and "uncommitted changes to tracked files" in r["result"] and not fake.calls
    git("checkout", "--", "README.md", cwd=app[1])
    # never on main
    git("checkout", "-q", "main", cwd=ws)
    r = appstages.pull_request(ctx)
    assert r["status"] == FAILED and "main" in r["result"] and not fake.calls


def test_stage11_no_write_and_no_pr_never_publish(cfg, app, tmp_path, monkeypatch):
    fake = FakePublisher()
    monkeypatch.setattr(appstages, "PUBLISHER", fake)
    for kw in ({"no_write": True}, {"no_pr": True}):
        ctx, ws = pr_ctx(cfg, app, tmp_path / ("c" + "".join(kw)), **kw)
        open(os.path.join(ws, "data/assessments.csv"), "w").write("new %s\n" % kw)
        r = appstages.pull_request(ctx)
        assert r["status"] == DONE and "nothing pushed" in r["result"] or "not pushed" in r["result"]
        assert git("log", "-1", "--format=%s", cwd=ws).startswith("data: KB update")
    assert fake.calls == []


def test_stage11_meta_only_change_is_not_a_pull_request(cfg, app, tmp_path, monkeypatch):
    fake = FakePublisher()
    monkeypatch.setattr(appstages, "PUBLISHER", fake)
    ctx, ws = pr_ctx(cfg, app, tmp_path)
    open(os.path.join(ws, "data/catalogue_v3/catalogue_meta.json"), "w").write('{"export_utc": "later"}\n')
    r = appstages.pull_request(ctx)
    assert r["status"] == DONE and "already has this data" in r["result"] and fake.calls == []


def test_stage11_push_failure_keeps_the_commit_and_reports(cfg, app, tmp_path, monkeypatch):
    class Bad(FakePublisher):
        def push(self, ws, branch):
            raise RuntimeError("git push failed: denied")
    monkeypatch.setattr(appstages, "PUBLISHER", Bad())
    ctx, ws = pr_ctx(cfg, app, tmp_path)
    open(os.path.join(ws, "data/assessments.csv"), "w").write("new\n")
    r = appstages.pull_request(ctx)
    assert r["status"] == FAILED and "denied" in r["result"] and "--redo pr" in r["result"]
    monkeypatch.setattr(appstages, "PUBLISHER", FakePublisher())
    assert appstages.pull_request(ctx)["status"] == DONE            # the retry reuses the kept commit


def test_real_publisher_never_forces_or_merges(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(appstages, "sh", lambda args, cwd=None, **k: (seen.append(list(args)) or (0, "https://github.com/x/y/pull/9\n")))
    p = appstages.Publisher()
    p.push(str(tmp_path), "data/kb-update-x")
    assert p.open_pr(str(tmp_path), "data/kb-update-x", "main", "t", "b") == "https://github.com/x/y/pull/9"
    flat = [a for c in seen for a in c]
    assert seen[0][:3] == ["git", "push", "-u"] and not any(a in ("--force", "-f", "--force-with-lease", "merge") for a in flat)
    assert seen[1][:3] == ["gh", "pr", "create"]


# ------------------------------------------------------------------ stage 12: photo candidates
def test_images_stage_is_after_pr_and_before_summary():
    names = [s.name for s in update.default_stages()]
    assert names.index("pr") < names.index("images") < names.index("summary") and names[-1] == "summary"
    assert len({s.num for s in update.default_stages()}) == len(names)


def test_images_stage_reads_the_export_workspace_and_never_prefills(tmp_path, monkeypatch):
    from kbpipe import images as I, update_stages as S
    ws, app = tmp_path / "ws", tmp_path / "app"
    for d in (ws, app):
        (d / "data" / "catalogue_v3").mkdir(parents=True)
        (d / "data" / "image_manifest.csv").write_text("make,model,filename,source,license,attribution\nTata,Nexon,tata_nexon.webp,x,y,z\n")
    (ws / "data" / "catalogue_v3" / "catalogue.csv").write_text("make,model,body_type\nTata,Nexon,SUV\nTata,Sierra,SUV\n")
    (app / "data" / "catalogue_v3" / "catalogue.csv").write_text("make,model,body_type\nTata,Nexon,SUV\n")
    seen = {}

    def fake_run(repo, oem, oem_new, run_dir=None, only=None, top_n=3, prefill=True, apply_repo=None):
        seen.update(repo=repo, prefill=prefill, apply_repo=apply_repo)
        return {"run_dir": run_dir, "no_brochure": [], "picks": {"tata_sierra": {"needs_human": True, "candidates": [{"file": "c1.jpg"}]}}}
    monkeypatch.setattr(I, "run", fake_run)
    cfg = {"app_repo": str(app), "oem_dir": str(tmp_path), "oem_new_dir": str(tmp_path), "runs_dir": str(tmp_path / "runs")}
    st = {"label": "u", "stages": {"export": {"data": {"workspace": str(ws)}}}, "created": "2026-11-17T00:00:00Z"}
    ctx = update.Ctx(cfg, str(tmp_path / "upd"), {"no_write": True}, st, lambda *_: None, [])
    r = S.images(ctx)
    assert r["status"] == update.DONE and r["data"]["need_human"] == ["tata_sierra"]
    assert seen == {"repo": str(ws), "prefill": False, "apply_repo": str(app)}     # the fresh catalogue is read; picks go to the real app repo
    st["stages"]["export"] = {}
    assert S.images(ctx)["result"] == "every catalogue model has a photo"             # fallback: the app repo, where Sierra is not listed


# ------------------------------------------------------------------ stage summaries say what happened to the KB
def test_summary_line_separates_fills_changes_and_confirmations(tmp_path):
    import json
    from kbpipe import update_stages as S
    run = tmp_path / "r1"
    run.mkdir()
    ops = [{"op": "cell", "expect_old": "Petrol", "value": "Petrol"}] * 3 + [{"op": "cell", "expect_old": None, "value": 5},
           {"op": "cell", "expect_old": 1, "value": 2}, {"op": "variant"}]
    (run / "changeset.json").write_text(json.dumps({"ops": ops}))
    (run / "run.json").write_text(json.dumps({"coverage_before": {"models": 92, "variants": 1464}, "coverage_after": {"models": 92, "variants": 1464}}))
    ctx = update.Ctx({"runs_dir": str(tmp_path)}, str(tmp_path), opts(), {"label": "u", "stages": {}, "created": "x"}, lambda *_: None, [])
    R = {"run": "r1", "processed": 7, "discovery": {"NEW_MODEL": 16, "EXISTING": 91, "UPCOMING": 88},
         "write": {"sha1_before": "7e5478c5aa", "sha1_after": "7e5478c5aa"}}
    _, line = S._summarise_pipeline(R, ctx, "specs")
    assert "16 model(s) found on both sites but not in the KB (0 added)" in line and "91 already in the KB" in line
    assert "1 blank cell(s) filled, 1 stored value(s) changed, 3 confirmed by fresh evidence" in line
    assert "KB unchanged (7e5478c5)" in line and "NEW_MODEL" not in line


# ---------------------------------------------------------------- golden file naming (any catalogue size)
@pytest.mark.parametrize("n,name", [(832, "golden_empty_evidence.json"), ("832", "golden_empty_evidence.json"),
                                    (1464, "golden_empty_evidence_1464.json"), ("1619", "golden_empty_evidence_1619.json")])
def test_golden_name_rule(n, name):
    assert appstages.golden_name(n) == name


def test_golden_name_is_accepted_by_the_pr_whitelist():
    assert appstages._allowed("tests/data/" + appstages.golden_name(1619))


def test_golden_template_prefers_existing_file_then_largest_sized_then_base(tmp_path):
    d = str(tmp_path)
    assert appstages.golden_template(d, "golden_empty_evidence_1619.json") is None
    (tmp_path / "golden_empty_evidence.json").write_text("{}")
    assert appstages.golden_template(d, "golden_empty_evidence_1619.json") == "golden_empty_evidence.json"
    (tmp_path / "golden_empty_evidence_1464.json").write_text("{}")
    (tmp_path / "golden_empty_evidence_999.json").write_text("{}")
    assert appstages.golden_template(d, "golden_empty_evidence_1619.json") == "golden_empty_evidence_1464.json"
    (tmp_path / "golden_empty_evidence_1619.json").write_text("{}")
    assert appstages.golden_template(d, "golden_empty_evidence_1619.json") == "golden_empty_evidence_1619.json"
    assert appstages.golden_template(str(tmp_path / "missing"), "x.json") is None


def test_regen_writes_a_new_file_with_format_and_queries_from_the_template(tmp_path):
    """REGEN run against a stub app: new file name written, queries and dump format come from the existing golden file."""
    pkg = tmp_path / "services" / "recsys"
    pkg.mkdir(parents=True)
    (tmp_path / "services" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (tmp_path / "services" / "catalogue.py").write_text("def get_catalogue():\n    return [0] * 1619\n")
    (pkg / "api.py").write_text("def recommend(q, evidence=None):\n    return {'recommendations': [{'variant_id': len(q), 'scores': {}, 'ranking_score': 1.0, 'criteria': []}]}\n")
    (pkg / "evidence.py").write_text("class Evidence:\n    pass\n")
    data = tmp_path / "tests" / "data"
    data.mkdir(parents=True)
    old = {"suv": [], "city car": []}
    tmpl = data / "golden_empty_evidence_1464.json"
    tmpl.write_text(json.dumps(old, indent=1, sort_keys=False, ensure_ascii=True) + "\n")
    raw = tmpl.read_text()
    kw, end = appstages._detect_dump(raw, json.loads(raw))
    assert kw is not None
    import sys
    r = subprocess.run([sys.executable, "-c", appstages.REGEN, json.dumps(kw), end,
                        appstages.golden_name(1619), "golden_empty_evidence_1464.json"],
                       cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = data / "golden_empty_evidence_1619.json"
    assert out.exists() and tmpl.read_text() == raw       # template untouched
    new = json.loads(out.read_text())
    assert sorted(new) == ["city car", "suv"] and new["suv"][0]["variant_id"] == 3
    assert out.read_text() == json.dumps(new, indent=1, sort_keys=False, ensure_ascii=True) + "\n"
