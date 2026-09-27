"""Build Phase 10B W2 (B1) quarantine entries from a DB copy. Read-only.
Rule (owner decision 2026-09-27, 'strict'): a B1 zero (accepted/new_field '0' from v3cars or 91wheels) is quarantined
unless another source's LIVE evidence (v_live_evidence) gives 0 for the same (variant, field), where
V3Cars (source 3) evidence never counts as corroboration in any decision and other B1 rows never count.
CONTRADICTED = another source's live evidence gives a non-zero value (V3Cars non-zero counts: keyword found)."""
import sqlite3, csv, sys, collections
db, out = sys.argv[1], sys.argv[2]
c = sqlite3.connect(f'file:{db}?mode=ro&immutable=1', uri=True)
zero = lambda v: str(v) in ('0', '0.0', 'False', 'false')
b1 = c.execute("""select fp.id, fp.variant_id, fp.field_name, so.source_id from field_provenance fp
  join source_observation so on so.id=fp.source_observation_id
  where fp.decision='accepted' and fp.accepted_value='0' and so.source_id in (2,3) order by fp.id""").fetchall()
b1ids = {r[0] for r in b1}
rows, cnt, cnt_design = [], collections.Counter(), collections.Counter()
for fid, vid, f, src in b1:
    ev = c.execute("select fp_id, source_id, accepted_value from v_live_evidence where variant_id=? and field_name=? and source_id<>? and fp_id<>?", (vid, f, src, fid)).fetchall()
    nz = any(v is not None and not zero(v) for _, s, v in ev)
    corr_strict = any(v is not None and zero(v) and s != 3 and i not in b1ids for i, s, v in ev)
    corr_design = any(v is not None and zero(v) and i not in b1ids for i, s, v in ev)
    cls = 'CONTRADICTED' if nz else ('CORROBORATED' if corr_strict else 'SOLE-SOURCE')
    cnt[cls] += 1; cnt_design['CONTRADICTED' if nz else ('CORROBORATED' if corr_design else 'SOLE-SOURCE')] += 1
    if cls == 'CORROBORATED': continue
    code = 'B1_ABSENT_AS_ZERO_CONTRADICTED' if cls == 'CONTRADICTED' else 'B1_ABSENT_AS_ZERO_SOLE'
    rows.append(('variant', vid, f, code, f"fp_id={fid}; zero_source={'v3cars' if src==3 else '91wheels'}; rule=strict_v3cars_never_corroborates"))
assert len({(r[1], r[2]) for r in rows}) == len(rows), 'duplicate cells'
w = csv.writer(open(out, 'w')); w.writerow(['target_table', 'target_id', 'target_field', 'reason_code', 'note']); w.writerows(rows)
print('strict:', dict(cnt), '| design rule:', dict(cnt_design), '| entries:', len(rows), collections.Counter(r[3] for r in rows))
