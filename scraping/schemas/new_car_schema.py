"""Canonical schema for new-car data used by scrapers."""

# Core vehicle identity fields.
IDENTITY_COLUMNS = (
    "make",
    "model",
    "variant",
    "full_name",
    "model_year",
    "body_type",
    "segment",
    "generation",
    "facelift_status",
    "discontinued",
)

# Price and market location fields.
PRICING_COLUMNS = (
    "price_ex_showroom",
    "price_on_road",
    "price_city",
    "currency",
)

# Engine, motor, gearbox, and performance fields.
POWERTRAIN_COLUMNS = (
    "fuel_type",
    "engine_cc",
    "cylinders",
    "turbocharged",
    "power_bhp",
    "torque_nm",
    "drivetrain",
    "transmission",
    "gearbox_speeds",
    "acceleration_0_100_seconds",
    "top_speed_kmph",
)

# Fuel economy, EV range, and charging fields.
EFFICIENCY_COLUMNS = (
    "mileage_arai_kmpl",
    "mileage_arai_km_per_kg",
    "mileage_real_world_kmpl",
    "fuel_tank_capacity_litres",
    "battery_capacity_kwh",
    "claimed_ev_range_km",
    "charging_time_ac_hours",
    "charging_time_dc_minutes",
)

# Dimensions, capacity, and packaging fields.
PRACTICALITY_COLUMNS = (
    "seating_capacity",
    "boot_space_litres",
    "ground_clearance_mm",
    "length_mm",
    "width_mm",
    "height_mm",
    "wheelbase_mm",
    "kerb_weight_kg",
    "turning_radius_metres",
)

# Safety equipment, driver assistance, and crash-test fields.
SAFETY_COLUMNS = (
    "airbags",
    "abs",
    "ebd",
    "esc",
    "traction_control",
    "hill_assist",
    "hill_descent_control",
    "tyre_pressure_monitoring_system",
    "rear_parking_sensors",
    "front_parking_sensors",
    "rear_camera",
    "camera_360",
    "adas_available",
    "adaptive_cruise_control",
    "lane_keep_assist",
    "lane_departure_warning",
    "automatic_emergency_braking",
    "blind_spot_monitoring",
    "crash_test_rating",
    "crash_test_agency",
)

# Cabin comfort, convenience, and infotainment fields.
COMFORT_COLUMNS = (
    "sunroof",
    "panoramic_sunroof",
    "automatic_climate_control",
    "cruise_control",
    "ventilated_front_seats",
    "powered_driver_seat",
    "powered_front_seats",
    "rear_ac_vents",
    "keyless_entry",
    "push_button_start",
    "wireless_charging",
    "infotainment_screen_inches",
    "android_auto",
    "apple_carplay",
    "connected_car_features",
)

# Ownership, service, and long-term confidence fields.
OWNERSHIP_COLUMNS = (
    "standard_warranty_years",
    "standard_warranty_km",
    "service_interval_km",
    "service_interval_months",
    "estimated_annual_service_cost",
    "reliability_score",
    "resale_value_score",
    "service_network_score",
)

# Source tracking and scrape metadata fields.
PROVENANCE_COLUMNS = (
    "source",
    "source_url",
    "source_last_updated",
    "scraped_at",
    "scrape_run_id",
    "field_completeness_score",
)

NEW_CAR_COLUMNS = (
    IDENTITY_COLUMNS
    + PRICING_COLUMNS
    + POWERTRAIN_COLUMNS
    + EFFICIENCY_COLUMNS
    + PRACTICALITY_COLUMNS
    + SAFETY_COLUMNS
    + COMFORT_COLUMNS
    + OWNERSHIP_COLUMNS
    + PROVENANCE_COLUMNS
)

REQUIRED_COLUMNS = (
    "make",
    "model",
    "variant",
    "full_name",
    "price_ex_showroom",
    "fuel_type",
    "transmission",
    "source",
    "source_url",
    "scraped_at",
)

NUMERIC_COLUMNS = (
    "price_ex_showroom",
    "price_on_road",
    "model_year",
    "engine_cc",
    "cylinders",
    "power_bhp",
    "torque_nm",
    "gearbox_speeds",
    "acceleration_0_100_seconds",
    "top_speed_kmph",
    "mileage_arai_kmpl",
    "mileage_arai_km_per_kg",
    "mileage_real_world_kmpl",
    "fuel_tank_capacity_litres",
    "battery_capacity_kwh",
    "claimed_ev_range_km",
    "charging_time_ac_hours",
    "charging_time_dc_minutes",
    "seating_capacity",
    "boot_space_litres",
    "ground_clearance_mm",
    "length_mm",
    "width_mm",
    "height_mm",
    "wheelbase_mm",
    "kerb_weight_kg",
    "turning_radius_metres",
    "airbags",
    "crash_test_rating",
    "infotainment_screen_inches",
    "standard_warranty_years",
    "standard_warranty_km",
    "service_interval_km",
    "service_interval_months",
    "estimated_annual_service_cost",
    "reliability_score",
    "resale_value_score",
    "service_network_score",
    "field_completeness_score",
)

BOOLEAN_COLUMNS = (
    "discontinued",
    "turbocharged",
    "abs",
    "ebd",
    "esc",
    "traction_control",
    "hill_assist",
    "hill_descent_control",
    "tyre_pressure_monitoring_system",
    "rear_parking_sensors",
    "front_parking_sensors",
    "rear_camera",
    "camera_360",
    "adas_available",
    "adaptive_cruise_control",
    "lane_keep_assist",
    "lane_departure_warning",
    "automatic_emergency_braking",
    "blind_spot_monitoring",
    "sunroof",
    "panoramic_sunroof",
    "automatic_climate_control",
    "cruise_control",
    "ventilated_front_seats",
    "powered_driver_seat",
    "powered_front_seats",
    "rear_ac_vents",
    "keyless_entry",
    "push_button_start",
    "wireless_charging",
    "android_auto",
    "apple_carplay",
    "connected_car_features",
)

CATEGORICAL_COLUMNS = (
    "make",
    "model",
    "variant",
    "body_type",
    "segment",
    "generation",
    "facelift_status",
    "fuel_type",
    "drivetrain",
    "transmission",
    "crash_test_agency",
    "price_city",
    "currency",
    "source",
)


def empty_car_record():
    """Return a blank new-car record with every canonical field present."""
    return {column: None for column in NEW_CAR_COLUMNS}


def validate_schema_columns(record):
    """Return missing required fields and columns outside the canonical schema."""
    record_columns = set(record)
    missing_required = [
        column for column in REQUIRED_COLUMNS if record.get(column) in (None, "")
    ]
    unknown_columns = [
        column for column in record_columns if column not in NEW_CAR_COLUMNS
    ]

    return {
        "missing_required": missing_required,
        "unknown_columns": unknown_columns,
    }


def calculate_field_completeness(record):
    """Return the percentage of canonical fields populated, from 0 to 100."""
    populated_fields = sum(
        1 for column in NEW_CAR_COLUMNS if record.get(column) not in (None, "")
    )
    return round((populated_fields / len(NEW_CAR_COLUMNS)) * 100, 2)
