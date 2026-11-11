# Needs the owner

Questions and approvals only the owner can give. Each has options and a recommendation. Work continues on everything else.

## Open

### N1. Delete the 0-byte `knowledge_base/ingestion/carrec_kb.db` (G5, deletion)
It is untracked and git-ignored (`knowledge_base/.gitignore:1`), so the code PR can't remove it (decision 6).
- **Option A (recommended):** you delete it after the DB-path fix merges: `rm "knowledge_base/ingestion/carrec_kb.db"`.
- **Option B:** authorise me to delete it.

### N2. Brezza 821: three cell quarantines predate P8 (G1)
10H quarantined 821's cruise control, HUD and sunroof, with your confirmation. P8 now says an edition with an identity contradiction is "fully held, never partially quarantined".
- **Option A (recommended):** keep them. They hide values whose only evidence is mislinked, and P8 is applied going forward.
- **Option B:** release the three so 821 is fully held as it was.

### N4. Exter editions 815 and 816 show another trim's price (G1)
815 "HX 6 Petrol Manual Dual Tone" sits on base HX 2 and 816 "HX 10 Petrol Automatic Dual Tone" on base HX 3, so the app shows ₹5.80 lakh and ₹6.91 lakh (HX 6 is ₹7.95 lakh, HX 10 ₹9.42 lakh). The brochure says only "Dual Tone Option is available on select trims" (p11), so P8 forbids a re-base. P8 (hold) and P5 (a known-wrong value is quarantined) pull in opposite directions. No paper verdict flips.
- **Option A (recommended):** allow a re-base when the edition's own name states the trim and the KB has exactly one such base, as an owner-approved exception to P8 for 815 and 816.
- **Option B:** add the Exter price list or a brochure that names the DT trims.
- **Option C:** keep holding; the wrong prices stay visible.

### N5. Schema proposal batch (G2, P16)
Four changes are proposed in [SCHEMA_PROPOSAL_20261106.md](reports/SCHEMA_PROPOSAL_20261106.md): powertrain-level quarantine, edition identity masking (833, 821, 815, 816), a catalogue-currency mechanism, and new feature fields. Nothing has been applied.
- **Option A (recommended):** approve S1 + S2 now (small, unblock held items), S3 as designed, and S4 for the fields brochures print widely.
- **Option B:** approve S1 + S2 only.
- **Option C:** defer all.

### N6. Resolver fix and re-ingestion (G3, P15)
Merge [PR #19](https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/19) when you're happy with it, then fast-forward is routine. After that I can run the blind P15 check (offline), but fetching car data needs your go. Plan: [REINGESTION_PLAN_20261106.md](reports/REINGESTION_PLAN_20261106.md).
- **Option A (recommended):** merge #19; I run the P15 check; you decide on fetching from its result.
- **Option B:** hold re-ingestion; the aggregator evidence stays as it is, with mislinks quarantined.

### N7. The 297 orphaned provenance rows (G5 if deleted)
They affect no value. See [ORPHANS_PROPOSAL.md](reports/phase10o/ORPHANS_PROPOSAL.md).
- **Option A (recommended):** keep them for now.
- **Option B:** archive and delete them, batched with the schema changes, so `foreign_key_check` becomes clean.

### N8. P11 side files block every write after the first batch (G5, deletion)
After batch 11A the KB folder holds an empty `carrec_kb.db-wal` (0 bytes) and a 32 KB `carrec_kb.db-shm`. No process holds them (`lsof` finds none). This SQLite build (3.54.0) leaves them behind after any open, even a read-only query on a copy, so they come back after every write. P11 requires no `-wal`/`-shm` beside prod, and P17 forbids deleting files without your approval, so batch 2 onward cannot be applied.
- **Option A (recommended):** amend P11: an empty `-wal` plus an `-shm` with no holder is allowed, because an empty WAL means the file hash describes the DB. I keep the SHA-1 recheck and integrity check.
- **Option B:** approve deleting the empty side files when no process holds them, before each write.
- **Option C:** you delete them by hand before each batch.
Until you decide, I keep extracting, validating and dry-running batches on copies, so they are ready to apply in order.

### N9. Other fields with large gaps (proposal, nothing extracted)
Empty cells among the 812 base variants: `drive_modes` 532, `fuel_tank_litres` 87, `connected_car_features` 50, `boot_space_litres` 41 (`claimed_ev_range_km` is empty for non-EV by design). The loop does not touch them.
- **Option A (recommended):** add `drive_modes` and `fuel_tank_litres` to the loop's scope in a later run: both are printed in most brochures' spec tables.
- **Option B:** leave them.

### N3. Out of this goal; need your input or ingestion
- Resuming 10D.
- GNCAP ingestion.
- New brands (Jeep, Citroën, BYD).
