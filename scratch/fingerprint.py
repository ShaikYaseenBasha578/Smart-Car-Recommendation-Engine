import pdfplumber
import sys

pdf_path = sys.argv[1]
print(f"--- Fingerprinting {pdf_path} ---")
with pdfplumber.open(pdf_path) as pdf:
    print(f"Total Pages: {len(pdf.pages)}")
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        text_upper = text.upper()
        if "ENGINE & TRIM PLAN" in text_upper:
            print(f"Page {i}: Found 'ENGINE & TRIM PLAN'")
        if "FEATURE" in text_upper:
            print(f"Page {i}: Found 'FEATURE'")
        if "SPECIFICATION" in text_upper:
            print(f"Page {i}: Found 'SPECIFICATION'")
            
        tables = page.extract_tables()
        if tables:
            for j, t in enumerate(tables):
                print(f"Page {i} Table {j}: {len(t)} rows, {len(t[0]) if t else 0} cols")
