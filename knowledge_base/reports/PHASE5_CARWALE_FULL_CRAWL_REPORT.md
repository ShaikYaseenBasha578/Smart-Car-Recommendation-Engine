# Phase 5 CarWale Full Crawl Report (Methodologically Reconciled)

## A. Objective
Execute a final ingest of CarWale to evaluate its capacity to resolve outstanding canonical variants, enrich empty feature arrays, and parse Marketing Editions. This report is strictly reconciled directly from the SQLite database and logs, using mathematically verified metrics.

## B. Crawl Discrepancy & Denominator Reconciliation
To evaluate the CarWale ingestion accurately, the crawler's states must be explicitly distinguished:
- **Discovered Slugs (1,168):** Total variant paths enumerated across 62 model pages.
- **Aborted - DB Lookup (39):** Models failing initial DB lookup due to hyphens in their canonical names (e.g., `Scorpio-N`, `S-Presso`).
- **Failed Parse / Extractor Exception (269):** Variants that were fetched via HTTP but returned `status != SUCCESS` (e.g., complex SUV HTML layouts missing specific tables), thereby safely skipped.
- **Logged DB Source Observations (860):** The precise number of `source_observation` rows successfully extracted, validated, and written to the database.
- **Resolved Observations (753):** Successfully matched to a canonical base variant or established as an Edition.
- **Unresolved Observations (107):** Clean extractions that failed to map to a canonical configuration.

*Reconciliation Constraint:* `1168 Discovered = 39 Aborted + 269 Failed Parse + 860 Logged`. `860 Logged = 753 Resolved + 107 Unresolved`.

## C. Source Coverage Limitations
While 62/62 model pages were attempted successfully, this does **not** mean 62/62 models had complete variant-level CarWale coverage.
Explicitly, **269 of the 1,168 discovered slugs failed extraction/parse** and never became source observations. This resulted in substantial source-level gaps, including major models (e.g., Toyota Fortuner, Toyota Innova Crysta, Maruti Suzuki Eeco, Maruti Suzuki WagonR) having **zero logged observations** in the database. These limitations are transparently documented in the model table.

## D. Canonical Resolution Recovery
We analyzed the exact canonical variant population against Phase 4 V3Cars results.
- **194 canonical variants were resolved by CarWale but had no corresponding resolved V3Cars observation.**
- All 194 variants are active configurations within the V6 canonical baseline. This represents a measured recovery against the comparison population, but does not imply that all 194 were entirely absent from V3Cars' website, nor does it represent historical recovery (as the V6 dataset strictly tracks active vehicles).

## E. Transmission Gap Recovery
We evaluated transmission recovery against a strictly defined canonical comparison population:
- **Total specific-automatic canonical variants unresolved by V3Cars:** 217 (Explicitly defined as `DCT`, `CVT`, `Torque Converter`, `AMT`, `e-CVT`, `iMT`).
- **Resolved by CarWale:** 15 cases subsequently resolved.
- **Remaining Unresolved:** 202 specific-automatic cases remain unresolved across both external sources.

## F. Marketing Editions
The Phase 5 `v_effective_variant` `COALESCE` inheritance logic evaluated ingested packages against base variants.
- **Total Editions Initialized:** 20
- **NO_MATERIAL_DIFFERENCE:** 4. (No verified structured difference was identified in the fields evaluated).
- **FEATURE_OR_SPEC_DIFFERENCE:** 16. (Source-extracted values differed from the inherited base configuration for one or more evaluated fields, resulting in 39 distinct field overrides captured).

## G. Field-Level Enrichment (Base Variants)
Calculated by asserting that `decision = 'new_field'` strictly implies a pre-crawl `NULL` state.
| Field | Pre-Null | Post-Null | Newly Populated | Confirmed | Rejected | Edition Overrides |
|---|---|---|---|---|---|---|
| **cruise_control** | 225 | 189 | 36 | 194 | 104 | 6 |
| **heads_up_display** | 241 | 235 | 6 | 45 | 15 | 5 |
| **boot_space_litres**| 41 | 41 | 0 | 165 | 588 | 14 |
| **transmission** | 0 | 0 | 0 | 724 | 29 | 0 |
| **sunroof** | 1 | 1 | 0 | 583 | 163 | 7 |

*(Note: Total Confirmations across all fields: 3,561. Total Accepted New Fields: 45. Total Rejected: 1,027. Total Edition Overrides: 39)*

## H. Pricing Refresh
- **Active Records Pricing Refreshed:** 0
- **Status:** FAILED / UNIMPLEMENTED
- **Explanation:** The `ingest_carwale.py` payload utilized the key `price`, whereas the schema strictly requires `price_ex_showroom`. The SQLite row-mapping logic safely skipped the unmapped key, performing zero updates. Pricing refresh was therefore a failed objective in Phase 5.

## I. Conflict Statistics & Unresolved Observations
- **Conflicts Rejected:** 1,027 fields. CarWale frequently clashed with the Canonical V6 authority (notably: 588 rejections on `boot_space_litres` and 163 on `sunroof`), showing limited incremental coverage for the tested dimension fields. 
- **Unresolved Observations:** The 107 unresolved logged observations represent a mix of causes: canonical configurations absent from the V6 baseline, identity resolution failures due to differing nomenclatures, or insufficient extracted data to meet the bounds tests.

## J. Database Integrity & Idempotency
- **Base Variants Pre-Crawl:** 812
- **Base Variants Post-Crawl:** 812
- **Integrity Status:** Passed implemented integrity checks. No unexpected base-variant mutations were detected.
- **Idempotency Verification:** The orchestrator artificially re-injected three models into the batch state. The SQL `UNIQUE` constraints intercepted the collisions, resulting in exactly **0 additional source observations, 0 additional provenance rows, 0 additional editions, and 0 canonical field updates**.

## K. Conclusions
CarWale was valuable as a secondary structured source because it:
- Resolved 753 of 860 logged observations.
- Provided 45 new base-field populations.
- Represented 20 marketing editions.
- Recovered 194 canonical variants that had no resolved V3Cars observation.
- Resolved 15 previously unresolved specific-automatic canonical cases.

**Limitations:**
- 269 discovered slugs failed before becoming observations.
- 107 logged observations remained unresolved.
- Pricing was not refreshed.
- Substantial exact-transmission and historical/canonical coverage limitations remain.
- CarWale should remain a production enrichment source, but it is **not** the sole source of truth.

## L. Recommendation for Phase 6
Proceed to the research/recommendation-engine design phase, while treating the remaining structured-data gaps as explicit KB limitations. Authoritative OEM/RTO enrichment can be added later where those gaps materially affect the recommender.

---
### Appendix: Reconciled 62-Model Audit Table
See `final_model_table3_corrected.md` for exact DB-reconciled metrics per model.
