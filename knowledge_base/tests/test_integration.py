import pytest
import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.common.updater import update_canonical

def test_resolve_and_update(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE model (id INTEGER PRIMARY KEY, manufacturer_id INTEGER, name TEXT)")
    conn.execute("CREATE TABLE manufacturer (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE powertrain (id INTEGER PRIMARY KEY, model_id INTEGER, fuel_type TEXT, engine_cc REAL, power_bhp REAL)")
    conn.execute("CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, generation_id INTEGER, powertrain_id INTEGER, name TEXT, full_name TEXT, transmission TEXT, drivetrain TEXT, is_discontinued INTEGER, price_ex_showroom REAL, boot_space_litres REAL, base_variant_id INTEGER, edition_classification TEXT)")
    conn.execute("CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE variant_alias (id INTEGER, variant_id INTEGER, source_id INTEGER, alias_name TEXT, needs_review INTEGER, is_verified INTEGER)")
    conn.execute("CREATE TABLE source_observation (id INTEGER PRIMARY KEY, source_id INTEGER, raw_name TEXT, raw_payload TEXT, source_url TEXT, extraction_method TEXT, resolved_variant_id INTEGER, resolution_status TEXT, observed_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE field_provenance (id INTEGER PRIMARY KEY, variant_id INTEGER, field_name TEXT, accepted_value TEXT, source_observation_id INTEGER, decision TEXT, decision_reason TEXT)")
    
    conn.execute("INSERT INTO source VALUES (1, '91wheels')")
    conn.execute("INSERT INTO manufacturer VALUES (1, 'Hyundai')")
    conn.execute("INSERT INTO model VALUES (1, 1, 'Creta')")
    conn.execute("INSERT INTO powertrain VALUES (1, 1, 'Petrol', 1497, 113)")
    conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission, price_ex_showroom, boot_space_litres) VALUES (1, 1, 1, 'E Petrol MT', 'Manual', 1090000, NULL)")
    
    vid, status, base_id = resolve_variant(conn, 'hyundai', 'creta', 'E', 'e-petrol', 'Petrol', 'Manual', 1497, 1090000)
    assert vid == 1
    assert status == 'resolved'
    
    # Contradiction (price > 3L diff) filters it out since there's no alias
    vid, status, base_id = resolve_variant(conn, 'hyundai', 'creta', 'E', 'e-petrol', 'Petrol', 'Manual', 1497, 1500000)
    assert vid is None
    assert status == 'unresolved'
    
    # Test update canonical
    norm = {'boot_space_litres': 433.0}
    obs_id, updates = update_canonical(conn, 1, 1, 'http://test', 'E', {'raw':'x'}, 'resolved', norm)
    
    assert updates == 1
    cur = conn.cursor()
    row = cur.execute("SELECT boot_space_litres FROM variant WHERE id=1").fetchone()
    assert row['boot_space_litres'] == 433.0
    
    prov = cur.execute("SELECT * FROM field_provenance WHERE variant_id=1").fetchone()
    assert prov['field_name'] == 'boot_space_litres'
    assert prov['decision'] == 'accepted'
