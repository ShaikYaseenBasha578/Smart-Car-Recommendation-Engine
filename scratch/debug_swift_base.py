import sys
import os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy

strat = VariantColumnMatrixStrategy()
pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
configs = strat.extract(pdf_path)
for i, c in enumerate(configs):
    val = next((f.raw_value for f in c.fields if "Wireless" in f.field_name), None)
    print(i, c.raw_variant_name, val)
