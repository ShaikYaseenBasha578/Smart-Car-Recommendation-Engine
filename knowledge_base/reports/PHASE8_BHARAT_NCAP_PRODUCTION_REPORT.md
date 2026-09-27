# PHASE 8 BHARAT NCAP PRODUCTION REPORT

## Execution Integrity
1. **Pre-ingestion production checksum**: `e752ebde5b7f227140bedb319c6b9753a3fdbdde`
2. **Backup checksum**: `e752ebde5b7f227140bedb319c6b9753a3fdbdde` (Verified identical to pre-ingestion)
3. **Production backup path**: `knowledge_base/backups/carrec_kb_pre_phase8_20260923210209.db`
4. **Source used**: Bharat NCAP (`bncap.in`), `source_id = 7`. Shadow corpus generated via `scratch/phase8a_shadow_ingestion_v4.py`.
11. **Integrity check result**: `ok`
13. **Post-production checksum**: `6cc95a6e8f5b0f988468366ca9dd4f6e5c10749b` (After `PRAGMA wal_checkpoint(TRUNCATE)`)

## Ingestion Scope
5. **Number of BNCAP tests ingested**: 37
6. **Number of source observations created**: 37
7. **Number of applicability rows created**: 324

## Applicability Semantics
8. **Applicability status breakdown**:
   - `EXACT_CANONICAL_VARIANT`: 13
   - `EXPLICIT_SOURCE_VARIANT_UNRESOLVED`: 291
   - `MODEL_SCOPE`: 19
   - `FAMILY_SCOPE`: 1
9. **Exact canonical variant mappings**: 13 (Deterministic, 1:1, non-fuzzy bounds only. Examples: `ALPHA 1.2L ISS 5MT` → `Alpha MT`).
10. **Explicit unresolved source variants**: 291 (Retained in shadow applicability schema to avoid poisoning canonical records with unsupported configuration mappings).

## True Logical Diff (Pre vs Post)
12. **Exact production pre/post logical diff**:
```text
table                          | added | deleted | modified
-----------------------------------------------------------------
manufacturer                   | 0     | 0       | 0       
model                          | 0     | 0       | 0       
generation                     | 0     | 0       | 0       
variant                        | 0     | 0       | 0       
powertrain                     | 0     | 0       | 0       
source                         | 0     | 0       | 0       
source_observation             | 37    | 0       | 0       
field_provenance               | 0     | 0       | 0       
safety_test                    | 37    | 0       | 0       
safety_test_applicability      | 324   | 0       | 0       
```

## Validation Gates
14. **Idempotency result**: `SUCCESS` (A duplicate pass on the post-ingestion copy yielded 0/0/0 mutations across all logical records).
15. **PDF validation result**: `SUCCESS` (37/37 PDFs checked. 0 missing, 0 zero-byte, 0 corrupt headers, 0 SHA-256 mismatches).
16. **Source completeness result**: `SUCCESS` (Discovered=37, Unique=37, Fetched=37, Parsed=37, Ingested=37).
17. **Any warnings**: None. Applicability flag isolation verified. Model-level variants accurately preserved without fabricating fake canonical variants. 

---

**FINAL VERDICT:**
**PRODUCTION_INGESTION_SUCCESS**
