"""Nothing may open the KB by a cwd-relative path: SQLite silently creates an empty file when the path is wrong."""
import ast, os, sqlite3, subprocess
import pytest
from knowledge_base.kb_db import KB_PATH, open_kb

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Creates the DB on purpose, from an absolute path.
ALLOWED = {"knowledge_base/db/migrate_v6.py"}


def tracked():
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p not in ALLOWED]


def test_no_relative_kb_path_is_opened_or_assigned():
    bad = []
    for rel in tracked():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path): continue
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            lit = None
            if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) == "connect" and node.args:
                lit = node.args[0]
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                lit = node.value
            if isinstance(lit, ast.Constant) and isinstance(lit.value, str) and lit.value.endswith("carrec_kb.db"):
                bad.append(f"{rel}:{node.lineno}")
    assert bad == []


def test_open_kb_refuses_a_missing_file_and_creates_nothing(tmp_path):
    missing = tmp_path / "nope.db"
    with pytest.raises(FileNotFoundError):
        open_kb(missing)
    assert not missing.exists()


def test_open_kb_handles_spaces_and_modes(tmp_path):
    d = tmp_path / "with space"; d.mkdir(); p = d / "k.db"
    c = sqlite3.connect(p); c.execute("create table t(x)"); c.commit(); c.close()
    c = open_kb(p); c.execute("insert into t values (1)"); c.commit(); c.close()
    r = open_kb(p, readonly=True)
    assert r.execute("select count(*) from t").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError):
        r.execute("insert into t values (2)")


def test_kb_path_is_absolute():
    assert os.path.isabs(KB_PATH) and KB_PATH.endswith(os.path.join("knowledge_base", "carrec_kb.db"))
