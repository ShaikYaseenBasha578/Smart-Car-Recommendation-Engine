import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
strategy = classify_layout(pdf_path, "maruti suzuki", "swift")
print("Selected Strategy:", type(strategy).__name__)

extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

print(f"Extracted {len(payloads)} configurations")
if payloads:
    print(len(payloads[0].keys()), "fields extracted.")
import pprint
for p in payloads:
    print(p['variant_name'])
