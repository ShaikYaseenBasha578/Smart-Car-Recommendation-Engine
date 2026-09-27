import time
import json
import os
import subprocess
import sys

STATE_FILE = 'knowledge_base/carwale_batch_state.json'

print("Waiting for batch runner to complete 62 models...")
while True:
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            count = len(state.get('processed_models', []))
            print(f"Progress: {count}/62 models")
            if count >= 62:
                print("All 62 models processed!")
                break
    except Exception:
        pass
    time.sleep(10)

print("Running post-crawl audit script...")
subprocess.run(['python3', 'knowledge_base/reports/audit_carwale_crawl.py'])

print("Running idempotency test...")
with open(STATE_FILE, 'r') as f:
    state = json.load(f)

# Pop 3 models for idempotency
subset = state['processed_models'][-3:]
for m in subset:
    state['processed_models'].remove(m)
    if m in state['results']:
        del state['results'][m]
    
with open(STATE_FILE, 'w') as f:
    json.dump(state, f)

print(f"Rerunning for models: {subset}")
subprocess.run(['python3', '-m', 'knowledge_base.ingestion.carwale.batch_runner_carwale'])
subprocess.run(['python3', 'knowledge_base/reports/audit_carwale_crawl.py', '> knowledge_base/reports/final_audit.txt'])

print("Idempotency check done! Wake up the agent.")
