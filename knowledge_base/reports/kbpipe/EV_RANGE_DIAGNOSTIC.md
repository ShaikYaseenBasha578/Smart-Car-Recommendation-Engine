# EV claimed-range diagnostic (22 Nov 2026, step 1 of PLAN_EV_RANGE_FILL.md)

Read-only. Nothing fetched, nothing written to the KB or to code. Per-variant rows: `EV_RANGE_DIAGNOSTIC.tsv` (61 rows, same folder).

## Summary

- **61 electric variants have no effective `claimed_ev_range_km`** in the KB copy `/tmp/carrec_audit/prod/kb_evrange_20261122.db` (view `v_variant_canonical_q`, powertrain fuel = Electric, 176 electric variants in all). [VERIFIED: sqlite query, 61 rows]. Two more electric variants (832, 827) have a raw NULL but are editions and inherit a value from their base (136 -> 489, 603 -> 543), so they are not counted.
- **40 of the 61 are in the app catalogue** (`cat.csv`: 136 electric, 40 with blank `ev_range_km`; the 40 ids are exactly the plan's Sierra EV 15, XEV 9e 9, Clavis EV 8, XUV400 5, XUV 3XO EV 2, Ebella 1). The other 21 are the unpriced ones (not in the app): Comet EV 3, Windsor EV 6, ZS EV 2, XEV 9S 6, XEV 9e 4. [VERIFIED]
- **Main finding: the CarWale parser misses a figure that CarWale does print for 46 of the 61 variants.** Every cached CarWale EV page carries the range at version level under the label **"Expected Range"** (itemId 459, unit km). `carwale.py:97` looks only for "Driving Range" or "Range", so it never matches, and CarWale contributes no range for any EV. kbpipe then sees one source (CarDekho) and leaves SINGLE_SOURCE blanks.
- **Is "Expected Range" the claimed figure?** [UNSURE, owner decision]. Evidence for: itemId 459 is the same item that CarWale's model-level key-spec card titles "Driving Range" (`modelPage.keySpecs`, identifier "459"), and CarWale's FAQ text calls that number the "ARAI driving range" or "company claimed driving range" (MG Comet EV 230 = Expected Range 230; MG ZS EV 461 = 461; XUV400 FAQ 375 = EC PRO Expected Range 375; Sierra EV FAQ 460 = the 63 kWh Expected Range 460). Evidence against: the plan assumes "Expected" means a CarWale estimate, and in three cases (below) CarWale's number is plainly wrong or disagrees with CarDekho. No page carries a version-level "Range (As tested by CarWale)" or "Range - Owner Reported" label; tested and owner figures exist only in the model-level `mileage` block (`expertTested`, `userReportedArai`).
- **Agreement if the parser read "Expected Range" (pipeline `agree_tolerance` 1%):** of the 46 variants with a CarWale value, 27 agree with CarDekho (23 exactly, 4 within 1%: Windsor 331 vs 332) and 19 disagree (Sierra EV 15, XUV400 2, XEV 9e 2). In the app, 14 of the 40 would get a two-site value (Clavis EV 8, XUV400 3, XEV 9e 2, Ebella 1); 19 more in-app variants have a CarWale value that disagrees with CarDekho (Sierra EV 15, XUV400 2, XEV 9e 2) and 7 have no CarWale value (XEV 9e 5, XUV 3XO EV 2).

## Counts per class and model

Class A = CarWale prints a figure under "Expected Range" (itemId 459) that the parser misses. B = CarWale prints only expected/tested/owner values: **0 variants**, because "Expected Range" is the only version-level label and a strict reading would put every A row in B (see the [UNSURE] note above). C = no CarWale value for the variant (label present, value blank, in all 15 cases). D = brochure for that exact model on disk (a flag combined with A or C).

| Model | Variants | In app | A | of which CW = CD | of which CW differs | C | D |
|---|---|---|---|---|---|---|---|
| Tata Sierra EV | 15 | 15 | 15 | 0 | 15 | 0 | 0 |
| Mahindra XEV 9e | 13 | 9 | 6 | 4 | 2 | 7 | 0 |
| Kia Carens Clavis EV | 8 | 8 | 8 | 8 | 0 | 0 | 8 |
| Mahindra XUV400 | 5 | 5 | 5 | 3 | 2 | 0 | 0 |
| Mahindra XUV 3XO EV | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| Toyota Urban Cruiser Ebella | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Mahindra XEV 9S | 6 | 0 | 0 | 0 | 0 | 6 | 0 |
| MG Windsor EV | 6 | 0 | 6 | 6 | 0 | 0 | 6 |
| MG Comet EV | 3 | 0 | 3 | 3 | 0 | 0 | 0 |
| MG ZS EV | 2 | 0 | 2 | 2 | 0 | 0 | 0 |
| Total | 61 | 40 | 46 | 27 | 19 | 15 | 14 |

[VERIFIED: `EV_RANGE_DIAGNOSTIC.tsv`, columns `cls`, `cw_vs_cd`, `in_app`.]

Notes by model:
- **Windsor EV has a brochure on disk** that the plan did not list: `knowledge_base/sources/oem/mg/windsor_ev/latest/brochures/mg_windsor_ev_brochure.pdf` (18.5 MB, dated 10 Sep, which may predate the KB rows, so P7 applies). The six variants are unpriced (not in the app). [VERIFIED: `ls`]
- **Clavis EV brochure:** `.../kia/carens_clavis_ev/latest/brochures/kia_carens_clavis_ev_brochure.pdf`. The KB holds only the 6-seat variants (the 7-seat ones were VARIANT_NOT_ADDED). [VERIFIED]
- No brochure folder exists for Sierra EV, XEV 9e, XEV 9S, XUV400, XUV 3XO EV (only the petrol/diesel `xuv_3xo`), Ebella, Comet EV or ZS EV. [VERIFIED: `ls` of `oem/{tata,mahindra,mg,kia,toyota}`]
- **XEV 9e (7 blank at CarWale):** the "Expected Range" item is present but its value is empty for Pack One, Pack Two, and the 79 kWh "No Charger" rows; the page-level key spec says "542 to 656 km" (a span across versions, not per variant). [VERIFIED: cache `6db76769...body`]
- **XEV 9S (6) and XUV 3XO EV (2):** value blank at version level; the 9S page has no "Driving Range" key spec and the 3XO EV page has none either. The 9S `mileage` block shows `userReportedArai` 500 (an owner figure, model level only). [VERIFIED]
- **Bad CarWale payloads seen:** XEV 9e "Pack Three Select 59.0 kWh 11.2kW Charger" (id 1572) carries Battery Capacity 79 kWh and Expected Range 656 inside a version named 59.0 kWh (CarDekho: 522); XEV 9e "Pack Three Select 59.0 kWh 7.2kW" says 542 (CarDekho 522); XUV400 EL PRO 34.5 kWh and its Dual Tone say 456 while CarDekho says 375 (CarWale's own synopsis says "EC and EL variants return an MIDC-certified range of 375km and 456km" under the old two-variant naming, so 456 belongs to the 39.4 kWh EL). These are the cases a two-site rule would need to hold. [VERIFIED: values; which one is right is outside knowledge, so [UNSURE]]
- Version names on every cached page match the KB variant name for all 61 (the parser keys by `versionId` from the payload; trim pages are not used). One exception is the 1572 payload above, where name and battery disagree. [VERIFIED: `carwale_name_matches_kb`, `carwale_battery_matches_name` columns]
- The cached page equals what the run stored: the "Expected Range" value in the run's CarWale observation (KB `source_observation`, source 4) equals the cached page value for all 61. Three model pages (Sierra EV, XEV 9e, XUV400) were refetched on 21 Nov, after the runs; their values are unchanged. [VERIFIED]

## Answer 1: why kbpipe took no CarWale value for XUV400

Cause: `kbpipe/sources/carwale.py:97`, `rng = g(sp, "Driving Range") or g(sp, "Range")`, where `sp` is built at line 79 from `v["specsSummary"]` and keyed by `itemName` (`_items`, lines 67-73). In the cached XUV400 page (`~/carrec_kb_cache/http/57/5765d09e105fd98ff76703162dc7131feb3e903958f79b537b989a7bcd84e49b.body`, key = SHA-256 of `https://www.carwale.com/mahindra-cars/xuv400/`, fetched 2026-11-21T13:08:27Z) every version's `specsSummary` has `itemName` "Expected Range" (itemId 459: EC PRO 34.5 = 375, EL PRO 34.5 = 456, EL PRO 34.5 DT = 456, EL PRO 39.4 = 456, EL PRO 39.4 DT = 456), and no "Driving Range" or "Range" item. So `g(sp, ...)` returns "" and line 98 (`if fuel == "Electric" and rng`) never sets `claimed_ev_range_km`. The "Driving Range" label you saw is not in the version data: it is the page-level `modelPage.keySpecs` card (title "Driving Range", identifier 459, text "375 to 456 km") and an FAQ ("ARAI driving range ... is 375 km"). The parser never reads `keySpecs` or the FAQ. I ran `carwale._map_version` (pure function) on all five versions: `claimed_ev_range_km` is absent in each. CarDekho alone gave 375/375/375/456/456 (CarDekho label "Range", `cardekho.py:128`), so `reconcile.decide` returned SINGLE_SOURCE (`reconcile.py:96`) and `plan.py:174` flagged all five. [VERIFIED]

Same cause for every other EV: the item is "Expected Range" on all 10 cached CarWale EV pages. [VERIFIED: probe over the 10 model pages]

## Answer 2: why neither site gave a value for the Tata Sierra EV (15 variants)

The premise is not quite right: both sites had a value, and neither was written.
- **CarDekho gave one** (label "Range": 566 km for 63 kWh, 665 km for 75 kWh RWD, 624 km for the 75 kWh AWD). It is stored as KB observations (source 5, e.g. obs 7768 for variant 1449). It was held as SINGLE_SOURCE in run `2026-11-13_2`, where the 15 variants were created (15 flag rows, `claimed_ev_range_km SINGLE_SOURCE cardekho`). [VERIFIED: `flags.tsv`, KB `source_observation`]
- **CarWale gave one but the parser cannot read it**: "Expected Range" 460 (63 kWh), 530 (75 kWh RWD), 500 (75 kWh AWD), cache `~/carrec_kb_cache/http/36/36913388b6131d1c4f2fcaed5f9af16a1f8b28e0a2dc04bd172c5673401cb745.body` (`https://www.carwale.com/tata-cars/sierra-ev/`, fetched 2026-11-21). Same cause as XUV400 (`carwale.py:97`). The page FAQ says "The ARAI driving range of Tata Sierra EV is 460 km". [VERIFIED]
- **Why there is no flag row in the 18 Nov run:** the 15 variants were already in the KB (ids 1449-1463), so they took the "variant already in the KB" branch of `plan.py` (about lines 118-146). With no CarWale value the decision is NULL/SINGLE_SOURCE, `route` returns FLAG_NULL (`reconcile.py:~121`), and that branch has no case for FLAG_NULL, so nothing is recorded. The only flags for them are the 15 from run `2026-11-13_2`. [VERIFIED: grep of flags in all real runs; `plan.py` read; [UNSURE] on exact line numbers of the branch]
- **Even once parsed, the two sites disagree on all 15:** CarWale 460/530/500 against CarDekho 566/665/624 (CarDekho is 23-26% higher). The pipeline would call that CONFLICT and still write nothing; only a Tata brochure (none on disk) or a third source settles it. The two figures look like different test cycles, which is [UNSURE].

## Method

1. Variant set: `v_variant_canonical_q` joined to `variant`, `powertrain.fuel_type = 'Electric'`, `claimed_ev_range_km IS NULL` (61). In-app flag: variant id present in `cat.csv` with `fuel_type == electric` and blank `ev_range_km` (40).
2. CarWale cache file: SHA-256 of the model URL without the `#vid=` fragment (`fetch.py:37`, `_paths`); `carwale.py` reads model pages only. Version = `versionId` from the link (`links.tsv` of the latest run containing it). All labels containing "range" or "km" were listed from `specsSummary`, `featureSpecs`, `basicSpecs`, `differentSpecs` per version; page-level `keySpecs`, `faqsByCategory`, `mileage`, and a raw-text count of "As tested", "Owner Reported", "Expected Range", "Driving Range", "ARAI", "MIDC", "claimed" were taken per model page.
3. CarDekho: KB `source_observation` (source 5) resolved to each variant (obs id in the TSV), cross-checked against the cached variant page parsed with `cardekho.parse_variant` (all "range"/"km" labels listed; the parser reads only "Range", `cardekho.py:128`). CarDekho pages also carry "Range - Tested" for Comet EV (182) and XUV400 (289.5), not a claimed figure.
4. Why blank: `flags.tsv` of every non-rehearsal, non-nowrite, non-audit run, filtered to `claimed_ev_range_km`.
5. Brochures: `ls` of `knowledge_base/sources/oem/` (read-only).
6. Scripts and intermediate JSON are in `/tmp` (`cw.py`, `diag2.py`, `diag3.py`, `final.py`). No network, no KB write, no repo code change.

## Limits

- Which of CarWale's and CarDekho's numbers is the true ARAI/MIDC figure is not decided here; no brochure covers the disagreeing models. [UNSURE]
- The TSV `cardekho_range_km` is taken from the cached CarDekho variant page and equals the KB observation value for all 61; `carwale_range` is in `carwale_variant_range_labels`.
- A CarWale model page lists a version once; the `#vid` links are matched by exact variant name, and all 61 matched.
