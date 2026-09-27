import sys
import os
import json
import sqlite3
sys.path.append(os.getcwd())

from knowledge_base.ingestion.oem.batch_runner_oem import resolve_oem_generation
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload

with open("knowledge_base/sources/oem/batch_report.json") as f:
    results = json.load(f)

for r in results['reports']:
    if r['model'] == 'Fronx':
        print(r)
