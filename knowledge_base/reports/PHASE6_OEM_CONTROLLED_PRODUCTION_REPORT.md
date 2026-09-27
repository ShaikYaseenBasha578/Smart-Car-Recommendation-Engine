# PHASE 6 OEM CONTROLLED PRODUCTION INGESTION REPORT

**Execution Date:** 2026-09-13  
**Authorized By:** Production gate passed after forensic audit, mapping repair, semantic audit, idempotency validation, and corpus mapping audit.

---

## FINAL VERDICT

```
PRODUCTION_INGESTION_SUCCESS
```

---

## 1. CHECKSUM CHAIN

| Checkpoint | SHA1 |
|---|---|
| Pre-run production | `6ea3b931f7c157880445688665c500fb368a0c7b` |
| Backup (pre-production) | `6ea3b931f7c157880445688665c500fb368a0c7b` |
| Post-run production | `e752ebde5b7f227140bedb319c6b9753a3fdbdde` |

Pre-run checksum matched expected pristine value exactly — ingestion was authorized to proceed.

---

## 2. SQLITE INTEGRITY

| Stage | Result |
|---|---|
| Pre-run `PRAGMA integrity_check` | `ok` |
| Post-run `PRAGMA integrity_check` | `ok` |
| Backup integrity | `ok` |

---

## 3. PRE/POST ROW COUNTS

| Table | Pre-run | Post-run | Delta |
|---|---|---|---|
| manufacturer | 12 | 12 | 0 |
| model | 62 | 62 | 0 |
| generation | 62 | 62 | 0 |
| variant | 832 | 832 | 0 |
| powertrain | 131 | 131 | 0 |
| source_observation | 3362 | 3414 | **+52** |
| field_provenance | 36312 | 36445 | **+133** |

---

## 4. 62-MODEL STATUS TABLE

| Model | Status |
|---|---|
| Honda Amaze | SUCCESS |
| Honda City | SUCCESS |
| Honda Elevate | PDF_TEXT_FAILURE |
| Hyundai Aura | SUCCESS |
| Hyundai Creta | SUCCESS |
| Hyundai Exter | SUCCESS |
| Hyundai Grand i10 Nios | SUCCESS |
| Hyundai Venue | EXTRACTION_FAILURE |
| Hyundai Verna | EXTRACTION_FAILURE |
| Kia Carens Clavis | EXTRACTION_FAILURE |
| Kia Carens Clavis EV | SUCCESS |
| Kia Seltos | PDF_TEXT_FAILURE |
| Kia Syros | PDF_TEXT_FAILURE |
| MG Hector | SUCCESS |
| MG Windsor EV | SUCCESS |
| Mahindra Bolero | EXTRACTION_FAILURE |
| Mahindra Scorpio Classic | SUCCESS |
| Mahindra Scorpio-N | RESOLUTION_FAILURE |
| Mahindra Thar | SUCCESS |
| Mahindra Thar Roxx | PDF_TEXT_FAILURE |
| Mahindra XUV 3XO | SUCCESS |
| Mahindra XUV 7XO | PDF_TEXT_FAILURE |
| Maruti Suzuki Alto K10 | EXTRACTION_FAILURE |
| Maruti Suzuki Baleno | SUCCESS |
| Maruti Suzuki Brezza | SUCCESS |
| Maruti Suzuki Dzire | SUCCESS |
| Maruti Suzuki Eeco | PDF_TEXT_FAILURE |
| Maruti Suzuki Ertiga | PDF_TEXT_FAILURE |
| Maruti Suzuki Fronx | SUCCESS |
| Maruti Suzuki Grand Vitara | PDF_TEXT_FAILURE |
| Maruti Suzuki Jimny | SUCCESS |
| Maruti Suzuki S-Presso | PDF_TEXT_FAILURE |
| Maruti Suzuki Swift | SUCCESS |
| Maruti Suzuki Victoris | SUCCESS |
| Maruti Suzuki WagonR | PDF_TEXT_FAILURE |
| Maruti Suzuki XL6 | SUCCESS |
| Maruti Suzuki e VITARA | SUCCESS |
| Nissan Gravite | EXTRACTION_FAILURE |
| Nissan Magnite | EXTRACTION_FAILURE |
| Renault Duster | EXTRACTION_FAILURE |
| Renault Triber | EXTRACTION_FAILURE |
| Skoda Kushaq | SUCCESS |
| Skoda Kylaq | SUCCESS |
| Skoda Slavia | SUCCESS |
| Tata Altroz | CLASSIFICATION_UNKNOWN (FeatureListStrategy quarantined) |
| Tata Harrier | CLASSIFICATION_UNKNOWN (FeatureListStrategy quarantined) |
| Tata Nexon | CLASSIFICATION_UNKNOWN (FeatureListStrategy quarantined) |
| Tata Nexon EV | CLASSIFICATION_UNKNOWN (FeatureListStrategy quarantined) |
| Tata Punch EV | CLASSIFICATION_UNKNOWN (FeatureListStrategy quarantined) |
| Tata Tiago | EXTRACTION_FAILURE |
| Tata Tiago EV | EXTRACTION_FAILURE |
| Tata Tigor | CLASSIFICATION_UNKNOWN (FeatureListStrategy quarantined) |
| Toyota Fortuner | EXTRACTION_FAILURE |
| Toyota Glanza | SUCCESS |
| Toyota Hilux | EXTRACTION_FAILURE |
| Toyota Innova Crysta | EXTRACTION_FAILURE |
| Toyota Innova Hycross | SUCCESS |
| Toyota Rumion | EXTRACTION_FAILURE |
| Toyota Urban Cruiser Hyryder | PDF_TEXT_FAILURE |
| Toyota Urban Cruiser Taisor | PDF_TEXT_FAILURE |
| Volkswagen Taigun | SUCCESS |
| Volkswagen Virtus | SUCCESS |

### Status Summary

| Status | Count |
|---|---|
| SUCCESS | 28 |
| PDF_TEXT_FAILURE | 12 |
| EXTRACTION_FAILURE | 15 |
| CLASSIFICATION_UNKNOWN | 6 |
| RESOLUTION_FAILURE | 1 |
| UNEXPECTED_ERROR | **0** |

---

## 5. SOURCE OBSERVATION ADDITIONS

**Total new source_observation rows: 52**  
Row IDs: sequential from 3363 to 3414  
All rows confirmed with:
- `source_id = 1` (OEM source)
- `extraction_method = "rsc_payload"`
- `resolution_status = "resolved"` where applicable
- No duplicate observation creation

---

## 6. FIELD PROVENANCE ADDITIONS

**Total new field_provenance rows: 133**

| Decision | Count |
|---|---|
| ACCEPTED | 1 |
| CONFIRMED | 104 |
| REJECTED | 28 |
| Other | 0 |

Only rows created by this run are counted (derived from pre/post table diff, not historical filtering by source_id).

---

## 7. CANONICAL MUTATIONS

### Expected Mutation — VERIFIED

| Field | Value |
|---|---|
| Table | `variant` |
| Variant ID | `669` |
| Field | `paddle_shifters` |
| Old value | `NULL` (Unknown) |
| New value | `0` (False) |
| Justification | OEM brochure explicitly marks `"-"` for paddle shifters, which after semantic normalizer patch correctly resolves to `0` (verified absence) |

### All Other Canonical Tables

| Table | Added | Deleted | Modified |
|---|---|---|---|
| manufacturer | 0 | 0 | 0 |
| model | 0 | 0 | 0 |
| generation | 0 | 0 | 0 |
| variant | 0 | 0 | **1 (expected, verified)** |
| powertrain | 0 | 0 | 0 |

No unexpected canonical mutations. CLASSIFICATION: ALL EXPECTED.

---

## 8. POST-PRODUCTION ISOLATED IDEMPOTENCY CHECK

An isolated copy was created at:
```
scratch/carrec_kb_phase6_postproduction_idempotency.db
```

The complete ingestion pipeline was re-run against that isolated copy.

| Table | Added | Deleted | Modified |
|---|---|---|---|
| manufacturer | 0 | 0 | 0 |
| model | 0 | 0 | 0 |
| generation | 0 | 0 | 0 |
| variant | 0 | 0 | 0 |
| powertrain | 0 | 0 | 0 |
| source_observation | 0 | 0 | 0 |
| field_provenance | 0 | 0 | 0 |

**IDEMPOTENCY: TRUE**

---

## 9. UNEXPECTED ERRORS

**Unexpected errors during this run: 0**

All non-SUCCESS outcomes were expected, pre-classified failure categories:

- `EXTRACTION_FAILURE`: borderless feature matrix could not be located (known limitation, fail-closed)
- `CLASSIFICATION_UNKNOWN`: FeatureListStrategy is quarantined and not yet production-capable (intentional)
- `PDF_TEXT_FAILURE`: PDF contains no machine-readable text (CID encoding or image-only)
- `RESOLUTION_FAILURE`: Generation pinning returned 0 matches (Scorpio-N: DB name mismatch, known issue)

No `UNEXPECTED_ERROR` statuses were observed. No silent exception suppression occurred.

---

## 10. TRANSACTION SAFETY

- Every model processed with explicit `BEGIN TRANSACTION` / `COMMIT` / `ROLLBACK`
- Rollback was invoked on every non-SUCCESS outcome
- No partial writes remain in production DB
- `isolation_level = None` was used for full manual transaction control

---

## 11. ROLLBACK STATUS

Rollback was **NOT required**. The ingestion completed cleanly.

The backup remains available at:
```
scratch/carrec_kb_phase6_final_preproduction_backup.db
```
Backup checksum: `6ea3b931f7c157880445688665c500fb368a0c7b`

---

## 12. FINAL PRODUCTION VERDICT

```
PRODUCTION_INGESTION_SUCCESS
```

**All success criteria met:**

- [x] Production transaction completed safely
- [x] No unexpected errors (0 UNEXPECTED_ERROR statuses)
- [x] No unexpected canonical mutations
- [x] Variant 669 `paddle_shifters` mutation matches the validated semantic result (NULL → 0)
- [x] Provenance reconciles exactly (133 rows: 1 accepted, 104 confirmed, 28 rejected, 0 other)
- [x] Post-run SQLite integrity check: `ok`
- [x] Post-production isolated idempotency passes (all tables 0/0/0)
- [x] No silent exception suppression anywhere in the execution path
