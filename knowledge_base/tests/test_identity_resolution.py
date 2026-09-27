import pytest
import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.oem.field_map_oem import normalize_power

@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE model (id INTEGER PRIMARY KEY, manufacturer_id INTEGER, name TEXT)")
    conn.execute("CREATE TABLE manufacturer (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE powertrain (id INTEGER PRIMARY KEY, model_id INTEGER, fuel_type TEXT, engine_cc REAL, power_bhp REAL)")
    conn.execute("CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, generation_id INTEGER, powertrain_id INTEGER, name TEXT, full_name TEXT, transmission TEXT, drivetrain TEXT, is_discontinued INTEGER, price_ex_showroom REAL, base_variant_id INTEGER, edition_classification TEXT)")
    conn.execute("CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE variant_alias (id INTEGER, variant_id INTEGER, source_id INTEGER, alias_name TEXT, needs_review INTEGER, is_verified INTEGER)")
    
    conn.execute("INSERT INTO source VALUES (1, '91wheels')")
    conn.execute("INSERT INTO manufacturer VALUES (1, 'Hyundai')")
    conn.execute("INSERT INTO model VALUES (1, 1, 'Creta')")
    conn.execute("INSERT INTO powertrain VALUES (1, 1, 'Petrol', 1497, 113)")
    conn.execute("INSERT INTO powertrain VALUES (2, 1, 'Diesel', 1493, 114)")
    
    # Base variants
    conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (1, 1, 1, 'E Petrol MT', 'Manual')")
    conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (2, 1, 2, 'E Diesel MT', 'Manual')")
    conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (3, 1, 1, 'EX Petrol MT', 'Manual')")
    
    # Editions
    conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission, base_variant_id) VALUES (4, 1, 1, 'E Dark Edition Petrol MT', 'Manual', 1)")
    conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission, base_variant_id) VALUES (5, 1, 1, 'E Knight Edition Petrol MT', 'Manual', 1)")
    
    return conn

def test_unique_trim_engine_trans(test_db):
    # 1. Unique via trim + engine + transmission
    # The variant name is just 'E', but fuel is 'Diesel'. Should uniquely resolve to E Diesel MT.
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'E', 'e', 'Diesel', 'Manual', 1493, None)
    assert vid == 2
    assert status == 'resolved'

def test_cross_powertrain_rejection(test_db):
    # 2. Prevent cross powertrain resolve
    # 'E' with Diesel must NOT resolve to E Petrol MT
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'E', 'e', 'Diesel', 'Manual', 1493, None)
    assert vid == 2  # Resolved to Diesel
    
def test_structured_vs_concatenated(test_db):
    # 3. Concatenated string caused false fuzzy match. Structured resolution fixes it.
    # If we pass edition="Dark Edition", it should only match the Dark Edition (id=4).
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'E', 'e', 'Petrol', 'Manual', 1497, None, edition="Dark Edition")
    assert vid == 4
    assert status == 'resolved'
    
    # If we just pass 'E' (no edition), it shouldn't fuzzy match Dark Edition because of the margin/edition checks.
    # It should resolve to the base E Petrol MT (id=1)
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'E', 'e', 'Petrol', 'Manual', 1497, None)
    assert vid == 1
    assert status == 'resolved'

def test_ambiguous_fails_closed(test_db):
    # 4. Ambiguous structured identity fails closed.
    # E Petrol but we have multiple editions. Wait, earlier test passed for E Petrol MT.
    # Let's add a collision: two EX Petrol MT variants (maybe diff price)
    test_db.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (99, 1, 1, 'EX(O) Petrol MT', 'Manual')")
    
    # If we pass just EX, it might collide with EX(O) if margin < 0.05
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'EX', 'ex', 'Petrol', 'Manual', 1497, None)
    # The similarities: EX vs EX Petrol MT = 1.0 (overlap=1), EX vs EX(O) Petrol MT = 0.8
    # Margin is 0.2, so it might resolve. Let's make an exact tie.
    test_db.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (100, 1, 1, 'EX Special Petrol MT', 'Manual')")
    
    # If we do NOT have edition stripping for "Special", wait, Special is an edition.
    # Let's insert two exactly identical trim names but different IDs.
    test_db.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (101, 1, 1, 'SX Petrol MT', 'Manual')")
    test_db.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (102, 1, 1, 'SX Petrol MT', 'Manual')")
    
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'SX', 'sx', 'Petrol', 'Manual', 1497, None)
    assert vid is None
    assert status == 'unresolved'

def test_explicit_edition(test_db):
    # 5. Explicit edition information survives into resolution
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'E', 'e', 'Petrol', 'Manual', 1497, None, edition="Knight Edition")
    assert vid == 5
    assert status == 'resolved'
    
    # Unknown edition triggers fallback
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'E', 'e', 'Petrol', 'Manual', 1497, None, edition="Summer Edition")
    assert status == 'edition_candidate'
    assert cand == 1  # Attaches to base E Petrol MT

def test_legacy_behavior(test_db):
    # 6. Legacy resolver behavior (just passing long variant_name)
    vid, status, cand = resolve_variant(test_db, 'hyundai', 'creta', 'E Dark Edition Petrol MT', 'e-dark-edition', 'Petrol', 'Manual', 1497, None)
    assert vid == 4
    assert status == 'resolved'

def test_normalize_power():
    # 7. normalize_power() expected behavior
    assert normalize_power("113 bhp") == 113.0
    # ~1.341 hp/kW
    kw_power = normalize_power("84.4 kw")
    assert abs(kw_power - 113.18) < 0.1
    
    # Material disagreement
    assert normalize_power("113 bhp 100 kw") is None
    
    # Minor disagreement (rounding tolerance)
    # 60 kW = 80.46 bhp
    assert normalize_power("80 bhp 60 kw") is not None
