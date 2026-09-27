import sys
import os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
strategy = classify_layout(pdf_path, "Maruti Suzuki", "Fronx")
configs = strategy.extract(pdf_path)

print(f"Total configs extracted: {len(configs)}")
for c in configs:
    print(f"Variant: {c.raw_variant_name}, Engine: {c.engine_name}, Fuel: {c.powertrain_type}, Trans: {c.transmission}, Fields: {len(c.fields)}")

