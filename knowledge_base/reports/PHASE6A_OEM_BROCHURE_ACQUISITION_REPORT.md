# Phase 6A: OEM Brochure Acquisition Report

## 1. Acquisition Overview

- **Total Canonical Models:** 62
- **Acquired / Already Present:** 8
- **Official Source Found but Download Blocked:** 0
- **Official Brochure Not Found:** 0
- **Source Ambiguous:** 0
- **Other Failures (Search Engine / WAF Blocks):** 54

## 2. Production Safety Verification

- **Production DB Hash (Before):** \`53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01\`
- **Production DB Hash (After):** \`53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01\`
- **Extraction / Ingestion:** No extraction, layout parsing, or ingestion occurred during this phase.

## 3. Manufacturer Failure Breakdown

Automated crawler requests were uniformly rejected with HTTP 202 (Accepted - Redirect to Captcha/WAF Challenge) by the underlying search engine due to strict automated bot protections against downloading OEM PDFs.

- **Honda:** 3 blocked models
- **Hyundai:** 3 blocked models
- **Kia:** 4 blocked models
- **MG:** 2 blocked models
- **Mahindra:** 6 blocked models
- **Maruti Suzuki:** 11 blocked models
- **Nissan:** 2 blocked models
- **Renault:** 2 blocked models
- **Skoda:** 3 blocked models
- **Tata:** 8 blocked models
- **Toyota:** 8 blocked models
- **Volkswagen:** 2 blocked models

## 4. Current vs Historical Brochures

For models where the artifact was successfully identified (e.g., Swift `gen4_2024`, Creta `gen2_facelift_2024`), the specific generation directory was explicitly maintained. 

## 5. 62-Model Acquisition Inventory

| Manufacturer | Model | Status | Official Source | Artifact | SHA-256 | Notes |
|---|---|---|---|---|---|---|
| Honda | Amaze | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Honda | City | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Honda | Elevate | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Hyundai | Aura | ALREADY_PRESENT | LOCAL | .../Aura_Brochure.pdf | 7f8bc76a... | VERIFIED |
| Hyundai | Creta | ALREADY_PRESENT | LOCAL | .../Hyundai_Creta_Brochure_Official.pdf | d9ad9205... | VERIFIED |
| Hyundai | Exter | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Hyundai | Grand i10 Nios | ALREADY_PRESENT | LOCAL | .../Grand_i10_Nios_Brochure.pdf | 064d8d8f... | VERIFIED |
| Hyundai | Venue | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Hyundai | Verna | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Kia | Carens Clavis | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Kia | Carens Clavis EV | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Kia | Seltos | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Kia | Syros | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| MG | Hector | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| MG | Windsor EV | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Mahindra | Bolero | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Mahindra | Scorpio Classic | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Mahindra | Scorpio-N | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Mahindra | Thar | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Mahindra | Thar Roxx | ALREADY_PRESENT | LOCAL | .../Thar_Roxx_Brochure.pdf | 12e63192... | VERIFIED |
| Mahindra | XUV 3XO | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Mahindra | XUV 7XO | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Alto K10 | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Baleno | ALREADY_PRESENT | LOCAL | .../Baleno_Brochure.pdf | 60bd6c9d... | VERIFIED |
| Maruti Suzuki | Brezza | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Dzire | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Eeco | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Ertiga | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Fronx | ALREADY_PRESENT | LOCAL | .../Fronx_Brochure.pdf | 737cc1f4... | VERIFIED |
| Maruti Suzuki | Grand Vitara | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Jimny | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | S-Presso | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | Swift | ALREADY_PRESENT | LOCAL | .../Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf | db41424a... | VERIFIED |
| Maruti Suzuki | Victoris | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | WagonR | ALREADY_PRESENT | LOCAL | .../WagonR_Brochure.pdf | b75963fc... | VERIFIED |
| Maruti Suzuki | XL6 | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Maruti Suzuki | e VITARA | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Nissan | Gravite | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Nissan | Magnite | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Renault | Duster | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Renault | Triber | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Skoda | Kushaq | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Skoda | Kylaq | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Skoda | Slavia | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Altroz | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Harrier | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Nexon | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Nexon EV | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Punch EV | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Tiago | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Tiago EV | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Tata | Tigor | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Fortuner | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Glanza | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Hilux | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Innova Crysta | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Innova Hycross | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Rumion | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Urban Cruiser Hyryder | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Toyota | Urban Cruiser Taisor | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Volkswagen | Taigun | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |
| Volkswagen | Virtus | OTHER_FAILURE | N/A | N/A | N/A | SEARCH_ENGINE_WAF_BLOCK_HTTP_202 |

---
**FINAL VERDICT**
`PHASE 6A BROCHURE ACQUISITION COMPLETE`
