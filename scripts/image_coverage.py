"""List catalogue models without a manifest image (data/image_manifest.csv), grouped by make.

A manifest row counts only if its file exists under static/car_images/.
Usage: python scripts/image_coverage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.catalogue import get_catalogue  # noqa: E402
from services.images import get_manifest  # noqa: E402


def missing_by_make() -> tuple[int, dict[str, list[str]]]:
    manifest = get_manifest()
    models = get_catalogue()[["make", "model"]].drop_duplicates().sort_values(["make", "model"])
    missing: dict[str, list[str]] = {}
    for make, model in models.itertuples(index=False):
        entry = manifest.get((make, model))
        if not entry or not (ROOT / "static" / "car_images" / entry["filename"]).exists():
            missing.setdefault(make, []).append(model)
    return len(models), missing


def main() -> int:
    total, missing = missing_by_make()
    n_missing = sum(len(v) for v in missing.values())
    print(f"{total - n_missing}/{total} models have a manifest image; {n_missing} without:")
    for make, models in missing.items():
        print(f"  {make} ({len(models)}): {', '.join(models)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
