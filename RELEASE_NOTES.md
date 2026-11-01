# Release notes: KB data release

## What changed

- **Data.** New-car recommendations now come from `data/catalogue.csv`, an export of the CarRec knowledge base (832 variants, 62 models, 12 brands), instead of the 2021-era `processed_dataset.csv`. Quarantined KB values are never exported.
- **Query understanding (intent v2).** A rule-based parser runs first. It handles budgets in lakh, crore, k and ₹, ranges, "around X", and Hinglish such as "tak", "ke andar" and "nahi". It also reads seats, airbags, safety stars, EV range, ground clearance, boot space, mileage, features, makes, models and exclusions ("diesel nahi", "no SUV"). The existing ML parser only fills body type, fuel or use case when the rules found nothing and it is confident.
- **Transmission types.** Each result shows its exact gearbox: manual, iMT, AMT, DCT, CVT, e-CVT, torque converter or single-speed EV. "Automatic but not AMT" and "clutchless" work as expected.
- **Unverified and safety labels.** If a requested feature or minimum is unknown for a car, the car is still shown, labelled "Unverified: …". Cars where it is known to be missing are removed. Safety stars come only from Bharat NCAP; unrated cars say "No Bharat NCAP rating on record" and are never shown as zero stars. Results with fewer unverified items come first.
- **Twins.** Four badge-engineered pairs (Taisor/Fronx, Glanza/Baleno, Hyryder/Grand Vitara, Rumion/Ertiga) are ranked as separate cars. When both cars of a pair make the results, one extra result is added.
- **Results.** Up to 8 models are returned (previously 4), best variant per model. Each card shows the number of matching variants.
- **Per-brand cap.** At most 2 models per brand, but only when the search names no brand or model and at least 4 brands have a match. With fewer matching brands the cap would only hide cars, so it is off.
- **Empty results.** When nothing matches, the response lists up to 3 hints: how many models would match if one requirement were dropped. Each hint is a button that reruns the search without that requirement; the results then say "Showing results without: …". `/predict` accepts an optional `drop` list of hint keys and then returns a `dropped` list; responses without `drop` are unchanged.
- **Suggestions.** 20 example searches across 8 categories (`data/suggested_queries.json`). The home and results pages show 5 chips from at least 3 categories, rotating every 8 seconds; rotation pauses on hover or focus and is off when the visitor prefers reduced motion. "More ideas ↻" shows a new set. A chip fills the search box and runs the search.
- **Shareable links.** The address bar holds the search (`/recommend?q=…&drop=…`), so back and forward work and links can be shared; `/?q=…` redirects there. Each set of results has a "Copy link" button.
- **Follow-up thread.** Each search adds a section (the query as a heading, then its results) below the earlier ones, up to 10; the oldest is dropped. A follow-up box with 3 suggestion chips sits under the latest results, and "New search" clears the thread. Each search is independent; nothing carries over from earlier ones.
- **Other.** "Something like <model>" searches its body type and price band. Brands we don't cover get a notice. Cars without a photo show a body-type silhouette. The TRANS tile shows the exact gearbox, e.g. "Automatic (DCT)". The search buttons no longer overflow on phones.

## Data version

- Catalogue export: 2026-10-31 (UTC), KB phase 10B-W6
- KB file SHA-256: `ab78684bf9ccac1a751d7d5c61cb9fafb4f886c1efdc9535cbb5ea8c8ba33565`
- `data/catalogue.csv` SHA-256: `7044eded79bf8bd6e4868903de037cf3420365362f21d0a7597b527c06ae1029`

## Evaluation

Evaluated against the research paper's query set (`paper/v0`, queries_v0) and its feasibility oracle: 213 phrasings, plus 28 end-to-end queries. Result: 0 hard-constraint violations and 0 false empties. Every feasible paper query returns all of the oracle's models, except where the 8-model limit or the per-brand cap applies.

**Scope:** the oracle checks budget, fuel, transmission family (manual/automatic), body type and seats only. Features, exact transmission types, safety stars, minimums (airbags, range, ground clearance, boot space, mileage), brands, models and exclusions are covered by the unit and end-to-end tests, not by the oracle.

## Known limitations

- 12 brands only: Honda, Hyundai, Kia, MG, Mahindra, Maruti Suzuki, Nissan, Renault, Skoda, Tata, Toyota, Volkswagen.
- 60 of 62 models have a photo, all taken from OEM brochures (`data/image_manifest.csv`; each card credits "<Make> brochure"). These images are not licensed for reuse and must be replaced before any commercial use. Hyundai Creta and Mahindra Thar Roxx have no photo and show the SUV silhouette.
- Mileage is unknown for about 40% of non-EV variants (no ARAI kmpl for 336 of 795; no figure at all for 299). Mileage minimums keep these cars, labelled "Unverified: mileage".
- Safety stars come only from Bharat NCAP: 20 models / 363 variants are rated. Older Global NCAP ratings are not used.

## Rollback

Set `DATA_SOURCE=legacy` on Render. The previous dataset and code path are still in this release.
