import pytest
import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant, normalize_engine_string

@pytest.fixture
def mock_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("CREATE TABLE manufacturer (id INTEGER PRIMARY KEY, name TEXT, transmission TEXT)")
    cur.execute("CREATE TABLE model (id INTEGER PRIMARY KEY, manufacturer_id INTEGER, name TEXT, transmission TEXT)")
    cur.execute("CREATE TABLE powertrain (id INTEGER PRIMARY KEY, fuel_type TEXT, transmission TEXT, engine_cc INTEGER, power_bhp INTEGER)")
    cur.execute("CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, powertrain_id INTEGER, name TEXT, transmission TEXT, price_ex_showroom INTEGER, base_variant_id INTEGER, generation_id INTEGER, is_discontinued INTEGER)")
    cur.execute("CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT, transmission TEXT)")
    cur.execute("CREATE TABLE variant_alias (id INTEGER PRIMARY KEY, variant_id INTEGER, source_id INTEGER, alias_name TEXT, transmission TEXT, needs_review INTEGER, is_verified INTEGER)")
    
    cur.execute("INSERT INTO manufacturer (id, name) VALUES (1, 'Skoda')")
    cur.execute("INSERT INTO manufacturer (id, name) VALUES (2, 'Maruti Suzuki')")
    
    cur.execute("INSERT INTO model (id, manufacturer_id, name) VALUES (1, 1, 'Kylaq')")
    cur.execute("INSERT INTO model (id, manufacturer_id, name) VALUES (2, 2, 'Fronx')")
    cur.execute("INSERT INTO model (id, manufacturer_id, name) VALUES (3, 2, 'Swift')")
    
    # Powertrains
    cur.execute("INSERT INTO powertrain (id, fuel_type, transmission) VALUES (1, 'Petrol', 'Manual')")
    cur.execute("INSERT INTO powertrain (id, fuel_type, transmission) VALUES (2, 'Petrol', 'Torque Converter')")
    cur.execute("INSERT INTO powertrain (id, fuel_type, transmission) VALUES (3, 'CNG', 'Manual')")
    cur.execute("INSERT INTO powertrain (id, fuel_type, transmission) VALUES (4, 'Petrol CNG', 'Manual')")  # Bi-fuel
    
    # Variants
    # Kylaq
    cur.execute("INSERT INTO variant (id, model_id, powertrain_id, name) VALUES (101, 1, 1, 'Classic Petrol Turbo Manual')")
    cur.execute("INSERT INTO variant (id, model_id, powertrain_id, name) VALUES (102, 1, 1, 'Classic Plus Petrol Turbo Manual')")
    
    # Fronx
    cur.execute("INSERT INTO variant (id, model_id, powertrain_id, name) VALUES (201, 2, 1, 'Sigma 1.2 Petrol MT')")
    cur.execute("INSERT INTO variant (id, model_id, powertrain_id, name) VALUES (202, 2, 3, 'Sigma CNG MT')")
    
    # Swift
    cur.execute("INSERT INTO variant (id, model_id, powertrain_id, name) VALUES (301, 3, 1, 'VXi Petrol Manual')")
    cur.execute("INSERT INTO variant (id, model_id, powertrain_id, name) VALUES (302, 3, 1, 'VXi (O) Petrol Manual')")
    
    conn.commit()
    return conn

def test_engine_normalization():
    assert normalize_engine_string("1.2 l Kappa petrol") == "1.2 kappa"
    assert normalize_engine_string("1.0L TSI") == "1.0 tsi"
    assert normalize_engine_string("Petrol (Neodrive)") == "(neodrive)"
    assert normalize_engine_string("1.2 l Bi-fuel Kappa petrol with Hy-CNG") == "1.2 kappa"

def test_semantic_resolution_classic(mock_db):
    # Tests that 'Classic' correctly penalizes 'Plus' and resolves to base Classic
    v_id, status, _ = resolve_variant(mock_db, 'skoda', 'kylaq', 'Classic', 'classic', 'Petrol', 'Manual', None, None)
    assert status == 'resolved'
    assert v_id == 101

def test_semantic_resolution_cng_bug(mock_db):
    # Tests that CNG doesn't incorrectly match pure Petrol trims
    v_id, status, _ = resolve_variant(mock_db, 'maruti-suzuki', 'fronx', 'Sigma', 'sigma', 'CNG', 'Manual', None, None, engine_name='1.2L')
    assert status == 'resolved'
    assert v_id == 202

def test_semantic_resolution_margin_tie_breaker(mock_db):
    # Tests that VXi resolves to VXi and not VXi (O)
    v_id, status, _ = resolve_variant(mock_db, 'maruti-suzuki', 'swift', 'VXi', 'vxi', 'Petrol', 'Manual', None, None)
    assert status == 'resolved'
    assert v_id == 301
    
    # Test that VXi (O) resolves to VXi (O)
    v_id, status, _ = resolve_variant(mock_db, 'maruti-suzuki', 'swift', 'VXi (O)', 'vxi-o', 'Petrol', 'Manual', None, None)
    assert status == 'resolved'
    assert v_id == 302

def test_fail_closed_on_different_fuel(mock_db):
    # Sigma Petrol payload should NOT resolve to Sigma CNG, but should resolve to Sigma Petrol
    v_id, status, _ = resolve_variant(mock_db, 'maruti-suzuki', 'fronx', 'Sigma', 'sigma', 'Petrol', 'Manual', None, None, engine_name='1.2')
    assert status == 'resolved'
    assert v_id == 201

