"""Phase 10C-2 offline evaluation: re-resolve every resolved CarWale observation with the NEW resolver path
(resolve_carwale_version) against a read-only /tmp COPY of production. Writes nothing to any DB.
Usage: python3 eval_carwale_reresolution.py <db_copy_path> <out_csv>
'Contradiction' is judged by an independent token check on the raw name (the same heuristic Phase 10A used),
not by the new parser, so the fix is not graded by its own logic. Price is not passed (not stored in payloads)."""
import sqlite3, csv, re, sys, collections
from knowledge_base.ingestion.carwale.ingest_carwale import resolve_carwale_version
from knowledge_base.ingestion.carwale.field_map_carwale import parse_version_name
db, out = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(f'file:{db}?mode=ro&immutable=1', uri=True); conn.row_factory = sqlite3.Row

def fuel10a(s):
    s = s.lower()
    for k, v in [('cng', 'CNG'), ('diesel', 'Diesel'), ('kwh', 'Electric'), ('electric', 'Electric'), ('hybrid', 'Hybrid'), ('petrol', 'Petrol')]:
        if k in s: return v
def tx10a(s):
    s = ' ' + s.lower() + ' '
    if any(k in s for k in ['automatic', 'amt', 'dct', 'cvt', 'ivt', ' at ', '(tc)', 'e-cvt']): return 'A'
    if 'manual' in s or ' mt' in s: return 'M'
def contradicts(raw, vid):
    if vid is None: return False
    t, f = conn.execute('select v.transmission, p.fuel_type from variant v join powertrain p on p.id=v.powertrain_id where v.id=?', (vid,)).fetchone()
    rf, rt = fuel10a(raw), tx10a(raw)
    vf = 'Hybrid' if 'Hybrid' in f else ('CNG' if 'CNG' in f else f.split()[0]); vt = 'M' if t in ('Manual', 'iMT') else 'A'
    bad_f = rf and rf != vf and not (rf == 'Petrol' and vf in ('Hybrid', 'CNG')) and not (rf == 'Hybrid' and vf == 'Petrol')
    bad_t = rt and rt != vt and t != 'iMT'
    return bool(bad_f or bad_t)

flagged = {r[0] for r in conn.execute("select target_id from evidence_quarantine where released_at is null and target_table='source_observation' and reason_code='B3_CARWALE_STRUCTURAL_MISMATCH'")}
rows = conn.execute("""select so.id, so.raw_name, so.source_url, so.resolved_variant_id, mf.name, m.name
  from source_observation so join variant v on v.id=so.resolved_variant_id join model m on m.id=v.model_id
  join manufacturer mf on mf.id=m.manufacturer_id where so.source_id=4 and so.resolution_status='resolved' order by so.id""").fetchall()
res, tab = [], collections.Counter()
for oid, raw, url, old_vid, make, model in rows:
    slug = url.rstrip('/').split('/')[-1]
    new_vid, status, base = resolve_carwale_version(conn, make.lower().replace(' ', '-'), model.lower().replace(' ', '-'), raw, slug)
    pf, pt = parse_version_name(raw)
    if new_vid is None: outcome = 'EDITION_CANDIDATE' if status == 'edition_candidate' else 'UNRESOLVED'
    elif new_vid == old_vid: outcome = 'SAME'
    else: outcome = 'DIFFERENT'
    grp = 'FLAGGED' if oid in flagged else 'UNFLAGGED'
    still = contradicts(raw, new_vid)
    old_contra = contradicts(raw, old_vid)
    tab[(grp, outcome)] += 1
    if still: tab[(grp, 'STILL_CONTRADICTING')] += 1
    res.append([oid, grp, raw, old_vid, new_vid if new_vid else '', status, base or '', outcome, pf or '', pt or '', int(old_contra), int(still)])
with open(out, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['observation_id', 'group', 'raw_name', 'old_variant_id', 'new_variant_id', 'new_status', 'edition_base_variant_id',
                'outcome', 'parsed_fuel', 'parsed_transmission', 'old_contradicts', 'new_contradicts'])
    w.writerows(res)
for g in ('FLAGGED', 'UNFLAGGED'):
    print(g, {k[1]: v for k, v in sorted(tab.items()) if k[0] == g})
print('total', len(res), 'flagged', sum(1 for r in res if r[1] == 'FLAGGED'))
