"""Phase 10F verification (read-only on both inputs).

Usage: python3 verify_phase10f.py <after.db> <before.db> <out_dir> <label>
  after.db  : the corrected DB (dry-run copy, or a byte copy of prod after the apply)
  before.db : a byte copy of prod at SHA-1 57f31e4d (the pre-change state)
Writes <out_dir>/verify_<label>.md and prints PASS/FAIL per check. Exit code 1 if any check fails.
The Pass A power scan is re-run on a throwaway copy of after.db (never on the input itself).
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

after_db, before_db, out_dir, label = sys.argv[1:5]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from apply_phase10f import KMKG_UPDATES, POWERTRAINS, target_hp  # noqa: E402

SCAN = os.path.expanduser("~/carrec_kb_scratch/corrections_passA/scripts/power_scan.py")
PDF_TEXT = os.path.expanduser("~/carrec_kb_scratch/corrections_passA/pdf_text")
OEM = os.path.expanduser("~/Car_recommender_app/Flask Based App with Used Cars Function/knowledge_base/sources/oem")
HELD_PT = {84: "Grand Vitara CNG: brochure has no CNG data", 88: "Victoris hybrid: brochure prints no total-system power"}
# CNG km/kg printed in each model's own brochure (10E- or 10F-verified, rendered); models absent here have no figure
BROCHURE_KMKG = {"Alto K10": 33.4, "Eeco": 26.78, "Ertiga": 26.11, "Fronx": 28.51, "Glanza": 30.61, "Rumion": 26.11,
                 "S-Presso": 32.73, "Swift": 32.85, "Urban Cruiser Hyryder": 26.6, "Urban Cruiser Taisor": 28.51,
                 "Victoris": 27.02, "WagonR": 33.47, "XL6": 26.23}
# owner-approved exemptions from the own-brochure check (10F checkpoint)
KMKG_EXEMPT = {225: "CATALOG_CURRENCY: KB WagonR 1.0 rows predate the brochure (64.37 bhp = 48 kW vs 50.4 kW printed); "
                    "33.54 vs 33.47 held, to be handled with Baleno"}

A = sqlite3.connect(f"file:{after_db}?mode=ro", uri=True)
A.execute("ATTACH DATABASE ? AS b", (f"file:{before_db}?mode=ro",))
L, fails = [], []


def check(name, ok, detail=""):
    L.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")
    if not ok:
        fails.append(name)


q = lambda sql, *p: A.execute(sql, p).fetchall()
one = lambda sql, *p: A.execute(sql, p).fetchone()

L.append(f"# Phase 10F verification: {label}\n\n| Check | Result | Detail |\n|---|---|---|")
ic = one("pragma integrity_check")[0]
check("integrity_check", ic == "ok", ic)
fk = q("pragma main.foreign_key_check")
check("foreign_key_check = 297 known orphans", len(fk) == 297 and all(r[0] == "field_provenance" and r[2] == "source_observation" for r in fk), f"{len(fk)} rows")
nv = one("select count(*) from main.variant")[0]
check("variant count = 832", nv == 832, str(nv))
act_b = one("select count(*) from b.evidence_quarantine where released_at is null")[0]
act_a = one("select count(*) from main.evidence_quarantine where released_at is null")[0]
new_q = q("select id,target_table,target_id,target_field,reason_code from main.evidence_quarantine where id not in (select id from b.evidence_quarantine) order by id")
exp_new = len(KMKG_UPDATES)
check(f"active quarantine = 720 + {exp_new} inserts = 722", act_b == 720 and act_a == 720 + len(new_q) == 722 and len(new_q) == exp_new,
      f"before {act_b}, after {act_a}, inserts {len(new_q)}")

# A: power
bad, prov_bad = [], []
for pt, mid, fuel, cc, old, kw, ps, bro, page, printed, users, eds in POWERTRAINS:
    exp = target_hp(kw, ps)
    got, d = one("select power_bhp, description from main.powertrain where id=?", pt)
    d_b = one("select description from b.powertrain where id=?", pt)[0]
    if got != exp or d != d_b.replace(f" {old}bhp ", f" {exp}bhp ") or d == d_b:
        bad.append((pt, got, exp, d_b, d))
    fp = q("select fp.variant_id, fp.accepted_value, so.raw_payload from main.field_provenance fp join main.source_observation so on so.id=fp.source_observation_id "
           "where fp.field_name='power_bhp' and fp.variant_id in (%s)" % ",".join(map(str, users)))
    ok = sorted(r[0] for r in fp) == sorted(users) and all(r[1] == str(exp) and json.loads(r[2])["page"] == page for r in fp)
    if not ok:
        prov_bad.append(pt)
check("A: every corrected power_bhp = brochure kW x 1.34102 (PS x 0.98632 for Duster), 2 dp; description: only the figure changed",
      not bad, f"{len(POWERTRAINS)} powertrains; mismatches {bad}")
check("A: one power_bhp provenance row per base variant, value and page as cited", not prov_bad, f"failing powertrains {prov_bad}")
pt_diff = q("select a.id from main.powertrain a join b.powertrain b on a.id=b.id where a.power_bhp is not b.power_bhp or a.description is not b.description "
            "or a.model_id<>b.model_id or a.fuel_type<>b.fuel_type or a.engine_cc is not b.engine_cc or a.torque_nm is not b.torque_nm")
check("A: powertrain rows changed = exactly the 16 in scope", sorted(r[0] for r in pt_diff) == sorted(p[0] for p in POWERTRAINS), str(sorted(r[0] for r in pt_diff)))
tmp = tempfile.mkdtemp()
shutil.copy(after_db, os.path.join(tmp, "s.db"))
scan = subprocess.run([sys.executable, "-I", SCAN, os.path.join(tmp, "s.db"), OEM, PDF_TEXT], capture_output=True, text=True).stdout
shutil.rmtree(tmp)
open(os.path.join(out_dir, f"power_scan_{label}.txt"), "w").write(scan)
sec_a, sec_b = scan.split("## (b)")
b_hits = [l for l in sec_b.splitlines() if l.startswith("pt=")]
groups, cur = [], None
for line in sec_a.splitlines():
    if line and not line.startswith(" ") and not line.startswith("#"):
        cur = {"head": line, "pts": []}
        groups.append(cur)
    elif line.strip().startswith("pt=") and cur:
        f = line.split()
        cur["pts"].append((int(f[0][3:]), float([x for x in f if x.startswith("power_bhp=")][0].split("=")[1])))
ps_groups = [g for g in groups if "~PS/hp" in g["head"]]
outliers = {p for g in ps_groups for p, v in g["pts"] if v == max(x[1] for x in g["pts"])}
check("A: PS-as-bhp scan re-run: (b) empty; PS-ratio groups' high members only held items", not b_hits and outliers <= set(HELD_PT),
      f"(b) hits {len(b_hits)}; PS-ratio high members {sorted(outliers)} (held: {HELD_PT}); other groups: {[g['head'].split('  ')[0] for g in groups if g not in ps_groups]}")

# B + C
for vid, col, old, new, *_ in KMKG_UPDATES:
    v = one(f"select {col} from main.v_variant_canonical_q where id=?", vid)[0]
    pr = q("select fp.accepted_value from main.field_provenance fp where fp.variant_id=? and fp.field_name=? and fp.decision_reason='OEM_BROCHURE_VERIFIED_10F'", vid, col)
    check(f"B/C: {vid} {col} = {new} with provenance", v == new and pr == [(str(new),)], f"value {v}; 10F provenance {pr}")
contra, no_bro, exempt = [], [], []
for vid, model, kg in q("select q.id, m.name, q.mileage_arai_km_per_kg from main.v_variant_canonical_q q join main.variant v on v.id=q.id join main.model m on m.id=v.model_id "
                        "join main.powertrain p on p.id=q.powertrain_id where p.fuel_type='CNG' and q.mileage_arai_km_per_kg is not null"):
    if model in BROCHURE_KMKG:
        if kg != BROCHURE_KMKG[model]:
            (exempt if vid in KMKG_EXEMPT else contra).append((vid, model, kg, BROCHURE_KMKG[model]))
    else:
        no_bro.append((vid, model, kg))
check("C: no CNG variant's km/kg contradicts its own brochure (owner exemptions listed)", not contra and [e[0] for e in exempt] == sorted(KMKG_EXEMPT),
      f"contradictions {contra}; exempt {exempt}: {KMKG_EXEMPT}")
L.append(f"| C: CNG km/kg with no own-brochure figure (NEEDS_HUMAN) | INFO | {no_bro} |")

# canonical + schema
cols = [d[0] for d in A.execute("select * from main.v_variant_canonical_q limit 0").description]
ca = {r[0]: r for r in A.execute("select * from main.v_variant_canonical_q")}
cb = {r[0]: r for r in A.execute(f"select {','.join(cols)} from b.v_variant_canonical_q")}
canon_diff = sorted((k, c, cb[k][j], ca[k][j]) for k in ca for j, c in enumerate(cols) if ca[k][j] != cb[k][j])
approved = {(v, c) for v, c, *_ in KMKG_UPDATES}
unexpected = [d for d in canon_diff if (d[0], d[1]) not in approved]
check("v_variant_canonical_q: only approved cells changed", not unexpected and len(canon_diff) == len(approved), f"{len(canon_diff)} cells changed; unexpected {unexpected}")
sch_a = q("select type, name, tbl_name, sql from main.sqlite_master where name not like 'sqlite_%' order by name")
sch_b = q("select type, name, tbl_name, sql from b.sqlite_master where name not like 'sqlite_%' order by name")
check("schema identical to before", sch_a == sch_b, f"{len(sch_a)} objects")

# ---------------- detail sections
L.append("\n## New quarantine rows\n\n| id | target_table | target_id | target_field | reason |\n|---|---|---|---|---|")
L += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |" for r in new_q]
L.append("\n## Cell-level diff vs prod (before)\n")
for t in [r[0] for r in q("select name from main.sqlite_master where type='table' order by name")]:
    plus = one(f'select count(*) from (select * from main."{t}" except select * from b."{t}")')[0]
    minus = one(f'select count(*) from (select * from b."{t}" except select * from main."{t}")')[0]
    L.append(f"- `{t}`: +{plus} / -{minus}")
for t in ("variant", "powertrain"):
    tc = [d[0] for d in A.execute(f"select * from main.{t} limit 0").description]
    a = {r[0]: r for r in A.execute(f"select * from main.{t}")}
    b = {r[0]: r for r in A.execute(f"select * from b.{t}")}
    d = sorted((k, tc[j], b[k][j], a[k][j]) for k in a for j in range(len(tc)) if a[k][j] != b[k][j] or type(a[k][j]) is not type(b[k][j]))
    L.append(f"\n**{t}: {len(d)} cells**\n\n| id | column | before | after |\n|---|---|---|---|")
    L += [f"| {x[0]} | {x[1]} | {x[2]!r} | {x[3]!r} |" for x in d]
L.append("\n**sqlite_sequence**\n")
L += [f"- {r[0]}: {r[1]} -> {r[2]}" for r in q("select a.name, b.seq, a.seq from main.sqlite_sequence a join b.sqlite_sequence b on a.name=b.name where a.seq<>b.seq")]
L.append("\n**evidence_amendment (new rows)**\n\n| id | table | target | column | old | new | reason |\n|---|---|---|---|---|---|---|")
L += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |" for r in q("select id,target_table,target_id,column_name,old_value,new_value,reason_code from main.evidence_amendment where id not in (select id from b.evidence_amendment) order by id")]
L.append("\n**field_provenance / source_observation (new rows)**\n\n| fp id | variant | field | value | obs id | pdf page |\n|---|---|---|---|---|---|")
for r in q("select fp.id, fp.variant_id, fp.field_name, fp.accepted_value, so.id, so.raw_payload from main.field_provenance fp join main.source_observation so on so.id=fp.source_observation_id where fp.id not in (select id from b.field_provenance) order by fp.id"):
    p = json.loads(r[5])
    L.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {p['pdf_path'].split('/')[-1]} p{p['page']} ({p['pdf_sha1'][:8]}) |")
L.append("\n## v_variant_canonical_q cell changes (all)\n\n| id | column | before | after |\n|---|---|---|---|")
L += [f"| {x[0]} | {x[1]} | {x[2]!r} | {x[3]!r} |" for x in canon_diff]
open(os.path.join(out_dir, f"verify_{label}.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:20]))
print("FAILED:" if fails else "ALL CHECKS PASS", fails if fails else "")
sys.exit(1 if fails else 0)
