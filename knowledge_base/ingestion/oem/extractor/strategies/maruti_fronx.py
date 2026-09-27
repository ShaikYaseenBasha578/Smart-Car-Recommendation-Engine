from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy

class MarutiFronxStrategy(BorderlessVariantColumnMatrixStrategy):
    def _find_pages(self, pdf):
        return [18, 19]
        
    def _get_crop_regions(self, page):
        w, h = page.width, page.height
        return [
            (0, 0, w/2, h),
            (w/2, 0, w, h)
        ]
        
    def _get_column_headers(self):
        return [
            "Sigma 1.2L MT/MT CNG",
            "Delta 1.2L MT/MT CNG/AMT",
            "Delta+ 1.2L MT/AMT & 1.0L Turbo MT",
            "Zeta 1.0L Turbo MT/AT",
            "Alpha 1.0L Turbo MT/AT"
        ]
