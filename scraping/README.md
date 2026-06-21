# Scraping Workspace

This folder contains scraping-related code and supporting files for the Smart Car Recommendation Engine.

- Raw scraped data goes to `datasets/raw`.
- Cleaned but not final data goes to `datasets/interim`.
- Final app-ready data goes to `datasets/processed`.
- Source-specific scraper modules go in `scraping/sources`.
- Logs go in `scraping/logs`.
- Schema definitions go in `scraping/schemas`.
- Tests go in `scraping/tests`.

## Active Pipeline Map

The active tree now keeps only the smallest runtime-coherent scraping set. Historical pilot, audit, and enrichment scripts were moved to `archive/scraping_reproducibility/historical_scripts/`.

| Order | Script | Classification | Required inputs | Produced outputs | Live scraping | Notes |
|---:|---|---|---|---|---|---|
| 1 | `scraping/schemas/new_car_schema.py` | ACTIVE_PIPELINE | none | canonical column lists and helpers | no | Shared schema definition. |
| 2 | `scraping/sources/carwale_variant_parser.py` | ACTIVE_PIPELINE | saved CarWale HTML path and source URL | `scraping/outputs/carwale_single_variant_record.json` when run as CLI | no | Parses a single saved variant page into the canonical schema. |
| 3 | `scraping/sources/carwale_fetcher.py` | ACTIVE_PIPELINE | explicit CarWale variant URL | `datasets/raw/carwale/html/`, `datasets/raw/carwale/records/`, `scraping/logs/carwale_fetch_log.jsonl` | yes | Controlled one-page fetch/cache/parse utility. Creates output directories as needed. |
| 4 | `scraping/sources/pipeline_utils.py` | MAINTENANCE_UTILITY | none | shared readiness helpers | no | Used by retained build/validation code. |
| 5 | `scraping/sources/final_dataset_builder.py` | FINAL_DATASET_BUILD | `datasets/interim/cosmetic_variant_recovered/`, final review reports in `scraping/outputs/` | final canonical JSON/CSV files in `datasets/processed/` | no | Use `--validate-only` to validate current processed outputs without rewriting them. |
| 6 | `scraping/tests/test_engine_cc_parsing.py` | MAINTENANCE_UTILITY | retained parser helper | unit-test result | no | Regression coverage for displacement parsing. |

## Current Final Build Inputs

The final canonical dataset builder uses active interim data and retained review evidence:

- `datasets/interim/cosmetic_variant_recovered/**/enriched_records.json`
- `scraping/outputs/remaining_record_review.json`
- `scraping/outputs/quarantined_records.json`
- `scraping/outputs/manual_review_required.json`
- `scraping/outputs/mileage_conflict_review.json`
- `scraping/outputs/engine_cc_repair_report.json`
- `scraping/outputs/cosmetic_variant_recovery_rejected.json`

## Validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover scraping/tests
python3 -m scraping.sources.final_dataset_builder --validate-only
```

Archived raw HTML and historical reports are not needed for Flask runtime. Use `scraping/ARCHIVE_SUMMARY.md` and `archive/scraping_reproducibility/ARCHIVE_INDEX.md` if a historical replay is needed locally.

## Missing-Field Enrichment Pipeline

The enrichment framework is policy-first. It audits gaps, proposes candidate work, and validates inheritance/conflicts, but it does not fill missing values unless a future source adapter supplies high-confidence evidence.

| Order | Script or module | Required inputs | Produced outputs | Live scraping | Purpose |
|---:|---|---|---|---|---|
| 1 | `scraping/config/field_enrichment_policy.json` | canonical schema | policy consumed by audits and enrichment helpers | no | Defines category, scope, applicability, sources, inheritance, and validation rule for every canonical field. |
| 2 | `scraping/config/field_source_strategy.json` | field policy | source strategy config | no | Maps fields to preferred and fallback source classes. |
| 3 | `scraping/sources/canonical_completeness_audit.py` | `datasets/processed/carrec_canonical_recommendation_ready.json`, field policy | `canonical_field_completeness.*`, `canonical_record_completeness.*`, `enrichment_queue.*`, `pilot_enrichment_plan.*` | no | Measures raw field/record completeness and creates a prioritized missing-field queue. |
| 4 | `scraping/sources/recommendation_completeness.py` | processed ready dataset, field policy | `recommendation_completeness_report.json`, `.md` | no | Scores records by recommendation-critical completeness instead of plain schema coverage. |
| 5 | `scraping/enrichment/missing_field_detector.py` | canonical records, field policy | queue entries in memory | no | Reusable detector for applicable missing fields. |
| 6 | `scraping/enrichment/adapters/base.py` | source-specific implementation | candidate envelopes | adapter-dependent | Interface for future sources such as OEM brochures or exact-variant portal pages. |
| 7 | `scraping/enrichment/engine.py` | records, policy, registered adapters | dry-run candidate/decision summary | adapter-dependent | Coordinates missing-field detection, candidate extraction, validation, conflict checks, and deterministic resolution. |
| 8 | `scraping/enrichment/validators.py` | record plus candidate value | validation issues | no | Enforces fuel-specific applicability, numeric ranges, and unit separation. |
| 9 | `scraping/enrichment/inheritance.py` | source record, target record, policy | inheritance allow/block decision | no | Blocks unsafe cross-powertrain or selected-default inheritance. |
| 10 | `scraping/enrichment/conflict_detector.py` | candidate values | conflict groups | no | Keeps conflicting source values unresolved for review. |
| 11 | `scraping/enrichment/provenance.py` and `scraping/schemas/enrichment_schema.py` | candidate or accepted value inputs | provenance/candidate envelopes | no | Standardizes evidence retained for every future merged value. |

Recommended audit sequence:

```bash
python3 -m scraping.sources.canonical_completeness_audit
python3 -m scraping.sources.recommendation_completeness
python3 -m unittest discover -s scraping/tests
python3 -m scraping.sources.final_dataset_builder --validate-only
```

Future enrichment should start with the generated `scraping/outputs/enrichment_queue.json`, select one source class and a small representative sample, then merge only values that pass the policy, validator, conflict, provenance, and review gates.
