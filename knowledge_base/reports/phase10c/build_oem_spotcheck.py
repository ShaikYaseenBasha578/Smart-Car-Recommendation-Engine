"""Build the Phase 10C-1 OEM spot-check sheet. Read-only; run against a /tmp COPY of production only.
Usage: python3 build_oem_spotcheck.py <db_copy_path> <out_csv>
Sample (seed 20260928): all rejected + all accepted OEM provenance rows, plus 20 confirmed rows chosen by
round-robin over models (model order and within-model order shuffled with the seed)."""
import sqlite3, csv, json, random, sys, collections
SEED, N_CONFIRMED = 20260928, 20
db, out = sys.argv[1], sys.argv[2]
c = sqlite3.connect(f'file:{db}?mode=ro&immutable=1', uri=True)
manifest = {e['model_id']: e['artifact_path'] for e in json.load(open('knowledge_base/sources/oem/brochure_manifest.json')).values()}
rows = c.execute("""select fp.id, so.id, mf.name||' '||m.name, m.id, v.id, v.name, so.raw_name, fp.field_name, fp.accepted_value, fp.decision
  from field_provenance fp join source_observation so on so.id=fp.source_observation_id
  join variant v on v.id=fp.variant_id join model m on m.id=v.model_id join manufacturer mf on mf.id=m.manufacturer_id
  where so.source_id=6 and so.source_url='offline_brochure' order by fp.id""").fetchall()
by = collections.defaultdict(list)
for r in rows: by[r[9]].append(r)
assert len(by['rejected']) == 28 and len(by['accepted']) == 1, {k: len(v) for k, v in by.items()}
rng = random.Random(SEED)
per_model = collections.defaultdict(list)
for r in by['confirmed']: per_model[r[2]].append(r)
models = sorted(per_model); rng.shuffle(models)
for m in models: rng.shuffle(per_model[m])
picked, i = [], 0
while len(picked) < N_CONFIRMED:
    m = models[i % len(models)]
    if per_model[m]: picked.append(per_model[m].pop(0))
    i += 1
assert len({r[2] for r in picked}) >= 8
sample = [('REJECTED_WOULD_FLIP', r) for r in by['rejected']] + [('CONFIRMED_SAMPLED', r) for r in sorted(picked)] + [('ACCEPTED', r) for r in by['accepted']]
cols = [r[1] for r in c.execute('pragma table_info(variant)')]
with open(out, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['stratum', 'provenance_id', 'observation_id', 'model', 'variant_id', 'variant_name', 'observation_raw_name', 'field',
                'extracted_value', 'current_canonical_value', 'decision', 'pdf_path', 'page_numbers', 'true_value', 'verdict', 'notes'])
    for stratum, (fid, oid, model, mid, vid, vname, raw, field, val, dec) in sample:
        canon = c.execute(f'select "{field}" from variant where id=?', (vid,)).fetchone()[0] if field in cols else None
        w.writerow([stratum, fid, oid, model, vid, vname, raw, field, val, canon, dec, manifest.get(mid, ''), '', '', '', ''])
print(len(sample), collections.Counter(s for s, _ in sample), 'confirmed models:', collections.Counter(r[2] for r in picked))
print('distinct PDFs:', len({manifest.get(r[3], '') for _, r in sample}))
