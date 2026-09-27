with open("knowledge_base/ingestion/oem/ingest_oem.py", "r") as f:
    code = f.read()

code = code.replace(
    "generation_id=generation_id, active_only=False",
    "generation_id=generation_id, active_only=False, source_name='oem'"
)

with open("knowledge_base/ingestion/oem/ingest_oem.py", "w") as f:
    f.write(code)
