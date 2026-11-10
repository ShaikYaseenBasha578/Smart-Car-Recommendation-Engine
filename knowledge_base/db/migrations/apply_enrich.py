"""Controlled write for one batch of the Claude-only enrichment loop (one brochure, in-scope variant cells).
Usage: apply_enrich.py <db> <phase> <cells.tsv>
cells.tsv columns: vid col old new pdf_rel pdf_sha1 page printed qualifier cls (old blank = NULL). Every cell was read from the cited
page by two independent headless Sonnet runs that agreed, and compared with the KB deterministically (see enrichment/enrich_batch.py).
The PDF's SHA-1 is checked against the file on disk before any write (P1). Shared body, invariants and idempotency: brochure_phase.run."""
import csv, hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from brochure_phase import run
OEM = "/Users/shaikyaseenbasha/Car_recommender_app/Flask Based App with Used Cars Function/knowledge_base/sources/oem/"
METHOD = ("two independent headless Sonnet runs on rendered page tiles plus page text agreed on this value; "
          "compared deterministically with the KB; no value taken from outside this page")


def num(col, v):
    if v == "": return None
    return float(v) if col.startswith("mileage") else int(float(v))


def main():
    db, phase, tsv = sys.argv[1:4]
    rows = list(csv.DictReader(open(tsv), delimiter="\t"))
    bro = {}
    for r in rows:
        h = hashlib.sha1(open(OEM + r["pdf_rel"], "rb").read()).hexdigest()
        assert h == r["pdf_sha1"], f"{r['pdf_rel']}: sha1 {h} != {r['pdf_sha1']}"
        bro[r["pdf_rel"]] = (r["pdf_rel"], h)
    cells = [dict(vid=int(r["vid"]), col=r["col"], old=num(r["col"], r["old"]), new=num(r["col"], r["new"]), bro=r["pdf_rel"], page=int(r["page"]),
                  printed=r["printed"], reason="OEM_BROCHURE_ENRICHMENT", release="*", method=METHOD, qualifier=r["qualifier"]) for r in rows]
    run(db, phase, bro, cells, quarantine_contradicted=True)


if __name__ == "__main__":
    main()
