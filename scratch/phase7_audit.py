#!/usr/bin/env python3
"""Phase 7 KB Coverage & Quality Audit — READ-ONLY"""
import sqlite3, json, csv, os, sys
from collections import defaultdict

DB = "knowledge_base/carrec_kb.db"
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

# ── 1. CANONICAL VARIANT FIELDS ────────────────────────────────────────────────
cur = conn.cursor()
cur.execute("PRAGMA table_info(variant)")
schema_cols = [r['name'] for r in cur.fetchall()]

# Exclude structural/meta columns
EXCLUDE = {'id','model_id','generation_id','powertrain_id','name','full_name',
           'v6_row_index','created_at','updated_at','base_variant_id','edition_classification',
           'is_discontinued'}
CANON_FIELDS = [c for c in schema_cols if c not in EXCLUDE]

TOTAL_VARIANTS = 832

# Field type classification
BOOLEAN = {'abs','esc','hill_assist','tyre_pressure_monitoring_system','rear_parking_sensors',
           'rear_camera','camera_360','adas_available','automatic_climate_control','rear_ac_vents',
           'ventilated_front_seats','cruise_control','paddle_shifters','wireless_charging',
           'heads_up_display','drive_modes','connected_car_features','android_auto','apple_carplay'}
NUMERIC = {'price_ex_showroom','length_mm','width_mm','height_mm','wheelbase_mm',
           'ground_clearance_mm','kerb_weight_kg','seating_capacity','boot_space_litres',
           'fuel_tank_litres','mileage_arai_kmpl','mileage_arai_km_per_kg',
           'claimed_ev_range_km','airbags'}
CATEGORICAL = {'transmission','drivetrain','sunroof','adas_tier'}

# Recommendation importance
IMPORTANT = {'price_ex_showroom','transmission','drivetrain','mileage_arai_kmpl',
             'mileage_arai_km_per_kg','claimed_ev_range_km','airbags','abs','esc',
             'hill_assist','tyre_pressure_monitoring_system','rear_parking_sensors',
             'rear_camera','camera_360','adas_available','adas_tier','automatic_climate_control',
             'rear_ac_vents','sunroof','ventilated_front_seats','cruise_control',
             'wireless_charging','heads_up_display','drive_modes','android_auto','apple_carplay',
             'seating_capacity','boot_space_litres','fuel_tank_litres'}

print("=== CANONICAL FIELD COVERAGE ===")
field_stats = []
for f in CANON_FIELDS:
    cur.execute(f"SELECT count(*) FROM variant WHERE {f} IS NOT NULL")
    non_null = cur.fetchone()[0]
    null = TOTAL_VARIANTS - non_null
    pct = round(100.0 * non_null / TOTAL_VARIANTS, 1)
    ftype = 'boolean' if f in BOOLEAN else ('numeric' if f in NUMERIC else 'categorical/text')
    important = f in IMPORTANT
    field_stats.append({'field': f, 'non_null': non_null, 'null': null,
                        'pct_populated': pct, 'pct_unknown': round(100-pct,1),
                        'type': ftype, 'important_for_rec': important})
    print(f"  {f}: {non_null}/{TOTAL_VARIANTS} ({pct}%) [{ftype}] {'★' if important else ''}")

# Write CSV
os.makedirs('scratch', exist_ok=True)
with open('scratch/phase7_canonical_field_coverage.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['field','type','important_for_rec','non_null','null',
                                       'pct_populated','pct_unknown'])
    w.writeheader()
    w.writerows(field_stats)
print(f"\nWrote scratch/phase7_canonical_field_coverage.csv")

# ── 2. MODEL/VARIANT COVERAGE ────────────────────────────────────────────────
print("\n=== MODEL/VARIANT COVERAGE ===")
cur.execute("""
    SELECT m.id, mk.name as make, m.name as model,
           count(distinct v.id) as variant_count,
           count(distinct v.powertrain_id) as pt_count
    FROM model m
    JOIN manufacturer mk ON m.manufacturer_id=mk.id
    LEFT JOIN variant v ON v.model_id=m.id
    GROUP BY m.id ORDER BY make, model
""")
models = [dict(r) for r in cur.fetchall()]

model_coverage = []
for m in models:
    mid = m['id']
    # count populated fields across all variants of this model
    total_cells = 0
    populated_cells = 0
    for f in IMPORTANT:
        cur.execute(f"SELECT count(*), count({f}) FROM variant WHERE model_id=?", (mid,))
        row = cur.fetchone()
        total_cells += row[0]
        populated_cells += row[1]
    completeness = round(100.0 * populated_cells / total_cells, 1) if total_cells > 0 else 0
    # provenance count for this model
    cur.execute("""
        SELECT count(*) FROM field_provenance fp
        JOIN variant v ON fp.variant_id=v.id
        WHERE v.model_id=?
    """, (mid,))
    prov_count = cur.fetchone()[0]
    # source obs count
    cur.execute("""
        SELECT count(*) FROM source_observation so
        JOIN variant v ON so.resolved_variant_id=v.id
        WHERE v.model_id=?
    """, (mid,))
    obs_count = cur.fetchone()[0]
    entry = {**m, 'completeness_pct': completeness,
             'provenance_rows': prov_count, 'source_obs': obs_count}
    model_coverage.append(entry)
    print(f"  {m['make']} {m['model']}: {m['variant_count']}v/{m['pt_count']}pt | {completeness}% | {obs_count} obs | {prov_count} prov")

# ── 3. SOURCE COVERAGE ────────────────────────────────────────────────────────
print("\n=== SOURCE COVERAGE ===")
cur.execute("""
    SELECT s.id, s.name, s.source_type, s.authority_tier,
           count(so.id) as obs_count,
           count(so.resolved_variant_id) as resolved_count,
           count(distinct so.resolved_variant_id) as distinct_variants
    FROM source s
    LEFT JOIN source_observation so ON so.source_id=s.id
    GROUP BY s.id
    ORDER BY obs_count DESC
""")
sources = [dict(r) for r in cur.fetchall()]
for s in sources:
    # distinct models covered
    cur.execute("""
        SELECT count(distinct v.model_id) FROM source_observation so
        JOIN variant v ON so.resolved_variant_id=v.id
        WHERE so.source_id=?
    """, (s['id'],))
    s['distinct_models'] = cur.fetchone()[0]
    print(f"  [{s['id']}] {s['name']} ({s['source_type']}, tier={s['authority_tier']}): "
          f"{s['obs_count']} obs | {s['resolved_count']} resolved | "
          f"{s['distinct_variants']} variants | {s['distinct_models']} models")

# ── 4. FIELD-LEVEL SOURCE DIVERSITY ──────────────────────────────────────────
print("\n=== FIELD-LEVEL SOURCE DIVERSITY (important fields) ===")
field_source_diversity = []
for f in sorted(IMPORTANT):
    cur.execute("""
        SELECT so.source_id, s.name, count(*) as cnt
        FROM field_provenance fp
        JOIN source_observation so ON fp.source_observation_id=so.id
        JOIN source s ON so.source_id=s.id
        WHERE fp.field_name=?
        GROUP BY so.source_id
    """, (f,))
    src_rows = cur.fetchall()
    sources_supporting = [(r['name'], r['cnt']) for r in src_rows]
    n_sources = len(sources_supporting)
    total_prov = sum(r[1] for r in sources_supporting)
    cur.execute(f"SELECT count(*) FROM variant WHERE {f} IS NOT NULL")
    non_null = cur.fetchone()[0]
    entry = {'field': f, 'sources_supporting': n_sources, 'total_prov': total_prov,
             'canonical_populated': non_null, 'source_details': json.dumps(sources_supporting)}
    field_source_diversity.append(entry)
    status = ('MULTI_SOURCE' if n_sources > 1 else
              ('SINGLE_SOURCE' if n_sources == 1 else 'NO_SOURCE'))
    print(f"  {f}: {status} ({n_sources} src, {total_prov} prov, {non_null} canonical)")

# ── 5. PROVENANCE ANALYSIS ────────────────────────────────────────────────────
print("\n=== PROVENANCE ANALYSIS ===")
cur.execute("""
    SELECT fp.decision, fp.decision_reason,
           count(*) as cnt,
           count(distinct fp.variant_id) as variants,
           count(distinct fp.field_name) as fields
    FROM field_provenance fp
    GROUP BY fp.decision, fp.decision_reason
    ORDER BY cnt DESC
""")
prov_rows = [dict(r) for r in cur.fetchall()]
for r in prov_rows:
    print(f"  {r['decision']}|{r['decision_reason']}: {r['cnt']} rows, "
          f"{r['variants']} variants, {r['fields']} fields")

with open('scratch/phase7_provenance_analysis.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['decision','decision_reason','cnt','variants','fields'])
    w.writeheader()
    w.writerows(prov_rows)
print(f"\nWrote scratch/phase7_provenance_analysis.csv")

# ── 6. CONFLICT AUDIT ────────────────────────────────────────────────────────
print("\n=== CONFLICT AUDIT ===")
cur.execute("""
    SELECT fp.variant_id, mk.name as make, m.name as model, v.name as variant,
           fp.field_name,
           fp.accepted_value as rejected_value,
           fp.decision_reason,
           so.source_id,
           s.name as source_name
    FROM field_provenance fp
    JOIN variant v ON fp.variant_id=v.id
    JOIN model m ON v.model_id=m.id
    JOIN manufacturer mk ON m.manufacturer_id=mk.id
    JOIN source_observation so ON fp.source_observation_id=so.id
    JOIN source s ON so.source_id=s.id
    WHERE fp.decision='rejected'
    ORDER BY mk.name, m.name, fp.field_name
    LIMIT 40
""")
conflicts = [dict(r) for r in cur.fetchall()]
print(f"  Total rejected provenance rows: 2454")
print(f"  Sample conflicts (first 40):")
for c in conflicts[:10]:
    print(f"    {c['make']} {c['model']} {c['variant']}: "
          f"{c['field_name']}={c['rejected_value']} from {c['source_name']} — {c['decision_reason']}")

# ── 7. RECOMMENDATION RELEVANCE ──────────────────────────────────────────────
print("\n=== RECOMMENDATION CATEGORIES ===")
REC_CATEGORIES = {
    'PRICE': ['price_ex_showroom'],
    'POWERTRAIN': [],  # in powertrain table
    'TRANSMISSION': ['transmission'],
    'DRIVETRAIN': ['drivetrain'],
    'EFFICIENCY': ['mileage_arai_kmpl','mileage_arai_km_per_kg','claimed_ev_range_km'],
    'SAFETY': ['airbags','abs','esc','hill_assist','tyre_pressure_monitoring_system'],
    'ADAS': ['adas_available','adas_tier','camera_360','rear_camera','rear_parking_sensors'],
    'PRACTICALITY': ['seating_capacity','boot_space_litres','fuel_tank_litres'],
    'DIMENSIONS': ['length_mm','width_mm','height_mm','wheelbase_mm','ground_clearance_mm'],
    'COMFORT': ['automatic_climate_control','rear_ac_vents','sunroof','ventilated_front_seats'],
    'INFOTAINMENT': ['android_auto','apple_carplay','heads_up_display'],
    'CONNECTIVITY': ['wireless_charging','connected_car_features'],
    'DRIVING': ['cruise_control','paddle_shifters','drive_modes'],
}
for cat, fields in REC_CATEGORIES.items():
    if not fields:
        print(f"  {cat}: (see powertrain table)")
        continue
    coverages = []
    for f in fields:
        cur.execute(f"SELECT count(*) FROM variant WHERE {f} IS NOT NULL")
        coverages.append(cur.fetchone()[0])
    avg = round(sum(coverages)/len(coverages), 0) if coverages else 0
    pct = round(100.0*avg/TOTAL_VARIANTS,1)
    print(f"  {cat}: {pct}% avg coverage ({','.join(fields[:2])} ...)")

# ── 8. CSV COMPARISON ───────────────────────────────────────────────────────
print("\n=== CSV FILE AVAILABILITY ===")
csv_paths = [
    'cars_ds_final_2021.csv',
    'carrec_recommendation_dataset_v6(5).csv',
    'knowledge_base/sources/carrec_recommendation_dataset_v6(5).csv',
    'knowledge_base/sources/v6_migration/carrec_recommendation_dataset_v6(5).csv',
]
for p in csv_paths:
    exists = os.path.exists(p)
    print(f"  {'EXISTS' if exists else 'MISSING'}: {p}")
    if exists:
        with open(p, 'r', errors='ignore') as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
            rows = sum(1 for _ in reader)
        print(f"    columns: {len(cols)}, rows: {rows}")

conn.close()
print("\n=== DONE ===")
