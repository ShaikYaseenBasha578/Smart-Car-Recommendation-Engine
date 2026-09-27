import sys
import tempfile
import pathlib

class MockTmpPath:
    def __init__(self, p):
        self.p = p
    def __truediv__(self, other):
        return self.p / other

try:
    from knowledge_base.tests.test_editions import test_edition_resolution_and_creation, setup_db
    with tempfile.TemporaryDirectory() as td:
        tp = MockTmpPath(pathlib.Path(td))
        conn = setup_db(tp)
        test_edition_resolution_and_creation(conn)
    print("Editions tests: PASSED")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Editions tests: FAILED", e)
