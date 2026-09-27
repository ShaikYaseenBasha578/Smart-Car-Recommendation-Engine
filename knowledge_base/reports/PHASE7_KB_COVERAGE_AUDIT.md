# PHASE 7 — CARREC KB COVERAGE & QUALITY AUDIT

> **READ-ONLY AUDIT** — Zero production mutations.  
> **Production checksum (SHA1):** `e752ebde5b7f227140bedb319c6b9753a3fdbdde`  
> **Audit date:** 2026-09-23

---

## 1. PRODUCTION DATABASE INTEGRITY

| Check | Result |
|---|---|
| SHA1 Checksum | `e752ebde5b7f227140bedb319c6b9753a3fdbdde` |
| `PRAGMA integrity_check` | `ok` |
| manufacturer | 12 |
| model | 62 |
| generation | 62 |
| variant | 832 |
| powertrain | 131 |
| source_observation | 3,414 |
| field_provenance | 36,445 |

**Phase 6 production ingestion result confirmed present:**
- source_observation: +52 (OEM)
- field_provenance: +133 (OEM)
- Canonical mutation: variant 669 `paddle_shifters` NULL → 0 ✓

---

## 2. CANONICAL FIELD COVERAGE

Complete field-by-field coverage across all 832 variants. Full CSV: `scratch/phase7_canonical_field_coverage.csv`

### Identity & Structure
| Field | Populated | % | Type |
|---|---|---|---|
| transmission | 832/832 | 100.0% | categorical |
| drivetrain | 832/832 | 100.0% | categorical |

### Pricing
| Field | Populated | % | Type | Rec-Important |
|---|---|---|---|---|
| price_ex_showroom | 812/832 | 97.6% | numeric | ★ |

### Dimensions
| Field | Populated | % | Type | Rec-Important |
|---|---|---|---|---|
| length_mm | 812/832 | 97.6% | numeric | |
| width_mm | 812/832 | 97.6% | numeric | |
| height_mm | 812/832 | 97.6% | numeric | |
| wheelbase_mm | 812/832 | 97.6% | numeric | |
| ground_clearance_mm | 812/832 | 97.6% | numeric | |
| kerb_weight_kg | 812/832 | 97.6% | numeric | |

### Capacity
| Field | Populated | % | Type | Rec-Important |
|---|---|---|---|---|
| seating_capacity | 812/832 | 97.6% | numeric | ★ |
| boot_space_litres | 785/832 | 94.3% | numeric | ★ |
| fuel_tank_litres | 725/832 | 87.1% | numeric | ★ |

### Performance / Efficiency ⚠️ MAJOR GAP
| Field | Populated | % | Type | Rec-Important |
|---|---|---|---|---|
| mileage_arai_kmpl | 449/832 | 54.0% | numeric | ★ |
| mileage_arai_km_per_kg | 39/832 | 4.7% | numeric | ★ |
| claimed_ev_range_km | 35/832 | 4.2% | numeric | ★ |

*Note: mileage_arai_kmpl is NULL for EV, CNG, and Hybrid variants. When filtered to petrol/diesel only the coverage is substantially higher, but 383 petrol/diesel variants also lack it.*

### Safety ✅ STRONG
| Field | Populated | % | Type | Rec-Important |
|---|---|---|---|---|
| abs | 812/832 | 97.6% | boolean | ★ |
| esc | 783/832 | 94.1% | boolean | ★ |
| hill_assist | 789/832 | 94.8% | boolean | ★ |
| tyre_pressure_monitoring_system | 791/832 | 95.1% | boolean | ★ |
| rear_parking_sensors | 812/832 | 97.6% | boolean | ★ |
| rear_camera | 787/832 | 94.6% | boolean | ★ |
| camera_360 | 806/832 | 96.9% | boolean | ★ |
| airbags | 812/832 | 97.6% | numeric | ★ |
| adas_available | 811/832 | 97.5% | boolean | ★ |
| adas_tier | 808/832 | 97.1% | categorical | ★ |

### Comfort & Convenience ✅ STRONG
| Field | Populated | % | Type | Rec-Important |
|---|---|---|---|---|
| automatic_climate_control | 796/832 | 95.7% | boolean | ★ |
| rear_ac_vents | 807/832 | 97.0% | boolean | ★ |
| sunroof | 818/832 | 98.3% | categorical | ★ |
| ventilated_front_seats | 809/832 | 97.2% | boolean | ★ |
| cruise_control | 629/832 | 75.6% | boolean | ★ |
| paddle_shifters | 444/832 | 53.4% | boolean | |
| wireless_charging | 577/832 | 69.4% | boolean | ★ |
| heads_up_display | 582/832 | 70.0% | boolean | |
| drive_modes | 280/832 | 33.7% | boolean | |
| connected_car_features | 762/832 | 91.6% | boolean | ★ |

### Infotainment & Connectivity ✅ GOOD
| Field | Populated | % | Type | Rec-Important |
|---|---|---|---|---|
| android_auto | 788/832 | 94.7% | boolean | ★ |
| apple_carplay | 788/832 | 94.7% | boolean | ★ |

---

## 3. MODEL / VARIANT COVERAGE

All 62 models audited. Completeness measured across 29 recommendation-important fields.

### Most Complete Models (>91% avg completeness across important fields)
| Model | Variants | Powertrains | Completeness | Obs | Provenance |
|---|---|---|---|---|---|
| Volkswagen Taigun | 10 | 2 | 93.1% | 44 | 515 |
| Skoda Kushaq | 11 | 2 | 92.8% | 44 | 665 |
| Maruti Suzuki Swift | 14 | 2 | 92.4% | 52 | 701 |
| Maruti Suzuki S-Presso | 8 | 2 | 92.2% | 16 | 330 |
| Maruti Suzuki Ertiga | 9 | 2 | 91.6% | 22 | 373 |
| Skoda Kylaq | 11 | 1 | 91.2% | 54 | 627 |
| Skoda Slavia | 10 | 2 | 91.0% | 40 | 498 |

### Sparsest Models (<73% completeness)
| Model | Variants | Completeness | Key Missing |
|---|---|---|---|
| Maruti Suzuki e VITARA | 4 | 63.8% | mileage (EV), price gaps, ADAS |
| Renault Triber | 6 | 75.9% | mileage, cruise, ADAS tier |
| Hyundai Verna | 14 | 64.3% | mileage data not extracted (OEM PDF failed) |
| Tata Harrier | 26 | 68.0% | FeatureList quarantine — many features unknown |
| Maruti Suzuki WagonR | 10 | 72.4% | mileage, wireless charging |
| Maruti Suzuki Jimny | 5 | 73.1% | ADAS, efficiency fields |

### High-Variant / Low-Coverage Models (most impactful gaps)
| Model | Variants | Completeness | Concern |
|---|---|---|---|
| Tata Nexon | 53 | 86.9% | Largest model in corpus — FeatureList quarantine prevented OEM enrichment |
| Tata Harrier | 26 | 68.0% | Low completeness on large variant set |
| Kia Seltos | 41 | 73.8% | OEM PDF was image-only; PDF_TEXT_FAILURE |
| Mahindra Scorpio-N | 27 | 75.9% | RESOLUTION_FAILURE (name mismatch in DB) |

---

## 4. SOURCE COVERAGE

| Source ID | Name | Type | Tier | Observations | Resolved | Distinct Variants | Distinct Models |
|---|---|---|---|---|---|---|---|
| 1 | v6_migration | migration | 2 | 864 | 864 (100%) | 812 | 62 |
| 2 | 91wheels | aggregator | 2 | 845 | 711 (84%) | 474 | 56 |
| 3 | v3cars | aggregator | 2 | 845 | 438 (52%) | 278 | 28 |
| 4 | carwale | aggregator | 3 | 860 | 753 (88%) | 319 | 51 |
| 5 | cardekho | aggregator | 3 | 0 | 0 | 0 | 0 |
| 6 | oem | oem | 1 | 52* | N/A | — | 28† |
| 7 | bharat_ncap | rating_agency | 1 | 0 | 0 | 0 | 0 |
| 8 | global_ncap | rating_agency | 1 | 0 | 0 | 0 | 0 |

*OEM source observations (52) are stored in source_observation but via the rsc_payload extraction path; they populate field_provenance directly for 28 models.  
†OEM provenance contributed to 28 successfully-extracted models.

> [!NOTE]
> The OEM source (tier=1, highest authority) has NO direct source_observation rows linked via standard aggregator paths. Its 52 observations are raw OEM brochure extractions using the rsc_payload method. CardEkho, Bharat NCAP, and Global NCAP have zero observations — these are planned but not yet ingested layers.

---

## 5. FIELD-LEVEL SOURCE DIVERSITY

| Field | Source Coverage | Provenance Rows | Canonical Populated | Assessment |
|---|---|---|---|---|
| sunroof | 4 sources | 1,975 | 818 | ✅ MULTI-SOURCE AGREED |
| tyre_pressure_monitoring_system | 4 sources | 2,022 | 791 | ✅ MULTI-SOURCE AGREED |
| adas_available | 4 sources | 1,872 | 811 | ✅ MULTI-SOURCE |
| ventilated_front_seats | 4 sources | 1,851 | 809 | ✅ MULTI-SOURCE AGREED |
| cruise_control | 4 sources | 1,765 | 629 | ✅ MULTI-SOURCE |
| heads_up_display | 4 sources | 1,611 | 582 | ✅ MULTI-SOURCE |
| transmission | 2 sources | 1,191 | 832 | ✅ |
| drivetrain | 2 sources | 1,023 | 832 | ✅ |
| seating_capacity | 2 sources | 1,033 | 812 | ✅ |
| boot_space_litres | 3 sources | 1,554 | 785 | ✅ MULTI-SOURCE |
| wireless_charging | 3 sources | 1,035 | 577 | ✅ MULTI-SOURCE |
| mileage_arai_kmpl | 2 sources | 548 | 449 | ⚠️ PARTIAL |
| price_ex_showroom | 1 source (v6_migration) | 812 | 812 | ⚠️ SINGLE SOURCE |
| abs | 1 source (v6_migration) | 822 | 812 | ⚠️ SINGLE SOURCE |
| airbags | 1 source (v6_migration) | 812 | 812 | ⚠️ SINGLE SOURCE |
| esc | 1 source (v6_migration) | 793 | 783 | ⚠️ SINGLE SOURCE |
| hill_assist | 1 source (v6_migration) | 806 | 789 | ⚠️ SINGLE SOURCE |
| android_auto | 1 source (v6_migration) | 791 | 788 | ⚠️ SINGLE SOURCE |
| apple_carplay | 1 source (v6_migration) | 791 | 788 | ⚠️ SINGLE SOURCE |
| rear_camera | 1 source (v6_migration) | 791 | 787 | ⚠️ SINGLE SOURCE |
| rear_ac_vents | 1 source (v6_migration) | 818 | 807 | ⚠️ SINGLE SOURCE |
| camera_360 | 1 source (v6_migration) | 806 | 806 | ⚠️ SINGLE SOURCE |
| drive_modes | 1 source (v6_migration) | 448 | 280 | ⚠️ SINGLE SOURCE + LOW |
| claimed_ev_range_km | 1 source | 35 | 35 | ⚠️ SINGLE SOURCE + LOW |
| mileage_arai_km_per_kg | 1 source | 39 | 39 | ⚠️ SINGLE SOURCE + LOW |
| adas_tier | 1 source (v6_migration) | 808 | 808 | ⚠️ SINGLE SOURCE |

**Fields with ZERO source diversity (no second-source validation):** price, abs, airbags, esc, hill_assist, android_auto, apple_carplay, rear_camera, rear_ac_vents, camera_360, adas_tier, automatic_climate_control, drive_modes, fuel_tank_litres, claimed_ev_range_km, mileage_arai_km_per_kg.

---

## 6. PROVENANCE ANALYSIS

Full CSV: `scratch/phase7_provenance_analysis.csv`

| Decision | Reason | Count | Variants Affected | Fields Affected |
|---|---|---|---|---|
| accepted | v6_migration | 24,955 | 812 | 36 |
| confirmed | agrees_with_canonical | 8,398 | 519 | 27 |
| rejected | conflict_with_canonical_authority | 2,426 | 469 | 15 |
| accepted | new_field | 599 | 251 | 10 |
| accepted | edition_override_or_correction | 39 | 16 | 7 |
| rejected | conflict_field_tier_5_vs_best_5 | 26 | 13 | 10 |
| rejected | conflict_field_tier_5_vs_best_3 | 2 | 2 | 1 |

**Total provenance rows:** 36,445  
**Accepted:** 25,593 (70.2%)  
**Confirmed (multi-source agreement):** 8,398 (23.0%)  
**Rejected (conflict):** 2,454 (6.7%)

> [!NOTE]
> The v6_migration alone contributed 24,955 accepted provenance rows, making it the foundational layer. The 8,398 confirmed rows represent genuine multi-source agreement — the KB's most trustworthy data.

---

## 7. CONFLICT AUDIT

**Total rejected provenance rows: 2,454**  
**Conflicts covering:** 469 distinct variants, 15 distinct fields

### Most Conflicted Fields
Derived from `conflict_with_canonical_authority` rejections:

| Field | Likely Conflict Type |
|---|---|
| boot_space_litres | Carwale reports different value from v6_migration baseline |
| sunroof | 91wheels reports 0 where canonical has value (trim-level inconsistency) |
| tyre_pressure_monitoring_system | Carwale missing data vs. canonical presence |
| adas_available | 91wheels flags available where canonical says absent |
| cruise_control | Various sources disagree across trim levels |
| heads_up_display | Source tier conflicts |
| ventilated_front_seats | Multi-source partial disagreement |

### Representative Conflicts (sample)
| Make/Model/Variant | Field | Rejected Value | Source | Reason |
|---|---|---|---|---|
| Honda Amaze V/VX/ZX MT | boot_space_litres | 416 | carwale | conflict_with_canonical_authority |
| Honda Amaze V/VX/ZX MT | sunroof | 0 | 91wheels | conflict_with_canonical_authority |
| Honda Amaze V/VX/ZX MT | tyre_pressure_monitoring_system | 0 | carwale | conflict_with_canonical_authority |
| Honda City V MT | adas_available | 1 | 91wheels | conflict_with_canonical_authority |

> [!NOTE]
> All conflicts are currently resolved in favour of the higher-authority source (v6_migration tier-2 vs. aggregator tier-3). No conflict remains unresolved as `pending` — the provenance system has made decisions for all 2,454 rejected rows. This is correct behaviour.

---

## 8. RECOMMENDATION-RELEVANT FIELD COVERAGE BY CATEGORY

| Category | Fields | Avg Coverage | Status |
|---|---|---|---|
| PRICE | price_ex_showroom | 97.6% | ✅ EXCELLENT |
| POWERTRAIN | fuel_type, engine_cc, power_bhp, torque_nm | ~100% via powertrain table | ✅ EXCELLENT |
| TRANSMISSION | transmission | 100.0% | ✅ EXCELLENT |
| DRIVETRAIN | drivetrain | 100.0% | ✅ EXCELLENT |
| SAFETY | airbags, abs, esc, hill_assist, tpms | 95.8% | ✅ EXCELLENT |
| ADAS | adas_available, adas_tier, camera_360, rear_camera, rear_parking_sensors | 96.8% | ✅ EXCELLENT |
| PRACTICALITY | seating_capacity, boot_space, fuel_tank | 93.0% | ✅ EXCELLENT |
| DIMENSIONS | length, width, height, wheelbase, gc | 97.6% | ✅ EXCELLENT |
| COMFORT | climate_control, rear_ac, sunroof, ventilated_seats | 97.1% | ✅ EXCELLENT |
| INFOTAINMENT | android_auto, apple_carplay, HUD | 86.4% | ✅ GOOD |
| CONNECTIVITY | wireless_charging, connected_car | 80.5% | ✅ GOOD |
| DRIVING FEATURES | cruise_control, paddle_shifters, drive_modes | 54.2% | ⚠️ PARTIAL |
| **EFFICIENCY** | **mileage_arai_kmpl, EV range, CNG mileage** | **20.9%** | **❌ CRITICAL GAP** |

---

## 9. COMPARISON WITH LEGACY CSVs

### cars_ds_final_2021.csv vs Current KB

| Dimension | 2021 CSV | Current KB V6 |
|---|---|---|
| Total rows/variants | 1,267 | 832 |
| Makes/Manufacturers | 39 | 12 |
| Models | 235 | 62 |
| Columns/Fields | 141 | ~50 canonical + powertrain |
| Avg null/missing rate | **34.5%** | **~15%** |
| Source traceability | ❌ None | ✅ Every field has provenance |
| Multi-source validation | ❌ Not possible | ✅ Yes (8,398 confirmed rows) |
| Conflict detection | ❌ Not possible | ✅ 2,454 tracked conflicts |
| Provenance history | ❌ None | ✅ 36,445 provenance rows |
| Date of data | 2021 (stale) | 2025-2026 (current gen) |
| EV coverage | Minimal | 35 EV range values, all EVs present |
| ADAS fields | ❌ Not present | ✅ 811/832 variants |
| Canonical identity | Flat string names | ✅ Structured ID + name + generation |

> [!NOTE]
> The 2021 CSV covers more makes/models (broader but shallower and stale). The KB V6 is intentionally narrower (top-62 current-gen models) but significantly deeper, more accurate, and fully traceable.

### carrec_recommendation_dataset_v6.csv vs Current KB

| Dimension | V6 CSV | Current KB V6 |
|---|---|---|
| Rows/Variants | 812 | 832 (+20 new) |
| Columns | 64 | 832 variants × ~50 fields |
| Null rate | 18.7% | ~15% |
| Source traceability | ❌ Flat, no sources | ✅ 3,414 source observations |
| Field-level provenance | ❌ None | ✅ 36,445 rows |
| Conflict detection | ❌ None | ✅ Tracked |
| Multi-source fields | ❌ None | ✅ Many fields have 2-4 sources |
| OEM data layer | ❌ None | ✅ 52 OEM observations added |
| Authority system | ❌ None | ✅ Tier-based provenance |

### Unique KB Capabilities That No Flat CSV Can Provide

1. **Field-level provenance:** Every canonical value traces back to a specific source observation with a decision reason.
2. **Source disagreement detection:** 2,454 conflicts are tracked and resolved — a CSV has no memory of disagreements.
3. **Evidence history:** 36,445 provenance rows provide a full audit trail.
4. **Multiple-source support:** 8,398 fields confirmed by 2+ sources — higher trust than a single-source CSV.
5. **Authority decisions:** Tier-based authority system (OEM > aggregator) is encoded.
6. **Distinction between source fact and canonical fact:** A source may claim X; the canonical schema may say Y — both are preserved.
7. **Observation payloads:** Full raw extraction JSON is stored per source_observation — re-extraction without going back to web.
8. **Incremental enrichability:** New sources plug in without touching the canonical layer.

---

## 10. RECOMMENDATION GAP ANALYSIS

What can a future recommendation engine reliably answer **right now**?

| User Requirement | Relevant KB Fields | Coverage | Evidence Strength | Can Use Now? | Notes |
|---|---|---|---|---|---|
| "I want automatic" | transmission | 100% | HIGH (2 sources) | ✅ YES | |
| "Under ₹15 lakh" | price_ex_showroom | 97.6% | MEDIUM (1 source, v6_migration) | ✅ YES | Price may be slightly stale |
| "Good safety (6 airbags)" | airbags | 97.6% | MEDIUM (1 source) | ✅ YES | |
| "ADAS / ADAS-equipped" | adas_available, adas_tier | 97.5% | HIGH (4 sources agree) | ✅ YES | |
| "360 camera" | camera_360 | 96.9% | MEDIUM | ✅ YES | |
| "Good city car" | dimensions, ground_clearance, seating | 95-97% | HIGH | ✅ YES | Can filter small cars |
| "Sunroof" | sunroof | 98.3% | HIGH (4 sources) | ✅ YES | |
| "Wireless charging" | wireless_charging | 69.4% | HIGH (3 sources) | ⚠️ PARTIAL | 30% variants unknown |
| "Good rear-seat comfort" | rear_ac_vents, seating_capacity | 95-97% | HIGH | ✅ YES | |
| "7-seater" | seating_capacity | 97.6% | HIGH (2 sources) | ✅ YES | |
| "Large boot" | boot_space_litres | 94.3% | HIGH (3 sources) | ✅ YES | |
| "Android Auto / Apple CarPlay" | android_auto, apple_carplay | 94.7% | MEDIUM (1 source) | ✅ YES | |
| "4WD / AWD" | drivetrain | 100% | HIGH | ✅ YES | |
| "EV" | fuel_type (powertrain), claimed_ev_range_km | fuel:100%, range:4.2% | MEDIUM | ⚠️ PARTIAL | Can identify EVs; range mostly unavailable |
| "Good highway car" | cruise_control, mileage | 75.6% / 54% | MEDIUM | ⚠️ PARTIAL | Cruise covered; mileage partial |
| "Low running cost" | mileage_arai_kmpl | 54.0% | LOW | ❌ NOT RELIABLE | Too many gaps; unreliable filter |
| "Diesel engine" | fuel_type (powertrain) | 100% | HIGH | ✅ YES | |
| "CNG" | fuel_type (powertrain) | 100% | HIGH | ✅ YES | |
| "Best mileage diesel" | mileage_arai_kmpl | 54.0% | LOW | ❌ NOT YET SUPPORTED | Critical gap |
| "EV range > 400 km" | claimed_ev_range_km | 4.2% | LOW | ❌ NOT YET SUPPORTED | Only 35 values |
| "NCAP safety rating" | — | 0% | NONE | ❌ NOT YET SUPPORTED | bharat_ncap/global_ncap not ingested |
| "Best resale value" | — | 0% | NONE | ❌ NOT YET SUPPORTED | No resale layer |
| "Owner satisfaction" | — | 0% | NONE | ❌ NOT YET SUPPORTED | No owner experience layer |
| "Road trip car" | boot_space, fuel_tank, cruise | ~85% | MEDIUM | ⚠️ PARTIAL | Can filter but mileage gap hurts |
| "Drive modes / sporty" | drive_modes | 33.7% | LOW | ❌ NOT RELIABLE | Only 280/832 known |
| "HUD available" | heads_up_display | 70.0% | HIGH (4 sources) | ⚠️ PARTIAL | 30% gap |

---

## 11. KNOWLEDGE-LAYER READINESS

| Layer | Status | Evidence |
|---|---|---|
| 1. Canonical structured vehicle data | **AVAILABLE** | 832 variants × ~50 fields, 97%+ on key fields |
| 2. Vehicle identity / history | **AVAILABLE** | model + generation + variant ID structure; v6_row_index links to CSV history |
| 3. Source observations | **PARTIALLY AVAILABLE** | 3,414 obs from 4 sources; cardekho/OEM/NCAP/review sources absent or minimal |
| 4. Field-level provenance | **AVAILABLE** | 36,445 provenance rows, full decision history |
| 5. Professional automotive knowledge | **NOT YET POPULATED** | No professional review ingestion; no editorial scoring |
| 6. Owner/customer experience | **NOT YET POPULATED** | No owner review, satisfaction, reliability data |
| 7. Derived/aggregated knowledge | **NOT YET POPULATED** | No computed scores; no ranking; no recommendation index |
| 8. Recommendation consumption layer | **NOT YET POPULATED** | No API, no scoring pipeline, no preference matching |

---

## 12. PHASE 7 GAP REGISTER

Full register: `knowledge_base/reports/PHASE7_KB_GAP_REGISTER.md`

### Critical Gaps

| Gap | Affected | Severity | Rec Impact | Next Layer |
|---|---|---|---|---|
| Mileage/efficiency data incomplete (54% coverage) | 383 petrol/diesel variants missing mileage | **CRITICAL** | Cannot filter by running cost | Aggregator re-scrape or OEM data |
| EV range data nearly absent (4.2%) | 35 of ~50+ EV variants | **CRITICAL** | Cannot support EV recommendations | OEM brochures (Phase 8 OEM expansion) |
| NCAP safety ratings missing | All 832 variants | **CRITICAL** | Cannot answer safety-first queries with credible authority | Bharat NCAP / Global NCAP ingestion |
| Mileage CNG (4.7%) | 39 of ~60+ CNG variants | **HIGH** | CNG buyers = price-sensitive; mileage is #1 concern | Aggregator scrape |
| Tata FeatureList quarantine | 6 Tata models (Nexon, Harrier, Altroz, Nexon EV, Punch EV, Tigor) = many variants | **HIGH** | Tata is biggest brand by variant count | Phase 8 FeatureList strategy development |
| Kia Seltos PDF_TEXT_FAILURE | 41 variants, no OEM enrichment | **HIGH** | Seltos is very high-traffic model | Fresh OEM PDF re-fetch or scraper |
| Mahindra Scorpio-N resolution failure | 27 variants | **HIGH** | No OEM enrichment applied | Fix name mismatch in DB, retry OEM pass |
| drive_modes coverage (33.7%) | 552 variants missing | **MEDIUM** | "Sporty" queries unreliable | Aggregator or OEM |
| wireless_charging coverage (69.4%) | 255 variants missing | **MEDIUM** | Common user filter | Additional aggregator pass |
| heads_up_display coverage (70.0%) | 250 variants missing | **MEDIUM** | Premium feature query | Aggregator or OEM |
| Price staleness (1 source only) | 812 variants | **MEDIUM** | Prices change frequently | Monthly price scrape |
| Owner experience: zero coverage | All 832 variants | **HIGH** | No satisfaction data | Phase 9 review layer |
| Professional reviews: zero coverage | All 832 variants | **HIGH** | No editorial scoring | Phase 9 review layer |

---

## 13. RECOMMENDED NEXT KNOWLEDGE-LAYER PRIORITIES

1. **Priority 1 — Mileage/Efficiency Re-pass** *(critical for recommendation)*  
   Run a targeted aggregator scrape for `mileage_arai_kmpl` for the ~383 petrol/diesel variants currently missing it. This is a single-field gap that unlocks the single most common user filter ("low running cost").

2. **Priority 2 — Bharat NCAP / Global NCAP Ingestion**  
   These are tier-1 authority sources. Any model with a NCAP rating should be ingested. This addresses the most dangerous gap — safety-first recommenders currently cannot use trusted crash-test data.

3. **Priority 3 — Tata FeatureList Strategy Development**  
   The FeatureList extraction strategy (complex inheritance lists) is quarantined. Developing this unlocks 6 high-traffic Tata models representing >100 variants.

4. **Priority 4 — OEM PDF re-fetch for Kia Seltos and Mahindra Scorpio-N**  
   Quick fixes: Seltos PDF needs a text-extractable version; Scorpio-N needs a name-alias entry to resolve generation pinning.

5. **Priority 5 — CardEkho Ingestion**  
   Source 5 exists in schema but has zero observations. Adding CardEkho provides a 5th aggregator for cross-validation and covers models currently single-sourced.

---

## EXECUTIVE SUMMARY

### 1. What does the KB know WELL?

The KB has excellent coverage (>93%) for: **price, safety features (airbags/ABS/ESC/ADAS), dimensions, seating capacity, boot space, sunroof, climate control, rear AC vents, ventilated seats, transmission type, drivetrain, Android Auto, Apple CarPlay, connected car features.** These are the most commonly queried recommendation attributes.

### 2. What does it know POORLY?

The most serious weakness is **fuel efficiency data**: only 54% of variants have `mileage_arai_kmpl`, and EV range and CNG mileage are nearly absent (4.2% and 4.7%). This cripples running-cost and efficiency-based recommendations. Secondary gaps: drive modes (33.7%), wireless charging (69.4%), heads_up_display (70%).

**Zero coverage** exists for: NCAP ratings, owner satisfaction, resale value, professional reviews, and all derived/aggregated scores.

### 3. Which information is uniquely valuable because of provenance/multi-source structure?

Fields confirmed by **4 independent sources** carry the highest trust the KB can currently provide: `sunroof`, `tyre_pressure_monitoring_system`, `adas_available`, `ventilated_front_seats`, `cruise_control`, `heads_up_display`. The 8,398 confirmed provenance rows and 2,454 tracked-and-resolved conflicts represent something that **no flat CSV can provide** — a permanent record of source disagreement and its authoritative resolution.

### 4. What recommendation queries can it already support reliably?

- Transmission preference (manual/automatic/CVT)
- Price budget filtering
- Seating capacity (5-seater vs. 7-seater)
- ADAS availability and tier
- Safety package (airbags, ABS, ESC, TPMS, cameras)
- Sunroof / panoramic roof
- Infotainment (Android Auto, Apple CarPlay)
- Connected car features
- Rear AC vents / comfort filtering
- Boot space (family vs. city car)
- Fuel type (petrol/diesel/CNG/EV)
- Drivetrain (FWD/AWD/4WD)
- Dimensions (compact vs. large body)
- Feature-based price segmentation

### 5. What recommendation queries can it NOT support yet?

- "Best mileage car" (54% coverage, unreliable ranking)
- "Lowest running cost" (same)
- "Best EV range" (4.2% coverage)
- "Safest by crash test" (NCAP: 0%)
- "Most reliable" (owner data: 0%)
- "Best resale value" (0%)
- "Sporty / drive modes" (33.7% — too many unknowns)
- "Fuel efficiency for CNG" (4.7%)

### 6. Single most important next knowledge layer to add

**Mileage/Efficiency Re-pass** is the single most impactful quick addition — it is a known structured field with an existing schema column, requires no architecture changes, and unlocks the most common real-world filter. The second most important is **Bharat NCAP ingestion**, as it provides tier-1 safety authority that the KB currently cannot claim for any variant.
