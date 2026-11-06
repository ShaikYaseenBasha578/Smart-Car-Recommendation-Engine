"""Single way to open the KB. SQLite creates an empty file when a path is wrong, which once left a 0-byte
ingestion/carrec_kb.db behind, so open_kb refuses a path that doesn't exist instead of creating it."""
import os
import sqlite3
from urllib.parse import quote

KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carrec_kb.db")


def open_kb(path=KB_PATH, readonly=False, **kwargs):
    """Open an existing KB file. Raises FileNotFoundError rather than creating one. `path` may be relative to the cwd."""
    path = os.path.abspath(os.fspath(path))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"KB file not found: {path}")
    mode = "ro" if readonly else "rw"
    return sqlite3.connect(f"file:{quote(path)}?mode={mode}", uri=True, **kwargs)
