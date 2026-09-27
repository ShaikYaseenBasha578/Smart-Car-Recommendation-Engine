import sqlite3
import json
import os
import time
from knowledge_base.ingestion.carwale.extractor_carwale import fetch_carwale_state, extract_variant
from knowledge_base.ingestion.carwale.field_map_carwale import map_carwale_features, map_resolver_fields
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.common.updater import update_canonical

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'carrec_kb.db'))))
CARWALE_SOURCE_ID = 4

def ensure_source_registered(conn):
    c = conn.cursor()
    c.execute("SELECT id FROM source WHERE id = ?", (CARWALE_SOURCE_ID,))
    if not c.fetchone():
        c.execute("""
            INSERT INTO source (id, name, authority_level, url)
            VALUES (?, 'CarWale', 2, 'https://www.carwale.com')
        """, (CARWALE_SOURCE_ID,))
        conn.commit()

def ingest_model_pilot(make_slug, model_slug_cw, canonical_model_slug):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_source_registered(conn)
    
    # 1. Fetch Model Page
    url = f"https://www.carwale.com/{make_slug}-cars/{model_slug_cw}/"
    print(f"Fetching {url}...")
    state = fetch_carwale_state(url)
    
    if not state:
        print("NO_DATA for model page.")
        return None
        
    versions = state.get('modelPage', {}).get('versions', [])
    if not versions:
        print("No versions found on model page.")
        return None
        
    stats = {'discovered': len(versions), 'resolved': 0, 'unresolved': 0, 'new_fields': 0}
    
    c = conn.cursor()
    # Find Model ID
    c.execute("""
        SELECT m.id FROM model m
        JOIN manufacturer ma ON m.manufacturer_id = ma.id
        WHERE LOWER(ma.name) = ? AND LOWER(m.name) = ?
    """, (make_slug.lower().replace('-', ' '), canonical_model_slug.lower().replace('-', ' ')))
    model_row = c.fetchone()
    if not model_row:
        print(f"Model {canonical_model_slug} not found in canonical!")
        return stats
    canonical_model_id = model_row['id']
    
    # Process each variant
    for i, v in enumerate(versions):
        v_name = v.get('versionName')
        v_slug = v.get('versionMaskingName')
        price = v.get('priceOverview', {}).get('price')
        if not v_slug: continue
        
        # We fetch the trim page
        v_url = f"{url}{v_slug}/"
        print(f"  Fetching {v_url}...")
        obs_data, status = extract_variant(v_url)
        time.sleep(0.5) # rate limit
        
        if status != 'SUCCESS' or not obs_data:
            stats['unresolved'] += 1
            continue
            
        # Extract features
        mapped_feats = map_carwale_features(obs_data['features'])
        
        # Combine
        normalized = {k: v for k, v in mapped_feats.items() if v is not None}
        if price: normalized['price'] = price
        
        # Resolution uses basic details from specsSummary
        ss = obs_data.get('specs_summary', {})
        # Wait, my extract_variant currently only returns features. 
        # Let's just pass None to fuel/cc/trans and let resolve_variant use name/price/trans
        fuel, cc, trans = map_resolver_fields(ss)
        if not trans: trans = normalized.get('transmission')
        
        # Attempt Identity Resolution
        target_variant_id, match_status, base_variant_id = resolve_variant(
            conn, make_slug, canonical_model_slug, v_name, v_slug, fuel=fuel, trans=trans, cc=cc, price=price
        )
        
        payload_dump = json.dumps(obs_data)
        
        if not target_variant_id and match_status != 'edition_candidate':
            update_canonical(conn, None, CARWALE_SOURCE_ID, v_url, v_name, payload_dump, 'unresolvable', {}, base_variant_id)
            stats['unresolved'] += 1
            continue
            
        stats['resolved'] += 1
        obs_id, updates = update_canonical(conn, target_variant_id, CARWALE_SOURCE_ID, v_url, v_name, payload_dump, match_status, normalized, base_variant_id)
        stats['new_fields'] += updates
        conn.commit()
        
    conn.close()
    return stats

if __name__ == '__main__':
    # Pilot run on a few models
    print("Testing Hyundai Verna (Historical):")
    print(ingest_model_pilot('hyundai', 'verna-2020', 'verna'))
    
    print("\nTesting Tata Harrier (Current):")
    # For Harrier, let's just do a limited pilot so it doesn't take 50 minutes (Harrier has 58 variants!)
    # I will modify ingest_model_pilot to slice versions[:3] for the test
