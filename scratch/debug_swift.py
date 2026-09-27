import sys
import os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

SWIFT_PDF = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
strategy = classify_layout(SWIFT_PDF, "Maruti Suzuki", "Swift")
configs = strategy.extract(SWIFT_PDF)
zxi_plus_amt = next(c for c in configs if c.raw_variant_name == "ZXi+" and c.transmission == "AMT")

for f in zxi_plus_amt.fields:
    if "Wireless" in f.field_name or "Camera" in f.field_name:
        print(f"{f.field_name}: {f.raw_value}")
