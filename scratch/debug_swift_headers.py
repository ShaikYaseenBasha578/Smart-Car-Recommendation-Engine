import sys
import os
sys.path.append(os.getcwd())
import pdfplumber
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

strat = VariantColumnMatrixStrategy()
pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
with pdfplumber.open(pdf_path) as pdf:
    page_idx, matrix, variants = strat._discover_structure(pdf)
    print("Variants found:", variants)
