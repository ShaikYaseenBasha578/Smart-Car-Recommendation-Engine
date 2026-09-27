from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
strategy = classify_layout(pdf_path, "Maruti Suzuki", "Swift")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)
import json
print(json.dumps(payloads[:1], indent=2))
