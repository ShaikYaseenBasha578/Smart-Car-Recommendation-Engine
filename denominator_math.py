import json

with open('knowledge_base/carwale_batch_state.json') as f:
    state = json.load(f)

tot_disc = 0
tot_res = 0
tot_unres = 0

for res in state['results'].values():
    if isinstance(res, dict):
        tot_disc += res['discovered']
        tot_res += res['resolved']
        tot_unres += res['unresolved']

print(f"State Discovered (Slugs on Pages): {tot_disc}")
print(f"State Resolved: {tot_res}")
print(f"State Unresolved: {tot_unres}")
print(f"Difference (Aborted/Failed Extractions): {tot_disc - tot_res - tot_unres}")

