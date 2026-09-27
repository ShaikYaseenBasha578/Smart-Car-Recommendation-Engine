import sys, json
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
make, model = "Maruti Suzuki", "Swift"

try:
    strategy = classify_layout(pdf_path, make, model)
    strat_name = type(strategy).__name__
    print(f"Detected Strategy: {strat_name}")
    
    extractor = OEMBrochureExtractor(strategy)
    configs = extractor.execute(pdf_path)
    print(f"Configurations Extracted: {len(configs)}")
    if configs:
        headers = [c.get('raw_variant_name', '') for c in configs]
        print(f"Headers: {headers}")
except Exception as e:
    print(f"Extraction Failed: {type(e).__name__} - {e}")

