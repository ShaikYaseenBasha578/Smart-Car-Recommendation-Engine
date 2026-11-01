# Phase 10C — closure record

- **Status:** CLOSED. Recorded 2026-11-02.
- **Owner decision (verbatim):** "Close 10C; the spot-check confirms OEM trust".
- **DB effect:** none. No write was made or authorised by this closure.

## What the decision rests on
- **Spot-check results** (`knowledge_base/reports/phase10c/OEM_SPOTCHECK_RESULTS.md`, commit `b84444c`):
  - CONFIRMED_SAMPLED: 20/20 correct (Wilson 95% CI 83.9–100%).
  - REJECTED_WOULD_FLIP: 21/28 correct. The 7 wrong rows are 5 `symbol_not_normalised` (rows 9, 12, 26–28) and 2 `value_wrong` (rows 24, 25).
  - ACCEPTED: 1/1 correct.
- **The verified corrections were applied by Phase 10B W6** (12 cells; 10 held under CATALOG_CURRENCY). The 10C/10D audit (`REPORT.md` §1.3) verified that write as complete and consistent.

## What the decision settles
- **The OEM brochure source is trusted as corroborating evidence.** The Phase 10B W4 "+1 corroboration on 99 cells" is **no longer provisional**.
- **`CLAUDE.md:35` is stale and should be corrected in 10E B6.** Proposed replacement for its two 10C clauses:
  - Old: "OEM extraction quality pending spot-check (W4 +1 corroboration on 99 cells is provisional); CarWale resolver code fix required before any CarWale re-ingestion."
  - New: "OEM extraction spot-checked in Phase 10C-1 (closed 2026-11-02; W4 corroboration confirmed). CarWale resolver code fixed in 10C-2; before any CarWale re-ingestion a match-type signal is still required (PHASE10C2_RESOLVER_FIX.md)."

## What it does not settle (no action implied)
- **No OEM re-tiering, and no flip of the 28 rejected OEM rows.** The README ties re-tiering to the rejected stratum, which was 21/28 correct, and 7 of those values are known-wrong. Re-tiering would need its own approved controlled write.
- **Carried forward to future phases:**
  - the CarWale match-type prerequisite;
  - the deferred `compute_similarity` change;
  - the V3Cars resolver audit (W6 report item 4).

## Where this lives
- **Written only in scratch.** The main checkout (`paper/v0`) and every worktree were not touched, and no git command was run.
- **10E B6 applies it.** The CLAUDE.md line change above should land there, and this record should be committed to `knowledge_base/reports/phase10c/` on the 10E `kb/*` branch.
