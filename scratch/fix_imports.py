def fix_file(path, old_import, new_import):
    with open(path, "r") as f:
        text = f.read()
    text = text.replace(old_import, new_import)
    with open(path, "w") as f:
        f.write(text)

fix_file(
    "knowledge_base/ingestion/oem/extractor/strategies/swift_2024.py",
    "from knowledge_base.ingestion.oem.extractor.base import VariantColumnMatrixStrategy, ConfigurationIR, ExtractedField",
    "from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy\nfrom knowledge_base.ingestion.oem.extractor.base import ConfigurationIR, ExtractedField"
)

fix_file(
    "knowledge_base/ingestion/oem/extractor/strategies/hyundai_creta_2024.py",
    "from knowledge_base.ingestion.oem.extractor.base import EngineTrimCrossMatrixStrategy, ConfigurationIR, ExtractedField",
    "from knowledge_base.ingestion.oem.extractor.families.engine_trim_cross_matrix import EngineTrimCrossMatrixStrategy\nfrom knowledge_base.ingestion.oem.extractor.base import ConfigurationIR, ExtractedField"
)
