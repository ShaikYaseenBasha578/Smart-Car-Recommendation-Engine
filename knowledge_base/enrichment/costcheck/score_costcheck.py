"""Deterministic scorer + pre-registered decision for the cost check. No LLM.

Usage: python -I score_costcheck.py <scratch> <out_dir>
Reads <scratch>/costcheck/runs/<page>_<arm>_r<rep>/out.json (claude -p --output-format json),
<scratch>/costcheck/inputs/manifest.json, <scratch>/work/cands.json (truth) and <scratch>/prod/q.db.

TRUTH: brochure-verified OEM observations 10E-10N (cands.json) for the page's PDF SHA-1 and page,
  keyed by (variant id, field). A cell is matched to the KB by exact variant name (whitespace-
  collapsed, case-insensitive) among the model's base variants.
CELL SCORING (per run):
  correct  FOUND cell, truth exists, value equals truth (numeric 1e-9; bool 1/0/true/false/yes/no)
  wrong    FOUND cell, truth exists, value differs (conflicting duplicate cells for one variant+field count as wrong)
  missed   a truth cell with no FOUND cell with a non-null value (absent, NOT_ON_PAGE or null)
  unknown  FOUND cell for a variant+field with no truth (listed, excluded from correct/wrong)
  invalid  cell whose variant name is not a catalogue base variant of the model (listed)
  recall = correct / truth cells on the page
QUALIFIER ERRORS (per run): QUAL_KEYS below was written from the page text before any run. For a
  key (trim, field, regex), every FOUND cell with value 1 on a variant of that trim must have a
  qualifier matching the regex (case-insensitive search); otherwise it is one qualifier error.
TOKENS (from the JSON usage): total = input + cache_creation_input + cache_read_input + output
  tokens (thinking tokens are inside output). Also reported: cost (total_cost_usd) and wall time
  (duration_ms). An overhead baseline (2 trivial runs of the same harness) is subtracted for the
  secondary 'net' figure; the decision uses the GROSS total.
DECISION (pre-registered):
  per page: mean over its 2 repeats; overall: sums over the 3 pages.
  HYBRID   if ALL: (1) sum_pages mean total tokens VERIFY <= 0.60 x EXTRACT;
                   (2) VERIFY wrong == 0 over all its runs;
                   (3) VERIFY pooled recall >= EXTRACT pooled recall - 0.05;
                   (4) VERIFY qualifier errors (all runs) <= EXTRACT's.
  else evaluate the same four conditions on each page alone (its 2 runs per arm): if at least one
  page type meets all four -> HYBRID-PARTIAL naming those page types, else ALL-CLAUDE.
"""
import csv, json, os, re, sqlite3, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
from filter_score_v2 import trim_key  # noqa: E402

QUAL_KEYS = {
    'venue_p20': [('HX5', 'paddle_shifters', r'DCT|AT'), ('HX6', 'paddle_shifters', r'DCT|AT'), ('HX8', 'paddle_shifters', r'DCT|AT'),
                  ('HX5', 'cruise_control', r'1\.0|turbo|1\.5|diesel|dsl'), ('HX6', 'cruise_control', r'DCT|AT')],
    'victoris_p16': [(t, 'paddle_shifters', r'6AT|\bAT\b|automatic') for t in ('VXI', 'ZXI', 'ZXI(O)', 'ZXI+', 'ZXI+(O)')] +
                    [(t, 'cruise_control', r'MT|hybrid|6AT|ACC|adaptive') for t in ('ZXI+', 'ZXI+(O)')],
    'syros_p7': [],
}
ARMS = ('extract', 'verify')
REPS = (1, 2)
PAGES = ('syros_p7', 'victoris_p16', 'venue_p20')


def nname(s):
    return re.sub(r'\s+', ' ', str(s)).strip().lower()


def pval(v):
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    m = {'true': 1.0, 'false': 0.0, 'yes': 1.0, 'no': 0.0}
    if s in m:
        return m[s]
    try:
        return float(s)
    except ValueError:
        return None


def parse_json(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    try:
        return json.loads(s)
    except Exception:
        a, b = s.find('{'), s.rfind('}')
        return json.loads(s[a:b + 1]) if a >= 0 and b > a else None


def usage_of(j):
    u = j.get('usage', {}) or {}
    tot = sum(u.get(k, 0) or 0 for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens'))
    return dict(input=u.get('input_tokens', 0), cache_create=u.get('cache_creation_input_tokens', 0),
                cache_read=u.get('cache_read_input_tokens', 0), output=u.get('output_tokens', 0), total=tot,
                cost=j.get('total_cost_usd'), ms=j.get('duration_ms'), turns=j.get('num_turns'), is_error=j.get('is_error'))


def main():
    scr, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    cc = f'{scr}/costcheck'
    man = json.load(open(f'{cc}/inputs/manifest.json'))
    db = sqlite3.connect(f'{scr}/prod/q.db')
    cands = json.load(open(f'{scr}/work/cands.json'))
    base = {}
    truth = {}
    for key, m in man.items():
        # model of any truth cell on the page
        tv = [r for r in cands if r['sha1'] == m['pdf_sha1'] and r['page'] == m['page']]
        mid = db.execute('select model_id from variant where id=?', (tv[0]['vid'],)).fetchone()[0]
        base[key] = {nname(n): i for i, n in db.execute('select id,name from variant where model_id=? and base_variant_id is null', (mid,))}
        truth[key] = {(r['vid'], r['field']): float(r['val']) for r in tv}
    vname = {i: n for k in base for n, i in base[k].items()}
    runs, cells_out, detail = [], [], []
    for key in PAGES:
        for arm in ARMS:
            for rep in REPS:
                d = f'{cc}/runs/{key}_{arm}_r{rep}'
                j = json.load(open(f'{d}/out.json'))
                u = usage_of(j)
                data = parse_json(j.get('result'))
                cells = (data or {}).get('cells', []) if isinstance(data, dict) else []
                review = (data or {}).get('review', []) if isinstance(data, dict) else []
                got = defaultdict(list); invalid = []; unknown = []
                for c in cells:
                    if not isinstance(c, dict):
                        continue
                    vid = base[key].get(nname(c.get('variant', '')))
                    if vid is None:
                        invalid.append(c.get('variant')); continue
                    if c.get('status') == 'FOUND' and pval(c.get('value')) is not None:
                        got[(vid, c.get('field'))].append(c)
                correct = wrong = 0
                for (vid, f), cs in got.items():
                    t = truth[key].get((vid, f))
                    vals = {pval(c['value']) for c in cs}
                    if t is None:
                        unknown.append(f'{vname[vid]}|{f}|{sorted(vals)}'); continue
                    if vals == {t}:
                        correct += 1
                    else:
                        wrong += 1; detail.append(dict(page=key, arm=arm, rep=rep, variant=vname[vid], field=f, truth=t, got=sorted(vals), qualifier=cs[0].get('qualifier')))
                missed = sum(1 for k in truth[key] if k not in got)
                qerr = 0
                for trim, f, rx in QUAL_KEYS[key]:
                    for (vid, ff), cs in got.items():
                        if ff != f or trim_key(vname[vid]) != trim.upper().replace(' ', ''):
                            continue
                        for c in cs:
                            if pval(c['value']) == 1.0 and not re.search(rx, str(c.get('qualifier', '')), re.I):
                                qerr += 1
                                detail.append(dict(page=key, arm=arm, rep=rep, variant=vname[vid], field=f, qualifier_error=True, qualifier=c.get('qualifier')))
                nt = len(truth[key])
                rv = Counter(r.get('verdict') for r in review if isinstance(r, dict))
                runs.append(dict(page=key, type=man[key]['type'], arm=arm, rep=rep, parsed=int(data is not None), cells=len(cells),
                                 truth_cells=nt, correct=correct, wrong=wrong, missed=missed, unknown=len(unknown), invalid=len(invalid),
                                 qualifier_errors=qerr, recall=round(correct / nt, 4), review=dict(rv), **u))
                for x in unknown:
                    cells_out.append(dict(page=key, arm=arm, rep=rep, unknown=x))
    base_runs = []
    for k in (1, 2):
        p = f'{cc}/runs/baseline_r{k}/out.json'
        if os.path.exists(p):
            base_runs.append(usage_of(json.load(open(p)))['total'])
    overhead = sum(base_runs) / len(base_runs) if base_runs else 0
    for name, data in (('runs', runs), ('unknown_cells', cells_out), ('detail', detail)):
        if data:
            with open(f'{out}/{name}.tsv', 'w') as fh:
                w = csv.DictWriter(fh, fieldnames=sorted({k for r in data for k in r}), delimiter='\t'); w.writeheader(); w.writerows(data)

    def sel(**kw):
        return [r for r in runs if all(r[k] == v for k, v in kw.items())]

    def agg(arm, pages):
        R = [r for r in runs if r['arm'] == arm and r['page'] in pages]
        n = len(R) / len(pages) if pages else 0
        meantok = sum(r['total'] for r in R) / max(1, len(R) // len(pages)) if R else 0
        return dict(mean_total_tokens_summed=sum(sum(r['total'] for r in R if r['page'] == p) / len(REPS) for p in pages),
                    mean_output_tokens_summed=sum(sum(r['output'] for r in R if r['page'] == p) / len(REPS) for p in pages),
                    mean_net_tokens_summed=sum(sum(r['total'] - overhead for r in R if r['page'] == p) / len(REPS) for p in pages),
                    wall_s_mean_per_run=sum(r['ms'] or 0 for r in R) / len(R) / 1000 if R else None,
                    cost_usd_mean_summed=sum(sum(r['cost'] or 0 for r in R if r['page'] == p) / len(REPS) for p in pages),
                    correct=sum(r['correct'] for r in R), wrong=sum(r['wrong'] for r in R), missed=sum(r['missed'] for r in R),
                    unknown=sum(r['unknown'] for r in R), invalid=sum(r['invalid'] for r in R),
                    qualifier_errors=sum(r['qualifier_errors'] for r in R), truth_cell_runs=sum(r['truth_cells'] for r in R),
                    recall=round(sum(r['correct'] for r in R) / sum(r['truth_cells'] for r in R), 4), runs=len(R))

    def conds(pages):
        e, v = agg('extract', pages), agg('verify', pages)
        ratio = v['mean_total_tokens_summed'] / e['mean_total_tokens_summed']
        c = dict(c1_tokens_le_60pct=ratio <= 0.60, c2_verify_wrong_zero=v['wrong'] == 0,
                 c3_recall_within_5pts=v['recall'] >= e['recall'] - 0.05, c4_qualifier_errors_le_extract=v['qualifier_errors'] <= e['qualifier_errors'])
        return dict(ratio=round(ratio, 4), saving_pct=round((1 - ratio) * 100, 1), net_ratio=round(v['mean_net_tokens_summed'] / e['mean_net_tokens_summed'], 4) if e['mean_net_tokens_summed'] > 0 else None,
                    extract=e, verify=v, conditions=c, all_met=all(c.values()))
    m = dict(overhead_baseline_total_tokens=overhead, overall=conds(PAGES), per_page={p: conds((p,)) for p in PAGES})
    if m['overall']['all_met']:
        dec = 'HYBRID'
    else:
        ok = [m['per_page'][p] and p for p in PAGES if m['per_page'][p]['all_met']]
        dec = f"HYBRID-PARTIAL: Flash for {[man[p]['type'] for p in ok]}" if ok else 'ALL-CLAUDE'
    m['decision'] = dec
    json.dump(m, open(f'{out}/metrics.json', 'w'), indent=1, default=str)
    print(json.dumps(m, indent=1, default=str))


if __name__ == '__main__':
    main()
