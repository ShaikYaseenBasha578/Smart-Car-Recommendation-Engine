# CarRec Knowledge Base — Data Flow & Lifecycle

The data pipeline transitions from a linear script (V6) into a continuous, staging-based Data Flow. This ensures that no incoming scraped data can silently corrupt the Canonical Database without validation.

## The 8-Stage Lifecycle

### 1. Source 
* External data exists in the wild.
* *Example:* 91Wheels updates the `boot_space` of the Tata Nexon to 382L. Team-BHP publishes a new ownership review complaining about the Nexon's AMT gearbox.

### 2. Extraction
* Specific python adapters (e.g., `step24_v4_extraction.py`, Team-BHP NLP scraper) fetch the data.

### 3. Observation (Staging)
* Data is dumped into the `Source_Observation` or `Review_Source_Document` tables. 
* *Crucially, the Canonical Database is untouched.*

### 4. Entity Resolution
* The system looks at the incoming observation's identifier (e.g., `91wheels/nexon/amt-fearless`).
* It queries the `Variant_Alias_Map` to find the corresponding Canonical `Variant` UUID. 
* If no UUID exists, the data is flagged for Manual Review (New Variant Detected).

### 5. Validation & Conflict Resolution
* The system compares the new Observation against existing Canonical facts.
* **No Conflict:** (e.g., Boot space was previously `NULL`). Proceed to update.
* **Conflict Detected:** (e.g., Canonical boot space is `350L (Source: OEM)`). 
  * The system checks the `Field-Level Source Authority Matrix`. 
  * Since OEM > 91Wheels, the canonical fact remains `350L`. The 91Wheels `382L` is stored in the JSONB `conflicts` array for debugging.

### 6. Canonical Variant Update
* The `Variant_Specs` table is updated. The JSONB provenance is updated: `{"val": 350, "src": "OEM", "conflicts": [{"val": 382, "src": "91Wheels"}]}`.

### 7. Derived Knowledge Generation
* For qualitative data (Team-BHP reviews), the raw text in the `Review_Source_Document` is processed by an ABSA LLM pipeline into `Extracted_Aspect_Observation` (e.g. `Gearbox -> Jerky -> Neg`). 
* A scheduled cron job aggregates these into `Derived_Consensus` (e.g., "60% Negative Sentiment for Nexon AMT Gearbox based on 45 reviews").

### 8. Recommendation Engine (Consumption)
* The frontend user says: "I want an automatic SUV with no gearbox issues."
* The Recommendation Engine queries a Read-Optimized Materialized View that flattens `Variant_Specs` and `Derived_Consensus` into a lightning-fast cache, instantly filtering out the Nexon AMT.
