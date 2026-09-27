import sys
import tempfile
import pathlib

# Mock pytest.fixture and tmp_path
class MockTmpPath:
    def __init__(self, p):
        self.p = p
    def __truediv__(self, other):
        return self.p / other

try:
    from knowledge_base.tests.test_extraction import test_safe_float, test_safe_bool, test_normalization
    test_safe_float()
    test_safe_bool()
    test_normalization()
    print("Extraction tests: PASSED")
except Exception as e:
    print("Extraction tests: FAILED", e)

try:
    from knowledge_base.tests.test_v3cars import test_v3cars_feature_mapping, test_v3cars_transmission_mismatch, test_v3cars_price_parsing
    test_v3cars_feature_mapping()
    test_v3cars_transmission_mismatch()
    test_v3cars_price_parsing()
    print("V3Cars tests: PASSED")
except Exception as e:
    print("V3Cars tests: FAILED", e)

try:
    from knowledge_base.tests.test_integration import test_resolve_and_update
    with tempfile.TemporaryDirectory() as td:
        tp = MockTmpPath(pathlib.Path(td))
        test_resolve_and_update(tp)
    print("Integration tests: PASSED")
except Exception as e:
    print("Integration tests: FAILED", e)

try:
    from knowledge_base.tests.test_editions import test_edition_resolution_and_creation
    # setup_db fixture usually yields a conn
    from knowledge_base.tests.test_editions import setup_db
    # Wait, setup_db is a fixture. We can't just call it easily if it yields.
    # Let's inspect test_editions.py to see how setup_db works
except Exception as e:
    print("Editions tests skipped/failed:", e)

