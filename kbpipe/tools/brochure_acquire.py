"""Download official brochure PDFs for models listed in kbpipe/data/brochure_urls_new_models.json into oem_new_dir
(never sources/oem). Polite: robots.txt obeyed, one attempt per URL, no retry around a block. Records URL, date, SHA-1 in
oem_new_dir/brochure_manifest.json. Existing downloads are not fetched again.

  python -m kbpipe.tools.brochure_acquire [--only "Tata Motors/Punch" ...]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from kbpipe import brochure, config, fetch  # noqa: E402

URLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "brochure_urls_new_models.json")


def robots_allows(f, url):
    """robots.txt obeyed. A host that answers 404 for /robots.txt has published no rules (standard reading: allowed); any other
    failure to read it (403, timeout) fails closed."""
    if f.robots_ok(url):
        return True
    scheme_host = "/".join(url.split("/")[:3])
    if f._robots_cache.get(scheme_host) is None:
        seen = []
        old = f.log
        f.log = lambda *x: seen.append(" ".join(str(i) for i in x))
        f._robots_cache.pop(scheme_host, None)
        f.get(scheme_host + "/robots.txt", max_age_days=1)
        f.log = old
        return any("HTTP 404" in x for x in seen) and not f.meta(scheme_host + "/robots.txt")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append")
    a = ap.parse_args()
    cfg = config.load()
    f = fetch.Fetcher(cfg, log=lambda *x: print("   ", *x))
    f.retries = 0
    urls = {k: v for k, v in json.load(open(URLS)).items() if not k.startswith("_")}
    man = brochure._load_json(os.path.join(cfg["oem_new_dir"], "brochure_manifest.json"), {})
    report = {}
    for key, lst in sorted(urls.items()):
        if a.only and key not in a.only:
            continue
        make, model = key.split("/", 1)
        item = {"make": make, "model": model}
        for n, (url, found_on) in enumerate(lst):
            mkey = key if n == 0 else "%s|%d" % (key, n + 1)
            if mkey in man and man[mkey]["url"] == url and os.path.exists(os.path.join(cfg["oem_new_dir"], man[mkey]["path"])):
                report[mkey] = "already downloaded"
                continue
            if not robots_allows(f, url):
                report[mkey] = "robots.txt disallows (or unreadable: 403/5xx)"
                print(mkey, report[mkey])
                continue
            body, meta = f.get(url, binary=True)
            if not body:
                report[mkey] = "not fetched (blocked or error)"
                print(mkey, report[mkey])
                continue
            if not body.startswith(b"%PDF"):
                report[mkey] = "not a PDF"
                print(mkey, report[mkey])
                continue
            got = brochure.store_new(item, url, body, meta, cfg, lambda s, m: print("   ", m), key=mkey)
            report[mkey] = ("ok " + got[0]["sha1"][:10]) if got else "rejected (no text layer or model name absent)"
            print(mkey, report[mkey])
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
