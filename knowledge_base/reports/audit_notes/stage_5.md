# Stage 5 — Ingestion, extraction, provenance

## Evidence in production by source (copy of prod) [VERIFIED]
| source (id, tier) | obs | statuses | provenance rows (acc/conf/rej) | observed |
|---|---|---|---|---|
| v6_migration (1, t2 in table / **t5 in code**) | 864 = 812 CSV + **52 OEM brochure** | applied 812; resolved 52 | 24,956 / 104 / 28 | 06-19..06-28; 09-13 |
| 91wheels (2, t2) | 845 | resolved 457, resolved_with_warning 254, unresolved 134 | 216 / 2345 / 323 | 09-09 |
| v3cars (3, t2 in table, t3 in code) | 845 | resolved 438, unresolvable 363, model_level 44 | 331 / 2176 / 997 | 09-09 |
| carwale (4, t3) | 860 | resolved 753, unresolvable 107 | 84 / 3561 / 1027 | 09-09 |
| oem (6, t1) | **0** | — | — | — |
| bharat_ncap (7, t1) | 37 | RESOLVED 20, UNRESOLVED 7, NO_MATCH 10 | none (anchors safety_test) | 09-23 |
| cardekho (5), global_ncap (8) | 0 | — | — | — |
| orphans (deleted CarWale pilot obs) | — | — | 6 / 212 / 79 | 09-09 |
- `source.authority_tier` (table) disagrees with `authority_matrix.py` (code): v6_migration 2 vs 5; v3cars 2 vs 3. The code value is what drives decisions. [VERIFIED table; code authority_matrix.py:75-78 VERIFIED]
- `extraction_method` = 'rsc_payload' for every non-v6 obs, including OEM PDFs and HTML scrapes (updater.py:41 hard-codes it) [VERIFIED].
- Decision reason `conflict_with_canonical_authority` (2,426 rows) is not emitted by current updater code; it was patched out by `fix_updater_inheritance.py` → **production provenance was produced by code versions that no longer exist** and were never committed [VERIFIED grep].

## Per-pipeline chain
### OEM brochures
acquire (manifest only; 67 PDFs, sha256 in 3 metadata files never checked) → profile/classify/extract (pdfplumber families) → `resolve_oem_generation` → `process_oem_payload` → `update_canonical(source_id=1, url='offline_brochure')`.
- **Confirmed bug: OEM observations written under source_id=1 (v6_migration), not 6 (oem)** [VERIFIED batch_runner_oem.py:141, scratch/production_ingestion_controlled.py:149, DB rows 3669–3720]. Effects: authority tier 5 (lowest) instead of 1 → OEM facts cannot override aggregator values; equal-tier conflicts rejected (28 OEM rejections are exactly the `conflict_field_tier_5_vs_best_{5,3}` rows) [VERIFIED]; OEM evidence indistinguishable from V6 CSV migration by source.
- PHASE6_OEM_CONTROLLED_PRODUCTION_REPORT line 137 says "`source_id = 1` (OEM source)" → [CONTRADICTED] by `source` table (1 = v6_migration, 6 = oem).
- Fail-closed: PDF text/CID failures, generation 0/>1 → raise; classifier falls back to Borderless for everything. Of 62 models: controlled run statuses per report — many EXTRACTION/PDF_TEXT/RESOLUTION failures [REPORTED-ONLY]. Only 52 observations / 50 variants landed; 1 accepted value (paddle_shifters=0) [VERIFIED].
- Idempotency: dedup on (source_id, 'offline_brochure', raw_name) — idempotent but lossy (collisions across configs/models) [VERIFIED code].
- Authoritative in prod? **No** — effectively tier-5 corroboration only.

### CarWale
model page `__INITIAL_STATE__` → version pages → resolver (91wheels aliases, no generation) → updater; commit per variant.
- **Phase 9A resolution mismatch still present**: obs 2842 "E Petrol 1.5L Manual" → variant 2 ("EX…"), obs 2843 "EX…" → variant 1 ("E…") [VERIFIED].
- **Edition over-absorption (new)**: 169 variants have >1 CarWale observation; edition variant 820 ("AX7 2WD Petrol 2.0L Turbo Manual 7 STR Dual Tone") has 33 CarWale obs incl. AX5, Diesel, Automatic configs [VERIFIED]. 39 `accepted` provenance values on edition variants 814–833 came from CarWale obs [VERIFIED count]; given the mis-resolution, some edition field values are likely from other configurations [INFERENCE].
- Crude check: 201/753 resolved CarWale obs have a different first token than the resolved variant name (upper bound, includes benign spacing diffs like "HX8" vs "HX 8") [VERIFIED query; significance not assessed].
- Tier 99 for sunroof/adas/HUD/boot/transmission → rejected unless canonical NULL [REPORTED-ONLY (subagent)].
- Authoritative in prod? Contributes 84 accepted values; 3,561 confirmations.

### V3Cars
- Absent feature keyword → 0 (`field_map_v3cars.py:24`), status forced to 'resolved' (`ingest_v3cars.py:104`) [VERIFIED code]. In prod: **285 `accepted/new_field` values of `0` from V3Cars** (HUD 100, wireless charging 93, cruise 65, ventilated seats 18, TPMS 9) [VERIFIED counts] — these assert absence from non-mention; violates PRECISION>COVERAGE [INFERENCE that non-mention caused them; code path VERIFIED].
- `base_variant_id` UnboundLocalError path at :85 [REPORTED-ONLY (subagent)].

### 91wheels
Current package cannot import/run (missing modules, 3-tuple unpacked into 2) [REPORTED-ONLY (subagent)]; data in prod came from a pre-refactor layout. 125 accepted `0` values from 91wheels too [VERIFIED count].

### BNCAP
index (37 URLs) → HTML + PDF factsheet (scratch/bncap_pdfs, SHA-256) → `source_observation` (source 7, full JSON payload) → `safety_test` (FK to observation) → `safety_test_applicability` (MODEL/FAMILY level, variant NULL). No field_provenance (by design).
- Phase 8 script commits inside `ingest()` before its invariant checks → checks cannot prevent a bad commit [VERIFIED phase8_production_ingestion.py L62→v4:498]. Phase 8B script: checksum pre-gate (EXPECTED_CHECKSUM e752ebde) ✓, DDL before BEGIN (autocommit), no backup creation, no auto-restore [VERIFIED].
- `logical_diff` in phase8b counts `modified` only when row counts are equal (hash-set diff) — can mask modifications when rows are added in the same table [VERIFIED phase8b_prod_ingestion.py ~L140-148].
- Phase 9B left `source_observation.resolution_status = 'UNRESOLVED'` for obs 3729/3736/3737 while `safety_test` says RESOLVED — two sources of truth now disagree [VERIFIED]. Not mentioned in PHASE9B report.

## Provenance invariants [VERIFIED]
- Every variant has ≥1 provenance row; 0 provenance rows with NULL observation id; 0 provenance rows whose variant ≠ observation's resolved variant; 0 provenance from unresolved obs.
- 297 orphans (FP 31888–32184 → obs 2608–2661; Creta 80, Harrier 109, Kushaq 76, Verna 32).
  - PHASE9A says all 6 `accepted` orphans are on variant 452 → [CONTRADICTED]: variants 441 (sunroof), 442 (adas_available), 452 (sunroof, cruise_control, HUD, TPMS) — all Harrier. Canonical values today equal the orphan accepted values, and each is corroborated by a live `confirmed` provenance row [VERIFIED].
  - 6 orphan `confirmed` rows (variants 277×5, 10×1 on `transmission`) and 1 `rejected` have no live accepted/confirmed support [VERIFIED] — `transmission` is not v6-provenanced, so those canonical transmissions have **no live evidence row** at all.
  - PHASE9A: "carwale_snapshot_before.json … final v3cars SO was in the mid-2500s" → [CONTRADICTED]: 2502 is a row count; max v3cars obs id is 2607.
  - PHASE9A classification RECOVERABLE_WITH_CERTAINTY = 0 → consistent with the still-present CarWale resolution swaps [VERIFIED supporting evidence].

## Recommendation (orphaned provenance) — no action taken
Treat the 297 rows as **immutable historical evidence with a severed source**: never delete, never re-point to surviving observations. Consumers should join with `LEFT JOIN source_observation` and treat unmatched rows as `evidence_unavailable`, never as authority. If annotation is ever done, do it in a separate side table (e.g. provenance_anomaly(fp_id, kind, noted_at)) rather than mutating `decision_reason`, so the original rows stay byte-identical. Enforce `PRAGMA foreign_keys=ON` for all future writers so this cannot recur.

Checksum gate: `1e3eb679…` ✔
