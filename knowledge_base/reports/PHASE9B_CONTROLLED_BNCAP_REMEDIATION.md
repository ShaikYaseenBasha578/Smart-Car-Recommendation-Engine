# Phase 9B — Controlled BNCAP Remediation Report

**Audit date:** 2026-09-26  
**Scope:** Controlled production remediation of 3 BNCAP `safety_test` records (Thar Roxx, Brezza, Dzire) established in Phase 9A.  

---

## 1. Pre-Production Verification

| Metric | Value | Result |
|--------|-------|--------|
| Pre-production Checksum | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ MATCH |
| Backup Checksum | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ MATCH |
| Pre-production Integrity | `ok` | ✅ PASS |

**Target Identification (Pre-state):**
*   **Thar Roxx** (`safety_test.id` = 9):
    *   `tested_vehicle_name`: `MAHINDRA – THAR ROXX`
    *   `resolution_status`: `UNRESOLVED`
    *   `resolution_justification`: `Multiple model matches: [53, 54].`
    *   `source_observation_id`: 3729
*   **Brezza** (`safety_test.id` = 16):
    *   `tested_vehicle_name`: `MARUTI – BREZZA`
    *   `resolution_status`: `UNRESOLVED`
    *   `resolution_justification`: `Could not identify manufacturer from title: "MARUTI – BREZZA"`
    *   `source_observation_id`: 3736
*   **Dzire** (`safety_test.id` = 17):
    *   `tested_vehicle_name`: `MARUTI – DZIRE – GASOLINE`
    *   `resolution_status`: `UNRESOLVED`
    *   `resolution_justification`: `Could not identify manufacturer from title: "MARUTI – DZIRE – GASOLINE"`
    *   `source_observation_id`: 3737

**INTENDED CHANGE:**
*   Modify exactly the 3 target `safety_test` records (id: 9, 16, 17) to `resolution_status` = `RESOLVED`.
*   Insert exactly 3 `safety_test_applicability` mappings linking to their respective `model_id` (54, 7, 13) at `MODEL_LEVEL` with `variant_id` = `NULL`.
*   Zero unrelated records modified, deleted, or added.

---

## 2. Production Remediation Execution

The controlled remediation transaction was executed against the production database `knowledge_base/carrec_kb.db`.

**Exact Applied Mappings:**
1.  **Thar Roxx** (st_id: 9) -> `manufacturer_id`: 5, `model_id`: 54, `generation_id`: 22, `match_confidence`: `MODEL_LEVEL`, `variant_id`: `NULL`
2.  **Brezza** (st_id: 16) -> `manufacturer_id`: 6, `model_id`: 7, `generation_id`: 24, `match_confidence`: `MODEL_LEVEL`, `variant_id`: `NULL`
3.  **Dzire** (st_id: 17) -> `manufacturer_id`: 6, `model_id`: 13, `generation_id`: 28, `match_confidence`: `MODEL_LEVEL`, `variant_id`: `NULL`

---

## 3. Post-Production Delta Audit

### ACTUAL CHANGE summary:

| Table | Backup Rows | Production Rows | Additions | Deletions | Modifications |
|-------|-------------|-----------------|-----------|-----------|---------------|
| `safety_test` | 37 | 37 | 0 | 0 | **3 (Expected)** |
| `safety_test_applicability` | 20 | 23 | **3 (Expected)** | 0 | 0 |
| `manufacturer` | 12 | 12 | 0 | 0 | 0 |
| `model` | 62 | 62 | 0 | 0 | 0 |
| `generation` | 62 | 62 | 0 | 0 | 0 |
| `variant` | 832 | 832 | 0 | 0 | 0 |
| `powertrain` | 131 | 131 | 0 | 0 | 0 |
| `source_observation` | 3,451 | 3,451 | 0 | 0 | 0 |
| `field_provenance` | 36,445 | 36,445 | 0 | 0 | 0 |
| `safety_rating` | 27 | 27 | 0 | 0 | 0 |
| `source` | 8 | 8 | 0 | 0 | 0 |

**Delta Audit Result:** ✅ PASS — Only the exact 3 intended modifications to `safety_test` and 3 intended additions to `safety_test_applicability` occurred. 

---

## 4. Semantic Validation

All 3 newly added `safety_test_applicability` rows (ids: 21, 22, 23) were validated:
*   References to `safety_test_id` match correctly (9, 16, 17).
*   References to `model_id` match intended targets (54, 7, 13).
*   `variant_id` = `NULL` for all three.
*   `match_confidence` = `MODEL_LEVEL` for all three.
*   Original safety-test provenance was strictly preserved without variant-level inferences.

---

## 5. Provenance & Artifact Validation

The 3 affected `safety_test` records were cross-checked:
*   `source_id` remains 7 (Bharat NCAP).
*   `source_observation_id` unchanged (3729, 3736, 3737) and exist in the `source_observation` table.
*   `artifact_path` and `artifact_checksum` values are intact and identical to pre-production.
*   **Local PDF Artifact Check:** SHA-256 sums for the 3 target PDFs in `scratch/bncap_pdfs/` were actively re-verified against the database string values. They matched perfectly.

---

## 6. Idempotency Test

A secondary isolated copy of the **post-production** database was generated (`scratch/phase9b_idempotency_test.db`). The Phase 9B remediation logic was rerun against it.
*   **Result:** 0 additions, 0 deletions, 0 modifications.
*   The script safely skipped all rows, recognizing the `resolution_status` as `RESOLVED`.
*   **Idempotency Result:** ✅ PASS

---

## 7. Canonical-Table Immutability

The core hierarchical structure representing CarRec vehicles (Manufacturer, Model, Generation, Variant, Powertrain) experienced exactly **zero modifications**. No canonical facts were altered. 

---

## 8. Post-Production Final Verification

| Metric | Value | Result |
|--------|-------|--------|
| Post-production Integrity | `ok` | ✅ PASS |
| New Production Checksum | `1e3eb6795452860276eca24e7dd1f52e85e67a93` | ✅ CONFIRMED DELTA |
| Unrelated Anomalies | None | ✅ PASS |

---

## 9. Final Verdict

PHASE 9B FINAL VERDICT:
**PASS**
