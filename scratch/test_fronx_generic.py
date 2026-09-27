import sys
import os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
strategy = classify_layout(pdf_path, "Maruti Suzuki", "Fronx")
print("Strategy:", type(strategy).__name__)
configs = strategy.extract(pdf_path)

for c in configs:
    print(c.raw_variant_name, c.engine_name, c.transmission, c.powertrain_type, len(c.fields))
