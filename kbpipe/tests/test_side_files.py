"""P11: no -wal / -shm file may sit beside the KB. The pipeline removes its own and refuses any it finds."""
import os
import sqlite3

import pytest

from kbpipe import kb


def wal_db(tmp_path, pending=False):
    p = str(tmp_path / "t.db")
    c = sqlite3.connect(p)
    c.execute("pragma journal_mode=wal")
    c.execute("create table t(x)")
    c.execute("insert into t values (1)")
    c.commit()
    if not pending:
        c.execute("pragma wal_checkpoint(TRUNCATE)")
    c.close()
    for f in ("-wal", "-shm"):   # the state this machine's SQLite leaves; made explicit so the test does not depend on the build
        if not os.path.exists(p + f):
            open(p + f, "wb").close()
    return p


def test_preflight_refuses_any_side_file(tmp_path):
    p = wal_db(tmp_path)
    with pytest.raises(kb.Stop, match="side file"):
        kb.preflight(p)
    os.remove(p + "-wal")
    with pytest.raises(kb.Stop, match="-shm"):
        kb.preflight(p, for_write=False)
    os.remove(p + "-shm")
    assert kb.preflight(p) == kb.sha1(p)


def test_checkpoint_and_backup_leave_no_side_files(tmp_path):
    p = wal_db(tmp_path)
    sha = kb.sha1(p)
    kb.checkpoint(p)
    assert not os.path.exists(p + "-wal") and not os.path.exists(p + "-shm") and kb.sha1(p) == sha
    dest = str(tmp_path / "b" / "backup.db")
    kb.backup(p, dest)
    assert sorted(os.listdir(tmp_path)) == ["b", "t.db"] and os.listdir(tmp_path / "b") == ["backup.db"]
    assert sqlite3.connect("file:%s?immutable=1" % p, uri=True).execute("select count(*) from t").fetchone()[0] == 1


def test_a_wal_with_content_is_never_removed(tmp_path):
    p = wal_db(tmp_path)
    with open(p + "-wal", "wb") as f:
        f.write(b"x" * 64)
    with pytest.raises(kb.Stop, match="not empty"):
        kb.remove_side_files(p)
    assert os.path.getsize(p + "-wal") == 64


def test_integrity_read_works_after_side_files_are_removed(tmp_path):
    """Regression (17 Nov): promote() checkpointed, which removed the side files, then opened the KB with mode=ro,
    which SQLite refuses for a WAL-mode file without them ("unable to open database file") after the write had committed."""
    p = wal_db(tmp_path)
    kb.checkpoint(p)
    assert not os.path.exists(p + "-wal")
    with pytest.raises(sqlite3.OperationalError):
        sqlite3.connect("file:%s?mode=ro" % p, uri=True).execute("pragma integrity_check").fetchone()
    assert kb.ro(p).execute("pragma integrity_check").fetchone()[0] == "ok"
    assert not os.path.exists(p + "-wal") and not os.path.exists(p + "-shm")
