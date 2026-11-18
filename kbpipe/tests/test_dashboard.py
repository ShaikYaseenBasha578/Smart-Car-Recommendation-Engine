"""The site generator runs on a tiny synthetic KB with no runs, no history and no recommender checkout, and is deterministic."""
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import make_kb  # noqa: E402
from kbpipe import dashboard  # noqa: E402

PAGES = ["index.html", "pipeline.html", "kb.html", "engine.html"]


class Tags(HTMLParser):
    VOID = {"meta", "br", "img", "input", "link", "hr", "path", "rect", "circle", "line", "stop"}

    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.hrefs = [], [], []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "href" in d:
            self.hrefs.append(d["href"])
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(tag)
        else:
            self.stack.pop()


def run(tmp_path, extra=()):
    db = make_kb(str(tmp_path / "kb.db"))
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    out = tmp_path / "site"
    argv = ["--db", db, "--runs", str(runs), "--history", str(tmp_path / "nohist"), "--date", "2026-01-02",
            "--recsys-dir", str(tmp_path / "no_recsys"), "--out-dir", str(out)] + list(extra)
    assert dashboard.main(argv) == 0
    return out, argv


def test_site_on_synthetic_fixture(tmp_path):
    out, argv = run(tmp_path)
    first = {}
    for fn in PAGES:
        html = (out / fn).read_text()
        first[fn] = html
        assert re.search(r"<title>[^<]{3,40}</title>", html)
        assert "http://" not in html and "https://" not in html
        assert not re.search(r"<script[^>]+src=|<link[^>]+rel=.stylesheet|@import|url\(", html)
        t = Tags()
        t.feed(html)
        assert not t.errors and not t.stack, (fn, t.errors, t.stack)
        for h in t.hrefs:
            assert h.startswith("#") or h.split("#")[0] in PAGES, (fn, h)
        assert 'aria-current="page"' in html
        assert "2026-01-02" in html and "/Users/" not in html
    assert "Data not found" in first["engine.html"]
    assert "Back to CarRec" not in first["index.html"]
    assert dashboard.main(argv) == 0   # same inputs, same bytes
    assert all((out / fn).read_text() == first[fn] for fn in PAGES)


def test_app_base_adds_back_link_and_keeps_relative_links(tmp_path):
    out, _ = run(tmp_path, ["--app-base", "/"])
    html = (out / "kb.html").read_text()
    assert '<a class="back" href="/">Back to CarRec</a>' in html
    assert 'href="pipeline.html"' in html


def test_out_index_path_writes_sibling_pages(tmp_path):
    db = make_kb(str(tmp_path / "kb.db"))
    (tmp_path / "runs").mkdir()
    out = tmp_path / "o" / "index.html"
    argv = ["--db", db, "--runs", str(tmp_path / "runs"), "--history", str(tmp_path / "h"), "--date", "2026-01-02",
            "--recsys-dir", str(tmp_path / "none"), "--out", str(out)]
    assert dashboard.main(argv) == 0
    assert all((tmp_path / "o" / fn).exists() for fn in PAGES)


def test_public_check_rejects_local_notes():
    for bad in ["see /Users/x/file", "branch feat/x", "a worktree", "kbpipe", "Sonnet"]:
        try:
            dashboard.check_public("t.html", "<p>%s</p>" % bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_header_is_one_compact_row_on_phones_and_keeps_the_theme_key(tmp_path):
    out, _ = run(tmp_path, ["--app-base", "/"])
    html = (out / "index.html").read_text()
    css = html.split("<style>")[1].split("</style>")[0]
    phone = css.split("@media (max-width:760px){")[1].split("\n}")[0]
    assert "flex-wrap:nowrap" in phone and "overflow-x:auto" in phone and "height:63px" in phone
    assert "localStorage.getItem('carrec-theme')" in html


def test_engine_page_prefers_the_final_result_files_and_drops_the_unsaved_note(tmp_path):
    import json
    root = tmp_path / "rec"
    (root / "eval" / "results").mkdir(parents=True)

    def ev(engine, recall):
        return {"engine": engine, "n_queries": 10, "summary": {
            "constraint_satisfaction": {"queries_with_cars": 10, "queries_zero_violations": 10, "violations": []},
            "relaxed_responses": {"n": 1, "truthfully_labelled": 1, "mislabelled": 0},
            "empty_handling": {"expect_empty_queries": 2, "outcomes": {"empty": 0, "cars_returned_unmarked": 1}},
            "unknown_probe": {"n_probes": 5, "still_returned": 5, "known_lacking_above": 1, "known_lacking_newly_above": 0},
            "shortlist_agreement": {"filled": 3, "recall_at_8": recall, "mrr": recall}}, "records": []}
    for name, e in [("final_v3_main", ev("v3", .9)), ("final_v3_heldout", ev("v3", .8)), ("final_current_main", ev("current", .7))]:
        (root / "eval" / "results" / (name + ".json")).write_text(json.dumps(e))
    E_ = dashboard.engine_data(str(root))
    assert E_["v3_main"]["file"] == "final_v3_main.json" and E_["cur_main"]["file"] == "final_current_main.json"
    assert E_["cur_held"] is None


def test_evidence_classes_and_honest_wording(tmp_path):
    cl = dashboard.classify_cell
    assert cl(None) == "none"
    assert cl([{"oem", "carwale"}, True]) == "brochure"
    assert cl([{"carwale", "cardekho"}, False]) == "two_sites"
    assert cl([{"carwale", "v6_migration"}, False]) == "one_site"
    assert cl([{"v6_migration"}, False]) == "import"
    out, _ = run(tmp_path)
    kb = (out / "kb.html").read_text()
    assert "June 2026 import only" in kb and "Page generated" in kb
    for fn in PAGES:
        html = (out / fn).read_text()
        assert "Every value has" not in html and "Every match comes from a verified" not in html


def test_price_freshness_bands_and_import_only(tmp_path):
    import sqlite3
    from conftest import make_kb
    db = make_kb(str(tmp_path / "p.db"))
    c = sqlite3.connect(db)
    c.executescript("""
    insert into source_observation(id,source_id,raw_name,source_url,observed_at,resolution_status) values
      (1,1,'a',null,'2026-06-28','applied'),(2,4,'b','https://x','2026-11-13T10:00:00Z','applied');
    insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision) values
      (1,'price_ex_showroom','800000',1,'accepted'),(2,'price_ex_showroom','1100000',1,'accepted'),(2,'price_ex_showroom','1100000',2,'confirmed');
    """)
    c.commit()
    c.row_factory = sqlite3.Row
    vrows = [{"id": 1, "base_variant_id": None, "price_ex_showroom": 800000}, {"id": 2, "base_variant_id": None, "price_ex_showroom": 1100000}]
    p = dashboard.price_freshness(c, vrows, "2026-11-16")
    assert (p["within30"], p["within90"], p["within180"], p["import_only"], p["no_evidence"]) == (1, 1, 1, 1, 0)
    assert p["import_age"] == 141


def test_verified_satisfaction_reads_named_fields(tmp_path):
    """Regression (18 Nov): the summary also holds a text "scope" field, and the page used to require every field to be a
    number, so it always said the figure was "being added"."""
    import json
    from kbpipe import dashboard as D
    def put(name, verified, cars):
        (tmp_path / name).write_text(json.dumps({"summary": {"verified_satisfaction": {
            "scope": "non-relaxed responses only", "queries_with_cars": cars, "queries_verified": verified,
            "share_verified": verified / cars, "queries_with_unverified": cars - verified}}}))
    put("audit_fix_v3_main.json", 180, 193)
    put("audit_fix_current_main.json", 175, 193)
    vs = D.verified_satisfaction(str(tmp_path))
    assert vs["v3_main"]["verified"] == 180 and vs["current_main"]["with_cars"] == 193 and "v3_heldout" not in vs
    assert D.verified_satisfaction(str(tmp_path / "missing")) is None
