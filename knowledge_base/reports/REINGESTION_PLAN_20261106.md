# Re-ingestion and re-linking plan (item 9, GATE G3; nothing run)

**Not started.** P15 needs two things first:
1. The resolver fix (PR #19) merged by the owner.
2. After that merge, a fresh blind subagent finding auto-accept precision ≥98% on a random sample of 50 auto-accepted links, re-links included.

Neither has happened, so no P15 result exists. Network fetches of car data are G3 and need your go even after that.

## What it would do
Offline replay on a copy showed what the fixed resolver would do with the stored 2026-09 observations (`reports/phase10i1c/replay_summary.txt`). Re-ingestion would fetch fresh pages instead.

## Steps, once approved
1. **P15 check, offline, no fetch.** Replay stored observations through the merged code on a copy. Draw 50 auto-accepted links at random, stratified by source. A fresh subagent judges them blind. Stop at <98%.
2. **Fetch into a scratch copy only**, one source at a time, with `--db <copy>`. Pilot one model per source first. CarWale: the page check should now reject mismatches; report the rate.
3. **Verify the copy.** `EXCEPT` diff: only new observations and provenance rows; no canonical value changes (the updater now writes none from aggregators, P2). No new variants.
4. **Blind-validate** a sample of new auto-accepted links (P12).
5. **Apply under P10.** New observations are added; old ones stay.
6. **Re-linking.** No hand re-pointing: correctly linked new observations replace the quarantined ones as evidence. 10H and B3 quarantines stay in place as the record. Release only with a separate check that the observation itself was right.
7. **Corroboration report**, plus review queues (`needs_review`, `edition_candidate`, `page_mismatch`) as a file for you.

## Risks
- Aggregator pages changed since 2026-09, so prices and names may have drifted (catalogue currency).
- 17% of correct links will sit in review, as you accepted.
- 91wheels and v3cars page structures aren't verified against current sites; the ingesters may need fixes.

## Decision needed
See NEEDS_YOU N6.
