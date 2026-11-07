import sqlite3
import json
import time
import os
import sys
import argparse

from knowledge_base.ingestion.v3cars.ingest_v3cars import ingest_model
from knowledge_base.kb_db import open_kb

STATE_FILE = os.path.join(os.path.dirname(__file__), 'v3cars_batch_state.json')

def get_models(db_path):
    conn = open_kb(db_path)
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

def run_batch(db_path):
    models = get_models(db_path)
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
            stats = ingest_model(make_slug, model_slug, db_path)
            print(f"Stats for {model_id}: {stats}")
            state['completed'].append(model_id)
            state[model_id] = stats
            save_state(state)
        except Exception as e:
            print(f"Error processing {model_id}: {e}")
            
        time.sleep(1.5) # Polite delay
        
    print("Batch run complete.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    run_batch(parser.parse_args().db)
