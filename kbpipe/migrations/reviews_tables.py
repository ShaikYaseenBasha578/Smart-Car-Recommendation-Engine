"""Migration for the review layers (REVIEW_LAYERS_PLAN.md section 3 and 9a): professional_assessment, owner_rating,
owner_theme, and three source rows. Pure additions: no existing table or view is touched.

  python -m kbpipe.migrations.reviews_tables <db path>          # a scratch copy
  python -m kbpipe.migrations.reviews_tables <db path> --prod   # production: needs the owner's P16 approval; NOT used in the build

Idempotent (IF NOT EXISTS, source rows by name), one transaction. Refuses the production file unless --prod is given."""
import os
import sqlite3
import sys

DDL = [
    """CREATE TABLE IF NOT EXISTS professional_assessment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL REFERENCES model(id),
  source_id INTEGER NOT NULL REFERENCES source(id),
  source_aspect TEXT NOT NULL,
  score REAL NOT NULL,
  scale_max REAL NOT NULL,
  variant_scope TEXT,
  source_url TEXT NOT NULL,
  published_on TEXT,
  observed_at TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'current' CHECK (status IN ('current','superseded','stale_generation')),
  note TEXT,
  quote TEXT,
  CHECK (score >= 0 AND score <= scale_max),
  UNIQUE(model_id, source_id, source_aspect, observed_at)
)""",
    """CREATE TABLE IF NOT EXISTS owner_rating (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL REFERENCES model(id),
  source_id INTEGER NOT NULL REFERENCES source(id),
  source_aspect TEXT NOT NULL,
  score REAL NOT NULL,
  scale_max REAL NOT NULL,
  rating_count INTEGER,
  source_url TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'current' CHECK (status IN ('current','superseded')),
  CHECK (score >= 0 AND score <= scale_max),
  UNIQUE(model_id, source_id, source_aspect, observed_at)
)""",
    """CREATE TABLE IF NOT EXISTS owner_theme (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL REFERENCES model(id),
  theme TEXT NOT NULL,
  label TEXT,
  direction TEXT NOT NULL CHECK (direction IN ('positive','negative','mixed')),
  mentions INTEGER NOT NULL,
  posts_sampled INTEGER NOT NULL,
  period TEXT,
  sample_urls TEXT NOT NULL,
  note TEXT,
  source_id INTEGER NOT NULL REFERENCES source(id),
  extracted_at TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  UNIQUE(model_id, theme, label, source_id)
)""",
]

SOURCES = [
    ("Autocar India expert review", "review", "https://www.autocarindia.com", 3,
     "Professional scores out of 10 from the model's expert-review page. Terms-grey source accepted by the owner (V1)."),
    ("CarWale user ratings", "review", "https://www.carwale.com", 3,
     "Owner ratings out of 5 and written-review themes from the model's user-review pages (V2)."),
    ("Team-BHP (owner-saved pages)", "review", "https://www.team-bhp.com", 3,
     "Threads saved by the owner in a browser and read from local files; the tool never contacts the site."),
]


class Refused(Exception):
    pass


def is_prod(path, prod_path=None):
    real = os.path.realpath(path)
    if prod_path and real == os.path.realpath(prod_path):
        return True
    return real.endswith(os.path.join("knowledge_base", "carrec_kb.db"))


def objects(c):
    return sorted(tuple(r) for r in c.execute(
        "select type,name,tbl_name,sql from sqlite_master where name not like 'sqlite_%' and name not in "
        "('professional_assessment','owner_rating','owner_theme')"))


def migrate_conn(c):
    """Apply inside the caller's transaction. Returns what it created."""
    made = []
    for ddl in DDL:
        name = ddl.split("EXISTS")[1].split("(")[0].strip()
        if not c.execute("select 1 from sqlite_master where type='table' and name=?", (name,)).fetchone():
            made.append(name)
        c.execute(ddl)
    for name, typ, url, tier, notes in SOURCES:
        if not c.execute("select 1 from source where name=?", (name,)).fetchone():
            c.execute("insert into source(name,source_type,base_url,authority_tier,notes) values (?,?,?,?,?)", (name, typ, url, tier, notes))
            made.append("source:" + name)
    return made


def has_tables(c):
    return all(c.execute("select 1 from sqlite_master where type='table' and name=?", (t,)).fetchone()
               for t in ("professional_assessment", "owner_rating", "owner_theme"))


def migrate(path, prod_flag=False, prod_path=None):
    if is_prod(path, prod_path) and not prod_flag:
        raise Refused("%s is the production KB; this migration needs --prod and the owner's P16 approval" % path)
    c = sqlite3.connect(path, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    before = objects(c)
    c.execute("BEGIN IMMEDIATE")
    try:
        made = migrate_conn(c)
        if objects(c) != before:
            raise RuntimeError("an existing table or view changed; rolled back")
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        c.close()
        raise
    ic = c.execute("pragma integrity_check").fetchone()[0]
    c.close()
    return {"created": made, "integrity_check": ic}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    prod = "--prod" in argv
    args = [a for a in argv if a != "--prod"]
    if len(args) != 1:
        print(__doc__)
        return 2
    try:
        from .. import config
        prod_path = config.load()["prod_db"]
    except Exception:
        prod_path = None
    try:
        print(migrate(args[0], prod_flag=prod, prod_path=prod_path))
    except Refused as e:
        print("REFUSED:", e)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
