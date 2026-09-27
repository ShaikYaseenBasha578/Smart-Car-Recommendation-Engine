with open("knowledge_base/ingestion/common/updater.py", "r") as f:
    code = f.read()

pt_logic = '''
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
                        cur.execute(\'''
                            SELECT s.name as source_name, fp.decided_at 
                            FROM field_provenance fp
                            JOIN source_observation so ON fp.source_observation_id = so.id
                            JOIN source s ON so.source_id = s.id
                            WHERE fp.variant_id = ? AND fp.field_name = ? AND fp.decision IN ('accepted', 'confirmed')
                            ORDER BY fp.decided_at DESC
                        \''', (variant_id, field))
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
                                
                    cur.execute(\'''
                        INSERT INTO field_provenance (variant_id, field_name, accepted_value, source_observation_id, decision, decision_reason)
                        VALUES (?, ?, ?, ?, ?, ?)
                    \''', (variant_id, field, str(val), obs_id, decision, reason))
            
            if pt_updates:
                set_clause = ', '.join([f"{k} = ?" for k in pt_updates.keys()])
                values = list(pt_updates.values())
                values.append(pt_id)
                cur.execute(f"UPDATE powertrain SET {set_clause} WHERE id = ?", values)
                updates += len(pt_updates)

'''

# Insert this block right before: "if canonical_updates:"
code = code.replace("if canonical_updates:", pt_logic + "    if canonical_updates:")

with open("knowledge_base/ingestion/common/updater.py", "w") as f:
    f.write(code)
