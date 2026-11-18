# Missing 16 models: regression and no-write run (18 Nov 2026)

Branch `kb/kbpipe`. Nothing was written to the KB (`--no-write`), no model call was made (every LLM backend was patched to raise; attempts: 0), pages came from the cache (0 network requests).

## Regression (old linker vs new linker, offline, cached pages)

`kbpipe/tools/link_regression.py`: `extract.model_bundle` re-run for all 91 `EXISTING` models of the 17 Nov discovery file, once on the tree before the change (`git archive 1c27966`) and once on this tree.

| | |
|---|---|
| CarWale versions compared | 1642 (91 models) |
| linked before | 1295 |
| identical pairs (CarDekho address and reason) | 1546 (all 1295 old links, plus 251 that were unlinked and still are) |
| **changed or disappeared** | **0** |
| new pairs for existing models (unlinked before, linked now) | 96 |

Variant-page outcomes for existing models are also unchanged: the 30 earlier 'unreadable / served another page' problems are the same 30; the only added problems are 'variant page unreadable' for the 96 new pairs, whose pages are not in the cache (offline run).

The 96 new pairs are in `missing16_regression_new_pairs_existing_models.tsv`. They are not errors, but they are new links and should be read before the rules are used on a write run:

| Rule | New pairs on existing models |
|---|---|
| D1 price | 37 |
| dual tone | 21 |
| D1 price+battery | 20 |
| battery | 17 |
| descriptor | 1 |

- *D1 price*: identity equal and unique, prices differ beyond 0.5% (CNG variants of Magnite, Gravite, Kwid, Grand Vitara; Thar Roxx; XEV 9e/9S 'No Charger'; Windsor EV; e VITARA; Sonet, Harrier, Bolero, Baleno and others). No price is written for these, a PRICE_DISAGREES item is raised.
- *dual tone*: 21 pairs (Nexon 9, XUV 3XO 7, Curvv 3, Duster 2) where one site writes Dual Tone or DT and the other does not, with exact price agreement and one candidate. This rule goes beyond the plan's enumerated list; see the report.
- *battery*: Carens Clavis EV 8, XEV 9e 5+4.

## No-write run on the 16 models

Run folder: `knowledge_base/runs/missing16_nowrite_2026-11-18_3` (the final run; `…_18` and `…_18_2` are earlier runs of the same command before the Tomahawk page-name fix and the linker-version fix, kept as evidence). Command: `kbpipe run --no-write --no-verify --label missing16_nowrite_2026-11-18 --only <each of the 16>` with refresh intervals set so cached pages are used and the OEM brochure folder pointed at a scratch folder.

Gates on staging: **passed** (schema, provenance 1941 of 1941 cells, rows, explained, reviews); idempotent re-apply: yes; staging would add 13 models, 72 variants, 1940 cells.

| Model | CarWale versions | Linked and used | Rules used | Held (variants not added) | Cells (accepted source) | Review items |
|---|---|---|---|---|---|---|
| Honda ZR-V | 1 | 0 | - | 1 | - | MODEL_NOT_ADDED 1 |
| Hyundai Creta Electric | 29 | 28 | D1 price+battery 4, battery 24 | 1 | carwale 188, oem 700 | PRICE_DISAGREES 4 |
| Kia Syros EV | 7 | 7 | D1 price+battery 1, battery 6 | 0 | carwale 53, oem 147 | PRICE_DISAGREES 1 |
| MG Comet EV | 5 | 3 | D1 price+battery 3 | 2 | carwale 35 | PRICE_DISAGREES 3 |
| MG Hector Tomahawk EV | 4 | 4 | D1 price+battery 4 | 0 | carwale 12, oem 108 | PRICE_DISAGREES 4 |
| MG Hector Tomahawk PHEV | 2 | 0 | - | 2 | - | MODEL_NOT_ADDED 1 |
| MG ZS EV | 6 | 2 | D1 price+battery 2 | 4 | carwale 38 | PRICE_DISAGREES 2 |
| Mahindra BE 6 Sporteq | 20 | 10 | D1 price+battery 10 | 10 | carwale 34, oem 247 | PRICE_DISAGREES 10 |
| Mahindra XUV 3XO EV | 4 | 2 | battery+descriptor 2 | 2 | carwale 11, oem 44 | - |
| Mahindra XUV400 | 5 | 5 | original rules 5 | 0 | carwale 81 | - |
| Maruti Suzuki Invicto | 3 | 3 | hybrid fuel 3 | 0 | carwale 63 | - |
| Nissan X-Trail | 1 | 0 | - | 1 | - | MODEL_NOT_ADDED 1 |
| Tata Tigor EV | 4 | 4 | battery 4 | 0 | carwale 33, oem 67 | - |
| Toyota Camry | 4 | 1 | dual tone+hybrid fuel 1 | 3 | carwale 23 | - |
| Toyota Fortuner Legender | 3 | 2 | dual tone 2 | 1 | carwale 36 | - |
| Toyota Urban Cruiser Ebella | 2 | 1 | battery 1 | 1 | carwale 20 | - |

'CarWale versions' excludes the listing's own special version (ZS EV 100-Year, skipped as an edition). Cells are written by accepted source; CarDekho confirms 1757 of them. A held variant is a CarWale version with no linked CarDekho variant ('only one site lists it'); it is not added and is reported in `flags.tsv`.

### Why variants are held

- **ZR-V (1)**: CarWale 'Sport ... e:HEV' vs CarDekho 'Hybrid'; the trim word 'Sport' appears on one site only. Review item MODEL_NOT_ADDED.
- **Hector Tomahawk PHEV (2)**: CarDekho says '7-Seater', CarWale gives no seat count, prices differ. The implied-seat rule needs an agreeing price. MODEL_NOT_ADDED.
- **X-Trail (1)**: CarWale has only fuel and gearbox words, CarDekho names the trim 'STD'. MODEL_NOT_ADDED.
- **Camry (3)**: 'Elegant' vs 'Elegance' (not linked, by design), and the two 'Platinum White Pearl' colour versions.
- **Creta Electric (1)**: 'Excellence 51.4 kWh Dual Tone' has no 51.4 kWh counterpart on CarDekho (its nearest name is a 42 kWh trim).
- **BE 6 Sporteq (10)**: every '11.2kW Charger' version (CarDekho has no charger designation).
- **XUV 3XO EV (2)**: the 'with Charger' versions. **ZS EV (4)**: colour-named versions (Dark Grey, Iconic Ivory). **Comet EV (2)**: the Dual Tone versions (prices also differ). **Fortuner Legender (1)**: the mild-hybrid version ('Neo Drive' on CarDekho). **Urban Cruiser Ebella (1)**: E3 Dual Tone.

