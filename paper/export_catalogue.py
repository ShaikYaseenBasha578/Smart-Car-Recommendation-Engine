"""Export the frozen KB catalogue (mapped per paper/SPEC.md §9) to paper/data/catalogue_snapshot.csv.

Usage: python3 paper/export_catalogue.py
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oracle.feasibility import load_catalogue  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "catalogue_snapshot.csv")
COLUMNS = ("variant_id", "manufacturer", "model_id", "model", "variant_name", "full_name", "body_type", "fuel_raw",
           "fuel", "transmission_raw", "transmission", "seats", "price", "model_excluded")


def main():
    catalogue = load_catalogue()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in catalogue:
            w.writerow([("" if r[c] is None else int(r[c]) if c in ("price", "model_excluded") else r[c])
                        for c in COLUMNS])
    print(f"wrote {len(catalogue)} rows to {OUT}")


if __name__ == "__main__":
    main()
