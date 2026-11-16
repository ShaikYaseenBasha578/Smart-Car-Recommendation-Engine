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
            assert h.startswith("#") or h in PAGES, (fn, h)
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
