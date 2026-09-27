import sqlite3
import json
import os
import time
import traceback
from knowledge_base.ingestion.carwale.ingest_carwale import ingest_model_pilot, DB_PATH

BATCH_STATE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'carwale_batch_state.json'))

def run_batch():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get all 62 models
    c.execute("""
        SELECT m.id, m.name as model_name, ma.name as make_name 
        FROM model m
        JOIN manufacturer ma ON m.manufacturer_id = ma.id
        ORDER BY ma.name, m.name
    """)
    models = c.fetchall()
    conn.close()
    
    if os.path.exists(BATCH_STATE_FILE):
        with open(BATCH_STATE_FILE, 'r') as f:
            state = json.load(f)
    else:
        state = {'processed_models': [], 'results': {}, 'global_stats': {
            'discovered': 0, 'resolved': 0, 'unresolved': 0, 'new_fields': 0
        }}
        
    for m in models:
        make = m['make_name']
        model = m['model_name']
        
        canonical_slug = model.lower().replace(' ', '-')
        make_slug = make.lower().replace(' ', '-')
        
        cw_slug = canonical_slug
        model_key = f"{make_slug}_{cw_slug}"
        
        if model_key in state['processed_models']:
            print(f"Skipping {model_key}, already processed.")
            continue
            
        print(f"\n=============================================")
        print(f"Processing Model: {make} {model}")
        print(f"=============================================")
        
        try:
            res = ingest_model_pilot(make_slug, cw_slug, canonical_slug)
            if res:
                state['results'][model_key] = res
                for k in ['discovered', 'resolved', 'unresolved', 'new_fields']:
                    state['global_stats'][k] += res.get(k, 0)
            else:
                state['results'][model_key] = 'FAILED_OR_NO_DATA'
        except Exception as e:
            print(f"ERROR on {model_key}: {e}")
            traceback.print_exc()
            state['results'][model_key] = 'ERROR'
            
        state['processed_models'].append(model_key)
        
        with open(BATCH_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
            
        # Delay between models to be respectful
        time.sleep(0.5)

if __name__ == '__main__':
    run_batch()
