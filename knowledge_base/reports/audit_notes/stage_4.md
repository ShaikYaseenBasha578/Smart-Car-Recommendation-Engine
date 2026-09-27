# Stage 4 — Canonical model & entity resolution

## Hierarchy (production copy) [VERIFIED]
manufacturer(12) → model(62) → generation(62, exactly 1 per model, all named "Gen 1 (V6 Import)", all `verification_status='unverified'`) → variant(832) → powertrain(131, owned by model, shared by variants).
- Every variant has generation and powertrain; 0 cross-model mismatches (variant.pt.model = variant.model; variant.gen.model = variant.model).
- `is_discontinued = 0` for all 832 → the discontinued mechanism is unused.
- Editions: 20 variants (ids 814–833, created by CarWale crawl 2026-09-09) have `base_variant_id` + `edition_classification` (16 FEATURE_OR_SPEC_DIFFERENCE, 4 NO_MATERIAL_DIFFERENCE). They hold NULL price/dimensions and inherit via `v_effective_variant`. Base chains are depth 1.
- **The generation layer is a placeholder**: any "generation-level" statement (e.g. safety applicability gen 22/24/28) currently means "the model", not a verified generation.

## Ambiguity points
1. Generation unknown for every model (placeholder) → cannot distinguish facelifts/generations (e.g. BNCAP Punch.ev 2024 vs 2026 tests both map to model 59). [VERIFIED]
2. Model identity by slug equality `lower(replace(name,' ','-'))` only — no manufacturer/model alias table (resolver.py:88-95) [REPORTED-ONLY (subagent)]. BNCAP resolution separately used substring matching of titles (caused the Thar/Thar Roxx and "MARUTI" failures) [REPORTED-ONLY: PHASE9A §7].
3. Alias lookup defaults to the **91wheels** alias table when a caller passes no `source_name` — CarWale and V3Cars do this, so their slugs resolve through another source's aliases [VERIFIED resolver.py:124-129].
4. `needs_review=1` aliases still return `resolved_with_warning`, which the updater treats as applicable [VERIFIED resolver.py:142-143; updater.py:45]. 189 of 469 aliases have needs_review=1; 0 are verified [VERIFIED query].
5. Fuzzy match threshold >0.5 with a 0.05 margin; ties → unresolved (no AMBIGUOUS state) [VERIFIED resolver.py:207-212]. Exact match takes first DB-order hit, no duplicate check [REPORTED-ONLY (subagent)].
6. Edition creation: resolver `edition_candidate` → updater clones the base row and names the edition from the source string. Production editions have **malformed identities** [VERIFIED]:
   - variant 833 name "Anniversary Edition Petrol 1.5L Turbo Automatic (DCT)" but powertrain = 999cc 114 bhp, transmission = Torque Converter (inherited from base 643 "Topline 1.0L TC").
   - variant 814 "ZX Petrol Manual Black Edition" with base 649 "VX Petrol Manual" (trim mismatch); 826 "Alpha Plus … Smart Hybrid" with base 218 "Alpha MT".
   - `full_name` = base full_name + edition name concatenated (e.g. "Honda Elevate VX Petrol Manual ZX Petrol Manual Black Edition").
7. Powertrain fields updated on the shared powertrain row affect all variants on it, with provenance recorded on only one variant [REPORTED-ONLY (subagent): updater.py:215; UPDATE statement VERIFIED].
8. OEM brochure observations: `raw_name` values like "V O O", "SV - - -" (column markers), constant `source_url='offline_brochure'`, dedup key (source_id,url,raw_name) → same trim name in another model/config is silently dropped [VERIFIED updater.py:32-37, ingest_oem.py:40; observed raw_names in DB].
9. BNCAP applicability: generation_id set for some MODEL_LEVEL rows, NULL for others (Baleno×2, Kylaq, Nexon EV, Punch EV×2, Harrier FAMILY) — inconsistent semantics [VERIFIED].

## Resolution mechanisms (file:line)
- `knowledge_base/ingestion/common/resolver.py:86-250` `resolve_variant` (model slug → alias → structural validation `validate_structured` :59-75 → exact → fuzzy → edition fallback >0.6 :247).
- `knowledge_base/ingestion/oem/ingest_oem.py:49-84` `resolve_oem_generation` (fail-closed on 0 / >1 generation) [REPORTED-ONLY (subagent)].
- BNCAP: `BNCAP_ALIAS_TABLE` in scratch/phase8a_shadow_ingestion_v4.py / phase8b_prod_ingestion.py (url_slug keyed) [REPORTED-ONLY: PHASE8B_FINAL_GATE §4]; Phase 9B manual url_slug + body_type resolution — script not on disk.
- `migrate_v6.py` alias seeding: needs_review if score <0.85 or fuel mismatch [REPORTED-ONLY (subagent)].

Checksum gate: `1e3eb679…` ✔
