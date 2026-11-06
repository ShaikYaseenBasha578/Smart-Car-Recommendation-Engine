"""Phase 10H-b: quarantine the 3 resolver mislinks 10H missed (owner decision 4, 2026-11-06). Inserts only; no re-linking.
Usage: apply_phase10hb.py <db_path>. One BEGIN IMMEDIATE transaction, foreign_keys=ON, no DDL, idempotent; invariants before COMMIT.
These observations carry no field_provenance rows, so no cell is left without evidence and the canonical view is unchanged.
All three were judged mislinks by a fresh blind subagent (reports/phase10i1a/validation)."""
import sqlite3, sys
PHASE = "10H-b"; REASON = "H1_RESOLVER_MISLINK"
ENTRIES = [
 (955, 206, "src=91wheels; resolved_variant=206 'X-Line(A) 1.5 Diesel AT'; source_name='X-Line (A) G1.5 Smartstream T-GDI 7AT (DCT)'; mismatch=fuel (turbo petrol vs diesel); better_target=191; blind-validated"),
 (1151, 690, "src=91wheels; resolved_variant=690 'AX7 L 2WD Diesel 2.2L Turbo Automatic'; source_name='AX7L Diesel 4WD AT (TC)'; mismatch=drivetrain (4WD vs 2WD); better_target=693; blind-validated"),
 (1157, 691, "src=91wheels; resolved_variant=691 'AX7 L 2WD Diesel 2.2L Turbo Manual'; source_name='AX7L 4WD MOCHA INTRS Diesel'; mismatch=drivetrain (4WD vs 2WD); better_target=694 (interior option not modelled); blind-validated"),
]
c = sqlite3.connect(sys.argv[1], isolation_level=None); c.execute("PRAGMA foreign_keys=ON"); one = lambda q, *a: c.execute(q, a).fetchone()
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
c.execute("BEGIN IMMEDIATE")
try:
    before = {t: snap(t) for t in tables}; canon = c.execute("select * from v_variant_canonical_q").fetchall()
    schema = c.execute("select name, sql from sqlite_master where name not like 'sqlite_%' order by 1").fetchall()
    n = 0
    for oid, vid, note in ENTRIES:
        assert one("select resolved_variant_id from source_observation where id=?", oid)[0] == vid, oid
        assert one("select count(*) from field_provenance where source_observation_id=?", oid)[0] == 0, oid
        if one("select count(*) from evidence_quarantine where released_at is null and target_table='source_observation' and target_id=?", oid)[0]: continue
        c.execute("insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note) values ('source_observation',?,NULL,?,?,?)", (oid, REASON, PHASE, note)); n += 1
    after = {t: snap(t) for t in tables}
    for t in tables:
        if t == "evidence_quarantine":
            assert set(before[t]) <= set(after[t]) and all(after[t][k] == before[t][k] for k in before[t]) and len(after[t]) - len(before[t]) == n
        else: assert after[t] == before[t], t
    assert c.execute("select * from v_variant_canonical_q").fetchall() == canon
    assert c.execute("select name, sql from sqlite_master where name not like 'sqlite_%' order by 1").fetchall() == schema
    assert one("select count(*) from evidence_quarantine where released_at is null")[0] == 1386
    assert one("pragma integrity_check")[0] == "ok"
    fk = c.execute("pragma foreign_key_check").fetchall(); assert len(fk) == 297
    c.execute("COMMIT"); print(f"COMMITTED; inserted={n}; active=1386")
except Exception as ex:
    c.execute("ROLLBACK"); print("ROLLBACK:", repr(ex)); sys.exit(1)
