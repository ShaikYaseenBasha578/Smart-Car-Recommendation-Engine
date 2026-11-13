"""Stage 3 glue: reconcile every cell of a model and sort the outcome into
  ops      -> the change-set (clear items, applied when the gates pass)
  review   -> items that wait for the owner (REVIEW_<date>.md / pending.json)
  conflicts-> every disagreement between sources, resolved or not
  flags    -> cells left null and why
Nothing here touches a database."""
import hashlib
import json

from . import fields as F
from . import match
from . import reconcile as R
from .sources import common as c

ORDER = ["fuel_type", "transmission"] + [f for f in F.FIELDS if f not in ("fuel_type", "transmission")]


def okey(obs):
    return hashlib.sha256(json.dumps([obs["source"], obs["url"], obs["raw_name"], obs["method"]], sort_keys=True).encode()).hexdigest()[:20]


def _cands(v, field, obs):
    out = []
    for tag, src in (("cw", "carwale"), ("cd", "cardekho")):
        fl = v.get("fields_" + tag)
        if fl and fl.get(field) is not None:
            k = okey(v["obs_" + tag])
            obs[k] = v["obs_" + tag]
            out.append({"source": src, "cls": R.AGG, "value": fl[field], "obs": k})
    for b in v.get("brochure") or []:
        if b["field"] == field:
            k = okey(b["obs"])
            obs[k] = b["obs"]
            out.append({"source": "oem", "cls": R.OEM, "value": b["value"], "obs": k})
    return out


def kb_variants(conn, model_id):
    rows = conn.execute("select v.*, p.fuel_type, p.engine_cc, p.power_bhp, p.torque_nm from variant v "
                        "left join powertrain p on p.id=v.powertrain_id where v.model_id=?", (model_id,)).fetchall()
    return [dict(r) for r in rows]


def plan_model(item, bundle, conn, cfg, P):
    """Append to P = {"obs": {}, "ops": [], "review": [], "conflicts": [], "flags": [], "stats": Counter-like dict}."""
    make, model = item["make"], item["model"]
    new_model = not item["in_kb"]
    held = model in cfg["held_models"] or bool(item.get("facelift"))
    kbv = kb_variants(conn, item["kb_model_id"]) if item["in_kb"] else []
    live = [x for x in kbv if x["base_variant_id"] is None]
    for x in live:
        x["_t"] = {"name": x["name"], "fuel": x["fuel_type"], "transmission": x["transmission"],
                   "price": x["price_ex_showroom"], "engine_cc": x["engine_cc"]}
    matched, model_ops, new_variants = set(), [], 0
    st = P["stats"]

    def bump(k, n=1):
        st[k] = st.get(k, 0) + n

    def log_conflict(v, d, kb_value=None, resolution=None):
        cf = dict(d["conflict"])
        cf.update({"make": make, "model": model, "variant": v["name"], "kb_value": kb_value,
                   "resolution": resolution or ("precedence: brochure" if cf["kind"] == "oem_over_aggregator" else "left null")})
        P["conflicts"].append(cf)

    for v in bundle["versions"]:
        if v["special"]:
            bump("editions_skipped")
            continue
        f = v["fields_cw"]
        tgt = {"name": v["name"], "fuel": f.get("fuel_type"), "transmission": f.get("transmission"),
               "price": f.get("price_ex_showroom"), "engine_cc": f.get("engine_cc")}
        hit = None
        if live:
            hit, why = match.link(tgt, [x["_t"] for x in live if x["id"] not in matched], make + " " + model)
            hit = next((x for x in live if hit is not None and x["_t"] is hit), None)
        dec = {fld: R.decide(fld, _cands(v, fld, P["obs"]), cfg) for fld in ORDER}
        P["links"].append({"make": make, "model": model, "carwale": v["name"], "carwale_fuel": f.get("fuel_type"),
                           "carwale_gearbox": f.get("transmission"), "carwale_price": f.get("price_ex_showroom"),
                           "cardekho": v.get("cd_name") or "", "cardekho_price": (v.get("fields_cd") or {}).get("price_ex_showroom"),
                           "cardekho_fuel": (v.get("fields_cd") or {}).get("fuel_type"),
                           "cardekho_gearbox": (v.get("fields_cd") or {}).get("transmission"),
                           "kb_variant": hit["name"] if hit else "", "kb_variant_id": hit["id"] if hit else "",
                           "kb_fuel": hit["fuel_type"] if hit else "", "kb_gearbox": hit["transmission"] if hit else "",
                           "site_link_reason": v["link_reason"]})
        if hit:                                                   # ---- variant already in the KB
            matched.add(hit["id"])
            bump("variants_matched")
            for fld in ORDER:
                d = dec[fld]
                cur = hit.get(fld)
                rt = R.route(d, True, cur, fld, held=False)
                if d["conflict"]:
                    log_conflict(v, d, cur)
                if rt == "CONFIRM":
                    model_ops.append({"op": "cell", "make": make, "model": model, "variant": hit["name"], "field": fld,
                                      "value": F.norm(fld, cur), "expect_old": F.norm(fld, cur), "reason": "AGGREGATORS_CONFIRM",
                                      "evidence": [dict(e, decision="confirmed") for e in d["evidence"]]})
                    bump("cells_confirmed")
                elif rt in ("REVIEW_CHANGE", "REVIEW_FILL"):
                    if F.FIELDS[fld][0] == "powertrain":
                        bump("powertrain_differences")
                        P["flags"].append({"make": make, "model": model, "variant": hit["name"], "field": fld,
                                           "why": "POWERTRAIN_DIFFERS", "kb": cur, "sources": d["value"]})
                        continue
                    P["_rev"].setdefault((make, model, fld, rt), []).append(
                        {"variant": hit["name"], "variant_id": hit["id"], "old": F.norm(fld, cur), "new": d["value"],
                         "reason": d["reason"], "evidence": d["evidence"]})
                    bump("cells_for_review")
                elif rt == "REVIEW_CONFLICT":
                    bump("high_conflicts")
            continue
        # ---- variant not in the KB
        idf, idt = dec["fuel_type"], dec["transmission"]
        if idf["status"] != "VALUE" or idt["status"] != "VALUE":
            why = "only one site lists it" if not v.get("fields_cd") else "the sites disagree on fuel or gearbox"
            P["flags"].append({"make": make, "model": model, "variant": v["name"], "field": "*", "why": "VARIANT_NOT_ADDED",
                               "detail": "%s (%s)" % (why, v["link_reason"])})
            bump("variants_not_added")
            for fld in ("fuel_type", "transmission"):
                if dec[fld]["conflict"]:
                    log_conflict(v, dec[fld])
            continue
        clash = [x for x in live if match.identity(x["name"], make + " " + model, x["fuel_type"], x["transmission"]) ==
                 match.identity(v["name"], make + " " + model, f.get("fuel_type"), f.get("transmission"))]
        ops = [{"op": "add_variant", "make": make, "model": model, "name": v["name"],
                "full_name": "%s %s %s" % (make, model, v["name"]), "transmission": idt["value"],
                "drivetrain": dec["drivetrain"]["value"] if dec["drivetrain"]["status"] == "VALUE" else None,
                "powertrain": {"fuel_type": idf["value"],
                               "engine_cc": dec["engine_cc"]["value"] if dec["engine_cc"]["status"] == "VALUE" else None,
                               "power_bhp": dec["power_bhp"]["value"] if dec["power_bhp"]["status"] == "VALUE" else None,
                               "torque_nm": dec["torque_nm"]["value"] if dec["torque_nm"]["status"] == "VALUE" else None}}]
        ncell = 0
        for fld in ORDER:
            d = dec[fld]
            if d["conflict"]:
                log_conflict(v, d)
            if d["status"] == "VALUE":
                ops.append({"op": "cell", "make": make, "model": model, "variant": v["name"], "field": fld, "value": d["value"],
                            "expect_old": d["value"] if fld in ("transmission", "drivetrain") else None,
                            "reason": d["reason"], "evidence": d["evidence"]})
                ncell += 1
            else:
                P["flags"].append({"make": make, "model": model, "variant": v["name"], "field": fld, "why": d["reason"],
                                   "detail": (d.get("single") or {}).get("source") or ""})
                bump("cells_null_" + d["reason"])
        if new_model or not (held or clash):
            model_ops += ops
            new_variants += 1
            bump("variants_added")
            bump("cells_written", ncell)
        else:
            why = ("model is held (catalogue currency, P7)" if held else
                   "the KB already has %r with the same trim, fuel and gearbox: renamed, or a new variant?" % clash[0]["name"])
            P["review"].append({"kind": "NEW_VARIANT", "make": make, "model": model, "title": "%s %s: add variant %r?" % (make, model, v["name"]),
                                "why": why, "impact": 1, "ops": ops, "default": "hold"})
            bump("variants_for_review")
    if new_model:
        if new_variants:
            note = "Created by kbpipe %s from CarWale and CarDekho listings; launch date per CarWale: %s." % (P["run"], bundle.get("launched"))
            P["ops"].append({"op": "add_model", "make": make, "model": model, "body_type": item["body_type"], "note": note})
            bump("models_added")
        else:
            P["review"].append({"kind": "MODEL_NOT_ADDED", "make": make, "model": model, "impact": 50,
                                "title": "%s %s is on sale but no variant could be added" % (make, model),
                                "why": "; ".join(sorted({x.get("detail", "") for x in P["flags"] if x["model"] == model and x["why"] == "VARIANT_NOT_ADDED"}))[:400]
                                       or "; ".join(bundle["problems"])[:400], "ops": [], "default": "hold"})
    P["ops"] += model_ops
    gone = [x for x in live if x["id"] not in matched and not x["is_discontinued"]]
    if gone and bundle["versions"]:
        P["review"].append({"kind": "VARIANTS_NOT_LISTED", "make": make, "model": model, "impact": len(gone),
                            "title": "%s %s: %d KB variants are not in the current listing" % (make, model, len(gone)),
                            "why": "Not linked to any current CarWale version: discontinued, or renamed. " + "; ".join(x["name"] for x in gone)[:600],
                            "ops": [{"op": "discontinue", "make": make, "model": model, "variant": x["name"],
                                     "reason": "NOT_IN_CURRENT_LISTING", "evidence": []} for x in gone],
                            "default": "hold"})
        bump("kb_variants_not_listed", len(gone))


def finish(P):
    """Fold per-cell review rows into one item per (model, field, kind) so the review stays short."""
    for (make, model, fld, rt), rows in sorted(P.pop("_rev").items()):
        kind = "PRICE_CHANGE" if fld == "price_ex_showroom" and rt == "REVIEW_CHANGE" else ("VALUE_CHANGE" if rt == "REVIEW_CHANGE" else "FILL_BLANK")
        ex = "; ".join("%s: %s -> %s" % (r["variant"], r["old"], r["new"]) for r in rows[:4])
        P["review"].append({
            "kind": kind, "make": make, "model": model, "field": fld, "impact": len(rows),
            "title": "%s %s: %s on %d variant(s) %s" % (make, model, fld, len(rows),
                                                         "differs from the KB" if rt == "REVIEW_CHANGE" else "can be filled"),
            "why": "Both sites agree with each other. Examples: " + ex, "default": "hold",
            "ops": [{"op": "cell", "make": make, "model": model, "variant": r["variant"], "field": fld, "value": r["new"],
                     "expect_old": r["old"], "reason": "AGGREGATOR_AGREED_OWNER_APPROVED", "evidence": r["evidence"]} for r in rows]})
    for i, r in enumerate(sorted(P["review"], key=lambda r: (-r["impact"], r["make"], r["model"], r["kind"]))):
        r["id"] = "R%03d" % (i + 1)
    P["review"].sort(key=lambda r: r["id"])
    return P


def new():
    return {"obs": {}, "ops": [], "review": [], "conflicts": [], "flags": [], "stats": {}, "_rev": {}, "run": None, "links": []}
