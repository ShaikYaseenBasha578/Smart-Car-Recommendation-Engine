"""Build the compact hybrid recommendation working dataset."""

from __future__ import annotations

import math
import pickle
import re
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

RAW_CANDIDATES = (
    ROOT / "datasets/raw/cars_ds_final_2021(2).csv",
    ROOT / "datasets/raw/cars_ds_final_2021.csv",
    ROOT / "datasets/raw/cars_ds_final_2021(3).csv",
)
PROCESSED_PATH = ROOT / "car_recommendation_assets/processed_dataset.csv"
MAPPINGS_PATH = ROOT / "car_recommendation_assets/categorical_mappings.pkl"
AUDITED_PATH = ROOT / "datasets/processed/carrec_canonical_recommendation_ready.csv"
PLAN_PATH = ROOT / "datasets/final/hybrid_refresh_plan.csv"
REFRESH_PATH = ROOT / "datasets/final/carrec_refresh_overrides.csv"
OUTPUT_PATH = ROOT / "datasets/final/carrec_hybrid_working.csv"
REVIEW_PATH = ROOT / "datasets/final/carrec_hybrid_review_queue.csv"
RECOMMENDATION_PATH = ROOT / "datasets/final/carrec_recommendation_dataset.csv"
RECOMMENDATION_JSON_PATH = ROOT / "datasets/final/carrec_recommendation_dataset.json"
VALIDATION_PATH = ROOT / "datasets/final/carrec_recommendation_validation.csv"
SCHEMA_PATH = ROOT / "scraping/schemas/carrec_recommendation_schema.json"
DRIVETRAIN_RECOVERY_REPORT_PATH = ROOT / "datasets/final/carrec_drivetrain_recovery_report.csv"
DRIVETRAIN_RECOVERY_SOURCE = "legacy_2021_drivetrain_recovery"
DRIVETRAIN_RECOVERY_DATE = "2026-06-23"
VERIFIED_DRIVETRAIN_SOURCE = "verified_user_drivetrain_correction"
VERIFIED_DRIVETRAIN_DATE = "2026-06-24"
VERIFIED_GROUND_CLEARANCE_SOURCE = "verified_user_ground_clearance"
VERIFIED_GROUND_CLEARANCE_DATE = "2026-06-24"

COMPACT_COLUMNS = [
    "make",
    "model",
    "variant",
    "full_name",
    "body_type",
    "price_ex_showroom",
    "fuel_type",
    "transmission",
    "engine_cc",
    "power_bhp",
    "torque_nm",
    "drivetrain",
    "mileage_arai_kmpl",
    "mileage_arai_km_per_kg",
    "claimed_ev_range_km",
    "seating_capacity",
    "boot_space_litres",
    "ground_clearance_mm",
    "airbags",
    "abs",
    "esc",
    "hill_assist",
    "tyre_pressure_monitoring_system",
    "rear_parking_sensors",
    "rear_camera",
    "camera_360",
    "automatic_climate_control",
    "rear_ac_vents",
    "android_auto",
    "apple_carplay",
    "sunroof",
    "ventilated_front_seats",
    "connected_car_features",
    "adas_available",
    "source",
    "source_last_updated",
]

CORE_FIELDS = [
    "make",
    "model",
    "variant",
    "price_ex_showroom",
    "body_type",
    "fuel_type",
    "transmission",
]

REQUIRED_SCHEMA_FIELDS = [
    "make",
    "model",
    "variant",
    "full_name",
    "body_type",
    "price_ex_showroom",
    "fuel_type",
    "transmission",
    "seating_capacity",
    "source",
]

NUMERIC_COLUMNS = [
    "price_ex_showroom",
    "engine_cc",
    "power_bhp",
    "torque_nm",
    "mileage_arai_kmpl",
    "mileage_arai_km_per_kg",
    "claimed_ev_range_km",
    "seating_capacity",
    "boot_space_litres",
    "ground_clearance_mm",
    "airbags",
]

AUDITED_MODELS = {
    ("hyundai", "creta"),
    ("mahindra", "xuv 3xo"),
    ("maruti suzuki", "swift"),
    ("mg", "windsor ev"),
    ("tata", "nexon"),
}

BOOLEAN_FEATURE_COLUMNS = (
    "abs",
    "esc",
    "hill_assist",
    "tyre_pressure_monitoring_system",
    "rear_parking_sensors",
    "rear_camera",
    "camera_360",
    "automatic_climate_control",
    "rear_ac_vents",
    "android_auto",
    "apple_carplay",
    "sunroof",
    "ventilated_front_seats",
    "connected_car_features",
    "adas_available",
)

LEGACY_TO_AUDITED = {
    ("hyundai", "creta"),
    ("mahindra", "xuv300"),
    ("maruti suzuki", "swift"),
    ("mg", "windsor ev"),
    ("tata", "nexon"),
}

DRIVETRAIN_PROTECTED_MODEL_UNIFORM = {
    ("toyota", "fortuner"),
    ("mahindra", "scorpio n scorpio classic"),
    ("mahindra", "xuv 3xo"),
    ("mahindra", "xuv 7xo"),
    ("tata", "harrier"),
    ("tata", "nexon ev"),
    ("mg", "windsor ev"),
}

VERIFIED_DRIVETRAIN_MODELS = {
    ("mahindra", "xuv 3xo"): "FWD",
    ("tata", "nexon ev"): "FWD",
    ("mg", "windsor ev"): "FWD",
    ("maruti suzuki", "eeco"): "RWD",
}

VERIFIED_GROUND_CLEARANCE_MODELS = {
    ("hyundai", "creta"): 190,
    ("mahindra", "bolero"): 180,
    ("mahindra", "xuv 3xo"): 201,
    ("maruti suzuki", "swift"): 163,
    ("maruti suzuki", "dzire"): 163,
    ("mg", "windsor ev"): 186,
    ("tata", "nexon"): 208,
    ("tata", "nexon ev"): 205,
    ("maruti suzuki", "brezza"): 198,
    ("hyundai", "venue"): 195,
    ("kia", "seltos"): 190,
    ("maruti suzuki", "ertiga"): 185,
    ("maruti suzuki", "xl6"): 180,
    ("maruti suzuki", "wagonr"): 170,
    ("maruti suzuki", "eeco"): 160,
    ("hyundai", "verna"): 165,
    ("hyundai", "grand i10 nios"): 165,
    ("maruti suzuki", "baleno"): 170,
    ("hyundai", "aura"): 165,
    ("honda", "amaze"): 172,
    ("honda", "city"): 165,
    ("toyota", "fortuner"): 225,
    ("toyota", "innova crysta"): 178,
    ("tata", "altroz"): 165,
    ("tata", "tiago"): 170,
    ("tata", "tigor"): 170,
    ("tata", "harrier"): 205,
    ("mahindra", "xuv 7xo"): 200,
    ("mg", "hector"): 192,
}

DRIVETRAIN_REVIEW_TOKENS = re.compile(r"\b(?:4wd|4x4|awd|4x2|2wd)\b", re.IGNORECASE)

LEGACY_BASELINE_PRESERVATION_FIELDS = (
    "airbags",
    "abs",
    "esc",
    "hill_assist",
    "tyre_pressure_monitoring_system",
    "rear_parking_sensors",
    "rear_camera",
    "automatic_climate_control",
    "rear_ac_vents",
    "android_auto",
    "apple_carplay",
    "boot_space_litres",
    "ground_clearance_mm",
    "mileage_arai_kmpl",
    "mileage_arai_km_per_kg",
    "drivetrain",
)

MODEL_NAME_OVERRIDES = {
    ("Maruti Suzuki R", "Wagon"): ("Maruti Suzuki", "WagonR"),
    ("Maruti Suzuki", "Vitara Brezza"): ("Maruti Suzuki", "Brezza"),
    ("Mahindra", "Xuv300"): ("Mahindra", "XUV 3XO"),
    ("Mahindra", "Xuv500"): ("Mahindra", "XUV 7XO"),
    ("Mahindra", "Scorpio"): ("Mahindra", "Scorpio-N / Scorpio Classic"),
    ("Tata", "Nexon Ev"): ("Tata", "Nexon EV"),
    ("Tata", "Safari Storme"): ("Tata", "Safari"),
    ("Hyundai", "Grand I10 Nios"): ("Hyundai", "Grand i10 NIOS"),
    ("Hyundai", "Elite I20"): ("Hyundai", "i20"),
    ("Mg", "Hector"): ("MG", "Hector"),
    ("Mg", "Zs Ev"): ("MG", "ZS EV"),
}


def read_raw() -> pd.DataFrame:
    for path in RAW_CANDIDATES:
        if path.exists():
            return pd.read_csv(path)
    choices = ", ".join(str(path.relative_to(ROOT)) for path in RAW_CANDIDATES)
    raise FileNotFoundError(f"Could not find raw legacy CSV. Tried: {choices}")


def norm_text(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def identity_key(make: object, model: object, variant: object) -> tuple[str, str, str]:
    return norm_text(make), norm_text(model), norm_text(variant)


def parse_number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value) if not pd.isna(value) else None
    text = str(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def parse_price(value: object) -> float | None:
    number = parse_number(value)
    if number is None or number <= 0:
        return None
    return number


def parse_bool(value: object) -> object:
    if value is None or pd.isna(value):
        return pd.NA
    text = str(value).strip().lower()
    if not text or text in {"nan", "unknown", "not available", "not on offer"}:
        return pd.NA
    if text in {"yes", "true", "1"}:
        return True
    if text in {"no", "false", "0"}:
        return False
    return pd.NA


def canonical_drivetrain(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = norm_text(text)
    if normalized in {"fwd", "front wheel drive", "fwd front wheel drive"}:
        return "FWD"
    if normalized in {"rwd", "rear wheel drive", "rwd rear wheel drive"}:
        return "RWD"
    if normalized in {"awd", "all wheel drive", "awd all wheel drive"}:
        return "AWD"
    if normalized in {"4wd", "four wheel drive", "4x4"}:
        return "4WD"
    return None


def has_drivetrain_review_token(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    return bool(DRIVETRAIN_REVIEW_TOKENS.search(str(value)))


def parse_airbags(row: pd.Series) -> float | None:
    count = parse_number(row.get("Number_of_Airbags"))
    if count is not None and count > 0:
        return count
    text = row.get("Airbags")
    if text is None or pd.isna(text):
        return None
    lowered = str(text).lower()
    if not lowered.strip():
        return None
    # The legacy text names airbag locations. Count recognizable bags without
    # treating missing text as zero.
    patterns = [
        "driver frontal",
        "front passenger frontal",
        "driver knee",
        "drive side",
        "front passenger side",
        "rear passenger side",
        "curtain",
        "driver head",
        "front passenger head",
        "driver pelvic",
        "front passenger pelvic",
    ]
    count = sum(1 for pattern in patterns if pattern in lowered)
    return float(count) if count else None


def normalize_make_model(make: object, model: object) -> tuple[str | None, str | None]:
    if make is None or pd.isna(make) or model is None or pd.isna(model):
        return None, None
    make_s = str(make).strip()
    model_s = str(model).strip()
    if make_s == "Mg":
        make_s = "MG"
    if make_s == "Maruti Suzuki R" and model_s == "Wagon":
        return "Maruti Suzuki", "WagonR"
    return MODEL_NAME_OVERRIDES.get((make_s, model_s), (make_s, model_s))


def normalize_transmission_from_processed(row: pd.Series) -> str | None:
    if bool(row.get("Transmission_Manual", False)):
        return "Manual"
    if bool(row.get("Transmission_CVT", False)):
        return "Automatic (CVT)"
    if bool(row.get("Transmission_DCT", False)):
        return "Automatic (DCT)"
    if bool(row.get("Transmission_Automatic", False)):
        return "Automatic"
    return None


def normalize_one_hot(row: pd.Series, prefix: str) -> str | None:
    values = []
    for col, value in row.items():
        if col.startswith(prefix) and bool(value):
            label = col.replace(prefix, "").strip()
            if label and label.lower() != "unknown":
                values.append(label)
    return values[0] if len(values) == 1 else None


def build_processed_lookup() -> dict[tuple[str, str, str], dict[str, object]]:
    processed = pd.read_csv(PROCESSED_PATH)
    with MAPPINGS_PATH.open("rb") as handle:
        mappings = pickle.load(handle)

    processed = processed.copy()
    processed["decoded_make"] = processed["Make"].map(mappings["reverse_make_mapping"])
    processed["decoded_model"] = processed["Model"].map(mappings["reverse_model_mapping"])
    processed["decoded_variant"] = processed["Variant"].map(mappings["reverse_variant_mapping"])
    processed["identity_key"] = processed.apply(
        lambda row: identity_key(row["decoded_make"], row["decoded_model"], row["decoded_variant"]),
        axis=1,
    )

    lookup: dict[tuple[str, str, str], dict[str, object]] = {}
    counts = processed["identity_key"].value_counts()
    for _, row in processed.iterrows():
        key = row["identity_key"]
        if counts[key] != 1:
            continue
        lookup[key] = {
            "transmission": normalize_transmission_from_processed(row),
            "fuel_type": normalize_one_hot(row, "Fuel_Type_"),
            "body_type": normalize_one_hot(row, "Body_Type_"),
            "drivetrain": normalize_one_hot(row, "Drivetrain_"),
            "duplicate_processed_identity": False,
        }
    return lookup


def load_audited_lookup() -> dict[tuple[str, str, str], dict[str, object]]:
    audited_csv = pd.read_csv(AUDITED_PATH)
    records: dict[tuple[str, str, str], dict[str, object]] = {}

    for _, row in audited_csv.iterrows():
        key = identity_key(row.get("make"), row.get("model"), row.get("variant"))
        records[key] = {col: row[col] if col in row.index else pd.NA for col in COMPACT_COLUMNS}
        if pd.isna(records[key].get("source_last_updated")):
            records[key]["source_last_updated"] = row.get("scraped_at", pd.NA)

    json_path = AUDITED_PATH.with_suffix(".json")
    if json_path.exists():
        with json_path.open("r", encoding="utf-8") as handle:
            wrapped_records = json.load(handle)
        for wrapped in wrapped_records:
            canonical = wrapped.get("canonical_record", {})
            key = identity_key(canonical.get("make"), canonical.get("model"), canonical.get("variant"))
            if not any(key):
                continue
            target = records.setdefault(key, {col: pd.NA for col in COMPACT_COLUMNS})
            for col in COMPACT_COLUMNS:
                if col in canonical and pd.notna(canonical[col]):
                    target[col] = canonical[col]
            if pd.isna(target.get("source_last_updated")) and canonical.get("scraped_at"):
                target["source_last_updated"] = canonical.get("scraped_at")

    return records


def build_legacy_drivetrain_evidence(
    raw: pd.DataFrame,
    processed_lookup: dict[tuple[str, str, str], dict[str, object]],
) -> tuple[dict[tuple[str, str, str], list[dict[str, object]]], dict[tuple[str, str], list[dict[str, object]]]]:
    exact: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    model: dict[tuple[str, str], list[dict[str, object]]] = {}

    for _, row in raw.iterrows():
        compact, _ = compact_legacy_row(row, processed_lookup)
        key = identity_key(compact.get("make"), compact.get("model"), compact.get("variant"))
        model_key = (key[0], key[1])
        if not all(model_key) or not key[2]:
            continue
        evidence = {
            "make": compact.get("make"),
            "model": compact.get("model"),
            "variant": compact.get("variant"),
            "legacy_drivetrain": compact.get("drivetrain"),
            "canonical_drivetrain": canonical_drivetrain(compact.get("drivetrain")),
        }
        exact.setdefault(key, []).append(evidence)
        model.setdefault(model_key, []).append(evidence)

    return exact, model


def build_legacy_baseline_preservation_lookup(
    raw: pd.DataFrame,
    processed_lookup: dict[tuple[str, str, str], dict[str, object]],
) -> dict[tuple[str, str, str], dict[str, object]]:
    lookup: dict[tuple[str, str, str], dict[str, object]] = {}
    counts: dict[tuple[str, str, str], int] = {}
    compact_rows: list[tuple[tuple[str, str, str], dict[str, object]]] = []

    for _, row in raw.iterrows():
        compact, _ = compact_legacy_row(row, processed_lookup)
        key = identity_key(compact.get("make"), compact.get("model"), compact.get("variant"))
        if not all(key):
            continue
        counts[key] = counts.get(key, 0) + 1
        compact_rows.append((key, compact))

    for key, compact in compact_rows:
        if counts[key] != 1:
            continue
        lookup[key] = {
            field: compact.get(field)
            for field in LEGACY_BASELINE_PRESERVATION_FIELDS
            if field in compact and pd.notna(compact.get(field))
        }

    return lookup


def coerce_override_value(value: object) -> object:
    if value is None or pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if not text:
        return pd.NA
    lowered = text.lower()
    if lowered in {"null", "none", "nan", "unknown"}:
        return pd.NA
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    number = parse_number(text)
    if number is not None and re.fullmatch(r"-?\d+(?:\.\d+)?", text.replace(",", "")):
        return int(number) if number.is_integer() else number
    return text


def match_override_target(df: pd.DataFrame, make: object, model: object, variant: object) -> pd.Series:
    mask = (
        df["make"].map(norm_text).eq(norm_text(make))
        & df["model"].map(norm_text).eq(norm_text(model))
    )
    if str(variant).strip() != "*":
        mask &= df["variant"].map(norm_text).eq(norm_text(variant))
    return mask


def apply_refresh_overrides(
    working_internal: pd.DataFrame,
    allowed_actions: set[str] | None = None,
    included_sources: set[str] | None = None,
    excluded_sources: set[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    if not REFRESH_PATH.exists():
        return working_internal, {"rows_added": 0, "rows_dropped": 0, "models_refreshed": 0}

    overrides = pd.read_csv(REFRESH_PATH)
    working = working_internal.copy()
    rows_added = 0
    rows_dropped = 0
    refreshed_models: set[tuple[str, str]] = set()
    lineup_change_models: set[tuple[str, str]] = set()

    for row in overrides.itertuples(index=False):
        action = str(getattr(row, "action")).strip().upper()
        if allowed_actions is not None and action not in allowed_actions:
            continue
        source = str(getattr(row, "source", "")).strip()
        if included_sources is not None and source not in included_sources:
            continue
        if excluded_sources is not None and source in excluded_sources:
            continue
        make = getattr(row, "make")
        model = getattr(row, "model")
        variant = getattr(row, "variant")
        refreshed_models.add((norm_text(make), norm_text(model)))

        if action == "DROP_VARIANT":
            lineup_change_models.add((norm_text(make), norm_text(model)))
            mask = match_override_target(working, make, model, variant)
            rows_dropped += int(mask.sum())
            working = working[~mask].copy()
            continue

        if action == "UPDATE_FIELD":
            field = str(getattr(row, "field")).strip()
            if field not in COMPACT_COLUMNS:
                continue
            mask = match_override_target(working, make, model, variant)
            value = coerce_override_value(getattr(row, "new_value"))
            working.loc[mask, field] = value
            continue

        if action == "ADD_VARIANT":
            lineup_change_models.add((norm_text(make), norm_text(model)))
            payload = json.loads(str(getattr(row, "new_value")))
            record = {col: pd.NA for col in COMPACT_COLUMNS}
            record.update(payload)
            record["make"] = str(make).strip()
            record["model"] = str(model).strip()
            record["variant"] = str(variant).strip()
            record["full_name"] = f"{record['make']} {record['model']} {record['variant']}"
            record["source"] = source or "refresh_override"
            record["source_last_updated"] = getattr(row, "source_last_updated", pd.NA)
            record["record_origin"] = "refresh_override"
            record["legacy_row_index"] = pd.NA
            working = pd.concat([working, pd.DataFrame([record])], ignore_index=True)
            rows_added += 1

    return working, {
        "rows_added": rows_added,
        "rows_dropped": rows_dropped,
        "models_refreshed": len(refreshed_models),
        "models_with_lineup_changes": len(lineup_change_models),
        "obsolete_fuel_trim_rows_removed": rows_dropped,
    }


def apply_source_recovery(
    working_internal: pd.DataFrame,
    audited_lookup: dict[tuple[str, str, str], dict[str, object]],
    legacy_baseline_lookup: dict[tuple[str, str, str], dict[str, object]],
) -> tuple[pd.DataFrame, dict[str, int]]:
    working = working_internal.copy()
    stats = {
        "audited_values_restored": 0,
        "legacy_baseline_values_preserved": 0,
        "audited_identity_matches": 0,
        "legacy_baseline_identity_matches": 0,
    }

    for idx, row in working.iterrows():
        key = identity_key(row.get("make"), row.get("model"), row.get("variant"))
        model_key = (key[0], key[1])

        if model_key in AUDITED_MODELS and key in audited_lookup:
            stats["audited_identity_matches"] += 1
            audited_values = audited_lookup[key]
            for col in COMPACT_COLUMNS:
                value = audited_values.get(col, pd.NA)
                if pd.notna(value):
                    if pd.isna(working.at[idx, col]) or str(working.at[idx, col]) != str(value):
                        stats["audited_values_restored"] += 1
                    working.at[idx, col] = value
            continue

        if key in legacy_baseline_lookup:
            stats["legacy_baseline_identity_matches"] += 1
            legacy_values = legacy_baseline_lookup[key]
            for col, value in legacy_values.items():
                if pd.notna(value) and pd.isna(working.at[idx, col]):
                    working.at[idx, col] = value
                    stats["legacy_baseline_values_preserved"] += 1

    return working, stats


def drivetrain_report_row(
    row: pd.Series,
    exact_evidence: dict[tuple[str, str, str], list[dict[str, object]]],
    model_evidence: dict[tuple[str, str], list[dict[str, object]]],
    current_model_variants: dict[tuple[str, str], list[object]],
    verified_overrides: dict[tuple[str, str, str], str],
) -> dict[str, object]:
    key = identity_key(row.get("make"), row.get("model"), row.get("variant"))
    model_key = (key[0], key[1])
    base = {
        "make": row.get("make"),
        "model": row.get("model"),
        "variant": row.get("variant"),
        "fuel_type": row.get("fuel_type"),
        "transmission": row.get("transmission"),
        "engine_cc": row.get("engine_cc"),
        "current_drivetrain": row.get("drivetrain"),
        "legacy_make": pd.NA,
        "legacy_model": pd.NA,
        "legacy_variant": pd.NA,
        "legacy_drivetrain": pd.NA,
        "match_method": pd.NA,
        "match_confidence": pd.NA,
        "recovery_status": "UNMATCHED",
        "reason": "no_legacy_model_family_match",
    }

    verified_value = verified_overrides.get(key)
    if verified_value:
        base.update(
            {
                "legacy_drivetrain": verified_value,
                "match_method": "explicit_override",
                "match_confidence": "verified",
                "recovery_status": "EXPLICIT_VERIFIED_OVERRIDE",
                "reason": "explicit_verified_override",
            }
        )
        return base

    exact_matches = exact_evidence.get(key, [])
    if exact_matches:
        legacy_values = {match["canonical_drivetrain"] for match in exact_matches if match["canonical_drivetrain"]}
        first = exact_matches[0]
        base.update(
            {
                "legacy_make": first["make"],
                "legacy_model": first["model"],
                "legacy_variant": first["variant"],
                "legacy_drivetrain": first["canonical_drivetrain"] or first["legacy_drivetrain"],
                "match_method": "exact_identity",
                "match_confidence": "high" if len(exact_matches) == 1 and len(legacy_values) == 1 else pd.NA,
            }
        )
        if len(exact_matches) == 1 and len(legacy_values) == 1:
            base["recovery_status"] = "AUTO_ACCEPT_EXACT"
            base["reason"] = "unique_exact_identity_valid_drivetrain"
        else:
            base["recovery_status"] = "REJECT_CONFLICT"
            base["reason"] = "duplicate_or_conflicting_legacy_identity"
        return base

    family = model_evidence.get(model_key, [])
    if not family:
        return base

    valid_values = {item["canonical_drivetrain"] for item in family if item["canonical_drivetrain"]}
    first_valid = next((item for item in family if item["canonical_drivetrain"]), family[0])
    base.update(
        {
            "legacy_make": first_valid["make"],
            "legacy_model": first_valid["model"],
            "legacy_variant": pd.NA,
            "legacy_drivetrain": first_valid["canonical_drivetrain"] or first_valid["legacy_drivetrain"],
            "match_method": "model_uniform",
            "match_confidence": pd.NA,
        }
    )

    if not valid_values:
        base["recovery_status"] = "UNMATCHED"
        base["reason"] = "legacy_model_family_has_no_valid_drivetrain"
        return base
    if len(valid_values) > 1:
        base["recovery_status"] = "REVIEW_AMBIGUOUS"
        base["reason"] = "legacy_model_family_mixed_drivetrain"
        return base
    if model_key in DRIVETRAIN_PROTECTED_MODEL_UNIFORM:
        base["recovery_status"] = "REVIEW_GENERATION_RISK"
        base["reason"] = "protected_or_high_risk_model_family"
        return base

    current_variants = current_model_variants.get(model_key, [])
    legacy_variants = [item.get("variant") for item in family]
    if any(has_drivetrain_review_token(value) for value in current_variants + legacy_variants):
        base["recovery_status"] = "REVIEW_GENERATION_RISK"
        base["reason"] = "variant_contains_drivetrain_token"
        return base

    base["legacy_drivetrain"] = next(iter(valid_values))
    base["match_confidence"] = "high"
    base["recovery_status"] = "AUTO_ACCEPT_MODEL_UNIFORM"
    base["reason"] = "legacy_model_family_uniform_valid_drivetrain"
    return base


def build_drivetrain_recovery_report(
    working_internal: pd.DataFrame,
    exact_evidence: dict[tuple[str, str, str], list[dict[str, object]]],
    model_evidence: dict[tuple[str, str], list[dict[str, object]]],
    verified_overrides: dict[tuple[str, str, str], str],
) -> pd.DataFrame:
    current_model_variants: dict[tuple[str, str], list[object]] = {}
    for _, row in working_internal.iterrows():
        model_key = (norm_text(row.get("make")), norm_text(row.get("model")))
        current_model_variants.setdefault(model_key, []).append(row.get("variant"))

    null_drivetrain = working_internal[working_internal["drivetrain"].isna()].copy()
    rows = [
        drivetrain_report_row(
            row,
            exact_evidence,
            model_evidence,
            current_model_variants,
            verified_overrides,
        )
        for _, row in null_drivetrain.iterrows()
    ]
    columns = [
        "make",
        "model",
        "variant",
        "fuel_type",
        "transmission",
        "engine_cc",
        "current_drivetrain",
        "legacy_make",
        "legacy_model",
        "legacy_variant",
        "legacy_drivetrain",
        "match_method",
        "match_confidence",
        "recovery_status",
        "reason",
    ]
    return pd.DataFrame(rows, columns=columns)


def sync_verified_drivetrain_overrides(
    working_internal: pd.DataFrame,
) -> tuple[dict[tuple[str, str, str], str], dict[str, int]]:
    overrides = pd.read_csv(REFRESH_PATH)
    verified_mask = overrides["source"].astype(str).eq(VERIFIED_DRIVETRAIN_SOURCE)
    preserved = overrides[~verified_mask].copy()
    rows: list[dict[str, object]] = []
    verified: dict[tuple[str, str, str], str] = {}

    for _, row in working_internal.iterrows():
        model_key = (norm_text(row.get("make")), norm_text(row.get("model")))
        drivetrain = VERIFIED_DRIVETRAIN_MODELS.get(model_key)
        if not drivetrain:
            continue
        key = identity_key(row.get("make"), row.get("model"), row.get("variant"))
        verified[key] = drivetrain
        rows.append(
            {
                "make": row.get("make"),
                "model": row.get("model"),
                "variant": row.get("variant"),
                "action": "UPDATE_FIELD",
                "field": "drivetrain",
                "new_value": drivetrain,
                "source": VERIFIED_DRIVETRAIN_SOURCE,
                "source_last_updated": VERIFIED_DRIVETRAIN_DATE,
                "notes": "explicit_verified_override",
            }
        )

    updated = pd.concat([preserved, pd.DataFrame(rows, columns=overrides.columns)], ignore_index=True)
    updated.to_csv(REFRESH_PATH, index=False)
    return verified, {"override_rows_written": len(rows)}


def verified_ground_clearance(row: pd.Series) -> int | None:
    model_key = (norm_text(row.get("make")), norm_text(row.get("model")))
    if model_key != ("mahindra", "scorpio n scorpio classic"):
        return VERIFIED_GROUND_CLEARANCE_MODELS.get(model_key)

    variant = str(row.get("variant"))
    if variant.startswith("Scorpio-N"):
        return 187
    if variant.startswith("Classic"):
        return 209
    return None


def sync_verified_ground_clearance_overrides(
    working_internal: pd.DataFrame,
) -> dict[str, object]:
    overrides = pd.read_csv(REFRESH_PATH)
    verified_mask = overrides["source"].astype(str).eq(VERIFIED_GROUND_CLEARANCE_SOURCE)
    preserved = overrides[~verified_mask].copy()
    rows: list[dict[str, object]] = []
    conflicts: list[str] = []
    unmatched_scorpio: list[str] = []
    already_matching = 0
    rows_by_model: dict[str, int] = {}

    for _, row in working_internal.iterrows():
        model_key = (norm_text(row.get("make")), norm_text(row.get("model")))
        expected = verified_ground_clearance(row)
        if model_key == ("mahindra", "scorpio n scorpio classic") and expected is None:
            unmatched_scorpio.append(str(row.get("variant")))
            continue
        if expected is None:
            continue

        current = parse_number(row.get("ground_clearance_mm"))
        if current is not None:
            if current != expected:
                conflicts.append(
                    f"{row.get('make')}|{row.get('model')}|{row.get('variant')}: "
                    f"existing={current:g}, verified={expected}"
                )
                continue
            already_matching += 1

        model_label = f"{row.get('make')} {row.get('model')}"
        rows_by_model[model_label] = rows_by_model.get(model_label, 0) + 1
        rows.append(
            {
                "make": row.get("make"),
                "model": row.get("model"),
                "variant": row.get("variant"),
                "action": "UPDATE_FIELD",
                "field": "ground_clearance_mm",
                "new_value": expected,
                "source": VERIFIED_GROUND_CLEARANCE_SOURCE,
                "source_last_updated": VERIFIED_GROUND_CLEARANCE_DATE,
                "notes": "explicit_verified_override",
            }
        )

    if conflicts:
        raise ValueError(
            "Verified ground-clearance conflicts detected; no overrides written:\n"
            + "\n".join(conflicts)
        )

    updated = pd.concat([preserved, pd.DataFrame(rows, columns=overrides.columns)], ignore_index=True)
    updated.to_csv(REFRESH_PATH, index=False)
    return {
        "override_rows_written": len(rows),
        "already_matching": already_matching,
        "conflicts": conflicts,
        "unmatched_scorpio": unmatched_scorpio,
        "rows_by_model": rows_by_model,
    }


def sync_drivetrain_recovery_overrides(report: pd.DataFrame) -> dict[str, int]:
    overrides = pd.read_csv(REFRESH_PATH)
    recovery_mask = overrides["source"].astype(str).eq(DRIVETRAIN_RECOVERY_SOURCE)
    preserved = overrides[~recovery_mask].copy()
    existing_targets = {
        (
            norm_text(row.get("make")),
            norm_text(row.get("model")),
            norm_text(row.get("variant")),
            str(row.get("field")).strip(),
        )
        for _, row in preserved.iterrows()
        if str(row.get("action")).strip().upper() == "UPDATE_FIELD"
    }

    accepted = report[
        report["recovery_status"].isin(["AUTO_ACCEPT_EXACT", "AUTO_ACCEPT_MODEL_UNIFORM"])
    ].copy()
    rows: list[dict[str, object]] = []
    for _, row in accepted.iterrows():
        target = (
            norm_text(row.get("make")),
            norm_text(row.get("model")),
            norm_text(row.get("variant")),
            "drivetrain",
        )
        if target in existing_targets:
            continue
        rows.append(
            {
                "make": row.get("make"),
                "model": row.get("model"),
                "variant": row.get("variant"),
                "action": "UPDATE_FIELD",
                "field": "drivetrain",
                "new_value": row.get("legacy_drivetrain"),
                "source": DRIVETRAIN_RECOVERY_SOURCE,
                "source_last_updated": DRIVETRAIN_RECOVERY_DATE,
                "notes": f"{row.get('recovery_status')} via {row.get('match_method')}",
            }
        )

    updated = pd.concat([preserved, pd.DataFrame(rows, columns=overrides.columns)], ignore_index=True)
    updated.to_csv(REFRESH_PATH, index=False)
    return {
        "override_rows_written": len(rows),
        "accepted_rows": len(accepted),
        "skipped_existing_update_targets": len(accepted) - len(rows),
    }


def normalize_allowed_values(working: pd.DataFrame) -> pd.DataFrame:
    normalized = working.copy()
    normalized["drivetrain"] = normalized["drivetrain"].map(
        lambda value: canonical_drivetrain(value) if pd.notna(value) else pd.NA
    )
    for column in BOOLEAN_FEATURE_COLUMNS:
        normalized[column] = normalized[column].astype("boolean")
    return normalized


def load_schema_contract() -> dict[str, object]:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Missing schema contract: {SCHEMA_PATH.relative_to(ROOT)}")
    with SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    fields = schema.get("fields", [])
    if [field.get("name") for field in fields] != COMPACT_COLUMNS:
        raise ValueError("Schema contract field order does not match COMPACT_COLUMNS")
    return schema


def normalized_identity_series(frame: pd.DataFrame) -> pd.Series:
    def validation_identity_part(value: object) -> str:
        if value is None or pd.isna(value):
            return ""
        return re.sub(r"\s+", " ", str(value).strip().lower())

    return frame[["make", "model", "variant"]].apply(
        lambda row: "|".join(
            [
                validation_identity_part(row["make"]),
                validation_identity_part(row["model"]),
                validation_identity_part(row["variant"]),
            ]
        ),
        axis=1,
    )


def dataframe_parity(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    if list(left.columns) != list(right.columns) or len(left) != len(right):
        return False
    left_json = left.where(pd.notna(left), None).to_json(orient="records", force_ascii=False)
    right_json = right.where(pd.notna(right), None).to_json(orient="records", force_ascii=False)
    return left_json == right_json


def value_counts_string(series: pd.Series) -> str:
    values = series.value_counts(dropna=False).to_dict()
    rendered = {}
    for key, value in values.items():
        rendered["null" if pd.isna(key) else str(key)] = int(value)
    return json.dumps(rendered, sort_keys=True)


def add_validation_row(
    rows: list[dict[str, object]],
    check: str,
    status: str,
    value: object,
    expected: object,
    notes: str = "",
) -> None:
    rows.append(
        {
            "check": check,
            "status": status,
            "value": value,
            "expected": expected,
            "notes": notes,
        }
    )


def validate_and_export_outputs(working: pd.DataFrame, review: pd.DataFrame) -> pd.DataFrame:
    schema = load_schema_contract()
    schema_fields = schema["fields"]
    field_map = {field["name"]: field for field in schema_fields}

    working.to_csv(OUTPUT_PATH, index=False)
    working.to_csv(RECOMMENDATION_PATH, index=False)
    records = json.loads(working.where(pd.notna(working), None).to_json(orient="records"))
    RECOMMENDATION_JSON_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    review.to_csv(REVIEW_PATH, index=False)

    recommendation = pd.read_csv(RECOMMENDATION_PATH)
    working_read = pd.read_csv(OUTPUT_PATH)
    with RECOMMENDATION_JSON_PATH.open("r", encoding="utf-8") as handle:
        json_records = json.load(handle)

    rows: list[dict[str, object]] = []
    hard_failures: list[str] = []

    def checked(check: str, passed: bool, value: object, expected: object, notes: str = "") -> None:
        add_validation_row(rows, check, "PASS" if passed else "FAIL", value, expected, notes)
        if not passed:
            hard_failures.append(check)

    checked("schema_column_names", list(working.columns) == COMPACT_COLUMNS, json.dumps(list(working.columns)), json.dumps(COMPACT_COLUMNS))
    checked("schema_column_order", list(working.columns) == [field["name"] for field in schema_fields], "matches" if list(working.columns) == [field["name"] for field in schema_fields] else "mismatch", "schema contract order")
    checked("dataset_row_count", len(working) == 475, len(working), 475)
    checked("dataset_column_count", working.shape[1] == 36, working.shape[1], 36)
    checked("manufacturer_count", working["make"].nunique(dropna=True) == 9, working["make"].nunique(dropna=True), 9)
    checked("model_count", working[["make", "model"]].drop_duplicates().shape[0] == 31, working[["make", "model"]].drop_duplicates().shape[0], 31)

    identity_duplicates = int(working.duplicated(subset=["make", "model", "variant"]).sum())
    normalized_duplicates = int(normalized_identity_series(working).duplicated().sum())
    checked("duplicate_identity_count", identity_duplicates == 0, identity_duplicates, 0)
    checked("normalized_duplicate_identity_count", normalized_duplicates == 0, normalized_duplicates, 0)

    missing_required = int(working[REQUIRED_SCHEMA_FIELDS].isna().sum().sum())
    missing_core = int(working[CORE_FIELDS].isna().sum().sum())
    checked("missing_required_field_count", missing_required == 0, missing_required, 0)
    checked("missing_core_field_count", missing_core == 0, missing_core, 0)
    checked("review_queue_size", len(review) == 0, len(review), 0)

    checked("price_ex_showroom_positive", bool((working["price_ex_showroom"] > 0).all()), int((working["price_ex_showroom"] <= 0).sum()), 0)
    checked("seating_capacity_positive", bool((working["seating_capacity"] > 0).all()), int((working["seating_capacity"] <= 0).sum()), 0)
    checked("airbags_at_least_one", bool((working["airbags"] >= 1).all()), int((working["airbags"] < 1).sum()), 0)

    electric = working["fuel_type"].eq("Electric")
    checked("electric_engine_cc_null", int(working.loc[electric, "engine_cc"].notna().sum()) == 0, int(working.loc[electric, "engine_cc"].notna().sum()), 0)
    checked("electric_range_present", int(working.loc[electric, "claimed_ev_range_km"].isna().sum()) == 0, int(working.loc[electric, "claimed_ev_range_km"].isna().sum()), 0)
    checked("non_electric_range_null", int(working.loc[~electric, "claimed_ev_range_km"].notna().sum()) == 0, int(working.loc[~electric, "claimed_ev_range_km"].notna().sum()), 0)

    for field in schema_fields:
        name = field["name"]
        allowed_values = field.get("allowed_values")
        if allowed_values is None:
            continue
        allowed_without_null = {value for value in allowed_values if value is not None}
        invalid = sorted(
            {
                str(value)
                for value in working[name].dropna().unique()
                if value not in allowed_without_null
            }
        )
        checked(f"allowed_values:{name}", not invalid, json.dumps(invalid), "no violations")

    for column in BOOLEAN_FEATURE_COLUMNS:
        non_null = working[column].dropna()
        invalid = sorted({str(value) for value in non_null.unique() if value not in {True, False}})
        checked(f"boolean_values:{column}", not invalid, json.dumps(invalid), "True/False/null only")

    conflict_count = int(
        working.assign(_key=normalized_identity_series(working))
        .groupby("_key")[["fuel_type", "transmission"]]
        .nunique(dropna=False)
        .gt(1)
        .any(axis=1)
        .sum()
    )
    checked("conflicting_duplicate_identity_fuel_transmission", conflict_count == 0, conflict_count, 0)

    checked("csv_json_row_parity", len(json_records) == len(working), len(json_records), len(working))
    checked("working_final_csv_parity", dataframe_parity(working_read, recommendation), "match" if dataframe_parity(working_read, recommendation) else "mismatch", "match")
    add_validation_row(
        rows,
        "working_memory_csv_round_trip",
        "INFO",
        "match" if dataframe_parity(working, working_read) else "serialization-normalized",
        "reported",
        "CSV round trips may normalize nullable scalar dtypes.",
    )
    checked("no_model_loss", working[["make", "model"]].drop_duplicates().shape[0] == 31, working[["make", "model"]].drop_duplicates().shape[0], 31)
    checked("no_variant_loss", len(working[["make", "model", "variant"]].drop_duplicates()) == 475, len(working[["make", "model", "variant"]].drop_duplicates()), 475)

    for column in COMPACT_COLUMNS:
        null_count = int(working[column].isna().sum())
        add_validation_row(rows, f"null_count:{column}", "INFO", null_count, "reported")
        add_validation_row(rows, f"null_percentage:{column}", "INFO", round(null_count / len(working), 6), "reported")

    for column in BOOLEAN_FEATURE_COLUMNS:
        true_count = int(working[column].eq(True).sum())
        false_count = int(working[column].eq(False).sum())
        null_count = int(working[column].isna().sum())
        add_validation_row(
            rows,
            f"boolean_distribution:{column}",
            "INFO",
            json.dumps({"true": true_count, "false": false_count, "null": null_count}, sort_keys=True),
            "reported",
        )

    constant_columns = [column for column in COMPACT_COLUMNS if working[column].nunique(dropna=False) == 1]
    near_constant_columns = []
    for column in COMPACT_COLUMNS:
        top_share = working[column].astype("object").fillna("<NULL>").value_counts(normalize=True, dropna=False).iloc[0]
        if 0.95 <= top_share < 1:
            near_constant_columns.append(f"{column}:{top_share:.3f}")
    add_validation_row(rows, "all_constant_columns", "INFO", json.dumps(constant_columns), "reported")
    add_validation_row(rows, "near_constant_columns", "INFO", json.dumps(near_constant_columns), "reported")

    for column in NUMERIC_COLUMNS:
        add_validation_row(
            rows,
            f"numeric_coverage_by_fuel_type:{column}",
            "INFO",
            json.dumps(working.groupby("fuel_type")[column].apply(lambda series: int(series.notna().sum())).to_dict(), sort_keys=True),
            "reported",
        )
        add_validation_row(
            rows,
            f"numeric_coverage_by_model:{column}",
            "INFO",
            json.dumps(
                {
                    f"{make} {model}": int(group[column].notna().sum())
                    for (make, model), group in working.groupby(["make", "model"])
                },
                sort_keys=True,
            ),
            "reported",
        )

    add_validation_row(rows, "drivetrain_distribution", "INFO", value_counts_string(working["drivetrain"]), "reported")
    add_validation_row(rows, "fuel_type_distribution", "INFO", value_counts_string(working["fuel_type"]), "reported")
    add_validation_row(rows, "transmission_distribution", "INFO", value_counts_string(working["transmission"]), "reported")

    validation = pd.DataFrame(rows)
    validation.to_csv(VALIDATION_PATH, index=False)

    if hard_failures:
        raise ValueError("Schema validation failed: " + ", ".join(hard_failures))
    return validation


def compact_legacy_row(row: pd.Series, processed_lookup: dict[tuple[str, str, str], dict[str, object]]) -> tuple[dict[str, object], list[str]]:
    output = {col: pd.NA for col in COMPACT_COLUMNS}
    issues: list[str] = []

    make, model = normalize_make_model(row.get("Make"), row.get("Model"))
    variant = row.get("Variant")
    key = identity_key(row.get("Make"), row.get("Model"), variant)
    processed = processed_lookup.get(key)

    if processed is None:
        issues.append("unmatched_processed_identity")

    output["make"] = make
    output["model"] = model
    output["variant"] = None if pd.isna(variant) else str(variant).strip()
    if output["make"] and output["model"] and output["variant"]:
        output["full_name"] = f"{output['make']} {output['model']} {output['variant']}"

    output["body_type"] = processed.get("body_type") if processed else None
    if not output["body_type"]:
        output["body_type"] = row.get("Body_Type") if not pd.isna(row.get("Body_Type")) else pd.NA

    output["price_ex_showroom"] = parse_price(row.get("Ex-Showroom_Price"))
    output["fuel_type"] = processed.get("fuel_type") if processed else None
    if not output["fuel_type"]:
        output["fuel_type"] = row.get("Fuel_Type") if not pd.isna(row.get("Fuel_Type")) else pd.NA

    output["transmission"] = processed.get("transmission") if processed else None
    output["engine_cc"] = parse_number(row.get("Displacement"))
    output["power_bhp"] = parse_number(row.get("Power"))
    output["torque_nm"] = parse_number(row.get("Torque"))
    output["drivetrain"] = processed.get("drivetrain") if processed else None
    if not output["drivetrain"]:
        output["drivetrain"] = row.get("Drivetrain") if not pd.isna(row.get("Drivetrain")) else pd.NA

    output["mileage_arai_kmpl"] = parse_number(row.get("ARAI_Certified_Mileage"))
    output["mileage_arai_km_per_kg"] = parse_number(row.get("ARAI_Certified_Mileage_for_CNG"))
    output["claimed_ev_range_km"] = parse_number(row.get("Electric_Range"))
    output["seating_capacity"] = parse_number(row.get("Seating_Capacity"))
    output["boot_space_litres"] = parse_number(row.get("Boot_Space"))
    output["ground_clearance_mm"] = parse_number(row.get("Ground_Clearance"))
    output["airbags"] = parse_airbags(row)
    output["abs"] = parse_bool(row.get("ABS_(Anti-lock_Braking_System)"))
    output["esc"] = parse_bool(row.get("ESP_(Electronic_Stability_Program)"))
    output["hill_assist"] = parse_bool(row.get("Hill_Assist"))
    output["tyre_pressure_monitoring_system"] = parse_bool(row.get("Tyre_Pressure_Monitoring_System"))

    parking = "" if pd.isna(row.get("Parking_Assistance")) else str(row.get("Parking_Assistance")).lower()
    output["rear_parking_sensors"] = True if "rear sensors" in parking else pd.NA
    output["rear_camera"] = True if "camera" in parking else pd.NA
    output["camera_360"] = True if "360" in parking else pd.NA

    ventilation = "" if pd.isna(row.get("Ventilation_System")) else str(row.get("Ventilation_System")).lower()
    output["automatic_climate_control"] = True if "automatic climate" in ventilation or "zone climate" in ventilation else pd.NA
    output["rear_ac_vents"] = parse_bool(row.get("Second_Row_AC_Vents"))
    output["android_auto"] = parse_bool(row.get("Android_Auto"))
    output["apple_carplay"] = parse_bool(row.get("Apple_CarPlay"))
    output["sunroof"] = pd.NA
    output["ventilated_front_seats"] = pd.NA
    output["connected_car_features"] = pd.NA
    output["adas_available"] = pd.NA
    output["source"] = "legacy_2021"
    output["source_last_updated"] = "2021"

    if not output["make"] or not output["model"] or not output["variant"]:
        issues.append("missing_core_identity")
    if output["price_ex_showroom"] is None:
        issues.append("invalid_price")
    if not output["transmission"]:
        issues.append("missing_transmission")

    return output, issues


def main() -> None:
    raw = read_raw()
    plan = pd.read_csv(PLAN_PATH)
    audited = pd.read_csv(AUDITED_PATH)
    processed_lookup = build_processed_lookup()
    audited_lookup = load_audited_lookup()
    exact_drivetrain_evidence, model_drivetrain_evidence = build_legacy_drivetrain_evidence(raw, processed_lookup)
    legacy_baseline_lookup = build_legacy_baseline_preservation_lookup(raw, processed_lookup)

    selected_plan = plan[plan["final_selected"].astype(str).str.lower().eq("true")].copy()
    selected_keys = {
        (norm_text(row.legacy_make), norm_text(row.legacy_model))
        for row in selected_plan.itertuples(index=False)
    }
    selected_current_models = {
        (norm_text(row.legacy_make), norm_text(row.current_model_name or row.legacy_model))
        for row in selected_plan.itertuples(index=False)
    }

    raw = raw.copy()
    raw["legacy_family_key"] = raw.apply(lambda row: (norm_text(row.get("Make")), norm_text(row.get("Model"))), axis=1)
    raw_selected = raw[raw["legacy_family_key"].isin(selected_keys)].copy()
    legacy_audited_mask = raw_selected["legacy_family_key"].isin(LEGACY_TO_AUDITED)
    raw_legacy = raw_selected[~legacy_audited_mask].copy()

    rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    legacy_transmission_attempts = 0
    legacy_transmission_success = 0

    for raw_index, row in raw_legacy.iterrows():
        compact, issues = compact_legacy_row(row, processed_lookup)
        compact["record_origin"] = "legacy"
        compact["legacy_row_index"] = raw_index
        rows.append(compact)

        legacy_transmission_attempts += 1
        if compact.get("transmission"):
            legacy_transmission_success += 1

        if issues:
            review = {
                "record_origin": "legacy",
                "legacy_row_index": raw_index,
                "make": compact.get("make"),
                "model": compact.get("model"),
                "variant": compact.get("variant"),
                "issues": "|".join(sorted(set(issues))),
            }
            review_rows.append(review)

    audited_selected = audited[
        audited.apply(lambda row: (norm_text(row.get("make")), norm_text(row.get("model"))) in AUDITED_MODELS, axis=1)
    ].copy()

    missing_audited = AUDITED_MODELS - {
        (norm_text(row.get("make")), norm_text(row.get("model")))
        for _, row in audited_selected.iterrows()
    }
    for make, model in sorted(missing_audited):
        review_rows.append(
            {
                "record_origin": "audited",
                "legacy_row_index": pd.NA,
                "make": make,
                "model": model,
                "variant": pd.NA,
                "issues": "audited_replacement_mismatch",
            }
        )

    for _, row in audited_selected.iterrows():
        compact = {col: row[col] if col in row.index else pd.NA for col in COMPACT_COLUMNS}
        if pd.isna(compact.get("source_last_updated")):
            compact["source_last_updated"] = row.get("scraped_at", pd.NA)
        compact["record_origin"] = "audited"
        compact["legacy_row_index"] = pd.NA
        rows.append(compact)

    working_internal = pd.DataFrame(rows)
    output_columns = COMPACT_COLUMNS + ["record_origin", "legacy_row_index"]
    working_internal = working_internal.reindex(columns=output_columns)
    working_internal, refresh_stats = apply_refresh_overrides(
        working_internal,
        allowed_actions={"DROP_VARIANT", "ADD_VARIANT"},
        excluded_sources={
            DRIVETRAIN_RECOVERY_SOURCE,
            VERIFIED_DRIVETRAIN_SOURCE,
            VERIFIED_GROUND_CLEARANCE_SOURCE,
        },
    )
    working_internal, recovery_stats = apply_source_recovery(
        working_internal,
        audited_lookup,
        legacy_baseline_lookup,
    )
    working_internal, update_stats = apply_refresh_overrides(
        working_internal,
        allowed_actions={"UPDATE_FIELD"},
        excluded_sources={
            DRIVETRAIN_RECOVERY_SOURCE,
            VERIFIED_DRIVETRAIN_SOURCE,
            VERIFIED_GROUND_CLEARANCE_SOURCE,
        },
    )
    verified_drivetrain_overrides, verified_drivetrain_stats = (
        sync_verified_drivetrain_overrides(working_internal)
    )
    verified_ground_clearance_stats = sync_verified_ground_clearance_overrides(
        working_internal
    )
    drivetrain_report = build_drivetrain_recovery_report(
        working_internal,
        exact_drivetrain_evidence,
        model_drivetrain_evidence,
        verified_drivetrain_overrides,
    )
    drivetrain_report.to_csv(DRIVETRAIN_RECOVERY_REPORT_PATH, index=False)
    drivetrain_override_stats = sync_drivetrain_recovery_overrides(drivetrain_report)
    working_internal, drivetrain_update_stats = apply_refresh_overrides(
        working_internal,
        allowed_actions={"UPDATE_FIELD"},
        included_sources={
            DRIVETRAIN_RECOVERY_SOURCE,
            VERIFIED_DRIVETRAIN_SOURCE,
            VERIFIED_GROUND_CLEARANCE_SOURCE,
        },
    )
    refresh_stats["models_refreshed"] = max(
        refresh_stats["models_refreshed"],
        update_stats["models_refreshed"],
        drivetrain_update_stats["models_refreshed"],
    )
    if review_rows:
        surviving_issue_keys = {
            (
                str(row.get("record_origin")),
                "" if pd.isna(row.get("legacy_row_index")) else str(row.get("legacy_row_index")),
                norm_text(row.get("make")),
                norm_text(row.get("model")),
                norm_text(row.get("variant")),
            )
            for _, row in working_internal.iterrows()
        }
        review_rows = [
            row
            for row in review_rows
            if (
                str(row.get("record_origin")),
                "" if pd.isna(row.get("legacy_row_index")) else str(row.get("legacy_row_index")),
                norm_text(row.get("make")),
                norm_text(row.get("model")),
                norm_text(row.get("variant")),
            )
            in surviving_issue_keys
        ]

    duplicate_mask = working_internal.duplicated(subset=["make", "model", "variant"], keep=False)
    duplicate_count = int(duplicate_mask.sum())
    for _, row in working_internal[duplicate_mask].iterrows():
        review_rows.append(
            {
                "record_origin": row.get("record_origin"),
                "legacy_row_index": row.get("legacy_row_index"),
                "make": row.get("make"),
                "model": row.get("model"),
                "variant": row.get("variant"),
                "issues": "duplicate_normalized_identity",
            }
        )

    for _, row in working_internal[working_internal[CORE_FIELDS].isna().any(axis=1)].iterrows():
        missing = [field for field in CORE_FIELDS if pd.isna(row.get(field))]
        review_rows.append(
            {
                "record_origin": row.get("record_origin"),
                "legacy_row_index": row.get("legacy_row_index"),
                "make": row.get("make"),
                "model": row.get("model"),
                "variant": row.get("variant"),
                "issues": "missing_core_fields:" + "|".join(missing),
            }
        )

    working = normalize_allowed_values(working_internal[COMPACT_COLUMNS].copy())

    review = pd.DataFrame(review_rows).drop_duplicates()
    if not review.empty:
        review = (
            review.groupby(
                ["record_origin", "legacy_row_index", "make", "model", "variant"],
                dropna=False,
                as_index=False,
            )["issues"]
            .apply(lambda values: "|".join(sorted(set("|".join(map(str, values)).split("|")))))
        )
    if review.empty:
        review = pd.DataFrame(columns=["record_origin", "legacy_row_index", "make", "model", "variant", "issues"])

    validation = validate_and_export_outputs(working, review)

    selected_model_count = working[["make", "model"]].drop_duplicates().shape[0]
    manufacturer_count = working["make"].dropna().nunique()
    audited_count = int(
        working_internal.apply(
            lambda row: (norm_text(row.get("make")), norm_text(row.get("model"))) in AUDITED_MODELS,
            axis=1,
        ).sum()
    )
    legacy_count = int(len(working_internal) - audited_count)
    core_missing = working[CORE_FIELDS].isna().sum()
    transmission_rate = (
        legacy_transmission_success / legacy_transmission_attempts
        if legacy_transmission_attempts
        else 0.0
    )

    print(f"total rows: {len(working)}")
    print(f"selected model count: {selected_model_count}")
    print(f"manufacturer count: {manufacturer_count}")
    print(f"rows added: {refresh_stats['rows_added']}")
    print(f"rows dropped: {refresh_stats['rows_dropped']}")
    print(f"models with lineup changes: {refresh_stats['models_with_lineup_changes']}")
    print(f"obsolete fuel/trim rows removed: {refresh_stats['obsolete_fuel_trim_rows_removed']}")
    print(f"audited row count: {audited_count}")
    print(f"legacy row count: {legacy_count}")
    print(f"audited values restored: {recovery_stats['audited_values_restored']}")
    print(f"audited exact identity matches: {recovery_stats['audited_identity_matches']}")
    print(f"legacy baseline values preserved: {recovery_stats['legacy_baseline_values_preserved']}")
    print(f"legacy baseline exact identity matches: {recovery_stats['legacy_baseline_identity_matches']}")
    print(f"drivetrain recovery overrides written: {drivetrain_override_stats['override_rows_written']}")
    print(f"drivetrain recovery accepted rows: {drivetrain_override_stats['accepted_rows']}")
    print(f"drivetrain recovery existing update targets skipped: {drivetrain_override_stats['skipped_existing_update_targets']}")
    print(f"duplicate identity count: {duplicate_count}")
    print("missing core fields:")
    for field, count in core_missing.items():
        print(f"  {field}: {int(count)}")
    print(f"transmission recovery rate: {transmission_rate:.2%}")
    print(f"review queue size: {len(review)}")
    print(f"models refreshed: {refresh_stats['models_refreshed']}")
    print(f"unresolved models: {review[['make', 'model']].drop_duplicates().shape[0] if not review.empty else 0}")
    print(f"working dataset: {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"recommendation dataset: {RECOMMENDATION_PATH.relative_to(ROOT)}")
    print(f"recommendation json: {RECOMMENDATION_JSON_PATH.relative_to(ROOT)}")
    print(f"validation report: {VALIDATION_PATH.relative_to(ROOT)}")
    print(f"review queue: {REVIEW_PATH.relative_to(ROOT)}")
    print(f"drivetrain recovery report: {DRIVETRAIN_RECOVERY_REPORT_PATH.relative_to(ROOT)}")
    print(
        "verified drivetrain overrides written: "
        f"{verified_drivetrain_stats['override_rows_written']}"
    )
    print(
        "verified ground-clearance overrides written: "
        f"{verified_ground_clearance_stats['override_rows_written']}"
    )
    print(
        "verified ground-clearance rows already matching: "
        f"{verified_ground_clearance_stats['already_matching']}"
    )
    print(
        "verified ground-clearance unmatched Scorpio rows: "
        f"{len(verified_ground_clearance_stats['unmatched_scorpio'])}"
    )
    print(f"schema validation rows: {len(validation)}")


if __name__ == "__main__":
    main()
