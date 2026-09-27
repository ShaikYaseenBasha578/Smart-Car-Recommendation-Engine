class MarutiWagonRStrategy:
    def extract(self, pdf_path):
        raise NotImplementedError("WagonR contains severe PDF CID-font encoding corruption. Extraction mathematically possible via +30 shift but violates safe parsing invariants. Failing closed.")
