"""Round-2 deterministic filter, mapper, scorer and decision. PRE-REGISTERED: no LLM, no tuning.

Usage: python -I filter_score_v2.py <db_copy> <gold.tsv> <truth.json> <index_dir> <prompts_dir> <calls_dir> <out_dir>
  call ids are read from <prompts_dir>/<pdf_sha1>_p<N>.callid

UNIT OF SCORING = a row after the per-trim split: a variant_label naming several trims
("Zxi / Zxi (O)") is split on / , & ; ' and ' into one row per trim (a segment that names no
trim, e.g. 'AMT' in 'VXI MT/AMT', attaches its tokens to the previous trim segment).

NORMALISATION: ws() = every run of whitespace -> one space, stripped. key() = upper case, all
whitespace removed. Trim keys come from KB variant names with these tokens removed: fuel,
gearbox, engine displacement (1.2, 1.5L …), TURBO, STRONG, HYBRID, MILD, ADAS, ALLGRIP, DUAL,
TONE and bracketed gearbox codes ((TC), (DCT) …).

FILTER: a row PASSES only if (a)-(e) all hold.
 (a) ws(value_quote) is a non-empty substring of ws(page text).
 (b) field is one of the fields asked; value parses (numbers; bool 1/0/true/false/yes/no) and
     appears in value_quote: numeric -> some number in the quote equals it; bool 1 -> the field
     keyword (cruise|wireless|paddle) or a presence mark (• ● ✓ ✔ Yes Std Standard, a standalone S,
     a gearbox code such as 6AT, '(AT only)'); bool 0 -> an absence mark (- – — × ✗ No NA N/A
     'Not available') as a standalone token.
 (c) ws(header_quote) is a non-empty substring of ws(page text), the label segment is not UNSURE,
     and key(label segment) is contained in key(header_quote).
 (d) structural link on <index>/<sha1>/p<N>.words.json (normalised 0..1 boxes, origin top-left).
     Words are ordered as the prompt text (Vision: rows as in ocr.txt; pdfplumber: as given).
     Trim spans: runs of consecutive words whose concatenated key EQUALS a trim key (ignoring
     , ; : . at word edges). Quote spans: minimal runs whose concatenated key CONTAINS the quote's
     key. Value anchors = quote spans of value_quote;
     if none and the field is numeric, words containing that number. Header anchors = spans of
     the claimed trim key, restricted to lie inside a header_quote quote-span when one is found.
     Trim occurrences = spans of every KB trim key of the model, keeping only maximal spans
     (a span inside a longer trim span is dropped: 'Zxi+' inside 'Zxi+ (O)').
     Tolerances: TY = 0.004 (vertical), TX = 0.003 (horizontal).
       vband(a,b): vertical intervals overlap within TY; hover(a,b): horizontal overlap within TX.
       COLUMN_HEADER   h.top < v.top, h.bottom <= v.top+TY, hover(h,v)
                       nearest = trim occurrences meeting the same test with max bottom (±TY)
       ROW_HEADER      vband(h,v), h.x1 <= v.x0+TX;  nearest = same test, max x1 (±TX)
       SAME_LINE       vband(h,v);                   nearest = same test, min horizontal gap (±TX)
       SECTION_HEADING h.top <= v.top+TY, h.x0 <= v.x1+TX; nearest = same test, max top (±TY)
     (d) holds if some (header anchor h, value anchor v) meets the relation AND h is in the
     nearest set of v. Any other label_source fails (d).
 (e) qualifier consistency: if a marker sits in value_quote or in the page line(s) holding it
     (markers: * ^ # ‡ † 'only' (AT)/(MT)/(AMT)/(DCT)/(CVT)/(IVT) and gearbox codes AT/6AT/DCT/DSG/
     AMT/IVT/CVT; the 'line' is the contiguous run of words in the value's band with gaps <= 0.010
     around each located value_quote span, else the page-text line(s) holding the quote), or a footnote/restriction marker sits in header_quote (* ^ # ‡ † 'only';
     gearbox words in a header are naming, not markers), then qualifier must be non-empty.
     A failure here is a QUALIFIER MISS.

MAPPING (deterministic; AMBIGUOUS is never guessed):
  trim = the label segment's trim key (must equal a KB trim key of the model, else AMBIGUOUS).
  gearbox/fuel/engine/ALLGRIP tokens: from the label segment, else from the header_quote
  segment(s) naming that trim (header first stripped of 'in addition to …' clauses); then
  intersected with the qualifier's tokens when the qualifier has any (empty result -> AMBIGUOUS).
  gearbox: MT/MANUAL->Manual; AT/6AT/AUTOMATIC/TC->Torque Converter; AMT; DCT/DCA/DSG->DCT;
  CVT/IVT->CVT,IVT; e-CVT. fuel: PETROL, DIESEL/DSL, CNG, HYBRID->Petrol Hybrid.
  engine tokens (1.0, 1.5 …) restrict to variant names containing them (only if some name has one).
  km/l: gearbox must be identified, else AMBIGUOUS; CNG variants excluded unless CNG is named;
        ALLGRIP variants included only if ALLGRIP is named.
  km/kg: gearbox must be identified, else AMBIGUOUS; restricted to CNG variants.
  features: no gearbox restriction -> every gearbox of the trim.
  Cumulative 'in addition to' lists apply only to the named trim (no inheritance is inferred).

SCORING against the truth set (all brochure-verified 10E–10N OEM cells for the 5 fields):
  CORRECT  every mapped variant that has truth equals the value (≥1 has truth), unit right
  WRONG    some mapped variant with truth differs, or the unit is wrong for the field
  UNKNOWN  no mapped variant has truth (listed, excluded from precision)
  AMBIGUOUS mapping ambiguous (listed, excluded from precision)
METRICS: precision = CORRECT/(CORRECT+WRONG) over passing rows + Wilson 95% lower bound;
  pass rate = passing/all rows; recall = gold cells FOUND / gold total, FOUND = a passing CORRECT
  row on the gold page, same field and value, whose mapped set contains the gold variant.
  Splits: page source (text/ocr) and layout (matrix vs non-matrix, from gold.tsv per page+field).
  Quote classes for value_quote and header_quote: exact / relabelled (≥80% of its tokens occur
  in the page text) / invented.
DECISION (pre-registered):
  CORRECT+WRONG < 40                              -> INCONCLUSIVE -> ALL-CLAUDE
  P >= .95 and LB >= .90 and pass rate >= .50     -> HYBRID
  P >= .95 and LB >= .90 and pass rate <  .50     -> HYBRID-LIMITED on the page types
      (source x layout) where P >= .95 and LB >= .90 hold on their own; if none -> ALL-CLAUDE
  otherwise                                       -> ALL-CLAUDE
"""
import csv, json, math, os, re, sqlite3, sys
from collections import Counter, defaultdict

TY, TX = 0.004, 0.003
FIELDS_NUM = {'mileage_arai_kmpl': {'KM/L', 'KMPL', 'KM/LTR', 'KM/LITRE'}, 'mileage_arai_km_per_kg': {'KM/KG'}}
KEYWORD = {'cruise_control': r'cruise', 'wireless_charging': r'wireless', 'paddle_shifters': r'paddle'}
PRESENT = r'(•|●|✓|✔|\bYes\b|\bStd\b|\bStandard\b|(?<![A-Za-z])S(?![A-Za-z])|\b\d?(AT|MT|AMT|DCT|CVT|IVT|DSG)\b|\bAT only\b)'
ABSENT = r'(^|\s|\|)(-|–|—|×|✗|No|NA|N/A|Not available)(\s|\||$)'
MARK_VALUE = r'[*^#‡†]|\bonly\b|\((AT|MT|AMT|DCT|CVT|IVT)\)|\b\d?(AT|DCT|DSG|AMT|IVT|CVT)\b'
MARK_HEADER = r'[*^#‡†]|\bonly\b'
GEARBOX = [(r'E-?CVT', {'e-CVT'}), (r'IVT|CVT', {'CVT', 'IVT'}), (r'AMT|AGS', {'AMT'}), (r'\d?DCT|DCA|\d?DSG', {'DCT'}),
           (r'\d?AT|AUTOMATIC|TC', {'Torque Converter'}), (r'\d?MT|MANUAL', {'Manual'})]
FUEL = [(r'STRONG HYBRID|HYBRID', {'Petrol Hybrid'}), (r'CNG', {'CNG'}), (r'DIESEL|DSL', {'Diesel'}), (r'PETROL', {'Petrol'})]
NONTRIM_RE = re.compile(r'^(\(?(PETROL|DIESEL|CNG|MT|AT|AMT|DCT|DCA|DSG|IVT|CVT|E-CVT|TC|MANUAL|AUTOMATIC)\)?|'
                        r'STRONG|HYBRID|MILD|ADAS|ALLGRIP|TURBO|DUAL|TONE|\d\.\d+L?)$')


def ws(s):
    return re.sub(r'\s+', ' ', str(s)).strip()


def key(s):
    return re.sub(r'\s+', '', str(s)).upper()


def nums(s):
    return [float(x.replace(',', '.')) for x in re.findall(r'\d+(?:[.,]\d+)?', s)]


def trim_key(name):
    return ''.join(t for t in str(name).upper().split() if not NONTRIM_RE.match(t))


def wilson_lb(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def tokens(text):
    """gearbox, fuel, engine, allgrip tokens of a text."""
    T = ' ' + str(text).upper() + ' '
    gb, fu, eng = set(), set(), set(re.findall(r'(?<![\d.])(\d\.\d)(?:\s*L)?(?![\d])', T))
    rest = T
    for pat, vals in GEARBOX:
        rx = r'(?<![A-Z0-9])(' + pat + r')(?![A-Z0-9])'
        if re.search(rx, rest):
            gb |= vals; rest = re.sub(rx, ' ', rest)
    for pat, vals in FUEL:
        rx = r'(?<![A-Z])(' + pat + r')(?![A-Z])'
        if re.search(rx, rest):
            fu |= vals; rest = re.sub(rx, ' ', rest)
    return gb, fu, eng, ('ALLGRIP' in T or 'ALL GRIP' in T)


def segments(label):
    return [s for s in re.split(r'[,/&;]| and ', str(label), flags=re.I) if s.strip()]


def split_label(label, trims):
    """-> list of (segment_text, trim_key or None). Token-only segments attach to the previous trim."""
    out = []
    for s in segments(label):
        tk = trim_key(s)
        if tk == '' and out:
            out[-1] = (out[-1][0] + ' ' + s, out[-1][1])
        else:
            out.append((s.strip(), tk if tk in trims else None))
    return out


def strip_addition(h):
    return re.sub(r'[\[(]?\s*(features\s+)?(in addition to|over)\b[^\])]*[\])]?', ' ', str(h), flags=re.I)


def value_in_quote(field, v, q):
    q = ws(q)
    if field in FIELDS_NUM:
        return v is not None and any(abs(v - n) < 1e-9 for n in nums(q))
    if v == 1:
        return bool(re.search(KEYWORD[field], q, re.I) or re.search(PRESENT, q))
    if v == 0:
        return bool(re.search(ABSENT, q))
    return False


def parse_value(field, val):
    if field in FIELDS_NUM:
        try:
            return float(str(val).replace(',', '.'))
        except ValueError:
            return None
    s = str(val).strip().lower()
    return {'1': 1, '0': 0, '1.0': 1, '0.0': 0, 'true': 1, 'false': 0, 'yes': 1, 'no': 0}.get(s)


def parse_rows(resp):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (resp or '').strip())
    try:
        d = json.loads(s)
    except Exception:
        m = re.search(r'\[.*\]', s, re.S)
        d = json.loads(m.group(0)) if m else []
    return d if isinstance(d, list) else [d]


# ---------------- geometry ----------------
def ordered_words(wj):
    """Vision words in ocr.txt row order, then any pdfplumber words (line None) as given."""
    W = [w for w in wj['words'] if w['line'] is not None]
    tail = [w for w in wj['words'] if w['line'] is None]
    if not W:
        return tail
    lines = defaultdict(list)
    for w in W:
        lines[w['line']].append(w)
    items = []
    for ln, ws_ in lines.items():
        x0 = min(w['x0'] for w in ws_); top = min(w['top'] for w in ws_)
        items.append((round(top, 3), round(x0, 3), ln))
    items.sort()
    rows, cur, cy = [], [], None
    for top, x0, ln in items:
        if cy is not None and abs(top - cy) > 0.006:
            rows.append(cur); cur = []
        if not cur:
            cy = top
        cur.append((x0, ln))
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        for _, ln in sorted(r):
            out.extend(sorted(lines[ln], key=lambda w: w['x0']))
    return out + tail


def box(ws_):
    return dict(x0=min(w['x0'] for w in ws_), top=min(w['top'] for w in ws_),
                x1=max(w['x1'] for w in ws_), bottom=max(w['bottom'] for w in ws_))


def spans(words, target, trim=False, maxw=40):
    if not target:
        return []
    keys = [key(w['text']).strip(',;:.') if trim else key(w['text']) for w in words]
    out = []
    for i in range(len(words)):
        acc = ''
        for j in range(i, min(len(words), i + maxw)):
            acc += keys[j]
            if acc == target:
                out.append((i, j, box(words[i:j + 1])))
                break
            if len(acc) >= len(target) or not target.startswith(acc):
                break
    return out


def spans_contain(words, target, maxw=60):
    """minimal runs of consecutive words whose concatenated key contains target."""
    if not target:
        return []
    keys = [key(w['text']) for w in words]
    out = []
    for i in range(len(words)):
        acc = ''
        for j in range(i, min(len(words), i + maxw)):
            acc += keys[j]
            if target in acc:
                if target not in acc[len(keys[i]):]:
                    out.append((i, j, box(words[i:j + 1])))
                break
    return out


def run_text(words, i, j, gap=0.010):
    """text of the contiguous word run around words[i..j] in the same band (gaps <= gap)."""
    b = box(words[i:j + 1]); lo, hi = i, j
    while lo > 0 and vband(words[lo - 1], b) and 0 <= b['x0'] - words[lo - 1]['x1'] <= gap:
        lo -= 1; b = box(words[lo:hi + 1])
    while hi + 1 < len(words) and vband(words[hi + 1], b) and 0 <= words[hi + 1]['x0'] - b['x1'] <= gap:
        hi += 1; b = box(words[lo:hi + 1])
    return ' '.join(w['text'] for w in words[lo:hi + 1])


def vband(a, b):
    return a['top'] <= b['bottom'] + TY and b['top'] <= a['bottom'] + TY


def hover(a, b):
    return a['x0'] <= b['x1'] + TX and b['x0'] <= a['x1'] + TX


def rel(src, h, v):
    if src == 'COLUMN_HEADER':
        return h['top'] < v['top'] and h['bottom'] <= v['top'] + TY and hover(h, v)
    if src == 'ROW_HEADER':
        return vband(h, v) and h['x1'] <= v['x0'] + TX
    if src == 'SAME_LINE':
        return vband(h, v)
    if src == 'SECTION_HEADING':
        return h['top'] <= v['top'] + TY and h['x0'] <= v['x1'] + TX
    return False


def nearest(src, v, occ):
    c = [o for o in occ if rel(src, o[2], v)]
    if not c:
        return []
    if src == 'COLUMN_HEADER':
        m = max(o[2]['bottom'] for o in c); return [o for o in c if o[2]['bottom'] >= m - TY]
    if src == 'ROW_HEADER':
        m = max(o[2]['x1'] for o in c); return [o for o in c if o[2]['x1'] >= m - TX]
    if src == 'SAME_LINE':
        gap = lambda b: max(0.0, b['x0'] - v['x1'], v['x0'] - b['x1'])
        m = min(gap(o[2]) for o in c); return [o for o in c if gap(o[2]) <= m + TX]
    m = max(o[2]['top'] for o in c); return [o for o in c if o[2]['top'] >= m - TY]


def trim_occurrences(words, trims):
    occ = []
    for t in trims:
        occ += [(i, j, b, t) for i, j, b in spans(words, t, trim=True)]
    keep = []
    for o in occ:
        if not any(p is not o and p[0] <= o[0] and o[1] <= p[1] and (p[1] - p[0]) > (o[1] - o[0]) for p in occ):
            keep.append(o)
    return [(o[0], o[1], o[2], o[3]) for o in keep]


def page_lines_with(pagetext, quote):
    q = ws(quote)
    if not q:
        return ''
    rx = r'\s+'.join(re.escape(t) for t in q.split(' '))
    m = re.search(rx, pagetext)
    if not m:
        return ''
    a = pagetext.rfind('\n', 0, m.start()) + 1
    b = pagetext.find('\n', m.end())
    return pagetext[a: b if b >= 0 else len(pagetext)]


def quote_class(q, pagetext_ws, ptoks):
    q = ws(q)
    if q and q in pagetext_ws:
        return 'exact'
    if not q:
        return 'empty'
    t = q.split(' ')
    return 'relabelled' if sum(x in ptoks for x in t) / len(t) >= 0.8 else 'invented'


# ---------------- mapping ----------------
class Mapper:
    def __init__(self, variants):  # (id, name, transmission, fuel)
        self.v = variants
        self.trims = sorted({trim_key(n) for _, n, _, _ in variants if trim_key(n)}, key=len, reverse=True)
        self.has_engine = any(re.search(r'\d\.\d', n) for _, n, _, _ in variants)

    def map(self, seg_text, tk, header_quote, qualifier, field):
        if tk is None:
            return 'AMBIGUOUS', set(), 'trim not in KB'
        gb, fu, eng, ag = tokens(self._strip_trim(seg_text))
        if not (gb or fu or eng or ag):
            hs = [s for s in segments(strip_addition(header_quote)) if trim_key(s) == tk]
            for s in hs:
                g2, f2, e2, a2 = tokens(self._strip_trim(s)); gb |= g2; fu |= f2; eng |= e2; ag = ag or a2
        qg, qf, qe, qa = tokens(qualifier)
        if qg:
            gb = (gb & qg) if gb else set(qg)
            if not gb:
                return 'AMBIGUOUS', set(), 'gearbox conflict label/qualifier'
        if qf:
            fu = (fu & qf) if fu else set(qf)
            if not fu:
                return 'AMBIGUOUS', set(), 'fuel conflict label/qualifier'
        if qe:
            eng = (eng & qe) if eng else set(qe)
        ag = ag or qa
        if field in FIELDS_NUM and not gb:
            return 'AMBIGUOUS', set(), 'mileage without gearbox'
        out = set()
        for vid, name, trans, fuel in self.v:
            if trim_key(name) != tk:
                continue
            if gb and trans not in gb:
                continue
            if fu and fuel not in fu:
                continue
            if eng and self.has_engine and not any(re.search(re.escape(e), name) for e in eng):
                continue
            if field == 'mileage_arai_km_per_kg' and fuel != 'CNG':
                continue
            if field == 'mileage_arai_kmpl':
                if fuel == 'CNG' and 'CNG' not in fu:
                    continue
                if ('ALLGRIP' in name.upper()) and not ag:
                    continue
            out.add(vid)
        if not out:
            return 'AMBIGUOUS', set(), 'no KB variant matches'
        return 'TRIM', out, ''

    @staticmethod
    def _strip_trim(s):
        # keep only the non-trim tokens of a segment
        return ' '.join(t for t in str(s).upper().split() if NONTRIM_RE.match(t) or re.match(r'^\d?(AT|MT|DCT|DSG)$', t))


def main():
    dbp, goldp, truthp, idxd, pdir, cdir, out = sys.argv[1:8]
    os.makedirs(out, exist_ok=True)
    db = sqlite3.connect(dbp)
    gold = list(csv.DictReader(open(goldp), delimiter='\t'))
    truth = {(r['vid'], r['field']): float(r['val']) for r in json.load(open(truthp))}
    pages, layout = {}, {}
    for g in gold:
        pages.setdefault((g['pdf_sha1'], g['page']), g)
        layout[(g['pdf_sha1'], g['page'], g['field'])] = g['layout']
    rows, calls = [], []
    for (sha, page), g in pages.items():
        pkey = f'{sha}_p{page}'
        asked = sorted({x['field'] for x in gold if x['pdf_sha1'] == sha})
        cid = open(f'{pdir}/{pkey}.callid').read().strip()
        cj = json.load(open(f'{cdir}/{cid}.json'))
        raw_text = open(f'{pdir}/{pkey}.pagetext.txt').read()
        ptext = ws(raw_text); ptoks = set(ptext.split(' '))
        words = ordered_words(json.load(open(f'{idxd}/{sha}/p{page}.words.json')))
        variants = db.execute('select v.id, v.name, v.transmission, p.fuel_type from variant v join powertrain p '
                              'on p.id=v.powertrain_id where v.model_id=?', (g['model_id'],)).fetchall()
        mp = Mapper(variants)
        occ = trim_occurrences(words, mp.trims)
        perr = ''
        try:
            parsed = parse_rows(cj.get('response'))
        except Exception as e:
            parsed, perr = [], f'parse error: {e}'
        calls.append(dict(call=cid, page=pkey, model=g['model'], source=g['prompt_source'], raw_rows=len(parsed),
                          status=cj.get('status'), agy_seconds=cj.get('duration_seconds'), parse_error=perr))
        for k, r in enumerate(parsed, 1):
            if not isinstance(r, dict):
                r = {}
            lab = str(r.get('variant_label', '')); src = str(r.get('label_source', '')).strip().upper()
            hq = str(r.get('header_quote', '')); ql = str(r.get('qualifier', '') or '')
            f = str(r.get('field', '')); unit = str(r.get('unit', '')); vq = str(r.get('value_quote', ''))
            v = parse_value(f, r.get('value')) if f in FIELDS_NUM or f in KEYWORD else None
            segs = [(lab, None)] if ws(lab).upper() in ('', 'UNSURE') else split_label(lab, set(mp.trims))
            vqc, hqc = quote_class(vq, ptext, ptoks), quote_class(hq, ptext, ptoks)
            a = vqc == 'exact'
            b = f in asked and v is not None and value_in_quote(f, v, vq)
            # value anchors
            vsp = spans_contain(words, key(vq)) if vq.strip() else []
            vanch = [x[2] for x in vsp]
            if not vanch and f in FIELDS_NUM and v is not None:
                vanch = [box([w]) for w in words if any(abs(v - n) < 1e-9 for n in nums(w['text']))]
            hq_spans = [(i, j) for i, j, _ in spans_contain(words, key(hq))] if hq.strip() else []
            # (e) qualifier: the value's 'line' = contiguous word run around a located value_quote,
            # else the page-text line(s) holding it
            line = ' '.join(run_text(words, i, j) for i, j, _ in vsp) if vsp else page_lines_with(raw_text, vq)
            marker = bool(re.search(MARK_VALUE, ws(vq), re.I) or re.search(MARK_VALUE, ws(line), re.I)
                          or re.search(MARK_HEADER, ws(hq), re.I))
            e = (not marker) or ws(ql) != ''
            for si, (seg, tk) in enumerate(segs, 1):
                c = hqc == 'exact' and ws(seg).upper() != 'UNSURE' and ws(seg) != '' and key(seg) in key(hq)
                if tk is None and ws(seg).upper() not in ('', 'UNSURE'):
                    c_trim = trim_key(seg)
                else:
                    c_trim = tk
                d = False; dreason = ''
                if src not in ('COLUMN_HEADER', 'ROW_HEADER', 'SAME_LINE', 'SECTION_HEADING'):
                    dreason = 'bad label_source'
                elif not c_trim:
                    dreason = 'no trim'
                elif not vanch:
                    dreason = 'value not located'
                else:
                    hanch = [o for o in occ if o[3] == c_trim]
                    if hq_spans:
                        inside = [o for o in hanch if any(i <= o[0] and o[1] <= j for i, j in hq_spans)]
                        hanch = inside
                    if not hanch:
                        dreason = 'header trim not located'
                    else:
                        for vb in vanch:
                            near = nearest(src, vb, occ)
                            for h in hanch:
                                if rel(src, h[2], vb) and h in near:
                                    d = True; break
                            if d:
                                break
                        if not d:
                            dreason = 'no structural link / not nearest'
                passed = a and b and c and d and e
                mstat, mset, mwhy = mp.map(seg, tk, hq, ql, f) if f in asked else ('AMBIGUOUS', set(), 'bad field')
                known = [(x, truth[(x, f)]) for x in sorted(mset) if (x, f) in truth]
                unit_ok = f not in FIELDS_NUM or key(unit).replace('LTR', 'L') in FIELDS_NUM[f]
                if mstat != 'TRIM':
                    verdict = 'AMBIGUOUS'
                elif not unit_ok:
                    verdict = 'WRONG'
                elif not known:
                    verdict = 'UNKNOWN'
                elif all(v is not None and abs(t - v) < 1e-9 for _, t in known):
                    verdict = 'CORRECT'
                else:
                    verdict = 'WRONG'
                rows.append(dict(row_id=f'{cid}.{k}.{si}', call=cid, page=pkey, model=g['model'], source=g['prompt_source'],
                                 layout=layout.get((sha, page, f), 'other'), variant_label=lab, segment=seg,
                                 label_source=src, header_quote=hq, qualifier=ql, field=f, value=r.get('value'), unit=unit,
                                 value_quote=vq, a=int(a), b=int(b), c=int(c), d=int(d), e=int(e), d_reason=dreason,
                                 qualifier_miss=int(not e), status='PASS' if passed else 'REJECTED',
                                 value_quote_class=vqc, header_quote_class=hqc, map_status=mstat, map_note=mwhy,
                                 mapped_variants=' '.join(map(str, sorted(mset))), truth_coverage=f'{len(known)}/{len(mset)}',
                                 verdict=verdict if passed else '', verdict_diagnostic=verdict))
    # recall
    rec = []
    for gc in gold:
        pk = f"{gc['pdf_sha1']}_p{gc['page']}"; vid = int(gc['variant_id']); gv = float(gc['value'])
        hit = ''
        for r in rows:
            if r['status'] != 'PASS' or r['verdict'] != 'CORRECT' or r['page'] != pk or r['field'] != gc['field']:
                continue
            pv = parse_value(r['field'], r['value'])
            if pv is None or abs(pv - gv) > 1e-9:
                continue
            if vid in {int(x) for x in r['mapped_variants'].split()}:
                hit = r['row_id']; break
        rec.append(dict(gold_id=gc['gold_id'], pdf=gc['pdf'], page=gc['page'], source=gc['prompt_source'], layout=gc['layout'],
                        field=gc['field'], variant=gc['variant_name'], value=gc['value'], FOUND=int(bool(hit)), row=hit))
    for name, data in (('rows', rows), ('recall', rec), ('calls', calls)):
        if data:
            with open(f'{out}/{name}.tsv', 'w') as fh:
                w = csv.DictWriter(fh, fieldnames=list(data[0]), delimiter='\t'); w.writeheader(); w.writerows(data)

    def stats(R, G):
        P = [r for r in R if r['status'] == 'PASS']
        cc = sum(r['verdict'] == 'CORRECT' for r in P); ww = sum(r['verdict'] == 'WRONG' for r in P)
        n = cc + ww
        return dict(rows=len(R), passing=len(P), pass_rate=round(len(P) / len(R), 4) if R else None,
                    correct=cc, wrong=ww, with_truth=n, precision=round(cc / n, 4) if n else None,
                    wilson_lb=round(wilson_lb(cc, n), 4) if n else None,
                    unknown=sum(r['verdict'] == 'UNKNOWN' for r in P), ambiguous=sum(r['verdict'] == 'AMBIGUOUS' for r in P),
                    gold=len(G), found=sum(x['FOUND'] for x in G), recall=round(sum(x['FOUND'] for x in G) / len(G), 4) if G else None)
    ismat = lambda x: 'matrix' if x['layout'] == 'matrix' else 'non-matrix'
    m = dict(overall=stats(rows, rec))
    for s in ('text', 'ocr'):
        m[f'source={s}'] = stats([r for r in rows if r['source'] == s], [x for x in rec if x['source'] == s])
    for L in ('matrix', 'non-matrix'):
        m[f'layout={L}'] = stats([r for r in rows if ismat(r) == L], [x for x in rec if ismat(x) == L])
    for s in ('text', 'ocr'):
        for L in ('matrix', 'non-matrix'):
            m[f'type={s}/{L}'] = stats([r for r in rows if r['source'] == s and ismat(r) == L],
                                       [x for x in rec if x['source'] == s and ismat(x) == L])
    m['quotes'] = dict(value_quote=dict(Counter(r['value_quote_class'] for r in rows)),
                       header_quote=dict(Counter(r['header_quote_class'] for r in rows)))
    m['qualifier_misses'] = sum(r['qualifier_miss'] for r in rows)
    m['reject_checks'] = dict(Counter(''.join(k for k in 'abcde' if not r[k]) for r in rows if r['status'] == 'REJECTED'))
    m['d_reasons'] = dict(Counter(r['d_reason'] for r in rows if not r['d']))
    m['unsure_rows'] = sum(ws(r['variant_label']).upper() == 'UNSURE' for r in rows)
    m['raw_rows'] = sum(c['raw_rows'] for c in calls)
    o = m['overall']
    ok = lambda s: s['precision'] is not None and s['precision'] >= 0.95 and s['wilson_lb'] >= 0.90
    if o['with_truth'] < 40:
        dec = 'INCONCLUSIVE -> ALL-CLAUDE'
    elif ok(o) and o['pass_rate'] >= 0.50:
        dec = 'HYBRID'
    elif ok(o):
        types = [k[5:] for k in m if k.startswith('type=') and ok(m[k])]
        dec = f'HYBRID-LIMITED on {types}' if types else 'ALL-CLAUDE (HYBRID-LIMITED with no qualifying page type)'
    else:
        dec = 'ALL-CLAUDE'
    m['decision'] = dec
    json.dump(m, open(f'{out}/metrics.json', 'w'), indent=1)
    print(json.dumps(m, indent=1))


if __name__ == '__main__':
    main()
