"""Report for a brochure run (reads only files in the run folder; opens before.db and staging.db read-only from copies;
never opens the production database).

  python -m kbpipe.tools.brochure_report <run_dir> --models "Hyundai/i20" "Tata/Punch" ...   (default: models with a brochure summary)

Writes <run_dir>/BROCHURE_REPORT.md, brochure_cells.tsv (every extracted cell with the checker's verdict), brochure_disagreements.tsv
(brochure versus the KB value, and brochure versus each aggregator, per cell) and prints the report."""
import argparse
import csv
import glob
import json
import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from kbpipe import brochure as B  # noqa: E402
from kbpipe import fields as F  # noqa: E402

CALLOUT = [("ABS", ["abs"]), ("ESC", ["esc"]), ("ADAS", ["adas_available"]), ("airbags", ["airbags"]),
           ("dimensions", ["length_mm", "width_mm", "height_mm", "wheelbase_mm", "ground_clearance_mm", "kerb_weight_kg"]),
           ("HUD", ["heads_up_display"])]


def opendb(path):
    d = tempfile.mkdtemp(prefix="brep_")
    p = os.path.join(d, "x.db")
    shutil.copyfile(path, p)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    return c


def blank_cells(conn, model):
    """{(variant_id, field)} blank and applicable, for the base (non-edition) variants of make/model."""
    make, name = model.split("/", 1)
    rows = conn.execute("select v.*, p.fuel_type f, p.engine_cc, p.power_bhp, p.torque_nm from variant v join model m on m.id=v.model_id "
                        "join manufacturer k on k.id=m.manufacturer_id left join powertrain p on p.id=v.powertrain_id "
                        "where k.name=? and m.name=? and v.base_variant_id is null", (make, name)).fetchall()
    out, total = set(), 0
    for r in rows:
        for f in B.BROCHURE_FIELDS:
            if not B.applicable(f, r["f"]):
                continue
            total += 1
            if r[f] is None:
                out.add((r["id"], f))
    return out, total, len(rows)


def tsv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--models", nargs="*")
    a = ap.parse_args()
    rd = a.run_dir
    sums = {}
    for p in glob.glob(os.path.join(rd, "brochure", "*_*.json")):
        d = json.load(open(p))
        if "cells" in d:
            sums["%s/%s" % (d["make"], d["model"])] = d
    models = a.models or sorted(sums)
    before = opendb(os.path.join(rd, "before.db"))
    after = opendb(os.path.join(rd, "staging.db")) if os.path.exists(os.path.join(rd, "staging.db")) else None
    cs = json.load(open(os.path.join(rd, "changeset.json")))
    obs = cs["observations"]
    # brochure fills in the change-set: cell ops whose accepted evidence is an OEM observation
    fills, corr = {}, {}
    for op in cs["ops"]:
        if op["op"] != "cell":
            continue
        ev = next((e for e in op["evidence"] if e["decision"] == "accepted"), None)
        if ev and obs.get(ev["obs"], {}).get("source") == "oem":
            (fills if op.get("expect_old") is None else corr).setdefault("%s/%s" % (op["make"], op["model"]), []).append(op)
    conflicts = [c for c in tsv(os.path.join(rd, "conflicts.tsv"))]
    lines = ["# Brochure report: %s" % os.path.basename(rd), ""]
    cells_out = []
    G = {}                                   # group -> [supported, checked]
    tot = {"blank_before": 0, "tracked": 0, "fill": 0, "blank_after": 0, "cells": 0, "sup": 0}
    call_tot = {k: [0, 0] for k, _ in CALLOUT}
    lines += ["| Model | Brochure | Variants | Tracked cells | Blank before | Brochure cells (unique) | Supported | Filled by brochure (staged) | Blank after (staging) | ABS | ESC | ADAS | Airbags | Dimensions | HUD |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        s = sums.get(m)
        bl, total, nv = blank_cells(before, m)
        al = blank_cells(after, m)[0] if after else bl
        cs_m = fills.get(m, [])
        ucells = {}
        for c in (s["cells"] if s else []):
            ucells[(c["variant"], c["field"])] = c
            cells_out.append(dict(c, model=m))
        sup = sum(1 for c in ucells.values() if c["verdict"] == "supported")
        for c in ucells.values():
            g = G.setdefault(c["group"], [0, 0])
            if c["verdict"] != "unchecked":
                g[1] += 1
                g[0] += c["verdict"] == "supported"
        cal = []
        for name, fl in CALLOUT:
            before_n = sum(1 for (v, f) in bl if f in fl)
            filled_n = sum(1 for (v, f) in bl if f in fl and (v, f) not in al)
            cal.append("%d/%d" % (filled_n, before_n))
            call_tot[name][0] += filled_n
            call_tot[name][1] += before_n
        status = (s or {}).get("status") or "no brochure"
        lines.append("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %s |" % (
            m, status, nv, total, len(bl), len(ucells), sup, len(cs_m), len(al), " | ".join(cal)))
        tot["blank_before"] += len(bl)
        tot["tracked"] += total
        tot["fill"] += len(cs_m)
        tot["blank_after"] += len(al)
        tot["cells"] += len(ucells)
        tot["sup"] += sup
    lines += ["", "Callout columns show cells filled / blank before, from the staged copy (all sources, not only the brochure).", "",
              "TOTAL: tracked %d, blank before %d, brochure cells %d (supported %d), filled by brochure in the change-set %d, blank after %d"
              % (tot["tracked"], tot["blank_before"], tot["cells"], tot["sup"], tot["fill"], tot["blank_after"]), ""]
    lines += ["Callouts, all models: " + "; ".join("%s %d of %d blank filled" % (k, v[0], v[1]) for k, v in call_tot.items()), ""]
    lines += ["## Checker verdicts per field group (unique cells)", "", "| Group | Supported | Checked | Rate |", "|---|---|---|---|"]
    for g in F.GROUPS:
        if g in G:
            lines.append("| %s | %d | %d | %.1f%% |" % (g, G[g][0], G[g][1], 100.0 * G[g][0] / max(1, G[g][1])))
    allv = {}
    for c in cells_out:
        allv[c["verdict"]] = allv.get(c["verdict"], 0) + 1
    lines += ["", "Verdicts over all extracted cell records: " + json.dumps(allv, sort_keys=True), ""]
    # disagreements: brochure vs aggregators (conflicts.tsv, kind oem_over_aggregator) and brochure vs KB value
    dis = []
    for c in conflicts:
        if c.get("kind") == "oem_over_aggregator" and ("%s/%s" % (c["make"], c["model"])) in models:
            dis.append({"model": "%s/%s" % (c["make"], c["model"]), "variant": c["variant"], "field": c["field"], "kind": "brochure_vs_aggregator",
                        "kb_value": c.get("kb_value"), "values": c.get("values"), "resolution": c.get("resolution")})
    kbd = []
    for m in models:
        for op in corr.get(m, []):
            kbd.append(op)
    lines.append("Disagreements: %d brochure-vs-aggregator conflicts logged (conflicts.tsv, oem_over_aggregator); %d staged brochure corrections of an existing value." % (len(dis), len(kbd)))
    with open(os.path.join(rd, "brochure_cells.tsv"), "w") as f:
        w = csv.DictWriter(f, ["model", "variant", "kb_variant_id", "field", "value", "raw", "page", "printed", "qualifier", "group", "verdict",
                               "checker", "check_evidence", "sha1", "kb_has_brochure_value"], delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(cells_out)
    with open(os.path.join(rd, "brochure_disagreements.tsv"), "w") as f:
        w = csv.DictWriter(f, ["model", "variant", "field", "kind", "kb_value", "values", "resolution"], delimiter="\t")
        w.writeheader()
        w.writerows(dis)
    open(os.path.join(rd, "BROCHURE_REPORT.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
