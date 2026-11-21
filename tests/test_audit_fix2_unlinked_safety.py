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


# ---- owner decision: variants with no price are left out of the catalogue
def test_split_unpriced_leaves_out_exactly_the_rows_with_no_price():
    rows = [{"variant_id": "1", "price_ex_showroom": "800000"}, {"variant_id": "2", "price_ex_showroom": ""},
            {"variant_id": "3", "price_ex_showroom": "0.0"}]
    kept, out = X.split_unpriced(rows)
    assert [r["variant_id"] for r in kept] == ["1", "3"] and [r["variant_id"] for r in out] == ["2"]


def test_row_count_check_subtracts_the_unpriced_variants_so_the_tolerance_stays_real():
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE variant(id INTEGER PRIMARY KEY); CREATE VIEW v_variant_canonical_q AS SELECT * FROM variant;"
                       + "".join(f"INSERT INTO variant VALUES ({i});" for i in range(100)))
    rows = [{"variant_id": str(i), "fuel_type": "petrol"} for i in range(80)]
    _, bad = X.sanity_checks(conn, rows, [], no_price=0)      # 80 of 100 is outside 5%
    assert any("row count" in f for f in bad)
    _, ok = X.sanity_checks(conn, rows, [], no_price=20)      # 80 of 100-20 is exact
    assert not any("row count" in f for f in ok)
    _, still_bad = X.sanity_checks(conn, rows, [], no_price=5)   # 80 of 95 is still outside the tolerance
    assert any("row count" in f for f in still_bad)
