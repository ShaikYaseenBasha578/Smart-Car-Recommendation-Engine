from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

print("Testing swift as 'unknown make/model':")
strategy = classify_layout("knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf", "unknown", "unknown")
print("Detected:", type(strategy).__name__)

print("\nTesting creta as 'unknown make/model':")
strategy = classify_layout("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf", "unknown", "unknown")
print("Detected:", type(strategy).__name__)

print("\nTesting fronx as 'unknown make/model':")
strategy = classify_layout("knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf", "unknown", "unknown")
print("Detected:", type(strategy).__name__)
