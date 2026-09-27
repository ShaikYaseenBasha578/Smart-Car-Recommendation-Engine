"""Apply phase10b_w3b_schema.sql to ONE SQLite file in a single transaction.
Usage: python3 apply_phase10b_w3b.py <db_path> <schema.sql>
Invariants checked BEFORE COMMIT: existing tables' row counts unchanged; new objects == expected set
(or already present on re-run); integrity_check ok. Any failure -> ROLLBACK, exit 1."""
import sqlite3, sys
db, ddl_path = sys.argv[1], sys.argv[2]
EXPECTED = {('view','v_safety_applicability_q')}
ddl = open(ddl_path).read()
stmts, buf = [], ''
for line in ddl.splitlines(keepends=True):
    buf += line
    if sqlite3.complete_statement(buf):
        if buf.strip(): stmts.append(buf.strip())
        buf = ''
assert not buf.strip(), 'trailing incomplete SQL'
c = sqlite3.connect(db, isolation_level=None)
c.execute('PRAGMA foreign_keys=ON')
objs = lambda: {(t, n) for t, n in c.execute("select type,name from sqlite_master where name not like 'sqlite_autoindex%'")}
before_objs = objs()
tables = [n for t, n in before_objs if t == 'table']
counts = lambda: {t: c.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables}
before = counts()
c.execute('BEGIN IMMEDIATE')
try:
    for s in stmts: c.execute(s)
    after = counts()
    assert after == before, f'row counts changed: {[t for t in tables if after[t]!=before[t]]}'
    new = objs() - before_objs
    assert new <= EXPECTED and (new | (before_objs & EXPECTED)) == EXPECTED, f'unexpected objects: {new ^ EXPECTED}'
    assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
    for v in ('v_safety_applicability_q',):
        c.execute(f'select count(*) from {v}').fetchone()
    c.execute('COMMIT')
    print('COMMITTED; new objects:', sorted(new))
except Exception as e:
    c.execute('ROLLBACK'); print('ROLLBACK:', e); sys.exit(1)
