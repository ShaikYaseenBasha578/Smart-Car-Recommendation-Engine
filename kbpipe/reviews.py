"""`kbpipe reviews`: professional scores (Autocar India) and owner ratings (CarWale), plus short notes and owner themes.
REVIEW_LAYERS_PLAN.md sections 3-5 and 9a. Numbers are read from the pages by parsers; an LLM only writes the short notes
and themes, and a second model must confirm each one against the page text. Nothing is written unless it passes validation,
the existing staging + gates + write.py path, and (for text) the verifier bar. Never fetches Team-BHP: --import-saved
reads local files only."""
import csv
import html
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone

from . import __version__, fetch, kb, llm, review_ops, write
from . import review_text as RT
from .migrations import reviews_tables as MIG
from .sources import autocar_reviews as AC
from .sources import carwale_ratings as CW

SRC_AUTOCAR, SRC_CARWALE, SRC_TBHP = "Autocar India expert review", "CarWale user ratings", "Team-BHP (owner-saved pages)"
THEMES = ["reliability", "service_cost", "service_experience", "real_world_mileage", "build_issues", "recurring_fault", "resale",
          "satisfaction"]
DIRECTIONS = ("positive", "negative", "mixed")
METHOD_AC = "kbpipe/%s autocar_expert_page" % __version__
METHOD_CW = "kbpipe/%s carwale_user_reviews_page" % __version__


# ---------------------------------------------------------------- helpers
def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def slugs(cfg, make, model):
    rc = cfg["reviews"]
    full = "%s %s" % (make, model)
    a = rc["autocar_slugs"].get(full) or rc["autocar_slugs"].get(model) or _slug(model)
    c = rc["carwale_slugs"].get(full) or rc["carwale_slugs"].get(model) or _slug(model)
    return a, c


def kb_models(db):
    c = kb.ro(db)
    rows = c.execute("select mo.id, m.name as make, mo.name as model, (select count(*) from variant v where v.model_id=mo.id) as nv "
                     "from model mo join manufacturer m on m.id=mo.manufacturer_id order by m.name, mo.name").fetchall()
    out = [dict(r) for r in rows]
    c.close()
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(s or "").lower()).strip()


def _words(s):
    return len((s or "").split())


def _in_text(needle, text):
    """Substring test that ignores case, runs of whitespace and curly quotes."""
    f = lambda s: re.sub(r"\s+", " ", (s or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"')
                         .replace("\u201d", '"').replace("\u2013", "-").replace("\u2014", "-")).strip().lower()
    return bool(f(needle)) and f(needle) in f(text)


class Flags:
    def __init__(self):
        self.rows = []

    def add(self, make, model, source, flag, detail=""):
        self.rows.append((make, model, source, flag, str(detail)[:300]))


# ---------------------------------------------------------------- identity and validation (plan section 4)
def autocar_identity(parsed, make, model, make_s, model_s, page_name=None):
    if not parsed:
        return False, "page not readable (no Autocar markup)"
    want = {_norm("%s %s" % (make, model))} | ({_norm(page_name)} if page_name else set())
    names = {_norm(parsed.get("page_name")), _norm(parsed.get("ld_name"))} - {""}
    if not names or not (names & want):
        return False, "page is for %r, wanted %s %s" % (parsed.get("page_name"), make, model)
    canon = parsed.get("canonical") or ""
    if canon and "/cars/%s/%s/" % (make_s, model_s) not in canon.rstrip("/") + "/":
        return False, "canonical URL %s is not the requested page" % canon
    return True, ""


def carwale_identity(parsed, make, model):
    if not parsed:
        return False, "page not readable (no initial-state userReviewListing)"
    if _norm(parsed["make"]) != _norm(make) or _norm(parsed["model"]) != _norm(model):
        return False, "page is for %s %s, wanted %s %s" % (parsed["make"], parsed["model"], make, model)
    return True, ""


def validate_autocar(p):
    """(ok, problems). Odd anything leaves the model out; a missing overall score alone keeps the seven aspects."""
    bad = []
    for label in AC.ASPECTS:
        v = p["aspects"].get(label)
        if v is None:
            bad.append("aspect missing: %s" % label)
        elif not (0 <= v <= AC.SCALE):
            bad.append("%s=%s outside 0..10" % (label, v))
    o = p["overall"] if p["overall"] is not None else p["ld_overall"]
    if o is not None and not (0 <= o <= AC.SCALE):
        bad.append("overall %s outside 0..10" % o)
    if p["overall"] is not None and p["ld_overall"] is not None and abs(p["overall"] - p["ld_overall"]) > 0.01:
        bad.append("overall differs: markup %s vs JSON-LD %s" % (p["overall"], p["ld_overall"]))
    if p["ld_best"] is not None and p["ld_best"] != AC.SCALE:
        bad.append("scale is %s, expected 10" % p["ld_best"])
    return not bad, bad


def validate_carwale(p):
    bad = []
    if not isinstance(p["rating_count"], int) or p["rating_count"] <= 0:
        bad.append("rating count %r is not a positive integer" % (p["rating_count"],))
    if not isinstance(p["overall"], (int, float)) or not (0 <= p["overall"] <= CW.SCALE):
        bad.append("overall %r outside 0..5" % (p["overall"],))
    for label in CW.ASPECTS:
        v = p["aspects"].get(label)
        if v is not None and not (0 <= v <= CW.SCALE):
            bad.append("%s=%s outside 0..5" % (label, v))
    return not bad, bad


def carwale_missing(p):
    """Aspects the site does not show for this model (new models lack some): unknown, never 0; stored as absent and flagged."""
    return [a for a in CW.ASPECTS if p["aspects"].get(a) is None]


# ---------------------------------------------------------------- LLM text (kbpipe/review_text.py holds the logic)
make_engine = lambda cfg, run_dir, log=None: RT.Engine(cfg, run_dir, log=log)    # tests replace this with fake backends


def carwale_items(cw, cfg):
    """The most recent written reviews, newest first, capped (reviews.carwale_max_reviews); id as text."""
    rc = cfg["reviews"]
    def _k(r):
        try:
            return int(r["id"])
        except (TypeError, ValueError):
            return 0
    rs = sorted(cw["reviews"], key=_k, reverse=True)[:rc["carwale_max_reviews"]]       # ids grow with time; the page lists reviews by relevance
    return [{"id": str(r["id"]), "text": ("%s. %s" % (r["title"], r["text"]))[:rc["carwale_review_chars"]]} for r in rs]


# ---------------------------------------------------------------- per-model numbers
def _stale(cfg, make, model, published_on):
    d = cfg["reviews"]["generation_dates"].get("%s %s" % (make, model)) or cfg["reviews"]["generation_dates"].get(model)
    return bool(d and published_on and published_on < d)


def autocar_model(cfg, fetcher, m, flags, log):
    """-> dict(parsed, url, observed_at, status) or None."""
    a_s, _ = slugs(cfg, m["make"], m["model"])
    if "%s %s" % (m["make"], m["model"]) in cfg["reviews"].get("autocar_no_review", []):
        flags.add(m["make"], m["model"], "autocar", "NO_EXPERT_REVIEW", "Autocar has no expert review page of its own for this model (checked 2026-11-15); nothing fetched")
        log("autocar", "%s %s: no expert review of its own (config), not fetched" % (m["make"], m["model"]))
        return None
    url = AC.url(AC.make_slug(m["make"]), a_s)
    body, meta, why = fetcher.get_polite(url, max_age_days=cfg["reviews"]["refresh_days"])
    if body is None:
        flags.add(m["make"], m["model"], "autocar", "UNREACHABLE", "%s (%s)" % (why, url))
        log("autocar", "%s %s: unreachable (%s)" % (m["make"], m["model"], why))
        return None
    p = AC.parse(body)
    ok, why = autocar_identity(p, m["make"], m["model"], AC.make_slug(m["make"]), a_s,
                               cfg["reviews"].get("autocar_page_names", {}).get("%s %s" % (m["make"], m["model"])))
    if not ok:
        flags.add(m["make"], m["model"], "autocar", "WRONG_PAGE", why)
        log("autocar", "%s %s: discarded, %s" % (m["make"], m["model"], why))
        return None
    ok, bad = validate_autocar(p)
    if not ok:
        flags.add(m["make"], m["model"], "autocar", "INVALID_SCORES", "; ".join(bad))
        log("autocar", "%s %s: left out, %s" % (m["make"], m["model"], "; ".join(bad)))
        return None
    if p["overall"] is None and p["ld_overall"] is None:
        flags.add(m["make"], m["model"], "autocar", "OVERALL_MISSING", "seven aspect scores kept, no overall row")
    return {"parsed": p, "url": url, "observed_at": meta["fetched_at"], "score_text": AC.score_text(body)}


def carwale_model(cfg, fetcher, m, flags, log, want_text):
    _, c_s = slugs(cfg, m["make"], m["model"])
    ms = CW.make_slug(m["make"])
    url = CW.url(ms, c_s, 1)
    body, meta, why = fetcher.get_polite(url, max_age_days=cfg["reviews"]["refresh_days"])
    if body is None:
        flags.add(m["make"], m["model"], "carwale", "UNREACHABLE", "%s (%s)" % (why, url))
        log("carwale", "%s %s: unreachable (%s)" % (m["make"], m["model"], why))
        return None
    p = CW.parse(body)
    ok, why = carwale_identity(p, m["make"], m["model"])
    if not ok:
        flags.add(m["make"], m["model"], "carwale", "WRONG_PAGE", why)
        log("carwale", "%s %s: discarded, %s" % (m["make"], m["model"], why))
        return None
    ok, bad = validate_carwale(p)
    if not ok:
        flags.add(m["make"], m["model"], "carwale", "INVALID_RATINGS", "; ".join(bad))
        log("carwale", "%s %s: left out, %s" % (m["make"], m["model"], "; ".join(bad)))
        return None
    miss = carwale_missing(p)
    if miss:
        flags.add(m["make"], m["model"], "carwale", "ASPECTS_MISSING", "not shown on the page, left empty: %s" % ", ".join(miss))
    if p["rating_count"] < cfg["reviews"]["low_confidence_ratings"]:
        flags.add(m["make"], m["model"], "carwale", "LOW_CONFIDENCE", "%d ratings (stored, flagged for export)" % p["rating_count"])
    res = {"parsed": p, "url": url, "observed_at": meta["fetched_at"], "reviews": list(p["reviews"]), "review_urls": {}, "score_text": CW.score_text(body)}
    for r in p["reviews"]:
        res["review_urls"][str(r["id"])] = url
    if want_text:
        pages = cfg["reviews"]["carwale_max_text_pages"]
        total = p["total_reviews"] or 0
        for n in range(2, pages + 1):
            if len(res["reviews"]) >= min(total, cfg["reviews"]["carwale_max_reviews"]):
                break
            u = CW.url(ms, c_s, n)
            b2, m2, why = fetcher.get_polite(u, max_age_days=cfg["reviews"]["refresh_days"])
            if b2 is None:
                flags.add(m["make"], m["model"], "carwale", "REVIEW_PAGE_UNREACHABLE", "%s (%s)" % (why, u))
                break
            q = CW.parse(b2)
            if not q or _norm(q["model"]) != _norm(m["model"]):
                flags.add(m["make"], m["model"], "carwale", "REVIEW_PAGE_WRONG", u)
                break
            for r in q["reviews"]:
                if str(r["id"]) not in res["review_urls"]:
                    res["reviews"].append(r)
                    res["review_urls"][str(r["id"])] = u
    return res


# ---------------------------------------------------------------- rows and change-set
def assessment_ops(cfg, m, ac, notes, now):
    p = ac["parsed"]
    pub = p["published_on"]
    st = "stale_generation" if _stale(cfg, m["make"], m["model"], pub) else "current"
    base = {"op": "assessment", "make": m["make"], "model": m["model"], "source": SRC_AUTOCAR, "scale_max": AC.SCALE,
            "variant_scope": None, "url": ac["url"], "published_on": pub, "observed_at": ac["observed_at"],
            "method": METHOD_AC, "status": st}
    ops = []
    o = p["overall"] if p["overall"] is not None else p["ld_overall"]
    if o is not None:
        ops.append(dict(base, aspect="overall", score=o))
    for label in AC.ASPECTS:
        n = notes.get(label) or {}
        method = METHOD_AC + (("; note: %s" % n["_method"]) if n.get("_method") else "")
        ops.append(dict(base, aspect=label, score=p["aspects"][label], note=n.get("note"), quote=n.get("quote"), method=method))
    return ops


def rating_ops(m, cw):
    p = cw["parsed"]
    base = {"op": "owner_rating", "make": m["make"], "model": m["model"], "source": SRC_CARWALE, "scale_max": CW.SCALE,
            "rating_count": p["rating_count"], "url": cw["url"], "observed_at": cw["observed_at"], "method": METHOD_CW}
    ops = [dict(base, aspect="overall", score=p["overall"])]
    ops += [dict(base, aspect=a, score=p["aspects"][a]) for a in CW.ASPECTS if p["aspects"].get(a) is not None]
    return ops


def theme_ops(m, source, themes, sampled, urls_of, now, method, period=None):
    out = []
    for t in themes:
        urls = []
        for i in t["ids"]:
            u = urls_of.get(i) or urls_of.get(str(i))
            if u and u not in urls:
                urls.append(u)
        out.append({"op": "owner_theme", "make": m["make"], "model": m["model"], "source": source, "theme": t["theme"],
                    "label": t["label"], "direction": t["direction"], "mentions": t["mentions"], "posts_sampled": sampled,
                    "period": period, "sample_urls": urls[:5], "note": t["note"], "extracted_at": now, "method": method})
    return out


def _tsv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _run_dir(cfg, label):
    base = os.path.join(cfg["runs_dir"], label or datetime.now(timezone.utc).strftime("reviews_%Y-%m-%d"))
    d, n = base, 1
    while os.path.exists(os.path.join(d, "RUN_SUMMARY.md")):
        n += 1
        d = "%s_%d" % (base, n)
    os.makedirs(d, exist_ok=True)
    return d, os.path.basename(d)


def _prepare_kb(cfg, run_dir, no_write, log):
    """Copy of prod (the read rule in CLAUDE.md). With --no-write, a missing review schema is added to the COPY only."""
    before = os.path.join(run_dir, "before.db")
    sha = kb.copy_for_read(cfg["prod_db"], before)
    c = kb.ro(before)
    have = MIG.has_tables(c)
    c.close()
    if not have:
        if not no_write:
            raise kb.Stop("the production KB has no review tables. Apply kbpipe/migrations/reviews_tables.py with the owner's P16 approval first; "
                          "this run writes nothing.")
        MIG.migrate(before, prod_flag=False, prod_path=cfg["prod_db"])
        log("kb", "review tables absent in prod: migrated the scratch copy only")
    return before, sha, have


def _fresh(conn, mid, source, days):
    try:
        r = conn.execute("select max(observed_at) from professional_assessment p join source s on s.id=p.source_id where p.model_id=? and s.name=? and p.status='current'", (mid, source)).fetchone()
        if source == SRC_CARWALE:
            r = conn.execute("select max(observed_at) from owner_rating p join source s on s.id=p.source_id where p.model_id=? and s.name=? and p.status='current'", (mid, source)).fetchone()
    except Exception:
        return False
    return bool(r and r[0] and fetch.age_days(r[0][:19] + "Z") < days)


# ---------------------------------------------------------------- the run
def run(cfg, only=None, max_models=None, no_write=False, label=None, no_text=False, verify_all=False, force=False, write_only=False, echo=print):
    t0 = time.time()
    run_dir, run_id = _run_dir(cfg, label)
    lines = []

    def log(stage, *msg):
        line = "%s [%s] %s" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), stage, " ".join(str(x) for x in msg))
        lines.append(line)
        echo(line)
        with open(os.path.join(run_dir, "run.log"), "a") as f:
            f.write(line + "\n")

    rc = cfg["reviews"]
    R = {"run": run_id, "started": fetch.now_iso(), "stopped": None, "write": None, "stage": None, "models": {}, "text": {}}
    flags = Flags()
    try:
        before, sha, tables_in_prod = _prepare_kb(cfg, run_dir, no_write, log)
    except kb.Stop as e:
        R["stopped"] = str(e)
        log("stop", e)
        _summary(cfg, run_dir, R, [], flags, {}, 0)
        return R
    R["sha1_before"] = sha
    models = kb_models(before)
    if only:
        want = {_norm(x) for x in only}
        models = [m for m in models if _norm(m["model"]) in want or _norm("%s %s" % (m["make"], m["model"])) in want]
    models.sort(key=lambda m: -m["nv"]) if not only else None
    if max_models is not None:
        models = models[:max_models]
    fetcher = fetch.Fetcher(cfg, log=log)
    conn = kb.ro(before)
    on_ac, on_cw = rc["sources"]["autocar"]["enabled"], rc["sources"]["carwale"]["enabled"]
    if not on_ac:
        log("config", "reviews.sources.autocar.enabled is false: Autocar is not fetched")
    engine, text_off = None, no_text
    if not no_text:
        try:
            engine = make_engine(cfg, run_dir, log)
            engine.write_only = write_only
        except ValueError as e:
            R["stopped"] = "text layer refused to start: %s" % e
            log("stop", R["stopped"])
            _summary(cfg, run_dir, R, [], flags, {}, 0)
            return R
    nfrac = min(1.0, max(rc["numbers_fraction"], rc["numbers_min"] / max(1, len(models))))
    now = fetch.now_iso()
    ops, rows, summary = [], [], []
    R["numbers_check"], R["not_reached"] = {}, []

    def stop_text(e, where):
        nonlocal text_off
        text_off = True
        R["text_stopped"] = {"role": e.role, "why": e.why, "at": where}
        log("llm", "%s ran out (%s): text stops here; the cache keeps everything obtained so far, rerun to resume" % (e.role, e.why))

    def tally(src, info):
        t = R["text"].setdefault(src, {"verified": 0, "ok": 0, "unchecked": 0})
        t["verified"] += info["checked"]
        t["ok"] += info["supported"]
        t["unchecked"] += info["unchecked"]

    def numbers(src, m, ev, scores, key):
        ok, n = engine.check_numbers(src, key, ev, scores, lambda s, f, d: flags.add(m["make"], m["model"], s, f, d))
        t = R["numbers_check"].setdefault(src, {"checked": 0, "ok": 0, "models": 0})
        t["checked"] += n
        t["ok"] += ok
        t["models"] += 1 if n else 0

    for idx, m in enumerate(models):
        key = "%s %s" % (m["make"], m["model"])
        S = {"model": key, "ac": None, "cw": None, "notes_kept": 0, "notes_dropped": 0, "themes_kept": 0, "themes_dropped": 0, "text": ""}
        summary.append(S)
        log("model", key)
        notes = {}
        fl = lambda src: (lambda s, f, d: flags.add(m["make"], m["model"], s, f, d))
        if text_off and engine and not no_text:
            R["not_reached"] = [("%s %s" % (x["make"], x["model"])) for x in models[idx:]]
            summary.pop()
            log("llm", "stopping the run before %s: %d models not reached" % (key, len(R["not_reached"])))
            break
        if on_ac and (force or not _fresh(conn, m["id"], SRC_AUTOCAR, rc["refresh_days"])):
            ac = autocar_model(cfg, fetcher, m, flags, log)
            if ac:
                p = ac["parsed"]
                S["ac"] = (p["overall"] if p["overall"] is not None else p["ld_overall"], p["published_on"])
                if engine and not text_off:
                    try:
                        verify = verify_all or RT.sampled(cfg["seed"], key, "autocar", rc["verify_fraction"])
                        notes, info = engine.autocar_notes(key, p, verify, fl("autocar"))
                        for n in notes.values():
                            n["_method"] = "llm writer %s; checked by %s" % (info["writer_model"], info["checker_model"] or "not sampled")
                        S["notes_kept"], S["notes_dropped"], S["text"] = info["kept"], info["dropped"], info["status"]
                        tally("autocar", info)
                        if RT.sampled(cfg["seed"], key, "numbers-autocar", nfrac):
                            sc = [("overall", p["overall"] if p["overall"] is not None else p["ld_overall"])] + [(l, p["aspects"][l]) for l in AC.ASPECTS]
                            numbers("autocar", m, ac["score_text"], [(l, v, RT._fmt(v), 0.01) for l, v in sc if v is not None], key)
                    except RT.TextStop as e:
                        S["text"] = "text stopped: %s" % e
                        stop_text(e, key)
                    except RT.TextFail as e:
                        S["text"] = "text failed: %s" % str(e)[:120]
                        flags.add(m["make"], m["model"], "autocar", "TEXT_FAILED", e)
                ops_m = assessment_ops(cfg, m, ac, notes, now)
                ops += ops_m
                rows += [("assessment", m["make"], m["model"], o["aspect"], o["score"], o["scale_max"], o["published_on"], o["status"], o["url"]) for o in ops_m]
        elif on_ac:
            log("autocar", "%s: current rows are younger than %d days, not re-read" % (key, rc["refresh_days"]))
        if on_cw and (force or not _fresh(conn, m["id"], SRC_CARWALE, rc["refresh_days"])):
            cw = carwale_model(cfg, fetcher, m, flags, log, want_text=bool(engine and not text_off))
            if cw:
                p = cw["parsed"]
                S["cw"] = (p["overall"], p["rating_count"])
                ops_m = rating_ops(m, cw)
                ops += ops_m
                rows += [("owner_rating", m["make"], m["model"], o["aspect"], o["score"], o["scale_max"], o["rating_count"], "current", o["url"]) for o in ops_m]
                if engine and not text_off:
                    items = carwale_items(cw, cfg)
                    try:
                        verify = verify_all or RT.sampled(cfg["seed"], key, "carwale", rc["verify_fraction"])
                        themes, info = engine.themes(key, "carwale", items, "owner reviews", verify, fl("carwale"))
                        method = "kbpipe/%s carwale_reviews_llm; writer %s; checked by %s" % (__version__, info["writer_model"], info["checker_model"] or "not sampled")
                        ops += theme_ops(m, SRC_CARWALE, themes, info["sampled"], cw["review_urls"], now, method)
                        for t in themes:
                            rows.append(("owner_theme", m["make"], m["model"], "%s%s" % (t["theme"], ":" + t["label"] if t["label"] else ""), t["mentions"], info["sampled"], t["direction"], "current", ""))
                        S["themes_kept"], S["themes_dropped"] = info["kept"], info["dropped"]
                        tally("carwale", info)
                        S["text"] = (S["text"] + "; " if S["text"] else "") + info["status"]
                        if RT.sampled(cfg["seed"], key, "numbers-carwale", nfrac):
                            sc = [("overall", p["overall"], RT._fmt(p["overall"]), 0.051)] + [(l, p["aspects"][l], "%.2f" % p["aspects"][l], 0.051) for l in CW.ASPECTS if p["aspects"].get(l) is not None]
                            numbers("carwale", m, cw["score_text"], sc, key)
                    except RT.TextStop as e:
                        S["text"] = (S["text"] + "; " if S["text"] else "") + "text stopped: %s" % e
                        stop_text(e, key)
                    except RT.TextFail as e:
                        S["text"] = (S["text"] + "; " if S["text"] else "") + "text failed: %s" % str(e)[:120]
                        flags.add(m["make"], m["model"], "carwale", "TEXT_FAILED", e)
        elif on_cw:
            log("carwale", "%s: current rows are younger than %d days, not re-read" % (key, rc["refresh_days"]))
    conn.close()
    # verifier bar per source: below it that source's TEXT is not written (numbers still are)
    for src, t in R["text"].items():
        if t["verified"]:
            t["accuracy"] = round(t["ok"] / t["verified"], 4)
            if t["accuracy"] < rc["verify_bar"]:
                t["withheld"] = True
                log("verify", "%s text below the %.0f%% bar (%d of %d): text not written" % (src, 100 * rc["verify_bar"], t["ok"], t["verified"]))
    for o in ops:
        if o["op"] == "assessment" and R["text"].get("autocar", {}).get("withheld"):
            o["note"] = o["quote"] = None
    if R["text"].get("carwale", {}).get("withheld"):
        ops = [o for o in ops if o["op"] != "owner_theme"]
    for o in ops:
        if o["op"] == "assessment":
            o.pop("_method", None)
    cs = {"run": run_id, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "observations": {}, "ops": ops}
    with open(os.path.join(run_dir, "changeset.json"), "w") as f:
        json.dump(cs, f, default=str)
    _tsv(os.path.join(run_dir, "reviews_rows.tsv"), ["kind", "make", "model", "aspect", "score_or_mentions", "scale_or_sampled", "published_or_count_or_direction", "status", "url"], rows)
    if engine:
        R["llm_calls"] = engine.stats["writer_calls"] + engine.stats["checker_calls"]
        R["llm"] = dict(engine.stats)
        R["backends_out"] = {"writer": getattr(engine.writer, "dead_why", {}), "checker": getattr(engine.checker, "dead_why", {})}
        with open(os.path.join(run_dir, "text_audit.jsonl"), "w") as f:
            for a in engine.audit:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        with open(os.path.join(run_dir, "numbers_check.jsonl"), "w") as f:
            for a in engine.numbers:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        wm = sorted({c["model"] for c in getattr(engine.writer, "calls", [])})
        cm = sorted({c["model"] for c in getattr(engine.checker, "calls", [])})
        R["text_models"] = {"writers": wm, "checkers": cm, "independent": not (set(wm) & set(cm))}
        for src, t in R["numbers_check"].items():
            if t["checked"]:
                t["accuracy"] = round(t["ok"] / t["checked"], 4)
                if t["accuracy"] < rc["numbers_bar"]:
                    t["below_bar"] = True
                    log("verify", "%s numbers re-check %d of %d = %.1f%%, below the %.0f%% bar (plan section 5: that source is not written)" % (
                        src, t["ok"], t["checked"], 100 * t["accuracy"], 100 * rc["numbers_bar"]))
        drop_ops = {"autocar": "assessment", "carwale": "owner_rating"}
        for src, t in R["numbers_check"].items():
            if t.get("below_bar"):
                ops = [o for o in ops if o["op"] != drop_ops[src]]
                cs["ops"] = ops
                with open(os.path.join(run_dir, "changeset.json"), "w") as f:
                    json.dump(cs, f, default=str)
    else:
        R["llm_calls"] = 0
    _stage_and_write(cfg, cs, run_dir, before, tables_in_prod, no_write, R, log)
    R["fetch"] = fetcher.stats
    R["blocks"] = list(getattr(fetcher, "blocks", []))
    for u, why in R["blocks"]:
        flags.add("", "", "fetch", "BLOCKED_" + why.upper().replace(":", "_"), u)
    R["runtime_seconds"] = round(time.time() - t0, 1)
    _tsv(os.path.join(run_dir, "flags.tsv"), ["make", "model", "source", "flag", "detail"], flags.rows)
    with open(os.path.join(run_dir, "run.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    _summary(cfg, run_dir, R, summary, flags, rc, len(ops))
    log("done", os.path.join(run_dir, "RUN_SUMMARY.md"))
    return R


def _stage_and_write(cfg, cs, run_dir, before, tables_in_prod, no_write, R, log):
    if not cs["ops"]:
        log("write", "nothing to write")
        return
    cfg2 = json.loads(json.dumps(cfg))
    if not tables_in_prod:
        cfg2["schema_sha256"] = None      # the scratch copy was migrated; its own pre-run schema is the reference
    ok, st = write.stage(cfg2, cs, run_dir, before, log)
    R["stage"] = {k: v for k, v in st.items() if k not in ("staging", "before")}
    log("gates", "staging %s: %s" % ("passed" if ok else "FAILED", json.dumps({k: v["ok"] for k, v in st.get("gates", {}).items()})))
    if not ok:
        R["stopped"] = "gates failed on staging; nothing was merged (%s)" % (st.get("error") or "; ".join(
            "%s: %s" % (k, v["detail"][0]) for k, v in st["gates"].items() if not v["ok"]) or "not idempotent")
        return
    if no_write:
        R["stopped"] = "--no-write: staged and gated, the KB was not touched"
        return
    try:
        R["write"] = write.promote(cfg, cs, run_dir, st, log)
        log("write", "KB updated: %s -> %s" % (R["write"]["sha1_before"][:8], R["write"]["sha1_after"][:8]))
        _changelog(cfg, R, cs)
    except (kb.Stop, Exception) as e:
        R["stopped"] = "write stopped: %s" % e
        log("stop", R["stopped"])


def _changelog(cfg, R, cs):
    n = {}
    for o in cs["ops"]:
        n[o["op"]] = n.get(o["op"], 0) + 1
    with open(cfg["changelog"], "a") as f:
        f.write("\n## kbpipe reviews %s\n- %s\n- KB SHA-1 %s -> %s; backup %s\n" % (
            R["run"], ", ".join("%d %s rows" % (v, k) for k, v in sorted(n.items())), R["write"]["sha1_before"],
            R["write"]["sha1_after"], R["write"]["backup"]))


def _summary(cfg, run_dir, R, summary, flags, rc, nops):
    L = ["# kbpipe reviews run %s" % R["run"], "", "Started %s. Mode: %s." % (R["started"], "no-write" if (R.get("stopped") or "").startswith("--no-write") or not R.get("write") else "write")]
    if R["stopped"]:
        L.append("\n**Stopped / status:** %s" % R["stopped"])
    L += ["", "## Per model", "", "| Model | Autocar overall (review date) | CarWale overall (ratings) | Notes kept / dropped | Themes kept / dropped | Text |", "|---|---|---|---|---|---|"]
    for S in summary:
        L.append("| %s | %s | %s | %d / %d | %d / %d | %s |" % (
            S["model"], "%s (%s)" % S["ac"] if S["ac"] else "none", "%s (%s)" % S["cw"] if S["cw"] else "none",
            S["notes_kept"], S["notes_dropped"], S["themes_kept"], S["themes_dropped"], S["text"] or "-"))
    L += ["", "## Text verification (source: run.json, text_audit.jsonl)", ""]
    for src, t in sorted(R.get("text", {}).items()):
        L.append("- %s: %d of %d checked claims supported%s%s" % (src, t["ok"], t["verified"], " (withheld: below bar)" if t.get("withheld") else "",
                                                                  ", %d kept without a check (not sampled)" % t["unchecked"] if t.get("unchecked") else ""))
    if not R.get("text"):
        L.append("- no text extraction ran")
    if R.get("text_models"):
        tm = R["text_models"]
        L.append("- writer model(s): %s; checker model(s): %s; independent: %s" % (", ".join(tm["writers"]), ", ".join(tm["checkers"]), tm["independent"]))
    for role, d in (R.get("backends_out") or {}).items():
        for name, why in d.items():
            L.append("- %s backend %s ran out and was skipped: %s" % (role, name, why[:160]))
    if R.get("text_stopped"):
        L.append("- **text stopped** (%(role)s out: %(why)s) at %(at)s. %(n)d models not reached; rerun with the same command to resume from the cache." % dict(R["text_stopped"], n=len(R.get("not_reached") or [])))
    for src, t in sorted((R.get("numbers_check") or {}).items()):
        if t["checked"]:
            L.append("- numbers re-check %s: %d of %d scores confirmed on the page (%d models)%s" % (src, t["ok"], t["checked"], t["models"], " BELOW BAR, source numbers withheld" if t.get("below_bar") else ""))
    L += ["", "## Counts", "", "- change-set ops: %d (changeset.json)" % nops, "- LLM calls made: %s (%s; llm_calls.jsonl); cache hits: writer %s, checker %s" % (R.get("llm_calls", 0), "writer %s, checker %s" % ((R.get("llm") or {}).get("writer_calls", 0), (R.get("llm") or {}).get("checker_calls", 0)), (R.get("llm") or {}).get("writer_cache_hits", 0), (R.get("llm") or {}).get("checker_cache_hits", 0)),
          "- fetches: %s" % json.dumps(R.get("fetch", {})), "- flags: %d (flags.tsv)" % len(flags.rows)]
    if R.get("stage"):
        L.append("- gates: %s; idempotent: %s" % (json.dumps({k: v["ok"] for k, v in R["stage"].get("gates", {}).items()}), R["stage"].get("idempotent")))
    if R.get("blocks"):
        L += ["", "## Blocked or unreachable fetches"] + ["- %s: %s" % (why, u) for u, why in R["blocks"]]
    with open(os.path.join(run_dir, "RUN_SUMMARY.md"), "w") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- Team-BHP helpers (no network)
def teambhp_links(cfg, run_dir, models=None):
    """teambhp_links.html: one search link per model, most popular first (popularity proxy: variants in the KB).
    Generating the file fetches nothing; the owner clicks, saves the page in a browser, and runs --import-saved."""
    if models is None:
        tmp = os.path.join(cfg["cache_dir"], "links_probe.db")
        kb.copy_for_read(cfg["prod_db"], tmp)
        models = kb_models(tmp)
        os.remove(tmp)
    models = sorted(models, key=lambda m: (-m["nv"], m["make"], m["model"]))
    rows = []
    for m in models:
        q = "site:team-bhp.com official review %s %s" % (m["make"], m["model"])
        rows.append('<li><a href="https://www.google.com/search?q=%s" target="_blank" rel="noopener">%s %s</a> <small>(%d variants in the KB)</small></li>'
                    % (re.sub(r"%20", "+", __import__("urllib.parse").parse.quote(q)), html.escape(m["make"]), html.escape(m["model"]), m["nv"]))
    page = ("<!doctype html><meta charset=utf-8><title>Team-BHP links</title><h1>Team-BHP threads to save</h1>"
            "<p>Open each link in your normal browser, open the official review thread, and save the page (File, Save Page As, "
            "Webpage HTML only) into <code>%s</code>. Then run <code>kbpipe reviews --import-saved &lt;folder&gt;</code>. "
            "This file only holds links; kbpipe never contacts Team-BHP.</p><ol>%s</ol>" % (html.escape(cfg["reviews"]["saved_pages_dir"]), "\n".join(rows)))
    path = os.path.join(run_dir, "teambhp_links.html")
    with open(path, "w") as f:
        f.write(page)
    return path


def _saved_url(page):
    for pat in (r"saved from url=\(\d+\)\s*(\S+?)\s*-->", r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', r'<meta[^>]+property="og:url"[^>]+content="([^"]+)"'):
        m = re.search(pat, page, re.I)
        if m:
            return html.unescape(m.group(1))
    return None


def _saved_posts(page):
    posts = [(m.group(1), re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip())
             for m in re.finditer(r'<div[^>]*id="post_message_(\d+)"[^>]*>(.*?)</div>', page, re.S)]
    if not posts:
        posts = [(str(i), re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))).strip())
                 for i, m in enumerate(re.finditer(r"<article[^>]*>(.*?)</article>", page, re.S))]
    return [(i, t) for i, t in posts if len(t) >= 40]


def _which_model(models, title, url):
    hay = " %s " % _norm("%s %s" % (title, url))
    best, tie = None, False
    for m in models:
        for name in ("%s %s" % (m["make"], m["model"]), m["model"]):
            n = _norm(name)
            if len(n) >= 4 and " %s " % n in hay:
                score = len(n)
                if best is None or score > best[0]:
                    best, tie = (score, m), False
                elif score == best[0] and best[1]["id"] != m["id"]:
                    tie = True
    return (best[1] if best and not tie else None)


def import_saved(cfg, folder, no_write=True, label=None, ask=None, verify_all=True, echo=print):
    """Read locally saved Team-BHP pages (never fetches anything) and write owner_theme rows, source 'Team-BHP (owner-saved pages)',
    extraction_method 'saved_page_llm'. The saved files are only read."""
    folder = os.path.abspath(os.path.expanduser(folder))
    run_dir, run_id = _run_dir(cfg, label or datetime.now(timezone.utc).strftime("saved_%Y-%m-%d"))
    flags, R = Flags(), {"run": run_id, "started": fetch.now_iso(), "stopped": None, "write": None, "stage": None, "text": {}}

    def log(stage, *msg):
        line = "%s [%s] %s" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), stage, " ".join(str(x) for x in msg))
        echo(line)
        with open(os.path.join(run_dir, "run.log"), "a") as f:
            f.write(line + "\n")
    try:
        before, sha, tables_in_prod = _prepare_kb(cfg, run_dir, no_write, log)
    except kb.Stop as e:
        R["stopped"] = str(e)
        _summary(cfg, run_dir, R, [], flags, {}, 0)
        return R
    models = kb_models(before)
    files = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith((".html", ".htm"))) if os.path.isdir(folder) else []
    groups = {}
    for fp in files:
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            page = f.read()
        url = _saved_url(page)
        title = (re.search(r"<title[^>]*>(.*?)</title>", page, re.S) or [None, ""])[1]
        m = _which_model(models, title, url or "")
        if m is None and ask:
            ans = ask("Which model is %s (%s)? " % (os.path.basename(fp), title.strip()[:80]))
            m = next((x for x in models if _norm("%s %s" % (x["make"], x["model"])) == _norm(ans) or _norm(x["model"]) == _norm(ans)), None)
        if m is None:
            flags.add("", "", "teambhp_saved", "MODEL_UNKNOWN", os.path.basename(fp))
            continue
        if not url:
            flags.add(m["make"], m["model"], "teambhp_saved", "URL_UNKNOWN", os.path.basename(fp))
            continue
        g = groups.setdefault(m["id"], {"m": m, "posts": [], "urls": {}})
        for pid, text in _saved_posts(page):
            g["posts"].append({"id": "%s#%s" % (url, pid), "text": text[:600]})
            g["urls"]["%s#%s" % (url, pid)] = "%s#post%s" % (url.split("#")[0], pid)
    try:
        engine = make_engine(cfg, run_dir, log)
    except ValueError as e:
        R["stopped"] = "text layer refused to start: %s" % e
        _summary(cfg, run_dir, R, [], flags, {}, 0)
        return R
    now, ops, summary = fetch.now_iso(), [], []
    for g in groups.values():
        m = g["m"]
        S = {"model": "%s %s" % (m["make"], m["model"]), "ac": None, "cw": None, "notes_kept": 0, "notes_dropped": 0, "themes_kept": 0, "themes_dropped": 0, "text": ""}
        summary.append(S)
        try:
            themes, info = engine.themes("%s %s" % (m["make"], m["model"]), "teambhp_saved", g["posts"], "forum posts", verify_all,
                                         lambda s_, f_, d_: flags.add(m["make"], m["model"], s_, f_, d_))
        except (RT.TextStop, RT.TextFail) as e:
            S["text"] = "text stopped: %s" % str(e)[:120]
            flags.add(m["make"], m["model"], "teambhp_saved", "TEXT_FAILED", e)
            if isinstance(e, RT.TextStop):
                break
            continue
        S["themes_kept"], S["themes_dropped"], S["text"] = info["kept"], info["dropped"], info["status"]
        R["text"].setdefault("teambhp_saved", {"verified": 0, "ok": 0})
        R["text"]["teambhp_saved"]["verified"] += info["checked"]
        R["text"]["teambhp_saved"]["ok"] += info["supported"]
        ops += theme_ops(m, SRC_TBHP, themes, info["sampled"], g["urls"], now, "saved_page_llm")
    t = R["text"].get("teambhp_saved")
    if t and t["verified"] and t["ok"] / t["verified"] < cfg["reviews"]["verify_bar"]:
        t["withheld"] = True
        ops = []
    cs = {"run": run_id, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "observations": {}, "ops": ops}
    with open(os.path.join(run_dir, "changeset.json"), "w") as f:
        json.dump(cs, f, default=str)
    R["llm_calls"] = engine.stats["writer_calls"] + engine.stats["checker_calls"]
    with open(os.path.join(run_dir, "text_audit.jsonl"), "w") as f:
        for a in engine.audit:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    _stage_and_write(cfg, cs, run_dir, before, tables_in_prod, no_write, R, log)
    _tsv(os.path.join(run_dir, "flags.tsv"), ["make", "model", "source", "flag", "detail"], flags.rows)
    with open(os.path.join(run_dir, "run.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    _summary(cfg, run_dir, R, summary, flags, {}, len(ops))
    return R
