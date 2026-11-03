# 10G pre-go: canonical cells traced to resolver mislinks (report only, no writes)

DB: `work.db` (scratch), a byte copy of prod `dedefb537ce36cec5e422c6688a3a85373030b39`. Scripts: `mislinks.py`, `mislinks_v3.py`, `mislink_report.py`; raw output `mislinks3.txt`.

Method: an aggregator observation (91wheels / v3cars / carwale) is *flagged* when its raw name contradicts the resolved variant on fuel, gearbox or trim. A canonical cell is *traced* when an `accepted`, un-quarantined field_provenance row cites a flagged observation and its value equals the cell in `v_variant_canonical_q`. Trim hits were reviewed by hand.

- **Price: no cell.** All 812 `price_ex_showroom` provenance rows are v6_migration [VERIFIED].
- **Named mislinks:** Nexon obs 885/888/897 have no provenance rows. Exter obs 1966/1970/1974/1975/1977 (HX3–HX8 → v655 HX 2) have 40 `confirmed` rows (zeros and Manual) and no `accepted` row, so no canonical cell depends on them [VERIFIED].

## A. Real mislinks: canonical cell depends on them: 30 cells

| variant | model / KB name | field | canonical | fp | obs (source): raw name | mismatch | other support |
|---|---|---|---|---|---|---|---|
| v34 | XUV 3XO / REVX M (O) Petrol 1.2L Turbo Manual | cruise_control | 0 | fp30668 | obs2183 v3cars: Xuv 3xoRevX M1.2L  Turbo Petrol Manual | trim:revxm≠revxmo | v3cars:confirmed,carwale:confirmed |
| v34 | XUV 3XO / REVX M (O) Petrol 1.2L Turbo Manual | ventilated_front_seats | 0 | fp30669 | obs2183 v3cars: Xuv 3xoRevX M1.2L  Turbo Petrol Manual | trim:revxm≠revxmo | v3cars:confirmed,carwale:confirmed |
| v34 | XUV 3XO / REVX M (O) Petrol 1.2L Turbo Manual | heads_up_display | 0 | fp30670 | obs2183 v3cars: Xuv 3xoRevX M1.2L  Turbo Petrol Manual | trim:revxm≠revxmo | v3cars:confirmed,carwale:confirmed |
| v36 | XUV 3XO / MX3 Petrol 1.2L Turbo Manual | ventilated_front_seats | 0 | fp34159 | obs3148 carwale: MX1 Petrol 1.2L Turbo Manual | trim:mx1≠mx3 | - |
| v50 | XUV 3XO / AX5L Petrol 1.2L Turbo Manual | ventilated_front_seats | 0 | fp30733 | obs2191 v3cars: Xuv 3xoAX51.2L  Turbo Petrol Manual | trim:ax5≠ax5l | - |
| v52 | XUV 3XO / AX7 Petrol 1.2L Turbo Manual Dual Tone | ventilated_front_seats | 0 | fp34312 | obs3170 carwale: AX7 Diesel 1.5L Turbo Manual Dual Tone | fuel:diesel≠petrol | - |
| v54 | XUV 3XO / AX7 Diesel 1.5L Turbo Manual Dual Tone | ventilated_front_seats | 0 | fp34291 | obs3167 carwale: AX7 Petrol 1.2L Turbo Manual Dual Tone | fuel:petrol≠diesel | - |
| v146 | Brezza / ZXi AT | mileage_arai_kmpl | 20.17 | fp26118 | obs1246 91wheels: ZXi+ AT DT | trim:zxiplus≠zxi | - |
| v210 | Ertiga / ZXi MT | mileage_arai_kmpl | 20.3 | fp26323 | obs1277 91wheels: ZXI+ Smart Hybrid AT | gearbox:auto≠Manual; trim:zxiplus≠zxi | - |
| v237 | Dzire / ZXi MT | mileage_arai_kmpl | 25.71 | fp26175 | obs1259 91wheels: ZXi + AT (AGS) | gearbox:auto≠Manual; trim:zxiplus≠zxi | - |
| v252 | Baleno / Alpha MT | mileage_arai_kmpl | 22.94 | fp26063 | obs1229 91wheels: Alpha AT (AGS) | gearbox:auto≠Manual | - |
| v293 | Amaze / ZX MT | mileage_arai_kmpl | 19.46 | fp25444 | obs980 91wheels: ZX AT (CVT) | gearbox:auto≠Manual | - |
| v306 | Innova Crysta / GX+ 8 Seater | mileage_arai_kmpl | 16.0 | fp27666 | obs1587 91wheels: GX FLT 8 Seater | trim:gxflt≠gxplus | - |
| v343 | Altroz / Accomplished S DCA | heads_up_display | 0 | fp31390 | obs2395 v3cars: AltrozAccomplished S1.2L CNG Automatic | fuel:cng≠petrol | - |
| v597 | Jimny / Zeta PRO MT | cruise_control | 0 | fp26439 | obs1331 91wheels: Zeta Pro AT | gearbox:auto≠Manual | - |
| v629 | Taigun / Highline Petrol 1.0L Turbo Automatic (TC) | cruise_control | 1 | fp31748 | obs2589 v3cars: TaigunHighline Plus1.0L  Turbo Petrol Automatic | trim:highlineplus≠highline | - |
| v630 | Taigun / Highline Petrol 1.0L Turbo Manual | cruise_control | 1 | fp31732 | obs2587 v3cars: TaigunHighline Plus1.0L  Turbo Petrol Manual | trim:highlineplus≠highline | - |
| v630 | Taigun / Highline Petrol 1.0L Turbo Manual | heads_up_display | 0 | fp31734 | obs2587 v3cars: TaigunHighline Plus1.0L  Turbo Petrol Manual | trim:highlineplus≠highline | - |
| v631 | Taigun / Highline Plus Petrol 1.0L Turbo Automatic (TC) | cruise_control | 1 | fp31724 | obs2586 v3cars: TaigunHighline1.0L  Turbo Petrol Automatic | trim:highline≠highlineplus | - |
| v632 | Taigun / Highline Plus Petrol 1.0L Turbo Manual | cruise_control | 1 | fp31716 | obs2585 v3cars: TaigunHighline1.0L  Turbo Petrol Manual | trim:highline≠highlineplus | - |
| v819 | Seltos / GTX (A) Petrol 1.5L Automatic (CVT) Dual Tone | heads_up_display | 1 | fp33768 | obs3073 carwale: GTX (O) Petrol 1.5L Turbo Automatic (DCT) | trim:gtxo≠gtxa | carwale:confirmed,carwale:confirmed,carwale:confirmed |
| v821 | Brezza / Zxi Petrol 1.0L Turbo Manual Dual Tone | sunroof | 0 | fp34687 | obs3243 carwale: Vxi Petrol 1.5L Automatic | gearbox:auto≠Manual; trim:vxi≠zxi | carwale:confirmed |
| v821 | Brezza / Zxi Petrol 1.0L Turbo Manual Dual Tone | heads_up_display | 1 | fp34710 | obs3246 carwale: Zxi Plus Petrol 1.0L Turbo Manual Dual Tone | trim:zxiplus≠zxi | carwale:confirmed,carwale:confirmed |
| v822 | Fronx / Alpha Petrol 1.0L Turbo Manual Dual Tone | cruise_control | 0 | fp34827 | obs3271 carwale: Zeta Petrol 1.0L Turbo Automatic (TC) | gearbox:auto≠Manual; trim:zeta≠alpha | carwale:confirmed |
| v822 | Fronx / Alpha Petrol 1.0L Turbo Manual Dual Tone | heads_up_display | 0 | fp34830 | obs3271 carwale: Zeta Petrol 1.0L Turbo Automatic (TC) | gearbox:auto≠Manual; trim:zeta≠alpha | carwale:confirmed |
| v823 | Grand Vitara / Zeta 2WD Petrol 1.5L Manual Dual Tone | heads_up_display | 1 | fp34910 | obs3286 carwale: Alpha 2WD Petrol 1.5L Manual Dual Tone | trim:alpha≠zeta | carwale:confirmed |
| v825 | Victoris / ZXi 2WD Petrol 1.5L Manual Dual Tone | heads_up_display | 1 | fp35140 | obs3330 carwale: ZXi Plus 2WD Petrol 1.5L Manual Dual Tone | trim:zxiplus≠zxi | carwale:confirmed |
| v828 | Magnite / N-Connecta Petrol Manual Dual Tone | cruise_control | 1 | fp35417 | obs3380 carwale: Tekna Petrol Manual Dual Tone | trim:tekna≠nconnecta | carwale:confirmed |
| v830 | Harrier / Pure X Petrol 1.5L Turbo Manual Dark Edition | tyre_pressure_monitoring_system | 1 | fp36007 | obs3484 carwale: Adventure X Dark Edition Petrol 1.5L Turbo Manual | trim:adventurex≠purex | carwale:confirmed |
| v831 | Harrier / Fearless X Dark Edition Diesel 2.0L Turbo Manual | ventilated_front_seats | 0 | fp36176 | obs3514 carwale: Adventure X Plus  Dark Edition Diesel 2.0L Turbo Manual | trim:adventurexplus≠fearlessx | - |

## B. Ambiguous trim (needs a human): 4 cells

| variant | model / KB name | field | canonical | fp | obs (source): raw name | mismatch | other support |
|---|---|---|---|---|---|---|---|
| v416 | XUV 7XO / AX3 Diesel MT | mileage_arai_kmpl | 17.0 | fp25949 | obs1194 91wheels: AX Diesel | trim:ax≠ax3 | - |
| v628 | Taigun / GT Plus Chrome Petrol 1.5L Turbo Automatic (DCT) | heads_up_display | 0 | fp31782 | obs2593 v3cars: TaigunGT Plus1.5L  Turbo Petrol Automatic | trim:gtplus≠gtpluschrome | carwale:confirmed |
| v804 | Carens Clavis EV / HTX 7 | cruise_control | 1 | fp33452 | obs3012 carwale: HTX E 42.0 kWh 7 STR | trim:htxe≠htx | carwale:confirmed |
| v806 | Carens Clavis EV / HTX ER | cruise_control | 1 | fp33469 | obs3016 carwale: HTX E ER 51.4 kWh 6 STR | trim:htxeer≠htxer | carwale:confirmed |

## C. Excluded as naming noise: 35 traced cells

For example 'HX 4' = 'HX4', 'Mid Range' = 'MR', '5Str', and glued v3cars names. Listed in `mislinks3.txt`.

## D. Corroboration counts that drop if the 26 A-set observations are excluded: 116 cells

- v36 adas_available: 2 → 1 sources
- v36 heads_up_display: 2 → 1 sources
- v36 transmission: 1 → 0 sources
- v36 tyre_pressure_monitoring_system: 2 → 1 sources
- v36 ventilated_front_seats: 1 → 0 sources
- v146 adas_available: 2 → 1 sources
- v146 height_mm: 2 → 1 sources
- v146 length_mm: 2 → 1 sources
- v146 mileage_arai_kmpl: 1 → 0 sources
- v146 seating_capacity: 2 → 1 sources
- v146 width_mm: 2 → 1 sources
- v210 adas_available: 2 → 1 sources
- v210 boot_space_litres: 2 → 1 sources
- v210 ground_clearance_mm: 2 → 1 sources
- v210 heads_up_display: 2 → 1 sources
- v210 height_mm: 2 → 1 sources
- v210 length_mm: 2 → 1 sources
- v210 mileage_arai_kmpl: 1 → 0 sources
- v210 seating_capacity: 2 → 1 sources
- v210 tyre_pressure_monitoring_system: 2 → 1 sources
- v210 ventilated_front_seats: 3 → 2 sources
- v210 width_mm: 2 → 1 sources
- v210 wireless_charging: 2 → 1 sources
- v237 adas_available: 2 → 1 sources
- v237 boot_space_litres: 2 → 1 sources
- v237 drivetrain: 2 → 1 sources
- v237 ground_clearance_mm: 2 → 1 sources
- v237 heads_up_display: 2 → 1 sources
- v237 height_mm: 2 → 1 sources
- v237 length_mm: 2 → 1 sources
- v237 mileage_arai_kmpl: 1 → 0 sources
- v237 seating_capacity: 2 → 1 sources
- v237 tyre_pressure_monitoring_system: 2 → 1 sources
- v237 ventilated_front_seats: 3 → 2 sources
- v237 width_mm: 2 → 1 sources
- v252 adas_available: 3 → 2 sources
- v252 boot_space_litres: 2 → 1 sources
- v252 cruise_control: 4 → 3 sources
- v252 drivetrain: 2 → 1 sources
- v252 ground_clearance_mm: 2 → 1 sources
- v252 heads_up_display: 4 → 3 sources
- v252 height_mm: 2 → 1 sources
- v252 length_mm: 2 → 1 sources
- v252 mileage_arai_kmpl: 1 → 0 sources
- v252 seating_capacity: 2 → 1 sources
- v252 tyre_pressure_monitoring_system: 2 → 1 sources
- v252 ventilated_front_seats: 2 → 1 sources
- v252 width_mm: 2 → 1 sources
- v252 wireless_charging: 2 → 1 sources
- v293 adas_available: 2 → 1 sources
- v293 boot_space_litres: 2 → 1 sources
- v293 cruise_control: 3 → 2 sources
- v293 drivetrain: 2 → 1 sources
- v293 ground_clearance_mm: 2 → 1 sources
- v293 heads_up_display: 2 → 1 sources
- v293 height_mm: 2 → 1 sources
- v293 length_mm: 2 → 1 sources
- v293 mileage_arai_kmpl: 1 → 0 sources
- v293 seating_capacity: 2 → 1 sources
- v293 tyre_pressure_monitoring_system: 2 → 1 sources
- v293 ventilated_front_seats: 3 → 2 sources
- v293 width_mm: 2 → 1 sources
- v306 adas_available: 2 → 1 sources
- v306 boot_space_litres: 2 → 1 sources
- v306 cruise_control: 2 → 1 sources
- v306 drivetrain: 2 → 1 sources
- v306 ground_clearance_mm: 2 → 1 sources
- v306 heads_up_display: 2 → 1 sources
- v306 height_mm: 2 → 1 sources
- v306 length_mm: 2 → 1 sources
- v306 mileage_arai_kmpl: 1 → 0 sources
- v306 seating_capacity: 2 → 1 sources
- v306 tyre_pressure_monitoring_system: 2 → 1 sources
- v306 ventilated_front_seats: 2 → 1 sources
- v306 width_mm: 2 → 1 sources
- v343 adas_available: 3 → 2 sources
- v343 cruise_control: 1 → 0 sources
- v343 heads_up_display: 2 → 1 sources
- v343 sunroof: 3 → 2 sources
- v343 ventilated_front_seats: 3 → 2 sources
- v343 wireless_charging: 1 → 0 sources
- v597 adas_available: 2 → 1 sources
- v597 boot_space_litres: 2 → 1 sources
- v597 cruise_control: 2 → 1 sources
- v597 drivetrain: 2 → 1 sources
- v597 ground_clearance_mm: 2 → 1 sources
- v597 heads_up_display: 1 → 0 sources
- v597 height_mm: 2 → 1 sources
- v597 length_mm: 2 → 1 sources
- v597 seating_capacity: 2 → 1 sources
- v597 ventilated_front_seats: 2 → 1 sources
- v597 width_mm: 2 → 1 sources
- v597 wireless_charging: 1 → 0 sources
- v629 adas_available: 3 → 2 sources
- v629 cruise_control: 1 → 0 sources
- v629 heads_up_display: 1 → 0 sources
- v629 sunroof: 2 → 1 sources
- v629 ventilated_front_seats: 3 → 2 sources
- v630 adas_available: 4 → 3 sources
- v630 cruise_control: 1 → 0 sources
- v630 heads_up_display: 2 → 1 sources
- v630 sunroof: 3 → 2 sources
- v630 transmission: 2 → 1 sources
- v630 ventilated_front_seats: 4 → 3 sources
- v631 adas_available: 2 → 1 sources
- v631 cruise_control: 1 → 0 sources
- v631 heads_up_display: 1 → 0 sources
- v631 sunroof: 2 → 1 sources
- v631 ventilated_front_seats: 2 → 1 sources
- v632 adas_available: 2 → 1 sources
- v632 cruise_control: 1 → 0 sources
- v632 heads_up_display: 1 → 0 sources
- v632 sunroof: 2 → 1 sources
- v632 transmission: 1 → 0 sources
- v632 ventilated_front_seats: 2 → 1 sources
- v831 ventilated_front_seats: 1 → 0 sources

The 677 trim-only flags outside the traced set were not hand-reviewed; they affect only `confirmed`/`rejected` rows.
