import json
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.strategies.standard_matrix import StandardMatrixStrategy

strategy = StandardMatrixStrategy(target_page=1)
extractor = OEMBrochureExtractor(strategy)
payload = extractor.execute("scratch/fixture_matrix.pdf")

print(json.dumps(payload, indent=2))
