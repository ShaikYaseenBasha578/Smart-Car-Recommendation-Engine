from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
from knowledge_base.ingestion.oem.extractor.base import ConfigurationIR, ExtractedField
from typing import List

class SwiftGen4VerticalStrategy(VariantColumnMatrixStrategy):
    def _get_variants(self) -> List[dict]:
        # Explicitly map the 5 columns to the 12 expected configurations
        # Columns in the PDF: 1=LXi, 2=VXi, 3=VXi (O), 4=ZXi, 5=ZXi+
        variants = []
        mapping = {
            1: [("LXi", "Petrol", "MT")],
            2: [("VXi", "Petrol", "MT"), ("VXi", "Petrol", "AMT"), ("VXi", "CNG", "MT")],
            3: [("VXi (O)", "Petrol", "MT"), ("VXi (O)", "Petrol", "AMT"), ("VXi (O)", "CNG", "MT")],
            4: [("ZXi", "Petrol", "MT"), ("ZXi", "Petrol", "AMT"), ("ZXi", "CNG", "MT")],
            5: [("ZXi+", "Petrol", "MT"), ("ZXi+", "Petrol", "AMT")]
        }
        
        for col_idx, configs in mapping.items():
            for v_name, fuel, trans in configs:
                variants.append({
                    "variant": v_name,
                    "engine": None,
                    "trans": trans,
                    "fuel": fuel,
                    "col_idx": col_idx
                })
        return variants
