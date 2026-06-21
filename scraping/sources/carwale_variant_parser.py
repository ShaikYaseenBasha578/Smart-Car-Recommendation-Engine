"""Parse one saved CarWale variant HTML file into the canonical schema."""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from scraping.schemas.new_car_schema import (
    NEW_CAR_COLUMNS,
    calculate_field_completeness,
    empty_car_record,
    validate_schema_columns,
)


OUTPUT_PATH = Path("scraping/outputs/carwale_single_variant_record.json")

YES_VALUES = {"yes", "available", "true", "standard", "present"}
NO_VALUES = {"no", "not available", "false", "none", "not offered"}


def extract_balanced_json(text: str, start_index: int) -> str | None:
    opening = text[start_index]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False

    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None


def extract_initial_state(html_text: str) -> dict | None:
    """Locate and parse window.__INITIAL_STATE__ from CarWale HTML."""
    marker_index = html_text.find("window.__INITIAL_STATE__")
    if marker_index == -1:
        return None

    equals_index = html_text.find("=", marker_index)
    if equals_index == -1:
        return None

    object_index = html_text.find("{", equals_index)
    if object_index == -1:
        return None

    payload = extract_balanced_json(html_text, object_index)
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def extract_ld_json(soup: BeautifulSoup) -> list[Any]:
    """Parse all valid application/ld+json script blocks."""
    objects = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text("", strip=False)
        if not text.strip():
            continue
        try:
            objects.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return objects


def normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def flatten_spec_feature_items(trim_page: dict) -> list[dict]:
    items: list[dict] = []

    for category in trim_page.get("specsFeaturesMaster") or []:
        category_name = category.get("name")
        for subcategory in category.get("subCategories") or []:
            subcategory_name = subcategory.get("name")
            for item in subcategory.get("items") or []:
                if isinstance(item, dict):
                    copied = dict(item)
                    copied["_category"] = category_name
                    copied["_subcategory"] = subcategory_name
                    items.append(copied)

    version_detail = trim_page.get("versionDetail") or {}
    for key in ("specsSummary", "featureSpecs"):
        for item in version_detail.get(key) or []:
            if isinstance(item, dict):
                copied = dict(item)
                copied["_category"] = copied.get("_category") or "versionDetail"
                copied["_subcategory"] = copied.get("_subcategory") or key
                items.append(copied)

    return items


def item_value(item: dict) -> str | None:
    value = item.get("value")
    if value not in (None, ""):
        return str(value).strip()

    rendered = item.get("renderedTemplates") or {}
    if isinstance(rendered, dict):
        for rendered_value in rendered.values():
            if rendered_value not in (None, ""):
                return str(rendered_value).strip()

    return None


def find_label_value(items: list[dict], candidate_labels: list[str] | tuple[str, ...]) -> str | None:
    """Search specs/features case-insensitively and support label variations."""
    normalized_candidates = [normalize_label(label) for label in candidate_labels]

    for item in items:
        item_name = normalize_label(str(item.get("itemName") or ""))
        for candidate in normalized_candidates:
            if item_name == candidate:
                return item_value(item)

    for item in items:
        item_name = normalize_label(str(item.get("itemName") or ""))
        rendered_labels = []
        rendered = item.get("renderedTemplates") or {}
        if isinstance(rendered, dict):
            rendered_labels = [normalize_label(str(value)) for value in rendered.values()]

        for candidate in normalized_candidates:
            if candidate in item_name:
                return item_value(item)
            if any(candidate in rendered_label for rendered_label in rendered_labels):
                return item_value(item)

    return None


def normalize_price(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).replace(",", "").strip()
    number_match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not number_match:
        return None

    number = float(number_match.group(1))
    lowered = text.lower()
    if "crore" in lowered:
        number *= 10_000_000
    elif "lakh" in lowered or "lac" in lowered:
        number *= 100_000

    return int(round(number))


def first_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def first_int(value: Any) -> int | None:
    number = first_number(value)
    return int(number) if number is not None else None


def normalize_engine_cc(value: Any) -> int | None:
    """Parse displacement only from explicit cc/capacity text."""
    if value in (None, ""):
        return None
    text = str(value).replace(",", " ").strip()
    lowered = text.lower()
    if any(unit in lowered for unit in ("bhp", "kw", "nm", "rpm", "ps")):
        return None
    if not re.search(r"\b(cc|cubic\s*centimet|displacement|engine\s*capacity)\b", lowered):
        return None
    match = re.search(r"(\d{3,4}(?:\.\d+)?)\s*(?:cc|cubic\s*centimet)", lowered)
    if not match:
        match = re.search(r"(\d{3,4}(?:\.\d+)?)", lowered)
    if not match:
        return None
    value_int = int(float(match.group(1)))
    if value_int < 600 or value_int > 6000:
        return None
    return value_int


def normalize_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value

    lowered = re.sub(r"\s+", " ", str(value).strip().lower())
    if lowered in YES_VALUES:
        return True
    if lowered in NO_VALUES or lowered.endswith("-no"):
        return False
    if lowered.startswith("no "):
        return False
    if lowered.startswith("not available"):
        return False
    if lowered.startswith("yes "):
        return True
    return None


def bool_from_label(items: list[dict], labels: list[str] | tuple[str, ...]) -> bool | None:
    value = find_label_value(items, labels)
    parsed = normalize_bool(value)
    if parsed is not None:
        return parsed
    if value:
        return True
    return None


def normalize_transmission(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    lowered = text.lower()
    if "manual" in lowered and "automatic" not in lowered:
        return "Manual"
    if "automatic" in lowered or "amt" in lowered or "dct" in lowered or "cvt" in lowered:
        return text
    return text


def gearbox_count(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"(\d+)\s*(?:speed|gears?|gearbox)", str(value), re.IGNORECASE)
    return int(match.group(1)) if match else None


def normalize_power_bhp(value: Any) -> float | None:
    return first_number(value)


def normalize_torque_nm(value: Any) -> float | None:
    return first_number(value)


def parse_dimensions(value: Any) -> tuple[int | None, int | None, int | None]:
    if value in (None, ""):
        return None, None, None
    numbers = re.findall(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    parsed = [int(float(number)) for number in numbers[:3]]
    while len(parsed) < 3:
        parsed.append(None)
    return parsed[0], parsed[1], parsed[2]


def parse_warranty(value: Any) -> tuple[int | None, int | None]:
    if value in (None, ""):
        return None, None
    text = str(value).replace(",", "")
    years = None
    kms = None

    year_match = re.search(r"(\d+)\s*years?", text, re.IGNORECASE)
    if year_match:
        years = int(year_match.group(1))

    km_match = re.search(r"(\d+)\s*(?:kms?|kilometers?)", text, re.IGNORECASE)
    if km_match:
        kms = int(km_match.group(1))

    return years, kms


def parse_charging_hours(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).lower()
    hours = 0.0
    matched = False

    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*h(?:rs?|ours?)?", text)
    if hour_match:
        hours += float(hour_match.group(1))
        matched = True

    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*m(?:ins?|inutes?)?", text)
    if minute_match:
        hours += float(minute_match.group(1)) / 60
        matched = True

    return round(hours, 2) if matched else first_number(value)


def parse_charging_minutes(value: Any) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).lower()
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*h(?:rs?|ours?)?", text)
    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*m(?:ins?|inutes?)?", text)
    total = 0
    matched = False

    if hour_match:
        total += int(round(float(hour_match.group(1)) * 60))
        matched = True
    if minute_match:
        total += int(round(float(minute_match.group(1))))
        matched = True

    return total if matched else first_int(value)


def ld_price_currency(ld_objects: list[Any]) -> tuple[int | None, str | None]:
    for obj in ld_objects:
        graph = obj.get("@graph") if isinstance(obj, dict) else None
        candidates = graph if isinstance(graph, list) else [obj]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            offers = candidate.get("offers")
            if isinstance(offers, dict):
                price = normalize_price(offers.get("price"))
                currency = offers.get("priceCurrency")
                if price or currency:
                    return price, currency
    return None, None


def price_from_breakup(trim_page: dict, version_id: Any) -> tuple[int | None, int | None]:
    if version_id in (None, ""):
        return None, None
    breakup = (trim_page.get("trimDetailedPriceBreakup") or {}).get(str(version_id))
    if not breakup:
        return None, None
    first_breakup = breakup[0] if isinstance(breakup, list) and breakup else {}
    if not isinstance(first_breakup, dict):
        return None, None
    return normalize_price(first_breakup.get("exShowRoom")), normalize_price(first_breakup.get("onRoad"))


def html_h1(soup: BeautifulSoup) -> str | None:
    h1 = soup.find("h1")
    return h1.get_text(" ", strip=True) if h1 else None


def set_if_present(record: dict, field: str, value: Any) -> None:
    if value not in (None, ""):
        record[field] = value


def parse_carwale_variant(html_path: str | Path, source_url: str) -> dict:
    html_text = Path(html_path).read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html_text, "html.parser")
    initial_state = extract_initial_state(html_text) or {}
    ld_objects = extract_ld_json(soup)
    trim_page = initial_state.get("trimPage") or {}
    trim_detail = trim_page.get("trimDetail") or {}
    version_detail = trim_page.get("versionDetail") or {}
    items = flatten_spec_feature_items(trim_page)

    record = empty_car_record()
    record["source"] = "CarWale"
    record["source_url"] = source_url
    record["scraped_at"] = datetime.now(timezone.utc).isoformat()
    record["scrape_run_id"] = str(uuid.uuid4())

    make = version_detail.get("makeName") or trim_detail.get("makeName")
    model = version_detail.get("modelName") or trim_detail.get("modelName")
    variant = version_detail.get("versionName") or trim_detail.get("trimName")
    page_title = html_h1(soup)

    set_if_present(record, "make", make)
    set_if_present(record, "model", model)
    set_if_present(record, "variant", variant)
    if make and model and variant:
        record["full_name"] = f"{make} {model} {variant}"
    elif page_title:
        record["full_name"] = page_title

    ex_showroom, on_road = price_from_breakup(trim_page, version_detail.get("versionId"))
    ld_price, currency = ld_price_currency(ld_objects)
    set_if_present(record, "price_ex_showroom", ex_showroom)
    set_if_present(record, "price_on_road", on_road or ld_price)
    set_if_present(record, "currency", currency or "INR")

    engine_value = find_label_value(items, ("Engine Type", "Engine"))
    displacement_value = find_label_value(items, ("Displacement", "Engine Displacement", "Engine Capacity", "Engine (cc)"))
    transmission_value = find_label_value(items, ("Transmission", "Transmission Type"))
    dimensions_value = find_label_value(items, ("Length *Width *Height", "Length Width Height"))
    warranty_value = find_label_value(items, ("Vehicle Warranty",))

    field_map = {
        "fuel_type": ("Fuel Type",),
        "drivetrain": ("Drivetrain",),
        "mileage_arai_kmpl": ("Mileage (ARAI)",),
        "fuel_tank_capacity_litres": ("Fuel Tank Capacity",),
        "claimed_ev_range_km": ("Driving Range", "Range"),
        "wheelbase_mm": ("Wheelbase",),
        "ground_clearance_mm": ("Ground Clearance",),
        "turning_radius_metres": ("Minimum Turning Radius", "Turning Radius"),
        "infotainment_screen_inches": ("Infotainment Screen", "Touchscreen", "Display"),
    }
    for field, labels in field_map.items():
        value = find_label_value(items, labels)
        if field in {"fuel_type", "drivetrain"}:
            set_if_present(record, field, value)
        else:
            set_if_present(record, field, first_number(value))

    record["transmission"] = normalize_transmission(transmission_value)
    record["gearbox_speeds"] = gearbox_count(transmission_value)
    record["engine_cc"] = normalize_engine_cc(displacement_value) if record["fuel_type"] != "Electric" else None
    if engine_value:
        cylinders_match = re.search(r"(\d+)\s*cylinders?", engine_value, re.IGNORECASE)
        if cylinders_match:
            record["cylinders"] = int(cylinders_match.group(1))

    battery_value = find_label_value(items, ("Battery", "Battery Capacity"))
    if record["fuel_type"] == "Electric":
        record["battery_capacity_kwh"] = first_number(battery_value)

    record["turbocharged"] = normalize_bool(find_label_value(items, ("Turbocharger/ Supercharger",)))
    if record["turbocharged"] is None:
        turbo_text = " ".join(str(v) for v in (engine_value, find_label_value(items, ("Engine Type",))) if v)
        if "turbo" in turbo_text.lower():
            record["turbocharged"] = True

    record["power_bhp"] = normalize_power_bhp(find_label_value(items, ("Max Power (bhp@rpm)", "Max Power", "Max Engine Power")))
    record["torque_nm"] = normalize_torque_nm(find_label_value(items, ("Max Torque (Nm@rpm)", "Max Torque", "Max Engine Torque")))

    ac_regular = find_label_value(items, ("AC Regular Charging",))
    ac_fast = find_label_value(items, ("AC Fast Charging",))
    dc_fast = find_label_value(items, ("DC Fast Charging",))
    record["charging_time_ac_hours"] = parse_charging_hours(ac_fast or ac_regular)
    record["charging_time_dc_minutes"] = parse_charging_minutes(dc_fast)

    record["seating_capacity"] = first_int(find_label_value(items, ("Seating Capacity",)))
    length, width, height = parse_dimensions(dimensions_value)
    record["length_mm"] = length
    record["width_mm"] = width
    record["height_mm"] = height
    record["boot_space_litres"] = first_number(find_label_value(items, ("Bootspace", "Boot Space")))

    record["airbags"] = first_int(find_label_value(items, ("Airbags",)))
    ncap_value = find_label_value(items, ("NCAP Rating", "Crash Test Rating"))
    record["crash_test_rating"] = first_number(ncap_value)
    if ncap_value:
        agency_match = re.search(r"\(([^)]+NCAP[^)]*)\)", ncap_value, re.IGNORECASE)
        if agency_match:
            record["crash_test_agency"] = agency_match.group(1)

    boolean_fields = {
        "abs": ("Anti-Lock Braking System (ABS)", "ABS"),
        "ebd": ("Electronic Brake-force Distribution (EBD)", "EBD"),
        "esc": ("Electronic Stability Program (ESP)", "Electronic Stability Control", "ESC"),
        "traction_control": ("Traction Control System (TC/TCS)", "Traction Control"),
        "hill_assist": ("Hill Hold Control", "Hill Assist", "Hill-Start Assist"),
        "hill_descent_control": ("Hill Descent Control",),
        "tyre_pressure_monitoring_system": ("Tyre Pressure Monitoring System", "TPMS"),
        "rear_parking_sensors": ("Parking Sensors", "Rear Parking Sensors"),
        "front_parking_sensors": ("Front Parking Sensors",),
        "rear_camera": ("Rear View Camera", "Driver Rear View Monitor", "Rear Camera"),
        "camera_360": ("360 Degree Camera", "360-degree Camera", "Surround View Monitor", "Parking Assist"),
        "adas_available": ("ADAS",),
        "sunroof": ("Sunroof",),
        "automatic_climate_control": ("Automatic Climate Control", "Air Conditioner"),
        "cruise_control": ("Cruise Control",),
        "ventilated_front_seats": ("Ventilated Seats", "Ventilated Front Seats"),
        "powered_driver_seat": ("Driver Seat Adjustment", "Powered Driver Seat"),
        "powered_front_seats": ("Front Passenger Seat Adjustment", "Powered Front Seats"),
        "rear_ac_vents": ("Rear AC Vents",),
        "keyless_entry": ("Central Locking", "Keyless Entry"),
        "push_button_start": ("Keyless Start/ Button Start", "Push Button Start"),
        "wireless_charging": ("Wireless Charger", "Wireless Charging"),
        "android_auto": ("Android Auto", "Smart Connectivity"),
        "apple_carplay": ("Apple CarPlay", "Smart Connectivity"),
        "connected_car_features": ("Mobile App", "Find My Car", "Geo-fence", "Check Vehicle Status via App"),
    }
    for field, labels in boolean_fields.items():
        value = find_label_value(items, labels)
        parsed = normalize_bool(value)
        if field == "automatic_climate_control" and parsed is None and value:
            parsed = "automatic" in value.lower() or "climate" in value.lower()
        elif field in {"powered_driver_seat", "powered_front_seats"} and parsed is None and value:
            parsed = any(word in value.lower() for word in ("electric", "powered"))
        elif field in {"android_auto", "apple_carplay"} and parsed is None and value:
            lowered = value.lower()
            parsed = ("android auto" in lowered) if field == "android_auto" else ("apple carplay" in lowered)
        elif field == "rear_parking_sensors" and parsed is None and value:
            parsed = "rear" in value.lower()
        elif field == "front_parking_sensors" and parsed is None and value:
            parsed = "front" in value.lower()
        elif field == "camera_360" and parsed is None and value:
            parsed = "360" in value or "surround" in value.lower()
        elif field == "keyless_entry" and parsed is None and value:
            parsed = "keyless" in value.lower()

        if parsed is not None:
            record[field] = parsed

    sunroof_value = find_label_value(items, ("Sunroof",))
    if sunroof_value:
        record["panoramic_sunroof"] = "panoramic" in sunroof_value.lower()

    warranty_years, warranty_km = parse_warranty(warranty_value)
    record["standard_warranty_years"] = warranty_years
    record["standard_warranty_km"] = warranty_km

    record["field_completeness_score"] = calculate_field_completeness(record)
    return {column: record.get(column) for column in NEW_CAR_COLUMNS}


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: python -m scraping.sources.carwale_variant_parser <html_path> <source_url>",
            file=sys.stderr,
        )
        raise SystemExit(2)

    record = parse_carwale_variant(sys.argv[1], sys.argv[2])
    validation = validate_schema_columns(record)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"Saved parsed record to {OUTPUT_PATH}")
    print(f"Missing required columns: {validation['missing_required']}")
    print(f"Field completeness: {record['field_completeness_score']}%")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
