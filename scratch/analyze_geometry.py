import sys, os, pdfplumber, json
from collections import defaultdict
sys.path.append(os.getcwd())

targets = ["Thar", "Alto K10", "Virtus", "Dzire", "Scorpio Classic", "Nexon", "Nexon EV", "Tiago", "Tiago EV"]

with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)

for model in targets:
    try:
        path = next(r['brochure_path'] for r in report['reports'] if r['model'] == model)
        print(f"\n{'='*40}\nMODEL: {model}\n{'='*40}")
        with pdfplumber.open(path) as pdf:
            # Find a page that likely has features
            target_page = None
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and ("FEATURE" in text.upper() or "VARIANT" in text.upper() or "SPECIFICATION" in text.upper()):
                    target_page = page
                    print(f"Selected Page: {i}")
                    break
            
            if not target_page:
                target_page = pdf.pages[len(pdf.pages) // 2]
                print(f"Fallback Page: {len(pdf.pages) // 2}")
                
            words = target_page.extract_words()
            
            print(f"Total Words Extracted: {len(words)}")
            
            if len(words) == 0:
                print("WARNING: No words found (Image-only or OCR failed).")
                continue
                
            # Sample geometry of rows
            y_bins = defaultdict(list)
            for w in words:
                # Quantize Y to nearest 5 points to group rows
                y_quant = round(w['top'] / 5) * 5
                y_bins[y_quant].append(w)
                
            # Sort bins by Y
            sorted_y = sorted(y_bins.keys())
            
            # Print a few dense rows
            dense_rows = [y for y in sorted_y if len(y_bins[y]) > 5]
            print(f"Number of dense rows (>5 words): {len(dense_rows)}")
            
            print("\nSample Dense Rows (showing words & their X-centers):")
            for y in dense_rows[:3]:
                row_words = sorted(y_bins[y], key=lambda x: x['x0'])
                # Group text logically for display
                print(f"Y={y}:")
                for w in row_words:
                    center_x = (w['x0'] + w['x1']) / 2
                    print(f"  [{center_x:.1f}] '{w['text']}'")
    except Exception as e:
        print(f"Error processing {model}: {e}")

