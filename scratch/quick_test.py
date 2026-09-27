import sys, json
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/dzire/latest/brochures/maruti_suzuki_dzire_brochure.pdf"
make, model = "Maruti Suzuki", "Dzire"

strategy = classify_layout(pdf_path, make, model)
print(f"Strategy: {type(strategy).__name__}")
extractor = OEMBrochureExtractor(strategy)
configs = extractor.execute(pdf_path)
print(f"Extracted: {len(configs)}")
if configs:
    print(f"Headers: {[c.get('raw_variant_name', '') for c in configs]}")
