import os

import pandas as pd

from utils import preprocess_user_input, filter_cars
from ml_parser.ml_intent_parser import preprocess_user_input_ml
from ranking_engine import rank_cars


def safe_slug(value):
    if value is None:
        return "unknown"

    try:
        if pd.isna(value):
            return "unknown"
    except Exception:
        pass

    return str(value).lower().replace(" ", "-")


def format_cardekho_url(make, model):
    return f"https://www.cardekho.com/{safe_slug(make)}/{safe_slug(model)}"


def format_carwale_url(make, model):
    return f"https://www.carwale.com/{safe_slug(make)}-cars/{safe_slug(model)}"


def normalize_column_name(value):
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


def apply_hard_feature_filters(filtered_df, filters):
    """
    Applies strict filters for explicitly requested hard features.
    If the dataset does not contain a reliable column for the requested feature,
    we return it as unsupported instead of pretending.
    """

    unsupported_features = []

    unsupported_hard_features = {
        "Sunroof",
        "Ventilated_Seats"
    }

    supported_hard_feature_keywords = {
        "Airbags": [
            "airbag",
            "airbags",
            "numberofairbags"
        ],
        "ABS_(Anti-lock_Braking_System)": [
            "abs",
            "antilock",
            "antilockbrakingsystem"
        ],
        "Cruise_Control": [
            "cruisecontrol"
        ],
        "Android_Auto": [
            "androidauto"
        ],
        "Apple_CarPlay": [
            "applecarplay",
            "carplay"
        ]
    }

    for filter_name in unsupported_hard_features:
        if filters.get(filter_name) == 1:
            print(f"⚠️ Requested feature not available in dataset: {filter_name}")
            unsupported_features.append(filter_name)

    for filter_name, keywords in supported_hard_feature_keywords.items():
        if filters.get(filter_name) == 1:
            matching_cols = []

            for col in filtered_df.columns:
                normalized_col = normalize_column_name(col)

                if any(normalize_column_name(keyword) in normalized_col for keyword in keywords):
                    matching_cols.append(col)

            print(f"🔒 Hard filter requested: {filter_name}")
            print(f"🔎 Matching columns found for {filter_name}:", matching_cols)

            if matching_cols:
                before_shape = filtered_df.shape

                feature_values = (
                    filtered_df[matching_cols]
                    .apply(pd.to_numeric, errors="coerce")
                    .fillna(0)
                )

                filtered_df = filtered_df[
                    (feature_values > 0).any(axis=1)
                ]

                print(f"🔒 {filter_name} filter before:", before_shape)
                print(f"🔒 {filter_name} filter after:", filtered_df.shape)

            else:
                print(f"⚠️ Requested feature not available in dataset: {filter_name}")
                unsupported_features.append(filter_name)

    return filtered_df, unsupported_features


def get_new_car_recommendations(
    user_query,
    df,
    categorical_mappings,
    app_root_path,
    make_json_safe
):
    print("🔎 Received new-car query:", user_query)

    # =========================
    # Parser: ML first, regex fallback
    # =========================

    try:
        parser_result = preprocess_user_input_ml(user_query)
        filters = parser_result["filters"]

        print("🧠 Parser used:", parser_result["parser_used"])
        print("🧾 ML intent:", parser_result["intent"])
        print("🔎 Final filters:", filters)

    except Exception as e:
        print("⚠️ ML parser failed, using regex fallback:", e)

        filters = preprocess_user_input(user_query)

        parser_result = {
            "parser_used": "regex_fallback",
            "intent": None
        }

        print("🔎 Regex fallback filters:", filters)

    # =========================
    # Mappings
    # =========================

    make_mapping = categorical_mappings["make_mapping"]
    reverse_make_mapping = categorical_mappings["reverse_make_mapping"]
    reverse_model_mapping = categorical_mappings["reverse_model_mapping"]
    reverse_variant_mapping = categorical_mappings["reverse_variant_mapping"]

    # =========================
    # Filter Dataset
    # =========================

    filtered_df = filter_cars(
        df,
        filters,
        make_mapping=make_mapping,
        reverse_make_mapping=reverse_make_mapping,
        reverse_model_mapping=reverse_model_mapping,
        reverse_variant_mapping=reverse_variant_mapping
    )

    # =========================
    # Hard Feature Filters
    # =========================

    filtered_df, unsupported_features = apply_hard_feature_filters(
        filtered_df,
        filters
    )

    if unsupported_features:
        return {
            "parser_used": parser_result["parser_used"],
            "intent": make_json_safe(parser_result["intent"]),
            "filters": make_json_safe(filters),
            "recommendations": [],
            "message": (
                "Your query requested "
                + ", ".join(unsupported_features)
                + ", but this dataset does not contain reliable information for that feature. "
                + "Please remove that feature or update the dataset with this column."
            )
        }

    if filtered_df.empty:
        return {
            "parser_used": parser_result["parser_used"],
            "intent": make_json_safe(parser_result["intent"]),
            "filters": make_json_safe(filters),
            "recommendations": [],
            "message": "No cars found matching your query."
        }

    filtered_df = filtered_df.copy()

    # =========================
    # Ranking Engine
    # =========================

    ranked_df = rank_cars(
        filtered_df=filtered_df,
        filters=filters,
        intent=parser_result.get("intent"),
        top_n=20
    )

    selected_cars = []
    make_count = {}

    max_recommendations = 10
    max_per_make = 2
    total_printed = 0

    for _, car in ranked_df.iterrows():
        if total_printed >= max_recommendations:
            break

        make_name = car["Make"]

        if make_count.get(make_name, 0) >= max_per_make:
            continue

        make_count[make_name] = make_count.get(make_name, 0) + 1

        selected_cars.append(car.to_dict())
        total_printed += 1

    # =========================
    # Format Output Cars
    # =========================

    for car in selected_cars:
        car["Transmission"] = "Not specified"

        for key in car:
            if key.startswith("Transmission_") and car[key] == 1:
                car["Transmission"] = (
                    key.replace("Transmission_", "")
                    .replace("_", " ")
                    .title()
                )

        car["Fuel_Type"] = "Not specified"

        for key in car:
            if key.startswith("Fuel_Type_") and car[key] == 1:
                car["Fuel_Type"] = (
                    key.replace("Fuel_Type_", "")
                    .replace("_", " ")
                    .title()
                )

        car["carDekhoLink"] = format_cardekho_url(
            car.get("Make"),
            car.get("Model")
        )

        car["carWaleLink"] = format_carwale_url(
            car.get("Make"),
            car.get("Model")
        )

        image_filename = (
            f"{str(car.get('Make')).lower().replace(' ', '_')}_"
            f"{str(car.get('Model')).lower().replace(' ', '_')}.jpg"
        )

        image_path = os.path.join(
            app_root_path,
            "static",
            "car_images",
            image_filename
        )

        if os.path.exists(image_path):
            car["carImage"] = f"/static/car_images/{image_filename}"
        else:
            car["carImage"] = "/static/car_images/pic1.avif"

    # =========================
    # Remove Duplicate Models + Clean Frontend Response
    # =========================

    unique_models = {}

    for car in selected_cars:
        model_name = car.get("Model")

        if model_name not in unique_models:
            clean_car = {
                "Make": make_json_safe(car.get("Make")),
                "Model": make_json_safe(car.get("Model")),
                "Variant": make_json_safe(car.get("Variant")),
                "Ex-Showroom_Price": make_json_safe(car.get("Ex-Showroom_Price")),
                "Displacement": make_json_safe(car.get("Displacement")),
                "Power": make_json_safe(car.get("Power")),
                "ARAI_Certified_Mileage": make_json_safe(car.get("ARAI_Certified_Mileage")),
                "Transmission": make_json_safe(car.get("Transmission")),
                "Fuel_Type": make_json_safe(car.get("Fuel_Type")),
                "carImage": make_json_safe(car.get("carImage")),
                "carDekhoLink": make_json_safe(car.get("carDekhoLink")),
                "carWaleLink": make_json_safe(car.get("carWaleLink")),
                "ranking_score": make_json_safe(car.get("ranking_score")),
                "match_reasons": make_json_safe(car.get("match_reasons")),
            }

            unique_models[model_name] = clean_car

    recommendations = list(unique_models.values())[:4]

    print("✅ Returning recommendations:", len(recommendations))

    for rec in recommendations:
        print(
            rec.get("Make"),
            rec.get("Model"),
            rec.get("Variant"),
            rec.get("ranking_score")
        )

    return {
        "parser_used": parser_result["parser_used"],
        "intent": make_json_safe(parser_result["intent"]),
        "filters": make_json_safe(filters),
        "recommendations": recommendations
    }
