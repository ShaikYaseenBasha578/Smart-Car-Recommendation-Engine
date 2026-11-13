"""CarWale adapter. Data comes from the JSON in <script id="initial-state">.

Brand page  -> current, upcoming and discontinued models.
Model page  -> every version with its id, name, average ex-showroom price, a spec summary and ~33 feature items.
Trim pages are NOT used: CarWale serves a trim's default version whatever version URL is asked for
(this caused the 2026-09 mislinks). Everything here is keyed by versionId taken from the payload itself."""
import html
import json
import re

from . import common as c

NAME = "carwale"
BASE = "https://www.carwale.com"
MAKE_SLUG = {"Maruti Suzuki": "maruti-suzuki", "Tata": "tata", "Hyundai": "hyundai", "Kia": "kia", "MG": "mg",
             "Mahindra": "mahindra", "Nissan": "nissan", "Renault": "renault", "Skoda": "skoda", "Toyota": "toyota",
             "Volkswagen": "volkswagen", "Honda": "honda"}
BODY = {1: "Sedan", 3: "Hatchback", 6: "SUV", 9: "MPV", 4: "Van", 7: "Pickup"}   # ids observed 2026-11-13; others -> None


def state(page):
    m = re.search(r'<script[^>]*id="initial-state"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return None
    try:
        return json.loads(html.unescape(m.group(1)))
    except ValueError:
        return None


def brand_url(make):
    return "%s/%s-cars/" % (BASE, MAKE_SLUG[make])


def model_url(make, masking):
    return "%s/%s-cars/%s/" % (BASE, MAKE_SLUG[make], masking)


def _date(s):
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", s or "")
    return "%s-%s-%s" % (m.group(3), m.group(1), m.group(2)) if m else None


def parse_brand(page, make):
    """[{name, slug, status: current|upcoming|discontinued, min_price, launched, body_style_id, brochure}]"""
    s = state(page)
    if not s or "makePage" not in s:
        return None
    out = []
    mp = s["makePage"]
    for m in mp.get("models") or []:
        st = {2: "current", 1: "upcoming"}.get(m.get("status"), "other")
        out.append({"name": (m.get("modelName") or "").strip(), "slug": m.get("modelMaskingName"), "status": st,
                    "min_price": (m.get("priceOverview") or {}).get("price") or None,
                    "launched": _date(m.get("launchedOn")), "body_style_id": m.get("bodyStyleId"),
                    "is_ev": bool(m.get("isElectricVehicle")), "brochure": m.get("brochurePath") or None,
                    "url": model_url(make, m.get("modelMaskingName"))})
    for m in mp.get("discontinuedModels") or []:
        out.append({"name": (m.get("modelName") or "").strip(), "slug": m.get("modelMaskingName"),
                    "status": "discontinued", "min_price": None, "launched": _date(m.get("launchedOn")),
                    "discontinued_on": _date(m.get("discontinuedOn")), "body_style_id": m.get("bodyStyleId"),
                    "is_ev": bool(m.get("isElectricVehicle")), "brochure": None,
                    "url": model_url(make, m.get("modelMaskingName"))})
    return out


def _items(lst):
    d = {}
    for it in lst or []:
        k = (it.get("itemName") or "").strip()
        if k:
            d[k] = (str(it.get("value") or "").strip(), (it.get("unitType") or "").strip())
    return d


def _map_version(v):
    """KB fields from one version dict. Only what the payload states for this versionId."""
    name = (v.get("versionName") or "").strip()
    sp, ft = _items(v.get("specsSummary")), _items(v.get("featureSpecs"))
    g = lambda d, k: d.get(k, ("", ""))[0]
    f = {}
    fuel = c.fuel(g(sp, "Fuel Type"), name)
    f["fuel_type"] = fuel
    f["transmission"] = c.transmission(g(sp, "Transmission Type"), name, fuel) if g(sp, "Transmission Type") else None
    dt = (g(sp, "Drivetrain") or g(ft, "Drivetrain")).upper()
    f["drivetrain"] = dt if dt in ("FWD", "RWD", "AWD", "4WD") else None
    f["engine_cc"] = c.num(g(sp, "Displacement")) if fuel != "Electric" else None
    f["power_bhp"] = c.num(g(sp, "Max Engine Power")) or c.num(g(sp, "Max Motor Power"))
    f["torque_nm"] = c.num(g(sp, "Max Engine Torque")) or c.num(g(sp, "Max Motor Torque"))
    f["seating_capacity"] = c.num(g(sp, "Seating Capacity") or g(ft, "Seating Capacity"))
    mil, unit = sp.get("Mileage (ARAI)", ("", ""))
    if mil and fuel not in ("Electric", None):
        if fuel == "CNG" or "kg" in unit.lower():
            f["mileage_arai_km_per_kg"] = c.num(mil)
        elif "kmpl" in unit.lower() or "km/l" in unit.lower():
            f["mileage_arai_kmpl"] = c.num(mil)
    rng = g(sp, "Driving Range") or g(sp, "Range")
    if fuel == "Electric" and rng:
        f["claimed_ev_range_km"] = c.num(rng)
    f["airbags"] = c.num(g(ft, "Airbags"))
    f["hill_assist"] = c.yes_no(g(ft, "Hill Hold Control"))
    f["cruise_control"] = c.yes_no(g(ft, "Cruise Control"))
    f["tyre_pressure_monitoring_system"] = c.yes_no(g(ft, "Tyre Pressure Monitoring System"))
    f["sunroof"] = c.yes_no(g(ft, "Sunroof Type"))
    f["ventilated_front_seats"] = c.yes_no(g(ft, "Ventilated Seats"))
    f["wireless_charging"] = c.yes_no(g(ft, "Wireless Charger"))
    f["android_auto"] = c.yes_no(g(ft, "Android Auto"))
    f["apple_carplay"] = c.yes_no(g(ft, "Apple CarPlay"))
    ps = g(ft, "Parking Sensors").lower()
    f["rear_parking_sensors"] = None if not ps else (1 if "rear" in ps else 0)
    pa = g(ft, "Parking Assist").lower()
    if pa:
        f["camera_360"] = 1 if "360" in pa else 0
        f["rear_camera"] = 1 if ("360" in pa or "camera" in pa) else 0
    ac = g(ft, "Air Conditioner Control").lower()
    if ac:
        f["automatic_climate_control"] = 1 if "auto" in ac or "climate" in ac else 0
    f["rear_ac_vents"] = c.yes_no(g(ft, "Rear AC Vents"))
    price = (v.get("priceOverview") or {})
    p = price.get("averageExShowRoomPrice") or price.get("exShowRoomPrice") or None
    f["price_ex_showroom"] = p if p and "ex-showroom" in (price.get("priceLabel") or "ex-showroom").lower() else (
        price.get("averageExShowRoomPrice") or None)
    return {k: v2 for k, v2 in f.items() if v2 is not None}


def parse_model(page):
    """{name, launched, replaced_launched, versions: [{id, name, status, fields{}, raw{}}]} or None."""
    s = state(page)
    if not s or "modelPage" not in s:
        return None
    mp = s["modelPage"]
    md = mp.get("modelDetails") or {}
    rep = mp.get("replacedModelDetails") or {}
    vers = []
    for v in mp.get("versions") or []:
        vers.append({"id": v.get("versionId"), "name": (v.get("versionName") or "").strip(),
                     "status": {2: "current", 1: "upcoming"}.get(v.get("status"), "other"),
                     "special": bool(v.get("isSpecialVersion")), "launched": _date(v.get("launchedOn")),
                     "fields": _map_version(v),
                     "raw": {"versionId": v.get("versionId"), "versionName": v.get("versionName"),
                             "price": (v.get("priceOverview") or {}).get("averageExShowRoomPrice"),
                             "specsSummary": {k: " ".join(x).strip() for k, x in _items(v.get("specsSummary")).items()},
                             "featureSpecs": {k: x[0] for k, x in _items(v.get("featureSpecs")).items()}}})
    return {"name": (md.get("modelName") or "").strip(), "make": md.get("makeName"),
            "status": {2: "current", 1: "upcoming"}.get(md.get("status"), "other"),
            "launched": _date(md.get("launchedOn")), "body_style_id": md.get("bodyStyleId"),
            "brochure": md.get("brochurePath") or None,
            "replaced_launched": _date(rep.get("launchedOn")), "replaced_discontinued": _date(rep.get("discontinuedOn")),
            "versions": vers}
