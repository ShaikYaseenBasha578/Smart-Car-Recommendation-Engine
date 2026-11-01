"""Phase 10E verification (read-only on both inputs).

Usage: python3 verify_phase10e.py <after.db> <before.db> <out_dir> <label>
  after.db  : the corrected DB (dry-run copy, or a byte copy of prod after the apply)
  before.db : a byte copy of prod at SHA-1 8592508 (the pre-change state)
Writes <out_dir>/verify_<label>.md and prints PASS/FAIL per check. Exit code 1 if any check fails.
The unique-index enforcement test runs on a throwaway copy of after.db (never on the input itself).
"""
import os
import shutil
import sqlite3
import sys
import tempfile

after_db, before_db, out_dir, label = sys.argv[1:5]
A = sqlite3.connect(f"file:{after_db}?mode=ro", uri=True)
A.execute("ATTACH DATABASE ? AS b", (f"file:{before_db}?mode=ro",))
L, fails = [], []


def check(name, ok, detail=""):
    L.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")
    if not ok:
        fails.append(name)


q = lambda sql, *p: A.execute(sql, p).fetchall()
one = lambda sql, *p: A.execute(sql, p).fetchone()

L.append(f"# Phase 10E verification: {label}\n\n| Check | Result | Detail |\n|---|---|---|")
check("integrity_check", one("pragma integrity_check")[0] == "ok", one("pragma integrity_check")[0])
fk = q("pragma main.foreign_key_check")
fk_ok = len(fk) == 297 and all(r[0] == "field_provenance" and r[2] == "source_observation" for r in fk)
check("foreign_key_check = 297 known orphans", fk_ok, f"{len(fk)} rows")
ux = one("select sql from main.sqlite_master where name='ux_quarantine_active'")
ux_same = ux and ux[0] == one("select sql from b.sqlite_master where name='ux_quarantine_active'")[0]
# enforcement on a throwaway copy
tmp = tempfile.mkdtemp()
shutil.copy(after_db, os.path.join(tmp, "t.db"))
t = sqlite3.connect(os.path.join(tmp, "t.db"), isolation_level=None)
r = t.execute("select target_table,target_id,target_field,reason_code from evidence_quarantine where released_at is null limit 1").fetchone()
try:
    t.execute("insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase) values (?,?,?,?,'TEST')", r)
    enforced = False
except sqlite3.IntegrityError as e:
    enforced = "ux_quarantine_active" in str(e)
t.close()
shutil.rmtree(tmp)
check("ux_quarantine_active exists, identical SQL, enforced", bool(ux_same) and enforced, f"duplicate insert rejected on a throwaway copy: {enforced}")
nv = one("select count(*) from main.variant")[0]
check("variant count = 832", nv == 832, str(nv))
act_b = one("select count(*) from b.evidence_quarantine where released_at is null")[0]
act_a = one("select count(*) from main.evidence_quarantine where released_at is null")[0]
new_q = q("select id,target_table,target_id,target_field,reason_code from main.evidence_quarantine where id not in (select id from b.evidence_quarantine) order by id")
check("active quarantine = 698 + inserts = 720", act_b == 698 and act_a == 698 + len(new_q) == 720, f"before {act_b}, after {act_a}, inserts {len(new_q)}")
cng = "select q.id from main.v_variant_canonical_q q join main.powertrain p on p.id=q.powertrain_id where p.fuel_type='CNG' and "
ia = q(cng + "q.mileage_arai_kmpl = q.mileage_arai_km_per_kg")
ib = q(cng + "q.mileage_arai_kmpl > 25")
check("CNG (a) kmpl = km/kg -> 0", not ia, str(ia))
check("CNG (b) kmpl > 25 -> 0", not ib, str(ib))
pad = sorted(r[0] for r in q("select id from main.v_variant_canonical_q where transmission in ('Manual','iMT') and paddle_shifters=1"))
check("manual/iMT + paddle=1 = {599 Jimny, 605 Kushaq, 824 Jimny edition}", pad == [599, 605, 824], str(pad))
pw = one("select power_bhp from main.powertrain where id=68")[0]
prov = q("select fp.variant_id, fp.accepted_value, so.raw_payload from main.field_provenance fp join main.source_observation so on so.id=fp.source_observation_id where fp.field_name='power_bhp'")
desc = one("select description from main.powertrain where id=68")[0]
desc_b = one("select description from b.powertrain where id=68")[0]
L.append(f"| powertrain 68 description | INFO | before {desc_b!r} -> after {desc!r} |")
check("powertrain 68 description: only the figure 89.7 -> 88.51 changed", desc_b.replace("89.7", "88.51") == desc and desc_b == "1197cc 89.7bhp Petrol", f"{desc_b!r} -> {desc!r}")
rb = q("select variant_id, accepted_value from main.field_provenance where field_name='base_variant_id' order by variant_id")
check("rebase provenance rows (814 -> 652, 826 -> 220)", rb == [(814, "652"), (826, "220")], str(rb))
check("Glanza petrol power_bhp = 88.51 with provenance", pw == 88.51 and len(prov) == 7 and all(p[1] == "88.51" for p in prov),
      f"power_bhp {pw}; {len(prov)} power provenance rows (variants {sorted(p[0] for p in prov)})")
wcols = "id,manufacturer_id,model_id,warranty_years,warranty_km,battery_warranty_years,battery_warranty_km,extended_warranty_available,source,source_url"
gv = one("select warranty_years,warranty_km,battery_warranty_years,battery_warranty_km,extended_warranty_available from main.v_warranty_q where id=12")
gv_raw = one("select battery_warranty_years,battery_warranty_km,extended_warranty_available from main.warranty where id=12")
others = one(f"select count(*) from (select {wcols} from main.warranty where id<>12 except select {wcols} from main.v_warranty_q)")[0]
others2 = one(f"select count(*) from (select {wcols} from main.v_warranty_q where id<>12 except select {wcols} from b.warranty)")[0]
nrows = one("select count(*) from main.v_warranty_q")[0]
hp = q("select has_provenance, count(*) from main.v_warranty_q group by 1")
wt_same = one(f"select count(*) from (select * from main.warranty except select * from b.warranty)")[0] + one(f"select count(*) from (select * from b.warranty except select * from main.warranty)")[0]
check("v_warranty_q: GV row 12 years/km blanked, battery+extended visible, other 17 unchanged, warranty table untouched",
      gv == (None, None) + gv_raw and gv_raw[0] is not None and others == 0 and others2 == 0 and nrows == 18 and wt_same == 0,
      f"row12 values {gv}; others diff {others}/{others2}; rows {nrows}; warranty table diff {wt_same}; has_provenance {hp}")
cols_a = [d[0] for d in A.execute("select * from main.v_variant_canonical_q limit 0").description]
cols_b = [d[0] for d in A.execute("select * from b.v_variant_canonical_q limit 0").description]
check("v_variant_canonical_q has no adas_tier; other columns identical in order", "adas_tier" not in cols_a and cols_a == [c for c in cols_b if c != "adas_tier"], f"{len(cols_b)} -> {len(cols_a)} columns")
ca = {r[0]: r for r in A.execute("select * from main.v_variant_canonical_q")}
cb_rows = {r[0]: r for r in A.execute(f"select {','.join(cols_a)} from b.v_variant_canonical_q")}
canon_diff = sorted((k, c, cb_rows[k][j], ca[k][j]) for k in ca for j, c in enumerate(cols_a) if ca[k][j] != cb_rows[k][j])
approved = ({(v, "mileage_arai_kmpl") for v in (245, 213, 591, 556, 217, 345)} | {(v, "mileage_arai_km_per_kg") for v in (245, 213, 556, 217)}
            | {(v, "paddle_shifters") for v in (5, 15, 16, 21, 23, 158, 561, 566, 627, 216, 217, 218, 220)})
unexpected = [d for d in canon_diff if (d[0], d[1]) not in approved and d[0] not in (814, 826)]
check("v_variant_canonical_q: changes only on approved cells + rebased editions 814/826", not unexpected, f"{len(canon_diff)} cells changed; unexpected {unexpected}")
sch_a = {r[0]: r[1] for r in q("select name, sql from main.sqlite_master where name not like 'sqlite_%'")}
sch_b = {r[0]: r[1] for r in q("select name, sql from b.sqlite_master where name not like 'sqlite_%'")}
sch_changed = sorted(n for n in set(sch_a) | set(sch_b) if sch_a.get(n) != sch_b.get(n))
eq_a, eq_b = sch_a["evidence_quarantine"], sch_b["evidence_quarantine"]
check_only = (eq_b.replace("'safety_test','safety_test_applicability'))", "'safety_test','safety_test_applicability','warranty'))")
                  .replace("CHECK (target_table <> 'variant' OR target_field IS NOT NULL)", "CHECK (target_table NOT IN ('variant','warranty') OR target_field IS NOT NULL)")) == eq_a
check("schema diff = evidence_quarantine CHECK + v_warranty_q + v_variant_canonical_q only", sch_changed == ["evidence_quarantine", "v_variant_canonical_q", "v_warranty_q"] and check_only,
      f"changed objects {sch_changed}; evidence_quarantine differs only in the CHECK clauses: {check_only}")

# ---------------- detail sections
L.append("\n## New quarantine rows\n\n| id | target_table | target_id | target_field | reason |\n|---|---|---|---|---|")
L += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |" for r in new_q]
L.append("\n## Cell-level diff vs prod (before)\n")
for t in [r[0] for r in q("select name from main.sqlite_master where type='table' order by name")]:
    plus = one(f'select count(*) from (select * from main."{t}" except select * from b."{t}")')[0]
    minus = one(f'select count(*) from (select * from b."{t}" except select * from main."{t}")')[0]
    L.append(f"- `{t}`: +{plus} / -{minus}")
for t in ("variant", "powertrain"):
    cols = [d[0] for d in A.execute(f"select * from main.{t} limit 0").description]
    a = {r[0]: r for r in A.execute(f"select * from main.{t}")}
    b = {r[0]: r for r in A.execute(f"select * from b.{t}")}
    d = sorted((k, cols[j], b[k][j], a[k][j]) for k in a for j in range(len(cols)) if a[k][j] != b[k][j] or type(a[k][j]) is not type(b[k][j]))
    L.append(f"\n**{t}: {len(d)} cells**\n\n| id | column | before | after |\n|---|---|---|---|")
    L += [f"| {x[0]} | {x[1]} | {x[2]!r} | {x[3]!r} |" for x in d]
L.append("\n**sqlite_sequence**\n")
L += [f"- {r[0]}: {r[1]} -> {r[2]}" for r in q("select a.name, b.seq, a.seq from main.sqlite_sequence a join b.sqlite_sequence b on a.name=b.name where a.seq<>b.seq")]
L.append("\n**evidence_amendment (new rows)**\n\n| id | table | target | column | old | new | reason |\n|---|---|---|---|---|---|---|")
L += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |" for r in q("select id,target_table,target_id,column_name,old_value,new_value,reason_code from main.evidence_amendment where id not in (select id from b.evidence_amendment) order by id")]
L.append("\n**field_provenance / source_observation (new rows)**\n\n| fp id | variant | field | value | obs id | pdf page |\n|---|---|---|---|---|---|")
import json
for r in q("select fp.id, fp.variant_id, fp.field_name, fp.accepted_value, so.id, so.raw_payload from main.field_provenance fp join main.source_observation so on so.id=fp.source_observation_id where fp.id not in (select id from b.field_provenance) order by fp.id"):
    p = json.loads(r[5])
    L.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {p['pdf_path'].split('/')[-1]} p{p['page']} ({p['pdf_sha1'][:8]}) |")
nofp = q("select so.id, so.resolved_variant_id, so.raw_payload from main.source_observation so where so.id not in (select id from b.source_observation) and not exists (select 1 from main.field_provenance fp where fp.source_observation_id=so.id)")
L += [f"| - | {r[1]} | (rebase evidence, no fp) | {json.loads(r[2])['fields']} | {r[0]} | {json.loads(r[2])['pdf_path'].split('/')[-1]} p{json.loads(r[2])['page']} |" for r in nofp]
L.append("\n## v_variant_canonical_q cell changes (all)\n\n| id | column | before | after |\n|---|---|---|---|")
L += [f"| {x[0]} | {x[1]} | {x[2]!r} | {x[3]!r} |" for x in canon_diff]
L.append("\n## Rebased editions: every inherited cell (own raw value NULL)\n")
vcols = [d[0] for d in A.execute("select * from main.variant limit 0").description]
for ed, ob, nb in ((814, 649, 652), (826, 218, 220)):
    own = dict(zip(vcols, one("select * from main.variant where id=?", ed)))
    ob_row = dict(zip(cols_a, one(f"select {','.join(cols_a)} from b.v_variant_canonical_q where id=?", ed)))
    nb_row = dict(zip(cols_a, one("select * from main.v_variant_canonical_q where id=?", ed)))
    inh = [c for c in cols_a if c in own and own[c] is None and c not in ("id", "base_variant_id")]
    L.append(f"\n**{ed}: base {ob} -> {nb}** ({len(inh)} inherited cells; {sum(ob_row[c] != nb_row[c] for c in inh)} change)\n\n| field | old value (old base {ob}) | new value (new base {nb}) | changed |\n|---|---|---|---|")
    L += [f"| {c} | {ob_row[c]!r} | {nb_row[c]!r} | {'Y' if ob_row[c] != nb_row[c] else ''} |" for c in inh]
L.append("\n## Schema objects changed\n")
for n in sch_changed:
    L.append(f"### {n}\nbefore:\n```sql\n{sch_b.get(n)}\n```\nafter:\n```sql\n{sch_a.get(n)}\n```")
open(os.path.join(out_dir, f"verify_{label}.md"), "w").write("\n".join(L) + "\n")
print("\n".join(l for l in L[:22]))
print("FAILED:" if fails else "ALL CHECKS PASS", fails if fails else "")
sys.exit(1 if fails else 0)
