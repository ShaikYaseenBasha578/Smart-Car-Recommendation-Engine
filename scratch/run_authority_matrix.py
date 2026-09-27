import sqlite3
import json
import shutil
import os
from knowledge_base.ingestion.common.updater import update_canonical

def print_result(label, conn, obs_id, var_id, field):
    cur = conn.cursor()
    cur.execute(f"SELECT {field} FROM variant WHERE id = ?", (var_id,))
    v = cur.fetchone()[0]
    cur.execute("SELECT decision, decision_reason FROM field_provenance WHERE source_observation_id = ? AND field_name = ?", (obs_id, field))
    prov = cur.fetchone()
    if prov:
        print(f"[{label}] value: {v} | decision: {prov['decision']} | reason: {prov['decision_reason']}")
    else:
        print(f"[{label}] value: {v} | NO PROVENANCE FOUND")

def setup_fresh_db(old_conn=None):
    if old_conn:
        old_conn.close()
    
    db_path = "scratch/test_db.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
    shutil.copy("knowledge_base/carrec_kb.db", db_path)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("INSERT INTO model (manufacturer_id, name) VALUES (1, 'TestModel')")
    model_id = cur.lastrowid
    cur.execute("INSERT INTO variant (model_id, name, transmission) VALUES (?, 'TestVar', 'MT')", (model_id,))
    var_id = cur.lastrowid
    return conn, var_id

def run_tests():
    conn, var_id = setup_fresh_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM source WHERE name='91wheels'")
    s91 = cur.fetchone()[0]
    cur.execute("SELECT id FROM source WHERE name='carwale'")
    scw = cur.fetchone()[0]
    cur.execute("SELECT id FROM source WHERE name='oem'")
    soem = cur.fetchone()[0]
    cur.execute("SELECT id FROM source WHERE name='global_ncap'")
    sgncap = cur.fetchone()[0]

    # A. NULL canonical + 91Wheels
    obs_a, _ = update_canonical(conn, var_id, s91, 'u', 'Test', {}, 'resolved', {'boot_space_litres': 300.0})
    print_result('A', conn, obs_a, var_id, 'boot_space_litres')
    
    # B. NULL canonical + OEM
    obs_b, _ = update_canonical(conn, var_id, soem, 'u', 'Test', {}, 'resolved', {'length_mm': 4000.0})
    print_result('B', conn, obs_b, var_id, 'length_mm')
    
    # C. 91Wheels value + identical OEM value
    obs_c, _ = update_canonical(conn, var_id, soem, 'u', 'Test', {}, 'resolved', {'boot_space_litres': 300.0})
    print_result('C', conn, obs_c, var_id, 'boot_space_litres')
    
    # D. 91Wheels value + conflicting OEM value
    conn, var_id = setup_fresh_db(conn)
    obs_d1, _ = update_canonical(conn, var_id, s91, 'u', 'Test', {}, 'resolved', {'width_mm': 1800.0})
    obs_d2, _ = update_canonical(conn, var_id, soem, 'u', 'Test2', {}, 'resolved', {'width_mm': 1810.0})
    print_result('D', conn, obs_d2, var_id, 'width_mm')
    
    # E. CarWale value + conflicting OEM value
    conn, var_id = setup_fresh_db(conn)
    obs_e1, _ = update_canonical(conn, var_id, scw, 'u', 'Test', {}, 'resolved', {'width_mm': 1800.0})
    obs_e2, _ = update_canonical(conn, var_id, soem, 'u', 'Test2', {}, 'resolved', {'width_mm': 1810.0})
    print_result('E', conn, obs_e2, var_id, 'width_mm')
    
    # F. OEM value + conflicting CarWale value
    conn, var_id = setup_fresh_db(conn)
    obs_f1, _ = update_canonical(conn, var_id, soem, 'u', 'Test', {}, 'resolved', {'width_mm': 1800.0})
    obs_f2, _ = update_canonical(conn, var_id, scw, 'u', 'Test2', {}, 'resolved', {'width_mm': 1810.0})
    print_result('F', conn, obs_f2, var_id, 'width_mm')
    
    # G. OEM value + conflicting 91Wheels value
    conn, var_id = setup_fresh_db(conn)
    obs_g1, _ = update_canonical(conn, var_id, soem, 'u', 'Test', {}, 'resolved', {'width_mm': 1800.0})
    obs_g2, _ = update_canonical(conn, var_id, s91, 'u', 'Test2', {}, 'resolved', {'width_mm': 1810.0})
    print_result('G', conn, obs_g2, var_id, 'width_mm')
    
    # H. Equal-authority conflicting sources (OEM vs Global NCAP)
    conn, var_id = setup_fresh_db(conn)
    obs_h1, _ = update_canonical(conn, var_id, soem, 'u', 'Test', {}, 'resolved', {'width_mm': 1800.0})
    obs_h2, _ = update_canonical(conn, var_id, sgncap, 'u', 'Test2', {}, 'resolved', {'width_mm': 1810.0})
    print_result('H', conn, obs_h2, var_id, 'width_mm')
    
    # I. Multiple historical provenance records where strongest source is not newest
    conn, var_id = setup_fresh_db(conn)
    obs_i1, _ = update_canonical(conn, var_id, soem, 'u', 'Test', {}, 'resolved', {'width_mm': 1800.0}) # OEM Tier 1
    obs_i2, _ = update_canonical(conn, var_id, scw, 'u', 'Test2', {}, 'resolved', {'width_mm': 1800.0}) # CarWale Tier 3 confirmed
    obs_i3, _ = update_canonical(conn, var_id, s91, 'u', 'Test3', {}, 'resolved', {'width_mm': 1810.0}) # 91Wheels Tier 2
    print_result('I', conn, obs_i3, var_id, 'width_mm')

    # J. Rejected lower-authority observation after an OEM value has become canonical
    conn, var_id = setup_fresh_db(conn)
    obs_j1, _ = update_canonical(conn, var_id, s91, 'u', 'Test', {}, 'resolved', {'width_mm': 1800.0}) # 91Wheels
    obs_j2, _ = update_canonical(conn, var_id, soem, 'u', 'Test2', {}, 'resolved', {'width_mm': 1810.0}) # OEM
    obs_j3, _ = update_canonical(conn, var_id, scw, 'u', 'Test3', {}, 'resolved', {'width_mm': 1820.0}) # CarWale later
    print_result('J', conn, obs_j3, var_id, 'width_mm')
    
    if conn: conn.close()

run_tests()
