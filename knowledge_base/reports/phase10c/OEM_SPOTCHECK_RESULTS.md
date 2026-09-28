# Phase 10C-1: OEM brochure extraction spot-check — results

Verdicts are the human reviewer's, checked against the brochure PDFs (aid: `spotcheck_aid/`). Transcribed into `OEM_SPOTCHECK_SHEET.csv` by `fill_spotcheck_results.py`; no DB was read or written.

Accuracy = rows with verdict `CORRECT` / rows in stratum (the extracted value matches the brochure). `error_type` is recorded independently of the verdict: a row can be `CORRECT` in value and still carry an error type (garbled raw name, wrong column that happens to hold the same value).

## Accuracy by stratum

| Stratum | n | CORRECT | WRONG | Accuracy | Wilson 95% CI |
|---|---|---|---|---|---|
| CONFIRMED_SAMPLED | 20 | 20 | 0 | 100.0% (20/20) | 83.9% – 100.0% |
| REJECTED_WOULD_FLIP | 28 | 23 | 5 | 82.1% (23/28) | — |
| ACCEPTED | 1 | 1 | 0 | 100.0% (1/1) | — |

All 49 rows: 44/49 CORRECT. The strata were sampled differently (census of rejected rows, stratified sample of confirmed rows, single accepted row), so the pooled figure is not a population estimate.

The CI is computed only for CONFIRMED_SAMPLED, the random sample (seed 20260928) of 104 confirmed rows. Wilson score interval, z = 1.96; no finite-population correction.

## error_type counts

| error_type | CONFIRMED_SAMPLED | REJECTED_WOULD_FLIP | ACCEPTED | Total |
|---|---|---|---|---|
| none | 15 | 23 | 1 | 39 |
| symbol_not_normalised | 0 | 5 | 0 | 5 |
| raw_name_garbled | 4 | 0 | 0 | 4 |
| column_misresolution | 1 | 0 | 0 | 1 |
| value_wrong | 0 | 0 | 0 | 0 |

## Non-`none` rows

| # | provenance_id | stratum | variant | field | extracted | true | verdict | error_type |
|---|---|---|---|---|---|---|---|---|
| 9 | 37269 | REJECTED_WOULD_FLIP | Maruti Suzuki Brezza ZXi MT | sunroof | `Standard` | 1 | WRONG | symbol_not_normalised |
| 12 | 37278 | REJECTED_WOULD_FLIP | Maruti Suzuki Brezza ZXi+ MT | sunroof | `Standard` | 1 | WRONG | symbol_not_normalised |
| 26 | 37317 | REJECTED_WOULD_FLIP | Volkswagen Virtus Highline Plus Petrol 1.0L Turbo Manual | sunroof | `[Vector:Curve]` | 1 | WRONG | symbol_not_normalised |
| 27 | 37318 | REJECTED_WOULD_FLIP | Volkswagen Virtus GT Plus Petrol 1.5L Turbo Automatic (DCT) Chrome | sunroof | `[Vector:Curve]` | 1 | WRONG | symbol_not_normalised |
| 28 | 37319 | REJECTED_WOULD_FLIP | Volkswagen Virtus GT Line Petrol 1.0L Turbo Manual | sunroof | `[Vector:Curve]` | 1 | WRONG | symbol_not_normalised |
| 29 | 37187 | CONFIRMED_SAMPLED | Honda Amaze V MT | automatic_climate_control | `0` | 0 | CORRECT | raw_name_garbled |
| 30 | 37189 | CONFIRMED_SAMPLED | Honda City SV MT | cruise_control | `0` | 0 | CORRECT | raw_name_garbled |
| 31 | 37190 | CONFIRMED_SAMPLED | Honda City SV MT | paddle_shifters | `0` | 0 | CORRECT | raw_name_garbled |
| 32 | 37192 | CONFIRMED_SAMPLED | Honda City ZX MT | paddle_shifters | `0` | 0 | CORRECT | raw_name_garbled |
| 40 | 37245 | CONFIRMED_SAMPLED | Maruti Suzuki Baleno Alpha MT | heads_up_display | `1` | 1 | CORRECT | column_misresolution |
