import sys
import os
import sqlite3
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import compute_similarity
print(compute_similarity("E", "E Petrol MT"))
