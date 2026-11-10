"""Assemble the frozen inputs for the cost check. Read-only on brochures and on the DB copy.

Usage: python -I build_inputs.py <db_copy> <enrich_scratch> <oem_root>
Writes <scratch>/costcheck/inputs/<key>/{page_text.txt, tile*.png, variants.txt, fields.txt, candidates.json}
and <scratch>/costcheck/inputs/manifest.json (DPI, tile boxes, sizes, SHA-1s).
PNGs are rendered with pypdfium2 from the PDF whose SHA-1 equals the one cited by the KB.
Page text and the candidate rows are exactly what round 2 used (prompts_r2/*.pagetext.txt, score_r2/rows.tsv).
"""
import csv, hashlib, json, os, shutil, sqlite3, sys
import pypdfium2

PAGES = {
    # key: (pdf sha1, page, pdf relpath, type, model_id lookup name, fields, round-2 call id)
    'syros_p7': dict(sha='7622f531b207ff69ab9ae6e3844653594356dced', page=7, rel='kia/syros/latest/brochures/kia_syros_brochure.pdf',
                     type='text-layer grid', model='Syros', call='018',
                     fields=['cruise_control', 'wireless_charging'],
                     # three horizontal tiles (pt, page is 1692 x 648), 20 pt overlap, 140 dpi
                     tiles=[dict(box=(0, 0, 580, 648), dpi=140), dict(box=(560, 0, 1140, 648), dpi=140), dict(box=(1120, 0, 1692, 648), dpi=140)]),
    'victoris_p16': dict(sha='94f94973736c150efdf2cc5ae6c40845d8e856a3', page=16, rel='maruti_suzuki/victoris/latest/brochures/maruti_suzuki_victoris_brochure.pdf',
                         type='OCR / scrambled-layer page', model='Victoris', call='021',
                         fields=['mileage_arai_kmpl', 'mileage_arai_km_per_kg', 'cruise_control', 'paddle_shifters'],
                         tiles=[dict(box=(0, 0, 595.28, 841.89), dpi=150)]),
    'venue_p20': dict(sha='00eabf1c73ad06d076b7e3928d9ca54d9b4cb1c4', page=20, rel='hyundai/venue/latest/brochures/hyundai_venue_brochure.pdf',
                      type='tick-icon grid', model='Venue', call='013',
                      fields=['cruise_control', 'paddle_shifters', 'wireless_charging'],
                      # tile1 = full page at 100 dpi; tile2 = header strip (y 85-125) stacked above the
                      # Comfort & Convenience block (y 700-1140), x 50-1030, at 115 dpi
                      tiles=[dict(box=(0, 0, 1080, 1332), dpi=100),
                             dict(stack=[(50, 85, 1030, 125), (50, 700, 1030, 1140)], dpi=115)]),
}


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def render(pg, box, dpi):
    s = dpi / 72
    im = pg.render(scale=s).to_pil()
    x0, y0, x1, y1 = box
    return im.crop((round(x0 * s), round(y0 * s), round(x1 * s), round(y1 * s)))


def main():
    dbp, scr, oem = sys.argv[1:4]
    out = f'{scr}/costcheck/inputs'; os.makedirs(out, exist_ok=True)
    db = sqlite3.connect(dbp)
    rows = list(csv.DictReader(open(f'{scr}/score_r2/rows.tsv'), delimiter='\t'))
    manifest = {}
    for key, c in PAGES.items():
        d = f'{out}/{key}'; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        pdf = f"{oem}/{c['rel']}"
        got = sha1(pdf); assert got == c['sha'], (key, got)
        pg = pypdfium2.PdfDocument(pdf)[c['page'] - 1]
        tiles = []
        for i, t in enumerate(c['tiles'], 1):
            if 'stack' in t:
                parts = [render(pg, b, t['dpi']) for b in t['stack']]
                from PIL import Image
                w = max(p.width for p in parts); h = sum(p.height for p in parts)
                im = Image.new('RGB', (w, h), 'white'); y = 0
                for p in parts:
                    im.paste(p, (0, y)); y += p.height
            else:
                im = render(pg, t['box'], t['dpi'])
            im.convert('RGB').save(f'{d}/tile{i}.png')
            tiles.append(dict(file=f'tile{i}.png', dpi=t['dpi'], px=list(im.size), **{k: v for k, v in t.items() if k != 'dpi'}))
        shutil.copy(f"{scr}/prompts_r2/{c['sha']}_p{c['page']}.pagetext.txt", f'{d}/page_text.txt')
        mid = db.execute('select id from model where name=?', (c['model'],)).fetchone()[0]
        base = db.execute('select id, name from variant where model_id=? and base_variant_id is null order by id', (mid,)).fetchall()
        open(f'{d}/variants.txt', 'w').write('\n'.join(n for _, n in base) + '\n')
        open(f'{d}/fields.txt', 'w').write('\n'.join(c['fields']) + '\n')
        names = dict(base)
        cands = []
        for r in rows:
            if r['page'] != f"{c['sha']}_p{c['page']}":
                continue
            ids = [int(x) for x in r['mapped_variants'].split()] if r['mapped_variants'] else []
            cands.append(dict(id=r['row_id'], trim_label=r['segment'], label_source=r['label_source'], header_quote=r['header_quote'],
                              mapped_variants=[names[i] for i in ids if i in names], field=r['field'], value=r['value'],
                              unit=r['unit'], qualifier=r['qualifier'], value_quote=r['value_quote']))
        json.dump(cands, open(f'{d}/candidates.json', 'w'), indent=1, ensure_ascii=False)
        manifest[key] = dict(type=c['type'], pdf_sha1=got, page=c['page'], flash_call=c['call'], fields=c['fields'],
                             variants=len(base), candidates=len(cands), tiles=tiles,
                             page_text_sha1=sha1(f'{d}/page_text.txt'), candidates_sha1=sha1(f'{d}/candidates.json'))
        print(key, manifest[key]['type'], 'variants', len(base), 'candidates', len(cands), [t['px'] for t in tiles])
    json.dump(manifest, open(f'{out}/manifest.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
