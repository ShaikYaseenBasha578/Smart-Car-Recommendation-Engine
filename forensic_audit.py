import sqlite3
import json
import os

DB_PATH = 'knowledge_base/carrec_kb.db'
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

def q(query, params=()):
    c.execute(query, params)
    return c.fetchall()

def q_val(query, params=()):
    c.execute(query, params)
    res = c.fetchone()
    return res[0] if res else 0

# 1. DB Changes (Pre vs Post)
with open('knowledge_base/carwale_snapshot_before.json', 'r') as f:
    pre = json.load(f)

post = {
    'manufacturer': q_val("SELECT COUNT(*) FROM manufacturer"),
    'model': q_val("SELECT COUNT(*) FROM model"),
    'generation': q_val("SELECT COUNT(*) FROM generation"),
    'powertrain': q_val("SELECT COUNT(*) FROM powertrain"),
    'base_variants': q_val("SELECT COUNT(*) FROM variant WHERE edition_classification IS NULL"),
    'edition_variants': q_val("SELECT COUNT(*) FROM variant WHERE edition_classification IS NOT NULL"),
    'source': q_val("SELECT COUNT(*) FROM source"),
    'source_observation': q_val("SELECT COUNT(*) FROM source_observation"),
    'field_provenance': q_val("SELECT COUNT(*) FROM field_provenance"),
    'variant_alias': q_val("SELECT COUNT(*) FROM variant_alias")
}

print("=== DB Changes ===")
for k in pre:
    print(f"{k}: Pre={pre[k]}, Post={post.get(k, 0)}, Diff={post.get(k, 0) - pre[k]}")

# Integrity Checks
duplicate_base = q_val("SELECT COUNT(*) FROM (SELECT name FROM variant WHERE edition_classification IS NULL GROUP BY name, model_id HAVING COUNT(*) > 1)")
print(f"Duplicate Base Variants: {duplicate_base}")

# 2. CarWale Resolution
cw_obs = q("SELECT resolution_status, COUNT(*) as cnt FROM source_observation WHERE source_id=4 GROUP BY resolution_status")
print("\n=== CW Resolution ===")
discovered = q_val("SELECT COUNT(*) FROM source_observation WHERE source_id=4")
print(f"Total Discovered: {discovered}")
for row in cw_obs:
    print(f"{row['resolution_status']}: {row['cnt']}")

# 3. Editions
editions_created = q_val("SELECT COUNT(*) FROM variant WHERE edition_classification IS NOT NULL")
print(f"\n=== Editions ===")
print(f"Editions Created: {editions_created}")
ed_class = q("SELECT edition_classification, COUNT(*) as cnt FROM variant WHERE edition_classification IS NOT NULL GROUP BY edition_classification")
for row in ed_class:
    print(f"{row['edition_classification']}: {row['cnt']}")

# 4. Conflicts
print("\n=== Conflicts/Provenance ===")
prov_decisions = q("SELECT decision, decision_reason, COUNT(*) as cnt FROM field_provenance WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4) GROUP BY decision, decision_reason")
for row in prov_decisions:
    print(f"{row['decision']} ({row['decision_reason']}): {row['cnt']}")

