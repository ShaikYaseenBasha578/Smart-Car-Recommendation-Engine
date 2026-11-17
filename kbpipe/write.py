"""The controlled write (CLAUDE.md P10, P11), done by code.

  preflight  holder check, -wal check, SHA-1
  backup     sqlite3 .backup into backups/, verified
  history    table dumps committed to the local history repo and tagged (no remote)
  staging    change-set applied to a copy of the backup; all four gates; re-applied -> must change nothing
  prod       SHA-1 rechecked; the identical change-set applied in one transaction; integrity and foreign-key
             checks; prod must equal staging table for table; WAL checkpoint; new SHA-1
A gate failure or any surprise stops before prod is touched."""
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone

from . import changeset, gates, kb


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def stage(cfg, cs, run_dir, source_db, log):
    """Apply to a staging copy and run the gates. Returns (ok, result). Never touches prod."""
    os.makedirs(run_dir, exist_ok=True)
    before = os.path.join(run_dir, "before.db")
    staging = os.path.join(run_dir, "staging.db")
    if os.path.abspath(source_db) != before:
        shutil.copyfile(source_db, before)
    shutil.copyfile(before, staging)
    res = {"ops": len(cs["ops"]), "gates": {}, "log_rows": 0, "idempotent": None, "error": None}
    try:
        applog = changeset.apply(staging, cs)
    except changeset.ApplyError as e:
        res["error"] = "apply failed on staging: %s" % e
        return False, res
    kb.checkpoint(staging)
    res["log_rows"] = len(applog)
    ok, g = gates.run_all(before, staging, applog, cfg)
    res["gates"] = {k: {"ok": v[0], "detail": v[1][:12]} for k, v in g.items()}
    again = os.path.join(run_dir, "idempotency.db")
    shutil.copyfile(staging, again)
    relog = changeset.apply(again, cs)
    kb.checkpoint(again)
    res["idempotent"] = (len(relog) == 0 and not kb.diff(staging, again))
    os.remove(again)
    with open(os.path.join(run_dir, "apply_log.tsv"), "w") as f:
        f.write("table\trowid\taction\tdetail\n")
        for r in applog:
            f.write("\t".join(str(x) for x in r) + "\n")
    res["staging"], res["before"] = staging, before
    return ok and res["idempotent"], res


def history_commit(cfg, db_path, tag, message, log):
    """Dump every table as sorted JSON lines into the local history repo, commit and tag. Never pushes."""
    repo = cfg["history_repo"]
    os.makedirs(os.path.join(repo, "tables"), exist_ok=True)
    git = lambda *a: subprocess.run(["git", "-C", repo] + list(a), capture_output=True, text=True)
    if not os.path.exists(os.path.join(repo, ".git")):
        git("init", "-q")
        git("config", "user.name", "kbpipe")
        git("config", "user.email", "kbpipe@localhost")
    if git("remote").stdout.strip():
        raise kb.Stop("the history repo has a remote; kbpipe only commits to a repo without one")
    c = kb.ro(db_path)
    for t in kb.tables(c):
        with open(os.path.join(repo, "tables", t + ".jsonl"), "w") as f:
            for r in c.execute('select * from "%s" order by 1' % t):
                f.write(json.dumps(list(r), ensure_ascii=False, default=str) + "\n")
    with open(os.path.join(repo, "schema.sql"), "w") as f:
        for r in c.execute("select sql from sqlite_master where sql is not null order by type, name"):
            f.write(r[0] + ";\n")
    with open(os.path.join(repo, "SHA1"), "w") as f:
        f.write(kb.sha1(db_path) + "\n")
    c.close()
    git("add", "-A")
    r = git("commit", "-q", "-m", message)
    t = tag
    n = 1
    while git("rev-parse", "-q", "--verify", "refs/tags/" + t).returncode == 0:
        n += 1
        t = "%s.%d" % (tag, n)
    git("tag", t)
    return t


def promote(cfg, cs, run_dir, stage_res, log):
    """Apply the staged change-set to prod. Returns a result dict. Raises kb.Stop on any safety condition."""
    db = cfg["prod_db"]
    before, staging = stage_res["before"], stage_res["staging"]
    sha_pre = kb.preflight(db)
    if kb.sha1(before) != sha_pre:
        raise kb.Stop("the KB changed since this run copied it; rerun")
    bpath = os.path.join(cfg["backup_dir"], "pre_kbpipe_%s_%s.db" % (cs["run"].replace("-", ""), utc_stamp()))
    kb.backup(db, bpath)
    tag = history_commit(cfg, bpath, "kb-run-%s" % cs["run"], "KB before kbpipe run %s (%s)" % (cs["run"], sha_pre), log)
    if kb.preflight(db) != sha_pre:
        raise kb.Stop("the KB changed during backup")
    expected = stage_res["log_rows"]

    def check(conn, applog):
        if len(applog) != expected:
            raise changeset.ApplyError("prod apply produced %d log rows, staging produced %d" % (len(applog), expected))

    applog = changeset.apply(db, cs, check=check)
    kb.checkpoint(db)          # WAL folded in and side files removed, so the file alone is the whole database
    c = kb.ro(db)              # immutable read: mode=ro cannot open a WAL-mode file whose side files are gone
    ic = c.execute("pragma integrity_check").fetchone()[0]
    c.close()
    same = not kb.diff(staging, db)
    sha_post = kb.sha1(db)
    res = {"sha1_before": sha_pre, "sha1_after": sha_post, "backup": bpath, "history_tag": tag, "integrity_check": ic,
           "prod_equals_staging": same, "rows": len(applog)}
    if ic != "ok" or not same:
        raise kb.Stop("post-apply verification failed (%s, prod==staging: %s). Backup: %s" % (ic, same, bpath))
    history_commit(cfg, db, "kb-run-%s-after" % cs["run"], "KB after kbpipe run %s (%s)" % (cs["run"], sha_post), log)
    kb.remove_side_files(db)   # the comparison above reads prod again; leave nothing beside it (P11)
    if kb.sha1(db) != sha_post:
        raise kb.Stop("the KB hash changed after the post-apply checks. Backup: %s" % bpath)
    return res
