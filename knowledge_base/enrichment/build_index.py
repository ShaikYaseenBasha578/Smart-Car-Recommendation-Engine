"""Brochure text index (read-only on brochures).

Usage: python -I build_index.py <out_index_dir> <ocr_bin> <expected_sha1>=<pdf_path> [...]

For each PDF (SHA-1 must equal the expected value, else the PDF is skipped):
  <out>/<sha1>/p<N>.txt          pdfplumber text layer
  <out>/<sha1>/p<N>.tables.json  pdfplumber extract_tables()
  <out>/<sha1>/p<N>.ocr.txt      macOS Vision OCR, only for image-only / scrambled / rotated pages,
                                 lines rebuilt into rows by y-position (left→right within a row)
  <out>/index.tsv                file, page, pdf_sha1, method, chars, upright, short_ratio, seconds
method: text | ocr (no usable text layer) | text+ocr (text layer present but scrambled/rotated;
the pilot feeds OCR for these pages).
Nothing is written next to the PDFs; renders go to <out>/<sha1>/png/.
"""
import hashlib, json, os, subprocess, sys, time
import pdfplumber, pypdfium2

MIN_CHARS = 50          # below this the page is treated as image-only
SHORT_RATIO = 0.45      # share of 1-char tokens above which the layer is "scrambled"
UPRIGHT_MIN = 0.80      # share of upright chars below which the page is "rotated"
DPI = 200


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def ocr_rows(ocr_bin, png):
    out = subprocess.run([ocr_bin, png], capture_output=True, text=True, check=True).stdout
    items = []
    for line in out.splitlines():
        parts = line.split('\t')
        if len(parts) != 3:
            continue
        x, y = (float(v) for v in parts[1].split(','))
        items.append((y, x, parts[2]))
    items.sort()
    rows, cur, cy = [], [], None
    for y, x, t in items:
        if cy is not None and abs(y - cy) > 0.006:
            rows.append(cur); cur = []
        if not cur:
            cy = y
        cur.append((x, t))
    if cur:
        rows.append(cur)
    return '\n'.join('   '.join(t for _, t in sorted(r)) for r in rows) + '\n'


def main():
    out, ocr_bin = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    idx_path = os.path.join(out, 'index.tsv')
    new = not os.path.exists(idx_path)
    idx = open(idx_path, 'a')
    if new:
        idx.write('file\tpage\tpdf_sha1\tmethod\tchars\tupright\tshort_ratio\tseconds\n')
    for arg in sys.argv[3:]:
        exp, path = arg.split('=', 1)
        got = sha1(path)
        if got != exp:
            print(f'SKIP sha1 mismatch {path}: {got} != {exp}', file=sys.stderr); continue
        d = os.path.join(out, got); os.makedirs(os.path.join(d, 'png'), exist_ok=True)
        pdfium = pypdfium2.PdfDocument(path)
        with pdfplumber.open(path) as pdf:
            for i, pg in enumerate(pdf.pages, 1):
                t0 = time.time()
                text = pg.extract_text() or ''
                tables = pg.extract_tables() or []
                ch = pg.chars
                up = sum(1 for c in ch if c.get('upright', True)) / len(ch) if ch else 0.0
                w = text.split()
                short = sum(1 for x in w if len(x) == 1) / len(w) if w else 0.0
                open(os.path.join(d, f'p{i}.txt'), 'w').write(text)
                json.dump(tables, open(os.path.join(d, f'p{i}.tables.json'), 'w'), ensure_ascii=False)
                if len(text.strip()) < MIN_CHARS:
                    method = 'ocr'
                elif short > SHORT_RATIO or up < UPRIGHT_MIN:
                    method = 'text+ocr'
                else:
                    method = 'text'
                chars = len(text)
                if method != 'text':
                    png = os.path.join(d, 'png', f'p{i}_{DPI}.png')
                    pdfium[i - 1].render(scale=DPI / 72).to_pil().save(png)
                    o = ocr_rows(ocr_bin, png)
                    open(os.path.join(d, f'p{i}.ocr.txt'), 'w').write(o)
                    if method == 'ocr':
                        chars = len(o)
                idx.write(f'{os.path.basename(path)}\t{i}\t{got}\t{method}\t{chars}\t{up:.2f}\t{short:.2f}\t{time.time()-t0:.2f}\n')
                idx.flush()
        print(f'indexed {path} ({got})', file=sys.stderr)


if __name__ == '__main__':
    main()
