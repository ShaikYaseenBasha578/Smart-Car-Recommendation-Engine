with open('knowledge_base/tests/test_integration.py', 'r') as f:
    code = f.read()

code = code.replace("vid, status = resolve_variant", "vid, status, base_id = resolve_variant")
code = code.replace("update_canonical(conn, vid, 1, 'http', 'E', {}, status, {'boot_space_litres': 433})", "update_canonical(conn, vid, 1, 'http', 'E', {}, status, {'boot_space_litres': 433}, base_id)")

with open('knowledge_base/tests/test_integration.py', 'w') as f:
    f.write(code)
