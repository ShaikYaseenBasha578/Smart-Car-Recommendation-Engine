# Run audit_2026-11-14

**Stopped / not merged:** --no-write: staged and gated, the KB was not touched

## Coverage (before → after)
Source: database counts in `audit_2026-11-14/run.json`.

- Models: 92 → 92. Variants: 1464 → 1464. Marked discontinued: 0 → 0.
- Filled cells: 36333 → 36333 of 52704 possible.
- Cells with at least one URL-backed evidence row: 26495 → 26495.

| Segment | Models | Variants |
|---|---|---|
| Hatchback | 14 → 14 | 174 → 174 |
| MPV | 10 → 10 | 121 → 121 |
| Pickup | 1 → 1 | 3 → 3 |
| SUV | 57 → 57 | 1046 → 1046 |
| Sedan | 9 → 9 | 116 → 116 |
| Van | 1 → 1 | 4 → 4 |

## Discovery and changes
Source: `audit_2026-11-14/discovery.json`, `audit_2026-11-14/run.json`.

- On sale on both sites and already in the KB: 91. New models found: 16. Out of scope by price: 11.
- Models processed this run: 107. Unchanged and skipped: 0. Deferred to the next run: 0.
- Models added: 0. Variants added: 0. Cells written: 0. Existing cells confirmed by both sites: 22779.
- Variants not added because only one site lists them or the sites disagree on identity: 420.
- Existing cells where both sites differ from the KB or could fill a blank (in review, not applied): 1174.
- KB variants not found in the current listing (in review, not marked): 187. Discontinued-model candidates: 1.

## Verification
Source: `audit_2026-11-14/verify/results.jsonl` only (written by the verifier, read-only).

- Overall: 89.6% (362 of 404; 95 unreachable, 1 verifier errors). Sample size 500.
- Legacy values (June 2026 import, no URL on record): 14156 cells, of which 9096 belong to a variant linked to a current page and could be sampled. They are checked against today's page, so a mismatch can also mean the car changed.
- Source class brochure: 96.0% (97 of 101; 24 unreachable, 0 verifier errors).
- Source class aggregator: 99.4% (154 of 155; 45 unreachable, 0 verifier errors).
- Source class legacy: 75.0% (111 of 148; 26 unreachable, 1 verifier errors).

| Field type | Accuracy | Checked | Match | Mismatch | Unreachable | Verifier errors |
|---|---|---|---|---|---|---|
| price | 58.0% | 50 | 29 | 21 | 0 | 0 |
| engine | 100.0% | 50 | 50 | 0 | 0 | 0 |
| drivetrain | 93.9% | 49 | 46 | 3 | 1 | 0 |
| dimensions | 95.5% | 22 | 21 | 1 | 28 | 0 |
| capacity | 98.4% | 62 | 61 | 1 | 13 | 0 |
| efficiency | 87.3% | 63 | 55 | 8 | 12 | 0 |
| safety | 91.7% | 48 | 44 | 4 | 27 | 0 |
| comfort | 93.3% | 60 | 56 | 4 | 14 | 1 |

**Below the 95% bar:** price, drivetrain, efficiency, safety, comfort.

By field type and source class:

| Stratum | Accuracy | Checked |
|---|---|---|
| capacity/aggregator | 100.0% | 20 |
| capacity/brochure | 100.0% | 25 |
| capacity/legacy | 94.1% | 17 |
| comfort/aggregator | 100.0% | 20 |
| comfort/brochure | 90.9% | 22 |
| comfort/legacy | 88.9% | 18 |
| dimensions/aggregator | n/a | 0 |
| dimensions/legacy | 95.5% | 22 |
| drivetrain/aggregator | 100.0% | 24 |
| drivetrain/legacy | 88.0% | 25 |
| efficiency/aggregator | 94.4% | 18 |
| efficiency/brochure | 100.0% | 25 |
| efficiency/legacy | 65.0% | 20 |
| engine/aggregator | 100.0% | 25 |
| engine/brochure | 100.0% | 25 |
| price/aggregator | 100.0% | 25 |
| price/legacy | 16.0% | 25 |
| safety/aggregator | 100.0% | 23 |
| safety/brochure | 50.0% | 4 |
| safety/legacy | 90.5% | 21 |

Human agreement sheet: `audit_2026-11-14/human_check.csv`. Fill the last column, then run `kbpipe agreement <file>`.

## Conflicts
Source: `audit_2026-11-14/conflicts.tsv`.

- 591 conflict(s); 247 above the disagreement threshold.
- Resolution: specific label kept: 309; left null: 282.
- Most frequent fields: transmission (309), torque_nm (50), power_bhp (49), tyre_pressure_monitoring_system (31), wireless_charging (26), cruise_control (20), ventilated_front_seats (19), mileage_arai_kmpl (18).

## Cells left blank
Source: `audit_2026-11-14/flags.tsv`.

- SINGLE_SOURCE: 677
- POWERTRAIN_DIFFERS: 469
- NO_SOURCE: 463
- VARIANT_NOT_ADDED: 420
- CONFLICT: 2

## Waiting for you
320 item(s) in `audit_2026-11-14/REVIEW_audit_2026-11-14.md`. Top of the list:

- M-Honda-elevate (FACELIFT): Honda Elevate: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Mahindra-thar (FACELIFT): Mahindra Thar: CarWale gives launch date 2026-09-22, after the KB's first data for this model (2026-06-25)
- M-Maruti-baleno (FACELIFT): Maruti Suzuki Baleno: CarWale gives launch date 2026-09-05, after the KB's first data for this model (2026-06-22)
- M-Maruti-brezza (FACELIFT): Maruti Suzuki Brezza: CarWale gives launch date 2026-07-24, after the KB's first data for this model (2026-06-22)
- M-Skoda-slavia (FACELIFT): Skoda Slavia: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Tata-tigor (DISCONTINUED_CANDIDATE): Tata Tigor: CarWale: not listed, CarDekho: discontinued
- M-Toyota-glanza (FACELIFT): Toyota Glanza: CarWale gives launch date 2026-10-14, after the KB's first data for this model (2026-06-24)
- M-Toyota-hilux (FACELIFT): Toyota Hilux: CarWale gives launch date 2026-07-28, after the KB's first data for this model (2026-06-24)
- R001 (MODEL_NOT_ADDED): Honda ZR-V is on sale but no variant could be added
- R002 (MODEL_NOT_ADDED): Hyundai Creta Electric is on sale but no variant could be added
- R003 (MODEL_NOT_ADDED): Kia Syros EV is on sale but no variant could be added
- R004 (MODEL_NOT_ADDED): MG Comet EV is on sale but no variant could be added

## Gates
Source: `audit_2026-11-14/run.json`.

- schema: pass — schema 0a0b2f5a1ef2, integrity ok, 297 known orphans
- provenance: pass — 0 of 0 new or changed cells have provenance
- rows: pass — evidence_amendment 681->681; evidence_quarantine 1636->1636; field_provenance 98967->108810
- explained: pass — 10361 changed rows, all in the run log
- idempotency re-run: 0 changes

## Cost and runtime
- LLM calls: 490 (gemini-3.5-flash-lite: 472, openai/gpt-oss-120b: 18). Cost: Rs 0 (free tier).
- Pages fetched: 370 from the network, 1398 from cache, 0 failed.
- Runtime: 59 minutes.
