# Stage 2 — History (git + non-git)

## Git
- [VERIFIED] 14 commits, 2026-06-04 → 2026-07-28. None touch `knowledge_base/`, `scratch/`, BNCAP, or provenance tables — the KB did not exist in git at any commit (`git ls-files knowledge_base scratch` = 0).
- KB-adjacent commits (CSV-era pipeline, not the SQLite KB): `bbd28a5`/`fcb949c` (2026-06-21) add `scraping/` enrichment framework incl. `scraping/enrichment/provenance.py`, CarWale fetcher; `564e346` (06-24) + `7f0383b` (07-28) add/modify `scripts/build_hybrid_working_dataset.py` and `datasets/`. All of `scraping/`, `datasets/`, `README.md` are now deleted in the working tree (uncommitted).
- **Therefore no KB mutation can be attributed to a commit.** Everything below is from file mtimes/hashes [VERIFIED (mtime)] and reports [REPORTED-ONLY]; causal links are INFERENCE.

## Reconstructed KB timeline (times IST as shown by `ls`; DB timestamps are UTC)
| When | Event | Evidence |
|---|---|---|
| 06-19..06-28 | V6 CSV migration: 812 variants, 812 obs, 24,955 provenance | `observed_at` of v6_migration obs [VERIFIED] |
| 09-09 18:09–18:23 | 91wheels crawl (obs 813–1657) | observed_at 12:39–12:53 UTC [VERIFIED]; batch_state.json mtime |
| 09-09 ~18:5x | V3Cars crawl (obs 1763–2607). **Obs 1658–1762 (105) and prov 27840–28383 (544) deleted, cleanly (no orphans)** — probably a V3Cars first attempt | id-gap analysis on pre_phase5 copy [VERIFIED gaps; cause INFERENCE] |
| 09-09 19:35–20:03 | CarWale pilot: obs 2608–2808 created, prov 31888–32514, variant 813 (edition) created | orphan decided_at 14:05–14:33 UTC; sqlite_sequence in pre_phase5 copy: variant=813, obs=2808, prov=32514 [VERIFIED] |
| 09-09 ~20:03–20:54 | Pilot obs 2608–2808 deleted, variant 813 deleted, prov 32185–32514 deleted, **prov 31888–32184 (297) left orphaned** | pre_phase5 copy already contains the 297 orphans [VERIFIED]. Matching code: `run_mini_pilot.py:8-11` (DELETE Harrier CarWale prov+obs, DELETE all edition variants) and `test_debug.py:10-11` (DELETE one Harrier obs, no prov cleanup) [VERIFIED code]. No script deletes Verna/Creta/Kushaq obs → manual/ad-hoc deletion [INFERENCE, agrees with PHASE9A §4] |
| 09-09 20:54 | backup `pre_phase5_carwale.sqlite` (f604994b) — **named "pre-CarWale" but taken after the pilot+deletion** | [VERIFIED] |
| 09-09 20:55–21:17 | CarWale full crawl (obs 2809–3668; 20 edition variants 814–833) | observed_at 15:25–15:47 UTC [VERIFIED] |
| 09-12 01:30 | scratch/carrec_kb_production_backup.db (6ea3b931) | mtime [VERIFIED] |
| 09-12 01:40 | First OEM production → fa4b985b (3414 obs, 36319 prov) | scratch/post_db_hash.txt [REPORTED-ONLY (subagent)], snapshot counts [VERIFIED] |
| 09-12 02:01–02:22 | Forensic snapshot, then prod restored to 6ea3b931 — **no restore script exists** (manual shell) | PHASE6_OEM_INGESTION_RECOVERY_REPORT [REPORTED-ONLY] |
| 09-13 ~23:47 | Controlled OEM production → e752ebde (+52 obs under source_id=1, +133 prov) | PHASE6_OEM_CONTROLLED_PRODUCTION_REPORT [REPORTED-ONLY]; counts [VERIFIED] |
| 09-23 21:02–21:04 | Phase 8 BNCAP production → 6cc95a6e (+37 obs, +37 tests, **+324 applicability** incl. 291 EXPLICIT_SOURCE_VARIANT_UNRESOLVED) | PHASE8_BHARAT_NCAP_PRODUCTION_REPORT [REPORTED-ONLY]; scratch/carrec_kb_idemp.db = 6cc95a6e with 324 applic [VERIFIED] |
| 09-23 21:0x–21:33 | **Undocumented revert** of Phase 8 back to e752ebde | phase8b_backup.db (21:33) == pre_phase8 backup hash [VERIFIED]; no report mentions a revert (grep for 324/6cc95a6e/restore) [VERIFIED absence] |
| 09-23 ~21:38 | Phase 8B production → c1e0647c (+37 obs, +37 tests, +20 applic) | phase8b_prod_ingestion.py mtime 21:38; report [REPORTED-ONLY]; diff pre/post copies [VERIFIED] |
| 09-25 | Phase 8B closeout report + Phase 9 audit | mtimes |
| 09-26 03:30 | backup phase9b (c1e0647c); Phase 9B applied → 1e3eb679 at 03:31 | [VERIFIED] |
| 09-26 03:30–03:53 → 09-27 | DB Browser for SQLite holding prod open rw with a 6-frame WAL | stage_0 [VERIFIED] |

## Scripts that plausibly caused historical mutations
- CarWale orphaning: `run_mini_pilot.py`, `test_debug.py` (root, untracked) + unscripted deletes [code VERIFIED; attribution INFERENCE].
- Phase 6 restore and Phase 8 revert: no script — manual file copy [INFERENCE from absence].
- `scratch/production_ingestion_controlled.py:236,338` can `shutil.copy2(BACKUP_DB, PROD_DB)` [VERIFIED] (without removing -wal/-shm — a stale WAL could be replayed over the restored file).

Checksum gate: `1e3eb679…` ✔
