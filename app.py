from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import numpy as np
import pickle
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from utils import preprocess_user_input, filter_cars
from utils_used import preprocess_user_input_used, scrape_cars24_selenium, scrape_cartrade_with_selenium  
import os  # ✅ Import for checking image file existence

app = Flask(__name__)
CORS(app)

# Load assets
with open('car_recommendation_assets/label_encoders.pkl', 'rb') as f:
    label_encoders = pickle.load(f)

with open('car_recommendation_assets/categorical_mappings.pkl', 'rb') as f:
    categorical_mappings = pickle.load(f)

df = pd.read_csv("car_recommendation_assets/processed_dataset.csv")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/recommend')
def recommend_page():
    return render_template('recommend.html')

@app.route("/used")
def used_page():
    return render_template("used.html")

@app.route("/used-cars", methods=["POST"])
def get_used_cars():
    query = request.get_json()["query"]
    
    print("🔎 Received query:", query)

    # This function should return a properly structured filters dict
    filters = preprocess_user_input_used(query)  # ✅ this returns a dictionary!

    print("🧠 Parsed filters:", filters)

    results = []

    cars24_results = scrape_cars24_selenium(filters)
    if cars24_results:
        results.extend(cars24_results)

    cartrade_results = scrape_cartrade_with_selenium(filters)
    if cartrade_results:
        results.extend(cartrade_results)

    return jsonify({"recommendations": results})



@app.route('/predict', methods=['POST'])
def predict():
    try:
        user_query = request.json.get('query')
        if not user_query:
            return jsonify({"error": "No query provided"}), 400

        filters = preprocess_user_input(user_query)

        make_mapping = categorical_mappings['make_mapping']
        model_mapping = categorical_mappings['model_mapping']
        variant_mapping = categorical_mappings['variant_mapping']
        reverse_make_mapping = categorical_mappings['reverse_make_mapping']
        reverse_model_mapping = categorical_mappings['reverse_model_mapping']
        reverse_variant_mapping = categorical_mappings['reverse_variant_mapping']

        filtered_df = filter_cars(
            df,
            filters,
            make_mapping=make_mapping,
            reverse_make_mapping=reverse_make_mapping,
            reverse_model_mapping=reverse_model_mapping,
            reverse_variant_mapping=reverse_variant_mapping
        )

        if filtered_df.empty:
            return jsonify({"message": "No cars found matching your query."}), 200

        numerical_cols = ['Ex-Showroom_Price', 'Displacement', 'Power', 'ARAI_Certified_Mileage']
        scaler = StandardScaler()
        filtered_df[numerical_cols] = scaler.fit_transform(filtered_df[numerical_cols])

        encoded_cats = filtered_df.filter(like='_').values
        final_features = np.hstack((filtered_df[numerical_cols], encoded_cats))

        knn_model = NearestNeighbors(n_neighbors=min(10, len(filtered_df)), metric='euclidean')
        knn_model.fit(final_features)

        query_vector = np.zeros(len(numerical_cols))
        query_categorical = np.zeros(encoded_cats.shape[1])
        one_hot_columns = list(df.filter(like='_').columns)

        for col in filters:
            if col in numerical_cols:
                query_vector[numerical_cols.index(col)] = np.mean(filters[col]) if isinstance(filters[col], list) else filters[col]
            elif col in df.columns:
                cat_column_name = col + "_" + str(filters[col])
                if cat_column_name in one_hot_columns:
                    cat_index = one_hot_columns.index(cat_column_name)
                    query_categorical[cat_index] = 1

        full_query_vector = np.hstack((query_vector, query_categorical))
        distances, indices = knn_model.kneighbors(full_query_vector.reshape(1, -1))

        selected_cars = []
        make_count = {}
        total_printed = 0
        max_recommendations = 10
        max_per_make = 2

        for index in indices[0]:
            if total_printed >= max_recommendations:
                break
            car = filtered_df.iloc[index]
            make_name = car['Make']
            if make_count.get(make_name, 0) >= max_per_make:
                continue
            make_count[make_name] = make_count.get(make_name, 0) + 1
            selected_cars.append(car.to_dict())
            total_printed += 1

        def format_cardekho_url(make, model):
            make_slug = make.lower().replace(" ", "-")
            model_slug = model.lower().replace(" ", "-")
            return f"https://www.cardekho.com/{make_slug}/{model_slug}"

        def format_carwale_url(make, model):
            make_slug = make.lower().replace(" ", "-")
            model_slug = model.lower().replace(" ", "-")
            return f"https://www.carwale.com/{make_slug}-cars/{model_slug}"
        
        for car in selected_cars:
            car['Ex-Showroom_Price'] = car['Ex-Showroom_Price'] * scaler.scale_[0] + scaler.mean_[0]
            car['Displacement'] = car['Displacement'] * scaler.scale_[1] + scaler.mean_[1]
            car['Power'] = car['Power'] * scaler.scale_[2] + scaler.mean_[2]
            car['ARAI_Certified_Mileage'] = car['ARAI_Certified_Mileage'] * scaler.scale_[3] + scaler.mean_[3]

            car['Transmission'] = 'Not specified'
            for key in car:
                if key.startswith('Transmission_') and car[key] == 1:
                    car['Transmission'] = key.replace('Transmission_', '').replace('_', ' ').title()

            car['Fuel_Type'] = 'Not specified'
            for key in car:
                if key.startswith('Fuel_Type_') and car[key] == 1:
                    car['Fuel_Type'] = key.replace('Fuel_Type_', '').replace('_', ' ').title()

            car['carDekhoLink'] = format_cardekho_url(car['Make'], car['Model'])
            car['carWaleLink'] = format_carwale_url(car['Make'], car['Model'])

            # ✅ Image Handling: check if image exists else use default
            image_filename = f"{car['Make'].lower().replace(' ', '_')}_{car['Model'].lower().replace(' ', '_')}.jpg"
            image_path = os.path.join(app.root_path, 'static', 'car_images', image_filename)

            if os.path.exists(image_path):
                car['carImage'] = f"/static/car_images/{image_filename}"
            else:
                car['carImage'] = "/static/car_images/pic1.avif"  # Default fallback


        # ✅ Remove duplicate models and return top 4
        unique_models = {}
        for car in selected_cars:
            if car['Model'] not in unique_models:
                unique_models[car['Model']] = car

        return jsonify({"recommendations": list(unique_models.values())[:4]}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
