import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

pdf_path = "knowledge_base/sources/oem/hyundai/aura/latest/brochures/Aura_Brochure.pdf"
strategy = classify_layout(pdf_path, "hyundai", "aura")
print("Selected Strategy:", type(strategy).__name__)

extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

print(f"Extracted {len(payloads)} configurations")
if payloads:
    print(len(payloads[0].keys()), "fields extracted.")
    print("Example variants:")
    for p in payloads:
        print(f"- {p['variant_name']}")
