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
            for row in tables[0]:
                clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                if "Wireless Charger" in clean_row[0]:
                    print("Found:", clean_row)
