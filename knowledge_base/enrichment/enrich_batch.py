"""One enrichment batch = one brochure. Read-only on brochures and on a prod COPY.

  prep     <batch_dir> <db_copy> <index_dir> <oem_root> <model_id> <pdf_rel> <page> [<page> ...]
  run      <batch_dir> [a|b]                run a: every variant/field of the page; run b (after classify): ONLY the validated pairs, blind
  classify <batch_dir> <db_copy>            deterministic comparison with the KB -> classified.tsv, summary.json; picks the validation pairs
                                            (every CORRECTION + stratified >=20% of FILLs, min 10) and writes the run-b folders; re-run after run b to merge it

Extraction prompt = costcheck common + GLOSSARY.md + costcheck EXTRACT + output schema (plus "page_columns").
Each run: its own folder holding only that page's inputs; Read tool only, confined to that folder, Sonnet, no MCP,
no session persistence. Run b never sees run a's folder or output.
Page tiling: 140 dpi, tiles at most 580 x 650 pt with 20 pt overlap (the cost-check Syros tiling, generalised).
Classification: FILL (KB cell empty/masked-empty), CONFIRM (same value), CORRECTION (different value), NOT_ON_PAGE,
CONFLICT (cell already brochure-verified and the new value differs: never written),
ABSENT_NOT_SHOWN (a 0 for a field the page never shows fitted on any trim and with no explicit absence marker: never written).
"""
import hashlib, json, math, os, random, re, sqlite3, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = ['mileage_arai_kmpl', 'mileage_arai_km_per_kg', 'cruise_control', 'wireless_charging',
          'heads_up_display', 'ventilated_front_seats', 'paddle_shifters']
UNIT = {'mileage_arai_kmpl': 'km/l', 'mileage_arai_km_per_kg': 'km/kg'}
DPI, TW, TH, OV = 140, 580, 650, 20
FLAGS = ['--model', 'sonnet', '--output-format', 'json', '--restricted', '--tools', 'Read', '--strict-mcp-config',
         '--disable-slash-commands', '--setting-sources', '', '--no-session-persistence', '--permission-mode', 'dontAsk',
         '--permission-prompts', 'none', '--max-budget-usd', '2']

COMMON = """You are working in a folder that contains only the files for this task. Use ONLY the Read tool, and read ONLY files in this folder (no shell, no writes, no web). Files:
- page_text.txt: text extracted from one car-brochure page (may be scrambled, incomplete or lack tick marks);
- tile1.png, tile2.png, ...: rendered images of the same page (read every tile that exists; the image is the authority when text and image differ);
- variants.txt: the catalogue's variant names for this car model, one per line;
- variant_info.tsv: for each variant in variants.txt, its fuel and gearbox from the catalogue (use them to apply gearbox and fuel qualifiers);
- fields.txt: the fields to extract, one per line.
FIELD GLOSSARY (authoritative; follow it exactly)
"""
TASK = """TASK
Read the page image(s) and text. For every variant and every listed field, report the value printed for it, with unit, qualifier, and the exact header/line it comes from. If the page doesn't say, write NOT_ON_PAGE.
"""
OUTPUT = """OUTPUT (reply with ONE JSON object and nothing else, no markdown fences):
{"page_columns":["<every trim/variant column or row header the page's feature or spec table prints, as printed>"],
 "cells":[{"variant":"<name exactly as in variants.txt>","field":"<field>","value":<number or null>,"unit":"<km/l|km/kg|bool>","qualifier":"<restriction printed with the value or its header, e.g. '6AT', 'DCT/AT only', '1.5 Diesel only', or ''>","source":"<the exact header or line the value comes from>","status":"FOUND|NOT_ON_PAGE"}]}
Rules for "cells":
- Give one cell for each catalogue variant and each listed field, except: mileage_arai_kmpl is for non-CNG, non-electric variants only; mileage_arai_km_per_kg is for CNG variants only.
- Features: value 1 if the page shows the feature fitted on that variant, 0 if shown absent. Apply restrictions: a feature marked "AT only" / "DCT/AT only" is 0 on manual variants and 1 (with the qualifier) on matching automatic variants; a feature restricted to certain engines is 1 only on those.
- Mileage: the figure printed for that variant's gearbox/fuel; put gearbox or fuel restrictions in "qualifier".
- If the page does not say, use value null and status NOT_ON_PAGE. Never guess.
- Give "source" and "qualifier" only for cells with a value. For NOT_ON_PAGE cells use "source":"" and "qualifier":"".
"""

COMMON_B = """You are working in a folder that contains only the files for this task. Use ONLY the Read tool, and read ONLY files in this folder (no shell, no writes, no web). Files:
- page_text.txt: text extracted from one car-brochure page (may be scrambled, incomplete or lack tick marks);
- tile1.png, tile2.png, ...: rendered images of the same page (read every tile that exists; the image is the authority when text and image differ);
- pairs.tsv: the variant/field pairs to answer, with each variant's fuel and gearbox from the catalogue (use them to apply gearbox and fuel qualifiers).
FIELD GLOSSARY (authoritative; follow it exactly)
"""
TASK_B = """TASK
Answer ONLY the variant/field pairs listed in pairs.tsv, nothing else. For each pair report the value printed for it, with unit, qualifier, and the exact header/line it comes from. If the page doesn't say, write NOT_ON_PAGE.
"""
OUTPUT_B = """OUTPUT (reply with ONE JSON object and nothing else, no markdown fences):
{"cells":[{"variant":"<name exactly as in pairs.tsv>","field":"<field>","value":<number or null>,"unit":"<km/l|km/kg|bool>","qualifier":"<restriction printed with the value or its header, or ''>","source":"<the exact header or line the value comes from>","status":"FOUND|NOT_ON_PAGE"}]}
Rules for "cells":
- Give exactly one cell for each pair in pairs.tsv, in any order.
- Features: value 1 if the page shows the feature fitted on that variant, 0 if shown absent. Apply restrictions: a feature marked "AT only" / "DCT/AT only" is 0 on manual variants and 1 (with the qualifier) on matching automatic variants; a feature restricted to certain engines is 1 only on those.
- Mileage: the figure printed for that variant's gearbox/fuel; put gearbox or fuel restrictions in "qualifier".
- If the page does not say, use value null and status NOT_ON_PAGE. Never guess.
- Give "source" and "qualifier" only for cells with a value. For NOT_ON_PAGE cells use "source":"" and "qualifier":"".
"""


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def build_prompt():
    return COMMON + open(f'{HERE}/GLOSSARY.md').read() + '\n' + TASK + OUTPUT


def tiles_for(w, h):
    xs = list(range(0, max(1, int(w)), TW - OV)) if w > TW else [0]
    ys = list(range(0, max(1, int(h)), TH - OV)) if h > TH else [0]
    boxes = []
    for y in ys:
        if y and y + OV >= h: continue
        for x in xs:
            if x and x + OV >= w: continue
            boxes.append((x, y, min(x + TW, w), min(y + TH, h)))
    return boxes


def prep(a):
    import pypdfium2
    bd, dbp, idx, oem, mid, rel = a[0], a[1], a[2], a[3], int(a[4]), a[5]
    pages = [int(x) for x in a[6:]]
    pdf = f'{oem}/{rel}'; sha = sha1(pdf)
    doc = pypdfium2.PdfDocument(pdf)
    db = sqlite3.connect(dbp)
    vs = db.execute("""select v.name, p.fuel_type, v.transmission from variant v left join powertrain p on p.id=v.powertrain_id
                       where v.model_id=? and v.base_variant_id is null order by v.id""", (mid,)).fetchall()
    fields = [f for f in FIELDS if not (f == 'mileage_arai_km_per_kg' and not any(x[1] == 'CNG' for x in vs))
              and not (f == 'mileage_arai_kmpl' and not any(x[1] not in ('CNG', 'Electric') for x in vs))]
    man = dict(pdf=rel, pdf_sha1=sha, model_id=mid, dpi=DPI, pdf_meta={k: str(v)[:60] for k, v in doc.get_metadata_dict().items()
                                                                          if k in ('CreationDate', 'ModDate', 'Title', 'Producer')},
               prompt_sha1=hashlib.sha1(build_prompt().encode()).hexdigest(), pages={})
    os.makedirs(bd, exist_ok=True)
    open(f'{bd}/prompt.txt', 'w').write(build_prompt())
    for pn in pages:
        pg = doc[pn - 1]; w, h = pg.get_size()
        meth = [l.split('\t')[3] for l in open(f'{idx}/index.tsv') if l.split('\t')[2] == sha and l.split('\t')[1] == str(pn)]
        meth = meth[0] if meth else 'text'
        txtf = f'{idx}/{sha}/p{pn}.txt' if meth == 'text' else f'{idx}/{sha}/p{pn}.ocr.txt'
        text = open(txtf).read()
        if meth == 'text+ocr': text = open(f'{idx}/{sha}/p{pn}.txt').read() + '\n\n----- OCR of the same page -----\n' + text
        boxes = tiles_for(w, h)
        # token saver: a text-layer page that never mentions a field's keyword cannot show it; skip that field for this page.
        # Pages without a clean text layer (ocr, text+ocr) keep every field.
        KW = {'mileage_arai_kmpl': r'km\s*/\s*l|kmpl|mileage|efficiency|arai', 'mileage_arai_km_per_kg': r'km\s*/\s*kg|mileage|efficiency|arai',
              'cruise_control': r'cruise|\bscc\b|\bacc\b', 'wireless_charging': r'wireless\s+(?:smartphone\s+|phone\s+|mobile\s+|device\s+)?charg|\bqi\b',
              'heads_up_display': r'head.?up|\bhud\b', 'ventilated_front_seats': r'ventilat|cooled\s+seat|seat\s+cool',
              'paddle_shifters': r'paddle'}
        pfields = fields if meth != 'text' else [f for f in fields if re.search(KW[f], text, re.I)]
        for arm in ('a',):
            d = f'{bd}/p{pn}/{arm}'; os.makedirs(d, exist_ok=True)
            open(f'{d}/page_text.txt', 'w').write(text if meth == 'text' else f'(text of a page without a clean text layer: the layer may be scrambled and the OCR may contain errors)\n{text}')
            open(f'{d}/variants.txt', 'w').write('\n'.join(x[0] for x in vs) + '\n')
            open(f'{d}/variant_info.tsv', 'w').write('variant\tfuel\tgearbox\n' + '\n'.join(f'{x[0]}\t{x[1]}\t{x[2]}' for x in vs) + '\n')
            open(f'{d}/fields.txt', 'w').write('\n'.join(pfields) + '\n')
            for i, b in enumerate(boxes, 1):
                s = DPI / 72
                im = pg.render(scale=s).to_pil().crop(tuple(round(v * s) for v in b)).convert('RGB')
                im.save(f'{d}/tile{i}.png')
        man['pages'][pn] = dict(fields=pfields, text_method=meth, size_pt=[round(w, 1), round(h, 1)], tile_boxes=[list(map(round, b)) for b in boxes])
    json.dump(man, open(f'{bd}/manifest.json', 'w'), indent=1)
    print(json.dumps({p: len(v['tile_boxes']) for p, v in man['pages'].items()}), 'fields', fields, 'variants', len(vs))


def one_run(args):
    d, prompt = args
    if os.path.exists(f'{d}/out.json') and os.path.getsize(f'{d}/out.json') > 0: return d
    r = subprocess.run(['claude', '-p', prompt] + FLAGS, cwd=d, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1500)
    open(f'{d}/out.json', 'w').write(r.stdout); open(f'{d}/err.txt', 'w').write(r.stderr)
    return d


def parse_result(txt):
    t = txt.strip()
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t)
    i, j = t.find('{'), t.rfind('}')
    return json.loads(t[i:j + 1])


def run(a):
    bd = a[0]; arm = a[1] if len(a) > 1 else 'a'; man = json.load(open(f'{bd}/manifest.json'))
    prompt = open(f'{bd}/prompt.txt' if arm == 'a' else f'{bd}/prompt_b.txt').read()
    pages = [pn for pn in man['pages'] if os.path.isdir(f'{bd}/p{pn}/{arm}')]
    jobs = [(f'{bd}/p{pn}/{arm}', prompt) for pn in pages]
    with ThreadPoolExecutor(2) as ex: list(ex.map(one_run, jobs))
    rows = ['page\tarm\ttotal_tokens\toutput_tokens\tcost_usd\tduration_ms\tis_error\tcells']
    for d, _ in jobs:
        pn = d.split('/')[-2]
        try:
            o = json.load(open(f'{d}/out.json')); u = o['usage']
            tot = u['input_tokens'] + u['cache_creation_input_tokens'] + u['cache_read_input_tokens'] + u['output_tokens']
            res = parse_result(o['result']); json.dump(res, open(f'{d}/cells.json', 'w'), indent=1)
            rows.append(f"{pn}\t{arm}\t{tot}\t{u['output_tokens']}\t{o['total_cost_usd']:.4f}\t{o['duration_ms']}\t{o['is_error']}\t{len(res['cells'])}")
        except Exception as e:
            rows.append(f'{pn}\t{arm}\t\t\t\t\tPARSE_ERROR {e!r}\t')
    open(f'{bd}/usage_{arm}.tsv', 'w').write('\n'.join(rows) + '\n'); print('\n'.join(rows))


def make_b(bd, man, sel_rows):
    """Targeted blind run b: only the selected variant/field pairs, no run-a output, its own folder per page."""
    open(f'{bd}/prompt_b.txt', 'w').write(COMMON_B + open(f'{HERE}/GLOSSARY.md').read() + '\n' + TASK_B + OUTPUT_B)
    import shutil
    for pn in man['pages']:
        rows = [r for r in sel_rows if r['page'] == pn]
        d = f'{bd}/p{pn}/b'
        if os.path.exists(f'{d}/cells.json'): continue   # run b already done: keep its raw output
        shutil.rmtree(d, ignore_errors=True)
        if not rows: continue
        os.makedirs(d)
        for f in os.listdir(f'{bd}/p{pn}/a'):
            if f == 'page_text.txt' or f.startswith('tile'): shutil.copy(f'{bd}/p{pn}/a/{f}', f'{d}/{f}')
        info = {}
        for l in open(f'{bd}/p{pn}/a/variant_info.tsv').read().splitlines()[1:]:
            n, fu, g = l.split('\t'); info[n] = (fu, g)
        open(f'{d}/pairs.tsv', 'w').write('variant\tfield\tfuel\tgearbox\n' + '\n'.join(f"{r['variant']}\t{r['field']}\t{info[r['variant']][0]}\t{info[r['variant']][1]}" for r in rows) + '\n')


def same(x, y, f):
    if x is None or y is None: return x is y
    return abs(float(x) - float(y)) < 0.005 if f.startswith('mileage') else int(float(x)) == int(float(y))


def classify(a):
    bd, dbp = a[0], a[1]; man = json.load(open(f'{bd}/manifest.json')); db = sqlite3.connect(dbp)
    cc = [d[0] for d in db.execute('select * from v_variant_canonical_q limit 0').description]
    mid = man['model_id']
    vs = {n: (vid, fuel) for vid, n, fuel in db.execute("""select v.id, v.name, p.fuel_type from variant v left join powertrain p on p.id=v.powertrain_id
                                                           where v.model_id=? and v.base_variant_id is null""", (mid,))}
    verified = {(v, f) for v, f in db.execute("select variant_id, field_name from field_provenance where decision_reason like 'OEM_BROCHURE_VERIFIED%' and decision in ('accepted','confirmed')")}
    quar = {(t, f) for t, f in db.execute("select target_id, target_field from evidence_quarantine where released_at is null and target_table='variant'")}
    qall = {t for t, f in quar if f == '*'}
    canon = {r[0]: r for r in db.execute('select * from v_variant_canonical_q')}
    stored = {r[0]: r[1:] for r in db.execute(f"select id, {', '.join(FIELDS)} from variant where model_id={mid}")}
    out, unmapped, cols = [], set(), {}
    for pn in man['pages']:
        res = {}
        for arm in ('a', 'b'):
            try: res[arm] = json.load(open(f'{bd}/p{pn}/{arm}/cells.json'))
            except Exception: res[arm] = dict(cells=[], page_columns=[])
        cols[pn] = {arm: res[arm].get('page_columns', []) for arm in res}
        cell = {arm: {(c['variant'], c['field']): c for c in res[arm]['cells']} for arm in res}
        for (vn, f), ca in cell['a'].items():
            if vn not in vs: unmapped.add(vn); continue
            vid, fuel = vs[vn]
            if f not in FIELDS: continue
            if f == 'mileage_arai_kmpl' and fuel in ('CNG', 'Electric'): continue
            if f == 'mileage_arai_km_per_kg' and fuel != 'CNG': continue
            cb = cell['b'].get((vn, f), {}); has_b = (vn, f) in cell['b']
            av = ca.get('value') if ca.get('status') == 'FOUND' else None
            bv = cb.get('value') if cb.get('status') == 'FOUND' else None
            kst = stored[vid][FIELDS.index(f)]; kcan = canon[vid][cc.index(f)]
            masked = (vid, f) in quar or vid in qall
            status = 'VERIFIED' if (vid, f) in verified else 'QUARANTINED' if masked else 'NULL' if kcan is None else 'UNVERIFIED'
            if av is None: cls = 'NOT_ON_PAGE'
            elif status == 'VERIFIED': cls = 'CONFIRM_V' if same(av, kst, f) else 'CONFLICT'
            elif kst is None: cls = 'FILL'
            elif same(av, kst, f): cls = 'CONFIRM'
            else: cls = 'CORRECTION'
            out.append(dict(page=pn, vid=vid, variant=vn, field=f, kb_stored=kst, kb_status=status, cls=cls,
                            a=av, a_qual=ca.get('qualifier', ''), a_src=ca.get('source', ''), b=bv, b_qual=cb.get('qualifier', ''),
                            has_b=has_b, agree=((av is None and bv is None) or (av is not None and bv is not None and same(av, bv, f))) if has_b else None))
    # absent-as-zero guard (10B lesson): a 0 on a page where the field is never shown fitted anywhere, with no explicit absence marker
    marker = re.compile(r"(^|[\s'\"(])[-\u2013\u2014x\u2717](?=$|[\s'\")])|dash|not available|not fitted|absent|cross", re.I)
    any1 = {(r['page'], r['field']) for r in out if r['a'] is not None and float(r['a']) == 1 and r['field'] not in UNIT}
    for r in out:
        if r['field'] in UNIT or r['a'] is None or float(r['a']) != 0 or r['cls'] in ('NOT_ON_PAGE', 'CONFLICT', 'CONFIRM_V'): continue
        if (r['page'], r['field']) not in any1 and not marker.search(r['a_src'] or ''): r['cls'] = 'ABSENT_NOT_SHOWN'
    # same cell on several pages must agree
    by = {}
    for r in out: by.setdefault((r['vid'], r['field']), []).append(r)
    for k, rs in by.items():
        vals = {round(float(r['a']), 3) for r in rs if r['a'] is not None}
        if len(vals) > 1:
            for r in rs: r['cls'] = 'PAGE_CONFLICT'
    rnd = random.Random(7); sel = set()
    for r in out:
        if r['cls'] == 'CORRECTION': sel.add(id(r))
    fills = [r for r in out if r['cls'] == 'FILL']
    groups = {}
    for r in fills: groups.setdefault((r['page'], r['field']), []).append(r)
    want = max(10, math.ceil(0.2 * len(fills))) if fills else 0; want = min(want, len(fills))
    picked = []
    for g in groups.values():
        rnd.shuffle(g); picked += g[:max(1, math.ceil(0.2 * len(g)))]
    rest = [r for r in fills if r not in picked]; rnd.shuffle(rest)
    picked += rest[:max(0, want - len(picked))]
    for r in picked: sel.add(id(r))
    for r in out: r['validate'] = id(r) in sel
    make_b(bd, man, [r for r in out if r['validate']])
    keys = ['page', 'vid', 'variant', 'field', 'kb_status', 'kb_stored', 'cls', 'a', 'a_qual', 'b', 'b_qual', 'agree', 'validate', 'a_src']
    with open(f'{bd}/classified.tsv', 'w') as f:
        f.write('\t'.join(keys) + '\n')
        for r in out: f.write('\t'.join('' if r[k] is None else str(r[k]) for k in keys) + '\n')
    vr = [r for r in out if r['validate'] and r['agree'] is not None]
    cnt = lambda p: sum(1 for r in out if p(r))
    summ = dict(cells=len(out), unmapped=sorted(unmapped), by_class={c: cnt(lambda r, c=c: r['cls'] == c) for c in ('FILL', 'CONFIRM', 'CORRECTION', 'NOT_ON_PAGE', 'ABSENT_NOT_SHOWN', 'CONFLICT', 'CONFIRM_V', 'PAGE_CONFLICT')},
                validated=len(vr), validated_agree=sum(1 for r in vr if r['agree']),
                selected=cnt(lambda r: r['validate']), page_columns=cols)
    json.dump(summ, open(f'{bd}/summary.json', 'w'), indent=1); print(json.dumps({k: v for k, v in summ.items() if k != 'page_columns'}))


if __name__ == '__main__':
    {'prep': prep, 'run': run, 'classify': classify}[sys.argv[1]](sys.argv[2:])
