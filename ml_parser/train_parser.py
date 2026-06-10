import json
import os
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "parser_training_data.json")
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")

os.makedirs(MODEL_DIR, exist_ok=True)


TARGETS = [
    "body_type",
    "fuel_type",
    "transmission",
    "use_case"
]


def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    queries = [item["query"] for item in data]
    labels = {
        target: [item[target] for item in data]
        for target in TARGETS
    }

    return queries, labels


def train_and_save_models():
    queries, labels = load_data()

    for target in TARGETS:
        print(f"Training model for: {target}")

        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                min_df=1
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                class_weight="balanced"
            ))
        ])

        pipeline.fit(queries, labels[target])

        model_path = os.path.join(MODEL_DIR, f"{target}_model.pkl")
        joblib.dump(pipeline, model_path)

        print(f"Saved: {model_path}")


if __name__ == "__main__":
    train_and_save_models()