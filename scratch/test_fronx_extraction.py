import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
strategy = classify_layout(pdf_path, "maruti suzuki", "fronx")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

print(f"Extracted {len(payloads)} configurations")
if payloads:
    print(len(payloads[0].keys()), "fields extracted.")
    print(json.dumps(payloads[0], indent=2))
