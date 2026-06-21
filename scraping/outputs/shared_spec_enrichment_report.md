# Shared Spec Enrichment Report

- Records inspected: 125
- Raw candidates extracted: 1422
- Unique record-field candidate groups: 1421
- Accepted record-field assignments: 1134
- Existing values preserved: 287
- Duplicate candidates: 1
- Superseded candidates: 0
- Rejected candidates: 0
- Unresolved record-field cells with no candidate: 201
- Unresolved conflicts: 0
- Weighted recommendation completeness before: 47.94%
- Weighted recommendation completeness after: 60.37%

## Candidate Disposition

| Status | Candidates |
|---|---:|
| ACCEPTED | 1134 |
| DUPLICATE_CANDIDATE | 1 |
| EXISTING_VALUE_PRESERVED | 287 |

## Unresolved Cell Reasons

| Null reason | Cells |
|---|---:|
| FIELD_NOT_PUBLISHED | 125 |
| SOURCE_UNAVAILABLE | 44 |
| UNSAFE_TO_INHERIT | 32 |

## Source Overlap

Only one adapter/source supplied candidates for accepted assignments, so the zero-conflict result means competing candidates generally did not reach conflict detection in this batch.

| Field | Assignments | Single-source | Multi-source disagreements |
|---|---:|---:|---:|
| `boot_space_litres` | 109 | 109 | 0 |
| `cylinders` | 118 | 118 | 0 |
| `drivetrain` | 119 | 119 | 0 |
| `fuel_tank_capacity_litres` | 108 | 108 | 0 |
| `gearbox_speeds` | 46 | 46 | 0 |
| `ground_clearance_mm` | 125 | 125 | 0 |
| `height_mm` | 72 | 72 | 0 |
| `length_mm` | 72 | 72 | 0 |
| `turbocharged` | 96 | 96 | 0 |
| `turning_radius_metres` | 125 | 125 | 0 |
| `wheelbase_mm` | 72 | 72 | 0 |
| `width_mm` | 72 | 72 | 0 |

## Inheritance Policy

- inherited_assignments_allowed: 1134
- candidate_assignments_blocked: 0
- candidate_assignments_never_generated_scope_or_source: 201
- model_level_assignments: 538
- powertrain_level_assignments: 596
- direct_exact_record_assignments: 0

## Coverage

| Field | Before | After | Gain |
|---|---:|---:|---:|
| `boot_space_litres` | 0 | 109 | 109 |
| `ground_clearance_mm` | 0 | 125 | 125 |
| `kerb_weight_kg` | 0 | 0 | 0 |
| `turning_radius_metres` | 0 | 125 | 125 |
| `fuel_tank_capacity_litres` | 0 | 108 | 108 |
| `drivetrain` | 6 | 125 | 119 |
| `cylinders` | 6 | 124 | 118 |
| `turbocharged` | 28 | 124 | 96 |
| `gearbox_speeds` | 35 | 81 | 46 |
| `length_mm` | 53 | 125 | 72 |
| `width_mm` | 53 | 125 | 72 |
| `height_mm` | 53 | 125 | 72 |
| `wheelbase_mm` | 53 | 125 | 72 |
