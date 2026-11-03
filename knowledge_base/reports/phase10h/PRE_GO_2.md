# Phase 10H pre-go checks (2026-11-03), read-only

## Validator (blind subagent; saw sample rows without class/reasons/targets, plus a DB copy)
Files: phase10h_validation/sample.tsv, sample2.tsv, judgements.tsv; key: phase10h/validation_key.tsv.
| Class | Sample | Validator: mislink | correct | unclear | Agreement |
|---|---|---|---|---|---|
| MISLINK_TARGET | 20 | 20 | 0 | 0 | 100% |
| MISLINK_NONE (batch 1, random) | 30 | 30 | 0 | 0 | 100% |
| MISLINK_NONE (batch 2, every no-match obs a Q3 cell depends on, not already sampled) | 13 | 12 | 0 | 1 (obs 3302, Jimny "Zeta" vs "Zeta PRO") | 100% of decided |
| EDITION_NOT_IN_KB | 10 | 10 | 0 | 0 | 100% |
| REVIEW (no classifier call) | 6 | 1 (833) | 5 (Fortuner) | 0 | n/a |

## Q3 cells depending on a no-match quarantine (q3_dependency.tsv)
13 of 46 (15 of 48 with Q2). None was judged a correct link. One depends on the unclear obs 3302: v597 cruise_control
(its other evidence, obs 1331 "Zeta Pro AT", is a gearbox mislink).

## Paper snapshot (8592508, copy) — paper_check.py, paper_impact.py
- Cells resting solely on mislinked observations: 3, all edition transmissions: 821 Manual, 831 Manual, 832 Automatic.
- Paper files that include 821/831/832/833: catalogue_snapshot.csv (all four rows; 821 model_excluded=1);
  queries_v0.jsonl: F026 lists 832 among its 24 oracle matches; system_prompts_v0.json: G-SUV (821, 831, 832) and
  G-Sedan (833) grounded tables, where each edition is one of several variants in an existing configuration row.
  No results files exist in the repo.
- Verdict flips if the transmission were unknown: none.
  - F026 (SUV, electric, automatic, ≥5 seats): 23 other non-excluded matches remain.
  - F025 (SUV, diesel, automatic) and F029 (Sedan, manual) involve 831 / 833 only as "all but transmission"
    candidates. They are feasible controls with 64 / 46 other matches; none carries a budget.
  - No infeasible query has an edition matching every constraint but transmission.
- Grounded tables: removing any one edition changes no configuration row and no min–max price, only that row's
  n_variants by 1.
- Engine (821, 833): not an oracle constraint and not in the grounded table key, so it decides nothing.
