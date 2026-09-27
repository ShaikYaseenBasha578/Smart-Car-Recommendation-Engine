import os

for script in ['knowledge_base/ingestion/carwale/ingest_carwale.py', 'knowledge_base/ingestion/v3cars/ingest_v3cars.py', 'knowledge_base/ingestion/91wheels/ingest_91wheels.py', 'knowledge_base/ingestion/91wheels/batch_runner.py', 'knowledge_base/ingestion/v3cars/batch_runner_v3cars.py']:
    if not os.path.exists(script): continue
    with open(script, 'r') as f:
        code = f.read()
        
    code = code.replace("os.path.join(os.path.dirname(__file__), '..', 'carrec_kb.db')", "os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'carrec_kb.db'))")
    code = code.replace("os.path.join(os.path.dirname(__file__), 'carrec_kb.db')", "os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'carrec_kb.db'))")
    code = code.replace("'carrec_kb.db'", "os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'carrec_kb.db'))")
    
    with open(script, 'w') as f:
        f.write(code)
