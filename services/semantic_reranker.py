import numpy as np


SEMANTIC_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_SEMANTIC_MODEL = None
_MODEL_LOAD_ATTEMPTED = False


def _has_value(value):
    if value is None:
        return False

    try:
        if value != value:
            return False
    except Exception:
        pass

    return str(value).strip() != ""


def _clean_value(value):
    if not _has_value(value):
        return ""

    return str(value).strip()


def _safe_get(row, possible_columns):
    for column in possible_columns:
        try:
            value = row.get(column)
        except AttributeError:
            value = row[column] if column in row else None

        if _has_value(value):
            return _clean_value(value)

    return ""


def _safe_num(value, default=0.0):
    try:
        number = float(value)
        if np.isnan(number) or np.isinf(number):
            return default
        return number
    except Exception:
        return default


def _column_enabled(row, possible_columns):
    for column in possible_columns:
        try:
            value = row.get(column)
        except AttributeError:
            value = row[column] if column in row else None

        if _safe_num(value, 0) > 0:
            return True

    return False


def _first_enabled_label(row, label_to_columns):
    for label, columns in label_to_columns.items():
        if _column_enabled(row, columns):
            return label

    return ""


def build_car_semantic_text(row):
    make = _safe_get(row, ["Make", "make", "Manufacturer", "manufacturer"])
    model = _safe_get(row, ["Model", "model", "Car_Name", "car_name", "Name", "name"])
    variant = _safe_get(row, ["Variant", "variant"])

    body_type = _safe_get(row, ["Body_Type", "body_type", "Body Type"])
    if not body_type:
        body_type = _first_enabled_label(row, {
            "SUV": ["Body_Type_SUV"],
            "sedan": ["Body_Type_Sedan"],
            "hatchback": ["Body_Type_Hatchback"],
            "MPV": ["Body_Type_MPV"],
            "MUV": ["Body_Type_MUV"],
            "coupe": ["Body_Type_Coupe"],
            "sports car": ["Body_Type_Sports"],
        })

    fuel_type = _safe_get(row, ["Fuel_Type", "fuel_type", "Fuel Type"])
    if not fuel_type:
        fuel_type = _first_enabled_label(row, {
            "petrol": ["Fuel_Type_Petrol"],
            "diesel": ["Fuel_Type_Diesel"],
            "CNG": ["Fuel_Type_CNG"],
            "electric": ["Fuel_Type_Electric"],
            "hybrid": ["Fuel_Type_Hybrid"],
        })

    transmission = _safe_get(row, ["Transmission", "transmission"])
    if not transmission:
        transmission = _first_enabled_label(row, {
            "automatic": ["Transmission_Automatic"],
            "manual": ["Transmission_Manual"],
        })

    mileage = _safe_get(row, [
        "Mileage",
        "mileage",
        "ARAI_Certified_Mileage",
        "ARAI Certified Mileage",
    ])
    price = _safe_get(row, [
        "Price",
        "price",
        "Ex-Showroom_Price",
        "Ex Showroom Price",
    ])
    seats = _safe_get(row, [
        "Seating_Capacity",
        "Seating Capacity",
        "seating_capacity",
        "Seats",
        "seats",
    ])

    car_name = " ".join(part for part in [make, model, variant] if part)
    if not car_name:
        car_name = "This car"

    description_parts = [car_name]

    attributes = []
    if body_type:
        attributes.append(f"{body_type} body type")
    if fuel_type:
        attributes.append(f"{fuel_type} fuel")
    if transmission:
        attributes.append(f"{transmission} transmission")
    if seats:
        attributes.append(f"{seats} seats")
    if mileage:
        attributes.append(f"{mileage} mileage")
    if price:
        attributes.append(f"priced around {price}")

    if attributes:
        description_parts.append("is a car with " + ", ".join(attributes))

    features = []
    if _column_enabled(row, ["Airbags", "airbags", "Number_of_Airbags"]):
        features.append("airbags")
    if _column_enabled(row, ["ABS_(Anti-lock_Braking_System)", "ABS", "Anti-lock_Braking_System"]):
        features.append("ABS")
    if _column_enabled(row, ["Sunroof", "sunroof"]):
        features.append("sunroof")
    if _column_enabled(row, ["Cruise_Control", "Cruise Control", "cruise_control"]):
        features.append("cruise control")
    if _column_enabled(row, ["Android_Auto", "Android Auto", "android_auto"]):
        features.append("Android Auto")
    if _column_enabled(row, ["Apple_CarPlay", "Apple CarPlay", "apple_carplay"]):
        features.append("Apple CarPlay")

    if features:
        description_parts.append("It includes " + ", ".join(features))

    return ". ".join(description_parts) + "."


def load_semantic_model():
    global _SEMANTIC_MODEL
    global _MODEL_LOAD_ATTEMPTED

    if _SEMANTIC_MODEL is not None:
        return _SEMANTIC_MODEL

    if _MODEL_LOAD_ATTEMPTED:
        return None

    _MODEL_LOAD_ATTEMPTED = True

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        print("Semantic reranker unavailable: sentence_transformers import failed:", e)
        return None

    try:
        _SEMANTIC_MODEL = SentenceTransformer(SEMANTIC_MODEL_NAME)
        return _SEMANTIC_MODEL
    except Exception as e:
        print("Semantic reranker unavailable: model loading failed:", e)
        _SEMANTIC_MODEL = None
        return None


def semantic_rerank(ranked_df, user_query, top_n=20, semantic_weight=0.15):
    """
    Apply a small transformer-based reranking boost after rule-based filtering
    and scoring. This is a reranking layer, not a replacement for hard filters
    or the existing ranking engine.
    """
    if ranked_df is None or ranked_df.empty:
        return ranked_df

    original_top = ranked_df.head(top_n)

    if not user_query or not str(user_query).strip():
        return original_top

    model = load_semantic_model()
    if model is None:
        return original_top

    try:
        reranked_df = ranked_df.copy()
        car_texts = [
            build_car_semantic_text(row)
            for _, row in reranked_df.iterrows()
        ]

        if not car_texts:
            return original_top

        query_embedding = model.encode(
            [str(user_query)],
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0]
        car_embeddings = model.encode(
            car_texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        similarities = np.dot(car_embeddings, query_embedding)
        semantic_scores = ((similarities + 1) / 2) * 100
        reranked_df["semantic_score"] = semantic_scores

        semantic_weight = max(0.0, min(float(semantic_weight), 1.0))

        if "ranking_score" in reranked_df.columns:
            ranking_scores = reranked_df["ranking_score"].apply(_safe_num)
            reranked_df["final_score"] = (
                ((1 - semantic_weight) * ranking_scores)
                + (semantic_weight * reranked_df["semantic_score"])
            )
        else:
            reranked_df["final_score"] = reranked_df["semantic_score"]

        return reranked_df.sort_values(
            by="final_score",
            ascending=False
        ).head(top_n)

    except Exception as e:
        print("Semantic reranking failed; returning rule-ranked results:", e)
        return original_top
