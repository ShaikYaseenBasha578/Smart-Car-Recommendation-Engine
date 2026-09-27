import json

baseline = ['Honda_City', 'Hyundai_Aura', 'Maruti Suzuki_Fronx', 'Maruti Suzuki_Victoris', 'Maruti Suzuki_Swift']

with open("knowledge_base/sources/oem/batch_report.json") as f:
    r = json.load(f)

success = r.get("GENERIC_SUCCESS", [])
missing = [m for m in baseline if m not in success]

if missing:
    print(f"FAILED: Missing from GENERIC_SUCCESS: {missing}")
else:
    print("SUCCESS: All 5 baseline models are in GENERIC_SUCCESS!")
