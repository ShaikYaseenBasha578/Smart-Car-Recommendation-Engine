import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
with open("knowledge_base/sources/oem/batch_report.json") as f: report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Swift')

class Strat(VariantColumnMatrixStrategy):
    def _score_candidate(self, r_idx, merged_headers, body_rows):
        score = super()._score_candidate(r_idx, merged_headers, body_rows)
        # Apply the fix manually to see
        total_cells = sum(1 for br in body_rows for c in br[1:] if str(c).strip())
        bool_cells = sum(1 for br in body_rows for c in br[1:] if str(c).strip() and (str(c).lower().strip() in ['y', 'n', 's', '-', 'o', 'na', 'std'] or "✔" in str(c) or "" in str(c) or "√" in str(c) or "●" in str(c)))
        if total_cells > 0:
            bool_density = bool_cells / total_cells
            if bool_density > 0.1:
                score += len(body_rows) * 2
        return score

strat = Strat()
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
