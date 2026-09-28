# Phase 10C-2: CarWale resolver fix (code only)

**Date:** 2026-09-28. **Branch:** kb/phase-10-0-versioning.

**Scope:** code, tests and an offline evaluation.
- **No DB writes, no ingestion, no re-resolution applied.** Production SHA-1 is `df9e2d9b391aa1b50edc42e27ccd63911345adf5`, unchanged before and after.
- Everything was evaluated on a read-only `/tmp` copy. Tests run in memory.

## Root cause (from PHASE10A B3 / PHASE10B0 §6)
1. The CarWale adapter passed `fuel=None, cc=None`. `specs_summary` is never populated, so `map_resolver_fields` returned nothing.
2. `validate_structured` skips any comparison with a null side, so no candidate was ever rejected on fuel.
3. With no `source_name`, `resolve_variant` matches through the **91wheels** alias table.

A fourth bug surfaced while fixing: `validate_structured` classified `AT` as *manual*. It was missing from the automatic list.

## Changes (CarWale path + shared validator only)
| File | Function | Change |
|---|---|---|
| `ingestion/carwale/field_map_carwale.py` | `parse_version_name` (new) | Parses fuel (CNG / Hybrid / Electric / Diesel / Petrol) and transmission (AMT / CVT / DCT / TC / MT / AT) from the version name. Any part that isn't stated comes back as `None`. |
| `ingestion/carwale/ingest_carwale.py` | `resolve_carwale_version` (new) | Parses the name. **Returns `unresolved` if fuel or transmission is unknown.** Otherwise calls `resolve_variant(..., fuel, trans, source_name='carwale')`, which uses only CarWale's own aliases. |
| `ingestion/carwale/ingest_carwale.py` | `ingest_model_pilot` | Replaced the `map_resolver_fields(specs_summary)` + `resolve_variant(...)` block with one call to `resolve_carwale_version`. |
| `ingestion/common/resolver.py` | `validate_structured` | The automatic-transmission set is now one shared constant that includes `at` and `dsg`; previously the source and canonical lists differed. The fuel rule moved into an explicit `FUEL_FAMILIES` table (below). |

**Fuel families.** Before, `cng` matched any canonical value containing `cng`. Now `cng` matches `CNG`, `hybrid` matches `Petrol Hybrid`, and `diesel` matches `Diesel Mild Hybrid`. Everything else must match exactly.

The full before/after diff is in commit history (`git show <commit> -- knowledge_base/ingestion`). The functions changed are:
- `validate_structured`, with its before and after shown in the diff;
- `ingest_model_pilot` (its resolution block);
- two new functions, `parse_version_name` and `resolve_carwale_version`.

Two parsing rules are deliberate and should be reviewed:
- **Electric implies AT.** 45 CarWale names are EVs that state only kWh. All 37 EV variants in the KB are single-speed `Automatic`, so this is a domain rule, not a guess. If rejected, those 45 become `unresolved`.
- **"Smart Hybrid" is Petrol.** This is Maruti's mild hybrid, which the KB stores as `Petrol`. Only "Electric + Petrol", "Strong Hybrid" or e-CVT count as Hybrid, which is `Petrol Hybrid` in the KB.

**Verified-alias override closed (owner-approved follow-up, 2026-09-28).** In `resolve_variant`, an alias with `is_verified=1` used to return `resolved_with_warning` even when it conflicted on fuel or transmission. It is now discarded on a `fuel_mismatch` or `transmission_mismatch` and falls through to exact/fuzzy matching, which are themselves validated. A verified alias whose only warnings are cc/price keeps the old `resolved_with_warning` behaviour. No alias is verified today (0 of 469), so current data is unaffected. Test: `test_verified_alias_fails_closed_on_fuel_or_transmission`. It fails when the guard is reverted and passes with it.

## Tests
- `knowledge_base/tests/test_carwale_resolution.py`, run only by explicit path.
- The fixture `knowledge_base/tests/fixtures/carwale_resolution_fixture.json` was extracted from a `/tmp` copy. It holds the 333 B3 observations, with the variant each must **not** resolve to, plus the 603 variants, powertrains and aliases of the 35 models involved.

| Test group | What it asserts |
|---|---|
| Parser (13 cases) | Fuel and transmission parsing, including the EV and mild-hybrid rules and unparseable names |
| Validator | `AT` counts as automatic; the hybrid and diesel families behave as intended |
| Fail closed | Unparseable names return `unresolved`, and a planted 91wheels alias is not followed |
| 10A examples | obs 2928 ↛ 152, 2858 ↛ 23, 2820 ↛ 647; any result is fuel- and transmission-consistent |
| B3 fixture (332 cases) | Each case never reproduces its bad resolution, and any result or edition base is consistent. obs 3185 is excluded and tested separately: it must still resolve to 820, as the probable false positive from W1 |

- **Result: 354 passed, 0 failed** (353 at the first commit, plus the verified-alias test).
- **Sensitivity check.** Run against the pre-fix behaviour in a `/tmp` package copy (old validator, no parsing, 91wheels alias): **107 failed**.
- The existing resolver tests (`test_v3cars.py`, `test_identity_resolution.py`, `test_resolution_semantic_normalization.py`) all pass: 15 passed.

## Offline evaluation (`carwale_reresolution_eval.csv`, `eval_carwale_reresolution.py`)
- All 753 currently resolved CarWale observations were re-resolved with the new path on a read-only copy.
- Price was not passed, because it isn't stored in the payloads. The live path passes price, which can only add rejections.
- "Flagged" means the 331 `B3_CARWALE_STRUCTURAL_MISMATCH` quarantined observations. "Unflagged" means the other 422, which include the E/EX swap pair 2842/2843.

| Group | Same variant | Different variant | Unresolved | Edition candidate | Still contradicting |
|---|---|---|---|---|---|
| Flagged (331) | 1 (obs 3185) | 160 | 141 | 29 | **0** by fuel/transmission check (2 by the 10A heuristic; see below) |
| Unflagged (422) | 171 | 135 | 111 | 5 | 0 |

- **Flagged, 330 excluding 3185:**
  - **141 now fail closed** as `unresolved`.
  - **29 become edition candidates**, and all 29 bases are consistent on fuel and transmission.
  - **160 re-resolve to a different variant** consistent in fuel and transmission.
  - The 10A token heuristic still flags **2** rows, obs 3339 and 3347 (Victoris "ZXi / ZXi Plus 2WD Hybrid (Electric + Petrol) … e-CVT" → 575 "ZXI+ (O) Strong Hybrid e-CVT"). The heuristic reads "Electric + Petrol" as Electric, which is an artifact: fuel (Petrol Hybrid) and transmission (e-CVT) are consistent. **The trim is still wrong**, though. ZXi should be 570 and ZXi Plus 574. This is a fuzzy-scoring trim error, which this fix does not target.
- **Unflagged regressions** (spec: "fine before, now unresolved or changed"): **251** in total, made of 111 unresolved, 5 edition candidates and 135 changed.
  - **83 of the 135 changes now resolve to the variant whose name exactly matches the raw name.** These are corrections, not regressions. They include the Creta E/EX swap (2842 → 1, 2843 → 2) and several V/SV/VX/ZX swaps.
  - The other 52 changes match neither name exactly and are **UNDETERMINABLE** without review. For example, "ZX Petrol Manual" moved from "ZX MT" to "ZX+ MT", which looks wrong.
  - **The 111 new unresolved** are mostly names like "V Petrol Manual" whose canonical name is "V MT". They were previously matched through the 91wheels alias table. `compute_similarity` cannot bridge "Petrol Manual" and "MT" because its normalisation helper, `get_tokens`, is dead code.
- An experiment, not applied: a CarWale-local retry with fuel and transmission words stripped from the name recovers 42 of the 111 to the same variant as before. It re-resolves 29 others to *different* variants that are unverified. It was left out to keep the fix minimal and fail-closed.

## Owner decisions (2026-09-28)
1. **Option 1 accepted: the coverage loss is accepted.** No CarWale-local retry. The 111 + 5 unflagged observations that no longer resolve stay unresolved under the new code.
2. **The shared `compute_similarity` change is deferred** to its own phase, because it affects every source.
3. **The verified-alias override is closed** (see Changes above).
4. **Policy for any future CarWale re-ingestion:**
   - Only **exact trim matches** are auto-accepted. An exact trim match is a candidate whose canonical name equals the CarWale version name (or its de-hyphenated slug) after passing the fuel/transmission check. This is the resolver's exact-match branch.
   - Everything else goes to **review**, not into canonical data: fuzzy matches, unverified alias matches, edition candidates, and CarWale-alias hits whose name differs.
   - `resolve_variant` currently returns `resolved` for both exact and fuzzy matches. A re-ingestion therefore needs a match-type signal (or an exact-name check in the CarWale path) before it runs. That is a prerequisite, not yet implemented.
   - No CarWale re-ingestion, and no release of B3 quarantines, happens without a separate authorised phase.

## Options considered (historical)
1. Accept the fix as-is. The fuel/transmission errors are eliminated; the cost is coverage (111 + 5 unflagged no longer resolved) and 52 changed resolutions to review.
2. Add the CarWale-local identity-only retry. It stays within the CarWale path: +42 recovered, and 29 changes need review.
3. Approve a shared change to `compute_similarity`: revive `get_tokens` normalisation of manual/automatic to mt/at. This is outside scope because it affects every source.
4. Separately, close the verified-alias override in `resolve_variant`, which is also outside scope.

