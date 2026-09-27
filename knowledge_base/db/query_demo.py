import sqlite3

DB_PATH = "knowledge_base/carrec_kb.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def print_results(title, query, params=()):
    print(f"\n--- {title} ---")
    cur.execute(query, params)
    rows = cur.fetchall()
    if not rows:
        print("No results found.")
        return
    keys = rows[0].keys()
    print(" | ".join(keys))
    print("-" * 60)
    for row in rows:
        print(" | ".join(str(row[k]) for k in keys))
    print(f"({len(rows)} rows)")

# 1. All Hyundai Creta variants
print_results(
    "All Hyundai Creta Variants (Showing 5)",
    """
    SELECT v.id, mfr.name as make, mdl.name as model, v.name as variant, v.price_ex_showroom 
    FROM variant v
    JOIN model mdl ON v.model_id = mdl.id
    JOIN manufacturer mfr ON mdl.manufacturer_id = mfr.id
    WHERE mfr.name = 'Hyundai' AND mdl.name = 'Creta'
    LIMIT 5
    """
)

# 2. All Petrol Creta powertrains
print_results(
    "All Petrol Creta Powertrains",
    """
    SELECT pt.id, pt.fuel_type, pt.engine_cc, pt.power_bhp, pt.description
    FROM powertrain pt
    JOIN model mdl ON pt.model_id = mdl.id
    JOIN manufacturer mfr ON mdl.manufacturer_id = mfr.id
    WHERE mfr.name = 'Hyundai' AND mdl.name = 'Creta' AND pt.fuel_type = 'Petrol'
    """
)

# 3. A specific Creta automatic variant
print_results(
    "A specific Creta automatic variant",
    """
    SELECT v.full_name, pt.description as powertrain, v.transmission, v.price_ex_showroom
    FROM variant v
    JOIN powertrain pt ON v.powertrain_id = pt.id
    WHERE v.full_name LIKE '%Creta%' AND v.transmission IN ('Automatic', 'CVT', 'DCT', 'Torque Converter')
    LIMIT 1
    """
)

# 4. Variants under a given price (e.g., under 6 Lakhs / 600000 Rupees)
print_results(
    "Variants under 6 Lakhs (600,000 Rupees)",
    """
    SELECT v.full_name, v.price_ex_showroom
    FROM variant v
    WHERE v.price_ex_showroom < 600000
    ORDER BY v.price_ex_showroom ASC
    LIMIT 5
    """
)

# 5. Safety information for a generation
print_results(
    "Safety information for Hyundai Creta generation",
    """
    SELECT sr.testing_body, sr.adult_stars, sr.child_stars, sr.test_year, sr.tested_variant
    FROM safety_rating sr
    JOIN model mdl ON sr.model_id = mdl.id
    JOIN manufacturer mfr ON mdl.manufacturer_id = mfr.id
    WHERE mfr.name = 'Hyundai' AND mdl.name = 'Creta'
    """
)

conn.close()
