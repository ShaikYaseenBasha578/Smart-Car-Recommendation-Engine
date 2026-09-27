import sqlite3
import json
import os
from knowledge_base.ingestion.v3cars.extractor_v3cars import build_variant_payloads
from knowledge_base.ingestion.v3cars.field_map_v3cars import (
    map_v3cars_features, extract_transmission_from_name,
    extract_fuel_from_name, extract_engine_cc_from_name, parse_price
)
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.common.updater import update_canonical

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'carrec_kb.db'))))
V3CARS_SOURCE_ID = 3

def ensure_source_registered(conn):
    c = conn.cursor()
    c.execute("SELECT id FROM source WHERE id = ?", (V3CARS_SOURCE_ID,))
    if not c.fetchone():
        c.execute("""
            INSERT INTO source (id, name, authority_level, url)
            VALUES (?, 'V3Cars', 2, 'https://www.v3cars.com')
        """, (V3CARS_SOURCE_ID,))
        conn.commit()

def ingest_model(make_slug, model_slug):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_source_registered(conn)
    
    print(f"Fetching {make_slug} {model_slug} from V3Cars...")
    variant_obs, model_obs, status = build_variant_payloads(make_slug, model_slug)
    
    if status == 'NO_DATA':
        print("Status: NO_DATA")
        return {'discovered': 0, 'resolved': 0, 'unresolved': 0, 'conflicts': 0, 'new_fields': 0}
        
    stats = {'discovered': len(variant_obs), 'resolved': 0, 'unresolved': 0, 'conflicts': 0, 'new_fields': 0}
    
    c = conn.cursor()
    
    # 1. Insert Model Level Observation (Warranty)
    for obs in model_obs:
        # Check idempotency for model-level observation
        c.execute("""
            SELECT id FROM source_observation
            WHERE source_id = ? AND raw_name = ? AND resolution_status = 'model_level'
        """, (V3CARS_SOURCE_ID, obs['raw_name']))
        if not c.fetchone():
            c.execute("""
                INSERT INTO source_observation (source_id, raw_name, raw_payload, source_url, extraction_method, resolution_status)
                VALUES (?, ?, ?, ?, ?, 'model_level')
            """, (V3CARS_SOURCE_ID, obs['raw_name'], json.dumps(obs['payload']), f"https://www.v3cars.com/{make_slug}-cars/{model_slug}", 'html_scrape'))
            conn.commit()
    
    # 2. Process Variant Observations
    for obs in variant_obs:
        raw_name = obs['v_variant_name']
        price = parse_price(obs['ex_showroom_price'])
        trans = extract_transmission_from_name(raw_name)
        fuel = extract_fuel_from_name(raw_name)
        cc = extract_engine_cc_from_name(raw_name)
        mapped_feats = map_v3cars_features(obs['features'])
        
        # Combine fields for canonical update
        normalized = dict(mapped_feats)
        if price: normalized['price'] = price
        if trans: normalized['transmission'] = trans
        if fuel: normalized['fuel_type'] = fuel
        if cc: normalized['displacement_cc'] = cc
        
        # Determine Model ID safely
        # E.g. make_slug 'hyundai', model_slug 'creta' -> match canonical DB
        c.execute("""
            SELECT m.id FROM model m
            JOIN manufacturer ma ON m.manufacturer_id = ma.id
            WHERE LOWER(ma.name) = ? AND LOWER(m.name) = ?
        """, (make_slug.lower().replace('-', ' '), model_slug.lower().replace('-', ' ')))
        model_row = c.fetchone()
        
        url = f"https://www.v3cars.com/{make_slug}-cars/{model_slug}"
        payload_dump = json.dumps(obs)
        
        if not model_row:
            # Unresolvable - Model missing
            update_canonical(conn, None, V3CARS_SOURCE_ID, url, raw_name, payload_dump, 'unresolvable', {}, base_variant_id)
            stats['unresolved'] += 1
            continue
            
        canonical_model_id = model_row[0]
        
        # Attempt Identity Resolution
        target_variant_id, match_status, base_variant_id = resolve_variant(conn, make_slug, model_slug, raw_name, "", fuel, trans, cc, price)
        
        if not target_variant_id and match_status != 'edition_candidate':
            # Unresolvable - Variant missing / bad bounds
            update_canonical(conn, None, V3CARS_SOURCE_ID, url, raw_name, payload_dump, 'unresolvable', {}, base_variant_id)
            stats['unresolved'] += 1
            continue
            
        stats['resolved'] += 1
        
        # Update Canonical & Provenance
        obs_id, updates = update_canonical(
            conn, target_variant_id, V3CARS_SOURCE_ID, url, raw_name, payload_dump, 'resolved', normalized
        )
        
        # Count stats
        if True:
            stats['new_fields'] += updates
            pass
            
    conn.commit()
    conn.close()
    return stats

if __name__ == '__main__':
    stats = ingest_model('hyundai', 'creta')
    print("Ingestion Stats:", stats)
