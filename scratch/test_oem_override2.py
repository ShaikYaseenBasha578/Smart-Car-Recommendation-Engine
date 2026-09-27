import sqlite3
from knowledge_base.ingestion.common.updater import update_canonical

def run():
    conn = sqlite3.connect("knowledge_base/carrec_kb.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 1. Create a dummy variant with NULL boot space
    cur.execute("INSERT INTO model (manufacturer_id, name) VALUES (1, 'TestModel')")
    model_id = cur.lastrowid
    cur.execute("INSERT INTO variant (model_id, name, transmission) VALUES (?, 'TestVariant', 'Manual')", (model_id,))
    var_id = cur.lastrowid
    
    # 2. Add 91wheels observation (Tier 2) - should be accepted
    cur.execute("SELECT id FROM source WHERE name = '91wheels'")
    s91 = cur.fetchone()['id']
    obs1, upd1 = update_canonical(conn, var_id, s91, 'http://test', 'TestVariant', {}, 'resolved', {'boot_space_litres': 300.0})
    print(f"91wheels update: {upd1} fields")
    cur.execute("SELECT decision, decision_reason FROM field_provenance WHERE source_observation_id = ?", (obs1,))
    print(f"91wheels prov: {dict(cur.fetchone())}")
    
    # 3. Add CarWale observation (Tier 3) with conflicting value - should be REJECTED
    cur.execute("SELECT id FROM source WHERE name = 'carwale'")
    scw = cur.fetchone()['id']
    obs2, upd2 = update_canonical(conn, var_id, scw, 'http://test2', 'TestVariant', {}, 'resolved', {'boot_space_litres': 310.0})
    print(f"CarWale update: {upd2} fields")
    cur.execute("SELECT decision, decision_reason FROM field_provenance WHERE source_observation_id = ?", (obs2,))
    print(f"CarWale prov: {dict(cur.fetchone())}")
    
    # 4. Add OEM observation (Tier 1) with conflicting value - should OVERRIDE
    cur.execute("SELECT id FROM source WHERE name = 'oem'")
    soem = cur.fetchone()['id']
    obs3, upd3 = update_canonical(conn, var_id, soem, 'http://test3', 'TestVariant', {}, 'resolved', {'boot_space_litres': 320.0})
    print(f"OEM update: {upd3} fields")
    cur.execute("SELECT decision, decision_reason FROM field_provenance WHERE source_observation_id = ?", (obs3,))
    print(f"OEM prov: {dict(cur.fetchone())}")
    
    # Verify final value
    cur.execute("SELECT boot_space_litres FROM variant WHERE id = ?", (var_id,))
    print(f"Final boot space: {cur.fetchone()['boot_space_litres']}")
    
    conn.rollback() # Don't save
run()
