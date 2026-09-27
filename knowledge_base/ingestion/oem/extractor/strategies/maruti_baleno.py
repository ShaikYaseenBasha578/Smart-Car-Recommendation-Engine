from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy

class MarutiBalenoStrategy(BorderlessVariantColumnMatrixStrategy):
    def _find_pages(self, pdf):
        return [10]
        
    def _get_crop_regions(self, page):
        w, h = page.width, page.height
        return [
            (0, 0, w, h)
        ]
        
    def _get_column_headers(self):
        # We know Baleno has 5 feature columns (Sigma, Delta, Zeta, Alpha, Alpha (O))
        # But wait, looking at the header, it's actually:
        # Sigma MT | Delta MT/AMT Delta CNG MT | Zeta MT/AMT Zeta CNG MT | Alpha MT/AMT | Alpha (O) MT/AMT
        # Let's write them cleanly so the expander works.
        return [
            "Sigma MT",
            "Delta MT/AMT & Delta CNG MT",
            "Zeta MT/AMT & Zeta CNG MT",
            "Alpha MT/AMT",
            "Alpha (O) MT/AMT"
        ]
