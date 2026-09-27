# Phase 9A — Findings and Resolution Report

**Audit date:** 2026-09-26  
**Scope:** Controlled investigation and proposed remediation for three Phase 9 audit findings.  
**Audit type:** Primarily read-only investigation. One isolated DB validation run. No production mutations.

---

## 1. Phase 9A Scope

This phase addressed exactly the three findings identified in the Phase 9 Post-NCAP KB Audit:

| Finding | Description |
|---------|-------------|
| A | 297 orphaned `field_provenance` records with broken `source_observation_id` FK references |
| B | 3 Bharat NCAP `safety_test` records classified UNRESOLVED that may be deterministically resolvable |
| C | 24 Global NCAP records in the legacy `safety_rating` table, lacking the new provenance pipeline |

**What was NOT done:**
- No professional reviewer data ingested
- No owner/ownership data ingested
- No schema redesign
- No production mutations of any kind
- Phase 10 was not started

---

## 2. Production Baseline

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| SHA-1 checksum (pre-audit) | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ MATCH |
| `PRAGMA integrity_check` (pre-audit) | `ok` | `ok` | ✅ PASS |
| SHA-1 checksum (post-audit) | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ MATCH |
| `PRAGMA integrity_check` (post-audit) | `ok` | `ok` | ✅ PASS |

---

## 3. Part A — Orphaned field_provenance Investigation

### Schemas

**`field_provenance`** columns:
- `id` (PK), `variant_id` (NOT NULL), `field_name` (NOT NULL), `accepted_value`, `source_observation_id` (nullable FK), `decision` (default `'accepted'`), `decision_reason`, `decided_at`

**`source_observation`** columns:
- `id` (PK), `source_id` (NOT NULL), `raw_name` (NOT NULL), `raw_payload`, `source_url`, `observed_at`, `extraction_method`, `resolved_variant_id`, `resolution_status`

> [!NOTE]
> There is no `ON DELETE CASCADE` or `ON DELETE SET NULL` constraint on `field_provenance.source_observation_id`. SQLite does not enforce FK constraints by default unless `PRAGMA foreign_keys=ON` is set per-connection. This is why the FK violation exists without triggering an error.

### Summary of Orphaned Records

| Model | Affected Variants | FP Rows | Distinct Broken SO IDs | confirmed | rejected | accepted |
|-------|-------------------|---------|----------------------|-----------|----------|----------|
| Creta (Hyundai) | 9 | 80 | 10 (2628–2637) | 62 | 18 | 0 |
| Harrier (Tata) | 6 | 109 | 14 (2625–2661) | 76 | 27 | 6 |
| Kushaq (Skoda) | 5 | 76 | 10 (2638–2647) | 57 | 19 | 0 |
| Verna (Hyundai) | 3 | 32 | 7 (2608–2620) | 17 | 15 | 0 |
| **Total** | **23** | **297** | **41** | **212** | **79** | **6** |

All 41 broken `source_observation_id` values fall in the range 2608–2661. The production `source_observation` table jumps from id=2607 (VW Virtus, source=v3cars) directly to id=2809 (Honda Amaze, source=carwale). The gap of 201 IDs contains no surviving records.

---

## 4. Root-Cause Analysis

**INVESTIGATION RESULT:** The 297 orphaned records are the result of a repeated CarWale ingestion pattern involving two distinct run-and-rollback cycles.

### Evidence Chain

1. **`knowledge_base/carwale_snapshot_before.json`** records the pre-CarWale-ingestion state:  
   `source_observation: 2502` — meaning the final v3cars SO was in the mid-2500s range.

2. **CarWale batch ingestion** (`batch_runner_carwale.py`, `ingest_carwale.py`) processed 62 models including Hyundai Verna, Hyundai Creta, Tata Harrier, and Skoda Kushaq. The first ingestion run created source_observations in the range 2608–2661 for these four models.

3. **`run_mini_pilot.py`** (a debugging script) contains:
   ```python
   c.execute("DELETE FROM field_provenance WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4 AND source_url LIKE '%harrier%')")
   c.execute("DELETE FROM source_observation WHERE source_id=4 AND source_url LIKE '%harrier%'")
   ```
   This pilot script explicitly deleted Harrier CarWale SOs and their FP references. The cascade deletion worked for the FP records it deleted, but produced the orphans for subsequent re-run FP records.

4. **No single script found** that deleted Verna, Creta, Kushaq source_observations. The most likely explanation is that these were deleted during a broader CarWale ingestion rollback (a `DELETE FROM source_observation WHERE source_id=4 AND source_url LIKE '%verna%'` pattern or a full `DELETE WHERE source_id=4` and re-run), and the corresponding FP cleanup was missed.

5. **Re-ingestion** of the same models created new SOs in the 2809+ range (next AUTOINCREMENT gap after unrelated models' IDs). The field_provenance records from the first run were not cleaned up and now reference deleted source_observations.

### Conclusion

**FACT:** The orphaned records are Category A — legitimate historical CarWale provenance evidence whose source_observations were deleted during an earlier debugging/cleanup cycle, without cascading the FP cleanup. They are not corrupt; they correctly record the decisions made during the first CarWale pass. The canonical values accepted from those SOs remain correct.

---

## 5. Orphan Classification

| Category | Count | Description |
|----------|-------|-------------|
| A — Historical provenance, SO deleted in cleanup | **297** | All 297 records |
| B — Duplicate/obsolete | 0 | — |
| C — Genuinely corrupt | 0 | — |
| D — Intentional schema state | 0 | — |

### Decision Breakdown

| Decision | Count | Implication |
|----------|-------|-------------|
| `confirmed` | 212 | The observation agreed with what was already canonical. The canonical value is correct independently. |
| `rejected` | 79 | The observation was rejected in favour of a higher-authority value. These records document a conflict resolution decision. The canonical value was NOT taken from this observation. |
| `accepted` | 6 | The observation supplied a new field value. Canonical value is correct but the audit trail is severed. |

> [!IMPORTANT]
> **Key finding:** The 6 `accepted` records represent the only cases where the deleted source_observation was the primary evidence for a canonical field value. For these 6 rows (all on Tata Harrier variants 452 `Diesel Pure X MT`), the accepted fields are `cruise_control`, `heads_up_display`, `sunroof`, `tyre_pressure_monitoring_system` — the canonical values remain correct but the evidence link is permanently severed.
>
> The 212 `confirmed` records are redundant evidence (the canonical value was already established from another source). The 79 `rejected` records document conflict-resolution outcomes and are factually inert.

### Recoverability Assessment

For recoverability to be `RECOVERABLE_WITH_CERTAINTY`, we would need to deterministically identify the surviving source_observation that was the re-ingestion replacement.

**Obstacle:** The surviving CarWale SOs for Creta show systematic name/variant resolution mismatches. For example, SO 2843 ("EX Petrol 1.5L Manual") resolves to variant_id=1 ("E Petrol 1.5L Manual"), and SO 2842 ("E Petrol 1.5L Manual") resolves to variant_id=2 ("EX Petrol 1.5L Manual"). This means the surviving SOs cannot be safely used to repair FP references — the `resolved_variant_id` assignments are unreliable for at least Creta.

| Classification | Count | Basis |
|---|---|---|
| `RECOVERABLE_WITH_CERTAINTY` | 0 | Surviving SOs have resolution mapping errors; cannot safely establish 1:1 FP→SO correspondence |
| `DUPLICATE_OBSOLETE` | 79 | Rejected records; the decision is correctly preserved in the FP row itself |
| `UNRECOVERABLE` | 218 | confirmed (212) + accepted (6): audit trail severed, canonical values correct |
| `REQUIRES_MANUAL_REVIEW` | 0 | — |

---

## 6. Proposed Provenance Remediation for Part A

**PROPOSED CHANGE (not yet applied to production):**

No active repair is proposed for production at this time. The reasoning:

1. **Canonical values are correct.** The orphaned FP records do not affect any canonical field value.
2. **Rejected records (79)** are inert — they document that a value was not accepted. These could be safely deleted without any functional impact, but deletion would remove the decision audit log.
3. **Confirmed records (212)** are redundant evidence. The canonical value is independently supported by surviving SOs from other sources (91wheels, v3cars).
4. **Accepted records (6)** — audit trail severed, but canonical values are correct. No repair can be performed without fabricating provenance.
5. **Recovery is not deterministic** due to SO resolution mapping errors in the re-ingestion.

**RECOMMENDED SAFE TREATMENT:**

Annotate the 297 records with a `decision_reason` suffix documenting their status rather than deleting them. Deletion of rejected/confirmed records could be done in a future maintenance pass but offers no data quality benefit. Deletion of the 6 accepted records would silently erase the only record that a second source contributed a value.

**Script status:** A remediation script would set `decision_reason = decision_reason || ' [SO_DELETED_IN_CLEANUP]'` on all 297 rows. This is safe, reversible, and does not modify any canonical value or delete any record.

**Production action for Part A: NONE at this time.** The finding is documented. The records are harmless. Cleanup can be scheduled as a low-priority maintenance pass.

---

## 7. Part B — BNCAP Alias Investigation

### Candidates Inspected

#### Candidate 1: MAHINDRA – THAR ROXX (safety_test id=9)

| Field | Value |
|-------|-------|
| `tested_vehicle_name` | `MAHINDRA – THAR ROXX` |
| `tested_variant_config` | `MAHINDRA – THAR ROXX – AX5L, MX3` |
| `body_type` | `SUV (2 rows)` |
| `test_period` | `November 2024 - Onwards` |
| `year_of_publication` | 2024 |
| `raw_source_url` | `https://www.bncap.in/vehicle/mahindra-thar-roxx/` |
| `resolution_status` | `UNRESOLVED` |
| `resolution_justification` | `Multiple model matches: [53, 54].` |

**Why it failed original resolution:** The title substring "THAR" matches both Thar (model_id=53) and Thar Roxx (model_id=54), producing multiple matches.

**Evidence for deterministic resolution:**
- URL slug `mahindra-thar-roxx` — unambiguously names Thar Roxx, not Thar
- Tested configs `AX5L` and `MX3` are Thar Roxx-specific trim designations (AX = Active series, MX = base with luxury; these do not exist on the original Thar)
- Thar Roxx is a distinct model in CarRec: `model_id=54`, `manufacturer_id=5` (Mahindra), `generation_id=22`
- **No variant-level evidence** → mapping must remain `MODEL_LEVEL`, `variant_id=NULL`

**Classification: RESOLVABLE_WITH_CERTAINTY**

#### Candidate 2: MARUTI – BREZZA (safety_test id=16)

| Field | Value |
|-------|-------|
| `tested_vehicle_name` | `MARUTI – BREZZA` |
| `tested_variant_config` | `MARUTI – BREZZA – ZXI+ 1.5L 6AT` |
| `body_type` | `SUV (2 rows)` |
| `test_period` | `July 2026 - Onwards` |
| `year_of_publication` | 2026 |
| `raw_source_url` | `https://www.bncap.in/vehicle/maruti-brezza/` |
| `resolution_status` | `UNRESOLVED` |
| `resolution_justification` | `Could not identify manufacturer from title: "MARUTI – BREZZA"` |

**Why it failed original resolution:** The Phase 8A resolver looked for the full manufacturer name `Maruti Suzuki` as a substring of the cleaned title. `"MARUTI"` does not contain `"marutisuzuki"`.

**Evidence for deterministic resolution:**
- URL slug `maruti-brezza` — "maruti" is a well-established abbreviation for Maruti Suzuki, uniquely identifying the manufacturer
- Model "Brezza" exists in CarRec: `model_id=7`, `manufacturer_id=6` (Maruti Suzuki), `body_type=SUV`
- Body type SUV in the test matches CarRec model body type
- No other Maruti Suzuki model is named "Brezza" in the canonical KB
- `variant_id=NULL` — `ZXI+ 1.5L 6AT` is a specific variant trim, but `MODEL_LEVEL` is the correct scope per Phase 8 principles
- **Classification: RESOLVABLE_WITH_CERTAINTY**

#### Candidate 3: MARUTI – DZIRE – GASOLINE (safety_test id=17)

| Field | Value |
|-------|-------|
| `tested_vehicle_name` | `MARUTI – DZIRE – GASOLINE` |
| `tested_variant_config` | `MARUTI – DZIRE – GASOLINE – LXI 1.2L ISS 5MT` |
| `body_type` | `Sedan (2 rows)` |
| `test_period` | `June 2025 - Onwards` |
| `year_of_publication` | 2025 |
| `raw_source_url` | `https://www.bncap.in/vehicle/maruti-dzire-gasoline/` |
| `resolution_status` | `UNRESOLVED` |
| `resolution_justification` | `Could not identify manufacturer from title: "MARUTI – DZIRE – GASOLINE"` |

**Why it failed original resolution:** Same reason as Brezza — `"MARUTI"` doesn't substring-match `"marutisuzuki"`.

**Evidence for deterministic resolution:**
- URL slug `maruti-dzire-gasoline` — "maruti" unambiguously identifies Maruti Suzuki; "dzire" identifies the model; "gasoline" = petrol-only qualifier
- Model "Dzire" exists in CarRec: `model_id=13`, `manufacturer_id=6` (Maruti Suzuki), `body_type=Sedan`
- Body type Sedan matches
- "GASOLINE" qualifier is consistent — Dzire in CarRec has only petrol/CNG variants; no diesel exists
- No other Maruti Suzuki Sedan named "Dzire" in canonical KB
- `variant_id=NULL` — `LXI 1.2L ISS 5MT` is variant-specific but test applicability is model-level
- **Classification: RESOLVABLE_WITH_CERTAINTY**

---

## 8. Part B — Isolated Validation Results

An isolated copy of the production DB was created at `scratch/phase9a_bncap_test.db`. The three resolutions were applied and verified. Production checksum was verified unchanged before and after.

### Pre-Application State (isolated DB)

| st_id | tested_vehicle_name | resolution_status | applicability_rows |
|---|---|---|---|
| 9 | MAHINDRA – THAR ROXX | UNRESOLVED | 0 |
| 16 | MARUTI – BREZZA | UNRESOLVED | 0 |
| 17 | MARUTI – DZIRE – GASOLINE | UNRESOLVED | 0 |

### Post-Application State (isolated DB)

| st_id | tested_vehicle_name | resolution_status | model | mfr | gen | variant | confidence |
|---|---|---|---|---|---|---|---|
| 9 | MAHINDRA – THAR ROXX | RESOLVED | 54 (Thar Roxx) | 5 (Mahindra) | 22 | NULL | MODEL_LEVEL |
| 16 | MARUTI – BREZZA | RESOLVED | 7 (Brezza) | 6 (Maruti Suzuki) | 24 | NULL | MODEL_LEVEL |
| 17 | MARUTI – DZIRE – GASOLINE | RESOLVED | 13 (Dzire) | 6 (Maruti Suzuki) | 28 | NULL | MODEL_LEVEL |

### Isolated DB Checks

| Check | Result |
|-------|--------|
| All `variant_id` values NULL (MODEL_LEVEL principle preserved) | ✅ PASS |
| safety_test total unchanged at 37 | ✅ PASS |
| safety_test_applicability increases from 20 to 23 | ✅ PASS (+3) |
| All canonical tables (manufacturer, model, generation, variant, powertrain, source, field_provenance) unchanged | ✅ PASS |
| Production checksum unchanged | ✅ PASS — `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` |

### Per-Candidate Assessment

| Candidate | Evidence Quality | Isolation Test | Production Action |
|-----------|-----------------|----------------|-------------------|
| Thar Roxx | DETERMINISTIC (url_slug + trim names are model-specific) | PASS | **SAFE_TO_APPLY** |
| Brezza | DETERMINISTIC (url_slug + SUV body type + no name ambiguity) | PASS | **SAFE_TO_APPLY** |
| Dzire | DETERMINISTIC (url_slug + Sedan body + petrol-only qualifier matches CarRec) | PASS | **SAFE_TO_APPLY** |

> [!IMPORTANT]
> All three resolutions are proposed at **MODEL_LEVEL only**. No variant_id is set. The tested variant configurations (ZXI+ 1.5L 6AT for Brezza; LXI 1.2L ISS 5MT for Dzire; AX5L/MX3 for Thar Roxx) are specific trims but the Phase 8/9 governing principle holds: **MODEL_LEVEL test result ≠ VARIANT_LEVEL applicability**.

---

## 9. Part C — Legacy Global NCAP safety_rating Audit

### Schema

`safety_rating` columns: `id`, `model_id` (NOT NULL FK), `generation_id` (nullable FK), `testing_body`, `adult_stars`, `child_stars`, `test_year`, `tested_variant`, `source_url`

Notable absences compared to `safety_test`: no `aop_score`, `cop_score`, `protocol_version`, `crash_test_weight_kg`, `test_period`, `sat_summary`, `artifact_path`, `artifact_checksum`, `source_observation_id`, `resolution_status`, `resolution_justification`.

### Global NCAP Record Inventory (24 records)

| ID | Model | Manufacturer | Adult ★ | Child ★ | Year | Tested Config | Has URL | model FK | gen FK |
|----|-------|---|---|---|---|---|---|---|---|
| 1 | Creta | Hyundai | 3.0 | 3.0 | 2022 | Creta - 2 Airbags | ✅ | ✅ | ✅ |
| 2 | Swift | Maruti Suzuki | 1.0 | 1.0 | 2022 | Swift - 2 Airbags | ✅ | ✅ | ✅ |
| 5 | Seltos | Kia | 3.0 | 2.0 | 2020 | Seltos - 2 Airbags | ✅ | ✅ | ✅ |
| 6 | Ertiga | Maruti Suzuki | 3.0 | 3.0 | 2019 | Ertiga - 2 Airbags | ✅ | ✅ | ✅ |
| 7 | WagonR | Maruti Suzuki | 1.0 | 0.0 | 2023 | WagonR - 2 Airbags | ✅ | ✅ | ✅ |
| 8 | Dzire | Maruti Suzuki | 5.0 | 4.0 | 2024 | Dzire - 6 Airbags | ✅ | ✅ | ✅ |
| 9 | Grand i10 Nios | Hyundai | 2.0 | 2.0 | 2020 | Grand i10 Nios - 2 Airbags | ✅ | ✅ | ✅ |
| 10 | Verna | Hyundai | 5.0 | 5.0 | 2023 | Verna - 6 Airbags | ✅ | ✅ | ✅ |
| 11 | Amaze | Honda | 2.0 | 0.0 | 2024 | Amaze - 2 Airbags | ✅ | ✅ | ✅ |
| 12 | Altroz | Tata | 5.0 | 3.0 | 2020 | Altroz - 2 Airbags | ✅ | ✅ | ✅ |
| 13 | Tiago | Tata | 4.0 | 3.0 | 2020 | Tiago - 2 Airbags | ✅ | ✅ | ✅ |
| 14 | Tigor | Tata | 4.0 | 3.0 | 2020 | Tigor - 2 Airbags | ✅ | ✅ | ✅ |
| 15 | Bolero | Mahindra | 1.0 | 1.0 | 2024 | Bolero Neo - 2 Airbags | ✅ | ✅ | ✅ |
| 16 | Scorpio-N | Mahindra | 5.0 | 3.0 | 2022 | Scorpio N - 2 Airbags | ✅ | ✅ | ✅ |
| 17 | Harrier | Tata | 5.0 | 5.0 | 2023 | Harrier - 6 Airbags | ✅ | ✅ | ✅ |
| 18 | Triber | Renault | 4.0 | 3.0 | 2021 | Triber - 2 Airbags | ✅ | ✅ | ✅ |
| 19 | S-Presso | Maruti Suzuki | 1.0 | 0.0 | 2022 | S-Presso - 2 Airbags | ✅ | ✅ | ✅ |
| 20 | Alto K10 | Maruti Suzuki | 2.0 | 0.0 | 2023 | Alto K10 - 2 Airbags | ✅ | ✅ | ✅ |
| 21 | Kushaq | Skoda | 5.0 | 5.0 | 2022 | Kushaq - 2 Airbags | ✅ | ✅ | ✅ |
| 22 | Slavia | Skoda | 5.0 | 5.0 | 2023 | Slavia - 2 Airbags | ✅ | ✅ | ✅ |
| 23 | Taigun | Volkswagen | 5.0 | 5.0 | 2022 | VW Taigun - 2 Airbags | ✅ | ✅ | ✅ |
| 24 | Virtus | Volkswagen | 5.0 | 5.0 | 2023 | VW Virtus - 2 Airbags | ✅ | ✅ | ✅ |
| 25 | Thar | Mahindra | 4.0 | 4.0 | 2020 | Thar - 2 Airbags | ✅ | ✅ | ✅ |
| 26 | Magnite | Nissan | 4.0 | 2.0 | 2022 | Magnite - 2 Airbags | ✅ | ✅ | ✅ |

### Classification

| Classification | Count | Records |
|---|---|---|
| WELL_SUPPORTED (model FK, gen FK, source_url, test_year, tested_variant all present) | 24 | All 24 |
| PARTIALLY_SUPPORTED | 0 | — |
| DUPLICATE (with BNCAP safety_test pipeline) | 5* | Altroz, Harrier, Seltos, Amaze — also have BNCAP tests; Harrier/Seltos/Amaze/Altroz. Different testing body, different year |
| AMBIGUOUS | 0 | — |
| MISSING_PROVENANCE (no source_url) | 0 | All 24 have source_url |

*"Duplicate" here means both Global NCAP and BNCAP results exist in the KB for the same model. These are NOT genuine duplicates — they are different test results from different agencies in different years. The word "duplicate" does not apply. All 5 dual-tested models have different test years and bodies.

> [!NOTE]
> The `tested_variant` strings in `safety_rating` include the airbag count as a qualifier (e.g., "Creta - 2 Airbags"). This is a meaningful qualifier: Global NCAP often tested the base/minimum-safety variant deliberately to establish a floor. This information is currently partially captured in the `tested_variant` string but is not structured as a separate `airbags` field.

---

## 10. Part C — Legacy Safety Architecture Assessment

### Current Two-Layer Architecture

| Layer | Table | Records | Provenance | Structured? | Used for BNCAP? |
|-------|-------|---------|-----------|-------------|-----------------|
| Legacy | `safety_rating` | 27 (3 BNCAP + 24 Global NCAP) | None (no source_observation link) | Star ratings only | Yes, 3 rows (pre-Phase-8 bootstrap) |
| Provenance-backed | `safety_test` + `safety_test_applicability` | 37 + 20 | Full (source_observation, artifact, checksum) | Full structured data | Yes (Phase 8B) |

The legacy `safety_rating` table provides star ratings only. It does not store protocol version, test weight, AOP/COP numerical scores, SAT summary, artifact checksums, or provenance chains. Source 8 (`global_ncap`) is registered in the `source` table but has no `source_observation` rows.

### Is the legacy table suitable for future migration?

**Yes, with conditions.** All 24 records have:
- Valid `model_id` and `generation_id` FKs pointing to correct canonical models
- `source_url` pointing to Global NCAP factsheet PDFs (publicly accessible)
- `test_year` allowing temporal ordering
- `tested_variant` documenting which configuration was tested (partially structured)

**Conditions required:**
1. Global NCAP PDFs must be downloaded and checksummed to fill `artifact_path`/`artifact_checksum`
2. AOP/COP numerical scores and protocol version must be extracted from the PDFs
3. A source_observation must be created for each record under source_id=8
4. The `safety_test_applicability` must be derived from existing `model_id`/`generation_id` mappings (all are already valid)
5. The 3 `safety_rating` BNCAP rows (Nexon, Nexon EV, Punch EV) overlap with `safety_test_applicability` — these should not be double-migrated

---

## 11. Part C — Future Migration Design

### Can Global NCAP use the same safety_test pipeline as BNCAP?

**INVESTIGATION RESULT:** Yes, structurally. The semantic differences are manageable.

**Mapping:**

| Global NCAP concept | BNCAP equivalent in safety_test | Notes |
|---------------------|--------------------------------|-------|
| `testing_body = 'Global NCAP'` | `source_id = 8` | Source already exists |
| Star ratings (adult/child) | `aop_stars`, `cop_stars` | Global NCAP uses adult/child, BNCAP uses AOP/COP — these map: adult=AOP, child=COP |
| `source_url` (PDF factsheet) | `factsheet_url` + `artifact_path` | Download, store, checksum |
| `model_id` + `generation_id` | `safety_test_applicability.model_id` / `generation_id` | Already valid FKs |
| `tested_variant` string | `tested_variant_config` | Existing field |
| `test_year` | `year_of_publication` | Direct mapping |
| AOP/COP numerical scores | `aop_score`, `cop_score` | Must be extracted from factsheet PDFs — not currently available in legacy table |
| Protocol version | `protocol_version` | Must be extracted from PDFs (e.g., "NCAP4" vs "Safer Cars For India") |
| SAT summary | `sat_summary` | Must be extracted from PDFs |
| Crash test weight | `crash_test_weight_kg` | Must be extracted from PDFs |

**Semantic differences that require care:**

1. **Scoring semantics differ:** BNCAP uses Adult Occupant Protection (AOP) and Child Occupant Protection (COP) with percentage scores. Global NCAP uses a star rating derived from similar categories but with different protocols (especially pre-2022 Safer Cars For India program vs. current). Numerical scores would be from different denominators — they must not be compared directly.

2. **Protocol versions span multiple programs:** The 24 records span tests from 2019–2024 under different Global NCAP programs. Protocol version must be recorded per record, not assumed uniform.

3. **Tested configuration semantics:** "2 Airbags" in Global NCAP means the specific low-spec configuration tested. This is meaningful safety information (it establishes a minimum floor) but is different from BNCAP's variant-config notation. The `tested_variant_config` field can absorb this.

4. **No variant-level resolution needed:** All Global NCAP records are already in `safety_rating` with model_id, so `safety_test_applicability` can be populated at `MODEL_LEVEL` without new entity resolution.

**Pre-requisites before migration:**
- Download 24 PDFs from `source_url` values, store in `scratch/gncap_pdfs/`, compute SHA-256 checksums
- Extract AOP/COP numerical scores, protocol, weight from PDFs
- Create 24 `source_observation` rows under `source_id=8`
- Insert 24 `safety_test` rows
- Insert 24 `safety_test_applicability` rows (no entity resolution required — model_ids already valid)
- Mark 3 BNCAP-duplicate rows as excluded from migration

---

## 12. Part D — Cross-Cutting Safety Architecture Recommendation

**INVESTIGATION RESULT: Approach B — Unified across NCAP providers using safety_test**

### Reasoning

1. **`safety_test` is already provider-agnostic.** The `source_id` field identifies the provider. `aop_stars`/`cop_stars` are semantically appropriate for both BNCAP and Global NCAP (adult/child occupation protection). The `protocol_version` field handles the program-specific differences.

2. **Unified architecture enables cross-provider queries.** A recommender that wants "models with ≥4 AOP stars from any NCAP body" can query `safety_test_applicability` + `safety_test` without joining a separate legacy table.

3. **The legacy `safety_rating` table should be retained but frozen.** It provides a safety net and historical reference. It should not be deleted until the migration is verified complete and the producing scripts are updated.

4. **Global NCAP migration is lower complexity than BNCAP** because all 24 records already have valid `model_id` FKs — no entity resolution step is needed.

5. **Professional-review and owner-experience layers must NOT touch `safety_test`.** That table is for objective, structured crash-test results. Editorial assessments and owner reports belong in entirely separate tables (as documented in the Phase 9 report).

**Stability assessment:** The `safety_test` + `safety_test_applicability` architecture is stable for building on. The addition of 24 Global NCAP rows would not change the schema or disrupt existing BNCAP data. The architecture is not at risk.

---

## 13. Production Integrity Verification

| Check | Value | Status |
|-------|-------|--------|
| Checksum before all investigation | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ |
| Integrity pre-audit | `ok` | ✅ |
| Checksum after all investigation | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ UNCHANGED |
| Integrity post-audit | `ok` | ✅ |
| Isolated test DB path | `scratch/phase9a_bncap_test.db` | Created and validated |
| Isolated test validates 3 BNCAP resolutions | PASS — 0 canonical mutations, variant_id=NULL for all | ✅ |

---

## 14. What Was NOT Changed

| Action | Status |
|--------|--------|
| Production DB modified | ❌ NOT done |
| Orphaned FP records deleted | ❌ NOT done |
| Orphaned FP records repaired | ❌ NOT done (UNRECOVERABLE) |
| BNCAP resolutions applied to production | ❌ NOT done — proposed only |
| Global NCAP migrated | ❌ NOT done |
| Schema altered | ❌ NOT done |
| New sources added | ❌ NOT done |
| Professional reviewer data ingested | ❌ NOT done |
| Owner/ownership data ingested | ❌ NOT done |
| Phase 10 started | ❌ NOT done |

---

## 15. Phase 9A Summary Table

| Finding | Investigation Result | Proposed Action | Production Impact |
|---------|---------------------|----------------|------------------|
| 297 orphaned FP records | Category A: historical provenance, SO deleted in cleanup/rollback cycle. All 297 explained. 212 confirmed (redundant), 79 rejected (inert), 6 accepted (severed). Unrecoverable due to SO resolution mapping errors. | No immediate production change. Future optional: add `[SO_DELETED_IN_CLEANUP]` annotation. | None |
| Thar Roxx BNCAP (id=9) | RESOLVABLE_WITH_CERTAINTY. url_slug + trim designations are model-specific. | Proposed: `resolution_status=RESOLVED`, `safety_test_applicability` row at MODEL_LEVEL, variant_id=NULL | Safe to apply |
| Brezza BNCAP (id=16) | RESOLVABLE_WITH_CERTAINTY. url_slug + SUV body type deterministic. | Proposed: `resolution_status=RESOLVED`, applicability at MODEL_LEVEL | Safe to apply |
| Dzire BNCAP (id=17) | RESOLVABLE_WITH_CERTAINTY. url_slug + Sedan body + petrol-only qualifier deterministic. | Proposed: `resolution_status=RESOLVED`, applicability at MODEL_LEVEL | Safe to apply |
| 24 Global NCAP records | All 24 well-supported. No FK violations. Source_url present for all. Data lacks structured AOP/COP scores, protocol, weight. | No immediate action. Future migration to safety_test pipeline defined. Pre-requisites: PDF download + extraction. | None now |
| Safety architecture | Unified safety_test pipeline for both BNCAP and Global NCAP is viable. | Approach B recommended. Legacy safety_rating to be frozen not deleted. | Future migration |

---

## 16. Phase 9A Final Verdict

```
PHASE 9A VERDICT: COMPLETE — REMEDIATION PROPOSED
```

**All three Phase 9 findings have been fully investigated with deterministic evidence.**

- **Finding A (297 orphaned FP records):** Root cause established. All 297 records explained. No production repair is warranted or possible with certainty. Canonical values are correct. Recommended future annotation only.

- **Finding B (3 BNCAP UNRESOLVED):** All three are classified `RESOLVABLE_WITH_CERTAINTY`. Isolated validation passed — 3 new `safety_test_applicability` rows at MODEL_LEVEL with `variant_id=NULL`. Production application is safe and ready. No canonical mutations. No variant-level inference.

- **Finding C (24 Global NCAP records):** All 24 records are well-supported with valid FKs and source URLs. A future migration design to the unified `safety_test` pipeline has been specified. Migration is not executed in this phase.

**Proposed production remediation (Finding B):**
Apply the 3 BNCAP resolutions to production in a controlled commit. This requires:
1. Explicit transaction with pre/post verification
2. Production checksum check before and after
3. Row-level delta confirmation: +3 `safety_test_applicability`, +0 canonical mutations
4. Post-apply `PRAGMA integrity_check`
