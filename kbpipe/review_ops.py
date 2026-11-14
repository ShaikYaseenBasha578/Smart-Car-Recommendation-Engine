"""Change-set ops for the review layers, applied inside changeset.apply's transaction. Rows are never deleted: a changed
score inserts a new row and marks the old one 'superseded'. Applying the same op twice changes nothing.

  {"op": "assessment", make, model, source, aspect, score, scale_max, variant_scope, url, published_on, observed_at,
   method, status, note, quote}
  {"op": "owner_rating", make, model, source, aspect, score, scale_max, rating_count, url, observed_at, method}
  {"op": "owner_theme", make, model, source, theme, label, direction, mentions, posts_sampled, period, sample_urls[],
   note, extracted_at, method}"""
import json

REVIEW_OPS = ("assessment", "owner_rating", "owner_theme")
REVIEW_TABLES = ("professional_assessment", "owner_rating", "owner_theme")


class ReviewApplyError(Exception):
    pass


def _one(c, q, *a):
    r = c.execute(q, a).fetchone()
    return r[0] if r else None


def _ids(c, op):
    mo = _one(c, "select mo.id from model mo join manufacturer m on m.id=mo.manufacturer_id where m.name=? and mo.name=?",
              op["make"], op["model"])
    sid = _one(c, "select id from source where name=?", op["source"])
    if mo is None:
        raise ReviewApplyError("model %s %s not in the KB" % (op["make"], op["model"]))
    if sid is None:
        raise ReviewApplyError("unknown source %r (run the reviews migration first)" % op["source"])
    return mo, sid


def _need(op, *keys):
    for k in keys:
        if op.get(k) in (None, ""):
            raise ReviewApplyError("%s op lacks %s" % (op["op"], k))


def _same(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) < 1e-9


def apply_op(c, cs, op, log):
    kind = op["op"]
    if kind not in REVIEW_OPS:
        raise ReviewApplyError("unknown review op %r" % kind)
    for t in REVIEW_TABLES:
        if not _one(c, "select 1 from sqlite_master where type='table' and name=?", t):
            raise ReviewApplyError("table %s is missing: apply kbpipe/migrations/reviews_tables.py first (P16)" % t)
    mo, sid = _ids(c, op)
    if kind == "assessment":
        _need(op, "aspect", "score", "scale_max", "url", "observed_at", "method")
        cur = c.execute("select id,score,published_on,note,quote from professional_assessment where model_id=? and source_id=? "
                        "and source_aspect=? and status in ('current','stale_generation') order by id desc limit 1",
                        (mo, sid, op["aspect"])).fetchone()
        if cur and _same(cur[1], op["score"]) and (cur[2] or None) == (op.get("published_on") or None):
            sets, vals = [], []
            if op.get("note") and not cur[3]:
                sets.append("note=?"), vals.append(op["note"])
            if op.get("quote") and not cur[4]:
                sets.append("quote=?"), vals.append(op["quote"])
            if sets:
                c.execute("update professional_assessment set %s where id=?" % ",".join(sets), vals + [cur[0]])
                log.append(("professional_assessment", cur[0], "update", "note"))
            return
        if cur:
            c.execute("update professional_assessment set status='superseded' where id=?", (cur[0],))
            log.append(("professional_assessment", cur[0], "update", "superseded"))
        rid = c.execute("insert into professional_assessment(model_id,source_id,source_aspect,score,scale_max,variant_scope,source_url,"
                        "published_on,observed_at,extraction_method,status,note,quote) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (mo, sid, op["aspect"], op["score"], op["scale_max"], op.get("variant_scope"), op["url"],
                         op.get("published_on"), op["observed_at"], op["method"], op.get("status") or "current",
                         op.get("note"), op.get("quote"))).lastrowid
        log.append(("professional_assessment", rid, "insert", "%s.%s" % (op["model"], op["aspect"])))
    elif kind == "owner_rating":
        _need(op, "aspect", "score", "scale_max", "url", "observed_at", "method")
        cur = c.execute("select id,score,rating_count from owner_rating where model_id=? and source_id=? and source_aspect=? "
                        "and status='current' order by id desc limit 1", (mo, sid, op["aspect"])).fetchone()
        if cur and _same(cur[1], op["score"]) and cur[2] == op.get("rating_count"):
            return
        if cur:
            c.execute("update owner_rating set status='superseded' where id=?", (cur[0],))
            log.append(("owner_rating", cur[0], "update", "superseded"))
        rid = c.execute("insert into owner_rating(model_id,source_id,source_aspect,score,scale_max,rating_count,source_url,observed_at,"
                        "extraction_method,status) values (?,?,?,?,?,?,?,?,?, 'current')",
                        (mo, sid, op["aspect"], op["score"], op["scale_max"], op.get("rating_count"), op["url"],
                         op["observed_at"], op["method"])).lastrowid
        log.append(("owner_rating", rid, "insert", "%s.%s" % (op["model"], op["aspect"])))
    else:
        _need(op, "theme", "direction", "mentions", "posts_sampled", "sample_urls", "extracted_at", "method")
        urls = json.dumps(op["sample_urls"])
        cur = c.execute("select id,direction,mentions,posts_sampled,sample_urls,note,period from owner_theme where model_id=? and theme=? "
                        "and label is ? and source_id=?", (mo, op["theme"], op.get("label"), sid)).fetchone()
        if cur:
            if (cur[1], cur[2], cur[3], cur[4], cur[5], cur[6]) == (op["direction"], op["mentions"], op["posts_sampled"], urls,
                                                                    op.get("note"), op.get("period")):
                return
            c.execute("update owner_theme set direction=?,mentions=?,posts_sampled=?,sample_urls=?,note=?,period=?,extracted_at=?,"
                      "extraction_method=? where id=?", (op["direction"], op["mentions"], op["posts_sampled"], urls, op.get("note"),
                                                         op.get("period"), op["extracted_at"], op["method"], cur[0]))
            log.append(("owner_theme", cur[0], "update", "%s.%s" % (op["model"], op["theme"])))
            return
        rid = c.execute("insert into owner_theme(model_id,theme,label,direction,mentions,posts_sampled,period,sample_urls,note,source_id,"
                        "extracted_at,extraction_method) values (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (mo, op["theme"], op.get("label"), op["direction"], op["mentions"], op["posts_sampled"], op.get("period"),
                         urls, op.get("note"), sid, op["extracted_at"], op["method"])).lastrowid
        log.append(("owner_theme", rid, "insert", "%s.%s" % (op["model"], op["theme"])))
