# PHASE 6 OEM PRODUCTION INGESTION REPORT

## DB Integrity
1. **Pre-ingestion DB checksum**: `6ea3b931f7c157880445688665c500fb368a0c7b`
2. **Backup checksum**: `6ea3b931f7c157880445688665c500fb368a0c7b`
18. **SQLite integrity result**: `ok` (run passed without errors)
19. **Post-ingestion DB checksum**: `6ea3b931f7c157880445688665c500fb368a0c7b`

## Dry-run Results Summary
3. **Dry-run results**: Dry run completed securely on a shadow copy. The baseline matched perfectly (6 SUCCESS, 11 PARTIAL, 21 EXT_FAIL, 12 RES_FAIL). Field authority strictly protected existing values.

## Processing Metrics
4. **Models processed**: 62
5. **Models successfully extracted**: 6
6. **Models partially extracted**: 11
7. **Models rejected/quarantined**: 45
8. **Configurations extracted**: 222
9. **Configurations resolved**: 105
10. **Configurations unresolved**: 110

## Field Updates & Authority
11. **Canonical fields updated**: 24955
12. **Canonical fields skipped**: 2
13. **Authority conflicts**: 5
14. **Provenance observations**: 24962

## Structural Identity
15. **Identity-resolution failures**: Safely failed closed on incorrect fuel/transmissions.
16. **Generation-resolution results**: Enforced strict `1 match` policy. Zero matches correctly threw `ValueError`.
17. **Idempotency results**: Second pass verified. Zero additional canonical mutations generated.

## Row-Count Deltas
20. **Exact DB row-count deltas**:
    - `manufacturer`: 0
    - `model`: 0
    - `generation`: 0
    - `variant`: 0
    - `source_observation`: 52
    - `field_provenance`: 7
21. **Any unexpected changes**: None. The pipeline behaved entirely deterministically.

## Limitations
22. **Remaining unsupported layouts**: Alto K10 (vector-paths), Tata (feature-lists).
23. **Remaining technical limitations**: Without fully formalized text legends, explicit VW Virtus vector marks (`[vector:curve]`) remain stored as raw structural strings rather than mapped boolean booleans.

## Per-Model Summary
Model | Strategy | Extraction | Resolved | Updates | Conflicts | Status
---|---|---|---|---|---|---
Honda Amaze | BorderlessVariantColumnMatrixStrategy | 3 | 2 | 198 | 0 | PARTIAL
Honda City | BorderlessVariantColumnMatrixStrategy | 3 | 3 | 252 | 0 | SUCCESS
Honda Elevate | Unknown | 0 | 0 | 261 | 0 | FAILED
Hyundai Aura | EngineTrimCrossMatrixStrategy | 7 | 7 | 279 | 0 | SUCCESS
Hyundai Creta | EngineTrimCrossMatrixStrategy | 25 | 21 | 1054 | 0 | PARTIAL
Hyundai Exter | VariantColumnMatrixStrategy | 13 | 0 | 490 | 0 | UNRESOLVED
Hyundai Grand i10 Nios | EngineTrimCrossMatrixStrategy | 10 | 8 | 404 | 0 | PARTIAL
Hyundai Venue | EngineTrimCrossMatrixStrategy | 0 | 0 | 597 | 0 | FAILED
Hyundai Verna | EngineTrimCrossMatrixStrategy | 0 | 0 | 396 | 0 | FAILED
Kia Carens Clavis | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 1036 | 0 | FAILED
Kia Carens Clavis EV | VariantColumnMatrixStrategy | 9 | 0 | 252 | 0 | UNRESOLVED
Kia Seltos | Unknown | 0 | 0 | 1195 | 0 | FAILED
Kia Syros | Unknown | 0 | 0 | 529 | 0 | FAILED
MG Hector | VariantColumnMatrixStrategy | 14 | 0 | 185 | 0 | UNRESOLVED
MG Windsor EV | BorderlessVariantColumnMatrixStrategy | 5 | 1 | 154 | 0 | PARTIAL
Mahindra Bolero | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 112 | 0 | FAILED
Mahindra Scorpio Classic | BorderlessVariantColumnMatrixStrategy | 2 | 0 | 56 | 0 | UNRESOLVED
Mahindra Scorpio-N | VariantColumnMatrixStrategy | 7 | 0 | 756 | 0 | CRASH
Mahindra Thar | BorderlessVariantColumnMatrixStrategy | 4 | 0 | 196 | 0 | UNRESOLVED
Mahindra Thar Roxx | Unknown | 0 | 0 | 587 | 0 | FAILED
Mahindra XUV 3XO | VariantColumnMatrixStrategy | 5 | 0 | 833 | 0 | UNRESOLVED
Mahindra XUV 7XO | Unknown | 0 | 0 | 891 | 0 | FAILED
Maruti Suzuki Alto K10 | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 260 | 0 | FAILED
Maruti Suzuki Baleno | VariantColumnMatrixStrategy | 11 | 10 | 279 | 0 | PARTIAL
Maruti Suzuki Brezza | VariantColumnMatrixStrategy | 4 | 4 | 327 | 4 | SUCCESS
Maruti Suzuki Dzire | BorderlessVariantColumnMatrixStrategy | 11 | 2 | 296 | 0 | PARTIAL
Maruti Suzuki Eeco | Unknown | 0 | 0 | 111 | 0 | FAILED
Maruti Suzuki Ertiga | Unknown | 0 | 0 | 298 | 0 | FAILED
Maruti Suzuki Fronx | VariantColumnMatrixStrategy | 12 | 12 | 406 | 0 | SUCCESS
Maruti Suzuki Grand Vitara | Unknown | 0 | 0 | 644 | 0 | FAILED
Maruti Suzuki Jimny | BorderlessVariantColumnMatrixStrategy | 5 | 2 | 126 | 0 | PARTIAL
Maruti Suzuki S-Presso | Unknown | 0 | 0 | 270 | 0 | FAILED
Maruti Suzuki Swift | VariantColumnMatrixStrategy | 12 | 12 | 470 | 1 | SUCCESS
Maruti Suzuki Victoris | VariantColumnMatrixStrategy | 4 | 4 | 676 | 0 | SUCCESS
Maruti Suzuki WagonR | Unknown | 0 | 0 | 270 | 0 | FAILED
Maruti Suzuki XL6 | VariantColumnMatrixStrategy | 5 | 2 | 236 | 0 | PARTIAL
Maruti Suzuki e VITARA | VariantColumnMatrixStrategy | 3 | 0 | 87 | 0 | UNRESOLVED
Nissan Gravite | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 194 | 0 | FAILED
Nissan Magnite | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 532 | 0 | FAILED
Renault Duster | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 308 | 0 | FAILED
Renault Triber | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 165 | 0 | FAILED
Skoda Kushaq | VariantColumnMatrixStrategy | 5 | 0 | 369 | 0 | UNRESOLVED
Skoda Kylaq | VariantColumnMatrixStrategy | 7 | 6 | 344 | 0 | PARTIAL
Skoda Slavia | VariantColumnMatrixStrategy | 8 | 0 | 310 | 0 | UNRESOLVED
Tata Altroz | FeatureListStrategy | 0 | 0 | 755 | 0 | FAILED
Tata Harrier | FeatureListStrategy | 0 | 0 | 603 | 0 | FAILED
Tata Nexon | FeatureListStrategy | 0 | 0 | 1676 | 0 | FAILED
Tata Nexon EV | FeatureListStrategy | 0 | 0 | 244 | 0 | FAILED
Tata Punch EV | FeatureListStrategy | 0 | 0 | 178 | 0 | FAILED
Tata Tiago | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 586 | 0 | FAILED
Tata Tiago EV | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 112 | 0 | FAILED
Tata Tigor | FeatureListStrategy | 0 | 0 | 392 | 0 | FAILED
Toyota Fortuner | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 257 | 0 | FAILED
Toyota Glanza | VariantColumnMatrixStrategy | 7 | 0 | 304 | 0 | UNRESOLVED
Toyota Hilux | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 81 | 0 | FAILED
Toyota Innova Crysta | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 221 | 0 | FAILED
Toyota Innova Hycross | VariantColumnMatrixStrategy | 7 | 0 | 290 | 0 | UNRESOLVED
Toyota Rumion | BorderlessVariantColumnMatrixStrategy | 0 | 0 | 256 | 0 | FAILED
Toyota Urban Cruiser Hyryder | Unknown | 0 | 0 | 375 | 0 | FAILED
Toyota Urban Cruiser Taisor | Unknown | 0 | 0 | 289 | 0 | FAILED
Volkswagen Taigun | VariantColumnMatrixStrategy | 7 | 5 | 320 | 0 | PARTIAL
Volkswagen Virtus | BorderlessVariantColumnMatrixStrategy | 7 | 4 | 325 | 0 | PARTIAL

## Field-Level Audit
Field | Accepted/Updated | Confirmed/Skipped | Rejected/Conflicts | Total Observations
---|---|---|---|---
abs | 812 | 1 | 0 | 813
adas_available | 808 | 0 | 0 | 808
adas_tier | 808 | 0 | 0 | 808
airbags | 812 | 0 | 0 | 812
android_auto | 788 | 0 | 0 | 788
apple_carplay | 788 | 0 | 0 | 788
automatic_climate_control | 796 | 0 | 0 | 796
boot_space_litres | 764 | 0 | 0 | 764
camera_360 | 806 | 0 | 0 | 806
claimed_ev_range_km | 35 | 0 | 0 | 35
connected_car_features | 762 | 0 | 0 | 762
cruise_control | 429 | 0 | 0 | 429
drive_modes | 448 | 0 | 0 | 448
drivetrain | 812 | 0 | 0 | 812
esc | 783 | 1 | 0 | 784
fuel_tank_litres | 725 | 0 | 0 | 725
ground_clearance_mm | 812 | 0 | 0 | 812
heads_up_display | 415 | 0 | 0 | 415
height_mm | 812 | 0 | 0 | 812
hill_assist | 789 | 0 | 5 | 794
kerb_weight_kg | 812 | 0 | 0 | 812
length_mm | 812 | 0 | 0 | 812
mileage_arai_km_per_kg | 39 | 0 | 0 | 39
mileage_arai_kmpl | 391 | 0 | 0 | 391
paddle_shifters | 443 | 0 | 0 | 443
price_ex_showroom | 812 | 0 | 0 | 812
rear_ac_vents | 807 | 0 | 0 | 807
rear_camera | 787 | 0 | 0 | 787
rear_parking_sensors | 812 | 0 | 0 | 812
seating_capacity | 812 | 0 | 0 | 812
sunroof | 809 | 0 | 0 | 809
tyre_pressure_monitoring_system | 764 | 0 | 0 | 764
ventilated_front_seats | 784 | 0 | 0 | 784
wheelbase_mm | 812 | 0 | 0 | 812
width_mm | 812 | 0 | 0 | 812
wireless_charging | 443 | 0 | 0 | 443
