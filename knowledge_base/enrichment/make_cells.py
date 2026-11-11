"""classified.tsv -> cells.tsv (writeable cells) + held.tsv (cells not written, with reason) + gate.json.
Usage: make_cells.py <batch_dir> <pdf_rel> <pdf_sha1>
Written: FILL, CONFIRM, CORRECTION; a validated cell (every CORRECTION + the sampled FILLs) only if the blind run b agrees; the rest rest on run a. Never written: NOT_ON_PAGE, ABSENT_NOT_SHOWN, CONFLICT, PAGE_CONFLICT,
any validated cell the blind run b disagrees on (sent to NEEDS_YOU). Gate (P12): the validated sample (every CORRECTION + stratified >=20% of FILLs)
must agree >= 95%, else the batch is rejected."""
import csv, json, sys
bd, rel, sha = sys.argv[1:4]
R = list(csv.DictReader(open(f'{bd}/classified.tsv'), delimiter='\t'))
import re
FOOT = re.compile(r'disclaimer|footnote|\*\s*available', re.I)
W, H = [], []
# one cell can appear on several pages. Choose a page whose reading does not rest on a footnote; a 0 that rests only on a footnote
# (Nexon "*Disclaimer: Available in AMT / DCA") is held for any class: the same model reads the same footnote the same way in both
# runs, so agreement proves nothing. P6: unclear is recorded, not written.
groups = {}
for r in R:
    if r['cls'] in ('FILL', 'CONFIRM', 'CORRECTION') and (r['validate'] != 'True' or r['agree'] == 'True'):
        groups.setdefault((r['vid'], r['field']), []).append(r)
    elif r['cls'] in ('FILL', 'CONFIRM', 'CORRECTION'):
        H.append(dict(vid=r['vid'], variant=r['variant'], field=r['field'], cls=r['cls'], reason=f"runs disagree: a={r['a']} b={r['b']}"))
    elif r['cls'] in ('CONFLICT', 'PAGE_CONFLICT', 'ABSENT_NOT_SHOWN'):
        H.append(dict(vid=r['vid'], variant=r['variant'], field=r['field'], cls=r['cls'], reason=r['cls']))
for (vid, f), rs in groups.items():
    ok = [r for r in rs if not (r['a'] in ('0', '0.0') and FOOT.search(r['a_src'] + ' ' + r['a_qual']))]
    if not ok:
        r = rs[0]; H.append(dict(vid=vid, variant=r['variant'], field=f, cls='FOOTNOTE_REVIEW', reason=f"0 rests on a footnote: {r['a_src'][:90]}")); continue
    r = ok[0]
    W.append(dict(vid=r['vid'], col=r['field'], old=r['kb_stored'], new=r['a'], pdf_rel=rel, pdf_sha1=sha, page=r['page'][1:] if r['page'].startswith('p') else r['page'],
                  printed=r['a_src'], qualifier=r['a_qual'], cls=r['cls'], variant=r['variant']))
keys = ['vid', 'col', 'old', 'new', 'pdf_rel', 'pdf_sha1', 'page', 'printed', 'qualifier', 'cls']
with open(f'{bd}/cells.tsv', 'w') as f:
    f.write('\t'.join(keys) + '\n')
    for w in W: f.write('\t'.join(str(w[k]).replace('\t', ' ').replace('\n', ' ') for k in keys) + '\n')
with open(f'{bd}/held.tsv', 'w') as f:
    f.write('vid\tvariant\tfield\tcls\treason\n')
    for h in H: f.write('\t'.join(str(h[k]) for k in ('vid', 'variant', 'field', 'cls', 'reason')) + '\n')
sel = [r for r in R if r['validate'] == 'True' and r['agree'] != '']
ag = sum(1 for r in sel if r['agree'] == 'True')
g = dict(validated=len(sel), agree=ag, rate=(ag / len(sel) if sel else 1.0), passed=(ag / len(sel) >= 0.95 if sel else True), written=len(W), held=len(H))
json.dump(g, open(f'{bd}/gate.json', 'w')); print(json.dumps(g))
