import sqlite3
import json
import time
import os
import sys

# Ensure ingest_v3cars is in path if run from root
sys.path.append(os.path.join(os.path.dirname(__file__), 'ingestion'))

from ingest_v3cars import ingest_model

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'carrec_kb.db'))))
STATE_FILE = os.path.join(os.path.dirname(__file__), 'v3cars_batch_state.json')

def get_models():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT ma.name as make, m.name as model
        FROM model m
        JOIN manufacturer ma ON m.manufacturer_id = ma.id
        ORDER BY ma.name, m.name
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'completed': []}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def run_batch():
    models = get_models()
    state = load_state()
    
    total = len(models)
    print(f"Total models to process: {total}")
    
    for make, model in models:
        make_slug = make.lower().replace(' ', '-')
        model_slug = model.lower().replace(' ', '-')
        model_id = f"{make_slug}_{model_slug}"
        
        if model_id in state['completed']:
            print(f"Skipping {model_id}, already completed.")
            continue
            
        print(f"Processing {model_id}...")
        try:
            stats = ingest_model(make_slug, model_slug)
            print(f"Stats for {model_id}: {stats}")
            state['completed'].append(model_id)
            state[model_id] = stats
            save_state(state)
        except Exception as e:
            print(f"Error processing {model_id}: {e}")
            
        time.sleep(1.5) # Polite delay
        
    print("Batch run complete.")

if __name__ == '__main__':
    run_batch()
