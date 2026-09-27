import json
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.strategies.swift_2024 import SwiftGen4VerticalStrategy
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

strategy = SwiftGen4VerticalStrategy()
extractor = OEMBrochureExtractor(strategy)
payload = extractor.execute("knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf")

normalized = map_oem_fields(payload[0])
print(json.dumps(normalized, indent=2))
