import re
from knowledge_base.ingestion.oem.field_map_oem import normalize_boolean, map_oem_fields

def test_mappings():
    # 1. Test '-'
    if normalize_boolean('-') != 0:
        print("FAIL: '-' should map to 0")
    else:
        print("PASS: '-' maps to 0")
        
    # 2. Test optional
    if normalize_boolean('O') != None:
        print("FAIL: 'O' should map to None")
    else:
        print("PASS: 'O' maps to None")
        
    if normalize_boolean('OptionalΔ') != None:
        print("FAIL: 'OptionalΔ' should map to None")
    else:
        print("PASS: 'OptionalΔ' maps to None")
        
    # Test semantic removal checks
    res = map_oem_fields({'traction control system tcs': 'Standard'})
    if 'esc' in res: print("FAIL: traction control implies esc")
    else: print("PASS: traction control does not imply esc")
    
    res = map_oem_fields({'hill descent control': 'Standard'})
    if 'hill_assist' in res: print("FAIL: hill descent implies hill assist")
    else: print("PASS: hill descent does not imply hill assist")
    
    res = map_oem_fields({'driver airbag': 'Standard'})
    if 'airbags' in res: print("FAIL: driver airbag implies total airbags")
    else: print("PASS: driver airbag does not imply total airbags")
    
    res = map_oem_fields({'6 airbags system': 'Standard'})
    if res.get('airbags') == 6: print("PASS: 6 airbags system correctly mapped")
    else: print("FAIL: 6 airbags system not mapped correctly")
    
    res = map_oem_fields({'quadruple vertical ac vents': 'Standard'})
    if 'rear_ac_vents' in res: print("FAIL: vertical ac vents implies rear ac vents")
    else: print("PASS: vertical ac vents does not imply rear ac vents")
    
    res = map_oem_fields({'vehicle stability assist vsa with electronic': 'Standard'})
    if res.get('esc') == 1: print("PASS: Honda VSA implies esc")
    else: print("FAIL: Honda VSA does not imply esc")

test_mappings()
