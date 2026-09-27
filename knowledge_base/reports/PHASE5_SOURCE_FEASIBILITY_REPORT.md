# Phase 5: Source Feasibility Report

## 1. Remaining KB Gaps (Phase 5B Quantification)
A rigorous SQL audit of the `carrec_kb.db` (812 canonical variants) revealed a critical misunderstanding of the current dataset state: **The canonical V6 dataset (ingested in Phase 1) already completely populates dimensions, weights, and engine specifications.** 

*   `length_mm`, `width_mm`, `height_mm`, `wheelbase_mm`, `ground_clearance_mm`: **0 missing (0%)**
*   `engine_cc`, `power_bhp`, `torque_nm`: **0 missing (0% for ICE)** (Only 11 EVs lack `engine_cc`).
*   `kerb_weight_kg`, `price_ex_showroom`: **0 missing (0%)**

**The Actual Structured Gaps:**
1.  **Missing Features:** `cruise_control` (228 missing / 28%), `heads_up_display` (244 missing / 30%), `boot_space_litres` (41 missing / 5%).
2.  **Current Pricing:** V6 prices reflect historical 2021-2023 Ex-Showroom figures.
3.  **Historical Variant Mapping (194 variants):** V3Cars failed to map these entirely because they dropped discontinued/older models from their current matrix.
4.  **Transmission Granularity Mismatch (142 variants):** V3Cars uses generic `"Automatic"` which bounced against our strict canonical bounds (`CVT`, `DCT`, `Torque Converter`).
5.  **Fuel Ambiguity (27 variants):** CNG/Hybrid taxonomy mismatches.

## 2. CarWale Feasibility (Phase 5A)
A live network assessment of CarWale yielded the following:
*   **Historical Coverage:** Excellent. (e.g., URL `/hyundai-cars/verna-2020/` successfully returns `200 OK`, unlike V3Cars and OEMs which wipe deprecated models).
*   **Transmission Granularity:** High. CarWale distinguishes CVT, DCT, and Torque Converter natively.
*   **Data Applicability:** Highly variant-specific.
*   **Scraping Difficulty:** High. The site utilizes a React/Loadable chunking architecture without an easily visible `__PRELOADED_STATE__`. It requires either API traffic reversing or headless browser rendering.
*   **Anti-Bot:** Moderate. Basic HTTP `GET` returned `200 OK` (no immediate Cloudflare block), but heavy crawling will require rotation/delays.
*   **Ingestion Fit:** Can seamlessly plug into our generic Phase 2 extraction/resolution pipeline.
*   **Problem Solved:** Directly targets the 194 missing historical variants and the 142 transmission-bounced variants that V3Cars failed to resolve.

## 3. OEM Feasibility (Phase 5C)
*   **Current Precision:** Absolute Tier-1 truth for pricing, dimensions, and active features.
*   **Historical Coverage:** Zero. Discontinued variants are immediately wiped from active OEM databases.
*   **Automation Difficulty:** Extreme. Requires building 15+ bespoke adapters for completely fragmented manufacturer architectures (React, Angular, Vanilla JS), many of which bury variant feature matrices in unstructured PDF brochures.
*   **Verdict:** OEM ingestion offers incredibly low marginal value for the effort because it abandons the 194 historical variants completely and relies on nightmare PDF parsing.

## 4. Team-BHP Role (Phase 5D)
Team-BHP is an unparalleled repository for **Experiential Knowledge**, not Structured Specifications. 
It must absolutely be utilized in the future for:
*   Long-term reliability and recurring defects (e.g., Skoda DSG failures, Hyundai paint peeling).
*   Real-world mileage vs ARAI.
*   NVH and ride-handling dynamics.
*   Ownership costs and service center competence.

*Do not* attempt to use Team-BHP to extract a structured 812-row table of exact Boot Space or `cruise_control` booleans.

## 5. Expected Marginal Coverage Improvement
Targeting an encyclopedic source with historical mapping (like CarWale) is expected to:
1.  Resolve the remaining ~336 unresolved V3Cars variants (194 missing + 142 transmission mismatches).
2.  Fill the final 28% subjective boolean gaps (`cruise_control`, `HUD`).
3.  Provide updated *current* pricing for active variants while preserving historical V6 pricing for discontinued models.

## 6. Recommended Phase 5 Source
**CARWALE**

## 7. Justification
The quantitative evidence proves that our primary structured gap is NOT basic dimensions or engines (V6 provided those), but rather feature-coverage and current-pricing for **historical and specifically-geared (CVT/DCT) variants**. 

OEM sources completely fail the historical requirement and are too fragmented. Team-BHP is an experiential source, not a structured database. CarWale mathematically offers the highest marginal value because it uniquely bridges the gap: it maintains deep historical variant pages (solving the 194 missing cases) and utilizes strict transmission nomenclature (solving the 142 V3Cars transmission conflicts), all within a unified (albeit technically challenging) site architecture.
