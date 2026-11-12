# Needs the owner

Questions and approvals only the owner can give. Each has options and a recommendation. Work continues on everything else.

## Open

### N2. Brezza 821: three cell quarantines predate P8 (G1)
10H quarantined 821's cruise control, HUD and sunroof, with your confirmation. P8 now says an edition with an identity contradiction is "fully held, never partially quarantined".
- **Option A (recommended):** keep them. They hide values whose only evidence is mislinked, and P8 is applied going forward.
- **Option B:** release the three so 821 is fully held as it was.

### N4. Exter editions 815 and 816 show another trim's price (G1)
815 "HX 6 Petrol Manual Dual Tone" sits on base HX 2 and 816 "HX 10 Petrol Automatic Dual Tone" on base HX 3, so the app shows ₹5.80 lakh and ₹6.91 lakh (the KB's own HX 6 Petrol Manual is ₹7.95 lakh, HX 10 Petrol Automatic ₹9.42 lakh). P8 forbids a re-base without brochure evidence naming the trim.
**Checked 2026-11-13 (phase 11N), still held.** The Exter brochure's variant tables (p10 and p11 header) list HX 2, HX 3, HX 4, HX 4+, HX 6, **HX 6 Knight**, HX 8, HX 10 and **HX 10 Knight**. It lists Knight columns, not "HX 6 Dual Tone" or "HX 10 Dual Tone"; its only Dual Tone line is the p11 note "DT-Dual Tone Option is available on select trims". So the brochure does not confirm 815/816 as trims, and nothing was re-based: before and after price are the same (815 ₹5.80 lakh, 816 ₹6.91 lakh).
- **Option A (recommended):** add the Exter price list, or a brochure that names the Dual Tone trims, and re-base from that (P8).
- **Option B:** treat 815/816 as the Knight editions (HX 6 Knight, HX 10 Knight) only if you can confirm that from a source; then re-base to HX 6 and HX 10 and rename.
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

### N3. Out of this goal; need your input or ingestion
- Resuming 10D.
- GNCAP ingestion.
- New brands (Jeep, Citroën, BYD).

## Resolved
### N1. Stray 0-byte ingestion/carrec_kb.db (resolved 2026-11-13)
Owner approved. The file was untracked and git-ignored, 0 bytes, held by no process; deleted from the main checkout.

### N8. P11 side files (resolved 2026-11-12)
Owner decision: a 0-byte `-wal` and a `-shm` are allowed before a write when `lsof` shows no holder; a non-empty `-wal` or any holder still means stop. After every apply: `PRAGMA wal_checkpoint(TRUNCATE)` and confirm the `-wal` is 0 bytes. The files are not deleted. P11 in CLAUDE.md and `write_phase.sh` amended.

### N9. Other fields with large gaps (resolved 2026-11-12)
Owner decision: `fuel_tank_litres` and `drive_modes` join the loop's scope (`GLOSSARY.md`). `drive_modes` follows the absent-is-not-zero rule: unlisted = unknown, never "none".

### N10. Nexon cruise control footnote (resolved 2026-11-12)
Owner decision: keep the 11 cells held (P6, unclear footnote scope). The rest of 11B was applied.

### N11. Seltos (resolved 2026-11-12)
Owner decision: 11C is not applied. Seltos is held entirely under P7 (the brochure prints trims the KB lacks, and the 19 wireless corrections rest on an optional-pack header). Held alongside Brezza, WagonR, Baleno, Jimny and Kylaq.
