"""Phase 10B W4: re-attribute the 52 OEM brochure observations from source_id 1 (v6_migration) to 6 (oem).
Re-attribution ONLY: no decision re-evaluation, no re-tiering, no quarantine. Each update logs one evidence_amendment row.
Usage: python3 apply_phase10b_w4.py <db_path> <entries.csv>
One BEGIN IMMEDIATE transaction, foreign_keys=ON. Idempotent: rows already at source_id=6 are skipped (no amendment).
Invariants BEFORE COMMIT: only source_observation.source_id changes, only on listed rows (which must also have
source_url='offline_brochure'); only evidence_amendment gains rows; v_variant_canonical_q unchanged; integrity ok."""
import sqlite3, sys, csv
db, path = sys.argv[1], sys.argv[2]
PHASE, REASON = '10B-W4', 'B2_OEM_SOURCE_REATTRIBUTION'
entries = list(csv.DictReader(open(path)))
ids = [int(e['target_id']) for e in entries]
assert len(ids) == 52 and len(set(ids)) == 52 and all(3669 <= i <= 3720 for i in ids)
assert all(e['target_table'] == 'source_observation' and e['column'] == 'source_id' and e['expected_old'] == '1'
           and e['new_value'] == '6' and e['reason_code'] == REASON for e in entries)
c = sqlite3.connect(db, isolation_level=None)
c.execute('PRAGMA foreign_keys=ON')
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
canon = lambda: sorted(c.execute('select * from v_variant_canonical_q').fetchall(), key=lambda r: r[0])
c.execute('BEGIN IMMEDIATE')
try:
    assert c.execute("select name, source_type from source where id=6").fetchone() == ('oem', 'oem')
    before = {t: snap(t) for t in tables}; canon_before = canon()
    upd = 0
    for i in ids:
        sid, url = c.execute('select source_id, source_url from source_observation where id=?', (i,)).fetchone()
        assert url == 'offline_brochure', f'{i}: unexpected url {url!r}'
        if sid == 6: continue
        assert sid == 1, f'{i}: expected source_id 1, found {sid}'
        c.execute('update source_observation set source_id=6 where id=?', (i,))
        c.execute("""insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase)
                     values ('source_observation',?,'source_id','1','6',?,?)""", (i, REASON, PHASE))
        upd += 1
    after = {t: snap(t) for t in tables}
    so_cols = [r[1] for r in c.execute('pragma table_info(source_observation)')]
    for t in tables:
        b, a = before[t], after[t]
        if t == 'evidence_amendment':
            assert set(b) <= set(a) and all(a[k] == b[k] for k in b) and len(a) - len(b) == upd; continue
        assert set(a) == set(b), f'{t}: rows added/deleted'
        for k in b:
            if a[k] == b[k]: continue
            d = [so_cols[j] for j in range(len(so_cols)) if a[k][j] != b[k][j]] if t == 'source_observation' else ['?']
            assert t == 'source_observation' and k in ids and d == ['source_id'], f'{t} {k}: unexpected change {d}'
    assert c.execute("select count(*) from source_observation where source_url='offline_brochure' and source_id=6").fetchone()[0] == 52
    assert c.execute("select count(*) from evidence_amendment where phase=?", (PHASE,)).fetchone()[0] == 52
    assert canon() == canon_before, 'v_variant_canonical_q changed'
    assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
    c.execute('COMMIT'); print(f'COMMITTED; updates={upd}')
except Exception as ex:
    c.execute('ROLLBACK'); print('ROLLBACK:', ex); sys.exit(1)
