"""Build gold.tsv from brochure-cited OEM observations (phases 10E–10N) on a byte copy of prod.

Usage: python -I make_gold.py <db_copy> <index_dir> <out_gold.tsv>
Each gold cell: an OEM observation (source_id 6, extraction_method manual_brochure_10*) whose
payload cites pdf_path + page + pdf_sha1, and whose value equals the current canonical value
in v_variant_canonical_q (brochure confirmed or corrected). Selection is fixed below (by
observation id) so the set is reproducible. Gemini never sees this file.
"""
import csv, json, sqlite3, sys

# obs ids: the first 40 are round 1 (PILOT_REPORT.md §3), unchanged; then the round-2 additions
SELECT = [
    # Ertiga p7 (image-only -> OCR): mileage km/l + CNG km/kg
    3864, 3918, 3919, 3920, 3921, 3759, 3922,
    # Victoris p16 (scrambled text layer -> OCR): km/l, km/kg, cruise, paddle
    3923, 3929, 3934, 3936, 3760, 4027, 4028, 4030, 3899, 3768, 3769,
    # Dzire p5 (scrambled -> OCR): km/l, km/kg
    3863, 3912, 3914, 3916,
    # Kia Syros p7 (clean text): cruise, wireless
    4035, 3883, 4037, 4041, 4034, 4044, 4047, 4050,
    # Tata Altroz p22 (clean text): cruise, wireless
    3981, 3985, 3994, 3980, 3998, 4023, 4024, 4026, 4002, 4008,
    # ---- round 2 additions (40) ----
    # Victoris p16 matrix cruise (+3), Syros p7 (+2)
    3900, 4029, 4031, 4040, 4051,
    # Hyundai Venue p20 (scrambled -> OCR, matrix): paddle, cruise, wireless
    3767, 3889, 3890, 3958, 3959, 3961, 3963, 3964, 3967,
    # VW Taigun p10 (scrambled -> OCR, matrix): paddle, cruise
    3770, 3865, 3867, 3968, 3970, 3971,
    # Hyundai Creta p14 (scrambled -> OCR, matrix): paddle
    3762, 3763, 3765,
    # Honda City p13 (text): km/l
    3906, 3907, 3909, 3910,
    # Honda Amaze p27 (text): km/l
    3862, 3903, 3905,
    # Tata Harrier p18 (text, cumulative list): cruise
    3876, 3878, 3879, 3941, 3944,
    # Tata Harrier p19 (text, cumulative list): wireless
    3945, 3949, 3952, 3953, 3955,
]
# Layout of the evidence for each (pdf, page, field), judged by reading the page text before any
# round-2 call. matrix = trims are column headers of a feature/spec grid; list = cumulative
# "features in addition to" trim lists; spec = model-level spec block or caption (gearbox/fuel
# labels, trims in a caption). Only 'matrix' counts as matrix in the split metrics.
LAYOUT = {
    ('maruti_suzuki_ertiga_brochure.pdf', 7): {'*': 'spec'},
    ('maruti_suzuki_victoris_brochure.pdf', 16): {'mileage_arai_kmpl': 'spec', 'mileage_arai_km_per_kg': 'spec',
                                                  'cruise_control': 'matrix', 'paddle_shifters': 'matrix'},
    ('maruti_suzuki_dzire_brochure.pdf', 5): {'*': 'spec'},
    ('kia_syros_brochure.pdf', 7): {'*': 'list'},
    ('tata_altroz_brochure.pdf', 22): {'*': 'list'},
    ('hyundai_venue_brochure.pdf', 20): {'*': 'matrix'},
    ('volkswagen_taigun_brochure.pdf', 10): {'*': 'matrix'},
    ('Hyundai_Creta_Brochure_Official.pdf', 14): {'*': 'matrix'},
    ('honda_city_brochure.pdf', 13): {'*': 'spec'},
    ('honda_amaze_brochure.pdf', 27): {'*': 'spec'},
    ('tata_harrier_brochure.pdf', 18): {'*': 'list'},
    ('tata_harrier_brochure.pdf', 19): {'*': 'list'},
}


def layout_of(pdf, page, field):
    L = LAYOUT[(pdf, int(page))]
    return L.get(field, L.get('*'))
FIELDS = {'mileage_arai_kmpl': 'km/l', 'mileage_arai_km_per_kg': 'km/kg',
          'cruise_control': 'bool', 'wireless_charging': 'bool', 'paddle_shifters': 'bool'}


def main():
    db = sqlite3.connect(sys.argv[1]); index_dir = sys.argv[2]
    methods = {}
    for r in csv.DictReader(open(f'{index_dir}/index.tsv'), delimiter='\t'):
        methods[(r['pdf_sha1'], int(r['page']))] = r['method']
    cols = [r[1] for r in db.execute('pragma table_info(v_variant_canonical_q)')]
    out = []
    for oid in SELECT:
        vid, meth, pl = db.execute('select resolved_variant_id, extraction_method, raw_payload from source_observation '
                                   'where id=? and source_id=6', (oid,)).fetchone()
        p = json.loads(pl)
        (field, val), = [(f, v) for f, v in p['fields'].items() if f in FIELDS]
        d = dict(zip(cols, db.execute('select * from v_variant_canonical_q where id=?', (vid,)).fetchone()))
        assert d[field] is not None and float(d[field]) == float(val), (oid, field, val, d[field])
        fuel = db.execute('select fuel_type from powertrain where id=?', (d['powertrain_id'],)).fetchone()[0]
        model = db.execute('select m.name from model m where m.id=?', (d['model_id'],)).fetchone()[0]
        m = methods[(p['pdf_sha1'], p['page'])]
        out.append(dict(gold_id=f'G{len(out)+1:02d}', model=model, model_id=d['model_id'], variant_id=vid,
                        variant_name=d['name'], transmission=d['transmission'], fuel=fuel, field=field,
                        value=val, unit=FIELDS[field], pdf=p['pdf_path'].split('/')[-1], pdf_sha1=p['pdf_sha1'],
                        page=p['page'], page_method=m, prompt_source='ocr' if m != 'text' else 'text',
                        layout=layout_of(p['pdf_path'].split('/')[-1], p['page'], field),
                        obs_id=oid, phase=meth[-3:], printed=str(p.get('printed', '')).replace('\t', ' ')))
    w = csv.DictWriter(open(sys.argv[3], 'w'), fieldnames=list(out[0]), delimiter='\t')
    w.writeheader(); w.writerows(out)
    print(len(out), 'gold cells', file=sys.stderr)


if __name__ == '__main__':
    main()
