import sys, os, pdfplumber, json, re
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)

lines = [
    "# VCM Candidate Diagnostics (62 Brochures)",
    "",
    "| Model | Strategy | VCM Extraction | Page | Variant Columns | Body Rows | Bool % | Num % | Final Status | Classification |",
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
]

vcm = VariantColumnMatrixStrategy()

for r in report['reports']:
    model = r['model']
    final_status = r.get('extraction_status', r.get('status', 'UNKNOWN'))
    
    classification = ""
    if final_status == "ZERO_CONFIGS" or final_status == "EXTRACTION_FAILURE":
        if model in ["Bolero", "Duster", "Triber"]: classification = "IMAGE_ONLY"
        elif model in ["Amaze", "Jimny"]: classification = "VERTICAL_MATRIX"
        elif model in ["Thar", "Alto K10", "Virtus"]: classification = "BORDERLESS_MATRIX"
        elif model in ["Venue", "Verna"]: classification = "EngineTrimCrossMatrix"
        else: classification = "NO_VALID_MATRIX / TECHNICAL_ONLY"
    elif final_status == "RESOLUTION_FAILURE":
        classification = "RESOLUTION_ABBREVIATION_MISMATCH"
    elif final_status == "PDF_TEXT_FAILURE":
        classification = "PDF_TEXT_FAILURE"
    else:
        classification = "GENERIC_SUCCESS"
        
    try:
        path = r['brochure_path']
        strategy = classify_layout(path, "", model)
        strat_name = strategy.__class__.__name__ if strategy else "None"
        
        if strat_name not in ["VariantColumnMatrixStrategy", "BorderlessVariantColumnMatrixStrategy"]:
            lines.append(f"| {model} | {strat_name} | NO_MATRIX_PASSED | - | - | - | - | - | {final_status} | {classification} |")
            continue
            
        with pdfplumber.open(path) as pdf:
            c_page, feature_rows, variants = vcm._discover_structure(pdf)
            
            if c_page == -1:
                lines.append(f"| {model} | {strat_name} | NO_MATRIX_PASSED | - | - | - | - | - | {final_status} | {classification} |")
                continue
                
            header = [v['variant'] for v in variants]
            total_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip())
            bool_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip() and (str(cell).lower().strip() in ['y', 'n', 's', '-', 'o', 'na', 'std'] or re.search(r'[✔√●]', str(cell).lower().strip())))
            num_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip() and re.fullmatch(r'[\d\.,]+', str(cell).lower().strip()))
            
            b_pct = round(bool_cells/total_cells if total_cells else 0, 2)
            n_pct = round(num_cells/total_cells if total_cells else 0, 2)
            
            lines.append(f"| {model} | {strat_name} | EXTRACTED | {c_page} | {len(header)} | {len(feature_rows)} | {b_pct} | {n_pct} | {final_status} | {classification} |")
    except Exception as e:
        lines.append(f"| {model} | ERROR | ERROR | - | - | - | - | - | {final_status} | {classification} |")
        
with open("PHASE6_VCM_DIAGNOSTICS_REPORT.md", "w") as f:
    f.write("\n".join(lines))
