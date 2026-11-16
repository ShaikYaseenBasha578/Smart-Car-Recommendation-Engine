"""Copy the four generated "project" pages into project_pages/ and point their links at the app's URLs.

    .venv/bin/python scripts/sync_project_pages.py --src <folder holding index.html, pipeline.html, kb.html, engine.html>

The pages are generated elsewhere and link to each other as index.html, pipeline.html, ... This script copies them
and rewrites only those href attributes (a #fragment is kept):

    index.html    -> /project
    pipeline.html -> /project/pipeline
    kb.html       -> /project/knowledge-base
    engine.html   -> /project/engine

Nothing else in a page is touched. Re-running with the same source gives byte-identical output (idempotent).
"""
import argparse
import re
import sys
from pathlib import Path

# source file name -> (served file name in project_pages/, public URL)
PAGES = {
    "index.html": ("index.html", "/project"),
    "pipeline.html": ("pipeline.html", "/project/pipeline"),
    "kb.html": ("kb.html", "/project/knowledge-base"),
    "engine.html": ("engine.html", "/project/engine"),
}
HREF = re.compile(r'(href=")(index|pipeline|kb|engine)\.html((?:#[^"]*)?")')
DEST = Path(__file__).resolve().parent.parent / "project_pages"


def rewrite(html):
    return HREF.sub(lambda m: m.group(1) + PAGES[m.group(2) + ".html"][1] + m.group(3), html)


def sync(src, dest=DEST):
    src, dest = Path(src), Path(dest)
    missing = [n for n in PAGES if not (src / n).is_file()]
    if missing:
        raise SystemExit("missing in %s: %s" % (src, ", ".join(missing)))
    dest.mkdir(parents=True, exist_ok=True)
    changed = []
    for name, (out, _url) in PAGES.items():
        text = rewrite((src / name).read_bytes().decode("utf-8")).encode("utf-8")
        target = dest / out
        if not target.exists() or target.read_bytes() != text:
            target.write_bytes(text)
            changed.append(out)
    return changed


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="folder with index.html, pipeline.html, kb.html, engine.html")
    args = ap.parse_args()
    done = sync(args.src)
    print("updated: " + ", ".join(done) if done else "already up to date")
    sys.exit(0)
