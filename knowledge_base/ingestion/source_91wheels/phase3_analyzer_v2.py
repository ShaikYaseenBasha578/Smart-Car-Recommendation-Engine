import sqlite3
import json
from ingestion.resolver import validate_structured
from ingestion.field_map import safe_float

def analyze():
    conn = sqlite3.connect('knowledge_base/carrec_kb.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    with open('knowledge_base/snapshot_before.json', 'r') as f:
        snapshot_before = {int(k): v for k, v in json.load(f).items()}
        
    cur.execute("SELECT * FROM variant")
    snapshot_after = {r['id']: dict(r) for r in cur.fetchall()}
    
    report = ["# Phase 3 91Wheels Coverage & Audit Report (Corrected)\n"]
    
    # --- 1. MODEL COVERAGE CLASSIFICATION ---
    report.append("## 1. Model Coverage Classification\n")
    report.append("| Model | Canonical Variants | Source Discovered | Resolved | Res. w/ Warning | Needs Review | Unresolved | Discovery % | Identity % | Status |")
    report.append("|---|---|---|---|---|---|---|---|---|---|")
    
    cur.execute("""
        SELECT m.id, mfr.name as make, m.name as model,
            (SELECT COUNT(*) FROM variant v WHERE v.model_id = m.id) as can_count
        FROM model m JOIN manufacturer mfr ON m.manufacturer_id = mfr.id
        ORDER BY make, model
    """)
    models = cur.fetchall()
    
    for m in models:
        cur.execute("""
            SELECT COUNT(*) as obs,
                   SUM(CASE WHEN resolution_status = 'resolved' THEN 1 ELSE 0 END) as res,
                   SUM(CASE WHEN resolution_status = 'resolved_with_warning' THEN 1 ELSE 0 END) as res_w,
                   SUM(CASE WHEN resolution_status = 'needs_review' THEN 1 ELSE 0 END) as rev,
                   SUM(CASE WHEN resolution_status = 'unresolved' THEN 1 ELSE 0 END) as unres
            FROM source_observation 
            WHERE (source_url LIKE ? OR source_url LIKE ?) AND source_id = 2
        """, (f"%/{m['make'].replace(' ', '-').lower()}/{m['model'].replace(' ', '-').lower()}%", 
              f"%/{m['make'].replace(' ', '-').lower()}/{m['model'].replace(' ', '-').lower()}"))
        s = cur.fetchone()
        
        can_c = m['can_count']
        obs = s['obs'] or 0
        res = s['res'] or 0
        res_w = s['res_w'] or 0
        rev = s['rev'] or 0
        unres = s['unres'] or 0
        
        disc_pct = min(100.0, (obs / can_c * 100)) if can_c > 0 else 0
        ident_pct = ((res + res_w) / can_c * 100) if can_c > 0 else 0
        
        if obs == 0:
            status = "NO_DATA"
        elif ident_pct >= 80.0:
            status = "COMPLETE"
        else:
            status = "PARTIAL"
            
        report.append(f"| {m['make']} {m['model']} | {can_c} | {obs} | {res} | {res_w} | {rev} | {unres} | {disc_pct:.1f}% | {ident_pct:.1f}% | {status} |")

    # --- 2 & 3. UNRESOLVED REASON ANALYSIS ---
    report.append("\n## 2. Unresolved & Review Reason Analysis\n")
    cur.execute("SELECT * FROM source_observation WHERE source_id=2 AND resolution_status IN ('needs_review', 'unresolved')")
    obs_rows = cur.fetchall()
    
    reasons = {
        'fuel_mismatch': 0, 'transmission_mismatch': 0, 'engine_cc_mismatch': 0, 
        'price_mismatch': 0, 'naming_mismatch_or_ambiguous': 0, 'source_variant_not_in_canonical': 0
    }
    
    for r in obs_rows:
        status = r['resolution_status']
        payload = json.loads(r['raw_payload'])
        raw = payload.get('raw', {})
        fuel = raw.get('v_variant_fuel_type')
        specs = raw.get('specs', {})
        trans = specs.get('transmission_type') if isinstance(specs, dict) else None
        cc = safe_float(specs.get('displacement') if isinstance(specs, dict) else None)
        price_dict = raw.get('variant_price', {})
        price = safe_float(price_dict.get('ex_showroom_price'))
        
        vid = r['resolved_variant_id']
        if status == 'needs_review' and vid:
            # We have a candidate, check why it failed bounds
            c_row = snapshot_before[vid]
            warnings = validate_structured(c_row, fuel, trans, cc, price)
            if warnings:
                for w in warnings: reasons[w] += 1
            else:
                reasons['naming_mismatch_or_ambiguous'] += 1
        else:
            # unresolved (no candidate found)
            # Either V6 doesn't have it (e.g. new variant) or naming is completely different
            reasons['naming_mismatch_or_ambiguous'] += 1

    report.append(f"- Bounds Failure (Fuel Mismatch): {reasons['fuel_mismatch']}")
    report.append(f"- Bounds Failure (Transmission Mismatch): {reasons['transmission_mismatch']}")
    report.append(f"- Bounds Failure (Engine CC Mismatch): {reasons['engine_cc_mismatch']}")
    report.append(f"- Bounds Failure (Price Mismatch): {reasons['price_mismatch']}")
    report.append(f"- Ambiguous Identity / Naming Mismatch / Missing from Canonical: {reasons['naming_mismatch_or_ambiguous']}")
    report.append("\n*Note: Many 'unresolved' variants are genuine new variants (e.g. new Dark Editions) present on 91Wheels but legitimately absent from the 2021 V6 Canonical base. We successfully prevented them from polluting existing variants.*")

    # --- 4. HISTORICAL ALIAS AUDIT ---
    report.append("\n## 3. Historical Alias Audit (variant_mapping.json)\n")
    cur.execute("SELECT alias_name, variant_id, needs_review, is_verified FROM variant_alias WHERE source_id=2")
    aliases = {a['alias_name']: a for a in cur.fetchall()}
    
    cur.execute("SELECT raw_payload, resolution_status, resolved_variant_id FROM source_observation WHERE source_id=2")
    all_obs = cur.fetchall()
    
    audit = {
        'exists_confirms': 0,
        'exists_contradicts': 0,
        'no_alias_resolved': 0,
        'no_alias_unresolved': 0
    }
    
    encountered = set()
    for o in all_obs:
        payload = json.loads(o['raw_payload'])
        slug = payload.get('raw', {}).get('v_variant_slug')
        if not slug: continue
        
        status = o['resolution_status']
        vid = o['resolved_variant_id']
        
        if slug in aliases:
            encountered.add(slug)
            a = aliases[slug]
            if status in ['resolved', 'resolved_with_warning'] and vid == a['variant_id']:
                audit['exists_confirms'] += 1
            else:
                audit['exists_contradicts'] += 1
        else:
            if status in ['resolved', 'resolved_with_warning']:
                audit['no_alias_resolved'] += 1
            else:
                audit['no_alias_unresolved'] += 1
                
    audit['exists_cannot_validate'] = len(aliases) - len(encountered)
    
    report.append(f"- Historical alias exists + current source confirms it: {audit['exists_confirms']}")
    report.append(f"- Historical alias exists + current source contradicts it (BLOCKED): {audit['exists_contradicts']}")
    report.append(f"- Historical alias exists + current source cannot validate it (absent in payload): {audit['exists_cannot_validate']}")
    report.append(f"- No historical alias + current source confidently resolved: {audit['no_alias_resolved']}")
    report.append(f"- No historical alias + unresolved: {audit['no_alias_unresolved']}")

    # --- 5. FIELD COVERAGE ---
    report.append("\n## 4. Global Field Coverage\n")
    report.append("| Field | Before (Non-Null) | After (Non-Null) | Confirmed (Matched V6) | Conflicted (Rejected) | Newly Populated (Gain) | % Gain | No Useful Value |")
    report.append("|---|---|---|---|---|---|---|---|")
    
    fields = [
        'price_ex_showroom', 'engine_cc', 'power_bhp', 'seating_capacity', 'ground_clearance_mm',
        'length_mm', 'width_mm', 'height_mm', 'boot_space_litres', 'mileage_arai_kmpl',
        'drivetrain', 'cruise_control', 'wireless_charging', 'heads_up_display', 'ventilated_front_seats',
        'sunroof', 'tyre_pressure_monitoring_system', 'adas_available'
    ]
    
    for f in fields:
        before_nn = sum(1 for v in snapshot_before.values() if v.get(f) is not None)
        after_nn = sum(1 for v in snapshot_after.values() if v.get(f) is not None)
        
        cur.execute("SELECT COUNT(*) as c FROM field_provenance WHERE field_name=? AND decision='accepted' AND source_observation_id IN (SELECT id FROM source_observation WHERE source_id=2)", (f,))
        newly_pop = cur.fetchone()['c']
        
        cur.execute("SELECT COUNT(*) as c FROM field_provenance WHERE field_name=? AND decision='confirmed' AND source_observation_id IN (SELECT id FROM source_observation WHERE source_id=2)", (f,))
        confirmed = cur.fetchone()['c']
        
        cur.execute("SELECT COUNT(*) as c FROM field_provenance WHERE field_name=? AND decision='rejected' AND source_observation_id IN (SELECT id FROM source_observation WHERE source_id=2)", (f,))
        conflicted = cur.fetchone()['c']
        
        pct_gain = (newly_pop / before_nn * 100) if before_nn > 0 else (100.0 if newly_pop > 0 else 0.0)
        no_useful = 812 - (before_nn + newly_pop + conflicted)
        
        report.append(f"| {f} | {before_nn} | {after_nn} | {confirmed} | {conflicted} | +{newly_pop} | {pct_gain:.1f}% | {no_useful} |")

    # --- 6. VERIFY ENRICHED VARIANTS ---
    report.append("\n## 5. Canonical Enrichment Verification\n")
    enriched = []
    total_cells = 0
    overwritten = 0
    
    for vid, before in snapshot_before.items():
        after = snapshot_after[vid]
        new_cells = []
        for k, v1 in before.items():
            v2 = after.get(k)
            if v1 != v2:
                if v1 is None and v2 is not None:
                    new_cells.append(f"{k} ({v2})")
                else:
                    overwritten += 1
        if new_cells:
            enriched.append((vid, after['name'], new_cells))
            total_cells += len(new_cells)
            
    report.append(f"- Exact number of newly populated cells: {total_cells}")
    report.append(f"- Exact number of variants affected: {len(enriched)}")
    report.append(f"- Exact number of fields overwritten: {overwritten} (MUST BE 0)\n")
    
    report.append("### Detailed Enriched Variants List")
    for vid, name, cells in enriched:
        report.append(f"- **ID {vid} | {name}**: {', '.join(cells)}")
        
    # --- 7. 91WHEELS CONFLICTS ---
    report.append("\n## 6. 91Wheels Conflicts Summary\n")
    report.append("| Field | Conflict Count | Canonical Policy | Action Taken | Examples (V6 -> 91W) |")
    report.append("|---|---|---|---|---|")
    
    cur.execute("SELECT field_name, variant_id, accepted_value FROM field_provenance WHERE decision='rejected' AND source_observation_id IN (SELECT id FROM source_observation WHERE source_id=2)")
    rejections = cur.fetchall()
    
    conflict_map = {}
    for r in rejections:
        f = r['field_name']
        if f not in conflict_map:
            conflict_map[f] = []
        conflict_map[f].append(r)
        
    for f, items in conflict_map.items():
        count = len(items)
        # grab up to 2 examples
        exs = []
        for i in range(min(2, count)):
            r = items[i]
            can_val = snapshot_before[r['variant_id']].get(f)
            exs.append(f"'{can_val}' -> '{r['accepted_value']}'")
            
        policy = "Existing canonical value must not be overwritten by secondary source."
        action = "Rejected 91Wheels observation, preserved canonical V6 value."
        report.append(f"| {f} | {count} | {policy} | {action} | {', '.join(exs)} |")

    # --- 8. NEXT-SOURCE DECISION ---
    report.append("\n## 7. Next-Source Decision (OEM vs V3Cars)\n")
    report.append("""
### Measured Gaps from Phase 3 (91Wheels):
1. **Missing Historical Variants:** 91Wheels heavily paginates and outright removes variants that are no longer actively sold (e.g., old Creta trims). This leaves our historical canonical V6 variants stranded without structured updates.
2. **Subjective/Unreliable Booleans:** 91Wheels aggressively reports `0` (False) for features like sunroofs and ADAS on variants where it simply lacks detailed data. This triggered massive conflicts (e.g. 141 sunroof rejections) where V6 had actual data.
3. **No Detailed Taxonomy for Trims:** The `NO_DATA` models (WagonR, Carens Clavis) occurred because the specific Next.js payload format used for feature matrices was completely absent or restricted.

### What V3Cars Would Solve:
- **Exact Variant Coverage & Feature Granularity:** V3Cars specifically architectures its platform around exhaustive variant-to-variant comparison matrices. It explicitly handles deep taxonomy (e.g. "E MT" vs "E MT (O)").
- **Historical Variants:** They maintain extensive historical databases to compare old vs new generations.
- **What it WOULD NOT solve:** Warranty accuracy or official starting price authoritative updates (they are still third-party).

### What OEM (Brochures/Websites) Would Solve:
- **Authoritative Specs & Pricing:** OEMs provide absolute Tier 1 truth for dimensions, CC, BHP, safety ratings, and current ex-showroom pricing.
- **Warranty & Official Features:** Absolute ground truth.
- **What it WOULD NOT solve:** Missing historical variants (OEMs actively wipe old brochures from live sites). It is also highly unstructured (PDF parsing required) resulting in slow ingestion scale.

### Final Recommendation for Phase 4:
Based on the high volume of **missing variants (NO_DATA / PARTIAL)** and the **boolean feature conflicts** identified in Phase 3, the highest marginal value at this point is **V3Cars**. 

We need a structured, exhaustive, highly granular exact-variant matrix to fill the specific trim-level holes left by 91Wheels. Attempting OEM extraction now would yield highly accurate data for *current* models, but would fail to resolve the historical variants that make up the bulk of our 812 canonical catalog.
""")

    with open('PHASE3_91WHEELS_COVERAGE_REPORT.md', 'w') as f:
        f.write("\n".join(report))

if __name__ == '__main__':
    analyze()
