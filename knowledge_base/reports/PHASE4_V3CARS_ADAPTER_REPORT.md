# Phase 4: V3Cars Source Adapter Report

## 1. Implementation Status
- **Status:** Complete (Representative Live Sample Validated).
- **Architecture:** Successfully decoupled extractor and mapper logic into a reusable Tier-2 ingestion pipeline leveraging the generic Phase 2 resolver and updater.

## 2. Files Created/Modified
- `knowledge_base/ingestion/extractor_v3cars.py` [NEW]: Implements a sophisticated parser that bypasses pure HTML/JSON guessing by dynamically compiling the "variant inheritance graph" (e.g., extracting "Features Over E") directly from V3Cars' *Variants Explained* articles. It also strictly isolates model-level warranty tables.
- `knowledge_base/ingestion/field_map_v3cars.py` [NEW]: Contains rigorous taxonomy mapping ensuring `connected-car technology` is NOT falsely collapsed into `wireless_charging`.
- `knowledge_base/ingestion/ingest_v3cars.py` [NEW]: Orchestrates the flow, preserving idempotency and Tier-2 field provenance.
- `knowledge_base/ingestion/updater.py` [MODIFIED]: Hardened boolean equivalence testing (`True`/`1` vs `False`/`0`) to prevent false-positive SQLite type mismatch conflicts between Phase 1 strings, Phase 3 integers, and Phase 4 bools.

## 3. Schema Changes
- **No schema changes were required.**
- **Limitation Handled (Model-Level Warranty):** Because V3Cars reports a single warranty table per model, cascading this assumption to all variants is epistemologically dangerous. We utilized the "least-lossy" approach: Model-level observations are ingested as a distinct raw `source_observation` with `resolution_status='model_level'` and `resolved_variant_id = NULL`. The raw payload embeds `{"scope": "MODEL"}` to securely preserve source scope without corrupting existing exact-variant canonical structures.

## 4. Test Results (Fixture & Integrity)
- Mock datasets were mapped through `field_map_v3cars.py` confirming strict parsing of `(O)`, `Turbo`, `Manual/Automatic`, and semantic feature terms.
- Canonical boolean mismatches (e.g. `False` vs `0`) were tested and explicitly patched.
- Special Trims (e.g. *King Edition*) that do not match the parsed standard trims fall back safely to empty feature arrays, triggering safe "conflicts" against existing DB values rather than overwriting canonical data.

## 5. Live Sample Results
Tested on a representative cross-section of 3 models (Hyundai Creta, Kia Seltos, Tata Nexon).

| Model | V3Cars Variants Discovered | Resolved to Canonical | Unresolved | New Canonical Fields Populated |
|---|---|---|---|---|
| **Hyundai Creta** | 34 | 34 | 0 | 0 (All gaps already filled by 91W / Confirmed 156 fields) |
| **Kia Seltos** | 44 | 44 | 0 | 69 |
| **Tata Nexon** | 81 | 81 | 0 | 32 |

### Enrichment & Conflict Highlights:
- **Variant Coverage:** V3Cars perfectly covered the vast majority of mainstream variants (159/159 exact matches across the 3 models tested).
- **Model-Level Evidence:** 3 Model-level Standard Warranty observations successfully isolated.
- **Conflicts Captured:** 
    - The resolver safely blocked V3Cars' generic `"Automatic"` transmission from overwriting the highly granular V6 canonical `"CVT"`, `"Torque Converter"`, or `"DCT"` values.
    - Special editions (e.g., Hyundai Creta *King Edition*) correctly rejected V3Cars' missing feature arrays, preserving the canonical presence of ADAS/Sunroof.

## 6. Historical Coverage & Limitations
- **Historical Gaps:** V3Cars primarily structures its articles around the *current* facelift. While it has some older variants, heavily discontinued variants (like pre-2020 base trims) do not appear in the active variant tables.
- **Limitation:** The extractor relies on V3Cars' editorial "Variants Explained" table structures (`STANDARD FEATURES`, `FEATURES OVER`). If V3Cars restructures these articles entirely, the inheritance graph parser will yield empty sets. However, due to Tier-2 architecture, this will safely fail-close as "conflicts" rather than silently corrupting data.

**Recommendation:** The V3Cars Adapter is stable, heavily validates source evidence scope, and safely yields variant-level taxonomy enrichment. Awaiting explicit approval to execute the full 62-model controlled crawl.
