from flask import Flask, request, jsonify, render_template, Response, abort
from flask_cors import CORS

import pandas as pd
import numpy as np
import os
import pickle
import re
import traceback

from services.new_car_service import get_new_car_recommendations

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Used-car search needs selenium/bs4 + headless Chrome; off unless explicitly enabled.
ENABLE_USED_CARS = os.environ.get("ENABLE_USED_CARS", "0") == "1"

if ENABLE_USED_CARS:
    from services.used_car_service import get_used_car_recommendations


app = Flask(__name__)
CORS(app)


@app.context_processor
def inject_feature_flags():
    return {"used_cars_enabled": ENABLE_USED_CARS}


# =========================
# Load Assets
# =========================

ASSETS_DIR = os.path.join(BASE_DIR, "car_recommendation_assets")

with open(os.path.join(ASSETS_DIR, "label_encoders.pkl"), "rb") as f:
    label_encoders = pickle.load(f)

with open(os.path.join(ASSETS_DIR, "categorical_mappings.pkl"), "rb") as f:
    categorical_mappings = pickle.load(f)

df = pd.read_csv(os.path.join(ASSETS_DIR, "processed_dataset.csv"))


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
    from services.catalogue import get_catalogue
    return render_template("index.html", variant_count=f"{len(get_catalogue()):,}")


# "How it works" pages: four generated, self-contained HTML files in project_pages/ (refresh: scripts/sync_project_pages.py).
# Only these fixed names are served, so there is no path to traverse.
PROJECT_PAGES = {
    "": "index.html",
    "pipeline": "pipeline.html",
    "knowledge-base": "kb.html",
    "engine": "engine.html",
}


# the generated pages carry their own header; it is swapped at serve time for the app's shared one (templates/_project_header.html)
_PROJECT_HEADER = re.compile(r'<header class="site-header".*?</header>', re.S)


@app.route("/project", defaults={"name": ""})
@app.route("/project/<name>")
def project_page(name):
    filename = PROJECT_PAGES.get(name)
    if filename is None:
        abort(404)
    with open(os.path.join(BASE_DIR, "project_pages", filename), "rb") as fh:
        body = fh.read()
    html = body.decode("utf-8")
    if _PROJECT_HEADER.search(html):
        header = render_template("_project_header.html", current=name)
        html = _PROJECT_HEADER.sub(lambda _m: header, html, count=1)
        body = html.encode("utf-8")
    return Response(body, mimetype="text/html", headers={"Cache-Control": "public, max-age=300"})


@app.route("/recommend")
def recommend_page():
    from services.catalogue import get_catalogue
    # the loading skeleton says "Checking N variants…" with the same catalogue size the landing page shows
    return render_template("recommend.html", variant_count_raw=len(get_catalogue()))


COMPARE_SORTS = {"best", "price", "mileage", "safety"}


def _stamp_date(data_as_of):
    """'14 Nov 2026', the same format as the results page's "Prices and specs updated" line."""
    from datetime import date
    try:
        d = date.fromisoformat(str(data_as_of["exported"]))
    except (KeyError, TypeError, ValueError):
        return str((data_as_of or {}).get("exported") or "")
    return f"{d.day} {d:%b} {d.year}"


@app.route("/compare")
def compare_page():
    from urllib.parse import urlencode
    from services.compare import get_compare, parse_ids

    ids = parse_ids(request.args.get("ids", ""))
    q = request.args.get("q", "")[:500]
    drop = request.args.get("drop", "")[:200]
    sort = request.args.get("sort", "")
    sort = sort if sort in COMPARE_SORTS and sort != "best" else ""
    data = get_compare(ids, app.root_path)
    cars = data["cars"]

    def search_args(**extra):
        args = {k: v for k, v in {"q": q, "drop": drop, "sort": sort}.items() if v}
        args.update(extra)
        return args

    back_url = "/recommend" + ("?" + urlencode(search_args()) if q else "")
    for car in cars:
        left = ",".join(str(c["variant_id"]) for c in cars if c is not car)
        car["remove_url"] = "/compare?" + urlencode(search_args(ids=left), safe=",")
    shown = len(cars) >= 2
    names = [c["model"] for c in cars]
    title = " vs ".join(names) + " | CarRec" if shown else "Compare cars | CarRec"
    if shown and len(title) > 60:
        title = f"Compare {len(cars)} cars | CarRec"
    return render_template("compare.html", page_title=title, shown=shown, cars=cars, rows=data["rows"],
                           missing=data["missing"], stamp=_stamp_date(data["data_as_of"]), q=q, back_url=back_url)


@app.route("/used")
def used_page():
    if not ENABLE_USED_CARS:
        return render_template("coming_soon.html")
    return render_template("used.html")


# =========================
# Used Cars Route
# =========================

@app.route("/used-cars", methods=["POST"])
def get_used_cars():
    if not ENABLE_USED_CARS:
        return jsonify({"error": "Used-car search is not available in this demo"}), 404

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
            make_json_safe=make_json_safe,
            drop=request.json.get("drop")
        )

        return jsonify(response_payload), 200

    except Exception as e:
        traceback.print_exc()
        print("❌ Prediction error:", e)
        return jsonify({"error": str(e)}), 500


# =========================
# Car Detail Route
# =========================

@app.route("/api/car/<make_slug>/<model_slug>")
def car_detail_api(make_slug, model_slug):
    from services.car_detail import get_car_detail

    drop = [d for d in request.args.get("drop", "").split(",") if d]
    variant_id = request.args.get("variant_id", type=int)
    detail = get_car_detail(make_slug, model_slug, q=request.args.get("q", ""), drop=drop,
                            variant_id=variant_id, app_root_path=app.root_path)
    if detail is None:
        return jsonify({"error": f"No car found for {make_slug}/{model_slug}"}), 404
    return jsonify(make_json_safe(detail)), 200


@app.route("/car/<make_slug>/<model_slug>")
def car_page(make_slug, model_slug):
    from services.car_detail import find_model

    rows = find_model(make_slug, model_slug)
    if rows is None:
        return render_template("car.html", page_title="Car not found | CarRec", not_found=True), 404
    first = rows.iloc[0]
    return render_template("car.html", page_title=f"{first['make']} {first['model']} | CarRec", not_found=False), 200


if __name__ == "__main__":
    app.run(debug=True, port=5001)