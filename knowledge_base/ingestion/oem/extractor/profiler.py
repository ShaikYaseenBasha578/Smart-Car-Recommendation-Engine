import pdfplumber
import re
from typing import List, Dict, Any, Tuple

class StructuralSignature:
    def __init__(self):
        self.total_pages: int = 0
        self.text_pages: int = 0
        self.image_only_pages: int = 0
        self.table_pages: List[int] = []
        self.largest_table: Tuple[int, int] = (0, 0) # (rows, cols)
        self.variant_token_density: float = 0.0
        self.powertrain_token_density: float = 0.0
        self.feature_row_density: float = 0.0
        self.multi_page_table_likelihood: bool = False
        self.header_repeat_likelihood: bool = False
        self.is_cid_corrupted: bool = False
        self.has_engine_trim_plan: bool = False
        
    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

def profile_pdf(pdf_path: str) -> StructuralSignature:
    sig = StructuralSignature()
    
    powertrain_keywords = r'\b(MT|AT|AMT|CVT|DCT|AGS|iVT|CNG|Petrol|Diesel|Turbo)\b'
    feature_keywords = r'\b(Standard|S|\-|S/O|O)\b'
    
    total_pt_tokens = 0
    total_feature_tokens = 0
    total_words = 0
    
    tables_by_page = {}
    
    with pdfplumber.open(pdf_path) as pdf:
        sig.total_pages = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text_upper = text.upper()
            
            # CID Corruption Check
            if "(cid:" in text or len([c for c in page.chars if 'cid' in c.get('text', '')]) > 100:
                sig.is_cid_corrupted = True
                
            if "ENGINE & TRIM PLAN" in text_upper or "ENGINE AND TRIM PLAN" in text_upper:
                sig.has_engine_trim_plan = True
                
            words = text.split()
            word_count = len(words)
            total_words += word_count
            
            if word_count < 10:
                sig.image_only_pages += 1
            else:
                sig.text_pages += 1
                
            # Token densities
            pt_matches = len(re.findall(powertrain_keywords, text, re.IGNORECASE))
            total_pt_tokens += pt_matches
            
            # Tables
            tables = page.extract_tables()
            if tables:
                sig.table_pages.append(i)
                tables_by_page[i] = tables
                
                for t in tables:
                    rows = len(t)
                    cols = max((len(r) for r in t if r), default=0)
                    if rows * cols > sig.largest_table[0] * sig.largest_table[1]:
                        sig.largest_table = (rows, cols)
                        
                    # Check for feature density within tables
                    for row in t:
                        if not row: continue
                        clean_row = [str(c).replace('\n', ' ').strip() for c in row if c]
                        feat_matches = sum(1 for cell in clean_row if re.search(feature_keywords, cell, re.IGNORECASE) or '\uf0fc' in cell or '✓' in cell)
                        total_feature_tokens += feat_matches

        # Densities
        if total_words > 0:
            sig.powertrain_token_density = total_pt_tokens / total_words
            sig.feature_row_density = total_feature_tokens / total_words
            
        # Check for multi-page tables
        if len(sig.table_pages) > 1:
            # simple heuristic: consecutive table pages with same max column count
            for j in range(len(sig.table_pages) - 1):
                p1 = sig.table_pages[j]
                p2 = sig.table_pages[j+1]
                if p2 == p1 + 1:
                    t1_cols = max((len(r) for t in tables_by_page[p1] for r in t if r), default=0)
                    t2_cols = max((len(r) for t in tables_by_page[p2] for r in t if r), default=0)
                    if t1_cols == t2_cols and t1_cols > 2:
                        sig.multi_page_table_likelihood = True
                        break
                        
    return sig
