with open("knowledge_base/ingestion/oem/extractor/classifier.py", "r") as f:
    content = f.read()

content = content.replace("bordered = VariantColumnMatrixStrategy()", "bordered = VariantColumnMatrixStrategy(make=make, model=model)")

with open("knowledge_base/ingestion/oem/extractor/classifier.py", "w") as f:
    f.write(content)
