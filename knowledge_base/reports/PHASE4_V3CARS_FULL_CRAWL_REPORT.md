# Phase 4: V3Cars Full Crawl Report

## A. Global Crawl Statistics
*   **Total Models Assessed:** 62
*   **V3Cars Data Found:** 50 Models (12 Models returned `NO_DATA` for variants/inheritance graphs)
*   **Total Variants Discovered:** 801
*   **Variants Resolved to Canonical:** 438
*   **Identity Resolution Rate:** 54.6%
*   **Total Cells Newly Populated:** 230
*   **Fields Overwritten:** 0 (Absolute Canonical Immutability Preserved)

## B. 62-Model Coverage Table

| Model | Discovered | Resolved | Unresolved | New Fields |
|---|---|---|---|---|
| honda_amaze | 6 | 0 | 6 | 0 |
| honda_city | 8 | 0 | 8 | 0 |
| honda_elevate | 9 | 9 | 0 | 9 |
| hyundai_aura | 8 | 1 | 7 | 3 |
| hyundai_creta | 34 | 34 | 0 | 0 |
| hyundai_exter | 19 | 19 | 0 | 0 |
| hyundai_grand-i10-nios | 15 | 0 | 15 | 0 |
| hyundai_venue | 35 | 35 | 0 | 13 |
| hyundai_verna | 22 | 8 | 14 | 0 |
| kia_carens-clavis | 0 | 0 | 0 | 0 |
| kia_carens-clavis-ev | 17 | 0 | 17 | 0 |
| kia_seltos | 44 | 44 | 0 | 69 |
| kia_syros | 17 | 14 | 3 | 17 |
| mg_hector | 7 | 1 | 6 | 0 |
| mg_windsor-ev | 5 | 0 | 5 | 0 |
| mahindra_bolero | 4 | 0 | 4 | 0 |
| mahindra_scorpio-classic | 4 | 4 | 0 | 4 |
| mahindra_scorpio-n | 31 | 0 | 31 | 0 |
| mahindra_thar | 7 | 7 | 0 | 17 |
| mahindra_thar-roxx | 28 | 27 | 1 | 9 |
| mahindra_xuv-3xo | 29 | 29 | 0 | 30 |
| mahindra_xuv-7xo | 0 | 0 | 0 | 0 |
| maruti-suzuki_alto-k10 | 0 | 0 | 0 | 0 |
| maruti-suzuki_baleno | 9 | 1 | 8 | 0 |
| maruti-suzuki_brezza | 0 | 0 | 0 | 0 |
| maruti-suzuki_dzire | 0 | 0 | 0 | 0 |
| maruti-suzuki_eeco | 0 | 0 | 0 | 0 |
| maruti-suzuki_ertiga | 9 | 0 | 9 | 0 |
| maruti-suzuki_fronx | 0 | 0 | 0 | 0 |
| maruti-suzuki_grand-vitara | 0 | 0 | 0 | 0 |
| maruti-suzuki_jimny | 6 | 1 | 5 | 0 |
| maruti-suzuki_s-presso | 8 | 0 | 8 | 0 |
| maruti-suzuki_swift | 14 | 14 | 0 | 0 |
| maruti-suzuki_victoris | 0 | 0 | 0 | 0 |
| maruti-suzuki_wagonr | 0 | 0 | 0 | 0 |
| maruti-suzuki_xl6 | 9 | 1 | 8 | 0 |
| maruti-suzuki_e-vitara | 0 | 0 | 0 | 0 |
| nissan_gravite | 8 | 0 | 8 | 0 |
| nissan_magnite | 22 | 0 | 22 | 0 |
| renault_duster | 17 | 0 | 17 | 0 |
| renault_triber | 7 | 0 | 7 | 0 |
| skoda_kushaq | 12 | 11 | 1 | 0 |
| skoda_kylaq | 13 | 13 | 0 | 10 |
| skoda_slavia | 10 | 10 | 0 | 12 |
| tata_altroz | 27 | 12 | 15 | 24 |
| tata_harrier | 55 | 19 | 36 | 22 |
| tata_nexon | 81 | 81 | 0 | 32 |
| tata_nexon-ev | 10 | 0 | 10 | 0 |
| tata_punch-ev | 6 | 0 | 6 | 0 |
| tata_tiago | 20 | 6 | 14 | 16 |
| tata_tiago-ev | 4 | 0 | 4 | 0 |
| tata_tigor | 14 | 0 | 14 | 0 |
| toyota_fortuner | 9 | 7 | 2 | 15 |
| toyota_glanza | 9 | 7 | 2 | 0 |
| toyota_hilux | 3 | 0 | 3 | 0 |
| toyota_innova-crysta | 8 | 0 | 8 | 0 |
| toyota_innova-hycross | 13 | 0 | 13 | 0 |
| toyota_rumion | 8 | 0 | 8 | 0 |
| toyota_urban-cruiser-hyryder | 18 | 0 | 18 | 0 |
| toyota_urban-cruiser-taisor | 0 | 0 | 0 | 0 |
| volkswagen_taigun | 11 | 11 | 0 | 20 |
| volkswagen_virtus | 12 | 12 | 0 | 9 |

## C. Variant Resolution Statistics
V3Cars yielded an identity resolution rate of 54.6%. It struggled to resolve due to highly generic transmission labels ("Automatic") that failed strict canonical boundary tests (e.g. `CVT`, `Torque Converter`, `DCT`), and entirely missing historical facelifts.

## D. Field-level Enrichment
| Field | Non-null Before | Non-null After | New Populated | Confirmed by Source | Rejected / Conflicting | % Gain |
|---|---|---|---|---|---|---|
| **Tyre Pressure Monitor** | 777 | 783 | 6 | 252 | 172 | +0.7% |
| **ADAS** | 808 | 808 | 0 | 370 | 68 | +0.0% |
| **Sunroof** | 809 | 809 | 0 | 254 | 184 | +0.0% |
| **Ventilated Seats** | 787 | 805 | 18 | 335 | 85 | +2.2% |
| **Cruise Control** | 509 | 584 | 75 | 195 | 137 | +9.2% |
| **Wireless Charging** | 515 | 577 | 62 | 198 | 147 | +7.6% |
| **Heads Up Display** | 499 | 568 | 69 | 338 | 0 | +8.5% |

*Note: Phase 3 (91Wheels) already saturated fields like Sunroof and ADAS; V3Cars largely served as corroborating evidence (`confirmed`).*

## E. Conflict Statistics
Total rejected actions: 997.
The majority of conflicts originated from:
1. **Generic Boolean Decay:** When V3Cars doesn't feature an exhaustive variant inheritance table for older/special-edition variants (e.g. *Creta King Edition*), the script yields an empty boolean array (`0`). This correctly bounded off against the canonical V6 `1`, preserving existing DB truths.
2. **Nomenclature Differences:** Features like "Cruise Control" vs "Adaptive Cruise Control".

## F. Historical Variant Coverage
V3Cars maintains excellent structure for *current* and *last-gen* facelifts, but completely removes heavily deprecated variants from its canonical pages. This resulted in dozens of unresolved historical V6 trims from 2021.

## G. Unresolved/Review Reasons
The 363 unresolved variants fell precisely into the following bounds-failure traps:
1. **Variant Not Found (194):** Historical or obscure variants completely absent from V3Cars.
2. **Transmission Mismatch (142):** V3Cars labeling variants purely as `"Automatic"`, while our canonical DB strictly requires specific architectures (`CVT`, `DCT`, `TC`). Identity resolver securely prevented overwriting.
3. **Fuel Mismatch (27):** V3Cars collapsing hybrid/CNG taxonomies ambiguously.

## H. Model-Level Warranty Evidence
Successfully extracted 44 Model-Level standard warranties (e.g., "3 Year(s) / Unlimitedkm"). 
These observations have been natively ingested as `source_observation` records with `resolution_status = 'model_level'` and `resolved_variant_id = NULL`. The raw payload specifies `"scope": "MODEL"`, preserving epistemological truth without forcing assumed conclusions on the variants.

## I. Canonical Immutability Verification
*   **Rows Unchanged:** 718
*   **Variants Enriched:** 94
*   **Fields Overwritten:** 0

The strict Tier-2 boundary protocols passed seamlessly.

## J. Idempotency Verification
Tested on two heavily covered models (Kia Seltos, Tata Nexon). The second ingestion pass correctly resulted in:
*   `new_fields: 0`
*   `conflicts: 0`
*   Observation deduplication successful.

## K. Remaining Limitations
V3Cars is fundamentally an editorialized recommendation platform. We extracted their feature inheritance graph, but we could NOT extract specific Engine CC, Dimensions, Boot Space, and precise Wheelbase measurements on a *variant-by-variant* basis. Their tables only publish these specs for a single "Recommended Powertrain" per model.

## L. Recommendation for Phase 5
**Is OEM now the highest-value next source?**
No.
While OEM brochures offer undeniable ground-truth accuracy (Tier 1), they exclusively represent *currently sold vehicles*. Because a massive portion of our 812-variant V6 Knowledge Base represents historically deprecated models (pre-2022 facelifts), OEM parsing would yield negligible enrichment for the bulk of our missing variant-specific dimensions and engine specifications.

**What is materially missing?**
Variant-specific dimensional and performance data across multiple powertrains (Turbo vs NA dimensions, exact boot space, weight), and deep historical coverage.

**Recommended Next Source:** CarWale or Team-BHP. These databases maintain massive historic encyclopedias encompassing variant-specific engine permutations spanning several generations, making them the most mathematically optimal target to resolve our remaining 194 unmapped variants.
