"""
OEM Ingestion Runner
Feeds extracted OEM offline data into resolver and updater.
"""

from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.common.updater import update_canonical
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

def process_oem_payload(conn, payload, make_slug, model_slug, source_id, generation_id):
    if generation_id is None:
        raise ValueError("OEM data requires an explicit generation_id to prevent historical data corruption.")

    # payload is expected to be a list of dicts, one per variant
    results = {'processed': 0, 'resolved': 0, 'unresolved': 0, 'updated': 0}
    
    for variant_data in payload:
        v_name = variant_data.get('variant_name')
        fuel = variant_data.get('fuel_type')
        trans = variant_data.get('transmission')
        cc = variant_data.get('engine_cc')
        engine_name = variant_data.get('engine_name')
        edition = variant_data.get('edition')
        
        # 1. Resolve Identity - STRICT generation pinning
        v_id, status, cand = resolve_variant(
            conn, make_slug, model_slug, v_name, v_name, 
            fuel, trans, cc, None, 
            generation_id=generation_id, active_only=False, source_name='oem',
            engine_name=engine_name, edition=edition
        )
        
        results['processed'] += 1
        
        if v_id:
            results['resolved'] += 1
            # 2. Map and Update
            normalized = map_oem_fields(variant_data)
            obs_id, upd_count = update_canonical(
                conn, v_id, source_id, 'offline_brochure', v_name, variant_data, 
                status, normalized, base_variant_id=None
            )
            results['updated'] += upd_count
        else:
            results['unresolved'] += 1
            
    return results

def resolve_oem_generation(conn, make_name, model_name, start_year):
    '''
    Strictly resolves exactly ONE generation for OEM ingestion.
    Fails closed if 0 or >1 matches are found to prevent ambiguity.
    '''
    cur = conn.cursor()
    # Normalize strings for matching
    make_clean = str(make_name).lower().replace('-', ' ').strip()
    model_clean = str(model_name).lower().replace('-', ' ').strip()
    
    if start_year is None:
        cur.execute('''
            SELECT g.id, g.name 
            FROM generation g
            JOIN model m ON g.model_id = m.id
            JOIN manufacturer mk ON m.manufacturer_id = mk.id
            WHERE LOWER(mk.name) = ? AND LOWER(m.name) = ?
        ''', (make_clean, model_clean))
    else:
        cur.execute('''
            SELECT g.id, g.name 
            FROM generation g
            JOIN model m ON g.model_id = m.id
            JOIN manufacturer mk ON m.manufacturer_id = mk.id
            WHERE LOWER(mk.name) = ? AND LOWER(m.name) = ? AND g.start_year = ?
        ''', (make_clean, model_clean, start_year))
    
    rows = cur.fetchall()
    
    if len(rows) == 0:
        raise ValueError(f"Generation Pinning Failed: 0 matches found for {make_clean} {model_clean} starting {start_year}.")
    
    if len(rows) > 1:
        raise ValueError(f"Generation Pinning Failed: Ambiguous lookup. {len(rows)} matches found for {make_clean} {model_clean} starting {start_year}.")
        
    return rows[0][0]
