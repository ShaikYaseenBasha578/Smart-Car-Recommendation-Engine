with open('scratch/production_ingestion_runner.py', 'r') as f:
    text = f.read()

text = text.replace("generation_id = gen_result['id']", "generation_id = gen_result")

with open('scratch/production_ingestion_runner.py', 'w') as f:
    f.write(text)
