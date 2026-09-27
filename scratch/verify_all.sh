#!/bin/bash
echo "=== AUDIT COUNTS ==="
python3 scratch/audit_counts.py

echo -e "\n=== PK DIFF PASS 1 ==="
python3 scratch/pk_diff.py

echo -e "\n=== IDEMPOTENCY PASS 2 ==="
PYTHONPATH=. python3 scratch/run_pass2.py

echo -e "\n=== PDF VALIDITY ==="
python3 scratch/verify_pdfs.py

echo -e "\n=== PRODUCTION IMMUTABILITY ==="
sqlite3 knowledge_base/carrec_kb.db "PRAGMA integrity_check;"
shasum knowledge_base/carrec_kb.db
