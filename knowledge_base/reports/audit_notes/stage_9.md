# Stage 9 — Reports, tests, recommender

## Report claims vs evidence (reports not edited)
| Report | Claim | Status |
|---|---|---|
| PHASE6_OEM_CONTROLLED_PRODUCTION | pre 6ea3b931 → post e752ebde; +52 obs, +133 prov | counts [VERIFIED via backup copies] |
| PHASE6_OEM_CONTROLLED_PRODUCTION:137 | "`source_id = 1` (OEM source)" | [CONTRADICTED] source 1 = v6_migration; OEM = 6 |
| PHASE7A | petrol 64.6%, diesel 50.3%, CNG 47.6%, EV 94.6% | [VERIFIED] reproducible (340/526, 84/167, 39/82, 35/37) |
| PHASE8A | shadow +27 applicability; "READY" | [REPORTED-ONLY]; superseded |
| PHASE8B_FINAL_GATE (09-23 08:38) | "Quarantined (UNRESOLVED): 3"; prod checksum e752ebde "never mutated" | [CONTRADICTED] 7 UNRESOLVED in post-8B DB; immutability true only at its time of writing |
| PHASE8_BHARAT_NCAP_PRODUCTION (09-23 21:04) | PRODUCTION_INGESTION_SUCCESS, 324 applicability, post 6cc95a6e | [VERIFIED] state existed (scratch/carrec_kb_idemp.db); **then silently reverted** — no report documents the revert [VERIFIED absence] |
| PHASE8B_PRODUCTION_INGESTION | e752ebde → c1e0647c; +37/+37/+20; 37 PDFs valid; 20 applic all variant NULL | [VERIFIED] |
| PHASE8B §5.7 | "generation_id NULL (correct for FAMILY_LEVEL)" | [VERIFIED] but 6 MODEL_LEVEL rows also NULL — undocumented |
| PHASE8B / PHASE9 | Harrier test mappings correct | [CONTRADICTED] test 27 HARRIER.EV → ICE-only Harrier |
| PHASE9 | 297 orphans on "Creta, Verna, Harrier, Kushaq, and others" | [CONTRADICTED] only those 4 models |
| PHASE9 | 20 NULL-price variants "could not be resolved" | [CONTRADICTED] they are the 20 edition variants |
| PHASE9 | lowercase statuses are "OEM observations" | [CONTRADICTED] there are 0 source-6 observations; lowercase = aggregators |
| PHASE9 | adas_tier = boolean duplicate | [VERIFIED] |
| PHASE9A | 297 orphans, 212/79/6, obs 2608–2661, 4 models | [VERIFIED] |
| PHASE9A | 6 accepted all on variant 452 | [CONTRADICTED] variants 441, 442, 452 |
| PHASE9A | snapshot 2502 ⇒ last v3cars SO in mid-2500s | [CONTRADICTED] max v3cars id 2607 |
| PHASE9A | "canonical values remain correct" | [REPORTED-ONLY] — unverifiable; for the 6 accepted, a live `confirmed` row exists [VERIFIED]; 6 confirmed `transmission` orphans have no live support |
| PHASE9A | CarWale SO 2842/2843 swapped | [VERIFIED] still present |
| PHASE9A | GNCAP 24 rows all have URL, gen FK | [VERIFIED] |
| PHASE9B | 3 modified + 3 added, nothing else; post 1e3eb679 | [VERIFIED] exact |
| PHASE9B | "Original safety-test provenance preserved" | partially — `source_observation.resolution_status` left UNRESOLVED (drift) |
| Backup names | `pre_phase5_carwale` is pre-CarWale | [CONTRADICTED] contains post-pilot state (297 orphans) |

## Tests (knowledge_base/tests + ingestion/oem/test_acquire_brochures.py) [REPORTED-ONLY (subagent) unless noted]
Exists: resolver identity/edition/tie tests, semantic normalisation, V3Cars mapping (asserts absent→0 as correct), 91wheels extractor fixture, PDF utils, variant-column matrix on real PDFs, integration (tmp DB with minimal schema). `test_borderless_spatial.py` references non-existent functions; `test_acquire_brochures.py` opens production (rw) [VERIFIED].
Missing: real-schema/constraint tests; FK enforcement; observation idempotency on re-run; authority tier behaviour incl. source_id correctness; canonical immutability; shared-powertrain side-effects; safety applicability semantics (EV↔ICE, generation); artifact checksum verification; provenance/observation status consistency; any test of BNCAP ingestion (code lives only in scratch). No test runner config pins tests away from prod. Tests were not run (would touch prod).

## Recommender [VERIFIED unless tagged]
- Reads **only** `car_recommendation_assets/processed_dataset.csv` (1265 rows × 395 cols) + pickles (app.py:21-27). **No KB access** (grep of app/services/utils/ranking/ml_parser for sqlite/carrec_kb/knowledge_base → none).
- Flow: `/predict` (app.py) → `services/new_car_service.get_new_car_recommendations` → ML intent parser (ml_parser/ml_intent_parser.py; regex fallback utils.py) → `utils.filter_cars` + `apply_hard_feature_filters` → `ranking_engine.rank_cars` → per-make diversity cap, top 4 → reasons → JSON → static/script.js [flow REPORTED-ONLY (subagent); endpoints/paths spot-checked].
- Assumptions: missing = 0/absent (`safe_num` default 0.0, ranking_engine.py:50-60; `.fillna(0)` new_car_service.py:105) [VERIFIED]; each CSV row = certain variant; no NCAP data used — "safety" = airbags>0 and ABS [REPORTED-ONLY (subagent)]; hard-coded model favourites/penalties and price thresholds [REPORTED-ONLY (subagent)]; CNG intent produces key `Fuel_Type_Cng` (ml_intent_parser.py:446 `.title()`) but the CSV column is `Fuel_Type_CNG + Petrol` → CNG filter silently dropped [VERIFIED].
- Used-car path scrapes CarTrade/OLX live with Selenium on each request [REPORTED-ONLY (subagent)].
- Integration point: the KB is currently a disconnected asset; any KB→recommender bridge must decide how to surface NULL/unknown, MODEL_LEVEL safety, derived edition values, and evidence class.

Checksum gate: `1e3eb679…` ✔
