import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES

pdf_path = "knowledge_base/sources/oem/honda/city/latest/brochures/City-Brochure.pdf"
strategy = classify_layout(pdf_path, "Honda", "City")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

identity = ['variant_name', 'fuel_type', 'transmission', 'engine_cc', 'engine_name', 'edition', 'powertrain_type', 'raw_variant_name']
examples = {}
for p in payloads[:1]:
    for k, v in p.items():
        if k in identity: continue
        kl = k.lower().strip()
        if kl not in OEM_FIELD_RULES:
            examples[kl] = v

print("\nHonda City Unmapped Field Examples:")
for k, v in list(examples.items())[:20]:
    print(f"  '{k}' -> '{v}'")
