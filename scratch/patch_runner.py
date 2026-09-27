with open('scratch/production_ingestion_runner.py', 'r') as f:
    text = f.read()

text = text.replace("gen_result = resolve_oem_generation(conn, make, model)", "gen_result = resolve_oem_generation(conn, make, model, info.get('year'))")

with open('scratch/production_ingestion_runner.py', 'w') as f:
    f.write(text)
