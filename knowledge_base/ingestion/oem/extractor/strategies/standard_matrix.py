from typing import List
from knowledge_base.ingestion.oem.extractor.base import OEMBrochureLayoutStrategy, ConfigurationIR, ExtractedField
from knowledge_base.ingestion.oem.extractor.utils import normalize_symbols
import pdfplumber

class StandardMatrixStrategy(OEMBrochureLayoutStrategy):
    """
    Generic layout strategy where variants are rows and features/specs are columns.
    Typically used for single-table matrix layouts.
    Assumes first row is headers (features), first column is variant names.
    """
    def __init__(self, target_page: int):
        self.target_page = target_page

    def extract(self, pdf_path: str) -> List[ConfigurationIR]:
        with pdfplumber.open(pdf_path) as pdf:
            if self.target_page < 1 or self.target_page > len(pdf.pages):
                raise ValueError(f"Page index {self.target_page} out of bounds.")
            page = pdf.pages[self.target_page - 1]
            tables = page.extract_tables()
            
        if not tables:
            raise ValueError("StandardMatrixStrategy failed: No tables found.")
            
        table = tables[0]
        if len(table) < 2:
            raise ValueError("StandardMatrixStrategy failed: Insufficient rows.")
            
        headers = [str(h).replace('\n', ' ').strip() if h else "" for h in table[0]]
        
        configurations = []
        for row in table[1:]:
            if not row or not row[0]: continue
            raw_variant = row[0].replace('\n', ' ').strip()
            
            # Simple identity parsing for fixture purposes
            pt_type = "CNG" if "CNG" in raw_variant.upper() else "Petrol"
            trans = "AMT" if "AMT" in raw_variant.upper() else "MT"
            
            fields = []
            for col_idx in range(1, len(row)):
                if col_idx < len(headers) and headers[col_idx]:
                    val = normalize_symbols(row[col_idx])
                    fields.append(ExtractedField(
                        field_name=headers[col_idx],
                        raw_value=val,
                        source_page=self.target_page,
                        section="MATRIX"
                    ))
                    
            configurations.append(ConfigurationIR(
                raw_variant_name=raw_variant,
                powertrain_type=pt_type,
                transmission=trans,
                fields=fields
            ))
            
        return configurations
