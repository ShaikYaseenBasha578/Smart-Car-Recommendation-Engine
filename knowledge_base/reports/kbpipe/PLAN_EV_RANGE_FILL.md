# Plan: fill the missing EV range (22 Nov 2026, awaiting owner approval)

## The gap

On `main` (1,556-variant catalogue), 40 of 136 electric variants show "Range: Not listed":

| Model | Missing | Why it was withheld (run `update_missing16_2026-11-18_specs`, `flags.tsv`) | OEM brochure on disk |
|---|---|---|---|
| Tata Sierra EV | 15 | no site gave a value (no flag row) | no |
| Mahindra XEV 9e | 9 | SINGLE_SOURCE: CarDekho only | no |
| Kia Carens Clavis EV | 8 | SINGLE_SOURCE: CarDekho only | **yes** (`kia/carens_clavis_ev`) |
| Mahindra XUV400 | 5 | SINGLE_SOURCE: CarDekho only | no |
| Mahindra XUV 3XO EV | 2 | SINGLE_SOURCE: CarDekho only | no (the `xuv_3xo` brochure is the petrol/diesel car) |
| Toyota Urban Cruiser Ebella | 1 | SINGLE_SOURCE: CarDekho only | no |

The unpriced EVs left out of the app (Comet EV, ZS EV, Hector Tomahawk EV, BE 6 Sporteq and others) are counted in step 1.

Why the brochure stage never read the Clavis EV brochure: it reads only new models and models with more than 50% blank cells, and the Clavis EV is neither.

CarWale pages do carry range-like fields, but most are not the claimed figure: "Expected Range", "Range (As tested by CarWale)" and "Range - Owner Reported". kbpipe reads only "Driving Range" or "Range". The XUV400 cache has a "Driving Range" label, yet no CarWale value was taken, and why is still to be found.

## Rules that apply

- A value is written only when two sites agree, or a maker brochure confirms it (kbpipe gates; P1, P2).
- The field is `claimed_ev_range_km`: the certified (ARAI/MIDC) claimed range. CarWale's tested range and owner-reported range are a different evidence class (PROFESSIONAL_ASSESSMENT / OWNER_REPORT) and are never written into this column.
- No cross-model inference (P3): for example, no Clavis EV value is copied to the XEV 9e.
- Catalogue currency (P7): if a brochure is newer than the KB rows for that model, hold and record.

## Steps

1. **Diagnostic (read-only, on a KB copy):** for every EV variant without a range, in the app and in the KB, list:
   - the CarDekho value;
   - every range label on the cached CarWale variant page, with its value;
   - whether a brochure is on disk.

   Also find out why the XUV400 "Driving Range" label gave nothing. Output: a table in `reports/kbpipe/`. No writes, no fetching.
2. **Clavis EV brochure:** run the brochure layer only for this model (`--only "Carens Clavis EV"`, brochure on). This is the existing path: Sonnet reads the page, Opus checks the page image, and only supported cells are kept.
   - Range is usually printed per battery pack. A variant gets that value only when its own name or spec states the same pack, and the page ties that range to it.
   - It fills the model's other blank cells too, through the same gates.
3. **CarWale parser (only if step 1 shows it misses a claimed figure):** read only labels that mean the claimed or certified range. Never read "Expected", "As tested" or "Owner Reported".
   - Sonnet writes the change with tests on cached pages.
   - If it would decide more than 20 cells, a blind check by a fresh agent must reach at least 95% agreement first (P12).
   - This gives CarDekho's values a second source, which the two-site rule needs.
4. **Brochures you save (your step):** the maker brochures for XEV 9e, XUV400, XUV 3XO EV, Sierra EV and Urban Cruiser Ebella, plus any unpriced EVs you want, into `knowledge_base/sources/oem/<make>/<model>/latest/brochures/`. Claude never writes there. Then rerun step 2 for those models.
5. **Update and pull request:** the normal tail (audit, export, app checks, pages, data pull request). You merge it.

## What it costs

- Steps 1 and 3 are local and use no paid calls.
- Step 2: one brochure read on the subscription (Sonnet reads, Opus checks), about 15 to 25 pages.
- Step 5: the audit uses the free Gemini quota.

## What it will not do

- It writes no range from one site alone, no tested or owner-reported range, and no value copied between models or packs.
- Variants that no source settles stay "Not listed".

## Expected result

- Without new brochures: the 8 Clavis EV variants, plus whatever step 3 turns into two-site agreement (up to 17 more, if CarWale prints the claimed figure).
- With your 5 brochures: potentially all 40.
