import json
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.strategies.hyundai_creta_2024 import HyundaiCreta2024Strategy
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

strategy = HyundaiCreta2024Strategy()
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf")

print(f"Total configurations extracted: {len(payloads)}")
if payloads:
    first_payload = payloads[0]
    print(json.dumps(first_payload, indent=2))
    print("Mapped fields:")
    print(json.dumps(map_oem_fields(first_payload), indent=2))
