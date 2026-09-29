"""Phase 10B W6 quarantine builder: the live accepted/confirmed field_provenance rows on the 12 W6 target cells whose
accepted_value contradicts the human-verified value. Held cells (phase10b_w6_held.csv) get no quarantine rows. Quarantining them (never modifying them) stops v_corroboration
from counting evidence that disagrees with the corrected canonical value.
Read-only on the DB (a /tmp copy of production). No value is judged here: the new value comes from
phase10b_w6_targets.csv, and each row's contradiction is a normalised inequality.
Usage (repo root): python3 knowledge_base/db/migrations/build_phase10b_w6_quarantine.py <db_copy>
Writes knowledge_base/db/migrations/phase10b_w6_quarantine.csv
"""
import csv
import sqlite3
import sys

TARGETS = "knowledge_base/db/migrations/phase10b_w6_targets.csv"
OUT = "knowledge_base/db/migrations/phase10b_w6_quarantine.csv"
EXPECTED = 13
REASON = "CONTRADICTED_BY_OEM_SPOTCHECK"
V3CARS = 3
W2_RULE = ("W2 rule: V3Cars maps 'keyword not found' to 0 (field_map_v3cars.py:24), so a V3Cars zero is not "
           "independent evidence of absence")
NORM = {"1": 1, "true": 1, "0": 0, "false": 0}


def norm(v):
    return NORM[str(v).strip().lower()]


def main():
    c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    targets = list(csv.DictReader(open(TARGETS, newline="")))
    assert len(targets) == 12
    out = []
    for t in targets:
        new = norm(t["new_value"])
        rows = c.execute("""select e.fp_id, e.source_id, s.name, e.decision, e.accepted_value
                            from v_live_evidence e join source s on s.id = e.source_id
                            where e.variant_id = ? and e.field_name = ? and e.decision in ('accepted','confirmed')
                            order by e.fp_id""", (t["variant_id"], t["column"])).fetchall()
        for fp_id, sid, sname, decision, val in rows:
            if norm(val) == new:
                continue  # agrees with the verified value: stays live
            note = (f"fp_id={fp_id}; variant_id={t['variant_id']}; field={t['column']}; source={sname}; "
                    f"decision={decision}; accepted_value={val}; contradicts OEM spot-check value {t['new_value']} "
                    f"(sheet_row={t['sheet_row']}, provenance_id={t['provenance_id']})")
            if sid == V3CARS and norm(val) == 0:
                note += "; " + W2_RULE
            out.append({"target_table": "field_provenance", "target_id": fp_id, "variant_id": t["variant_id"],
                        "column": t["column"], "source_id": sid, "source_name": sname, "decision": decision,
                        "accepted_value": val, "verified_value": t["new_value"], "sheet_row": t["sheet_row"],
                        "reason_code": REASON, "phase": "10B-W6", "note": note})
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for o in out:
        print(o["target_id"], o["variant_id"], o["column"], o["source_name"], o["decision"], o["accepted_value"], "vs", o["verified_value"])
    print(f"quarantine rows={len(out)}")
    if len(out) != EXPECTED:
        sys.exit(f"STOP: expected {EXPECTED}, got {len(out)}")


if __name__ == "__main__":
    main()
