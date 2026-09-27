import sqlite3
import pytest
from knowledge_base.ingestion.common.updater import update_canonical
from knowledge_base.ingestion.common.resolver import resolve_variant

@pytest.fixture
def setup_db(tmp_path):
    db_path = tmp_path / "test_editions.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Minimal schema
    c.execute("CREATE TABLE manufacturer (id INTEGER PRIMARY KEY, name TEXT)")
    c.execute("CREATE TABLE model (id INTEGER PRIMARY KEY, manufacturer_id INTEGER, name TEXT)")
    c.execute("CREATE TABLE powertrain (id INTEGER PRIMARY KEY, model_id INTEGER, fuel_type TEXT, engine_cc REAL, power_bhp REAL)")
    c.execute("""
        CREATE TABLE variant (
            id INTEGER PRIMARY KEY, model_id INTEGER, generation_id INTEGER, powertrain_id INTEGER, drivetrain TEXT, 
            name TEXT, full_name TEXT, transmission TEXT, sunroof INTEGER, 
            boot_space_litres REAL, is_discontinued INTEGER DEFAULT 0,
            base_variant_id INTEGER, edition_classification TEXT,
            price_ex_showroom REAL
        )
    """)
    c.execute("CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT)")
    c.execute("CREATE TABLE source_observation (id INTEGER PRIMARY KEY, source_id INTEGER, raw_name TEXT, raw_payload TEXT, source_url TEXT, extraction_method TEXT, resolved_variant_id INTEGER, resolution_status TEXT)")
    c.execute("CREATE TABLE field_provenance (id INTEGER PRIMARY KEY, variant_id INTEGER, field_name TEXT, accepted_value TEXT, source_observation_id INTEGER, decision TEXT, decision_reason TEXT)")
    c.execute("CREATE TABLE variant_alias (variant_id INTEGER, source_id INTEGER, alias_name TEXT, needs_review INTEGER, is_verified INTEGER)")
    
    # Create test data
    c.execute("INSERT INTO manufacturer (id, name) VALUES (1, 'Tata')")
    c.execute("INSERT INTO model (id, manufacturer_id, name) VALUES (1, 1, 'Harrier')")
    c.execute("INSERT INTO powertrain (id, model_id, fuel_type, engine_cc) VALUES (1, 1, 'Diesel', 1956)")
    c.execute("INSERT INTO variant (id, model_id, powertrain_id, name, full_name, transmission, sunroof, boot_space_litres) VALUES (10, 1, 1, 'Pure X MT', 'Tata Harrier Pure X MT', 'Manual', 0, 425)")
    c.execute("INSERT INTO variant (id, model_id, powertrain_id, name, full_name, transmission, sunroof, boot_space_litres) VALUES (11, 1, 1, 'Pure X AT', 'Tata Harrier Pure X AT', 'Torque Converter', 0, 425)")
    
    conn.commit()
    return conn

def test_edition_resolution_and_creation(setup_db):
    conn = setup_db
    c = conn.cursor()
    
    # Attempt to resolve an edition
    t_id, status, base_id = resolve_variant(conn, 'Tata', 'Harrier', 'Pure X Dark Edition MT', 'pure-x-dark-edition', 'Diesel', 'Manual', 1956, None)
    assert status == 'edition_candidate'
    assert base_id == 10
    
    # Update canonical should CREATE the edition
    obs_id, updates = update_canonical(conn, None, 1, 'http', 'Pure X Dark Edition MT', {}, 'edition_candidate', {'sunroof': 1}, base_variant_id=base_id)
    
    # Verify edition creation
    c.execute("SELECT * FROM variant WHERE base_variant_id = 10")
    ed = c.fetchone()
    assert ed is not None
    assert ed['name'] == 'Pure X Dark Edition MT'
    assert ed['edition_classification'] == 'FEATURE_OR_SPEC_DIFFERENCE'
    assert ed['sunroof'] == 1
    assert ed['transmission'] == 'Manual'
    
    # Verify base variant is untouched
    c.execute("SELECT sunroof FROM variant WHERE id = 10")
    bv = c.fetchone()
    assert bv['sunroof'] == 0
    
    # Verify view
    c.execute("""
        CREATE VIEW v_effective_variant AS
        SELECT v.id, v.name, v.base_variant_id, COALESCE(v.sunroof, bv.sunroof) as sunroof, COALESCE(v.boot_space_litres, bv.boot_space_litres) as boot_space_litres
        FROM variant v LEFT JOIN variant bv ON v.base_variant_id = bv.id
    """)
    c.execute("SELECT sunroof, boot_space_litres FROM v_effective_variant WHERE id = ?", (ed['id'],))
    eff = c.fetchone()
    assert eff['sunroof'] == 1 # Overridden
    assert eff['boot_space_litres'] == 425 # Inherited
    
    # Test different transmission fails to map as edition
    t_id2, status2, base_id2 = resolve_variant(conn, 'Tata', 'Harrier', 'Pure X Dark Edition AT', 'pure-x-dark-at', 'Diesel', 'Torque Converter', 1956, None)
    # This should map to base_id 11 (Pure X AT), not 10!
    print('t_id2', t_id2, 'status2', status2, 'base_id2', base_id2)
    assert base_id2 == 11
    
