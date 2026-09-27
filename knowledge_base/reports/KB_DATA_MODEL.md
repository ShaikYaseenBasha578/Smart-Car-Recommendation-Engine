# CarRec Knowledge Base — Logical Data Model

To support the multi-tiered architecture without overengineering, the KB requires the following core logical entities. 

## 1. Identity & Hierarchy Entities

**`Manufacturer`**
* *Purpose:* Root entity (e.g., Hyundai, Tata).
* *Key Fields:* `id`, `name`, `origin_country`

**`Model`**
* *Purpose:* Marketing nameplate (e.g., Creta, Nexon).
* *Key Fields:* `id`, `manufacturer_id`, `name`

**`Generation`**
* *Purpose:* Solves the applicability problem for safety ratings and generational shifts.
* *Key Fields:* `id`, `model_id`, `generation_identifier` (e.g., "Creta Gen 2 Facelift"), `start_year`, `end_year`

**`Powertrain_Architecture`**
* *Purpose:* Groups variants that share structural and dynamic traits (e.g., Nexon ICE vs Nexon EV). Crucial for safety rating and ride-quality boundaries.
* *Key Fields:* `id`, `generation_id`, `fuel_type`, `hybrid_type`, `ev_architecture`

**`Variant` (The Core Entity)**
* *Purpose:* The exact purchasable configuration. The canonical unit of recommendation.
* *Key Fields:* `id` (UUID), `powertrain_id`, `canonical_name` (e.g., "Hyundai Creta 1.5 MT SX"), `transmission`, `discontinued` (boolean).

## 2. Specification & Provenance Entities

**`Variant_Specs` (The V6 Successor)**
* *Purpose:* Wide table storing the accepted canonical facts for immediate querying. 
* *Key Fields:* `variant_id` (PK), `price_ex_showroom`, `engine_cc`, `airbags`, etc.
* *Design Note:* Instead of raw values, fields susceptible to conflict (like `boot_space`) will use a custom Postgres Composite Type or JSONB storing `{"val": 433, "src": "OEM", "updated": "2026-09-01"}`.

**`Source_Observation` (The Staging Area)**
* *Purpose:* Stores raw incoming data from scrapers before it becomes canonical. Prevents silent overwriting.
* *Key Fields:* `id`, `source_name` (e.g., "91Wheels"), `source_url`, `extracted_date`, `variant_alias_id`, `json_payload` (the raw scraped features).

## 3. Experiential & Derived Knowledge Entities

**`Review_Source_Document`**
* *Purpose:* Tracks the origin of a qualitative review (e.g., a specific Team-BHP thread or Autocar article).
* *Key Fields:* `id`, `source_type` ("OWNER", "PROFESSIONAL"), `url`, `author`, `publication_date`, `applicable_powertrain_id` (Reviews rarely apply to a single trim variant, they usually apply to the Powertrain/Generation).

**`Extracted_Aspect_Observation`**
* *Purpose:* The output of our NLP Aspect-Based Sentiment Analysis models.
* *Key Fields:* `id`, `document_id`, `aspect` (e.g., "Gearbox", "AC", "Ride Quality"), `sentiment_score` (-1.0 to 1.0), `raw_quote`, `confidence`.

**`Derived_Consensus`**
* *Purpose:* The aggregated rollup of `Extracted_Aspect_Observation`. The engine queries this table to answer "How reliable is the DSG?"
* *Key Fields:* `powertrain_id`, `aspect`, `average_sentiment`, `evidence_count`, `summary_text` (LLM-generated synthesis of the quotes).

## 4. Entity Resolution Entities

**`Variant_Alias_Map`**
* *Purpose:* Resolves source-specific messy names to our canonical `Variant` UUID.
* *Key Fields:* `id`, `source_name` (e.g., "CarWale"), `source_variant_id` (e.g., "creta-ex-diesel"), `canonical_variant_id`.
