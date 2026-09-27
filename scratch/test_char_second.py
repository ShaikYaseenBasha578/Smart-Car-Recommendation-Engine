import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars

with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Scorpio Classic')

with pdfplumber.open(path) as p:
    res = reconstruct_text_from_chars(p.pages[11].chars)
    print("SCORPIO CLASSIC RECONSTRUCTION (Top 5 rows):")
    for r in res['rows'][:5]:
        print(r['text'])
