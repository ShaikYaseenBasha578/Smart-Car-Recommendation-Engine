# Dimensions Enrichment Notes

## Kerb Weight Caveat
The `kerb_weight_kg` field contains a **model-level approximation**, not a precise trim-specific weight. Because a car's weight varies significantly based on engine options, transmission, battery packs (for EVs), and trim-level features, the value here is indicative of the base/average model as published by standard automotive platforms (CarDekho, CarWale, 91wheels). 

A new boolean column `kerb_weight_kg_approximate` has been added to `dimension_enrichment.csv` (set to `True` for all rows) to explicitly flag this to any future ranking engines or developers. **Do not use this field for precise payload or range calculations without knowing the exact trim.**

## Completeness
- `length_mm`, `width_mm`, `height_mm`, `wheelbase_mm`: 100% complete.
- `fuel_tank_litres`: 87% complete (Missing intentionally on EVs).
- `kerb_weight_kg`: 75% complete (47/62 models).
