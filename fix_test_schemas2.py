import glob

for test_file in glob.glob("knowledge_base/tests/*.py"):
    with open(test_file, 'r') as f:
        code = f.read()
    
    code = code.replace(
        "INSERT INTO variant VALUES (1, 1, 1, 'E Petrol MT', 'Manual', 1090000, NULL)",
        "INSERT INTO variant (id, model_id, powertrain_id, name, transmission, price_ex_showroom, boot_space_litres) VALUES (1, 1, 1, 'E Petrol MT', 'Manual', 1090000, NULL)"
    )
    
    with open(test_file, 'w') as f:
        f.write(code)
