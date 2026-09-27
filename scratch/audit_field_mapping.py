import json
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES

pdf_path = "knowledge_base/sources/oem/honda/amaze/latest/brochures/honda_amaze_brochure.pdf"
strategy = classify_layout(pdf_path, "Honda", "Amaze")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

identity = ['variant_name', 'fuel_type', 'transmission', 'engine_cc', 'engine_name', 'edition', 'powertrain_type', 'raw_variant_name']

mapped = 0
unmapped = 0
examples = {}

for p in payloads:
    for k, v in p.items():
        if k in identity: continue
        kl = k.lower().strip()
        if kl in OEM_FIELD_RULES:
            mapped += 1
        else:
            unmapped += 1
            if kl not in examples:
                examples[kl] = v

print(f"Honda Amaze: Mapped = {mapped}, Unmapped = {unmapped}")
print("\nUnmapped Field Examples:")
for k, v in list(examples.items())[:20]:
    print(f"  '{k}' -> '{v}'")
