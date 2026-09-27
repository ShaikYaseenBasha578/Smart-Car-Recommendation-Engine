with open('knowledge_base/ingestion/oem/extractor/classifier.py', 'r') as f:
    lines = f.readlines()
    
out = []
for l in lines:
    if "if res[0] != -1:" in l:
        out.append("                if res[0] > 10:\n") # Need a strictly positive score to trust bordered strategy
    else:
        out.append(l)

with open('knowledge_base/ingestion/oem/extractor/classifier.py', 'w') as f:
    f.writelines(out)
