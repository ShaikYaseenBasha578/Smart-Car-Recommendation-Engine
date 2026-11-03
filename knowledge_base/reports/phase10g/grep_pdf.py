"""Read-only text-layer grep of brochures. Usage: grep_pdf.py <oem_root> <regex> <relpath> ..."""
import os, re, sys, hashlib
import fitz
root, rx = sys.argv[1], re.compile(sys.argv[2], re.I)
for rel in sys.argv[3:]:
    p = os.path.join(root, rel)
    print(f"=== {rel} sha1={hashlib.sha1(open(p,'rb').read()).hexdigest()[:12]}")
    for i, pg in enumerate(fitz.open(p), 1):
        for line in pg.get_text().splitlines():
            if rx.search(line): print(f"  p{i}: {line.strip()[:150]}")
