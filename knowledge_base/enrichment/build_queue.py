"""Work queue for the Claude-only enrichment loop. Read-only on a prod COPY.

Usage: python -I build_queue.py <db_copy> <pdfs.tsv> <out_dir>
  pdfs.tsv: "<sha1>\t<relpath under sources/oem>" per brochure
Writes <out_dir>/queue.json and <out_dir>/RUN_STATE.md.

Queue cell = (base variant, in-scope field) whose canonical value is NULL, masked by an active quarantine, or present
with no OEM_BROCHURE_VERIFIED provenance. Editions (P8) are skipped. Models with a catalogue-currency hold (P7) are listed
as held, not queued. Applicability: km/l is for non-CNG non-electric variants, km/kg for CNG variants only.
"""
import json, os, sqlite3, sys
from collections import defaultdict

FIELDS = ['mileage_arai_kmpl', 'mileage_arai_km_per_kg', 'cruise_control', 'wireless_charging',
          'heads_up_display', 'ventilated_front_seats', 'paddle_shifters', 'fuel_tank_litres', 'drive_modes']
# brochure folder (make/model) -> KB model id. Alternates are listed in BROCHURE_PICK.
FOLDER_MODEL = {
    'honda/amaze': 19, 'honda/city': 20, 'honda/elevate': 50, 'hyundai/aura': 17, 'hyundai/creta': 1, 'hyundai/exter': 51,
    'hyundai/grand_i10_nios': 16, 'hyundai/venue': 8, 'hyundai/verna': 18, 'kia/carens_clavis': 61, 'kia/carens_clavis_ev': 62,
    'kia/seltos': 9, 'kia/syros': 60, 'mahindra/bolero': 26, 'mahindra/scorpio_classic': 27, 'mahindra/scorpio_n': 28,
    'mahindra/thar': 53, 'mahindra/thar_roxx': 54, 'mahindra/xuv_3xo': 2, 'mahindra/xuv_7xo': 29,
    'maruti_suzuki/alto_k10': 37, 'maruti_suzuki/baleno': 15, 'maruti_suzuki/brezza': 7, 'maruti_suzuki/dzire': 13,
    'maruti_suzuki/e_vitara': 45, 'maruti_suzuki/eeco': 14, 'maruti_suzuki/ertiga': 10, 'maruti_suzuki/fronx': 35,
    'maruti_suzuki/grand_vitara': 39, 'maruti_suzuki/jimny': 44, 'maruti_suzuki/s_presso': 36, 'maruti_suzuki/swift': 3,
    'maruti_suzuki/victoris': 40, 'maruti_suzuki/wagon_r': 12, 'maruti_suzuki/xl6': 11, 'mg/hector': 31, 'mg/windsor_ev': 4,
    'nissan/gravite': 57, 'nissan/magnite': 56, 'renault/duster': 55, 'renault/triber': 32, 'skoda/kushaq': 46,
    'skoda/kylaq': 52, 'skoda/slavia': 47, 'tata/altroz': 23, 'tata/harrier': 30, 'tata/nexon': 5, 'tata/nexon_ev': 6,
    'tata/punch_ev': 59, 'tata/tiago': 24, 'tata/tiago_ev': 58, 'tata/tigor': 25, 'tata_motors/nexon': 5,
    'toyota/fortuner': 22, 'toyota/glanza': 33, 'toyota/hilux': 42, 'toyota/innova_crysta': 21, 'toyota/innova_hycross': 41,
    'toyota/rumion': 43, 'toyota/urban_cruiser_hyryder': 38, 'toyota/urban_cruiser_taisor': 34,
    'volkswagen/taigun': 48, 'volkswagen/virtus': 49,
}
# Catalogue-currency holds (CLAUDE.md: Baleno, Brezza, Kylaq Sportline, WagonR 1.0 rows, Jimny "PRO" naming, Seltos)
P7_HOLD = {15: 'Baleno catalogue currency (10D audit)', 7: 'Brezza catalogue currency (10D audit)',
           52: 'Kylaq Sportline catalogue currency (10D audit)', 12: 'WagonR 1.0 rows predate the brochure (10F)',
           44: 'Jimny rows are named "PRO"; naming/currency unresolved (10H obs 3302)',
           9: 'Seltos: the brochure prints trims the KB lacks (GTX(O), X-Line(O)) and wireless charging sits under an optional-pack header (owner decision 2026-11-12, NEEDS_YOU N11)'}


def main():
    dbp, pdfs, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    db = sqlite3.connect(dbp)
    canon_cols = {r[1] for r in db.execute('pragma table_info(variant)')}
    verified = defaultdict(set)   # variant -> fields with brochure-verified provenance
    for v, f in db.execute("select variant_id, field_name from field_provenance where decision_reason like 'OEM_BROCHURE_VERIFIED%' and decision in ('accepted','confirmed')"):
        verified[v].add(f)
    q = defaultdict(set)          # variant -> fields with an active cell quarantine
    for t, f in db.execute("select target_id, target_field from evidence_quarantine where released_at is null and target_table='variant'"):
        q[t].add(f)
    canon = {r[0]: r for r in db.execute('select * from v_variant_canonical_q')}
    cc = [d[0] for d in db.execute('select * from v_variant_canonical_q limit 0').description]
    stored = {}
    for r in db.execute(f"select id, {', '.join(FIELDS)} from variant"):
        stored[r[0]] = dict(zip(FIELDS, r[1:]))
    models = defaultdict(lambda: dict(variants=[], cells=defaultdict(list)))
    for vid, mid, name, trans, fuel in db.execute("""select v.id, v.model_id, v.name, v.transmission, p.fuel_type from variant v
            left join powertrain p on p.id=v.powertrain_id where v.base_variant_id is null order by v.id"""):
        m = models[mid]; m['variants'].append((vid, name, trans, fuel))
        for f in FIELDS:
            if f == 'mileage_arai_kmpl' and fuel in ('CNG', 'Electric'): continue
            if f == 'mileage_arai_km_per_kg' and fuel != 'CNG': continue
            if f == 'fuel_tank_litres' and fuel == 'Electric': continue
            cv = canon[vid][cc.index(f)]
            if f in verified[vid]: continue
            if f in q[vid] or '*' in q[vid]:
                st = 'QUARANTINED' if stored[vid][f] is not None else 'QUARANTINED_NULL'
            elif cv is None: st = 'NULL'
            else: st = 'UNVERIFIED'
            m['cells'][f].append((vid, st))
    brochures = defaultdict(list)
    for l in open(pdfs):
        sha, rel = l.rstrip('\n').split('\t')
        key = '/'.join(rel.split('/')[:2])
        brochures[FOLDER_MODEL[key]].append((sha, rel))
    mname = dict(db.execute('select id, name from model'))
    queue, held = [], []
    for mid, m in models.items():
        n = sum(len(v) for v in m['cells'].values())
        row = dict(model_id=mid, model=mname[mid], base_variants=len(m['variants']), queued=n,
                   by_field={f: len(v) for f, v in m['cells'].items()},
                   by_status={s: sum(1 for v in m['cells'].values() for _, st in v if st == s) for s in ('NULL', 'QUARANTINED', 'QUARANTINED_NULL', 'UNVERIFIED')},
                   brochures=brochures.get(mid, []))
        if mid in P7_HOLD: row['hold'] = P7_HOLD[mid]; held.append(row)
        elif not row['brochures']: row['hold'] = 'no brochure on disk (P9)'; held.append(row)
        else: queue.append(row)
    queue.sort(key=lambda r: (r['model'] != 'Syros', -r['queued']))
    json.dump(dict(queue=queue, held=held), open(f'{out}/queue.json', 'w'), indent=1)
    with open(f'{out}/RUN_STATE.md', 'w') as f:
        f.write('# RUN_STATE (continue the enrichment loop from here)\n\n')
        f.write(f'Queue built from prod copy. Brochure batches in order; status column is updated after each batch.\n\n')
        f.write('| # | model | base variants | queued cells | NULL | QUARANTINED | UNVERIFIED | status |\n|---|---|---|---|---|---|---|---|\n')
        for i, r in enumerate(queue, 1):
            s = r['by_status']
            f.write(f"| {i} | {r['model']} | {r['base_variants']} | {r['queued']} | {s['NULL'] + s['QUARANTINED_NULL']} | {s['QUARANTINED']} | {s['UNVERIFIED']} | pending |\n")
        f.write('\n## Held (not queued)\n')
        for r in held:
            f.write(f"- {r['model']} ({r['queued']} cells): {r['hold']}\n")
        f.write(f"\nTotals: queued {sum(r['queued'] for r in queue)} cells in {len(queue)} brochure batches; held {sum(r['queued'] for r in held)}.\n")


if __name__ == '__main__':
    main()
