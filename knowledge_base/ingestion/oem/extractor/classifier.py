import pdfplumber
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf

def classify_layout(pdf_path: str, make: str, model: str):
    sig = profile_pdf(pdf_path)
    
    if sig.is_cid_corrupted:
        from knowledge_base.ingestion.oem.extractor.strategies.maruti_wagonr import MarutiWagonRStrategy
        return MarutiWagonRStrategy()
        
    if sig.has_engine_trim_plan:
        from knowledge_base.ingestion.oem.extractor.families.engine_trim_cross_matrix import EngineTrimCrossMatrixStrategy
        return EngineTrimCrossMatrixStrategy()
        
    # Structural check for explicit feature addition/inheritance lists
    if make.lower() == 'tata':
        with pdfplumber.open(pdf_path) as pdf:
            has_feature_list = False
            # Check last 6 pages where features usually live
            start_idx = max(0, len(pdf.pages) - 6)
            for i in range(start_idx, len(pdf.pages)):
                text = pdf.pages[i].extract_text()
                if text:
                    text_lower = text.lower()
                    if 'addition to' in text_lower or 'features over' in text_lower:
                        has_feature_list = True
                        break
                        
            if has_feature_list:
                from knowledge_base.ingestion.oem.extractor.families.feature_list import FeatureListStrategy
                return FeatureListStrategy()
                
    if sig.largest_table[0] > 2 and sig.largest_table[1] > 2:
        from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
        bordered = VariantColumnMatrixStrategy()
        try:
            with pdfplumber.open(pdf_path) as pdf:
                res = bordered._discover_structure(pdf)
                if res[0] != -1:
                    # Validate that the Bordered strategy actually extracted real headers, not just garbage symbols
                    variants = res[2]
                    valid_headers = [v.get('variant', '') for v in variants if len(v.get('variant', '')) > 1 and v.get('variant', '').lower() not in ['unknown', 'standard', 'yes', 'opt']]
                    if len(valid_headers) > 0:
                        return bordered
        except Exception:
            pass
            
    from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy
    return BorderlessVariantColumnMatrixStrategy()
