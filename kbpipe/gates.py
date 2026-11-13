"""Scripted gates. Each returns (ok, detail). A failed gate blocks the merge from staging into the KB.

1 schema      the live schema hash equals the pinned one (or the pre-run one), integrity_check is ok,
              foreign_key_check shows only the orphans that were there before, written values are in range
2 provenance  every new or changed cell has a provenance row whose observation has a URL, a date and a method
3 rows        no table lost rows
4 explained   every row of the full EXCEPT diff is in the apply log; nothing was removed"""
import sqlite3

from . import fields as F
from . import kb


def _conn(path):
    return kb.ro(path)


def gate_schema(before, after, cfg):
    b, a = _conn(before), _conn(after)
    out = []
    pinned = cfg.get("schema_sha256") or kb.schema_sha256(b)
    if kb.schema_sha256(a) != pinned:
        out.append("schema hash changed")
    ic = a.execute("pragma integrity_check").fetchone()[0]
    if ic != "ok":
        out.append("integrity_check: %s" % ic)
    fb = b.execute("pragma foreign_key_check").fetchall()
    fa = a.execute("pragma foreign_key_check").fetchall()
    if len(fa) != len(fb) or any(r[0] != "field_provenance" for r in fa):
        out.append("foreign_key_check: %d rows (was %d)" % (len(fa), len(fb)))
    d = kb.diff(before, after)
    cols = [r[1] for r in a.execute("pragma table_info(variant)")]
    for row in d.get("variant", {}).get("added", []):
        rec = dict(zip(cols, row))
        for f in F.VARIANT_FIELDS:
            if not F.in_range(f, rec.get(f)):
                out.append("variant %s %s=%r out of range" % (rec["id"], f, rec.get(f)))
        if rec["transmission"] not in F.TRANSMISSIONS:
            out.append("variant %s transmission %r" % (rec["id"], rec["transmission"]))
    return (not out, out or ["schema %s, integrity ok, %d known orphans" % (pinned[:12], len(fa))])


def changed_cells(before, after):
    """[(variant_id, field, new_value)] for every data cell that is new or different, powertrain fields of new variants included."""
    b, a = _conn(before), _conn(after)
    cols = [r[1] for r in a.execute("pragma table_info(variant)")]
    old = {r["id"]: r for r in b.execute("select * from variant")}
    out = []
    for r in a.execute("select * from variant"):
        o = old.get(r["id"])
        for f in F.VARIANT_FIELDS:
            if f in cols and r[f] is not None and (o is None or not F.same(f, o[f], r[f])):
                out.append((r["id"], f, r[f]))
        if o is None and r["powertrain_id"] is not None:
            p = a.execute("select * from powertrain where id=?", (r["powertrain_id"],)).fetchone()
            for f in F.POWERTRAIN_FIELDS:
                if p[f] is not None:
                    out.append((r["id"], f, p[f]))
    return out


def gate_provenance(before, after, cfg):
    a = _conn(after)
    cells = changed_cells(before, after)
    bad = []
    for vid, f, val in cells:
        rows = a.execute(
            "select p.accepted_value, o.source_url, o.observed_at, o.extraction_method from field_provenance p "
            "join source_observation o on o.id=p.source_observation_id "
            "where p.variant_id=? and p.field_name=? and p.decision='accepted'", (vid, f)).fetchall()
        ok = any(F.same(f, r[0], val) and r[1] and r[2] and r[3] and str(r[3]).startswith("kbpipe") for r in rows)
        if not ok:
            bad.append("variant %s %s=%r has no kbpipe provenance with url, date and method" % (vid, f, val))
    return (not bad, bad[:20] or ["%d of %d new or changed cells have provenance" % (len(cells), len(cells))])


def gate_rows(before, after, cfg):
    b, a = _conn(before), _conn(after)
    bad, tot = [], []
    for t in kb.tables(b):
        nb = b.execute('select count(*) from "%s"' % t).fetchone()[0]
        na = a.execute('select count(*) from "%s"' % t).fetchone()[0]
        tot.append("%s %d->%d" % (t, nb, na))
        if na < nb:
            bad.append("%s lost rows: %d -> %d" % (t, nb, na))
    return (not bad, bad or tot)


def gate_explained(before, after, log, cfg):
    d = kb.diff(before, after)
    logged = {(t, i) for t, i, _, _ in log}
    bad = []
    n = 0
    for t, ch in d.items():
        if ch.get("new_table"):
            bad.append("new table %s" % t)
            continue
        added_ids = {r[0] for r in ch["added"]}
        for r in ch["removed"]:
            if t != "variant" or r[0] not in added_ids:
                bad.append("%s row %s was removed or changed outside variant" % (t, r[0]))
        for r in ch["added"]:
            n += 1
            if (t, r[0]) not in logged:
                bad.append("%s row %s changed but is not in the run log" % (t, r[0]))
    for t, i, action, _ in log:
        if t not in d or i not in {r[0] for r in d[t]["added"]}:
            bad.append("log says %s %s %s but the diff has no such row" % (action, t, i))
    return (not bad, bad[:20] or ["%d changed rows, all in the run log" % n])


def run_all(before, after, log, cfg):
    res = {"schema": gate_schema(before, after, cfg), "provenance": gate_provenance(before, after, cfg),
           "rows": gate_rows(before, after, cfg), "explained": gate_explained(before, after, log, cfg)}
    return all(v[0] for v in res.values()), res
