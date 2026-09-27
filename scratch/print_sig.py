import sys
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf

pdf_path = "knowledge_base/sources/oem/honda/city/latest/brochures/honda_city_brochure.pdf"
sig = profile_pdf(pdf_path)
print(f"largest_table: {sig.largest_table}")
