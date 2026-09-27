import sys, pdfplumber
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

pdf_path = "knowledge_base/sources/oem/honda/city/latest/brochures/honda_city_brochure.pdf"
strategy = VariantColumnMatrixStrategy()
with pdfplumber.open(pdf_path) as pdf:
    res = strategy._discover_structure(pdf)
    print(f"res: {res}")
