"""
CarRec Knowledge Base — V6 Migration Script

Migrates carrec_recommendation_dataset_v6.csv (812 rows, 64 columns)
into the Phase 1 SQLite Knowledge Base.

Usage:
    python3 knowledge_base/migrate_v6.py

Requires: KB_SCHEMA.sql in project root.
Produces: knowledge_base/carrec_kb.db
"""
import csv
import json
import os
import sqlite3
import sys
import math

# Paths relative to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V6_CSV = os.path.join(PROJECT_ROOT, 'AG Datasets', 'carrec_recommendation_dataset_v6.csv')
VARIANT_MAPPING = os.path.join(PROJECT_ROOT, 'variant_mapping.json')
SCHEMA_SQL = os.path.join(PROJECT_ROOT, 'KB_SCHEMA.sql')
DB_PATH = os.path.join(PROJECT_ROOT, 'knowledge_base', 'carrec_kb.db')


def safe_float(val):
    """Convert to float, returning None for empty/NaN/non-numeric."""
    if val is None:
        return None
    s = str(val).strip()
    if s == '' or s.lower() in ('nan', 'na', 'n/a', 'none', '-'):
        return None
    try:
        f = float(s)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def safe_int(val):
    """Convert to int, returning None for empty/NaN."""
    f = safe_float(val)
    if f is None:
        return None
    return int(f)


def safe_bool(val):
    """Convert V6 True/False strings to 1/0/None."""
    if val is None:
        return None
    s = str(val).strip()
    if s == '' or s.lower() in ('nan', 'na', 'n/a', 'none', '-'):
        return None
    if s.lower() in ('true', '1', 'yes'):
        return 1
    if s.lower() in ('false', '0', 'no'):
        return 0
    return None


def safe_text(val):
    """Return text or None for empty."""
    if val is None:
        return None
    s = str(val).strip()
    if s == '' or s.lower() in ('nan', 'na', 'n/a', 'none'):
        return None
    return s


def load_v6():
    """Load V6 CSV into list of dicts."""
    with open(V6_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"Loaded {len(rows)} rows from V6 CSV")
    return rows


def create_db():
    """Create fresh database from schema."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    with open(SCHEMA_SQL, 'r') as f:
        schema = f.read()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    conn.commit()
    print(f"Created database at {DB_PATH}")
    return conn


def step1_manufacturers(conn, rows):
    """Step 1: Extract unique manufacturers."""
    makes = sorted(set(r['make'] for r in rows))
    cur = conn.cursor()
    for name in makes:
        cur.execute("INSERT INTO manufacturer (name) VALUES (?)", (name,))
    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM manufacturer").fetchone()[0]
    print(f"Step 1: {count} manufacturers inserted")
    return count


def step2_models(conn, rows):
    """Step 2: Extract unique models."""
    cur = conn.cursor()
    seen = set()
    for r in rows:
        key = (r['make'], r['model'])
        if key in seen:
            continue
        seen.add(key)
        mfr_id = cur.execute(
            "SELECT id FROM manufacturer WHERE name = ?", (r['make'],)
        ).fetchone()[0]
        cur.execute(
            "INSERT INTO model (manufacturer_id, name, body_type) VALUES (?, ?, ?)",
            (mfr_id, r['model'], safe_text(r.get('body_type')))
        )
    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM model").fetchone()[0]
    print(f"Step 2: {count} models inserted")
    return count


def step3_generations(conn):
    """Step 3: Create placeholder generations for every model."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO generation (model_id, name, verification_status, notes)
        SELECT id, 'Gen 1 (V6 Import)', 'unverified',
               'Auto-created during V6 migration. Generation data unverified.'
        FROM model
    """)
    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM generation").fetchone()[0]
    print(f"Step 3: {count} generation placeholders inserted")
    return count


def step4_powertrains(conn, rows):
    """Step 4: Extract unique powertrains per model.

    Groups by (model, fuel_type, engine_cc, power_bhp) — NOT just (model, fuel_type).
    """
    cur = conn.cursor()
    seen = set()
    for r in rows:
        fuel = safe_text(r['fuel_type'])
        cc = safe_float(r.get('engine_cc'))
        bhp = safe_float(r.get('power_bhp'))
        torque = safe_float(r.get('torque_nm'))
        model_key = (r['make'], r['model'])
        pt_key = (model_key, fuel, cc, bhp)

        if pt_key in seen:
            continue
        seen.add(pt_key)

        model_id = cur.execute(
            "SELECT m.id FROM model m JOIN manufacturer mfr ON m.manufacturer_id = mfr.id "
            "WHERE mfr.name = ? AND m.name = ?",
            (r['make'], r['model'])
        ).fetchone()[0]

        # Build human-readable description
        parts = []
        if cc:
            parts.append(f"{int(cc)}cc")
        if bhp:
            parts.append(f"{bhp}bhp")
        if fuel:
            parts.append(fuel)
        desc = ' '.join(parts) if parts else fuel

        cur.execute(
            "INSERT INTO powertrain (model_id, fuel_type, engine_cc, power_bhp, torque_nm, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (model_id, fuel, cc, bhp, torque, desc)
        )

    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM powertrain").fetchone()[0]
    print(f"Step 4: {count} powertrains inserted")
    return count


def step5_variants(conn, rows):
    """Step 5: Insert all 812 variants with full spec columns."""
    cur = conn.cursor()

    # Pre-build lookup caches
    model_cache = {}
    for row in cur.execute(
        "SELECT m.id, mfr.name, m.name FROM model m JOIN manufacturer mfr ON m.manufacturer_id = mfr.id"
    ):
        model_cache[(row[1], row[2])] = row[0]

    gen_cache = {}
    for row in cur.execute("SELECT id, model_id FROM generation"):
        gen_cache[row[1]] = row[0]

    pt_cache = {}
    for row in cur.execute("SELECT id, model_id, fuel_type, engine_cc, power_bhp FROM powertrain"):
        pt_cache[(row[1], row[2], row[3], row[4])] = row[0]

    for idx, r in enumerate(rows):
        model_id = model_cache[(r['make'], r['model'])]
        gen_id = gen_cache[model_id]

        fuel = safe_text(r['fuel_type'])
        cc = safe_float(r.get('engine_cc'))
        bhp = safe_float(r.get('power_bhp'))
        pt_id = pt_cache.get((model_id, fuel, cc, bhp))

        cur.execute("""
            INSERT INTO variant (
                model_id, generation_id, powertrain_id,
                name, full_name, transmission, drivetrain, is_discontinued,
                price_ex_showroom,
                length_mm, width_mm, height_mm, wheelbase_mm,
                ground_clearance_mm, kerb_weight_kg,
                seating_capacity, boot_space_litres, fuel_tank_litres,
                mileage_arai_kmpl, mileage_arai_km_per_kg, claimed_ev_range_km,
                airbags, abs, esc, hill_assist,
                tyre_pressure_monitoring_system,
                rear_parking_sensors, rear_camera, camera_360,
                adas_available, adas_tier,
                automatic_climate_control, rear_ac_vents,
                sunroof, ventilated_front_seats,
                cruise_control, paddle_shifters, wireless_charging,
                heads_up_display, drive_modes, connected_car_features,
                android_auto, apple_carplay,
                v6_row_index
            ) VALUES (
                ?, ?, ?,
                ?, ?, ?, ?, 0,
                ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?
            )
        """, (
            model_id, gen_id, pt_id,
            r['variant'], safe_text(r.get('full_name')), r['transmission'],
            safe_text(r.get('drivetrain')) or 'FWD',
            safe_float(r.get('price_ex_showroom')),
            safe_float(r.get('length_mm')), safe_float(r.get('width_mm')),
            safe_float(r.get('height_mm')), safe_float(r.get('wheelbase_mm')),
            safe_float(r.get('ground_clearance_mm')), safe_float(r.get('kerb_weight_kg')),
            safe_int(r.get('seating_capacity')), safe_float(r.get('boot_space_litres')),
            safe_float(r.get('fuel_tank_litres')),
            safe_float(r.get('mileage_arai_kmpl')), safe_float(r.get('mileage_arai_km_per_kg')),
            safe_float(r.get('claimed_ev_range_km')),
            safe_int(r.get('airbags')), safe_bool(r.get('abs')),
            safe_bool(r.get('esc')), safe_bool(r.get('hill_assist')),
            safe_bool(r.get('tyre_pressure_monitoring_system')),
            safe_bool(r.get('rear_parking_sensors')), safe_bool(r.get('rear_camera')),
            safe_bool(r.get('camera_360')),
            safe_bool(r.get('adas_available')), safe_text(r.get('adas_tier')),
            safe_bool(r.get('automatic_climate_control')), safe_bool(r.get('rear_ac_vents')),
            safe_text(r.get('sunroof')), safe_bool(r.get('ventilated_front_seats')),
            safe_bool(r.get('cruise_control')), safe_bool(r.get('paddle_shifters')),
            safe_bool(r.get('wireless_charging')),
            safe_bool(r.get('heads_up_display')), safe_bool(r.get('drive_modes')),
            safe_bool(r.get('connected_car_features')),
            safe_bool(r.get('android_auto')), safe_bool(r.get('apple_carplay')),
            idx
        ))

    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM variant").fetchone()[0]
    print(f"Step 5: {count} variants inserted")
    return count


def step6_source_observations(conn, rows):
    """Step 6: Create source observations for every V6 row."""
    cur = conn.cursor()
    v6_source_id = cur.execute(
        "SELECT id FROM source WHERE name = 'v6_migration'"
    ).fetchone()[0]

    # Build variant lookup by (make, model, variant_name)
    variant_lookup = {}
    for row in cur.execute("""
        SELECT v.id, mfr.name, mdl.name, v.name
        FROM variant v
        JOIN model mdl ON v.model_id = mdl.id
        JOIN manufacturer mfr ON mdl.manufacturer_id = mfr.id
    """):
        variant_lookup[(row[1], row[2], row[3])] = row[0]

    for r in rows:
        variant_id = variant_lookup.get((r['make'], r['model'], r['variant']))
        full_name = safe_text(r.get('full_name')) or f"{r['make']} {r['model']} {r['variant']}"

        cur.execute("""
            INSERT INTO source_observation (
                source_id, raw_name, raw_payload, observed_at,
                extraction_method, resolved_variant_id, resolution_status
            ) VALUES (?, ?, ?, ?, 'v6_migration', ?, 'applied')
        """, (
            v6_source_id,
            full_name,
            json.dumps(dict(r)),
            safe_text(r.get('source_last_updated')) or '2026-06-19',
            variant_id
        ))

    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0]
    print(f"Step 6: {count} source observations inserted")
    return count


# V6 columns that map to variant table spec fields (for provenance)
V6_TO_VARIANT_FIELDS = {
    'price_ex_showroom': 'price_ex_showroom',
    'engine_cc': None,  # lives on powertrain, skip
    'power_bhp': None,
    'torque_nm': None,
    'drivetrain': 'drivetrain',
    'seating_capacity': 'seating_capacity',
    'boot_space_litres': 'boot_space_litres',
    'ground_clearance_mm': 'ground_clearance_mm',
    'length_mm': 'length_mm',
    'width_mm': 'width_mm',
    'height_mm': 'height_mm',
    'wheelbase_mm': 'wheelbase_mm',
    'kerb_weight_kg': 'kerb_weight_kg',
    'fuel_tank_litres': 'fuel_tank_litres',
    'mileage_arai_kmpl': 'mileage_arai_kmpl',
    'mileage_arai_km_per_kg': 'mileage_arai_km_per_kg',
    'claimed_ev_range_km': 'claimed_ev_range_km',
    'airbags': 'airbags',
    'abs': 'abs',
    'esc': 'esc',
    'hill_assist': 'hill_assist',
    'tyre_pressure_monitoring_system': 'tyre_pressure_monitoring_system',
    'rear_parking_sensors': 'rear_parking_sensors',
    'rear_camera': 'rear_camera',
    'camera_360': 'camera_360',
    'adas_available': 'adas_available',
    'adas_tier': 'adas_tier',
    'automatic_climate_control': 'automatic_climate_control',
    'rear_ac_vents': 'rear_ac_vents',
    'sunroof': 'sunroof',
    'ventilated_front_seats': 'ventilated_front_seats',
    'cruise_control': 'cruise_control',
    'paddle_shifters': 'paddle_shifters',
    'wireless_charging': 'wireless_charging',
    'heads_up_display': 'heads_up_display',
    'drive_modes': 'drive_modes',
    'connected_car_features': 'connected_car_features',
    'android_auto': 'android_auto',
    'apple_carplay': 'apple_carplay',
}


def step7_provenance(conn, rows):
    """Step 7: Create field provenance for every non-NULL spec field."""
    cur = conn.cursor()

    # Build observation lookup by variant_id
    obs_lookup = {}
    for row in cur.execute(
        "SELECT id, resolved_variant_id FROM source_observation WHERE resolution_status = 'applied'"
    ):
        obs_lookup[row[1]] = row[0]

    # Build variant lookup
    variant_lookup = {}
    for row in cur.execute("""
        SELECT v.id, mfr.name, mdl.name, v.name
        FROM variant v
        JOIN model mdl ON v.model_id = mdl.id
        JOIN manufacturer mfr ON mdl.manufacturer_id = mfr.id
    """):
        variant_lookup[(row[1], row[2], row[3])] = row[0]

    provenance_rows = []
    for r in rows:
        variant_id = variant_lookup.get((r['make'], r['model'], r['variant']))
        if variant_id is None:
            continue
        obs_id = obs_lookup.get(variant_id)

        for v6_col, kb_field in V6_TO_VARIANT_FIELDS.items():
            if kb_field is None:
                continue
            raw_val = r.get(v6_col)
            if raw_val is None:
                continue
            s = str(raw_val).strip()
            if s == '' or s.lower() in ('nan', 'na', 'n/a', 'none'):
                continue

            provenance_rows.append((
                variant_id, kb_field, s, obs_id,
                'accepted', 'v6_migration'
            ))

    cur.executemany("""
        INSERT INTO field_provenance (
            variant_id, field_name, accepted_value,
            source_observation_id, decision, decision_reason
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, provenance_rows)

    conn.commit()
    count = cur.execute("SELECT COUNT(*) FROM field_provenance").fetchone()[0]
    print(f"Step 7: {count} provenance records inserted")
    return count


def step8_safety(conn, rows):
    """Step 8: Extract safety ratings at model level."""
    cur = conn.cursor()
    seen = set()
    inserted = 0

    for r in rows:
        body = safe_text(r.get('safety_rating_body'))
        if not body:
            continue

        model_id = cur.execute(
            "SELECT m.id FROM model m JOIN manufacturer mfr ON m.manufacturer_id = mfr.id "
            "WHERE mfr.name = ? AND m.name = ?",
            (r['make'], r['model'])
        ).fetchone()[0]

        gen_id = cur.execute(
            "SELECT id FROM generation WHERE model_id = ?", (model_id,)
        ).fetchone()[0]

        test_year = safe_int(r.get('safety_rating_test_year'))
        key = (model_id, body, test_year)
        if key in seen:
            continue
        seen.add(key)

        cur.execute("""
            INSERT INTO safety_rating (
                model_id, generation_id, testing_body,
                adult_stars, child_stars, test_year,
                tested_variant, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model_id, gen_id, body,
            safe_float(r.get('safety_rating_adult_stars')),
            safe_float(r.get('safety_rating_child_stars')),
            test_year,
            safe_text(r.get('safety_rating_tested_variant')),
            safe_text(r.get('safety_rating_source_url'))
        ))
        inserted += 1

    conn.commit()
    print(f"Step 8: {inserted} safety ratings inserted")
    return inserted


def step9_warranty(conn, rows):
    """Step 9: Extract warranty at manufacturer level (with model-level for EVs)."""
    cur = conn.cursor()
    seen_mfr = set()
    seen_model_ev = set()
    inserted = 0

    for r in rows:
        wy = safe_float(r.get('warranty_years'))
        if wy is None:
            continue

        mfr_id = cur.execute(
            "SELECT id FROM manufacturer WHERE name = ?", (r['make'],)
        ).fetchone()[0]

        bwy = safe_float(r.get('battery_warranty_years'))
        has_battery = bwy is not None

        # Manufacturer-level warranty (ICE/general)
        if mfr_id not in seen_mfr:
            seen_mfr.add(mfr_id)
            cur.execute("""
                INSERT INTO warranty (
                    manufacturer_id, model_id,
                    warranty_years, warranty_km,
                    battery_warranty_years, battery_warranty_km,
                    extended_warranty_available,
                    source, source_url
                ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mfr_id, wy,
                safe_text(r.get('warranty_km')),
                bwy, safe_text(r.get('battery_warranty_km')),
                safe_bool(r.get('extended_warranty_available')),
                safe_text(r.get('warranty_source')),
                safe_text(r.get('warranty_source_url'))
            ))
            inserted += 1

        # If EV with battery warranty, also create model-level row
        if has_battery:
            model_id = cur.execute(
                "SELECT m.id FROM model m JOIN manufacturer mfr ON m.manufacturer_id = mfr.id "
                "WHERE mfr.name = ? AND m.name = ?",
                (r['make'], r['model'])
            ).fetchone()[0]

            if model_id not in seen_model_ev:
                seen_model_ev.add(model_id)
                cur.execute("""
                    INSERT INTO warranty (
                        manufacturer_id, model_id,
                        warranty_years, warranty_km,
                        battery_warranty_years, battery_warranty_km,
                        extended_warranty_available,
                        source, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mfr_id, model_id, wy,
                    safe_text(r.get('warranty_km')),
                    bwy, safe_text(r.get('battery_warranty_km')),
                    safe_bool(r.get('extended_warranty_available')),
                    safe_text(r.get('warranty_source')),
                    safe_text(r.get('warranty_source_url'))
                ))
                inserted += 1

    conn.commit()
    print(f"Step 9: {inserted} warranty records inserted")
    return inserted


def step10_aliases(conn, rows):
    """Step 10: Import variant_mapping.json with review flags."""
    if not os.path.exists(VARIANT_MAPPING):
        print("Step 10: variant_mapping.json not found, skipping aliases")
        return 0

    with open(VARIANT_MAPPING, 'r') as f:
        mappings = json.load(f)

    cur = conn.cursor()

    # Source IDs
    src_91w = cur.execute("SELECT id FROM source WHERE name = '91wheels'").fetchone()[0]
    src_cw = cur.execute("SELECT id FROM source WHERE name = 'carwale'").fetchone()[0]

    # Variant lookup
    variant_lookup = {}
    for row in cur.execute("""
        SELECT v.id, mfr.name, mdl.name, v.name
        FROM variant v
        JOIN model mdl ON v.model_id = mdl.id
        JOIN manufacturer mfr ON mdl.manufacturer_id = mfr.id
    """):
        variant_lookup[(row[1], row[2], row[3])] = row[0]

    inserted = 0
    flagged = 0

    for m in mappings:
        variant_id = variant_lookup.get((m['make'], m['model'], m['variant']))
        if variant_id is None:
            continue

        v_name_lower = m['variant'].lower()

        # 91wheels alias
        url_91 = m.get('91wheels_url')
        score_91 = m.get('91wheels_score', 0)
        if url_91:
            slug = url_91.rstrip('/').split('/')[-1]
            # Fuel mismatch detection
            fuel_mismatch = (
                ('petrol' in v_name_lower and 'diesel' in url_91.lower()) or
                ('diesel' in v_name_lower and 'petrol' in url_91.lower()) or
                ('cng' in v_name_lower and 'cng' not in url_91.lower() and 'diesel' in url_91.lower()) or
                ('electric' in v_name_lower and 'petrol' in url_91.lower())
            )
            needs_review = 1 if (score_91 < 0.85 or fuel_mismatch) else 0
            if needs_review:
                flagged += 1

            try:
                cur.execute("""
                    INSERT INTO variant_alias (
                        variant_id, source_id, alias_name, source_url,
                        confidence, match_method, needs_review, is_verified
                    ) VALUES (?, ?, ?, ?, ?, 'fuzzy', ?, 0)
                """, (variant_id, src_91w, slug, url_91, score_91, needs_review))
                inserted += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate slug for this source — skip

        # CarWale alias
        url_cw = m.get('carwale_url')
        score_cw = m.get('carwale_score', 0)
        if url_cw:
            slug_cw = url_cw.rstrip('/').split('/')[-1]
            needs_review_cw = 1 if score_cw < 0.85 else 0
            if needs_review_cw:
                flagged += 1

            try:
                cur.execute("""
                    INSERT INTO variant_alias (
                        variant_id, source_id, alias_name, source_url,
                        confidence, match_method, needs_review, is_verified
                    ) VALUES (?, ?, ?, ?, ?, 'fuzzy', ?, 0)
                """, (variant_id, src_cw, slug_cw, url_cw, score_cw, needs_review_cw))
                inserted += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate slug for this source — skip

    conn.commit()
    print(f"Step 10: {inserted} aliases inserted ({flagged} flagged for review)")
    return inserted


def main():
    print("=" * 60)
    print("CarRec Knowledge Base — V6 Migration")
    print("=" * 60)

    # Load V6
    rows = load_v6()
    if len(rows) == 0:
        print("ERROR: No rows loaded from V6 CSV")
        sys.exit(1)

    # Create fresh DB
    conn = create_db()

    try:
        step1_manufacturers(conn, rows)
        step2_models(conn, rows)
        step3_generations(conn)
        step4_powertrains(conn, rows)
        step5_variants(conn, rows)
        step6_source_observations(conn, rows)
        step7_provenance(conn, rows)
        step8_safety(conn, rows)
        step9_warranty(conn, rows)
        step10_aliases(conn, rows)

        # Quick summary
        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        for table in ['manufacturer', 'model', 'generation', 'powertrain', 'variant',
                       'source_observation', 'field_provenance', 'safety_rating',
                       'warranty', 'variant_alias', 'source']:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:25s} {count:>6d} rows")

        # Quick v_variant_full test
        test = conn.execute("SELECT * FROM v_variant_full LIMIT 1").fetchone()
        if test:
            print(f"\n  v_variant_full view: OK (columns: {len(test)})")
        else:
            print("\n  WARNING: v_variant_full view returned no rows")

    except Exception as e:
        print(f"\nERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

    print("\nMigration complete.")


if __name__ == '__main__':
    main()
