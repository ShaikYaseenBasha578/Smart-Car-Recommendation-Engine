report_md = """# PHASE 6 OEM PRODUCTION INGESTION FORENSIC AUDIT

## 1. Checksums & Integrity
- **Production DB checksum before**: `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Current production DB checksum**: `fa4b985bb52657013189080efee1107558ce3b3f`
- **Backup checksum**: `6ea3b931f7c157880445688665c500fb368a0c7b`
- **SQLite integrity**: Passed (`ok`)

## 2. Exact Database Diffs
- **Tables changed**: `source_observation`, `field_provenance`
- **Rows added/deleted/modified**:
  - `source_observation`: +52 rows added (IDs 3669 to 3720)
  - `field_provenance`: +7 rows added (IDs 37187 to 37193)
  - All other tables (including canonical fields in `variant` and `powertrain`): 0 changes.

## 3. Ingestion Reality Check
- **Actual ingestion-created source observations**: 52
- **Actual ingestion-created field provenance**: 7
- **Actual canonical mutations**: 0 (The 7 provenances were either 'confirmed' or 'rejected' due to conflict).

## 4. Forensic Explanations
- **Explanation of the 24,955 and 24,962 claims**: The reporting script used the query `SELECT COUNT(*) WHERE source_id = 1`. This queried the *entire historical baseline* of OEM provenance previously seeded into the database (e.g. from v6 migration), rather than isolating the rows created strictly during this transaction block.
- **Explanation of impossible per-model update counts**: Because the query counted historical rows, any model with a large pre-existing dataset (like Hyundai Venue, Kia Seltos) showed hundreds of "updates", even when extraction genuinely yielded 0 configurations during the run.

## 5. Architecture Audits
- **Silent exception audit**: `scratch/production_ingestion.py` and `scratch/idempotency_run.py` both use `except Exception: pass` around the core resolution and database update loop. This is **UNSAFE** and **REQUIRES_CHANGE**. It completely masks fatal extraction errors, DB integrity violations, and unresolved generation targets, making it impossible to distinguish between "successful with 0 updates" and "crashed".
- **Dry-run isolation audit**: **VALID**. `knowledge_base/ingestion/oem/batch_runner_oem.py` uses `shutil.copy2()` to strictly copy the prod DB to `isolated_batch_kb.db` and routes all SQLite connections to the copy. The dry-run did not leak into production.
- **Idempotency methodology audit**: **INVALID**. The idempotency script suppressed errors, relied solely on Python return values (`res['updated']`), and did not perform a byte-level or row-level snapshot comparison of the database.

## 6. Conclusions
- **Whether the previous production-ingestion report is valid**: NO. It was fundamentally flawed by incorrect reporting queries and swallowed exceptions.
- **Whether the production DB currently contains legitimate Phase 6 changes**: It contains 52 valid `source_observation` rows and 7 `field_provenance` rows, but the extraction is drastically underperforming because `OEM_FIELD_RULES` in `field_map_oem.py` is severely incomplete. It lacks mappings for almost all non-Maruti features, discarding extracted data before it reaches the DB.
- **Whether rollback is recommended**: YES. While the changes are small and technically safe, the run was executed under a flawed script that suppressed exceptions. A pristine database state must be restored before attempting to fix the field mappings.
- **Exact next action required**: 
  1. Restore production DB from backup.
  2. Remove all `except Exception: pass` blocks from ingestion scripts.
  3. Expand `OEM_FIELD_RULES` in `field_map_oem.py` to cover the full spectrum of extracted OEM brochure fields.
"""

with open("knowledge_base/reports/PHASE6_OEM_PRODUCTION_INGESTION_FORENSIC_AUDIT.md", "w") as f:
    f.write(report_md)
print("Forensic report generated.")
