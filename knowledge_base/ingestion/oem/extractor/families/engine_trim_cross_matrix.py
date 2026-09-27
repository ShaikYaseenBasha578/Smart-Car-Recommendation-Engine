import pdfplumber
from typing import List, Tuple
from knowledge_base.ingestion.oem.extractor.base import OEMBrochureLayoutStrategy, ConfigurationIR, ExtractedField
from knowledge_base.ingestion.oem.extractor.utils import normalize_symbols

class EngineTrimCrossMatrixStrategy(OEMBrochureLayoutStrategy):
    """
    Layout Family: Engine-Trim Cross Matrix
    """
    
    def _find_pages(self, pdf) -> Tuple[int, int]:
        feature_page_idx = -1
        spec_page_idx = -1
        
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            text_upper = text.upper()
            
            if ("ENGINE & TRIM PLAN" in text_upper or "ENGINE AND TRIM PLAN" in text_upper):
                feature_page_idx = i
            if "TECHNICAL SPECIFICATIONS" in text_upper and "DIMENSIONS" in text_upper:
                spec_page_idx = i
                
        return feature_page_idx, spec_page_idx

    def _get_variants(self) -> List[str]:
        return []
        
    def _parse_tech_specs(self, text: str) -> dict:
        return {}
        
    def _parse_engine_tokens(self, tokens: List[str]) -> Tuple[str, str]:
        trans = "MT"
        if "iVT" in tokens: trans = "iVT"
        elif "AT" in tokens or "auto" in [t.lower() for t in tokens]: trans = "AT"
        elif "DCT" in tokens: trans = "DCT"
        elif "AMT" in tokens: trans = "AMT"
        elif "manual" in [t.lower() for t in tokens]: trans = "MT"
        
        engine_tokens = [t for t in tokens if t not in ['●', '-', 'S'] and t not in ['MT', 'iVT', 'AT', 'DCT', 'AMT', 'manual']]
        return " ".join(engine_tokens), trans

    def extract(self, pdf_path: str) -> List[ConfigurationIR]:
        with pdfplumber.open(pdf_path) as pdf:
            f_idx, s_idx = self._find_pages(pdf)
            if f_idx == -1 or s_idx == -1:
                raise ValueError("Could not structurally locate Engine & Trim Plan or Technical Specifications.")
                
            page_text = pdf.pages[f_idx].extract_text(layout=True)
            import re
            page_text = re.sub(r'●\s*\([^)]+\)', '●', page_text)
            spec_text = pdf.pages[s_idx].extract_text(layout=True)
            
        lines = page_text.split('\n')
        variants = self._get_variants()
        if not variants:
            # Dynamically find the Variants line
            for line in lines:
                if line.strip().startswith("Variant") or line.strip().startswith("VARIANTS") or line.strip().startswith("Variants"):
                    tokens = line.strip().split()
                    # Remove the word "Variant(s)"
                    variants = tokens[1:]
                    break
        if not variants:
            raise NotImplementedError("Could not structurally discover variants and none provided.")
        configs = []
        
        in_engine_plan = False
        in_features = False
        current_engine = ""
        
        for line in lines:
            if ("Engine & trim plan" in line or "Engine and trim plan" in line):
                in_engine_plan = True
                continue
            if in_engine_plan and ("Safety" in line or "Features" in line or "Exterior" in line or "Interior" in line):
                in_engine_plan = False
                in_features = True
                
            tokens = line.strip().split()
            if not tokens: continue
            
            if in_engine_plan:
                checks = tokens[-len(variants):]
                if len(checks) == len(variants) and all(any(sym in c for sym in ['●', '-', 'S']) for c in checks):
                    engine_name, trans = self._parse_engine_tokens(tokens[:-len(variants)])
                    if engine_name:
                        current_engine = engine_name
                    else:
                        engine_name = current_engine
                    for v_idx, check in enumerate(checks):
                        if '●' in check or 'S' in check:
                            configs.append({
                                "variant": variants[v_idx],
                                "engine": engine_name,
                                "transmission": trans,
                                "features": []
                            })
                else:
                    engine_name, _ = self._parse_engine_tokens(tokens)
                    if engine_name: current_engine = engine_name
                    continue
                            
            elif in_features:
                if len(tokens) > len(variants):
                    checks = tokens[-len(variants):]
                    if all(c in ['●', '-', 'S', 'Standard'] for c in checks):
                        feature_name = " ".join(tokens[:-len(variants)])
                        for v_idx, val in enumerate(checks):
                            mapped_val = "Standard" if val in ["S", "●"] else val
                            for c in configs:
                                if c["variant"] == variants[v_idx]:
                                    c["features"].append(ExtractedField(
                                        field_name=feature_name,
                                        raw_value=mapped_val,
                                        source_page=f_idx,
                                        section="Key features"
                                    ))
                                    
        specs = self._parse_tech_specs(spec_text)
        results = []
        for c in configs:
            pt_type = "Petrol" if "petrol" in c["engine"].lower() else "Diesel"
            if "cng" in c["engine"].lower(): pt_type = "CNG"
            
            eng_specs = {}
            for k, v in specs.items():
                if k.lower() in c["engine"].lower() or c["engine"].lower() in k.lower():
                    eng_specs = v
                    break
                    
            for sk, sv in eng_specs.items():
                c["features"].append(ExtractedField(
                    field_name=sk,
                    raw_value=sv,
                    source_page=s_idx,
                    section="Technical specifications"
                ))
            
            results.append(ConfigurationIR(
                raw_variant_name=c["variant"],
                powertrain_type=pt_type,
                transmission=c["transmission"],
                engine_name=c["engine"],
                fields=c["features"]
            ))
            
        return results
