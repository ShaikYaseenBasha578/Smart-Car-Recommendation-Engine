"""Phase 10B W3: B5 + B6 BNCAP status fixes. Only resolution_status on the listed rows is updated
(each logged to evidence_amendment); applicability row 14 is quarantined, never deleted.
Usage: python3 apply_phase10b_w3.py <db_path> <entries.csv>
One BEGIN IMMEDIATE transaction, foreign_keys=ON. Idempotent: an update whose current value already equals
new_value is skipped (no amendment row); a quarantine already active is skipped. Any row not in the expected
state -> ROLLBACK. Invariants checked BEFORE COMMIT."""
import sqlite3, sys, csv
db, path = sys.argv[1], sys.argv[2]
PHASE = '10B-W3'
entries = list(csv.DictReader(open(path)))
c = sqlite3.connect(db, isolation_level=None)
c.execute('PRAGMA foreign_keys=ON')
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
c.execute('BEGIN IMMEDIATE')
try:
    before = {t: snap(t) for t in tables}
    upd = q = 0
    touched = {}  # (table, id) -> column
    for e in entries:
        tt, tid = e['target_table'], int(e['target_id'])
        if e['action'] == 'update':
            assert tt in ('safety_test', 'source_observation') and e['column_or_field'] == 'resolution_status'
            cur = c.execute(f'select resolution_status from "{tt}" where id=?', (tid,)).fetchone()
            assert cur is not None, f'missing {tt} {tid}'
            touched[(tt, tid)] = 'resolution_status'
            if cur[0] == e['new_value']: continue
            assert cur[0] == e['expected_old'], f'{tt} {tid}: expected {e["expected_old"]!r}, found {cur[0]!r}'
            c.execute(f'update "{tt}" set resolution_status=? where id=?', (e['new_value'], tid))
            c.execute("""insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase)
                         values (?,?,?,?,?,?,?)""", (tt, tid, 'resolution_status', cur[0], e['new_value'], e['reason_code'], PHASE))
            upd += 1
        elif e['action'] == 'quarantine':
            assert c.execute(f'select count(*) from "{tt}" where id=?', (tid,)).fetchone()[0] == 1, f'missing {tt} {tid}'
            if c.execute("""select count(*) from evidence_quarantine where released_at is null and target_table=? and target_id=?
                            and target_field is null and reason_code=?""", (tt, tid, e['reason_code'])).fetchone()[0]: continue
            c.execute("""insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note)
                         values (?,?,NULL,?,?,?)""", (tt, tid, e['reason_code'], PHASE, e['note']))
            q += 1
        else:
            raise ValueError(e['action'])
    after = {t: snap(t) for t in tables}
    for t in tables:
        b, a = before[t], after[t]
        if t in ('evidence_quarantine', 'evidence_amendment'):
            assert set(b) <= set(a) and all(a[k] == b[k] for k in b), f'{t}: existing rows changed'
            continue
        assert set(a) == set(b), f'{t}: rows added/deleted'
        cols = [r[1] for r in c.execute(f'pragma table_info("{t}")')]
        for k in b:
            if a[k] == b[k]: continue
            diff = [cols[i] for i in range(len(cols)) if a[k][i] != b[k][i]]
            assert touched.get((t, k)) == 'resolution_status' and diff == ['resolution_status'], f'{t} {k}: unexpected change {diff}'
    added_q = len(after['evidence_quarantine']) - len(before['evidence_quarantine'])
    added_a = len(after['evidence_amendment']) - len(before['evidence_amendment'])
    assert (added_q, added_a) == (q, upd), (added_q, added_a, q, upd)
    for e in entries:
        if e['action'] == 'update':
            assert c.execute(f'select resolution_status from "{e["target_table"]}" where id=?', (int(e['target_id']),)).fetchone()[0] == e['new_value']
    assert c.execute("select count(*) from evidence_quarantine where released_at is null and phase=?", (PHASE,)).fetchone()[0] == 1
    assert c.execute("select count(*) from evidence_amendment where phase=?", (PHASE,)).fetchone()[0] == 5
    assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
    c.execute('COMMIT'); print(f'COMMITTED; updates={upd}; quarantines={q}')
except Exception as ex:
    c.execute('ROLLBACK'); print('ROLLBACK:', ex); sys.exit(1)
