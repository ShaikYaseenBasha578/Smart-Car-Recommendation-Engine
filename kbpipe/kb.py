"""KB file safety: holder check, hashes, backup, copies. Implements P10/P11 mechanics; never opens prod for writing
(only changeset.apply does, called from write.py after the checks here pass)."""
import hashlib
import os
import shutil
import sqlite3
import subprocess

ALLOWED_HOLDER = "com.apple.Virtualization.VirtualMachine"


class Stop(Exception):
    """A hard stop: the run must not write. The message goes into the report."""


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def holders(db):
    """[(command, pid, fd_mode)] for the db and its side files. Empty when nothing holds them."""
    files = [p for p in (db, db + "-wal", db + "-shm") if os.path.exists(p)]
    try:
        out = subprocess.run(["lsof", "+c", "0", "-F", "pcfa"] + files, capture_output=True, text=True).stdout
    except FileNotFoundError:
        raise Stop("lsof not available; cannot check holders (P11)")
    res, pid, cmd = [], None, None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = line[1:]
        elif line.startswith("c"):
            cmd = line[1:]
        elif line.startswith("a"):
            res.append((cmd, pid, line[1:]))
    return res


def preflight(db, for_write=True):
    """Raise Stop unless prod is safe to copy (and to write). Returns its SHA-1."""
    if not os.path.exists(db):
        raise Stop("KB not found: %s" % db)
    for cmd, pid, mode in holders(db):
        if not (cmd == ALLOWED_HOLDER and mode == "r"):
            raise Stop("KB is held by %s (pid %s, mode %s); P11 allows only a read-only %s" % (cmd, pid, mode, ALLOWED_HOLDER))
    wal = db + "-wal"
    if os.path.exists(wal) and os.path.getsize(wal) > 0:
        raise Stop("non-empty -wal beside the KB (%d bytes); P11 says stop" % os.path.getsize(wal))
    return sha1(db)


def copy_for_read(db, dest):
    """Byte copy with the hash checked before and after (the read rule in CLAUDE.md)."""
    a = preflight(db, for_write=False)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(db, dest)
    if sha1(db) != a or sha1(dest) != a:
        raise Stop("KB changed while it was being copied")
    return a


def ro(path):
    c = sqlite3.connect("file:%s?immutable=1" % path, uri=True)
    c.row_factory = sqlite3.Row
    return c


def sha3(path):
    out = subprocess.run(["sqlite3", path, ".sha3sum"], capture_output=True, text=True)
    return out.stdout.strip()


def backup(db, dest):
    """sqlite3 .backup (P10 step 2), verified by .sha3sum."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = subprocess.run(["sqlite3", db, ".backup '%s'" % dest], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dest):
        raise Stop("backup failed: %s" % r.stderr.strip())
    if sha3(db) != sha3(dest):
        raise Stop("backup content differs from the KB")
    return dest


def checkpoint(db):
    c = sqlite3.connect(db)
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()
    wal = db + "-wal"
    if os.path.exists(wal) and os.path.getsize(wal) > 0:
        raise Stop("-wal is not empty after checkpoint")


def tables(c):
    return [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence' order by 1")]


def schema_sha256(c):
    rows = c.execute("select type,name,tbl_name,sql from sqlite_master where name not like 'sqlite_%' order by type,name").fetchall()
    return hashlib.sha256(repr([tuple(r) for r in rows]).encode()).hexdigest()


def diff(before, after):
    """Full per-table EXCEPT diff in both directions. {table: {"added": [rows], "removed": [rows]}} keyed by rowid-first tuples."""
    c = sqlite3.connect("file::memory:", uri=True)
    c.execute("attach database ? as b", ("file:%s?immutable=1" % before,))
    c.execute("attach database ? as a", ("file:%s?immutable=1" % after,))
    out = {}
    for (t,) in c.execute("select name from a.sqlite_master where type='table' and name<>'sqlite_sequence' order by 1").fetchall():
        if not c.execute("select 1 from b.sqlite_master where type='table' and name=?", (t,)).fetchone():
            out[t] = {"added": c.execute('select * from a."%s"' % t).fetchall(), "removed": [], "new_table": True}
            continue
        add = c.execute('select * from a."%s" except select * from b."%s"' % (t, t)).fetchall()
        rem = c.execute('select * from b."%s" except select * from a."%s"' % (t, t)).fetchall()
        if add or rem:
            out[t] = {"added": add, "removed": rem}
    c.close()
    return out
