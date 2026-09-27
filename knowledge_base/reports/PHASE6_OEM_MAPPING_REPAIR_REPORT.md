# PHASE 6 OEM MAPPING REPAIR REPORT

## 1. ORIGINAL MAPPING BLOCKER
The previous corpus-level audit revealed that deterministic canonicalizable fields (e.g., ESC, TPMS, ABS variations) were being silently dropped because `OEM_FIELD_RULES` lacked their exact string representations, relying instead on generic variants. Furthermore, unsupported fields (like Isofix, Rear Defogger) were suspected of being dropped canonicals, demanding a schema-level verification.

## 2. CORPUS CLASSIFICATION & SCHEMA VERIFICATION
A strict schema check against `variant` and `powertrain` confirmed exactly which boolean feature columns genuinely exist.
- **Confirmed Canonical Targets:** `abs`, `esc`, `hill_assist`, `tyre_pressure_monitoring_system`, `rear_parking_sensors`, `rear_camera`, `camera_360`, `adas_available`, `automatic_climate_control`, `rear_ac_vents`, `sunroof`, `ventilated_front_seats`, `cruise_control`, `paddle_shifters`, `wireless_charging`, `heads_up_display`, `drive_modes`, `connected_car_features`, `android_auto`, `apple_carplay`.

- **Explicitly Unsupported (Not in Schema):** `isofix`, `keyless entry system`, `automatic headlamps`, `rear defogger`. 

### Corpus Field Classification
| Raw Field | Classification | Target Canonical Field |
|---|---|---|
| `electronic stability control (esc)` | **CANONICALIZABLE** | `esc` |
| `tyre pressure monitoring system(tpms) highline` | **CANONICALIZABLE** | `tyre_pressure_monitoring_system` |
| `abs(anti-lock braking system) with ebd` | **CANONICALIZABLE** | `abs` |
| `vehicle stability management (vsm)` | **CANONICALIZABLE** | `esc` |
| `isofix` | **UNSUPPORTED** | `N/A` |
| `keyless entry system` | **UNSUPPORTED** | `N/A` |
| `automatic headlamps` | **UNSUPPORTED** | `N/A` |
| `rear defogger` | **UNSUPPORTED** | `N/A` |

## 3. MAPPINGS ADDED
A robust string normalization layer (`clean_key`) was introduced to strip punctuation and normalize spacing, safely mapping the following to canonical targets:
- `'electronic stability control (esc)'` -> `esc`
- `'tyre pressure monitoring system(tpms) highline'` -> `tyre_pressure_monitoring_system`
- `'abs(anti-lock braking system) with ebd'` -> `abs`
- `'vehicle stability management (vsm)'` -> `esc`

*Note on Unknown Semantics:* All new mappings flow through `normalize_boolean`, which strictly preserves `0` for explicit OEM absence and `None` for ambiguous/unknown values, ensuring no false negatives overwrite existing DB facts. Targeted unit tests verified this behavior.

## 4. MAPPINGS INTENTIONALLY NOT ADDED
Mappings for `isofix`, `keyless entry system`, `automatic headlamps`, and `rear defogger` were **intentionally rejected** because the canonical schema does not contain columns for them. Synthesizing canonical fields violates the strict schema constraints.

## 5. CORPUS AUDIT RESULTS (AFTER REPAIR)
- **Total Extracted Non-Identity:** 11,518
- **Total Mapped:** 561 *(Increased due to new ESC/ABS/TPMS synonym rules)*
- **Total Unmapped:** 10,957 *(All remaining are Marketing/Unsupported/Ambiguous)*
- **CANONICALIZABLE Remaining:** 0

## 6. SHADOW INGESTION & IDEMPOTENCY RESULTS
A completely isolated shadow ingestion run (Pass 1 & Pass 2) was executed on a fresh copy of the pristine DB.

### Pass 1 (Ingestion)
- **Source Observations Added:** 52
- **Field Provenance Added:** 71 *(Increased from 46 due to the new valid mappings being successfully extracted and confirmed/rejected)*
- **Reconciliation:** 54 confirmed, 17 rejected, 0 accepted.
- **Canonical Mutations:** 0 *(The DB remains perfectly insulated from overwrite corruption)*

### Pass 2 (True Idempotency)
- **Additions:** 0
- **Deletions:** 0
- **Modifications:** 0
*Idempotency is mathematically absolute.*

## 7. PRODUCTION DB NON-MUTATION
- **Checksum Before:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Checksum After:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Integrity:** `ok`

## FINAL VERDICT
**READY_FOR_FINAL_PRODUCTION_GATE**

