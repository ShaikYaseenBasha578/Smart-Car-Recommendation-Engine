# CarRec Knowledge Base — Phase 1 Specification

## 1. Phase 1 Scope
The objective of Phase 1 is to migrate the flat `carrec_recommendation_dataset_v6.csv` into a robust SQLite relational database, enabling traceable provenance and safe hierarchical data inheritance (Safety/Warranty). 
**Out of Scope for Phase 1:** NLP pipelines, professional/owner reviews, and the new recommendation engine.

## 2. The Database Choice: SQLite
We are rejecting PostgreSQL for Phase 1. SQLite with the JSON1 extension provides all the relational integrity and JSON document-storage required without the infrastructure overhead. It is perfect for a highly read-optimized dataset of ~812 variants.

## 3. The Core Concept: The Purchasable Variant
The fundamental unit remains the **Purchasable Variant**. Objective specifications (Price, Dimensions, Engine, Features) will not be normalized into abstract tables. They will live directly on the `variant` table as standard columns (`price_ex_showroom`, `boot_space_litres`). This ensures the database remains instantly queryable for the eventual recommendation engine without massive `JOIN` penalties.

## 4. Provenance and Conflict Resolution
To prevent silent overwrites:
1. **Source Observation:** Web scrapers (91Wheels, V3Cars) NO LONGER update CSVs. They `INSERT` their scraped payload as a JSON object into `source_observation`.
2. **Validation Engine:** A Python daemon reads `source_observation`. It uses `variant_alias` to resolve the source's variant URL to our Canonical UUID.
3. **Canonical Update:** If the data matches or fills a `NULL` hole, it updates the `variant` table. If it conflicts with existing data, the script consults the `SOURCE_AUTHORITY_MATRIX.md`. The winning value updates `variant`, and the details are logged in `field_provenance` to explain exactly *why* a number was chosen.

## 5. Safely Storing Safety & Warranty
In V6, safety and warranty were flat columns duplicated across dozens of rows. 
In Phase 1, they are moved to dedicated tables:
* `safety_rating` is linked to `generation_id` (so 2022 Creta results don't bleed into 2024 models) and optionally `powertrain_id` (so ICE ratings don't automatically apply to EV).
* `warranty` is linked to `powertrain_id` (separating EV battery warranties from standard ICE warranties).

## 6. Future Experiential Layer Hooks
While we are not building the NLP review engine yet, Phase 1 establishes the exact Foreign Keys (`generation_id`, `powertrain_id`, `variant_id`) that the future `owner_review` and `derived_consensus` tables will need to attach their statistical findings to the correct car.
