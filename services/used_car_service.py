from utils_used import (
    preprocess_user_input_used,
    scrape_cartrade_with_selenium,
    generate_cartrade_filtered_url,
    scrape_olx_selenium
)


def get_used_car_recommendations(query, make_json_safe):
    print("🔎 Received used-car query:", query)

    filters = preprocess_user_input_used(query)

    print("🧠 Used-car parsed filters:", filters)

    results = []
    source_errors = []

    try:
        cartrade_url = generate_cartrade_filtered_url(filters)
        print("🔗 CarTrade URL:", cartrade_url)

        cartrade_results = scrape_cartrade_with_selenium(cartrade_url)
        if cartrade_results:
            results.extend(cartrade_results)
    except Exception as e:
        print("⚠️ CarTrade scraper failed:", e)
        source_errors.append({
            "source": "CarTrade",
            "error": str(e)
        })

    try:
        olx_results = scrape_olx_selenium(filters)
        if olx_results:
            results.extend(olx_results)
    except Exception as e:
        print("⚠️ OLX scraper failed:", e)
        source_errors.append({
            "source": "OLX",
            "error": str(e)
        })

    return {
        "filters": make_json_safe(filters),
        "recommendations": make_json_safe(results),
        "source_errors": make_json_safe(source_errors)
    }
