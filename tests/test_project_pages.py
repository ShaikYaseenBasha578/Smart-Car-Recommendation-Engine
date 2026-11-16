import re
from pathlib import Path

import pytest

import app as app_module

ROOT = Path(__file__).resolve().parent.parent
URLS = ["/project", "/project/pipeline", "/project/knowledge-base", "/project/engine"]


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.mark.parametrize("url", URLS)
def test_project_pages_serve_html(client, url):
    r = client.get(url)
    assert r.status_code == 200
    assert r.mimetype == "text/html"
    assert b"<html" in r.data.lower()
    assert "max-age" in r.headers["Cache-Control"]


@pytest.mark.parametrize("url", ["/project/nope", "/project/index.html", "/project/pipeline.html",
                                 "/project/..%2fapp.py", "/project/%2e%2e/app.py", "/project/../app.py",
                                 "/project/pipeline/extra", "/project/..%5capp.py"])
def test_unknown_and_traversal_are_404(client, url):
    assert client.get(url).status_code == 404


def test_home_and_results_link_to_project(client):
    for url in ("/", "/recommend"):
        assert 'href="/project"' in client.get(url).get_data(as_text=True)
    home = client.get("/").get_data(as_text=True)
    for url in URLS[1:]:
        assert 'href="%s"' % url in home


@pytest.mark.parametrize("name", ["index", "pipeline", "kb", "engine"])
def test_page_files_are_clean(name):
    html = (ROOT / "project_pages" / (name + ".html")).read_text(encoding="utf-8")
    assert not re.search(r'(?:src|href)\s*=\s*["\']?\s*(?:https?:)?//', html, re.I)
    assert not re.search(r"url\(\s*['\"]?\s*(?:https?:)?//", html, re.I)
    for bad in ("/Users/", "worktree", "feat/", "kb/kbpipe"):
        assert bad not in html
    assert not re.search(r'href="(?:index|pipeline|kb|engine)\.html', html)


def test_sync_script_is_idempotent(tmp_path):
    from scripts import sync_project_pages as sp
    src = tmp_path / "src"
    src.mkdir()
    for n in ("index", "pipeline", "kb", "engine"):
        (src / (n + ".html")).write_text('<a href="kb.html#x">k</a><a href="/">h</a>')
    out = tmp_path / "out"
    assert len(sp.sync(src, out)) == 4
    assert sp.sync(src, out) == []
    assert 'href="/project/knowledge-base#x"' in (out / "kb.html").read_text()
