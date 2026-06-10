import json
import random
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TRAIN_PATH = os.path.join(BASE_DIR, "parser_training_data.json")
TEST_PATH = os.path.join(BASE_DIR, "parser_test_data.json")


body_types = ["suv", "sedan", "hatchback", "mpv", "muv"]
fuel_types = ["petrol", "diesel", "cng", "electric"]
transmissions = ["automatic", "manual"]
use_cases = ["family", "city", "commute", "student", "parents", "highway", "premium", "budget", "enthusiast"]

features = [
    "sunroof",
    "airbags",
    "abs",
    "cruise control",
    "android auto",
    "apple carplay"
]

budgets = [6, 8, 10, 12, 15, 18, 20, 25, 30, 40, 50]


templates = [
    "I need a {body_type} under {budget} lakh",
    "Suggest a {fuel_type} {body_type} below {budget} lakh",
    "Looking for an {transmission} {body_type} under {budget} lakh",
    "Need a {fuel_type} {transmission} car for {use_case}",
    "Best {body_type} for {use_case} use under {budget} lakh",
    "Recommend a {body_type} with {feature}",
    "I want a {fuel_type} car with {feature} under {budget} lakh",
    "Need a {transmission} car for {use_case}",
    "Looking for a {body_type} for {use_case}",
    "Suggest a {fuel_type} {transmission} {body_type} with {feature}",
    "Need a car for {use_case} with good mileage under {budget} lakh",
    "I want a safe car for {use_case} under {budget} lakh",
]


def feature_labels(feature):
    return {
        "sunroof": feature == "sunroof",
        "airbags": feature == "airbags",
        "abs": feature == "abs",
        "cruise_control": feature == "cruise control",
        "android_auto": feature == "android auto",
        "apple_carplay": feature == "apple carplay"
    }


def make_example():
    body_type = random.choice(body_types)
    fuel_type = random.choice(fuel_types)
    transmission = random.choice(transmissions)
    use_case = random.choice(use_cases)
    feature = random.choice(features)
    budget = random.choice(budgets)

    template = random.choice(templates)

    query = template.format(
        body_type=body_type,
        fuel_type=fuel_type,
        transmission=transmission,
        use_case=use_case,
        feature=feature,
        budget=budget
    )

    # If a field does not appear in the template, label it unknown.
    label_body_type = body_type if "{body_type}" in template else "unknown"
    label_fuel_type = fuel_type if "{fuel_type}" in template else "unknown"
    label_transmission = transmission if "{transmission}" in template else "unknown"
    label_use_case = use_case if "{use_case}" in template else "general"

    return {
        "query": query,
        "body_type": label_body_type,
        "fuel_type": label_fuel_type,
        "transmission": label_transmission,
        "use_case": label_use_case,
        "price_max": budget * 100000 if "{budget}" in template else None,
        "features": feature_labels(feature) if "{feature}" in template else {
            "sunroof": False,
            "airbags": False,
            "abs": False,
            "cruise_control": False,
            "android_auto": False,
            "apple_carplay": False
        }
    }


def generate_dataset(n=300):
    seen = set()
    data = []

    while len(data) < n:
        example = make_example()
        if example["query"] not in seen:
            seen.add(example["query"])
            data.append(example)

    random.shuffle(data)
    return data


if __name__ == "__main__":
    random.seed(42)

    all_data = generate_dataset(400)

    split = int(len(all_data) * 0.8)
    train_data = all_data[:split]
    test_data = all_data[split:]

    with open(TRAIN_PATH, "w", encoding="utf-8") as f:
        json.dump(train_data, f, indent=2)

    with open(TEST_PATH, "w", encoding="utf-8") as f:
        json.dump(test_data, f, indent=2)

    print(f"Generated {len(train_data)} training examples")
    print(f"Generated {len(test_data)} test examples")
    print(f"Saved train: {TRAIN_PATH}")
    print(f"Saved test: {TEST_PATH}")