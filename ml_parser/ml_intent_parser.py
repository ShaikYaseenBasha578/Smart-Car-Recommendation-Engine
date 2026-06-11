import os
import re
import joblib


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")


BODY_TYPE_TO_COLUMN = {
    "suv": "Body_Type_SUV",
    "sedan": "Body_Type_Sedan",
    "hatchback": "Body_Type_Hatchback",
    "mpv": "Body_Type_MPV",
    "muv": "Body_Type_MUV",
    "coupe": "Body_Type_Coupe",
    "convertible": "Body_Type_Convertible",
    "pickup": "Body_Type_Pick-up",
    "wagon": "Body_Type_Wagon",
    "crossover": "Body_Type_Crossover",
    "sports": "Body_Type_Sports"
}


MAKE_NORMALIZATION = {
    "tata": "Tata",
    "datsun": "Datsun",
    "renault": "Renault",
    "maruti": "Maruti Suzuki",
    "suzuki": "Maruti Suzuki",
    "maruti suzuki": "Maruti Suzuki",
    "hyundai": "Hyundai",
    "toyota": "Toyota",
    "nissan": "Nissan",
    "volkswagen": "Volkswagen",
    "ford": "Ford",
    "mahindra": "Mahindra",
    "fiat": "Fiat",
    "honda": "Honda",
    "skoda": "Skoda",
    "jeep": "Jeep",
    "mg": "Mg",
    "kia": "Kia",
    "volvo": "Volvo",
    "bmw": "Bmw",
    "audi": "Audi",
    "land rover": "Land Rover",
    "lexus": "Lexus",
    "jaguar": "Jaguar",
    "porsche": "Porsche",
    "maserati": "Maserati",
    "lamborghini": "Lamborghini",
    "bentley": "Bentley",
    "ferrari": "Ferrari",
    "aston martin": "Aston Martin",
    "isuzu": "Isuzu"
}


def load_model(name):
    path = os.path.join(MODEL_DIR, f"{name}_model.pkl")

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing model: {path}. Run python ml_parser/train_parser.py first."
        )

    return joblib.load(path)


class MLIntentParser:
    def __init__(self):
        self.body_type_model = load_model("body_type")
        self.fuel_type_model = load_model("fuel_type")
        self.transmission_model = load_model("transmission")
        self.use_case_model = load_model("use_case")

    # =========================
    # Rule-Based Exact Extractors
    # =========================

    def extract_exact_body_type(self, query):
        q = query.lower()

        body_keywords = {
            "suv": ["suv", "compact suv"],
            "sedan": ["sedan"],
            "hatchback": ["hatchback"],
            "mpv": ["mpv"],
            "muv": ["muv"],
            "coupe": ["coupe"],
            "convertible": ["convertible"],
            "pickup": ["pickup", "pick-up"],
            "wagon": ["wagon"],
            "crossover": ["crossover"],
            "sports": ["sports car", "sporty car"]
        }

        for body_type, keywords in body_keywords.items():
            for keyword in keywords:
                if re.search(r"\b" + re.escape(keyword) + r"\b", q):
                    return body_type

        return None

    def extract_exact_fuel_type(self, query):
        q = query.lower()

        fuel_keywords = {
            "diesel": ["diesel"],
            "petrol": ["petrol", "gasoline"],
            "cng": ["cng"],
            "electric": ["electric", "ev"],
            "hybrid": ["hybrid"]
        }

        for fuel_type, keywords in fuel_keywords.items():
            for keyword in keywords:
                if re.search(r"\b" + re.escape(keyword) + r"\b", q):
                    return fuel_type

        return None

    def extract_exact_transmission(self, query):
        q = query.lower()

        has_automatic = re.search(r"\b(automatic|amt|cvt|dct|auto)\b", q)
        has_manual = re.search(r"\bmanual\b", q)

        if has_automatic and not has_manual:
            return "automatic"

        if has_manual and not has_automatic:
            return "manual"

        return None

    def extract_exact_use_case(self, query):
        q = query.lower()

        if any(word in q for word in ["premium", "luxury", "luxurious"]):
            return "premium"

        if any(word in q for word in ["family", "families", "large family", "big family"]):
            return "family"

        if any(word in q for word in ["parents", "elderly", "senior"]):
            return "parents"

        if any(word in q for word in ["highway", "long drive", "long drives", "road trip", "touring"]):
            return "highway"

        if any(word in q for word in ["student", "college"]):
            return "student"

        if any(word in q for word in ["budget", "cheap", "affordable", "low cost"]):
            return "budget"

        if any(word in q for word in ["city", "traffic", "commute", "daily use", "daily city"]):
            return "city"

        if any(word in q for word in ["enthusiast", "performance", "sporty", "fun to drive"]):
            return "enthusiast"

        return None

    # =========================
    # Rule-Based Numeric Extractors
    # =========================

    def extract_price(self, query):
        query = query.lower()

        range_match = re.search(
            r"(\d+)\s*to\s*(\d+)\s*(lakh|lakhs|cr|crore)?",
            query
        )

        if range_match:
            min_val = int(range_match.group(1))
            max_val = int(range_match.group(2))
            unit = range_match.group(3) or "lakh"

            multiplier = 10000000 if unit in ["cr", "crore"] else 100000

            return {
                "price_min": min_val * multiplier,
                "price_max": max_val * multiplier
            }

        under_match = re.search(
            r"(under|below|less than|max|maximum|upto|up to)\s*(\d+)\s*(lakh|lakhs|cr|crore)?",
            query
        )

        if under_match:
            val = int(under_match.group(2))
            unit = under_match.group(3) or "lakh"

            multiplier = 10000000 if unit in ["cr", "crore"] else 100000

            return {
                "price_min": None,
                "price_max": val * multiplier
            }

        above_match = re.search(
            r"(above|over|more than|min|minimum)\s*(\d+)\s*(lakh|lakhs|cr|crore)?",
            query
        )

        if above_match:
            val = int(above_match.group(2))
            unit = above_match.group(3) or "lakh"

            multiplier = 10000000 if unit in ["cr", "crore"] else 100000

            return {
                "price_min": val * multiplier,
                "price_max": None
            }

        return {
            "price_min": None,
            "price_max": None
        }

    def extract_seating_capacity(self, query):
        q = query.lower()

        match = re.search(r"(\d+)[- ]?seater", q)

        if match:
            return int(match.group(1))

        if "large family" in q or "big family" in q:
            return 7

        return None

    def extract_mileage(self, query):
        query = query.lower()

        range_match = re.search(r"(\d+)\s*to\s*(\d+)\s*kmpl", query)

        if range_match:
            return [int(range_match.group(1)), int(range_match.group(2))]

        min_match = re.search(
            r"(above|more than|at least|min|minimum)\s*(\d+)\s*kmpl",
            query
        )

        if min_match:
            return [int(min_match.group(2)), float("inf")]

        max_match = re.search(
            r"(under|below|less than|max|maximum)\s*(\d+)\s*kmpl",
            query
        )

        if max_match:
            return [0, int(max_match.group(2))]

        if (
            "good mileage" in query
            or "fuel efficient" in query
            or "high mileage" in query
        ):
            return [18, float("inf")]

        return None

    def extract_features(self, query):
        q = query.lower()

        feature_keywords = {
            "Sunroof": [
                "sunroof",
                "sun roof",
                "panoramic roof",
                "moonroof",
                "moon roof"
            ],
            "Ventilated_Seats": [
                "ventilated seats",
                "ventilated seat",
                "ventilated front seats",
                "seat ventilation",
                "cooled seats",
                "cooled seat",
                "cooling seats"
            ],
            "Airbags": [
                "airbag",
                "airbags",
                "safety airbags"
            ],
            "ABS_(Anti-lock_Braking_System)": [
                "abs",
                "anti-lock",
                "anti lock",
                "anti-lock braking system",
                "anti lock braking system"
            ],
            "Cruise_Control": [
                "cruise control"
            ],
            "Android_Auto": [
                "android auto"
            ],
            "Apple_CarPlay": [
                "apple carplay",
                "carplay"
            ]
        }

        features = {
            "Sunroof": 0,
            "Ventilated_Seats": 0,
            "Airbags": 0,
            "ABS_(Anti-lock_Braking_System)": 0,
            "Cruise_Control": 0,
            "Android_Auto": 0,
            "Apple_CarPlay": 0
        }

        for feature_name, keywords in feature_keywords.items():
            for keyword in keywords:
                if re.search(r"\b" + re.escape(keyword) + r"\b", q):
                    features[feature_name] = 1
                    break

        return features

    def extract_makes(self, query):
        q = query.lower()
        found = []

        for raw_make, normalized_make in MAKE_NORMALIZATION.items():
            pattern = r"\b" + re.escape(raw_make) + r"\b"

            if re.search(pattern, q):
                found.append(normalized_make)

        return list(dict.fromkeys(found))

    # =========================
    # ML Prediction + Hybrid Intent
    # =========================

    def predict_label(self, model, query):
        prediction = model.predict([query])[0]
        return prediction

    def parse_to_intent(self, query):
        # ML predictions
        body_type = self.predict_label(self.body_type_model, query)
        fuel_type = self.predict_label(self.fuel_type_model, query)
        transmission = self.predict_label(self.transmission_model, query)
        use_case = self.predict_label(self.use_case_model, query)

        # Exact rule-based overrides
        exact_body_type = self.extract_exact_body_type(query)
        exact_fuel_type = self.extract_exact_fuel_type(query)
        exact_transmission = self.extract_exact_transmission(query)
        exact_use_case = self.extract_exact_use_case(query)

        if exact_body_type is not None:
            body_type = exact_body_type

        if exact_fuel_type is not None:
            fuel_type = exact_fuel_type

        if exact_transmission is not None:
            transmission = exact_transmission

        if exact_use_case is not None:
            use_case = exact_use_case

        price = self.extract_price(query)
        seating_capacity = self.extract_seating_capacity(query)
        mileage = self.extract_mileage(query)
        features = self.extract_features(query)
        makes = self.extract_makes(query)

        intent = {
            "price_min": price["price_min"],
            "price_max": price["price_max"],
            "makes": makes,
            "body_type": body_type,
            "fuel_type": fuel_type,
            "transmission": transmission,
            "seating_capacity": seating_capacity,
            "mileage": mileage,
            "features": features,
            "use_case": use_case
        }

        return intent

    def intent_to_filters(self, intent):
        filters = {}

        price_min = intent.get("price_min")
        price_max = intent.get("price_max")

        if price_min is not None and price_max is not None:
            filters["Ex-Showroom_Price"] = [price_min, price_max]

        elif price_max is not None:
            filters["Ex-Showroom_Price"] = price_max

        elif price_min is not None:
            filters["price_min_only"] = price_min

        if intent.get("makes"):
            filters["Make"] = intent["makes"]

        body_type = intent.get("body_type")

        if body_type and body_type != "unknown":
            if body_type in BODY_TYPE_TO_COLUMN:
                filters["Body_Type"] = BODY_TYPE_TO_COLUMN[body_type]

        transmission = intent.get("transmission")

        if transmission == "automatic":
            filters["Transmission_Automatic"] = 1

        elif transmission == "manual":
            filters["Transmission_Manual"] = 1

        seating_capacity = intent.get("seating_capacity")

        if seating_capacity is not None:
            filters["Seating_Capacity"] = seating_capacity

        mileage = intent.get("mileage")

        if mileage is not None:
            filters["ARAI_Certified_Mileage"] = mileage

        fuel_type = intent.get("fuel_type")

        if fuel_type and fuel_type != "unknown":
            filters[f"Fuel_Type_{fuel_type.title()}"] = 1

        for feature_name, value in intent.get("features", {}).items():
            if value == 1:
                filters[feature_name] = 1

        return filters

    def parse(self, query):
        intent = self.parse_to_intent(query)
        filters = self.intent_to_filters(intent)

        return {
            "parser_used": "self_made_ml_parser",
            "intent": intent,
            "filters": filters
        }


_parser_instance = None


def preprocess_user_input_ml(query):
    global _parser_instance

    if _parser_instance is None:
        _parser_instance = MLIntentParser()

    return _parser_instance.parse(query)