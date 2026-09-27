from typing import List
from knowledge_base.ingestion.oem.extractor.base import ConfigurationIR, OEMBrochureLayoutStrategy

class OEMBrochureExtractor:
    def __init__(self, strategy: OEMBrochureLayoutStrategy):
        self.strategy = strategy
        
    def execute(self, pdf_path: str) -> List[dict]:
        configurations: List[ConfigurationIR] = self.strategy.extract(pdf_path)
        payloads = []
        
        for config in configurations:
            payload = {
                "raw_variant_name": config.raw_variant_name,
                "powertrain_type": config.powertrain_type,
                "transmission": config.transmission,
                "fuel_type": config.powertrain_type,
                "engine_name": config.engine_name,
                "edition": config.edition
            }
            
            # Preserve the structured variant name
            import re
            payload['variant_name'] = re.sub(r'\s+', ' ', config.raw_variant_name.strip())
            
            for field in config.fields:
                if field.raw_value is not None:
                    payload[field.field_name] = field.raw_value
                    
            payloads.append(payload)
            
        return payloads
