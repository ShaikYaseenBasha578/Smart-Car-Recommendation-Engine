import sqlite3
conn = sqlite3.connect('scratch/carrec_kb_phase8a_shadow.db')
conn.row_factory = sqlite3.Row

tests = ['MARUTI-BALENO-GASOLINE (2 AB)', 'MARUTI-BALENO-GASOLINE (6 AB)', 'TATA – Punch.ev 2026', 'TATA PUNCH.EV', 'TATA SAFARI/ HARRIER', 'MARUTI – BREZZA']
for t in tests:
    st = conn.execute("SELECT id FROM safety_test WHERE tested_vehicle_name=?", (t,)).fetchone()
    if not st: 
        print(f"\n--- {t} --- Not in DB")
        continue
    
    apps = conn.execute("SELECT * FROM safety_test_applicability WHERE safety_test_id=?", (st['id'],)).fetchall()
    
    print(f"\n--- {t} ---")
    high_level = [a for a in apps if a['mapping_status'] in ('MODEL_SCOPE', 'FAMILY_SCOPE')]
    if high_level:
        print(f"High-level Scope: {high_level[0]['mapping_status']}")
        
    explicit = [a for a in apps if a['mapping_status'] in ('EXACT_CANONICAL_VARIANT', 'EXPLICIT_SOURCE_VARIANT_UNRESOLVED')]
    print(f"Explicit Variants Extracted: {len(explicit)}")
    for e in explicit:
        print(f" - {e['source_variant_name']} -> {e['mapping_status']} (canonical_id: {e['variant_id']})")
