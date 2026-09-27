import json

with open("scratch/phase6_swift_dry_run_results.json") as f:
    results = json.load(f)
with open("scratch/phase6_swift_dry_run_prov.json") as f:
    prov = json.load(f)

print("### Resolution Mapping")
for r in results:
    print(f"- **{r['raw_name']}** -> Resolved to: **{r['canon_name']}** (Status: {r['resolution_status']})")

print("\n### Field Decisions")
for p in prov:
    # Just show a few for brevity
    if p['decision'] != 'confirmed':
        print(f"- {p['variant']} | {p['field_name']} | {p['accepted_value']} | {p['decision']} ({p['decision_reason']})")
