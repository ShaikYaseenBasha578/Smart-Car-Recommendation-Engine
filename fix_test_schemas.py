import glob

for test_file in glob.glob("knowledge_base/tests/*.py"):
    with open(test_file, 'r') as f:
        code = f.read()
    
    code = code.replace(
        "CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, powertrain_id INTEGER, name TEXT, transmission TEXT, price_ex_showroom REAL, boot_space_litres REAL)",
        "CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, generation_id INTEGER, powertrain_id INTEGER, name TEXT, full_name TEXT, transmission TEXT, drivetrain TEXT, is_discontinued INTEGER, price_ex_showroom REAL, boot_space_litres REAL, base_variant_id INTEGER, edition_classification TEXT)"
    )
    
    with open(test_file, 'w') as f:
        f.write(code)
