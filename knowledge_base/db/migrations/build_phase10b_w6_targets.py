"""Phase 10B W6 target builder: derive canonical-cell corrections from the human-verified OEM spot-check sheet.

Reads ONLY knowledge_base/reports/phase10c/OEM_SPOTCHECK_SHEET.csv (true_value = the reviewer's verdict, commit b84444c)
and the page anchors of the verification aid (spotcheck_aid/index.html). No DB access; no value is re-judged.
A target is a sheet row whose normalised true_value differs from the normalised current_canonical_value.
Usage (repo root): python3 knowledge_base/db/migrations/build_phase10b_w6_targets.py
Writes knowledge_base/db/migrations/phase10b_w6_targets.csv (applied) and phase10b_w6_held.csv (held, with reason)
"""
import csv
import re
import sys

SHEET = "knowledge_base/reports/phase10c/OEM_SPOTCHECK_SHEET.csv"
AID = "knowledge_base/reports/phase10c/spotcheck_aid/index.html"
OUT = "knowledge_base/db/migrations/phase10b_w6_targets.csv"
HELD_OUT = "knowledge_base/db/migrations/phase10b_w6_held.csv"
EXPECTED_DERIVED, EXPECTED = 22, 12
# Owner decision 2026-09-29: cells whose brochure post-dates a model update that the V6 rows predate are held out of
# W6 and logged under CATALOG_CURRENCY (the KB has no model-year dimension). Kylaq rows 17-23 are applied: its update
# only added a Sportline variant; existing trims are unchanged.
HOLD = {
    **{n: "CATALOG_CURRENCY: Brezza V6 rows observed 2026-06-22, pre-July-2026 update; brochure 2026-07-27 is post-update"
       for n in (5, 6, 7, 8, 10, 11, 13, 14, 15)},
    4: "CATALOG_CURRENCY: Baleno V6 rows observed 2026-06-22, pre-facelift; brochure 2026-09-05 is post-facelift",
}
REASON = "OEM_SPOTCHECK_VERIFIED"

TRUE = {"1", "✓", "●", "■", "standard", "true"}
FALSE = {"0", "–", "-", "false"}
# Storage convention per column: sunroof is TEXT holding 'True'/'False' (809 of 818 non-null rows); the rest are INTEGER 0/1.
TEXT_BOOL = {"sunroof": ("True", "False")}


def norm(v):
    s = v.strip().lower()
    if s in TRUE:
        return 1
    if s in FALSE:
        return 0
    raise ValueError(f"unnormalisable value {v!r}")


def main():
    rows = list(csv.DictReader(open(SHEET, newline="")))
    assert len(rows) == 49 and all(r["verdict"] for r in rows), "sheet not fully verified"
    html = open(AID).read()
    # page per card: the '#page=N' link inside <section id="rowK">
    pages = {}
    for sec in re.findall(r'<section class="card[^"]*" id="row(\d+)">(.*?)</section>', html, re.S):
        m = re.search(r"#page=(\d+)", sec[1])
        pages[int(sec[0])] = int(m.group(1)) if m else None

    out, held = [], []
    for i, r in enumerate(rows, 1):
        t, c = norm(r["true_value"]), norm(r["current_canonical_value"])
        if t == c:
            continue
        f = r["field"]
        new = TEXT_BOOL[f][0 if t else 1] if f in TEXT_BOOL else str(t)
        (held if i in HOLD else out).append({
            "sheet_row": i, "provenance_id": r["provenance_id"], "stratum": r["stratum"], "verdict": r["verdict"],
            "model": r["model"], "variant_id": r["variant_id"], "variant_name": r["variant_name"], "column": f,
            "expected_old": r["current_canonical_value"], "true_value": r["true_value"], "new_value": new,
            "page": pages.get(i), "reason_code": REASON,
            "note": f"provenance_id={r['provenance_id']}; sheet_row={i}; human-verified against brochure p.{pages.get(i)} (page located by verification aid)",
        })
        if i in HOLD:
            held[-1]["hold_reason"] = HOLD[i]
    assert sorted(h["sheet_row"] for h in held) == sorted(HOLD), "hold list does not match derived targets"
    with open(HELD_OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(held[0]))
        w.writeheader()
        w.writerows(held)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for o in out:
        print(o["sheet_row"], o["provenance_id"], o["variant_id"], o["column"], o["expected_old"], "->", o["new_value"], "p.", o["page"])
    print(f"derived={len(out) + len(held)} held={len(held)} targets={len(out)}")
    if len(out) + len(held) != EXPECTED_DERIVED or len(out) != EXPECTED:
        sys.exit(f"STOP: expected {EXPECTED_DERIVED} derived / {EXPECTED} applied")


if __name__ == "__main__":
    main()
