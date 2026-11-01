"""Build the homepage hero mosaic from the brochure images in data/image_manifest.csv.

Writes ~400px-wide WebP thumbnails to static/car_images/hero/ and the list the homepage reads,
static/hero_images.json ([{"src", "alt", "make", "model"}]). Only manifest images are used.

Needs Pillow (not a runtime dependency):  python scripts/build_hero_images.py
"""

import csv
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "image_manifest.csv"
SOURCE_DIR = ROOT / "static" / "car_images"
OUT_DIR = SOURCE_DIR / "hero"
OUT_JSON = ROOT / "static" / "hero_images.json"
WIDTH = 400
QUALITY = 68


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    entries = []
    for row in rows:
        source = SOURCE_DIR / row["filename"]
        if not source.is_file():
            print(f"skip (missing): {row['filename']}")
            continue
        target = OUT_DIR / (Path(row["filename"]).stem + ".webp")
        with Image.open(source) as im:
            im = im.convert("RGB")
            height = round(im.height * WIDTH / im.width)
            im.resize((WIDTH, height), Image.LANCZOS).save(target, "WEBP", quality=QUALITY, method=6)
        entries.append({
            "src": "/static/car_images/hero/" + target.name,
            "alt": f"{row['make']} {row['model']}",
            "make": row["make"],
            "model": row["model"],
        })

    OUT_JSON.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum((OUT_DIR / Path(e["src"]).name).stat().st_size for e in entries)
    print(f"{len(entries)} thumbnails, {total / 1024:.0f} KB total -> {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
