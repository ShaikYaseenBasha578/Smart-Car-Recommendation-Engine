"""apply-review: turn the owner's ticks in REVIEW_<run>.md into a change-set and send it through the same write path."""
import json
import os
import re
from datetime import datetime, timezone

from . import kb, write


def decisions(md_path):
    ap, rj = set(), set()
    with open(md_path) as f:
        for line in f:
            m = re.match(r"\s*-\s*\[\s*[xX]\s*\]\s*(approve|reject)\s+(\S+)", line)
            if m:
                (ap if m.group(1) == "approve" else rj).add(m.group(2))
    both = ap & rj
    return ap - both, rj - both, both


def apply(cfg, md_path, echo=print, no_write=False):
    run_dir = os.path.dirname(os.path.abspath(md_path))
    with open(os.path.join(run_dir, "pending.json")) as f:
        pend = json.load(f)
    ap, rj, both = decisions(md_path)
    done_path = os.path.join(run_dir, "review_done.json")
    done = json.load(open(done_path)) if os.path.exists(done_path) else {}
    items = [r for r in pend["items"] if r["id"] in ap and r["id"] not in done and r["ops"]]
    for i in rj:
        done.setdefault(i, "rejected")
    res = {"approved": [r["id"] for r in items], "rejected": sorted(rj), "ticked_both": sorted(both), "write": None, "stopped": None}
    if items:
        stamp = datetime.now(timezone.utc)
        ops = [op for r in items for op in r["ops"]]
        used = {e["obs"] for op in ops for e in op.get("evidence", [])}
        cs = {"run": pend["run"] + "-review", "ts": stamp.strftime("%Y-%m-%d %H:%M:%S"),
              "observations": {k: v for k, v in pend["observations"].items() if k in used}, "ops": ops}
        sub = os.path.join(run_dir, "review_" + stamp.strftime("%H%M%S"))
        os.makedirs(sub)
        try:
            kb.copy_for_read(cfg["prod_db"], os.path.join(sub, "before.db"))
            ok, st = write.stage(cfg, cs, sub, os.path.join(sub, "before.db"), echo)
            res["gates"] = {k: v["ok"] for k, v in st.get("gates", {}).items()}
            if not ok:
                res["stopped"] = st.get("error") or "gates failed: %s" % json.dumps(st.get("gates"))[:600]
            elif not no_write:
                res["write"] = write.promote(cfg, cs, sub, st, echo)
                for r in items:
                    done[r["id"]] = "applied"
                with open(cfg["changelog"], "a") as f:
                    f.write("\n## kbpipe %s — review decisions applied\n**What changed:** %d approved item(s) (%s), %d change(s). "
                            "**Prod SHA-1:** `%s…` → `%s…`.\n" % (cs["run"], len(items), ", ".join(res["approved"]), len(ops),
                                                                  res["write"]["sha1_before"][:8], res["write"]["sha1_after"][:8]))
        except kb.Stop as e:
            res["stopped"] = str(e)
    with open(done_path, "w") as f:
        json.dump(done, f, indent=1)
    return res
