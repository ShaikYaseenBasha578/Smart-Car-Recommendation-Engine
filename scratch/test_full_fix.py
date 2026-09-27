import sys
import os
import sqlite3
import re
sys.path.append(os.getcwd())

from knowledge_base.ingestion.common.resolver import compute_similarity

def normalize_engine_string(engine_str):
    if not engine_str: return ""
    s = engine_str.lower()
    s = re.sub(r'(\d\.\d)\s*l(?!\w)', r'\1', s)
    s = s.replace('petrol', '').replace('diesel', '').replace('cng', '')
    s = s.replace('bi-fuel', '').replace('with hy-', '')
    return re.sub(r'\s+', ' ', s).strip()

def validate_structured(c, fuel, trans, cc, price):
    warnings = []
    if fuel and c['fuel_type']:
        f1, f2 = fuel.lower(), c['fuel_type'].lower()
        if f1 != f2:
            if not (f1 == 'cng' and 'cng' in f2):
                warnings.append('fuel_mismatch')
    if trans and c['transmission']:
        t1 = 'auto' if trans.lower() in ['automatic', 'amt', 'cvt', 'dct', 'tc', 'ivt', 'dca', 'torque converter', 'e-cvt'] else 'manual'
        t2 = 'auto' if c['transmission'].lower() in ['automatic', 'amt', 'cvt', 'dct', 'tc', 'ivt', 'torque converter', 'e-cvt'] else 'manual'
        if t1 != t2:
            warnings.append('transmission_mismatch')
    return warnings

def test_resolve(model, variant_name, fuel, trans, engine_name):
    conn = sqlite3.connect("knowledge_base/carrec_kb.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT v.id, v.name, pt.fuel_type, pt.engine_cc, v.transmission FROM variant v JOIN model m ON v.model_id = m.id JOIN powertrain pt ON v.powertrain_id = pt.id WHERE m.name = ?", (model,))
    all_variants = [dict(r) for r in cur.fetchall()]
    
    candidates = []
    
    test_name = variant_name
    if engine_name:
        test_name += " " + normalize_engine_string(engine_name)
        
    for c in all_variants:
        if validate_structured(c, fuel, trans, None, None):
            continue
            
        score = compute_similarity(test_name, c['name'])
        
        candidates.append((score, c['name']))
        
    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"\n--- {model}: {variant_name} | {fuel} | {trans} | {engine_name} ---")
    print(f"Test Name: '{test_name}'")
    if not candidates:
        print("No candidates.")
        return
        
    for c in candidates[:3]:
        print(f"  {c[0]:.2f}: {c[1]}")
        
    if candidates[0][0] > 0.5:
        if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.05:
            print("RESULT: MARGIN FAILURE")
        else:
            print("RESULT: SUCCESS")
    else:
        print("RESULT: SCORE TOO LOW")

test_resolve("Fronx", "Sigma", "CNG", "Manual", "1.2L")
test_resolve("Swift", "VXi", "Petrol", "Manual", None)
test_resolve("Kylaq", "Classic", "Petrol", "Manual", None)
test_resolve("Aura", "SX", "Petrol", "Manual", "1.2 l Kappa petrol")
