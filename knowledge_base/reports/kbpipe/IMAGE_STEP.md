# Image step (`kbpipe/images.py`)

Gives catalogue models that have no photo one from the **maker's own brochure PDF already on disk**.

## Sourcing rule (the app's existing practice)
The app's 60 original photos came from OEM brochures (commits `e137c27`, `bdc599a`, branch `feat/brochure-images-only`):
WebP, 800 px wide, quality 80, no metadata, `static/car_images/<make>_<model>.webp`, one row per model in
`data/image_manifest.csv` (`make, model, filename, source, license, attribution`). `source` is `<pdf>, p.<n>`; attribution is
`<Make> brochure`; license is "OEM brochure - not licensed for reuse; replace for commercial use". The step follows this
exactly and adds the PDF SHA-1 to `source` (`<pdf>, p.<n>, SHA-1 <40 hex>`). It never downloads anything, never uses
aggregator/press/search/social images, never generates or edits pixels (a human crop is a plain rectangle of the brochure picture),
and calls no model. A model with no brochure keeps its body-type placeholder.

## Commands
Dry run (writes only into the run folder; ~10 min for 30 large brochures):

    .venv-kbpipe/bin/python -m kbpipe.images --app-repo ~/carrec_worktrees/recsys-v3 [--run-dir DIR] [--only "Tata/Punch"]

Run folder: `candidates/<slug>/c1..c3.jpg`, `contact_sheet.html`, `picks.json`. Edit `picks.json`: set `choice` (1-3, null = keep
placeholder) and optionally `crop` = [left, top, right, bottom] fractions of the chosen candidate. Models whose confidence is
below 0.62 or whose lead over the runner-up is under 0.04 are left `choice: null, needs_human: true`.

Apply (processes each choice into the app, adds manifest rows; refuses to touch a model that already has an image unless `--replace`;
refuses if the PDF's SHA-1 changed since the run):

    .venv-kbpipe/bin/python -m kbpipe.images --app-repo ... --apply DIR/picks.json [--replace]

Needs Pillow and numpy in addition to PyMuPDF (not yet in `kbpipe/requirements.txt`; add `Pillow`, `numpy`).

## Hook for `kbpipe update`
Stage placed **after the brochure stage and before the export stage**:

    from kbpipe import images
    result = images.stage(cfg, run_dir, write=False)          # --no-write: candidates only
    # with writes and a human-edited picks file:
    result = images.stage(cfg, run_dir, write=True, picks_path=".../picks.json", replace=False)

`cfg` is the loaded kbpipe config (uses `app_repo`, `oem_dir`, `oem_new_dir`). Candidates go to `<run_dir>/images/`. Returns
`{"run_dir", "models", "no_brochure": [...], "need_human": [...]}` (plus `"apply": {"applied", "skipped"}` when writing). The stage
should only report these lists; applying needs a human-edited picks file, so it belongs after review, not in the unattended run.

## How far to trust it (measured 2026-11-17, 28 models with a usable brochure, eye picks from Part 1 of the image task)
Agreement = same brochure page as the picked image (generous: it ignores whether the exact picture matches).
- Heuristic v1 (size, aspect, early page, text share, colour/edge): top-1 7/28 (25%), top-3 contains the eye pick 14/28 (50%).
- v2 (adds a "busiest landscape window" candidate for portrait pages): top-1 7/28 (25%), top-3 17/28 (61%).
- v2 pre-filled a pick for 5 models; 3 were right (60%). Wrong pre-fills: a hero with a large text overlay, a hero with a person.
- The v2 tuning used the same 28 models after seeing v1 results, so these numbers are optimistic.
Conclusion: **never apply without a human pick.** The step is a candidate finder; the contact sheet is the product. Weaknesses:
no car detector (text-free interiors and detail shots score well), tall pages with a small car need a hand crop, vector or tiled
heroes are only caught as page-region crops.
