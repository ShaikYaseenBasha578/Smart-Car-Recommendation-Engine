# Run 2026-11-13_2

## Coverage (before → after)
Source: database counts in `2026-11-13_2/run.json`.

- Models: 90 → 92. Variants: 1447 → 1464. Marked discontinued: 0 → 0.
- Filled cells: 33113 → 36333 of 52704 possible.
- Cells with at least one URL-backed evidence row: 23252 → 26495.

| Segment | Models | Variants |
|---|---|---|
| Hatchback | 14 → 14 | 174 → 174 |
| MPV | 10 → 10 | 121 → 121 |
| Pickup | 1 → 1 | 3 → 3 |
| SUV | 55 → 57 | 1029 → 1046 |
| Sedan | 9 → 9 | 116 → 116 |
| Van | 1 → 1 | 4 → 4 |

## Discovery and changes
Source: `2026-11-13_2/discovery.json`, `2026-11-13_2/run.json`.

- On sale on both sites and already in the KB: 89. New models found: 18. Out of scope by price: 11.
- Models processed this run: 107. Unchanged and skipped: 0. Deferred to the next run: 0.
- Models added: 2. Variants added: 17. Cells written: 3243. Existing cells confirmed by both sites: 19536.
- Variants not added because only one site lists them or the sites disagree on identity: 420.
- Existing cells where both sites differ from the KB or could fill a blank (in review, not applied): 1174.
- KB variants not found in the current listing (in review, not marked): 187. Discontinued-model candidates: 1.

## Verification
Source: `2026-11-13_2/verify/results.jsonl` only (written by the verifier, read-only).

- Overall: 100.0% (23 of 23; 0 unreachable, 0 verifier errors). Sample size 23.
- Source class aggregator: 100.0% (23 of 23; 0 unreachable, 0 verifier errors).

| Field type | Accuracy | Checked | Match | Mismatch | Unreachable | Verifier errors |
|---|---|---|---|---|---|---|
| price | 100.0% | 1 | 1 | 0 | 0 | 0 |
| engine | 100.0% | 3 | 3 | 0 | 0 | 0 |
| drivetrain | 100.0% | 3 | 3 | 0 | 0 | 0 |
| capacity | 100.0% | 3 | 3 | 0 | 0 | 0 |
| comfort | 100.0% | 13 | 13 | 0 | 0 | 0 |

No field type is below the 95% bar.

By field type and source class:

| Stratum | Accuracy | Checked |
|---|---|---|
| capacity/aggregator | 100.0% | 3 |
| comfort/aggregator | 100.0% | 13 |
| drivetrain/aggregator | 100.0% | 3 |
| engine/aggregator | 100.0% | 3 |
| price/aggregator | 100.0% | 1 |

Human agreement sheet: `2026-11-13_2/human_check.csv`. Fill the last column, then run `kbpipe agreement <file>`.

## Conflicts
Source: `2026-11-13_2/conflicts.tsv`.

- 591 conflict(s); 247 above the disagreement threshold.
- Resolution: specific label kept: 309; left null: 282.
- Most frequent fields: transmission (309), torque_nm (50), power_bhp (49), tyre_pressure_monitoring_system (31), wireless_charging (26), cruise_control (20), ventilated_front_seats (19), mileage_arai_kmpl (18).

## Cells left blank
Source: `2026-11-13_2/flags.tsv`.

- SINGLE_SOURCE: 894
- NO_SOURCE: 597
- POWERTRAIN_DIFFERS: 469
- VARIANT_NOT_ADDED: 420
- CONFLICT: 2

## Waiting for you
320 item(s) in `2026-11-13_2/REVIEW_2026-11-13_2.md`. Top of the list:

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
Source: `2026-11-13_2/run.json`.

- schema: pass — schema 0a0b2f5a1ef2, integrity ok, 297 known orphans
- provenance: pass — 3243 of 3243 new or changed cells have provenance
- rows: pass — evidence_amendment 681->681; evidence_quarantine 1636->1636; field_provenance 77176->98967
- explained: pass — 23164 changed rows, all in the run log
- idempotency re-run: 0 changes

## Write
- KB SHA-1 64ac467b33a6c69e4d4ff8114ffaced0a3861f67 → 6011504064a4d6ba894f26bc6c1556b7f14ccccf. Backup: `pre_kbpipe_20261113_2_20261113T210607Z.db`. History tag: `kb-run-2026-11-13_2`. integrity_check: ok. Prod equals staging: True.

## Cost and runtime
- LLM calls: 23 (gemini-3.5-flash-lite: 2, openai/gpt-oss-120b: 21). Cost: Rs 0 (free tier).
- Pages fetched: 47 from the network, 1509 from cache, 0 failed.
- Runtime: 10 minutes.
