import re

with open('knowledge_base/ingestion/common/updater.py', 'r') as f:
    code = f.read()

# Change initial classification to UNRESOLVED_EDITION
code = code.replace("'FEATURE_OR_SPEC_DIFFERENCE'", "'UNRESOLVED_EDITION'")

# We can append a check at the end of update_canonical to upgrade the status if there were updates
upgrade_logic = """
    if canonical_updates:
        set_clause = ', '.join([f"{k} = ?" for k in canonical_updates.keys()])
        values = list(canonical_updates.values())
        values.append(variant_id)
        cur.execute(f"UPDATE variant SET {set_clause} WHERE id = ?", values)
        updates = len(canonical_updates)
        
    # Upgrade classification based on evidence
    cur.execute("SELECT base_variant_id, edition_classification FROM variant WHERE id = ?", (variant_id,))
    v_info = cur.fetchone()
    if v_info and v_info['base_variant_id']:
        if updates > 0:
            cur.execute("UPDATE variant SET edition_classification = 'FEATURE_OR_SPEC_DIFFERENCE' WHERE id = ?", (variant_id,))
        elif v_info['edition_classification'] == 'UNRESOLVED_EDITION':
            # If no updates, it's just the same as base
            cur.execute("UPDATE variant SET edition_classification = 'NO_MATERIAL_DIFFERENCE' WHERE id = ?", (variant_id,))
"""

# Replace the end
code = re.sub(r"    if canonical_updates:.*?updates = len\(canonical_updates\)", upgrade_logic, code, flags=re.DOTALL)

with open('knowledge_base/ingestion/common/updater.py', 'w') as f:
    f.write(code)
