import sys
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

pdf_path = "knowledge_base/sources/oem/honda/city/latest/brochures/honda_city_brochure.pdf"
strategy = classify_layout(pdf_path, "Honda", "City")
extractor = OEMBrochureExtractor(strategy)
configs = extractor.execute(pdf_path)
print(f"Configurations Extracted: {len(configs)}")
if configs:
    headers = [c.get('raw_variant_name', '') for c in configs]
    print(f"Headers: {headers}")
