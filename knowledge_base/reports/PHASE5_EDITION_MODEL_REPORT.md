# Phase 5 Edition Model Architecture Report

## Why Editions Cannot Safely Be Treated As Aliases By Default
Marketed editions (e.g., "Dark Edition", "Knight Edition") are not necessarily identical to their base variants. 
If an edition is collapsed into the base variant as an alias without verification, any unique features belonging *only* to the edition (if extracted from source evidence) would overwrite the canonical truth of the base variant.

## Why Editions Should Not Automatically Become Independent Technical Variants
Conversely, creating a tier-1 technical variant for every cosmetic marketing package is an unverified assumption.
An edition frequently retains the identical mechanical, dimensional, and specification truth of the standard variant. Duplicating these fields structurally creates redundancy and complicates future updates.

## Architecture: Distinguishing Base Variants from Editions
We implemented a self-referencing hierarchy within the core `variant` table:
*   `base_variant_id INTEGER REFERENCES variant(id)`
*   `edition_classification TEXT` 

If `base_variant_id` is NULL, the record serves as a base variant. 
If `base_variant_id` is populated, the record serves as an edition derived from that base variant.

## How Inheritance and Overrides Work
To support inheritance without EAV modeling, we utilize SQLite `COALESCE`.
When an edition is created, its core feature columns are initialized as `NULL`. 
During ingestion, the edition receives updates *only* for the fields explicitly extracted from the source observation.
A new view, `v_effective_variant`, executes a projection:
`COALESCE(v.sunroof, bv.sunroof) AS sunroof`
This ensures missing fields gracefully fall back to the base variant's truth, while explicit edition overrides (including explicit `0`/`False` states) take precedence.

## How Provenance Works
Because editions are strictly rows in the `variant` table, the existing `field_provenance` ledger functions natively. 
If an observation asserts a value for a specific edition, that value is written to the edition row, and a provenance record is stamped against the edition's `variant_id`. The base variant remains entirely isolated from this evidence.

## Historical Editions
Because editions are stored alongside base variants, they natively support the `is_discontinued` boolean flag. Historical editions can be mapped and retained permanently.

## Future Context
*   **Recommendation Engine:** The research algorithm can choose to query the base variants to evaluate broad technical choices, or query `v_effective_variant` to evaluate granular trims. 
*   **Live Website:** The website can query `v_effective_variant` to display the marketed configurations along with their exact feature differences (where supported by source evidence).
*   **Complexity:** The architecture avoids complex ontologies (EAV, separate override tables) to remain manageable for the GitHub repository and research paper.

## Reassessment of Tata Harrier CarWale Failures
In the initial pilot, several Harrier variants were rejected. 
Following the architecture upgrade, these were re-tested.
1.  **Editions Successfully Classified:** Suffix keywords (`Dark Edition`) were used strictly as string-splitting heuristics by `resolver.py`. Upon successful matching of the underlying base variant, the records were ingested as `edition_candidates`.
2.  **Evidence-Based Classification:** The `updater.py` evaluated the extracted payload against the canonical base variant. If overrides were written, the edition was automatically classified as `FEATURE_OR_SPEC_DIFFERENCE`. If no differences were found, it was classified as `NO_MATERIAL_DIFFERENCE`.

## Conclusion
The KB now possesses the architectural model required to distinguish canonical base variants from cosmetic or feature-altered editions without hallucination or base-data corruption. 

**Note: This report does not recommend an immediate full crawl. The architecture and findings must be reviewed before proceeding.**
