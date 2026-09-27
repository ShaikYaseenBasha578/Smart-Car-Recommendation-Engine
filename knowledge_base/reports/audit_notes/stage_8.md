# Stage 8 — Current production state & data quality

All numbers from `/tmp/carrec_audit/prod/carrec_kb.db` (byte-identical copy of prod, SHA-1 1e3eb679…). [VERIFIED]

## Row counts
| table | rows | sqlite_sequence | deleted ids implied |
|---|---|---|---|
| manufacturer | 12 | 12 | 0 |
| model | 62 | 62 | 0 |
| generation | 62 | 62 | 0 |
| powertrain | 131 | 131 | 0 |
| variant | 832 | 833 | 1 (id 813) |
| variant_alias | 469 | 469 | 0 |
| source | 8 | 8 | 0 |
| source_observation | 3,451 | 3,757 | 306 (1658–1762, 2608–2808) |
| field_provenance | 36,445 | 37,319 | 874 (27840–28383, 32185–32514) |
| safety_rating | 27 | 27 | 0 |
| safety_test | 37 | 37 | 0 |
| safety_test_applicability | 23 | 23 | 0 |
| warranty | 18 | 18 | 0 |
Views: v_effective_variant 832, v_variant_full 832.

Claimed canonical 12/62/62/832/131 → **matches** [VERIFIED]. Phase 8B (+37 safety_test, +37 obs, +20 applic, 0 canonical) → matches pre/post copies [VERIFIED]. 37 PDF SHA-256 → 37/37 valid [VERIFIED].

## Phase 9B diff (backup c1e0647c vs prod, both copies; full-row EXCEPT both directions, every table) [VERIFIED]
- safety_test: 3 rows differ (ids 9, 16, 17) — only `resolution_status` UNRESOLVED→RESOLVED and `resolution_justification` changed.
- safety_test_applicability: +3 (ids 21 → test 9/model 54/gen 22; 22 → 16/7/24; 23 → 17/13/28; all MODEL_LEVEL, variant NULL); 0 removed.
- sqlite_sequence: 1 row differs (applicability seq 20→23).
- All other tables identical; schema identical. **Claim confirmed exactly.**

## Mileage / range coverage with powertrain-applicable denominators [VERIFIED]
| fuel | variants | kmpl | km/kg | EV range |
|---|---|---|---|---|
| Petrol | 525 | 340 (64.8%) | — | — |
| Petrol Hybrid | 20 | 19 (95.0%) | — | — |
| Flex Fuel | 1 | 0 | — | — |
| Diesel | 165 | 84 (50.9%) | — | — |
| Diesel Mild Hybrid | 2 | 0 | — | — |
| CNG | 82 | 6 (petrol-mode) | 39 (47.6%) | — |
| Electric | 37 | 0 | 0 | 35 (94.6%) raw; 37 (100%) via v_effective_variant |
- Phase 7A 64.6% petrol = 340/526 (Petrol+Flex) and 50.3% diesel = 84/167 (Diesel+DMH) → **reproducible, not stale**; Phase 9 used 546 (Petrol+Hybrid+Flex) = 359/546 = 65.8%. The reports use three different petrol groupings → [CONTRADICTED] only in denominator definition, not data.
- Via `v_effective_variant`, petrol kmpl rises to 350/525 because editions inherit base mileage (derived, not observed).

## Other field coverage (raw → effective, of 832)
Lowest: drive_modes 280→295, paddle_shifters 444→461, wireless_charging 577→596, HUD 582→597, cruise_control 629→643, fuel_tank 725→741. Price/dimensions/airbags/abs/seating: 812 raw (all from V6 CSV), 832 effective (20 editions inherit base values — **edition price = base price is a derived value, not a fact**). Powertrain: engine_cc NULL on 11 (all EV); power/torque complete.

## Quality checks
| Check | Result |
|---|---|
| integrity_check | ok |
| FK violations | 297 (field_provenance→source_observation only) |
| variant/powertrain/generation cross-model mismatch | 0 |
| duplicate variant (model, lower(name)) / full_name / powertrain | 0 / 0 / 0 |
| EV with kmpl/tank; non-EV with range; non-CNG with km/kg | 0 / 0 / 0 |
| CNG with kmpl | 6 (ids 213, 217, 245, 345, 556, 591) — petrol-mode figures or mislabelled; 4 have no km/kg at all |
| price NULL | 20 (exactly the 20 editions) — PHASE9 calls them "variants that could not be resolved" → [CONTRADICTED] |
| out-of-range mileage/airbags/dims/seats | 0 |
| `adas_tier` values | '0.0' (698) / '1.0' (110) / NULL (24): a duplicated boolean, not a tier |
| aliases needs_review / verified | 189 / 0 of 469 |
| observations "resolved" with NULL variant | 20 (BNCAP model-level; by design) |
| observations with non-schema status values | resolved, resolved_with_warning, unresolved, model_level, RESOLVED, UNRESOLVED, NO_MATCH (schema comment lists pending/applied/conflict/rejected/unresolvable) |
| safety_test vs its observation status | 3 disagree (9B) |
| unresolved safety tests | 4 UNRESOLVED (Citroen×2, VinFast×2), 10 NO_MATCH |
| EV test applied to ICE-only model | 1 (test 27 Harrier.EV → model 30) |
| OEM observations under wrong source | 52 (source 1 instead of 6) |
| edition identity contradictions | variant 833 (name 1.5 DCT vs 1.0 TC powertrain), 814, 826 base-trim mismatch |
| CarWale E/EX swap | obs 2842/2843 still swapped |
| canonical transmission with zero live provenance | e.g. variants 10, 277 (transmission has no accepted provenance for any variant; came from V6 CSV) |
| missing artifacts / checksum mismatches | 0 / 0 |

Checksum gate: `1e3eb679…` ✔
