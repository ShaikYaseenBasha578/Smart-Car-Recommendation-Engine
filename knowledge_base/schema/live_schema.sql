-- Live schema of knowledge_base/carrec_kb.db (production)
-- Source: SELECT sql FROM sqlite_master on a /tmp copy; production SHA-1 1e3eb6795452860276eca24e7dd1f52e85e67a93
-- Generated 2026-09-27T00:31:36Z. Authoritative over KB_SCHEMA.sql (stale).
-- Autoindexes (sql IS NULL) are implied by PRIMARY KEY/UNIQUE and omitted.

CREATE TABLE field_provenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL REFERENCES variant(id),
    field_name TEXT NOT NULL,            -- Column name: 'boot_space_litres', etc.
    accepted_value TEXT,                 -- Stringified accepted value
    source_observation_id INTEGER REFERENCES source_observation(id),
    decision TEXT NOT NULL DEFAULT 'accepted',
    -- 'accepted' (this observation provided the canonical value),
    -- 'confirmed' (agrees with existing canonical value),
    -- 'rejected' (disagrees, was overridden),
    -- 'pending' (conflict unresolved)
    decision_reason TEXT,                -- Why: 'v6_migration', 'authority_priority', 'manual', etc.
    decided_at TEXT DEFAULT (datetime('now')),
    UNIQUE(variant_id, field_name, source_observation_id)
);

CREATE TABLE generation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL REFERENCES model(id),
    name TEXT NOT NULL,                  -- 'Gen 1 (V6 Import)', etc.
    start_year INTEGER,
    end_year INTEGER,                    -- NULL = current
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    -- 'unverified' (V6 migration placeholder), 'verified', 'needs_review'
    notes TEXT
);

CREATE TABLE manufacturer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE            -- 'Hyundai', 'Maruti Suzuki', etc.
);

CREATE TABLE model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer_id INTEGER NOT NULL REFERENCES manufacturer(id),
    name TEXT NOT NULL,                  -- 'Creta', 'Fronx', etc.
    body_type TEXT,                      -- 'SUV', 'Hatchback', 'Sedan', etc.
    UNIQUE(manufacturer_id, name)
);

CREATE TABLE powertrain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL REFERENCES model(id),
    fuel_type TEXT NOT NULL,             -- V6 vocabulary: Petrol, Diesel, CNG, Electric,
                                         -- Diesel Mild Hybrid, Petrol Hybrid, Flex Fuel
    engine_cc REAL,                      -- NULL for pure EVs
    power_bhp REAL,                      -- Distinguishes same-displacement tunes
    torque_nm REAL,
    description TEXT,                    -- Human label: '1497cc 113bhp Petrol', etc.
    UNIQUE(model_id, fuel_type, engine_cc, power_bhp)
    -- ponytail: engine_cc+power_bhp is sufficient to distinguish V6 powertrains.
    -- If a future model has two engines with identical cc AND bhp (unlikely),
    -- add a disambiguator column then.
);

CREATE TABLE safety_rating (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL REFERENCES model(id),
    generation_id INTEGER REFERENCES generation(id),
    testing_body TEXT NOT NULL,           -- 'Global NCAP', 'Bharat NCAP'
    adult_stars REAL,
    child_stars REAL,
    test_year INTEGER,
    tested_variant TEXT,                  -- Exact variant string that was tested
    source_url TEXT,
    UNIQUE(model_id, testing_body, test_year)
);

CREATE TABLE safety_test (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id             INTEGER NOT NULL REFERENCES source(id),
    source_observation_id INTEGER REFERENCES source_observation(id),
    tested_vehicle_name   TEXT NOT NULL,
    tested_variant_config TEXT,
    body_type             TEXT,
    crash_test_weight_kg  TEXT,
    year_of_publication   INTEGER,
    test_period           TEXT,
    protocol_version      TEXT,
    aop_score             REAL,
    aop_stars             INTEGER,
    cop_score             REAL,
    cop_stars             INTEGER,
    sat_summary           TEXT,
    factsheet_url         TEXT,
    raw_source_url        TEXT NOT NULL UNIQUE,
    artifact_path         TEXT,
    artifact_checksum     TEXT,
    resolution_status     TEXT NOT NULL,
    applicability_notes   TEXT,
    resolution_justification TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE safety_test_applicability (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    safety_test_id    INTEGER NOT NULL REFERENCES safety_test(id),
    manufacturer_id   INTEGER REFERENCES manufacturer(id),
    model_id          INTEGER REFERENCES model(id),
    generation_id     INTEGER REFERENCES generation(id),
    variant_id        INTEGER REFERENCES variant(id),
    match_confidence  TEXT NOT NULL,
    notes             TEXT,
    UNIQUE(safety_test_id, model_id, match_confidence)
);

CREATE TABLE source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,          -- 'v6_migration', '91wheels', 'v3cars', etc.
    source_type TEXT NOT NULL,          -- 'migration', 'aggregator', 'oem', 'rating_agency', 'review'
    base_url TEXT,
    authority_tier INTEGER NOT NULL DEFAULT 3, -- 1=highest (OEM/NCAP), 2=primary aggregator, 3=secondary
    notes TEXT
);

CREATE TABLE source_observation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES source(id),
    raw_name TEXT NOT NULL,              -- As the source named this variant
    raw_payload TEXT,                     -- JSON blob of all extracted fields
    source_url TEXT,
    observed_at TEXT NOT NULL DEFAULT (datetime('now')),
    extraction_method TEXT,              -- 'v6_migration', 'meta_tag_json', 'html_scrape'
    resolved_variant_id INTEGER REFERENCES variant(id),
    resolution_status TEXT NOT NULL DEFAULT 'pending'
    -- 'pending', 'applied', 'conflict', 'rejected', 'unresolvable'
);

CREATE TABLE sqlite_sequence(name,seq);

CREATE TABLE variant (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL REFERENCES model(id),
    generation_id INTEGER REFERENCES generation(id),
    powertrain_id INTEGER REFERENCES powertrain(id),

    -- Identity
    name TEXT NOT NULL,                  -- V6 'variant' column: 'E Petrol 1.5L Manual'
    full_name TEXT,                      -- V6 'full_name': 'Hyundai Creta E Petrol 1.5L Manual'
    transmission TEXT NOT NULL,          -- V6 vocabulary: Manual, Automatic, CVT, DCT, AMT, iMT,
                                         -- Torque Converter, e-CVT
    drivetrain TEXT DEFAULT 'FWD',       -- FWD, RWD, AWD, 4WD
    is_discontinued INTEGER NOT NULL DEFAULT 0,

    -- Pricing
    price_ex_showroom REAL,              -- In rupees (V6 stores raw rupee value)

    -- Dimensions
    length_mm REAL,
    width_mm REAL,
    height_mm REAL,
    wheelbase_mm REAL,
    ground_clearance_mm REAL,
    kerb_weight_kg REAL,

    -- Capacity
    seating_capacity INTEGER,
    boot_space_litres REAL,
    fuel_tank_litres REAL,

    -- Performance
    mileage_arai_kmpl REAL,
    mileage_arai_km_per_kg REAL,         -- CNG
    claimed_ev_range_km REAL,

    -- Safety
    airbags INTEGER,
    abs INTEGER,                         -- 0/1/NULL
    esc INTEGER,
    hill_assist INTEGER,
    tyre_pressure_monitoring_system INTEGER,
    rear_parking_sensors INTEGER,
    rear_camera INTEGER,
    camera_360 INTEGER,
    adas_available INTEGER,
    adas_tier TEXT,

    -- Comfort & Convenience
    automatic_climate_control INTEGER,
    rear_ac_vents INTEGER,
    sunroof TEXT,                         -- Text value preserved from V6
    ventilated_front_seats INTEGER,
    cruise_control INTEGER,
    paddle_shifters INTEGER,
    wireless_charging INTEGER,
    heads_up_display INTEGER,
    drive_modes INTEGER,
    connected_car_features INTEGER,

    -- Infotainment
    android_auto INTEGER,
    apple_carplay INTEGER,

    -- V6 Migration Reference
    v6_row_index INTEGER,                -- 0-based index in V6 CSV

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')), base_variant_id INTEGER REFERENCES variant(id), edition_classification TEXT,

    UNIQUE(model_id, name, generation_id)
);

CREATE TABLE variant_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL REFERENCES variant(id),
    source_id INTEGER NOT NULL REFERENCES source(id),
    alias_name TEXT NOT NULL,            -- Source's name/slug for this variant
    source_url TEXT,                      -- Full URL on this source
    confidence REAL NOT NULL DEFAULT 0.5,
    match_method TEXT,                   -- 'fuzzy', 'exact', 'manual', 'url_mapping'
    needs_review INTEGER NOT NULL DEFAULT 1,
    is_verified INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source_id, alias_name)
);

CREATE TABLE warranty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer_id INTEGER REFERENCES manufacturer(id),
    model_id INTEGER REFERENCES model(id), -- NULL = manufacturer-wide
    warranty_years REAL,
    warranty_km TEXT,                     -- 'Unlimited' or numeric string
    battery_warranty_years REAL,
    battery_warranty_km TEXT,
    extended_warranty_available INTEGER,
    source TEXT,
    source_url TEXT
);

CREATE INDEX idx_alias_variant ON variant_alias(variant_id);

CREATE INDEX idx_generation_model ON generation(model_id);

CREATE INDEX idx_model_manufacturer ON model(manufacturer_id);

CREATE INDEX idx_observation_source ON source_observation(source_id);

CREATE INDEX idx_observation_url ON source_observation(source_url);

CREATE INDEX idx_observation_variant ON source_observation(resolved_variant_id);

CREATE INDEX idx_powertrain_model ON powertrain(model_id);

CREATE INDEX idx_provenance_field ON field_provenance(field_name);

CREATE INDEX idx_provenance_variant ON field_provenance(variant_id);

CREATE INDEX idx_safety_model ON safety_rating(model_id);

CREATE INDEX idx_variant_generation ON variant(generation_id);

CREATE INDEX idx_variant_model ON variant(model_id);

CREATE INDEX idx_variant_powertrain ON variant(powertrain_id);

CREATE INDEX idx_variant_price ON variant(price_ex_showroom);

CREATE INDEX idx_warranty_mfr ON warranty(manufacturer_id);

CREATE VIEW v_effective_variant AS
    SELECT
        v.id, v.model_id, v.generation_id, v.powertrain_id, v.name, v.full_name, v.transmission, v.drivetrain, v.is_discontinued, COALESCE(v.price_ex_showroom, bv.price_ex_showroom) AS price_ex_showroom, COALESCE(v.length_mm, bv.length_mm) AS length_mm, COALESCE(v.width_mm, bv.width_mm) AS width_mm, COALESCE(v.height_mm, bv.height_mm) AS height_mm, COALESCE(v.wheelbase_mm, bv.wheelbase_mm) AS wheelbase_mm, COALESCE(v.ground_clearance_mm, bv.ground_clearance_mm) AS ground_clearance_mm, COALESCE(v.kerb_weight_kg, bv.kerb_weight_kg) AS kerb_weight_kg, COALESCE(v.seating_capacity, bv.seating_capacity) AS seating_capacity, COALESCE(v.boot_space_litres, bv.boot_space_litres) AS boot_space_litres, COALESCE(v.fuel_tank_litres, bv.fuel_tank_litres) AS fuel_tank_litres, COALESCE(v.mileage_arai_kmpl, bv.mileage_arai_kmpl) AS mileage_arai_kmpl, COALESCE(v.mileage_arai_km_per_kg, bv.mileage_arai_km_per_kg) AS mileage_arai_km_per_kg, COALESCE(v.claimed_ev_range_km, bv.claimed_ev_range_km) AS claimed_ev_range_km, COALESCE(v.airbags, bv.airbags) AS airbags, COALESCE(v.abs, bv.abs) AS abs, COALESCE(v.esc, bv.esc) AS esc, COALESCE(v.hill_assist, bv.hill_assist) AS hill_assist, COALESCE(v.tyre_pressure_monitoring_system, bv.tyre_pressure_monitoring_system) AS tyre_pressure_monitoring_system, COALESCE(v.rear_parking_sensors, bv.rear_parking_sensors) AS rear_parking_sensors, COALESCE(v.rear_camera, bv.rear_camera) AS rear_camera, COALESCE(v.camera_360, bv.camera_360) AS camera_360, COALESCE(v.adas_available, bv.adas_available) AS adas_available, COALESCE(v.adas_tier, bv.adas_tier) AS adas_tier, COALESCE(v.automatic_climate_control, bv.automatic_climate_control) AS automatic_climate_control, COALESCE(v.rear_ac_vents, bv.rear_ac_vents) AS rear_ac_vents, COALESCE(v.sunroof, bv.sunroof) AS sunroof, COALESCE(v.ventilated_front_seats, bv.ventilated_front_seats) AS ventilated_front_seats, COALESCE(v.cruise_control, bv.cruise_control) AS cruise_control, COALESCE(v.paddle_shifters, bv.paddle_shifters) AS paddle_shifters, COALESCE(v.wireless_charging, bv.wireless_charging) AS wireless_charging, COALESCE(v.heads_up_display, bv.heads_up_display) AS heads_up_display, COALESCE(v.drive_modes, bv.drive_modes) AS drive_modes, COALESCE(v.connected_car_features, bv.connected_car_features) AS connected_car_features, COALESCE(v.android_auto, bv.android_auto) AS android_auto, COALESCE(v.apple_carplay, bv.apple_carplay) AS apple_carplay, v.v6_row_index, v.created_at, v.updated_at, v.base_variant_id, v.edition_classification
    FROM variant v
    LEFT JOIN variant bv ON v.base_variant_id = bv.id;

CREATE VIEW v_variant_full AS
SELECT
    v.id AS variant_id,
    mfr.name AS make,
    mdl.name AS model,
    v.name AS variant,
    v.full_name,
    mdl.body_type,
    g.name AS generation,
    g.verification_status AS gen_status,
    pt.fuel_type,
    pt.engine_cc,
    pt.power_bhp,
    pt.torque_nm,
    pt.description AS powertrain_description,
    v.transmission,
    v.drivetrain,
    v.price_ex_showroom,
    v.seating_capacity,
    v.length_mm, v.width_mm, v.height_mm,
    v.wheelbase_mm, v.ground_clearance_mm, v.kerb_weight_kg,
    v.boot_space_litres, v.fuel_tank_litres,
    v.mileage_arai_kmpl, v.mileage_arai_km_per_kg, v.claimed_ev_range_km,
    v.airbags, v.abs, v.esc, v.adas_available, v.adas_tier,
    v.sunroof, v.ventilated_front_seats, v.cruise_control,
    v.android_auto, v.apple_carplay,
    v.connected_car_features,
    v.is_discontinued
FROM variant v
JOIN model mdl ON v.model_id = mdl.id
JOIN manufacturer mfr ON mdl.manufacturer_id = mfr.id
LEFT JOIN generation g ON v.generation_id = g.id
LEFT JOIN powertrain pt ON v.powertrain_id = pt.id;

