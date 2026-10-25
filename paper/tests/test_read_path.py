"""No code under paper/ reads the raw variant table; SQL touches only the quarantine-aware view and its joins."""
import ast
import os
import re

PAPER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_TABLES = {"v_variant_canonical_q", "model", "manufacturer", "powertrain"}
TABLE_REF = re.compile(r"\b(?:FROM|JOIN)\s+[\"'`\[]?(\w+)", re.IGNORECASE)
RAW_VARIANT = re.compile(r"\b(?:FROM|JOIN)\s+[\"'`\[]?" + "variant" + r"\b", re.IGNORECASE)


def py_files():
    for root, _, files in os.walk(PAPER_DIR):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


def string_constants(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_no_raw_variant_table_reads():
    for path in py_files():
        for s in string_constants(path):
            assert not RAW_VARIANT.search(s), f"{path}: raw variant table referenced in {s!r}"


def test_sql_uses_only_allowed_tables():
    found = False
    for path in py_files():
        for s in string_constants(path):
            if re.search(r"\bSELECT\b", s) and TABLE_REF.search(s):
                found = True
                tables = set(TABLE_REF.findall(s))
                assert tables <= ALLOWED_TABLES, f"{path}: {tables - ALLOWED_TABLES}"
    assert found, "expected the oracle's catalogue SQL to be scanned"


def test_only_the_oracle_opens_sqlite_and_only_immutably():
    for path in py_files():
        with open(path, encoding="utf-8") as f:
            src = f.read()
        if "sqlite3.connect(" in src and not path.endswith(os.path.join("tests", "test_read_path.py")):
            assert path.endswith(os.path.join("oracle", "feasibility.py")), path
            assert "mode=ro&immutable=1" in src and "uri=True" in src
