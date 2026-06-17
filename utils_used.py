# import numpy as np
# import pandas as pd
import datetime
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def normalize_used_car_result(car, source):
    return {
        "title": car.get("title", "") or "",
        "price": car.get("price", "") or "",
        "km": car.get("km", "") or "",
        "fuel": car.get("fuel", "") or "",
        "transmission": car.get("transmission", "") or "",
        "owner": car.get("owner", "") or "",
        "location": car.get("location", "") or "",
        "image_url": car.get("image_url", "") or "",
        "listing_url": car.get("listing_url", "") or "",
        "source": source
    }

def preprocess_user_input_used(user_query):
    filters = {}

    query = user_query.lower()

    # 💰 Budget
    under_match = re.search(r'under (\d+)\s*(lakh|cr|crore)?', query)
    if under_match:
        val = int(under_match.group(1))
        multiplier = 100000  # default to lakh
        if under_match.group(2) and 'cr' in under_match.group(2):
            multiplier = 10000000
        filters['price_max'] = val * multiplier

    between_match = re.search(r'(\d+)\s*to\s*(\d+)\s*(lakh|cr|crore)?', query)
    if between_match:
        val1 = int(between_match.group(1))
        val2 = int(between_match.group(2))
        multiplier = 100000
        if between_match.group(3) and 'cr' in between_match.group(3):
            multiplier = 10000000
        filters['price_min'] = val1 * multiplier
        filters['price_max'] = val2 * multiplier

    # 📍 City
    cities = ['hyderabad', 'mumbai', 'delhi', 'bangalore', 'chennai', 'pune', 'kolkata']
    for city in cities:
        if city in query:
            filters['city'] = city
            break

    # ⛽ Fuel
    for fuel in ['petrol', 'diesel', 'cng', 'electric']:
        if fuel in query:
            filters['fuel_type'] = fuel
            break

    # 🚙 Body Type
    for body in ['suv', 'sedan', 'hatchback', 'mpv']:
        if body in query:
            filters['body_type'] = body
            break

    # ⚙️ Transmission
    if 'automatic' in query:
        filters['transmission'] = 'automatic'
    elif 'manual' in query:
        filters['transmission'] = 'manual'

    # 🏢 Make / Brand
    makes = ['tata', 'maruti', 'suzuki', 'hyundai', 'honda', 'mahindra', 'toyota', 'ford', 'renault', 'kia', 'volkswagen', 'nissan'
             ,'jeep','mg','skoda','audi','bmw','ford','datsun','chevrolet','volvo','mercedes-benz','porsche','jaguar','byd']
    filters['make'] = [make for make in makes if make in query]

    # 📆 Year
    year_match = re.search(r'(from|after)?\s*(20[0-2][0-9])', query)
    if year_match:
        filters['year_min'] = int(year_match.group(2))

    # 🚗 KM Driven
    km_match = re.search(r'(under|less than|below)?\s*(\d+)(k)?\s*(km|kms|kilometers)', query)
    if km_match:
        km_value = int(km_match.group(2))
        if km_match.group(3):  # 'k' present
            km_value *= 1000
        filters['km_max'] = km_value


    return filters

def generate_cars24_filtered_url(filters):
    make = filters.get("make")
    if isinstance(make, list):
        make = make[0] if make else None
    make = make.lower() if make else None

    city = filters.get("city", "hyderabad").lower()

    # Decide base URL based on whether make is present
    if make:
        url = f"https://www.cars24.com/buy-used-{make}-cars-{city}/"
    else:
        url = f"https://www.cars24.com/buy-used-cars-{city}/"

    filter_params = []

    # Body Type
    if "body_type" in filters:
        filter_params.append(f"f=bodyType:in:{filters['body_type'].lower()}")

    # Fuel Type
    if "fuel_type" in filters:
        filter_params.append(f"f=fuelType:in:{filters['fuel_type'].lower()}")

    # Transmission
    if "transmission" in filters:
        filter_params.append(f"f=transmission:=:{filters['transmission'].lower()}")

    # Price Range
    price_min = filters.get("price_min", 0)
    price_max = filters.get("price_max", 10000000)
    filter_params.append(f"f=listingPrice:bw:{price_min},{price_max}")

    # KM Driven
    if "km_max" in filters:
        filter_params.append(f"f=odometer:bw:0,{filters['km_max']}")

    # Year Range — NEW LOGIC
    year_min = filters.get("year_min")
    year_max = filters.get("year_max")

    if year_min and not year_max:
        year_max = datetime.now().year
    elif year_max and not year_min:
        year_min = 2000

    if year_min and year_max:
        filter_params.append(f"f=year:bw:{year_min},{year_max}")

    # Seats
    if "seats" in filters:
        filter_params.append(f"f=seatNumber:in:{filters['seats']}")

    # Add filters to URL
    if filter_params:
        url += "?" + "&".join(filter_params)

    # Static flags
    url += "&sort=bestmatch&serveWarrantyCount=true&listingSource=TabFilter"

    return url

def scrape_cars24_selenium(filters):
    url = generate_cars24_filtered_url(filters)
    print(f"🔗 Scraping URL: {url}")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("window-size=1200,800")
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(12)

    listings = []
    cards = driver.find_elements(By.CSS_SELECTOR, "div.styles_normalCardWrapper__qDZjq")

    for card in cards:
        try:
            title = card.find_element(By.CSS_SELECTOR, "span.sc-braxZu").text.strip()
            price = card.find_element(By.CSS_SELECTOR, "p.sc-braxZu.cyPhJl").text.strip()
            location = card.find_element(By.CSS_SELECTOR, "p.lmmumg").text.strip()
            img_url = card.find_element(By.TAG_NAME, "img").get_attribute("src")

            listings.append(normalize_used_car_result({
                "title": title,
                "price": price,
                "location": location,
                "image_url": img_url,
                "listing_url": url  # fallback to filtered page URL
            }, "Cars24"))

        except Exception as e:
            print("⚠️ Error parsing card:", e)
            continue

    driver.quit()
    return listings

def generate_cartrade_filtered_url(filters):
    base_url = "https://www.cartrade.com/second-hand/{city}/"
    query_params = {
        "sc": 1,     # always show all cars
        "so": -1     # default sort order
    }

    # --- City ---
    city = filters.get("city", "hyderabad").lower()
    city_id_map = {
        "hyderabad": 105,
        # Add more cities if needed
    }
    query_params["city"] = city_id_map.get(city, 105)

    # --- Price ---
    price_min = filters.get("price_min", 0)
    price_max = filters.get("price_max", 10000000)
    # Convert rupees to lakhs
    price_min_lakhs = max(0, price_min // 100000)
    price_max_lakhs = max(1, price_max // 100000)
    if price_max_lakhs >= price_min_lakhs:
        query_params["budget"] = f"{price_min_lakhs}-{price_max_lakhs}"

    # --- Fuel Type ---
    fuel_map = {
        "petrol": 1,
        "diesel": 2,
        "cng": 3,
        "lpg": 4,
        "electric": 5
    }
    fuel_type = filters.get("fuel_type")
    if fuel_type:
        query_params["fuel"] = fuel_map.get(fuel_type.lower(), 1)

    # --- Transmission ---
    trans_map = {
        "manual": 1,
        "automatic": 2
    }
    transmission = filters.get("transmission")
    if transmission:
        query_params["trans"] = trans_map.get(transmission.lower(), 1)

    # --- KM Driven ---
    km_max = filters.get("km_max")
    if km_max:
        query_params["kms"] = f"{km_max // 1000}-"  # CarTrade uses km in 1000s (50 = 50,000)

    # --- Body Type ---
    body_map = {
        "suv": 6,
        "sedan": 1,
        "hatchback": 3,
        "muv": 6,
        "coupe": 8
    }
    body_type = filters.get("body_type")
    if body_type:
        query_params["bodytype"] = body_map.get(body_type.lower(), 1)

    # --- Make ---
    make_map = {
        "maruti": 8,
        "hyundai": 9,
        "honda": 10,
        "toyota": 11,
        "tata": 12,
        "mahindra": 13,
        "renault": 24,
        "ford": 14,
        "kia": 43
        # Add more if needed
    }
    make = filters.get("make")
    if make:
        if isinstance(make, list):
            make = make[0]
        query_params["car"] = make_map.get(make.lower(), 8)

    # Construct query string
    query_str = "&".join(f"{k}={v}" for k, v in query_params.items())
    full_url = f"{base_url.format(city=city)}#{query_str}"
    return full_url

def generate_olx_filtered_url(filters):
    city = filters.get("city", "hyderabad").lower()
    city_category_urls = {
        "hyderabad": "https://www.olx.in/hyderabad_g4058526/cars_c84"
    }

    url = city_category_urls.get(city, city_category_urls["hyderabad"])
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    filter_parts = []

    if price_min and price_max:
        filter_parts.append(f"price_between_{price_min}_to_{price_max}")
    elif price_max:
        filter_parts.append(f"price_max_{price_max}")
    elif price_min:
        filter_parts.append(f"price_min_{price_min}")

    transmission = filters.get("transmission")
    if transmission:
        transmission_map = {
            "automatic": "transmission_eq_1",
            "manual": "transmission_eq_2"
        }
        transmission_filter = transmission_map.get(str(transmission).lower())

        if transmission_filter:
            filter_parts.append(transmission_filter)

    if filter_parts:
        url += "?filter=" + "%2C".join(filter_parts)

    print(f"🔗 OLX generated URL: {url}")
    return url

def infer_olx_body_type_from_title(title):
    normalized_title = f" {str(title).lower()} "

    body_type_models = {
        "hatchback": [
            "alto",
            "alto 800",
            "wagon r",
            "swift",
            "baleno",
            "i20",
            "grand i10",
            "santro",
            "tiago",
            "polo",
            "brio",
            "kwid",
            "celerio",
            "ignis",
            "figo"
        ],
        "sedan": [
            "dzire",
            "amaze",
            "city",
            "verna",
            "vento",
            "rapid",
            "ciaz",
            "corolla",
            "altis",
            "civic",
            "elantra",
            "sunny",
            "aspire",
            "etios",
            "slavia",
            "virtus"
        ],
        "suv": [
            "brezza",
            "nexon",
            "creta",
            "seltos",
            "venue",
            "ecosport",
            "xuv",
            "harrier",
            "safari",
            "hector",
            "compass",
            "fortuner",
            "thar",
            "scorpio",
            "duster",
            "kushaq",
            "taigun",
            "sonet",
            "kiger",
            "magnite"
        ],
        "muv": [
            "ertiga",
            "innova",
            "carens",
            "marazzo",
            "triber",
            "lodgy"
        ]
    }

    for body_type, model_names in body_type_models.items():
        for model_name in model_names:
            if f" {model_name} " in normalized_title:
                return body_type

    return ""

def is_valid_olx_image_url(image_url):
    normalized_url = str(image_url or "").strip()
    lowered_url = normalized_url.lower()

    if not normalized_url:
        return False

    if not lowered_url.startswith("http"):
        return False

    if lowered_url.startswith("data:") or "base64" in lowered_url:
        return False

    if "placeholder" in lowered_url:
        return False

    return True

def scrape_olx_selenium(filters):
    url = generate_olx_filtered_url(filters)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1366,900")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(options=options)
    listings = []

    try:
        driver.get(url)

        card_selector = (
            "li[data-aut-id='itemBox'], "
            "div[data-aut-id='itemBox'], "
            "a[href*='/item/'], "
            "a[href*='olx.in/item']"
        )

        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, card_selector))
            )
        except Exception:
            print("Timed out waiting for OLX listings to load.")
            return []

        cards = driver.find_elements(By.CSS_SELECTOR, card_selector)
        print("🔎 OLX cards found:", len(cards))

        for card in cards:
            try:
                def get_text(selectors):
                    for selector in selectors:
                        try:
                            value = card.find_element(By.CSS_SELECTOR, selector).text.strip()
                            if value:
                                return value
                        except Exception:
                            continue
                    return ""

                title = get_text([
                    "[data-aut-id='itemTitle']",
                    "[data-aut-id='title']",
                    "[title]",
                    "span",
                    "h2",
                    "h3"
                ])

                price = get_text([
                    "[data-aut-id='itemPrice']",
                    "[data-aut-id='price']",
                    "[aria-label*='Price']",
                    "span"
                ])

                location = get_text([
                    "[data-aut-id='item-location']",
                    "[data-aut-id='itemLocation']",
                    "[data-aut-id='location']",
                    "[aria-label*='Location']"
                ])

                listing_url = ""
                try:
                    link_tag = card if card.tag_name.lower() == "a" else card.find_element(By.CSS_SELECTOR, "a[href]")
                    listing_url = link_tag.get_attribute("href") or ""
                except Exception:
                    pass

                image_url = ""
                try:
                    image_tag = card.find_element(By.TAG_NAME, "img")
                    srcset = image_tag.get_attribute("srcset") or ""

                    if srcset:
                        srcset_candidates = [
                            candidate.strip().split(" ")[0]
                            for candidate in srcset.split(",")
                            if candidate.strip()
                        ]
                        for candidate in reversed(srcset_candidates):
                            if is_valid_olx_image_url(candidate):
                                image_url = candidate
                                break

                    if not image_url:
                        data_src = image_tag.get_attribute("data-src") or ""
                        if is_valid_olx_image_url(data_src):
                            image_url = data_src

                    if not image_url:
                        data_original = image_tag.get_attribute("data-original") or ""
                        if is_valid_olx_image_url(data_original):
                            image_url = data_original

                    if not image_url:
                        src = image_tag.get_attribute("src") or ""
                        if is_valid_olx_image_url(src):
                            image_url = src
                except Exception:
                    pass

                if not image_url:
                    image_url = "/static/pic.avif"

                if not title and not price and not listing_url:
                    continue

                listings.append(normalize_used_car_result({
                    "title": title,
                    "price": price,
                    "location": location,
                    "image_url": image_url,
                    "listing_url": listing_url
                }, "OLX"))

            except Exception as e:
                print("Error parsing an OLX card:", e)
                continue

        print("🔎 OLX raw listings parsed:", len(listings))
        strong_matches = []
        unknown_body_matches = []

        make_filter = filters.get("make")
        if isinstance(make_filter, list):
            make_terms = [str(make).lower() for make in make_filter if make]
        elif make_filter:
            make_terms = [str(make_filter).lower()]
        else:
            make_terms = []

        body_type = filters.get("body_type")
        transmission = filters.get("transmission")
        fuel_type = filters.get("fuel_type")

        automatic_terms = ["automatic", "amt", "cvt", "dct", " at "]
        manual_terms = ["manual", " mt "]
        fuel_terms = ["petrol", "diesel", "cng", "electric"]

        for listing in listings:
            searchable_text = " ".join([
                listing.get("title", ""),
                listing.get("fuel", ""),
                listing.get("transmission", ""),
                listing.get("location", "")
            ]).lower()

            if make_terms and not any(make in searchable_text for make in make_terms):
                continue

            if transmission:
                padded_text = f" {searchable_text} "
                mentions_automatic = any(term in padded_text for term in automatic_terms)
                mentions_manual = any(term in padded_text for term in manual_terms)

                if str(transmission).lower() == "automatic" and mentions_manual:
                    continue

                if str(transmission).lower() == "manual" and mentions_automatic:
                    continue

            if fuel_type:
                mentioned_fuels = [fuel for fuel in fuel_terms if fuel in searchable_text]
                if mentioned_fuels and str(fuel_type).lower() not in mentioned_fuels:
                    continue

            inferred_body_type = infer_olx_body_type_from_title(listing.get("title", ""))

            if body_type:
                requested_body_type = str(body_type).lower()

                if inferred_body_type == requested_body_type:
                    strong_matches.append(listing)
                elif not inferred_body_type:
                    unknown_body_matches.append(listing)
            else:
                strong_matches.append(listing)

        filtered_listings = strong_matches + unknown_body_matches
        final_listings = filtered_listings if filtered_listings else listings
        final_listings = final_listings[:10]

        print("🔎 OLX listings after relevance filtering:", len(filtered_listings))
        print("✅ OLX listings returned:", len(final_listings))
        return final_listings

    finally:
        driver.quit()

def scrape_cartrade_with_selenium(full_url, headless=True):
    # Setup Chrome options
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0")

    # Start driver
    driver = webdriver.Chrome(options=options)
    print("Opening URL:", full_url, "of type:", type(full_url))  # 🔍 debug
    
    # Final check before opening the URL
    if not isinstance(full_url, str) or not full_url.startswith("http"):
        print("❌ Invalid URL passed to Selenium:", full_url)
        driver.quit()
        return []  # Prevent crash by returning an empty list

    
    driver.get(full_url)

    # Wait until at least one listing loads
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.carlistblk_new"))
        )
    except:
        print("Timed out waiting for listings to load.")
        driver.quit()
        return []

    listings = []
    car_cards = driver.find_elements(By.CSS_SELECTOR, "li.carlistblk_new")

    for card in car_cards:
        try:
            title = card.find_element(By.CLASS_NAME, "card-title").text.strip()
            price = card.find_element(By.CLASS_NAME, "cr_prc").text.strip()
            add_info = card.find_element(By.CLASS_NAME, "additional-info").text.strip()
            info_parts = [x.strip() for x in add_info.split("|")]
            # Get link to the original listing
            link_tag = card.find_element(By.CSS_SELECTOR, "a.font-muli[href*='/second-hand/']")
            relative_link = link_tag.get_attribute("href")
            listing_url = relative_link if relative_link.startswith("http") else "https://www.cartrade.com" + relative_link


            km = info_parts[0] if len(info_parts) > 0 else None
            fuel = info_parts[1] if len(info_parts) > 1 else None
            location = info_parts[2] if len(info_parts) > 2 else None

            # Image
            try:
                image_tag = card.find_element(By.CSS_SELECTOR, "img.blk_grid_img_new--non-absure")
            except:
                image_tag = card.find_element(By.TAG_NAME, "img")

            image_url = image_tag.get_attribute("src") if image_tag else None

            # Extract year from title
            year = None
            if title:
                for word in title.split():
                    if word.isdigit() and len(word) == 4:
                        year = word
                        break

            listings.append(normalize_used_car_result({
                "title": title,
                "price": price,
                "location": location,
                "km": km,
                "fuel": fuel,
                "year": year,
                "image_url": image_url,
                "listing_url": listing_url
            }, "CarTrade"))
        except Exception as e:
            print("Error parsing a card:", e)
            continue

    driver.quit()
    return listings
