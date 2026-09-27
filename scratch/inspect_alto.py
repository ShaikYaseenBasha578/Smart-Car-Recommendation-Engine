import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == "Alto K10")
with pdfplumber.open(path) as pdf:
    for i, p in enumerate(pdf.pages):
        text = p.extract_text()
        if text and "VXi" in text:
            print(f"Page {i} has VXi")
            for w in p.extract_words():
                if len(w['text']) == 1:
                    print(w['text'], end=' ')
