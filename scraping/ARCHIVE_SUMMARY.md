# Scraping Archive Summary

The project cleanup moved historical scraping artifacts into:

`archive/scraping_reproducibility/`

The archive contains raw HTML caches, superseded interim datasets, historical reports, one-off probe scripts, source-audit notes, and fetch logs. These files are not needed for Flask runtime and are not required by the final canonical processed datasets.

Active outputs remain in place:

- `datasets/processed/carrec_canonical_recommendation_ready.*`
- `datasets/processed/carrec_canonical_nullable_usable.*`
- `datasets/processed/carrec_canonical_excluded.json`
- final audit, resolution, conflict, quarantine, and cleanup reports under `scraping/outputs/`

The local archive is gitignored. Its index is:

`archive/scraping_reproducibility/ARCHIVE_INDEX.md`

To inspect archived evidence, open the archive index and follow the archived path listed for the original file. To rebuild the final dataset, use the retained active pipeline inputs and scripts; restoring archived raw caches is only needed for deeper source-level replay.
