"""
Field-Level Source Authority Matrix.
Returns the authority tier (lower is better, 1 = highest) for a given source and canonical field.
If a source has no authority for a field, returns 99 (lowest/no authority).
"""

# Map source names to canonical strings
SOURCE_ALIASES = {
    '91wheels': '91wheels',
    'v3cars': 'v3cars',
    'carwale': 'carwale',
    'cardekho': 'cardekho',
    'oem': 'oem',
    'autocar_india': 'autocar_india',
    'team_bhp': 'team_bhp',
    'global_ncap': 'gncap',
    'bharat_ncap': 'bncap',
    'overdrive': 'overdrive',
    'evo_india': 'evo_india',
    'v6_migration': 'v6_migration'
}

# The matrix defines the preferred (1), secondary (2), and tertiary (3) sources for each field.
# Any source not explicitly listed gets tier 99.
FIELD_AUTHORITY = {
    # Objective Specifications
    'engine_cc': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'power_bhp': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'torque_nm': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'transmission': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'drivetrain': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'length_mm': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'width_mm': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'height_mm': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'wheelbase_mm': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'ground_clearance_mm': {'oem': 1, '91wheels': 2, 'autocar_india': 3},
    'boot_space_litres': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'kerb_weight_kg': {'oem': 1, 'autocar_india': 2, '91wheels': 3},
    'fuel_tank_litres': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'mileage_arai_kmpl': {'oem': 1, '91wheels': 2, 'carwale': 3},
    'claimed_ev_range_km': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    
    # Variant-Specific Features
    'airbags': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'abs': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'esc': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'hill_assist': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'tyre_pressure_monitoring_system': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'rear_parking_sensors': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'rear_camera': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'camera_360': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'adas_available': {'oem': 1, '91wheels': 2, 'autocar_india': 3},
    'adas_tier': {'oem': 1, '91wheels': 2, 'autocar_india': 3},
    'sunroof': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'automatic_climate_control': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'rear_ac_vents': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'ventilated_front_seats': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'cruise_control': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'paddle_shifters': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'wireless_charging': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'heads_up_display': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'drive_modes': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'connected_car_features': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'android_auto': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    'apple_carplay': {'oem': 1, '91wheels': 2, 'v3cars': 3},
    
    # Experiential (Subjective & Tested)
    'real_world_mileage_kmpl': {'team_bhp': 1, 'autocar_india': 2, 'overdrive': 3},
    '0_100_kmph_tested': {'autocar_india': 1, 'evo_india': 2, 'overdrive': 3},
    
    # Market
    'price_ex_showroom': {'oem': 1, '91wheels': 2, 'carwale': 3}
}

def get_authority_tier(source_name, field_name):
    # Baseline migration gets a flat tier 5 for all fields to allow real sources to overwrite.
    if source_name == 'v6_migration':
        return 5
        
    s = SOURCE_ALIASES.get(source_name, source_name)
    field_tiers = FIELD_AUTHORITY.get(field_name, {})
    return field_tiers.get(s, 99)
