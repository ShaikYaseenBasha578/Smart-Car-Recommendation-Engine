"""Phase 10G (held items from 10F): one controlled write.

Usage: python3 apply_phase10g.py <db_path>
One BEGIN IMMEDIATE transaction with foreign_keys=ON. No DDL. Every invariant is checked before COMMIT; any
failure rolls back. Idempotent: a re-run on an already-corrected DB makes no change.

Write mechanism (Phase 10E/10F pattern): UPDATE + one evidence_amendment row per changed cell.
Scope (owner decisions at the 10G checkpoint, 2026-11-03):
  pt 84 Grand Vitara CNG 87.8 and pt 88 Victoris Petrol Hybrid 115.6 -> power_bhp NULL (unverified). Both figures
    are PS values labelled bhp (87.8 PS = the K15C CNG-mode figure printed by Victoris p16 / Hyryder p14; 115.6 =
    the 85 kW system figure printed by Grand Vitara p15 / Hyryder p14), and neither model's own brochure prints
    the figure. evidence_quarantine cannot target powertrain (CHECK constraint), so NULL is the only no-DDL way to
    show the cell as unverified. The description drops the figure ("1462cc CNG"), as it embeds the same value.
    The v6 source_observation rows (548/549 and 567/570/571/574/575) are kept unchanged as evidence. These
    variants have no power_bhp field_provenance rows, so none is written or quarantined.
  833 left untouched: v_variant_canonical_q passes powertrain_id through unmasked, so quarantining its powertrain
    would need a view change (DDL).
"""
import json
import sqlite3
import sys

PHASE = "10G"
REASON = "PS_AS_BHP_NO_OEM_SOURCE"
# (pt, model_id, fuel, cc, old power_bhp, old description, new description, base-variant users, editions)
POWERTRAINS = [
    (84, 39, "CNG", 1462.0, 87.8, "1462cc 87.8bhp CNG", "1462cc CNG", (548, 549), ()),
    (88, 40, "Petrol Hybrid", 1490.0, 115.6, "1490cc 115.6bhp Petrol Hybrid", "1490cc Petrol Hybrid",
     (567, 570, 571, 574, 575), ()),
]
V6_OBS = {84: (548, 549), 88: (567, 570, 571, 574, 575)}  # observation ids == variant ids for v6_migration rows


def main():
    db = sys.argv[1]
    c = sqlite3.connect(db, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    one = lambda sql, *a: c.execute(sql, a).fetchone()
    tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
    snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
    counts = dict(update=0, amend=0)
    c.execute("BEGIN IMMEDIATE")
    try:
        before = {t: snap(t) for t in tables}
        schema_before = {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")}
        canon_before = {r[0]: r for r in c.execute("select * from v_variant_canonical_q")}

        def amend(tid, col, old, new):
            c.execute("""insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase)
                         values ('powertrain',?,?,?,?,?,?)""",
                      (tid, col, None if old is None else str(old), None if new is None else str(new), REASON, PHASE))
            counts["amend"] += 1

        for pt, mid, fuel, cc, old, d_old, d_new, users, editions in POWERTRAINS:
            row = one("select model_id, fuel_type, engine_cc, power_bhp, description from powertrain where id=?", pt)
            if row[3] is not None:
                assert row == (mid, fuel, cc, old, d_old), f"powertrain {pt}: drift {row}"
                c.execute("update powertrain set power_bhp=NULL, description=? where id=?", (d_new, pt))
                counts["update"] += 1
                amend(pt, "power_bhp", old, None)
                amend(pt, "description", d_old, d_new)
            assert one("select power_bhp, description from powertrain where id=?", pt) == (None, d_new)
            got_users = tuple(r[0] for r in c.execute("select id from variant where powertrain_id=? and base_variant_id is null order by id", (pt,)))
            got_eds = tuple(r[0] for r in c.execute("select id from variant where powertrain_id=? and base_variant_id is not null order by id", (pt,)))
            assert got_users == users and got_eds == editions, (pt, got_users, got_eds)
            assert one(f"select count(*) from field_provenance where field_name='power_bhp' and variant_id in ({','.join('?' * len(users))})", *users)[0] == 0
            for oid in V6_OBS[pt]:
                p = json.loads(one("select raw_payload from source_observation where id=? and source_id=1 and resolved_variant_id=?", oid, oid)[0])
                assert p["power_bhp"] == str(old), (oid, p.get("power_bhp"))

        # ================= invariants before COMMIT =================
        pts = {p[0] for p in POWERTRAINS}
        pcols = [r[1] for r in c.execute("pragma table_info(powertrain)")]
        after = {t: snap(t) for t in tables}
        for t in tables:
            b, a = before[t], after[t]
            if t == "evidence_amendment":
                assert set(b) <= set(a) and all(a[k] == b[k] for k in b), f"{t}: existing rows changed"
                new_rows = [a[k] for k in set(a) - set(b)]
                assert all(r[1] == "powertrain" and r[6] == REASON and r[7] == PHASE for r in new_rows)
                assert len(new_rows) == counts["amend"]
                continue
            assert set(a) == set(b), f"{t}: rows added/deleted"
            for k in b:
                if a[k] == b[k]:
                    continue
                if t == "powertrain":
                    diff = {pcols[j] for j in range(len(pcols)) if a[k][j] != b[k][j]}
                    assert k in pts and diff <= {"power_bhp", "description"}, f"powertrain {k}: {diff}"
                else:
                    raise AssertionError(f"{t} {k}: unexpected change")
        schema_after = {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")}
        assert schema_after == schema_before, "schema changed"
        assert {r[0]: r for r in c.execute("select * from v_variant_canonical_q")} == canon_before, "canonical view changed"
        assert one("select count(*) from variant")[0] == 832
        assert one("select count(*) from powertrain where power_bhp is null")[0] == len(POWERTRAINS)
        assert one("select count(*) from evidence_quarantine where released_at is null")[0] == 722
        assert one("select * from variant where id=833") == before["variant"][833], "833 must stay untouched"
        assert one("pragma integrity_check")[0] == "ok"
        fk = c.execute("pragma foreign_key_check").fetchall()
        assert len(fk) == 297 and all(r[0] == "field_provenance" and r[2] == "source_observation" for r in fk), len(fk)
        c.execute("COMMIT")
        print(f"COMMITTED; {json.dumps(counts)}")
    except Exception as ex:
        c.execute("ROLLBACK")
        import traceback
        traceback.print_exc()
        print("ROLLBACK:", repr(ex))
        sys.exit(1)


if __name__ == "__main__":
    main()
