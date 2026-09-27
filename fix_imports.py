import re

# Carwale
with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'r') as f:
    code = f.read()
code = code.replace("from extractor_carwale", "from knowledge_base.ingestion.carwale.extractor_carwale")
code = code.replace("from field_map_carwale", "from knowledge_base.ingestion.carwale.field_map_carwale")
code = code.replace("from resolver", "from knowledge_base.ingestion.common.resolver")
code = code.replace("from updater", "from knowledge_base.ingestion.common.updater")
with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'w') as f:
    f.write(code)

# V3Cars
with open('knowledge_base/ingestion/v3cars/ingest_v3cars.py', 'r') as f:
    code = f.read()
code = code.replace("from extractor_v3cars", "from knowledge_base.ingestion.v3cars.extractor_v3cars")
code = code.replace("from field_map_v3cars", "from knowledge_base.ingestion.v3cars.field_map_v3cars")
code = code.replace("from resolver", "from knowledge_base.ingestion.common.resolver")
code = code.replace("from updater", "from knowledge_base.ingestion.common.updater")
with open('knowledge_base/ingestion/v3cars/ingest_v3cars.py', 'w') as f:
    f.write(code)

# 91Wheels
with open('knowledge_base/ingestion/91wheels/ingest_91wheels.py', 'r') as f:
    code = f.read()
code = code.replace("from extractor_91wheels", "from knowledge_base.ingestion.91wheels.extractor_91wheels")
code = code.replace("from field_map import", "from knowledge_base.ingestion.91wheels.field_map_91wheels import")
code = code.replace("from resolver", "from knowledge_base.ingestion.common.resolver")
code = code.replace("from updater", "from knowledge_base.ingestion.common.updater")
with open('knowledge_base/ingestion/91wheels/ingest_91wheels.py', 'w') as f:
    f.write(code)
