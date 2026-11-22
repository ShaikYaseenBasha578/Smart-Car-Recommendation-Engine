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


# ---------- shared header on /project, one theme control site-wide (PR F) ----------
SUBNAV = {"/project": "Overview", "/project/pipeline": "Pipeline", "/project/knowledge-base": "Knowledge base", "/project/engine": "Engine"}


@pytest.mark.parametrize("url", URLS)
def test_project_pages_use_the_shared_header(client, url):
    r = client.get(url)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count('<header class="site-header') == 1
    for link in ('href="/recommend">Find a car', 'href="/#how-it-works" class="nav-extra">How it works'):
        assert link in html
    assert re.search(r'<a href="/project" aria-current="page">The project</a>', html)
    assert html.count('id="themebtn"') == 1
    assert "Back to CarRec" not in html
    sub = re.search(r'<nav class="nav subnav" aria-label="Project pages">(.*?)</nav>', html, re.S).group(1)
    current = re.findall(r'<a href="[^"]*" aria-current="page">([^<]*)</a>', sub)
    assert current == [SUBNAV[url]]
    assert len(re.findall(r"<a ", sub)) == 4


def test_project_unknown_is_still_404(client):
    assert client.get("/project/unknown").status_code == 404


def test_project_page_without_a_generated_header_is_served_unchanged(client, monkeypatch):
    import builtins
    page = b"<html><body><p>no header here</p></body></html>"
    real_open = builtins.open

    def fake_open(path, *a, **k):
        if str(path).endswith("index.html") and "project_pages" in str(path):
            import io
            return io.BytesIO(page)
        return real_open(path, *a, **k)

    monkeypatch.setattr(app_module, "open", fake_open, raising=False)
    r = client.get("/project")
    assert r.status_code == 200 and r.data == page
    assert "max-age" in r.headers["Cache-Control"] and r.mimetype == "text/html"


def test_overview_intro_comes_before_any_audit_figure(client):
    html = client.get("/project").get_data(as_text=True)
    assert "the app shows the" in html
    stored = html.index("variants; the app shows the")
    assert stored < html.index("June 2026 import")


def _app_urls():
    from services.catalogue import get_catalogue
    make, model = get_catalogue()[["make", "model"]].iloc[0]
    from services.new_car_service import safe_slug
    return ["/", "/recommend", "/car/%s/%s" % (safe_slug(make), safe_slug(model)), "/compare"]


@pytest.mark.parametrize("url", _app_urls())
def test_app_pages_have_one_theme_button_and_the_head_script(client, url):
    r = client.get(url)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count('id="themebtn"') == 1
    assert '<span class="lbl">Theme: </span><span data-theme-label>Auto</span>' in html
    head = html[:html.index("</head>")]
    assert 'localStorage.getItem("carrec-theme")' in head
    assert "script.js" in html


def test_every_dark_block_in_style_css_can_be_switched_by_the_theme_button():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    parts = css.split("prefers-color-scheme: dark")[1:]
    assert len(parts) == 2          # a new dark block must be added here with its guard, and the count raised
    for part in parts:
        assert ':root:not([data-theme="light"])' in part[:120]
    assert css.count(':root[data-theme="dark"]') >= len(parts)


THEME_HARNESS = """
const vm = require('vm'), fs = require('fs');
const store = {}; let fail = process.argv.at(-3) === 'fail';
const attrs = {};
const label = { textContent: 'Auto' };
let click = null;
const btn = { querySelector: () => label, addEventListener: (t, f) => { click = f; } };
const doc = { documentElement: { setAttribute: (k, v) => { attrs[k] = v; }, removeAttribute: (k) => { delete attrs[k]; } },
  getElementById: () => btn, addEventListener() {} };
const ls = { getItem: k => { if (fail) throw new Error('x'); return k in store ? store[k] : null; },
  setItem: (k, v) => { if (fail) throw new Error('x'); store[k] = v; } };
if (process.argv.at(-3) === 'saved') store['carrec-theme'] = 'dark';
const ctx = vm.createContext({ console, document: doc, localStorage: ls, location: { origin: 'http://x', pathname: '/', search: '' } });
vm.runInContext(fs.readFileSync(process.argv.at(-1), 'utf8'), ctx);
vm.runInContext('initTheme()', ctx);
const out = [[label.textContent, attrs['data-theme'] || null]];
for (let i = 0; i < 3; i++) { click(); out.push([label.textContent, attrs['data-theme'] || null]); }
process.stdout.write(JSON.stringify({ out, store }));
"""


def _run_theme(mode):
    import json
    import shutil
    import subprocess
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    args = ["node", "-e", THEME_HARNESS, "x", mode, "x", str(ROOT / "static" / "script.js")]  # the harness reads mode as argv[-3]
    return json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)


def test_init_theme_cycles_auto_light_dark_and_saves():
    r = _run_theme("none")
    assert r["out"] == [["Auto", None], ["Light", "light"], ["Dark", "dark"], ["Auto", None]]
    assert r["store"]["carrec-theme"] == "auto"


def test_init_theme_works_without_storage():
    r = _run_theme("fail")
    assert r["out"][1:3] == [["Light", "light"], ["Dark", "dark"]]


def test_init_theme_restores_a_saved_choice():
    r = _run_theme("saved")
    assert r["out"][0] == ["Dark", "dark"]
