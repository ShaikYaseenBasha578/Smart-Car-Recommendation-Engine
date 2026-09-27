import sys
import os
import json
import re
import pdfplumber
sys.path.append(os.getcwd())

from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

class ImprovedVariantColumnMatrixStrategy(VariantColumnMatrixStrategy):
    def _score_candidate(self, r_idx, merged_headers, body_rows):
        label = merged_headers[0].lower() if merged_headers else ""
        cols = merged_headers[1:]
        
        score = 0
        
        # 1. Technical Specification Penalty (Headers & Label)
        tech_keywords = ['length', 'width', 'height', 'wheelbase', 'capacity', 'suspension', 'brake', 'engine type', 'max power', 'max torque', 'displacement', 'dimension', 'weight']
        if any(kw in label for kw in tech_keywords):
            score -= 200
            
        valid_cols = 0
        trim_tokens = 0
        for c in cols:
            c_low = c.lower()
            if not c_low: continue
            valid_cols += 1
            
            # Trim tokens
            if re.search(r'\b(sigma|delta|zeta|alpha|lxi|vxi|zxi|zx|sx|style|classic|sport|plus|era|magna|asta|sportz|smart|pure|creative|fearless|empowered|adventure|accomplished)\b', c_low):
                score += 10
                trim_tokens += 1
                
            # Powertrain tokens
            if re.search(r'\b(mt|at|amt|cvt|dct|ags|ivt|cng|petrol|diesel|turbo|ev|electric)\b', c_low):
                score += 5
                
            # Pure numbers >= 50 (likely dimensions or power)
            if re.fullmatch(r'\d{2,}', c_low.replace(',', '').replace('.', '')):
                score -= 30
                
            # Technical specs in header
            if re.search(r'\b(water-cooled|disc|drum|mcpherson|strut|torsion|beam)\b', c_low):
                score -= 50
                
        if valid_cols == 0:
            return -1000
            
        # 2. Body scoring (Feature matrix vs Technical matrix)
        total_cells = 0
        bool_cells = 0
        numeric_cells = 0
        
        for br in body_rows:
            for c in br[1:]:
                c_clean = c.lower().strip()
                if not c_clean: continue
                total_cells += 1
                if c_clean in ['y', 'n', 's', '-', 'o', 'na', 'std'] or re.search(r'[✔√●]', c_clean):
                    bool_cells += 1
                elif re.fullmatch(r'[\d\.,]+', c_clean):
                    numeric_cells += 1
                    
        bool_density = 0.0
        numeric_density = 0.0
        if total_cells > 0:
            bool_density = bool_cells / total_cells
            numeric_density = numeric_cells / total_cells
            
            # Feature matrices have high booleans, low pure numbers
            score += (bool_density * 200)
            score -= (numeric_density * 200)
            
        # Hard fail if no trim tokens AND high numeric density
        if trim_tokens == 0 and numeric_density > 0.3:
            score -= 500
            
        return score

    def _discover_structure(self, pdf):
        provided_variants = self._get_variants()
        
        best_score = -1000
        best_candidate = None
        
        # 1. Candidate Generation & Scoring
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables: continue
            
            for matrix in tables:
                if len(matrix) < 3 or len(matrix[0]) < 2: continue
                
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
                        
                        next_r_idx = r_idx + 1
                        while next_r_idx < len(clean_matrix):
                            next_row = clean_matrix[next_r_idx]
                            first_col = next_row[0].strip().lower()
                            is_continuation = not first_col or first_col in ["variant", "variants", "powertrain", "transmission", "engine"]
                            if not is_continuation:
                                pt_count = sum(1 for c in next_row if re.search(r'\b(MT|AT|AMT|CVT|DCT|AGS|iVT|CNG|Petrol|Diesel|Turbo)\b', c, re.IGNORECASE))
                                if len([c for c in next_row if c]) > 0 and pt_count / len([c for c in next_row if c]) > 0.3:
                                    is_continuation = True
                            
                            if is_continuation:
                                for c_idx in range(len(merged_headers)):
                                    if c_idx < len(next_row) and next_row[c_idx]:
                                        merged_headers[c_idx] += " " + next_row[c_idx]
                                next_r_idx += 1
                            else:
                                break
                                
                        body_rows = clean_matrix[next_r_idx:]
                        score = self._score_candidate(r_idx, merged_headers, body_rows)
                        
                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                'page_idx': i,
                                'matrix': matrix,
                                'clean_matrix': clean_matrix,
                                'next_r_idx': next_r_idx,
                                'merged_headers': merged_headers
                            }
                            
        # 2. Threshold Check
        if best_score < 20 or not best_candidate:
            return -1, None, None
            
        # 3. Validation & Multi-page Extension
        c = best_candidate
        variants = []
        if provided_variants:
            variants = provided_variants
        else:
            for c_idx in range(1, len(c['merged_headers'])):
                header_text = c['merged_headers'][c_idx]
                if header_text:
                    expanded = self._expand_header(header_text)
                    for exp in expanded:
                        exp['col_idx'] = c_idx
                        variants.append(exp)
                        
        if not variants:
            return -1, None, None
            
        feature_rows = c['clean_matrix'][c['next_r_idx']:]
        
        # Continuation logic...
        expected_cols = max((len(r) for r in c['matrix']), default=0)
        next_page_idx = c['page_idx'] + 1
        while next_page_idx < len(pdf.pages):
            next_page = pdf.pages[next_page_idx]
            next_tables = next_page.extract_tables()
            if not next_tables: break
            
            next_tables.sort(key=lambda t: len(t), reverse=True)
            next_matrix = next_tables[0]
            
            next_cols = max((len(r) for r in next_matrix if r), default=0)
            if next_cols != expected_cols: break
                
            is_continuation_table = True
            if len(next_matrix) > 0 and len(next_matrix[0]) > 0:
                first_cell = str(next_matrix[0][0]).strip().lower() if next_matrix[0][0] else ""
                if first_cell in ["variant", "variants"] or re.search(r'\b(LXi|VXi|Sigma|Delta|Era|Magna|Sportz|Asta)\b', str(next_matrix[0]), re.IGNORECASE):
                    is_continuation_table = False
                    
            if not is_continuation_table: break
                
            for row in next_matrix:
                clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                if any(clean_row):
                    feature_rows.append(clean_row)
            next_page_idx += 1
            
        return c['page_idx'], feature_rows, variants

# Let's test on 3 specific files: Swift (success), Honda City (was hallucination), and Mg Windsor EV (was hallucination)
import json
with open("knowledge_base/sources/oem/batch_report.json", 'r') as f:
    report = json.load(f)

def test_doc(make, model):
    try:
        path = next(r['brochure_path'] for r in report['reports'] if r['make'] == make and r['model'] == model)
        strat = ImprovedVariantColumnMatrixStrategy()
        with pdfplumber.open(path) as pdf:
            page, matrix, variants = strat._discover_structure(pdf)
            print(f"\n--- {make} {model} ---")
            if page == -1:
                print("FAILED CLOSED (No valid matrix found)")
            else:
                print(f"FOUND Matrix on page {page}, rows: {len(matrix)}, variants: {len(variants)}")
                for v in variants[:3]:
                    print(f"  {v}")
    except Exception as e:
        print(f"{make} {model} Error: {e}")

test_doc("Maruti Suzuki", "Swift")
test_doc("Honda", "City")
test_doc("MG", "Windsor EV")
test_doc("Tata", "Nexon")
