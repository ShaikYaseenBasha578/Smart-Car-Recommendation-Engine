import sys, os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.oem.extractor.base import ConfigurationIR

ir = ConfigurationIR(
    raw_variant_name="AXT",
    powertrain_type=None,
    transmission=None,
    engine_name=None,
    fields=[]
)
try:
    res = resolve_variant("Mahindra", "Thar", ir.raw_variant_name, ir.powertrain_type, ir.transmission, ir.engine_name, ir.edition)
    print(f"Resolved: {res}")
except Exception as e:
    print(f"Resolver failed: {e}")
    print("RAW_IDENTITY_PRESERVED")
    print("RESOLUTION_UNRESOLVED")
