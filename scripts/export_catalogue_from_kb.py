"""Export the CarRec knowledge base (KB) as a flat, one-row-per-variant catalogue.

Reads only the KB's quarantine-aware read path:
  - variant cells        -> v_variant_canonical_q (quarantined cells masked to NULL)
  - make/model/body/fuel -> model, manufacturer, powertrain (no quarantine targets)
  - safety               -> v_safety_applicability_q + safety_test, Bharat NCAP only,
                            latest test per model (year desc, safety_test.id desc)

The legacy safety_rating table (mostly old-protocol Global NCAP) is deliberately unused.

The KB (plus its -wal, if any) is copied into a temporary directory and only that
copy is opened (mode=ro), so nothing is ever created next to the --kb path.

Usage:
    python scripts/export_catalogue_from_kb.py --kb /tmp/kb_ro.db [--out-dir data]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_ROWS = 832

BODY_TYPES = {"SUV", "Hatchback", "MPV", "Sedan", "Van", "Pickup"}

FUEL_MAP = {
    "Petrol": "petrol",
    "Diesel": "diesel",
    "CNG": "cng",
    "Electric": "electric",
    "Petrol Hybrid": "hybrid",
    "Diesel Mild Hybrid": "diesel",
    "Flex Fuel": "petrol",
}

TRANSMISSION_MAP = {
    "Manual": "manual",
    "iMT": "imt",
    "AMT": "amt",
    "DCT": "dct",
    "CVT": "cvt",
    "e-CVT": "e_cvt",
    "Torque Converter": "torque_converter",
    # "Automatic" is handled separately: single_speed_ev, and only for Electric rows.
}
MANUAL_FAMILY = {"manual", "imt"}

TESTING_BODY_MAP = {"bharat_ncap": "Bharat NCAP"}

# export column -> v_variant_canonical_q column
SPEC_FROM_VARIANT = {
    "price_ex_showroom": "price_ex_showroom",
    "seats": "seating_capacity",
    "drivetrain": "drivetrain",
    "mileage_kmpl": "mileage_arai_kmpl",
    "mileage_km_per_kg": "mileage_arai_km_per_kg",
    "ev_range_km": "claimed_ev_range_km",
    "boot_space_litres": "boot_space_litres",
    "ground_clearance_mm": "ground_clearance_mm",
    "length_mm": "length_mm",
    "airbags": "airbags",
}
SPEC_FROM_POWERTRAIN = ("engine_cc", "power_bhp", "torque_nm")
SPEC_COLUMNS = [
    "price_ex_showroom", "seats", "engine_cc", "power_bhp", "torque_nm", "drivetrain",
    "mileage_kmpl", "mileage_km_per_kg", "ev_range_km", "boot_space_litres",
    "ground_clearance_mm", "length_mm", "airbags",
]
BOOL_COLUMNS = [
    "abs", "android_auto", "apple_carplay", "cruise_control", "sunroof", "adas_available",
    "camera_360", "ventilated_front_seats", "wireless_charging", "heads_up_display",
]
SAFETY_COLUMNS = [
    "safety_stars_adult", "safety_stars_child", "safety_testing_body", "safety_test_year",
]
# Fields checked for NULL/quarantine and listed in unverified_fields. Safety is excluded:
# a blank safety_stars_adult means "no Bharat NCAP rating on record", handled by the app.
CHECKED_COLUMNS = SPEC_COLUMNS + BOOL_COLUMNS + ["adas_tier"]
# Fields that don't apply to a fuel type, so a blank there is not "unverified".
NOT_APPLICABLE = {
    "electric": {"engine_cc", "mileage_kmpl", "mileage_km_per_kg"},
    "petrol": {"ev_range_km", "mileage_km_per_kg"},
    "diesel": {"ev_range_km", "mileage_km_per_kg"},
    "hybrid": {"ev_range_km", "mileage_km_per_kg"},
    "cng": {"ev_range_km"},
}

# export column -> variant field name used in evidence_quarantine.target_field
VARIANT_FIELD = {**SPEC_FROM_VARIANT, **{c: c for c in BOOL_COLUMNS}, "adas_tier": "adas_tier"}

COLUMNS = [
    "variant_id", "make", "model", "variant", "full_name", "body_type",
    "fuel_raw", "fuel_type",
    "transmission_raw", "transmission_type", "transmission_family",
    *SPEC_COLUMNS, *BOOL_COLUMNS, "adas_tier", *SAFETY_COLUMNS,
    "unverified_fields",
]

TRUE_VALUES = {"1", "true"}
FALSE_VALUES = {"0", "false"}


class ExportError(Exception):
    pass


def fmt_num(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def fmt_bool(value, column: str, variant_id: int) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if isinstance(value, float) and value in (0.0, 1.0):
        text = str(int(value))
    if text in TRUE_VALUES:
        return "true"
    if text in FALSE_VALUES:
        return "false"
    raise ExportError(f"variant {variant_id}: unmapped boolean {column}={value!r}")


def fmt_int(value, column: str, variant_id: int) -> str:
    """Integer-valued cell stored as text/real in the KB ('1.0' -> '1')."""
    if value is None:
        return ""
    try:
        number = float(value)
    except ValueError:
        raise ExportError(f"variant {variant_id}: non-numeric {column}={value!r}") from None
    if not number.is_integer():
        raise ExportError(f"variant {variant_id}: non-integer {column}={value!r}")
    return str(int(number))


def phase_key(phase: str):
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.findall(r"\d+|\D+", phase))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_variants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    variant_cols = ", ".join(f"q.{c}" for c in sorted(set(SPEC_FROM_VARIANT.values()) | set(BOOL_COLUMNS) | {"adas_tier"}))
    return conn.execute(
        f"""
        SELECT q.id AS variant_id, mf.name AS make, m.name AS model, q.name AS variant,
               q.full_name, m.body_type, q.model_id, q.base_variant_id,
               pt.fuel_type AS fuel_raw, q.transmission AS transmission_raw,
               pt.engine_cc, pt.power_bhp, pt.torque_nm, {variant_cols}
        FROM v_variant_canonical_q q
        JOIN model m ON m.id = q.model_id
        JOIN manufacturer mf ON mf.id = m.manufacturer_id
        LEFT JOIN powertrain pt ON pt.id = q.powertrain_id
        ORDER BY q.id
        """
    ).fetchall()


def load_safety(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT a.model_id, a.id AS applicability_id, st.id AS safety_test_id,
               st.aop_stars, st.cop_stars, st.year_of_publication, so.name AS source_name
        FROM v_safety_applicability_q a
        JOIN safety_test st ON st.id = a.safety_test_id
        JOIN source so ON so.id = st.source_id
        JOIN v_safety_test_status s ON s.safety_test_id = st.id
        WHERE s.canonical_status = 'resolved_model' AND a.model_id IS NOT NULL
        ORDER BY a.model_id, st.year_of_publication DESC, st.id DESC, a.id DESC
        """
    ).fetchall()
    latest: dict[int, sqlite3.Row] = {}
    for row in rows:
        latest.setdefault(row["model_id"], row)
    return latest


def build_rows(conn: sqlite3.Connection) -> tuple[list[dict], dict[int, sqlite3.Row]]:
    safety = load_safety(conn)
    out = []
    seen: set[int] = set()
    for r in load_variants(conn):
        vid = r["variant_id"]
        if vid in seen:
            raise ExportError(f"duplicate variant_id {vid}")
        seen.add(vid)

        if r["body_type"] not in BODY_TYPES:
            raise ExportError(f"variant {vid}: unmapped body_type {r['body_type']!r}")
        if r["fuel_raw"] not in FUEL_MAP:
            raise ExportError(f"variant {vid}: unmapped fuel_type {r['fuel_raw']!r}")
        trans_raw = r["transmission_raw"]
        if trans_raw == "Automatic":
            if r["fuel_raw"] != "Electric":
                raise ExportError(f"variant {vid}: 'Automatic' transmission on non-EV ({r['fuel_raw']})")
            trans_type = "single_speed_ev"
        elif trans_raw in TRANSMISSION_MAP:
            trans_type = TRANSMISSION_MAP[trans_raw]
        else:
            raise ExportError(f"variant {vid}: unmapped transmission {trans_raw!r}")

        row = {
            "variant_id": str(vid),
            "make": r["make"],
            "model": r["model"],
            "variant": r["variant"],
            "full_name": r["full_name"] or "",
            "body_type": r["body_type"].lower(),
            "fuel_raw": r["fuel_raw"],
            "fuel_type": FUEL_MAP[r["fuel_raw"]],
            "transmission_raw": trans_raw,
            "transmission_type": trans_type,
            "transmission_family": "manual" if trans_type in MANUAL_FAMILY else "automatic",
        }
        for col, src in SPEC_FROM_VARIANT.items():
            row[col] = fmt_num(r[src])
        for col in SPEC_FROM_POWERTRAIN:
            row[col] = fmt_num(r[col])
        for col in BOOL_COLUMNS:
            row[col] = fmt_bool(r[col], col, vid)
        row["adas_tier"] = fmt_int(r["adas_tier"], "adas_tier", vid)

        test = safety.get(r["model_id"])
        if test is not None:
            if test["source_name"] not in TESTING_BODY_MAP:
                raise ExportError(f"safety_test {test['safety_test_id']}: unmapped source {test['source_name']!r}")
            row["safety_stars_adult"] = fmt_num(test["aop_stars"])
            row["safety_stars_child"] = fmt_num(test["cop_stars"])
            row["safety_testing_body"] = TESTING_BODY_MAP[test["source_name"]]
            row["safety_test_year"] = fmt_num(test["year_of_publication"])
        else:
            for col in SAFETY_COLUMNS:
                row[col] = ""

        skip = NOT_APPLICABLE[row["fuel_type"]]
        row["unverified_fields"] = ";".join(c for c in CHECKED_COLUMNS if c not in skip and row[c] == "")
        out.append(row)

    if len(out) != EXPECTED_ROWS:
        raise ExportError(f"row count {len(out)} != expected {EXPECTED_ROWS}")
    return out, safety


def quarantine_counts(conn: sqlite3.Connection, rows: list[dict], safety: dict[int, sqlite3.Row]) -> Counter:
    """Assert no exported cell carries a quarantined value; return quarantined-cell counts per column."""
    by_id = {int(r["variant_id"]): r for r in rows}
    field_to_col = {f: c for c, f in VARIANT_FIELD.items()}
    raw = {r["id"]: r for r in conn.execute("SELECT * FROM variant")}
    children: dict[int, list[int]] = {}
    for vid, v in raw.items():
        if v["base_variant_id"] is not None:
            children.setdefault(v["base_variant_id"], []).append(vid)

    counts: Counter = Counter()
    for q in conn.execute(
        "SELECT target_id, target_field FROM v_active_quarantine WHERE target_table = 'variant' ORDER BY id"
    ):
        tid, field = q["target_id"], q["target_field"]
        cols = list(VARIANT_FIELD) if field == "*" else [field_to_col[field]] if field in field_to_col else []
        for col in cols:
            src = VARIANT_FIELD[col]
            # the variant itself, plus edition children that would inherit this cell
            affected = [tid] + [c for c in children.get(tid, []) if raw[c][src] is None]
            for vid in affected:
                if vid in by_id:
                    if by_id[vid][col] != "":
                        raise ExportError(f"variant {vid}: exported quarantined value {col}={by_id[vid][col]!r}")
                    counts[col] += 1

    bad_tests = {r[0] for r in conn.execute(
        "SELECT target_id FROM v_active_quarantine WHERE target_table = 'safety_test'")}
    bad_apps = {r[0] for r in conn.execute(
        "SELECT target_id FROM v_active_quarantine WHERE target_table = 'safety_test_applicability'")}
    for test in safety.values():
        if test["safety_test_id"] in bad_tests or test["applicability_id"] in bad_apps:
            raise ExportError(f"safety_test {test['safety_test_id']}: quarantined evidence exported")
    return counts


def latest_phase(conn: sqlite3.Connection) -> str | None:
    phases = [r[0] for r in conn.execute(
        "SELECT phase FROM evidence_amendment UNION SELECT phase FROM evidence_quarantine") if r[0]]
    return max(phases, key=phase_key) if phases else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kb", required=True, type=Path, help="path to (a copy of) carrec_kb.db")
    parser.add_argument("--out-dir", default=Path("data"), type=Path)
    args = parser.parse_args(argv)

    if not args.kb.is_file():
        print(f"error: KB not found: {args.kb}", file=sys.stderr)
        return 2

    wal_path = Path(f"{args.kb}-wal")
    with tempfile.TemporaryDirectory(prefix="carrec_kb_") as tmp:
        copy = Path(tmp) / "kb.db"
        shutil.copyfile(args.kb, copy)
        if wal_path.exists():
            shutil.copyfile(wal_path, Path(f"{copy}-wal"))
        conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows, safety = build_rows(conn)
            quarantined = quarantine_counts(conn, rows, safety)
            phase = latest_phase(conn)
        except ExportError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        finally:
            conn.close()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "catalogue.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    meta = {
        "export_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kb_sha256": sha256_file(args.kb),
        # A non-empty -wal means kb_sha256 does not describe the full DB state.
        "kb_wal_nonempty": wal_path.exists() and wal_path.stat().st_size > 0,
        "kb_latest_phase": phase,
        "row_count": len(rows),
        "catalogue_sha256": sha256_file(csv_path),
        "safety_rule": "Bharat NCAP via v_safety_applicability_q (resolved_model only); "
                       "latest year_of_publication per model, tie -> highest safety_test.id; "
                       "legacy safety_rating unused",
        "columns": {
            **{
                col: {
                    "non_null": sum(1 for r in rows if r[col] != ""),
                    "unverified": sum(1 for r in rows if col in r["unverified_fields"].split(";")),
                    "not_applicable_blank": sum(
                        1 for r in rows if r[col] == "" and col in NOT_APPLICABLE[r["fuel_type"]]),
                    "quarantined": quarantined.get(col, 0),
                }
                for col in CHECKED_COLUMNS
            },
            **{col: {"non_null": sum(1 for r in rows if r[col] != "")} for col in SAFETY_COLUMNS},
        },
        "transmission_type_distribution": dict(sorted(Counter(r["transmission_type"] for r in rows).items())),
        "fuel_type_distribution": dict(sorted(Counter(r["fuel_type"] for r in rows).items())),
    }
    meta_path = args.out_dir / "catalogue_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wrote {len(rows)} rows -> {csv_path} (sha256 {meta['catalogue_sha256']})")
    print(f"wrote {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
