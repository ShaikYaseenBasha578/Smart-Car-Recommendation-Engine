from dataclasses import dataclass, field
from typing import List, Optional, Any

@dataclass
class ExtractedField:
    field_name: str
    raw_value: Any
    source_page: Optional[int] = None
    section: Optional[str] = None
    
@dataclass
class ConfigurationIR:
    raw_variant_name: str  # Trim or Variant
    powertrain_type: str   # Petrol, Diesel, CNG
    transmission: str      # MT, AT, AMT, etc.
    engine_name: Optional[str] = None # e.g. "1.5 l U2 CRDi"
    edition: Optional[str] = None
    fields: List[ExtractedField] = field(default_factory=list)

class OEMBrochureLayoutStrategy:
    def extract(self, pdf_path: str) -> List[ConfigurationIR]:
        raise NotImplementedError
