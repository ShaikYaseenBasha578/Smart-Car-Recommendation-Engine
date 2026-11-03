# Phase 10G — held items: read-only checkpoint (2026-11-03)

Prod untouched: SHA-1 dedefb537ce36cec5e422c6688a3a85373030b39 before/after (access_step0.txt, access_end.txt).
Holder: com.apple.Virtualization.VirtualMachine PID 4854, FD 2613r; no -wal/-shm. Queries ran on work.db (copy).
No new brochures on disk (newest PDF mtime 2026-09-10; none newer than prod).

## Item-by-item [VERIFIED unless tagged]
| # | Item | KB now | Only provenance | Brochure re-check (10G) | Options | Rec |
|---|------|--------|-----------------|--------------------------|---------|-----|
| 1 | pt 84 Grand Vitara CNG power (548, 549) | 87.8 bhp | v6_migration obs 548/549 | GV p15: no CNG column. 87.8 = the K15C CNG-mode **PS** figure printed by Victoris p16 and Hyryder p14 (64.6 kW = 86.63 bhp) | A NULL + amendment · B twin value 86.63 (cross-model) · C hold | A |
| 2 | pt 88 Victoris strong-hybrid power (567, 570, 571, 574, 575) | 115.6 bhp | v6_migration ×5 | Victoris p16 hybrid column: engine 68 kW, motor 59 kW, no system total ("74 kW (100.6 Ps)" is the CNG car's petrol mode). 115.6 = GV p15 / Hyryder p14 system **PS** (85 kW = 113.99 bhp) | A NULL + amendment · B twin value 113.99 (cross-model) · C hold | A |
| 3 | Grand Vitara 548/549 km/kg 26.6 | 26.6 | v6_migration fp 16871/16904 | GV: no CNG data; matches Hyryder p14 | owner already decided "unverified, no quarantine" | no action |
| 4 | Exter CNG km/kg 27.1 (655, 657, 660, 663, 666) | 27.1 | v6_migration ×5 | Exter brochure: no km/kg anywhere (14 pages, text layer) | needs a new OEM source | no action |
| 5 | Nexon CNG km/kg 17.44 (13 variants) | 17.44 | v6_migration ×13 | Nexon p39 points to the separate iCNG brochure (not on disk) | needs that brochure | no action |
| 6 | WagonR 225 km/kg 33.54 vs 33.47 | 33.54 | v6_migration fp 7149 | CATALOG_CURRENCY (model-year) | with Baleno; model-year dimension = schema change | out of 10G |
| 7 | Edition 833 (Virtus "Anniversary Edition 1.5L Turbo Automatic (DCT)") | TC, pt 103 (999 cc / 114), base 643 (Topline 1.0 TC), price NULL | name + CarWale obs 3668 (tier 3): 1498 cc, 148 bhp, 7-speed DCT | Virtus brochure: no "Anniversary" (10E, re-grepped); 1.5 DSG only on GT Plus | A re-base → base 638, pt 104, transmission DCT (non-OEM evidence) · C hold | owner call |

Option A for 1/2 = `UPDATE powertrain SET power_bhp=NULL, description='1462cc CNG' / '1490cc Petrol Hybrid'` + evidence_amendment
(reason e.g. UNIT_UNVERIFIABLE_NO_OEM_SOURCE). No schema change: evidence_quarantine cannot target powertrain, and the exporter
reads power from powertrain, so NULL is the only way to show "unverified". The v6 observations stay as evidence.
Dry-run must confirm the app handles a NULL power (filter/ranking/detail) before prod.

## Found in passing (not held items, not fixed)
- Resolver mismatches: 91wheels obs 885/888 (Petrol AT) and 897 (Diesel AT) resolved to Nexon CNG variants 86/108;
  v3cars obs 1966/1970/1974/1975/1977 (Exter HX3/HX4/HX6/HX8) all resolved to 655 (HX 2). Only names/prices, no spec cells affected.
- Exter CNG 68.0 (brochure 50.5 kW = 67.72) and Nexon CNG 99.0 (73.52 kW = 98.59): rounding, not PS-as-bhp.
