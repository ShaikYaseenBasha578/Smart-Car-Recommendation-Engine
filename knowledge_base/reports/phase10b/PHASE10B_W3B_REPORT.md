# Phase 10B W3b — v_safety_applicability_q (schema-only controlled write)

**Date:** 2026-09-27. **Branch:** kb/phase-10-0-versioning. **Scope:** +1 view; no row, table, index or existing view changed.

## Object
`v_safety_applicability_q` (`knowledge_base/db/migrations/phase10b_w3b_schema.sql`, `CREATE VIEW IF NOT EXISTS`): all columns of `safety_test_applicability`, excluding rows that
1. are under active quarantine (`evidence_quarantine`, target_table='safety_test_applicability');
2. belong to a safety_test under active quarantine; or
3. belong to a safety_test whose `v_safety_test_status.canonical_status = 'no_match'` (owner addition).
Row 14 (Harrier.EV test 27 → ICE-only model 30) is excluded by conditions 1 and 3 independently.

CLAUDE.md read-path rule extended: consumers read safety applicability **only** through `v_safety_applicability_q`; the raw table stays allowed for audits.

## Controlled-write evidence
- Applier: `knowledge_base/db/migrations/apply_phase10b_w3b.py` (W0 applier pattern; expected object set = {v_safety_applicability_q}; single transaction, `foreign_keys=ON`, invariants before COMMIT).
- Backup: `knowledge_base/backups/pre_phase10b_w3b_20260927T080255Z.db` — file SHA-1 `3640143e44579a901c532d5262c1b5fa1d60e479`, content `.sha3sum` `26ee0895…50fc0a` = production pre-W3b; integrity ok; copied to Google Drive `My Drive/CarRec_backups/`, SHA-1 verified.
- Isolated diff vs backup (EXCEPT, both directions): **0 row differences in every table**; schema +1 view, none removed/altered. Re-run: no new objects, content hash unchanged (idempotent).
- View check: 22 rows = 23 − row 14; 0/0 EXCEPT vs "raw table minus row 14"; column list identical to the table. Throwaway tests: releasing row 14's quarantine alone keeps it hidden (no_match condition); a test-level quarantine on test 33 hides its row 19.
- Production: pre SHA-1 `516c50651d3e97871c2f7566ce1db712566a63b4`; COMMITTED; checkpoint `0|0|0`, no side files; integrity ok; FK: only the 297 known orphans; production diff and schema identical to isolated; view returns 22 rows.
- **New production SHA-1: `2a315b311f117844d7683f4364e1b0ad4f57802f`.**
