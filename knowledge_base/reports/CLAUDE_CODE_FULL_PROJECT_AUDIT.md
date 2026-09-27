# CarRec — Full Project Forensic Audit (Claude Code, 2026-09-27)

**Mode:** forensic, read-only. Nothing in the repo was implemented, fixed, run, or committed. Every DB query ran on byte-identical copies in `/tmp/carrec_audit/`.
**Production DB:** `knowledge_base/carrec_kb.db`. SHA-1 at start `1e3eb6795452860276eca24e7dd1f52e85e67a93`; SHA-1 at every stage gate and at the end: the same value.
**Evidence tags:** [VERIFIED] (query, file:line, or hash), [REPORTED-ONLY] (a prior report, a subagent, or the brief), [CONTRADICTED] (evidence disagrees with a prior claim), INFERENCE (my own reasoning, not proven).
**Stage notes** with full evidence are in `knowledge_base/reports/audit_notes/stage_0.md` … `stage_10.md`. The script risk table is in `CLAUDE_CODE_SCRIPT_SAFETY_MAP.md`.

---

## 1. Overview
CarRec has two systems that are not connected to each other:
- **The Flask recommender.** It runs on a static 2025 CSV of 1,265 rows. [VERIFIED]
- **The SQLite knowledge base (KB).** It has a provenance model: 12 manufacturers, 62 models, 62 generations, 832 variants and 131 powertrains, plus 3,451 observations, 36,445 provenance rows and a Bharat NCAP safety layer. [VERIFIED]

The KB was built in phases 1–9B (2026-09-08 → 09-26) by Antigravity and ChatGPT-driven agents. None of the KB work is in git: the code, schema, reports, backups and evidence artifacts are all untracked. [VERIFIED]

What holds up:
- The KB's claimed canonical counts are correct.
- The Phase 8B and Phase 9B deltas are exactly what their reports say.
- All 37 BNCAP PDF checksums are valid.
- `integrity_check` returns `ok`.

What is wrong:
- Source attribution for OEM data is wrong.
- Some safety applicability is wrong.
- Some edition identities are malformed.
- One absent-means-zero pipeline wrote 285 facts that no source actually stated.
- History can only be reconstructed from backups and file timestamps. At least one production revert (Phase 8) is recorded nowhere.

## 2. Repo architecture
Repo root: `Flask Based App with Used Cars Function/`. Directory classes are in stage_1.
- **Tracked in git (244 files):** the Flask app, `ml_parser/`, `car_recommendation_assets/`, and the older `scraping/` + `datasets/` pipeline. `scraping/`, `datasets/` and `README.md` are **deleted in the working tree**: 97 tracked files are deleted and not committed. [VERIFIED]
- **Untracked, not ignored:** `knowledge_base/` (except `carrec_kb.db`, which is ignored by `knowledge_base/.gitignore:1`), `scratch/` (330 `.py` files, 18 DBs, the BNCAP PDFs), about 74 root-level `fix_*`/`patch_*`/`rewrite_*`/`forensic_*` scripts, `KB_SCHEMA.sql`, and `graphify-out/`. [VERIFIED `git check-ignore -v`, `git status --ignored`]
- **Prior-agent artifacts:** `../AGENTS.md` and `knowledge_base/reports/AGENTS.md` (the "Ponytail" minimal-diff coding style, which has **no DB rules**), `.agents/*/graphify.md`, and `.agent`/`.gemini` "impeccable" UI skills. [VERIFIED]

## 3. Production architecture
- The KB is a SQLite file in WAL mode, written by Python ingestion code (`knowledge_base/ingestion/*`) and by scripts in `scratch/`. [VERIFIED]
- The KB has no consumer in the app. [VERIFIED: grep]
- Production evidence artifacts live in `scratch/bncap_pdfs/` (37 PDFs) and `knowledge_base/sources/oem/` (67 PDFs). [VERIFIED]
- At the start of this audit, DB Browser for SQLite had production open read-write with a 6-frame WAL. After it was closed, the main file's hash was unchanged. [VERIFIED]

## 4. Schema map
The full detail is in stage_3. [VERIFIED]
- **Objects:** 13 tables plus `sqlite_sequence`, 2 views, 25 indexes, **0 triggers, 0 CHECK constraints**, no `ON DELETE` actions.
- **Hierarchy:** `manufacturer` → `model` → `generation`; `model` → `powertrain`; `variant` references model, generation, powertrain and `base_variant_id`.
- **Evidence:** `source`, `source_observation`, `field_provenance`, `variant_alias`.
- **Safety:** `safety_rating` (legacy), `safety_test`, `safety_test_applicability`. There is also a `warranty` table.
- **UNIQUE constraints that nullable columns weaken:** `variant(model_id, name, generation_id)`, `powertrain(…, engine_cc, power_bhp)`, `safety_test_applicability(…, model_id, …)`.
- **`source_observation` has no UNIQUE constraint.**
- **Drift from the documented schema:** `KB_SCHEMA.sql` lacks `safety_test*`, `base_variant_id`, `edition_classification` and `v_effective_variant`. There is no schema version table.
- **Foreign keys are not enforced.** Only `KB_SCHEMA.sql:3` and `scratch/phase8_production_ingestion.py:51` turn `PRAGMA foreign_keys` on.

## 5. Data lifecycle
The full timeline is in stage_2.

The stages run in this order:
1. V6 CSV migration (June).
2. 91wheels crawl (09-09).
3. V3Cars crawl (09-09), including one clean deletion of an earlier attempt.
4. CarWale pilot, then an ad-hoc deletion that left **297 orphans**.
5. The backup named "pre_phase5_carwale". [CONTRADICTED: it already contains the orphans]
6. CarWale full crawl, which created 20 edition variants.
7. OEM production attempt 1 (09-12). It was restored manually.
8. Controlled OEM run (09-13). Hash `e752ebde`.
9. Phase 8 BNCAP production (324 applicability rows, hash `6cc95a6e`). It was **reverted, and no document records the revert**.
10. Phase 8B (hash `c1e0647c`).
11. Phase 9B (hash `1e3eb679`).

[VERIFIED hashes and counts on copies. Ordering by mtime. The causes of the restores and reverts are INFERENCE.]

## 6. Provenance
- **Model:** one `source_observation` per source record, and one `field_provenance` row per (variant, field, observation) decision (accepted / confirmed / rejected). [VERIFIED]
- **Positive invariants:** every variant has provenance; no provenance row points at a different variant than its observation; no provenance comes from an unresolved observation. [VERIFIED]
- **297 orphaned provenance rows** point to observation IDs 2608–2661 (Creta 80, Harrier 109, Kushaq 76, Verna 32). [VERIFIED]
  - The 6 `accepted` orphans are on Harrier variants 441, 442 and 452. PHASE9A says they are all on 452. [CONTRADICTED] A live `confirmed` row corroborates each of them. [VERIFIED]
  - 6 `confirmed` orphans on `transmission` have no live support. [VERIFIED]
- **`transmission` has no `accepted` provenance anywhere.** It came from the V6 CSV without a provenance row. [VERIFIED]
- The rows carrying reason `conflict_with_canonical_authority` (2,426) were written by an updater version that no longer exists. [VERIFIED by grep]
- **Recommendation (not done):** keep the orphans immutable. Record the anomaly in a side table rather than by mutating `decision_reason`. Always read provenance with a `LEFT JOIN`, and treat a missing observation as "evidence unavailable". Enable foreign keys for every writer.

## 7. Safety
The full detail is in stage_6.

**Two layers:**
- `safety_rating`: 24 Global NCAP rows plus 3 Bharat NCAP rows. Model-level assertions with no evidence chain.
- `safety_test` (37) + `safety_test_applicability` (23): an evidence-backed layer that links to source 7 observations and to checksummed PDFs.

**What checks out:**
- All 37 SHA-256 checksums match. [VERIFIED]
- All 23 applicability rows have `variant_id` NULL. [VERIFIED]

**Findings:**
- **Test 27 "TATA – HARRIER.EV" is mapped MODEL_LEVEL to model 30 "Harrier", which has only Diesel and Petrol variants.** [VERIFIED: confirmed bug]
- `generation_id` is set on 15 MODEL_LEVEL rows and NULL on 7, with no rule. Every generation is a placeholder anyway. [VERIFIED]
- Phase 9B left 3 `source_observation` statuses at UNRESOLVED while the matching tests are RESOLVED. [VERIFIED]

**Global NCAP migration** would require:
- acquiring and checksumming the PDFs into a durable location;
- source 8 observations;
- extracting the protocol, because pre-2022 and later protocols are not comparable, and neither is comparable to BNCAP;
- MODEL_LEVEL applicability with the generation marked unknown;
- keeping `safety_rating` frozen.

This is analysis only.

## 8. Ingestion pipelines
The full detail is in stage_5.

| Source | Status in prod | Key defects |
|---|---|---|
| V6 migration | 812 obs, 24,955 accepted | Single CSV origin for all price, dimension and airbag values |
| 91wheels | 845 obs | Package cannot run now [REPORTED-ONLY (subagent)]; 125 accepted `0`s [VERIFIED] |
| V3Cars | 845 obs | Absent → 0 (`field_map_v3cars.py:24`), status forced to `resolved` (`ingest_v3cars.py:104`); **285 accepted `0` facts** [VERIFIED] |
| CarWale | 860 obs, 20 editions | Resolves through 91wheels aliases (`resolver.py:124-129`); E/EX swap (obs 2842/2843); edition variant 820 absorbs 33 observations of other configs [VERIFIED] |
| OEM brochures | 52 obs, **under source_id 1** | `batch_runner_oem.py:141` / `production_ingestion_controlled.py:149` → tier 5 not tier 1; constant URL `offline_brochure` gives lossy dedup; junk `raw_name`s ("V O O") [VERIFIED] |
| BNCAP | 37 obs, 37 tests | The Phase 8 script commits before its invariant checks; the 8B script creates no backup and does no restore; resolution used substring matching [VERIFIED] |

- **Fail-closed behaviour:** resolver margin 0.05; edition fallback threshold >0.6; OEM generation lookup must return exactly one; `needs_review` aliases are still applied as `resolved_with_warning` (`resolver.py:142-143`, `updater.py:45`). [VERIFIED]
- **Idempotency:** observations are deduplicated on (source_id, source_url, raw_name) only. The updater has no transaction of its own. [VERIFIED]

## 9. Entity resolution
The full detail is in stage_4.
- **Model lookup** is exact slug match only; there is no model alias.
- **Variant lookup** runs, in order: source alias (defaulting to 91wheels), structural validation (fuel, transmission, cc ±50, price ±₹3 L), exact match, fuzzy match >0.5 with a margin, then an edition fallback that creates new variants.
- **The generation layer is entirely placeholder.** Each of the 62 generations is "Gen 1 (V6 Import)", unverified. [VERIFIED]
- **Edition identities are malformed:**
  - Variant 833 is named "…1.5L Turbo Automatic (DCT)" but sits on the 1.0 TC powertrain.
  - Variants 814 and 826 have a base variant with a different trim.
  - `full_name` values are concatenations of two names.

  [VERIFIED]

## 10. Script risk summary
See `CLAUDE_CODE_SCRIPT_SAFETY_MAP.md`.
- **Scripts that delete production rows:** `run_mini_pilot.py` (prov, obs, all editions) and `test_debug.py`.
- **Can overwrite production with an old backup:** `scratch/production_ingestion_controlled.py:236,338`.
- **Rebuilds the DB:** `migrate_v6.py`.
- **Changes the schema:** `migrate_editions.py`.
- **Opens production during tests:** `pytest` from the repo root.
- **Open production read-write:** almost every "read-only" script.
- **Rewrite untracked code with no undo:** the source-rewriting `fix_*`/`patch_*` scripts.
- **Phase 9A/9B scripts are missing from disk.**

[VERIFIED for the cited lines]

## 11. Current production state
[VERIFIED]

| Table | Rows |
|---|---|
| manufacturer | 12 |
| model | 62 |
| generation | 62 |
| powertrain | 131 |
| variant | 832 |
| variant_alias | 469 |
| source | 8 |
| source_observation | 3,451 |
| field_provenance | 36,445 |
| safety_rating | 27 |
| safety_test | 37 |
| safety_test_applicability | 23 |
| warranty | 18 |

- **Deleted IDs implied by `sqlite_sequence`:** variant 1, observation 306, provenance 874.
- **Phase 9B diff against its backup:** exactly 3 `safety_test` rows modified (status and justification only), 3 applicability rows added, and the sequence bump. Nothing else changed.

## 12. Data quality
[VERIFIED; full table in stage_8]

**Mileage coverage**, counted against applicable powertrains only:

| Fuel | Coverage |
|---|---|
| Petrol | 340/525 (64.8%) |
| Diesel | 84/165 (50.9%) |
| Petrol Hybrid | 19/20 |
| CNG (km/kg) | 39/82 (47.6%) |
| EV range | 35/37 (94.6%) |

Phase 7A's figures reproduce with its own groupings (526 and 167 variants). The reports disagree only on how they group fuels.

**Other checks:**
- 6 CNG variants carry a kmpl value; 4 of them have no km/kg value.
- `adas_tier` duplicates the ADAS boolean.
- 189 aliases need review; 0 are verified.
- The 20 NULL-price variants are the edition variants; `v_effective_variant` fills them with the base variant's values.
- Status vocabulary is inconsistent across sources.

**What checks clean:**
- no duplicate identities;
- no cross-model mismatches;
- no impossible EV/ICE field combinations;
- no missing artifacts.

## 13. Technical debt
- None of the KB is under version control: code, schema, reports, backups or artifacts. The code that produced the current data no longer exists as it was, because it was mutated by `fix_*`/`patch_*` scripts.
- There is no migration or version system. `KB_SCHEMA.sql` is stale.
- Foreign keys are not enforced.
- DB paths depend on the current working directory.
- The `source.authority_tier` values in the table disagree with `authority_matrix.py` (v6 2 vs 5, v3cars 2 vs 3).
- `extraction_method` is hard-coded to `rsc_payload`.
- Status vocabularies are mixed.
- Production evidence sits in `scratch/`. Stray DBs sit in `knowledge_base/` (`isolated_batch_kb.db`, `test_aura.db`, and a 0-byte `ingestion/carrec_kb.db`).
- Backups have no manifest, and no script creates them.
- The 91wheels package is broken. `test_borderless_spatial.py` is broken.
- The CSV-era `scraping/` and `datasets/` folders are deleted but not committed.
- The updater's `updates` count is overwritten rather than added to (`updater.py:222`, `updates = len(…)`).
- The Phase 9A CarWale resolution mismatch is still present and is carried here as debt.

## 14. Confirmed bugs / mismatches
[VERIFIED]
1. OEM observations use source_id 1 (v6_migration) instead of 6 (oem). As a result:
   - they get authority tier 5 instead of 1;
   - all 28 OEM rejections come from this;
   - the Phase 6 report is [CONTRADICTED].
2. BNCAP test 27 (Harrier.EV) is applied to the ICE-only Harrier.
3. V3Cars writes an absent feature as 0: 285 accepted zero-facts.
4. CarWale obs 2842/2843 are swapped between Creta E and Creta EX.
5. Edition variant 820 absorbs 33 CarWale observations from other trims, fuels and gearboxes, and 39 accepted values landed on editions.
6. Edition variant 833's name contradicts its powertrain and transmission. Variants 814 and 826 have base variants with a different trim.
7. Phase 9B left `source_observation` status stale on 3 rows.
8. `scratch/phase8_production_ingestion.py` commits before its invariant checks.
9. `phase8b_prod_ingestion.py`'s `logical_diff` counts modifications only when row counts are equal.
10. The recommender's CNG filter key `Fuel_Type_Cng` does not exist in the CSV.
11. `test_acquire_brochures.py` opens production.
12. The backup named `pre_phase5_carwale` is not a pre-CarWale state.
13. Report contradictions, all listed in stage_9: PHASE8B_FINAL_GATE UNRESOLVED count (3 vs 7), PHASE9 "20 unresolved variants" and "OEM lowercase statuses", PHASE9A "variant 452" and "mid-2500s".

## 15. Test coverage
Existing tests cover resolver unit logic, edition creation, V3Cars mapping, extractor fixtures and PDF utilities, all on minimal schemas. [REPORTED-ONLY (subagent)]

Missing tests:
- real schema and constraints;
- FK enforcement;
- re-run idempotency;
- authority and source_id correctness;
- canonical immutability;
- shared-powertrain side effects;
- safety applicability semantics;
- artifact checksums;
- status consistency between observations and tests;
- BNCAP ingestion (its code lives only in `scratch/`).

Tests were not run, because collecting them opens production.

## 16. Recommender integration points
[VERIFIED except where tagged]
- **Data:** the CSV plus pickles. No KB.
- **Flow:** `/predict` → ML/regex intent parser → hard filters → `rank_cars` → diversity cap → top 4 with reasons.
- **Assumptions baked in:**
  - missing means 0 (`safe_num`, `.fillna(0)`);
  - every row is a certain variant;
  - safety means airbags > 0 and ABS, with no NCAP [REPORTED-ONLY (subagent)];
  - hard-coded favourites and penalties [REPORTED-ONLY (subagent)].
- **Where the KB would plug in:** replace the CSV with a read-only KB view that carries three-valued features (true / false / unknown), evidence class, and safety at MODEL_LEVEL.

## 17. Future-layer integration points
See stage_10.
- Professional-review and owner layers attach as new `source` types plus `source_observation` rows, with scoped applicability tables modelled on `safety_test_applicability`, and assessment tables that are **never** routed through `field_provenance` or used to update canonical columns.
- Keep five evidence classes separate: OEM_FACT, SAFETY_TEST_RESULT, PROFESSIONAL_ASSESSMENT, OWNER_REPORT and DERIVED_VALUE.
- Blocked until two things are fixed: OEM facts are mislabelled as v6 migration, and absent-means-zero facts are stored as real facts.

## 18. Recommended next phases (recommendations only)
1. **Phase 10-0, governance, with no DB change:** put `knowledge_base/` code, `KB_SCHEMA.sql`, reports, the backup manifest and the PDF artifacts (or their checksums) under git. Move the BNCAP PDFs out of `scratch/`. Adopt `CLAUDE.md`.
2. **Phase 10A, read-only diagnostics:** quantify the effects of the OEM source mislabel, the V3Cars zero-facts, CarWale mis-resolution onto editions, and Harrier.EV. Produce remediation proposals, each with an isolated diff.
3. **Phase 10B, controlled remediations,** one per change, using the SAFETY_MAP procedure:
   - re-attribute the 52 OEM observations;
   - reclassify Harrier.EV as NO_MATCH;
   - resync the 3 observation statuses;
   - quarantine rather than delete the V3Cars zero-facts.
4. Only after 10A and 10B: design the real generation layer, then design the review and owner layers.

## 19. Things that must NOT be changed casually
- The production DB file.
- The 297 orphaned provenance rows. Do not delete them or re-point them.
- The 24 Global NCAP rows in `safety_rating`. Do not migrate them until protocol handling exists.
- `scratch/bncap_pdfs/*`, because the checksums are pinned in the DB.
- `knowledge_base/sources/oem/*`.
- Every file in `knowledge_base/backups/`.
- `scratch/carrec_kb_idemp.db`: the only surviving copy of the Phase 8 (324-row) state.
- `scratch/carrec_kb_pre_restore_forensic_snapshot.db`.
- `v_effective_variant`: consumers rely on it.
- `authority_matrix.py` tiers.
- The resolver thresholds.
- The `source` IDs.

## 20. Unresolved uncertainties
- Whether DB Browser's 6 WAL frames had been committed and checkpointed, or were uncommitted and discarded. Either way, the main file hash was unchanged.
- Who deleted CarWale pilot observations for Verna, Creta and Kushaq. No script does it.
- Why Phase 8 was reverted, and whether the revert was a file copy.
- Whether the canonical values supported only by V6 or orphaned rows (e.g. `transmission`) are correct.
- Whether the 285 V3Cars zeros, and the 125 from 91wheels, are true absences.
- Which edition field values came from mis-resolved observations.
- Whether the Phase 9A/9B scripts matched what their reports describe (the scripts are missing).
- The correctness of the positional AOP/COP star parsing.
- The correct generation for the BNCAP tests (2024 vs 2026 Punch.ev).
- The behaviour of the 91wheels and CarWale code at the time it ran. That code was mutated afterwards.
- Claims from subagents that I did not re-read line by line (tagged REPORTED-ONLY (subagent)).
