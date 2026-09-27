import sqlite3
import json
from knowledge_base.ingestion.carwale.extractor_carwale import extract_variant, fetch_carwale_state
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.carwale.field_map_carwale import extract_transmission_from_name, extract_fuel_from_name, extract_engine_cc_from_name, parse_price, map_carwale_features

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
conn.row_factory = sqlite3.Row

harrier_urls = [
    "smart-diesel-20l-turbo-manual",
    "pure-x-petrol-15l-turbo-manual-dark-edition",
    "adventure-x-petrol-15l-turbo-manual",
    "pure-x-diesel-20l-turbo-manual",
    "adventure-x-plus-petrol-15l-turbo-manual",
    "adventure-x-dark-edition-petrol-15l-turbo-manual",
    "pure-x-petrol-15l-turbo-automatic-tc",
    "adventure-x-plus-dark-edition-petrol-15l-turbo-manual"
]

print("| CarWale Raw Name | Proposed Base Variant | Resolution Result | Classification | Disposition | Actual Diffs |")
print("|---|---|---|---|---|---|")

for slug in harrier_urls:
    url = f"https://www.carwale.com/tata-cars/harrier/{slug}/"
    state = fetch_carwale_state(url)
    if not state:
        print(f"| {slug} | error fetching |")
        continue
    
    payload = extract_variant(state)
    if not payload:
        print(f"| {slug} | error parsing payload |")
        continue
        
    v_name = payload['VersionName']
    price = parse_price(payload.get('VersionPrice', ''))
    trans = extract_transmission_from_name(v_name)
    fuel = extract_fuel_from_name(v_name)
    cc = extract_engine_cc_from_name(v_name)
    
    target_id, match_status, base_id = resolve_variant(
        conn, 'tata', 'harrier', v_name, slug, fuel=fuel, trans=trans, cc=cc, price=price
    )
    
    if match_status == 'edition_candidate' and base_id:
        target_id = base_id
        
    if not target_id:
        print(f"| {v_name} | None | unresolvable | OUTSIDE_CANONICAL_SCOPE | Rejected | None |")
        continue
        
    c = conn.cursor()
    c.execute("SELECT name, * FROM variant WHERE id = ?", (target_id,))
    base_row = c.fetchone()
    base_name = base_row['name']
    
    normalized = map_carwale_features(payload)
    
    def norm(v):
        if v in (1, '1', 'True', 'true', True): return '1'
        if v in (0, '0', 'False', 'false', False): return '0'
        if v is None: return None
        return str(v)
        
    diffs = []
    for k, v in normalized.items():
        if k in base_row.keys():
            can_val = base_row[k]
            v_str = norm(v)
            can_str = norm(can_val)
            if v_str is not None and can_str is not None and v_str != can_str:
                diffs.append(f"{k}={v_str} (base={can_str})")
                
    cls = 'NO_MATERIAL_DIFFERENCE' if not diffs else 'FEATURE_OR_SPEC_DIFFERENCE'
    diff_str = ", ".join(diffs) if diffs else "None"
    
    if match_status != 'edition_candidate':
        cls = 'BASE_VARIANT'
        
    print(f"| {v_name} | {base_name} | {match_status if match_status != 'edition_candidate' else 'resolved'} | {cls} | Stored | {diff_str} |")

