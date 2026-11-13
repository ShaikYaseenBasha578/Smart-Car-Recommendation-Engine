"""kbpipe command line.  kbpipe run | apply-review | agreement | status | pin-schema"""
import argparse
import json
import os
import sys

from . import config, kb, pipeline, report, review


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kbpipe", description="CarRec KB enrichment pipeline")
    ap.add_argument("--config", help="path to kbpipe.config.json")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="discovery -> extraction -> reconciliation -> verification -> gates -> write -> report")
    r.add_argument("--full", action="store_true", help="re-process every model, ignoring the incremental state")
    r.add_argument("--max-models", type=int, help="process at most N models this run")
    r.add_argument("--only", action="append", help="process only this model name (repeatable)")
    r.add_argument("--no-write", action="store_true", help="stage and gate, but never touch the KB")
    r.add_argument("--no-verify", action="store_true", help="skip the verifier (no accuracy number)")
    r.add_argument("--audit", choices=["full", "changed", "none"], help="final audit scope (default: full on the first run, else changed)")
    r.add_argument("--label", help="name of the run folder (default: today's date)")
    a = sub.add_parser("apply-review", help="apply the items ticked in a REVIEW_<run>.md")
    a.add_argument("review_file")
    a.add_argument("--no-write", action="store_true")
    g = sub.add_parser("agreement", help="owner-vs-verifier agreement from a filled human_check.csv")
    g.add_argument("sheet")
    sub.add_parser("status", help="KB state and last run")
    sub.add_parser("pin-schema", help="print the current schema hash to pin in the config")
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    if args.cmd == "run":
        R = pipeline.run(cfg, full=args.full, max_models=args.max_models, only=args.only, no_write=args.no_write,
                         no_verify=args.no_verify, audit=args.audit, label=args.label,
                         echo=lambda line: print(line, flush=True))
        return 1 if (R.get("stopped") and not R.get("write") and "--no-write" not in (R.get("stopped") or "")) else 0
    if args.cmd == "apply-review":
        print(json.dumps(review.apply(cfg, args.review_file, no_write=args.no_write), indent=1, default=str))
        return 0
    if args.cmd == "agreement":
        print(json.dumps(report.agreement(args.sheet), indent=1))
        return 0
    if args.cmd == "pin-schema":
        tmp = os.path.join(cfg["cache_dir"], "schema_probe.db")
        kb.copy_for_read(cfg["prod_db"], tmp)
        print(kb.schema_sha256(kb.ro(tmp)))
        os.remove(tmp)
        return 0
    if args.cmd == "status":
        try:
            sha = kb.preflight(cfg["prod_db"], for_write=False)
            print("KB %s\nSHA-1 %s\nholders: none that block" % (cfg["prod_db"], sha))
        except kb.Stop as e:
            print("KB not safe to use: %s" % e)
        runs = sorted(d for d in os.listdir(cfg["runs_dir"])) if os.path.isdir(cfg["runs_dir"]) else []
        print("runs: %s" % (", ".join(runs[-5:]) or "none"))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
