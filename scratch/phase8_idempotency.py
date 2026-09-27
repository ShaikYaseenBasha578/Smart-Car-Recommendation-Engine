import sqlite3
import json
DB = "scratch/carrec_kb_phase8_shadow.db"
conn = sqlite3.connect(DB, isolation_level=None)
conn.row_factory = sqlite3.Row

c = conn.execute("SELECT count(*) FROM safety_test")
pre_tests = c.fetchone()[0]
c = conn.execute("SELECT count(*) FROM safety_test_applicability")
pre_appls = c.fetchone()[0]

# we just want to run Pass 3 to show 0 additions
# We will do this by re-running the exact logic but not wiping the DB.
