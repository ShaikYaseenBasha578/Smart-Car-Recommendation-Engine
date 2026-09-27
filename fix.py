with open("scratch/phase6_swift_dry_run.py", "r") as f:
    code = f.read()
code = code.replace("results = process_oem_payload(conn, brochure_payload, 'maruti-suzuki', 'swift', oem_source_id, generation_id=gen_id)", "results = process_oem_payload(conn, brochure_payload, 'maruti-suzuki', 'swift', oem_source_id, generation_id=gen_id)")
code = code.replace("m.name='swift'", "m.name='Swift'")
code = code.replace("BROCHURE_METADATA = {\n    \"__meta__\": {\n        \"oem\": \"maruti-suzuki India Limited\",\n        \"model\": \"swift\",", "BROCHURE_METADATA = {\n    \"__meta__\": {\n        \"oem\": \"Maruti Suzuki India Limited\",\n        \"model\": \"Swift\",")
with open("scratch/phase6_swift_dry_run.py", "w") as f:
    f.write(code)
