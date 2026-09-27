import sys, os, pdfplumber, json, re
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

def evaluate_model(model_name, pdf_path):
    strategy = classify_layout(pdf_path, "", model_name)
    strat_name = strategy.__class__.__name__ if strategy else "None"
    
    if strat_name not in ["VariantColumnMatrixStrategy", "BorderlessVariantColumnMatrixStrategy"]:
        return {"model": model_name, "strategy": strat_name, "vcm_audit": None}
        
    vcm = VariantColumnMatrixStrategy()
    with pdfplumber.open(pdf_path) as pdf:
        c_page, feature_rows, variants = vcm._discover_structure(pdf)
        
        if c_page == -1:
            return {"model": model_name, "strategy": strat_name, "vcm_audit": {"status": "NO_MATRIX_PASSED"}}
            
        header = [v['raw_variant_name'] for v in variants]
        total_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip())
        bool_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip() and (str(cell).lower().strip() in ['y', 'n', 's', '-', 'o', 'na', 'std'] or re.search(r'[✔√●]', str(cell).lower().strip())))
        num_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip() and re.fullmatch(r'[\d\.,]+', str(cell).lower().strip()))
        
        return {
            "model": model_name,
            "strategy": strat_name,
            "vcm_audit": {
                "status": "EXTRACTED",
                "page": c_page,
                "header": header,
                "body_rows": len(feature_rows),
                "bool_density": round(bool_cells/total_cells if total_cells else 0, 2),
                "num_density": round(num_cells/total_cells if total_cells else 0, 2)
            }
        }

with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)
    
results = []
for r in report['reports']:
    try:
        res = evaluate_model(r['model'], r['brochure_path'])
        res['final_status'] = r['status']
        results.append(res)
    except Exception as e:
        print(f"Error on {r['model']}: {e}")

with open("scratch/vcm_audit_results.json", "w") as f:
    json.dump(results, f, indent=2)

