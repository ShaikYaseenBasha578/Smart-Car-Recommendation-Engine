"""W7 measurement (read-only): how many v_corroboration cells count evidence whose value disagrees with the canonical value.

v_corroboration counts DISTINCT source_id over live accepted/confirmed field_provenance rows per (variant, field),
without comparing accepted_value to the canonical value. For each v_corroboration row this script compares every
counted source's values with v_variant_canonical_q (the read path) and classifies the cell:
  NO_CANONICAL  canonical value is NULL (empty or masked by quarantine), so there is nothing to agree with
  ALL_AGREE     every counted source has at least one value equal to canonical
  MIXED         >=1 counted source agrees and >=1 has no value equal to canonical  (count overstated)
  ALL_DISAGREE  no counted source has a value equal to canonical                   (count entirely spurious)
Also counts cells where a V3Cars zero is counted (W2 rule: V3Cars zeros are "not found", never corroboration).
Equality after normalisation: True/False -> 1/0; No/Yes/Yes[n] -> 0/1 (drive_modes; off with --strict); numbers compared as floats (abs diff <= 1e-9); other text trimmed and
case-folded. Format-only mismatches (e.g. 'FWD' vs 'Front Wheel Drive') count as disagreement, so the per-field table
is reported for review. Usage: python3 measure_w7_corroboration_value_blind.py <db_copy> [out.csv] [--strict]
"""
import csv
import sqlite3
import sys
from collections import Counter, defaultdict

V3CARS = 3


STRICT = "--strict" in sys.argv


def norm(v):
    if v is None:
        return None
    s = str(v).strip()
    low = s.lower()
    if low in ("true", "false"):
        return 1.0 if low == "true" else 0.0
    if not STRICT and (low == "no" or low == "yes" or low.startswith("yes[")):
        return 0.0 if low == "no" else 1.0  # drive_modes evidence: 'No' / 'Yes[n]'; canonical is 0/1
    try:
        return float(s)
    except ValueError:
        return low


def eq(a, b):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))
    return a == b


def main():
    db = [a for a in sys.argv[1:] if a != "--strict"][0]
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    qcols = [d[0] for d in c.execute("select * from v_variant_canonical_q limit 0").description]
    canon = {r[0]: dict(zip(qcols, r)) for r in c.execute("select * from v_variant_canonical_q")}
    ev = defaultdict(lambda: defaultdict(list))  # (variant, field) -> source -> [values]
    for vid, field, sid, val in c.execute("""select e.variant_id, e.field_name, e.source_id, e.accepted_value
            from v_live_evidence e where e.decision in ('accepted','confirmed')
            and not exists (select 1 from v_active_quarantine q where q.target_table='variant'
                            and q.target_id=e.variant_id and q.target_field in (e.field_name,'*'))"""):
        ev[(vid, field)][sid].append(val)
    rows = c.execute("select variant_id, field_name, corroborating_sources from v_corroboration").fetchall()
    per_field = defaultdict(Counter)
    total = Counter()
    v3_zero = v3_zero_only = 0
    overcount = 0
    unknown_field = set()
    detail = []
    for vid, field, n in rows:
        srcs = ev[(vid, field)]
        assert len(srcs) == n, f"({vid},{field}): recomputed {len(srcs)} != view {n}"
        if any(sid == V3CARS and any(norm(v) == 0.0 for v in vals) for sid, vals in srcs.items()):
            v3_zero += 1
            if len(srcs) == 1:
                v3_zero_only += 1
        if field not in qcols:
            unknown_field.add(field)
            cls = "NO_CANONICAL"
        else:
            cv = norm(canon[vid][field])
            if cv is None:
                cls = "NO_CANONICAL"
            else:
                agree = {sid for sid, vals in srcs.items() if any(eq(norm(v), cv) for v in vals)}
                dis = set(srcs) - agree
                overcount += len(dis)
                cls = "ALL_AGREE" if not dis else ("ALL_DISAGREE" if not agree else "MIXED")
                if dis:
                    detail.append((vid, field, canon[vid][field], n, len(agree),
                                   ";".join(f"{s}:{'|'.join(map(str, srcs[s]))}" for s in sorted(dis))))
        per_field[field][cls] += 1
        total[cls] += 1
    affected = total["MIXED"] + total["ALL_DISAGREE"]
    print(f"db={db}")
    print(f"v_corroboration cells: {len(rows)}")
    for k in ("ALL_AGREE", "MIXED", "ALL_DISAGREE", "NO_CANONICAL"):
        print(f"  {k}: {total[k]}")
    print(f"AFFECTED (MIXED + ALL_DISAGREE): {affected}  ({affected / len(rows):.1%} of cells)")
    print(f"disagreeing source-counts included in corroboration: {overcount}")
    print(f"cells counting a V3Cars zero (W2 rule): {v3_zero}; of which V3Cars is the only counted source: {v3_zero_only}")
    if unknown_field:
        print(f"fields not in v_variant_canonical_q: {sorted(unknown_field)}")
    print("per field: field | ALL_AGREE | MIXED | ALL_DISAGREE | NO_CANONICAL")
    for f in sorted(per_field, key=lambda f: -(per_field[f]["MIXED"] + per_field[f]["ALL_DISAGREE"])):
        p = per_field[f]
        print(f"  {f} | {p['ALL_AGREE']} | {p['MIXED']} | {p['ALL_DISAGREE']} | {p['NO_CANONICAL']}")
    args = [a for a in sys.argv[1:] if a != "--strict"]
    if len(args) > 1:
        with open(args[1], "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["variant_id", "field", "canonical_value", "corroborating_sources", "agreeing_sources",
                        "disagreeing_source:values"])
            w.writerows(sorted(detail))


if __name__ == "__main__":
    main()
