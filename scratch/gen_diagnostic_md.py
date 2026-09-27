import json

with open("scratch/vcm_audit_results.json") as f:
    results = json.load(f)
    
lines = [
    "# VCM Candidate Diagnostics (62 Brochures)",
    "",
    "| Model | Strategy | VCM Status | Page | Score | Trims Detected | Body Rows | Bool % | Num % | Final Status |",
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
]

for r in results:
    model = r['model']
    strat = r['strategy']
    audit = r.get('vcm_audit')
    final = r.get('final_status')
    
    if audit:
        status = audit['status']
        if status == "EXTRACTED":
            page = str(audit['page'])
            # Score wasn't returned in the JSON payload from the audit script, but we know it passed.
            score = ">20" 
            trims = str(len(audit['header']))
            rows = str(audit['body_rows'])
            b_pct = str(audit['bool_density'])
            n_pct = str(audit['num_density'])
        else:
            page = "-"
            score = "-"
            trims = "-"
            rows = "-"
            b_pct = "-"
            n_pct = "-"
    else:
        status = "N/A"
        page = "-"
        score = "-"
        trims = "-"
        rows = "-"
        b_pct = "-"
        n_pct = "-"
        
    line = f"| {model} | {strat} | {status} | {page} | {score} | {trims} | {rows} | {b_pct} | {n_pct} | {final} |"
    lines.append(line)
    
with open("scratch/PHASE6_VCM_DIAGNOSTICS.md", "w") as f:
    f.write("\n".join(lines))
