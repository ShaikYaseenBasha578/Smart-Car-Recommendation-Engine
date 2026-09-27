"""
CarRec Knowledge Base — Post-Migration Validation

Runs all validation checks against the migrated database.

Usage:
    python3 knowledge_base/validate_migration.py
"""
import csv
import json
import os
import sqlite3
import sys
import math
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'knowledge_base', 'carrec_kb.db')
V6_CSV = os.path.join(PROJECT_ROOT, 'AG Datasets', 'carrec_recommendation_dataset_v6.csv')
EXPECTED_VARIANT_COUNT = 812


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return passed


def load_v6():
    with open(V6_CSV, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def safe_float(val):
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


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    v6_rows = load_v6()

    print("=" * 60)
    print("CarRec KB — Post-Migration Validation")
    print("=" * 60)

    passed = 0
    failed = 0

    # 1. Variant count
    count = cur.execute("SELECT COUNT(*) FROM variant").fetchone()[0]
    if check("Variant count", count == EXPECTED_VARIANT_COUNT,
             f"expected {EXPECTED_VARIANT_COUNT}, got {count}"):
        passed += 1
    else:
        failed += 1

    # 2. Manufacturer count
    mfr_count = cur.execute("SELECT COUNT(*) FROM manufacturer").fetchone()[0]
    v6_makes = len(set(r['make'] for r in v6_rows))
    if check("Manufacturer count", mfr_count == v6_makes,
             f"expected {v6_makes}, got {mfr_count}"):
        passed += 1
    else:
        failed += 1

    # 3. Model count
    model_count = cur.execute("SELECT COUNT(*) FROM model").fetchone()[0]
    v6_models = len(set((r['make'], r['model']) for r in v6_rows))
    if check("Model count", model_count == v6_models,
             f"expected {v6_models}, got {model_count}"):
        passed += 1
    else:
        failed += 1

    # 4. Every variant has model_id NOT NULL
    orphans = cur.execute(
        "SELECT COUNT(*) FROM variant WHERE model_id IS NULL"
    ).fetchone()[0]
    if check("All variants have model_id", orphans == 0,
             f"{orphans} orphans" if orphans else ""):
        passed += 1
    else:
        failed += 1

    # 5. Every variant has powertrain_id NOT NULL
    no_pt = cur.execute(
        "SELECT COUNT(*) FROM variant WHERE powertrain_id IS NULL"
    ).fetchone()[0]
    if check("All variants have powertrain_id", no_pt == 0,
             f"{no_pt} missing" if no_pt else ""):
        passed += 1
    else:
        failed += 1

    # 6. Every variant has generation_id NOT NULL
    no_gen = cur.execute(
        "SELECT COUNT(*) FROM variant WHERE generation_id IS NULL"
    ).fetchone()[0]
    if check("All variants have generation_id", no_gen == 0,
             f"{no_gen} missing" if no_gen else ""):
        passed += 1
    else:
        failed += 1

    # 7. Price range sanity (variants with price)
    price_range = cur.execute("""
        SELECT MIN(price_ex_showroom), MAX(price_ex_showroom)
        FROM variant WHERE price_ex_showroom IS NOT NULL
    """).fetchone()
    min_p, max_p = price_range[0], price_range[1]
    price_ok = min_p >= 100000 and max_p <= 100000000  # 1L to 10Cr reasonable
    if check("Price range sanity", price_ok,
             f"min={min_p:.0f} max={max_p:.0f}"):
        passed += 1
    else:
        failed += 1

    # 8. Every variant has at least one source_observation
    no_obs = cur.execute("""
        SELECT COUNT(*) FROM variant v
        WHERE NOT EXISTS (
            SELECT 1 FROM source_observation so WHERE so.resolved_variant_id = v.id
        )
    """).fetchone()[0]
    if check("All variants have source_observation", no_obs == 0,
             f"{no_obs} without observations" if no_obs else ""):
        passed += 1
    else:
        failed += 1

    # 9. Every variant has at least one provenance record
    no_prov = cur.execute("""
        SELECT COUNT(*) FROM variant v
        WHERE NOT EXISTS (
            SELECT 1 FROM field_provenance fp WHERE fp.variant_id = v.id
        )
    """).fetchone()[0]
    if check("All variants have provenance", no_prov == 0,
             f"{no_prov} without provenance" if no_prov else ""):
        passed += 1
    else:
        failed += 1

    # 10. Generation verification_status is 'unverified' for all
    verified_gens = cur.execute(
        "SELECT COUNT(*) FROM generation WHERE verification_status != 'unverified'"
    ).fetchone()[0]
    if check("All generations marked unverified", verified_gens == 0,
             f"{verified_gens} not unverified" if verified_gens else ""):
        passed += 1
    else:
        failed += 1

    # 11. Multi-powertrain model check — Hyundai Creta Petrol should have 2 powertrains
    creta_pts = cur.execute("""
        SELECT COUNT(*) FROM powertrain pt
        JOIN model m ON pt.model_id = m.id
        JOIN manufacturer mfr ON m.manufacturer_id = mfr.id
        WHERE mfr.name = 'Hyundai' AND m.name = 'Creta' AND pt.fuel_type = 'Petrol'
    """).fetchone()[0]
    if check("Hyundai Creta has 2 Petrol powertrains", creta_pts == 2,
             f"got {creta_pts}"):
        passed += 1
    else:
        failed += 1

    # 12. v_variant_full view works
    view_count = cur.execute("SELECT COUNT(*) FROM v_variant_full").fetchone()[0]
    if check("v_variant_full view returns rows", view_count == EXPECTED_VARIANT_COUNT,
             f"expected {EXPECTED_VARIANT_COUNT}, got {view_count}"):
        passed += 1
    else:
        failed += 1

    # 13. Variant alias review flags
    aliases_needing_review = cur.execute(
        "SELECT COUNT(*) FROM variant_alias WHERE needs_review = 1"
    ).fetchone()[0]
    total_aliases = cur.execute("SELECT COUNT(*) FROM variant_alias").fetchone()[0]
    if check("Variant aliases imported with review flags",
             total_aliases > 0 and aliases_needing_review > 0,
             f"{total_aliases} total, {aliases_needing_review} need review"):
        passed += 1
    else:
        failed += 1

    # 14. Spot-check: 20 random variants against V6
    print("\n  --- Spot-Check (20 random variants) ---")
    random.seed(42)
    sample_indices = random.sample(range(len(v6_rows)), min(20, len(v6_rows)))
    spot_pass = 0
    spot_fail = 0

    for idx in sample_indices:
        v6 = v6_rows[idx]
        row = cur.execute("""
            SELECT * FROM v_variant_full
            WHERE make = ? AND model = ? AND variant = ?
        """, (v6['make'], v6['model'], v6['variant'])).fetchone()

        if row is None:
            print(f"    FAIL: Not found — {v6['make']} {v6['model']} {v6['variant']}")
            spot_fail += 1
            continue

        # Check key fields
        errors = []
        v6_price = safe_float(v6.get('price_ex_showroom'))
        kb_price = row['price_ex_showroom']
        if v6_price and kb_price and abs(v6_price - kb_price) > 1:
            errors.append(f"price: V6={v6_price} KB={kb_price}")

        v6_fuel = v6.get('fuel_type', '').strip()
        kb_fuel = row['fuel_type'] or ''
        if v6_fuel and v6_fuel != kb_fuel:
            errors.append(f"fuel: V6={v6_fuel} KB={kb_fuel}")

        v6_trans = v6.get('transmission', '').strip()
        kb_trans = row['transmission'] or ''
        if v6_trans and v6_trans != kb_trans:
            errors.append(f"trans: V6={v6_trans} KB={kb_trans}")

        if errors:
            print(f"    FAIL: {v6['full_name']} — {'; '.join(errors)}")
            spot_fail += 1
        else:
            spot_pass += 1

    if check(f"Spot-check ({spot_pass}/{spot_pass + spot_fail})",
             spot_fail == 0,
             f"{spot_fail} mismatches" if spot_fail else "all matched"):
        passed += 1
    else:
        failed += 1

    # Summary
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
    print("=" * 60)

    conn.close()
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
