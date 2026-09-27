import sqlite3
import os
import shutil
import math
import json
from knowledge_base.ingestion.common.updater import update_canonical
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields, PS_TO_BHP, KW_TO_BHP
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload

def setup_fresh_db():
    db_path = "scratch/test_final_audit.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
    shutil.copy("knowledge_base/carrec_kb.db", db_path)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("INSERT INTO source (name, source_type, authority_tier) VALUES ('team_bhp', 'community', 1)")
    
    cur.execute("INSERT INTO manufacturer (id, name) VALUES (999, 'Make')")
    cur.execute("INSERT INTO model (id, manufacturer_id, name) VALUES (999, 999, 'BlockerModel')")
    model_id = 999
    cur.execute("INSERT INTO generation (model_id, name) VALUES (?, 'Gen1')", (model_id,))
    gen1 = cur.lastrowid
    cur.execute("INSERT INTO generation (model_id, name) VALUES (?, 'Gen2')", (model_id,))
    gen2 = cur.lastrowid
    
    cur.execute("INSERT INTO powertrain (id, model_id, fuel_type, engine_cc) VALUES (999, 999, 'Petrol', 1200)")
    pt_id = 999
    
    cur.execute("INSERT INTO variant (model_id, generation_id, powertrain_id, name, transmission, is_discontinued, price_ex_showroom) VALUES (?, ?, ?, 'Base', 'MT', 1, 1000)", (model_id, gen1, pt_id))
    var_gen1 = cur.lastrowid
    cur.execute("INSERT INTO variant (model_id, generation_id, powertrain_id, name, transmission, is_discontinued, price_ex_showroom) VALUES (?, ?, ?, 'Base', 'MT', 0, 1000)", (model_id, gen2, pt_id))
    var_gen2 = cur.lastrowid
    
    cur.execute("SELECT id FROM source WHERE name='91wheels'")
    s91 = cur.fetchone()[0]
    cur.execute("SELECT id FROM source WHERE name='carwale'")
    scw = cur.fetchone()[0]
    cur.execute("SELECT id FROM source WHERE name='oem'")
    soem = cur.fetchone()[0]
    cur.execute("SELECT id FROM source WHERE name='team_bhp'")
    stbhp = cur.fetchone()[0]
    
    return conn, var_gen2, var_gen1, s91, scw, soem, stbhp, gen1, gen2


def test_boolean_semantics():
    assert map_oem_fields({'abs': 'Yes'})['abs'] == 1
    assert map_oem_fields({'abs': 'Standard'})['abs'] == 1
    assert map_oem_fields({'abs': '✓'})['abs'] == 1
    assert map_oem_fields({'abs': 'No'})['abs'] == 0
    assert 'abs' not in map_oem_fields({'abs': 'Available'})
    assert 'abs' not in map_oem_fields({'abs': 'Optional'})
    assert 'abs' not in map_oem_fields({'abs': '-'})
    assert 'abs' not in map_oem_fields({'abs': 'Unknown'})
    assert 'abs' not in map_oem_fields({'abs': ''})
    assert 'abs' not in map_oem_fields({'abs': 'N/A'})

def test_numeric_normalization():
    assert map_oem_fields({'max torque': '172 Nm'})['torque_nm'] == 172.0
    assert map_oem_fields({'displacement': '1197 cc'})['engine_cc'] == 1197.0
    assert map_oem_fields({'length': '3995 mm'})['length_mm'] == 3995.0
    assert math.isclose(map_oem_fields({'max power': '100 PS'})['power_bhp'], 100.0 * PS_TO_BHP)
    assert math.isclose(map_oem_fields({'max power': '82.4 PS'})['power_bhp'], 82.4 * PS_TO_BHP)
    assert math.isclose(map_oem_fields({'max power': '100 kW'})['power_bhp'], 100.0 * KW_TO_BHP)
    assert math.isclose(map_oem_fields({'max power': '735.5 kW'})['power_bhp'], 735.5 * KW_TO_BHP)
    
    assert map_oem_fields({'max power': '100 bhp'})['power_bhp'] == 100.0
    assert 'power_bhp' not in map_oem_fields({'max power': '100 hp'}) # Ambiguous
    assert 'power_bhp' not in map_oem_fields({'max power': '100'}) # Unitless
    assert 'power_bhp' not in map_oem_fields({'max power': '100.5.2 bhp'}) # Malformed
    
    assert map_oem_fields({'displacement': '1,197 cc'})['engine_cc'] == 1197.0
    assert map_oem_fields({'displacement': '1.2 L'})['engine_cc'] == 1200.0
    assert map_oem_fields({'length': '399.5 cm'})['length_mm'] == 3995.0
    assert map_oem_fields({'length': '400 cm'})['length_mm'] == 4000.0

def test_generation_safety():
    conn, v_gen2, v_gen1, s91, scw, soem, stbhp, gen1, gen2 = setup_fresh_db()
    
    # Missing generation
    try:
        process_oem_payload(conn, [{'variant_name': 'Base', 'transmission': 'Manual'}], 'make', 'blockermodel', soem, generation_id=None)
        assert False, "Failed to raise ValueError"
    except ValueError:
        pass
        
    # Current generation
    res = process_oem_payload(conn, [{'variant_name': 'Base', 'transmission': 'Manual'}], 'make', 'blockermodel', soem, generation_id=gen2)
    assert res['resolved'] == 1
    
    # Historical generation
    res = process_oem_payload(conn, [{'variant_name': 'Base', 'transmission': 'Manual'}], 'make', 'blockermodel', soem, generation_id=gen1)
    assert res['resolved'] == 1
    
    conn.close()

def test_raw_evidence_separation():
    conn, v_id, _, s91, scw, soem, stbhp, _, _ = setup_fresh_db()
    cur = conn.cursor()
    
    # Accepted observation
    raw_acc = {'max power': '100 PS'}
    obs_id_acc, _ = update_canonical(conn, v_id, soem, 'url1', 'T', raw_acc, 'resolved', map_oem_fields(raw_acc))
    cur.execute("SELECT raw_payload FROM source_observation WHERE id = ?", (obs_id_acc,))
    assert json.loads(cur.fetchone()[0])['max power'] == '100 PS'
    
    # Rejected / ambiguous observation (lower tier)
    raw_rej = {'max power': '100.5.2 bhp'} # Ambiguous float
    obs_id_rej, _ = update_canonical(conn, v_id, scw, 'url2', 'T', raw_rej, 'resolved', map_oem_fields(raw_rej))
    cur.execute("SELECT raw_payload FROM source_observation WHERE id = ?", (obs_id_rej,))
    assert json.loads(cur.fetchone()[0])['max power'] == '100.5.2 bhp' # Preserved despite not mapping to canonical field
    
    # Lower authority rejected but preserved
    raw_low = {'boot space': '320 litres'}
    obs_id_low, _ = update_canonical(conn, v_id, scw, 'url3', 'T', raw_low, 'resolved', map_oem_fields(raw_low))
    cur.execute("SELECT raw_payload FROM source_observation WHERE id = ?", (obs_id_low,))
    assert json.loads(cur.fetchone()[0])['boot space'] == '320 litres'
    
    conn.close()

if __name__ == '__main__':
    test_boolean_semantics()
    test_numeric_normalization()
    test_generation_safety()
    test_raw_evidence_separation()
    print("Final safety tests passed.")
