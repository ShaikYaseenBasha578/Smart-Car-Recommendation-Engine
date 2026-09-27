import glob

for test_file in glob.glob("knowledge_base/tests/*.py"):
    with open(test_file, 'r') as f:
        code = f.read()
    
    code = code.replace("from ..ingestion.field_map", "from knowledge_base.ingestion.91wheels.field_map_91wheels")
    code = code.replace("from ..ingestion.extractor_91wheels", "from knowledge_base.ingestion.91wheels.extractor_91wheels")
    code = code.replace("from ..ingestion.resolver", "from knowledge_base.ingestion.common.resolver")
    code = code.replace("from ..ingestion.updater", "from knowledge_base.ingestion.common.updater")
    code = code.replace("from knowledge_base.ingestion.resolver", "from knowledge_base.ingestion.common.resolver")
    code = code.replace("from knowledge_base.ingestion.updater", "from knowledge_base.ingestion.common.updater")
    code = code.replace("from knowledge_base.ingestion.field_map", "from knowledge_base.ingestion.91wheels.field_map_91wheels")
    code = code.replace("from knowledge_base.ingestion.extractor_91wheels", "from knowledge_base.ingestion.91wheels.extractor_91wheels")
    
    with open(test_file, 'w') as f:
        f.write(code)
