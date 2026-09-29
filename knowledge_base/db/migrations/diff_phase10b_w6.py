"""Phase 10B W6 diff: exact EXCEPT diff, both directions, of every table (and sqlite_master) between a backup and a
post-W6 DB, cell-level for `variant` and `v_variant_canonical_q`,
plus EXCEPT diffs of v_live_evidence, v_corroboration, v_observation_status and v_safety_applicability_q. Read-only on both
(after.db opened mode=ro, backup ATTACHed mode=ro).
Usage: python3 diff_phase10b_w6.py <backup.db> <after.db>   -> prints a deterministic report (diff it across runs)."""
import sqlite3
import sys

bk, af = sys.argv[1], sys.argv[2]
c = sqlite3.connect(f"file:{af}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS b", (f"file:{bk}?mode=ro",))
out = []
sm = {db: f"select type,name,tbl_name,sql from {db}.sqlite_master" for db in ("main", "b")}
out.append(f"schema: +{len(c.execute(sm['main'] + ' except ' + sm['b']).fetchall())} "
           f"-{len(c.execute(sm['b'] + ' except ' + sm['main']).fetchall())}")
tables = [r[0] for r in c.execute("select name from main.sqlite_master where type='table' order by name")]
for t in tables:
    plus = c.execute(f'select * from main."{t}" except select * from b."{t}"').fetchall()
    minus = c.execute(f'select * from b."{t}" except select * from main."{t}"').fetchall()
    out.append(f"table {t}: +{len(plus)} -{len(minus)}")
    if t == "sqlite_sequence":
        out += [f"  + {r}" for r in sorted(plus)] + [f"  - {r}" for r in sorted(minus)]
    if t == "evidence_amendment":
        out += [f"  + {r[:8]}" for r in sorted(plus)]
    if t == "evidence_quarantine":
        out += [f"  + {r[:6]}" for r in sorted(plus)]


def cells(rel):
    cols = [d[0] for d in c.execute(f"select * from main.{rel} limit 0").description]
    a = {r[0]: r for r in c.execute(f"select * from main.{rel}")}
    b = {r[0]: r for r in c.execute(f"select * from b.{rel}")}
    assert set(a) == set(b), f"{rel}: id sets differ"
    diff = sorted((k, cols[j], b[k][j], a[k][j]) for k in a for j in range(len(cols))
                  if a[k][j] != b[k][j] or type(a[k][j]) is not type(b[k][j]))
    return diff


for rel in ("variant", "v_variant_canonical_q"):
    d = cells(rel)
    out.append(f"{rel} cells changed: {len(d)} across {len({x[0] for x in d})} rows; columns {sorted({x[1] for x in d})}")
    out += [f"  {k}.{col}: {old!r} -> {new!r}" for k, col, old, new in d]
for v in ("v_live_evidence", "v_corroboration", "v_observation_status", "v_safety_applicability_q"):
    plus = c.execute(f"select * from main.{v} except select * from b.{v}").fetchall()
    minus = c.execute(f"select * from b.{v} except select * from main.{v}").fetchall()
    out.append(f"view {v}: +{len(plus)} -{len(minus)}")
    if v == "v_corroboration":
        out += [f"  + {r}" for r in sorted(plus)] + [f"  - {r}" for r in sorted(minus)]
print("\n".join(out))
