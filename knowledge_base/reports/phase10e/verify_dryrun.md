# Phase 10E verification: dryrun

| Check | Result | Detail |
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

## New quarantine rows

| id | target_table | target_id | target_field | reason |
|---|---|---|---|---|
| 699 | field_provenance | 26233 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 700 | field_provenance | 26338 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 701 | field_provenance | 27737 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 702 | field_provenance | 26621 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 703 | field_provenance | 26695 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 704 | field_provenance | 17141 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 705 | field_provenance | 164 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 706 | field_provenance | 504 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 707 | field_provenance | 538 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 708 | field_provenance | 708 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 709 | field_provenance | 776 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 710 | field_provenance | 5110 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 711 | field_provenance | 17321 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 712 | field_provenance | 17480 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 713 | field_provenance | 19382 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 714 | variant | 345 | mileage_arai_kmpl | UNIT_SUSPECT_SOURCE_MISLABEL |
| 715 | variant | 216 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED |
| 716 | variant | 217 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED |
| 717 | variant | 218 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED |
| 718 | variant | 220 | paddle_shifters | PADDLE_ON_MT_NOT_MENTIONED |
| 719 | warranty | 12 | warranty_years | CONTRADICTED_BY_OEM_BROCHURE |
| 720 | warranty | 12 | warranty_km | CONTRADICTED_BY_OEM_BROCHURE |

## Cell-level diff vs prod (before)

- `evidence_amendment`: +22 / -0
- `evidence_quarantine`: +22 / -0
- `field_provenance`: +22 / -0
- `generation`: +0 / -0
- `manufacturer`: +0 / -0
- `model`: +0 / -0
- `powertrain`: +1 / -1
- `safety_rating`: +0 / -0
- `safety_test`: +0 / -0
- `safety_test_applicability`: +0 / -0
- `source`: +0 / -0
- `source_observation`: +22 / -0
- `sqlite_sequence`: +4 / -4
- `variant`: +16 / -16
- `variant_alias`: +0 / -0
- `warranty`: +0 / -0

**variant: 20 cells**

| id | column | before | after |
|---|---|---|---|
| 5 | paddle_shifters | 1 | 0 |
| 15 | paddle_shifters | 1 | 0 |
| 16 | paddle_shifters | 1 | 0 |
| 21 | paddle_shifters | 1 | 0 |
| 23 | paddle_shifters | 1 | 0 |
| 158 | paddle_shifters | 1 | 0 |
| 213 | mileage_arai_km_per_kg | None | 26.11 |
| 213 | mileage_arai_kmpl | 26.11 | None |
| 217 | mileage_arai_km_per_kg | None | 26.23 |
| 217 | mileage_arai_kmpl | 26.23 | None |
| 245 | mileage_arai_km_per_kg | None | 26.78 |
| 245 | mileage_arai_kmpl | 26.78 | None |
| 556 | mileage_arai_km_per_kg | 26.6 | 27.02 |
| 556 | mileage_arai_kmpl | 27.02 | None |
| 561 | paddle_shifters | 1 | 0 |
| 566 | paddle_shifters | 1 | 0 |
| 591 | mileage_arai_kmpl | 26.11 | None |
| 627 | paddle_shifters | 1 | 0 |
| 814 | base_variant_id | 649 | 652 |
| 826 | base_variant_id | 218 | 220 |

**powertrain: 2 cells**

| id | column | before | after |
|---|---|---|---|
| 68 | description | '1197cc 89.7bhp Petrol' | '1197cc 88.51bhp Petrol' |
| 68 | power_bhp | 89.7 | 88.51 |

**sqlite_sequence**

- source_observation: 3757 -> 3779
- field_provenance: 37319 -> 37341
- evidence_amendment: 69 -> 91
- evidence_quarantine: 698 -> 720

**evidence_amendment (new rows)**

| id | table | target | column | old | new | reason |
|---|---|---|---|---|---|---|
| 70 | variant | 245 | mileage_arai_kmpl | 26.78 | None | OEM_UNIT_KMKG_IN_KMPL |
| 71 | variant | 245 | mileage_arai_km_per_kg | None | 26.78 | OEM_UNIT_KMKG_IN_KMPL |
| 72 | variant | 213 | mileage_arai_kmpl | 26.11 | None | OEM_UNIT_KMKG_IN_KMPL |
| 73 | variant | 213 | mileage_arai_km_per_kg | None | 26.11 | OEM_UNIT_KMKG_IN_KMPL |
| 74 | variant | 591 | mileage_arai_kmpl | 26.11 | None | OEM_UNIT_KMKG_IN_KMPL |
| 75 | variant | 556 | mileage_arai_kmpl | 27.02 | None | OEM_UNIT_KMKG_IN_KMPL |
| 76 | variant | 556 | mileage_arai_km_per_kg | 26.6 | 27.02 | OEM_SPOTCHECK_VERIFIED |
| 77 | variant | 217 | mileage_arai_kmpl | 26.23 | None | OEM_UNIT_KMKG_IN_KMPL |
| 78 | variant | 217 | mileage_arai_km_per_kg | None | 26.23 | OEM_UNIT_KMKG_IN_KMPL |
| 79 | variant | 5 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 80 | variant | 15 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 81 | variant | 16 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 82 | variant | 21 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 83 | variant | 23 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 84 | variant | 158 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 85 | variant | 561 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 86 | variant | 566 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 87 | variant | 627 | paddle_shifters | 1 | 0 | OEM_BROCHURE_AT_ONLY |
| 88 | powertrain | 68 | power_bhp | 89.7 | 88.51 | OEM_UNIT_PS_AS_BHP |
| 89 | powertrain | 68 | description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 90 | variant | 814 | base_variant_id | 649 | 652 | EDITION_REBASE_OEM_BROCHURE |
| 91 | variant | 826 | base_variant_id | 218 | 220 | EDITION_REBASE_OEM_BROCHURE |

**field_provenance / source_observation (new rows)**

| fp id | variant | field | value | obs id | pdf page |
|---|---|---|---|---|---|
| 37320 | 245 | mileage_arai_km_per_kg | 26.78 | 3758 | maruti_suzuki_eeco_brochure.pdf p2 (d964c7b5) |
| 37321 | 213 | mileage_arai_km_per_kg | 26.11 | 3759 | maruti_suzuki_ertiga_brochure.pdf p7 (d5a10fb1) |
| 37322 | 556 | mileage_arai_km_per_kg | 27.02 | 3760 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37323 | 217 | mileage_arai_km_per_kg | 26.23 | 3761 | NEXA-Xl6-Brochure.pdf p15 (e66cbeec) |
| 37324 | 5 | paddle_shifters | 0 | 3762 | Hyundai_Creta_Brochure_Official.pdf p14 (cc5b2fbc) |
| 37325 | 15 | paddle_shifters | 0 | 3763 | Hyundai_Creta_Brochure_Official.pdf p14 (cc5b2fbc) |
| 37326 | 16 | paddle_shifters | 0 | 3764 | Hyundai_Creta_Brochure_Official.pdf p14 (cc5b2fbc) |
| 37327 | 21 | paddle_shifters | 0 | 3765 | Hyundai_Creta_Brochure_Official.pdf p14 (cc5b2fbc) |
| 37328 | 23 | paddle_shifters | 0 | 3766 | Hyundai_Creta_Brochure_Official.pdf p14 (cc5b2fbc) |
| 37329 | 158 | paddle_shifters | 0 | 3767 | hyundai_venue_brochure.pdf p20 (00eabf1c) |
| 37330 | 561 | paddle_shifters | 0 | 3768 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37331 | 566 | paddle_shifters | 0 | 3769 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37332 | 627 | paddle_shifters | 0 | 3770 | volkswagen_taigun_brochure.pdf p10 (b2a396b5) |
| 37333 | 476 | power_bhp | 88.51 | 3771 | toyota_glanza_brochure.pdf p1 (fd682f60) |
| 37334 | 477 | power_bhp | 88.51 | 3772 | toyota_glanza_brochure.pdf p1 (fd682f60) |
| 37335 | 478 | power_bhp | 88.51 | 3773 | toyota_glanza_brochure.pdf p1 (fd682f60) |
| 37336 | 480 | power_bhp | 88.51 | 3774 | toyota_glanza_brochure.pdf p1 (fd682f60) |
| 37337 | 481 | power_bhp | 88.51 | 3775 | toyota_glanza_brochure.pdf p1 (fd682f60) |
| 37338 | 483 | power_bhp | 88.51 | 3776 | toyota_glanza_brochure.pdf p1 (fd682f60) |
| 37339 | 484 | power_bhp | 88.51 | 3777 | toyota_glanza_brochure.pdf p1 (fd682f60) |
| 37340 | 814 | base_variant_id | 652 | 3778 | honda_elevate_brochure.pdf p48 (3b794463) |
| 37341 | 826 | base_variant_id | 220 | 3779 | NEXA-Xl6-Brochure.pdf p15 (e66cbeec) |

## v_variant_canonical_q cell changes (all)

| id | column | before | after |
|---|---|---|---|
| 5 | paddle_shifters | 1 | 0 |
| 15 | paddle_shifters | 1 | 0 |
| 16 | paddle_shifters | 1 | 0 |
| 21 | paddle_shifters | 1 | 0 |
| 23 | paddle_shifters | 1 | 0 |
| 158 | paddle_shifters | 1 | 0 |
| 213 | mileage_arai_km_per_kg | None | 26.11 |
| 213 | mileage_arai_kmpl | 26.11 | None |
| 216 | paddle_shifters | 1 | None |
| 217 | mileage_arai_km_per_kg | None | 26.23 |
| 217 | mileage_arai_kmpl | 26.23 | None |
| 217 | paddle_shifters | 1 | None |
| 218 | paddle_shifters | 1 | None |
| 220 | paddle_shifters | 1 | None |
| 245 | mileage_arai_km_per_kg | None | 26.78 |
| 245 | mileage_arai_kmpl | 26.78 | None |
| 345 | mileage_arai_kmpl | 26.2 | None |
| 556 | mileage_arai_km_per_kg | 26.6 | 27.02 |
| 556 | mileage_arai_kmpl | 27.02 | None |
| 561 | paddle_shifters | 1 | 0 |
| 566 | paddle_shifters | 1 | 0 |
| 591 | mileage_arai_kmpl | 26.11 | None |
| 627 | paddle_shifters | 1 | 0 |
| 814 | adas_available | 0 | 1 |
| 814 | base_variant_id | 649 | 652 |
| 814 | connected_car_features | 0 | 1 |
| 814 | price_ex_showroom | 1379000.0 | 1502000.0 |
| 826 | base_variant_id | 218 | 220 |
| 826 | paddle_shifters | 1 | None |
| 826 | price_ex_showroom | 1253800.0 | 1302100.0 |
| 826 | tyre_pressure_monitoring_system | 0 | 1 |
| 826 | ventilated_front_seats | 0 | 1 |

## Rebased editions: every inherited cell (own raw value NULL)


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

## Schema objects changed

### evidence_quarantine
before:
```sql
CREATE TABLE evidence_quarantine (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  target_table    TEXT NOT NULL CHECK (target_table IN
                   ('source_observation','field_provenance','variant','safety_test','safety_test_applicability')),
  target_id       INTEGER NOT NULL,
  target_field    TEXT,
  reason_code     TEXT NOT NULL,
  phase           TEXT NOT NULL,
  note            TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  released_at     TEXT,
  released_reason TEXT,
  CHECK (target_table <> 'variant' OR target_field IS NOT NULL),
  CHECK (released_at IS NULL OR released_reason IS NOT NULL)
)
```
after:
```sql
CREATE TABLE evidence_quarantine (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  target_table    TEXT NOT NULL CHECK (target_table IN
                   ('source_observation','field_provenance','variant','safety_test','safety_test_applicability','warranty')),
  target_id       INTEGER NOT NULL,
  target_field    TEXT,
  reason_code     TEXT NOT NULL,
  phase           TEXT NOT NULL,
  note            TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  released_at     TEXT,
  released_reason TEXT,
  CHECK (target_table NOT IN ('variant','warranty') OR target_field IS NOT NULL),
  CHECK (released_at IS NULL OR released_reason IS NOT NULL)
)
```
### v_variant_canonical_q
before:
```sql
CREATE VIEW v_variant_canonical_q AS
  SELECT
    v.id,
    v.model_id,
    v.generation_id,
    v.powertrain_id,
    v.name,
    v.full_name,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('transmission','*')) THEN NULL ELSE v.transmission END AS transmission,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('drivetrain','*')) THEN NULL ELSE v.drivetrain END AS drivetrain,
    v.is_discontinued,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('price_ex_showroom','*')) OR (v.price_ex_showroom IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('price_ex_showroom','*'))) THEN NULL ELSE COALESCE(v.price_ex_showroom, bv.price_ex_showroom) END AS price_ex_showroom,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('length_mm','*')) OR (v.length_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('length_mm','*'))) THEN NULL ELSE COALESCE(v.length_mm, bv.length_mm) END AS length_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('width_mm','*')) OR (v.width_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('width_mm','*'))) THEN NULL ELSE COALESCE(v.width_mm, bv.width_mm) END AS width_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('height_mm','*')) OR (v.height_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('height_mm','*'))) THEN NULL ELSE COALESCE(v.height_mm, bv.height_mm) END AS height_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('wheelbase_mm','*')) OR (v.wheelbase_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('wheelbase_mm','*'))) THEN NULL ELSE COALESCE(v.wheelbase_mm, bv.wheelbase_mm) END AS wheelbase_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('ground_clearance_mm','*')) OR (v.ground_clearance_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('ground_clearance_mm','*'))) THEN NULL ELSE COALESCE(v.ground_clearance_mm, bv.ground_clearance_mm) END AS ground_clearance_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('kerb_weight_kg','*')) OR (v.kerb_weight_kg IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('kerb_weight_kg','*'))) THEN NULL ELSE COALESCE(v.kerb_weight_kg, bv.kerb_weight_kg) END AS kerb_weight_kg,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('seating_capacity','*')) OR (v.seating_capacity IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('seating_capacity','*'))) THEN NULL ELSE COALESCE(v.seating_capacity, bv.seating_capacity) END AS seating_capacity,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('boot_space_litres','*')) OR (v.boot_space_litres IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('boot_space_litres','*'))) THEN NULL ELSE COALESCE(v.boot_space_litres, bv.boot_space_litres) END AS boot_space_litres,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('fuel_tank_litres','*')) OR (v.fuel_tank_litres IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('fuel_tank_litres','*'))) THEN NULL ELSE COALESCE(v.fuel_tank_litres, bv.fuel_tank_litres) END AS fuel_tank_litres,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('mileage_arai_kmpl','*')) OR (v.mileage_arai_kmpl IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('mileage_arai_kmpl','*'))) THEN NULL ELSE COALESCE(v.mileage_arai_kmpl, bv.mileage_arai_kmpl) END AS mileage_arai_kmpl,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('mileage_arai_km_per_kg','*')) OR (v.mileage_arai_km_per_kg IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('mileage_arai_km_per_kg','*'))) THEN NULL ELSE COALESCE(v.mileage_arai_km_per_kg, bv.mileage_arai_km_per_kg) END AS mileage_arai_km_per_kg,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('claimed_ev_range_km','*')) OR (v.claimed_ev_range_km IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('claimed_ev_range_km','*'))) THEN NULL ELSE COALESCE(v.claimed_ev_range_km, bv.claimed_ev_range_km) END AS claimed_ev_range_km,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('airbags','*')) OR (v.airbags IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('airbags','*'))) THEN NULL ELSE COALESCE(v.airbags, bv.airbags) END AS airbags,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('abs','*')) OR (v.abs IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('abs','*'))) THEN NULL ELSE COALESCE(v.abs, bv.abs) END AS abs,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('esc','*')) OR (v.esc IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('esc','*'))) THEN NULL ELSE COALESCE(v.esc, bv.esc) END AS esc,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('hill_assist','*')) OR (v.hill_assist IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('hill_assist','*'))) THEN NULL ELSE COALESCE(v.hill_assist, bv.hill_assist) END AS hill_assist,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('tyre_pressure_monitoring_system','*')) OR (v.tyre_pressure_monitoring_system IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('tyre_pressure_monitoring_system','*'))) THEN NULL ELSE COALESCE(v.tyre_pressure_monitoring_system, bv.tyre_pressure_monitoring_system) END AS tyre_pressure_monitoring_system,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_parking_sensors','*')) OR (v.rear_parking_sensors IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_parking_sensors','*'))) THEN NULL ELSE COALESCE(v.rear_parking_sensors, bv.rear_parking_sensors) END AS rear_parking_sensors,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_camera','*')) OR (v.rear_camera IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_camera','*'))) THEN NULL ELSE COALESCE(v.rear_camera, bv.rear_camera) END AS rear_camera,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('camera_360','*')) OR (v.camera_360 IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('camera_360','*'))) THEN NULL ELSE COALESCE(v.camera_360, bv.camera_360) END AS camera_360,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('adas_available','*')) OR (v.adas_available IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('adas_available','*'))) THEN NULL ELSE COALESCE(v.adas_available, bv.adas_available) END AS adas_available,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('adas_tier','*')) OR (v.adas_tier IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('adas_tier','*'))) THEN NULL ELSE COALESCE(v.adas_tier, bv.adas_tier) END AS adas_tier,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('automatic_climate_control','*')) OR (v.automatic_climate_control IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('automatic_climate_control','*'))) THEN NULL ELSE COALESCE(v.automatic_climate_control, bv.automatic_climate_control) END AS automatic_climate_control,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_ac_vents','*')) OR (v.rear_ac_vents IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_ac_vents','*'))) THEN NULL ELSE COALESCE(v.rear_ac_vents, bv.rear_ac_vents) END AS rear_ac_vents,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('sunroof','*')) OR (v.sunroof IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('sunroof','*'))) THEN NULL ELSE COALESCE(v.sunroof, bv.sunroof) END AS sunroof,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('ventilated_front_seats','*')) OR (v.ventilated_front_seats IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('ventilated_front_seats','*'))) THEN NULL ELSE COALESCE(v.ventilated_front_seats, bv.ventilated_front_seats) END AS ventilated_front_seats,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('cruise_control','*')) OR (v.cruise_control IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('cruise_control','*'))) THEN NULL ELSE COALESCE(v.cruise_control, bv.cruise_control) END AS cruise_control,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('paddle_shifters','*')) OR (v.paddle_shifters IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('paddle_shifters','*'))) THEN NULL ELSE COALESCE(v.paddle_shifters, bv.paddle_shifters) END AS paddle_shifters,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('wireless_charging','*')) OR (v.wireless_charging IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('wireless_charging','*'))) THEN NULL ELSE COALESCE(v.wireless_charging, bv.wireless_charging) END AS wireless_charging,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('heads_up_display','*')) OR (v.heads_up_display IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('heads_up_display','*'))) THEN NULL ELSE COALESCE(v.heads_up_display, bv.heads_up_display) END AS heads_up_display,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('drive_modes','*')) OR (v.drive_modes IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('drive_modes','*'))) THEN NULL ELSE COALESCE(v.drive_modes, bv.drive_modes) END AS drive_modes,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('connected_car_features','*')) OR (v.connected_car_features IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('connected_car_features','*'))) THEN NULL ELSE COALESCE(v.connected_car_features, bv.connected_car_features) END AS connected_car_features,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('android_auto','*')) OR (v.android_auto IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('android_auto','*'))) THEN NULL ELSE COALESCE(v.android_auto, bv.android_auto) END AS android_auto,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('apple_carplay','*')) OR (v.apple_carplay IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('apple_carplay','*'))) THEN NULL ELSE COALESCE(v.apple_carplay, bv.apple_carplay) END AS apple_carplay,
    v.v6_row_index,
    v.created_at,
    v.updated_at,
    v.base_variant_id,
    v.edition_classification
  FROM variant v
  LEFT JOIN variant bv ON bv.id = v.base_variant_id
```
after:
```sql
CREATE VIEW v_variant_canonical_q AS
  SELECT
    v.id,
    v.model_id,
    v.generation_id,
    v.powertrain_id,
    v.name,
    v.full_name,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('transmission','*')) THEN NULL ELSE v.transmission END AS transmission,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('drivetrain','*')) THEN NULL ELSE v.drivetrain END AS drivetrain,
    v.is_discontinued,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('price_ex_showroom','*')) OR (v.price_ex_showroom IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('price_ex_showroom','*'))) THEN NULL ELSE COALESCE(v.price_ex_showroom, bv.price_ex_showroom) END AS price_ex_showroom,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('length_mm','*')) OR (v.length_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('length_mm','*'))) THEN NULL ELSE COALESCE(v.length_mm, bv.length_mm) END AS length_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('width_mm','*')) OR (v.width_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('width_mm','*'))) THEN NULL ELSE COALESCE(v.width_mm, bv.width_mm) END AS width_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('height_mm','*')) OR (v.height_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('height_mm','*'))) THEN NULL ELSE COALESCE(v.height_mm, bv.height_mm) END AS height_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('wheelbase_mm','*')) OR (v.wheelbase_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('wheelbase_mm','*'))) THEN NULL ELSE COALESCE(v.wheelbase_mm, bv.wheelbase_mm) END AS wheelbase_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('ground_clearance_mm','*')) OR (v.ground_clearance_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('ground_clearance_mm','*'))) THEN NULL ELSE COALESCE(v.ground_clearance_mm, bv.ground_clearance_mm) END AS ground_clearance_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('kerb_weight_kg','*')) OR (v.kerb_weight_kg IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('kerb_weight_kg','*'))) THEN NULL ELSE COALESCE(v.kerb_weight_kg, bv.kerb_weight_kg) END AS kerb_weight_kg,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('seating_capacity','*')) OR (v.seating_capacity IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('seating_capacity','*'))) THEN NULL ELSE COALESCE(v.seating_capacity, bv.seating_capacity) END AS seating_capacity,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('boot_space_litres','*')) OR (v.boot_space_litres IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('boot_space_litres','*'))) THEN NULL ELSE COALESCE(v.boot_space_litres, bv.boot_space_litres) END AS boot_space_litres,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('fuel_tank_litres','*')) OR (v.fuel_tank_litres IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('fuel_tank_litres','*'))) THEN NULL ELSE COALESCE(v.fuel_tank_litres, bv.fuel_tank_litres) END AS fuel_tank_litres,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('mileage_arai_kmpl','*')) OR (v.mileage_arai_kmpl IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('mileage_arai_kmpl','*'))) THEN NULL ELSE COALESCE(v.mileage_arai_kmpl, bv.mileage_arai_kmpl) END AS mileage_arai_kmpl,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('mileage_arai_km_per_kg','*')) OR (v.mileage_arai_km_per_kg IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('mileage_arai_km_per_kg','*'))) THEN NULL ELSE COALESCE(v.mileage_arai_km_per_kg, bv.mileage_arai_km_per_kg) END AS mileage_arai_km_per_kg,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('claimed_ev_range_km','*')) OR (v.claimed_ev_range_km IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('claimed_ev_range_km','*'))) THEN NULL ELSE COALESCE(v.claimed_ev_range_km, bv.claimed_ev_range_km) END AS claimed_ev_range_km,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('airbags','*')) OR (v.airbags IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('airbags','*'))) THEN NULL ELSE COALESCE(v.airbags, bv.airbags) END AS airbags,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('abs','*')) OR (v.abs IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('abs','*'))) THEN NULL ELSE COALESCE(v.abs, bv.abs) END AS abs,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('esc','*')) OR (v.esc IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('esc','*'))) THEN NULL ELSE COALESCE(v.esc, bv.esc) END AS esc,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('hill_assist','*')) OR (v.hill_assist IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('hill_assist','*'))) THEN NULL ELSE COALESCE(v.hill_assist, bv.hill_assist) END AS hill_assist,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('tyre_pressure_monitoring_system','*')) OR (v.tyre_pressure_monitoring_system IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('tyre_pressure_monitoring_system','*'))) THEN NULL ELSE COALESCE(v.tyre_pressure_monitoring_system, bv.tyre_pressure_monitoring_system) END AS tyre_pressure_monitoring_system,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_parking_sensors','*')) OR (v.rear_parking_sensors IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_parking_sensors','*'))) THEN NULL ELSE COALESCE(v.rear_parking_sensors, bv.rear_parking_sensors) END AS rear_parking_sensors,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_camera','*')) OR (v.rear_camera IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_camera','*'))) THEN NULL ELSE COALESCE(v.rear_camera, bv.rear_camera) END AS rear_camera,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('camera_360','*')) OR (v.camera_360 IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('camera_360','*'))) THEN NULL ELSE COALESCE(v.camera_360, bv.camera_360) END AS camera_360,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('adas_available','*')) OR (v.adas_available IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('adas_available','*'))) THEN NULL ELSE COALESCE(v.adas_available, bv.adas_available) END AS adas_available,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('automatic_climate_control','*')) OR (v.automatic_climate_control IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('automatic_climate_control','*'))) THEN NULL ELSE COALESCE(v.automatic_climate_control, bv.automatic_climate_control) END AS automatic_climate_control,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_ac_vents','*')) OR (v.rear_ac_vents IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_ac_vents','*'))) THEN NULL ELSE COALESCE(v.rear_ac_vents, bv.rear_ac_vents) END AS rear_ac_vents,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('sunroof','*')) OR (v.sunroof IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('sunroof','*'))) THEN NULL ELSE COALESCE(v.sunroof, bv.sunroof) END AS sunroof,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('ventilated_front_seats','*')) OR (v.ventilated_front_seats IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('ventilated_front_seats','*'))) THEN NULL ELSE COALESCE(v.ventilated_front_seats, bv.ventilated_front_seats) END AS ventilated_front_seats,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('cruise_control','*')) OR (v.cruise_control IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('cruise_control','*'))) THEN NULL ELSE COALESCE(v.cruise_control, bv.cruise_control) END AS cruise_control,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('paddle_shifters','*')) OR (v.paddle_shifters IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('paddle_shifters','*'))) THEN NULL ELSE COALESCE(v.paddle_shifters, bv.paddle_shifters) END AS paddle_shifters,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('wireless_charging','*')) OR (v.wireless_charging IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('wireless_charging','*'))) THEN NULL ELSE COALESCE(v.wireless_charging, bv.wireless_charging) END AS wireless_charging,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('heads_up_display','*')) OR (v.heads_up_display IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('heads_up_display','*'))) THEN NULL ELSE COALESCE(v.heads_up_display, bv.heads_up_display) END AS heads_up_display,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('drive_modes','*')) OR (v.drive_modes IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('drive_modes','*'))) THEN NULL ELSE COALESCE(v.drive_modes, bv.drive_modes) END AS drive_modes,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('connected_car_features','*')) OR (v.connected_car_features IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('connected_car_features','*'))) THEN NULL ELSE COALESCE(v.connected_car_features, bv.connected_car_features) END AS connected_car_features,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('android_auto','*')) OR (v.android_auto IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('android_auto','*'))) THEN NULL ELSE COALESCE(v.android_auto, bv.android_auto) END AS android_auto,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('apple_carplay','*')) OR (v.apple_carplay IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('apple_carplay','*'))) THEN NULL ELSE COALESCE(v.apple_carplay, bv.apple_carplay) END AS apple_carplay,
    v.v6_row_index,
    v.created_at,
    v.updated_at,
    v.base_variant_id,
    v.edition_classification
  FROM variant v
  LEFT JOIN variant bv ON bv.id = v.base_variant_id
```
### v_warranty_q
before:
```sql
None
```
after:
```sql
CREATE VIEW v_warranty_q AS
  SELECT
    w.id,
    w.manufacturer_id,
    w.model_id,
    CASE WHEN w.model_id IS NULL THEN 'MAKE' ELSE 'MODEL' END AS grain,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('warranty_years','*')) THEN NULL ELSE w.warranty_years END AS warranty_years,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('warranty_km','*')) THEN NULL ELSE w.warranty_km END AS warranty_km,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('battery_warranty_years','*')) THEN NULL ELSE w.battery_warranty_years END AS battery_warranty_years,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('battery_warranty_km','*')) THEN NULL ELSE w.battery_warranty_km END AS battery_warranty_km,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('extended_warranty_available','*')) THEN NULL ELSE w.extended_warranty_available END AS extended_warranty_available,
    w.source,
    w.source_url,
    0 AS has_provenance  -- constant: field_provenance/source_observation reference variant rows only (no schema change made)
  FROM warranty w
```
