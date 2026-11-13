# Run 2026-11-13

## Coverage (before → after)
Source: database counts in `2026-11-13/run.json`.

- Models: 62 → 90. Variants: 832 → 1447. Marked discontinued: 0 → 0.
- Filled cells: 25792 → 33113 of 52092 possible.
- Cells with at least one URL-backed evidence row: 5728 → 23252.

| Segment | Models | Variants |
|---|---|---|
| Hatchback | 10 → 14 | 122 → 174 |
| MPV | 9 → 10 | 100 → 121 |
| Pickup | 1 → 1 | 3 → 3 |
| SUV | 33 → 55 | 522 → 1029 |
| Sedan | 8 → 9 | 81 → 116 |
| Van | 1 → 1 | 4 → 4 |

## Discovery and changes
Source: `2026-11-13/discovery.json`, `2026-11-13/run.json`.

- On sale on both sites and already in the KB: 61. New models found: 46. Out of scope by price: 11.
- Models processed this run: 101. Unchanged and skipped: 0. Deferred to the next run: 6.
- Models added: 28. Variants added: 615. Cells written: 12605. Existing cells confirmed by both sites: 9880.
- Variants not added because only one site lists them or the sites disagree on identity: 406.
- Existing cells where both sites differ from the KB or could fill a blank (in review, not applied): 1174.
- KB variants not found in the current listing (in review, not marked): 187. Discontinued-model candidates: 1.

## Verification
Source: `2026-11-13/verify/results.jsonl` only (written by the verifier, read-only).

- Overall: 97.0% (517 of 533; 11 unreachable, 185 verifier errors). Sample size 729.
- Source class aggregator: 97.0% (517 of 533; 11 unreachable, 185 verifier errors).

| Field type | Accuracy | Checked | Match | Mismatch | Unreachable | Verifier errors |
|---|---|---|---|---|---|---|
| price | 97.7% | 43 | 42 | 1 | 0 | 17 |
| engine | 95.7% | 115 | 110 | 5 | 0 | 52 |
| drivetrain | 93.1% | 58 | 54 | 4 | 0 | 27 |
| capacity | 97.8% | 46 | 45 | 1 | 0 | 14 |
| efficiency | 100.0% | 24 | 24 | 0 | 0 | 11 |
| safety | 99.3% | 139 | 138 | 1 | 11 | 64 |
| comfort | 96.3% | 108 | 104 | 4 | 0 | 0 |

**Below the 95% bar:** drivetrain.
**Stopped during the run:** comfort (batch 8: 32 of 34 matched).

By field type and source class:

| Stratum | Accuracy | Checked |
|---|---|---|
| capacity/aggregator | 97.8% | 46 |
| comfort/aggregator | 96.3% | 108 |
| drivetrain/aggregator | 93.1% | 58 |
| efficiency/aggregator | 100.0% | 24 |
| engine/aggregator | 95.7% | 115 |
| price/aggregator | 97.7% | 43 |
| safety/aggregator | 99.3% | 139 |

Planted-error control (`2026-11-13/verify/planted.jsonl`): 20 values the verifier had confirmed were re-submitted with a wrong value; it called 0 of 0 a mismatch.

Human agreement sheet: `2026-11-13/human_check.csv`. Fill the last column, then run `kbpipe agreement <file>`.

## Conflicts
Source: `2026-11-13/conflicts.tsv`.

- 589 conflict(s); 247 above the disagreement threshold.
- Resolution: specific label kept: 307; left null: 282.
- Most frequent fields: transmission (307), torque_nm (50), power_bhp (49), tyre_pressure_monitoring_system (31), wireless_charging (26), cruise_control (20), ventilated_front_seats (19), mileage_arai_kmpl (18).

## Cells left blank
Source: `2026-11-13/flags.tsv`.

- SINGLE_SOURCE: 7506
- NO_SOURCE: 5458
- FIELD_GROUP_STOPPED: 2914
- POWERTRAIN_DIFFERS: 434
- VARIANT_NOT_ADDED: 406
- CONFLICT: 173

## Waiting for you
322 item(s) in `2026-11-13/REVIEW_2026-11-13.md`. Top of the list:

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
Source: `2026-11-13/run.json`.

- schema: pass — schema 0a0b2f5a1ef2, integrity ok, 297 known orphans
- provenance: pass — 9456 of 9456 new or changed cells have provenance
- rows: pass — evidence_amendment 681->681; evidence_quarantine 1636->1636; field_provenance 38104->77176
- explained: pass — 42176 changed rows, all in the run log
- idempotency re-run: 0 changes

## Write
- KB SHA-1 7c0de89b902e105492345db28366e526d29bc3b6 → 64ac467b33a6c69e4d4ff8114ffaced0a3861f67. Backup: `pre_kbpipe_20261113_20261113T185116Z.db`. History tag: `kb-run-2026-11-13`. integrity_check: ok. Prod equals staging: True.

## Cost and runtime
- LLM calls: 544 (haiku: 317, openai/gpt-oss-120b: 227). Cost: Rs 0 (free tier).
- Pages fetched: 58 from the network, 1509 from cache, 0 failed.
- Runtime: 106 minutes.
