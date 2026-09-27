from knowledge_base.ingestion.oem.extractor.strategies.hyundai_creta_2024 import HyundaiCreta2024Strategy

strategy = HyundaiCreta2024Strategy()
try:
    configs = strategy.extract("knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf")
    print(f"Extracted {len(configs)}")
except Exception as e:
    print(f"Failed: {e}")
