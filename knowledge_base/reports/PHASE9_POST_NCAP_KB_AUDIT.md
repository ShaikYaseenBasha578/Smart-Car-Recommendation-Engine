# Phase 9 — Post-NCAP Knowledge Base Quality, Coverage, and Readiness Audit

**Audit date:** 2026-09-25  
**Audit type:** Read-only. No production mutations.  
**Production DB:** `knowledge_base/carrec_kb.db`

---

## 1. Executive Status

> [!IMPORTANT]
> Phase 8B (Bharat NCAP Production Ingestion) is confirmed complete. This audit establishes the post-NCAP state of the KB as the authoritative baseline for all future phases.

The CarRec Knowledge Base is **structurally sound** after Phase 8B. All canonical tables are consistent, all foreign keys referencing the canonical hierarchy are valid, and all Phase 8B additions have been independently verified. One pre-existing structural finding is documented: 297 `field_provenance` rows reference `source_observation` IDs that no longer exist in the database. This is a legacy data issue from a prior cleanup phase, not a Phase 8B artefact, and does not affect the correctness of accepted canonical values.

**Audit verdict at end of report: PASS WITH FINDINGS**

---

## 2. Production Baseline

### Checksum and Integrity

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| SHA-1 checksum | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ MATCH |
| `PRAGMA integrity_check` | `ok` | `ok` | ✅ PASS |

### Complete Table Inventory

| Table | Rows | Notes |
|-------|------|-------|
| `manufacturer` | 12 | Canonical |
| `model` | 62 | Canonical |
| `generation` | 62 | Canonical |
| `variant` | 832 | Canonical |
| `powertrain` | 131 | Canonical |
| `source` | 8 | Configuration |
| `source_observation` | 3,451 | Evidence |
| `field_provenance` | 36,445 | Evidence |
| `safety_test` | 37 | BNCAP (Phase 8B) |
| `safety_test_applicability` | 20 | BNCAP (Phase 8B) |
| `safety_rating` | 27 | Pre-existing legacy safety summary |
| `warranty` | 18 | Pre-existing warranty records |
| `variant_alias` | 469 | Pre-existing source alias mappings |
| `sqlite_sequence` | — | Internal |

**Views:** `v_effective_variant`, `v_variant_full`

---

## 3. Canonical Vehicle Coverage

### Hierarchy Summary

| Metric | Value |
|--------|-------|
| Manufacturers | 12 |
| Models | 62 |
| Generations | 62 (1 per model) |
| Variants | 832 |
| Powertrains | 131 |
| Min variants per model | 2 |
| Max variants per model | 53 |
| Avg variants per model | 13.4 |
| Min powertrains per model | 1 |
| Max powertrains per model | 4 |
| Avg powertrains per model | 2.1 |

### Hierarchy Completeness

> [!NOTE]
> All completeness checks pass. No structural gaps.

| Check | Count | Status |
|-------|-------|--------|
| Models with no variants | 0 | ✅ Complete |
| Models with no powertrain records | 0 | ✅ Complete |
| Generations with no variants | 0 | ✅ Complete |
| Variants with no powertrain link | 0 | ✅ Complete |

### Manufacturer Distribution

| Manufacturer | Models |
|---|---|
| Maruti Suzuki | 15 |
| Tata | 8 |
| Toyota | 8 |
| Mahindra | 7 |
| Hyundai | 6 |
| Kia | 4 |
| Honda | 3 |
| Skoda | 3 |
| MG | 2 |
| Nissan | 2 |
| Renault | 2 |
| Volkswagen | 2 |

### Body Type Distribution

| Body Type | Models |
|---|---|
| SUV | 33 |
| Hatchback | 10 |
| MPV | 9 |
| Sedan | 8 |
| Van | 1 |
| Pickup | 1 |

### Fuel Type Distribution (Powertrain Table)

| Fuel Type | Powertrains |
|---|---|
| Petrol | 68 |
| CNG | 24 |
| Diesel | 21 |
| Electric | 11 |
| Petrol Hybrid | 5 |
| Flex Fuel | 1 |
| Diesel Mild Hybrid | 1 |

**OBSERVATION:** CNG is the second-largest powertrain category by distinct powertrain records, consistent with the Indian market. Electric (11) covers the current EV models in the top-62.

---

## 4. Field-Level Coverage Audit

### Variant Table — Core Fields (Total = 832 variants)

| Field | Populated | NULL/Unknown | Coverage % | Classification |
|-------|-----------|--------------|-----------|----------------|
| `price_ex_showroom` | 812 | 20 | 97.6% | ✅ Well-supported |
| `length_mm` | 812 | 20 | 97.6% | ✅ Well-supported |
| `width_mm` | 812 | 20 | 97.6% | ✅ Well-supported |
| `height_mm` | 812 | 20 | 97.6% | ✅ Well-supported |
| `wheelbase_mm` | 812 | 20 | 97.6% | ✅ Well-supported |
| `ground_clearance_mm` | 812 | 20 | 97.6% | ✅ Well-supported |
| `kerb_weight_kg` | 812 | 20 | 97.6% | ✅ Well-supported |
| `seating_capacity` | 812 | 20 | 97.6% | ✅ Well-supported |
| `airbags` | 812 | 20 | 97.6% | ✅ Well-supported |
| `abs` | 812 | 20 | 97.6% | ✅ Well-supported |
| `rear_parking_sensors` | 812 | 20 | 97.6% | ✅ Well-supported |
| `sunroof` | 818 | 14 | 98.3% | ✅ Well-supported |
| `adas_available` | 811 | 21 | 97.5% | ✅ Well-supported |
| `boot_space_litres` | 785 | 47 | 94.4% | ✅ Well-supported |
| `tpms` | 791 | 41 | 95.1% | ✅ Well-supported |
| `rear_camera` | 787 | 45 | 94.6% | ✅ Well-supported |
| `esc` | 783 | 49 | 94.1% | ✅ Well-supported |
| `automatic_climate_control` | 796 | 36 | 95.7% | ✅ Well-supported |
| `android_auto` | 788 | 44 | 94.7% | ✅ Well-supported |
| `apple_carplay` | 788 | 44 | 94.7% | ✅ Well-supported |
| `fuel_tank_litres` | 725 | 107 | 87.1% | ✅ Well-supported |
| `cruise_control` | 629 | 203 | 75.6% | ✅ Well-supported |
| `wireless_charging` | 577 | 255 | 69.4% | ⚠️ Partially supported |

> [!NOTE]
> The 20 variants with no price/dimension data represent a structurally consistent group — these are likely variants that could not be resolved to authoritative spec data. The NULL is correct (precision over coverage). `wireless_charging` at 69.4% is the lowest non-powertrain-specific field but is not critical for primary recommendation filtering.

### Powertrain-Specific Efficiency Fields

> [!IMPORTANT]
> Denominators are powertrain-correct. This corrects the Phase 7 aggregate-denominator error.

| Field | Denominator (correct) | Populated | Coverage % | Classification |
|-------|----------------------|-----------|-----------|----------------|
| Petrol mileage (`mileage_arai_kmpl`) | 546 petrol variants | 359 | 65.8% | ⚠️ Partially supported |
| Diesel mileage (`mileage_arai_kmpl`) | 167 diesel variants | 84 | 50.3% | ⚠️ Partially supported |
| CNG mileage (`mileage_arai_km_per_kg`) | 82 CNG variants | 39 | 47.6% | ⚠️ Partially supported |
| EV claimed range (`claimed_ev_range_km`) | 37 EV variants | 35 | 94.6% | ✅ Well-supported |

**KNOWN GAP:** CNG mileage (47.6%) remains the weakest efficiency field, as identified in Phase 7A. Petrol (65.8%) and diesel (50.3%) are partially supported. EV range is near-complete. Efficiency data for non-EV powertrains is a meaningful recommendation gap.

### Transmission and Drivetrain

| Transmission | Variants | % |
|---|---|---|
| Manual | 447 | 53.7% |
| Torque Converter | 143 | 17.2% |
| AMT | 84 | 10.1% |
| DCT | 54 | 6.5% |
| CVT | 41 | 4.9% |
| Automatic | 37 | 4.4% |
| e-CVT | 20 | 2.4% |
| iMT | 6 | 0.7% |

| Drivetrain | Variants |
|---|---|
| FWD | 741 (89.1%) |
| RWD | 60 (7.2%) |
| 4WD | 26 (3.1%) |
| AWD | 5 (0.6%) |

**OBSERVATION:** All 832 variants are flagged `is_discontinued = 0`, meaning the KB currently represents only active variants. The `base_variant_id` inheritance mechanism is active: 20 variants carry a base reference (for edition/spec inheritance via `v_effective_variant` view), with 812 root variants.

---

## 5. Provenance Audit

### Source Table

| ID | Name | Type | Authority Tier |
|----|------|------|----------------|
| 1 | v6_migration | migration | 2 |
| 2 | 91wheels | aggregator | 2 |
| 3 | v3cars | aggregator | 2 |
| 4 | carwale | aggregator | 3 |
| 5 | cardekho | aggregator | 3 |
| 6 | oem | oem | 1 (highest) |
| 7 | bharat_ncap | rating_agency | 1 (highest) |
| 8 | global_ncap | rating_agency | 1 (highest) |

**OBSERVATION:** Source 8 (`global_ncap`) is registered but has no `source_observation` rows. Its data is represented in the separate `safety_rating` table (24 Global NCAP rows), not through the `source_observation` + `safety_test` provenance pipeline. This is an architectural inconsistency — see Section 7.

### source_observation Distribution

| Source | Observations |
|--------|-------------|
| v6_migration | 864 |
| carwale | 860 |
| 91wheels | 845 |
| v3cars | 845 |
| bharat_ncap | 37 |
| **Total** | **3,451** |

### source_observation Resolution Status

| Status | Count | Notes |
|--------|-------|-------|
| `resolved` | 1,700 | Matched to a source without variant binding |
| `applied` | 812 | Matched and applied to a canonical variant |
| `unresolvable` | 470 | Could not be resolved to any variant |
| `resolved_with_warning` | 254 | Resolved with caveats |
| `unresolved` | 134 | Pending resolution |
| `model_level` | 44 | Resolved to model, not variant |
| `RESOLVED` | 20 | BNCAP resolved (case difference) |
| `NO_MATCH` | 10 | BNCAP no-match |
| `UNRESOLVED` | 7 | BNCAP unresolved |

**OBSERVATION:** The BNCAP `resolution_status` values (`RESOLVED`, `NO_MATCH`, `UNRESOLVED`) use a different case convention than the OEM observations (`resolved`, `applied`, `unresolvable`). This is a minor naming inconsistency that does not affect data integrity but may complicate future queries.

### field_provenance

| Metric | Value |
|--------|-------|
| Total field_provenance rows | 36,445 |
| Distinct variants with field provenance | 832 |
| Variants with no field provenance | 0 |
| Broken variant FK references | 0 |
| field_provenance rows with NULL source_observation_id | 0 |
| Broken source_observation FK references | **297** |

> [!WARNING]
> **AUDIT FINDING — PRE-EXISTING:** 297 `field_provenance` rows reference `source_observation` IDs in the range 2608–2661 that no longer exist in the database. These source_observations were deleted in a prior cleanup phase. The affected FP rows cover 23 canonical variants across models including Creta, Verna, Harrier, Kushaq, and others.
>
> The `decision` breakdown of the 297 broken references:
> - `confirmed`: 212 rows
> - `rejected`: 79 rows  
> - `accepted`: 6 rows
>
> The `rejected` rows are inert (they record a decision to reject a value). The `confirmed`/`accepted` rows retain their `accepted_value` directly on the field_provenance record, so canonical values are not lost even with the broken SO link. However, the audit trail back to the original source evidence for those 297 field decisions is severed.
>
> **Severity:** Medium. Canonical values are correct. Audit trail for 297 field decisions is incomplete.
> **Recommendation:** Document this in the next engineering phase. Do not attempt repair during Phase 9.

---

## 6. Bharat NCAP Coverage Audit

### Test Totals

| Metric | Count |
|--------|-------|
| Total safety_test records | 37 |
| Tests with applicability mappings | 20 |
| Tests without applicability mappings | 17 |
| Total applicability rows | 20 |
| Variant-level mappings | 0 |

### Tests by Resolution Status

| Status | Count | Interpretation |
|--------|-------|----------------|
| RESOLVED | 20 | Mapped to ≥1 canonical model |
| NO_MATCH | 10 | Vehicle not in CarRec top-62 |
| UNRESOLVED | 7 | Ambiguous or manufacturer not in CarRec |

### Applicability by Confidence Level

| Match Confidence | Rows |
|---|---|
| MODEL_LEVEL | 19 |
| FAMILY_LEVEL | 1 (Tata Harrier/Safari shared platform) |
| VARIANT_LEVEL | 0 (intentionally: strict principle preserved) |

### Models WITH Bharat NCAP Coverage (17 canonical models)

| Manufacturer | Model | Confidence |
|---|---|---|
| Honda | Amaze | MODEL_LEVEL |
| Hyundai | Venue | MODEL_LEVEL |
| Kia | Seltos | MODEL_LEVEL |
| Kia | Syros | MODEL_LEVEL |
| Mahindra | XUV 3XO | MODEL_LEVEL |
| Mahindra | XUV 7XO | MODEL_LEVEL |
| Maruti Suzuki | Baleno | MODEL_LEVEL (×2 — 2-airbag and 6-airbag tests) |
| Maruti Suzuki | Victoris | MODEL_LEVEL |
| Maruti Suzuki | e VITARA | MODEL_LEVEL |
| Renault | Duster | MODEL_LEVEL |
| Skoda | Kylaq | MODEL_LEVEL |
| Tata | Altroz | MODEL_LEVEL |
| Tata | Harrier | MODEL_LEVEL + FAMILY_LEVEL |
| Tata | Nexon | MODEL_LEVEL |
| Tata | Nexon EV | MODEL_LEVEL |
| Tata | Punch EV | MODEL_LEVEL (×2 — original and 2026 update) |
| Toyota | Innova Hycross | MODEL_LEVEL |

> [!NOTE]
> Baleno has two separate BNCAP tests (2-airbag and 6-airbag configurations). Both are correctly mapped to the same model_id=15 as distinct `safety_test` rows with one `safety_test_applicability` row each.

### BNCAP Safety Gap: 45 Models with No Bharat NCAP Result

The following 45 of 62 canonical models have no Bharat NCAP applicability in the current KB. **This does not mean these models are unsafe** — it means no Bharat NCAP result is currently represented for them.

Prominent gaps include: Hyundai Creta, Hyundai Grand i10 Nios, Hyundai Verna, Maruti Suzuki Brezza, Maruti Suzuki Dzire, Maruti Suzuki Swift, Maruti Suzuki WagonR, Tata Nexon (wait — covered), MG Hector, MG Windsor EV, all Mahindra SUVs without recent tests, all Skoda Kushaq/Slavia, all Tiago/Tigor, all Toyota models except Innova Hycross, all Volkswagen models.

**KNOWN GAP:** 72.6% of the canonical 62-model KB (45 models) has no current Bharat NCAP representation. Several of these models may have been tested under Bharat NCAP since Phase 8A data capture. The 7 UNRESOLVED tests include vehicles (Brezza, Dzire) that are in CarRec but whose manufacturer name ("MARUTI" without "Suzuki") caused the resolution to fail. These are addressable via alias table additions.

### UNRESOLVED Tests — Classification

| Test | Why UNRESOLVED | Addressable? |
|------|----------------|--------------|
| CITROEN-BASALT | Citroen not in CarRec top-62 | No — not in scope |
| CITROEN C3 AIRCROSS | Citroen not in CarRec top-62 | No — not in scope |
| MAHINDRA THAR ROXX | model_id ambiguity (Thar=53, Thar Roxx=54) | Yes — alias table |
| MARUTI BREZZA | "MARUTI" doesn't match "Maruti Suzuki" | Yes — alias table |
| MARUTI DZIRE GASOLINE | Same as above | Yes — alias table |
| VINFAST VF6 | VinFast not in CarRec top-62 | No — not in scope |
| VINFAST VF7 | VinFast not in CarRec top-62 | No — not in scope |

**AUDIT FINDING:** 3 of the 7 UNRESOLVED tests (Thar Roxx, Brezza, Dzire) could be resolved with targeted alias table additions. These tests currently produce no applicability mappings, meaning the safety data exists in the KB but is not linked to CarRec canonical models.

---

## 7. Safety Data Semantics Audit

### safety_test Schema Coverage (37 records — all BNCAP)

| Field | Populated | % | Notes |
|-------|-----------|---|-------|
| `tested_vehicle_name` | 37 | 100% | ✅ |
| `tested_variant_config` | 37 | 100% | ✅ |
| `body_type` | 37 | 100% | ✅ |
| `crash_test_weight_kg` | 37 | 100% | ✅ |
| `year_of_publication` | 37 | 100% | ✅ |
| `test_period` | 37 | 100% | ✅ |
| `protocol_version` | 37 | 100% | ✅ |
| `aop_score` | 37 | 100% | ✅ |
| `aop_stars` | 37 | 100% | ✅ |
| `cop_score` | 37 | 100% | ✅ |
| `cop_stars` | 37 | 100% | ✅ |
| `sat_summary` | 37 | 100% | ✅ |
| `factsheet_url` | 37 | 100% | ✅ |
| `artifact_path` | 37 | 100% | ✅ |
| `artifact_checksum` | 37 | 100% | ✅ |
| `resolution_justification` | 37 | 100% | ✅ |
| `applicability_notes` | 37 | 100% | ✅ |

**OBSERVATION:** Every safety_test field is 100% populated. The BNCAP data layer is complete and dense.

### AOP/COP Star Distribution

| AOP Stars | COP Stars | Count |
|---|---|---|
| 4 | 3 | 2 |
| 4 | 4 | 1 |
| 5 | 4 | 2 |
| 5 | 5 | 32 |

**OBSERVATION:** 32 of 37 tests (86%) are 5-star AOP and 5-star COP. This reflects the relatively recent Bharat NCAP program which has primarily tested newer, safety-equipped vehicles.

### Legacy safety_rating Table

> [!NOTE]
> The `safety_rating` table (27 rows) is a pre-existing structure that predates the Phase 8 BNCAP pipeline. It stores simplified star-rating summaries.
> - 3 rows: Bharat NCAP (Nexon, Nexon EV, Punch EV) — these overlap with safety_test/safety_test_applicability
> - 24 rows: Global NCAP — stored only here, not in safety_test pipeline
>
> **Architectural observation:** Two parallel safety data representations exist:
> 1. `safety_rating` — simple star-rating summary, legacy, pre-Phase-8
> 2. `safety_test` + `safety_test_applicability` — rich provenance-backed structure (Phase 8)
>
> The 24 Global NCAP results in `safety_rating` are not backed by `source_observation` provenance. Source 8 (`global_ncap`) exists in the source table but has no `source_observation` rows.
>
> **AUDIT FINDING:** The KB contains two architecturally separate safety data layers. `safety_rating` is an unprovened legacy layer. `safety_test` is the authoritative provenance-backed layer. For Global NCAP data, only the legacy layer exists.

---

## 8. Data Consistency Findings

### All FK Consistency Checks

| Check | Result |
|-------|--------|
| model → manufacturer FK validity | ✅ 0 violations |
| generation → model FK validity | ✅ 0 violations |
| variant → model FK validity | ✅ 0 violations |
| variant → generation FK validity (where set) | ✅ 0 violations |
| powertrain → model FK validity | ✅ 0 violations |
| variant.powertrain → same model as variant | ✅ 0 violations |
| safety_test_applicability model → manufacturer | ✅ 0 violations |
| safety_test_applicability generation → model | ✅ 0 violations |
| variant_alias → variant FK validity | ✅ 0 violations |
| Duplicate variant names (per model+generation) | ✅ 0 violations |
| Duplicate powertrain records | ✅ 0 violations |
| Duplicate generation names per model | ✅ 0 violations |
| EV variants with ICE mileage field | ✅ 0 violations |
| Non-EV variants with EV range field | ✅ 0 violations |
| Non-CNG variants with CNG mileage field | ✅ 0 violations |
| Variants with zero/negative price | ✅ 0 violations |
| source_observation → source FK validity | ✅ 0 violations |
| source_observation broken variant FK | ✅ 0 violations |
| field_provenance broken variant FK | ✅ 0 violations |
| **field_provenance broken source_observation FK** | ⚠️ **297 violations** |

### Pre-Existing Finding: 297 Orphaned field_provenance Records

- **Table:** `field_provenance`
- **Record IDs:** FP rows 31888–highest in batch referencing SO IDs 2608–2661
- **Issue:** `source_observation_id` values 2608–2661 no longer exist in `source_observation`
- **Why anomaly:** The referenced SO records were deleted in a prior cleanup phase without cascading cleanup to `field_provenance`
- **Affected variants:** 23 variants across Creta, Verna, Harrier, Kushaq, and others
- **Decision breakdown:** 212 `confirmed`, 79 `rejected`, 6 `accepted`
- **Severity:** Medium — audit trail severed for 297 field decisions; canonical values unaffected
- **Classification:** Pre-existing data hygiene issue, not a Phase 8B artefact

### ADAS Field Clarification

The `adas_tier` column stores numeric values (0.0 = no ADAS, 1.0 = ADAS present), not text tier names. The distribution is internally consistent: 698 variants have `adas_available=0` and `adas_tier=0.0`; 110 have `adas_available=1` and `adas_tier=1.0`. This is not an inconsistency — both fields encode the same boolean differently.

**OBSERVATION:** The `adas_tier` field name implies a categorical tier classification (e.g., Level 1/2/3 or named tiers) but in practice stores a binary numeric equivalent of `adas_available`. This makes `adas_tier` redundant in the current state. Future enrichment should distinguish ADAS sophistication levels.

---

## 9. Precision / Unknown / Quarantine Findings

### Design Principle Verification

The core principle is: **authoritative evidence → canonical value; ambiguous evidence → unknown/unresolved**.

| Principle Check | Result |
|---|---|
| UNRESOLVED/NO_MATCH BNCAP tests have applicability rows | ✅ 0 violations (correct: none should) |
| BNCAP tests mapped at variant level | ✅ 0 (all NULL variant_id — correct) |
| EV-specific mileage stored on ICE variants | ✅ 0 violations |
| ICE mileage stored on EV variants | ✅ 0 violations |
| `applied` source_observations without variant_id | ✅ 0 violations |
| Unresolvable/rejected observations forced into canonical | Not directly queryable, but FP `rejected` decision records confirm rejections are preserved |

### resolution_status Case Inconsistency

**AUDIT FINDING (Minor):** `source_observation.resolution_status` uses lowercase vocabulary for OEM observations (`resolved`, `applied`, `unresolvable`, `resolved_with_warning`, `unresolved`, `model_level`) but uppercase vocabulary for BNCAP observations (`RESOLVED`, `NO_MATCH`, `UNRESOLVED`). The schema comment shows the intended values are lowercase. The uppercase values were written by the Phase 8 ingestion script.

- **Severity:** Low — does not affect data correctness
- **Impact:** Queries filtering on `resolution_status` must handle both cases
- **Recommendation:** Normalize to lowercase in a future maintenance pass

### BNCAP Resolution Observations

The 7 UNRESOLVED tests correctly preserve their ambiguity:
- Citroen and VinFast are not in CarRec — correctly unresolved (no CarRec models to map to)
- Thar Roxx produced multiple matches (model_id 53=Thar, 54=Thar Roxx) — correctly deferred rather than guessing
- Maruti Brezza/Dzire used "MARUTI" title — manufacturer lookup failed; data is preserved but unmapped

No inferred facts were introduced. The fail-closed principle is observed.

---

## 10. Recommendation Readiness

### Field Coverage Assessment for Recommendation/Filtering

| Dimension | Coverage | Status | Notes |
|---|---|---|---|
| Price (ex-showroom) | 97.6% | ✅ Well-supported | Core filter |
| Fuel type | 100% (via powertrain) | ✅ Well-supported | Core filter |
| Transmission | 100% | ✅ Well-supported | Core filter |
| Body type | 100% (via model) | ✅ Well-supported | Core filter |
| Drivetrain | 100% | ✅ Well-supported | |
| Seating capacity | 97.6% | ✅ Well-supported | Practical filter |
| Dimensions (L/W/H/WB) | 97.6% | ✅ Well-supported | |
| Ground clearance | 97.6% | ✅ Well-supported | |
| Boot space | 94.4% | ✅ Well-supported | |
| Airbags | 97.6% | ✅ Well-supported | Safety filter |
| ABS / ESC | 97.6% / 94.1% | ✅ Well-supported | Safety filter |
| TPMS | 95.1% | ✅ Well-supported | |
| Rear parking sensors + camera | 97.6% / 94.6% | ✅ Well-supported | |
| ADAS availability | 97.5% | ✅ Well-supported | |
| Sunroof | 98.3% | ✅ Well-supported | |
| Climate control | 95.7% | ✅ Well-supported | |
| Android Auto / CarPlay | 94.7% | ✅ Well-supported | |
| Bharat NCAP safety | 27.4% of models (17/62) | ⚠️ Partially supported | Only model-level |
| Global NCAP safety | ~39% of models (via safety_rating) | ⚠️ Partially supported | Legacy layer, no provenance |
| Petrol efficiency (ARAI) | 65.8% of petrol variants | ⚠️ Partially supported | |
| Diesel efficiency (ARAI) | 50.3% of diesel variants | ⚠️ Partially supported | |
| CNG efficiency (ARAI) | 47.6% of CNG variants | ⚠️ Partially supported | |
| EV range | 94.6% of EV variants | ✅ Well-supported | |
| Cruise control | 75.6% | ✅ Well-supported | |
| Wireless charging | 69.4% | ⚠️ Partially supported | |
| Ride quality | Not represented | ❌ Unsupported | Editorial |
| Handling / NVH | Not represented | ❌ Unsupported | Editorial |
| Reliability data | Not represented | ❌ Unsupported | Owner experience |
| Real-world efficiency | Not represented | ❌ Unsupported | Owner experience |
| Service/parts experience | Not represented | ❌ Unsupported | Owner experience |

**OBSERVATION:** The KB currently supports a strong **specification-based** recommender. Filtering by price, fuel type, body type, transmission, seating capacity, dimensions, safety equipment, and infotainment is well-supported. Efficiency-based filtering for ICE powertrains is partial. Safety-rating-based filtering is available for 17 models (BNCAP) and approximately 24 models (Global NCAP via legacy layer) but not at variant level.

---

## 11. Professional Reviewer Layer Readiness

> [!NOTE]
> No implementation. Schema readiness analysis only.

### What Would Need to Exist

Professional reviewer information captures editorial assessment — subjective, source-attributed, potentially conflicting between reviewers, and fundamentally different from OEM specifications.

#### New Entities Required

**`reviewer_source`** — Identifies the review outlet:
- `id`, `name` (e.g., "Autocar India"), `source_type` = 'review_outlet', `authority_tier`, `base_url`
- Could reuse the existing `source` table with `source_type='review'`

**`vehicle_review`** — One record per review per vehicle:
- `id`, `source_id` → reviewer_source, `model_id`, `generation_id` (nullable), `variant_id` (nullable — most reviews don't test all variants)
- `review_url`, `review_date`, `reviewer_name`, `raw_article_url`, `artifact_path`, `artifact_checksum`
- Must NOT collapse to a single truth — retain full source attribution

**`review_dimension`** — One row per assessed quality dimension per review:
- `id`, `review_id` → vehicle_review
- `dimension` (e.g., 'ride_quality', 'handling', 'nVH', 'engine_refinement', 'gearbox')
- `sentiment` — structured vocabulary: 'positive', 'negative', 'neutral', 'qualified' (not free text)
- `raw_quote` — verbatim quote preserving original evidence
- `confidence` — extraction confidence if extracted automatically

**`review_recommendation`** — Explicit reviewer verdict:
- `id`, `review_id`, `target_group` (e.g., 'highway commuters', 'families'), `recommendation_type` ('recommended_for', 'not_recommended_for', 'notable_caveat')
- `raw_text` — verbatim

#### What Existing Tables Support

- `source` — Already structured to accept new sources; `source_type='review'` is a valid extension
- `source_observation` — Could absorb a review's raw payload but is currently designed for variant-observation matching; not ideal for article-level evidence
- `variant` — FK target for variant-level review findings

#### Critical Design Constraints

1. **Never collapse multiple reviewer opinions into a single canonical fact.** A reviewer's assessment of ride quality is not a fact — it is an attributed opinion. Conflicting opinions must be preserved as separate rows, not averaged or merged.
2. **Distinguish fact from assessment explicitly.** The schema must make it structurally impossible to confuse `variant.airbags = 6` (OEM fact) with `review_dimension.sentiment = 'positive'` for 'ride_quality' (editorial assessment).
3. **Reviewer identity must be preserved** — `reviewer_name` on the review record, not collapsed to outlet level.
4. **Generation/variant specificity matters** — A review of the pre-facelift Creta is not applicable to the post-facelift. Generation-gating is required.

---

## 12. Owner / Ownership Advice Layer Readiness

> [!NOTE]
> No implementation. Schema readiness analysis only.

### What Would Need to Exist

Owner experience is distinct from both OEM specifications and professional editorial assessment. It is aggregate anecdotal evidence with variable reliability, high individual variance, and temporal drift (ownership experience changes with age of vehicle fleet).

#### New Entities Required

**`owner_experience_source`** — Identifies the owner community:
- `id`, `platform` (e.g., 'TeamBHP', 'CarDekho user reviews', 'MouthShut'), `source_type` = 'owner_community'
- Critically: authority_tier for owner sources must be *lower* than OEM/NCAP

**`ownership_theme`** — Structured vocabulary of ownership dimensions:
- `real_world_efficiency`, `reliability`, `service_quality`, `parts_availability`, `highway_comfort`, `city_comfort`, `long_term_build_quality`, `common_complaints`, `known_issues`
- Must be a controlled vocabulary, not free text

**`owner_report`** — Aggregated signal per model per theme per source platform:
- `id`, `model_id`, `generation_id`, `source_id`, `theme`, `sentiment_ratio` (positive/negative/neutral counts, not a single verdict), `sample_size`, `collection_date`, `evidence_summary`
- Individual reports must not be presented as universal facts
- Must store sample_size to allow downstream confidence weighting

#### Critical Design Constraints

1. **Individual anecdote ≠ fact.** Owner reports must be represented as aggregate signals with sample sizes, not individual assertions.
2. **Temporal currency matters.** A 2019 complaint about a model's gearbox may not apply to 2024 units. Reports must carry `collection_date` and ideally a `model_year_range`.
3. **Distinguish real-world efficiency from ARAI efficiency.** Real-world owner-reported fuel economy is a distinct field, not a correction to `mileage_arai_kmpl`. Both must coexist without overwriting each other.
4. **Service experience is market-specific.** The same model can have vastly different service network experiences in different geographies. The KB would need location-gating if this dimension is pursued.
5. **Platform bias must be acknowledged.** TeamBHP users skew enthusiast/educated; CarDekho reviews may skew toward dissatisfied customers who bother to write. Source attribution allows downstream consumers to apply appropriate weighting.

#### What Existing Tables Support

- `source` — Can accommodate owner community sources with appropriate `authority_tier`
- `model`, `generation` — Natural FK anchors for owner reports
- The existing `warranty` table is adjacent: it represents a factual ownership-dimension (OEM-warranted coverage) and is already present

---

## 13. Identified Coverage Gaps

| Gap | Coverage | Recommendation Impact | Evidence Availability | Complexity | Risk |
|-----|----------|----------------------|----------------------|------------|------|
| BNCAP: 45 of 62 models unrepresented | High (72.6% gap) | High — safety filtering incomplete | Medium (BNCAP public; 3 UNRESOLVED fixable) | Low (alias table fix for 3; scraping for new tests) | Low |
| Global NCAP: 24 results in legacy layer without provenance | Medium | Medium — data exists but not in pipeline | High (Global NCAP public) | Medium (requires ingestion into safety_test pipeline) | Low |
| Petrol/Diesel ARAI efficiency: 34–50% gap | High | High — efficiency is a primary recommender input | Medium (OEM brochures; partially done) | Medium | Low |
| CNG ARAI efficiency: 52% gap | Medium | Medium for CNG-focused recommendations | Medium | Medium | Low |
| `wireless_charging`: 30.6% gap | Low | Low | Medium | Low | Low |
| 297 orphaned field_provenance FKs | — | None (canonical values correct) | N/A | Low (cleanup) | Low |
| `resolution_status` case inconsistency | — | None | N/A | Low (migration) | Low |
| 3 BNCAP UNRESOLVED fixable via alias | Low | Low (3 models) | High | Low | Low |
| ADAS tier not granular (binary only) | Medium | Medium | Low (no structured source) | Medium | Medium |
| Ride quality / handling / NVH | 0% | High for quality recommendations | Medium (editorial) | High | High (editorial reliability) |
| Real-world fuel economy | 0% | Medium | Medium (owner communities) | High | High (anecdote reliability) |
| Reliability / long-term ownership | 0% | High for ownership advice | Medium | High | High |

---

## 14. Recommended Next Engineering Phase

Based on this audit, the following is the recommended engineering priority ordering for consideration. **No implementation is authorized during Phase 9.**

### Priority A — Low effort, high precision, zero risk

1. **BNCAP alias table extension (3 tests):** Add aliases for `MARUTI → Maruti Suzuki` and explicit `Thar Roxx` resolution to map 3 currently-UNRESOLVED tests. This would move Brezza, Dzire, and Thar Roxx from unresolved to model-level applicability. No scraping required.

2. **`resolution_status` case normalization:** Normalize the 37 BNCAP `source_observation.resolution_status` values from `RESOLVED`/`NO_MATCH`/`UNRESOLVED` to lowercase to match the existing vocabulary. Low-risk, low-effort migration.

### Priority B — Medium effort, high value

3. **Global NCAP ingestion into safety_test pipeline:** 24 Global NCAP results exist in the legacy `safety_rating` table without source provenance. Ingesting them into `safety_test` + `safety_test_applicability` with proper `source_observation` provenance would:
   - Extend safety coverage to an additional ~10 models not in BNCAP
   - Make Global NCAP data consistent with BNCAP in the provenance architecture

4. **Efficiency data enrichment (Petrol, Diesel, CNG):** Continue OEM brochure extraction targeting the remaining mileage gaps. Petrol at 65.8% and diesel at 50.3% are material gaps for efficiency-based recommendation.

### Priority C — Higher effort, higher reward

5. **BNCAP refresh:** Additional vehicles have likely been tested since Phase 8A scraping. A controlled re-scrape and incremental ingestion would increase model coverage.

6. **orphaned field_provenance cleanup:** A targeted cleanup pass could delete the 297 `rejected` FP rows with broken SO references and document the `confirmed`/`accepted` ones as manually evidenced.

### Priority D — Design phase before implementation

7. **Professional reviewer schema design:** No data ingestion. Define the schema entities, provenance requirements, and vocabulary before any implementation.

8. **Owner/ownership experience schema design:** Same — design before implementation.

---

## 15. Final Phase 9 Verdict

### Summary Table

| Audit Area | Finding | Status |
|---|---|---|
| Production checksum | Unchanged: `c1e0647ce463c98eebd9d2bd9470940fdb23ead5` | ✅ PASS |
| Database integrity | `ok` (verified twice: pre- and post-audit) | ✅ PASS |
| Canonical hierarchy completeness | 62 models, all with variants, powertrains, generations | ✅ PASS |
| Canonical FK consistency | Zero violations across all canonical tables | ✅ PASS |
| Powertrain-specific field denominators | Correctly applied (petrol/diesel/CNG/EV denominated separately) | ✅ PASS |
| Bharat NCAP data quality | 37 tests, all fields 100% populated, all artifacts verified | ✅ PASS |
| BNCAP provenance integrity | 37/37 valid chains; 0 broken, 0 URL mismatches | ✅ PASS |
| BNCAP applicability semantics | 0 variant-level mappings; UNRESOLVED correctly unmapped | ✅ PASS |
| BNCAP coverage gap | 45/62 models unrepresented | ⚠️ KNOWN GAP |
| field_provenance orphaned FKs | 297 records with broken SO links (pre-existing) | ⚠️ FINDING |
| source_observation case inconsistency | BNCAP uses uppercase status vocabulary | ⚠️ FINDING |
| Legacy safety_rating layer | 24 Global NCAP results not in provenance pipeline | ⚠️ FINDING |
| Efficiency field coverage (ICE/CNG) | 47.6–65.8% populated | ⚠️ KNOWN GAP |
| Recommendation readiness (spec-based) | Core dimensions well-supported | ✅ PASS |
| Professional review layer | Not implemented; schema readiness analyzed | ✅ ASSESSED |
| Owner experience layer | Not implemented; schema readiness analyzed | ✅ ASSESSED |
| No production mutations | Checksum unchanged throughout audit | ✅ CONFIRMED |

---

## PHASE 9 AUDIT VERDICT: PASS WITH FINDINGS

The CarRec Knowledge Base is **structurally sound** after Phase 8B. All canonical vehicle data is internally consistent with zero FK violations. The Bharat NCAP safety layer is complete, provenance-backed, and semantically strict. The KB correctly preserves uncertainty — NULL values are legitimate unknowns, unresolved tests are correctly unmapped, and no editorial inferences have been introduced as facts.

**Findings requiring future attention (none block Phase 10 design):**
1. 297 orphaned `field_provenance` records — audit trail severed, canonical values unaffected
2. BNCAP `resolution_status` case inconsistency — cosmetic, no data impact
3. 45/62 models have no BNCAP safety representation — material gap, addressable incrementally
4. Global NCAP data exists in legacy `safety_rating` without provenance — architectural debt
5. 3 BNCAP UNRESOLVED tests fixable via alias table — low-hanging fruit

None of these findings constitute a data integrity failure. The KB is ready for the design of the next data layer.
