import numpy as np
import pandas as pd


# =========================
# Column Mappings
# =========================

BODY_TYPE_COLUMNS = {
    "suv": "Body_Type_SUV",
    "sedan": "Body_Type_Sedan",
    "hatchback": "Body_Type_Hatchback",
    "mpv": "Body_Type_MPV",
    "muv": "Body_Type_MUV",
    "coupe": "Body_Type_Coupe",
    "sports": "Body_Type_Sports"
}


FUEL_TYPE_COLUMNS = {
    "petrol": "Fuel_Type_Petrol",
    "diesel": "Fuel_Type_Diesel",
    "cng": "Fuel_Type_CNG",
    "electric": "Fuel_Type_Electric",
    "hybrid": "Fuel_Type_Hybrid"
}


# =========================
# Safe Helpers
# =========================

def safe_num(value, default=0.0):
    try:
        value = float(value)

        if np.isnan(value) or np.isinf(value):
            return default

        return value

    except Exception:
        return default


def normalize_text(value):
    return (
        str(value)
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "")
    )


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
    for fuel_type, col in FUEL_TYPE_COLUMNS.items():
        if has_column_value(row, col):
            return fuel_type

    return "unknown"


def has_airbags(row):
    if "Airbags" in row.index:
        return safe_num(row["Airbags"], 0) > 0

    for col in row.index:
        lowered = col.lower()

        if "airbag" in lowered and safe_num(row[col], 0) > 0:
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

    normalized_feature = normalize_text(feature_name)

    feature_aliases = {
        "sunroof": [
            "sunroof",
            "sunroofs",
            "sunroofmoonroof",
            "panoramicroof",
            "moonroof"
        ],
        "ventilatedseats": [
            "ventilatedseats",
            "ventilatedseat",
            "seatventilation",
            "cooledseats",
            "coolingseats"
        ],
        "cruisecontrol": [
            "cruisecontrol"
        ],
        "androidauto": [
            "androidauto"
        ],
        "applecarplay": [
            "applecarplay",
            "carplay"
        ]
    }

    patterns = feature_aliases.get(normalized_feature, [normalized_feature])

    for col in row.index:
        normalized_col = normalize_text(col)

        if any(pattern in normalized_col for pattern in patterns):
            if safe_num(row[col], 0) > 0:
                return True

    return False


def get_requested_budget(filters):
    price_filter = filters.get("Ex-Showroom_Price")

    if price_filter is None:
        return None, None

    if isinstance(price_filter, list) and len(price_filter) == 2:
        return price_filter[0], price_filter[1]

    return None, price_filter


# =========================
# Score Components
# =========================

def price_score(row, filters, use_case):
    price = safe_num(row.get("Ex-Showroom_Price"), 0)
    price_min, price_max = get_requested_budget(filters)

    reasons = []

    if price <= 0:
        return 0, reasons

    if price_max is None:
        return 0, reasons

    if price > price_max:
        return -100, ["over budget"]

    if use_case in ["budget", "student"]:
        target_price = price_max * 0.55

    elif use_case == "premium":
        target_price = price_max * 0.92

    elif use_case in ["highway", "enthusiast"]:
        target_price = price_max * 0.88

    elif use_case in ["family", "parents"]:
        target_price = price_max * 0.78

    else:
        target_price = price_max * 0.70

    closeness = 1 - abs(price - target_price) / max(price_max, 1)
    score = max(0, closeness) * 40

    reasons.append("within budget")

    budget_utilization = price / price_max

    if use_case == "premium":
        if 0.75 <= budget_utilization <= 0.98:
            score += 18
            reasons.append("uses premium budget well")

        elif budget_utilization < 0.60:
            score -= 22
            reasons.append("penalized for underusing premium budget")

    elif use_case in ["highway", "enthusiast"]:
        if 0.70 <= budget_utilization <= 0.98:
            score += 12
            reasons.append("uses budget well for performance use")

    elif use_case in ["family", "parents"]:
        if 0.60 <= budget_utilization <= 0.95:
            score += 6
            reasons.append("uses budget well for practical use")

    if use_case in ["family", "parents", "highway", "premium"] and price < price_max * 0.40:
        score -= 12
        reasons.append("penalized for being too basic for this use-case")

    return score, reasons


def mileage_score(row, filters, use_case):
    mileage = safe_num(row.get("ARAI_Certified_Mileage"), 0)

    reasons = []

    if mileage <= 0:
        return 0, reasons

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
        "Ventilated_Seats": "ventilated seats",
        "Cruise_Control": "cruise control",
        "Android_Auto": "Android Auto",
        "Apple_CarPlay": "Apple CarPlay",
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
                if filter_col in ["Sunroof", "Ventilated_Seats"]:
                    score += 15
                else:
                    score += 8

                reasons.append(f"has {label}")

            else:
                if filter_col in ["Sunroof", "Ventilated_Seats"]:
                    score -= 50
                else:
                    score -= 10

                reasons.append(f"missing requested {label}")

    return score, reasons


def fuel_match_score(row, filters):
    score = 0
    reasons = []

    for fuel_type, col in FUEL_TYPE_COLUMNS.items():
        if filters.get(col) == 1:
            if has_column_value(row, col):
                score += 12
                reasons.append(f"matches requested {fuel_type} fuel")
            else:
                score -= 8
                reasons.append(f"does not match requested {fuel_type} fuel")

    return score, reasons


def body_type_match_score(row, filters):
    score = 0
    reasons = []

    requested_body_col = filters.get("Body_Type")

    if not requested_body_col:
        return score, reasons

    if requested_body_col in row.index and has_column_value(row, requested_body_col):
        score += 12
        reasons.append("matches requested body type")
    else:
        score -= 8
        reasons.append("does not match requested body type")

    return score, reasons


def transmission_match_score(row, filters):
    score = 0
    reasons = []

    if filters.get("Transmission_Automatic") == 1:
        if has_column_value(row, "Transmission_Automatic"):
            score += 10
            reasons.append("matches automatic preference")
        else:
            score -= 8
            reasons.append("does not match automatic preference")

    if filters.get("Transmission_Manual") == 1:
        if has_column_value(row, "Transmission_Manual"):
            score += 8
            reasons.append("matches manual preference")
        else:
            score -= 6
            reasons.append("does not match manual preference")

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

    # =========================
    # Family
    # =========================

    if use_case == "family":
        if seats >= 5:
            score += 6
            reasons.append("suitable seating for family")

        if seats >= 6:
            score += 7
            reasons.append("extra seating capacity")

        if body_type in ["suv", "mpv", "muv"]:
            score += 12
            reasons.append("very practical family body type")

        elif body_type == "sedan":
            score += 9
            reasons.append("comfortable family sedan")

        elif body_type == "hatchback":
            score += 3
            reasons.append("usable family hatchback")

        if has_airbags(row):
            score += 10
            reasons.append("airbags for safety")

        if has_abs(row):
            score += 8
            reasons.append("ABS for safety")

        if mileage >= 17:
            score += 4
            reasons.append("family-friendly mileage")

        bad_family_models = [
            "nano",
            "redi-go",
            "redi go",
            "alto 800",
            "eon",
            "kwid",
            "qute"
        ]

        if any(bad_model in model_name for bad_model in bad_family_models):
            score -= 18
            reasons.append("penalized as too small/basic for family use")

    # =========================
    # Parents
    # =========================

    elif use_case == "parents":
        if transmission == "automatic":
            score += 12
            reasons.append("automatic is easier for parents")

        if has_airbags(row):
            score += 10
            reasons.append("airbags for safety")

        if has_abs(row):
            score += 8
            reasons.append("ABS for safety")

        if body_type in ["hatchback", "sedan", "suv"]:
            score += 5
            reasons.append("practical body type for parents")

        if mileage >= 14:
            score += 3
            reasons.append("reasonable mileage for parents")

        bad_parent_models = [
            "nano",
            "redi-go",
            "redi go",
            "kwid",
            "eon",
            "re60",
            "qute"
        ]

        if any(bad_model in model_name for bad_model in bad_parent_models):
            score -= 15
            reasons.append("penalized as too basic for parents")

    # =========================
    # Highway
    # =========================

    elif use_case == "highway":
        if body_type in ["suv", "sedan"]:
            score += 10
            reasons.append("good highway body type")

        if power >= 90:
            score += 8
            reasons.append("adequate highway power")

        if power >= 110:
            score += 4
            reasons.append("stronger highway performance")

        if torque >= 180:
            score += 7
            reasons.append("good torque for highway use")

        if fuel_type == "diesel":
            score += 6
            reasons.append("diesel suits highway driving")

        if has_abs(row):
            score += 7
            reasons.append("ABS useful for highway safety")

        if has_airbags(row):
            score += 7
            reasons.append("airbags useful for highway safety")

        if has_feature(row, "Cruise_Control"):
            score += 5
            reasons.append("cruise control useful for highway driving")

        weak_highway_models = [
            "nano",
            "redi-go",
            "redi go",
            "kwid",
            "alto",
            "eon"
        ]

        if any(bad_model in model_name for bad_model in weak_highway_models):
            score -= 20
            reasons.append("penalized as weak for highway use")

    # =========================
    # City / Commute
    # =========================

    elif use_case in ["city", "commute"]:
        if body_type in ["hatchback", "sedan", "suv"]:
            score += 6
            reasons.append("practical for city/commute")

        if transmission == "automatic":
            score += 7
            reasons.append("automatic helps in traffic")

        if mileage >= 17:
            score += 8
            reasons.append("efficient for daily use")

        if price > 0 and price < 1000000:
            score += 3
            reasons.append("reasonable daily-use price")

    # =========================
    # Student
    # =========================

    elif use_case == "student":
        if mileage >= 18:
            score += 10
            reasons.append("student-friendly mileage")

        if body_type in ["hatchback", "sedan"]:
            score += 6
            reasons.append("student-friendly body type")

        if fuel_type in ["petrol", "cng"]:
            score += 5
            reasons.append("practical fuel choice")

        if price > 0 and price < 900000:
            score += 5
            reasons.append("student-friendly price")

    # =========================
    # Budget
    # =========================

    elif use_case == "budget":
        if mileage >= 18:
            score += 10
            reasons.append("good mileage for budget buyer")

        if fuel_type in ["petrol", "cng", "diesel"]:
            score += 5
            reasons.append("practical budget fuel type")

        if body_type in ["hatchback", "sedan"]:
            score += 6
            reasons.append("budget-friendly body type")

    # =========================
    # Premium
    # =========================

    elif use_case == "premium":
        if has_feature(row, "Sunroof"):
            score += 8
            reasons.append("sunroof adds premium feel")

        if has_feature(row, "Ventilated_Seats"):
            score += 10
            reasons.append("ventilated seats add premium comfort")

        if has_feature(row, "Android_Auto"):
            score += 4
            reasons.append("has Android Auto")

        if has_feature(row, "Apple_CarPlay"):
            score += 4
            reasons.append("has Apple CarPlay")

        if has_feature(row, "Cruise_Control"):
            score += 5
            reasons.append("has cruise control")

        if body_type in ["suv", "muv"]:
            score += 10
            reasons.append("premium SUV-like body type")

        elif body_type == "sedan":
            score += 8
            reasons.append("premium sedan body type")

        if power >= 120:
            score += 5
            reasons.append("premium-level power")

    # =========================
    # Enthusiast
    # =========================

    elif use_case == "enthusiast":
        if power >= 100:
            score += 10
            reasons.append("strong power output")

        if torque >= 180:
            score += 8
            reasons.append("strong torque output")

        if body_type in ["sedan", "suv", "sports", "coupe"]:
            score += 6
            reasons.append("enthusiast-friendly body type")

    return score, reasons


def model_quality_adjustment(row, use_case):
    score = 0
    reasons = []

    make_name = str(row.get("Make", "")).lower()
    model_name = str(row.get("Model", "")).lower()

    bad_makes = [
        "unknown",
        "premier",
        "fiat",
        "bajaj"
    ]

    outdated_or_basic_models = [
        "rio",
        "nano",
        "redi-go",
        "redi go",
        "eon",
        "punto",
        "punto evo",
        "qute",
        "re60"
    ]

    if make_name in bad_makes:
        score -= 18
        reasons.append("penalized low-confidence/older make")

    if any(bad_model in model_name for bad_model in outdated_or_basic_models):
        score -= 18
        reasons.append("penalized outdated/basic model")

    family_friendly_models = [
        "ertiga",
        "triber",
        "venue",
        "nexon",
        "xuv300",
        "brezza",
        "amaze",
        "dzire",
        "aspire",
        "xcent",
        "verito",
        "baleno"
    ]

    highway_friendly_models = [
        "venue",
        "nexon",
        "xuv300",
        "creta",
        "seltos",
        "kicks",
        "duster",
        "ecosport",
        "brezza",
        "scorpio",
        "xuv500",
        "harrier",
        "compass"
    ]

    parents_friendly_models = [
        "amaze",
        "dzire",
        "aspire",
        "xcent",
        "yaris",
        "baleno",
        "i20",
        "tiago",
        "venue",
        "nexon"
    ]

    premium_strong_models = [
        "compass",
        "hector",
        "harrier",
        "seltos",
        "creta",
        "xuv500",
        "xuv700",
        "tucson",
        "kodiaq",
        "zs ev",
        "hexa",
        "octavia",
        "passat",
        "a3",
        "civic"
    ]

    premium_weak_models = [
        "brezza",
        "wr-v",
        "terrano",
        "duster",
        "ecosport",
        "kwid",
        "alto",
        "s-presso",
        "redi-go",
        "redi go"
    ]

    if use_case == "family":
        if any(good_model in model_name for good_model in family_friendly_models):
            score += 10
            reasons.append("strong family-friendly model match")

    elif use_case == "highway":
        if any(good_model in model_name for good_model in highway_friendly_models):
            score += 10
            reasons.append("strong highway-friendly model match")

    elif use_case == "parents":
        if any(good_model in model_name for good_model in parents_friendly_models):
            score += 10
            reasons.append("strong parents-friendly model match")

    elif use_case == "premium":
        if any(model in model_name for model in premium_strong_models):
            score += 18
            reasons.append("strong premium model match")

        if any(model in model_name for model in premium_weak_models):
            score -= 14
            reasons.append("penalized as less premium for this query")

    return score, reasons


def explicit_filter_score(row, filters):
    score = 0
    reasons = []

    excluded = [
        "Ex-Showroom_Price",
        "ARAI_Certified_Mileage",
        "Displacement",
        "Power",
        "Torque",
        "Body_Type"
    ]

    for col, value in filters.items():
        if col in row.index and col not in excluded:
            if safe_num(row[col], 0) == safe_num(value, -999):
                score += 5
                reasons.append(f"matches {col}")

    return score, reasons


# =========================
# Main Ranking
# =========================

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

    score, reasons = fuel_match_score(row, filters)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = body_type_match_score(row, filters)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = transmission_match_score(row, filters)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = use_case_score(row, use_case)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = explicit_filter_score(row, filters)
    total_score += score
    all_reasons.extend(reasons)

    score, reasons = model_quality_adjustment(row, use_case)
    total_score += score
    all_reasons.extend(reasons)

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