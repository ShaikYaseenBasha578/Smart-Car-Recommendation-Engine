"""Phase 10C-1: record the human verdicts in OEM_SPOTCHECK_SHEET.csv and summarise them.

The verdicts below are the reviewer's, transcribed as given. This script applies
no judgement of its own: rows not listed are CORRECT with true_value = extracted_value.
Reads no database. Run from the repo root, on the blank sheet from commit 1fa3ecf:
    git show 1fa3ecf:knowledge_base/reports/phase10c/OEM_SPOTCHECK_SHEET.csv > knowledge_base/reports/phase10c/OEM_SPOTCHECK_SHEET.csv
    python3 knowledge_base/reports/phase10c/fill_spotcheck_results.py
"""
import csv
import math
from collections import Counter

SHEET = "knowledge_base/reports/phase10c/OEM_SPOTCHECK_SHEET.csv"
RESULTS = "knowledge_base/reports/phase10c/OEM_SPOTCHECK_RESULTS.md"

SYM_TICK = "symbol_not_normalised: extracted 'Standard' for ✓"
SYM_DOT = "symbol_not_normalised: extracted '[Vector:Curve]' for ●"
GARBLED = "raw_name_garbled: table cells leaked into name"

# sheet row number (1-based, sheet order) -> (true_value or None for extracted_value, verdict, notes, error_type)
EXCEPTIONS = {
    9: ("1", "WRONG", SYM_TICK, "symbol_not_normalised"),
    12: ("1", "WRONG", SYM_TICK, "symbol_not_normalised"),
    24: ("1", "WRONG", "extractor read wireless row only; wired AA/CarPlay present", "value_wrong"),
    25: ("1", "WRONG", "same as #24", "value_wrong"),
    26: ("1", "WRONG", SYM_DOT + "; canonical False contradicts brochure", "symbol_not_normalised"),
    27: ("1", "WRONG", SYM_DOT, "symbol_not_normalised"),
    28: ("1", "WRONG", SYM_DOT, "symbol_not_normalised"),
    29: (None, "CORRECT", GARBLED, "raw_name_garbled"),
    30: (None, "CORRECT", GARBLED, "raw_name_garbled"),
    31: (None, "CORRECT", GARBLED, "raw_name_garbled"),
    32: (None, "CORRECT", "raw_name_garbled; ZX paddle shifters CVT-only, so 0 correct for MT", "raw_name_garbled"),
    40: (None, "CORRECT", "column_misresolution: value read from Alpha (O) column, filed under Alpha; values coincide",
         "column_misresolution"),
}
STRATA = ["CONFIRMED_SAMPLED", "REJECTED_WOULD_FLIP", "ACCEPTED"]
ERROR_TYPES = ["none", "symbol_not_normalised", "raw_name_garbled", "column_misresolution", "value_wrong"]


def wilson(k, n, z=1.959964):
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def main():
    with open(SHEET, newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = list(reader)
    assert len(rows) == 49
    assert all(not r["true_value"] and not r["verdict"] and not r["notes"] for r in rows), "sheet already filled"
    if "error_type" not in fields:
        fields.append("error_type")

    for i, r in enumerate(rows, 1):
        tv, verdict, notes, etype = EXCEPTIONS.get(i, (None, "CORRECT", "", "none"))
        r["true_value"] = r["extracted_value"] if tv is None else tv
        r["verdict"], r["notes"], r["error_type"] = verdict, notes, etype

    with open(SHEET, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)  # default \r\n, as in the original file
        w.writeheader()
        w.writerows(rows)

    lines = ["# Phase 10C-1: OEM brochure extraction spot-check — results", "",
             "Verdicts are the human reviewer's, checked against the brochure PDFs (aid: `spotcheck_aid/`). "
             "Transcribed into `OEM_SPOTCHECK_SHEET.csv` by `fill_spotcheck_results.py`; no DB was read or written.", "",
             "Reviewer confirmed on 2026-09-29 that all 49 rows were viewed. After a full pass, rows #24/#25 were added as "
             "exceptions and no others. Claude's independent second reading (`spotcheck_aid/claude_second_reading.csv`) "
             "agrees with the final `true_value` on 49/49 rows.", "",
             "Accuracy = rows with verdict `CORRECT` / rows in stratum (the extracted value matches the brochure). "
             "`error_type` is recorded independently of the verdict: a row can be `CORRECT` in value and still carry an error type "
             "(garbled raw name, wrong column that happens to hold the same value).", "",
             "## Accuracy by stratum", "",
             "| Stratum | n | CORRECT | WRONG | Accuracy | Wilson 95% CI |", "|---|---|---|---|---|---|"]
    for s in STRATA:
        sr = [r for r in rows if r["stratum"] == s]
        k = sum(r["verdict"] == "CORRECT" for r in sr)
        wrong = sum(r["verdict"] == "WRONG" for r in sr)
        ci = "{:.1%} – {:.1%}".format(*wilson(k, len(sr))) if s == "CONFIRMED_SAMPLED" else "—"
        lines.append(f"| {s} | {len(sr)} | {k} | {wrong} | {k / len(sr):.1%} ({k}/{len(sr)}) | {ci} |")
    k_all = sum(r["verdict"] == "CORRECT" for r in rows)
    lines += ["", f"All 49 rows: {k_all}/49 CORRECT. The strata were sampled differently (census of rejected rows, "
              "stratified sample of confirmed rows, single accepted row), so the pooled figure is not a population estimate.", "",
              "The CI is computed only for CONFIRMED_SAMPLED, the random sample (seed 20260928) of 104 confirmed rows. "
              "Wilson score interval, z = 1.96; no finite-population correction.", "",
              "## error_type counts", "",
              "| error_type | " + " | ".join(STRATA) + " | Total |", "|---|" + "---|" * (len(STRATA) + 1)]
    for e in ERROR_TYPES:
        per = [sum(r["error_type"] == e for r in rows if r["stratum"] == s) for s in STRATA]
        lines.append(f"| {e} | " + " | ".join(map(str, per)) + f" | {sum(per)} |")
    lines += ["", "## Non-`none` rows", "", "| # | provenance_id | stratum | variant | field | extracted | true | verdict | error_type |",
              "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        if r["error_type"] != "none":
            lines.append(f"| {i} | {r['provenance_id']} | {r['stratum']} | {r['model']} {r['variant_name']} | {r['field']} | "
                         f"`{r['extracted_value']}` | {r['true_value']} | {r['verdict']} | {r['error_type']} |")
    with open(RESULTS, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
