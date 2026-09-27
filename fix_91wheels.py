import glob, os

for root, dirs, files in os.walk('knowledge_base'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r') as file:
                code = file.read()
            if "91wheels" in code:
                # We want to replace knowledge_base.ingestion.91wheels
                # with knowledge_base.ingestion.source_91wheels
                code = code.replace("knowledge_base.ingestion.91wheels", "knowledge_base.ingestion.source_91wheels")
                with open(path, 'w') as file:
                    file.write(code)
