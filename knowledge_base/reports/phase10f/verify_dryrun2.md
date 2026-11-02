# Phase 10F verification: dryrun2

| Check | Result | Detail |
|---|---|---|
| integrity_check | PASS | ok |
| foreign_key_check = 297 known orphans | PASS | 297 rows |
| variant count = 832 | PASS | 832 |
| active quarantine = 720 + 2 inserts = 722 | PASS | before 720, after 722, inserts 2 |
| A: every corrected power_bhp = brochure kW x 1.34102 (PS x 0.98632 for Duster), 2 dp; description: only the figure changed | PASS | 16 powertrains; mismatches [] |
| A: one power_bhp provenance row per base variant, value and page as cited | PASS | failing powertrains [] |
| A: powertrain rows changed = exactly the 16 in scope | PASS | [70, 71, 72, 73, 74, 75, 77, 79, 80, 81, 82, 83, 85, 86, 87, 117] |
| A: PS-as-bhp scan re-run: (b) empty; PS-ratio groups' high members only held items | PASS | (b) hits 0; PS-ratio high members [84, 88] (held: {84: 'Grand Vitara CNG: brochure has no CNG data', 88: 'Victoris hybrid: brochure prints no total-system power'}); other groups: ['Petrol 998cc 89.0Nm', 'Petrol 1997cc 380.0Nm'] |
| B/C: 558 mileage_arai_km_per_kg = 27.02 with provenance | PASS | value 27.02; 10F provenance [('27.02',)] |
| B/C: 562 mileage_arai_km_per_kg = 27.02 with provenance | PASS | value 27.02; 10F provenance [('27.02',)] |
| C: no CNG variant's km/kg contradicts its own brochure (owner exemptions listed) | PASS | contradictions []; exempt [(225, 'WagonR', 33.54, 33.47)]: {225: 'CATALOG_CURRENCY: KB WagonR 1.0 rows predate the brochure (64.37 bhp = 48 kW vs 50.4 kW printed); 33.54 vs 33.47 held, to be handled with Baleno'} |
| C: CNG km/kg with no own-brochure figure (NEEDS_HUMAN) | INFO | [(75, 'Nexon', 17.44), (80, 'Nexon', 17.44), (83, 'Nexon', 17.44), (86, 'Nexon', 17.44), (89, 'Nexon', 17.44), (94, 'Nexon', 17.44), (98, 'Nexon', 17.44), (103, 'Nexon', 17.44), (107, 'Nexon', 17.44), (108, 'Nexon', 17.44), (115, 'Nexon', 17.44), (117, 'Nexon', 17.44), (118, 'Nexon', 17.44), (548, 'Grand Vitara', 26.6), (549, 'Grand Vitara', 26.6), (655, 'Exter', 27.1), (657, 'Exter', 27.1), (660, 'Exter', 27.1), (663, 'Exter', 27.1), (666, 'Exter', 27.1)] |
| v_variant_canonical_q: only approved cells changed | PASS | 2 cells changed; unexpected [] |
| schema identical to before | PASS | 42 objects |

## New quarantine rows

| id | target_table | target_id | target_field | reason |
|---|---|---|---|---|
| 721 | field_provenance | 17208 | None | CONTRADICTED_BY_OEM_BROCHURE |
| 722 | field_provenance | 17338 | None | CONTRADICTED_BY_OEM_BROCHURE |

## Cell-level diff vs prod (before)

- `evidence_amendment`: +34 / -0
- `evidence_quarantine`: +2 / -0
- `field_provenance`: +82 / -0
- `generation`: +0 / -0
- `manufacturer`: +0 / -0
- `model`: +0 / -0
- `powertrain`: +16 / -16
- `safety_rating`: +0 / -0
- `safety_test`: +0 / -0
- `safety_test_applicability`: +0 / -0
- `source`: +0 / -0
- `source_observation`: +82 / -0
- `sqlite_sequence`: +4 / -4
- `variant`: +2 / -2
- `variant_alias`: +0 / -0
- `warranty`: +0 / -0

**variant: 2 cells**

| id | column | before | after |
|---|---|---|---|
| 558 | mileage_arai_km_per_kg | 26.6 | 27.02 |
| 562 | mileage_arai_km_per_kg | 26.6 | 27.02 |

**powertrain: 32 cells**

| id | column | before | after |
|---|---|---|---|
| 70 | description | '1197cc 89.7bhp Petrol' | '1197cc 88.51bhp Petrol' |
| 70 | power_bhp | 89.7 | 88.51 |
| 71 | description | '1197cc 77.5bhp CNG' | '1197cc 76.44bhp CNG' |
| 71 | power_bhp | 77.5 | 76.44 |
| 72 | description | '998cc 100.1bhp Petrol' | '998cc 98.7bhp Petrol' |
| 72 | power_bhp | 100.1 | 98.7 |
| 73 | description | '1197cc 89.7bhp Petrol' | '1197cc 88.51bhp Petrol' |
| 73 | power_bhp | 89.7 | 88.51 |
| 74 | description | '1197cc 77.5bhp CNG' | '1197cc 76.44bhp CNG' |
| 74 | power_bhp | 77.5 | 76.44 |
| 75 | description | '998cc 100.1bhp Petrol' | '998cc 98.7bhp Petrol' |
| 75 | power_bhp | 100.1 | 98.7 |
| 77 | description | '998cc 56.7bhp CNG' | '998cc 55.92bhp CNG' |
| 77 | power_bhp | 56.7 | 55.92 |
| 79 | description | '998cc 56.7bhp CNG' | '998cc 55.92bhp CNG' |
| 79 | power_bhp | 56.7 | 55.92 |
| 80 | description | '1462cc 103.1bhp Petrol' | '1462cc 101.65bhp Petrol' |
| 80 | power_bhp | 103.1 | 101.65 |
| 81 | description | '1462cc 87.8bhp CNG' | '1462cc 86.63bhp CNG' |
| 81 | power_bhp | 87.8 | 86.63 |
| 82 | description | '1490cc 115.6bhp Petrol Hybrid' | '1490cc 113.99bhp Petrol Hybrid' |
| 82 | power_bhp | 115.6 | 113.99 |
| 83 | description | '1462cc 103.1bhp Petrol' | '1462cc 101.65bhp Petrol' |
| 83 | power_bhp | 103.1 | 101.65 |
| 85 | description | '1490cc 115.6bhp Petrol Hybrid' | '1490cc 113.99bhp Petrol Hybrid' |
| 85 | power_bhp | 115.6 | 113.99 |
| 86 | description | '1462cc 103.1bhp Petrol' | '1462cc 101.65bhp Petrol' |
| 86 | power_bhp | 103.1 | 101.65 |
| 87 | description | '1462cc 87.8bhp CNG' | '1462cc 86.63bhp CNG' |
| 87 | power_bhp | 87.8 | 86.63 |
| 117 | description | '1333cc 163.0bhp Petrol' | '1333cc 160.77bhp Petrol' |
| 117 | power_bhp | 163.0 | 160.77 |

**sqlite_sequence**

- source_observation: 3779 -> 3861
- field_provenance: 37341 -> 37423
- evidence_amendment: 91 -> 125
- evidence_quarantine: 720 -> 722

**evidence_amendment (new rows)**

| id | table | target | column | old | new | reason |
|---|---|---|---|---|---|---|
| 92 | powertrain | 70 | power_bhp | 89.7 | 88.51 | OEM_UNIT_PS_AS_BHP |
| 93 | powertrain | 70 | description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 94 | powertrain | 71 | power_bhp | 77.5 | 76.44 | OEM_UNIT_PS_AS_BHP |
| 95 | powertrain | 71 | description | 1197cc 77.5bhp CNG | 1197cc 76.44bhp CNG | OEM_UNIT_PS_AS_BHP |
| 96 | powertrain | 72 | power_bhp | 100.1 | 98.7 | OEM_UNIT_PS_AS_BHP |
| 97 | powertrain | 72 | description | 998cc 100.1bhp Petrol | 998cc 98.7bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 98 | powertrain | 73 | power_bhp | 89.7 | 88.51 | OEM_UNIT_PS_AS_BHP |
| 99 | powertrain | 73 | description | 1197cc 89.7bhp Petrol | 1197cc 88.51bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 100 | powertrain | 74 | power_bhp | 77.5 | 76.44 | OEM_UNIT_PS_AS_BHP |
| 101 | powertrain | 74 | description | 1197cc 77.5bhp CNG | 1197cc 76.44bhp CNG | OEM_UNIT_PS_AS_BHP |
| 102 | powertrain | 75 | power_bhp | 100.1 | 98.7 | OEM_UNIT_PS_AS_BHP |
| 103 | powertrain | 75 | description | 998cc 100.1bhp Petrol | 998cc 98.7bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 104 | powertrain | 77 | power_bhp | 56.7 | 55.92 | OEM_UNIT_PS_AS_BHP |
| 105 | powertrain | 77 | description | 998cc 56.7bhp CNG | 998cc 55.92bhp CNG | OEM_UNIT_PS_AS_BHP |
| 106 | powertrain | 79 | power_bhp | 56.7 | 55.92 | OEM_UNIT_PS_AS_BHP |
| 107 | powertrain | 79 | description | 998cc 56.7bhp CNG | 998cc 55.92bhp CNG | OEM_UNIT_PS_AS_BHP |
| 108 | powertrain | 80 | power_bhp | 103.1 | 101.65 | OEM_UNIT_PS_AS_BHP |
| 109 | powertrain | 80 | description | 1462cc 103.1bhp Petrol | 1462cc 101.65bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 110 | powertrain | 81 | power_bhp | 87.8 | 86.63 | OEM_UNIT_PS_AS_BHP |
| 111 | powertrain | 81 | description | 1462cc 87.8bhp CNG | 1462cc 86.63bhp CNG | OEM_UNIT_PS_AS_BHP |
| 112 | powertrain | 82 | power_bhp | 115.6 | 113.99 | OEM_UNIT_PS_AS_BHP |
| 113 | powertrain | 82 | description | 1490cc 115.6bhp Petrol Hybrid | 1490cc 113.99bhp Petrol Hybrid | OEM_UNIT_PS_AS_BHP |
| 114 | powertrain | 83 | power_bhp | 103.1 | 101.65 | OEM_UNIT_PS_AS_BHP |
| 115 | powertrain | 83 | description | 1462cc 103.1bhp Petrol | 1462cc 101.65bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 116 | powertrain | 85 | power_bhp | 115.6 | 113.99 | OEM_UNIT_PS_AS_BHP |
| 117 | powertrain | 85 | description | 1490cc 115.6bhp Petrol Hybrid | 1490cc 113.99bhp Petrol Hybrid | OEM_UNIT_PS_AS_BHP |
| 118 | powertrain | 86 | power_bhp | 103.1 | 101.65 | OEM_UNIT_PS_AS_BHP |
| 119 | powertrain | 86 | description | 1462cc 103.1bhp Petrol | 1462cc 101.65bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 120 | powertrain | 87 | power_bhp | 87.8 | 86.63 | OEM_UNIT_PS_AS_BHP |
| 121 | powertrain | 87 | description | 1462cc 87.8bhp CNG | 1462cc 86.63bhp CNG | OEM_UNIT_PS_AS_BHP |
| 122 | powertrain | 117 | power_bhp | 163.0 | 160.77 | OEM_UNIT_PS_AS_BHP |
| 123 | powertrain | 117 | description | 1333cc 163.0bhp Petrol | 1333cc 160.77bhp Petrol | OEM_UNIT_PS_AS_BHP |
| 124 | variant | 558 | mileage_arai_km_per_kg | 26.6 | 27.02 | OEM_BROCHURE_MISMATCH |
| 125 | variant | 562 | mileage_arai_km_per_kg | 26.6 | 27.02 | OEM_BROCHURE_MISMATCH |

**field_provenance / source_observation (new rows)**

| fp id | variant | field | value | obs id | pdf page |
|---|---|---|---|---|---|
| 37342 | 485 | power_bhp | 88.51 | 3780 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37343 | 487 | power_bhp | 88.51 | 3781 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37344 | 488 | power_bhp | 88.51 | 3782 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37345 | 489 | power_bhp | 88.51 | 3783 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37346 | 490 | power_bhp | 88.51 | 3784 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37347 | 486 | power_bhp | 76.44 | 3785 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37348 | 491 | power_bhp | 98.7 | 3786 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37349 | 492 | power_bhp | 98.7 | 3787 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37350 | 493 | power_bhp | 98.7 | 3788 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37351 | 494 | power_bhp | 98.7 | 3789 | toyota_urban_cruiser_taisor_brochure.pdf p21 (b2afc7a7) |
| 37352 | 495 | power_bhp | 88.51 | 3790 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37353 | 497 | power_bhp | 88.51 | 3791 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37354 | 498 | power_bhp | 88.51 | 3792 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37355 | 500 | power_bhp | 88.51 | 3793 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37356 | 501 | power_bhp | 88.51 | 3794 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37357 | 496 | power_bhp | 76.44 | 3795 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37358 | 499 | power_bhp | 76.44 | 3796 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37359 | 502 | power_bhp | 98.7 | 3797 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37360 | 503 | power_bhp | 98.7 | 3798 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37361 | 504 | power_bhp | 98.7 | 3799 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37362 | 505 | power_bhp | 98.7 | 3800 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37363 | 506 | power_bhp | 98.7 | 3801 | Fronx_Brochure.pdf p19 (2c9ad3ad) |
| 37364 | 510 | power_bhp | 55.92 | 3802 | maruti_suzuki_s_presso_brochure.pdf p5 (76d42865) |
| 37365 | 513 | power_bhp | 55.92 | 3803 | maruti_suzuki_s_presso_brochure.pdf p5 (76d42865) |
| 37366 | 518 | power_bhp | 55.92 | 3804 | maruti_suzuki_alto_k10_brochure.pdf p5 (2a87ea04) |
| 37367 | 521 | power_bhp | 55.92 | 3805 | maruti_suzuki_alto_k10_brochure.pdf p5 (2a87ea04) |
| 37368 | 523 | power_bhp | 101.65 | 3806 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37369 | 524 | power_bhp | 101.65 | 3807 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37370 | 525 | power_bhp | 101.65 | 3808 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37371 | 529 | power_bhp | 101.65 | 3809 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37372 | 530 | power_bhp | 101.65 | 3810 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37373 | 532 | power_bhp | 101.65 | 3811 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37374 | 533 | power_bhp | 101.65 | 3812 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37375 | 534 | power_bhp | 101.65 | 3813 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37376 | 526 | power_bhp | 86.63 | 3814 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37377 | 528 | power_bhp | 86.63 | 3815 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37378 | 527 | power_bhp | 113.99 | 3816 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37379 | 531 | power_bhp | 113.99 | 3817 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37380 | 535 | power_bhp | 113.99 | 3818 | toyota_urban_cruiser_hyryder_brochure.pdf p14 (ec7984ce) |
| 37381 | 536 | power_bhp | 101.65 | 3819 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37382 | 537 | power_bhp | 101.65 | 3820 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37383 | 538 | power_bhp | 101.65 | 3821 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37384 | 539 | power_bhp | 101.65 | 3822 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37385 | 540 | power_bhp | 101.65 | 3823 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37386 | 541 | power_bhp | 101.65 | 3824 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37387 | 542 | power_bhp | 101.65 | 3825 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37388 | 543 | power_bhp | 101.65 | 3826 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37389 | 544 | power_bhp | 101.65 | 3827 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37390 | 545 | power_bhp | 101.65 | 3828 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37391 | 546 | power_bhp | 101.65 | 3829 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37392 | 547 | power_bhp | 101.65 | 3830 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37393 | 550 | power_bhp | 113.99 | 3831 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37394 | 551 | power_bhp | 113.99 | 3832 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37395 | 552 | power_bhp | 113.99 | 3833 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37396 | 553 | power_bhp | 113.99 | 3834 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37397 | 554 | power_bhp | 113.99 | 3835 | maruti_suzuki_grand_vitara_brochure.pdf p15 (023ce2e3) |
| 37398 | 555 | power_bhp | 101.65 | 3836 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37399 | 557 | power_bhp | 101.65 | 3837 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37400 | 559 | power_bhp | 101.65 | 3838 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37401 | 560 | power_bhp | 101.65 | 3839 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37402 | 561 | power_bhp | 101.65 | 3840 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37403 | 563 | power_bhp | 101.65 | 3841 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37404 | 564 | power_bhp | 101.65 | 3842 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37405 | 565 | power_bhp | 101.65 | 3843 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37406 | 566 | power_bhp | 101.65 | 3844 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37407 | 568 | power_bhp | 101.65 | 3845 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37408 | 569 | power_bhp | 101.65 | 3846 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37409 | 572 | power_bhp | 101.65 | 3847 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37410 | 573 | power_bhp | 101.65 | 3848 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37411 | 556 | power_bhp | 86.63 | 3849 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37412 | 558 | power_bhp | 86.63 | 3850 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37413 | 562 | power_bhp | 86.63 | 3851 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37414 | 707 | power_bhp | 160.77 | 3852 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37415 | 708 | power_bhp | 160.77 | 3853 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37416 | 709 | power_bhp | 160.77 | 3854 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37417 | 710 | power_bhp | 160.77 | 3855 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37418 | 712 | power_bhp | 160.77 | 3856 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37419 | 713 | power_bhp | 160.77 | 3857 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37420 | 714 | power_bhp | 160.77 | 3858 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37421 | 715 | power_bhp | 160.77 | 3859 | renault_duster_brochure.pdf p20 (10f1f3b6) |
| 37422 | 558 | mileage_arai_km_per_kg | 27.02 | 3860 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |
| 37423 | 562 | mileage_arai_km_per_kg | 27.02 | 3861 | maruti_suzuki_victoris_brochure.pdf p16 (94f94973) |

## v_variant_canonical_q cell changes (all)

| id | column | before | after |
|---|---|---|---|
| 558 | mileage_arai_km_per_kg | 26.6 | 27.02 |
| 562 | mileage_arai_km_per_kg | 26.6 | 27.02 |
