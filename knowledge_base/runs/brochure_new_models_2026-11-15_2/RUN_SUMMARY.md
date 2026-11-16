# Run brochure_new_models_2026-11-15_2

**Stopped / not merged:** --no-write: staged and gated, the KB was not touched

## Coverage (before → after)
Source: database counts in `brochure_new_models_2026-11-15_2/run.json`.

- Models: 92 → 92. Variants: 1464 → 1464. Marked discontinued: 0 → 0.
- Filled cells: 36333 → 38534 of 52704 possible.
- Cells with at least one URL-backed evidence row: 26495 → 28696.

| Segment | Models | Variants |
|---|---|---|
| Hatchback | 14 → 14 | 174 → 174 |
| MPV | 10 → 10 | 121 → 121 |
| Pickup | 1 → 1 | 3 → 3 |
| SUV | 57 → 57 | 1046 → 1046 |
| Sedan | 9 → 9 | 116 → 116 |
| Van | 1 → 1 | 4 → 4 |

## Discovery and changes
Source: `brochure_new_models_2026-11-15_2/discovery.json`, `brochure_new_models_2026-11-15_2/run.json`.

- On sale on both sites and already in the KB: 91. New models found: 16. Out of scope by price: 11.
- Models processed this run: 30. Unchanged and skipped: 0. Deferred to the next run: 0.
- Models added: 0. Variants added: 0. Cells written: 2201. Existing cells confirmed by both sites: 7550.
- Variants not added because only one site lists them or the sites disagree on identity: 106.
- Existing cells where both sites differ from the KB or could fill a blank (in review, not applied): 5.
- KB variants not found in the current listing (in review, not marked): 0. Discontinued-model candidates: 1.

## Verification
Source: `brochure_new_models_2026-11-15_2/verify/results.jsonl` only (written by the verifier, read-only).

- Overall: no checked cells. Sample size 0.

| Field type | Accuracy | Checked | Match | Mismatch | Unreachable | Verifier errors |
|---|---|---|---|---|---|---|

No field type is below the 95% bar.

By field type and source class:

| Stratum | Accuracy | Checked |
|---|---|---|

Human agreement sheet: not produced (no checked cells). Fill the last column, then run `kbpipe agreement <file>`.

## Conflicts
Source: `brochure_new_models_2026-11-15_2/conflicts.tsv`.

- 212 conflict(s); 104 above the disagreement threshold.
- Resolution: specific label kept: 90; precedence: brochure: 70; left null: 52.
- Most frequent fields: transmission (90), power_bhp (18), torque_nm (13), ventilated_front_seats (13), cruise_control (10), mileage_arai_kmpl (9), rear_camera (8), camera_360 (6).

## Cells left blank
Source: `brochure_new_models_2026-11-15_2/flags.tsv`.

- POWERTRAIN_DIFFERS: 254
- VARIANT_NOT_ADDED: 106

## Waiting for you
11 item(s) in `brochure_new_models_2026-11-15_2/REVIEW_brochure_new_models_2026-11-15_2.md`. Top of the list:

- M-Honda-elevate (FACELIFT): Honda Elevate: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Mahindra-thar (FACELIFT): Mahindra Thar: CarWale gives launch date 2026-09-22, after the KB's first data for this model (2026-06-25)
- M-Maruti-baleno (FACELIFT): Maruti Suzuki Baleno: CarWale gives launch date 2026-09-05, after the KB's first data for this model (2026-06-22)
- M-Maruti-brezza (FACELIFT): Maruti Suzuki Brezza: CarWale gives launch date 2026-07-24, after the KB's first data for this model (2026-06-22)
- M-Skoda-slavia (FACELIFT): Skoda Slavia: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Tata-tigor (DISCONTINUED_CANDIDATE): Tata Tigor: CarWale: not listed, CarDekho: discontinued
- M-Toyota-glanza (FACELIFT): Toyota Glanza: CarWale gives launch date 2026-10-14, after the KB's first data for this model (2026-06-24)
- M-Toyota-hilux (FACELIFT): Toyota Hilux: CarWale gives launch date 2026-07-28, after the KB's first data for this model (2026-06-24)
- M-Honda-amaze2ndgen (REVIEW_MODEL): Honda Amaze 2nd Gen: name carries a generation marker: new model, or a generation of one the KB has?
- R001 (VALUE_CHANGE): Tata Aeris: cruise_control on 3 variant(s) differs from the KB
- R002 (VALUE_CHANGE): Skoda Kodiaq: mileage_arai_kmpl on 2 variant(s) differs from the KB

## Gates
Source: `brochure_new_models_2026-11-15_2/run.json`.

- schema: pass — schema 87b7f560cd53, integrity ok, 297 known orphans
- provenance: pass — 2201 of 2201 new or changed cells have provenance
- rows: pass — evidence_amendment 681->681; evidence_quarantine 1636->1636; field_provenance 98967->113601
- explained: pass — 15974 changed rows, all in the run log
- reviews: pass — 0 new or changed review rows have provenance
- idempotency re-run: 0 changes

## Cost and runtime
- LLM calls: 0 (none). Cost: Rs 0 (free tier).
- Pages fetched: 0 from the network, 475 from cache, 0 failed.
- Runtime: 16 minutes.
