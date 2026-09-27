import sys
import os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy

strat = BorderlessVariantColumnMatrixStrategy()
print(strat._expand_header("Delta+ 1.2L MT/AMT & 1.0L Turbo MT"))
print(strat._expand_header("Zeta 1.0L Turbo MT/AT"))
