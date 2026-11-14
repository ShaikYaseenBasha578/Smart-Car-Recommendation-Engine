"""The dashboard generator runs on a tiny synthetic KB with no runs and no history, and is deterministic."""
import os
import re
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import make_kb  # noqa: E402
from kbpipe import dashboard  # noqa: E402


def test_dashboard_on_synthetic_fixture(tmp_path):
    db = make_kb(str(tmp_path / "kb.db"))
    runs = tmp_path / "runs"
    runs.mkdir()
    out = tmp_path / "out" / "index.html"
    argv = ["--db", db, "--runs", str(runs), "--history", str(tmp_path / "nohist"), "--date", "2026-01-02", "--out", str(out)]
    assert dashboard.main(argv) == 0
    html = out.read_text()
    assert "<title>CarRec Knowledge Base</title>" in html
    d = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert d["glance"]["variants"] == 2 and d["glance"]["models"] == 1 and d["glance"]["makes"] == 1
    assert d["glance"]["values"] > 0 and d["trust"] is None
    assert "http://" not in html and "https://" not in html
    first = html
    assert dashboard.main(argv) == 0
    assert out.read_text() == first
