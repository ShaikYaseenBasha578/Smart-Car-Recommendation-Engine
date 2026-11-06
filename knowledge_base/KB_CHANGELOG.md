# CarRec knowledge base changelog

Plain-language record of every applied KB phase. Full evidence is in `knowledge_base/reports/`. Open questions for the owner are in [NEEDS_YOU.md](NEEDS_YOU.md).

## 10E — 2026-11-02 — Brochure corrections: CNG mileage, paddle shifters, Glanza power, edition bases
**Why:** CNG cars held km/kg figures in the km/l column, some manual cars claimed paddle shifters, Glanza power was a PS figure labelled bhp, and two editions pointed at the wrong base trim.
**What changed:** 19 variant cells corrected or moved, 4 cells quarantined for paddle shifters and 1 for a suspect unit; 1 powertrain power corrected (7 Glanza variants); 2 editions re-based; 15 contradicted provenance rows and 2 warranty cells quarantined. 22 brochure observations added. Schema: `evidence_quarantine` rebuilt to allow warranty targets, and views updated.
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

## Current state
As of phase 10H (prod `8074a9dd67829042ba04a16bbe9c5a26702c88c6`).
- **Active quarantines:** 1,383 (947 observations, 403 variant cells, 30 provenance rows, 2 warranty cells, 1 safety applicability row).
- **Variants / models / makes:** 832 / 62 / 12.
- **Coverage:**
  - power: 825/832 = 99.2%
  - mileage km/l (non-CNG, non-EV): 446/713 = 62.6%
  - km/kg on CNG variants: 42/82 = 51.2%
  - safety stars (variants of models with a usable test): 363/832 = 43.6%
  - warranty (a model or manufacturer-wide figure, not yet exported, no brochure provenance): 832/832 = 100%
- **Open items:** see [NEEDS_YOU.md](NEEDS_YOU.md).
