from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

import pandas as pd
import numpy as np
import pickle
import traceback

from services.new_car_service import get_new_car_recommendations
from services.used_car_service import get_used_car_recommendations


app = Flask(__name__)
CORS(app)


# =========================
# Load Assets
# =========================

with open("car_recommendation_assets/label_encoders.pkl", "rb") as f:
    label_encoders = pickle.load(f)

with open("car_recommendation_assets/categorical_mappings.pkl", "rb") as f:
    categorical_mappings = pickle.load(f)

df = pd.read_csv("car_recommendation_assets/processed_dataset.csv")


# =========================
# Helper Functions
# =========================

def make_json_safe(value):
    """
    Converts NumPy/Pandas/Python values into valid JSON-safe values.
    Handles NaN and Infinity properly.
    """

    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [make_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]

    if isinstance(value, np.ndarray):
        return [make_json_safe(v) for v in value.tolist()]

    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)

    if isinstance(value, (np.floating, float)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value


# =========================
# Page Routes
# =========================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/recommend")
def recommend_page():
    return render_template("recommend.html")


@app.route("/used")
def used_page():
    return render_template("used.html")


# =========================
# Used Cars Route
# =========================

@app.route("/used-cars", methods=["POST"])
def get_used_cars():
    try:
        query = request.get_json().get("query")

        if not query:
            return jsonify({"error": "No query provided"}), 400

        response_payload = get_used_car_recommendations(
            query=query,
            make_json_safe=make_json_safe
        )

        return jsonify(response_payload), 200

    except Exception as e:
        traceback.print_exc()
        print("❌ Used-car error:", e)
        return jsonify({"error": str(e)}), 500


# =========================
# New Car Recommendation Route
# =========================

@app.route("/predict", methods=["POST"])
def predict():
    try:
        user_query = request.json.get("query")

        if not user_query:
            return jsonify({"error": "No query provided"}), 400

        response_payload = get_new_car_recommendations(
            user_query=user_query,
            df=df,
            categorical_mappings=categorical_mappings,
            app_root_path=app.root_path,
            make_json_safe=make_json_safe
        )

        return jsonify(response_payload), 200

    except Exception as e:
        traceback.print_exc()
        print("❌ Prediction error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)