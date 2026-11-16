"""Audit 2026-11-16, fix 2: crash tests that name a KB model but are not linked to it are reported by the exporter."""
import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_catalogue_from_kb", ROOT / "scripts" / "export_catalogue_from_kb.py")
X = importlib.util.module_from_spec(spec)
sys.modules["export_catalogue_from_kb"] = X
spec.loader.exec_module(X)


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE manufacturer(id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE model(id INTEGER PRIMARY KEY, manufacturer_id INT, name TEXT);
        CREATE TABLE safety_test(id INTEGER PRIMARY KEY, tested_vehicle_name TEXT);
        CREATE TABLE safety_test_applicability(id INTEGER PRIMARY KEY, safety_test_id INT, model_id INT);
        CREATE VIEW v_safety_applicability_q AS SELECT * FROM safety_test_applicability;
        INSERT INTO manufacturer VALUES (1,'Tata'),(2,'Mahindra');
        INSERT INTO model VALUES (1,1,'Curvv'),(2,1,'Nexon'),(3,2,'XEV 9e'),(4,1,'Tiago');
        INSERT INTO safety_test VALUES (1,'TATA CURVV'),(2,'TATA – NEXON'),(3,'MAHINDRA – XEV 9e'),(4,'MAHINDRA – BE 6');
        INSERT INTO safety_test_applicability VALUES (1,2,2);
    """)
    return conn


def test_unlinked_test_naming_a_kb_model_is_reported_and_linked_or_unknown_ones_are_not():
    got = X.unlinked_safety_tests(make_db())
    assert [(i, hits) for i, _, hits in got] == [(1, ["Curvv"]), (3, ["XEV 9e"])]   # Nexon is linked; BE 6 is not a KB model
