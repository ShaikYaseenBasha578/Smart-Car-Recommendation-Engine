# Stage 1 — Repository inventory

Method: three read-only Explore subagents (root+scratch; knowledge_base; Flask app + misc dirs) + my own spot-verification of every high-risk claim. Agent claims I did not personally re-read are tagged [REPORTED-ONLY (subagent)].

## Directory map (repo root = `Flask Based App with Used Cars Function/`)
| Path | Purpose | Class | Can write prod KB? |
|---|---|---|---|
| `knowledge_base/carrec_kb.db` | Production KB (SQLite, WAL mode) | PRODUCTION | — |
| `knowledge_base/backups/` | 4 phase backups (see stage_0) | backup | no (data) |
| `knowledge_base/ingestion/common/` | resolver.py, updater.py, authority_matrix.py, fetcher.py | production-critical code | via callers |
| `knowledge_base/ingestion/carwale/` | CarWale adapter; `DB_PATH` resolves to prod from `__file__` | production-critical / legacy | **YES** (commits per variant) [REPORTED-ONLY (subagent): ingest_carwale.py:10,103] |
| `knowledge_base/ingestion/v3cars/` | V3Cars adapter | legacy | **YES** [REPORTED-ONLY (subagent): ingest_v3cars.py:12,23,53,112] |
| `knowledge_base/ingestion/source_91wheels/` | 91wheels adapter — **broken imports, cannot run** | legacy | batch_runner.py targets prod (relative) |
| `knowledge_base/ingestion/oem/` | brochure acquisition + PDF extractor families + batch runner (runs on isolated copy, never commits) | experimental | batch_runner_oem copies prod → `knowledge_base/isolated_batch_kb.db` |
| `knowledge_base/db/` | migrate_v6.py (os.remove(DB_PATH) at :85), migrate_editions.py (ALTER + DROP VIEW), validate/query_demo | HIGH-RISK legacy | migrate_editions: YES (relative path) |
| `knowledge_base/tests/` | pytest suite, tmp/in-memory DBs; minimal schemas | tests | no — except `ingestion/oem/test_acquire_brochures.py` opens prod rw-mode connection [VERIFIED acquire_brochures.py:15,51] |
| `knowledge_base/sources/oem/` | 67 brochure PDFs + manifest (3 Skoda PDFs are from cartrade, not OEM) | evidence artifacts | no |
| `knowledge_base/reports/` | ~70 phase reports (all untracked) | docs | no (audit_carwale_crawl.py reads prod) |
| `knowledge_base/{isolated_batch_kb.db,test_aura.db}` | scratch copies misplaced in KB dir | scratch | — |
| `knowledge_base/ingestion/carrec_kb.db` | 0-byte stray (09-09 20:03) — artefact of a relative-path connect in the pre-refactor layout | junk | — |
| `knowledge_base/*.json` | batch state + pre-crawl snapshots (91wheels/v3cars/carwale) | generated | — |
| `scratch/` | 330 .py, 18 .db, logs, **`bncap_pdfs/` (37 production safety artifacts)**, all BNCAP/Phase 6–8 production scripts | scratch — but holds production-critical artifacts & scripts | **YES** (see safety map) |
| root `*.py` (~74) | fix_/patch_/rewrite_ (edit source files), forensic_* (read-only), run_mini_pilot.py & test_debug.py (**DELETE on prod**) | scratch / HIGH-RISK | yes (2 scripts) |
| `app.py`, `services/`, `ranking_engine.py`, `utils*.py`, `ml_parser/`, `templates/`, `static/`, `car_recommendation_assets/` | Flask recommender | production-critical (app) | **no** — no sqlite/KB reference [VERIFIED grep rc=1] |
| `scripts/build_hybrid_working_dataset.py` | builds `datasets/final/*` — now broken (datasets/ deleted from working tree) | legacy | no |
| `AG Datasets/`, `AG Scraping scripts/`, `(old)scraping and datasets/`, `archive/` | Antigravity-era CSV pipeline + moved copy of deleted `scraping/` | legacy | no [REPORTED-ONLY (subagent)] |
| `graphify-out/`, `reverse_engineering_reports/` | generated knowledge graph + handoff docs | generated | no |
| `.agent/`, `.gemini/`, `.impeccable/` | "impeccable" UI-design skill (Antigravity/Gemini) | agent artifact | no |
| `.agents/` (+ parent `../.agents`) | graphify rule/workflow | agent artifact | no |

## Prior-agent constraints worth carrying over
- `../AGENTS.md` / `knowledge_base/reports/AGENTS.md` ("Ponytail"): minimal diffs, root-cause fixes, "not lazy about … error handling that prevents data loss", leave one runnable check. **Contains no DB-safety rules.** [VERIFIED read]
- `.agents/rules/graphify.md`: query `graphify-out/` first; run `graphify update .` after code edits. [VERIFIED read] (graph is stale w.r.t. untracked KB code — not verified further)
- `reverse_engineering_reports/AGENT_HANDOFF.md`: missing features must be "Unknown", not False [REPORTED-ONLY (subagent)] — violated by the live recommender and by V3Cars absent→0.
- Precision>coverage, checksum-gated production writes, isolated idempotency runs: encoded only in phase reports, not in any rule file.

## Backup / snapshot → phase map (SHA-1, from stage 0 + copies)
| Hash | Files | Phase state | Evidence |
|---|---|---|---|
| f604994b | backups/carrec_kb_pre_phase5_carwale.sqlite (09-09 20:54) | after 91wheels+V3Cars, after CarWale *pilot* + its deletion (297 orphans already present), before CarWale full crawl | [VERIFIED counts: 2502 obs, 0 carwale obs, 297 orphans] |
| 6ea3b931 | scratch/carrec_kb_production_backup.db, scratch/carrec_kb_phase6_final_preproduction_backup.db, scratch/integration_test_kb.db, scratch/isolated_batch_kb.db, knowledge_base/isolated_batch_kb.db | post-CarWale, pre-OEM (3362 obs) | [VERIFIED] |
| fa4b985b | scratch/carrec_kb_pre_restore_forensic_snapshot.db, scratch/idempotency_kb.db | first (failed) OEM production 09-12 (3414 obs / 36319 prov) — later restored | [VERIFIED counts]; restore per PHASE6_OEM_INGESTION_RECOVERY_REPORT [REPORTED-ONLY] |
| e752ebde | backups/carrec_kb_pre_phase8_20260923210209.db, backups/carrec_kb_phase8b_backup.db, scratch/carrec_kb_phase6_postproduction_idempotency.db | post-Phase-6 controlled OEM (09-13) = pre-Phase-8 | [VERIFIED] |
| 6cc95a6e | scratch/carrec_kb_idemp.db | Phase 8 production state (324 applicability rows) — later reverted | [VERIFIED counts: 324 applic] |
| c1e0647c | backups/carrec_kb_phase9b_backup.db, scratch/carrec_kb_phase8b_isolated.db | post-8B = pre-9B | [VERIFIED] |
| 1e3eb679 | knowledge_base/carrec_kb.db | post-9B (current) | [VERIFIED] |
| others | scratch/phase8*_shadow*, isolated_*_kb*, phase9a_bncap_test, phase9b_idempotency_test, test_aura | shadow/test copies | hashes in stage_0/this session |

## Dependency map (DB-touching)
- `common/updater` → `common/authority_matrix`; all adapters → `common/resolver` + `common/updater`.
- OEM: `batch_runner_oem` → profiler/classifier/extractor → `ingest_oem.process_oem_payload` → updater. Production OEM runs were driven from `scratch/production_ingestion*.py`, `scratch/final_production_ingestion.py` [REPORTED-ONLY (subagent)].
- BNCAP: `scratch/phase8a_shadow_ingestion_v4.py::ingest` (commits internally, :498 [VERIFIED]) ← `scratch/phase8_production_ingestion.py`; `scratch/phase8b_prod_ingestion.py` self-contained [VERIFIED]. Phase 9A/9B scripts: **not on disk** [REPORTED-ONLY (subagent); `ls scratch | grep phase9` shows only the two .db outputs — VERIFIED].
- Flask app: depends on nothing in knowledge_base/ [VERIFIED].

Checksum gate: `1e3eb6795452860276eca24e7dd1f52e85e67a93` ✔
