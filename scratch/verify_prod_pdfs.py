import sqlite3
import os
import hashlib
import fitz # PyMuPDF

PROD_DB = "knowledge_base/carrec_kb.db"
conn = sqlite3.connect(PROD_DB)
rows = conn.execute("SELECT artifact_path, artifact_checksum FROM safety_test").fetchall()
conn.close()

missing = 0
zero_byte = 0
invalid_header = 0
pymupdf_error = 0
no_pages = 0
hash_mismatch = 0

for row in rows:
    path = row[0]
    expected_hash = row[1]
    
    if not os.path.exists(path):
        missing += 1
        continue
        
    size = os.path.getsize(path)
    if size == 0:
        zero_byte += 1
        continue
        
    with open(path, 'rb') as f:
        header = f.read(4)
        if header != b'%PDF':
            invalid_header += 1
            
        f.seek(0)
        actual_hash = hashlib.sha256(f.read()).hexdigest()
        if actual_hash != expected_hash:
            hash_mismatch += 1
            
    try:
        doc = fitz.open(path)
        if len(doc) == 0:
            no_pages += 1
        doc.close()
    except Exception:
        pymupdf_error += 1

print(f"Total PDFs Checked: {len(rows)}")
print(f"missing: {missing}")
print(f"zero_byte: {zero_byte}")
print(f"invalid_header: {invalid_header}")
print(f"pymupdf_error: {pymupdf_error}")
print(f"no_pages: {no_pages}")
print(f"hash_mismatch: {hash_mismatch}")
