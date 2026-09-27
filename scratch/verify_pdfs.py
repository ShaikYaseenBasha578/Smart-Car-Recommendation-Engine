import fitz, os, hashlib, sqlite3

conn = sqlite3.connect('scratch/carrec_kb_phase8a_shadow.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT artifact_path, artifact_checksum FROM safety_test WHERE artifact_path IS NOT NULL").fetchall()

failures = {
    'missing': 0,
    'zero_byte': 0,
    'invalid_header': 0,
    'pymupdf_error': 0,
    'no_pages': 0,
    'hash_mismatch': 0
}

for r in rows:
    path = r['artifact_path']
    expected_hash = r['artifact_checksum']
    
    if not os.path.exists(path):
        failures['missing'] += 1
        continue
    if os.path.getsize(path) == 0:
        failures['zero_byte'] += 1
        continue
        
    with open(path, 'rb') as f:
        header = f.read(5)
        if header != b'%PDF-':
            failures['invalid_header'] += 1
            
        f.seek(0)
        actual_hash = hashlib.sha256(f.read()).hexdigest()
        if actual_hash != expected_hash:
            failures['hash_mismatch'] += 1

    try:
        doc = fitz.open(path)
        if doc.page_count <= 0:
            failures['no_pages'] += 1
    except Exception as e:
        print(f"PyMuPDF error on {path}: {e}")
        failures['pymupdf_error'] += 1

print("--- PDF VALIDITY ---")
print(f"Total PDFs Checked: {len(rows)}")
for k, v in failures.items():
    print(f"{k}: {v}")
