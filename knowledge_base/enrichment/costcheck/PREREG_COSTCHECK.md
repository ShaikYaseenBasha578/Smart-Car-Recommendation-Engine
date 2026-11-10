# Cost check pre-registration: "Claude verifies Flash" vs "Claude extracts alone"
Frozen in the commit "costcheck pre-registration", before any measured run. Nothing below changes after it.

## Pages (all from round 2; Flash outputs reused, 0 new agy calls)
| key | type | brochure p. | Flash call | fields | catalogue variants | Flash candidate rows (after per-trim split) |
|---|---|---|---|---|---|---|
| syros_p7 | text-layer grid (trims as row headers over feature lists; my round-2 layout label for it was "list", there is no text-layer *matrix* page in the gold set) | Kia Syros p7 | #018 | cruise, wireless | 17 | 2 |
| victoris_p16 | OCR / scrambled-layer page | Maruti Victoris p16 | #021 | km/l, km/kg, cruise, paddle | 21 | 17 |
| venue_p20 | tick-icon grid | Hyundai Venue p20 | #013 | cruise, paddle, wireless | 19 | 39 |

Inputs (identical for both arms; VERIFY adds only candidates.json): page PNG tiles, round-2 page text (`prompts_r2/*.pagetext.txt`),
base-variant names (editions excluded), field list. Tiles (see `inputs_frozen/manifest.json`):
- Syros: 3 horizontal tiles of the 1692×648 pt page, 140 dpi, 20 pt overlap.
- Victoris: 1 full page, 150 dpi.
- Venue: tile1 = full page at 100 dpi; tile2 = header strip stacked above the Comfort & Convenience block, 115 dpi.

Candidate rows given to VERIFY: every round-2 Flash row after the per-trim split (not only filter-passing ones), with the
trim label, label_source, quotes, qualifier, field/value/unit, and the catalogue variant names the round-2 mapper assigned
(names only; mapper ambiguity leaves the list empty). No truth values are in any input.

## Runs
- 3 pages × 2 arms × 2 repeats = **12 measured runs**, plus **2 overhead-baseline runs** (same harness, prompt "Reply with the single word OK.").
- `claude -p --model sonnet --output-format json --restricted --tools Read --strict-mcp-config --disable-slash-commands --setting-sources "" --no-session-persistence --permission-mode dontAsk --permission-prompts none --max-budget-usd 2`,
  cwd = a per-run folder holding only that run's inputs. `claude --help` has no max-turns flag, so turns are bounded by the budget cap. Effort is left at its default.
- Isolation canary (before freezing, on unrelated files): reads outside the folder were refused, no shell or write tool existed.
  An image-Read canary on a non-measured page worked, and the JSON reports token usage.
- Prompts: `prompt_common.txt` + `prompt_extract.txt` or `prompt_verify.txt` + `prompt_output.txt`. The two arm instructions are verbatim from the brief.
  Both arms use the same output schema (`cells` + `review`; EXTRACT's `review` is empty).

## Scoring and decision
Defined in the docstring of `score_costcheck.py` (truth set, cell scoring, qualifier keys written from page text before any run,
token accounting, decision). Summary:
- tokens = input + cache_creation + cache_read + output from the JSON usage. **The decision uses these gross totals**;
  net-of-overhead totals (baseline subtracted), cost and wall time are reported alongside.
- HYBRID iff all of: (1) VERIFY ≤ 60% of EXTRACT in mean total tokens summed over 3 pages; (2) VERIFY has 0 wrong values on truth rows in all 6 runs;
  (3) VERIFY pooled recall ≥ EXTRACT's − 5 points; (4) VERIFY qualifier errors ≤ EXTRACT's.
- Otherwise: per page, the same four conditions on that page alone; ≥1 page meeting all four → HYBRID-PARTIAL (naming the page types), else ALL-CLAUDE.
- Truth is sparse on these pages (Syros 19 cells, Victoris 32, Venue 16). Cells without truth are UNKNOWN and listed, never counted as correct or wrong.
- One run pair per page type, 2 repeats: the result is a pilot measurement, not a distribution.

## Mechanical fixes before freezing
Typos in `build_inputs.py` (a dict key, a pypdfium2 argument). The scorer was self-tested on synthetic run outputs (not model output).

## File hashes
```
    739e3c98c3b7b0ec2b34fb274356b9364ef31995  prompt_common.txt
    6324c4b646aaef7635d52267e74a4523b620d458  prompt_extract.txt
    5ea983850514fe091bba29fae454935282c4ad1f  prompt_verify.txt
    d8cc9c5ba7e0fe90cfa090a2c2d00159ffa2dc2f  prompt_output.txt
    5aeac423a37013fdd971e06dbae331249ca3db60  build_inputs.py
    bb1b7cdda9f4569215c5cfb3b60cdda23feb510c  score_costcheck.py
    8b49acbadc44b1ce64f22892deb24b513b4a4c64  run_costcheck.sh
    b67cb4119a4498dd80860f70322b0007bd856803  inputs_frozen/manifest.json
    87bdc1ce0a23fb8ebd8dd596a6cf93ec447995f7  inputs_frozen/syros_p7_candidates.json
    28dd6e36cd7b7db8185a5cc2d96341079d14bffe  inputs_frozen/syros_p7_variants.txt
    fcec6ce625bdcffb21103192988815ee417bfc25  inputs_frozen/venue_p20_candidates.json
    acf4d2805590f70a33ddcfce2d6c9c3d48d69572  inputs_frozen/venue_p20_variants.txt
    c74cf94b7c1f2515dbf278627aa623f82bea5cd7  inputs_frozen/victoris_p16_candidates.json
    8c004fd367b023af9896b257dae30816adcfd743  inputs_frozen/victoris_p16_variants.txt
```
Input files (scratch):
```
    57d390b8b3331b078cb75d049d8552b5d159e673  syros_p7/tile1.png
    4b9066f2e3e0404c3e4db3f348944edbbf2f3bd4  syros_p7/tile2.png
    efd3358e40d6d01b28351c306a10b11cb8c77eda  syros_p7/tile3.png
    0b97a63b4cbb3ce9b58ceb787c06374e263b7498  venue_p20/tile1.png
    7fe55bd004def80a995c446b947e6e824bd15ea5  venue_p20/tile2.png
    3390be72b98728c2894efa2722cd0f392931e1e0  victoris_p16/tile1.png
    be754fa77a04da2be2f3c6e934739a6e41c85109  syros_p7/page_text.txt
    bda35bbec805d3657d2bdce9e635945bc852097c  venue_p20/page_text.txt
    10e65c39b7b3ab08b9f5af808094e4feac8347cd  victoris_p16/page_text.txt
```
