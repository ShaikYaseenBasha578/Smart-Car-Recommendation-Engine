# Variant Identity & Entity Resolution Specification

The central challenge of building the CarRec Knowledge Base is **Entity Resolution**: determining that "Hyundai Creta SX (O) 1.5 Diesel AT" on 91Wheels is the exact same purchasable unit as "Creta 1.5 U2 CRDi AT SX Opt" on CarWale.

## The Canonical Identity Strategy

To prevent cross-variant contamination, the KB uses a **Decoupled Identity Model**. We do not force sources to conform to our naming convention. Instead, we generate a persistent internal UUID for the canonical variant, and map source-specific strings to it via an Alias Map.

### 1. The Canonical UUID
Every variant in the database receives an immutable UUID (`variant_id`). This is the absolute primary key. If a manufacturer renames a trim, the UUID remains the same.

### 2. The Internal Fingerprint (Slug)
To assist human debugging and initial V6 migration, every `variant_id` is assigned a deterministic Canonical Slug.
**Format:** `make_model_generation_fuel_transmission_trim`
**Example:** `hyundai_creta_gen2fl_diesel_tc_sx-o`

### 3. The `Variant_Alias_Map` Junction Table
We will migrate the logic currently inside `variant_mapping.json` into a formal relational table.

| alias_id | source | source_identifier | canonical_variant_id | match_confidence | manual_override |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 91wheels | `creta/sx-o-diesel-at` | `uuid-1234` | 1.0 | TRUE |
| 2 | carwale | `creta/1-5-u2-crdi-at-sx-opt` | `uuid-1234` | 0.85 | FALSE |

## Handling Identity Edge Cases

### A. Transmission & Powertrain Nomenclature
* **Problem:** Aggregators mix up Automatic designations (AT vs TC vs CVT vs DCT vs IVT vs AMT).
* **Solution:** The KB enforces a strict internal enum for `transmission_type` on the canonical `Variant` record. The `Source_Observation` staging table accepts the messy string, but the conflict resolver requires mapping it to the strict enum.

### B. Facelifts and Generations (The 2022 vs 2024 Creta Problem)
* **Problem:** 91Wheels replaces the 2022 Creta variant pages with the 2024 Facelift pages using the exact same URL slugs. If we overwrite directly, we destroy historical pricing and falsely apply 2022 safety ratings to 2024 models.
* **Solution:** The KB introduces the `Generation` entity. When a scraper detects a major structural update or model-year facelift, the old `Variant` records are marked `discontinued = TRUE`. Entirely new `Variant` UUIDs are generated for the facelift, linked to the new `Generation` ID. The `Variant_Alias_Map` is updated to point the 91Wheels URL slug to the *new* UUID.

### C. Duplicate / Similar Names
* **Problem:** Tata Nexon "Fearless" vs "Fearless Plus" vs "Fearless Plus S".
* **Solution:** No automated fuzzy-matching is allowed to bridge variants if their Ex-Showroom Price differs by more than ₹1,000. Price is used as the ultimate validation vector for trim separation. If two variants have different prices, they are different canonical variants, regardless of name similarity.
