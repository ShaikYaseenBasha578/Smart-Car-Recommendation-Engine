import pypdf

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"

try:
    with open(pdf_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        text = ""
        for i, page in enumerate(reader.pages):
            text += page.extract_text()
            if i > 5: break
        print(text[:1000])
except Exception as e:
    print(e)
