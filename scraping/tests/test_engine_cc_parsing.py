import unittest

from scraping.sources.carwale_variant_parser import normalize_engine_cc


class EngineCcParsingTest(unittest.TestCase):
    def test_cc_values_parse(self):
        self.assertEqual(normalize_engine_cc("1199 cc"), 1199)
        self.assertEqual(normalize_engine_cc("1497 cc"), 1497)

    def test_power_values_do_not_parse_as_cc(self):
        self.assertIsNone(normalize_engine_cc("118 bhp"))
        self.assertIsNone(normalize_engine_cc("99 bhp"))
        self.assertIsNone(normalize_engine_cc("Permanent Magnet Synchronous Motor 134 bhp"))

    def test_missing_displacement_remains_null(self):
        self.assertIsNone(normalize_engine_cc(None))


if __name__ == "__main__":
    unittest.main()
