import sys
import os
import sqlite3
sys.path.append(os.getcwd())

with open("knowledge_base/ingestion/common/resolver.py", "r") as f:
    content = f.read()

new_content = content.replace("candidates.sort(key=lambda x: x[0], reverse=True)", "candidates.sort(key=lambda x: x[0], reverse=True); print('CANDIDATES:', [(s, c['name']) for s, c in candidates])")
with open("knowledge_base/ingestion/common/resolver.py", "w") as f:
    f.write(new_content)
