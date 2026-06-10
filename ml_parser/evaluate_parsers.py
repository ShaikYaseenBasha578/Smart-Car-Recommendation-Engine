import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.append(PROJECT_ROOT)

from utils import preprocess_user_input
from ml_parser.ml_intent_parser import preprocess_user_input_ml


TEST_PATH = os.path.join(CURRENT_DIR, "parser_test_data.json")


def load_test_data():
    with open(TEST_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    eval_data = []

    for item in raw_data:
        expected = {}

        if item.get("price_max") is not None:
            expected["price_max"] = item["price_max"]

        if item.get("body_type") != "unknown":
            expected["body_type"] = item["body_type"]

        if item.get("fuel_type") != "unknown":
            expected["fuel_type"] = item["fuel_type"]

        if item.get("transmission") != "unknown":
            expected["transmission"] = item["transmission"]

        if item.get("use_case") not in ["unknown", "general", None]:
            expected["use_case"] = item["use_case"]

        features = item.get("features", {})

        if features.get("sunroof"):
            expected["sunroof"] = True
        if features.get("airbags"):
            expected["airbags"] = True
        if features.get("abs"):
            expected["abs"] = True
        if features.get("cruise_control"):
            expected["cruise_control"] = True
        if features.get("android_auto"):
            expected["android_auto"] = True
        if features.get("apple_carplay"):
            expected["apple_carplay"] = True

        eval_data.append({
            "query": item["query"],
            "expected": expected
        })

    return eval_data


def regex_filters_to_eval_fields(filters):
    result = {}

    price = filters.get("Ex-Showroom_Price")
    if isinstance(price, list):
        result["price_min"] = price[0]
        result["price_max"] = price[1]
    elif isinstance(price, int):
        result["price_max"] = price

    if filters.get("Body_Type") == "Body_Type_SUV":
        result["body_type"] = "suv"
    elif filters.get("Body_Type") == "Body_Type_Sedan":
        result["body_type"] = "sedan"
    elif filters.get("Body_Type") == "Body_Type_Hatchback":
        result["body_type"] = "hatchback"
    elif filters.get("Body_Type") == "Body_Type_MPV":
        result["body_type"] = "mpv"
    elif filters.get("Body_Type") == "Body_Type_MUV":
        result["body_type"] = "muv"
    elif filters.get("Body_Type") == "Body_Type_Sports":
        result["body_type"] = "sports"

    if filters.get("Transmission_Automatic") == 1:
        result["transmission"] = "automatic"
    elif filters.get("Transmission_Manual") == 1:
        result["transmission"] = "manual"

    if filters.get("Seating_Capacity") is not None:
        result["seating_capacity"] = filters["Seating_Capacity"]

    if filters.get("Sunroof") == 1:
        result["sunroof"] = True

    if filters.get("Airbags") == 1:
        result["airbags"] = True

    if filters.get("ABS_(Anti-lock_Braking_System)") == 1:
        result["abs"] = True

    # Regex parser does not currently expose use_case cleanly.
    return result


def ml_intent_to_eval_fields(intent):
    result = {}

    if intent.get("price_min") is not None:
        result["price_min"] = intent["price_min"]

    if intent.get("price_max") is not None:
        result["price_max"] = intent["price_max"]

    if intent.get("body_type") and intent["body_type"] != "unknown":
        result["body_type"] = intent["body_type"]

    if intent.get("fuel_type") and intent["fuel_type"] != "unknown":
        result["fuel_type"] = intent["fuel_type"]

    if intent.get("transmission") and intent["transmission"] != "unknown":
        result["transmission"] = intent["transmission"]

    if intent.get("seating_capacity") is not None:
        result["seating_capacity"] = intent["seating_capacity"]

    if intent.get("use_case") and intent["use_case"] != "unknown":
        result["use_case"] = intent["use_case"]

    features = intent.get("features", {})

    if features.get("Sunroof") == 1:
        result["sunroof"] = True

    if features.get("Airbags") == 1:
        result["airbags"] = True

    if features.get("ABS_(Anti-lock_Braking_System)") == 1:
        result["abs"] = True

    return result


def score_prediction(predicted, expected):
    total_fields = len(expected)
    correct_fields = 0

    field_scores = {}

    for field, expected_value in expected.items():
        predicted_value = predicted.get(field)
        is_correct = predicted_value == expected_value

        field_scores[field] = {
            "expected": expected_value,
            "predicted": predicted_value,
            "correct": is_correct
        }

        if is_correct:
            correct_fields += 1

    return correct_fields, total_fields, field_scores


def evaluate():
    regex_correct = 0
    regex_total = 0

    ml_correct = 0
    ml_total = 0

    detailed_results = []

    for item in load_test_data():
        query = item["query"]
        expected = item["expected"]

        regex_filters = preprocess_user_input(query)
        regex_eval = regex_filters_to_eval_fields(regex_filters)

        ml_result = preprocess_user_input_ml(query)
        ml_eval = ml_intent_to_eval_fields(ml_result["intent"])

        r_correct, r_total, r_fields = score_prediction(regex_eval, expected)
        m_correct, m_total, m_fields = score_prediction(ml_eval, expected)

        regex_correct += r_correct
        regex_total += r_total

        ml_correct += m_correct
        ml_total += m_total

        detailed_results.append({
            "query": query,
            "expected": expected,
            "regex_prediction": regex_eval,
            "ml_prediction": ml_eval,
            "regex_field_scores": r_fields,
            "ml_field_scores": m_fields
        })

    regex_accuracy = regex_correct / regex_total if regex_total else 0
    ml_accuracy = ml_correct / ml_total if ml_total else 0

    print("\n========== Parser Evaluation ==========")
    print(f"Regex parser field accuracy: {regex_accuracy:.2%}")
    print(f"ML parser field accuracy:    {ml_accuracy:.2%}")

    print("\n========== Detailed Results ==========")
    for result in detailed_results:
        print("\nQuery:", result["query"])
        print("Expected:", result["expected"])
        print("Regex:", result["regex_prediction"])
        print("ML:", result["ml_prediction"])

    output_path = os.path.join(CURRENT_DIR, "parser_eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "regex_accuracy": regex_accuracy,
            "ml_accuracy": ml_accuracy,
            "details": detailed_results
        }, f, indent=2)

    print(f"\nSaved detailed results to: {output_path}")


if __name__ == "__main__":
    evaluate()