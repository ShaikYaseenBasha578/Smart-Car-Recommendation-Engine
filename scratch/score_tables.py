import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
with open("knowledge_base/sources/oem/batch_report.json") as f: report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Swift')

strat = VariantColumnMatrixStrategy()
with pdfplumber.open(path) as pdf:
    tables = pdf.pages[5].extract_tables()
    for t_idx, matrix in enumerate(tables):
        clean_matrix = []
        for row in matrix:
            clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
            if any(clean_row):
                clean_matrix.append(clean_row)
        if len(clean_matrix) < 3: continue
        for r_idx, row in enumerate(clean_matrix[:5]):
            non_empty = [c for c in row if c]
            if len(non_empty) > 2:
                merged_headers = list(row)
                score = strat._score_candidate(r_idx, merged_headers, clean_matrix[r_idx+1:])
                print(f"Table {t_idx} r_idx {r_idx} Score: {score}")
                break
