import numpy as np
import pandas as pd


BODY_TYPE_COLUMNS = {
    "suv": "Body_Type_SUV",
    "sedan": "Body_Type_Sedan",
    "hatchback": "Body_Type_Hatchback",
    "mpv": "Body_Type_MPV",
    "muv": "Body_Type_MUV",
    "coupe": "Body_Type_Coupe",
    "sports": "Body_Type_Sports"
}


def safe_num(value, default=0.0):
    try:
        value = float(value)
        if np.isnan(value) or np.isinf(value):
            return default
        return value
    except Exception:
        return default


def has_column_value(row, col):
    if col not in row.index:
        return False

    value = safe_num(row[col], 0)
    return value > 0


def has_any_column(row, possible_cols):
    return any(has_column_value(row, col) for col in possible_cols)


def get_body_type(row):
    for body_type, col in BODY_TYPE_COLUMNS.items():
        if has_column_value(row, col):
            return body_type
    return "unknown"


def get_transmission(row):
    if has_column_value(row, "Transmission_Automatic"):
        return "automatic"
    if has_column_value(row, "Transmission_Manual"):
        return "manual"
    return "unknown"


def get_fuel_type(row):
    fuel_cols = {
        "petrol": "Fuel_Type_Petrol",
        "diesel": "Fuel_Type_Diesel",
        "cng": "Fuel_Type_CNG",
        "electric": "Fuel_Type_Electric",
        "hybrid": "Fuel_Type_Hybrid"
    }

    for fuel, col in fuel_cols.items():
        if has_column_value(row, col):
            return fuel

    return "unknown"


def has_airbags(row):
    # Handles either direct Airbags count column or one-hot style columns
    if "Airbags" in row.index:
        return safe_num(row["Airbags"], 0) > 0

    for col in row.index:
        if "airbag" in col.lower() and safe_num(row[col], 0) > 0:
            return True

    return False


def has_abs(row):
    possible_cols = [
        "ABS_(Anti-lock_Braking_System)",
        "ABS",
        "Anti-lock_Braking_System"
    ]

    if has_any_column(row, possible_cols):
        return True

    for col in row.index:
        lowered = col.lower()
        if ("abs" in lowered or "anti-lock" in lowered) and safe_num(row[col], 0) > 0:
            return True

    return False


def has_feature(row, feature_name):
    if feature_name in row.index:
        return safe_num(row[feature_name], 0) > 0

    lowered_feature = feature_name.lower()

    for col in row.index:
        if lowered_feature in col.lower() and safe_num(row[col], 0) > 0:
            return True

    return False


def get_requested_budget(filters):
    price_filter = filters.get("Ex-Showroom_Price")

    if price_filter is None:
        return None, None

    if isinstance(price_filter, list):
        if len(price_filter) == 2:
            return price_filter[0], price_filter[1]

    return None, price_filter


def price_score(row, filters, use_case):
    price = safe_num(row.get("Ex-Showroom_Price"), 0)
    price_min, price_max = get_requested_budget(filters)

    if price <= 0:
        return 0, []

    reasons = []

    if price_max is None:
        return 0, reasons

    if price > price_max:
        return -100, ["over budget"]

    if use_case in ["budget", "student"]:
        target_price = price_max * 0.55
    elif use_case in ["premium", "enthusiast"]:
        target_price = price_max * 0.85
    else:
        target_price = price_max * 0.70

    closeness = 1 - abs(price - target_price) / max(price_max, 1)
    score = max(0, closeness) * 18

    if price <= price_max:
        reasons.append("within budget")

    # Avoid recommending extremely cheap/weak cars for family/parents/highway queries
    if use_case in ["family", "parents", "highway"] and price < price_max * 0.30:
        score -= 8
        reasons.append("penalized for being too basic for this use-case")

    return score, reasons


def mileage_score(row, filters, use_case):
    mileage = safe_num(row.get("ARAI_Certified_Mileage"), 0)
    reasons = []

    if mileage <= 0:
        return 0, reasons

    # Normalize roughly between 10 and 25 kmpl
    score = np.clip((mileage - 10) / 15, 0, 1) * 12

    if mileage >= 18:
        reasons.append("good mileage")

    if "ARAI_Certified_Mileage" in filters:
        score += 6
        reasons.append("matches mileage preference")

    if use_case in ["city", "commute", "family", "student", "budget"]:
        score += np.clip((mileage - 12) / 12, 0, 1) * 5

    return score, reasons


def feature_match_score(row, filters):
    score = 0
    reasons = []

    feature_map = {
        "Sunroof": "sunroof",
        "Cruise_Control": "cruise control",
        "Android_Auto": "android auto",
        "Apple_CarPlay": "apple carplay",
        "ABS_(Anti-lock_Braking_System)": "ABS",
        "Airbags": "airbags"
    }

    for filter_col, label in feature_map.items():
        if filters.get(filter_col) == 1:
            if filter_col == "Airbags":
                present = has_airbags(row)
            elif filter_col == "ABS_(Anti-lock_Braking_System)":
                present = has_abs(row)
            else:
                present = has_feature(row, filter_col)

            if present:
                score += 8
                reasons.append(f"has {label}")
            else:
                score -= 4

    return score, reasons


def use_case_score(row, use_case):
    score = 0
    reasons = []

    body_type = get_body_type(row)
    transmission = get_transmission(row)
    fuel_type = get_fuel_type(row)

    price = safe_num(row.get("Ex-Showroom_Price"), 0)
    mileage = safe_num(row.get("ARAI_Certified_Mileage"), 0)
    power = safe_num(row.get("Power"), 0)
    torque = safe_num(row.get("Torque"), 0)
    seats = safe_num(row.get("Seating_Capacity"), 0)

    model_name = str(row.get("Model", "")).lower()

    if use_case == "family":
        if seats >= 5:
            score += 6
            reasons.append("suitable seating for family")

        if seats >= 6:
            score += 5
            reasons.append("extra seating capacity")

        if body_type in ["suv", "mpv", "muv", "sedan"]:
            score += 7
            reasons.append("practical family body type")

        if has_airbags(row):
            score += 6
            reasons.append("airbags for safety")

        if has_abs(row):
            score += 5
            reasons.append("ABS for safety")

        if mileage >= 17:
            score += 4
            reasons.append("family-friendly mileage")

        if "nano" in model_name:
            score -= 12
            reasons.append("penalized as too small for family use")

    elif use_case == "parents":
        if transmission == "automatic":
            score += 8
            reasons.append("automatic is easier for parents")

        if has_airbags(row):
            score += 7
            reasons.append("airbags for safety")

        if has_abs(row):
            score += 6
            reasons.append("ABS for safety")

        if body_type in ["hatchback", "sedan", "suv"]:
            score += 4
            reasons.append("practical body type for parents")

        if "nano" in model_name:
            score -= 10
            reasons.append("penalized as too basic for parents")

    elif use_case == "highway":
        if body_type in ["suv", "sedan"]:
            score += 7
            reasons.append("good highway body type")

        if power >= 90:
            score += 7
            reasons.append("adequate highway power")

        if torque >= 180:
            score += 5
            reasons.append("good torque for highway use")

        if has_abs(row):
            score += 5
            reasons.append("ABS useful for highway safety")

        if has_airbags(row):
            score += 5
            reasons.append("airbags useful for highway safety")

        if has_feature(row, "Cruise_Control"):
            score += 4
            reasons.append("cruise control useful for highway driving")

    elif use_case in ["city", "commute"]:
        if body_type in ["hatchback", "sedan", "suv"]:
            score += 5
            reasons.append("practical for city/commute")

        if transmission == "automatic":
            score += 5
            reasons.append("automatic helps in traffic")

        if mileage >= 17:
            score += 6
            reasons.append("efficient for daily use")

    elif use_case == "student":
        if price > 0:
            score += 5

        if mileage >= 18:
            score += 8
            reasons.append("student-friendly mileage")

        if body_type in ["hatchback", "sedan"]:
            score += 5
            reasons.append("student-friendly body type")

        if fuel_type in ["petrol", "cng"]:
            score += 4
            reasons.append("practical fuel choice")

    elif use_case == "budget":
        if mileage >= 18:
            score += 8
            reasons.append("good mileage for budget buyer")

        if fuel_type in ["petrol", "cng", "diesel"]:
            score += 4
            reasons.append("practical budget fuel type")

        if body_type in ["hatchback", "sedan"]:
            score += 5
            reasons.append("budget-friendly body type")

    elif use_case == "premium":
        if has_feature(row, "Sunroof"):
            score += 5
            reasons.append("sunroof adds premium feel")

        if has_feature(row, "Android_Auto"):
            score += 4
            reasons.append("has Android Auto")

        if has_feature(row, "Apple_CarPlay"):
            score += 4
            reasons.append("has Apple CarPlay")

        if has_feature(row, "Cruise_Control"):
            score += 4
            reasons.append("has cruise control")

        if body_type in ["suv", "sedan"]:
            score += 5
            reasons.append("premium body type")

    elif use_case == "enthusiast":
        if power >= 100:
            score += 10
            reasons.append("strong power output")

        if torque >= 180:
            score += 7
            reasons.append("strong torque output")

        if body_type in ["sedan", "suv", "sports", "coupe"]:
            score += 5
            reasons.append("enthusiast-friendly body type")

    return score, reasons


def explicit_filter_score(row, filters):
    score = 0
    reasons = []

    for col, value in filters.items():
        if col in row.index and col not in [
            "Ex-Showroom_Price",
            "ARAI_Certified_Mileage",
            "Displacement",
            "Power"
        ]:
            if safe_num(row[col], 0) == safe_num(value, -999):
                score += 5
                reasons.append(f"matches {col}")

    return score, reasons


def rank_single_car(row, filters, intent):
    use_case = "general"

    if intent and intent.get("use_case"):
        use_case = intent.get("use_case")

    total_score = 0
    all_reasons = []

    score, reasons = price_score(row, filters, use_case)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = mileage_score(row, filters, use_case)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = feature_match_score(row, filters)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = use_case_score(row, use_case)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = explicit_filter_score(row, filters)
    total_score += score
    all_reasons.extend(reasons)

    make_name = str(row.get("Make", "")).lower()

    if make_name == "unknown":
        total_score -= 15
        all_reasons.append("penalized unknown make")

    return total_score, all_reasons


def rank_cars(filtered_df, filters, intent=None, top_n=20):
    ranked_df = filtered_df.copy()

    scores = []
    reasons_list = []

    for _, row in ranked_df.iterrows():
        score, reasons = rank_single_car(row, filters, intent)
        scores.append(score)
        reasons_list.append(reasons[:5])

    ranked_df["ranking_score"] = scores
    ranked_df["match_reasons"] = reasons_list

    ranked_df = ranked_df.sort_values(
        by="ranking_score",
        ascending=False
    )

    return ranked_df.head(top_n)