"""Deterministic filter + scorer for the Flash extraction pilot. No LLM anywhere in this file.

Usage: python -I filter_score.py <db_copy> <gold.tsv> <truth.json> <prompts_dir> <calls_dir> <arm> <out_dir>
  truth.json  brochure-verified OEM observations 10E–10N ({vid, field, val}); gold.tsv ⊂ truth
  arm         suffix of the prompt set (e.g. '' or '.arm2'); call ids are read from <page><arm>.callid

FILTER (row passes only if all three hold)
  (a) quote is an exact substring of the page text given to Gemini, after whitespace
      normalisation only (every run of whitespace -> one space; nothing else changed)
  (b) the value appears in the quote: numeric fields -> a number in the quote equals the value;
      bool fields -> value 1 needs the field keyword or a presence mark in the quote,
      value 0 needs an absence mark (-, –, —, ×, ✗, No, NA, N/A, Not available)
  (c) printed_label appears in the quote (whitespace-normalised, case-sensitive), or in the row
      header / column header of a pdfplumber table cell that contains the value
QUOTE CLASS for (a)-failures: 'relabelled' if ≥80% of the quote's tokens occur in the page text
  (quote rearranged / labels added), else 'invented'.
LABEL MAPPING (deterministic): split label on , / & ; and ' and '; per segment find exact trim
  tokens (longest first, boundaries exclude + ( alnum), gearbox tokens and fuel tokens.
  TRIM      ≥1 segment names a trim -> variants of those trims, filtered by the segment's tokens
  MODEL     no trim anywhere but gearbox/fuel tokens -> all variants matching the tokens
  AMBIGUOUS a named trim whose tokens match no KB variant
  NONE      no trim and no gearbox/fuel token, or the label contains a feature word (cruise,
            wireless, charg, paddle, efficiency, mileage, km/l, km/kg): feature names, 'UNSURE' …
  Before trim matching, an "in addition to <trim>" clause is removed (it references the
  previous trim, it does not label this value).
CORRECT (precision numerator): passing row, mapping TRIM or MODEL, and for every mapped variant
  that has a truth value for the field the value equals it, with ≥1 such variant; mapped variants
  whose truth disagrees make the row WRONG_VALUE_FOR_LABEL. Rows mapped NONE/AMBIGUOUS are
  UNATTRIBUTABLE (counted not correct: they cannot be written to any variant).
FOUND (recall): gold cell with a passing row, same field, value and unit, label mapping TRIM and
  the gold variant in the mapped set. FOUND_MODEL is reported separately (label names no trim).
"""
import csv, json, os, re, sqlite3, sys
from collections import Counter

NUMERIC = {'mileage_arai_kmpl': 'km/l', 'mileage_arai_km_per_kg': 'km/kg'}
KEYWORD = {'cruise_control': r'cruise', 'wireless_charging': r'wireless', 'paddle_shifters': r'paddle'}
PRESENT = r'(✓|✔|●|\bYes\b|\bStd\b|\bStandard\b|\b\d?(AT|MT|AMT|DCT|CVT)\b)'
ABSENT = r'(^|\s|\|)(-|–|—|×|✗|No|NA|N/A|Not available)(\s|\||$)'
GEARBOX = [(r'E-?CVT', {'e-CVT'}), (r'IVT|CVT', {'CVT', 'IVT'}), (r'AMT', {'AMT'}), (r'DCT|DCA|DSG', {'DCT'}),
           (r'\d?AT|AUTOMATIC|TC', {'Torque Converter'}), (r'\d?MT|MANUAL', {'Manual'})]
FUEL = [(r'STRONG HYBRID|HYBRID', {'Petrol Hybrid'}), (r'CNG', {'CNG'}), (r'DIESEL', {'Diesel'}), (r'PETROL', {'Petrol'})]
FEATURE_WORDS = r'CRUISE|WIRELESS|CHARG|PADDLE|EFFICIENCY|MILEAGE|KM/L|KM/KG'
NONTRIM = {'PETROL', 'DIESEL', 'CNG', 'MT', 'AT', 'AMT', 'DCT', 'DCA', 'IVT', 'CVT', 'E-CVT', 'MANUAL', 'AUTOMATIC',
           'STRONG', 'HYBRID', 'ADAS', 'ALLGRIP', 'TURBO'}


def ws(s):
    return re.sub(r'\s+', ' ', str(s)).strip()


def nums(s):
    return [float(x.replace(',', '.')) for x in re.findall(r'\d+(?:[.,]\d+)?', s)]


def norm_label(s):
    s = ws(s).upper()
    return re.sub(r'\s+\(', '(', s)


def trim_of(name):
    toks = [t for t in norm_label(name).split() if t not in NONTRIM]
    return ' '.join(toks)


def tok_re(t):
    return r'(?<![A-Z0-9+(])' + re.escape(t) + r'(?![A-Z0-9+(])'


class Mapper:
    def __init__(self, variants):  # [(id, name, transmission, fuel)]
        self.v = variants
        self.trims = sorted({trim_of(n) for _, n, _, _ in variants}, key=len, reverse=True)

    def tokens(self, seg):
        gb, fu, rest = set(), set(), seg
        for pat, vals in GEARBOX:
            if re.search(r'(?<![A-Z0-9])(' + pat + r')(?![A-Z0-9])', rest):
                gb |= vals; rest = re.sub(r'(?<![A-Z0-9])(' + pat + r')(?![A-Z0-9])', ' ', rest)
        for pat, vals in FUEL:
            if re.search(r'(?<![A-Z])(' + pat + r')(?![A-Z])', rest):
                fu |= vals; rest = re.sub(r'(?<![A-Z])(' + pat + r')(?![A-Z])', ' ', rest)
        allgrip = 'ALLGRIP' in seg or 'ALL GRIP' in seg
        return gb, fu, allgrip

    def match(self, trims, gb, fu, allgrip, use_allgrip):
        out = set()
        for vid, name, trans, fuel in self.v:
            if trims is not None and trim_of(name) not in trims:
                continue
            if gb and trans not in gb:
                continue
            if fu and fuel not in fu:
                continue
            if use_allgrip and allgrip != ('ALLGRIP' in name.upper()):
                continue
            out.add(vid)
        return out

    def map(self, label):
        L = norm_label(label)
        if not L or L == 'UNSURE':
            return 'NONE', set()
        if re.search(FEATURE_WORDS, L):   # a feature/spec name, not a variant label
            return 'NONE', set()
        # a heading's back-reference ("HTX [Features in addition to HTK+ (O)]") names another trim
        L = re.sub(r'[\[(]?\s*(FEATURES\s+)?IN ADDITION TO\b[^\])]*[\])]?', ' ', L)
        segs = [s for s in re.split(r'[,/&;]| AND ', L) if s.strip()]
        found_trim, any_tok, res, amb = False, False, set(), False
        for s in segs:
            trims, rest = set(), s
            for t in self.trims:
                if re.search(tok_re(t), rest):
                    trims.add(t); rest = re.sub(tok_re(t), ' ', rest)
            gb, fu, ag = self.tokens(rest)
            if trims:
                found_trim = True
                m = self.match(trims, gb, fu, ag, ag)
                if not m:
                    amb = True
                res |= m
            elif gb or fu or ag:
                any_tok = True
        if found_trim:
            return ('AMBIGUOUS', res) if amb and not res else ('TRIM', res)
        if any_tok:
            gb, fu, ag = self.tokens(L)
            return 'MODEL', self.match(None, gb, fu, ag, True)
        return 'NONE', set()


def value_in_quote(field, value, quote):
    q = ws(quote)
    if field in NUMERIC:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        return any(abs(v - n) < 1e-9 for n in nums(q))
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return False
    if v == 1:
        return bool(re.search(KEYWORD[field], q, re.I) or re.search(PRESENT, q))
    if v == 0:
        return bool(re.search(ABSENT, q))
    return False


def label_in_tables(label, value, field, tables):
    lab = ws(label)
    for t in tables:
        if not t:
            continue
        header = [ws(c or '') for c in t[0]]
        for r in t:
            cells = [ws(c or '') for c in r]
            for j, c in enumerate(cells):
                hit = value_in_quote(field, value, c) if c else False
                if not hit:
                    continue
                rowh = cells[0] if cells else ''
                colh = header[j] if j < len(header) else ''
                if lab and (lab in rowh or lab in colh):
                    return True
    return False


def parse_rows(resp):
    s = (resp or '').strip()
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', s)
    try:
        d = json.loads(s)
    except Exception:
        m = re.search(r'\[.*\]', s, re.S)
        d = json.loads(m.group(0)) if m else []
    return d if isinstance(d, list) else [d]


def main():
    dbp, goldp, truthp, pdir, cdir, arm, out = sys.argv[1:8]
    manual = {}
    if len(sys.argv) > 8 and os.path.exists(sys.argv[8]):   # row_id -> CORRECT|WRONG_VALUE_FOR_LABEL (page read by Claude)
        for r in csv.DictReader(open(sys.argv[8]), delimiter='\t'):
            manual[r['row_id']] = r['verdict']
    os.makedirs(out, exist_ok=True)
    db = sqlite3.connect(dbp)
    gold = list(csv.DictReader(open(goldp), delimiter='\t'))
    truth = {(r['vid'], r['field']): float(r['val']) for r in json.load(open(truthp))}
    pages = {}
    for g in gold:
        pages.setdefault((g['pdf_sha1'], g['page']), g)
    rows, calls = [], []
    for (sha, page), g in pages.items():
        key = f'{sha}_p{page}'
        cid = open(f'{pdir}/{key}{arm}.callid').read().strip()
        cj = json.load(open(f'{cdir}/{cid}.json'))
        idx = json.load(open(f'{cdir}/../index/{sha}/p{page}.tables.json'))
        pagetext = ws(open(f'{pdir}/{key}.pagetext.txt').read())
        ptoks = set(pagetext.split())
        variants = db.execute('select v.id, v.name, v.transmission, p.fuel_type from variant v '
                              'join powertrain p on p.id=v.powertrain_id where v.model_id=?', (g['model_id'],)).fetchall()
        mp = Mapper(variants)
        try:
            parsed = parse_rows(cj.get('response'))
        except Exception:
            parsed = []
        calls.append(dict(call=cid, page=key, model=g['model'], source=g['prompt_source'], rows=len(parsed),
                          agy_seconds=cj.get('duration_seconds'), status=cj.get('status')))
        for k, r in enumerate(parsed):
            lab, f, val, unit, q = (str(r.get('printed_label', '')), str(r.get('field', '')), r.get('value'),
                                    str(r.get('unit', '')), str(r.get('quote', '')))
            a = ws(q) in pagetext and ws(q) != ''
            b = f in NUMERIC or f in KEYWORD
            b = b and value_in_quote(f, val, q)
            c = (ws(lab) != '' and ws(lab) in ws(q)) or label_in_tables(lab, val, f, idx)
            if lab.strip().upper() == 'UNSURE':
                c = False
            qclass = 'exact' if a else ('relabelled' if q and sum(t in ptoks for t in ws(q).split()) / max(1, len(ws(q).split())) >= 0.8 else 'invented')
            passed = a and b and c
            mstat, mset = mp.map(lab)
            checks = [(v, truth.get((v, f))) for v in sorted(mset)]
            known = [(v, t) for v, t in checks if t is not None]
            try:
                fv = float(val)
            except (TypeError, ValueError):
                fv = None
            if mstat in ('NONE', 'AMBIGUOUS'):
                verdict = 'UNATTRIBUTABLE'
            elif not known:
                verdict = manual.get(f'{cid}.{k+1}', 'NO_TRUTH')
            elif all(fv is not None and abs(t - fv) < 1e-9 for _, t in known):
                verdict = 'CORRECT'
            else:
                verdict = 'WRONG_VALUE_FOR_LABEL'
            num_on_page = (f not in NUMERIC) or (fv is not None and any(abs(fv - n) < 1e-9 for n in nums(pagetext)))
            rows.append(dict(row_id=f'{cid}.{k+1}', call=cid, page=key, model=g['model'], source=g['prompt_source'],
                             printed_label=lab, field=f, value=val, unit=unit, quote=q,
                             a_exact_quote=int(a), b_value_in_quote=int(b), c_label=int(c), status='PASS' if passed else 'REJECTED',
                             quote_class=qclass, map_status=mstat, mapped_variants=' '.join(map(str, sorted(mset))),
                             verdict=verdict if passed else '', verdict_diagnostic=verdict, truth_coverage=f'{len(known)}/{len(checks)}',
                             value_on_page=int(num_on_page)))
    # recall
    found = []
    for gc in gold:
        vid, fld, gv, gu = int(gc['variant_id']), gc['field'], float(gc['value']), gc['unit']
        hit, hit_model = '', ''
        for r in rows:
            if r['status'] != 'PASS' or r['field'] != fld or r['page'] != f"{gc['pdf_sha1']}_p{gc['page']}":
                continue
            try:
                rv = float(r['value'])
            except (TypeError, ValueError):
                continue
            unit_ok = (gu == 'bool') or (ws(r['unit']).lower().replace(' ', '') in {gu, gu.replace('/', 'p'), 'kmpl' if gu == 'km/l' else gu})
            if abs(rv - gv) > 1e-9 or not unit_ok:
                continue
            ids = {int(x) for x in r['mapped_variants'].split()} if r['mapped_variants'] else set()
            if vid in ids and r['map_status'] == 'TRIM':
                hit = hit or r['row_id']
            elif vid in ids and r['map_status'] == 'MODEL':
                hit_model = hit_model or r['row_id']
        found.append(dict(gold_id=gc['gold_id'], source=gc['prompt_source'], pdf=gc['pdf'], field=fld,
                          variant=gc['variant_name'], value=gc['value'], FOUND=int(bool(hit)), found_row=hit,
                          FOUND_MODEL=int(bool(hit_model) and not hit), model_row=hit_model))
    for name, data in (('rows', rows), ('recall', found), ('calls', calls)):
        with open(f'{out}/{name}.tsv', 'w') as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]), delimiter='\t'); w.writeheader(); w.writerows(data)
    P = [r for r in rows if r['status'] == 'PASS']
    corr = sum(r['verdict'] == 'CORRECT' for r in P)
    attributable = [r for r in P if r['verdict'] in ('CORRECT', 'WRONG_VALUE_FOR_LABEL')]
    m = dict(arm=arm or 'arm1', rows=len(rows), passing=len(P),
             pass_rate=round(len(P) / len(rows), 4) if rows else None,
             precision=round(corr / len(P), 4) if P else None,
             precision_attributable_only=round(corr / len(attributable), 4) if attributable else None,
             verdicts=dict(Counter(r['verdict'] for r in P)),
             reject_reasons=dict(Counter(f"a{r['a_exact_quote']}b{r['b_value_in_quote']}c{r['c_label']}" for r in rows if r['status'] == 'REJECTED')),
             quote_class=dict(Counter(r['quote_class'] for r in rows)),
             map_status_all=dict(Counter(r['map_status'] for r in rows)),
             unsure_labels=sum(r['printed_label'].strip().upper() == 'UNSURE' for r in rows),
             wrong_values=sum(1 for r in rows if not r['value_on_page']) + sum(r['verdict'] == 'WRONG_VALUE_FOR_LABEL' for r in P),
             recall=round(sum(f['FOUND'] for f in found) / len(found), 4),
             found=sum(f['FOUND'] for f in found), found_model_level=sum(f['FOUND_MODEL'] for f in found),
             recall_text=f"{sum(f['FOUND'] for f in found if f['source']=='text')}/{sum(1 for f in found if f['source']=='text')}",
             recall_ocr=f"{sum(f['FOUND'] for f in found if f['source']=='ocr')}/{sum(1 for f in found if f['source']=='ocr')}",
             rejected_verdict_diagnostic=dict(Counter(r['verdict_diagnostic'] for r in rows if r['status'] == 'REJECTED')),
             calls=[c['call'] for c in calls])
    json.dump(m, open(f'{out}/metrics.json', 'w'), indent=1)
    print(json.dumps(m, indent=1))


if __name__ == '__main__':
    main()
