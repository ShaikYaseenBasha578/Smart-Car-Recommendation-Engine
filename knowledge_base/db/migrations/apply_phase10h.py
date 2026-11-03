"""Phase 10H: quarantine resolver mislinks (inserts into evidence_quarantine only).

Usage: python3 apply_phase10h.py <db_path> <phase10h_entries.csv>
One BEGIN IMMEDIATE transaction with foreign_keys=ON. No DDL. Every invariant is checked before COMMIT; any failure
rolls back. Idempotent: an entry is skipped when an identical active quarantine (table, id, field, reason) exists.

Entries (built by build_entries.py from classify_links.py output; 10B-W1 pattern, no re-linking):
  H1_RESOLVER_MISLINK          source_observation  resolved to the wrong variant; the KB has the right one (in the note)
  H1_RESOLVER_NO_KB_VARIANT    source_observation  resolved to the wrong variant; the KB has no matching variant
  H1_EDITION_NOT_IN_KB         source_observation  an edition the KB doesn't model, attached to its base
  H1_SOLE_SOURCE_FROM_MISLINK  variant cell        stored canonical value whose only live evidence is the above
Owner decisions (2026-11-03): obs 3302 held out (Jimny "Zeta" vs "Zeta PRO", unclear), so v597 cruise_control is not
in Q3; Brezza 821's identity (name says 1.0L Turbo, powertrain is 1.5) is not written, but its 3 sole-source feature
cells are masked like any other Q3 cell.
"""
import csv
import json
import sqlite3
import sys

PHASE = "10H"
EXPECTED = {"H1_RESOLVER_MISLINK": 442, "H1_RESOLVER_NO_KB_VARIANT": 116, "H1_EDITION_NOT_IN_KB": 56,
            "H1_SOLE_SOURCE_FROM_MISLINK": 47}
ACTIVE_AFTER = 1383  # 722 before 10H


def main():
    db, entries_path = sys.argv[1], sys.argv[2]
    entries = list(csv.DictReader(open(entries_path)))
    got = {}
    for e in entries:
        got[e["reason_code"]] = got.get(e["reason_code"], 0) + 1
    assert got == EXPECTED, f"entry list counts {got} != {EXPECTED}"
    assert not any(e["target_table"] == "source_observation" and e["target_id"] == "3302" for e in entries)
    assert not any(e["target_table"] == "variant" and e["target_id"] == "597" and e["target_field"] == "cruise_control" for e in entries)
    # 821: only its identity (powertrain/transmission) is held; its 3 sole-source feature cells are in Q3 (owner, 2026-11-03)
    assert not any(e["target_table"] == "variant" and e["target_id"] == "821" and e["target_field"] in ("transmission", "powertrain_id") for e in entries)
    c = sqlite3.connect(db, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    one = lambda sql, *a: c.execute(sql, a).fetchone()
    tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
    snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
    vcols = {r[1] for r in c.execute("pragma table_info(variant)")}
    c.execute("BEGIN IMMEDIATE")
    try:
        before = {t: snap(t) for t in tables}
        schema_before = {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")}
        canon_cols = [d[0] for d in c.execute("select * from v_variant_canonical_q limit 0").description]
        canon_before = {r[0]: r for r in c.execute("select * from v_variant_canonical_q")}
        inserted = 0
        for e in entries:
            tt, tid, tf = e["target_table"], int(e["target_id"]), (e["target_field"] or None)
            assert tt in ("source_observation", "variant"), tt
            assert one(f'select count(*) from "{tt}" where id=?', tid)[0] == 1, f"missing target {tt} {tid}"
            if tt == "source_observation":
                assert tf is None
                src, vid = one("select s.name, o.resolved_variant_id from source_observation o join source s on s.id=o.source_id where o.id=?", tid)
                assert src in ("91wheels", "v3cars", "carwale") and vid is not None, (tid, src, vid)
            else:
                assert tf in vcols and tf in canon_cols, tf
                assert one(f'select "{tf}" from variant where id=?', tid)[0] is not None, f"variant {tid}.{tf}: not stored on the variant"
            if one("""select count(*) from evidence_quarantine where released_at is null and target_table=? and target_id=?
                      and ifnull(target_field,'')=ifnull(?,'') and reason_code=?""", tt, tid, tf, e["reason_code"])[0]:
                continue
            if tt == "source_observation":
                assert one("select count(*) from evidence_quarantine where released_at is null and target_table='source_observation' and target_id=?", tid)[0] == 0, f"obs {tid} already quarantined"
            c.execute("insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note) values (?,?,?,?,?,?)",
                      (tt, tid, tf, e["reason_code"], PHASE, e["note"]))
            inserted += 1

        # ================= invariants before COMMIT =================
        after = {t: snap(t) for t in tables}
        for t in tables:
            b, a = before[t], after[t]
            if t == "evidence_quarantine":
                assert set(b) <= set(a) and all(a[k] == b[k] for k in b), "existing quarantine rows changed"
                new = [a[k] for k in set(a) - set(b)]
                assert len(new) == inserted and all(r[5] == PHASE for r in new)
                continue
            assert a == b, f"{t} changed"
        assert {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")} == schema_before, "schema changed"
        active = one("select count(*) from evidence_quarantine where released_at is null")[0]
        assert active == ACTIVE_AFTER, f"active quarantines {active} != {ACTIVE_AFTER}"
        assert one("select count(*) from evidence_quarantine where released_at is null and phase=?", PHASE)[0] == len(entries)
        # canonical view: exactly the Q3 cells change, each to NULL
        q3 = {(int(e["target_id"]), e["target_field"]) for e in entries if e["target_table"] == "variant"}
        changed = set()
        for vid, row in ((r[0], r) for r in c.execute("select * from v_variant_canonical_q")):
            for j, col in enumerate(canon_cols):
                if row[j] != canon_before[vid][j]:
                    changed.add((vid, col))
                    assert row[j] is None, f"canonical {vid}.{col} changed to {row[j]!r}, not NULL"
        idx = {col: j for j, col in enumerate(canon_cols)}
        # editions inherit a NULL cell from their base, and the view masks it when the base cell is quarantined
        inherits = {(r[0], f) for r in c.execute("select id, base_variant_id from variant where base_variant_id is not null")
                    for b, f in q3 if b == r[1] and one(f'select "{f}" from variant where id=?', r[0])[0] is None}
        expected = {(vid, f) for vid, f in q3 | inherits if canon_before[vid][idx[f]] is not None}  # empty on an idempotent re-run
        assert changed == expected, f"canonical changes {sorted(changed ^ expected)[:10]} differ from the Q3 list"
        assert all(one(f'select "{f}" from v_variant_canonical_q where id=?', vid)[0] is None for vid, f in q3)
        # every quarantined observation is out of the live evidence; every Q3 cell has no live evidence left
        obs_ids = [int(e["target_id"]) for e in entries if e["target_table"] == "source_observation"]
        assert one(f"select count(*) from v_live_evidence where observation_id in ({','.join(map(str, obs_ids))})")[0] == 0
        for vid, f in q3:
            assert one("select count(*) from v_live_evidence where variant_id=? and field_name=? and decision in ('accepted','confirmed')", vid, f)[0] == 0, (vid, f)
        assert one("select count(*) from variant")[0] == 832
        assert one("pragma integrity_check")[0] == "ok"
        fk = c.execute("pragma foreign_key_check").fetchall()
        assert len(fk) == 297 and all(r[0] == "field_provenance" and r[2] == "source_observation" for r in fk), len(fk)
        c.execute("COMMIT")
        print(f"COMMITTED; {json.dumps({'inserted': inserted, 'active': active, 'canonical_cells_masked': len(changed)})}")
    except Exception as ex:
        c.execute("ROLLBACK")
        import traceback
        traceback.print_exc()
        print("ROLLBACK:", repr(ex))
        sys.exit(1)


if __name__ == "__main__":
    main()
