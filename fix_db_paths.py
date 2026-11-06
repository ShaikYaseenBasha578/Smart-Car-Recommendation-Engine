import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)))))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import os

for script in ['knowledge_base/ingestion/carwale/ingest_carwale.py', 'knowledge_base/ingestion/v3cars/ingest_v3cars.py', 'knowledge_base/ingestion/91wheels/ingest_91wheels.py', 'knowledge_base/ingestion/91wheels/batch_runner.py', 'knowledge_base/ingestion/v3cars/batch_runner_v3cars.py']:
    if not os.path.exists(script): continue
    with open(script, 'r') as f:
        code = f.read()
        
    code = code.replace("os.path.join(os.path.dirname(__file__), '..', KB_PATH)", "os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', KB_PATH))")
    code = code.replace("os.path.join(os.path.dirname(__file__), KB_PATH)", "os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', KB_PATH))")
    code = code.replace("KB_PATH", "os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', KB_PATH))")
    
    with open(script, 'w') as f:
        f.write(code)
