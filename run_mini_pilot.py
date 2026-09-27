import sqlite3
import knowledge_base.ingestion.carwale.ingest_carwale as cw
cw.DB_PATH = 'knowledge_base/carrec_kb.db'

# Clear state
conn = sqlite3.connect(cw.DB_PATH)
c = conn.cursor()
c.execute("DELETE FROM field_provenance WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4 AND source_url LIKE '%harrier%')")
c.execute("DELETE FROM source_observation WHERE source_id=4 AND source_url LIKE '%harrier%'")
c.execute("DELETE FROM variant WHERE edition_classification IS NOT NULL")
conn.commit()

# Monkeypatch extract_all_model_urls to return ONLY the 8 we care about
original_extract = cw.extract_all_model_urls
def mini_extract(*args):
    return [
        "https://www.carwale.com/tata-cars/harrier/smart-diesel-20l-turbo-manual/",
        "https://www.carwale.com/tata-cars/harrier/pure-x-petrol-15l-turbo-manual-dark-edition/",
        "https://www.carwale.com/tata-cars/harrier/adventure-x-petrol-15l-turbo-manual/",
        "https://www.carwale.com/tata-cars/harrier/pure-x-diesel-20l-turbo-manual/",
        "https://www.carwale.com/tata-cars/harrier/adventure-x-plus-petrol-15l-turbo-manual/",
        "https://www.carwale.com/tata-cars/harrier/adventure-x-dark-edition-petrol-15l-turbo-manual/",
        "https://www.carwale.com/tata-cars/harrier/pure-x-petrol-15l-turbo-automatic-tc/",
        "https://www.carwale.com/tata-cars/harrier/adventure-x-plus-dark-edition-petrol-15l-turbo-manual/"
    ]
cw.extract_all_model_urls = mini_extract
cw.ingest_model_pilot('tata', 'harrier', 'harrier')
