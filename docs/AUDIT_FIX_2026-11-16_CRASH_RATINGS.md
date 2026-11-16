# Crash ratings missing for eight models (audit 2026-11-16, finding 2)

## Diagnosis: the KB lacks the links; the exporter is correct

Checked on the read-only copy `/tmp/carrec_audit/blind/kb_copy.db` only; nothing was written to any database.

- `scripts/export_catalogue_from_kb.py` reads `v_safety_applicability_q` joined to `safety_test`, keeping only tests whose
  `v_safety_test_status.canonical_status = 'resolved_model'`. That is the rule it documents, and it is the right one.
- Re-exporting from the copy gives a `catalogue.csv` that is byte-identical to the shipped `data/catalogue_v3/catalogue.csv`
  (0 differing cells over 1,464 rows), so the export is faithful to the KB.
- For models 78, 80, 85, 86, 87, 88, 89, 90 (XEV 9e, Tekton, Curvv, Curvv EV, Harrier EV, Punch, Safari, Sierra) there is no row
  in `safety_test_applicability` at all (Safari is the exception in the test, not the table: see below). Their tests were ingested
  on 2026-09-23 with `resolution_status = 'NO_MATCH'` ("not in CarRec top-62"), and the models were added to the `model` table
  on 2026-11-13. Nobody re-ran the match.

So the site is right to say there is no rating linked. The wording "No Bharat NCAP rating on record" (now "No crash-test rating on
record") is accurate about the KB, which holds a test that is not linked. I did not change it to "rating not yet linked": that
would need the exporter to guess a link by name, which is exactly what must not be surfaced without the owner's decision.

What changed in code: the exporter now prints a WARNING for every test that is not linked although its title names a model in
the `model` table (`unlinked_safety_tests`), so this cannot go unnoticed again. On the copy it lists tests 10, 21, 25, 26, 27, 32, 34.
No catalogue value changed.

## Rows the owner would need (NOT applied)

All tests: source `bharat_ncap` (source id 7), protocol AIS-197, `aop_stars` 5, `cop_stars` 5 (Curvv, Curvv EV, Harrier EV, XEV 9e,
Sierra, Punch, Tekton all 5/5 in the stored fields). `v_safety_test_status` maps `NO_MATCH` to `no_match`, which
`v_safety_applicability_q` hides, so each test also needs `resolution_status` set to `RESOLVED` (with a justification) before the
exporter will surface it. Existing rows use `match_confidence = 'MODEL_LEVEL'`, `variant_id` NULL.

| model (id) | safety_test id | raw_source_url | tested name / variants (stored) | proposed applicability row | caveat |
|---|---|---|---|---|---|
| XEV 9e (78) | 10 | bncap.in/vehicle/mahindra-xev-9e/ | MAHINDRA - XEV 9e - THREE B79 | (10, manufacturer 5, model 78, generation 78, MODEL_LEVEL) | none found |
| Curvv (85) | 26 | bncap.in/vehicle/tata-curvv/ | TATA - CURVV - ACCOM + A DMT | (26, 10, 85, 85, MODEL_LEVEL) | none found |
| Curvv EV (86) | 25 | bncap.in/vehicle/tata-curvv-ev/ | TATA - CURVV.EV - EMP + A 55 | (25, 10, 86, 86, MODEL_LEVEL) | none found |
| Harrier EV (87) | 27 | bncap.in/vehicle/tata-harrier-ev/ | TATA - HARRIER.EV - EMP 75 & EMP 75 AWD | (27, 10, 87, 87, MODEL_LEVEL) | justification already says "Matched manufacturer and model systematically" |
| Sierra (90) | 34 | bncap.in/vehicle/tata-sierra/ | TATA - SIERRA - ACCOMP+ & ADV+ [CRAIL MT] | (34, 10, 90, 90, MODEL_LEVEL) | tested variants are the listed ones; model-level is the convention used for the other BNCAP rows |
| Safari (89) | 33 (already RESOLVED, linked to Harrier 30 FAMILY_LEVEL) | bncap.in/vehicle/tata-safari-harrier/ (title "TATA SAFARI/ HARRIER") | TATA - SAFARI/ HARRIER - ADV+ | (33, 10, 89, 89, FAMILY_LEVEL) with the justification the test already carries ("BNCAP page explicitly covers Harrier AND Safari as one test") | the only row needed is the Safari applicability; no status change |
| Punch (88) | 32 | bncap.in/vehicle/tata-punch/ | TATA - PUNCH - PURE+ CNG AMT & ACCOMP CNG MT (2026) | NOT proposed as MODEL_LEVEL | the stored variant list names only two CNG variants; the stored fields do not establish that the rating covers the petrol Punch. Owner decision: variant-level rows, or confirm on the BNCAP page that the 2026 test covers the whole model |
| Tekton (80) | 21 | bncap.in/vehicle/nissan-tekton/ | title NISSAN - TEKTON, but `tested_variant_config` reads "RENAULT - DUSTER - EVOLUTION (1.3L MT), TECHNO (1.3L DCT) & ICONIC (1.3L MT)" | NOT proposed | the stored title and variant list disagree (the variants are named Duster). Check the BNCAP page; the KB's own Duster (model 55) is already linked to test 22 |

Template for an owner-approved write (one transaction, per the KB policy; example for XEV 9e):

```sql
UPDATE safety_test SET resolution_status='RESOLVED',
  resolution_justification='Model added to KB 2026-11-13; BNCAP title names it exactly (owner-approved re-resolve)'
  WHERE id=10;
INSERT INTO safety_test_applicability (safety_test_id, manufacturer_id, model_id, generation_id, match_confidence, notes)
  VALUES (10, 5, 78, 78, 'MODEL_LEVEL', 'Re-resolved after model was added');
```

After such a write, re-export (`scripts/export_catalogue_from_kb.py --kb <copy>`); only these models' four safety columns should change.
