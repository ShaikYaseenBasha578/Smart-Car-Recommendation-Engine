from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

pdf_path = "knowledge_base/sources/oem/mahindra/thar_roxx/latest/brochures/Thar_Roxx_Brochure.pdf"
try:
    strategy = classify_layout(pdf_path, "mahindra", "thar_roxx")
    print("Selected:", type(strategy).__name__)
except Exception as e:
    print("Exception:", e)
