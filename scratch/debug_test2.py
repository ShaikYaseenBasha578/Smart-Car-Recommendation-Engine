import sys
import os
import sqlite3
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import resolve_variant, compute_similarity

def print_scores():
    cnames = [
        'E Petrol MT',
        'E Diesel MT',
        'EX Petrol MT',
        'E Dark Edition Petrol MT',
        'E Knight Edition Petrol MT'
    ]
    for c in cnames:
        s1 = compute_similarity("E Dark Edition", c)
        print(f"Similarity E Dark Edition vs {c}: {s1}")

print_scores()
