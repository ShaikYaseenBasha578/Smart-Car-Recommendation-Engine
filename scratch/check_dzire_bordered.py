import sys, pdfplumber
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/dzire/latest/brochures/maruti_suzuki_dzire_brochure.pdf"
strategy = VariantColumnMatrixStrategy()
with pdfplumber.open(pdf_path) as pdf:
    res = strategy._discover_structure(pdf)
    if res[0] != -1:
        print(f"Page: {res[0]}")
        print(f"Headers: {res[2]}")
