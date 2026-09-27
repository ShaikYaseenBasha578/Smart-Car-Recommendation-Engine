-- Phase 10B W0: quarantine / amendment schema (additive only).
-- Design: knowledge_base/reports/phase10b/PHASE10B0_QUARANTINE_DESIGN.md (option B, commit 373efae).
-- Idempotent: every statement uses IF NOT EXISTS. Touches no existing table, row, index or view.
-- Owner decisions applied: BNCAP Citroen/VinFast UNRESOLVED -> no_match ('manufacturer_not_in_kb');
-- v_variant_canonical_q is the required consumer read path.

CREATE TABLE IF NOT EXISTS evidence_quarantine (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  target_table    TEXT NOT NULL CHECK (target_table IN
                   ('source_observation','field_provenance','variant','safety_test','safety_test_applicability')),
  target_id       INTEGER NOT NULL,
  target_field    TEXT,
  reason_code     TEXT NOT NULL,
  phase           TEXT NOT NULL,
  note            TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  released_at     TEXT,
  released_reason TEXT,
  CHECK (target_table <> 'variant' OR target_field IS NOT NULL),
  CHECK (released_at IS NULL OR released_reason IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_quarantine_active
  ON evidence_quarantine(target_table, target_id, IFNULL(target_field,''), reason_code)
  WHERE released_at IS NULL;

CREATE TABLE IF NOT EXISTS evidence_amendment (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  target_table TEXT NOT NULL,
  target_id    INTEGER NOT NULL,
  column_name  TEXT NOT NULL,
  old_value    TEXT,
  new_value    TEXT,
  reason_code  TEXT NOT NULL,
  phase        TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_amendment_target ON evidence_amendment(target_table, target_id);

CREATE VIEW IF NOT EXISTS v_active_quarantine AS
  SELECT id, target_table, target_id, target_field, reason_code, phase, created_at
  FROM evidence_quarantine
  WHERE released_at IS NULL;

-- Live evidence: provenance whose observation exists (drops the 297 historical orphans)
-- and neither the observation nor the provenance row is under active quarantine.
CREATE VIEW IF NOT EXISTS v_live_evidence AS
  SELECT fp.id AS fp_id, fp.variant_id, fp.field_name, fp.decision, fp.accepted_value,
         so.id AS observation_id, so.source_id
  FROM field_provenance fp
  JOIN source_observation so ON so.id = fp.source_observation_id
  WHERE NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='source_observation' AND q.target_id=so.id)
    AND NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='field_provenance' AND q.target_id=fp.id);

-- Corroboration = distinct sources with live accepted/confirmed evidence for (variant, field);
-- quarantined canonical cells get no row (count 0).
CREATE VIEW IF NOT EXISTS v_corroboration AS
  SELECT e.variant_id, e.field_name,
         COUNT(DISTINCT e.source_id) AS corroborating_sources,
         GROUP_CONCAT(DISTINCT e.source_id) AS source_ids
  FROM v_live_evidence e
  WHERE e.decision IN ('accepted','confirmed')
    AND NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='variant' AND q.target_id=e.variant_id
                      AND q.target_field IN (e.field_name,'*'))
  GROUP BY e.variant_id, e.field_name;

-- Required consumer read path: v_effective_variant semantics with quarantined cells masked to NULL.
-- An inherited value is also masked when the base variant's cell is quarantined.
CREATE VIEW IF NOT EXISTS v_variant_canonical_q AS
  SELECT
    v.id,
    v.model_id,
    v.generation_id,
    v.powertrain_id,
    v.name,
    v.full_name,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('transmission','*')) THEN NULL ELSE v.transmission END AS transmission,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('drivetrain','*')) THEN NULL ELSE v.drivetrain END AS drivetrain,
    v.is_discontinued,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('price_ex_showroom','*')) OR (v.price_ex_showroom IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('price_ex_showroom','*'))) THEN NULL ELSE COALESCE(v.price_ex_showroom, bv.price_ex_showroom) END AS price_ex_showroom,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('length_mm','*')) OR (v.length_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('length_mm','*'))) THEN NULL ELSE COALESCE(v.length_mm, bv.length_mm) END AS length_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('width_mm','*')) OR (v.width_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('width_mm','*'))) THEN NULL ELSE COALESCE(v.width_mm, bv.width_mm) END AS width_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('height_mm','*')) OR (v.height_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('height_mm','*'))) THEN NULL ELSE COALESCE(v.height_mm, bv.height_mm) END AS height_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('wheelbase_mm','*')) OR (v.wheelbase_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('wheelbase_mm','*'))) THEN NULL ELSE COALESCE(v.wheelbase_mm, bv.wheelbase_mm) END AS wheelbase_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('ground_clearance_mm','*')) OR (v.ground_clearance_mm IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('ground_clearance_mm','*'))) THEN NULL ELSE COALESCE(v.ground_clearance_mm, bv.ground_clearance_mm) END AS ground_clearance_mm,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('kerb_weight_kg','*')) OR (v.kerb_weight_kg IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('kerb_weight_kg','*'))) THEN NULL ELSE COALESCE(v.kerb_weight_kg, bv.kerb_weight_kg) END AS kerb_weight_kg,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('seating_capacity','*')) OR (v.seating_capacity IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('seating_capacity','*'))) THEN NULL ELSE COALESCE(v.seating_capacity, bv.seating_capacity) END AS seating_capacity,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('boot_space_litres','*')) OR (v.boot_space_litres IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('boot_space_litres','*'))) THEN NULL ELSE COALESCE(v.boot_space_litres, bv.boot_space_litres) END AS boot_space_litres,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('fuel_tank_litres','*')) OR (v.fuel_tank_litres IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('fuel_tank_litres','*'))) THEN NULL ELSE COALESCE(v.fuel_tank_litres, bv.fuel_tank_litres) END AS fuel_tank_litres,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('mileage_arai_kmpl','*')) OR (v.mileage_arai_kmpl IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('mileage_arai_kmpl','*'))) THEN NULL ELSE COALESCE(v.mileage_arai_kmpl, bv.mileage_arai_kmpl) END AS mileage_arai_kmpl,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('mileage_arai_km_per_kg','*')) OR (v.mileage_arai_km_per_kg IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('mileage_arai_km_per_kg','*'))) THEN NULL ELSE COALESCE(v.mileage_arai_km_per_kg, bv.mileage_arai_km_per_kg) END AS mileage_arai_km_per_kg,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('claimed_ev_range_km','*')) OR (v.claimed_ev_range_km IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('claimed_ev_range_km','*'))) THEN NULL ELSE COALESCE(v.claimed_ev_range_km, bv.claimed_ev_range_km) END AS claimed_ev_range_km,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('airbags','*')) OR (v.airbags IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('airbags','*'))) THEN NULL ELSE COALESCE(v.airbags, bv.airbags) END AS airbags,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('abs','*')) OR (v.abs IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('abs','*'))) THEN NULL ELSE COALESCE(v.abs, bv.abs) END AS abs,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('esc','*')) OR (v.esc IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('esc','*'))) THEN NULL ELSE COALESCE(v.esc, bv.esc) END AS esc,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('hill_assist','*')) OR (v.hill_assist IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('hill_assist','*'))) THEN NULL ELSE COALESCE(v.hill_assist, bv.hill_assist) END AS hill_assist,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('tyre_pressure_monitoring_system','*')) OR (v.tyre_pressure_monitoring_system IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('tyre_pressure_monitoring_system','*'))) THEN NULL ELSE COALESCE(v.tyre_pressure_monitoring_system, bv.tyre_pressure_monitoring_system) END AS tyre_pressure_monitoring_system,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_parking_sensors','*')) OR (v.rear_parking_sensors IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_parking_sensors','*'))) THEN NULL ELSE COALESCE(v.rear_parking_sensors, bv.rear_parking_sensors) END AS rear_parking_sensors,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_camera','*')) OR (v.rear_camera IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_camera','*'))) THEN NULL ELSE COALESCE(v.rear_camera, bv.rear_camera) END AS rear_camera,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('camera_360','*')) OR (v.camera_360 IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('camera_360','*'))) THEN NULL ELSE COALESCE(v.camera_360, bv.camera_360) END AS camera_360,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('adas_available','*')) OR (v.adas_available IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('adas_available','*'))) THEN NULL ELSE COALESCE(v.adas_available, bv.adas_available) END AS adas_available,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('adas_tier','*')) OR (v.adas_tier IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('adas_tier','*'))) THEN NULL ELSE COALESCE(v.adas_tier, bv.adas_tier) END AS adas_tier,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('automatic_climate_control','*')) OR (v.automatic_climate_control IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('automatic_climate_control','*'))) THEN NULL ELSE COALESCE(v.automatic_climate_control, bv.automatic_climate_control) END AS automatic_climate_control,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('rear_ac_vents','*')) OR (v.rear_ac_vents IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('rear_ac_vents','*'))) THEN NULL ELSE COALESCE(v.rear_ac_vents, bv.rear_ac_vents) END AS rear_ac_vents,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('sunroof','*')) OR (v.sunroof IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('sunroof','*'))) THEN NULL ELSE COALESCE(v.sunroof, bv.sunroof) END AS sunroof,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('ventilated_front_seats','*')) OR (v.ventilated_front_seats IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('ventilated_front_seats','*'))) THEN NULL ELSE COALESCE(v.ventilated_front_seats, bv.ventilated_front_seats) END AS ventilated_front_seats,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('cruise_control','*')) OR (v.cruise_control IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('cruise_control','*'))) THEN NULL ELSE COALESCE(v.cruise_control, bv.cruise_control) END AS cruise_control,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('paddle_shifters','*')) OR (v.paddle_shifters IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('paddle_shifters','*'))) THEN NULL ELSE COALESCE(v.paddle_shifters, bv.paddle_shifters) END AS paddle_shifters,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('wireless_charging','*')) OR (v.wireless_charging IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('wireless_charging','*'))) THEN NULL ELSE COALESCE(v.wireless_charging, bv.wireless_charging) END AS wireless_charging,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('heads_up_display','*')) OR (v.heads_up_display IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('heads_up_display','*'))) THEN NULL ELSE COALESCE(v.heads_up_display, bv.heads_up_display) END AS heads_up_display,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('drive_modes','*')) OR (v.drive_modes IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('drive_modes','*'))) THEN NULL ELSE COALESCE(v.drive_modes, bv.drive_modes) END AS drive_modes,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('connected_car_features','*')) OR (v.connected_car_features IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('connected_car_features','*'))) THEN NULL ELSE COALESCE(v.connected_car_features, bv.connected_car_features) END AS connected_car_features,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('android_auto','*')) OR (v.android_auto IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('android_auto','*'))) THEN NULL ELSE COALESCE(v.android_auto, bv.android_auto) END AS android_auto,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.id AND q.target_field IN ('apple_carplay','*')) OR (v.apple_carplay IS NULL AND EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='variant' AND q.target_id=v.base_variant_id AND q.target_field IN ('apple_carplay','*'))) THEN NULL ELSE COALESCE(v.apple_carplay, bv.apple_carplay) END AS apple_carplay,
    v.v6_row_index,
    v.created_at,
    v.updated_at,
    v.base_variant_id,
    v.edition_classification
  FROM variant v
  LEFT JOIN variant bv ON bv.id = v.base_variant_id;

-- Canonical 5-value resolution vocabulary as a read-only mapping (stored strings unchanged).
CREATE VIEW IF NOT EXISTS v_observation_status AS
  SELECT so.id AS observation_id, so.source_id, so.resolution_status AS raw_status,
    CASE
      WHEN so.source_id = 7 AND so.id IN (3721, 3722, 3756, 3757) AND so.resolution_status = 'UNRESOLVED' THEN 'no_match'
      WHEN so.resolution_status = 'applied' THEN 'resolved_variant'
      WHEN so.resolution_status = 'resolved' AND so.source_id = 3 THEN 'resolved_variant_unverified'
      WHEN so.resolution_status = 'resolved' THEN 'resolved_variant'
      WHEN so.resolution_status = 'resolved_with_warning' THEN 'resolved_variant_unverified'
      WHEN so.resolution_status IN ('model_level','RESOLVED') THEN 'resolved_model'
      WHEN so.resolution_status IN ('unresolved','unresolvable','UNRESOLVED') THEN 'unresolved'
      WHEN so.resolution_status = 'NO_MATCH' THEN 'no_match'
    END AS canonical_status,
    CASE
      WHEN so.source_id = 7 AND so.id IN (3721, 3722, 3756, 3757) AND so.resolution_status = 'UNRESOLVED'
        THEN 'manufacturer_not_in_kb'   -- Citroen x2, VinFast x2 (owner decision 2026-09-27)
      WHEN so.resolution_status = 'resolved' AND so.source_id = 3 THEN 'v3cars_status_forced'
    END AS status_reason
  FROM source_observation so;

-- Same 5-value vocabulary for safety_test (stored strings unchanged).
CREATE VIEW IF NOT EXISTS v_safety_test_status AS
  SELECT st.id AS safety_test_id, st.source_observation_id, st.resolution_status AS raw_status,
    CASE
      WHEN st.id IN (1, 2, 36, 37) AND st.resolution_status = 'UNRESOLVED' THEN 'no_match'
      WHEN st.resolution_status = 'RESOLVED' THEN 'resolved_model'
      WHEN st.resolution_status = 'UNRESOLVED' THEN 'unresolved'
      WHEN st.resolution_status = 'NO_MATCH' THEN 'no_match'
    END AS canonical_status,
    CASE
      WHEN st.id IN (1, 2, 36, 37) AND st.resolution_status = 'UNRESOLVED'
        THEN 'manufacturer_not_in_kb'   -- Citroen x2, VinFast x2 (owner decision 2026-09-27)
    END AS status_reason
  FROM safety_test st;
