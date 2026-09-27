# CarRec Knowledge Base Architecture

The CarRec Automotive Knowledge Base is designed to support both rigorous research/reproducibility and a production recommendation product. It maintains a strict provenance ledger mapping source observations to canonical truths.

## Core Hierarchy
1. **Manufacturer** (e.g., Hyundai)
2. **Model** (e.g., Creta)
3. **Generation** (e.g., 2nd Gen)
4. **Powertrain** (e.g., 1.5L Diesel)
5. **Variant** (e.g., SX Opt Diesel AT)

## Canonical Variant Concept
The `variant` table stores the primary canonical representation of a vehicle. A base canonical variant represents a distinct technical configuration. Fields on this table are strictly populated based on verified evidence from authoritative sources, tracked via the `field_provenance` table.

## Edition / Package Concept
Automakers frequently release marketed packages (e.g., "Dark Edition", "Anniversary Edition"). 
To represent these without bloating the canonical taxonomy or treating them merely as aliases, the `variant` table utilizes a self-referencing relationship:
- `base_variant_id`: Points to the underlying base canonical variant.
- `edition_classification`: Categorizes the edition based on source evidence:
  - `NO_MATERIAL_DIFFERENCE`: Evidence confirms no structured feature changes.
  - `FEATURE_OR_SPEC_DIFFERENCE`: Evidence confirms one or more overridden features.
  - `DISTINCT_TECHNICAL_CONFIGURATION`: Evidence suggests a genuinely distinct configuration.
  - `UNRESOLVED_EDITION`: The relationship is known but evidence is currently lacking.

## Inheritance and Overrides
A view named `v_effective_variant` leverages SQLite `COALESCE` to project the final purchasable configuration. 
Editions are initialized with `NULL` for feature columns. `COALESCE` gracefully falls back to the base variant's truth unless the edition contains an explicitly verified override (including an explicit `0`/`False`).

## Provenance
Every cell populated in the `variant` table requires a corresponding row in `field_provenance`. 
Editions have their own independent provenance. Overrides observed on an edition are stamped against the edition's `variant_id`, ensuring the base variant is never accidentally mutated by edition-specific marketing.

## Historical Handling
Historical and discontinued configurations are strictly preserved. The `is_discontinued` flag on the `variant` table ensures that historical data remains queryable for research and historical alias resolution, without polluting active pricing.

## Resolver Behavior and Unresolved States
The resolver isolates unstructured strings into targeted base variants utilizing strict structural bounds (Transmission, Fuel Type, Displacement). If a record cannot be safely mapped, it is logged in `source_observation` with an `unresolvable` status, preventing hallucinated merges.

## Future Context
- **Recommendation Engine:** The research algorithm can filter purely by `base_variant_id IS NULL` to compare fundamental architectures, preventing feature-space duplication.
- **Live Website:** The website can query `v_effective_variant` to display precise, actual marketed vehicle names along with accurate trims.
