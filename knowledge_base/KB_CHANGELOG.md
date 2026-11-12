# CarRec knowledge base changelog

Plain-language record of every applied KB phase. Full evidence is in `knowledge_base/reports/`. Open questions for the owner are in [NEEDS_YOU.md](NEEDS_YOU.md).

## 10E — 2026-11-02 — Brochure corrections: CNG mileage, paddle shifters, Glanza power, edition bases
**Why:** CNG cars held km/kg figures in the km/l column, some manual cars claimed paddle shifters, Glanza power was a PS figure labelled bhp, and two editions pointed at the wrong base trim.
**What changed:** 18 variant cells corrected or moved, 4 cells quarantined for paddle shifters and 1 for a suspect unit; 1 powertrain power corrected (7 Glanza variants); 2 editions re-based; 15 contradicted provenance rows and 2 warranty cells quarantined. 22 brochure observations added. Schema: `evidence_quarantine` rebuilt to allow warranty targets, and views updated.
**Examples:**
- Maruti Ertiga ZXi CNG: km/kg blank → 26.11 and km/l 26.11 → blank (brochure, p7)
- Hyundai Creta SX Premium Petrol Manual: paddle shifters yes → no (brochure, p14)
- Honda Elevate ZX Black Edition: base trim 649 → 652 ZX (brochure, p48)
**What app users now see:** Correct km/kg on the affected CNG cars, no false paddle shifters on manuals, and correct Glanza power.
**Not done / held:**
- Virtus edition 833: identity contradiction with no OEM source.
- Altroz 345 km/l: quarantined, because no OEM source prints its km/kg.
- Victoris 558/562 km/kg: not in the approved set (fixed in 10F).
**Prod SHA-1:** `8592508…` → `57f31e4d…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/15 **Ranking-track line:** KB corrections (10E), export re-run: PR #15.

## 10F — 2026-11-02 — PS figures stored as bhp, and two Victoris km/kg values
**Why:** 16 powertrains stored the brochure's PS figure in the bhp column, overstating power by about 1.4%. Two Victoris CNG variants held the Grand Vitara/Hyryder km/kg figure.
**What changed:** 16 powertrain powers corrected (80 base variants, 83 catalogue rows with editions); 2 variant km/kg cells corrected; 2 contradicted provenance rows quarantined; 82 brochure observations added. Schema: none.
**Examples:**
- Maruti Fronx 1.2 petrol: power 89.7 → 88.51 (brochure, p19)
- Toyota Hyryder strong hybrid: power 115.6 → 113.99 (brochure, p14)
- Maruti Victoris VXI CNG MT: km/kg 26.6 → 27.02 (brochure, p16)
**What app users now see:** Power in true bhp on Fronx, Taisor, S-Presso, Alto K10, Hyryder, Grand Vitara, Victoris and Duster, and the correct km/kg on the two Victoris variants.
**Not done / held:**
- WagonR 225 km/kg: catalogue currency, handle with Baleno.
- Grand Vitara 548/549 km/kg: the brochure has no CNG data, so unverified.
- Exter and Nexon CNG km/kg: no brochure figure on disk.
- Grand Vitara CNG and Victoris hybrid power: the brochures don't print the figure (settled in 10G).
**Prod SHA-1:** `57f31e4d…` → `dedefb53…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/16 **Ranking-track line:** KB unit corrections (10F), export re-run: PR #16.

## 10G — 2026-11-03 — Blank the two power values no brochure can support
**Why:** Grand Vitara CNG and Victoris strong-hybrid power were PS figures labelled bhp, and neither car's own brochure prints the figure, so no verified replacement exists.
**What changed:** 2 powertrain powers nulled (7 variants) with their descriptions updated; quarantined: 0; observations kept as evidence. Schema: none.
**Examples:**
- Maruti Grand Vitara Delta CNG MT: power 87.8 → blank (Grand Vitara brochure p15 has no CNG column)
- Maruti Victoris VXI Strong Hybrid: power 115.6 → blank (Victoris brochure p16 prints engine and motor, no system total)
**What app users now see:** Power shows as "unverified" on these 7 variants, never as 0.
**Not done / held:**
- Virtus edition 833: masking its powertrain needs a schema change.
- Exter and Nexon CNG km/kg, Grand Vitara 548/549 km/kg: no brochure figure.
**Prod SHA-1:** `dedefb53…` → `52f00fc7…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/17 **Ranking-track line:** KB 10G: Grand Vitara CNG and Victoris hybrid power now unverified: PR #17.

## 10H — 2026-11-03 — Quarantine aggregator observations linked to the wrong variant
**Why:** The resolver had linked 736 of 1,902 aggregator observations to the wrong variant, so wrong trims were corroborating or supplying values. A blind subagent validated the classification.
**What changed:** 614 observations quarantined (442 wrong variant with a right one in the KB, 116 wrong variant with no KB match, 56 editions attached to a base); 47 cells quarantined, which masks 50 values including 3 inherited by an edition. Corrected: 0. Schema: none.
**Examples:**
- Maruti Dzire ZXi MT: km/l 25.71 → unverified (the value came from "ZXi + AT (AGS)", 91wheels; no brochure correction yet)
- Honda Amaze ZX MT: km/l 19.46 → unverified (came from "ZX AT (CVT)", 91wheels)
- Tata Harrier Fearless X MT: cruise control yes → unverified (only evidence was a mislinked CarWale page)
**What app users now see:** 50 values on 30 catalogue rows show as "unverified" instead of a value borrowed from another trim.
**Not done / held:**
- Jimny obs 3302 / v597: unclear, so not quarantined.
- Brezza 821 identity: held; needs an OEM source or edition powertrain masking.
- No re-linking until after the resolver fix and re-ingestion.
**Prod SHA-1:** `52f00fc7…` → `8074a9dd…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/18 **Ranking-track line:** KB 10H: mislinked aggregator evidence quarantined, paper v0 unaffected: PR #18.

## 10H-b — 2026-11-06 — Quarantine three more observations linked to the wrong variant
**Why:** The resolver-fix prototype found three mislinks 10H missed: two Thar Roxx 4WD listings linked to 2WD variants and a Seltos turbo-petrol listing linked to a diesel. A blind subagent confirmed all three.
**What changed:** 3 observations quarantined. Cells corrected, nulled or quarantined: 0, because these observations fed no values. Schema: none.
**Examples:**
- Thar Roxx "AX7L Diesel 4WD AT (TC)" (91wheels): link to AX7 L 2WD Automatic → quarantined (no brochure change)
- Seltos "X-Line (A) T-GDI 7AT (DCT)" (91wheels): link to X-Line(A) Diesel AT → quarantined (no brochure change)
**What app users now see:** No change.
**Not done / held:**
- Re-linking: waits for the resolver fix and re-ingestion (P15).
**Prod SHA-1:** `8074a9dd…` → `9bf0bc7a…`. **App PR:** none. **Ranking-track line:** KB 10H-b: 3 more mislinks quarantined; no value changed.

## 10J — 2026-11-06 — Settle the hidden values from each car's own brochure
**Why:** 10H hid 47 values whose only evidence was linked to the wrong variant. Most could be settled from the brochures on disk, and some turned out wrong.
**What changed:** 8 cells corrected, 17 confirmed unchanged, 25 quarantines released; 25 brochure observations added. Observations quarantined: 0. Schema: none.
**Examples:**
- Maruti Dzire ZXi MT: km/l 25.71 → 24.79 (Dzire brochure, p5)
- VW Taigun Highline MT: cruise control yes → no (Taigun brochure, p10, "AT only")
- Tata Harrier Pure X Diesel MT: sunroof no → yes (Harrier brochure, p18)
**What app users now see:** 27 values on 18 catalogue rows are back, 8 of them corrected. The rest of the 10H values still show as "unverified".
**Not done / held:**
- HUD (5 cells) and XUV 3XO ventilated seats (5): the brochures don't mention them.
- Baleno 252, Brezza 146 km/l: catalogue currency, the brochures are newer than the KB rows.
- Innova Crysta 306, XUV 7XO 416 km/l: the brochures print no mileage.
- Editions 821, 831, 832 (8 cells): edition cells are never written.
**Prod SHA-1:** `9bf0bc7a…` → `2623fa7a…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/20 **Ranking-track line:** KB 10J: 25 hidden values settled from brochures, 8 corrected; export re-run.

## 10K — 2026-11-06 — Restore "AT only"-style qualifiers dropped from brochure tables
**Why:** Some feature cells ignored a qualifier printed in the brochure, such as "AT only", "AMT only" or "not available in CNG AMT". So manual cars claimed automatic-only features, and a misread "AMT only" took hill assist away from higher trims.
**What changed:** 16 cells corrected; 19 contradicted provenance rows quarantined; 16 brochure observations added. Schema: none.
**Examples:**
- Skoda Kushaq Classic Plus MT: paddle shifters and cruise control yes → no (Kushaq brochure, p27)
- Hyundai Venue HX4 1.2 MT: cruise control yes → no (Venue brochure, p20)
- Grand i10 Nios Asta MT: hill assist no → yes (Nios brochure, p10)
**What app users now see:** Correct feature ticks on these 15 Kushaq, Venue, Nios, Victoris and Tiago variants.
**Not done / held:**
- Jimny 599 paddle shifters: the brochure doesn't mention them.
- Nios Magna AMT: the brochure has no such variant.
**Prod SHA-1:** `2623fa7a…` → `459e4a99…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/21 **Ranking-track line:** KB 10K: 16 feature cells corrected from brochure qualifiers; export re-run.

## 10L — 2026-11-06 — Warranty gets brochure citations and appears in the app
**Why:** Warranty rows came mostly from an aggregator, Grand Vitara's figures were wrong, Hyundai's make-wide "unlimited km" was contradicted by two of its brochures, and the app showed no warranty at all.
**What changed:** 2 cells corrected, 15 rows cited to a brochure page, 3 model rows added, 2 quarantines released. Schema: none.
**Examples:**
- Maruti Grand Vitara: warranty 2 years / 40,000 km → 3 years / 100,000 km (Grand Vitara brochure, p15)
- Hyundai Grand i10 Nios: unlimited km (make-wide) → 3 years / 100,000 km (Nios brochure, p13)
**What app users now see:** The car page shows standard warranty, and battery warranty on EVs and hybrids, wherever a brochure backs it. Otherwise it says "Not verified".
**Not done / held:**
- Hyundai make row, MG, Renault: no brochure on disk settles them; shown as not verified.
- Grand Vitara battery figures, Hyryder battery km: not printed in the brochures.
**Prod SHA-1:** `459e4a99…` → `acf32b47…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/22 **Ranking-track line:** KB 10L: warranty cited and exported; new catalogue columns; no existing column changed.

## 10M — 2026-11-06 — CNG pages say km/l doesn't apply
**Why:** CNG cars are rated in km/kg, and the car page hid the km/l row with no explanation. Cards, the variants table and ranking already used km/kg only.
**What changed:** App code only. Cells changed: 0. Schema: none.
**Examples:**
- Maruti Ertiga ZXi CNG: "Mileage (ARAI)" hidden → "Not applicable: CNG is rated in km/kg", beside 26.11 km/kg (app display, no data change)
**What app users now see:** On CNG car pages, km/l is marked not applicable next to the km/kg figure.
**Not done / held:**
- 40 of 82 CNG variants have no km/kg yet: item 8.
**Prod SHA-1:** `acf32b47…` → `acf32b47…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/23 **Ranking-track line:** App only; no data change.

## 10N — 2026-11-06 — Fill mileage, cruise control and wireless charging from brochures (first batch)
**Why:** Many cars had blank or wrong mileage and feature values that the brochures on disk settle.
**What changed:** 149 cells checked against 13 brochures: 70 blanks filled, 56 corrected, 23 confirmed; 55 quarantines released; 58 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Maruti Dzire VXi AMT: mileage 22.0 → 25.71 km/l (Dzire brochure, p5)
- Maruti Ertiga VXi AT: mileage 18.69 → 20.3 km/l (Ertiga brochure, p7)
- Maruti Victoris ZXI+ AT ADAS: cruise control blank → yes, adaptive (Victoris brochure, p16)
**What app users now see:** 151 updated values for mileage, cruise control and wireless charging, including 2 editions that inherit from a changed base.
**Not done / held:**
- Most other gap cells (about 1,140, not recounted): not read yet, or the brochure is silent.
- First validation failed for cruise control (87.5%); nothing was written until the table was fixed and a second blind check agreed 32 of 32.
**Prod SHA-1:** `acf32b47…` → `758310ea…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/24 **Ranking-track line:** KB 10N: 126 mileage and feature cells changed from brochures; export re-run.

## 11A — 2026-11-11 — Syros: feature cells checked against the brochure
**Why:** Many Syros feature cells were empty or unverified. The brochure's trim table settles most of them.
**What changed:** 49 cells checked on one brochure page: 8 blanks filled, 1 corrected, 40 confirmed; 2 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Kia Syros HTX Diesel Automatic: wireless charging 0 → 1 (Syros brochure, p7)
- Kia Syros HTK+ Petrol DCT: paddle shifters blank → yes (Syros brochure, p7)
- Kia Syros HTK+ Petrol Manual: paddle shifters blank → no, "Automatic Only" (Syros brochure, p7)
**What app users now see:** 9 Syros cells change in the next catalogue export; the confirmed cells show as brochure-checked.
**Not done / held:**
- Head-up display (17 cells): the page never shows it, so a 0 would be a guess.
- Mileage km/l (17 cells): the Syros brochure prints none.
**Prod SHA-1:** `758310ea…` → `795a1223…`. **App PR:** none yet (export after every 3 batches). **Ranking-track line:** KB 11A: 9 Syros feature cells changed from the brochure.

## 11B — 2026-11-12 — Nexon: feature cells checked against the brochure
**Why:** Many Nexon feature cells were empty, unverified or quarantined. The persona pages settle most of them.
**What changed:** 143 cells checked on three brochure pages: 12 blanks filled, 3 corrected, 128 confirmed; 14 old quarantines released; 3 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Tata Nexon Creative Plus (PS) CNG: wireless charging 0 → 1 (Nexon brochure, p39)
- Tata Nexon Fearless Plus (PS) CNG: wireless charging 0 → 1 (Nexon brochure, p39)
- Tata Nexon Creative Plus (PS) CNG Dual Tone: wireless charging blank → yes (Nexon brochure, p39)
**What app users now see:** 15 Nexon cells change in the next catalogue export; the confirmed cells show as brochure-checked.
**Not done / held:**
- Cruise control on 11 Nexon cars: a footnote says "Available in AMT / DCA" but the page does not say which lines it covers (owner decision: held).
- Cruise control on Pure + PS (15 cells): the persona pages disagree with each other.
- Mileage and CNG km/kg: the brochure prints none.
**Prod SHA-1:** `795a1223…` → `afad3a5f…`. **App PR:** none yet (export after every 3 applied batches). **Ranking-track line:** KB 11B: 15 Nexon feature cells changed from the brochure.

## 11D — 2026-11-12 — Creta: feature and drive-mode cells checked against the brochure
**Why:** Many Creta feature cells were unverified and some were wrong. The brochure's feature matrix settles them.
**What changed:** 138 cells checked on two brochure pages: 10 blanks filled, 14 corrected, 114 confirmed; 31 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Hyundai Creta S(O) Petrol Manual: cruise control no → yes (Creta brochure, p14)
- Hyundai Creta SX Premium Petrol Manual: ventilated front seats no → yes (Creta brochure, p14)
- Hyundai Creta EX(O) Petrol CVT: paddle shifters yes → no (Creta brochure, p14)
**What app users now see:** 24 Creta cells change in the next catalogue export; the confirmed cells show as brochure-checked.
**Not done / held:**
- Mileage and fuel tank: not printed on the pages read.
- Seltos (held, P7) and Carens Clavis (rejected at the validation gate, 34 of 38 agreed; re-run later).
**Prod SHA-1:** `afad3a5f…` → `b653b3f8…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/25 (covers 11A, 11B and 11D; based on app/kb-10n-export). **Ranking-track line:** KB 11D: 24 Creta feature cells changed from the brochure.

## 11E — 2026-11-12 — Scorpio-N: feature, fuel tank and drive-mode cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 125 cells checked on 2 brochure page(s): 71 blanks filled, 6 corrected, 48 confirmed; 0 old quarantines released; 6 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Mahindra Scorpio-N Z8T Diesel MT: ventilated front seats no → yes, driver and co-driver (Scorpio-N brochure, p24)
- Mahindra Scorpio-N Z4 Petrol MT: fuel tank 57 L confirmed (Scorpio-N brochure, p23)
- Mahindra Scorpio-N Z8L Diesel 2WD AT: drive modes blank → 3, Zip-Zap-Zoom (Scorpio-N brochure, p24)
**What app users now see:** The changed cells appear in the next catalogue export; confirmed cells show as brochure-checked.
**Not done / held:**
- Mileage: the pages read print no km/l.
- Head-up display and paddle shifters: not shown on the pages (unknown, not zero).
- Drive modes on petrol variants and Diesel 4WD: not on the page row.
**Prod SHA-1:** `b653b3f8…` → `96356815…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/26 (covers 11E, 11F and 11G; based on app/kb-11d-export). **Ranking-track line:** KB 11E: 77 Scorpio-N cells changed from the brochure.

## 11F — 2026-11-12 — XUV 7XO: feature, fuel tank and drive-mode cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 124 cells checked on 2 brochure page(s): 16 blanks filled, 1 corrected, 107 confirmed; 0 old quarantines released; 17 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Mahindra XUV 7XO AX7 Tech Petrol AT: wireless charging no → yes, front charger with active cooling (XUV 7XO brochure, p28)
- Mahindra XUV 7XO AX Diesel MT: drive modes blank → 4, Zip/Zap/Zoom/Custom (XUV 7XO brochure, p28)
- Mahindra XUV 7XO AX3 Petrol MT: fuel tank 60 L confirmed (XUV 7XO brochure, p30)
**What app users now see:** The changed cells appear in the next catalogue export; confirmed cells show as brochure-checked.
**Not done / held:**
- Mileage, head-up display and paddle shifters: not shown on the pages read.
- Drive modes on petrol variants: the row says diesel only, so unknown.
**Prod SHA-1:** `96356815…` → `58d3ef0e…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/26 (covers 11E, 11F and 11G; based on app/kb-11d-export). **Ranking-track line:** KB 11F: 17 XUV 7XO cells changed from the brochure.

## 11G — 2026-11-12 — XUV 3XO: cruise, wireless and fuel-tank cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 56 cells checked on 2 brochure page(s): 0 blanks filled, 1 corrected, 55 confirmed; 2 old quarantines released; 1 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Mahindra XUV 3XO AX5 Diesel AT: cruise control no → yes (XUV 3XO brochure, p13)
- Mahindra XUV 3XO MX1 Petrol: fuel tank 42 L confirmed (XUV 3XO brochure, p14)
- Mahindra XUV 3XO AX5 Luxury Petrol MT: wireless charging yes confirmed (XUV 3XO brochure, p13)
**What app users now see:** The changed cells appear in the next catalogue export; confirmed cells show as brochure-checked.
**Not done / held:**
- Wireless charging on MX3, MX3 Pro, AX5 and AX7 (14 cells, stored yes): held, the brochure's lists are not exhaustive (see above).
- Mileage, head-up display, ventilated seats, paddle shifters, drive modes: not on the pages read.
**Prod SHA-1:** `58d3ef0e…` → `e351341c…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/26 (covers 11E, 11F and 11G; based on app/kb-11d-export). **Ranking-track line:** KB 11G: 1 XUV 3XO cells changed from the brochure.

## 11H — 2026-11-12 — Altroz: feature, fuel tank and drive-mode cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 74 cells checked on 2 brochure page(s): 38 blanks filled, 27 corrected, 9 confirmed; 0 old quarantines released; 27 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Tata Altroz Pure Diesel: fuel tank 60 L → 37 L (Altroz brochure, p23)
- Tata Altroz Creative S DCA: paddle shifters blank → yes, Petrol DCA only (Altroz brochure, p22)
- Tata Altroz Pure Petrol MT: drive modes blank → 2, Eco and Sport (Altroz brochure, p22)
**What app users now see:** Altroz paddle-shifter cells fill in and 27 fuel-tank values correct (fuel tank is not shown in the app catalogue).
**Not done / held:**
- Mileage and head-up display: not on the pages read.
- Drive modes on DCA and CNG variants: the row names other variants only.
**Prod SHA-1:** `e351341c…` → `98a46dbd…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/27 (covers 11H, 11I and 11J; based on app/kb-11g-export). **Ranking-track line:** KB 11H: 65 Altroz cells changed from the brochure.

## 11I — 2026-11-12 — Harrier: feature, fuel tank and drive-mode cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 85 cells checked on 3 brochure page(s): 14 blanks filled, 0 corrected, 71 confirmed; 0 old quarantines released; 3 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Tata Harrier Pure X Diesel AT: paddle shifters blank → yes, AT only (Harrier brochure, p18)
- Tata Harrier Adventure X Petrol MT: drive modes blank → 3, City, Sports and Eco (Harrier brochure, p18)
- Tata Harrier Fearless X Diesel MT: wireless charging yes confirmed (Harrier brochure, p19)
**What app users now see:** The changed cells appear in the next catalogue export; confirmed cells show as brochure-checked.
**Not done / held:**
- Mileage and head-up display: not on the pages read.
- The two Dark editions: editions inherit from their base (P8).
**Prod SHA-1:** `98a46dbd…` → `39f913e6…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/27 (covers 11H, 11I and 11J; based on app/kb-11g-export). **Ranking-track line:** KB 11I: 14 Harrier cells changed from the brochure.

## 11J — 2026-11-12 — Tiago: feature and fuel-tank cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 77 cells checked on 2 brochure page(s): 17 blanks filled, 26 corrected, 34 confirmed; 6 old quarantines released; 26 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Tata Tiago Smart Petrol: fuel tank 60 L → 35 L (Tiago brochure, p27)
- Tata Tiago Pure+ Petrol MT: cruise control no → yes (Tiago brochure, p28)
- Tata Tiago Creative+ Petrol MT: wireless charging no → yes (Tiago brochure, p28)
**What app users now see:** Cruise control and wireless charging change on 6 Tiago variants (fuel tank is not shown in the app catalogue).
**Not done / held:**
- Mileage, head-up display and drive modes: not on the pages read (drive modes were not listed).
- One CNG AMT cruise-control zero held by the footnote guard.
**Prod SHA-1:** `39f913e6…` → `ff444f4a…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/27 (covers 11H, 11I and 11J; based on app/kb-11g-export). **Ranking-track line:** KB 11J: 43 Tiago cells changed from the brochure.

## 11K — 2026-11-12 — Grand Vitara: feature, mileage, fuel-tank and drive-mode cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 134 cells checked on 1 brochure page(s): 5 blanks filled, 9 corrected, 120 confirmed; 0 old quarantines released; 14 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Maruti Grand Vitara Zeta Petrol MT: ventilated front seats yes → no (Grand Vitara brochure, p15)
- Maruti Grand Vitara Alpha(O) AllGrip Petrol AT: mileage 20.58 → 19.20 km/l (Grand Vitara brochure, p15)
- Maruti Grand Vitara Delta+ Strong Hybrid: wireless charging yes → no (Grand Vitara brochure, p15)
**What app users now see:** The changed cells appear in the next catalogue export; confirmed cells show as brochure-checked.
**Not done / held:**
- CNG km/kg: the Grand Vitara brochure has no CNG data (still unverified).
- Pass over any further pages (fuel tank 45 L was confirmed from the matrix).
**Prod SHA-1:** `ff444f4a…` → `28924082…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/28 (covers 11K, 11L and 11M; based on app/kb-11j-export). **Ranking-track line:** KB 11K: 14 Grand Vitara cells changed from the brochure.

## 11L — 2026-11-12 — Thar Roxx: feature, fuel-tank and drive-mode cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 86 cells checked on 3 brochure page(s): 14 blanks filled, 7 corrected, 65 confirmed; 7 old quarantines released; 17 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Mahindra Thar Roxx MX5 2WD Petrol AT: wireless charging yes → no (Thar Roxx brochure, p2)
- Mahindra Thar Roxx MX3 2WD Diesel AT: cruise control no → yes (Thar Roxx brochure, p3)
- Mahindra Thar Roxx MX5 2WD Diesel MT: drive modes blank → 2, Zip and Zoom, RWD (Thar Roxx brochure, p3)
**What app users now see:** The changed cells appear in the next catalogue export; confirmed cells show as brochure-checked.
**Not done / held:**
- Mileage, head-up display and paddle shifters: not on the pages read.
- Drive modes on 4x4 variants: the tick is printed for RWD only.
**Prod SHA-1:** `28924082…` → `52711fd1…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/28 (covers 11K, 11L and 11M; based on app/kb-11j-export). **Ranking-track line:** KB 11L: 21 Thar Roxx cells changed from the brochure.

## 11M — 2026-11-12 — Venue: feature, fuel-tank and drive-mode cells checked against the brochure
**Why:** Many cells for this model were empty, unverified or wrong. The brochure settles them.
**What changed:** 97 cells checked on 3 brochure page(s): 13 blanks filled, 1 corrected, 83 confirmed; 0 old quarantines released; 3 contradicted provenance rows quarantined. Schema: none.
**Examples:**
- Hyundai Venue HX7 1.5 Diesel MT: ventilated front seats yes → no (Venue brochure, p20)
- Hyundai Venue HX 10 DCT: drive modes blank → 3, Eco, Normal and Sport (Venue brochure, p20)
- Hyundai Venue HX 2 Petrol: drive modes blank → 0, dash printed (Venue brochure, p20)
**What app users now see:** The changed cells appear in the next catalogue export; confirmed cells show as brochure-checked.
**Not done / held:**
- Mileage and head-up display: not on the pages read.
**Prod SHA-1:** `52711fd1…` → `8039119b…`. **App PR:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/28 (covers 11K, 11L and 11M; based on app/kb-11j-export). **Ranking-track line:** KB 11M: 14 Venue cells changed from the brochure.

## Current state
As of phase 11M (prod `8039119ba0ba5e787025d198e1f2aad569c19c3a`).
- **Active quarantines:** 1,502 (950 observations, 294 variant cells, 257 provenance rows, 1 safety applicability row(s)).
- **Variants / models / makes:** 832 / 62 / 12.
- **Coverage:**
  - power: 825/832 = 99.2%
  - mileage km/l (non-CNG, non-EV): 462/713 = 64.8%
  - km/kg on CNG variants: 45/82 = 54.9%
  - safety stars (variants of models with a usable test): 363/832 = 43.6%
  - warranty: 832/832 = 100.0%; rows 21 of 21; see the warranty entries for provenance and export status.
- **Open items:** 7 in [NEEDS_YOU.md](NEEDS_YOU.md).
