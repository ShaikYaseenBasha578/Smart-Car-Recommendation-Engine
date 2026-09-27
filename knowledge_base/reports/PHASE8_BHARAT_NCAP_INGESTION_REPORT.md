# PHASE 8 — BHARAT NCAP SAFETY KNOWLEDGE INGESTION REPORT

> **Status:** SHADOW AUDIT COMPLETE  
> **Production DB Status:** UNTOUCHED (Checksum verified before and after)  
> **Production Checksum:** `e752ebde5b7f227140bedb319c6b9753a3fdbdde`

---

## 1. SOURCE AUDIT & DISCOVERY

A direct inspection of the official Bharat NCAP portal (`https://www.bncap.in/vehicle-safety-ratings/`) was performed.

### Findings:
- BNCAP maintains an official directory of all tested vehicles.
- There is **no structured API** available to the public. 
- Results are published as HTML detail pages containing embedded PDF "Factsheets".
- **Total Published Tests Found:** 37
- **Data Structure:**
  - `tested_vehicle_name` (e.g., "TATA SAFARI/ HARRIER")
  - `test_period` (e.g., "Dec 2023 - Onwards")
  - `aop_score` (Adult Occupant Protection out of 32)
  - `cop_score` (Child Occupant Protection out of 49)
  - `factsheet_url` (Direct link to the official PDF report)

> [!CAUTION]
> The HTML representation of the Star Rating uses embedded CSS icons (`icon-star-1`) without semantic tags, making it highly fragile to scrape directly. We extract raw AOP/COP scores instead, which are mathematically reliable, while maintaining the Factsheet PDF URL as the absolute source of truth.

---

## 2. SEPARATE SAFETY EVIDENCE MODEL

To maintain the distinction between "generic equipment claims" and "crash test evidence", a new relational layer was designed. 

**Schema Additions (Shadow DB only):**
```sql
CREATE TABLE safety_test (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES source(id),
    tested_vehicle_name TEXT,
    test_period TEXT,
    aop_score REAL,
    cop_score REAL,
    stars INTEGER,
    factsheet_url TEXT,
    raw_source_url TEXT UNIQUE,
    resolution_status TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE safety_test_applicability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    safety_test_id INTEGER REFERENCES safety_test(id),
    manufacturer_id INTEGER REFERENCES manufacturer(id),
    model_id INTEGER REFERENCES model(id),
    generation_id INTEGER REFERENCES generation(id),
    variant_id INTEGER REFERENCES variant(id),
    match_confidence TEXT, 
    notes TEXT,
    UNIQUE(safety_test_id, variant_id)
);
```
> [!TIP]
> This schema ensures that one test (e.g., "Tata Safari / Harrier") can explicitly map to multiple specific models or variants without mutating generic variant table columns.

---

## 3. ENTITY RESOLUTION & APPLICABILITY

We employed a strict, conservative resolution engine.

- **`RESOLVED`**: The test maps unambiguously to a known CarRec Model (e.g., Tata Nexon).
- **`NO_MATCH`**: The test is for a vehicle not currently in the CarRec top-62 (e.g., Citroen Basalt, VinFast VF7).
- **`UNRESOLVED`**: The vehicle exists in the market but naming ambiguity prevented automatic matching (quarantined for manual review).

### Applicability Rule Enforcement
The current mapper assigns a `match_confidence` of `MODEL_LEVEL` to resolved tests. This correctly flags that while the test belongs to the model (e.g., Tata Nexon), BNCAP does not guarantee it applies to *all* variants (e.g., EV vs ICE). The `safety_test_applicability` table allows us to progressively narrow this to `EXACT_VARIANT` via Phase 8.1 manual/PDF corroboration if needed, without data loss.

---

## 4. SHADOW INGESTION RESULTS

A full end-to-end ingestion was run against `scratch/carrec_kb_phase8_shadow.db`.

### Document & Parse Inventory
- **Tests Discovered:** 37
- **Tests Acquired & Parsed:** 37
- **Parse Failures:** 0

### Resolution Status
- **`RESOLVED`**: 25 tests mapped to CarRec models
- **`NO_MATCH`**: 9 tests (Citroen, VinFast, future models)
- **`UNRESOLVED`**: 3 tests (Ambiguous naming)

### Applicability Scope
- **Variants Mapped (`MODEL_LEVEL`):** 448
- **`EXACT_VARIANT` mappings:** 0 (Intentionally deferred to prevent false propagation)

---

## 5. DATA INTEGRITY AUDIT (LOGICAL DIFF)

Pre and Post counts of the standard production tables were taken to ensure no unintended mutations occurred during the safety ingestion.

| Table | Pre-Ingestion | Post-Ingestion | Diff |
|---|---|---|---|
| manufacturer | 12 | 12 | **0** |
| model | 62 | 62 | **0** |
| generation | 62 | 62 | **0** |
| variant | 832 | 832 | **0** |
| powertrain | 131 | 131 | **0** |
| source_observation | 3,414 | 3,414 | **0** |
| field_provenance | 36,445 | 36,445 | **0** |
| **safety_test** | **0** | **37** | **+37** |
| **safety_test_applicability** | **0** | **448** | **+448** |

**Verdict:** PERFECT ISOLATION. No generic tables were mutated.

---

## 6. IDEMPOTENCY

Pass 2 of the ingestion script was executed immediately after Pass 1 against the same shadow database.

**Pass 2 Results:**
- `safety_test`: +0 rows
- `safety_test_applicability`: +0 rows
- Parse errors: 0

**Verdict:** TRUE LOGICAL IDEMPOTENCY CONFIRMED. The ingestion relies on `raw_source_url` as the unique identity key.

---

## 7. RECOMMENDATION CONSUMPTION PREPARATION

Future recommendation logic will consume this layer via JOINs, not by checking variant booleans.

**Query Intent:** *"I want a safe car"*
1. Engine looks up `variant.model_id` in `safety_test_applicability`.
2. Yields linked `safety_test_id`.
3. Checks `aop_score` and `cop_score`.
4. Returns result *alongside* the `match_confidence` (e.g., "Tata Nexon scored 32.22/32 AOP. *Note: Test applies at the Model Level*").
5. If no record exists, returns "Not Tested by Bharat NCAP" rather than "Unsafe".

---

## 8. PRODUCTION GATE VERDICT

All required pre-flight conditions have been met:
✅ Official-source acquisition proven
✅ Test identity and Factsheet URLs preserved
✅ Applicability is explicitly tracked (`MODEL_LEVEL`)
✅ Entity resolution is conservative (Unresolved are quarantined)
✅ Provenance is complete (Linked to Source ID 7)
✅ Logical Diff confirmed 0 mutations to standard tables
✅ Pass-2 Idempotency succeeded

**Final Verdict:** 
`READY_FOR_BHARAT_NCAP_PRODUCTION`

---

## EXECUTIVE SUMMARY

1. **How many Bharat NCAP tests were found?** 37 tests.
2. **How many were successfully resolved to CarRec entities?** 25 tests resolved to known models.
3. **How many remain ambiguous/unresolved?** 3 ambiguous, 9 un-matched (future/absent brands).
4. **How many have exact variant applicability?** 0. The current pass mapped at the model level to prevent false-positive propagation.
5. **How many are only model/generation-level?** All 25 resolved tests were mapped as `MODEL_LEVEL`.
6. **What safety info can the future recommender reliably use?** AOP scores, COP scores, applicable periods, and the official Factsheet PDF.
7. **What remains unsupported?** Exact trim-level exclusions (e.g., if a base variant lacks 6 airbags, does the 5-star rating still apply?). This requires manual parsing of the Factsheet PDFs.
8. **Is the system ready for production?** YES. The shadow run proves the schema and ingestion are safe and idempotent.

*(See `scratch/phase8_bharat_ncap_coverage.csv` for the detailed model-by-model mapping).*
