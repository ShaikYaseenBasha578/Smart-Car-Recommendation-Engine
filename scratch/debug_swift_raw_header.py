import sys
import os
sys.path.append(os.getcwd())
import pdfplumber
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

strat = VariantColumnMatrixStrategy()
pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        tables = page.extract_tables()
        if tables:
            tables.sort(key=lambda t: len(t), reverse=True)
            matrix = tables[0]
            clean_matrix = []
            for row in matrix:
                clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                if any(clean_row):
                    clean_matrix.append(clean_row)
            for r_idx, row in enumerate(clean_matrix[:5]):
                non_empty = [c for c in row if c]
                if len(non_empty) > 2:
                    print("Found header row:", row)
                    break
            break
