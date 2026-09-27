# Stage 3 — Schema

Source: `sqlite3 /tmp/carrec_audit/prod/carrec_kb.db .schema` → `/tmp/carrec_audit/prod_schema.sql` (270 lines). [VERIFIED]

## Objects
- 13 user tables + `sqlite_sequence`: source, manufacturer, model, generation, powertrain, variant, variant_alias, source_observation, field_provenance, safety_rating, warranty, safety_test, safety_test_applicability.
- 2 views: `v_variant_full`, `v_effective_variant` (COALESCE(v.col, base.col) over one level of `base_variant_id`).
- 14 explicit indexes + 11 autoindexes. **0 triggers. 0 CHECK constraints.** No `ON DELETE` actions anywhere.
- `journal_mode=wal` persisted in the file header.

## Keys / constraints (all tables AUTOINCREMENT integer PK)
| Table | FKs | UNIQUE | Notable nullability / gaps |
|---|---|---|---|
| source | — | name | authority_tier NOT NULL default 3 |
| manufacturer | — | name | |
| model | manufacturer_id→manufacturer | (manufacturer_id,name) | body_type nullable |
| generation | model_id→model | **none** | verification_status default 'unverified' |
| powertrain | model_id→model | (model_id,fuel_type,engine_cc,power_bhp) | engine_cc/power_bhp nullable → UNIQUE ineffective when NULL (EVs) |
| variant | model_id, generation_id, powertrain_id, base_variant_id→variant | (model_id,name,generation_id) | generation_id/powertrain_id nullable → UNIQUE ineffective if generation NULL; transmission NOT NULL; is_discontinued NOT NULL default 0 |
| variant_alias | variant_id, source_id | (source_id,alias_name) | alias unique per source, not per model → same slug in two models collides |
| source_observation | source_id, resolved_variant_id | **none** | resolution_status free text (comment lists pending/applied/conflict/rejected/unresolvable — actual values differ) |
| field_provenance | variant_id, source_observation_id | (variant_id,field_name,source_observation_id) | source_observation_id nullable |
| safety_rating | model_id, generation_id | (model_id,testing_body,test_year) | no source_id / observation link |
| warranty | manufacturer_id, model_id | none | source is free text |
| safety_test | source_id, source_observation_id | raw_source_url | artifact_path relative, nullable; resolution_status free text |
| safety_test_applicability | safety_test_id, manufacturer_id, model_id, generation_id, variant_id | (safety_test_id,model_id,match_confidence) | model_id nullable → UNIQUE ineffective for NULL model |

## Drift vs documented schema
- `KB_SCHEMA.sql` (repo root, untracked) defines 11 tables + `v_variant_full` [VERIFIED grep]. Missing from it: `safety_test`, `safety_test_applicability` (created by `CREATE TABLE IF NOT EXISTS` inside BNCAP ingestion scripts, `scratch/phase8b_prod_ingestion.py:64-96` [VERIFIED]), `variant.base_variant_id`, `variant.edition_classification`, `v_effective_variant` (added by `knowledge_base/db/migrate_editions.py` [REPORTED-ONLY (subagent)]), `idx_observation_url`.
- There is no migration registry / schema version table.

## Foreign-key enforcement
- `PRAGMA foreign_keys=ON` appears only in `KB_SCHEMA.sql:3` and `scratch/phase8_production_ingestion.py:51` [VERIFIED grep]. It is per-connection; **no KB ingestion module enables it** → FKs are declarative only. This is why 297 orphans exist without error [VERIFIED 297 via foreign_key_check].

Checksum gate: `1e3eb679…` ✔
