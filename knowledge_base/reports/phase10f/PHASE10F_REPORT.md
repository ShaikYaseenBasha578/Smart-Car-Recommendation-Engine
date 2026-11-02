# Phase 10F — KB unit and mislabel corrections

**Status: APPLIED to prod** (2026-11-02T09:19:25Z) and verified.

**Prod SHA-1:** `57f31e4d4a5f1f01b4a12e1c0d2e507795953cfe` → **`dedefb537ce36cec5e422c6688a3a85373030b39`**.

Files (scratch: `~/carrec_kb_scratch/phase10f/`; committed copies on `kb/10f-units`):
- **Write script:** `apply_phase10f.py`, SHA-1 `87de663c8a2e12167a917d2f89688cac894e70e8`, run on prod. The checkpoint version is kept as `apply_phase10f.v1.py`.
- **Verifier:** `verify_phase10f.py`.
- **Verification outputs:** `verify_dryrun2.md` (final dry run) and `verify_prod.md` (prod). Their bodies are identical.
  - The checkpoint dry runs are `verify_dryrun.md` and `verify_dryrun_gv.md`; both were superseded by the owner's edits.
- **Scans:** `power_scan.txt` (before the change) and `power_scan_prod.txt` (after it).
- **Evidence and logs:**
  - brochure evidence: `render/`, `ocrpages/`, `ocr_all.tsv`;
  - logs: `access_step0.txt`, `access_checkpoint.txt`, `backup_log.txt`, `apply_prod_log.txt`, `lsof_pre_apply.txt`.

## 0. Access

**Step 0 (09:03:45Z)** [VERIFIED `access_step0.txt`]
- SHA-1 `57f31e4d…`; no `-wal` or `-shm`.
- The only holder was `com.apple.Virtualization.VirtualMachine`, PID 4854, FD `2613r` (read-only), which CLAUDE.md allows for a read.
- Scratch copy `prod/carrec_kb.db` (chmod 444): its SHA-1 is identical to prod's.

**Checkpoint (09:12:35Z)** [VERIFIED `access_checkpoint.txt`]: the same holder, and the same SHA-1.

**Owner decision at "go"** (verbatim): "I accept the read-only com.apple.Virtualization.VirtualMachine holder for this write."

**Before the apply (09:19:24Z)** [VERIFIED `apply_prod_log.txt`, `lsof_pre_apply.txt`]
- SHA-1 `57f31e4d…`; no side files.
- The only holder was that accepted one (`2613r`).
- The guard aborts on any other holder, side file or SHA mismatch.

**After the apply (09:19:25Z)**
- `integrity_check` = ok; `foreign_key_check` = 297.
- `wal_checkpoint(TRUNCATE)` = `0|0|0`; no side files.
- SHA-1 `dedefb53…`.
- The same VM holder is still present, read-only.

**Backup** [VERIFIED `backup_log.txt`]
- File: `knowledge_base/backups/pre_phase10f_20261102T091906Z.db`, SHA-1 `8e50fbe7…`.
- Made with `.backup` from the verified byte copy, as in 10E.
- Its `.sha3sum` `170eb4b55ad1315ea5b0cc4c7008860a5887c3c31f05fca5540d771b` equals that of the source (prod at `57f31e4d`).
- It is git-ignored (`.gitignore:270 *.db`).

## 1. Scope A — PS stored as bhp (FIXED: 16 powertrains, 80 base variants)

How the brochure cells were checked:
- Every cited cell was rendered and visually confirmed (`render/`).
- The S-Presso and Alto K10 pages are image-only, so they were OCR'd and then confirmed from crops.
- Taisor p14 carries the power text only in its text layer; the rendered page shows a graphic there. So p21 is cited, which is visually confirmed.

Target: hp = kW × 1.34102, 2 dp, rounded half-up. The Duster prints only PS, so its target is PS × 0.98632.

| pt | Model | Fuel/cc | Before | Brochure (page) | After | Base variants (provenance rows) | Editions (shared row, not written) |
|---|---|---|---|---|---|---|---|
| 70 | Urban Cruiser Taisor | Petrol 1197 | 89.7 | 66 kW (p21) | 88.51 | 485, 487–490 | — |
| 71 | Urban Cruiser Taisor | CNG 1197 | 77.5 | 57 kW (p21) | 76.44 | 486 | — |
| 72 | Urban Cruiser Taisor | Petrol 998 T | 100.1 | 73.6 kW (p21) | 98.70 | 491–494 | — |
| 73 | Fronx | Petrol 1197 | 89.7 | 66 kW (p19) | 88.51 | 495, 497, 498, 500, 501 | — |
| 74 | Fronx | CNG 1197 | 77.5 | 57 kW (p19) | 76.44 | 496, 499 | — |
| 75 | Fronx | Petrol 998 T | 100.1 | 73.6 kW (p19) | 98.70 | 502–506 | 822 |
| 77 | S-Presso | CNG 998 | 56.7 | CNG mode 41.7 kW (p5, image) | 55.92 | 510, 513 | — |
| 79 | Alto K10 | CNG 998 | 56.7 | CNG mode 41.7 kW (p5, image) | 55.92 | 518, 521 | — |
| 80 | Urban Cruiser Hyryder | Petrol 1462 | 103.1 | 75.8 kW (p14) | 101.65 | 523–525, 529, 530, 532–534 | — |
| 81 | Urban Cruiser Hyryder | CNG 1462 | 87.8 | CNG mode 64.6 kW (p14) | 86.63 | 526, 528 | — |
| 82 | Urban Cruiser Hyryder | Petrol Hybrid 1490 | 115.6 | total system 85 kW (p14) | 113.99 | 527, 531, 535 | — |
| 83 | Grand Vitara | Petrol 1462 | 103.1 | 75.8 kW (p15) | 101.65 | 536–547 | 823 |
| 85 | Grand Vitara | Petrol Hybrid 1490 | 115.6 | total system 85 kW (p15) | 113.99 | 550–554 | — |
| 86 | Victoris | Petrol 1462 | 103.1 | 75.8 kW (p16) | 101.65 | 555, 557, 559–561, 563–566, 568, 569, 572, 573 | 825 |
| 87 | Victoris | CNG 1462 | 87.8 | CNG mode 64.6 kW (p16) | 86.63 | 556, 558, 562 | — |
| 117 | Duster | Petrol 1333 | 163.0 | "163 @ 5250" ps only (p20, also p9) | 160.77 | 707–710, 712–715 | — |

**What was written for each powertrain:**
- `power_bhp` and `description` (only the figure changes) + 2 `evidence_amendment` rows (`OEM_UNIT_PS_AS_BHP`).
- One OEM `source_observation` + `field_provenance(power_bhp)` per base variant. The payload carries the PDF path, SHA-1, page, printed text and conversion.

Notes:
- No v6 power provenance existed, so nothing was quarantined.
- Hybrids 82 and 85 keep total-system output, converted to hp.

**Torque (report-only):** all 16 match their brochures except GV pt 83 and Victoris pt 86. Both hold 136.8 Nm; their brochures print 139 @ 4300 (GV p15, Victoris p16). 136.8 is the Hyryder figure.

### Reconciliation of Pass A §8

**Table (b)** (Pass A: "20 powertrains"; the table lists 17 ids):

| pt | Model | Outcome | Reason |
|---|---|---|---|
| 68 | Glanza petrol | FIXED (10E) | 89.7 → 88.51 in Phase 10E |
| 70, 71, 72 | Taisor | FIXED (10F) | §1 |
| 73, 74, 75 | Fronx | FIXED (10F) | §1 |
| 80, 81, 82 | Hyryder | FIXED (10F) | §1 |
| 83, 85 | Grand Vitara petrol, hybrid | FIXED (10F) | §1 |
| 84 | Grand Vitara CNG | **NEEDS_HUMAN** | The GV brochure has no CNG data; 87.8 is unconfirmed (open item) |
| 86, 87 | Victoris petrol, CNG | FIXED (10F) | §1 |
| 117 | Duster 1333 | FIXED (10F) | PS only printed: 163 × 0.98632 = 160.77 |
| 77, 79 | S-Presso, Alto K10 CNG | FIXED (10F) | Image brochures OCR'd: CNG mode 41.7 kW |

**Table (a)** engine-group members not covered above:

| pt | Model, fuel, value | Outcome | Reason |
|---|---|---|---|
| 28 | WagonR CNG 55.92 | FALSE_POSITIVE | = 41.7 kW × 1.34102 (WagonR brochure p5 prints 41.7 kW / 56.6 PS): already hp |
| 27 | WagonR petrol 64.37 | FALSE_POSITIVE (for PS-as-bhp) | 64.37 = 48 kW in hp, not a PS figure. The brochure prints 50.4 kW → stale, CATALOG_CURRENCY (report-only) |
| 76, 78 | S-Presso, Alto K10 petrol 65.7 | FALSE_POSITIVE (for PS-as-bhp) | 65.7 = 49 kW in hp, not PS. Their brochures print 50.4 kW → stale, CATALOG_CURRENCY (report-only) |
| 35, 36 | Baleno petrol 88.51, CNG 76.44 | FALSE_POSITIVE | = 66 / 57 kW × 1.34102: already hp (the Baleno brochure is post-facelift, W6 CATALOG_CURRENCY) |
| 69 | Glanza CNG 76.4 | FALSE_POSITIVE | ≈ 57 kW × 1.34102 = 76.44 (hp, rounded); the PS figure would be 77.5 [INFERENCE: Glanza CNG power line not rendered] |
| 16, 24, 26, 93 | Brezza, Ertiga, XL6 CNG 86.63; Rumion CNG 86.6 | FALSE_POSITIVE | = 64.6 kW × 1.34102 (Rumion p6 prints 64.6 kW CNG mode): already hp |
| 23 | Ertiga petrol 101.65 | FALSE_POSITIVE | = 75.8 kW × 1.34102: already hp |
| 114, 62 | Thar Roxx 174.0, XUV 7XO 197.13 | FALSE_POSITIVE | Ratio 1.133, not the PS/hp ratio 1.0139; different tunes [INFERENCE: brochures not checked] |

**Not on the Pass A list but found in 10F:** pt 88, Victoris Petrol Hybrid, 115.6 — **NEEDS_HUMAN**. The Victoris brochure prints engine 68 kW and motor 59 kW but no total-system power, and 115.6 is the GV/Hyryder figure.

The post-apply scan (`power_scan_prod.txt`): (b) has 0 hits, and the PS-ratio groups' high members are only {84, 88}.

## 2. Scope B — Victoris 558, 562 (FIXED)

The Victoris brochure (`94f94973…`, p16) prints a single CNG figure: "27.02 km/kg". It is visually confirmed.

| variant | field | before | after | provenance | quarantined |
|---|---|---|---|---|---|
| 558 VXI CNG MT | mileage_arai_km_per_kg | 26.6 | 27.02 | OEM obs + fp (p16) | fp 17208 → quarantine id 721 |
| 562 ZXI CNG MT | mileage_arai_km_per_kg | 26.6 | 27.02 | OEM obs + fp (p16) | fp 17338 → quarantine id 722 |

The CLAUDE.md backlog item is removed on `kb/10f-units`.

## 3. Scope C — CNG km/kg scan (no further writes)

All 83 CNG variants were checked: 37 have a km/kg value, and none is an edition.

| Model (variants) | KB km/kg | Own brochure (page) | Outcome |
|---|---|---|---|
| Alto K10 (518, 521) | 33.4 | 33.40 (p5, image) | match |
| Eeco (245), Ertiga (213), XL6 (217) | 26.78 / 26.11 / 26.23 | same (10E) | match |
| Fronx (496, 499) / Taisor (486) | 28.51 | 28.51 (p19 / p21) | match |
| Glanza (479, 482) | 30.61 | 30.61 (p1) | match |
| Rumion (591) | 26.11 | 26.11 (p6) | match |
| S-Presso (510, 513) | 32.73 | 32.73 (p5, image) | match |
| Swift (63, 65, 69) | 32.85 | 32.85 (p6) | match |
| Hyryder (526, 528) | 26.6 | 26.6 [CNG mode] (p14) | match |
| Victoris (556, 558, 562) | 27.02 | 27.02 (p16) | match (558 and 562 after §2) |
| **WagonR (225)** | 33.54 | 33.47 (p5, image) | **Held: CATALOG_CURRENCY** (owner decision) |
| **Grand Vitara (548, 549)** | 26.6 | no CNG data in the brochure | **Unverified** (owner decision: not quarantined) |
| **Exter (655, 657, 660, 663, 666)** | 27.1 | the brochure prints no km/kg | **Unverified** |
| **Nexon (13 variants)** | 17.44 | p39 refers to a separate Nexon iCNG brochure (not on disk) | **Unverified** |

**WagonR 225, owner decision at "go":** "Drop the WagonR 225 correction and the quarantine of its source row 7149 … catalogue-currency case (KB rows predate the brochure; to be handled with Baleno)."
- KB evidence: the WagonR 1.0 petrol power is 64.37 bhp, which is 48 kW, against 50.4 kW printed.
- 227 AGS is 22.5 km/l, against 25.19 printed.
- 225 is exempt from the own-brochure check, with that reason.

**Grand Vitara 548/549, owner decision at "go":** "Do not quarantine Grand Vitara 548/549. Record them as unverified."
- Copy pattern: 26.6 is the Hyryder twin engine's brochure figure.
- The same value sat on Victoris 558/562, where it was contradicted and fixed in §2.
- Fronx/Taisor 28.51 and Rumion/Ertiga 26.11 are shared too, but each own brochure confirms the value.

## 4. Write script and dry run

`apply_phase10f.py`:
- One `BEGIN IMMEDIATE` transaction, `foreign_keys=ON`, **no DDL**.
- `--oem` re-hashes all 8 cited PDFs.
- Invariants checked before COMMIT:
  - only the allowed rows and columns differ;
  - the schema is identical;
  - the canonical view changes only on approved cells;
  - 832 variants, integrity ok, 297 foreign-key orphans;
  - the target values.
- The owner's edits removed the WagonR 225 entry and the GV proposal option.

**Final dry run** (`dry2/`, a fresh copy of `57f31e4d`):
- `COMMITTED; update 18, amend 34, obs 82, fp 82, quar 2`.
- updates: 16 powertrains + 2 variant cells;
- amendments: 32 powertrain + 2 variant;
- provenance: 80 power rows + 2 km/kg rows.

**Idempotency:** a re-run made 0 changes; sha3 `6f2dc93bcc48e9adf3205ec3cd5995a83322ae035428fa606e741ac9` unchanged; EXCEPT diff 0.

**Prod:**
- The identical script (SHA-1 `87de663c…`) gave the same counts.
- Prod vs the dry run: 0 differing rows in every table, excluding the `created_at`/`observed_at`/`decided_at` timestamps.
- A re-run on the prod copy made 0 changes.

## 5. Verification — prod (`verify_prod.md`): ALL PASS

| Check | Result |
|---|---|
| integrity_check | ok |
| foreign_key_check | 297 known orphans only |
| variant count | 832 |
| active quarantine | 720 → **722** (new: 721 fp 17208, 722 fp 17338) |
| corrected power_bhp = kW × 1.34102 (2 dp), description shows only the figure change | 16/16 |
| power provenance: one row per base variant, value and page as cited | 80/80 |
| powertrain rows changed | exactly the 16 |
| PS-as-bhp scan re-run | (b) 0 hits; PS-ratio high members {84, 88} = held |
| 558, 562 km/kg = 27.02 with provenance | PASS |
| no CNG km/kg contradicts its own brochure | PASS (exempt: 225, CATALOG_CURRENCY) |
| v_variant_canonical_q | only 558 and 562 km/kg changed |
| schema identical to the backup state | 42 objects |

## 6. Cell-level diff vs backup

The full listing is in `verify_prod.md`.
- **powertrain:** 32 cells (16 × `power_bhp`, 16 × `description`).
- **variant:** 2 cells.
- **New rows:** `evidence_amendment` +34 (ids 92–125), `source_observation` +82, `field_provenance` +82, `evidence_quarantine` +2 (721–722).
- No other table changed.

## 7. Branches

- **`kb/10f-units`:** worktree `~/carrec_worktrees/kb-10f`, from the `paper/v0` HEAD `c5a8609`. Pushed, no PR (commit `16b54c0` + this report follow-up).
  - It carries CLAUDE.md (the Victoris item removed; WagonR 225, GV 548/549, the missing GV and Nexon iCNG brochures, Exter, pt 84 and pt 88 added; backup listed; prod SHA updated), `knowledge_base/db/migrations/apply_phase10f.py` + `verify_phase10f.py`, and `knowledge_base/reports/phase10f/`.
- **`app/kb-10f-export`:** worktree `~/carrec_worktrees/app-10f`, from `origin/main` `d40b368` (after `git fetch origin`). Data-only commit `9c52d9c`, pushed.
  - **PR: https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/16** (open, not merged).
  - **Export:** run twice from a byte copy of prod `dedefb53`; the two runs were identical.
    - `catalogue.csv` SHA-1 `f6ef96072718680374db84059ea5d33864cbb6ab` (sha256 `ffce4794…`).
    - `catalogue_meta.json` SHA-1 `932e4d387771dcf3ce5e363b19e362810e111306` (identical across runs apart from the export timestamp).
    - 832 rows; `kb_latest_phase` 10F; the exporter's failure checks passed (exit 0).
  - **Tests:** `pytest -q` 352 passed.
  - **Catalogue field diff vs `main`:** only allowed fields changed (`catalogue_field_diff.txt`).
    - `power_bhp` on 83 rows: the 80 base variants of §1, plus editions 822, 823 and 825 via the shared powertrain.
      - 89.7 → 88.51 ×10
      - 77.5 → 76.44 ×3
      - 100.1 → 98.7 ×10
      - 56.7 → 55.92 ×4
      - 103.1 → 101.65 ×35
      - 87.8 → 86.63 ×5
      - 115.6 → 113.99 ×8
      - 163 → 160.77 ×8
    - `mileage_km_per_kg` on 2 rows: 558 and 562, 26.6 → 27.02.
    - `unverified_fields`: unchanged. Columns and rows are unchanged.

## 8. Prod SHA-1

- Before: `57f31e4d4a5f1f01b4a12e1c0d2e507795953cfe`, backed up as `pre_phase10f_20261102T091906Z`.
- After: **`dedefb537ce36cec5e422c6688a3a85373030b39`** (2026-11-02, size 38699008).

## 9. Message for the ranking track

KB unit corrections (10F) merged-ready, export re-run: https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/16

## 10. Report-only / deferred

- **Open (CLAUDE.md):**
  - WagonR 225 (CATALOG_CURRENCY);
  - Grand Vitara 548/549 km/kg unverified;
  - the GV CNG data and Nexon iCNG brochures are missing;
  - Exter CNG km/kg unverified;
  - power for pt 84 and pt 88.
- **Stale petrol power, CATALOG_CURRENCY:** S-Presso and Alto K10 (pt 76, 78) hold 65.7, WagonR 1.0 (pt 27) holds 64.37. Their brochures print 50.4 kW.
- **WagonR 229 VXi CNG:** km/kg is NULL; the brochure prints 33.47. A fill is out of scope.
- **Duster TCe 100 (pt 116):** 99.0, while the brochure prints 100 PS (= 98.63 hp). Not the PS-as-bhp pattern.
- **Torque:** GV and Victoris petrol hold 136.8, while their brochures print 139 Nm.
