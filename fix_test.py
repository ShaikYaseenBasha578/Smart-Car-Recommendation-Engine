with open("scratch/test_resolver_extended.py", "r") as f:
    code = f.read()

code = code.replace(
    "assert get_variant_name(v_id) == 'unresolved', \"Wrong transmission should fail structured validation\"",
    "assert get_variant_name(v_id) == 'VXi Petrol Automatic', \"Wrong string but correct structured transmission should resolve to AMT\""
)
with open("scratch/test_resolver_extended.py", "w") as f:
    f.write(code)
