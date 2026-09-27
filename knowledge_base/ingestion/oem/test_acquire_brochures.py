import unittest
from urllib.parse import urlparse
import sys
import os
import shutil

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import acquire_brochures as ab

class TestAcquisition(unittest.TestCase):
    def setUp(self):
        self.mg_config = ab.OEM_DOMAINS['MG']
        self.mahindra_config = ab.OEM_DOMAINS['Mahindra']
        
    def test_hostname_validation(self):
        self.assertTrue(ab.is_valid_domain("https://mahindra.com/brochure.pdf", self.mahindra_config))
        self.assertTrue(ab.is_valid_domain("https://auto.mahindra.com/brochure.pdf", self.mahindra_config))
        
    def test_trusted_cdn_validation(self):
        # MG explicitly trusts scene7.com
        self.assertTrue(ab.is_valid_domain("https://s7ap1.scene7.com/brochure.pdf", self.mg_config))
        
    def test_arbitrary_cdn_rejection(self):
        # Mahindra does not have scene7 or amazonaws trusted
        self.assertFalse(ab.is_valid_domain("https://s7ap1.scene7.com/brochure.pdf", self.mahindra_config))
        self.assertFalse(ab.is_valid_domain("https://s3.amazonaws.com/mahindra/brochure.pdf", self.mahindra_config))
        self.assertFalse(ab.is_valid_domain("https://random.cloudfront.net/mahindra.pdf", self.mahindra_config))
        
    def test_lookalike_rejection(self):
        self.assertFalse(ab.is_valid_domain("https://evil-example-mahindra.com/brochure.pdf", self.mahindra_config))
        
    def test_viewer_wrapper_handling(self):
        url = "https://www.nexaexperience.com/pdf-viewer?pdf=/content/dam/msil/nexa/in/en/assets/cars/evitara/documents/e_VITARA_Brochure.pdf"
        resolved = ab.resolve_viewer_wrappers(url, url)
        self.assertEqual(resolved, "https://www.nexaexperience.com/content/dam/msil/nexa/in/en/assets/cars/evitara/documents/e_VITARA_Brochure.pdf")

    def test_model_counts(self):
        models = ab.get_models()
        self.assertEqual(len(models), 62)

    def test_pdf_validation_missing_magic_bytes(self):
        # Create fake text file
        with open("fake.pdf", "w") as f: f.write("Not a PDF")
        status = ab.verify_document_content("fake.pdf", "Test", "Test")
        self.assertEqual(status, "REJECTED")
        os.remove("fake.pdf")

if __name__ == '__main__':
    unittest.main()
