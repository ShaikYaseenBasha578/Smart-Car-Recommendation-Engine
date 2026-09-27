import json
import sqlite3

report_path = "knowledge_base/sources/oem/batch_report.json"
db_path = "knowledge_base/isolated_batch_kb.db"

with open(report_path) as f:
    r = json.load(f)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

output = ["# DRY RUN REPORT\n"]

agg = {
    'configs_extracted': 0,
    'configs_resolved': 0,
    'configs_unresolved': 0,
    'proposed_updates': 0,
    'accepted_updates': 0,
    'rejected_skipped': 0,
    'provenance_observations': 0,
    'conflicts': 0,
    'failures': len(r.get('EXTRACTION_FAILURE', [])) + len(r.get('RESOLUTION_FAILURE', [])) + len(r.get('PDF_TEXT_FAILURE', []))
}

for rep in r['reports']:
    make = rep['make']
    model = rep['model']
    # Query DB to get field updates
    # We want to find all source_observations created in this run. 
    # Since isolated_batch_kb is copied from prod, any source_observation where source_id = 1 (OEM) 
    # Wait, OEM source_id in ingest_oem.py is hardcoded as `1`. Wait, is it `1`?
    # ingest_oem.py: process_oem_payload(conn, payloads, make_slug, model_slug, 1, gen_id)
    # Yes, source_id = 1.
    
    # Actually, to isolate this run's insertions from historical, we can look at the MAX(id) before run?
    # Or we can just count all field_provenance for source_observation where source_id = 1 and variant's make/model match.
    # We assume previous OEM observations might exist, but wait! The previous Option B run was on isolated DB, production doesn't have Phase 6 OEM observations yet!
    # Let's count them!
    
    c.execute('''
        SELECT fp.decision, COUNT(*) as cnt
        FROM field_provenance fp
        JOIN source_observation so ON fp.source_observation_id = so.id
        JOIN variant v ON fp.variant_id = v.id
        JOIN generation g ON v.generation_id = g.id
        JOIN model m ON g.model_id = m.id
        JOIN manufacturer mk ON m.manufacturer_id = mk.id
        WHERE so.source_id = 1 AND LOWER(mk.name) = ? AND LOWER(m.name) = ?
        GROUP BY fp.decision
    ''', (make.lower().strip(), model.lower().strip()))
    
    fp_stats = {row['decision']: row['cnt'] for row in c.fetchall()}
    
    accepted = fp_stats.get('accepted', 0)
    confirmed = fp_stats.get('confirmed', 0)
    rejected = fp_stats.get('rejected', 0)
    
    proposed = accepted + confirmed + rejected
    
    agg['configs_extracted'] += rep['configs_extracted']
    agg['configs_resolved'] += rep['configs_resolved']
    agg['configs_unresolved'] += rep['configs_unresolved']
    agg['proposed_updates'] += proposed
    agg['accepted_updates'] += accepted
    agg['rejected_skipped'] += (confirmed + rejected)
    agg['provenance_observations'] += proposed
    agg['conflicts'] += rejected
    
    output.append(f"## {make} {model}")
    output.append(f"- Brochure: {rep['brochure_path']}")
    output.append(f"- Strategy: {rep['classifier']}")
    output.append(f"- Extraction Status: {rep['extraction_status']} | Resolution Status: {rep['resolution_status']}")
    output.append(f"- Configs Extracted: {rep['configs_extracted']} | Resolved: {rep['configs_resolved']} | Unresolved: {rep['configs_unresolved']}")
    output.append(f"- Fields Proposed: {proposed}")
    output.append(f"- Fields Accepted/Updated: {accepted}")
    output.append(f"- Fields Skipped (Already Populated/Confirmed): {confirmed}")
    output.append(f"- Fields Rejected (Conflicts/Authority): {rejected}")
    if rep['errors']:
        output.append(f"- Errors: {rep['errors']}")
    output.append("")

output.append("## AGGREGATE METRICS")
for k, v in agg.items():
    output.append(f"- {k}: {v}")

with open("scratch/dry_run_report.md", "w") as f:
    f.write("\n".join(output))
print("Dry run report logic ready!")
