"""Phase 10H, read-only: canonical cells left with no live evidence if the mislinked observations are quarantined.
Usage: sole_source.py <db_copy> <links.tsv> <out.tsv> [--with-editions]"""
import csv, sqlite3, sys
from collections import Counter
db = sqlite3.connect(sys.argv[1])
links = {int(r["obs"]): r for r in csv.DictReader(open(sys.argv[2]), delimiter="\t")}
classes = {"MISLINK_TARGET", "MISLINK_NONE"} | ({"EDITION_NOT_IN_KB"} if "--with-editions" in sys.argv else set())
bad = {o for o, r in links.items() if r["cls"] in classes}
ids = ",".join(map(str, bad))
cols = {c[1] for c in db.execute("pragma table_info(v_variant_canonical_q)")}
IDENTITY = {"transmission"}  # copied from the v6 row; v6 wrote no provenance row for it
cand = db.execute(f"""with a as (select variant_id, field_name from v_live_evidence where decision in ('accepted','confirmed') and observation_id in ({ids}) group by 1,2),
  b as (select variant_id, field_name from v_live_evidence where decision in ('accepted','confirmed') and observation_id not in ({ids}) group by 1,2)
  select a.variant_id, a.field_name from a left join b using(variant_id, field_name) where b.field_name is null order by 1,2""").fetchall()
out = []
for vid, f in cand:
    if f in IDENTITY or f not in cols: continue
    canon = db.execute(f'select "{f}" from v_variant_canonical_q where id=?', (vid,)).fetchone()[0]
    if canon is None: continue
    own = db.execute(f'select "{f}", base_variant_id from variant where id=?', (vid,)).fetchone()
    ev = db.execute(f"""select fp.id, fp.decision, fp.accepted_value, fp.source_observation_id, s.name from field_provenance fp
        join source_observation o on o.id=fp.source_observation_id join source s on s.id=o.source_id
        where fp.variant_id=? and fp.field_name=? and fp.source_observation_id in ({ids})
        and fp.id in (select fp_id from v_live_evidence) order by fp.id""", (vid, f)).fetchall()
    out.append(dict(variant=vid, field=f, canonical=canon, stored_on_variant=own[0] is not None, base=own[1] or "",
                    evidence=";".join(f"fp{e[0]}:{e[1]}={e[2]}<-obs{e[3]}({e[4]},{links[e[3]]['cls']})" for e in ev)))
with open(sys.argv[3], "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0]), delimiter="\t"); w.writeheader(); w.writerows(out)
print(len(out), "cells;", Counter(o["field"] for o in out).most_common(), "| stored on variant:", sum(o["stored_on_variant"] for o in out),
      "| decisions:", Counter("accepted" if ":accepted=" in o["evidence"] else "confirmed-only" for o in out))
