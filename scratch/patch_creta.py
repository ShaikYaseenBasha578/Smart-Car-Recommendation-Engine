import re
with open("knowledge_base/ingestion/oem/extractor/strategies/hyundai_creta_2024.py", "r") as f:
    code = f.read()

# Replace the loop with explicit counting
new_loop = """
        engine_context = "1.5 l MPi petrol"
        trans_count = 0
        for line in lines12:
            tokens = line.strip().split()
            if not tokens: continue
            
            trans = tokens[0]
            if trans in ["MT", "iVT", "AT", "DCT"] and len(tokens) >= 10:
                trans_count += 1
                if trans_count == 1: engine_context = "1.5 l MPi petrol"
                elif trans_count == 2: engine_context = "1.5 l MPi petrol"
                elif trans_count == 3: engine_context = "1.5 l U2 CRDi diesel"
                elif trans_count == 4: engine_context = "1.5 l U2 CRDi diesel"
                elif trans_count == 5: engine_context = "1.5 l Turbo GDi petrol"
"""

# I will just write a python script to replace the old loop in the file
