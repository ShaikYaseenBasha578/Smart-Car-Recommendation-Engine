# Schema proposal batch — 2026-11-06 (GATE G2; nothing applied)

P16 requires owner approval for any DDL. Each proposal is independent. All would go through P10 with a backup, a dry run and a full diff.

## S1. Powertrain-level quarantine
**Problem:** `evidence_quarantine.target_table` (CHECK) excludes `powertrain`, so a doubtful power, torque or cc can only be nulled (10G did this to pt 84 and 88).

**Change:**
- Add `'powertrain'` to the CHECK (table rebuild, as 10E did for `'warranty'`).
- Add a view `v_powertrain_q` masking `power_bhp`, `torque_nm`, `engine_cc` and `battery_capacity_kwh`.
- Point the exporter at `v_powertrain_q`.

**Benefit:** a doubtful value stays stored instead of being overwritten. 10G's two NULLs could be restored as quarantined values, reversibly.

**Cost:** one table rebuild, one new view, one exporter line. No catalogue change by itself.

## S2. Masking an edition's own powertrain and transmission
**Problem:** four editions contradict their own identity and are fully held (P8), still visible with wrong data:
| Edition | Name says | KB holds |
|---|---|---|
| 833 Virtus Anniversary | 1.5 Turbo DCT | 999 cc, torque converter, base 1.0 TC |
| 821 Brezza Zxi | 1.0 Turbo | 1462 cc |
| 815 Exter HX 6 DT | HX 6 | base HX 2, so HX 2's price and features |
| 816 Exter HX 10 DT | HX 10 | base HX 3, so HX 3's price and features |

`v_variant_canonical_q` passes `powertrain_id` through unmasked, and its `COALESCE` inherits base values whatever the base is.

**Change:**
- Add `identity_held INTEGER DEFAULT 0` to `variant`, or a `target_field='identity'` quarantine row read by the view (no new column; my preference).
- For a held edition, the view returns NULL for `powertrain_id`, `transmission`, and every inherited cell.
- The exporter must accept these rows. **Two options:**
  - **A (recommended):** drop held editions from the catalogue until an OEM source settles them (832 → 828 rows).
  - **B:** export them with blanks. This needs exporter changes, since NULL fuel and transmission currently raise `ExportError`, and the app's filters must handle them.

**Paper:** the snapshot is frozen, so no effect (P13 exposure already recorded for 821, 831, 832, 833, 815, 816).

## S3. Catalogue-currency mechanism
**Problem:** there is no model-year dimension, so P7 can only hold. Known cases: Baleno (brochure 23.80 / 24.77 km/l vs KB 22.35 / 22.94), Brezza (KB has no 1.0 Turbo rows matching current listings), WagonR 225 and the 1.0 rows, S-Presso and Alto K10 petrol power, Kylaq Sportline, Jimny (including obs 3302 / v597 "Zeta" vs "Zeta PRO", and paddle shifters on 599).

**Change (smallest that works):** a new table `model_catalog_status(model_id, status, kb_data_as_of, brochure_path, brochure_sha1, brochure_as_of, note)`, with `status` in `current | stale_hold | refresh_in_progress`.
- The exporter adds a `catalogue_status` column, so the app can flag stale models.
- A model refresh then becomes one reviewed phase per model: every variant is rewritten from the brochure in one go, satisfying P7's "never one variant on its own".

**Not proposed:** per-variant model-year rows. That is a bigger redesign, and `generation` already exists as 62 placeholders.

## S4. New fields from the handoff
Add nullable columns to `variant`: `gears INTEGER`, `cylinders INTEGER` (better on `powertrain`), `push_start INTEGER`, `led_headlamps INTEGER`, `alloy_wheels INTEGER`, `isofix INTEGER`, `touchscreen_cm REAL`, `powered_driver_seat INTEGER`.

Each needs matching lines in `v_variant_canonical_q` (a view rebuild) and exporter and app work. Values come only from brochures (P1), so coverage grows by phase. Not mentioned stays NULL.

**Recommendation:** add `isofix`, `push_start`, `led_headlamps`, `alloy_wheels` and `gears` first; most brochures print them. Defer `touchscreen_cm` and `powered_driver_seat`, whose wording varies.

## Decision needed
See NEEDS_YOU N5.
