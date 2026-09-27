import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

for name, pdf_path in [
    ("fronx", "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"),
    ("baleno", "knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf")
]:
    strategy = classify_layout(pdf_path, "maruti suzuki", name)
    print(f"\n[{name.upper()}] Selected Strategy: {type(strategy).__name__}")
    
    extractor = OEMBrochureExtractor(strategy)
    payloads = extractor.execute(pdf_path)
    
    print(f"Extracted {len(payloads)} configurations")
    if payloads:
        print(len(payloads[0].keys()), "fields extracted.")
        print(f"Sample Variant 0: {payloads[0]['variant_name']}")
        print(f"Sample Variant -1: {payloads[-1]['variant_name']}")
