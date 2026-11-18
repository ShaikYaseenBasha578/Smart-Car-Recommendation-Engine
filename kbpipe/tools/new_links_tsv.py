"""List every CarWale-CarDekho link a run made for the NEW_MODEL items, for a blind check. Facts only: no verdict column.
  python -m kbpipe.tools.new_links_tsv <run folder> <out.tsv>
Reads the run's links.tsv and discovery.json; the variant page name (cached) is read offline to flag the page-name kWh spelling rule."""
import csv
import json
import os
import sys

from .. import config, extract, fetch
from ..sources import cardekho as cd

COLS = ["make", "model", "carwale_name", "carwale_url", "cardekho_name", "cardekho_url", "rule_used", "carwale_price", "cardekho_price"]


def main(run_dir, out):
    cfg = config.load()
    f = fetch.Fetcher(cfg, log=lambda *a: None, offline=True)
    new = {(i["make"], i["model"]) for i in json.load(open(os.path.join(run_dir, "discovery.json"))) if i["kind"] == "NEW_MODEL"}
    rows = []
    with open(os.path.join(run_dir, "links.tsv"), newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if (r["make"], r["model"]) not in new or not r["cardekho_url"]:
                continue
            rule = r["site_link_reason"]
            page, _ = f.get(r["cardekho_url"])
            pv = cd.parse_variant(page) if page else None
            if pv and extract._page_name(pv["name"]) != extract._page_name(r["cardekho"]):
                rule += "; page-name check allowance (page prints %r, list says %r)" % (pv["name"], r["cardekho"])
            rows.append([r["make"], r["model"], r["carwale"], r["carwale_url"], r["cardekho"], r["cardekho_url"], rule,
                         r["carwale_price"], r["cardekho_price"]])
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(COLS)
        w.writerows(rows)
    print("%d links" % len(rows))


if __name__ == "__main__":
    main(*sys.argv[1:3])
