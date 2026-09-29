"""Phase 10B W6: correct 12 canonical variant cells to the human-verified OEM brochure values (Phase 10C-1 spot-check),
and quarantine the 13 live field_provenance rows on those cells that contradict the verified value.
Usage: python3 apply_phase10b_w6.py <db_path> <phase10b_w6_targets.csv> <phase10b_w6_quarantine.csv>
One BEGIN IMMEDIATE transaction, foreign_keys=ON.
- Each changed cell logs one evidence_amendment row (reason OEM_SPOTCHECK_VERIFIED, phase 10B-W6). Notes (provenance_id,
  sheet row, page) live in the targets CSV, keyed by (variant_id, column, phase); no DDL.
- Each contradicting field_provenance row gets one evidence_quarantine row (reason CONTRADICTED_BY_OEM_SPOTCHECK,
  target_field NULL as for other non-variant targets). field_provenance itself is NOT touched.
Idempotent: cells already at new_value and field_provenance rows already under an active quarantine with this reason
are skipped. Any other current value aborts.
Invariants BEFORE COMMIT: only the listed variant cells change (that column only); evidence_amendment and
evidence_quarantine gain exactly the new rows; every other table unchanged; v_variant_canonical_q changes only on the
target cells (no target has an inheriting edition since the Brezza cells were held); v_corroboration changes only on the target cells; no active variant quarantine on a target; integrity ok."""
import csv
import sqlite3
import sys

db, tpath, qpath = sys.argv[1], sys.argv[2], sys.argv[3]
PHASE, REASON, QREASON = "10B-W6", "OEM_SPOTCHECK_VERIFIED", "CONTRADICTED_BY_OEM_SPOTCHECK"
TEXT_COLS = {"sunroof"}
INHERITED_OK = set()  # the 821 inheritance was only via Brezza base 142, now held (owner decision 2026-09-29)

T = list(csv.DictReader(open(tpath, newline="")))
Q = list(csv.DictReader(open(qpath, newline="")))
cells = [(int(t["variant_id"]), t["column"]) for t in T]
qids = [int(q["target_id"]) for q in Q]
assert len(T) == 12 and len(set(cells)) == 12
assert len(Q) == 13 and len(set(qids)) == 13
assert all(t["reason_code"] == REASON for t in T)
assert all(t["new_value"] in (("True", "False") if t["column"] in TEXT_COLS else ("0", "1")) for t in T)
assert all(q["target_table"] == "field_provenance" and q["reason_code"] == QREASON and q["phase"] == PHASE
           and (int(q["variant_id"]), q["column"]) in cells for q in Q)

c = sqlite3.connect(db, isolation_level=None)
c.execute("PRAGMA foreign_keys=ON")
vcols = [r[1] for r in c.execute("pragma table_info(variant)")]
assert all(col in vcols for _, col in cells)
qcols = [d[0] for d in c.execute("select * from v_variant_canonical_q limit 0").description]
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
canon = lambda: {r[0]: r for r in c.execute("select * from v_variant_canonical_q")}
corr = lambda: {(r[0], r[1]): r for r in c.execute("select * from v_corroboration")}
typed = lambda col, v: v if col in TEXT_COLS else int(v)

c.execute("BEGIN IMMEDIATE")
try:
    before = {t: snap(t) for t in tables}
    canon_before, corr_before = canon(), corr()
    upd = qins = 0
    for t in T:
        vid, col = int(t["variant_id"]), t["column"]
        assert c.execute("select count(*) from v_active_quarantine where target_table='variant' and target_id=? "
                         "and target_field in (?,'*')", (vid, col)).fetchone()[0] == 0, f"{vid}.{col}: quarantined"
        cur = c.execute(f'select "{col}" from variant where id=?', (vid,)).fetchone()[0]
        new = typed(col, t["new_value"])
        if cur == new and type(cur) is type(new):
            continue
        assert cur == typed(col, t["expected_old"]) and type(cur) is type(new), f"{vid}.{col}: unexpected current {cur!r}"
        c.execute(f'update variant set "{col}"=? where id=?', (new, vid))
        c.execute("""insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase)
                     values ('variant',?,?,?,?,?,?)""", (vid, col, t["expected_old"], t["new_value"], REASON, PHASE))
        upd += 1
    for q in Q:
        fid = int(q["target_id"])
        fp = c.execute("select variant_id, field_name, decision, accepted_value from field_provenance where id=?", (fid,)).fetchone()
        assert fp == (int(q["variant_id"]), q["column"], q["decision"], q["accepted_value"]), f"fp {fid}: drift {fp}"
        if c.execute("select count(*) from v_active_quarantine where target_table='field_provenance' and target_id=? "
                     "and reason_code=?", (fid, QREASON)).fetchone()[0]:
            continue
        c.execute("""insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note)
                     values ('field_provenance',?,NULL,?,?,?)""", (fid, QREASON, PHASE, q["note"]))
        qins += 1

    after = {t: snap(t) for t in tables}
    changed = set()
    for tb in tables:
        b, a = before[tb], after[tb]
        if tb in ("evidence_amendment", "evidence_quarantine"):
            assert set(b) <= set(a) and all(a[k] == b[k] for k in b), f"{tb}: existing rows changed"
            added = [a[k] for k in set(a) - set(b)]
            assert len(added) == (upd if tb == "evidence_amendment" else qins), f"{tb}: unexpected row count"
            if tb == "evidence_quarantine":
                assert sorted(r[2] for r in added) == sorted(qids if qins else [])
                assert all(r[1] == "field_provenance" and r[4] == QREASON and r[5] == PHASE for r in added)
            continue
        assert set(a) == set(b), f"{tb}: rows added/deleted"
        for k in b:
            if a[k] == b[k]:
                continue
            assert tb == "variant", f"{tb} {k}: unexpected change"
            for j, col in enumerate(vcols):
                if a[k][j] != b[k][j] or type(a[k][j]) is not type(b[k][j]):
                    assert (k, col) in cells, f"variant {k}.{col}: unexpected change"
                    changed.add((k, col))
    assert len(changed) == upd
    ca = canon()
    assert set(ca) == set(canon_before)
    qchanged = {(k, col) for k in ca for j, col in enumerate(qcols) if ca[k][j] != canon_before[k][j]}
    assert qchanged <= set(cells) | INHERITED_OK, f"canonical_q unexpected: {qchanged - set(cells) - INHERITED_OK}"
    if upd:
        assert qchanged == set(cells) | INHERITED_OK, f"canonical_q missing: {set(cells) | INHERITED_OK - qchanged}"
    co = corr()
    cchanged = {k for k in set(co) | set(corr_before) if co.get(k) != corr_before.get(k)}
    assert cchanged <= set(cells), f"v_corroboration unexpected: {cchanged - set(cells)}"
    assert c.execute("select count(*) from evidence_amendment where phase=?", (PHASE,)).fetchone()[0] == 12
    assert c.execute("select count(*) from v_active_quarantine where phase=? and reason_code=?", (PHASE, QREASON)).fetchone()[0] == 13
    assert c.execute("select count(*) from v_live_evidence e where decision in ('accepted','confirmed') and exists "
                     "(select 1 from evidence_quarantine q where q.phase=? and q.target_table='field_provenance' "
                     "and q.target_id=e.fp_id)", (PHASE,)).fetchone()[0] == 0
    assert c.execute("pragma integrity_check").fetchone()[0] == "ok"
    c.execute("COMMIT")
    print(f"COMMITTED; updates={upd}; quarantine_inserts={qins}; canonical_q cells changed={len(qchanged)}; "
          f"v_corroboration cells changed={len(cchanged)}")
except Exception as ex:
    c.execute("ROLLBACK")
    print("ROLLBACK:", ex)
    sys.exit(1)
