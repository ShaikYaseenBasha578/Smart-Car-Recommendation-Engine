# Smart Car Recommendation Engine

A Flask-based car recommendation web app that lets users search for cars using natural language queries. The app processes the query, filters a dataset of 1,268 cars using a KNN model, and returns ranked recommendations as visual cards with direct links to CarDekho and CarWale.

---

## Features

- **Natural Language Search:** Type queries like "Petrol automatic SUV under 15 lakhs" and get matched results instantly
- **KNN Recommendation Engine:** Queries are parsed and matched against a preprocessed 1,268 × 141 feature matrix using K-Nearest Neighbors
- **New Car Recommendations:** Filter by fuel type, transmission, price range, and more from a cleaned dataset
- **Used Car Listings:** Fetches live used car listings scraped from Cars24 and CarTrade via a multi-threaded Selenium pipeline
- **Car Detail Cards:** Each result displays price, mileage, transmission, and fuel type with direct links to CarDekho and CarWale
- **Dark Mode:** Toggle between light and dark themes

---

## Tech Stack

- **Backend:** Python, Flask
- **ML Model:** Scikit-Learn (KNN, Euclidean distance)
- **Data Processing:** Pandas, NumPy
- **Encoding:** One-Hot Encoding, Label Encoding
- **Web Scraping:** Selenium (multi-threaded)
- **Frontend:** HTML, CSS, JavaScript

---

## Project Structure

```
Smart-Car-Recommendation-Engine/
├── app.py                          # Main Flask app, routes and UI logic
├── utils.py                        # New car query parser and KNN recommendation logic
├── utils_used.py                   # Used car live listing fetcher via Selenium
├── car_recommendation_assets/
│   ├── knn_model.pkl               # Trained KNN model
│   ├── categorical_mappings.pkl    # Categorical feature mappings
│   ├── label_encoders.pkl          # Label encoders
│   └── processed_dataset.csv      # Cleaned and preprocessed car dataset
├── templates/
│   ├── index.html                  # Homepage with search bar
│   ├── recommend.html              # New car results page
│   └── used.html                   # Used car results page
├── static/
│   ├── style.css
│   ├── script.js
│   └── car_images/                 # Car images for result cards
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.8+
- Google Chrome + ChromeDriver (for used car scraping via Selenium)

### Installation

1. Clone the repository
```
git clone https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine.git
```

2. Navigate to the project directory
```
cd Smart-Car-Recommendation-Engine
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Run the app
```
python app.py
```

5. Open your browser and go to
```
http://127.0.0.1:5003
```

---

## How It Works

```
User Query (natural language)
        ↓
Query Parser — utils.py
(extracts fuel type, transmission, price range, etc.)
        ↓
DataFrame Filter — utils.py
(filters dataset based on parsed query attributes)
        ↓
KNN Model — app.py
(Euclidean distance on 1,268 × 141 feature matrix)
        ↓
Ranked Recommendations
        ↓
Result Cards (price, mileage, transmission, fuel type)
+ CarDekho / CarWale links
```

For used cars, `utils_used.py` runs a parallel Selenium scraping pipeline against Cars24 and CarTrade to fetch live listings matching the query.

---

## Project Status

Active — local deployment only, not hosted publicly.
