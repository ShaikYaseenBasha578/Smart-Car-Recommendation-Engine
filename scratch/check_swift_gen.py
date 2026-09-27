import sqlite3
conn = sqlite3.connect("scratch/integration_test_kb.db")
c = conn.cursor()
c.execute("SELECT g.id, g.name, g.start_year, m.name, mk.name FROM generation g JOIN model m ON g.model_id = m.id JOIN manufacturer mk ON m.manufacturer_id = mk.id WHERE m.name LIKE '%Swift%'")
for r in c.fetchall():
    print(r)
