import re

with open('knowledge_base/ingestion/common/updater.py', 'r') as f:
    code = f.read()

new_logic = """
    updates = 0
    # Use v_effective_variant to get the inherited truth, so we don't treat inherited values as overrides!
    cur.execute('SELECT * FROM v_effective_variant WHERE id = ?', (variant_id,))
    v_row = cur.fetchone()
    if not v_row: 
        # Fallback to variant table if view is somehow missing
        cur.execute('SELECT * FROM variant WHERE id = ?', (variant_id,))
        v_row = cur.fetchone()
    if not v_row: return obs_id, 0
    
    # Also fetch the RAW variant row to know what is ACTUALLY stored on the edition vs base
    cur.execute('SELECT * FROM variant WHERE id = ?', (variant_id,))
    raw_v_row = cur.fetchone()
"""

# Replace the fetching part
code = re.sub(r"    updates = 0.*?if not v_row: return obs_id, 0", new_logic, code, flags=re.DOTALL)

# Now fix the comparison
comparison_logic = """
        can_val = v_row[field]
        raw_can_val = raw_v_row[field]
        
        val_str = _norm_bool(val)
        can_str = _norm_bool(can_val)
        
        decision = 'pending'
        reason = ''
        
        # Only accept if the incoming value actually differs from the EFFECTIVE inherited value
        if can_val is None and val is not None:
            decision = 'accepted'
            reason = 'new_field'
            canonical_updates[field] = val
        elif can_str == val_str:
            decision = 'confirmed'
            reason = 'agrees_with_canonical'
        else:
            # It differs from the effective value!
            if raw_can_val is None:
                # The edition hasn't explicitly overridden this yet, so we accept the override!
                decision = 'accepted'
                reason = 'edition_override_or_correction'
                canonical_updates[field] = val
            else:
                decision = 'rejected'
                reason = 'conflict_with_canonical_authority'
"""

code = re.sub(r"        can_val = v_row\[field\].*?reason = 'conflict_with_canonical_authority'", comparison_logic, code, flags=re.DOTALL)

with open('knowledge_base/ingestion/common/updater.py', 'w') as f:
    f.write(code)
