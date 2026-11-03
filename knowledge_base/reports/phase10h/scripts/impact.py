"""Phase 10H, read-only: what the mislinked observations feed. Usage: impact.py <db_copy> <links.tsv>"""
import csv, sqlite3, sys
from collections import Counter, defaultdict
db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row
links = {int(r["obs"]): r for r in csv.DictReader(open(sys.argv[2]), delimiter="\t")}
BAD = {"MISLINK_TARGET", "MISLINK_NONE"}
cls_of = lambda oid: links[oid]["cls"] if oid in links else None
bad = {o for o, r in links.items() if r["cls"] in BAD}
edn = {o for o, r in links.items() if r["cls"] == "EDITION_NOT_IN_KB"}
qobs = {r[0] for r in db.execute("select target_id from v_active_quarantine where target_table='source_observation'")}
qfp = {r[0] for r in db.execute("select target_id from v_active_quarantine where target_table='field_provenance'")}
print("already quarantined: mislinked obs", len(bad & qobs), "edition obs", len(edn & qobs))
fps = db.execute(f"select * from field_provenance where source_observation_id in ({','.join(map(str, bad | edn))})").fetchall()
print("fp rows on mislinked obs, by decision:", Counter((("MISLINK" if f["source_observation_id"] in bad else "EDITION"), f["decision"]) for f in fps))
cols = {c[1] for c in db.execute("pragma table_info(v_variant_canonical_q)")}
src_of = dict(db.execute("select o.id, s.name from source_observation o join source s on s.id=o.source_id").fetchall())
canon = []
for f in fps:
    if f["decision"] != "accepted" or f["id"] in qfp or f["source_observation_id"] in qobs or f["field_name"] not in cols: continue
    v = db.execute(f'select "{f["field_name"]}" from v_variant_canonical_q where id=?', (f["variant_id"],)).fetchone()[0]
    if v is None or str(v) != f["accepted_value"] and not (isinstance(v, float) and f["accepted_value"] and float(f["accepted_value"]) == v): continue
    raw = db.execute(f'select "{f["field_name"]}" from variant where id=?', (f["variant_id"],)).fetchone()[0]
    others = db.execute(f"""select o.id, s.name, fp.decision, fp.accepted_value from field_provenance fp join source_observation o on o.id=fp.source_observation_id
        join source s on s.id=o.source_id where fp.variant_id=? and fp.field_name=? and fp.id<>? and fp.decision in ('accepted','confirmed')""",
        (f["variant_id"], f["field_name"], f["id"])).fetchall()
    good = [(s, d, val) for oid, s, d, val in others if oid not in bad and oid not in edn and oid not in qobs]
    agree = [g for g in good if g[2] == f["accepted_value"]]
    canon.append(dict(fp=f["id"], variant=f["variant_id"], field=f["field_name"], value=f["accepted_value"], own_cell=raw is not None,
                      obs=f["source_observation_id"], src=src_of[f["source_observation_id"]], cls=cls_of(f["source_observation_id"]),
                      support=";".join(f"{s}:{d}" for s, d, _ in agree)))
print(f"canonical cells whose accepted value comes from a mislinked/edition obs: {len(canon)}")
print("  by class:", Counter(c["cls"] for c in canon))
print("  by field:", Counter(c["field"] for c in canon).most_common())
print("  with independent agreeing support:", sum(1 for c in canon if c["support"]), "| sole support:", sum(1 for c in canon if not c["support"]))
print("  cell stored on the variant itself (not inherited):", sum(c["own_cell"] for c in canon))
with open("canonical_cells.tsv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(canon[0]), delimiter="\t"); w.writeheader(); w.writerows(canon)
# corroboration counts that fall if mislinked (and, separately, edition) obs are excluded
def drop(excl):
    ids = ",".join(map(str, excl))
    return db.execute(f"""with a as (select variant_id, field_name, count(distinct source_id) n from v_live_evidence where decision in ('accepted','confirmed') group by 1,2),
      b as (select variant_id, field_name, count(distinct source_id) n from v_live_evidence where decision in ('accepted','confirmed') and observation_id not in ({ids}) group by 1,2)
      select a.variant_id, a.field_name, a.n, coalesce(b.n,0) from a left join b using(variant_id, field_name) where coalesce(b.n,0) < a.n""").fetchall()
d1, d2 = drop(bad), drop(bad | edn)
print("corroboration cells that drop: mislinks only", len(d1), "| incl. edition obs", len(d2), "| to zero (mislinks):", sum(1 for r in d1 if r[3] == 0))
# carwale payload/raw identity mismatch
cw = [r for r in links.values() if r["src"] == "carwale"]
print("carwale resolved obs:", len(cw), "payload name differs from raw name:", sum(1 for r in cw if r["payload_name"]),
      Counter(r["cls"] for r in cw if r["payload_name"]))
