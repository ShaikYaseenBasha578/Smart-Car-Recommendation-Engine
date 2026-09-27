from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

strategy = classify_layout("hyundai", "creta")
configs = strategy.extract("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf")
for c in configs:
    print(c.raw_variant_name, c.engine_name)
