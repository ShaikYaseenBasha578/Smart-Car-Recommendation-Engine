import json
import os
import sqlite3

import pytest

from kbpipe import changeset, fetch, gates, kb, reviews, write
from kbpipe.migrations import reviews_tables as MIG
from kbpipe.sources import autocar_reviews as AC
from kbpipe.sources import carwale_ratings as CW

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "reviews")
ASPECT_SCORES = dict(zip(AC.ASPECTS, [8, 7, 6, 8, 8, 8, 8]))


def autocar_page(name="Tata Nexon", make_s="tata", model_s="nexon", overall=8, ld=8.0, scores=None, drop=None):
    scores = scores or ASPECT_SCORES
    ld_json = json.dumps({"@context": "https://schema.org", "@graph": [{"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item": {
        "@type": "Review", "name": name + " review", "itemReviewed": {"@type": ["Product", "Car"], "name": name},
        "reviewRating": {"@type": "Rating", "ratingValue": "%.1f" % ld, "bestRating": "10", "worstRating": "1"},
        "datePublished": "2025-07-04"}}]}]}) if ld is not None else "{}"
    asp = ""
    for label, v in scores.items():
        if label == drop:
            continue
        asp += ('<span class="text-sm font-medium">%s</span><div class="relative flex size-8 items-center justify-center"><svg></svg>'
                '<p class="text-[10px] font-semibold">%s</p></div><div class="styledInnerHTML_x prose"><p>Reviewer text about %s is long enough here.</p></div>' % (label, v, label))
    ov = '<div>Autocar score</div><div class="x"><span class="b">%s</span></div>' % overall if overall is not None else ""
    return ('<html><head><title>x | Autocar India</title><link rel="canonical" href="https://www.autocarindia.com/cars/%s/%s/expert-reviews"/>'
            '<script type="application/ld+json">%s</script></head><body><h1>%s Expert Review</h1><p>Last Updated on: <!-- -->13 Nov 2026</p>'
            '<div id="pros-and-cons"><h3>We like</h3><ul><li>Strong safety kit</li><li>Smooth ride quality</li></ul><h3>We don\'t like</h3><ul><li>Weak engine</li></ul>'
            '<h2>%s Expert Review</h2></div>%s%s</body></html>' % (make_s, model_s, ld_json, name, name, ov, asp))


def carwale_page(make="Tata", model="Nexon", total=120, reviews=None, aspects=True, overall=4.5, rating_count=300, page=1):
    params = [{"QuestionId": q, "MinHeading": h, "Answer": 4.2} for q, h in CW.ASPECT_IDS.items()] if aspects else []
    params.append({"QuestionId": 155, "MinHeading": "Would you be interested?", "Answer": 1.1})
    state = {"userReviewListing": {"modelDetails": {"makeName": make, "modelName": model},
             "aggregateRating": {"totalRatings": rating_count, "overallRating": overall, "reviewCount": {"total": total},
                                 "reviewParameters": params, "vehicleInfo": {"ModelId": 5}},
             "userReviewList": {"Reviews": reviews if reviews is not None else [], "TotalRecordCount": total}}}
    return '<html><body><script type="application/json" id="initial-state">%s</script></body></html>' % json.dumps(state)


def cw_reviews(start, n=10, text="The service cost is very high and the AC failed twice"):
    return [{"Id": start + i, "Title": "T%d" % i, "Description": "%s (review %d)" % (text, start + i), "RatingInfo": {"UserRating": 4},
             "VehicleInfo": {"VersionId": 1}, "LastUpdatedOn": "x"} for i in range(n)]


# ------------------------------------------------------------------ parsers
def test_autocar_parser_synthetic():
    p = AC.parse(autocar_page())
    assert p["page_name"] == "Tata Nexon" and p["overall"] == 8.0 and p["ld_overall"] == 8.0 and p["published_on"] == "2025-07-04"
    assert p["last_updated"] == "13 Nov 2026" and p["aspects"] == {k: float(v) for k, v in ASPECT_SCORES.items()}
    assert p["pros"] == ["Strong safety kit", "Smooth ride quality"] and p["cons"] == ["Weak engine"]
    assert reviews.validate_autocar(p) == (True, [])
    assert "Reviewer text about Value For Money" in AC.text_blob(p)


def test_autocar_validation_rules():
    p = AC.parse(autocar_page(drop="Value For Money"))
    ok, bad = reviews.validate_autocar(p)
    assert not ok and "aspect missing: Value For Money" in bad[0]
    ok, bad = reviews.validate_autocar(AC.parse(autocar_page(overall=7, ld=8.0)))
    assert not ok and "differs" in bad[0]
    ok, bad = reviews.validate_autocar(AC.parse(autocar_page(scores=dict(ASPECT_SCORES, **{"Features And Safety": 11}))))
    assert not ok and "outside 0..10" in bad[0]
    ok, _ = reviews.validate_autocar(AC.parse(autocar_page(overall=None, ld=None)))
    assert ok            # aspects only (the Elevate case): kept, flagged, no overall row


def test_carwale_parser_and_validation():
    p = CW.parse(carwale_page(reviews=cw_reviews(1)))
    assert p["overall"] == 4.5 and p["rating_count"] == 300 and p["review_count"] == 120 and len(p["aspects"]) == 7 and len(p["reviews"]) == 10
    assert "Would you be interested?" not in p["aspects"]
    assert reviews.validate_carwale(p) == (True, [])
    assert not reviews.validate_carwale(CW.parse(carwale_page(aspects=False)))[0]
    assert not reviews.validate_carwale(CW.parse(carwale_page(rating_count=0)))[0]
    assert not reviews.validate_carwale(CW.parse(carwale_page(overall=6)))[0]
    assert CW.parse("<html>blocked</html>") is None


def test_wrong_page_check():
    p = AC.parse(autocar_page(name="Tata Punch", model_s="punch"))
    ok, why = reviews.autocar_identity(p, "Tata", "Nexon", "tata", "nexon")
    assert not ok and "Punch" in why
    p = AC.parse(autocar_page(name="Tata Nexon", model_s="nexon-ev"))          # redirected to another canonical page
    assert not reviews.autocar_identity(p, "Tata", "Nexon", "tata", "nexon")[0]
    assert reviews.autocar_identity(AC.parse(autocar_page()), "Tata", "Nexon", "tata", "nexon")[0]
    assert not reviews.carwale_identity(CW.parse(carwale_page(model="Punch")), "Tata", "Nexon")[0]
    assert reviews.carwale_identity(CW.parse(carwale_page()), "Tata", "Nexon")[0]


@pytest.mark.skipif(not os.path.isdir(FIX), reason="local review fixtures absent (not committed)")
@pytest.mark.parametrize("name,overall,date,cw_overall", [("creta", 9.0, "2025-10-09", 4.6), ("nexon", 8.0, "2025-07-04", 4.59), ("swift", 8.0, "2025-10-16", 4.53)])
def test_real_fixture_pages(name, overall, date, cw_overall):
    a = AC.parse(open(os.path.join(FIX, "autocar_%s.html" % name)).read())
    assert a["overall"] == overall == a["ld_overall"] and a["published_on"] == date and len(a["aspects"]) == 7
    assert reviews.validate_autocar(a)[0]
    c = CW.parse(open(os.path.join(FIX, "carwale_%s.html" % name)).read())
    assert c["overall"] == cw_overall and len(c["aspects"]) == 7 and len(c["reviews"]) == 10 and reviews.validate_carwale(c)[0]


# ------------------------------------------------------------------ migration
def test_migration_idempotent_additive_and_refuses_prod(kbfile, tmp_path):
    c = sqlite3.connect(kbfile)
    before = MIG.objects(c)
    c.close()
    r1 = MIG.migrate(kbfile)
    assert r1["integrity_check"] == "ok" and "owner_theme" in r1["created"]
    assert MIG.migrate(kbfile)["created"] == []
    c = sqlite3.connect(kbfile)
    assert MIG.objects(c) == before and MIG.has_tables(c)
    assert c.execute("select count(*) from source where name like '%Autocar%' or name like 'CarWale user%' or name like 'Team-BHP%'").fetchone()[0] == 3
    c.close()
    d = tmp_path / "knowledge_base"
    d.mkdir()
    prodlike = d / "carrec_kb.db"
    prodlike.write_bytes(b"")
    with pytest.raises(MIG.Refused):
        MIG.migrate(str(prodlike))
    assert prodlike.stat().st_size == 0                 # untouched


# ------------------------------------------------------------------ end to end on a scratch KB
class FakeBudget:
    def __init__(self, cfg, run_dir):
        self.n, self.extract, self.verify = 0, "x", "y"

    def call(self, chain, prompt, label):
        self.n += 1
        if "decide from its EVIDENCE" in prompt:
            res, cur = [], None
            for line in prompt.splitlines():
                if line.startswith("CLAIM "):
                    cur = line.split(":")[0][6:]
                elif line.startswith("EVIDENCE ") and cur is not None:
                    pass
                elif cur is not None and line.strip() and not line.startswith(("CLAIM", "EVIDENCE")) and not any(r["id"] == cur for r in res):
                    res.append({"id": cur, "verdict": "supported" if "UNSUPPORTED" not in prompt.split("CLAIM %s" % cur)[1].split("CLAIM")[0] else "not_supported", "supporting_line": line.strip()})
            return {"results": res}, "fake-verify"
        if "Autocar India" in prompt:
            return {"notes": [{"aspect": "Ride Comfort And Handling", "note": "Composed over bad roads.", "quote": "Reviewer text about Ride Comfort And Handling is long enough here."},
                              {"aspect": "Features And Safety", "note": "Feature list is strong.", "quote": "invented words not on the page"},
                              {"aspect": "Made Up Aspect", "note": "x", "quote": None}]}, "fake-extract"
        ids = [l[1:l.index("]")] for l in prompt.splitlines() if l.startswith("[")]
        return {"themes": [{"theme": "service_cost", "label": None, "direction": "negative", "review_ids": ids[:12], "note": "Owners find servicing expensive."},
                           {"theme": "recurring_fault", "label": "AC failure", "direction": "negative", "review_ids": ids[:2], "note": "x"}]}, "fake-extract"


def _setup(monkeypatch, cfg, tmp_path):
    from kbpipe.tests.conftest import make_kb
    db = make_kb(str(tmp_path / "kb.db"))
    MIG.migrate(db)
    pages = {"https://www.autocarindia.com/cars/tata/nexon/expert-reviews": autocar_page(),
             "https://www.carwale.com/tata-cars/nexon/user-reviews/": carwale_page(reviews=cw_reviews(100), total=30),
             "https://www.carwale.com/tata-cars/nexon/reviews/page/2/": carwale_page(reviews=cw_reviews(200), total=30),
             "https://www.carwale.com/tata-cars/nexon/reviews/page/3/": carwale_page(reviews=cw_reviews(300), total=30)}

    def fake_get(self, url, max_age_days=None):
        if url in pages:
            return pages[url], {"fetched_at": "2026-11-14T10:00:00Z", "status": 200}, None
        self.__dict__.setdefault("blocks", []).append((url, "blocked:403"))
        return None, None, "blocked:403"
    monkeypatch.setattr(fetch.Fetcher, "get_polite", fake_get)
    monkeypatch.setattr(reviews, "Budget", FakeBudget)
    cfg["prod_db"] = db
    return db


def test_no_write_run_stages_gates_and_leaves_prod_alone(monkeypatch, cfg, tmp_path):
    db = _setup(monkeypatch, cfg, tmp_path)
    sha = kb.sha1(db)
    R = reviews.run(cfg, only=["Nexon"], no_write=True, label="t1", verify_all=True, echo=lambda *a: None)
    assert kb.sha1(db) == sha
    assert R["stage"]["idempotent"] and all(v["ok"] for v in R["stage"]["gates"].values()), R["stage"]
    cs = json.load(open(os.path.join(cfg["runs_dir"], "t1", "changeset.json")))
    kinds = [o["op"] for o in cs["ops"]]
    assert kinds.count("assessment") == 8 and kinds.count("owner_rating") == 8
    th = [o for o in cs["ops"] if o["op"] == "owner_theme"]
    assert len(th) == 1 and th[0]["theme"] == "service_cost" and th[0]["mentions"] == 12 and th[0]["posts_sampled"] == 30   # AC fault cited by 2 only: dropped
    notes = {o["aspect"]: o for o in cs["ops"] if o["op"] == "assessment" and o.get("note")}
    assert sorted(notes) == ["Features And Safety", "Ride Comfort And Handling"] and notes["Ride Comfort And Handling"]["quote"]
    assert notes["Features And Safety"]["quote"] is None          # invented quote dropped, the note itself survives
    flags = open(os.path.join(cfg["runs_dir"], "t1", "flags.tsv")).read()
    assert "QUOTE_DROPPED" in flags and "NOTE_DROPPED" in flags and "THEME_DROPPED" in flags
    assert os.path.exists(os.path.join(cfg["runs_dir"], "t1", "reviews_rows.tsv"))
    assert "Autocar overall" in open(os.path.join(cfg["runs_dir"], "t1", "RUN_SUMMARY.md")).read()


def test_write_path_end_to_end_on_scratch_and_idempotent(monkeypatch, cfg, tmp_path):
    db = _setup(monkeypatch, cfg, tmp_path)
    R = reviews.run(cfg, only=["Nexon"], no_write=False, label="w1", verify_all=True, echo=lambda *a: None)
    assert R["write"] and R["write"]["integrity_check"] == "ok" and R["write"]["prod_equals_staging"], R
    c = sqlite3.connect(db)
    assert c.execute("select count(*) from professional_assessment where status='current'").fetchone()[0] == 8
    assert c.execute("select count(*) from owner_rating").fetchone()[0] == 8
    assert c.execute("select direction,mentions,posts_sampled from owner_theme").fetchall() == [("negative", 12, 30)]
    pa = c.execute("select published_on, source_url, extraction_method from professional_assessment where source_aspect='overall'").fetchone()
    assert pa[0] == "2025-07-04" and pa[1].startswith("https://www.autocarindia.com") and pa[2].startswith("kbpipe")
    c.close()
    cs = json.load(open(os.path.join(cfg["runs_dir"], "w1", "changeset.json")))
    assert changeset.apply(db, cs) == []                  # idempotent: the identical change-set changes nothing
    R2 = reviews.run(cfg, only=["Nexon"], no_write=True, label="w2", echo=lambda *a: None)
    assert not R2["write"] and "younger than" in open(os.path.join(cfg["runs_dir"], "w2", "run.log")).read()


def test_changed_score_supersedes_and_keeps_history(monkeypatch, cfg, tmp_path):
    db = _setup(monkeypatch, cfg, tmp_path)
    reviews.run(cfg, only=["Nexon"], no_text=True, label="h1", echo=lambda *a: None)
    cs = json.load(open(os.path.join(cfg["runs_dir"], "h1", "changeset.json")))
    for o in cs["ops"]:
        if o["op"] == "assessment" and o["aspect"] == "overall":
            o["score"], o["observed_at"] = 9.0, "2027-01-01T00:00:00Z"
    log = changeset.apply(db, cs)
    assert [r[2] for r in log].count("update") == 1
    c = sqlite3.connect(db)
    assert c.execute("select status from professional_assessment where source_aspect='overall' order by id").fetchall() == [("superseded",), ("current",)]


def test_wrong_page_and_blocks_are_recorded_not_retried(monkeypatch, cfg, tmp_path):
    db = _setup(monkeypatch, cfg, tmp_path)
    orig = fetch.Fetcher.get_polite

    def wrong(self, url, max_age_days=None):
        if "autocarindia" in url:
            return autocar_page(name="Tata Punch", model_s="punch"), {"fetched_at": "2026-11-14T10:00:00Z"}, None
        return None, None, "blocked:429"
    monkeypatch.setattr(fetch.Fetcher, "get_polite", wrong)
    reviews.run(cfg, only=["Nexon"], no_write=True, no_text=True, label="b1", echo=lambda *a: None)
    f = open(os.path.join(cfg["runs_dir"], "b1", "flags.tsv")).read()
    assert "WRONG_PAGE" in f and "UNREACHABLE" in f
    cs = json.load(open(os.path.join(cfg["runs_dir"], "b1", "changeset.json")))
    assert cs["ops"] == []


def test_off_switch_never_fetches_autocar(monkeypatch, cfg, tmp_path):
    _setup(monkeypatch, cfg, tmp_path)
    seen = []
    orig = fetch.Fetcher.get_polite
    monkeypatch.setattr(fetch.Fetcher, "get_polite", lambda self, url, max_age_days=None: (seen.append(url), orig(self, url, max_age_days))[1])
    cfg["reviews"]["sources"]["autocar"]["enabled"] = False
    reviews.run(cfg, only=["Nexon"], no_write=True, no_text=True, label="o1", echo=lambda *a: None)
    assert seen == [] or all("autocarindia" not in u for u in seen)


def test_write_refused_when_prod_lacks_tables(monkeypatch, cfg, tmp_path):
    from kbpipe.tests.conftest import make_kb
    db = make_kb(str(tmp_path / "kb.db"))
    cfg["prod_db"] = db
    sha = kb.sha1(db)
    R = reviews.run(cfg, only=["Nexon"], no_write=False, label="p1", echo=lambda *a: None)
    assert "no review tables" in R["stopped"] and kb.sha1(db) == sha


def test_gate_rejects_thin_themes(kbfile, tmp_path):
    MIG.migrate(kbfile)
    import shutil
    after = str(tmp_path / "after.db")
    shutil.copyfile(kbfile, after)
    c = sqlite3.connect(after)
    sid = c.execute("select id from source where name=?", (reviews.SRC_CARWALE,)).fetchone()[0]
    c.execute("insert into owner_theme(model_id,theme,label,direction,mentions,posts_sampled,sample_urls,source_id,extracted_at,extraction_method) "
              "values (1,'reliability',null,'negative',2,10,'[\"u\"]',?,'2026-11-14','x')", (sid,))
    c.commit()
    c.close()
    ok, detail = gates.gate_reviews(kbfile, after, {"reviews": {"min_theme_mentions": 3, "min_reviews_sampled": 20}})
    assert not ok and "below the evidence minimum" in detail[0]


# ------------------------------------------------------------------ saved pages (Team-BHP), local files only
def test_import_saved_reads_local_files_only(monkeypatch, cfg, tmp_path):
    db = _setup(monkeypatch, cfg, tmp_path)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    monkeypatch.setattr(fetch.Fetcher, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetcher used")))
    monkeypatch.setattr(fetch.Fetcher, "get_polite", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetcher used")))
    folder = tmp_path / "saved"
    folder.mkdir()
    posts = "".join('<div id="post_message_%d">Post %d: the Nexon service cost is high and the AC failed on my car number %d at the service centre.</div>' % (i, i, i) for i in range(22))
    (folder / "any name.html").write_text('<!-- saved from url=(0070)https://example.invalid/forum/thread-1-tata-nexon-review.html -->'
                                          '<html><head><title>Tata Nexon ownership review</title></head><body>%s</body></html>' % posts)
    (folder / "mystery.html").write_text("<html><title>Something else</title><body></body></html>")
    R = reviews.import_saved(cfg, str(folder), no_write=False, label="s1", verify_all=True, echo=lambda *a: None)
    assert R["write"], R
    c = sqlite3.connect(db)
    rows = c.execute("select t.theme,t.mentions,t.posts_sampled,t.extraction_method,s.name,t.sample_urls from owner_theme t join source s on s.id=t.source_id").fetchall()
    assert rows and rows[0][3] == "saved_page_llm" and rows[0][4] == reviews.SRC_TBHP and rows[0][2] == 22 and "thread-1-tata-nexon" in rows[0][5]
    assert "MODEL_UNKNOWN" in open(os.path.join(cfg["runs_dir"], "s1", "flags.tsv")).read()


def test_teambhp_links_file_has_links_only(cfg, tmp_path):
    models = [{"id": 1, "make": "Tata", "model": "Nexon", "nv": 40}, {"id": 2, "make": "Kia", "model": "Syros", "nv": 10}]
    p = reviews.teambhp_links(cfg, str(tmp_path), models)
    t = open(p).read()
    assert t.index("Nexon") < t.index("Syros") and "site%3Ateam-bhp.com" in t and "<a href=" in t
