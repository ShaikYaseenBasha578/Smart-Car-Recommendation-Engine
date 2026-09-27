import pdfplumber
import json
import os

pdfs = [
    ("Swift", "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"),
    ("Creta", "knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf"),
    ("WagonR", "knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf"),
    ("i10_Nios", "knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf"),
    ("Fronx", "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"),
    ("Baleno", "knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf")
]

results = {}

for name, path in pdfs:
    print(f"Inspecting {name}...")
    try:
        with pdfplumber.open(path) as pdf:
            tables_count = 0
            feature_pages = []
            spec_pages = []
            
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text: continue
                text_upper = text.upper()
                
                # Simple heuristics for finding structural pages
                if "TECHNICAL SPECIFICATION" in text_upper or "SPECIFICATIONS" in text_upper:
                    spec_pages.append(i)
                if "FEATURES" in text_upper or "EQUIPMENT" in text_upper:
                    feature_pages.append(i)
                    
                tables = page.extract_tables()
                tables_count += len(tables)
                
            results[name] = {
                "total_pages": len(pdf.pages),
                "tables_extracted": tables_count,
                "spec_pages": spec_pages,
                "feature_pages": feature_pages
            }
    except Exception as e:
        print(f"Error reading {name}: {e}")

print(json.dumps(results, indent=2))
