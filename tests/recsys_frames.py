"""Hand-built catalogue-shaped frames for the recsys tests."""

import numpy as np
import pandas as pd

from services.catalogue import get_catalogue

COLUMNS = list(get_catalogue().columns)
BOOLS = ["abs", "android_auto", "apple_carplay", "cruise_control", "sunroof", "adas_available", "camera_360",
         "ventilated_front_seats", "wireless_charging", "heads_up_display", "esc", "hill_assist", "tpms",
         "rear_parking_sensors", "rear_camera", "auto_climate_control", "rear_ac_vents",
         "connected_car_features", "paddle_shifters"]

BASE = dict(
    make="Acme", model="M0", variant="V", body_type="suv", fuel_raw="Petrol", fuel_type="petrol",
    transmission_raw="Manual", transmission_type="manual", transmission_family="manual",
    price_ex_showroom=1000000.0, seats=5.0, engine_cc=1200.0, power_bhp=100.0, torque_nm=150.0,
    mileage_kmpl=18.0, boot_space_litres=400.0, ground_clearance_mm=180.0, wheelbase_mm=2600.0,
    kerb_weight_kg=1100.0, airbags=6.0,
)


def make_row(variant_id, **kw):
    row = {c: None for c in COLUMNS}
    for c in COLUMNS:
        if c not in BOOLS:
            row[c] = np.nan if c not in ("make", "model", "variant", "full_name", "body_type", "fuel_raw", "fuel_type",
                                         "transmission_raw", "transmission_type", "transmission_family", "drivetrain",
                                         "safety_testing_body", "warranty_km", "battery_warranty_km") else None
    row.update(BASE)
    row.update(kw)
    row["variant_id"] = variant_id
    row["full_name"] = f"{row['make']} {row['model']} {row['variant']}"
    row["unverified_fields"] = kw.get("unverified_fields", frozenset())
    return row


def make_frame(rows):
    """rows: list of dicts of overrides; variant_id = 1..n unless given."""
    data = []
    for i, kw in enumerate(rows, start=1):
        kw = dict(kw)
        vid = kw.pop("variant_id", i)
        data.append(make_row(vid, **kw))
    df = pd.DataFrame(data, columns=COLUMNS)
    for c in BOOLS:
        df[c] = df[c].astype(object)
    df.index = df["variant_id"].to_numpy()
    return df
