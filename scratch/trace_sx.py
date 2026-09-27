import sys
import os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import compute_similarity

print(compute_similarity("SX", "SX MT"))
print(compute_similarity("SX 1.2 kappa", "SX MT"))
