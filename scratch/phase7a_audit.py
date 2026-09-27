#!/usr/bin/env python3
"""
Phase 7A — Powertrain-Aware Coverage Audit (READ-ONLY)
"""
import sqlite3, csv, json, os
from collections import defaultdict

DB = "knowledge_base/carrec_kb.db"
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
c = conn.cursor()

TOTAL_VARIANTS = 832

# ── HELPER ────────────────────────────────────────────────────────────────────
def q(sql, params=()):
    c.execute(sql, params)
    return c.fetchall()

def q1(sql, params=()):
    c.execute(sql, params)
    r = c.fetchone()
    return r[0] if r else 0

# ── 1. POWERTRAIN POPULATION ──────────────────────────────────────────────────
print("=== POWERTRAIN POPULATION ===")
# The variant table links to powertrain via powertrain_id.
# powertrain table has fuel_type.
# Some variants have no powertrain_id (NULL) — treat as unlinked.

pt_pop = q("""
    SELECT
        COALESCE(p.fuel_type, 'UNLINKED') as fuel_type,
        count(v.id) as variant_count
    FROM variant v
    LEFT JOIN powertrain p ON v.powertrain_id = p.id
    GROUP BY COALESCE(p.fuel_type, 'UNLINKED')
    ORDER BY variant_count DESC
""")

fuel_populations = {}
for row in pt_pop:
    fuel = row['fuel_type']
    cnt  = row['variant_count']
    fuel_populations[fuel] = cnt
    pct = round(100.0 * cnt / TOTAL_VARIANTS, 1)
    print(f"  {fuel}: {cnt} variants ({pct}%)")

# Aggregate for analysis convenience
petrol_fuels   = {'Petrol', 'Flex Fuel'}
diesel_fuels   = {'Diesel', 'Diesel Mild Hybrid'}
hybrid_fuels   = {'Petrol Hybrid', 'Diesel Mild Hybrid'}
electric_fuels = {'Electric'}
cng_fuels      = {'CNG'}

def pop(*fuel_set):
    return sum(fuel_populations.get(f, 0) for f in fuel_set)

petrol_variants   = pop(*petrol_fuels)
diesel_variants   = pop(*diesel_fuels)
hybrid_variants   = pop(*hybrid_fuels)
electric_variants = pop(*electric_fuels)
cng_variants      = pop(*cng_fuels)

print(f"\n  Aggregated groups:")
print(f"    Petrol (incl Flex Fuel):       {petrol_variants}")
print(f"    Diesel (incl Diesel MH):       {diesel_variants}")
print(f"    CNG:                           {cng_variants}")
print(f"    Electric:                      {electric_variants}")
print(f"    Hybrid (Strong/Mild):          {hybrid_variants}")

# ── 2. PETROL MILEAGE ─────────────────────────────────────────────────────────
print("\n=== PETROL — mileage_arai_kmpl ===")
petrol_total = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type IN ('Petrol','Flex Fuel')
""")
petrol_populated = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type IN ('Petrol','Flex Fuel')
      AND v.mileage_arai_kmpl IS NOT NULL
""")
petrol_missing = petrol_total - petrol_populated
petrol_pct = round(100.0 * petrol_populated / petrol_total, 1) if petrol_total else 0

# source-backed: has at least one field_provenance row for mileage_arai_kmpl
petrol_src_backed = q1("""
    SELECT count(distinct v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    JOIN field_provenance fp ON fp.variant_id = v.id AND fp.field_name = 'mileage_arai_kmpl'
    WHERE p.fuel_type IN ('Petrol','Flex Fuel')
""")
print(f"  Applicable: {petrol_total} | Populated: {petrol_populated} | Missing: {petrol_missing} | Coverage: {petrol_pct}%")
print(f"  Source-backed: {petrol_src_backed} / {petrol_total} ({round(100.0*petrol_src_backed/petrol_total,1)}%)")

# ── 3. DIESEL MILEAGE ─────────────────────────────────────────────────────────
print("\n=== DIESEL — mileage_arai_kmpl ===")
diesel_total = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type IN ('Diesel','Diesel Mild Hybrid')
""")
diesel_populated = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type IN ('Diesel','Diesel Mild Hybrid')
      AND v.mileage_arai_kmpl IS NOT NULL
""")
diesel_missing = diesel_total - diesel_populated
diesel_pct = round(100.0 * diesel_populated / diesel_total, 1) if diesel_total else 0
diesel_src_backed = q1("""
    SELECT count(distinct v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    JOIN field_provenance fp ON fp.variant_id = v.id AND fp.field_name = 'mileage_arai_kmpl'
    WHERE p.fuel_type IN ('Diesel','Diesel Mild Hybrid')
""")
print(f"  Applicable: {diesel_total} | Populated: {diesel_populated} | Missing: {diesel_missing} | Coverage: {diesel_pct}%")
print(f"  Source-backed: {diesel_src_backed} / {diesel_total} ({round(100.0*diesel_src_backed/diesel_total,1)}%)")

# ── 4. CNG MILEAGE ───────────────────────────────────────────────────────────
print("\n=== CNG — mileage_arai_km_per_kg ===")
cng_total = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type = 'CNG'
""")
cng_populated = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type = 'CNG'
      AND v.mileage_arai_km_per_kg IS NOT NULL
""")
cng_missing = cng_total - cng_populated
cng_pct = round(100.0 * cng_populated / cng_total, 1) if cng_total else 0
cng_src_backed = q1("""
    SELECT count(distinct v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    JOIN field_provenance fp ON fp.variant_id = v.id AND fp.field_name = 'mileage_arai_km_per_kg'
    WHERE p.fuel_type = 'CNG'
""")
# Does mileage_arai_kmpl also apply to CNG? (dual-fuel CNG variants often have both)
cng_also_has_kmpl = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type = 'CNG'
      AND v.mileage_arai_kmpl IS NOT NULL
""")
print(f"  Applicable: {cng_total} | Populated (km_per_kg): {cng_populated} | Missing: {cng_missing} | Coverage: {cng_pct}%")
print(f"  Source-backed (km_per_kg): {cng_src_backed} / {cng_total}")
print(f"  Also have mileage_arai_kmpl: {cng_also_has_kmpl} (dual-fuel petrol mileage)")

# ── 5. EV RANGE ──────────────────────────────────────────────────────────────
print("\n=== ELECTRIC — claimed_ev_range_km ===")
ev_total = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type = 'Electric'
""")
ev_populated = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type = 'Electric'
      AND v.claimed_ev_range_km IS NOT NULL
""")
ev_missing = ev_total - ev_populated
ev_pct = round(100.0 * ev_populated / ev_total, 1) if ev_total else 0
ev_src_backed = q1("""
    SELECT count(distinct v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    JOIN field_provenance fp ON fp.variant_id = v.id AND fp.field_name = 'claimed_ev_range_km'
    WHERE p.fuel_type = 'Electric'
""")
print(f"  Applicable: {ev_total} | Populated: {ev_populated} | Missing: {ev_missing} | Coverage: {ev_pct}%")
print(f"  Source-backed: {ev_src_backed} / {ev_total} ({round(100.0*ev_src_backed/ev_total,1) if ev_total else 0}%)")

# Check if any EV variant has mileage_arai_kmpl (should be NULL)
ev_has_kmpl = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type = 'Electric' AND v.mileage_arai_kmpl IS NOT NULL
""")
print(f"  EV variants with mileage_arai_kmpl (should be 0): {ev_has_kmpl}")

# ── 6. HYBRID ────────────────────────────────────────────────────────────────
print("\n=== HYBRID — efficiency fields ===")
hybrid_total = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type IN ('Petrol Hybrid','Diesel Mild Hybrid')
""")
hybrid_kmpl = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type IN ('Petrol Hybrid','Diesel Mild Hybrid')
      AND v.mileage_arai_kmpl IS NOT NULL
""")
hybrid_range = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id = p.id
    WHERE p.fuel_type IN ('Petrol Hybrid','Diesel Mild Hybrid')
      AND v.claimed_ev_range_km IS NOT NULL
""")
print(f"  Hybrid total: {hybrid_total}")
print(f"  mileage_arai_kmpl populated: {hybrid_kmpl} / {hybrid_total} ({round(100.0*hybrid_kmpl/hybrid_total,1) if hybrid_total else 0}%)")
print(f"  claimed_ev_range_km populated: {hybrid_range} / {hybrid_total}")

# Breakdown by sub-type
for ft in ('Petrol Hybrid','Diesel Mild Hybrid'):
    tot = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE p.fuel_type=?", (ft,))
    pop_ = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE p.fuel_type=? AND v.mileage_arai_kmpl IS NOT NULL", (ft,))
    print(f"    {ft}: {pop_}/{tot} mileage_arai_kmpl populated")

# ── 7. VARIANTS WITH NO POWERTRAIN LINK ──────────────────────────────────────
print("\n=== UNLINKED VARIANTS (no powertrain_id) ===")
unlinked = q1("SELECT count(*) FROM variant WHERE powertrain_id IS NULL")
print(f"  Variants with NULL powertrain_id: {unlinked}")
if unlinked > 0:
    rows = q("""
        SELECT mk.name||' '||m.name as car, v.name, v.transmission
        FROM variant v
        JOIN model m ON v.model_id=m.id
        JOIN manufacturer mk ON m.manufacturer_id=mk.id
        WHERE v.powertrain_id IS NULL LIMIT 10
    """)
    for r in rows:
        print(f"    {r['car']} — {r['name']} ({r['transmission']})")

# ── 8. NULL CLASSIFICATION for mileage_arai_kmpl ─────────────────────────────
print("\n=== NULL CLASSIFICATION for mileage_arai_kmpl ===")
# For non-EV variants (petrol/diesel/hybrid/flex):
# A = genuinely missing (no provenance at all)
# B = not applicable (EV/CNG variants)
# C = provenance exists but canonical value is NULL (unresolved)
non_ev_total = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id=p.id
    WHERE p.fuel_type NOT IN ('Electric','CNG')
""")
non_ev_populated = q1("""
    SELECT count(v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id=p.id
    WHERE p.fuel_type NOT IN ('Electric','CNG')
      AND v.mileage_arai_kmpl IS NOT NULL
""")
non_ev_missing = non_ev_total - non_ev_populated

# Of the missing: how many have NO provenance for this field?
no_prov = q1("""
    SELECT count(distinct v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id=p.id
    WHERE p.fuel_type NOT IN ('Electric','CNG')
      AND v.mileage_arai_kmpl IS NULL
      AND v.id NOT IN (SELECT variant_id FROM field_provenance WHERE field_name='mileage_arai_kmpl')
""")
# How many have provenance but still NULL canonical?
has_prov_null = q1("""
    SELECT count(distinct v.id) FROM variant v
    JOIN powertrain p ON v.powertrain_id=p.id
    WHERE p.fuel_type NOT IN ('Electric','CNG')
      AND v.mileage_arai_kmpl IS NULL
      AND v.id IN (SELECT variant_id FROM field_provenance WHERE field_name='mileage_arai_kmpl')
""")
print(f"  Non-EV/CNG applicable variants: {non_ev_total}")
print(f"  Populated: {non_ev_populated}")
print(f"  Missing (NULL): {non_ev_missing}")
print(f"    A. No provenance at all (genuine gap): {no_prov}")
print(f"    C. Has provenance but canonical=NULL:  {has_prov_null}")
print(f"    B. Not applicable (EV/CNG): counted separately above")

# ── 9. SOURCE COVERAGE for efficiency fields ──────────────────────────────────
print("\n=== SOURCE COVERAGE FOR EFFICIENCY FIELDS ===")
for field in ('mileage_arai_kmpl', 'mileage_arai_km_per_kg', 'claimed_ev_range_km'):
    total_prov = q1("SELECT count(*) FROM field_provenance WHERE field_name=?", (field,))
    distinct_variants = q1("SELECT count(distinct variant_id) FROM field_provenance WHERE field_name=?", (field,))
    canonical_pop = q1(f"SELECT count(*) FROM variant WHERE {field} IS NOT NULL")
    
    src_rows = q("""
        SELECT s.name, s.source_type, s.authority_tier, count(*) as cnt
        FROM field_provenance fp
        JOIN source_observation so ON fp.source_observation_id=so.id
        JOIN source s ON so.source_id=s.id
        WHERE fp.field_name=?
        GROUP BY s.id ORDER BY cnt DESC
    """, (field,))
    
    multi = len(src_rows) > 1
    print(f"  {field}:")
    print(f"    Canonical populated: {canonical_pop}")
    print(f"    Total provenance rows: {total_prov} across {distinct_variants} variants")
    print(f"    Sources ({len(src_rows)}):")
    for sr in src_rows:
        print(f"      [{sr['authority_tier']}] {sr['name']} ({sr['source_type']}): {sr['cnt']} prov rows")
    print(f"    Multi-source: {'YES' if multi else 'NO'}")

# ── 10. MODEL-LEVEL EFFICIENCY COVERAGE ──────────────────────────────────────
print("\n=== MODEL-LEVEL EFFICIENCY COVERAGE ===")
models = q("""
    SELECT m.id, mk.name as make, m.name as model
    FROM model m JOIN manufacturer mk ON m.manufacturer_id=mk.id
    ORDER BY mk.name, m.name
""")

model_rows = []
for m in models:
    mid = m['id']

    # Petrol
    pet_t = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type IN ('Petrol','Flex Fuel')", (mid,))
    pet_p = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type IN ('Petrol','Flex Fuel') AND v.mileage_arai_kmpl IS NOT NULL", (mid,))
    # Diesel
    die_t = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type IN ('Diesel','Diesel Mild Hybrid')", (mid,))
    die_p = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type IN ('Diesel','Diesel Mild Hybrid') AND v.mileage_arai_kmpl IS NOT NULL", (mid,))
    # CNG
    cng_t = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type='CNG'", (mid,))
    cng_p = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type='CNG' AND v.mileage_arai_km_per_kg IS NOT NULL", (mid,))
    # EV
    ev_t  = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type='Electric'", (mid,))
    ev_p  = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type='Electric' AND v.claimed_ev_range_km IS NOT NULL", (mid,))
    # Hybrid
    hyb_t = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type IN ('Petrol Hybrid','Diesel Mild Hybrid')", (mid,))
    hyb_p = q1("SELECT count(v.id) FROM variant v JOIN powertrain p ON v.powertrain_id=p.id WHERE v.model_id=? AND p.fuel_type IN ('Petrol Hybrid','Diesel Mild Hybrid') AND v.mileage_arai_kmpl IS NOT NULL", (mid,))

    def cov(p, t):
        return round(100.0*p/t, 0) if t > 0 else None

    row = {
        'make': m['make'], 'model': m['model'],
        'petrol_total': pet_t, 'petrol_pop': pet_p, 'petrol_cov': cov(pet_p, pet_t),
        'diesel_total': die_t, 'diesel_pop': die_p, 'diesel_cov': cov(die_p, die_t),
        'cng_total': cng_t,    'cng_pop': cng_p,   'cng_cov': cov(cng_p, cng_t),
        'ev_total': ev_t,      'ev_pop': ev_p,      'ev_cov': cov(ev_p, ev_t),
        'hybrid_total': hyb_t, 'hybrid_pop': hyb_p, 'hybrid_cov': cov(hyb_p, hyb_t),
    }
    model_rows.append(row)

    # Print only models with gaps
    parts = []
    if pet_t > 0: parts.append(f"Petrol:{pet_p}/{pet_t}={cov(pet_p,pet_t)}%")
    if die_t > 0: parts.append(f"Diesel:{die_p}/{die_t}={cov(die_p,die_t)}%")
    if cng_t > 0: parts.append(f"CNG:{cng_p}/{cng_t}={cov(cng_p,cng_t)}%")
    if ev_t  > 0: parts.append(f"EV:{ev_p}/{ev_t}={cov(ev_p,ev_t)}%")
    if hyb_t > 0: parts.append(f"Hybrid:{hyb_p}/{hyb_t}={cov(hyb_p,hyb_t)}%")
    if parts:
        print(f"  {m['make']} {m['model']}: {' | '.join(parts)}")

# Write CSV
os.makedirs('scratch', exist_ok=True)
with open('scratch/phase7a_powertrain_coverage.csv', 'w', newline='') as f:
    fnames = ['make','model',
              'petrol_total','petrol_pop','petrol_cov',
              'diesel_total','diesel_pop','diesel_cov',
              'cng_total','cng_pop','cng_cov',
              'ev_total','ev_pop','ev_cov',
              'hybrid_total','hybrid_pop','hybrid_cov']
    w = csv.DictWriter(f, fieldnames=fnames)
    w.writeheader()
    w.writerows(model_rows)
print(f"\nWrote scratch/phase7a_powertrain_coverage.csv")

# ── 11. OLD vs NEW METRICS ────────────────────────────────────────────────────
print("\n=== OLD vs CORRECTED METRICS ===")
print(f"  mileage_arai_kmpl:")
print(f"    OLD (global):    {449}/{TOTAL_VARIANTS} = {round(100.0*449/TOTAL_VARIANTS,1)}%")
print(f"    Petrol correct:  {petrol_populated}/{petrol_total} = {petrol_pct}%")
print(f"    Diesel correct:  {diesel_populated}/{diesel_total} = {diesel_pct}%")
print(f"  mileage_arai_km_per_kg:")
print(f"    OLD (global):    39/{TOTAL_VARIANTS} = {round(100.0*39/TOTAL_VARIANTS,1)}%")
print(f"    CNG correct:     {cng_populated}/{cng_total} = {cng_pct}%")
print(f"  claimed_ev_range_km:")
print(f"    OLD (global):    35/{TOTAL_VARIANTS} = {round(100.0*35/TOTAL_VARIANTS,1)}%")
print(f"    EV correct:      {ev_populated}/{ev_total} = {ev_pct}%")

# ── 12. PRIORITY ASSESSMENT ───────────────────────────────────────────────────
print("\n=== PRIORITY ASSESSMENT ===")
def classify(pct):
    if pct is None: return "NO DATA"
    if pct >= 85: return "WELL COVERED"
    if pct >= 60: return "MODERATELY COVERED"
    if pct >= 30: return "SIGNIFICANT GAP"
    return "CRITICAL GAP"

print(f"  Petrol mileage ({petrol_pct}%): {classify(petrol_pct)}")
print(f"  Diesel mileage ({diesel_pct}%): {classify(diesel_pct)}")
print(f"  CNG mileage ({cng_pct}%): {classify(cng_pct)}")
print(f"  EV range ({ev_pct}%): {classify(ev_pct)}")
print(f"  Hybrid mileage ({round(100.0*hybrid_kmpl/hybrid_total,1) if hybrid_total else 0}%): {classify(round(100.0*hybrid_kmpl/hybrid_total,1) if hybrid_total else None)}")

conn.close()

print("\n=== AUDIT COMPLETE ===")
print("Production DB was opened READ-ONLY. Zero mutations.")
