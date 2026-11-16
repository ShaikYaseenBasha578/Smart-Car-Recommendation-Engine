"""kbpipe command line.  kbpipe update | run | apply-review | agreement | status | pin-schema"""
import argparse
import json
import os
import sys

from . import audit, config, kb, pipeline, report, review, reviews


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
    r.add_argument("--no-brochure", action="store_true", help="skip the brochure layer (no OEM brochure pages are read)")
    r.add_argument("--label", help="name of the run folder (default: today's date)")
    r.add_argument("--resume-audit", metavar="RUN_FOLDER", help="continue an interrupted audit from that folder's verify/results.jsonl (no discovery, no write); scope from --audit")
    v = sub.add_parser("reviews", help="professional scores (Autocar India), owner ratings and themes (CarWale); also --import-saved")
    v.add_argument("--only", action="append", help="process only this model (name or 'Make Model'; repeatable)")
    v.add_argument("--max-models", type=int)
    v.add_argument("--no-write", action="store_true", help="stage and gate, but never touch the KB")
    v.add_argument("--label", help="name of the run folder")
    v.add_argument("--no-text", action="store_true", help="numbers only: no LLM notes or themes")
    v.add_argument("--verify-all", action="store_true", help="verify every note and theme (default: the configured fraction)")
    v.add_argument("--force", action="store_true", help="ignore the 90-day freshness of rows already in the KB (pages come from the cache; use it to add text to rows that hold only numbers)")
    v.add_argument("--write-only", action="store_true", help="only warm the writer cache (Sonnet); the checker is not called and no text is kept. Run the same command without it later to do the checks")
    v.add_argument("--no-themes", action="store_true", help="Autocar notes only: CarWale written reviews are not read and no owner themes are made")
    v.add_argument("--import-saved", metavar="FOLDER", help="read locally saved Team-BHP pages (never fetches) into owner_theme")
    v.add_argument("--teambhp-links", action="store_true", help="only write teambhp_links.html (links; fetches nothing)")
    u = sub.add_parser("update", help="the whole update in one command: specs, brochures, reviews, audit, export to the app, tests, project pages, pull request")
    u.add_argument("--no-write", action="store_true", help="run every stage against staging copies: no KB write, no push, no pull request")
    u.add_argument("--resume", action="store_true", help="continue an interrupted update from its state.json (stages already done are not repeated)")
    u.add_argument("--only-stages", action="append", metavar="LIST", help="run only these stages (names or numbers, comma separated): preflight specs brochures reviews text saved audit export checks pages pr summary")
    u.add_argument("--skip-stages", action="append", metavar="LIST", help="leave these stages out")
    u.add_argument("--max-models", type=int, help="cap the models processed per update")
    u.add_argument("--no-pr", action="store_true", help="commit to the app branch locally; do not push or open a pull request")
    u.add_argument("--quick", action="store_true", help="skip brochures, review text and saved pages (no subscription allowance used)")
    u.add_argument("--redo", action="append", metavar="STAGE", help="run this stage again although it is done")
    u.add_argument("--label", help="name of the update folder (default update_<date>); with --resume, the update to continue (default: the latest)")
    u.add_argument("--no-verify", action="store_true", help="no verifier calls at all (stage 2 verification and the stage 7 audit are skipped)")
    a = sub.add_parser("apply-review", help="apply the items ticked in a REVIEW_<run>.md")
    a.add_argument("review_file")
    a.add_argument("--no-write", action="store_true")
    g = sub.add_parser("agreement", help="owner-vs-verifier agreement from a filled human_check.csv")
    g.add_argument("sheet")
    sub.add_parser("status", help="KB state and last run")
    sub.add_parser("pin-schema", help="print the current schema hash to pin in the config")
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    if args.cmd == "update":
        from . import update
        state, rc = update.run(cfg, {"no_write": args.no_write, "resume": args.resume, "only_stages": args.only_stages,
                                     "skip_stages": args.skip_stages, "max_models": args.max_models, "no_pr": args.no_pr,
                                     "quick": args.quick, "redo": args.redo, "label": args.label, "no_verify": args.no_verify},
                               echo=lambda line: print(line, flush=True))
        return rc
    if args.cmd == "run" and args.resume_audit:
        R = audit.run(cfg, scope=args.audit if args.audit in ("full", "changed") else "changed", resume=args.resume_audit,
                      echo=lambda line: print(line, flush=True))
        print(json.dumps({k: R.get(k) for k in ("scope", "cells", "already_done", "checked_now", "stopped_on_limit")}, indent=1))
        return 1 if R.get("stopped_on_limit") else 0
    if args.cmd == "run":
        if args.no_brochure:
            cfg.setdefault("brochure", {})["enabled"] = False
        R = pipeline.run(cfg, full=args.full, max_models=args.max_models, only=args.only, no_write=args.no_write,
                         no_verify=args.no_verify, audit=args.audit, label=args.label,
                         echo=lambda line: print(line, flush=True))
        return 1 if (R.get("stopped") and not R.get("write") and "--no-write" not in (R.get("stopped") or "")) else 0
    if args.cmd == "reviews":
        echo = lambda line: print(line, flush=True)
        if args.teambhp_links:
            d = os.path.join(cfg["runs_dir"], args.label or "teambhp_links")
            os.makedirs(d, exist_ok=True)
            print(reviews.teambhp_links(cfg, d))
            return 0
        if args.import_saved:
            R = reviews.import_saved(cfg, args.import_saved, no_write=args.no_write, label=args.label,
                                     ask=(input if sys.stdin.isatty() else None), echo=echo)
            return 1 if (R.get("stopped") and not R.get("write") and "--no-write" not in R["stopped"]) else 0
        if args.no_themes:
            cfg["reviews"]["themes_enabled"] = False
        R = reviews.run(cfg, only=args.only, max_models=args.max_models, no_write=args.no_write, label=args.label,
                        no_text=args.no_text, verify_all=args.verify_all, force=args.force, write_only=args.write_only, echo=echo)
        return 1 if (R.get("stopped") and not R.get("write") and "--no-write" not in R["stopped"]) else 0
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
