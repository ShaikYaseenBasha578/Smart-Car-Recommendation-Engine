"""Phase 10G: full per-table EXCEPT diff in both directions. Usage: except_diff_phase10g.py <before.db> <after.db>"""
import sqlite3, sys
c = sqlite3.connect(sys.argv[2]); c.execute("attach ? as b", (sys.argv[1],))
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' order by name")]
tb = [r[0] for r in c.execute("select name from b.sqlite_master where type='table' order by name")]
assert tables == tb, ("table sets differ", tables, tb)
sb = c.execute("select type,name,sql from b.sqlite_master where name not like 'sqlite_%' order by 1,2").fetchall()
sa = c.execute("select type,name,sql from main.sqlite_master where name not like 'sqlite_%' order by 1,2").fetchall()
print("schema identical:", sa == sb)
total = 0
for t in tables:
    added = c.execute(f'select * from main."{t}" except select * from b."{t}"').fetchall()
    removed = c.execute(f'select * from b."{t}" except select * from main."{t}"').fetchall()
    if added or removed:
        print(f"## {t}: +{len(added)} -{len(removed)}")
        for r in removed: print("  -", r)
        for r in added: print("  +", r)
    total += len(added) + len(removed)
print("total differing rows:", total)
