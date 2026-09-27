import re

def score_table(matrix):
    best_score = -1000
    best_combo = None
    
    clean_matrix = []
    for row in matrix:
        clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
        if any(clean_row):
            clean_matrix.append(clean_row)
            
    if len(clean_matrix) < 3 or len(clean_matrix[0]) < 2:
        return best_score, None
        
    for r_idx, row in enumerate(clean_matrix[:5]):
        non_empty = [c for c in row if c]
        if len(non_empty) < 2: continue
        
        merged_headers = list(row)
        # Simplified merge for testing
        next_r_idx = r_idx + 1
        
        # Scoring this candidate header
        label = merged_headers[0].lower()
        cols = merged_headers[1:]
        
        score = 0
        
        # 1. Technical Specification Penalty (Headers)
        tech_keywords = ['length', 'width', 'height', 'wheelbase', 'capacity', 'suspension', 'brake', 'engine type', 'max power', 'max torque', 'displacement']
        if any(kw in label for kw in tech_keywords):
            score -= 100
            
        # Analyze columns
        valid_cols = 0
        for c in cols:
            c_low = c.lower()
            if not c_low: continue
            valid_cols += 1
            
            # Trim tokens
            if re.search(r'\b(sigma|delta|zeta|alpha|lxi|vxi|zxi|zx|sx|style|classic|sport|plus)\b', c_low):
                score += 5
                
            # Powertrain tokens
            if re.search(r'\b(mt|at|amt|cvt|dct|ags|ivt|cng|petrol|diesel|turbo)\b', c_low):
                score += 2
                
            # Pure numbers >= 100 (likely dimensions or power)
            if re.fullmatch(r'\d{3,}', c_low.replace(',', '')):
                score -= 10
                
            # Technical specs in header
            if re.search(r'\b(water-cooled|disc|drum|mcpherson)\b', c_low):
                score -= 20
                
        # 2. Body scoring (Feature matrix vs Technical matrix)
        body_rows = clean_matrix[next_r_idx:]
        total_cells = 0
        bool_cells = 0
        numeric_cells = 0
        
        for br in body_rows:
            for c in br[1:]:
                c_clean = c.lower().strip()
                if not c_clean: continue
                total_cells += 1
                if c_clean in ['y', 'n', 's', '-', 'o', 'na'] or re.search(r'[✔√]', c_clean):
                    bool_cells += 1
                elif re.fullmatch(r'[\d\.,]+', c_clean):
                    numeric_cells += 1
                    
        if total_cells > 0:
            bool_density = bool_cells / total_cells
            numeric_density = numeric_cells / total_cells
            
            score += (bool_density * 50)
            score -= (numeric_density * 50)
            
        if score > best_score:
            best_score = score
            best_combo = (r_idx, merged_headers)
            
    return best_score, best_combo

dim_table = [
    ["Dimensions", "Length", "Width"],
    ["Overall", "4295", "1770"],
    ["Wheelbase", "2600", "2600"]
]

feat_table = [
    ["Features", "Sigma", "Delta"],
    ["Airbags", "Y", "Y"],
    ["Sunroof", "-", "Y"]
]

print("Dimensions:", score_table(dim_table))
print("Features:", score_table(feat_table))
