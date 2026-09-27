import json
with open("scratch/swift_dry_run_extracted.json", "r") as f:
    payloads = json.load(f)

for p in payloads:
    p['variant_name'] = p['raw_variant_name'].replace(' CNG', '')
    if p['powertrain_type'] == 'CNG':
        p['fuel_type'] = 'CNG'
        p['variant_name'] += ' CNG'
    else:
        p['fuel_type'] = 'Petrol'
        p['variant_name'] += ' Petrol'
        
    if p['transmission'] == 'AMT':
        p['variant_name'] += ' AMT'
    else:
        p['variant_name'] += ' Manual'
        
    p['engine_cc'] = 1197
    p['price_ex_showroom'] = None

with open("scratch/swift_dry_run_extracted.json", "w") as f:
    json.dump(payloads, f, indent=2)
