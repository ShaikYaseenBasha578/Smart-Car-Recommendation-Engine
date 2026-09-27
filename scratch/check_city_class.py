import sys
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

pdf_path = "knowledge_base/sources/oem/honda/city/latest/brochures/honda_city_brochure.pdf"
strategy = classify_layout(pdf_path, "Honda", "City")
print(f"Strategy: {type(strategy).__name__}")
