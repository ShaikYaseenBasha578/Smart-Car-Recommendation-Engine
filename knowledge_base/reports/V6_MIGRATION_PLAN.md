# Migration Plan: V6 to Phase 1 Knowledge Base

This document outlines the exact deterministic script sequence to convert the flat `carrec_recommendation_dataset_v6.csv` into the new SQLite relational schema without losing data or NULL semantics.

## Step 1: Bootstrap the Hierarchies (Make, Model)
1. Query V6 for `SELECT DISTINCT make FROM v6`. Insert into `manufacturer`.
2. Query V6 for `SELECT DISTINCT make, model FROM v6`. Insert into `model` with Foreign Keys (FK) to `manufacturer`.

## Step 2: Infer "Generation 1" Defaults
V6 lacks explicit generation data.
1. For every `model_id` in the `model` table, insert one row into `generation` named `"Gen 1 (Auto-Migrated)"`. 
2. *Rationale:* This preserves the schema requirement for Safety Ratings without requiring manual annotation immediately.

## Step 3: Infer Powertrain Architectures
V6 blends fuel types and transmissions.
1. Group V6 by `(model, fuel_type)`. 
2. Insert these into `powertrain`, linking to the default `generation_id`. (e.g. Nexon ICE vs Nexon EV become distinct powertrains).

## Step 4: Insert Canonical Variants
1. Iterate over all 812 rows in V6.
2. Generate a UUID for the row.
3. Map the row to the correct `powertrain_id`.
4. Insert all objective specifications (Dimensions, Engine CC, Features, Price) directly into the `variant` table.
5. *Validation Check:* Assert `SELECT COUNT(*) FROM variant == 812`.

## Step 5: Migrate Aliases (variant_mapping.json)
1. Read the existing `variant_mapping.json`.
2. For each mapping (e.g. `91wheels_url`), strip the base URL to get the `source_id`.
3. Join against the V6 row to find the new Canonical UUID.
4. Insert into `variant_alias` with `source_name = '91wheels'` and `source_id = 'slug'`.

## Step 6: Extract Safety & Warranty
1. Find unique Safety Ratings in V6 (ignoring `NaN`).
2. Insert into `safety_rating`, linking to the correct `generation_id` or `powertrain_id` based on the V6 source row.
3. Find unique Warranty combinations.
4. Insert into `warranty`, linking to the correct `powertrain_id` (this neatly separates the EV batteries).
5. Drop these columns from the flat dataset during the import.

## Rollback Strategy
Because the process writes to a local `carrec_kb.sqlite3` file, rolling back simply requires deleting the `.sqlite3` file and rerunning the Python migration script. The original `carrec_recommendation_dataset_v6.csv` remains completely untouched.
