# Run update_rehearsal_resume_2026-11-17_specs

**Stopped / not merged:** --no-write: staged and gated, the KB was not touched

## Coverage (before → after)
Source: database counts in `update_rehearsal_resume_2026-11-17_specs/run.json`.

- Models: 92 → 92. Variants: 1464 → 1464. Marked discontinued: 0 → 0.
- Filled cells: 38534 → 38534 of 52704 possible.
- Cells with at least one URL-backed evidence row: 28696 → 28696.

| Segment | Models | Variants |
|---|---|---|
| Hatchback | 14 → 14 | 174 → 174 |
| MPV | 10 → 10 | 121 → 121 |
| Pickup | 1 → 1 | 3 → 3 |
| SUV | 57 → 57 | 1046 → 1046 |
| Sedan | 9 → 9 | 116 → 116 |
| Van | 1 → 1 | 4 → 4 |

## Discovery and changes
Source: `update_rehearsal_resume_2026-11-17_specs/discovery.json`, `update_rehearsal_resume_2026-11-17_specs/run.json`.

- On sale on both sites and already in the KB: 91. New models found: 16. Out of scope by price: 11.
- Models processed this run: 7. Unchanged and skipped: 100. Deferred to the next run: 0.
- Models added: 0. Variants added: 0. Cells written: 0. Existing cells confirmed by both sites: 1825.
- Variants not added because only one site lists them or the sites disagree on identity: 14.
- Existing cells where both sites differ from the KB or could fill a blank (in review, not applied): 48.
- KB variants not found in the current listing (in review, not marked): 29. Discontinued-model candidates: 1.

## Verification
Source: `update_rehearsal_resume_2026-11-17_specs/verify/results.jsonl` only (written by the verifier, read-only).

- Overall: no checked cells. Sample size 0.

| Field type | Accuracy | Checked | Match | Mismatch | Unreachable | Verifier errors |
|---|---|---|---|---|---|---|

No field type is below the 95% bar.

By field type and source class:

| Stratum | Accuracy | Checked |
|---|---|---|

Human agreement sheet: not produced (no checked cells). Fill the last column, then run `kbpipe agreement <file>`.

## Conflicts
Source: `update_rehearsal_resume_2026-11-17_specs/conflicts.tsv`.

- 39 conflict(s); 13 above the disagreement threshold.
- Resolution: specific label kept: 26; left null: 13.
- Most frequent fields: transmission (26), wireless_charging (6), sunroof (2), torque_nm (2), rear_ac_vents (1), android_auto (1), apple_carplay (1).

## Cells left blank
Source: `update_rehearsal_resume_2026-11-17_specs/flags.tsv`.

- SINGLE_SOURCE: 60
- NO_SOURCE: 28
- POWERTRAIN_DIFFERS: 18
- VARIANT_NOT_ADDED: 14

## Waiting for you
27 item(s) in `update_rehearsal_resume_2026-11-17_specs/REVIEW_update_rehearsal_resume_2026-11-17_specs.md`. Top of the list:

- M-Honda-elevate (FACELIFT): Honda Elevate: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Mahindra-thar (FACELIFT): Mahindra Thar: CarWale gives launch date 2026-09-22, after the KB's first data for this model (2026-06-25)
- M-Maruti-baleno (FACELIFT): Maruti Suzuki Baleno: CarWale gives launch date 2026-09-05, after the KB's first data for this model (2026-06-22)
- M-Maruti-brezza (FACELIFT): Maruti Suzuki Brezza: CarWale gives launch date 2026-07-24, after the KB's first data for this model (2026-06-22)
- M-Skoda-slavia (FACELIFT): Skoda Slavia: CarWale gives launch date 2026-10-06, after the KB's first data for this model (2026-06-25)
- M-Tata-tigor (DISCONTINUED_CANDIDATE): Tata Tigor: CarWale: not listed, CarDekho: discontinued
- M-Toyota-glanza (FACELIFT): Toyota Glanza: CarWale gives launch date 2026-10-14, after the KB's first data for this model (2026-06-24)
- M-Toyota-hilux (FACELIFT): Toyota Hilux: CarWale gives launch date 2026-07-28, after the KB's first data for this model (2026-06-24)
- R001 (VARIANTS_NOT_LISTED): Mahindra Scorpio-N: 27 KB variants are not in the current listing
- M-Honda-amaze2ndgen (REVIEW_MODEL): Honda Amaze 2nd Gen: name carries a generation marker: new model, or a generation of one the KB has?
- R002 (PRICE_CHANGE): Kia Syros: price_ex_showroom on 15 variant(s) differs from the KB
- R003 (VALUE_CHANGE): Kia Syros: automatic_climate_control on 10 variant(s) differs from the KB

## Gates
Source: `update_rehearsal_resume_2026-11-17_specs/run.json`.

- schema: pass — schema 87b7f560cd53, integrity ok, 297 known orphans
- provenance: pass — 0 of 0 new or changed cells have provenance
- rows: pass — evidence_amendment 686->686; evidence_quarantine 1636->1636; field_provenance 111145->113215
- explained: pass — 2174 changed rows, all in the run log
- reviews: pass — 0 new or changed review rows have provenance
- idempotency re-run: 0 changes

## Cost and runtime
- LLM calls: 0 (none). Cost: Rs 0 (free tier).
- Pages fetched: 0 from the network, 1538 from cache, 0 failed.
- Runtime: 0 minutes.
