import sys, os, re, pdfplumber, json
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

class AuditedVCMStrategy(VariantColumnMatrixStrategy):
    def _is_structural_trim(self, text):
        """Returns True if the string looks structurally like a vehicle trim/variant name."""
        text = text.strip()
        if not text: return False
        
        # Must have some alphabetic characters (a pure number like 4295 is not a trim)
        if not re.search(r'[a-zA-Z]', text):
            return False
            
        # Shouldn't be too long (technical specs are often long phrases)
        if len(text) > 25:
            return False
            
        # Avoid common tech specification headers
        tech_keywords = ['length', 'width', 'height', 'wheelbase', 'capacity', 'suspension', 'brake', 'engine', 'power', 'torque', 'displacement', 'dimension', 'weight', 'colour', 'color', 'performance', 'transmission', 'type', 'gear']
        if any(kw in text.lower() for kw in tech_keywords):
            return False
            
        # Avoid measurement units
        if re.search(r'\b(mm|cc|rpm|kmpl|nm|kw|ps|bhp)\b', text.lower()):
            return False
            
        return True

    def _score_candidate(self, r_idx, merged_headers, body_rows):
        label = merged_headers[0].lower() if merged_headers and merged_headers[0] else ""
        cols = merged_headers[1:]
        
        score = 0
        tech_keywords = ['length', 'width', 'height', 'wheelbase', 'capacity', 'suspension', 'brake', 'engine', 'max power', 'max torque', 'displacement', 'dimension', 'weight', 'colour', 'color', 'performance']
        if any(kw in label for kw in tech_keywords):
            score -= 200
            
        valid_cols = 0
        structural_trims = 0
        explicit_trims = 0
        powertrain_tokens = 0
        
        for c in cols:
            c_low = str(c).lower().strip()
            if not c_low: continue
            valid_cols += 1
            
            if self._is_structural_trim(c_low):
                structural_trims += 1
                score += 5
                
            # Bonus for explicit known trims
            if re.search(r'\b(sigma|delta|zeta|alpha|lxi|vxi|zxi|zx|sx|style|classic|sport|plus|era|magna|asta|sportz|smart|pure|creative|fearless|empowered|adventure|accomplished)\b', c_low):
                explicit_trims += 1
                score += 10
                
            if re.search(r'\b(mt|at|amt|cvt|dct|ags|ivt|cng|petrol|diesel|turbo|ev|electric)\b', c_low):
                powertrain_tokens += 1
                score += 5
                
            if re.fullmatch(r'\d{2,}', c_low.replace(',', '').replace('.', '')):
                score -= 30
                
            if re.search(r'\b(water-cooled|disc|drum|mcpherson|strut|torsion|beam)\b', c_low):
                score -= 50
                
        if valid_cols == 0:
            return -1000
            
        total_cells = 0
        bool_cells = 0
        numeric_cells = 0
        
        for br in body_rows:
            for c in br[1:]:
                c_clean = str(c).lower().strip()
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
            
            score += (bool_density * 200)
            score -= (numeric_density * 200)
            
            # Reward table length if it is a plausible feature matrix (either boolean or text-heavy, but not heavily numeric)
            if bool_density > 0.1 or (structural_trims >= 2 and numeric_density < 0.3):
                score += len(body_rows) * 2
                
        if len(body_rows) < 3:
            score -= 500
            
        if structural_trims == 0 and numeric_density > 0.3:
            score -= 500
            
        # Relaxed the penalty: if we have structural trims but no booleans, it might be a text feature matrix.
        # Only penalize if there are NO structural trims AND low booleans.
        if structural_trims == 0 and bool_density < 0.05:
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
            
            for t_idx, matrix in enumerate(tables):
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
                                'table_idx': t_idx,
                                'matrix': matrix,
                                'clean_matrix': clean_matrix,
                                'next_r_idx': next_r_idx,
                                'merged_headers': merged_headers
                            }
                            
        # 2. Threshold Check (Fail-closed)
        if best_score < 20 or not best_candidate:
            return -1, None, None
            
        c = best_candidate
        
        # AUDIT 2 FIX: We extract columns structurally first. If they fail, we reject.
        structural_variants = []
        for c_idx in range(1, len(c['merged_headers'])):
            header_text = c['merged_headers'][c_idx]
            if header_text:
                expanded = self._expand_header(header_text)
                for exp in expanded:
                    exp['col_idx'] = c_idx
                    structural_variants.append(exp)
                    
        # If structural column extraction failed entirely, reject the candidate!
        # Do NOT let `provided_variants` rescue a table that has no structural configuration headers.
        if not structural_variants:
            return -1, None, None
            
        variants = provided_variants if provided_variants else structural_variants
            
        feature_rows = c['clean_matrix'][c['next_r_idx']:]
        
        # 3. Validated Continuation Logic (AUDIT 1 FIX)
        expected_cols = max((len(r) for r in c['matrix']), default=0)
        
        # Calculate parent baseline for compatibility checks
        parent_total_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip())
        parent_bool_cells = sum(1 for br in feature_rows for cell in br[1:] if str(cell).strip() and (str(cell).lower().strip() in ['y', 'n', 's', '-', 'o', 'na', 'std'] or re.search(r'[✔√●]', str(cell).lower().strip())))
        parent_bool_density = (parent_bool_cells / parent_total_cells) if parent_total_cells > 0 else 0.0

        next_page_idx = c['page_idx'] + 1
        while next_page_idx < len(pdf.pages):
            next_page = pdf.pages[next_page_idx]
            next_tables = next_page.extract_tables()
            if not next_tables: break
            
            # Remove greedy lambda sorting! Evaluate all tables on the next page that match the expected column count.
            compatible_table_found = False
            for next_matrix in next_tables:
                next_cols = max((len(r) for r in next_matrix if r), default=0)
                if next_cols != expected_cols: continue
                
                # Validation A: Ensure it doesn't have a new variant header
                is_continuation_table = True
                if len(next_matrix) > 0 and len(next_matrix[0]) > 0:
                    first_cell = str(next_matrix[0][0]).strip().lower() if next_matrix[0][0] else ""
                    # Check if the first row looks like a new header
                    if first_cell in ["variant", "variants"] or re.search(r'\b(LXi|VXi|Sigma|Delta|Era|Magna|Sportz|Asta)\b', str(next_matrix[0]), re.IGNORECASE):
                        is_continuation_table = False
                        
                if not is_continuation_table: continue
                
                # Validation B: Structural compatibility (bool density shouldn't deviate wildly if parent was highly boolean)
                cont_total = sum(1 for r in next_matrix for cell in r[1:] if str(cell).strip())
                cont_bool = sum(1 for r in next_matrix for cell in r[1:] if str(cell).strip() and (str(cell).lower().strip() in ['y', 'n', 's', '-', 'o', 'na', 'std'] or re.search(r'[✔√●]', str(cell).lower().strip())))
                cont_bool_density = (cont_bool / cont_total) if cont_total > 0 else 0.0
                
                # If parent was highly boolean (>30%), continuation must have at least *some* booleans (>5%) or vice-versa
                if parent_bool_density > 0.3 and cont_bool_density < 0.05 and cont_total > 10:
                    continue # Probably a technical spec table sharing the same column count
                    
                # Compatible continuation!
                for row in next_matrix:
                    clean_row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                    if any(clean_row):
                        feature_rows.append(clean_row)
                        
                compatible_table_found = True
                break # We take the first compatible table on the page
                
            if not compatible_table_found:
                break
                
            next_page_idx += 1
            
        return c['page_idx'], feature_rows, variants

