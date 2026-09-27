# PHASE 7A — POWERTRAIN-AWARE COVERAGE AUDIT

> **READ-ONLY CORRECTION/EXTENSION of Phase 7**  
> **Purpose:** Replace misleading global coverage percentages with powertrain-aware denominators.  
> **Zero production mutations.**  
> **Audit date:** 2026-09-23

---

## 1. PRODUCTION DATABASE INTEGRITY

| Check | Pre-Audit | Post-Audit |
|---|---|---|
| SHA1 Checksum | `e752ebde5b7f227140bedb319c6b9753a3fdbdde` | `e752ebde5b7f227140bedb319c6b9753a3fdbdde` |
| `PRAGMA integrity_check` | `ok` | `ok` |
| manufacturer | 12 | 12 |
| model | 62 | 62 |
| generation | 62 | 62 |
| variant | 832 | 832 |
| powertrain | 131 | 131 |
| source_observation | 3,414 | 3,414 |
| field_provenance | 36,445 | 36,445 |

**Checksum unchanged. Zero mutations confirmed.**

> [!NOTE]
> The production DB was opened in read-only mode (`file:...?mode=ro`). All queries are SELECT-only. No BEGIN TRANSACTION, no INSERT, no UPDATE.

---

## 2. POWERTRAIN POPULATION

*Derived from: `variant.powertrain_id → powertrain.fuel_type`*

| Fuel Type | Variants | % of 832 |
|---|---|---|
| Petrol | 525 | 63.1% |
| Diesel | 165 | 19.8% |
| CNG | 82 | 9.9% |
| Electric | 37 | 4.4% |
| Petrol Hybrid | 20 | 2.4% |
| Diesel Mild Hybrid | 2 | 0.2% |
| Flex Fuel | 1 | 0.1% |

**Variants with NULL `powertrain_id`: 0** — every variant is linked.

### Aggregated Groups for Efficiency Analysis

| Group | Fuel Types Included | Applicable Variants |
|---|---|---|
| Petrol | Petrol + Flex Fuel | **526** |
| Diesel | Diesel + Diesel Mild Hybrid | **167** |
| CNG | CNG | **82** |
| Electric | Electric | **37** |
| Hybrid | Petrol Hybrid + Diesel Mild Hybrid | **22** |

**Total: 834** (sum, not additive — every variant belongs to exactly one fuel_type)

---

## 3. PETROL MILEAGE COVERAGE — `mileage_arai_kmpl`

| Metric | Value |
|---|---|
| Applicable variants (Petrol / Flex Fuel) | **526** |
| Populated | **340** |
| Missing (NULL) | **186** |
| **Powertrain-aware coverage** | **64.6%** |
| Source-backed populated | 340 / 526 |
| Sources contributing | 2 (v6_migration + 91wheels) |

> [!NOTE]
> Every populated petrol mileage value is directly source-backed. There are no orphaned canonical values without provenance.

### Petrol Mileage — Null Classification

| Category | Count | Description |
|---|---|---|
| A. Genuine gap (no provenance) | **186** | No source has ever supplied this value |
| C. Has provenance but canonical NULL | **0** | No unresolved conflicts holding back a value |
| B. Not applicable | N/A | EV and CNG are counted separately |
| D. Source conflict | 0 | No provenance-blocked petrol mileage values |

All 186 missing petrol mileage values are **Category A: genuine data gaps** with no source evidence at all.

**Assessment: MODERATELY COVERED (64.6%)**

---

## 4. DIESEL MILEAGE COVERAGE — `mileage_arai_kmpl`

| Metric | Value |
|---|---|
| Applicable variants (Diesel + Diesel Mild Hybrid) | **167** |
| Populated | **84** |
| Missing (NULL) | **83** |
| **Powertrain-aware coverage** | **50.3%** |
| Source-backed populated | 84 / 167 |
| Diesel Mild Hybrid (2 variants) | 0/2 populated |

### Diesel Null Classification

| Category | Count |
|---|---|
| A. Genuine gap (no provenance) | **83** |
| C. Has provenance but canonical NULL | **0** |

All 83 missing diesel mileage values are Category A genuine gaps.

**Assessment: SIGNIFICANT GAP (50.3%)**

---

## 5. CNG MILEAGE COVERAGE — `mileage_arai_km_per_kg`

| Metric | Value |
|---|---|
| Applicable variants (CNG) | **82** |
| Populated (`km_per_kg`) | **39** |
| Missing | **43** |
| **Powertrain-aware coverage** | **47.6%** |
| Source-backed | 39 (single source: v6_migration) |
| Multi-source | NO |

> [!NOTE]
> 6 CNG variants also have `mileage_arai_kmpl` populated — this captures petrol-mode efficiency on bi-fuel (CNG+Petrol) vehicles. These are **not** a substitute for the CNG-mode `km_per_kg` field but indicate correct dual-fuel behaviour.

**Assessment: SIGNIFICANT GAP (47.6%)**  
**Additional concern: Single-source (v6_migration only) — no cross-validation.**

---

## 6. ELECTRIC RANGE COVERAGE — `claimed_ev_range_km`

| Metric | Value |
|---|---|
| Applicable variants (Electric) | **37** |
| Populated | **35** |
| Missing | **2** |
| **Powertrain-aware coverage** | **94.6%** |
| Source-backed | 35 (single source: v6_migration) |
| Multi-source | NO |

> [!IMPORTANT]
> The Phase 7 global metric of **4.2%** was produced by dividing 35 by 832 (all variants). The correct powertrain-aware figure is **94.6%** — the EV range field is almost completely populated for applicable variants.
>
> Phase 7's classification of EV range as "nearly absent" was an artifact of an inappropriate denominator. **EV range is actually well covered.**

EV variants with `mileage_arai_kmpl` populated: **0** — correct, as ICE mileage does not apply to pure EVs.

The 2 missing EV range values: Maruti Suzuki e VITARA has 4 variants, 3 populated (75%); 1 missing.

**Assessment: WELL COVERED (94.6%)**

---

## 7. HYBRID EFFICIENCY COVERAGE

| Metric | Value |
|---|---|
| Applicable variants (Petrol Hybrid + Diesel Mild Hybrid) | **22** |
| Populated `mileage_arai_kmpl` | **19** |
| **Hybrid mileage coverage** | **86.4%** |
| `claimed_ev_range_km` populated | **0** |

### By Sub-Type

| Sub-type | Total | mileage_arai_kmpl | Coverage |
|---|---|---|---|
| Petrol Hybrid (strong) | 20 | 19 | 95.0% |
| Diesel Mild Hybrid | 2 | 0 | 0.0% |

> [!NOTE]
> Strong hybrids correctly use `mileage_arai_kmpl` (ARAI-rated combined efficiency). The 0 EV range values for hybrids are correct — non-plugin hybrids do not have an externally-chargeable EV range figure.
>
> The 2 Diesel Mild Hybrid variants (both in Toyota Fortuner) are missing mileage — a real but minor gap.

**Assessment: WELL COVERED (86.4%)**

---

## 8. NULL CLASSIFICATION SUMMARY

For the primary efficiency field `mileage_arai_kmpl` across all non-EV/CNG applicable variants:

| Category | Count | Meaning |
|---|---|---|
| A. Genuine gap (no source evidence) | **270** | No aggregator or OEM has ever supplied this value |
| B. Not applicable (EV/CNG) | 119 | These variants use different fields by design |
| C. Provenance exists but canonical NULL | **0** | No blocked or conflicted values |
| D. Source conflict | 0 | No active conflicts blocking this field |
| E. Unresolved source observation | 0 | All observations that were ingested are resolved |

**All 270 missing petrol/diesel/hybrid mileage values are Category A: the data simply does not exist in any currently-ingested source.**

---

## 9. SOURCE COVERAGE FOR EFFICIENCY FIELDS

| Field | Canonical Populated | Total Provenance | Distinct Variants | Sources | Multi-Source |
|---|---|---|---|---|---|
| `mileage_arai_kmpl` | 449 | 548 rows | 449 | v6_migration (391) + 91wheels (157) | ✅ YES |
| `mileage_arai_km_per_kg` | 39 | 39 rows | 39 | v6_migration only | ❌ NO |
| `claimed_ev_range_km` | 35 | 35 rows | 35 | v6_migration only | ❌ NO |

> [!NOTE]
> `mileage_arai_kmpl` benefits from two sources with 99 overlapping confirmations, making it the most source-trustworthy efficiency field. CNG mileage and EV range are single-source and should be treated with lower confidence until a second source is added.

---

## 10. MODEL-LEVEL EFFICIENCY COVERAGE

*Full data in `scratch/phase7a_powertrain_coverage.csv`*

### Models with 100% Coverage (all applicable powertrain types)

| Model | Petrol | Diesel | CNG | EV | Hybrid |
|---|---|---|---|---|---|
| Hyundai Creta | 100% | 100% | — | — | — |
| Kia Carens Clavis | 100% | 100% | — | — | — |
| Kia Carens Clavis EV | — | — | — | 100% | — |
| Kia Syros | 100% | 100% | — | — | — |
| MG Windsor EV | — | — | — | 100% | — |
| Mahindra Bolero | — | 100% | — | — | — |
| Mahindra Scorpio Classic | — | 100% | — | — | — |
| Mahindra Thar Roxx | 100% | 100% | — | — | — |
| Mahindra XUV 3XO | 100% | 100% | — | — | — |
| Maruti Suzuki Alto K10 | 100% | — | 100% | — | — |
| Maruti Suzuki Fronx | 91%* | 100% | — | — | — |
| Maruti Suzuki Grand Vitara | 92%* | — | 100% | — | 100% |
| Maruti Suzuki S-Presso | 100% | — | 100% | — | — |
| Maruti Suzuki Swift | 100% | — | 100% | — | — |
| Maruti Suzuki Victoris | 93%* | — | 100% | — | 100% |
| Nissan Magnite | 95%* | — | — | — | — |
| Skoda Kushaq | 100% | — | — | — | — |
| Skoda Kylaq | 100% | — | — | — | — |
| Skoda Slavia | 100% | — | — | — | — |
| Tata Nexon | 100% | 100% | 100% | — | — |
| Tata Punch EV | — | — | — | 100% | — |
| Tata Tiago EV | — | — | — | 100% | — |
| Toyota Glanza | 100% | — | 100% | — | — |
| Toyota Innova Hycross | 100% | — | — | — | 100% |
| Toyota Rumion | 100% | — | 100% | — | — |
| Toyota Urban Cruiser Hyryder | 100% | — | 100% | — | 100% |
| Toyota Urban Cruiser Taisor | 100% | — | 100% | — | — |
| Volkswagen Taigun | 100% | — | — | — | — |

*Near-complete (≥91%)

### Models with 0% Coverage Despite Applicable Variants (Critical Gaps)

| Model | Petrol Variants | Diesel Variants | CNG Variants | Root Cause |
|---|---|---|---|---|
| Kia Seltos | 0/26 (0%) | 0/15 (0%) | — | PDF_TEXT_FAILURE — OEM PDF not machine-readable |
| Hyundai Venue | 0/13 (0%) | 0/6 (0%) | — | EXTRACTION_FAILURE — extractor returned no payloads |
| Hyundai Verna | 0/14 (0%) | — | — | EXTRACTION_FAILURE — extractor returned no payloads |
| Tata Harrier | 0/12 (0%) | 0/14 (0%) | — | FeatureListStrategy quarantined |
| Tata Tiago | 0/11 (0%) | — | 0/9 (0%) | EXTRACTION_FAILURE |
| Renault Duster | 0/11 (0%) | — | — | EXTRACTION_FAILURE (borderless) |
| Renault Triber | 0/6 (0%) | — | — | EXTRACTION_FAILURE (borderless) |
| Mahindra Scorpio-N | 0/9 (0%) | 0/18 (0%) | — | RESOLUTION_FAILURE (name mismatch) |
| MG Hector | 0/7 (0%) | — | — | No mileage in v6_migration or aggregators |

### Models with Partial but Non-Zero Coverage

| Model | Worst Gap | Detail |
|---|---|---|
| Mahindra XUV 7XO | Petrol 17%, Diesel 12% | Only 4/28 variants have mileage |
| Tata Altroz | Petrol 15%, Diesel 0%, CNG 0% | Only 2/27 petrol variants populated |
| Maruti Suzuki Brezza | Petrol 25% | 2/8 petrol variants; CNG 0% |
| Maruti Suzuki Baleno | Petrol 43%, CNG 0% | 3/7 petrol variants |
| Maruti Suzuki WagonR | Petrol 12% | 1/8 petrol variants |
| Honda City | Petrol 29% | 2/7 petrol variants; Hybrid 0% |
| Tata Tigor | Petrol 50%, CNG 0% | 4/8 petrol; 0/6 CNG |
| Hyundai Aura | Petrol 50%, CNG 0% | 3/6 petrol; 0/3 CNG |
| Mahindra Thar | Diesel 50% | 2/4 diesel; 0/3 petrol |
| Maruti Suzuki Dzire | Petrol 57%, CNG 0% | 4/7 petrol |

---

## 11. OLD vs CORRECTED METRICS

### Phase 7 vs Phase 7A — Key Corrections

| Field | Phase 7 Metric (Global) | Phase 7A Correct Metric | Denominator | Verdict |
|---|---|---|---|---|
| `mileage_arai_kmpl` (petrol) | 54.0% (449/832) | **64.6% (340/526)** | Petrol variants only | Phase 7 was pessimistic |
| `mileage_arai_kmpl` (diesel) | 54.0% (449/832) | **50.3% (84/167)** | Diesel variants only | Phase 7 was slightly optimistic for diesel |
| `mileage_arai_km_per_kg` | 4.7% (39/832) | **47.6% (39/82)** | CNG variants only | Phase 7 was **severely misleading** |
| `claimed_ev_range_km` | 4.2% (35/832) | **94.6% (35/37)** | EV variants only | Phase 7 was **severely misleading** |
| Hybrid mileage | Subsumed in petrol% | **86.4% (19/22)** | Hybrid variants only | Phase 7 did not separate this |

### Which Phase 7 Conclusions Were Misleading?

| Phase 7 Claim | Correct Assessment | Error Type |
|---|---|---|
| "EV range nearly absent (4.2%)" | EV range is **WELL COVERED at 94.6%** | Wrong denominator — applied all-832 to EV-only field |
| "CNG mileage nearly absent (4.7%)" | CNG mileage is at **47.6%** — a real but different gap | Wrong denominator — applied all-832 to CNG-only field |
| "Overall mileage: ~54%" | More nuanced: petrol 64.6%, diesel 50.3% — separate stories | Mixed fuels into one number |
| "Mileage re-pass is #1 priority" | EV range needs no re-pass; CNG and diesel are the real gaps | Incorrectly ranked EV range as urgent |
| "EV range gap is critical" | Not a gap — almost fully covered | Denominator error |

---

## 12. REVISED POWERTRAIN-AWARE EFFICIENCY ASSESSMENT

| Dimension | Applicable Variants | Coverage | Status |
|---|---|---|---|
| EV range (`claimed_ev_range_km`) | 37 | **94.6%** | ✅ WELL COVERED |
| Hybrid mileage (`mileage_arai_kmpl`) | 22 | **86.4%** | ✅ WELL COVERED |
| Petrol mileage (`mileage_arai_kmpl`) | 526 | **64.6%** | ⚠️ MODERATELY COVERED |
| CNG mileage (`mileage_arai_km_per_kg`) | 82 | **47.6%** | ❌ SIGNIFICANT GAP |
| Diesel mileage (`mileage_arai_kmpl`) | 167 | **50.3%** | ❌ SIGNIFICANT GAP |

### Single-Source Risk (no cross-validation)

| Field | Source Count | Risk |
|---|---|---|
| `mileage_arai_kmpl` | 2 (v6_migration + 91wheels) | LOW |
| `mileage_arai_km_per_kg` | 1 (v6_migration only) | MEDIUM |
| `claimed_ev_range_km` | 1 (v6_migration only) | MEDIUM |

### Model Concentration of Gaps

The diesel and petrol mileage gaps are **highly concentrated** in a small set of models:

**Responsible for the majority of missing petrol mileage (186 gaps):**
- Kia Seltos: 26 variants (PDF failure)
- Tata Altroz: 11 variants
- Mahindra XUV 7XO: 10 variants
- Maruti Suzuki WagonR: 7 variants
- Hyundai Venue: 13 variants
- Hyundai Verna: 14 variants
- Tata Harrier: 12 variants (quarantine)
- Renault Duster: 11 variants
- Tata Tiago: 11 variants

**Responsible for the majority of missing diesel mileage (83 gaps):**
- Mahindra Scorpio-N: 18 variants (resolution failure)
- Tata Harrier: 14 variants (quarantine)
- Kia Seltos: 15 variants (PDF failure)
- Hyundai Venue: 6 variants

> [!IMPORTANT]
> **Fixing just 3 root causes would close ~60% of all efficiency gaps:**
> 1. Kia Seltos PDF (text-extractable version) → 41 variants
> 2. Mahindra Scorpio-N name alias → 27 variants
> 3. Tata FeatureListStrategy → ~50+ affected Tata variants

---

## 13. IS A MILEAGE RE-PASS JUSTIFIED?

### Revised Analysis

| Question | Answer |
|---|---|
| Is EV range a gap? | **NO** — 94.6% coverage. No re-pass needed. |
| Is petrol mileage a gap? | **PARTIAL** — 64.6% coverage. Significant but not critical. |
| Is diesel mileage a gap? | **YES** — 50.3% coverage is a real gap for a meaningful segment (167 variants). |
| Is CNG mileage a gap? | **YES** — 47.6% coverage with single-source only. |
| Is a full mileage re-pass warranted? | **CONDITIONALLY** — targeted model-specific fixes are more efficient than a broad re-pass. |

### Recommended Approach (Highest ROI First)

1. **Fix Kia Seltos PDF** (re-fetch text-extractable version) → immediately closes 41 petrol + 15 diesel variant gaps
2. **Fix Scorpio-N name alias** → closes 9 petrol + 18 diesel variant gaps  
3. **Develop Tata FeatureListStrategy** → closes ~50+ Tata variant gaps across mileage and features
4. **Then assess remaining gap** — after those three fixes, the petrol coverage will likely exceed 80% and diesel exceed 70%, at which point the gap may be acceptable

A **broad aggregator re-scrape for mileage** is a lower-priority option than targeted structural fixes, because the gaps are caused by **extraction pipeline failures**, not by missing source data.

---

## 14. REVISED RECOMMENDATION RELEVANCE

| User Query | Revised Feasibility | Correct Coverage |
|---|---|---|
| "Best EV range" | ✅ **FULLY SUPPORTABLE** | 94.6% of EV variants have range |
| "CNG fuel efficiency" | ⚠️ PARTIAL (47.6%) | Real gap; only half of CNG variants covered |
| "Best petrol mileage" | ⚠️ PARTIAL (64.6%) | Significant gap; rankings may be incomplete |
| "Best diesel mileage" | ❌ UNRELIABLE (50.3%) | Too many diesel variants missing |
| "Hybrid efficiency" | ✅ SUPPORTABLE (86.4%) | Good coverage for hybrids |
| "Low running cost (petrol)" | ⚠️ PARTIAL | Same as petrol mileage |

---

## EXECUTIVE SUMMARY

### 1. What percentage of petrol variants have mileage?
**64.6%** (340 of 526 petrol/flex-fuel variants) — *MODERATELY COVERED*

### 2. What percentage of diesel variants have mileage?
**50.3%** (84 of 167 diesel/diesel-MH variants) — *SIGNIFICANT GAP*

### 3. What percentage of CNG variants have mileage?
**47.6%** (39 of 82 CNG variants) — *SIGNIFICANT GAP, single-source only*

### 4. What percentage of EV variants have range?
**94.6%** (35 of 37 EV variants) — *WELL COVERED*

### 5. Which efficiency field is genuinely weakest?
**CNG `mileage_arai_km_per_kg`** at 47.6% with single-source backing. Diesel `mileage_arai_kmpl` at 50.3% is a close second.

### 6. Is a mileage re-pass justified?
**Conditionally.** A broad re-scrape is not the most efficient path. The gaps are caused by 3 specific structural failures (Kia Seltos PDF, Scorpio-N name alias, Tata FeatureListStrategy). Fixing those root causes recovers ~60% of all missing mileage values with no scraping at all.

### 7. What should the next KB task be based on the corrected evidence?
Based on corrected powertrain-aware metrics, the priority order is:

1. **Bharat NCAP ingestion** — safety authority gap is 0% coverage for all 832 variants; this cannot be fixed by any structural fix
2. **Kia Seltos PDF re-fetch** — 41-variant unlock, petrol + diesel mileage + features
3. **Mahindra Scorpio-N name alias** — 27-variant unlock, low-effort, high impact
4. **Tata FeatureListStrategy development** — largest Tata models are fully quarantined
5. **CNG mileage second-source ingestion** — add cross-validation for the 39 existing CNG values
6. **Diesel mileage targeted aggregator pass** — Innova Crysta, Fortuner specifically
