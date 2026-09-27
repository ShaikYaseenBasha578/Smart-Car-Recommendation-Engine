import sqlite3
import json
import os
import time
from ingestion.ingest import ingest_model

STATE_FILE = 'knowledge_base/batch_state.json'

def get_models_from_kb(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT lower(replace(mfr.name, ' ', '-')) as make_slug, 
                        lower(replace(m.name, ' ', '-')) as model_slug
        FROM model m
        JOIN manufacturer mfr ON m.manufacturer_id = mfr.id
        ORDER BY make_slug, model_slug
    """)
    return cur.fetchall()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'completed': []}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def run_batch():
    conn = sqlite3.connect('knowledge_base/carrec_kb.db')
    conn.row_factory = sqlite3.Row
    models = get_models_from_kb(conn)
    state = load_state()
    completed = set(state['completed'])
    
    total = len(models)
    print(f"Found {total} models to process.")
    
    for i, row in enumerate(models):
        make = row['make_slug']
        model = row['model_slug']
        key = f"{make}/{model}"
        
        if key in completed:
            continue
            
        print(f"[{i+1}/{total}] Processing {key}...")
        try:
            res = ingest_model(conn, make, model)
            print(f"  Result: {res}")
            conn.commit()
            
            completed.add(key)
            state['completed'] = list(completed)
            save_state(state)
        except Exception as e:
            print(f"  CRITICAL ERROR processing {key}: {e}")
            # Stop runner to allow manual inspection
            break

if __name__ == '__main__':
    run_batch()
