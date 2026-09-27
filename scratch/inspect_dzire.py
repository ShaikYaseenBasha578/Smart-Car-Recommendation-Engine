import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Dzire')
try:
    c = VariantColumnMatrixStrategy().extract(path)
    print("Bordered success!")
except Exception as e:
    print("Bordered failed:", str(e))
