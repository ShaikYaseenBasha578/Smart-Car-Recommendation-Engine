"""classified.tsv -> cells.tsv (writeable cells) + held.tsv (cells not written, with reason) + gate.json.
Usage: make_cells.py <batch_dir> <pdf_rel> <pdf_sha1>
Written: FILL, CONFIRM, CORRECTION where run a and run b agree. Never written: NOT_ON_PAGE, ABSENT_NOT_SHOWN, CONFLICT, PAGE_CONFLICT,
any cell the two runs disagree on (sent to NEEDS_YOU). Gate (P12): the validated sample (every CORRECTION + stratified >=20% of FILLs)
must agree >= 95%, else the batch is rejected."""
import csv, json, sys
bd, rel, sha = sys.argv[1:4]
R = list(csv.DictReader(open(f'{bd}/classified.tsv'), delimiter='\t'))
W, H = [], []
for r in R:
    if r['cls'] in ('FILL', 'CONFIRM', 'CORRECTION') and r['agree'] == 'True':
        old = r['kb_stored']
        W.append(dict(vid=r['vid'], col=r['field'], old=old, new=r['a'], pdf_rel=rel, pdf_sha1=sha, page=r['page'][1:] if r['page'].startswith('p') else r['page'],
                      printed=r['a_src'], qualifier=r['a_qual'], cls=r['cls'], variant=r['variant']))
    elif r['cls'] in ('FILL', 'CONFIRM', 'CORRECTION'):
        H.append(dict(vid=r['vid'], variant=r['variant'], field=r['field'], cls=r['cls'], reason=f"runs disagree: a={r['a']} b={r['b']}"))
    elif r['cls'] in ('CONFLICT', 'PAGE_CONFLICT', 'ABSENT_NOT_SHOWN'):
        H.append(dict(vid=r['vid'], variant=r['variant'], field=r['field'], cls=r['cls'], reason=r['cls']))
keys = ['vid', 'col', 'old', 'new', 'pdf_rel', 'pdf_sha1', 'page', 'printed', 'qualifier', 'cls']
with open(f'{bd}/cells.tsv', 'w') as f:
    f.write('\t'.join(keys) + '\n')
    for w in W: f.write('\t'.join(str(w[k]).replace('\t', ' ').replace('\n', ' ') for k in keys) + '\n')
with open(f'{bd}/held.tsv', 'w') as f:
    f.write('vid\tvariant\tfield\tcls\treason\n')
    for h in H: f.write('\t'.join(str(h[k]) for k in ('vid', 'variant', 'field', 'cls', 'reason')) + '\n')
sel = [r for r in R if r['validate'] == 'True']
ag = sum(1 for r in sel if r['agree'] == 'True')
g = dict(validated=len(sel), agree=ag, rate=(ag / len(sel) if sel else 1.0), passed=(ag / len(sel) >= 0.95 if sel else True), written=len(W), held=len(H))
json.dump(g, open(f'{bd}/gate.json', 'w')); print(json.dumps(g))
