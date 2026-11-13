"""Measure a brochure-layer run from its run folder (reads only files in the run folder; opens its before.db, a scratch copy
of the KB, read-only; never opens the production database).

  python -m kbpipe.tools.brochure_measure <run_dir> [--kb-models Creta Venue Swift] [--new-models Punch Sonet]

Per model: pages read, LLM calls, cells kept, cells dropped for disagreement.
KB models: how many of the reader's cells agree / disagree with the KB's existing brochure-backed values for the same
(variant, field), ignoring the skip rule, and how many brochure-backed KB cells the reader did not produce.
New models: of the cells the changeset writes from a brochure, how many the aggregators alone would have left blank
(NO_SOURCE or SINGLE_SOURCE) or in conflict, compared with the SINGLE_SOURCE / NO_SOURCE rows still in flags.tsv."""
import argparse
import csv
import glob
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from kbpipe import fields as F  # noqa: E402
from kbpipe import reconcile as R  # noqa: E402


def tsv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def kb_value(conn, vid, field):
    if F.FIELDS[field][0] == "variant":
        r = conn.execute('select "%s" from variant where id=?' % field, (vid,)).fetchone()
    else:
        r = conn.execute('select p."%s" from variant v join powertrain p on p.id=v.powertrain_id where v.id=?' % field, (vid,)).fetchone()
    return r[0] if r else None


def backed(conn):
    sid = conn.execute("select id from source where name='oem'").fetchone()
    rows = conn.execute("select p.variant_id, p.field_name from field_provenance p join source_observation o on o.id=p.source_observation_id "
                        "where o.source_id=? and p.decision in ('accepted','confirmed')", (sid[0],)).fetchall()
    return {(r[0], r[1]) for r in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--kb-models", nargs="*", default=[])
    ap.add_argument("--new-models", nargs="*", default=[])
    a = ap.parse_args()
    rd = a.run_dir
    sums = {}
    for p in glob.glob(os.path.join(rd, "brochure", "*_*.json")):
        if os.path.basename(p) != "summary.json":
            d = json.load(open(p))
            sums[d["model"]] = d
    print("PER MODEL (llm_calls counts every LLM call; each page is read twice)")
    for m, d in sorted(sums.items()):
        print("  %-8s status=%-34s pages_read=%d llm_calls=%d cells_kept=%d attached=%d skipped_existing=%d dropped_disagree=%d dropped_single_read=%d dropped_page_conflict=%d" % (
            m, d["status"], d["pages_read"], d["llm_calls"], d["cells_kept"], d["cells_attached"], d["cells_skipped_existing"],
            d["cells_dropped_disagree"], d["cells_dropped_single_read"], d["cells_dropped_page_conflict"]))
    print("  total llm_calls:", sum(d["llm_calls"] for d in sums.values()))
    import shutil
    import tempfile
    tmp = os.path.join(tempfile.mkdtemp(prefix="brochure_measure_"), "before.db")
    shutil.copyfile(os.path.join(rd, "before.db"), tmp)     # a copy of the run's scratch copy, so no -wal/-shm is created beside it
    conn = sqlite3.connect(tmp)
    bk = backed(conn)
    links = tsv(os.path.join(rd, "links.tsv"))
    for m in a.kb_models:
        d = sums.get(m)
        if not d:
            print("\n%s: no brochure summary" % m)
            continue
        ids = {int(l["kb_variant_id"]) for l in links if l["model"] == m and l["kb_variant_id"] != ""}
        agree, dis, new_cells, rows = 0, 0, 0, []
        got = set()
        for c in d["cells"]:
            vid = c["kb_variant_id"]
            if vid is None:
                continue
            got.add((vid, c["field"]))
            if (vid, c["field"]) not in bk:
                new_cells += 1
                continue
            kv = kb_value(conn, vid, c["field"])
            if R.agree(c["field"], kv, c["value"], 0.0):
                agree += 1
            else:
                dis += 1
                rows.append((c["variant"], c["field"], kv, c["value"], c["page"], c["printed"]))
        missed = [(v, f) for (v, f) in bk if v in ids and f in F.FIELDS and f not in ("price_ex_showroom", "fuel_type", "transmission") and (v, f) not in got]
        print("\n%s vs KB brochure-backed cells (linked variants: %d; KB brochure-backed cells on them: %d)" % (m, len(ids), sum(1 for (v, f) in bk if v in ids)))
        print("  agree=%d  disagree=%d  KB-has-it-but-reader-missed-it=%d  reader-cells-with-no-KB-brochure-value=%d" % (agree, dis, len(missed), new_cells))
        for r in rows[:15]:
            print("  DISAGREE %s | %s | KB=%s reader=%s | page %s | printed: %s" % r)
        if len(rows) > 15:
            print("  ... %d more" % (len(rows) - 15))
    cs = json.load(open(os.path.join(rd, "changeset.json")))
    flags = tsv(os.path.join(rd, "flags.tsv"))
    for m in a.new_models:
        d = sums.get(m)
        cnt = {"NO_SOURCE": 0, "SINGLE_SOURCE": 0, "CONFLICT": 0, "aggregators_agreed": 0}
        n_oem = 0
        for op in cs["ops"]:
            if op.get("model") != m or op["op"] != "cell" or op["reason"] != "OEM_BROCHURE":
                continue
            n_oem += 1
            agg = [e for e in op["evidence"] if cs["observations"][e["obs"]]["source"] != "oem"]
            if not agg:
                cnt["NO_SOURCE"] += 1
            elif len(agg) == 1:
                cnt["SINGLE_SOURCE"] += 1
            elif all(e["decision"] == "confirmed" for e in agg):
                cnt["aggregators_agreed"] += 1
            else:
                cnt["CONFLICT"] += 1
        left = {}
        for fl in flags:
            if fl["model"] == m and fl["why"] in ("SINGLE_SOURCE", "NO_SOURCE"):
                left[fl["why"]] = left.get(fl["why"], 0) + 1
        print("\n%s (new model): brochure cells in the changeset: %d" % (m, n_oem))
        print("  of these, aggregators alone would have left: NO_SOURCE=%d SINGLE_SOURCE=%d CONFLICT=%d (would have been written anyway: %d)" % (
            cnt["NO_SOURCE"], cnt["SINGLE_SOURCE"], cnt["CONFLICT"], cnt["aggregators_agreed"]))
        print("  still blank in flags.tsv: %s" % json.dumps(left))
        if d:
            print("  brochure cells kept by the reader: %d, attached: %d" % (d["cells_kept"], d["cells_attached"]))


if __name__ == "__main__":
    main()
