"""Regression for linker changes. Offline: cached pages only, no network, no KB, no model.

  run      re-runs extract.model_bundle for the discovery items of the given kinds and records, per CarWale version, the CarDekho
           address and the reason it linked to (or None). Run it once per package tree: the old one
           (`git archive <commit> kbpipe | tar -x -C <dir>`) and this tree.
  compare  old.json vs new.json: pairs identical, changed (must be 0), and pairs that are new (unlinked before, linked now).

  python kbpipe/tools/link_regression.py run <dir containing kbpipe/> <discovery.json> EXISTING,NEW_MODEL <out.json>
  python kbpipe/tools/link_regression.py compare <old.json> <new.json> [new_pairs.tsv]
"""
import json
import sys


def run(root, disc, kinds, out):
    sys.path.insert(0, root)
    import kbpipe
    from kbpipe import config, extract, fetch, match
    assert kbpipe.__file__.startswith(root), kbpipe.__file__
    cfg = config.load()
    f = fetch.Fetcher(cfg, log=lambda *a: None, offline=True)
    orig, calls = match.link, []

    def wrap(target, cands, model, *a, **kw):
        hit, why = orig(target, cands, model, *a, **kw)
        calls.append((target["name"], kw.get("tier", 0), hit["url"] if hit else None, why, hit["name"] if hit else None))
        return hit, why
    match.link = wrap
    res = {}
    for it in json.load(open(disc)):
        if it.get("kind") not in kinds.split(","):
            continue
        del calls[:]
        b = extract.model_bundle(it, cfg, f, lambda *a: None, {})
        rows = []                                    # one row per CarWale version, in listing order: [name, url, reason, cardekho name, tier]
        for name, tier, url, why, cdname in calls:
            if tier == 0:
                rows.append([name, url, why, cdname, 0])
            elif url:
                for r in rows:
                    if r[0] == name and r[1] is None:
                        r[1:] = [url, why, cdname, tier]
                        break
        res["%s/%s" % (it["make"], it["model"])] = {"versions": len(b["versions"]), "pairs": rows, "problems": b["problems"]}
    json.dump(res, open(out, "w"), indent=1)
    print("%d models, %d versions" % (len(res), sum(len(v["pairs"]) for v in res.values())))


def compare(old, new, out=None):
    o, n = json.load(open(old)), json.load(open(new))
    tot = same = 0
    changed, fresh = [], []
    for k in o:
        assert len(o[k]["pairs"]) == len(n[k]["pairs"]), k
        for a, b in zip(o[k]["pairs"], n[k]["pairs"]):
            assert a[0] == b[0]
            tot += 1
            if a[1] == b[1] and (a[1] is None or a[2] == b[2]):
                same += 1
            elif a[1] is None:
                fresh.append((k, b))
            else:
                changed.append((k, a, b))
    linked_old = sum(1 for k in o for a in o[k]["pairs"] if a[1])
    print("pairs %d, identical %d, changed %d, new %d; linked before %d" % (tot, same, len(changed), len(fresh), linked_old))
    for x in changed:
        print("CHANGED", x)
    if out:
        with open(out, "w") as f:
            f.write("model\tcarwale_name\tcardekho_name\tcardekho_url\treason\ttier\n")
            for k, b in fresh:
                f.write("\t".join([k, b[0], b[3] or "", b[1], b[2], str(b[4])]) + "\n")
    return tot, same, changed, fresh


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(*sys.argv[2:6])
    else:
        compare(*sys.argv[2:5])
