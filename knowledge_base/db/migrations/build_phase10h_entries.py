"""Phase 10H: build the quarantine entry list (phase10h_entries.csv) (Q1 mislinked obs, Q2 edition obs, Q3 sole-source cells).
Usage: build_entries.py <db_copy> <links_go.tsv> <sole_go.tsv> <out.csv>
Owner decisions (2026-11-03): obs 3302 held out (unclear; Jimny catalogue currency), so v597 cruise_control is not a
sole-source cell; obs already under an active quarantine are skipped (10B-W1 B3)."""
import csv, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
links = list(csv.DictReader(open(sys.argv[2]), delimiter="\t"))
active = {r[0] for r in db.execute("select target_id from evidence_quarantine where released_at is null and target_table='source_observation'")}
REASON = {"MISLINK_TARGET": "H1_RESOLVER_MISLINK", "MISLINK_NONE": "H1_RESOLVER_NO_KB_VARIANT", "EDITION_NOT_IN_KB": "H1_EDITION_NOT_IN_KB"}
out = []
for r in links:
    if r["cls"] not in REASON or int(r["obs"]) in active: continue
    note = (f"src={r['src']}; resolved_variant={r['resolved']} '{r['resolved_name']}'; source_name='{r['raw']}'"
            + (f"; payload_name='{r['payload_name']}'" if r["payload_name"] else "")
            + f"; mismatch={r['why'] or 'edition not modelled in KB'}"
            + (f"; better_target={r['targets']}" if r["cls"] == "MISLINK_TARGET" else "")
            + "; classifier=10H classify_links.py, blind-validated sample")
    out.append(dict(target_table="source_observation", target_id=r["obs"], target_field="", reason_code=REASON[r["cls"]], note=note))
for c in csv.DictReader(open(sys.argv[3]), delimiter="\t"):
    if c["stored_on_variant"] != "True": continue
    out.append(dict(target_table="variant", target_id=c["variant"], target_field=c["field"], reason_code="H1_SOLE_SOURCE_FROM_MISLINK",
                    note=f"canonical={c['canonical']}; all live evidence is from 10H-quarantined observations: {c['evidence']}"))
with open(sys.argv[4], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["target_table", "target_id", "target_field", "reason_code", "note"]); w.writeheader(); w.writerows(out)
from collections import Counter
print(len(out), Counter(e["reason_code"] for e in out))
