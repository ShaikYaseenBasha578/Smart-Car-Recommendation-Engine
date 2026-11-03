# Phase 10H — resolver mislinks: read-only checkpoint (2026-11-03)

Prod untouched: SHA-1 `52f00fc761a11be5f4763a022fd526e6ea20396d` before and after (`access_step0.txt`, `access_end.txt`).
Holder: `com.apple.Virtualization.VirtualMachine` PID 4854, FD 2613r; no `-wal`/`-shm`. All queries ran on
`work.db`, a byte copy. No repo script was run; the resolver and ingest code was read only.

## 1. Classification of every resolved aggregator observation (`classify_links.py` → `links.tsv`)
1,902 resolved observations (91wheels, v3cars, carwale). Each one's own structured fields (fuel, gearbox, engine cc;
91wheels slug and fuel field, CarWale `Fuel Type` / `Transmission` / `Engine`) and its trim name are compared with
the resolved variant and with every other variant of the same model.

| Class | n | Meaning |
|---|---|---|
| OK | 1,104 | resolved variant matches |
| MISLINK_TARGET | 584 | wrong variant; the KB has the right one (listed per row) |
| MISLINK_NONE | 152 | wrong variant; the KB has no variant matching the source |
| EDITION_NOT_IN_KB | 56 | same trim, fuel and gearbox, but the source names an edition (Dark, Camo, Knight…) the KB doesn't model; attached to the base |
| REVIEW | 6 | Fortuner (no trim name) ×5, and 833 (cc 1498 ≠ 999: the known open item) |

By source: carwale 333 + 68, 91wheels 185 + 47, v3cars 66 + 37 (TARGET + NONE).

**Precision (hand review of random samples, final version):** MISLINK_TARGET 40/40 correct; MISLINK_NONE about 37/40
(the misses are ambiguous trims such as Elevate "ADV Edition" and Carens Clavis EV "HTX E"); EDITION_NOT_IN_KB 10/10.
The classifier went through 8 iterations; each fix removed only naming noise ("HX 2" = "HX2", "Mid Range" = "MR",
"Bi-Fuel CNG" = "Hy-CNG", Tata "A" = automatic, battery kWh). Kia "(A)" means ADAS, not automatic, and is kept
distinct.

## 2. Root causes (code read, not run)
- **R1, resolver** (`knowledge_base/ingestion/common/resolver.py`): `validate_structured` is the only fuel/gearbox
  guard, and it does nothing when the caller passes no fuel/transmission. For **490 of 711** resolved 91wheels
  observations the payload has no `specs` block and no fuel field, so the resolver got neither (91wheels takes them
  from `v_variant_fuel_type` / `specs.transmission_type`; v3cars parses them from the name). Fuzzy acceptance is
  `score > 0.5` with a 0.05 margin over the runner-up, and identity tokens only need to *overlap*
  (`compute_similarity`), so "ZXi + AT (AGS)" → "ZXi MT", "HX 3" → "HX 2", "Highline Plus" → "Highline".
  The observations date from 2026-09-09 and predate the 10C-2 fix (2026-09-28: CarWale fails closed on fuel/gearbox
  parsed from the name; verified aliases fail closed). 10C-2 does not cover R1's trim identity or R2. Also,
  `ingest_91wheels.py:44` unpacks two values from `resolve_variant`, which now returns three, so that runner would
  crash as written.
- **R2, CarWale scrape identity** (`knowledge_base/ingestion/carwale/ingest_carwale.py:68-104`): it resolves on the
  version name from the model page, but stores the features of whatever trim page CarWale serves, and never checks
  `obs_data['v_variant_name']` against the requested name. **470 of 753 resolved CarWale observations carry a payload
  for a different version** (e.g. five Elevate ZX rows all carry "ZX Petrol Manual Signature Black Edition"). The
  classifier therefore judges CarWale rows by the payload's version name, which the features actually describe.
  Also: the CarWale `ex_showroom_price` is `modelPriceOverview.price`, a model-level figure (not used by any fp row).
- 10B-W1 already quarantined 333 CarWale observations (B3, from raw-name fuel/gearbox conflicts): 177 of them are
  mislinks here; 156 are OK by payload identity. Those stay quarantined (no release proposed).

## 3. Impact (`impact.py`, `sole_source.py`)
- Price: none (all 812 price provenance rows are v6_migration).
- Provenance rows on mislinked observations: 2,834 confirmed, 893 rejected, 97 accepted (editions: 273 / 108 / 0).
- Corroboration (`v_corroboration` source counts) would fall on **790** (variant, field) cells if the mislinks are
  quarantined. 123 of them fall to zero: 48 are `transmission` (an identity column copied from the v6 row, which
  has no v6 provenance row, so nothing changes), 18 are NULL canonical cells, and the rest are in the next item.
- **Canonical cells left with no live evidence**: 54 (56 with editions). 46 (48) store their own value on the variant.
  The other 8 are editions that inherit from their base, so they need nothing. The 46 cover 30 variants:
  cruise_control 17, heads_up_display 8, ventilated_front_seats 7, mileage_arai_kmpl 7, TPMS 7, sunroof 4,
  adas_available 2, boot_space_litres 2. They include the four known wrong mileages (Dzire 237 25.71, Baleno 252
  22.94, Amaze 293 19.46, Ertiga 210 20.3: AT figures on MT variants). List: `sole_source.tsv`.
- 8 more canonical cells come from a mislink but have independent agreeing support; they would stay.

## 4. Proposed 10H write (10B-W1 pattern; no re-linking, no DDL, no threshold change)
| Step | Entries | Reason code (new) | Effect |
|---|---|---|---|
| Q1 quarantine mislinked obs not yet quarantined | 559 (442 TARGET + 117 NONE) | `H1_RESOLVER_MISLINK` / `H1_RESOLVER_NO_KB_VARIANT` (note: resolved id, better target ids, the mismatch) | out of `v_live_evidence` / `v_corroboration` |
| Q2 quarantine edition obs (owner choice) | 56 | `H1_EDITION_NOT_IN_KB` | same |
| Q3 quarantine stored canonical cells left with no live evidence | 46 (48 with Q2) | `H1_SOLE_SOURCE_FROM_MISLINK` (as W1's `B3_SOLE_SOURCE_FROM_MISRESOLVED`) | masked to NULL; the app shows "unverified" |

Active quarantines: 722 → 1,327 (Q1 + Q3) or 1,385 (Q1 + Q2 + Q3). App re-export: those cells blank and listed in
`unverified_fields`; nothing else (the exporter doesn't read corroboration).

Alternative for the 7 `mileage_arai_kmpl` cells in Q3: correct them from the brochure, 10F-style. The Amaze, Baleno,
Brezza, Dzire, Ertiga, XUV 7XO and Innova Crysta brochures are all on disk. That needs a page-by-page read first,
so it is a separate checkpoint if chosen.

## 5. Not in the write (separate decisions)
- **Resolver code fix** (R1, R2), required before any re-ingestion: CarWale must fail closed when the page's
  `versionName` ≠ the requested name. The fuzzy path should require equal trim identity (as `classify_links.py`
  does), and fuel/gearbox should be parsed from the slug or name when the caller passes none. `links.tsv` can serve
  as a regression fixture. Thresholds unchanged (do-not-touch list).
- **Brezza edition 821** "Zxi Petrol 1.0L Turbo Manual Dual Tone" sits on the 1.5 powertrain (as 833 does); CarWale
  says 998 cc. An edition-identity / CATALOG_CURRENCY item.
- A **0-byte `knowledge_base/ingestion/carrec_kb.db`** (2026-09-09 20:03), probably a script opening a relative
  path. Left untouched.
