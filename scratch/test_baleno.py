import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

strategy = classify_layout("maruti suzuki", "baleno")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute("knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf")

print(f"Extracted {len(payloads)} configurations")
if payloads:
    print(len(payloads[0].keys()), "fields extracted.")
    print(json.dumps(payloads[0], indent=2))
