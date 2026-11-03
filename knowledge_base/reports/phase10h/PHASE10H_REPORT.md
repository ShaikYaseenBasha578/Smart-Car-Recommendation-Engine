# Phase 10H — resolver mislinks

Date: 2026-11-03. Controlled write authorised by the owner ("go", 2026-11-03), with the read-only
`com.apple.Virtualization.VirtualMachine` holder (PID 4854, FD 2613r) accepted for this write only.

| | SHA-1 |
|---|---|
| Prod before | `52f00fc761a11be5f4763a022fd526e6ea20396d` (= post-10G) |
| Backup | `knowledge_base/backups/pre_phase10h_20261103T112654Z.db` (file `b3e7cae3…`; `.sha3sum` `246a43ba…` == source copy) |
| Prod after | `8074a9dd67829042ba04a16bbe9c5a26702c88c6` |
| Apply script | `knowledge_base/db/migrations/apply_phase10h.py` (`27716e5d…`, the version run on prod) |
| Entry list | `knowledge_base/db/migrations/phase10h_entries.csv` (`f7277c99…`, 661 rows), built by `build_phase10h_entries.py` |

Phases of this work: read-only checkpoint (`PHASE10H_CHECKPOINT.md`), two pre-go rounds (`PRE_GO_2.md`, §3, §6),
then the write. Scripts in `scripts/`; validator material in `validation/`; paper checks in `paper/`.

## 1. Classification [VERIFIED `scripts/classify_links.py` → `links.tsv`, on a byte copy of `52f00fc7`]
Every resolved aggregator observation (1,902: 91wheels, v3cars, CarWale) is compared with its resolved variant and with
every other variant of the same model. The comparison uses the observation's structured fields (fuel, gearbox, engine
cc) and its trim name. For CarWale it uses the payload's own version name, because the stored features describe that
version (see R2).

| Class | n |
|---|---|
| OK | 1,104 |
| MISLINK_TARGET (wrong variant; the KB has the right one, listed per row) | 584 |
| MISLINK_NONE (wrong variant; the KB has no matching variant) | 152 |
| EDITION_NOT_IN_KB (an edition the KB doesn't model, attached to its base) | 56 |
| REVIEW (Fortuner names without a trim ×5; 833) | 6 |

## 2. Root causes [VERIFIED by reading the code; nothing was run]
- **R1, resolver** (`knowledge_base/ingestion/common/resolver.py`):
  - `validate_structured` is the only fuel/gearbox guard, and it does nothing when the caller passes neither. For
    490 of 711 resolved 91wheels observations the payload has no `specs` block and no fuel field.
  - Fuzzy acceptance needs only `score > 0.5` with a 0.05 margin, and identity tokens need only overlap.
  - The observations date from 2026-09-09, before the 10C-2 fix (2026-09-28). 10C-2 fixed CarWale fuel/gearbox
    parsing and verified aliases, but not trim identity or R2.
  - `ingest_91wheels.py:44` unpacks two values from a function that now returns three.
- **R2, CarWale page identity** (`knowledge_base/ingestion/carwale/ingest_carwale.py:68-104`):
  - It resolves on the requested version name but stores the features of the trim page CarWale serves, and never
    compares the two.
  - **470 of 753** resolved CarWale observations carry another version's payload. The payload's
    `ex_showroom_price` is model-level (`modelPriceOverview`), but no provenance row uses it.

## 3. Validation [VERIFIED `validation/judgements.tsv`, joined to `validation/validation_key.tsv`]
A fresh subagent saw only the sample rows (obs, source, model, raw name, CarWale payload name, resolved id and name;
**no class, reasons or targets**) and a DB copy. It judged each case against a written standard.

| Class | Cases | Mislink | Correct | Unclear | Agreement |
|---|---|---|---|---|---|
| MISLINK_TARGET | 20 | 20 | 0 | 0 | 100% |
| MISLINK_NONE, random | 30 | 30 | 0 | 0 | 100% |
| MISLINK_NONE, every no-match obs a Q3 cell depends on (not already sampled) | 13 | 12 | 0 | 1 | 100% of decided |
| EDITION_NOT_IN_KB | 10 | 10 | 0 | 0 | 100% |
| REVIEW (no classifier call) | 6 | 1 (833) | 5 (Fortuner) | 0 | n/a |

The unclear case is obs 3302: Jimny "Zeta Petrol Manual" → 597 "Zeta PRO MT", where every KB Jimny row is "PRO".
Q3 dependency on a no-match observation (`q3_dependency.tsv`): 13 of 46 cells (15 of 48 with the edition
observations). None was judged a correct link. One depends on obs 3302 (v597 cruise_control).

## 4. Write (owner decisions at "go")
Inserts into `evidence_quarantine` only, phase `10H`, 10B-W1 pattern. No re-linking, no DDL, no threshold change.

| Entries | Reason code | n |
|---|---|---|
| Q1 mislinked obs not already quarantined | `H1_RESOLVER_MISLINK` / `H1_RESOLVER_NO_KB_VARIANT` | 442 / 116 |
| Q2 edition-on-base obs | `H1_EDITION_NOT_IN_KB` | 56 |
| Q3 stored canonical cells left with no live evidence | `H1_SOLE_SOURCE_FROM_MISLINK` | 47 |

- **Owner exclusions:** obs 3302 is held out (unclear; Jimny catalogue currency), so v597 cruise_control keeps it as
  evidence and is not in Q3.
- **Brezza 821:** no identity write. Its 3 sole-source feature cells (cruise_control, heads_up_display, sunroof)
  are in Q3; the owner confirmed this. 177 mislinks were already under 10B-W1 B3 quarantines and are untouched.
- **Each note** records the source, the resolved variant, the source's names, the mismatch and (for Q1 TARGET) the
  better target ids.
- **Canonical effect:** 50 cells become NULL. These are the 47 Q3 cells plus 3 that edition 831 inherits from base
  458 (cruise_control, heads_up_display, TPMS), because the view masks an inherited cell when the base cell is
  quarantined.
- **Active quarantines:** 722 → 1,383.

## 5. Dry run, idempotency, prod apply [VERIFIED]
- **Dry run (byte copy):** `COMMITTED; {"inserted": 661, "active": 1383, "canonical_cells_masked": 50}`.
- **Full `EXCEPT` diff** (`dryrun_diff.txt`): schema identical; +661 `evidence_quarantine` rows (equal to the entry
  CSV, field for field) and the sqlite_sequence row; nothing else.
- **In-transaction invariants:**
  - every other table is unchanged row for row;
  - the canonical view changes exactly at the expected 50 cells, each to NULL;
  - no quarantined observation remains in `v_live_evidence`, and no Q3 cell keeps live evidence;
  - 832 variants; integrity ok; 297 FK orphans.
- **Re-run on the post-change copy:** 0 inserts, empty diff.
- **Immediately before the apply:** SHA-1 `52f00fc7…`; the only holder was the accepted VM process (`2613r`); no
  `-wal`/`-shm`.
- **Apply:** the same COMMITTED line as the dry run.
- **After:** `integrity_check` ok, `foreign_key_check` 297, `wal_checkpoint(TRUNCATE)` 0|0|0, new SHA-1 `8074a9dd…`
  (`apply_prod_log.txt`).
- **Prod vs backup** (`prod_vs_backup_diff.txt`): equal to the dry-run diff, timestamps masked. A re-run on a prod
  copy changes nothing.

## 6. Paper v0 impact (frozen snapshot `8592508789594ab76cf98e463bbf77606a76a7e2`) [VERIFIED]
Read-only, on byte copies of the snapshot. The snapshot was still `8592508…`, mode 444, with no side files, before
and after. 10H does not change the snapshot. These findings cover the paper's exposure to the mislinks the snapshot
already contains.

- **Paper-field cells resting solely on mislinked observations** (`scripts/paper_check.py` → `paper/paper_cells.tsv`):
  - Fields checked: body_type, fuel, transmission, seats and price, as `paper/oracle/feasibility.py` reads them.
  - **3 cells, all edition transmissions:**
    - 821 Brezza "Zxi Petrol 1.0L Turbo Manual Dual Tone": Manual (obs 3241/3244/3246);
    - 831 Harrier "Fearless X Dark Edition Diesel 2.0L Turbo Manual": Manual (7 CarWale obs);
    - 832 Nexon EV "Empowered Plus A 45.0 kWh Dark Edition": Automatic (obs 3606/3607).
  - Every other body_type, fuel, seats and price cell has v6 evidence (editions through their base for the
    model-level and powertrain-level fields), and so do the other 826 transmissions.
  - 818, 820 and 833 have edition transmissions with no evidence at all (not mislink-related).
- **Paper files that include editions 821/831/832/833:**
  - `paper/data/catalogue_snapshot.csv`: all four rows; 821 is in the excluded Brezza model.
  - `paper/data/queries_v0.jsonl`: only **F026** (SUV, electric, automatic, ≥5 seats) lists one (832) among its 24
    oracle matches.
  - `paper/data/system_prompts_v0.json`: the G-SUV (821, 831, 832) and G-Sedan (833) grounded tables, where each
    edition is one of several variants in an existing configuration row.
  - No results files exist in the repo.
- **Would a verdict flip if the edition's transmission were unknown** (`scripts/paper_impact.py` →
  `paper/paper_impact.txt`, using the paper oracle on a snapshot copy)? **No.**
  - F026 keeps 23 other non-excluded matches.
  - F025 (SUV, diesel, automatic) and F029 (Sedan, manual) involve 831 and 833 only as candidates that match every
    constraint but transmission. They are feasible controls with 64 and 46 other matches, and carry no budget.
  - No infeasible query has an edition that matches every constraint except transmission.
- **Grounded tables:** removing any one of these editions changes no configuration row and no min–max price, only
  that row's variant count by 1.
- **Engine (821, 833):** not an oracle constraint and not in the grounded-table key, so it decides nothing.

## 7. App
- **Export:** from a prod copy, run twice, identical. `catalogue.csv` SHA-1 `e4bebd77a44734cdf12e4c9e2481ead81581c2fc`,
  byte-equal to the dry-run export; meta `kb_latest_phase` 10H.
- **Field diff vs `main`** (`catalogue_field_diff.txt`, checked by `scripts/catalogue_diff.py` against
  `expected_cells.tsv`):
  - 50 cells on 30 rows become blank: cruise_control 16, mileage_kmpl 7, heads_up_display 7, tpms 7,
    ventilated_front_seats 6, sunroof 4, boot_space_litres 2, adas_available 1;
  - `unverified_fields` gains exactly those columns;
  - nothing else changes.
- **Behaviour and tests:** `pytest -q` 352 passed. The detail API lists the cells under "unverified"; `/predict`
  output contains no NaN.
- **Branch:** `app/kb-10h-export` (f8cf73a), PR https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/18 (not merged).

## 8. Open items after 10H (in CLAUDE.md)
- **Ingestion freeze rule:** no aggregator ingestion or re-ingestion until the resolver fix is merged.
- **Resolver fix:**
  - CarWale page check;
  - trim identity;
  - fuel and gearbox parsing;
  - the `ingest_91wheels.py` crash;
  - the 0-byte `ingestion/carrec_kb.db` and its relative-path cause.
- **Brochure correction** of the 47 Q3 cells.
- **Re-linking** after re-ingestion.
- **Powertrain / edition-identity masking** (needs a view change).
- **Brezza 821**, next to 833.
- **Jimny obs 3302 / v597**, under Jimny catalogue currency.

## 9. Message
KB 10H applied (prod `8074a9dd`): 661 quarantines (558 mislinked observations, 56 edition-on-base, 47 sole-source
cells; 50 canonical cells masked); paper v0 unaffected (no verdict flips); app re-export PR #18.
