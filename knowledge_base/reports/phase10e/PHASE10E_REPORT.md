# Phase 10E — KB corrections, Pass B

**Status: APPLIED to prod (2026-11-01 23:28 UTC).** Prod SHA-1 `8592508…` → `57f31e4d4a5f1f01b4a12e1c0d2e507795953cfe`.

- **First checkpoint:** stopped once on a dry-run schema-text failure (the table name came back quoted after the rebuild). The owner decided 2026-11-02:
  1. rebuild by renaming the old table aside;
  2. accept the read-only VM `lsof` holder for this write;
  3. Grand Vitara: quarantine the years and km cells only;
  4. keep the description change only if just the figure changed (it did);
  5. add a provenance row for each rebase;
  6. accept the 7 Glanza rows, the 15 source-row quarantines and the rebase value changes;
  7. 833 goes to the backlog.
- **Second dry run:** passed everything, so the run continued through steps 5–8 per the owner's instruction.
- **Run:** 2026-11-01 23:15–23:40 UTC.
- **Scratch:** `~/carrec_kb_scratch/corrections_passB/`.

## 0. Access and precheck log

- **Prod SHA-1:** `8592508789594ab76cf98e463bbf77606a76a7e2` at every check (23:15, 23:18 and 23:24 UTC).
  - Raw output: `access_step0.txt`, `backup_log.txt`, `access_checkpoint.txt`.
- **`lsof`:** identical each time. No `-wal` or `-shm`.
  ```
  COMMAND    PID             USER   FD   TYPE DEVICE SIZE/OFF      NODE NAME
  com.apple 4854 shaikyaseenbasha 2613r   REG   1,17 38584320 136286357 knowledge_base/carrec_kb.db
  ```
  `lsof +c 0` resolves the holder to `com.apple.Virtualization.VirtualMachine`. It passes the provisional rule for reads. **Under the write rule, any holder means stop and ask.**
- **10C/10D state matches the audit:**
  - 0 rows tagged 10C or 10D;
  - phases present: 10B-W1..W6 only;
  - newest quarantine/amendment row 2026-09-29 00:55:09;
  - 698 active quarantines; 832 variants.
- **10D script baseline:** `knowledge_base/reports/phase10d/count_version_binding.py`, 4436 B, mtime 2026-10-02 04:38. These equal the audit's values.
  - The audit did not record a SHA-1. The owner accepted size and mtime on 2026-11-02.
  - **Baseline SHA-1 recorded: `b73ca69b1257164244cee8f7f0f83e544cf71826`.**
- **Brochures re-verified** (`brochure_evidence.txt`): all 12 cited PDFs match Pass A's SHA-1s. Quoted text was found on each cited page that has a text layer.
  - Victoris p16 (scrambled text layer) and XL6 p15 (fuel row not in the text layer) were rendered and checked visually: Victoris paddle row "Lxi - / Vxi 6AT / Zxi(O) 6AT / Zxi+(O) 6AT", CNG 27.02 km/kg; XL6 CNG 26.23 km/kg.
  - Eeco p2 and Ertiga p7 are image-only; Pass A's OCR has 26.78 km/kg and 26.11 km/kg on them.

## 1. Snapshot and backup

| What | Path | SHA-1 | Notes |
|---|---|---|---|
| Paper snapshot | `~/carrec_kb_snapshots/carrec_kb_paper_v0_8592508.db` | `8592508789594ab76cf98e463bbf77606a76a7e2` | `chmod 444` (`-r--r--r--`) |
| Paper loader diff (NOT applied) | `~/carrec_kb_scratch/corrections_passB/paper_loader.diff` | — | Repoints `paper/oracle/feasibility.py:15` `DB_PATH` (asserted against `FROZEN_SHA1` at line 16) to the snapshot, with a `CARREC_PAPER_KB` override. `git apply --check` passes; the file is unchanged in the checkout. |
| Backup (CLAUDE.md step 2) | `knowledge_base/backups/pre_phase10e_20261101T231809Z.db` | `0bcfc5b48d17d089b64b26d12720f9146213240d` | `.backup` from a SHA-verified scratch copy. `.sha3sum` `ce49ad21…08d155f2` equals prod's. `integrity_check` ok. No side files beside it (checks ran on copies). The directory is git-ignored. No Drive copy (not requested). |

## 2. Per-item change tables (from prod: `evidence_amendment` phase `10E` joined to the new provenance rows)

### 1. CNG mileage

| variant_id | model | variant | field | before | after | source | page | PDF SHA-1 |
|---|---|---|---|---|---|---|---|---|
| 213 | Ertiga | ZXi CNG | mileage_arai_km_per_kg | None | 26.11 | maruti_suzuki_ertiga_brochure.pdf | 7 | d5a10fb1556e2ad77abd66a5747471bed3df5d2d |
| 213 | Ertiga | ZXi CNG | mileage_arai_kmpl | 26.11 | None | maruti_suzuki_ertiga_brochure.pdf | 7 | d5a10fb1556e2ad77abd66a5747471bed3df5d2d |
| 217 | XL6 | Zeta CNG | mileage_arai_km_per_kg | None | 26.23 | NEXA-Xl6-Brochure.pdf | 15 | e66cbeecb310f06cd6f0205f2772f152a5b6a891 |
| 217 | XL6 | Zeta CNG | mileage_arai_kmpl | 26.23 | None | NEXA-Xl6-Brochure.pdf | 15 | e66cbeecb310f06cd6f0205f2772f152a5b6a891 |
| 245 | Eeco | 5 Seater AC CNG | mileage_arai_km_per_kg | None | 26.78 | maruti_suzuki_eeco_brochure.pdf | 2 | d964c7b53a8136234131c0d5c165c647ae1f2a11 |
| 245 | Eeco | 5 Seater AC CNG | mileage_arai_kmpl | 26.78 | None | maruti_suzuki_eeco_brochure.pdf | 2 | d964c7b53a8136234131c0d5c165c647ae1f2a11 |
| 556 | Victoris | LXI CNG MT | mileage_arai_km_per_kg | 26.6 | 27.02 | maruti_suzuki_victoris_brochure.pdf | 16 | 94f94973736c150efdf2cc5ae6c40845d8e856a3 |
| 556 | Victoris | LXI CNG MT | mileage_arai_kmpl | 27.02 | None | maruti_suzuki_victoris_brochure.pdf | 16 | 94f94973736c150efdf2cc5ae6c40845d8e856a3 |
| 591 | Rumion | S MT CNG | mileage_arai_kmpl | 26.11 | None | toyota_rumion_brochure.pdf | 6 | c1d41f62df6331b12d505f05032fdf4425e3da80 |

### 2. Paddle shifters

| variant_id | model | variant | field | before | after | source | page | PDF SHA-1 |
|---|---|---|---|---|---|---|---|---|
| 5 | Creta | EX Diesel 1.5L Turbo Manual | paddle_shifters | 1 | 0 | Hyundai_Creta_Brochure_Official.pdf | 14 | cc5b2fbc3490e16d1e5de56d61b49eb7372ce362 |
| 15 | Creta | SX Premium Petrol 1.5L Manual | paddle_shifters | 1 | 0 | Hyundai_Creta_Brochure_Official.pdf | 14 | cc5b2fbc3490e16d1e5de56d61b49eb7372ce362 |
| 16 | Creta | SX Premium Petrol 1.5L Manual Dual Tone | paddle_shifters | 1 | 0 | Hyundai_Creta_Brochure_Official.pdf | 14 | cc5b2fbc3490e16d1e5de56d61b49eb7372ce362 |
| 21 | Creta | SX Premium Diesel 1.5L Turbo Manual | paddle_shifters | 1 | 0 | Hyundai_Creta_Brochure_Official.pdf | 14 | cc5b2fbc3490e16d1e5de56d61b49eb7372ce362 |
| 23 | Creta | SX Premium Diesel 1.5L Turbo Manual Dual Tone | paddle_shifters | 1 | 0 | Hyundai_Creta_Brochure_Official.pdf | 14 | cc5b2fbc3490e16d1e5de56d61b49eb7372ce362 |
| 158 | Venue | HX5 1.5 Diesel MT | paddle_shifters | 1 | 0 | hyundai_venue_brochure.pdf | 20 | 00eabf1c73ad06d076b7e3928d9ca54d9b4cb1c4 |
| 561 | Victoris | ZXI (O) MT | paddle_shifters | 1 | 0 | maruti_suzuki_victoris_brochure.pdf | 16 | 94f94973736c150efdf2cc5ae6c40845d8e856a3 |
| 566 | Victoris | ZXI+ (O) MT | paddle_shifters | 1 | 0 | maruti_suzuki_victoris_brochure.pdf | 16 | 94f94973736c150efdf2cc5ae6c40845d8e856a3 |
| 627 | Taigun | GT Line Petrol 1.0L Turbo Manual | paddle_shifters | 1 | 0 | volkswagen_taigun_brochure.pdf | 10 | b2a396b599758b80a6643ad479eb21426eaa2c3c |

### 3. Glanza power

| variant_id | model | variant | field | before | after | source | page | PDF SHA-1 |
|---|---|---|---|---|---|---|---|---|
| 476 | Glanza | E Petrol MT | powertrain[68].description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 476 | Glanza | E Petrol MT | powertrain[68].power_bhp | 89.7 | 88.51 | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 477 | Glanza | S Petrol MT | powertrain[68].description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 477 | Glanza | S Petrol MT | powertrain[68].power_bhp | 89.7 | 88.51 | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 478 | Glanza | S Petrol AMT | powertrain[68].description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 478 | Glanza | S Petrol AMT | powertrain[68].power_bhp | 89.7 | 88.51 | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 480 | Glanza | G Petrol MT | powertrain[68].description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 480 | Glanza | G Petrol MT | powertrain[68].power_bhp | 89.7 | 88.51 | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 481 | Glanza | G Petrol AMT | powertrain[68].description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 481 | Glanza | G Petrol AMT | powertrain[68].power_bhp | 89.7 | 88.51 | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 483 | Glanza | V Petrol MT | powertrain[68].description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 483 | Glanza | V Petrol MT | powertrain[68].power_bhp | 89.7 | 88.51 | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 484 | Glanza | V Petrol AMT | powertrain[68].description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |
| 484 | Glanza | V Petrol AMT | powertrain[68].power_bhp | 89.7 | 88.51 | toyota_glanza_brochure.pdf | 1 | fd682f602d0fe869b41128fe8e7b96d8268f029f |

### 6. Edition rebases

| variant_id | model | variant | field | before | after | source | page | PDF SHA-1 |
|---|---|---|---|---|---|---|---|---|
| 814 | Elevate | ZX Petrol Manual Black Edition | base_variant_id | 649 | 652 | honda_elevate_brochure.pdf | 48 | 3b794463eeda84b292eab3a1b9e07ab65a40ccfc |
| 826 | XL6 | Alpha Plus Petrol Manual Dual Tone Smart Hybrid | base_variant_id | 218 | 220 | NEXA-Xl6-Brochure.pdf | 15 | e66cbeecb310f06cd6f0205f2772f152a5b6a891 |

### Quarantine rows added (all items; 22)

| id | target_table | target_id | target_field | reason | evidence (note, abridged) |
|---|---|---|---|---|---|
| 699 | field_provenance | 26233 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=26233; variant_id=245; field=mileage_arai_kmpl; source=91wheels; accepted_value=26.78; contradicted by knowledge_base/sources/oem/maruti_suzuki/… |
| 700 | field_provenance | 26338 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=26338; variant_id=213; field=mileage_arai_kmpl; source=91wheels; accepted_value=26.11; contradicted by knowledge_base/sources/oem/maruti_suzuki/… |
| 701 | field_provenance | 27737 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=27737; variant_id=591; field=mileage_arai_kmpl; source=91wheels; accepted_value=26.11; contradicted by knowledge_base/sources/oem/toyota/rumion/… |
| 702 | field_provenance | 26621 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=26621; variant_id=556; field=mileage_arai_kmpl; source=91wheels; accepted_value=27.02; contradicted by knowledge_base/sources/oem/maruti_suzuki/… |
| 703 | field_provenance | 26695 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=26695; variant_id=217; field=mileage_arai_kmpl; source=91wheels; accepted_value=26.23; contradicted by knowledge_base/sources/oem/maruti_suzuki/… |
| 704 | field_provenance | 17141 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=17141; variant_id=556; field=mileage_arai_km_per_kg; source=v6_migration; accepted_value=26.6; contradicted by knowledge_base/sources/oem/maruti… |
| 705 | field_provenance | 164 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=164; variant_id=5; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/hyundai/creta/gen… |
| 706 | field_provenance | 504 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=504; variant_id=15; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/hyundai/creta/ge… |
| 707 | field_provenance | 538 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=538; variant_id=16; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/hyundai/creta/ge… |
| 708 | field_provenance | 708 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=708; variant_id=21; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/hyundai/creta/ge… |
| 709 | field_provenance | 776 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=776; variant_id=23; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/hyundai/creta/ge… |
| 710 | field_provenance | 5110 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=5110; variant_id=158; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/hyundai/venue/… |
| 711 | field_provenance | 17321 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=17321; variant_id=561; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/maruti_suzuki… |
| 712 | field_provenance | 17480 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=17480; variant_id=566; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/maruti_suzuki… |
| 713 | field_provenance | 19382 | None | CONTRADICTED_BY_OEM_BROCHURE | fp_id=19382; variant_id=627; field=paddle_shifters; source=v6_migration; accepted_value=True; contradicted by knowledge_base/sources/oem/volkswagen/ta… |
| 714 | variant | 345 | mileage_arai_kmpl | UNIT_SUSPECT_SOURCE_MISLABEL | Altroz CNG kmpl 26.2 (91wheels fp 27188). The same 91wheels source stored a km/kg figure as kmpl on the 5 brochure-verified CNG siblings (245, 213, 59… |
| 715 | variant | 216 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED | XL6 MT paddle_shifters=1 (v6_migration). Brochure p15 feature list has no paddle row; p10 ties paddle shifters to the 6-speed AT but does not state MT… |
| 716 | variant | 217 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED | XL6 MT paddle_shifters=1 (v6_migration). Brochure p15 feature list has no paddle row; p10 ties paddle shifters to the 6-speed AT but does not state MT… |
| 717 | variant | 218 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED | XL6 MT paddle_shifters=1 (v6_migration). Brochure p15 feature list has no paddle row; p10 ties paddle shifters to the 6-speed AT but does not state MT… |
| 718 | variant | 220 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED | XL6 MT paddle_shifters=1 (v6_migration). Brochure p15 feature list has no paddle row; p10 ties paddle shifters to the 6-speed AT but does not state MT… |
| 719 | warranty | 12 | warranty_years | CONTRADICTED_BY_OEM_BROCHURE | warranty row 12 (Grand Vitara) warranty_years=2.0; brochure p15 prints '3 YEARS/1 00 000 KM WARRANTY': knowledge_base/sources/oem/maruti_suzuki/grand_… |
| 720 | warranty | 12 | warranty_km | CONTRADICTED_BY_OEM_BROCHURE | warranty row 12 (Grand Vitara) warranty_km=40000.0; brochure p15 prints '3 YEARS/1 00 000 KM WARRANTY': knowledge_base/sources/oem/maruti_suzuki/grand… |


## 3. Verification results

- **Script:** `apply_phase10e.py`, SHA-1 `c874ad03d2b7c3cf8af64d5228404cf65c478d4a`. The identical file ran on the dry-run copy and on prod.
- **Dry run 2** (`dryrun.db`): committed with 21 updates, 22 amendments, 22 OEM `source_observation` rows, 22 `field_provenance` rows, 22 quarantines and 3 DDL steps. All in-transaction invariants passed.
- **Idempotency:** a re-run on a copy made 0 changes; `.sha3sum` `9f065cb7…` before and after.
- **Prod apply:**
  - SHA-1 `8592508…` was rechecked immediately before (23:28:14 UTC). The read-only VM holder was accepted by the owner for this write.
  - The script committed with the same counts.
  - `integrity_check` immediately after: ok. `wal_checkpoint(TRUNCATE)`: `0|0|0`. No `-wal` or `-shm` afterwards.
- **Prod verification** ran on a byte copy (SHA-1 = prod) against the pre-change copy. **The output is identical to dry run 2**, line for line. A table-by-table EXCEPT between prod and the dry-run DB, ignoring timestamp columns, is empty, and the schemas are identical.

Detail is in `verify_dryrun.md` and `verify_prod.md`.

| Check | Result (dry run 2 = prod) | Detail |
|---|---|---|
| integrity_check | PASS | ok |
| foreign_key_check = 297 known orphans | PASS | 297 rows |
| ux_quarantine_active exists, identical SQL, enforced | PASS | duplicate insert rejected on a throwaway copy: True |
| variant count = 832 | PASS | 832 |
| active quarantine = 698 + inserts = 720 | PASS | before 698, after 720, inserts 22 |
| CNG (a) kmpl = km/kg -> 0 | PASS | [] |
| CNG (b) kmpl > 25 -> 0 | PASS | [] |
| manual/iMT + paddle=1 = {599 Jimny, 605 Kushaq, 824 Jimny edition} | PASS | [599, 605, 824] |
| powertrain 68 description | INFO | before '1197cc 89.7bhp Petrol' -> after '1197cc 88.51bhp Petrol' |
| powertrain 68 description: only the figure 89.7 -> 88.51 changed | PASS | '1197cc 89.7bhp Petrol' -> '1197cc 88.51bhp Petrol' |
| rebase provenance rows (814 -> 652, 826 -> 220) | PASS | [(814, '652'), (826, '220')] |
| Glanza petrol power_bhp = 88.51 with provenance | PASS | power_bhp 88.51; 7 power provenance rows (variants [476, 477, 478, 480, 481, 483, 484]) |
| v_warranty_q: GV row 12 years/km blanked, battery+extended visible, other 17 unchanged, warranty table untouched | PASS | row12 values (None, None, 8.0, '160000.0', None); others diff 0/0; rows 18; warranty table diff 0; has_provenance [(0, 18)] |
| v_variant_canonical_q has no adas_tier; other columns identical in order | PASS | 49 -> 48 columns |
| v_variant_canonical_q: changes only on approved cells + rebased editions 814/826 | PASS | 32 cells changed; unexpected [] |
| schema diff = evidence_quarantine CHECK + v_warranty_q + v_variant_canonical_q only | PASS | changed objects ['evidence_quarantine', 'v_variant_canonical_q', 'v_warranty_q']; evidence_quarantine differs only in the CHECK clauses: True |

- **Cell-level diff vs prod (before):** `variant` 20 cells (9 mileage, 9 paddle shifters, 2 `base_variant_id`); `powertrain` 2 cells (id 68 `power_bhp`, `description`).
- **Rows added:** `evidence_amendment` +22 (ids 70–91); `evidence_quarantine` +22 (ids 699–720); `source_observation` +22 (ids 3758–3779); `field_provenance` +22.
- **Sequence bookkeeping only** (`sqlite_sequence`).
- **Every other table:** +0/−0.

## 4. Rebase inherited-cell diffs (prod)



**814: base 649 -> 652** (33 inherited cells; 3 change)

| field | old value (old base 649) | new value (new base 652) | changed |
|---|---|---|---|
| price_ex_showroom | 1379000.0 | 1502000.0 | Y |
| length_mm | 4312.0 | 4312.0 |  |
| width_mm | 1790.0 | 1790.0 |  |
| height_mm | 1650.0 | 1650.0 |  |
| wheelbase_mm | 2650.0 | 2650.0 |  |
| ground_clearance_mm | 220.0 | 220.0 |  |
| kerb_weight_kg | 1213.0 | 1213.0 |  |
| seating_capacity | 5 | 5 |  |
| fuel_tank_litres | 40.0 | 40.0 |  |
| mileage_arai_kmpl | 15.31 | 15.31 |  |
| mileage_arai_km_per_kg | None | None |  |
| claimed_ev_range_km | None | None |  |
| airbags | 6 | 6 |  |
| abs | 1 | 1 |  |
| esc | 1 | 1 |  |
| hill_assist | 1 | 1 |  |
| tyre_pressure_monitoring_system | 0 | 0 |  |
| rear_parking_sensors | 1 | 1 |  |
| rear_camera | 1 | 1 |  |
| camera_360 | 0 | 0 |  |
| adas_available | 0 | 1 | Y |
| automatic_climate_control | 1 | 1 |  |
| rear_ac_vents | 1 | 1 |  |
| sunroof | 'True' | 'True' |  |
| ventilated_front_seats | 0 | 0 |  |
| paddle_shifters | None | None |  |
| wireless_charging | None | None |  |
| heads_up_display | 0 | 0 |  |
| drive_modes | None | None |  |
| connected_car_features | 0 | 1 | Y |
| android_auto | 1 | 1 |  |
| apple_carplay | 1 | 1 |  |
| v6_row_index | None | None |  |

**826: base 218 -> 220** (34 inherited cells; 4 change)

| field | old value (old base 218) | new value (new base 220) | changed |
|---|---|---|---|
| price_ex_showroom | 1253800.0 | 1302100.0 | Y |
| length_mm | 4445.0 | 4445.0 |  |
| width_mm | 1775.0 | 1775.0 |  |
| height_mm | 1755.0 | 1755.0 |  |
| wheelbase_mm | 2740.0 | 2740.0 |  |
| ground_clearance_mm | 180.0 | 180.0 |  |
| kerb_weight_kg | 1225.0 | 1225.0 |  |
| seating_capacity | 6 | 6 |  |
| fuel_tank_litres | 45.0 | 45.0 |  |
| mileage_arai_kmpl | 19.01 | 19.01 |  |
| mileage_arai_km_per_kg | None | None |  |
| claimed_ev_range_km | None | None |  |
| airbags | 6 | 6 |  |
| abs | 1 | 1 |  |
| esc | 1 | 1 |  |
| hill_assist | 1 | 1 |  |
| tyre_pressure_monitoring_system | 0 | 1 | Y |
| rear_parking_sensors | 1 | 1 |  |
| rear_camera | 1 | 1 |  |
| camera_360 | 0 | 0 |  |
| adas_available | 0 | 0 |  |
| automatic_climate_control | 1 | 1 |  |
| rear_ac_vents | 1 | 1 |  |
| sunroof | 'False' | 'False' |  |
| ventilated_front_seats | 0 | 1 | Y |
| cruise_control | 1 | 1 |  |
| paddle_shifters | 1 | None | Y |
| wireless_charging | 0 | 0 |  |
| heads_up_display | 0 | 0 |  |
| drive_modes | 0 | 0 |  |
| connected_car_features | 1 | 1 |  |
| android_auto | 1 | 1 |  |
| apple_carplay | 1 | 1 |  |
| v6_row_index | None | None |  |


## 5. Variant 833 finding (read-only; no change in 10E; HIGH-PRIORITY BACKLOG)

- **Brochure:** `volkswagen/virtus/latest/brochures/volkswagen_virtus_brochure.pdf`, SHA-1 `882313c241b15256afc8f3c740c141a59d42a61a`. "Issue: January 2025"; PDF dated 2025-11-04, modified 2026-02-05.
  - **It never mentions an Anniversary Edition.** The text layer covers all 16 pages. Pages 1–9 also carry images, which were not OCR'd.
- **The p10 Performance matrix** (rendered and checked):
  - 1.0 TSI 6MT: Comfortline, Highline, Highline Plus, Topline, GT Line.
  - 1.0 TSI 6AT (torque converter): Highline, Highline Plus, Topline, GT Line.
  - **1.5 TSI 7-speed DSG: GT Plus Chrome and GT Plus Sport only.**
- **KB:**
  - 833's name is "Anniversary Edition Petrol 1.5L Turbo Automatic (DCT)" (CarWale obs 3668). Its CarWale `transmission='DCT'` row (fp 37182) is `rejected`.
  - Links: base 643 (Topline 1.0 TC), powertrain 103 (999 cc, 114 bhp), transmission 'Torque Converter'.
- **Finding: UNDETERMINABLE from the brochure** (existence and powertrain). The row is internally inconsistent: its name says 1.5 DCT, its links say 1.0 TC. Under the brochure's matrix a 1.5 DSG edition cannot sit on a Topline base.

## 6. Schema diff (prod vs backup)

| Object | Change |
|---|---|
| `evidence_quarantine` | Stored DDL differs **only** in the CHECK: `IN (…,'safety_test_applicability')` → `IN (…,'safety_test_applicability','warranty')`, and `CHECK (target_table <> 'variant' OR …)` → `CHECK (target_table NOT IN ('variant','warranty') OR …)`. Header unquoted, as before. Rebuilt by renaming the old table aside (`legacy_alter_table` ON), creating the new one from today's exact stored text plus the CHECK, copying 698 rows, and dropping the old table. |
| `ux_quarantine_active` | Recreated, byte-identical, enforced. |
| `v_warranty_q` | New. Quarantine-aware; `grain`; `has_provenance` = constant 0 (no provenance table can reference a warranty row; provenance schema not changed). |
| `v_variant_canonical_q` | The `adas_tier` line removed; the other 48 columns identical in order and values, except the approved cells. |

Nothing else changed: views, tables, indexes and triggers are all identical.

## 7. Branches

STEP8_PLACEHOLDER

## 8. Prod SHA-1

- Before: `8592508789594ab76cf98e463bbf77606a76a7e2`. Frozen as the paper snapshot `~/carrec_kb_snapshots/carrec_kb_paper_v0_8592508.db` (chmod 444).
- After: **`57f31e4d4a5f1f01b4a12e1c0d2e507795953cfe`** (2026-11-02; size 38699008).

## 9. Message for the ranking track

MSG_PLACEHOLDER

## 10. Deferred or skipped

- **833 Virtus Anniversary Edition:** high-priority backlog (§5). No change.
- **605 Kushaq and 599/824 Jimny paddle shifters:** no change, as instructed. They are the only manual cars with `paddle_shifters=1` left.
- **345 Altroz kmpl:** quarantined. The true km/kg figure is unknown; no OEM source prints it.
- **Victoris 558/562 km/kg 26.6:** same defect as 556 (Pass A §11). Not in the approved set; backlog.
- **Warranty:**
  - `v_warranty_q` is not wired into the export, as instructed.
  - `has_provenance` is constant 0 until a provenance schema can reference warranty rows.
  - The Grand Vitara values (2.0 / '40000.0') were not changed, only masked.
  - CLAUDE.md's read-path rule does not yet mention `v_warranty_q`; that belongs in the change that wires warranty into the export.
- **Glanza siblings:** Taisor and Fronx still store 89.7 for the same 66 kW engine (Pass A §8 power backlog).
- **The paper loader diff is NOT applied.** `paper/` still reads `knowledge_base/carrec_kb.db`, whose SHA-1 is now `57f31e4d…`, so its `FROZEN_SHA1` assert will fail until `~/carrec_kb_scratch/corrections_passB/paper_loader.diff` is applied on the paper branch.
- **No Drive copy** of the 10E backup (not requested).
- **Main checkout:** not modified. The only new file in its tree is the git-ignored backup `knowledge_base/backups/pre_phase10e_20261101T231809Z.db`, which CLAUDE.md requires. The 10D script is untouched (SHA-1 `b73ca69b…`). W6's leftover `-shm`/`-wal` are left in place.
