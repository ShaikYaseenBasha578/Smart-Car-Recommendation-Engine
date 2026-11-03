"""Field-level catalogue diff vs main, checked against the expected 10H cells. Usage: catalogue_diff.py <main.csv> <new.csv> <expected_cells.tsv>"""
import csv, sys
from collections import Counter
EXPORT = {"mileage_arai_kmpl": "mileage_kmpl", "seating_capacity": "seats", "tyre_pressure_monitoring_system": "tpms",
          "boot_space_litres": "boot_space_litres"}
a = {r["variant_id"]: r for r in csv.DictReader(open(sys.argv[1]))}
b = {r["variant_id"]: r for r in csv.DictReader(open(sys.argv[2]))}
cols = list(next(iter(a.values())))
print("rows", len(a), len(b), "same ids", set(a) == set(b), "same columns", cols == list(next(iter(b.values()))))
exp = {(r["variant"], r["field"]) for r in csv.DictReader(open(sys.argv[3]), delimiter="\t")}
exp_cols = {(v, EXPORT.get(f, f)) for v, f in exp}
missing_map = {f for _, f in exp_cols if f not in cols}
print("expected cells", len(exp), "| export columns not found:", missing_map)
diff, cnt = set(), Counter()
for k in sorted(a, key=int):
    for col in cols:
        if a[k][col] != b[k][col]:
            cnt[col] += 1
            if col != "unverified_fields": diff.add((k, col))
            print(f"  v{k} {a[k]['model']} | {a[k]['variant'][:40]} | {col}: {a[k][col]!r} -> {b[k][col]!r}")
print(dict(cnt))
print("value diffs == expected cells:", diff == exp_cols, "| unexpected:", sorted(diff - exp_cols), "| expected but unchanged:", sorted(exp_cols - diff))
# unverified_fields must change exactly by the newly blank columns
bad = [k for k in a if set(b[k]["unverified_fields"].split(";")) - {""} != (set(a[k]["unverified_fields"].split(";")) - {""}) | {c for v, c in diff if v == k}]
print("unverified_fields consistent:", not bad, bad[:5])
