# Phase 10G — items held in 10F

Date: 2026-11-03. Controlled write authorised by the owner ("go", 2026-11-03), with the read-only
`com.apple.Virtualization.VirtualMachine` holder (PID 4854, FD 2613r) accepted for this write only.

| | SHA-1 |
|---|---|
| Prod before | `dedefb537ce36cec5e422c6688a3a85373030b39` (= post-10F) |
| Backup | `knowledge_base/backups/pre_phase10g_20261103T105041Z.db` (file `e66ba047…`; `.sha3sum` `900bc10b…` == source copy) |
| Prod after | `52f00fc761a11be5f4763a022fd526e6ea20396d` |
| Apply script | `knowledge_base/db/migrations/apply_phase10g.py` (`e1a6b231…`, the version run on prod) |

## 1. Checkpoint (read-only)
Full table: `PHASE10G_CHECKPOINT.md`. No brochure on disk is newer than 2026-09-10, so no held item had new OEM
evidence. Every held value has a single source, the v6 migration [VERIFIED `q_held.py` → `q_held.txt`, on a byte copy]. Re-checks of
the 10F brochure claims:

- Victoris p16: the strong-hybrid column prints engine 68 kW and motor 59 kW, with no system total. "74 kW (100.6 Ps)"
  is the CNG car's petrol-mode figure [VERIFIED, positioned text layer, PDF `94f94973…`].
- Grand Vitara p15: no CNG column; the system total is 85 kW [115.56 PS] [VERIFIED, PDF `023ce2e3…`].
- Exter: no km/kg on any of 14 pages; Nexon p39 points to the separate iCNG brochure [VERIFIED].

## 2. Pre-go checks requested by the owner
**Journal mode** [VERIFIED, file header bytes 18–19, read without opening]: WAL for prod, the pre-10F backup, the
pre-10E backup, the pre-W6 backup and the paper snapshot. Nothing changed at 10F. Side note: the pre-W6 backup has an
empty `-wal` and a `-shm` dated 2026-09-29 06:25, from someone opening it then; left untouched.

**Resolver mislinks**: see `MISLINK_REPORT.md` (scripts in `mislinks/`). Summary [VERIFIED on a byte copy of `dedefb53`;
the trace is identical on post-10G prod]:
- price: no cell; all 812 price provenance rows are v6_migration;
- named mislinks (Nexon 885/888/897, Exter 1966–1977 → 655): no canonical cell depends on them;
- 30 canonical cells depend on a real mislink (fuel, gearbox or trim) and 4 on an ambiguous one. 4 of the 30 are
  AT mileage on MT variants: Dzire 237 25.71, Baleno 252 22.94, Amaze 293 19.46, Ertiga 210 20.3;
- 116 corroboration counts would drop if those observations were excluded.
No write; listed as an open item.

## 3. Write (owner decisions)
| Target | Change | Amendment |
|---|---|---|
| powertrain 84 (Grand Vitara CNG; 548, 549) | power_bhp 87.8 → NULL; description `1462cc 87.8bhp CNG` → `1462cc CNG` | 126, 127 |
| powertrain 88 (Victoris strong hybrid; 567, 570, 571, 574, 575) | power_bhp 115.6 → NULL; description `1490cc 115.6bhp Petrol Hybrid` → `1490cc Petrol Hybrid` | 128, 129 |

Reason code `PS_AS_BHP_NO_OEM_SOURCE`, phase `10G`. Both values were PS figures labelled bhp, and neither model's own
brochure prints the figure. `evidence_quarantine` cannot target `powertrain`, so NULL is the only no-DDL way to
show "unverified". The description is updated because it embeds the same figure, and nothing reads it (the exporter
does not). The v6 observations (548/549, 567/570/571/574/575) are unchanged. These variants have no `power_bhp`
field_provenance rows.

**833: untouched.** Its transmission can be quarantined, but `v_variant_canonical_q` passes `powertrain_id` through
unmasked, so masking the powertrain needs a view change (DDL). Under the owner's rule, if a schema change would be
needed, 833 is left as is. The script asserts that the 833 row is unchanged.

## 4. Dry run and idempotency [VERIFIED]
On a byte copy: `COMMITTED; {"update": 2, "amend": 4}`. Full `EXCEPT` diff (`dryrun_diff.txt`): schema identical,
10 differing rows (2 powertrain rows each way, 4 new amendments, sqlite_sequence). A re-run on the post-change copy:
0 updates, and the diff is empty. In-transaction invariants: no other table or row changed, schema unchanged,
`v_variant_canonical_q` identical, 832 variants, 2 NULL powers, 722 active quarantines, 833 unchanged,
integrity ok, and only the 297 known FK orphans.

## 5. Prod apply [VERIFIED `apply_prod_log.txt`]
Immediately before the apply: SHA-1 `dedefb53…`, the only holder the accepted VM process (`2613r`), no `-wal`/`-shm`.
`COMMITTED; {"update": 2, "amend": 4}`. After: `integrity_check` ok, `foreign_key_check` 297,
`wal_checkpoint(TRUNCATE)` 0|0|0, new SHA-1 `52f00fc7…`. The prod-vs-backup `EXCEPT` diff
(`prod_vs_backup_diff.txt`) equals the dry-run diff once timestamps are masked. A re-run on a prod copy changes
nothing.

## 6. App
- Export from a prod copy, run twice, identical: `catalogue.csv` SHA-1 `a3d75befeb7997c26f8668942240fbf8db24ae48`,
  byte-equal to the dry-run export; meta `kb_latest_phase` 10G.
- Field diff vs `main` (`catalogue_field_diff.txt`): `power_bhp` '' on 548, 549, 567, 570, 571, 574, 575, and
  `power_bhp` added to `unverified_fields` on the same 7 rows. Nothing else.
- Behaviour with a NULL power (`app_probe.txt`): the detail API shows Power `unverified` with no value; pages return
  200; `/predict` returns these cars with `Power: null`, with no 0 and no NaN in the JSON; the summary drops the
  unknown from its bhp range. The ranking engine scores an unknown power as 0 (`safe_num`) for use-case points only.
  `twins.py` drops these rows from engine matching. The same queries on `main` give the same result sets, apart
  from the Power value.
- `pytest -q`: 352 passed (the full app suite).
- Branch `app/kb-10g-export` (4726a48), PR https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/17 (not merged).

## 7. Open items after 10G (in CLAUDE.md)
Powertrain-level quarantine (needs DDL); the resolver mislinks; the Nexon iCNG brochure; Exter km/kg; 833 held
pending an OEM source; Grand Vitara 548/549 km/kg unverified (unchanged owner decision); WagonR 225 with Baleno
(CATALOG_CURRENCY).

## 8. Message
KB 10G applied (prod `52f00fc7`): Grand Vitara CNG and Victoris hybrid power → NULL/unverified; 833 untouched
(DDL needed); app re-export PR #17.
