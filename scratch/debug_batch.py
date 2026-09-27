import sys
sys.path.append('.')
from knowledge_base.ingestion.oem.batch_runner_oem import get_pdf_metadata
metadata = get_pdf_metadata("knowledge_base/sources/oem/tata/nexon_ev/latest/brochures/nexon-ev-brochure.pdf")
print(metadata)
