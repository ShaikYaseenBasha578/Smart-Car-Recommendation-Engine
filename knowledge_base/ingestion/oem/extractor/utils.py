import pdfplumber
import re

def normalize_symbols(val: str) -> str:
    """
    Normalizes common PDF symbols (checkmarks, dashes) into standard text.
    """
    if not val:
        return val
    val = val.replace('\n', ' ').strip()
    if val == '-':
        return '-'
    if '\uf0fc' in val or '✓' in val:
        val = val.replace('✓', '').replace('\uf0fc', '').strip()
        return 'Standard ' + val if val else 'Standard'
    return val

def extract_tables_from_page(pdf_path: str, page_index: int):
    """
    Helper to extract tables from a specific page safely.
    """
    with pdfplumber.open(pdf_path) as pdf:
        if page_index < 0 or page_index >= len(pdf.pages):
            raise ValueError(f"Page index {page_index} out of bounds.")
        page = pdf.pages[page_index]
        return page.extract_tables()

def apply_condition(val: str, current_powertrain: str, current_transmission: str) -> str:
    """
    Common logic to handle 'AMT only', 'MT only', 'CNG Only' annotations.
    Returns '-' if the condition fails, or the stripped value if it passes.
    """
    if not val: return val
    
    val_lower = val.lower()
    
    if '(amt only)' in val_lower:
        if current_transmission != 'AMT': return '-'
        return re.sub(r'\(amt only\)', '', val, flags=re.IGNORECASE).strip()
        
    if '(mt only)' in val_lower:
        if current_transmission != 'MT': return '-'
        return re.sub(r'\(mt only\)', '', val, flags=re.IGNORECASE).strip()
        
    if 'cng only' in val_lower or '(cng only)' in val_lower:
        if current_powertrain != 'CNG': return '-'
        return re.sub(r'\(?cng only\)?', '', val, flags=re.IGNORECASE).strip()
        
    return val
