# Stage 7 — Script safety classification

Deliverable written: `knowledge_base/reports/CLAUDE_CODE_SCRIPT_SAFETY_MAP.md` (table + NEVER-RUN list + controlled-write procedure).

Key verified items:
- `run_mini_pilot.py:8-11` DELETEs field_provenance, source_observation, and all edition variants on prod, commits [VERIFIED].
- `test_debug.py:10-11` DELETEs a prod observation without provenance cleanup [VERIFIED].
- `scratch/production_ingestion_controlled.py:236,338` copy a backup over prod [VERIFIED].
- `scratch/phase8_production_ingestion.py`: invariant checks run after `ingest()` already committed [VERIFIED].
- `scratch/phase8b_prod_ingestion.py`: SHA-1 pre-gate, DDL outside txn, no backup creation, no restore, hash-set diff [VERIFIED].
- `batch_runner_oem.py:141` / `production_ingestion_controlled.py:149` pass source_id=1 for OEM [VERIFIED].
- Phase 9A/9B scripts missing from disk [VERIFIED].
- 330 scratch + 74 root scripts classified via subagent [REPORTED-ONLY (subagent)] except the lines above.

Checksum gate: `1e3eb679…` ✔
