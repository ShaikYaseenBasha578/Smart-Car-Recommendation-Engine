"""Agreement between the deterministic scorer and the blind subagent.

Usage: python -I compare_blind.py <blind_key.tsv> <blind/answers.tsv> <out.tsv>
A row agrees when status (PASS/REJECTED) matches and, if both say PASS, the verdict matches.
"""
import csv, json, sys

key = {r['blind_id']: r for r in csv.DictReader(open(sys.argv[1]), delimiter='\t')}
ans = {r['blind_id'].strip(): r for r in csv.DictReader(open(sys.argv[2]), delimiter='\t')}
out, agree = [], 0
per = {'a': 0, 'b': 0, 'c': 0, 'status': 0}
for bid, k in sorted(key.items()):
    a = ans.get(bid, {})
    st = a.get('status', '').strip().upper()
    vd = a.get('verdict', '').strip().upper()
    ok = st == k['status'] and (k['status'] != 'PASS' or vd == k['verdict'])
    agree += ok
    for c in ('a', 'b', 'c'):
        per[c] += str(a.get(c, '')).strip() == k[c]
    per['status'] += st == k['status']
    out.append(dict(blind_id=bid, row_id=k['row_id'], arm=k['arm'], scorer_status=k['status'], blind_status=st,
                    scorer_verdict=k['verdict'], blind_verdict=vd, scorer_abc=k['a'] + k['b'] + k['c'],
                    blind_abc=''.join(str(a.get(c, '?')).strip() for c in 'abc'), agree=int(ok), note=a.get('note', '')))
w = csv.DictWriter(open(sys.argv[3], 'w'), fieldnames=list(out[0]), delimiter='\t'); w.writeheader(); w.writerows(out)
n = len(key)
print(json.dumps(dict(rows=n, answered=len(ans), agree=agree, agreement=round(agree / n, 4),
                      per_check={c: f'{v}/{n}' for c, v in per.items()}), indent=1))
