import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)

tata_models = ['Nexon', 'Tiago', 'Nexon EV', 'Tiago EV']

for model in tata_models:
    try:
        path = next(r['brochure_path'] for r in report['reports'] if r['model'] == model)
        print(f"\n--- {model} ---")
        with pdfplumber.open(path) as p:
            for i, page in enumerate(p.pages):
                text = page.extract_text()
                if text and ("addition to" in text.lower() or "features over" in text.lower()):
                    print(f"Page {i} explicit inheritance found!")
                    # snippet
                    idx = text.lower().find("addition to")
                    if idx == -1: idx = text.lower().find("features over")
                    print(text[max(0, idx-20):idx+50].replace('\n', ' '))
                    break
    except StopIteration:
        pass
