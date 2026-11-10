"""Brochure text index (read-only on brochures).

Usage: python -I build_index.py <out_index_dir> <ocr_bin> <expected_sha1>=<pdf_path> [...]

For each PDF (SHA-1 must equal the expected value, else the PDF is skipped):
  <out>/<sha1>/p<N>.txt          pdfplumber text layer
  <out>/<sha1>/p<N>.tables.json  pdfplumber extract_tables()
  <out>/<sha1>/p<N>.ocr.txt      macOS Vision OCR, only for image-only / scrambled / rotated pages,
                                 lines rebuilt into rows by y-position (left→right within a row)
  <out>/<sha1>/p<N>.words.json   word boxes of the text the prompt uses for that page:
                                 pdfplumber extract_words (method 'text') or Vision word boxes
                                 (method 'ocr'); Vision words followed by pdfplumber words
                                 ('text+ocr', whose prompt carries the layer's tables). {"coord": COORD, "source": ..., "words":
                                 [{"text", "x0", "top", "x1", "bottom", "line"}]}; "line" = Vision
                                 observation index (OCR) or null (pdfplumber).
  <out>/index.tsv                file, page, pdf_sha1, method, chars, upright, short_ratio, seconds,
                                 words_source, words, coord
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
COORD = 'normalised page coords 0..1, origin top-left, x right, y down: x0,top,x1,bottom'


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def ocr_run(ocr_bin, png):
    """Returns (rows text, words). Row grouping uses the line box (x0, top) rounded to 3 dp,
    exactly as round 1 did, so the OCR text of round-1 pages is unchanged."""
    out = subprocess.run([ocr_bin, png], capture_output=True, text=True, check=True).stdout
    items, words, line_no = [], [], -1
    for line in out.splitlines():
        parts = line.split('\t')
        if len(parts) != 3:
            continue
        x0, top, x1, bot = (float(v) for v in parts[1].split(','))
        if parts[0] == 'L':
            line_no += 1
            items.append((round(top, 3), round(x0, 3), parts[2]))
        elif parts[0] == 'W':
            words.append(dict(text=parts[2], x0=x0, top=top, x1=x1, bottom=bot, line=line_no))
    return ocr_rows_from(items), words


def ocr_rows_from(items):
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


def plumber_words(pg):
    W, H = float(pg.width), float(pg.height)
    return [dict(text=w['text'], x0=w['x0'] / W, top=w['top'] / H, x1=w['x1'] / W, bottom=w['bottom'] / H, line=None)
            for w in pg.extract_words()]


def main():
    out, ocr_bin = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    idx_path = os.path.join(out, 'index.tsv')
    new = not os.path.exists(idx_path)
    idx = open(idx_path, 'a')
    if new:
        idx.write('file\tpage\tpdf_sha1\tmethod\tchars\tupright\tshort_ratio\tseconds\twords_source\twords\tcoord\n')
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
                    o, words = ocr_run(ocr_bin, png)
                    open(os.path.join(d, f'p{i}.ocr.txt'), 'w').write(o)
                    src = 'vision'
                    if method == 'text+ocr':   # the prompt also carries pdfplumber tables of this layer
                        words = words + plumber_words(pg); src = 'vision+pdfplumber'
                    if method == 'ocr':
                        chars = len(o)
                else:
                    words, src = plumber_words(pg), 'pdfplumber'
                json.dump(dict(coord=COORD, source=src, words=words), open(os.path.join(d, f'p{i}.words.json'), 'w'),
                          ensure_ascii=False)
                idx.write(f'{os.path.basename(path)}\t{i}\t{got}\t{method}\t{chars}\t{up:.2f}\t{short:.2f}\t{time.time()-t0:.2f}'
                          f'\t{src}\t{len(words)}\t{COORD}\n')
                idx.flush()
        print(f'indexed {path} ({got})', file=sys.stderr)


if __name__ == '__main__':
    main()
