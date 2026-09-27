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
    db_path = "scratch/test_blockers.sqlite"
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

def test_field_level_authority():
    conn, v_id, _, s91, scw, soem, stbhp, _, _ = setup_fresh_db()
    cur = conn.cursor()
    
    update_canonical(conn, v_id, s91, 'u', 'T', {}, 'resolved', {'boot_space_litres': 300.0})
    update_canonical(conn, v_id, soem, 'u', 'T2', {}, 'resolved', {'boot_space_litres': 310.0})
    cur.execute("SELECT boot_space_litres FROM variant WHERE id = ?", (v_id,))
    assert cur.fetchone()[0] == 310.0, "OEM failed to override lower-tier objective field"
    
    update_canonical(conn, v_id, soem, 'u', 'T', {}, 'resolved', {'mileage_arai_kmpl': 20.0})
    update_canonical(conn, v_id, stbhp, 'u', 'T', {}, 'resolved', {'mileage_arai_kmpl': 25.0})
    cur.execute("SELECT mileage_arai_kmpl FROM variant WHERE id = ?", (v_id,))
    assert cur.fetchone()[0] == 20.0, "Source with no field authority incorrectly overwrote."
    
    cur.execute("SELECT decision FROM field_provenance WHERE field_name = 'mileage_arai_kmpl' AND decision = 'rejected'")
    assert cur.fetchone()[0] == 'rejected', "Lower-tier evidence not preserved as rejected."
    
    conn.close()

def test_generation_safety():
    conn, v_gen2, v_gen1, s91, scw, soem, stbhp, gen1, gen2 = setup_fresh_db()
    
    try:
        process_oem_payload(conn, [{'variant_name': 'Base', 'transmission': 'Manual'}], 'make', 'blockermodel', soem, generation_id=None)
        assert False, "Failed to raise ValueError on missing generation_id"
    except ValueError:
        pass
        
    res = process_oem_payload(conn, [{'variant_name': 'Base', 'transmission': 'Manual'}], 'make', 'blockermodel', soem, generation_id=gen2)
    assert res['resolved'] == 1, "Correct generation failed to resolve"
    
    res = process_oem_payload(conn, [{'variant_name': 'Base', 'transmission': 'Manual'}], 'make', 'blockermodel', soem, generation_id=gen1)
    assert res['resolved'] == 1, "Failed to resolve to historical generation"
    
    conn.close()

def test_unit_normalization():
    # 172 Nm remains 172 Nm
    assert map_oem_fields({'max torque': '172 Nm'})['torque_nm'] == 172.0
    # 1197 cc remains 1197 cc
    assert map_oem_fields({'displacement': '1197 cc'})['engine_cc'] == 1197.0
    # 3995 mm remains 3995 mm
    assert map_oem_fields({'length': '3995 mm'})['length_mm'] == 3995.0
    
    # Mathematical derivation without arbitrary rounding
    assert math.isclose(map_oem_fields({'max power': '100 PS'})['power_bhp'], 100.0 * PS_TO_BHP)
    assert math.isclose(map_oem_fields({'max power': '100 kW'})['power_bhp'], 100.0 * KW_TO_BHP)
    
    # Ambiguous unitless rejected
    assert 'power_bhp' not in map_oem_fields({'max power': '100'})
    
    # Ambiguous "hp" rejected
    assert 'power_bhp' not in map_oem_fields({'max power': '100 hp'})
    
    # No conversion when source unit matches canonical unit
    assert map_oem_fields({'max power': '100 bhp'})['power_bhp'] == 100.0
    
    # Robustness
    assert 'power_bhp' not in map_oem_fields({'max power': '100.5.2 bhp'}) # malformed float
    assert map_oem_fields({'displacement': '1,197 cc'})['engine_cc'] == 1197.0
    assert math.isclose(map_oem_fields({'max power': '82.4 PS'})['power_bhp'], 82.4 * PS_TO_BHP)
    
    # Booleans
    assert map_oem_fields({'abs': 'Standard'})['abs'] == 1
    assert map_oem_fields({'abs': 'No'})['abs'] == 0
    assert 'abs' not in map_oem_fields({'abs': 'Optional'})
    assert 'abs' not in map_oem_fields({'abs': 'Available'})
    assert 'abs' not in map_oem_fields({'abs': '-'})

def test_raw_payload_preservation():
    conn, v_id, _, s91, scw, soem, stbhp, _, _ = setup_fresh_db()
    cur = conn.cursor()
    
    raw = {'max power': '100 PS'}
    norm = map_oem_fields(raw)
    
    update_canonical(conn, v_id, soem, 'u', 'T', raw, 'resolved', norm)
    
    cur.execute("SELECT raw_payload FROM source_observation ORDER BY id DESC LIMIT 1")
    payload_str = cur.fetchone()[0]
    payload = json.loads(payload_str)
    
    # raw source string "100 PS" remains preserved in raw_payload
    assert payload['max power'] == '100 PS'
    
    conn.close()

if __name__ == '__main__':
    test_field_level_authority()
    test_generation_safety()
    test_unit_normalization()
    test_raw_payload_preservation()
    print("All precise numeric tests passed.")
