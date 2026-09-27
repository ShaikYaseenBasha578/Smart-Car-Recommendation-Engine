# Stage 6 — Safety architecture

## Two layers [VERIFIED schema + rows]
| | `safety_rating` (legacy) | `safety_test` + `safety_test_applicability` |
|---|---|---|
| Rows | 27 (24 Global NCAP 2019–2024, 3 Bharat NCAP 2024: Nexon, Nexon EV, Punch EV) | 37 tests, 23 applicability rows |
| Granularity | one summary per (model, body, year); adult/child stars | one row per published test; AOP/COP score + stars, protocol, weight, SAT text, test period |
| Link to model | model_id NOT NULL + generation_id | via applicability: MODEL_LEVEL (22) / FAMILY_LEVEL (1); variant_id NULL on all 23 |
| Provenance | `source_url` only; no source_id, no observation, no artifact | `source_observation_id` (source 7, raw payload), `raw_source_url` UNIQUE, `artifact_path`, `artifact_checksum` |
| Unresolved representation | none (only resolved rows exist) | `safety_test.resolution_status` ∈ {RESOLVED 23, UNRESOLVED 4, NO_MATCH 10}; unresolved/no-match tests have 0 applicability rows |
Semantics: `safety_rating` = asserted fact about a model with no evidence chain. `safety_test` = a SAFETY_TEST_RESULT about a tested configuration; applicability is a separate, explicitly scoped claim ("this result is relevant to model X"), never a variant attribute.

## Artifacts [VERIFIED]
- All 37 `artifact_path` values point to `scratch/bncap_pdfs/*.pdf` (relative path, untracked scratch dir). Recomputed SHA-256 for all 37: **37 match, 0 mismatch, 0 missing, 0 NULL**. (Script: /tmp/carrec_audit, `hashlib.sha256` over file bytes vs `artifact_checksum`.)
- Risk: production evidence lives in `scratch/` (name implies disposable), not in git, relative to repo root.

## Applicability semantics observed [VERIFIED]
- MODEL_LEVEL rows: generation_id populated for 15, NULL for 7 (Baleno×2, Kylaq, Nexon EV, Punch EV×2) — no documented rule. FAMILY_LEVEL (Safari/Harrier test 33 → Harrier only), gen NULL.
- Since every generation is the placeholder "Gen 1 (V6 Import)", a populated generation_id adds no information.
- Multiple tests per model without temporal disambiguation: Baleno (2 AB vs 6 AB, tests 14/15), Punch EV (2024 test 31 vs 2026 test 30), Harrier (test 27 MODEL_LEVEL + test 33 FAMILY_LEVEL).
  - **Confirmed mis-resolution:** test 27 "TATA – HARRIER.EV" (config "EMP 75 & EMP 75 AWD", justification "Matched manufacturer and model systematically.") is mapped MODEL_LEVEL to model 30 "Harrier", whose 26 variants are all Diesel (14) / Petrol (12) — no EV exists in the KB. An EV crash test is therefore applied to an ICE-only model [VERIFIED]. Per the KB's own rules this should have been NO_MATCH (Harrier.EV not in top-62). Not flagged by PHASE8B/9/9A.
- Phase 9B additions verified exactly: tests 9/16/17 → models 54/7/13, gens 22/24/28, MODEL_LEVEL, variant NULL.
- Status drift: obs 3729/3736/3737 still UNRESOLVED in `source_observation` (see stage 5).
- Overlap: the 3 BNCAP `safety_rating` rows duplicate tests 28/29/31 with equal star values (5/5) [VERIFIED]; Punch EV has 2 BNCAP tests but 1 legacy row.
- PHASE8B_FINAL_GATE §7 "Quarantined (UNRESOLVED): 3" vs PHASE8B ingestion report "UNRESOLVED 7" → [CONTRADICTED] within Phase 8B documents (DB pre-9B had 7) [VERIFIED via 9B backup].
- Star extraction relies on the **order** of two schema.org `ratingValue` elements (first=AOP, second=COP) [REPORTED-ONLY: PHASE8B_FINAL_GATE §1] — positional parsing risk.

## Global NCAP migration — what it would require (analysis only)
1. Acquire each of the 24 `source_url` PDFs; store under a durable artifact path (not scratch/), SHA-256, record fetch date.
2. Create 24 `source_observation` rows under source 8 with the raw extracted payload.
3. Extract per-PDF: protocol (pre-2022 "Safer Cars for India" vs 2022+ protocol — stars **not comparable** across protocols or with BNCAP), adult/child points, stars, tested config (airbag count), test year/period.
4. Insert `safety_test` rows with `resolution_status`; applicability at MODEL_LEVEL only; mark generation unknown unless a real generation exists (many GNCAP tests predate current generations — e.g. Creta 2022 test vs current facelift).
5. Keep `safety_rating` frozen; exclude the 3 BNCAP rows; decide deprecation only after consumers move.
6. Needs a protocol/comparability field or rule before any recommender scoring mixes agencies.
(PHASE9A §11 proposes the same path [REPORTED-ONLY]; its claim "no entity resolution step is needed" is too strong — temporal/generation applicability is unresolved.)

Checksum gate: `1e3eb679…` ✔
