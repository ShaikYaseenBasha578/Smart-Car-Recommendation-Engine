# Smart Car Recommendation Engine

An India-focused Flask car discovery platform that turns natural-language queries into new-car recommendations, retrieves matching used-car listings, and supports a provenance-aware vehicle-data enrichment workflow.

The application combines intent parsing, structured filtering, and explainable ranking for new-car discovery. Its supporting data pipeline maintains model- and variant-level information—including specifications, safety, comfort, and performance fields—through validation, source policy, and review controls.

## What it does

### New-car recommendations

- Accepts natural-language requests such as `automatic SUV under 15 lakhs with cruise control`.
- Uses an ML intent parser with a regex fallback to extract budget, make, body style, fuel, transmission, seating, mileage, and feature preferences.
- Applies hard filters where reliable data is available, then ranks matching vehicles and returns match reasons.
- Returns concise, de-duplicated recommendation cards with key specifications, images, and CarDekho/CarWale links.

### Used-car discovery

- Parses a used-car query into search filters.
- Retrieves matching listings from CarTrade and OLX through Selenium-based source adapters.
- Returns source-level errors alongside available results, so one unavailable source does not prevent a response.

### Vehicle-data pipeline

- Defines a canonical schema for recommendation-ready vehicle records.
- Includes controlled CarWale variant fetching and parsing utilities.
- Audits field and recommendation completeness, identifies missing data, and prioritizes enrichment work.
- Uses policy-based validation, provenance tracking, inheritance safeguards, and conflict detection before data can be accepted.

## Tech stack

- **Backend:** Python and Flask
- **Recommendation:** ML intent parsing, structured filtering, and rule-based ranking
- **Data:** Pandas and NumPy with serialized categorical mappings and a processed vehicle dataset
- **Used-car retrieval:** Selenium, Chrome, and ChromeDriver
- **Data enrichment:** Schema-driven Python pipeline with source adapters and automated tests
- **Frontend:** HTML, CSS, and JavaScript

## Project structure

```text
Smart-Car-Recommendation-Engine/
├── app.py                         # Flask routes and application setup
├── services/
│   ├── new_car_service.py         # New-car parsing, filtering, and ranking flow
│   └── used_car_service.py        # Used-car source orchestration
├── ml_parser/                     # Intent-parser training, evaluation, and runtime code
├── ranking_engine.py              # Recommendation scoring and match reasons
├── utils.py                       # New-car query filters
├── utils_used.py                  # Used-car query parsing and Selenium scrapers
├── car_recommendation_assets/     # Processed dataset and category mappings
├── scraping/                      # Canonical-schema, fetch, enrichment, and validation tools
├── templates/                     # Flask HTML templates
├── static/                        # Styles, client-side scripts, and vehicle images
└── requirements.txt               # Python dependencies
```

See [scraping/README.md](scraping/README.md) for the active dataset build, validation, and enrichment workflow.

## Getting started

### Prerequisites

- Python 3.8 or later
- Google Chrome and ChromeDriver for used-car retrieval

### Installation

1. Clone the repository.

   ```bash
   git clone https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine.git
   cd Smart-Car-Recommendation-Engine
   ```

2. Create and activate a virtual environment (recommended).

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the project dependencies.

   ```bash
   pip install -r requirements.txt
   pip install selenium
   ```

   `selenium` is required when using the used-car search flow.

4. Start the application.

   ```bash
   python app.py
   ```

5. Open [http://127.0.0.1:5001](http://127.0.0.1:5001).

## Application routes

| Route | Purpose |
| --- | --- |
| `/` | Landing page |
| `/recommend` | New-car recommendation page |
| `/predict` | New-car recommendation API (`POST`) |
| `/used` | Used-car search page |
| `/used-cars` | Used-car search API (`POST`) |

## How new-car recommendations work

```text
Natural-language query
        ↓
ML intent parser (regex fallback)
        ↓
Structured vehicle filters + supported hard-feature filters
        ↓
Ranking engine
        ↓
De-duplicated recommendation cards with match reasons
```

## Development notes

- New-car recommendations depend on the local assets in `car_recommendation_assets/`.
- Used-car source availability can vary because it depends on third-party websites and browser automation.
- The app runs locally by default and is not currently configured for public hosting.
