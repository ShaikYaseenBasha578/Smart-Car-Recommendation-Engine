"""KB field registry. One row per value the pipeline may write: where it lives, its type and its audit group."""

# name: (table, kind, group)   kind: num | int | bool | cat
FIELDS = {
    "price_ex_showroom": ("variant", "int", "price"),
    "fuel_type": ("powertrain", "cat", "engine"),
    "engine_cc": ("powertrain", "int", "engine"),
    "power_bhp": ("powertrain", "num", "engine"),
    "torque_nm": ("powertrain", "num", "engine"),
    "transmission": ("variant", "cat", "drivetrain"),
    "drivetrain": ("variant", "cat", "drivetrain"),
    "length_mm": ("variant", "int", "dimensions"),
    "width_mm": ("variant", "int", "dimensions"),
    "height_mm": ("variant", "int", "dimensions"),
    "wheelbase_mm": ("variant", "int", "dimensions"),
    "ground_clearance_mm": ("variant", "int", "dimensions"),
    "kerb_weight_kg": ("variant", "int", "dimensions"),
    "seating_capacity": ("variant", "int", "capacity"),
    "boot_space_litres": ("variant", "num", "capacity"),
    "fuel_tank_litres": ("variant", "num", "capacity"),
    "mileage_arai_kmpl": ("variant", "num", "efficiency"),
    "mileage_arai_km_per_kg": ("variant", "num", "efficiency"),
    "claimed_ev_range_km": ("variant", "num", "efficiency"),
    "airbags": ("variant", "int", "safety"),
    "abs": ("variant", "bool", "safety"),
    "esc": ("variant", "bool", "safety"),
    "hill_assist": ("variant", "bool", "safety"),
    "tyre_pressure_monitoring_system": ("variant", "bool", "safety"),
    "rear_parking_sensors": ("variant", "bool", "safety"),
    "rear_camera": ("variant", "bool", "safety"),
    "camera_360": ("variant", "bool", "safety"),
    "adas_available": ("variant", "bool", "safety"),
    "automatic_climate_control": ("variant", "bool", "comfort"),
    "rear_ac_vents": ("variant", "bool", "comfort"),
    "sunroof": ("variant", "bool", "comfort"),
    "ventilated_front_seats": ("variant", "bool", "comfort"),
    "cruise_control": ("variant", "bool", "comfort"),
    "paddle_shifters": ("variant", "bool", "comfort"),
    "wireless_charging": ("variant", "bool", "comfort"),
    "heads_up_display": ("variant", "bool", "comfort"),
    "drive_modes": ("variant", "int", "comfort"),
    "connected_car_features": ("variant", "bool", "comfort"),
    "android_auto": ("variant", "bool", "comfort"),
    "apple_carplay": ("variant", "bool", "comfort"),
}
GROUPS = ["price", "engine", "drivetrain", "dimensions", "capacity", "efficiency", "safety", "comfort"]
VARIANT_FIELDS = [f for f, v in FIELDS.items() if v[0] == "variant"]
POWERTRAIN_FIELDS = [f for f, v in FIELDS.items() if v[0] == "powertrain"]

TRANSMISSIONS = {"Manual", "CVT", "Torque Converter", "DCT", "AMT", "Automatic", "iMT", "e-CVT"}
DRIVETRAINS = {"FWD", "RWD", "4WD", "AWD"}
FUELS = {"Diesel", "Petrol", "CNG", "Electric", "Flex Fuel", "Petrol Hybrid", "Diesel Mild Hybrid"}
BODY_TYPES = {"Hatchback", "MPV", "Pickup", "SUV", "Sedan", "Van"}

# plausible ranges: a value outside is rejected by the schema gate (never written)
RANGES = {
    "price_ex_showroom": (200000, 20000000), "engine_cc": (600, 6000), "power_bhp": (20, 800), "torque_nm": (40, 1200),
    "length_mm": (2500, 6000), "width_mm": (1300, 2300), "height_mm": (1200, 2300), "wheelbase_mm": (1800, 3600),
    "ground_clearance_mm": (90, 320), "kerb_weight_kg": (600, 3500), "seating_capacity": (2, 10),
    "boot_space_litres": (50, 2500), "fuel_tank_litres": (15, 120), "mileage_arai_kmpl": (5, 40),
    "mileage_arai_km_per_kg": (10, 45), "claimed_ev_range_km": (100, 1000), "airbags": (0, 12), "drive_modes": (0, 9),
}

DEFINITIONS = {   # short, source-neutral definitions given to the verifier
    "price_ex_showroom": "ex-showroom price of this exact variant, in rupees",
    "fuel_type": "fuel: Petrol, Diesel, CNG, Electric, Petrol Hybrid (strong hybrid), Diesel Mild Hybrid, Flex Fuel. A petrol mild hybrid counts as Petrol",
    "engine_cc": "engine displacement in cc",
    "power_bhp": "maximum power in bhp",
    "torque_nm": "maximum torque in Nm",
    "transmission": "gearbox type: Manual, AMT, CVT, DCT, Torque Converter, iMT, e-CVT, or Automatic (EV single-speed or automatic of unstated type)",
    "drivetrain": "driven wheels: FWD, RWD, AWD or 4WD",
    "length_mm": "overall length in mm", "width_mm": "overall width in mm", "height_mm": "overall height in mm",
    "wheelbase_mm": "wheelbase in mm", "ground_clearance_mm": "ground clearance in mm", "kerb_weight_kg": "kerb weight in kg",
    "seating_capacity": "number of seats", "boot_space_litres": "boot space in litres",
    "fuel_tank_litres": "fuel tank capacity in litres (not CNG cylinder water capacity)",
    "mileage_arai_kmpl": "ARAI-certified mileage in km/l", "mileage_arai_km_per_kg": "ARAI-certified CNG mileage in km/kg",
    "claimed_ev_range_km": "claimed/certified electric driving range in km",
    "airbags": "number of airbags", "abs": "anti-lock braking system fitted (1) or not (0)",
    "esc": "electronic stability control/program (ESC/ESP) fitted (1) or not (0)",
    "hill_assist": "hill hold / hill start assist fitted (1) or not (0)",
    "tyre_pressure_monitoring_system": "tyre pressure monitoring (direct or indirect) fitted (1) or not (0)",
    "rear_parking_sensors": "rear parking sensors fitted (1) or not (0)",
    "rear_camera": "rear/reverse parking camera fitted (1) or not (0); a 360-degree camera includes a rear camera",
    "camera_360": "360-degree / surround-view camera fitted (1) or not (0)",
    "adas_available": "any ADAS driver-assistance suite fitted (1) or not (0)",
    "automatic_climate_control": "automatic climate control fitted (1); manual air conditioning is 0",
    "rear_ac_vents": "rear AC vents fitted (1) or not (0)",
    "sunroof": "any sunroof (single-pane or panoramic) fitted (1) or not (0)",
    "ventilated_front_seats": "ventilated/cooled front seats fitted (1) or not (0)",
    "cruise_control": "any cruise control (plain or adaptive) fitted (1) or not (0)",
    "paddle_shifters": "steering-mounted paddle shifters fitted (1) or not (0)",
    "wireless_charging": "wireless phone charger fitted (1) or not (0); wireless Android Auto/CarPlay does not count",
    "heads_up_display": "head-up display fitted (1) or not (0)",
    "drive_modes": "number of selectable drive modes (0 if none)",
    "connected_car_features": "connected-car telematics/app features fitted (1) or not (0)",
    "android_auto": "Android Auto (wired or wireless) supported (1) or not (0)",
    "apple_carplay": "Apple CarPlay (wired or wireless) supported (1) or not (0)",
}


def norm(field, value):
    """Canonical python value for a field, or None. Booleans are 0/1 ints."""
    if value is None or value == "":
        return None
    kind = FIELDS[field][1]
    if kind == "bool":
        s = str(value).strip().lower()
        if s in ("1", "1.0", "true", "yes"):
            return 1
        if s in ("0", "0.0", "false", "no"):
            return 0
        return None
    if kind == "int":
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None
    if kind == "num":
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None
    return str(value).strip()


def same(field, a, b):
    a, b = norm(field, a), norm(field, b)
    if a is None or b is None:
        return a is b
    return a == b


def in_range(field, value):
    v = norm(field, value)
    if v is None:
        return True
    if field in RANGES:
        lo, hi = RANGES[field]
        return lo <= v <= hi
    if field == "transmission":
        return v in TRANSMISSIONS
    if field == "drivetrain":
        return v in DRIVETRAINS
    if field == "fuel_type":
        return v in FUELS
    if FIELDS[field][1] == "bool":
        return v in (0, 1)
    return True
