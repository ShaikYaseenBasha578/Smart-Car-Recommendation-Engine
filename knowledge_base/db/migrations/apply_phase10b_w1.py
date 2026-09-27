"""Phase 10B W1: insert B3 quarantine entries into evidence_quarantine. Inserts only.
Usage: python3 apply_phase10b_w1.py <db_path> <entries.csv>
One BEGIN IMMEDIATE transaction, foreign_keys=ON. Idempotent: an entry is skipped if an identical
active quarantine (table, id, field, reason) exists. Invariants checked BEFORE COMMIT; any failure -> ROLLBACK."""
import sqlite3, sys, csv
db, entries_path = sys.argv[1], sys.argv[2]
PHASE = '10B-W1'
entries = list(csv.DictReader(open(entries_path)))
c = sqlite3.connect(db, isolation_level=None)
c.execute('PRAGMA foreign_keys=ON')
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
counts = lambda: {t: c.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables}
c.execute('BEGIN IMMEDIATE')
try:
    before = counts()
    inserted = 0
    for e in entries:
        tt, tid, tf = e['target_table'], int(e['target_id']), (e['target_field'] or None)
        assert tt in ('source_observation', 'variant'), tt
        assert c.execute(f'select count(*) from "{tt}" where id=?', (tid,)).fetchone()[0] == 1, f'missing target {tt} {tid}'
        if tf: assert tf in [r[1] for r in c.execute('pragma table_info(variant)')], f'bad field {tf}'
        exists = c.execute("""select count(*) from evidence_quarantine where released_at is null and target_table=?
                              and target_id=? and ifnull(target_field,'')=ifnull(?,'') and reason_code=?""",
                           (tt, tid, tf, e['reason_code'])).fetchone()[0]
        if exists: continue
        c.execute("""insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note)
                     values (?,?,?,?,?,?)""", (tt, tid, tf, e['reason_code'], PHASE, e['note']))
        inserted += 1
    after = counts()
    changed = {t: after[t] - before[t] for t in tables if after[t] != before[t]}
    expected = {'evidence_quarantine': inserted} if inserted else {}
    # sqlite_sequence gains/updates a row for evidence_quarantine on first insert (AUTOINCREMENT bookkeeping)
    changed.pop('sqlite_sequence', None)
    assert changed == expected, f'unexpected table changes: {changed}'
    active = c.execute("select count(*) from evidence_quarantine where released_at is null and phase=?", (PHASE,)).fetchone()[0]
    assert active == len(entries), f'active W1 entries {active} != {len(entries)}'
    assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
    c.execute('COMMIT'); print(f'COMMITTED; inserted={inserted}; active W1 entries={active}')
except Exception as ex:
    c.execute('ROLLBACK'); print('ROLLBACK:', ex); sys.exit(1)
