import sqlite3

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
c = conn.cursor()

def q_val(query, params=()):
    c.execute(query, params)
    res = c.fetchone()
    return res[0] if res else 0

fields = {
    'cruise_control': 'cruise_control',
    'heads_up_display': 'heads_up_display',
    'boot_space_litres': 'boot_space_litres',
    'transmission': 'transmission',
    'price': 'price_ex_showroom',
    'sunroof': 'sunroof',
    'ADAS': 'adas_available',
    'ventilated_seats': 'ventilated_front_seats',
    'TPMS': 'tyre_pressure_monitoring_system'
}

print("=== Field Level Enrichment ===")
print(f"{'Field (Alias)':<20} | {'Pre-Null':<10} | {'Post-Null':<10} | {'Newly Pop':<10} | {'Rejected':<10} | {'Edition Ov':<10}")
print("-" * 75)

for display_name, col_name in fields.items():
    post_null = q_val(f"SELECT COUNT(*) FROM variant WHERE edition_classification IS NULL AND {col_name} IS NULL")
    
    # CW extraction mapped fields
    if display_name == 'price': prov_field = 'price'
    elif display_name == 'ADAS': prov_field = 'adas'
    elif display_name == 'ventilated_seats': prov_field = 'ventilated_seats'
    elif display_name == 'TPMS': prov_field = 'tpms'
    else: prov_field = col_name

    newly_pop = q_val(f"""
        SELECT COUNT(DISTINCT variant_id) FROM field_provenance 
        WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4) 
        AND field_name = '{prov_field}' 
        AND decision = 'accepted' AND decision_reason = 'new_field'
        AND variant_id IN (SELECT id FROM variant WHERE edition_classification IS NULL)
    """)
    
    rejected = q_val(f"""
        SELECT COUNT(*) FROM field_provenance 
        WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4) 
        AND field_name = '{prov_field}' 
        AND decision = 'rejected'
    """)
    
    edition_ov = q_val(f"""
        SELECT COUNT(*) FROM field_provenance 
        WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4) 
        AND field_name = '{prov_field}' 
        AND decision = 'accepted' AND decision_reason = 'edition_override_or_correction'
    """)
    
    pre_null = post_null + newly_pop
    
    print(f"{display_name:<20} | {pre_null:<10} | {post_null:<10} | {newly_pop:<10} | {rejected:<10} | {edition_ov:<10}")

