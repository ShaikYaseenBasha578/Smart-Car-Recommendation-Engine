"""Export the KB review layers as the two flat files the v3 engine reads.

    python scripts/export_reviews_from_kb.py --db /tmp/carrec_audit/prod/export_copy.db [--out-dir data]

  data/assessments.csv    expert scores (professional_assessment, status = 'current')
      model, aspect, value, source, url, published_on, n_sources, raw_score, scale_max, source_aspect
  data/owner_ratings.csv  owner scores (owner_rating, status = 'current')
      model, aspect, value, rating_count, low_confidence, source, url, observed_at, raw_score, scale_max,
      source_aspect

`aspect` is the engine's aspect; `value` = raw_score / scale_max in [0, 1]. A source label can feed several engine
aspects (one output row each). Labels live in ONE table, LABEL_MAP below; a label that is not in the table makes the
export fail loudly (so a new label on the source site is noticed, not silently dropped).

--db must be a COPY of the KB (never the production file); a WAL-mode file is opened from a temporary copy, nothing is
created beside it. Model names come from model.name, the same source as scripts/export_catalogue_from_kb.py.
Output is sorted, so running twice gives byte-identical files.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------------------------------------------
# THE mapping table: (kind, source label) -> engine aspects. kind: "expert" (assessments.csv) or "owner"
# (owner_ratings.csv). An aspect listed in UNUSED_IN_SCORING is exported but the engine does not score it.
# ---------------------------------------------------------------------------------------------------------------
LABEL_MAP: dict[tuple[str, str], list[str]] = {
    # Autocar India (scale 10)
    ("expert", "Performance And Refinement"): ["engine_performance", "refinement"],
    ("expert", "Ride Comfort And Handling"): ["ride_comfort", "handling"],
    ("expert", "Interior Space And Comfort"): ["front_space", "rear_seat_comfort"],
    ("expert", "Mileage / Range And Efficiency"): ["real_world_mileage"],
    ("expert", "Features And Safety"): ["features_tech"],
    ("expert", "Value For Money"): ["value_for_money"],
    ("expert", "Exterior Design And Engineering"): ["build_quality"],
    ("expert", "overall"): ["overall"],  # kept in the file; the engine uses it only as a low-weight fallback
    # CarWale owner ratings (scale 5)
    ("owner", "After Sales Cost and Experience"): ["service_cost", "service_experience"],
    ("owner", "Comfort and Space"): ["comfort"],
    ("owner", "Performance"): ["performance"],
    ("owner", "Fuel Economy"): ["real_world_mileage"],
    ("owner", "Value for Money"): ["value"],
    ("owner", "Features and Technology"): ["features"],
    ("owner", "overall"): ["satisfaction"],
    ("owner", "Design and Styling"): ["design"],
}
UNUSED_IN_SCORING = {"design"}

# KB source.name -> the short name shown in explanations
SOURCE_DISPLAY = {"Autocar India expert review": "Autocar India", "CarWale user ratings": "CarWale"}

LOW_CONFIDENCE_BELOW = 30  # rating_count under this is flagged

ASSESSMENT_COLUMNS = ["model", "aspect", "value", "source", "url", "published_on", "n_sources", "raw_score",
                      "scale_max", "source_aspect"]
OWNER_COLUMNS = ["model", "aspect", "value", "rating_count", "low_confidence", "source", "url", "observed_at",
                 "raw_score", "scale_max", "source_aspect"]


class ExportError(Exception):
    pass


def fmt(x: float) -> str:
    """Compact, deterministic number text."""
    return f"{x:.4f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def _map(kind: str, label: str, key: str) -> list[str]:
    try:
        return LABEL_MAP[(kind, label)]
    except KeyError:
        raise ExportError(f"{key}: label {label!r} ({kind}) is not in LABEL_MAP") from None


def expert_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT m.name AS model, s.name AS source, p.source_aspect, p.score, p.scale_max, p.source_url,
                  p.published_on, p.observed_at, p.id
           FROM professional_assessment p JOIN model m ON m.id = p.model_id JOIN source s ON s.id = p.source_id
           WHERE p.status = 'current'
           ORDER BY m.name, p.source_aspect, p.observed_at DESC, p.id DESC"""
    ).fetchall()
    seen, out = set(), []
    for r in rows:
        if r["source"] not in SOURCE_DISPLAY:
            raise ExportError(f"professional_assessment {r['id']}: unmapped source {r['source']!r}")
        k = (r["model"], r["source"], r["source_aspect"])
        if k in seen:  # newest observation wins if a model ever has two 'current' rows for one label
            continue
        seen.add(k)
        if not r["scale_max"] or not 0 <= r["score"] <= r["scale_max"]:
            raise ExportError(f"professional_assessment {r['id']}: bad score {r['score']}/{r['scale_max']}")
        for aspect in _map("expert", r["source_aspect"], f"professional_assessment {r['id']}"):
            out.append({"model": r["model"], "aspect": aspect, "value": fmt(r["score"] / r["scale_max"]),
                        "source": SOURCE_DISPLAY[r["source"]], "url": r["source_url"],
                        "published_on": r["published_on"] or "", "n_sources": 0,
                        "raw_score": fmt(float(r["score"])), "scale_max": fmt(float(r["scale_max"])),
                        "source_aspect": r["source_aspect"]})
    sources: dict[tuple[str, str], set[str]] = {}
    for o in out:
        sources.setdefault((o["model"], o["aspect"]), set()).add(o["source"])
    for o in out:
        o["n_sources"] = len(sources[(o["model"], o["aspect"])])
    out.sort(key=lambda o: (o["model"], o["aspect"], o["source"], o["source_aspect"]))
    return out


def owner_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT m.name AS model, s.name AS source, o.source_aspect, o.score, o.scale_max, o.rating_count,
                  o.source_url, o.observed_at, o.id
           FROM owner_rating o JOIN model m ON m.id = o.model_id JOIN source s ON s.id = o.source_id
           WHERE o.status = 'current'
           ORDER BY m.name, o.source_aspect, o.observed_at DESC, o.id DESC"""
    ).fetchall()
    seen, out = set(), []
    for r in rows:
        if r["source"] not in SOURCE_DISPLAY:
            raise ExportError(f"owner_rating {r['id']}: unmapped source {r['source']!r}")
        k = (r["model"], r["source"], r["source_aspect"])
        if k in seen:
            continue
        seen.add(k)
        if not r["scale_max"] or not 0 <= r["score"] <= r["scale_max"]:
            raise ExportError(f"owner_rating {r['id']}: bad score {r['score']}/{r['scale_max']}")
        count = r["rating_count"]
        for aspect in _map("owner", r["source_aspect"], f"owner_rating {r['id']}"):
            out.append({"model": r["model"], "aspect": aspect, "value": fmt(r["score"] / r["scale_max"]),
                        "rating_count": "" if count is None else str(int(count)),
                        # no count = unknown confidence, treated as low
                        "low_confidence": "true" if count is None or count < LOW_CONFIDENCE_BELOW else "false",
                        "source": SOURCE_DISPLAY[r["source"]], "url": r["source_url"],
                        "observed_at": r["observed_at"] or "", "raw_score": fmt(float(r["score"])),
                        "scale_max": fmt(float(r["scale_max"])), "source_aspect": r["source_aspect"]})
    out.sort(key=lambda o: (o["model"], o["aspect"], o["source"], o["source_aspect"]))
    return out


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def check_models(conn: sqlite3.Connection, rows: list[dict], what: str) -> None:
    """Every exported model name must be a model.name the catalogue export uses (view v_variant_canonical_q)."""
    names = {r[0] for r in conn.execute(
        "SELECT DISTINCT m.name FROM v_variant_canonical_q q JOIN model m ON m.id = q.model_id")}
    missing = sorted({r["model"] for r in rows} - names)
    if missing:
        raise ExportError(f"{what}: models not in the catalogue export: {missing}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, type=Path, help="a COPY of carrec_kb.db (never the production file)")
    ap.add_argument("--out-dir", default=Path("data"), type=Path)
    args = ap.parse_args(argv)
    if not args.db.is_file():
        print(f"error: KB copy not found: {args.db}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="carrec_reviews_") as tmp:
        copy = Path(tmp) / "kb.db"
        shutil.copyfile(args.db, copy)
        if Path(f"{args.db}-wal").exists():
            shutil.copyfile(f"{args.db}-wal", f"{copy}-wal")
        conn = sqlite3.connect(str(copy))
        conn.row_factory = sqlite3.Row
        try:
            expert, owner = expert_rows(conn), owner_rows(conn)
            check_models(conn, expert, "assessments")
            check_models(conn, owner, "owner_ratings")
        except ExportError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        finally:
            conn.close()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "assessments.csv", ASSESSMENT_COLUMNS, expert)
    write_csv(args.out_dir / "owner_ratings.csv", OWNER_COLUMNS, owner)
    print(f"assessments.csv: {len(expert)} rows, {len({r['model'] for r in expert})} models")
    print(f"owner_ratings.csv: {len(owner)} rows, {len({r['model'] for r in owner})} models, "
          f"{sum(1 for r in owner if r['low_confidence'] == 'true')} low-confidence rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
