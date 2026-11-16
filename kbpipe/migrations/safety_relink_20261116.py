"""Link six Bharat NCAP tests to models added to the KB on 2026-11-13 (owner-approved 2026-11-17).

The tests were ingested on 2026-09-23 as NO_MATCH because the models were not in the KB yet. This script re-resolves five of
them at MODEL_LEVEL and adds Safari to the Safari/Harrier family test. Punch (test 32) and Tekton (test 21) are left alone:
their stored variant lists do not establish the model-level link.

Usage: python -m kbpipe.migrations.safety_relink_20261116 <db path>
One transaction, idempotent, no DDL. Each resolution_status change is logged in evidence_amendment.
"""
import sqlite3
import sys

PHASE = "AUDIT_FIX_20261116"
REASON = "SAFETY_RERESOLVE_MODEL_ADDED"
JUST = "Model added to KB 2026-11-13; BNCAP title names it exactly (owner-approved re-resolve 2026-11-17)."
# (safety_test_id, manufacturer_id, model_id, expected model name, expected url fragment)
MODEL_LEVEL = [
    (10, 5, 78, "XEV 9e", "mahindra-xev-9e"),
    (26, 10, 85, "Curvv", "tata-curvv/"),
    (25, 10, 86, "Curvv EV", "tata-curvv-ev"),
    (27, 10, 87, "Harrier EV", "tata-harrier-ev"),
    (34, 10, 90, "Sierra", "tata-sierra"),
]
FAMILY = (33, 10, 89, "Safari", "tata-safari-harrier")


def run(path):
    c = sqlite3.connect(path, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    out = {"status_updates": 0, "rows_added": 0}
    c.execute("BEGIN IMMEDIATE")
    try:
        gen_used = c.execute("select count(*) from safety_test_applicability where generation_id is not null").fetchone()[0]
        for tid, man, mid, name, frag in MODEL_LEVEL + [FAMILY]:
            m = c.execute("select name, manufacturer_id from model where id=?", (mid,)).fetchone()
            t = c.execute("select resolution_status, raw_source_url, aop_stars, cop_stars from safety_test where id=?", (tid,)).fetchone()
            if not m or m[0] != name or m[1] != man:
                raise RuntimeError("model %s is not %s / manufacturer %s: %r" % (mid, name, man, m))
            if not t or frag not in (t[1] or "") or t[2] != 5 or t[3] != 5:
                raise RuntimeError("safety_test %s is not the expected 5/5 test for %s: %r" % (tid, name, t))
            level = "FAMILY_LEVEL" if tid == FAMILY[0] else "MODEL_LEVEL"
            if level == "MODEL_LEVEL" and t[0] != "RESOLVED":
                c.execute("insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase) "
                          "values('safety_test',?,?,?,?,?,?)", (tid, "resolution_status", t[0], "RESOLVED", REASON, PHASE))
                c.execute("update safety_test set resolution_status='RESOLVED', resolution_justification=? where id=?", (JUST, tid))
                out["status_updates"] += 1
            if level == "FAMILY_LEVEL" and t[0] != "RESOLVED":
                raise RuntimeError("family test %s is expected to be RESOLVED already" % tid)
            have = c.execute("select 1 from safety_test_applicability where safety_test_id=? and model_id=?", (tid, mid)).fetchone()
            if not have:
                gen = None
                if gen_used:
                    g = c.execute("select id from generation where model_id=?", (mid,)).fetchall()
                    gen = g[0][0] if len(g) == 1 else None
                note = ("BNCAP page explicitly covers Harrier AND Safari as one test (shared platform); Safari added to KB 2026-11-13."
                        if level == "FAMILY_LEVEL" else "Re-resolved after the model was added to the KB (2026-11-13).")
                c.execute("insert into safety_test_applicability(safety_test_id,manufacturer_id,model_id,generation_id,variant_id,"
                          "match_confidence,notes) values(?,?,?,?,NULL,?,?)", (tid, man, mid, gen, level, note))
                out["rows_added"] += 1
        fk = c.execute("select count(*) from pragma_foreign_key_check").fetchone()[0]
        if fk != 297:
            raise RuntimeError("foreign_key_check is %d, expected the known 297" % fk)
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        c.close()
        raise
    out["integrity_check"] = c.execute("pragma integrity_check").fetchone()[0]
    c.close()
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    print(run(sys.argv[1]))
