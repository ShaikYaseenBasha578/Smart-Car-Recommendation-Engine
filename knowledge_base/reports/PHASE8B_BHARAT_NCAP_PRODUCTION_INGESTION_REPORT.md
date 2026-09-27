# Phase 8B — Bharat NCAP Production Ingestion Report

## Objective
Safely apply the Phase 8A Bharat NCAP ingestion logic to the production `carrec_kb.db`, verifying integrity, checksums, logical diffs, and idempotency.

## 1. Pre-Run Verification
- **Expected pristine checksum**: `e752ebde5b7f227140bedb319c6b9753a3fdbdde`
- **Actual production checksum**: `e752ebde5b7f227140bedb319c6b9753a3fdbdde` (Match)
- **Backup checksum**: `e752ebde5b7f227140bedb319c6b9753a3fdbdde`
- **Backup location**: `knowledge_base/backups/carrec_kb_phase8b_backup.db`
- **Pre-run PRAGMA integrity_check**: `ok`

## 2. Ingestion Results
The validated BNCAP entity resolution and ingestion script was applied with explicit transaction management.

### Entity Resolution Breakdown (37 Tests Total)
- **RESOLVED (Model/Family Level)**: 20
- **UNRESOLVED (Ambiguous matches)**: 7
- **NO_MATCH (Not in CarRec DB)**: 10

### Logical Table Diffs
| Table | Pre-Run Rows | Post-Run Rows | Added | Deleted | Modified |
|-------|--------------|---------------|-------|---------|----------|
| `manufacturer` | 12 | 12 | 0 | 0 | 0 |
| `model` | 62 | 62 | 0 | 0 | 0 |
| `generation` | 62 | 62 | 0 | 0 | 0 |
| `variant` | 832 | 832 | 0 | 0 | 0 |
| `powertrain` | 131 | 131 | 0 | 0 | 0 |
| `source` | 8 | 8 | 0 | 0 | 0 |
| `source_observation` | 3414 | 3451 | 37 | 0 | 0 |
| `field_provenance` | 36445 | 36445 | 0 | 0 | 0 |
| `safety_test` | 0 | 37 | 37 | 0 | 0 |
| `safety_test_applicability` | 0 | 20 | 20 | 0 | 0 |

**Canonical Mutation Verdict:** ZERO canonical mutations found. Strict safety mapping preserved.

## 3. Post-Run Verification
- **Post-run production checksum**: `c1e0647ce463c98eebd9d2bd9470940fdb23ead5`
- **Post-run PRAGMA integrity_check**: `ok`

### Idempotency Check
An isolated copy of the post-production DB (`scratch/carrec_kb_phase8b_isolated.db`) was created and subjected to the exact same ingestion process.
- **Idempotency Verdict**: PASSED. 0 additions, 0 deletions, and 0 modifications across all tables on the second pass.

---

## 5. Phase 8B Closeout Audit

Performed: 2026-09-25. Read-only. No production mutations.

### 5.1 Production Checksum
- **Known Phase 8B post-production checksum**: `c1e0647ce463c98eebd9d2bd9470940fdb23ead5`
- **Measured checksum (SHA-1)**: `c1e0647ce463c98eebd9d2bd9470940fdb23ead5`
- **Result**: ✅ MATCH

### 5.2 Production PRAGMA integrity_check (pre-audit)
- **Result**: `ok` ✅

### 5.3 Exact Row Counts (Live Query)

| Table | Expected | Actual | Match |
|-------|----------|--------|-------|
| `manufacturer` | 12 | 12 | ✅ |
| `model` | 62 | 62 | ✅ |
| `generation` | 62 | 62 | ✅ |
| `variant` | 832 | 832 | ✅ |
| `powertrain` | 131 | 131 | ✅ |
| `source` | 8 | 8 | ✅ |
| `source_observation` | 3451 | 3451 | ✅ |
| `field_provenance` | 36445 | 36445 | ✅ |
| `safety_test` | 37 | 37 | ✅ |
| `safety_test_applicability` | 20 | 20 | ✅ |

All counts match expected exactly.

### 5.4 Bharat NCAP Record Validation
- **BNCAP source confirmed**: `id=7`, `name=bharat_ncap`, `source_type=rating_agency`
- **All 37 safety_test records**: `source_id=7` — all correct
- **All 37 records have**: `tested_vehicle_name` PRESENT, `raw_source_url` PRESENT, `resolution_status` PRESENT, `source_observation_id` PRESENT
- **All 37 records have**: `artifact_path` HAS_PATH, `artifact_checksum` HAS_CHECKSUM
- **source_observation references**: all 37 resolve to existing `source_observation` rows
- **Exceptions**: None

### 5.5 PDF Artifact Verification (CRITICAL)
Checksum algorithm confirmed from Phase 8A code: **SHA-256** (`hashlib.sha256`)

All 37 PDF artifacts were independently verified:

| ID | Vehicle | File Exists | Readable | Checksum Match |
|----|---------|-------------|----------|----------------|
| 1 | CITROEN-BASALT | YES | OK | ✅ PASS |
| 2 | CITROEN – C3 AIRCROSS (5-SEATER) | YES | OK | ✅ PASS |
| 3 | HONDA – AMAZE 3RD GEN | YES | OK | ✅ PASS |
| 4 | HYUNDAI-TUCSON | YES | OK | ✅ PASS |
| 5 | HYUNDAI – VENUE | YES | OK | ✅ PASS |
| 6 | KIA – SELTOS | YES | OK | ✅ PASS |
| 7 | KIA-SYROS | YES | OK | ✅ PASS |
| 8 | MAHINDRA – BE 6 | YES | OK | ✅ PASS |
| 9 | MAHINDRA – THAR ROXX | YES | OK | ✅ PASS |
| 10 | MAHINDRA – XEV 9e | YES | OK | ✅ PASS |
| 11 | Mahindra-XUV 3XO | YES | OK | ✅ PASS |
| 12 | Mahindra-XUV 400 EV | YES | OK | ✅ PASS |
| 13 | MAHINDRA – XUV 7XO | YES | OK | ✅ PASS |
| 14 | MARUTI-BALENO-GASOLINE (2 AB) | YES | OK | ✅ PASS |
| 15 | MARUTI-BALENO-GASOLINE (6 AB) | YES | OK | ✅ PASS |
| 16 | MARUTI – BREZZA | YES | OK | ✅ PASS |
| 17 | MARUTI – DZIRE – GASOLINE | YES | OK | ✅ PASS |
| 18 | MARUTI SUZUKI – e VITARA | YES | OK | ✅ PASS |
| 19 | MARUTI SUZUKI – INVICTO | YES | OK | ✅ PASS |
| 20 | MARUTI SUZUKI – VICTORIS | YES | OK | ✅ PASS |
| 21 | NISSAN – TEKTON | YES | OK | ✅ PASS |
| 22 | RENAULT – DUSTER | YES | OK | ✅ PASS |
| 23 | SKODA – KYLAQ | YES | OK | ✅ PASS |
| 24 | TATA ALTROZ | YES | OK | ✅ PASS |
| 25 | TATA CURVV EV | YES | OK | ✅ PASS |
| 26 | TATA CURVV | YES | OK | ✅ PASS |
| 27 | TATA – HARRIER.EV | YES | OK | ✅ PASS |
| 28 | TATA NEXON.EV | YES | OK | ✅ PASS |
| 29 | TATA NEXON | YES | OK | ✅ PASS |
| 30 | TATA – Punch.ev 2026 | YES | OK | ✅ PASS |
| 31 | TATA PUNCH.EV | YES | OK | ✅ PASS |
| 32 | TATA – PUNCH | YES | OK | ✅ PASS |
| 33 | TATA SAFARI/ HARRIER | YES | OK | ✅ PASS |
| 34 | TATA – SIERRA | YES | OK | ✅ PASS |
| 35 | TOYOTA – INNOVA HYCROSS | YES | OK | ✅ PASS |
| 36 | VINFAST – VF6 | YES | OK | ✅ PASS |
| 37 | VINFAST – VF7 | YES | OK | ✅ PASS |

- **Missing files**: 0
- **Checksum mismatches**: 0
- **Total failures**: 0

### 5.6 Provenance Verification (source_observation → safety_test)

Every `safety_test` record was individually verified against its linked `source_observation`:

| Metric | Expected | Actual |
|--------|----------|--------|
| Total safety_test records | 37 | 37 |
| Valid provenance links (so_id resolves) | 37 | 37 |
| Broken provenance links | 0 | 0 |
| URL mismatches (st.raw_source_url ≠ so.source_url) | 0 | 0 |
| st.source_id = 7 (BNCAP) | 37 | 37 |
| so.source_id = 7 (BNCAP) | 37 | 37 |

All 37 provenance chains are intact.

### 5.7 Applicability Verification

All 20 `safety_test_applicability` rows were individually verified:

- All `safety_test_id` values reference existing `safety_test` rows: ✅
- All `manufacturer_id` values reference valid `manufacturer` rows: ✅
- All `model_id` values reference valid `model` rows: ✅
- All `generation_id` values reference valid `generation` rows where populated: ✅
- `variant_id` is **NULL** for all 20 rows (strict MODEL_LEVEL/FAMILY_LEVEL principle observed): ✅
- `match_confidence` values used: `MODEL_LEVEL` (19 rows), `FAMILY_LEVEL` (1 row): ✅
- Model belongs to the referenced manufacturer in all rows: ✅

#### FAMILY_LEVEL Case (id=33: TATA SAFARI/ HARRIER)
- `match_confidence = FAMILY_LEVEL`
- Mapped to `model_id=30` (Harrier) only — Safari not mapped as not in CarRec top-62
- `generation_id = NULL` (correct for FAMILY_LEVEL)
- `variant_id = NULL` (correct — no fabricated variant mapping)
- Justification: `"BNCAP page explicitly covers Harrier AND Safari as one test (shared platform)."`

### 5.8 Resolution-Status Consistency

| Status | Expected Count | Actual Count | Has Applicability Rows | Expected |
|--------|---------------|--------------|------------------------|----------|
| RESOLVED | 20 | 20 | 20 rows (1 per test) | ✅ Correct |
| UNRESOLVED | 7 | 7 | 0 | ✅ Correct |
| NO_MATCH | 10 | 10 | 0 | ✅ Correct |

UNRESOLVED tests (7): CITROEN-BASALT, CITROEN C3 AIRCROSS, MAHINDRA THAR ROXX, MARUTI BREZZA, MARUTI DZIRE, VINFAST VF6, VINFAST VF7 — zero applicability rows each.

NO_MATCH tests (10): HYUNDAI TUCSON, MAHINDRA BE 6, MAHINDRA XEV 9e, MAHINDRA XUV 400 EV, MARUTI SUZUKI INVICTO, NISSAN TEKTON, TATA CURVV EV, TATA CURVV, TATA PUNCH (ICE), TATA SIERRA — zero applicability rows each.

### 5.9 Canonical Vehicle-Table Immutability
Comparison method: deterministic primary-key–based row comparison against `carrec_kb_phase8b_backup.db`.

| Table | Added | Deleted | Modified | Status |
|-------|-------|---------|----------|--------|
| `manufacturer` | 0 | 0 | 0 | ✅ PASS |
| `model` | 0 | 0 | 0 | ✅ PASS |
| `generation` | 0 | 0 | 0 | ✅ PASS |
| `variant` | 0 | 0 | 0 | ✅ PASS |
| `powertrain` | 0 | 0 | 0 | ✅ PASS |
| `field_provenance` | 0 | 0 | 0 | ✅ PASS |

**All six canonical tables are byte-for-byte identical to the pristine pre-Phase-8 backup.**

### 5.10 Source Table Immutability
| Table | Added | Deleted | Modified | Status |
|-------|-------|---------|----------|--------|
| `source` | 0 | 0 | 0 | ✅ PASS |

The BNCAP source (`id=7`) existed in the backup prior to ingestion. No source table mutations occurred.

### 5.11 Expected NCAP Additions (Independent Verification vs Backup)

| Table | Backup Rows | Prod Rows | Delta | Expected | Status |
|-------|------------|-----------|-------|----------|--------|
| `source_observation` | 3414 | 3451 | +37 | +37 | ✅ PASS |
| `safety_test` | 0 | 37 | +37 | +37 | ✅ PASS |
| `safety_test_applicability` | 0 | 20 | +20 | +20 | ✅ PASS |

No unexpected additions, deletions, or modifications were found outside these expected NCAP-related changes.

### 5.12 Final PRAGMA integrity_check (post-audit)
- **Result**: `ok` ✅

### 5.13 Isolated Idempotency Artifact
- **File**: `scratch/carrec_kb_phase8b_isolated.db`
- **Integrity**: `ok`
- **Row counts** (safety_test=37, safety_test_applicability=20, source_observation=3451): Consistent with production
- Second-pass idempotency test during Phase 8B execution reported: 0 additions, 0 deletions, 0 modifications across all tables

### 5.14 Unexpected Mutations
**None found.** All tables conform exactly to Phase 8B expected state.

---

## 6. Closeout Audit Summary

| # | Verification Category | Result |
|---|----------------------|--------|
| 1 | Production DB integrity (pre-audit) | ✅ PASS |
| 2 | Production DB checksum | ✅ PASS |
| 3 | Exact row counts (all 10 tables) | ✅ PASS |
| 4 | BNCAP record completeness (37 tests) | ✅ PASS |
| 5 | PDF artifact existence (37 files) | ✅ PASS |
| 6 | PDF artifact SHA-256 checksums (37 checksums) | ✅ PASS |
| 7 | Provenance links source_observation→safety_test | ✅ PASS |
| 8 | Applicability FK validity (20 rows) | ✅ PASS |
| 9 | Applicability variant_id = NULL (strict MODEL/FAMILY) | ✅ PASS |
| 10 | FAMILY_LEVEL Harrier/Safari case | ✅ PASS |
| 11 | Resolution-status consistency (20/7/10) | ✅ PASS |
| 12 | UNRESOLVED tests have no applicability rows | ✅ PASS |
| 13 | NO_MATCH tests have no applicability rows | ✅ PASS |
| 14 | Canonical table immutability (PK-based diff) | ✅ PASS |
| 15 | Source table immutability | ✅ PASS |
| 16 | Expected NCAP additions (+37/+37/+20) | ✅ PASS |
| 17 | No unexpected mutations | ✅ PASS |
| 18 | Production DB integrity (post-audit) | ✅ PASS |
| 19 | Isolated idempotency artifact present and consistent | ✅ PASS |

**ALL 19 CHECKS: PASS**

---

## 7. Final Verdict

**READY_FOR_PHASE_9**

The Bharat NCAP safety layer has been successfully ingested into production and independently audited. All required closeout checks passed with no exceptions, no inferred successes, and no silent repairs. Canonical vehicle data is immutable. Provenance chains are intact. All 37 PDF artifacts are present and checksums verified. Resolution semantics are strictly observed — no fabricated variant mappings exist.
