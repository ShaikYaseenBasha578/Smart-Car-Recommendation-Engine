# Phase 1 Implementation Plan & Dependencies

This document maps the planned database system onto the existing repository, identifying what stays, what changes, and what must be created.

## 1. Repository Restructuring
**Create a new module:** `carrec_kb/`
This directory will isolate the new database operations from the legacy Flask recommender.

**Inside `carrec_kb/`:**
* `schema.py`: SQLAlchemy ORM models (or raw SQLite creation scripts) defining the tables.
* `resolution_engine.py`: The logic that compares `source_observation` JSON against the Canonical DB.
* `crud.py`: Database access wrappers.

## 2. Script Retirement & Refactoring
**To Retire:** 
* `do_merge.py`, `step37_merge_v6.py`, `step36_audit_and_fix.py`. These flat CSV merge scripts are replaced by the database constraints.

**To Refactor (Turn into Adapters):**
* `step24_v4_extraction.py` (91Wheels JSON scraper)
* `step33_build_final.py` (V3Cars Scraper)
* *Change Required:* Instead of updating `carrec_recommendation_dataset_vX.csv`, they will now `INSERT INTO source_observation (source, payload, observed_at)`. 

## 3. The Development Sequence (First 7 Tasks)

1. **Database Initialization:** Run the `KB_SCHEMA.sql` inside a new SQLite file (`carrec.db`).
2. **Build the Migration Script:** Write `migrate_v6_to_kb.py` following the exact steps in `V6_MIGRATION_PLAN.md`.
3. **Execute Migration & Validate:** Verify exactly 812 rows in `variant`, and verify Safety/Warranty tables populated correctly.
4. **Adapter Refactor:** Modify the 91Wheels scraper to output raw Next.js JSON to the `source_observation` table.
5. **Entity Resolution Logic:** Write the script that queries `variant_alias` to link the new observation to the Canonical UUID.
6. **Conflict Resolution Logic:** Write the script that compares the Staging JSON to the Canonical `variant` row, using the Authority Matrix to resolve mismatches.
7. **Legacy Export Layer:** Write a nightly cron script `export_kb_to_v6.py` that flattens the SQLite database back into `carrec_recommendation_dataset_v6_compatible.csv`. This ensures the current `ranking_engine.py` in the Flask app doesn't break while we research the new recommender.

## 4. Dependencies
* `sqlite3` (Built-in)
* `SQLAlchemy` (Recommended for Pythonic interaction and ORM migrations, but optional).
* No heavy Docker or Postgres dependencies for Phase 1.
