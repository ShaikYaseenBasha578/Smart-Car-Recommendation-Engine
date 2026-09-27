# PHASE 7 KB GAP REGISTER

> **READ-ONLY audit artefact** — No gaps are repaired in this phase.  
> **Generated:** 2026-09-23  
> **Scope:** All 832 variants / 62 models / knowledge_base/carrec_kb.db  
> **Production checksum:** `e752ebde5b7f227140bedb319c6b9753a3fdbdde`

---

## CRITICAL Gaps

### GAP-001 — Mileage/Efficiency Data Incomplete

| Attribute | Value |
|---|---|
| **Field** | `mileage_arai_kmpl` |
| **Current coverage** | 449/832 (54.0%) |
| **Missing** | ~383 petrol/diesel variants |
| **Severity** | 🔴 CRITICAL |
| **Recommendation impact** | Cannot reliably answer "low running cost", "best mileage", "highway efficiency" queries. Ranking by efficiency is untrustworthy with 46% gap. |
| **Affected models** | Hyundai Verna (PDF fail), Kia Seltos (PDF fail), Tata Harrier, Tata Nexon, and many more |
| **Next layer** | Aggregator re-scrape (91wheels / v3cars targeted for this field) or OEM Phase 8 expansion |
| **Effort** | Medium — existing field, existing sources, no schema change |

---

### GAP-002 — EV Range Nearly Absent

| Attribute | Value |
|---|---|
| **Field** | `claimed_ev_range_km` |
| **Current coverage** | 35/832 (4.2%) |
| **Missing** | ~50+ EV/PHEV variants lack range data |
| **Severity** | 🔴 CRITICAL |
| **Recommendation impact** | Cannot support EV-range queries at all. EV buyers' primary criterion is range. |
| **Affected models** | Tata Nexon EV, Tata Punch EV, MG Windsor EV, Maruti e VITARA, Kia Carens Clavis EV, and others |
| **Next layer** | OEM brochure Phase 8 expansion; OEM PDFs for EV models are the only reliable source |
| **Effort** | Medium — requires Phase 8 OEM extraction pass for EV-specific brochures |

---

### GAP-003 — NCAP Safety Ratings Missing

| Attribute | Value |
|---|---|
| **Fields** | N/A (requires new field: `bharat_ncap_stars`, `global_ncap_stars`, `ncap_year`) |
| **Current coverage** | 0/832 (0%) |
| **Severity** | 🔴 CRITICAL |
| **Recommendation impact** | Cannot answer "safest car" or safety-first queries with authoritative crash-test data. |
| **Affected models** | All 832 variants — this layer is completely absent |
| **Next layer** | Bharat NCAP ingestion (source ID 7 exists, zero observations), Global NCAP (source ID 8 exists, zero observations) |
| **Effort** | High — requires new canonical fields, new ingestion pipeline, NCAP data sourcing |

---

## HIGH Gaps

### GAP-004 — Tata FeatureList Strategy Quarantined

| Attribute | Value |
|---|---|
| **Affected models** | Tata Altroz, Tata Harrier, Tata Nexon, Tata Nexon EV, Tata Punch EV, Tata Tigor |
| **Affected variants** | ~140+ (Nexon alone: 53 variants) |
| **Severity** | 🟠 HIGH |
| **Recommendation impact** | Tata is the largest brand by variant count in corpus. OEM enrichment for all Tata models failed due to quarantined FeatureListStrategy. Feature-level completeness is limited to v6_migration data only. |
| **Root cause** | Complex inheritance lists in Tata brochures require a strategy not yet production-capable |
| **Next layer** | Phase 8 FeatureListStrategy development and de-quarantine |
| **Effort** | High — requires new extractor strategy with full regression gate |

---

### GAP-005 — Kia Seltos OEM Failure (PDF_TEXT_FAILURE)

| Attribute | Value |
|---|---|
| **Affected model** | Kia Seltos |
| **Affected variants** | 41 variants |
| **Severity** | 🟠 HIGH |
| **Recommendation impact** | Seltos is one of the highest-traffic models in the Indian car market. No OEM enrichment was applied. |
| **Root cause** | Brochure PDF was image-only (no extractable text) |
| **Next layer** | Phase 8 OEM re-fetch with text-extractable PDF version |
| **Effort** | Low — re-fetch and re-run existing pipeline |

---

### GAP-006 — Mahindra Scorpio-N RESOLUTION_FAILURE

| Attribute | Value |
|---|---|
| **Affected model** | Mahindra Scorpio-N |
| **Affected variants** | 27 variants |
| **Severity** | 🟠 HIGH |
| **Recommendation impact** | Second-largest Mahindra model by variant count. No OEM enrichment applied. |
| **Root cause** | DB model name `Scorpio-N` did not match OEM brochure slug; `resolve_oem_generation()` returned 0 matches for `scorpio n starting None` |
| **Next layer** | Add model name alias to generation resolver, or add synonym to brochure manifest |
| **Effort** | Low — targeted fix in manifest or resolver alias table |

---

### GAP-007 — Owner Experience Layer Absent

| Attribute | Value |
|---|---|
| **Fields** | owner_satisfaction_score, reliability_rating, long_term_issues, real_world_mileage, etc. (not yet in schema) |
| **Current coverage** | 0/832 (0%) |
| **Severity** | 🟠 HIGH |
| **Recommendation impact** | Cannot answer questions like "most reliable", "owner satisfaction", "real-world fuel economy". These are major decision factors. |
| **Next layer** | Phase 9: Owner review layer (CarDekho user reviews, auto forums, survey data) |
| **Effort** | Very High — requires new schema fields, new sources, sentiment analysis |

---

### GAP-008 — CNG Mileage Coverage (4.7%)

| Attribute | Value |
|---|---|
| **Field** | `mileage_arai_km_per_kg` |
| **Current coverage** | 39/832 (4.7%) |
| **Affected** | ~60+ CNG variants |
| **Severity** | 🟠 HIGH |
| **Recommendation impact** | CNG buyers are strongly price/efficiency driven. Mileage is the #1 filter criterion. |
| **Next layer** | Aggregator re-scrape targeted for CNG variants |
| **Effort** | Low-Medium |

---

## MEDIUM Gaps

### GAP-009 — Drive Modes Coverage (33.7%)

| Attribute | Value |
|---|---|
| **Field** | `drive_modes` |
| **Current coverage** | 280/832 (33.7%) |
| **Severity** | 🟡 MEDIUM |
| **Recommendation impact** | "Sporty" queries, off-road recommendations unreliable. However, most entry-level cars genuinely don't have drive modes, so partial unknown is expected. |
| **Next layer** | OEM Phase 8 (drive modes are well-documented in OEM brochures) |

---

### GAP-010 — Wireless Charging Coverage (69.4%)

| Attribute | Value |
|---|---|
| **Field** | `wireless_charging` |
| **Current coverage** | 577/832 (69.4%) |
| **Severity** | 🟡 MEDIUM |
| **Recommendation impact** | Common premium filter in ₹10L+ segment. 30% unknown gap reduces filter reliability. |
| **Next layer** | OEM Phase 8; aggregator re-scrape |

---

### GAP-011 — Heads-Up Display Coverage (70.0%)

| Attribute | Value |
|---|---|
| **Field** | `heads_up_display` |
| **Current coverage** | 582/832 (70.0%) |
| **Severity** | 🟡 MEDIUM |
| **Recommendation impact** | Premium feature filter with 30% gap. |
| **Next layer** | OEM Phase 8; aggregator re-scrape |

---

### GAP-012 — Price Data Has Single Source

| Attribute | Value |
|---|---|
| **Field** | `price_ex_showroom` |
| **Current coverage** | 812/832 (97.6%) — **but only 1 source** |
| **Severity** | 🟡 MEDIUM |
| **Recommendation impact** | Prices change frequently. v6_migration data may be 6-12 months stale. All price filtering is based on a single un-validated source. |
| **Next layer** | Monthly price scrape from carwale/91wheels; provenance system will detect changes |

---

### GAP-013 — CardEkho Source Has Zero Observations

| Attribute | Value |
|---|---|
| **Source** | cardekho (source_id=5, tier=3) |
| **Current obs** | 0 |
| **Severity** | 🟡 MEDIUM |
| **Recommendation impact** | An additional cross-validation source that exists in schema but contributes nothing. Reduces multi-source confidence for all fields. |
| **Next layer** | CardEkho scraping pipeline |

---

### GAP-014 — Professional Review Layer Absent

| Attribute | Value |
|---|---|
| **Fields** | expert_rating, driving_dynamics_score, value_for_money_score, etc. (not in schema) |
| **Current coverage** | 0/832 (0%) |
| **Severity** | 🟡 MEDIUM |
| **Recommendation impact** | Cannot produce editorial-backed recommendations. Cannot distinguish "good value" objectively. |
| **Next layer** | Phase 9: Professional review ingestion |

---

## LOW Gaps

### GAP-015 — Tata Tiago PDF Failure

| Field | Tata Tiago, Tata Tiago EV — EXTRACTION_FAILURE (borderless matrix not located) |
|---|---|
| **Severity** | 🟢 LOW |
| **Note** | Tiago has reasonable coverage from v6_migration; this only prevents OEM enrichment |

---

### GAP-016 — Toyota Legacy Model OEM Failures

| Affected | Toyota Fortuner, Hilux, Innova Crysta, Rumion — EXTRACTION_FAILURE |
|---|---|
| **Severity** | 🟢 LOW |
| **Note** | These older-generation models have acceptable v6_migration coverage; OEM enrichment failure is acceptable for legacy models |

---

### GAP-017 — paddle_shifters 53.4% Coverage

| Attribute | Value |
|---|---|
| **Field** | `paddle_shifters` |
| **Current coverage** | 444/832 (53.4%) |
| **Severity** | 🟢 LOW |
| **Note** | Many MT-only variants genuinely don't have paddle shifters. Expected unknowns for manual cars. |

---

## Gap Priority Summary

| Priority | Gap | Effort | Unlock |
|---|---|---|---|
| 1 | GAP-001 Mileage re-pass | Medium | Running cost queries |
| 2 | GAP-003 NCAP ingestion | High | Safety authority queries |
| 3 | GAP-006 Scorpio-N alias fix | Low | 27 variants enriched |
| 4 | GAP-005 Seltos PDF re-fetch | Low | 41 variants enriched |
| 5 | GAP-002 EV range Phase 8 | Medium | EV recommendations |
| 6 | GAP-004 Tata FeatureList | High | 140+ variants enriched |
| 7 | GAP-007 Owner reviews | Very High | Satisfaction queries |
| 8 | GAP-013 CardEkho scrape | Medium | Cross-validation boost |
| 9 | GAP-009 Drive modes | Low-Medium | Sporty queries |
| 10 | GAP-012 Price refresh | Low-Medium | Price accuracy |
