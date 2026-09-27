from knowledge_base.ingestion.carwale.extractor_carwale import fetch_carwale_state
state = fetch_carwale_state('https://www.carwale.com/mahindra-cars/scorpio-n/')
versions = state.get('modelPage', {}).get('versions', [])
print(f"Versions: {len(versions)}")
for v in versions[:3]:
    print(v.get('versionName'), "->", v.get('versionMaskingName'))
