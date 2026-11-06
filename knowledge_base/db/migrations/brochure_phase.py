"""Shared body of a brochure-evidence controlled write (P1, P10): correct or confirm base-variant cells, each with one OEM
observation and one provenance row citing PDF, page and SHA-1, and optionally release a named quarantine on the cell.
One BEGIN IMMEDIATE transaction, foreign_keys=ON, no DDL, idempotent, invariants checked before COMMIT.

A cell is a dict: vid, col, old, new, bro, page, printed, reason (amendment reason code), release (quarantine reason code or None).
old == new means the brochure confirms the stored value."""
import json
import sqlite3

OEM_SOURCE_ID = 6


def same(a, b):
    if a is None or b is None: return a is b
    try: return float(a) == float(b)
    except (TypeError, ValueError):
        return {"true": "1", "false": "0"}.get(str(a).lower(), str(a)) == {"true": "1", "false": "0"}.get(str(b).lower(), str(b))


def run(db, phase, bro_table, cells, expect_counts=None, quarantine_contradicted=False):
    method, fp_reason = f"manual_brochure_{phase}", f"OEM_BROCHURE_VERIFIED_{phase}"
    c = sqlite3.connect(db, isolation_level=None); c.execute("PRAGMA foreign_keys=ON")
    one = lambda q, *a: c.execute(q, a).fetchone()
    tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
    snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
    n = dict(corrected=0, confirmed=0, amend=0, obs=0, fp=0, released=0)
    if quarantine_contradicted: n["quar"] = 0
    assert len({(x["vid"], x["col"]) for x in cells}) == len(cells), "duplicate cell"
    c.execute("BEGIN IMMEDIATE")
    try:
        before = {t: snap(t) for t in tables}
        schema = c.execute("select name, sql from sqlite_master where name not like 'sqlite_%' order by 1").fetchall()
        canon_cols = [d[0] for d in c.execute("select * from v_variant_canonical_q limit 0").description]
        canon_before = {r[0]: r for r in c.execute("select * from v_variant_canonical_q")}
        for x in cells:
            vid, col = x["vid"], x["col"]
            assert one("select base_variant_id from variant where id=?", vid)[0] is None, f"{vid} is an edition (P8)"
            assert x["bro"] in bro_table, x["bro"]
            cur = one(f'select "{col}" from variant where id=?', vid)[0]
            if not same(cur, x["new"]):
                assert same(cur, x["old"]), f"{vid}.{col}: expected {x['old']!r}, found {cur!r}"
                c.execute(f'update variant set "{col}"=? where id=?', (x["new"], vid)); n["corrected"] += 1
                c.execute("insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase) values ('variant',?,?,?,?,?,?)",
                          (vid, col, None if x["old"] is None else str(x["old"]), str(x["new"]), x["reason"], phase)); n["amend"] += 1
            elif same(x["old"], x["new"]) and not one("select count(*) from evidence_amendment where target_table='variant' and target_id=? and column_name=? and phase=?", vid, col, phase)[0]:
                n["confirmed"] += 1
            path, sha1 = bro_table[x["bro"]]
            name = one("select full_name from variant where id=?", vid)[0]
            payload = json.dumps({"phase": phase, "method": "human-verified brochure read, page rendered and read", "pdf_path": f"knowledge_base/sources/oem/{path}",
                                  "pdf_sha1": sha1, "page": x["page"], "printed": x["printed"], "variant": name, "fields": {col: x["new"]}}, sort_keys=True)
            if not one("select count(*) from source_observation where source_id=? and resolved_variant_id=? and raw_payload=?", OEM_SOURCE_ID, vid, payload)[0]:
                oid = c.execute("insert into source_observation(source_id,raw_name,raw_payload,source_url,extraction_method,resolved_variant_id,resolution_status) values (?,?,?,?,?,?,'resolved')",
                                (OEM_SOURCE_ID, name, payload, "offline_brochure", method, vid)).lastrowid; n["obs"] += 1
                dec = "confirmed" if same(x["old"], x["new"]) else "accepted"
                c.execute("insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision,decision_reason) values (?,?,?,?,?,?)",
                          (vid, col, str(x["new"]), oid, dec, fp_reason)); n["fp"] += 1
            if quarantine_contradicted and not same(x["old"], x["new"]):
                # live provenance rows the brochure contradicts (10E/10F pattern); the rows themselves stay as evidence
                for fid, val in c.execute("select fp_id, accepted_value from v_live_evidence where variant_id=? and field_name=? and decision in ('accepted','confirmed')", (vid, col)).fetchall():
                    if not same(val, x["new"]):
                        c.execute("insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note) values ('field_provenance',?,NULL,'CONTRADICTED_BY_OEM_BROCHURE',?,?)",
                                  (fid, phase, f"fp_id={fid}; variant_id={vid}; field={col}; accepted_value={val}; contradicted by knowledge_base/sources/oem/{path} sha1 {sha1} p{x['page']}")); n["quar"] += 1
            if x.get("release"):
                # release == "*": any active quarantine on this cell, because the brochure now settles it
                any_reason = "" if x["release"] == "*" else " and reason_code=?"
                n["released"] += c.execute(f"update evidence_quarantine set released_at=datetime('now'), released_reason=? where target_table='variant' and target_id=? and target_field=?{any_reason} and released_at is null",
                                           (f"{phase}: verified from brochure {x['bro']} p{x['page']}", vid, col) + (() if x["release"] == "*" else (x["release"],))).rowcount
        # ================= invariants before COMMIT =================
        cellset = {(x["vid"], x["col"]) for x in cells}; vcols = [r[1] for r in c.execute("pragma table_info(variant)")]
        after = {t: snap(t) for t in tables}
        for t in tables:
            b, a = before[t], after[t]
            if t in ("evidence_amendment", "source_observation", "field_provenance"):
                assert set(b) <= set(a) and all(a[k] == b[k] for k in b), f"{t}: existing rows changed"
            elif t == "evidence_quarantine":
                assert set(b) <= set(a)
                assert all(a[k][1] == "field_provenance" and a[k][5] == phase for k in set(a) - set(b))
                for k in b:
                    if a[k] != b[k]:
                        assert a[k][:7] == b[k][:7] and b[k][8] is None, f"quarantine {k} changed unexpectedly"
                        assert (a[k][2], a[k][3]) in cellset
            elif t == "variant":
                assert set(a) == set(b)
                for k in b:
                    for j, col in enumerate(vcols):
                        if a[k][j] != b[k][j]: assert (k, col) in cellset, f"variant {k}.{col} changed"
            else:
                assert a == b, f"{t} changed"
        assert c.execute("select name, sql from sqlite_master where name not like 'sqlite_%' order by 1").fetchall() == schema, "schema changed"
        inherit = {(r[0], f) for r in c.execute("select id, base_variant_id from variant where base_variant_id is not null") for b, f in cellset if b == r[1]}
        for vid, row in ((r[0], r) for r in c.execute("select * from v_variant_canonical_q")):
            for j, col in enumerate(canon_cols):
                if row[j] != canon_before[vid][j]:
                    assert (vid, col) in cellset | inherit, f"canonical {vid}.{col} changed unexpectedly"
        for x in cells:
            assert same(one(f'select "{x["col"]}" from v_variant_canonical_q where id=?', x["vid"])[0], x["new"]), (x["vid"], x["col"])
        assert one("select count(*) from variant")[0] == 832
        assert one("pragma integrity_check")[0] == "ok"
        fk = c.execute("pragma foreign_key_check").fetchall()
        assert len(fk) == 297 and all(r[0] == "field_provenance" and r[2] == "source_observation" for r in fk), len(fk)
        if expect_counts and n["obs"]:
            assert n == expect_counts, f"counts {n} != {expect_counts}"
        c.execute("COMMIT"); print("COMMITTED;", json.dumps(n), "active", one("select count(*) from v_active_quarantine")[0])
    except Exception as ex:
        c.execute("ROLLBACK")
        import traceback; traceback.print_exc(); print("ROLLBACK:", repr(ex))
        raise SystemExit(1)
