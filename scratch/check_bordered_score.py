import sys, pdfplumber
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
strategy = VariantColumnMatrixStrategy()
with pdfplumber.open(pdf_path) as pdf:
    res = strategy._discover_structure(pdf)
    print(f"Res: {res}")
