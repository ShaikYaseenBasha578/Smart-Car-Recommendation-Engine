import pdfplumber
import json
with pdfplumber.open("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf") as pdf:
    settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
    tables = pdf.pages[12].extract_tables(table_settings=settings)
    
    settings_text = {"vertical_strategy": "text", "horizontal_strategy": "text"}
    tables_text = pdf.pages[12].extract_tables(table_settings=settings_text)
    
    out = {"lines": tables, "text": tables_text}
    with open("scratch/creta_tables_test.json", "w") as f:
        json.dump(out, f, indent=2)
