"""CarDekho adapter. Data comes from the `window.__INITIAL_STATE__ = {...}` object.

Brand page   -> current, upcoming and expired models.
Model page   -> variant list with URL, fuel and ex-showroom price.
Variant page -> full specification and feature tables for exactly that variant (checked against its own title)."""
import html
import json
import re

from . import common as c

NAME = "cardekho"
BASE = "https://www.cardekho.com"
MAKE_SLUG = {"Maruti Suzuki": "Maruti", "Tata": "Tata", "Hyundai": "Hyundai", "Kia": "Kia", "MG": "MG",
             "Mahindra": "Mahindra", "Nissan": "Nissan", "Renault": "Renault", "Skoda": "Skoda", "Toyota": "Toyota",
             "Volkswagen": "Volkswagen", "Honda": "Honda"}
BODY = {"sport utilities": "SUV", "hatchback": "Hatchback", "sedans": "Sedan", "muv": "MPV", "minivans": "Van",
        "pickup trucks": "Pickup"}


def state(page):
    i = page.find("window.__INITIAL_STATE__")
    if i < 0:
        return None
    j = page.find("{", i)
    try:
        return json.JSONDecoder().raw_decode(page[j:])[0]
    except ValueError:
        return None


def brand_url(make):
    return "%s/cars/%s" % (BASE, MAKE_SLUG[make])


def _price_lakh(s):
    n = c.num(s)
    if n is None:
        return None
    return int(round(n * (10000000 if "cr" in str(s).lower() else 100000)))


def parse_brand(page, make):
    s = state(page)
    if not s or "items" not in s:
        return None
    out = []
    for m in s.get("items") or []:
        out.append({"name": (m.get("name") or "").strip(), "slug": m.get("slug"), "status": "current",
                    "min_price": m.get("minComparePrice") or _price_lakh(m.get("minPrice")),
                    "body_type": BODY.get((m.get("vehicleType") or "").strip().lower()),
                    "vehicle_type": m.get("vehicleType"), "url": BASE + (m.get("modelUrl") or "")})
    for m in ((s.get("upcomingCars") or {}).get("items") or []):
        out.append({"name": (m.get("name") or "").strip(), "slug": m.get("slug"), "status": "upcoming",
                    "min_price": None, "body_type": None, "url": BASE + (m.get("modelUrl") or "")})
    for m in ((s.get("ExpiredCars") or {}).get("list") or []):
        nm = (m.get("text") or "").strip()
        if nm.lower().startswith(make.lower().split()[0].lower() + " "):
            nm = nm[len(make.split()[0]) + 1:]
        out.append({"name": nm, "slug": None, "status": "discontinued", "min_price": None, "body_type": None,
                    "url": BASE + (m.get("link") or "")})
    return out


def parse_model(page):
    """{name, variants: [{name, short, url, fuel, price, status}]} or None."""
    s = state(page)
    if not s or "variantTable" not in s:
        return None
    out = []
    for v in (s["variantTable"].get("variantList") or []):
        out.append({"name": (v.get("title") or v.get("name") or "").strip(),
                    "short": (v.get("variantShortName") or "").strip(), "url": BASE + (v.get("url") or ""),
                    "fuel": c.fuel(v.get("fuelName")), "price": v.get("exShowRoomPrice") or None,
                    "sub": v.get("subText") or "", "status": (v.get("variantStatus") or "").upper()})
    return {"name": ((s.get("overView") or {}).get("name") or "").strip(), "variants": out}


def _tables(s):
    d = {}
    st = s.get("specsTechnicalJson") or {}
    for sec in ("specification", "featured"):
        for g in st.get(sec) or []:
            for it in g.get("items") or []:
                k = html.unescape((it.get("text") or "").strip())
                if k and k not in d:
                    d[k] = html.unescape(str(it.get("value") or "").strip())
    return d


def parse_variant(page):
    """{name, fields{}, raw{}} for the variant the page itself says it shows, or None."""
    s = state(page)
    if not s or "specsTechnicalJson" not in s:
        return None
    name = s.get("selectedVariant")
    if isinstance(name, dict):
        name = name.get("name")
    name = (name or (s.get("overView") or {}).get("name") or "").strip()
    t = _tables(s)
    g = lambda k: t.get(k, "")
    f = {}
    fuel = c.fuel(g("Fuel Type"), name)
    f["fuel_type"] = fuel
    f["transmission"] = c.transmission(g("Transmission Type"), name, fuel) if g("Transmission Type") else None
    dt = g("Drive Type").upper().replace("2WD", "")
    f["drivetrain"] = dt if dt in ("FWD", "RWD", "AWD", "4WD") else None
    if fuel != "Electric":
        f["engine_cc"] = c.num(g("Displacement"))
    f["power_bhp"] = c.num(g("Max Power")) if "bhp" in g("Max Power").lower() else None
    f["torque_nm"] = c.num(g("Max Torque")) if "nm" in g("Max Torque").lower() else None
    for kb, key in (("length_mm", "Length"), ("width_mm", "Width"), ("height_mm", "Height"), ("wheelbase_mm", "Wheel Base"),
                    ("kerb_weight_kg", "Kerb Weight")):
        f[kb] = c.num(g(key))
    f["ground_clearance_mm"] = c.num(g("Ground Clearance Unladen") or g("Ground Clearance (Unladen)"))
    f["boot_space_litres"] = c.num(g("Boot Space"))
    f["seating_capacity"] = c.num(g("Seating Capacity"))
    tank = g("Petrol Fuel Tank Capacity") or g("Diesel Fuel Tank Capacity") or g("Fuel Tank Capacity")
    f["fuel_tank_litres"] = c.num(tank) if tank else None
    for key, kb in (("Petrol Mileage ARAI", "mileage_arai_kmpl"), ("Diesel Mileage ARAI", "mileage_arai_kmpl"),
                    ("CNG Mileage ARAI", "mileage_arai_km_per_kg")):
        if g(key) and fuel != "Electric":
            if kb == "mileage_arai_km_per_kg" and fuel != "CNG":
                continue
            if kb == "mileage_arai_kmpl" and fuel == "CNG":
                continue
            f[kb] = c.num(g(key))
    if fuel == "Electric" and g("Range"):
        f["claimed_ev_range_km"] = c.num(g("Range"))
    f["airbags"] = c.num(g("No. of Airbags"))
    for key, kb in (("Anti-lock Braking System (ABS)", "abs"), ("Electronic Stability Control (ESC)", "esc"),
                    ("Hill Assist", "hill_assist"), ("Tyre Pressure Monitoring System (TPMS)", "tyre_pressure_monitoring_system"),
                    ("Rear Camera", "rear_camera"), ("360 View Camera", "camera_360"),
                    ("Automatic Climate Control", "automatic_climate_control"), ("Rear AC Vents", "rear_ac_vents"),
                    ("Sunroof", "sunroof"), ("Ventilated Seats", "ventilated_front_seats"),
                    ("Cruise Control", "cruise_control"), ("Paddle Shifters", "paddle_shifters"),
                    ("Wireless Phone Charging", "wireless_charging"), ("Heads-Up Display (HUD)", "heads_up_display"),
                    ("Android Auto", "android_auto"), ("Apple CarPlay", "apple_carplay")):
        f[kb] = c.yes_no(g(key)) if key in t else None
    if f.get("camera_360") == 1:
        f["rear_camera"] = 1
    ps = g("Parking Sensors").lower()
    if "Parking Sensors" in t and ps:
        f["rear_parking_sensors"] = 0 if ps in ("no", "not available") else (1 if "rear" in ps else 0)
    return {"name": name, "fields": {k: v for k, v in f.items() if v is not None}, "raw": t}
