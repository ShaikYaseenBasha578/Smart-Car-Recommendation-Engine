import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
with open("knowledge_base/sources/oem/batch_report.json") as f: report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Swift')

from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
strat = VariantColumnMatrixStrategy()
with pdfplumber.open(path) as pdf:
    _, rows, _ = strat._discover_structure(pdf)
    print("NEW ROWS:", len(rows))
    print(rows[-1])
