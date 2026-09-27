from knowledge_base.ingestion.oem.extractor.families.engine_trim_cross_matrix import EngineTrimCrossMatrixStrategy

class HyundaiAuraStrategy(EngineTrimCrossMatrixStrategy):
    def extract(self, pdf_path):
        # We patch the pdf extraction by overriding a hook or just intercepting.
        # But wait, EngineTrimCrossMatrixStrategy reads text directly from pdfplumber.
        # Let's override `_get_variants` to provide the exact variants to avoid parsing bugs.
        return super().extract(pdf_path)
