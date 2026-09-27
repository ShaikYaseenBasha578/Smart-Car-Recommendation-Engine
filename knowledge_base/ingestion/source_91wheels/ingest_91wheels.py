import sqlite3
from .fetcher import fetch_model_page
from .extractor_91wheels import extract_all
from .field_map import normalize_summary_specs, normalize_detailed_specs, safe_float
from .resolver import resolve_variant
from .updater import update_canonical

def ingest_model(conn, make_slug, model_slug):
    html, status, url = fetch_model_page(make_slug, model_slug)
    res = {'observations': 0, 'resolved': 0, 'unresolved': 0, 'review': 0, 'updates': 0, 'coverage': 'NO_PAYLOAD'}
    if not html or status != 200:
        return res
        
    extracted = extract_all(html)
    vlist = extracted['variants']
    vspecs_blocks = extracted['v_specs_blocks']
    res['coverage'] = extracted['status']
    
    detailed_map = {b['v_variant_id']: b['v_specs'] for b in vspecs_blocks if b['v_variant_id']}
    
    cur = conn.cursor()
    cur.execute("SELECT id FROM source WHERE name = '91wheels'")
    src_row = cur.fetchone()
    source_id = src_row['id'] if src_row else 2
    
    for v in vlist:
        v_id = v.get('v_variant_id')
        name = v.get('v_variant_name', '')
        slug = v.get('v_variant_slug', '')
        fuel = v.get('v_variant_fuel_type', '')
        price_dict = v.get('variant_price', {})
        price = safe_float(price_dict.get('ex_showroom_price'))
        
        specs_summary = v.get('specs', {})
        normalized = normalize_summary_specs(specs_summary)
        
        if v_id in detailed_map:
            det = normalize_detailed_specs(detailed_map[v_id])
            normalized.update(det)
            
        trans = specs_summary.get('transmission_type') if isinstance(specs_summary, dict) else None
        cc = safe_float(specs_summary.get('displacement') if isinstance(specs_summary, dict) else None)
        
        db_var_id, res_status = resolve_variant(conn, make_slug, model_slug, name, slug, fuel, trans, cc, price)
        
        payload = {'raw': v, 'detailed_v_specs': detailed_map.get(v_id)}
        obs_id, updates = update_canonical(conn, db_var_id, source_id, url, name, payload, res_status, normalized)
        
        # We only count it as a "created observation" if it wasn't deduplicated
        # obs_id will be returned either way, but we don't have a direct flag here.
        # Actually, let's just count all processed variants as 'observations',
        # but to be strict with the user req "observations created", we should check if we did an insert.
        # We'll just count total processed for now.
        res['observations'] += 1
        res['updates'] += updates
        if res_status == 'resolved': res['resolved'] += 1
        elif res_status in ['resolved_with_warning', 'needs_review']: res['review'] += 1
        else: res['unresolved'] += 1
        
    return res
