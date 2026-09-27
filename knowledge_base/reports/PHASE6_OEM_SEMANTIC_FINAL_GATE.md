# PHASE 6 OEM SEMANTIC FINAL GATE

## 1. MAPPINGS REVIEWED
All newly added OEM mappings were semantically audited against strict equivalence constraints to ensure true canonical representation.

- **`traction control system tcs` -> `esc`**: **REMOVED**. (Traction control prevents wheel spin during acceleration; ESC prevents lateral skidding. OEM assertion of TCS does not guarantee full ESC.)
- **`hill descent control` -> `hill_assist`**: **REMOVED**. (Descent control manages downhill braking; hill assist holds brakes on uphill start.)
- **`driver airbag` -> `airbags`**: **REMOVED**. (Does not guarantee total airbags = 1.)
- **`co driver airbag` -> `airbags`**: **REMOVED**. (Does not guarantee total airbags = 2.)
- **`epb with auto hold abs with ebd` -> `abs`**: **KEPT**. (Explicit presence of ABS logic.)
- **`vehicle stability assist vsa with electronic` -> `esc`**: **KEPT**. (Honda's VSA is their proprietary name for full ESC).
- **`adaptive cruise control` -> `cruise_control`**: **KEPT**. (Adaptive cruise is a superset of cruise control).
- **`Honda sensing ADAS` -> `adas_available`**: **KEPT**. (Honda Sensing is standard ADAS).
- **`smartphone connectivity` -> `connected_car_features`**: **REMOVED**. (Commonly refers to Apple CarPlay/Android Auto local projection, not cellular telematics.)
- **`connectivity dongle optional` -> `connected_car_features`**: **REMOVED**. (Dealer-level accessory; does not represent base variant OEM connected car logic).
- **`quadruple vertical ac vents` -> `rear_ac_vents`**: **REMOVED**. (Lacks explicit "rear" semantic presence).
- **`drive modes diesel zip zap zoom` -> `drive_modes`**: **KEPT**. (Tata's explicit selectable engine map system).
- **`6 airbags system` -> `airbags`**: **REVISED**. (Fixed normalizer lambda so value extracts as the integer `6` if standard, rather than returning `None`.)
- **`esc electronic stability control abs antilock braking system ebd` -> `esc`, `abs`**: **KEPT**. (Explicit simultaneous presence).

## 2. 417 UNRESOLVED VALUE CLASSIFICATION
The previous audit reported 417 cases where a mapping rule existed but the value could not be resolved by the boolean normalizer.
- **Genuinely Unknown/Unsupported**: 0
- **Bad Normalization (Fixed)**: 195 (Fields where explicit absence like `"-"` was dropping to `None` instead of mapping to `0`. Re-mapped `"-"` to strictly mean `0` / False).
- **Valid Canonicalizable Evidence Gap (Fixed)**: 12 (Fields like `6 airbags system` providing the number implicitly inside the key, fixed with a lambda).
- **Semantically Ambiguous**: 210 (Fields with values like `"O"`, `"Optional"`, `"O (CVT only)"`. Strictly mapped to `None` since canonical schemas represent guaranteed standard features, and writing `0` would falsely indicate unavailability.)
- **Extraction Artifact**: 0

*No semantically deterministic canonical fact remains unresolved.*

## 3. REGRESSION RESULTS
A dedicated semantic unit test suite was executed to prove negative constraints.
- `"-"` mapped correctly to `0` (False).
- `"O"`, `"Optional"` mapped correctly to `None` (Unknown).
- `traction control` does NOT imply ESC (Passed).
- `hill descent` does NOT imply Hill Assist (Passed).
- `driver airbag` does NOT set total airbags to 1 (Passed).
- `"6 airbags system"` correctly maps to integer `6` (Passed).
- Generic AC vents do NOT imply rear AC vents (Passed).
- Honda VSA maps to ESC (Passed).

## 4. PASS 1 (INGESTION) LOGICAL DB DIFF
Isolated shadow ingestion was run on the pristine production DB using the semantically hardened mappings.
- **manufacturer**: 0 added, 0 deleted, 0 modified
- **model**: 0 added, 0 deleted, 0 modified
- **generation**: 0 added, 0 deleted, 0 modified
- **variant**: 0 added, 0 deleted, **1 MODIFIED**
  - *Mutation Justification*: Variant ID 669 updated `paddle_shifters` from `None` to `0`. This is a **genuinely authoritative improvement** because the normalizer fix correctly mapped the explicit OEM text `"-"` into a verified absence `0`, filling a previously unknown canonical gap securely!
- **powertrain**: 0 added, 0 deleted, 0 modified
- **source_observation**: 52 added, 0 deleted, 0 modified
- **field_provenance**: 133 added, 0 deleted, 0 modified

## 5. PROVENANCE RECONCILIATION
- **Total field_provenance rows generated**: 133
- **Confirmed (matched existing schema)**: 104
- **Rejected (conflict with existing schema)**: 28
- **Accepted (overwrite)**: 1 (The explicit paddle_shifter absence mentioned above).

## 6. PASS 2 (IDEMPOTENCY) LOGICAL DB DIFF
Re-running the pipeline entirely proved perfect idempotency:
- **0 additions, 0 deletions, 0 modifications** across all seven schema tables.

## 7. PRODUCTION DB NON-MUTATION
- **Checksum**: `6ea3b931f7c157880445688665c500fb368a0c7b`
- **SQLite Integrity**: `ok`

---
## FINAL VERDICT
**READY_FOR_PRODUCTION_INGESTION**
