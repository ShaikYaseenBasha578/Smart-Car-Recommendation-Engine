"""Reconciliation: turn the candidate values for one cell into a decision. Pure functions, no I/O.

Precedence (CLAUDE.md P1, P2 as amended by D5):
  1. OEM brochure. If brochure candidates agree with each other, their value wins. Aggregators that differ are
     logged as conflicts and recorded as rejected evidence.
  2. Aggregators. A value is accepted only when at least two different aggregators agree and none disagrees.
     One aggregator alone never decides (SINGLE_SOURCE -> the cell stays null and is flagged).
  3. Nothing else is used. No estimate, no inference from another variant or model, no model memory.

What happens to the decision depends on the row:
  new row        -> written when the decision is clear
  existing row   -> an aggregator-agreed value that differs from the KB, or fills a blank, goes to review (P2);
                    a value that agrees is recorded as confirming evidence; a brochure value that differs goes to
                    review as well (P7: one variant of a model is never corrected on its own)."""
from . import fields as F

OEM, AGG = "oem", "aggregator"


def agree(field, a, b, tol):
    """Same value for reconciliation purposes. Numbers may differ by rounding (relative `tol`); everything else is exact."""
    a, b = F.norm(field, a), F.norm(field, b)
    if a is None or b is None:
        return False
    if F.FIELDS[field][1] in ("num", "int") and field != "airbags" and field != "seating_capacity" and field != "drive_modes":
        if a == b:
            return True
        return abs(a - b) / max(abs(a), abs(b)) <= tol
    return a == b


def rel_gap(field, a, b):
    a, b = F.norm(field, a), F.norm(field, b)
    if F.FIELDS[field][1] in ("num", "int") and a is not None and b is not None and max(abs(a), abs(b)) > 0:
        return abs(a - b) / max(abs(a), abs(b))
    return None


def decide(field, candidates, cfg):
    """candidates: [{"source": name, "cls": "oem"|"aggregator", "value": v, "obs": key}], in source-precedence order.
    Returns {"status": VALUE|NULL, "value", "reason", "evidence": [...], "conflict": None|{...}}.
    reason: OEM_BROCHURE | AGGREGATOR_AGREED_UNVERIFIED | SINGLE_SOURCE | CONFLICT | OEM_CONFLICT | NO_SOURCE"""
    agree_tol = cfg.get("agree_tolerance", 0.01)
    high_tol = cfg["numeric_tolerance"]
    cands = [c for c in candidates if F.norm(field, c["value"]) is not None]
    if not cands:
        return {"status": "NULL", "value": None, "reason": "NO_SOURCE", "evidence": [], "conflict": None}

    def conflict(kind, winner=None):
        gaps = [rel_gap(field, x["value"], y["value"]) for i, x in enumerate(cands) for y in cands[i + 1:]]
        gaps = [g for g in gaps if g is not None]
        numeric = F.FIELDS[field][1] in ("num", "int") and field not in ("airbags", "seating_capacity", "drive_modes")
        high = (max(gaps) > high_tol) if (numeric and gaps) else True
        return {"field": field, "kind": kind, "high": bool(high), "resolved_value": winner,
                "values": [{"source": c["source"], "cls": c["cls"], "value": F.norm(field, c["value"])} for c in cands]}

    oem = [c for c in cands if c["cls"] == OEM]
    agg = [c for c in cands if c["cls"] == AGG]
    if oem:
        if all(agree(field, oem[0]["value"], c["value"], agree_tol) for c in oem[1:]):
            val = F.norm(field, oem[0]["value"])
            ev = [{"obs": oem[0]["obs"], "decision": "accepted", "value": val}]
            ev += [{"obs": c["obs"], "decision": "confirmed", "value": F.norm(field, c["value"])} for c in oem[1:]]
            differs = False
            for c in agg:
                ok = agree(field, val, c["value"], agree_tol)
                differs = differs or not ok
                ev.append({"obs": c["obs"], "decision": "confirmed" if ok else "rejected", "value": F.norm(field, c["value"])})
            return {"status": "VALUE", "value": val, "reason": "OEM_BROCHURE", "evidence": ev,
                    "conflict": conflict("oem_over_aggregator", val) if differs else None}
        return {"status": "NULL", "value": None, "reason": "OEM_CONFLICT", "evidence": [], "conflict": conflict("oem_vs_oem")}
    sources = []
    for c in agg:
        if c["source"] not in [s["source"] for s in sources]:
            sources.append(c)
    if len(sources) < 2:
        return {"status": "NULL", "value": None, "reason": "SINGLE_SOURCE", "evidence": [],
                "conflict": None, "single": {"source": sources[0]["source"], "value": F.norm(field, sources[0]["value"])}}
    first = sources[0]
    if all(agree(field, first["value"], c["value"], agree_tol) for c in sources[1:]):
        val = F.norm(field, first["value"])
        ev = [{"obs": first["obs"], "decision": "accepted", "value": val}]
        ev += [{"obs": c["obs"], "decision": "confirmed", "value": F.norm(field, c["value"])} for c in sources[1:]]
        return {"status": "VALUE", "value": val, "reason": "AGGREGATOR_AGREED_UNVERIFIED", "evidence": ev, "conflict": None}
    return {"status": "NULL", "value": None, "reason": "CONFLICT", "evidence": [], "conflict": conflict("aggregator_vs_aggregator")}


def route(decision, existing_row, existing_value, field, held=False, edition=False):
    """What to do with a decision. Returns one of:
    WRITE (new row, clear value) · CONFIRM (existing value agrees: add corroborating evidence only) ·
    REVIEW_CHANGE · REVIEW_FILL · REVIEW_CONFLICT · SKIP (nothing to do) · FLAG_NULL (stays null, reported)"""
    if edition:
        return "SKIP"
    if decision["status"] != "VALUE":
        if decision["conflict"] and decision["conflict"]["high"]:
            return "REVIEW_CONFLICT"
        return "FLAG_NULL" if (not existing_row or existing_value is None) else "SKIP"
    if not existing_row:
        return "WRITE"
    if existing_value is None:
        return "REVIEW_FILL"
    if agree(field, existing_value, decision["value"], 0.0) or F.same(field, existing_value, decision["value"]):
        return "SKIP" if held else "CONFIRM"
    return "REVIEW_CHANGE"
