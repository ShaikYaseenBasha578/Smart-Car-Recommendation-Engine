-- Phase 10B W3b: quarantine-aware safety applicability view (additive, schema only).
-- Required consumer read path for safety applicability (CLAUDE.md). Raw table stays allowed for audits.
-- Excludes applicability rows that are (1) under active quarantine, (2) whose safety_test is under active
-- quarantine, or (3) whose safety_test maps to canonical status 'no_match' in v_safety_test_status.
CREATE VIEW IF NOT EXISTS v_safety_applicability_q AS
  SELECT a.*
  FROM safety_test_applicability a
  WHERE NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='safety_test_applicability' AND q.target_id=a.id)
    AND NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='safety_test' AND q.target_id=a.safety_test_id)
    AND NOT EXISTS (SELECT 1 FROM v_safety_test_status s
                    WHERE s.safety_test_id=a.safety_test_id AND s.canonical_status='no_match');
