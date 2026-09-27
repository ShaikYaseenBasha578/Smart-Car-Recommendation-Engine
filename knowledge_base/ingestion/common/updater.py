from knowledge_base.ingestion.common.authority_matrix import get_authority_tier

import sqlite3
import json


def _norm_bool(v):
    if v in (1, '1', 'True', 'true', True): return '1'
    if v in (0, '0', 'False', 'false', False): return '0'
    if v is None: return None
    return str(v)

def update_canonical(conn, variant_id, source_id, url, raw_name, raw_payload, status, normalized_fields, base_variant_id=None):
    cur = conn.cursor()
    if status == 'edition_candidate' and base_variant_id:
        cur.execute("SELECT id FROM variant WHERE base_variant_id = ? AND name = ?", (base_variant_id, raw_name))
        ex_edition = cur.fetchone()
        if ex_edition:
            variant_id = ex_edition['id']
            status = 'resolved'
        else:
            cur.execute('''
                INSERT INTO variant (base_variant_id, model_id, generation_id, powertrain_id, name, full_name, transmission, drivetrain, is_discontinued, edition_classification)
                SELECT ?, model_id, generation_id, powertrain_id, ?, full_name || ' ' || ?, transmission, drivetrain, is_discontinued, 'UNRESOLVED_EDITION'
                FROM variant WHERE id = ?
            ''', (base_variant_id, raw_name, raw_name, base_variant_id))
            variant_id = cur.lastrowid
            status = 'resolved'

    
    cur.execute('''
        SELECT id FROM source_observation 
        WHERE source_id = ? AND source_url = ? AND raw_name = ?
    ''', (source_id, url, raw_name))
    existing = cur.fetchone()
    if existing:
        return existing['id'], 0
        
    cur.execute('''
        INSERT INTO source_observation (source_id, raw_name, raw_payload, source_url, extraction_method, resolved_variant_id, resolution_status)
        VALUES (?, ?, ?, ?, 'rsc_payload', ?, ?)
    ''', (source_id, raw_name, json.dumps(raw_payload), url, variant_id, status))
    obs_id = cur.lastrowid
    
    if not variant_id or status not in ['resolved', 'resolved_with_warning']:
        return obs_id, 0
        

    updates = 0
    # Use v_effective_variant to get the inherited truth, so we don't treat inherited values as overrides!
    try:
        cur.execute('SELECT * FROM v_effective_variant WHERE id = ?', (variant_id,))
        v_row = cur.fetchone()
    except sqlite3.OperationalError:
        cur.execute('SELECT * FROM variant WHERE id = ?', (variant_id,))
        v_row = cur.fetchone()
    if not v_row: return obs_id, 0
    
    # Also fetch the RAW variant row to know what is ACTUALLY stored on the edition vs base
    cur.execute('SELECT * FROM variant WHERE id = ?', (variant_id,))
    raw_v_row = cur.fetchone()

    
    canonical_updates = {}
    
    for field, val in normalized_fields.items():
        if field not in v_row.keys(): continue

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
                # Value exists directly on this variant, check field-level source authority!
                cur.execute('''
                    SELECT s.name as source_name, fp.decided_at 
                    FROM field_provenance fp
                    JOIN source_observation so ON fp.source_observation_id = so.id
                    JOIN source s ON so.source_id = s.id
                    WHERE fp.variant_id = ? AND fp.field_name = ? AND fp.decision IN ('accepted', 'confirmed')
                    ORDER BY fp.decided_at DESC
                ''', (variant_id, field))
                historical_prov = cur.fetchall()
                
                cur.execute('SELECT name FROM source WHERE id = ?', (source_id,))
                incoming_source_row = cur.fetchone()
                incoming_source_name = incoming_source_row['name'] if incoming_source_row else 'unknown'
                
                incoming_tier = get_authority_tier(incoming_source_name, field)
                
                if historical_prov:
                    # Find the best (lowest integer) authority tier among all accepted/confirmed provenances
                    best_existing_tier = 99
                    for p in historical_prov:
                        p_tier = get_authority_tier(p['source_name'], field)
                        if p_tier < best_existing_tier:
                            best_existing_tier = p_tier
                            
                    if incoming_tier < best_existing_tier: # Lower number means higher authority (Tier 1 > Tier 2)
                        decision = 'accepted'
                        reason = f'field_authority_override_tier_{incoming_tier}_over_{best_existing_tier}'
                        canonical_updates[field] = val
                    else:
                        decision = 'rejected'
                        reason = f'conflict_field_tier_{incoming_tier}_vs_best_{best_existing_tier}'
                else:
                    # If we don't have provenance, check if the incoming source even has authority
                    if incoming_tier < 99:
                        decision = 'accepted'
                        reason = 'edition_override_or_correction'
                        canonical_updates[field] = val
                    else:
                        decision = 'rejected'
                        reason = 'conflict_no_field_authority'

            
        cur.execute('''
            INSERT INTO field_provenance (variant_id, field_name, accepted_value, source_observation_id, decision, decision_reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (variant_id, field, str(val), obs_id, decision, reason))
        

    
    # Powertrain Updates
    pt_id = v_row['powertrain_id']
    pt_updates = {}
    if pt_id:
        cur.execute('SELECT * FROM powertrain WHERE id = ?', (pt_id,))
        pt_row = cur.fetchone()
        if pt_row:
            for field in ['power_bhp', 'torque_nm', 'engine_cc', 'fuel_efficiency', 'battery_capacity_kwh']:
                if field in normalized_fields and normalized_fields[field] is not None:
                    val = normalized_fields[field]
                    can_val = pt_row[field]
                    
                    val_str = _norm_bool(val)
                    can_str = _norm_bool(can_val)
                    
                    if can_val is None and val is not None:
                        pt_updates[field] = val
                        decision = 'accepted'
                        reason = 'new_powertrain_field'
                    elif can_str == val_str:
                        decision = 'confirmed'
                        reason = 'agrees_with_canonical'
                    else:
                        cur.execute('''
                            SELECT s.name as source_name, fp.decided_at 
                            FROM field_provenance fp
                            JOIN source_observation so ON fp.source_observation_id = so.id
                            JOIN source s ON so.source_id = s.id
                            WHERE fp.variant_id = ? AND fp.field_name = ? AND fp.decision IN ('accepted', 'confirmed')
                            ORDER BY fp.decided_at DESC
                        ''', (variant_id, field))
                        historical_prov = cur.fetchall()
                        
                        cur.execute('SELECT name FROM source WHERE id = ?', (source_id,))
                        incoming_source_row = cur.fetchone()
                        incoming_source_name = incoming_source_row['name'] if incoming_source_row else 'unknown'
                        
                        incoming_tier = get_authority_tier(incoming_source_name, field)
                        
                        if historical_prov:
                            best_existing_tier = 99
                            for p in historical_prov:
                                p_tier = get_authority_tier(p['source_name'], field)
                                if p_tier < best_existing_tier:
                                    best_existing_tier = p_tier
                                    
                            if incoming_tier < best_existing_tier:
                                pt_updates[field] = val
                                decision = 'accepted'
                                reason = f'field_authority_override_tier_{incoming_tier}_over_{best_existing_tier}'
                            else:
                                decision = 'rejected'
                                reason = f'conflict_field_tier_{incoming_tier}_vs_best_{best_existing_tier}'
                        else:
                            if incoming_tier < 99:
                                pt_updates[field] = val
                                decision = 'accepted'
                                reason = 'override_or_correction'
                            else:
                                decision = 'rejected'
                                reason = 'conflict_no_field_authority'
                                
                    cur.execute('''
                        INSERT INTO field_provenance (variant_id, field_name, accepted_value, source_observation_id, decision, decision_reason)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (variant_id, field, str(val), obs_id, decision, reason))
            
            if pt_updates:
                set_clause = ', '.join([f"{k} = ?" for k in pt_updates.keys()])
                values = list(pt_updates.values())
                values.append(pt_id)
                cur.execute(f"UPDATE powertrain SET {set_clause} WHERE id = ?", values)
                updates += len(pt_updates)

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

        
    return obs_id, updates
