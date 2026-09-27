# Architectural Decisions & Rationale

## 1. Storage: PostgreSQL (JSONB) vs Graph/MongoDB
* **Decision:** PostgreSQL with JSONB columns.
* **Alternative Considered:** Neo4j (Graph) or MongoDB.
* **Reason:** Car recommendation relies heavily on strict numerical and boolean filtering (e.g., `price < 1500000 AND airbags >= 6`). Relational databases excel at this. However, traditional SQL fails at handling dynamic provenance (tracking conflicts per field). JSONB allows us to keep the relational querying power while embedding flexible provenance metadata directly alongside the data.

## 2. Ontology: Purchasable Variant vs Generic "Vehicle"
* **Decision:** The primary unit of truth is the exact purchasable `Variant` (e.g., Hyundai Creta SX 1.5 AT).
* **Alternative Considered:** Abstracting features to the `Model` level and using inheritance (e.g., Model has Airbags, Variant inherits Model).
* **Reason:** In India, features differ wildly between variants. Applying a "Model" level feature inheritance leads to false positives. We restrict hierarchy only to things that strictly apply universally (e.g., `Powertrain_Architecture` dictates EV vs ICE; `Generation` dictates Crash Safety). 

## 3. Provenance: No Silent Overwrites
* **Decision:** Incoming scraped data must stage into a `Source_Observation` table.
* **Alternative Considered:** Scripts update the main CSV/Database directly (The V6 approach).
* **Reason:** Silent overwriting destroys data trust. If a scraper pulls a malformed number, the previous correct data is lost. By staging data and using a Source Authority Matrix to resolve conflicts, the KB becomes self-healing and auditable.

## 4. Reviews: Segregating Objective vs Experiential Data
* **Decision:** Qualitative reviews (Team-BHP) will be stored in separate `Derived_Consensus` tables, never inside `Variant_Specs`.
* **Alternative Considered:** Adding columns like `ride_comfort_score` directly to the `Variant_Specs` table.
* **Reason:** Objective specs (Length = 4300mm) are absolute facts. Experiential data (Ride = Stiff) is a statistical consensus of opinions. Mixing them confuses the recommendation engine. The engine must know whether a constraint is a "Hard Filter" (Must have Sunroof) vs a "Soft Weight" (Prefer comfortable ride).

## 5. Backward Compatibility (V6 CSV Export)
* **Decision:** The KB will feature an automated nightly export that flattens the relational DB back into `carrec_recommendation_dataset_v6_compatible.csv`.
* **Reason:** The existing Python Flask recommendation code expects the flat 64-column V6 structure. We cannot afford to rewrite the entire frontend immediately. This export allows the KB to evolve its data acquisition pipeline independently of the consumer app.
