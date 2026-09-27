# CarRec Knowledge Base — Architecture Review

This document critically re-evaluates the previously proposed architecture for the CarRec Knowledge Base (KB), adjusting it for practical implementation in Phase 1. The goal is to build a robust foundation without premature optimization.

## 1. Storage: PostgreSQL vs. SQLite
* **Previous Recommendation:** PostgreSQL.
* **New Decision:** **SQLite (with JSON1 extension)** for Phase 1.
* **Rationale:** The current dataset is ~812 rows. Even with extreme historical growth and extensive provenance tracking, the dataset will easily remain under 1GB. SQLite requires zero infrastructure, runs locally alongside the codebase, eliminates networking overhead, and natively supports powerful JSON operations. It accelerates development while retaining standard SQL constraints. We will defer PostgreSQL until concurrency/scale explicitly demands it.

## 2. Provenance: Inline JSONB vs. Wide Tables + Ledger
* **Previous Recommendation:** Embedding provenance inside the canonical column (e.g., `boot_space = {"val": 433, "src": "OEM"}`).
* **New Decision:** **Hybrid Wide Table + Provenance Ledger**.
* **Rationale:** Inline JSON completely destroys the ability to easily query the database (e.g., `SELECT * FROM variant WHERE boot_space > 400` becomes complex and slow). 
  * **Solution:** The `variant` table remains a traditional "wide" table with standard datatypes (`INTEGER`, `REAL`). A separate `field_provenance` ledger table tracks *why* a specific field holds that value, tracking the source, extraction date, and any flagged conflicts. The database remains trivial to query for the recommender.

## 3. Entity Hierarchy
* **Retained Decision:** Manufacturer ➔ Model ➔ Generation ➔ Powertrain ➔ Variant.
* **Rationale:** This is strictly necessary. Safety ratings apply to a *Generation*. Battery warranties apply to a *Powertrain*. Variants inherit these safely.
* **Adjustment for Phase 1:** Since V6 does not have explicit `Generation` data for all cars, the migration will create a default "Unknown Generation 1" for every model. This prevents the schema from breaking while allowing manual correction later.

## 4. Entity Resolution & Aliasing
* **Retained Decision:** Decoupled Identity Model (Canonical UUID vs Source Aliases).
* **Rationale:** `variant_mapping.json` proves that sources use entirely different naming conventions (e.g., `carwale_id` vs `91wheels_id`). A dedicated `variant_alias` table maps these strings to the canonical `variant_id`.

## 5. Review & Experiential Evidence Layer
* **Previous Recommendation:** Build NLP ABSA tables now.
* **New Decision:** **Deferred**.
* **Rationale:** The NLP recommendation engine is a future research project. The Phase 1 schema will simply ensure the hierarchical IDs exist so that future `owner_review` tables can easily hold a `powertrain_id` or `variant_id` foreign key.

## 6. Source Observations
* **Retained Decision:** Scrapers write to staging, not directly to the canonical DB.
* **Adjustment for Phase 1:** Scrapers will dump raw JSON payloads into a `source_observation` table. A resolution script parses this JSON, compares it to the canonical `variant`, and logs conflicts in `field_provenance`.
