# Existing V6 to Knowledge Base Mapping

The future Knowledge Base (KB) must ingest and absorb all 64 columns of `carrec_recommendation_dataset_v6.csv`. No data will be discarded. Here is the explicit mapping of how V6 fields will be transitioned into the new logical architecture.

## 1. Identity & Hierarchy Fields
These fields will be extracted from the flat CSV and normalized into the new Hierarchical Entities (`Manufacturer`, `Model`, `Powertrain_Architecture`, `Variant`).

* **`make`** -> Move to `Manufacturer.name`
* **`model`** -> Move to `Model.name`
* **`variant`** -> Keep as `Variant.canonical_name`
* **`full_name`** -> Potentially obsolete (Can be generated dynamically: Make + Model + Variant)
* **`fuel_type`** -> Move to `Powertrain_Architecture.fuel_type`
* **`transmission`** -> Keep on `Variant` (Determines the exact purchasable unit)
* **`body_type`** -> Move to `Generation` or `Model` (Applies to the whole car)

## 2. Core Objective Specifications
These remain on the `Variant_Specs` wide table. They will be supplemented with JSONB provenance.

* **Keep Unchanged (Supplement with Provenance):** 
  `engine_cc`, `power_bhp`, `torque_nm`, `drivetrain`, `seating_capacity`, `boot_space_litres`, `ground_clearance_mm`, `length_mm`, `width_mm`, `height_mm`, `wheelbase_mm`, `kerb_weight_kg`, `fuel_tank_litres`
* **Source/Provenance Columns to Deprecate:**
  `kerb_weight_kg_source`, `fuel_tank_litres_source` -> These standalone columns become obsolete as provenance is natively embedded into the JSONB of the parent column.

## 3. Mileage & EV Metrics
* **Keep Unchanged (Supplement with Provenance):**
  `mileage_arai_kmpl`, `mileage_arai_km_per_kg`, `claimed_ev_range_km`
* **Future Addition Needed:** Need a new field for `real_world_mileage` derived from the `Derived_Consensus` NLP engine.

## 4. Variant Equipment & Features
These dictate the exact variant trim level and will remain directly on the `Variant_Specs` table.

* **Keep Unchanged:**
  `airbags`, `abs`, `esc`, `hill_assist`, `tyre_pressure_monitoring_system`, `rear_parking_sensors`, `rear_camera`, `camera_360`, `automatic_climate_control`, `rear_ac_vents`, `android_auto`, `apple_carplay`, `sunroof`, `ventilated_front_seats`, `connected_car_features`, `adas_available`, `adas_tier`, `cruise_control`, `paddle_shifters`, `wireless_charging`, `heads_up_display`, `drive_modes`

## 5. Pricing
* **Keep Unchanged:** `price_ex_showroom`
* **Future Addition Needed:** `Price_History` ledger table to track monthly OEM price hikes.

## 6. Safety & Warranty (The V6 Enrichment)
These fields will be moved out of the flat Variant row and mapped to higher-level entities to prevent duplication and generation mismatch.

* **Safety Ratings:** 
  `safety_rating_body`, `safety_rating_adult_stars`, `safety_rating_child_stars`, `safety_rating_test_year`, `safety_rating_tested_variant`, `safety_rating_source_url`
  *Mapping:* Move to a dedicated `Safety_Test` entity. Link this entity to the `Generation` or `Powertrain_Architecture` (NOT the `Variant`). 
* **Warranty:**
  `warranty_years`, `warranty_km`, `battery_warranty_years`, `battery_warranty_km`, `extended_warranty_available`, `warranty_source`, `warranty_source_url`
  *Mapping:* Move to a dedicated `Warranty_Policy` entity linked to the `Manufacturer` or `Powertrain_Architecture` (EV vs ICE batteries).

## What V6 Cannot Represent (New KB Additions)
V6 is entirely blind to the following concepts, which the new KB will introduce:
1. **Historical Changes:** Discontinued variants, generational facelifts.
2. **Experiential Evidence:** Team-BHP reliability scores, ride-comfort ratings, Autocar NVH reviews.
3. **Conflict Resolution:** If CarWale says 433L boot and 91Wheels says 448L, V6 silently accepts whatever script ran last. The KB will store both in `Source_Observation` and flag a conflict.
