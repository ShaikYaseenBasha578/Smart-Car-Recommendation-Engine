with open("knowledge_base/ingestion/oem/extractor/classifier.py", "r") as f:
    content = f.read()

content = content.replace("bordered = VariantColumnMatrixStrategy(make=make, model=model)", "bordered = VariantColumnMatrixStrategy()")

with open("knowledge_base/ingestion/oem/extractor/classifier.py", "w") as f:
    f.write(content)
