# The 297 orphaned field_provenance rows: proposal (item 10; nothing changed)

Read-only on a copy of prod `acf32b47…`; `orphans.py`, full list in `orphans.tsv`.

## What they are [VERIFIED]
- 297 rows point to 41 observation ids in 2608–2661 that no longer exist. All were decided on 2026-09-09: the CarWale pilot observations were deleted that day, by hand, and their provenance rows stayed.
- 23 variants: Harrier 109, Creta 80, Kushaq 76, Verna 32.
- Decisions: 212 confirmed, 79 rejected, 6 accepted.
- None is quarantined, and none counts as evidence: `v_live_evidence` inner-joins the observation, so `v_corroboration` never sees them.
- 4 of the 6 accepted rows still equal the canonical value, and each has other live evidence. So **no canonical value depends on an orphan**.

## Harm today
None to reads. Their only effect: `foreign_key_check` is never clean (always 297), so every write has to allow that exact number, and a new real orphan would have to be noticed by count.

## Options
| Option | Change | For | Against |
|---|---|---|---|
| **A. Keep as they are (recommended for now)** | none | zero risk; they are evidence of what happened on 2026-09-09 | `foreign_key_check` stays at 297 |
| B. Archive, then delete | copy to a new table, then delete; `foreign_key_check` becomes 0 | clean integrity checks; any new orphan is immediately visible | needs DDL (P16) and a deletion (P17, G5), and removes them from the table CLAUDE.md says never to touch |
| C. Quarantine them all | 297 rows in `evidence_quarantine` | marks them explicitly | changes nothing functionally; `foreign_key_check` still 297 |

**Recommendation:** A now. B is the right eventual clean-up, batched with the schema proposals if you want it. It needs your approval (NEEDS_YOU N7).
