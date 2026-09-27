with open('knowledge_base/ingestion/oem/extractor/classifier.py', 'r') as f:
    content = f.read()

content = content.replace("with pdfplumber.open(pdf_path) as pdf:", "if make.lower() == 'tata':\n        with pdfplumber.open(pdf_path) as pdf:")

with open('knowledge_base/ingestion/oem/extractor/classifier.py', 'w') as f:
    f.write(content)
