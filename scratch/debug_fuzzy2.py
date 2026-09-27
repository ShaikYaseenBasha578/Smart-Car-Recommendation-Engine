def validate_structured(c, fuel, trans, cc, price):
    warnings = []
    if fuel and c['fuel_type']:
        f1, f2 = fuel.lower(), c['fuel_type'].lower()
        if f1 != f2:
            # FIX: Require 'cng' in f2 if f1 is 'cng'
            if not (f1 == 'cng' and 'cng' in f2):
                warnings.append('fuel_mismatch')
    if trans and c['transmission']:
        t1 = 'auto' if trans.lower() in ['automatic', 'amt', 'cvt', 'dct', 'tc', 'ivt', 'dca', 'torque converter', 'e-cvt'] else 'manual'
        t2 = 'auto' if c['transmission'].lower() in ['automatic', 'amt', 'cvt', 'dct', 'tc', 'ivt', 'torque converter', 'e-cvt'] else 'manual'
        if t1 != t2:
            warnings.append('transmission_mismatch')
    if cc and c['engine_cc'] and abs(cc - c['engine_cc']) > 50:
        warnings.append('engine_cc_mismatch')
    return warnings

c1 = {'fuel_type': 'Petrol', 'transmission': 'Manual', 'engine_cc': None}
c2 = {'fuel_type': 'Petrol CNG', 'transmission': 'Manual', 'engine_cc': None}

print(validate_structured(c1, 'CNG', 'Manual', None, None))
print(validate_structured(c2, 'CNG', 'Manual', None, None))
