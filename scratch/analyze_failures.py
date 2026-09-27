import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
failures = [
    "Honda_Amaze", "Hyundai_Venue", "Hyundai_Verna", "MG_Windsor EV",
    "Mahindra_Bolero", "Mahindra_Thar", "Maruti Suzuki_Alto K10",
    "Maruti Suzuki_Jimny", "Nissan_Magnite", "Renault_Duster",
    "Renault_Triber", "Tata_Nexon", "Tata_Nexon EV", "Tata_Punch EV",
    "Tata_Tiago", "Tata_Tiago EV", "Toyota_Fortuner", "Volkswagen_Virtus"
]
with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)

for f in failures:
    try:
        model_name = f.split("_", 1)[1] if "_" in f else f
        r_list = [r for r in report['reports'] if r['model'] == model_name]
        if not r_list:
            print(f"NOT FOUND: {model_name}")
            continue
        r = r_list[0]
        path = r['brochure_path']
        print(f"=== {f} ===")
        with pdfplumber.open(path) as pdf:
            tables_found = sum(1 for p in pdf.pages if p.extract_tables())
            print(f"Pages with tables: {tables_found}/{len(pdf.pages)}")
            
            largest = None
            for p in pdf.pages:
                tables = p.extract_tables()
                for t in tables:
                    if not largest or len(t) > len(largest):
                        largest = t
            if largest:
                print(f"Largest table shape: {len(largest)} rows, {max(len(row) for row in largest)} cols")
                for row in largest[:3]:
                    print([str(c).replace('\n', ' ')[:20] for c in row])
            else:
                print("No tables extracted by pdfplumber")
        print()
    except Exception as e:
        print(f"Error on {f}: {e}")
