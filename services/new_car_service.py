import os

import pandas as pd

from utils import preprocess_user_input, filter_cars
from ml_parser.ml_intent_parser import preprocess_user_input_ml
from ranking_engine import rank_cars
from services.catalogue import get_catalogue, get_meta
from services.filter_v2 import FEATURE_COLUMNS, MIN_COLUMNS, UNRATED_SAFETY_LABEL, filter_candidates
from services.intent_v2 import parse_intent
from services.ranking_adapter import rank_candidates
from services.twins import complete_twin_pairs

# "kb" (default): KB catalogue + intent_v2 + filter_v2. "legacy": processed_dataset.csv path.
DEFAULT_DATA_SOURCE = "kb"
MAX_KB_MODELS = 8
MAX_KB_MODELS_PER_MAKE = 2  # same diversity rule as the legacy path, at model level
MAX_RELAXATION_HINTS = 3

TRANSMISSION_LABELS = {
    "manual": "Manual",
    "imt": "Manual (iMT, clutchless)",
    "amt": "Automatic (AMT)",
    "dct": "Automatic (DCT)",
    "cvt": "Automatic (CVT)",
    "e_cvt": "Automatic (e-CVT)",
    "torque_converter": "Automatic (torque converter)",
    "single_speed_ev": "Automatic (single-speed EV)",
}


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
    data_source = os.environ.get("DATA_SOURCE", DEFAULT_DATA_SOURCE).strip().lower()

    if data_source == "legacy":
        return get_legacy_recommendations(user_query, df, categorical_mappings, app_root_path, make_json_safe)

    if data_source != "kb":
        raise ValueError(f"DATA_SOURCE must be 'kb' or 'legacy', got {data_source!r}")

    return get_kb_recommendations(user_query, app_root_path, make_json_safe)


def find_car_image(app_root_path, make, model):
    """make_model.jpg as before; then the hyphenated model name used by most files on disk."""
    make_part = str(make).lower().replace(" ", "_")
    model_part = str(model).lower()

    for image_filename in (
        f"{make_part}_{model_part.replace(' ', '_')}.jpg",
        f"{make_part}_{model_part.replace(' ', '-')}.jpg",
    ):
        if os.path.exists(os.path.join(app_root_path, "static", "car_images", image_filename)):
            return f"/static/car_images/{image_filename}"

    return "/static/car_images/pic1.avif"


def data_as_of():
    meta = get_meta()
    return {
        "exported": meta["export_utc"][:10],
        "kb_phase": meta["kb_latest_phase"],
    }


def safety_summary(car):
    if pd.isna(car["safety_stars_adult"]):
        return None

    return {
        "stars_adult": int(car["safety_stars_adult"]),
        "stars_child": None if pd.isna(car["safety_stars_child"]) else int(car["safety_stars_child"]),
        "testing_body": car["safety_testing_body"],
        "year": None if pd.isna(car["safety_test_year"]) else int(car["safety_test_year"]),
    }


def select_models(ranked, intent):
    """Best variant per model, max per make, up to MAX_KB_MODELS models.

    Each twin pair (services/twins.py) with both models selected raises the limit by one.
    """
    per_make_cap = None if (intent["makes"] or intent["models"]) else MAX_KB_MODELS_PER_MAKE

    selected = []
    seen_models = set()
    make_count = {}

    for _, car in ranked.iterrows():
        limit = MAX_KB_MODELS + complete_twin_pairs([(c["make"], c["model"]) for c in selected])
        if len(selected) >= limit:
            break

        if car["model"] in seen_models:
            continue

        if per_make_cap is not None and make_count.get(car["make"], 0) >= per_make_cap:
            continue

        seen_models.add(car["model"])
        make_count[car["make"]] = make_count.get(car["make"], 0) + 1
        selected.append(car)

    return selected


def _transmission_label(transmission):
    if transmission["include_types"]:
        names = sorted({TRANSMISSION_LABELS[t].split("(")[-1].rstrip(")") if "(" in TRANSMISSION_LABELS[t]
                        else TRANSMISSION_LABELS[t] for t in transmission["include_types"]})
        label = " / ".join(names) + " transmission"
    elif transmission["family"]:
        label = f"{transmission['family']} transmission"
    else:
        label = "transmission preference"
    if transmission["exclude_types"]:
        label += " (excluding " + ", ".join(t.upper() for t in transmission["exclude_types"]) + ")"
    return label


def _rupees(value):
    return f"₹{value / 100000:g} lakh"


def relaxable_constraints(intent):
    """(human label, intent with only that constraint dropped) for every active constraint."""
    def without(**changes):
        relaxed = dict(intent)
        relaxed.update(changes)
        return relaxed

    options = []
    budget = intent["budget"]
    if budget["min"] is not None or budget["max"] is not None:
        if budget["min"] is not None and budget["max"] is not None:
            label = f"budget {_rupees(budget['min'])}–{_rupees(budget['max'])}"
        elif budget["max"] is not None:
            label = f"budget under {_rupees(budget['max'])}"
        else:
            label = f"budget above {_rupees(budget['min'])}"
        options.append((label, without(budget={"min": None, "max": None})))
    if intent["body_types"]:
        options.append((" / ".join(intent["body_types"]).upper().replace("HATCHBACK", "hatchback")
                        .replace("SEDAN", "sedan").replace("PICKUP", "pickup").replace("VAN", "van")
                        + " body type", without(body_types=[], reference_models=[])))
    if intent["exclude_body_types"]:
        options.append(("excluding " + ", ".join(intent["exclude_body_types"]), without(exclude_body_types=[])))
    if intent["fuel_types"]:
        options.append((" / ".join(intent["fuel_types"]) + " fuel", without(fuel_types=[])))
    if intent["exclude_fuel_types"]:
        options.append(("excluding " + ", ".join(intent["exclude_fuel_types"]), without(exclude_fuel_types=[])))
    transmission = intent["transmission"]
    if transmission["family"] or transmission["include_types"] or transmission["exclude_types"]:
        options.append((_transmission_label(transmission),
                        without(transmission={"family": None, "include_types": [], "exclude_types": []})))
    if intent["seats_min"] is not None:
        options.append((f"{intent['seats_min']}+ seats", without(seats_min=None)))
    if intent["makes"]:
        options.append((" / ".join(intent["makes"]), without(makes=[])))
    if intent["models"]:
        options.append((" / ".join(intent["models"]), without(models=[])))
    if intent["reference_models"]:
        options.append(("similar to " + ", ".join(intent["reference_models"]), without(reference_models=[])))
    for feature in intent["required_features"]:
        options.append((FEATURE_COLUMNS[feature][1],
                        without(required_features=[f for f in intent["required_features"] if f != feature])))
    for key, (_, label) in MIN_COLUMNS.items():
        if intent[key] is not None:
            options.append((f"minimum {label} {intent[key]:g}", without(**{key: None})))
    if intent["min_safety_stars"] is not None:
        options.append((f"{intent['min_safety_stars']}-star safety", without(min_safety_stars=None)))
    return options


def relaxation_hints(intent):
    """For an empty result: how many models each single dropped constraint would bring back."""
    hints = []
    for label, relaxed in relaxable_constraints(intent):
        ranked, _ = rank_candidates(relaxed, filter_candidates(relaxed, get_catalogue()))
        if ranked.empty:
            continue
        models = list(dict.fromkeys(ranked["model"]))
        hints.append({"drop": label, "would_return": len(models), "top_models": models[:3]})

    hints.sort(key=lambda h: -h["would_return"])
    return hints[:MAX_RELAXATION_HINTS]


def get_kb_recommendations(user_query, app_root_path, make_json_safe):
    print("🔎 Received new-car query (kb):", user_query)

    intent = parse_intent(user_query)
    candidates = filter_candidates(intent, get_catalogue())
    ranked, filters = rank_candidates(intent, candidates)

    print("🧾 intent_v2:", {k: v for k, v in intent.items() if k != "trace"})
    print("🔎 Candidates after filter_v2:", len(candidates))

    response = {
        "parser_used": "intent_v2",
        "intent": make_json_safe(intent),
        "filters": make_json_safe(filters),
        "recommendations": [],
        "data_as_of": data_as_of(),
        "unsupported_terms": intent["unsupported_terms"],
    }

    unsupported_note = ""
    if intent["unsupported_terms"]:
        unsupported_note = (
            ", ".join(intent["unsupported_terms"])
            + " isn't in our catalogue, so that part of your query was ignored."
        )

    if ranked.empty:
        response["message"] = " ".join(filter(None, [unsupported_note, "No cars match all your requirements."]))
        # separate from recommendations: the result stays empty
        response["relaxation_hints"] = relaxation_hints(intent)
        return response

    variant_counts = candidates["model"].value_counts()
    selected = select_models(ranked, intent)

    recommendations = []

    for car in selected:
        unverified = list(car["unverified"])
        if car["unrated_safety"]:
            unverified.append(UNRATED_SAFETY_LABEL)

        recommendations.append({
            # existing response keys (same names and types as the legacy path)
            "Make": make_json_safe(car["make"]),
            "Model": make_json_safe(car["model"]),
            "Variant": make_json_safe(car["variant"]),
            "Ex-Showroom_Price": make_json_safe(car["price_ex_showroom"]),
            "Displacement": make_json_safe(car["engine_cc"]),
            "Power": make_json_safe(car["power_bhp"]),
            "ARAI_Certified_Mileage": make_json_safe(car["mileage_kmpl"]),
            "Transmission": car["transmission_family"].title(),
            "Fuel_Type": make_json_safe(car["fuel_raw"]),
            "carImage": find_car_image(app_root_path, car["make"], car["model"]),
            "carDekhoLink": format_cardekho_url(car["make"], car["model"]),
            "carWaleLink": format_carwale_url(car["make"], car["model"]),
            "ranking_score": make_json_safe(car["ranking_score"]),
            "match_reasons": make_json_safe(car["match_reasons"]),
            # added by the kb path
            "transmission_type": car["transmission_type"],
            "transmission_label": TRANSMISSION_LABELS[car["transmission_type"]],
            "matched_features": [m for m in car["matched"] if m in FEATURE_COLUMNS],
            "unverified": unverified,
            "safety": safety_summary(car),
            "matching_variant_count": int(variant_counts[car["model"]]),
        })

    response["recommendations"] = recommendations
    if unsupported_note:
        response["message"] = unsupported_note + " Showing the closest matches."

    print("✅ Returning recommendations (kb):", len(recommendations))
    return response


def get_legacy_recommendations(
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
