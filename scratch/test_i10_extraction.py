import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

strategy = classify_layout("hyundai", "grand i10 nios")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute("knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf")

print(f"Extracted {len(payloads)} configurations")
if payloads:
    print(json.dumps(payloads[0], indent=2))
