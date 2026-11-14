"""Change-set: the only thing that modifies a KB file. A change-set is plain JSON, built by the pipeline and applied
identically to the staging copy and then to prod (P10). Applying it twice changes nothing.

{"run": "2026-11-13", "ts": "2026-11-13 10:00:00",
 "observations": {key: {"source", "raw_name", "payload", "url", "observed_at", "method"}},
 "ops": [
   {"op": "add_model", "make", "model", "body_type", "note"},
   {"op": "add_variant", "make", "model", "name", "full_name", "transmission", "drivetrain",
    "powertrain": {"fuel_type", "engine_cc", "power_bhp", "torque_nm"}},
   {"op": "cell", "make", "model", "variant", "field", "value", "expect_old", "reason",
    "evidence": [{"obs": key, "decision": "accepted|confirmed|rejected", "value": v}]},
   {"op": "discontinue", "make", "model", "variant", "reason", "evidence": [...]}
 ]}

Rules enforced here: no deletes, no DDL, editions are never written (P8), an existing value changes only when
`expect_old` names the value being replaced, and every change is returned in the log."""
import json
import sqlite3

from . import fields as F
from . import review_ops

ANY = "__ANY__"


class ApplyError(Exception):
    pass


def _one(c, q, *a):
    r = c.execute(q, a).fetchone()
    return r[0] if r else None


def _ids(c, op):
    mk = _one(c, "select id from manufacturer where name=?", op["make"])
    mo = _one(c, "select id from model where manufacturer_id=? and name=?", mk, op["model"]) if mk else None
    return mk, mo


def _variant(c, op):
    mk, mo = _ids(c, op)
    if mo is None:
        return None
    return _one(c, "select id from variant where model_id=? and name=?", mo, op["variant"] if "variant" in op else op["name"])


def _obs(c, cs, key, vid, log):
    o = cs["observations"][key]
    sid = _one(c, "select id from source where name=?", o["source"])
    if sid is None:
        raise ApplyError("unknown source %r" % o["source"])
    payload = o["payload"] if isinstance(o["payload"], str) else json.dumps(o["payload"], sort_keys=True)
    oid = _one(c, "select id from source_observation where source_id=? and resolved_variant_id=? and source_url=? "
                  "and raw_name=? and extraction_method=? and raw_payload=?", sid, vid, o["url"], o["raw_name"], o["method"], payload)
    if oid is None:
        if not (o.get("url") and o.get("observed_at") and o.get("method")):
            raise ApplyError("observation %s lacks url, date or method" % key)
        oid = c.execute("insert into source_observation(source_id,raw_name,raw_payload,source_url,observed_at,extraction_method,"
                        "resolved_variant_id,resolution_status) values (?,?,?,?,?,?,?,'resolved')",
                        (sid, o["raw_name"], payload, o["url"], o["observed_at"], o["method"], vid)).lastrowid
        log.append(("source_observation", oid, "insert", key))
    return oid


def _provenance(c, cs, op, vid, log):
    for ev in op.get("evidence") or []:
        oid = _obs(c, cs, ev["obs"], vid, log)
        if _one(c, "select id from field_provenance where variant_id=? and field_name=? and source_observation_id=?",
                vid, op["field"], oid) is None:
            val = ev.get("value", op.get("value"))
            pid = c.execute("insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision,"
                            "decision_reason,decided_at) values (?,?,?,?,?,?,?)",
                            (vid, op["field"], None if val is None else str(val), oid, ev["decision"], op["reason"], cs["ts"])).lastrowid
            log.append(("field_provenance", pid, "insert", "%s.%s" % (vid, op["field"])))


def _powertrain(c, mo, pt, log):
    row = c.execute("select id from powertrain where model_id=? and fuel_type=? and engine_cc is ? and power_bhp is ?",
                    (mo, pt["fuel_type"], pt.get("engine_cc"), pt.get("power_bhp"))).fetchone()
    if row:
        return row[0]
    desc = " ".join(x for x in ["%dcc" % pt["engine_cc"] if pt.get("engine_cc") else "",
                                "%sbhp" % pt["power_bhp"] if pt.get("power_bhp") else "", pt["fuel_type"]] if x)
    pid = c.execute("insert into powertrain(model_id,fuel_type,engine_cc,power_bhp,torque_nm,description) values (?,?,?,?,?,?)",
                    (mo, pt["fuel_type"], pt.get("engine_cc"), pt.get("power_bhp"), pt.get("torque_nm"), desc)).lastrowid
    log.append(("powertrain", pid, "insert", desc))
    return pid


def apply(db_path, cs, check=None):
    """Apply in ONE transaction with foreign keys on. `check(conn, log)` runs before COMMIT and may raise to roll back.
    Returns the log: [(table, rowid, action, detail)]."""
    c = sqlite3.connect(db_path, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    log = []
    c.execute("BEGIN IMMEDIATE")
    try:
        for op in cs["ops"]:
            kind = op["op"]
            if kind == "add_model":
                mk, mo = _ids(c, op)
                if mk is None:
                    raise ApplyError("make %r is not in the KB (out of scope)" % op["make"])
                if mo is None:
                    if op.get("body_type") not in F.BODY_TYPES:
                        raise ApplyError("body type %r for %s" % (op.get("body_type"), op["model"]))
                    mo = c.execute("insert into model(manufacturer_id,name,body_type) values (?,?,?)",
                                   (mk, op["model"], op["body_type"])).lastrowid
                    log.append(("model", mo, "insert", op["model"]))
                    gid = c.execute("insert into generation(model_id,name,verification_status,notes) values (?,?,'unverified',?)",
                                    (mo, "Gen 1 (kbpipe)", op.get("note") or "Created by kbpipe; generation data unverified.")).lastrowid
                    log.append(("generation", gid, "insert", op["model"]))
            elif kind == "add_variant":
                mk, mo = _ids(c, op)
                if mo is None:
                    raise ApplyError("model %s %s missing for variant %s" % (op["make"], op["model"], op["name"]))
                if _variant(c, op) is None:
                    if op["transmission"] not in F.TRANSMISSIONS:
                        raise ApplyError("transmission %r" % op["transmission"])
                    gid = _one(c, "select min(id) from generation where model_id=?", mo)
                    pid = _powertrain(c, mo, op["powertrain"], log)
                    vid = c.execute("insert into variant(model_id,generation_id,powertrain_id,name,full_name,transmission,drivetrain,"
                                    "created_at,updated_at) values (?,?,?,?,?,?,?,?,?)",
                                    (mo, gid, pid, op["name"], op["full_name"], op["transmission"], op.get("drivetrain"),
                                     cs["ts"], cs["ts"])).lastrowid
                    log.append(("variant", vid, "insert", op["full_name"]))
            elif kind == "cell":
                vid = _variant(c, op)
                if vid is None:
                    raise ApplyError("variant not found: %s %s %s" % (op["make"], op["model"], op["variant"]))
                field = op["field"]
                if field not in F.FIELDS:
                    raise ApplyError("unknown field %s" % field)
                if not F.in_range(field, op["value"]):
                    raise ApplyError("%s=%r is outside the allowed range" % (field, op["value"]))
                if F.FIELDS[field][0] == "variant":
                    if _one(c, "select base_variant_id from variant where id=?", vid) is not None:
                        raise ApplyError("variant %s is an edition; editions are never written (P8)" % vid)
                    cur = _one(c, 'select "%s" from variant where id=?' % field, vid)
                    if not F.same(field, cur, op["value"]):
                        exp = op.get("expect_old")
                        if exp != ANY and not F.same(field, cur, exp):
                            raise ApplyError("%s.%s: expected %r, found %r" % (vid, field, exp, cur))
                        val = F.norm(field, op["value"])
                        if field == "sunroof":
                            val = "True" if val == 1 else "False"   # the column is TEXT; this is the KB's majority spelling
                        c.execute('update variant set "%s"=?, updated_at=? where id=?' % field, (val, cs["ts"], vid))
                        log.append(("variant", vid, "update", field))
                        if cur is not None:
                            aid = c.execute("insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,"
                                            "reason_code,phase,created_at) values ('variant',?,?,?,?,?,?,?)",
                                            (vid, field, str(cur), str(val), op["reason"], "kbpipe-" + cs["run"], cs["ts"])).lastrowid
                            log.append(("evidence_amendment", aid, "insert", "%s.%s" % (vid, field)))
                else:
                    # powertrain fields: the value lives on the powertrain row made by add_variant; only provenance is added
                    cur = _one(c, 'select p."%s" from variant v join powertrain p on p.id=v.powertrain_id where v.id=?' % field, vid)
                    if not F.same(field, cur, op["value"]):
                        continue      # the variant sits on an existing powertrain row with another value: no evidence is attached
                _provenance(c, cs, op, vid, log)
            elif kind == "discontinue":
                vid = _variant(c, op)
                if vid is None:
                    raise ApplyError("variant not found: %s" % op.get("variant"))
                if _one(c, "select is_discontinued from variant where id=?", vid) != 1:
                    c.execute("update variant set is_discontinued=1, updated_at=? where id=?", (cs["ts"], vid))
                    log.append(("variant", vid, "update", "is_discontinued"))
                    aid = c.execute("insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,"
                                    "phase,created_at) values ('variant',?,'is_discontinued','0','1',?,?,?)",
                                    (vid, op["reason"], "kbpipe-" + cs["run"], cs["ts"])).lastrowid
                    log.append(("evidence_amendment", aid, "insert", "%s.is_discontinued" % vid))
                for ev in op.get("evidence") or []:
                    _obs(c, cs, ev["obs"], vid, log)
            elif kind in review_ops.REVIEW_OPS:
                try:
                    review_ops.apply_op(c, cs, op, log)
                except review_ops.ReviewApplyError as e:
                    raise ApplyError(str(e))
            else:
                raise ApplyError("unknown op %r" % kind)
        if check:
            check(c, log)
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        c.close()
        raise
    c.close()
    return log
