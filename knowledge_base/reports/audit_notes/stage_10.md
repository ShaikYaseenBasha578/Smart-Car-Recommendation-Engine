# Stage 10 — Future-layer integration points (≤1 page, no schema design)

## Where new layers attach
- **Source registry (`source`)**: each review outlet / owner-report channel becomes a `source` row with its own `source_type` (e.g. `professional_review`, `owner_report`). `authority_tier` must not be reused across evidence classes — tier ordering only makes sense *within* a class (and today the code ignores the table value anyway).
- **Acquisition + raw evidence (`source_observation`)**: a review article or owner post is an observation (raw payload, URL, fetch time, artifact + checksum as BNCAP does). Resolution status must use one normalised vocabulary (today: 3 case/semantic variants).
- **Entity scope**: like `safety_test_applicability`, reviews/owner reports attach to an explicit scope (manufacturer/model/generation/variant/powertrain) with an explicit confidence level; never forced to variant. Needs real generations first (all 62 are placeholders).
- **Assessment tables (new, separate)**: Professional Review → review → evidence (quoted claim, section) → assessment (normalised dimension, polarity, reviewer). Owner Experience → report → evidence → aggregate. These are **separate from** `field_provenance`, which should remain the ledger for canonical *fact* columns only.

## Semantic separation that must hold
| Class | Lives in | May update canonical `variant`/`powertrain`? |
|---|---|---|
| OEM_FACT (spec sheets, brochures, price lists) | variant/powertrain + field_provenance (source 6, tier 1) | yes, via authority rules |
| SAFETY_TEST_RESULT | safety_test + applicability | never |
| PROFESSIONAL_ASSESSMENT | new review/assessment tables | never |
| OWNER_REPORT | new owner tables | never |
| DERIVED_VALUE (edition inheritance, coverage %, scores, recommender weights) | views / recommender, labelled derived | never written back |
Current violations to fix before layering: OEM facts stored under the v6_migration source (indistinguishable from CSV migration); V3Cars "not mentioned" written as fact `0`; `v_effective_variant` presents inherited edition values without a derived flag; legacy `safety_rating` asserts ratings without evidence chain.

Checksum gate: `1e3eb679…` ✔
