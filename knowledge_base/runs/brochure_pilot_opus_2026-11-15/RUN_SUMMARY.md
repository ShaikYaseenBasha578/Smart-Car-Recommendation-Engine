# Run brochure_pilot_opus_2026-11-15

**Stopped / not merged:** --no-write: staged and gated, the KB was not touched

## Coverage (before → after)
Source: database counts in `brochure_pilot_opus_2026-11-15/run.json`.

- Models: 92 → 92. Variants: 1464 → 1464. Marked discontinued: 0 → 0.
- Filled cells: 36333 → 36794 of 52704 possible.
- Cells with at least one URL-backed evidence row: 26495 → 26956.

| Segment | Models | Variants |
|---|---|---|
| Hatchback | 14 → 14 | 174 → 174 |
| MPV | 10 → 10 | 121 → 121 |
| Pickup | 1 → 1 | 3 → 3 |
| SUV | 57 → 57 | 1046 → 1046 |
| Sedan | 9 → 9 | 116 → 116 |
| Van | 1 → 1 | 4 → 4 |

## Discovery and changes
Source: `brochure_pilot_opus_2026-11-15/discovery.json`, `brochure_pilot_opus_2026-11-15/run.json`.

- On sale on both sites and already in the KB: 91. New models found: 16. Out of scope by price: 11.
- Models processed this run: 4. Unchanged and skipped: 0. Deferred to the next run: 0.
- Models added: 0. Variants added: 0. Cells written: 461. Existing cells confirmed by both sites: 953.
- Variants not added because only one site lists them or the sites disagree on identity: 2.
- Existing cells where both sites differ from the KB or could fill a blank (in review, not applied): 0.
- KB variants not found in the current listing (in review, not marked): 0. Discontinued-model candidates: 1.

## Verification
Source: `brochure_pilot_opus_2026-11-15/verify/results.jsonl` only (written by the verifier, read-only).

- Overall: no checked cells. Sample size 0.

| Field type | Accuracy | Checked | Match | Mismatch | Unreachable | Verifier errors |
|---|---|---|---|---|---|---|

No field type is below the 95% bar.

By field type and source class:

| Stratum | Accuracy | Checked |
|---|---|---|

Human agreement sheet: not produced (no checked cells). Fill the last column, then run `kbpipe agreement <file>`.

## Conflicts
Source: `brochure_pilot_opus_2026-11-15/conflicts.tsv`.

- 26 conflict(s); 20 above the disagreement threshold.
- Resolution: precedence: brochure: 15; left null: 11.
- Most frequent fields: torque_nm (11), power_bhp (7), cruise_control (4), mileage_arai_kmpl (3), rear_ac_vents (1).

## Cells left blank
Source: `brochure_pilot_opus_2026-11-15/flags.tsv`.

- POWERTRAIN_DIFFERS: 45
- VARIANT_NOT_ADDED: 2

## Waiting for you
9 item(s) in `brochure_pilot_opus_2026-11-15/REVIEW_brochure_pilot_opus_2026-11-15.md`. Top of the list:

- M-Honda-elevate (FACELIFT): Honda Elevate: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Mahindra-thar (FACELIFT): Mahindra Thar: CarWale gives launch date 2026-09-22, after the KB's first data for this model (2026-06-25)
- M-Maruti-baleno (FACELIFT): Maruti Suzuki Baleno: CarWale gives launch date 2026-09-05, after the KB's first data for this model (2026-06-22)
- M-Maruti-brezza (FACELIFT): Maruti Suzuki Brezza: CarWale gives launch date 2026-07-24, after the KB's first data for this model (2026-06-22)
- M-Skoda-slavia (FACELIFT): Skoda Slavia: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Tata-tigor (DISCONTINUED_CANDIDATE): Tata Tigor: CarWale: not listed, CarDekho: discontinued
- M-Toyota-glanza (FACELIFT): Toyota Glanza: CarWale gives launch date 2026-10-14, after the KB's first data for this model (2026-06-24)
- M-Toyota-hilux (FACELIFT): Toyota Hilux: CarWale gives launch date 2026-07-28, after the KB's first data for this model (2026-06-24)
- M-Honda-amaze2ndgen (REVIEW_MODEL): Honda Amaze 2nd Gen: name carries a generation marker: new model, or a generation of one the KB has?

## Gates
Source: `brochure_pilot_opus_2026-11-15/run.json`.

- schema: pass — schema 87b7f560cd53, integrity ok, 297 known orphans
- provenance: pass — 461 of 461 new or changed cells have provenance
- rows: pass — evidence_amendment 681->681; evidence_quarantine 1636->1636; field_provenance 98967->101487
- explained: pass — 2790 changed rows, all in the run log
- reviews: pass — 0 new or changed review rows have provenance
- idempotency re-run: 0 changes

## Cost and runtime
- LLM calls: 0 (none). Cost: Rs 0 (free tier).
- Pages fetched: 3 from the network, 82 from cache, 0 failed.
- Runtime: 10 minutes.
