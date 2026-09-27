import sqlite3

prod_conn = sqlite3.connect("knowledge_base/carrec_kb.db")
prod_conn.row_factory = sqlite3.Row
shadow_conn = sqlite3.connect("scratch/isolated_shadow_kb.db")
shadow_conn.row_factory = sqlite3.Row

# 1. RECONCILE ALL 46 PROVENANCE ROWS
print("--- PROVENANCE RECONCILIATION ---")
# Get max ID from prod
prod_max = prod_conn.execute("SELECT MAX(id) FROM field_provenance").fetchone()[0]

new_prov = shadow_conn.execute("SELECT fp.*, v.name as vname, m.name as mname FROM field_provenance fp JOIN variant v ON fp.variant_id = v.id JOIN model m ON v.model_id = m.id WHERE fp.id > ?", (prod_max,)).fetchall()

accepted = 0
rejected = 0
confirmed = 0
other = 0

print("ID | Make Model Variant | Field | Value | Decision | Source Obs ID | Reason")
for p in new_prov:
    if p['decision'] == 'accepted': accepted += 1
    elif p['decision'] == 'rejected': rejected += 1
    elif p['decision'] == 'confirmed': confirmed += 1
    else: other += 1
    print(f"{p['id']} | {p['mname']} {p['vname']} | {p['field_name']} | {p['accepted_value']} | {p['decision']} | {p['source_observation_id']} | -")

print(f"\nTotal: {len(new_prov)} | Accepted: {accepted} | Rejected: {rejected} | Confirmed: {confirmed} | Other: {other}")

# 2. PROVE CANONICAL MUTATIONS
print("\n--- CANONICAL MUTATION DIFF ---")
prod_vars = {r['id']: dict(r) for r in prod_conn.execute("SELECT * FROM variant").fetchall()}
shad_vars = {r['id']: dict(r) for r in shadow_conn.execute("SELECT * FROM variant").fetchall()}

mutations = 0
for vid, s_var in shad_vars.items():
    if vid not in prod_vars:
        print(f"NEW VARIANT ADDED: {vid}")
        continue
    p_var = prod_vars[vid]
    
    diffs = {}
    for k, v in s_var.items():
        if k in ['updated_at']: continue
        if p_var[k] != v:
            diffs[k] = (p_var[k], v)
    if diffs:
        mutations += 1
        print(f"Variant {vid} MUTATED: {diffs}")

if mutations == 0:
    print("ZERO CANONICAL MUTATIONS DETECTED IN VARIANT TABLE.")

prod_pts = {r['id']: dict(r) for r in prod_conn.execute("SELECT * FROM powertrain").fetchall()}
shad_pts = {r['id']: dict(r) for r in shadow_conn.execute("SELECT * FROM powertrain").fetchall()}
pt_mutations = 0
for pid, s_pt in shad_pts.items():
    if pid not in prod_pts: continue
    p_pt = prod_pts[pid]
    diffs = {}
    for k, v in s_pt.items():
        if k in ['updated_at']: continue
        if p_pt[k] != v:
            diffs[k] = (p_pt[k], v)
    if diffs:
        pt_mutations += 1
        print(f"Powertrain {pid} MUTATED: {diffs}")
        
if pt_mutations == 0:
    print("ZERO CANONICAL MUTATIONS DETECTED IN POWERTRAIN TABLE.")
