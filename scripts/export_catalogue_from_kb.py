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

# Sanity limits (replace the old fixed 832-row assertion; the KB grows between exports).
ROW_COUNT_TOLERANCE = 0.05      # exported rows within 5% of (KB variant rows - rows the quarantine-aware view excludes)
NON_NULL_DROP_LIMIT = 5.0       # a column's non-null rate may be at most this many points below the previous file

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
    # "Automatic" is handled separately: single_speed_ev for Electric rows, HYBRID_AUTOMATIC_TYPE for Petrol Hybrid rows.
}
# The 2026-11 KB holds three Renault Duster hybrids (1361, 1366, 1367) whose transmission is just "Automatic" (a
# multi-mode hybrid gearbox). The engine's transmission vocabulary is closed, so the row needs one of its types to stay
# findable under "automatic"; the nearest family for a series/parallel hybrid is e_cvt. The raw value is kept in
# transmission_raw. Review item: a vocabulary entry of its own would be more honest (needs engine changes).
HYBRID_AUTOMATIC_TYPE = "e_cvt"
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
    "width_mm": "width_mm",
    "height_mm": "height_mm",
    "wheelbase_mm": "wheelbase_mm",
    "kerb_weight_kg": "kerb_weight_kg",
    "fuel_tank_litres": "fuel_tank_litres",
    "airbags": "airbags",
}
SPEC_FROM_POWERTRAIN = ("engine_cc", "power_bhp", "torque_nm")
SPEC_COLUMNS = [
    "price_ex_showroom", "seats", "engine_cc", "power_bhp", "torque_nm", "drivetrain",
    "mileage_kmpl", "mileage_km_per_kg", "ev_range_km", "boot_space_litres",
    "ground_clearance_mm", "length_mm", "width_mm", "height_mm", "wheelbase_mm", "kerb_weight_kg",
    "fuel_tank_litres", "airbags",
]
BOOL_COLUMNS = [
    "abs", "android_auto", "apple_carplay", "cruise_control", "sunroof", "adas_available",
    "camera_360", "ventilated_front_seats", "wireless_charging", "heads_up_display",
    # detail-view features (>= 50% coverage in v_variant_canonical_q)
    "esc", "hill_assist", "tpms", "rear_parking_sensors", "rear_camera",
    "auto_climate_control", "rear_ac_vents", "connected_car_features", "paddle_shifters",
]
# export column -> v_variant_canonical_q column, where the names differ
BOOL_SOURCE = {"tpms": "tyre_pressure_monitoring_system", "auto_climate_control": "automatic_climate_control"}
SAFETY_COLUMNS = [
    "safety_stars_adult", "safety_stars_child", "safety_testing_body", "safety_test_year",
]
# Fields checked for NULL/quarantine and listed in unverified_fields. Safety is excluded:
# a blank safety_stars_adult means "no Bharat NCAP rating on record", handled by the app.
CHECKED_COLUMNS = SPEC_COLUMNS + BOOL_COLUMNS
# Fields that don't apply to a fuel type, so a blank there is not "unverified".
NOT_APPLICABLE = {
    "electric": {"engine_cc", "mileage_kmpl", "mileage_km_per_kg", "fuel_tank_litres"},
    "petrol": {"ev_range_km", "mileage_km_per_kg"},
    "diesel": {"ev_range_km", "mileage_km_per_kg"},
    "hybrid": {"ev_range_km", "mileage_km_per_kg"},
    # CNG mileage is a km/kg figure; the KB holds no kmpl figure for any CNG row (Phase 10E).
    "cng": {"ev_range_km", "mileage_kmpl"},
}

# export column -> variant field name used in evidence_quarantine.target_field
VARIANT_FIELD = {**SPEC_FROM_VARIANT, **{c: BOOL_SOURCE.get(c, c) for c in BOOL_COLUMNS}}

# Only figures with a brochure citation are exported; anything else shows as unverified in the app.
WARRANTY_COLUMNS = ["warranty_years", "warranty_km", "battery_warranty_years", "battery_warranty_km"]
OEM_WARRANTY_SOURCE = "OEM brochure"
BATTERY_WARRANTY_FUELS = {"electric", "hybrid"}
# The source text says when a brochure backs only part of a row (KB Phase 10L).
BATTERY_FIGURES_NOT_CITED = "battery figures not in this brochure"
BATTERY_KM_NOT_CITED = "battery km not printed"

COLUMNS = [
    "variant_id", "make", "model", "variant", "full_name", "body_type",
    "fuel_raw", "fuel_type",
    "transmission_raw", "transmission_type", "transmission_family",
    *SPEC_COLUMNS, *BOOL_COLUMNS, *SAFETY_COLUMNS, *WARRANTY_COLUMNS,
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


def phase_key(phase: str):
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.findall(r"\d+|\D+", phase))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_variants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    sources = set(SPEC_FROM_VARIANT.values()) | {BOOL_SOURCE.get(c, c) for c in BOOL_COLUMNS}
    variant_cols = ", ".join(f"q.{c}" for c in sorted(sources))
    return conn.execute(
        f"""
        SELECT q.id AS variant_id, mf.name AS make, m.name AS model, q.name AS variant,
               q.full_name, m.body_type, q.model_id, m.manufacturer_id, q.base_variant_id,
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


def unlinked_safety_tests(conn: sqlite3.Connection) -> list[tuple[int, str, list[str]]]:
    """(test id, tested vehicle name, [models in the KB whose name appears in it]) for every crash test that is not
    linked to a model in v_safety_applicability_q although the test title names a model that is in the `model` table.
    Report only: the exporter never links a test itself (that is a KB write, and a name match is not applicability).
    Found 2026-11-16: eight models added after their tests were ingested showed "no rating on record"."""
    def norm(text: str) -> str:
        return "".join(ch for ch in str(text).lower() if ch.isalnum())

    models = conn.execute("SELECT m.name AS model, mf.name AS make FROM model m "
                          "JOIN manufacturer mf ON mf.id = m.manufacturer_id").fetchall()
    out = []
    for t in conn.execute(
            """SELECT st.id, st.tested_vehicle_name FROM safety_test st
               WHERE NOT EXISTS (SELECT 1 FROM v_safety_applicability_q a WHERE a.safety_test_id = st.id)
               ORDER BY st.id"""):
        title = norm(t["tested_vehicle_name"])
        hits = sorted({m["model"] for m in models
                       if len(norm(m["model"])) >= 4 and norm(m["model"]) in title
                       and norm(m["make"].split()[0]) in title})
        if hits:
            out.append((t["id"], t["tested_vehicle_name"], hits))
    return out


def load_warranty(conn: sqlite3.Connection) -> tuple[dict[int, sqlite3.Row], dict[int, sqlite3.Row]]:
    """Brochure-cited rows from the quarantine-aware view: (by model, by make)."""
    by_model: dict[int, sqlite3.Row] = {}
    by_make: dict[int, sqlite3.Row] = {}
    for w in conn.execute("SELECT * FROM v_warranty_q WHERE source LIKE ? ORDER BY id", (OEM_WARRANTY_SOURCE + "%",)):
        if w["model_id"] is not None:
            by_model[w["model_id"]] = w
        else:
            by_make[w["manufacturer_id"]] = w
    return by_model, by_make


def fmt_km(value) -> str:
    """'100000.0' -> '100000'; 'Unlimited' stays."""
    if value is None or value == "":
        return ""
    text = str(value).strip()
    return text if text.lower() == "unlimited" else fmt_num(float(text))


def build_rows(conn: sqlite3.Connection) -> tuple[list[dict], dict[int, sqlite3.Row]]:
    safety = load_safety(conn)
    warranty_by_model, warranty_by_make = load_warranty(conn)
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
            if r["fuel_raw"] == "Electric":
                trans_type = "single_speed_ev"
            elif r["fuel_raw"] == "Petrol Hybrid":
                trans_type = HYBRID_AUTOMATIC_TYPE
            else:
                raise ExportError(f"variant {vid}: 'Automatic' transmission on {r['fuel_raw']}")
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
            row[col] = fmt_bool(r[BOOL_SOURCE.get(col, col)], col, vid)

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

        w = warranty_by_model.get(r["model_id"]) or warranty_by_make.get(r["manufacturer_id"])
        battery = (w is not None and row["fuel_type"] in BATTERY_WARRANTY_FUELS
                   and BATTERY_FIGURES_NOT_CITED not in (w["source"] or ""))
        row["warranty_years"] = fmt_num(w["warranty_years"]) if w else ""
        row["warranty_km"] = fmt_km(w["warranty_km"]) if w else ""
        row["battery_warranty_years"] = fmt_num(w["battery_warranty_years"]) if battery else ""
        row["battery_warranty_km"] = (fmt_km(w["battery_warranty_km"])
                                      if battery and BATTERY_KM_NOT_CITED not in (w["source"] or "") else "")

        skip = NOT_APPLICABLE[row["fuel_type"]]
        row["unverified_fields"] = ";".join(c for c in CHECKED_COLUMNS if c not in skip and row[c] == "")
        out.append(row)

    return out, safety


def read_old_catalogue(path: Path | None) -> list[dict]:
    if path is None or not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def split_unpriced(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Owner decision 2026-11: a variant with no price (price_ex_showroom NULL in v_variant_canonical_q, which already
    masks quarantined cells) is left out of the app catalogue until the KB has a price. Returns (kept, left_out)."""
    kept = [r for r in rows if r["price_ex_showroom"] != ""]
    return kept, [r for r in rows if r["price_ex_showroom"] == ""]


def sanity_checks(conn: sqlite3.Connection, rows: list[dict], old_rows: list[dict],
                  no_price: int = 0) -> tuple[list[dict], list[str]]:
    """Replaces the fixed row-count assertion. Returns (table, failures).

    1. row count within ROW_COUNT_TOLERANCE of (KB variant rows - variants the view excludes)
    2. no duplicate variant ids (also checked while building)
    3. per column, the non-null rate (share of rows with a value; columns that do not apply to a row's fuel type count
       as non-null there) of the rows that were already in the previous file ("carried": same variant id) must not be
       worse than the previous file's rate for those same rows by more than NON_NULL_DROP_LIMIT points. This is the
       only per-column check that can fail the export.
    The rows that are new in this export are reported, never failed: a freshly added model often has blanks (the KB
    records only what the source states), so a column where the new rows are more than NON_NULL_DROP_LIMIT points
    sparser than the previous file is marked "new rows sparse" in the table (`new_rows_pct`, `new_rows_sparse`).
    """
    failures: list[str] = []
    kb_variants = conn.execute("SELECT COUNT(*) FROM variant").fetchone()[0]
    in_view = conn.execute("SELECT COUNT(*) FROM v_variant_canonical_q").fetchone()[0]
    excluded = kb_variants - in_view
    expected = kb_variants - excluded - no_price      # no_price: variants deliberately left out (split_unpriced)
    if abs(len(rows) - expected) > ROW_COUNT_TOLERANCE * expected:
        failures.append(f"row count {len(rows)} is not within {ROW_COUNT_TOLERANCE:.0%} of {expected} "
                        f"(KB variants {kb_variants} - excluded {excluded} - no price {no_price})")
    ids = [r["variant_id"] for r in rows]
    if len(set(ids)) != len(ids):
        failures.append("duplicate variant ids")

    def rate(rs: list[dict], col: str) -> float | None:
        if not rs:
            return None
        ok = 0
        for r in rs:
            na = col in NOT_APPLICABLE.get(r.get("fuel_type", ""), set())
            ok += 1 if (r.get(col, "") != "" or na) else 0
        return 100.0 * ok / len(rs)

    old_ids = {r["variant_id"] for r in old_rows}
    new_ids = set(ids)
    carried = [r for r in rows if r["variant_id"] in old_ids]
    added = [r for r in rows if r["variant_id"] not in old_ids]
    old_carried = [r for r in old_rows if r["variant_id"] in new_ids]
    table = []
    for col in CHECKED_COLUMNS + SAFETY_COLUMNS:
        new, old = rate(rows, col), rate(old_rows, col)
        same, was = rate(carried, col), rate(old_carried, col)
        fresh = rate(added, col)
        delta = None if old is None else new - old
        carried_delta = None if same is None or was is None else same - was
        bad = carried_delta is not None and carried_delta < -NON_NULL_DROP_LIMIT
        if bad:
            failures.append(f"{col}: non-null rate of the {len(carried)} carried-over rows {same:.1f}% vs {was:.1f}% "
                            f"before ({carried_delta:+.1f} points)")
        sparse = fresh is not None and old is not None and fresh < old - NON_NULL_DROP_LIMIT
        table.append({"column": col, "new_pct": round(new, 1), "old_pct": None if old is None else round(old, 1),
                      "delta": None if delta is None else round(delta, 1), "worse_than_limit": bad,
                      # same variant ids as the previous file: separates "new KB rows are sparse" from "old rows got worse"
                      "carried_over_rows_pct": None if same is None else round(same, 1),
                      "carried_over_before_pct": None if was is None else round(was, 1),
                      "new_rows_pct": None if fresh is None else round(fresh, 1), "new_rows_sparse": sparse})
    table.insert(0, {"column": "ROWS", "new_pct": len(rows), "old_pct": len(old_rows) or None, "delta": None,
                     "worse_than_limit": False, "kb_variants": kb_variants, "excluded": excluded, "excluded_no_price": no_price,
                     "carried_over_rows": len(carried), "new_rows": len(added)})
    return table, failures


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
    parser.add_argument("--compare-to", type=Path, default=None,
                        help="previous catalogue.csv for the non-null sanity check (default: OUT_DIR/catalogue.csv "
                             "if it exists; read before it is overwritten)")
    parser.add_argument("--force", action="store_true", help="write the files even if a sanity check fails")
    args = parser.parse_args(argv)

    if not args.kb.is_file():
        print(f"error: KB not found: {args.kb}", file=sys.stderr)
        return 2

    wal_path = Path(f"{args.kb}-wal")
    old_rows = read_old_catalogue(args.compare_to or args.out_dir / "catalogue.csv")
    with tempfile.TemporaryDirectory(prefix="carrec_kb_") as tmp:
        copy = Path(tmp) / "kb.db"
        shutil.copyfile(args.kb, copy)
        if wal_path.exists():
            shutil.copyfile(wal_path, Path(f"{copy}-wal"))
        # the temp copy is throwaway; a WAL-mode file cannot be opened mode=ro without a -shm beside it
        conn = sqlite3.connect(str(copy))
        conn.row_factory = sqlite3.Row
        try:
            rows, safety = build_rows(conn)
            rows, unpriced = split_unpriced(rows)
            quarantined = quarantine_counts(conn, rows, safety)
            unlinked = unlinked_safety_tests(conn)
            sanity, failures = sanity_checks(conn, rows, old_rows, no_price=len(unpriced))
            phase = latest_phase(conn)
        except ExportError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        finally:
            conn.close()

    for test_id, name, hits in unlinked:
        print(f"WARNING: safety_test {test_id} ({name}) names {', '.join(hits)}, which is in the KB, but no applicability "
              "row links them: the catalogue shows no crash rating for it. Link it in the KB (owner decision).")
    print("sanity table (non-null %, new vs previous file; carried = rows whose variant id was in the previous file, "
          "before = the previous file's rate for those same rows; added = rows new in this export):")
    for t in sanity:
        print(f"  {t['column']:<26} new {t['new_pct']!s:>6}  old {t['old_pct']!s:>6}  delta {t['delta']!s:>6}"
              f"  carried {t.get('carried_over_rows_pct')!s:>6}  before {t.get('carried_over_before_pct')!s:>6}"
              f"  added {t.get('new_rows_pct')!s:>6}"
              + ("  <-- CARRIED ROWS WORSE (fails)" if t["worse_than_limit"] else "")
              + ("  <-- new rows sparse (reported, not a failure)" if t.get("new_rows_sparse") else ""))
    sparse_cols = [t["column"] for t in sanity if t.get("new_rows_sparse")]
    if sparse_cols:
        print(f"{sparse_cols.__len__()} column(s) are sparser on the rows added in this export than in the previous file: "
              + ", ".join(sparse_cols))
    if failures:
        for f in failures:
            print(f"sanity check failed: {f}", file=sys.stderr)
        if not args.force:
            print("error: nothing written (use --force to write anyway)", file=sys.stderr)
            return 1

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
        # variants in the KB view with no price: left out of this catalogue until the KB has one (owner decision)
        "excluded_no_price": {"count": len(unpriced),
                              "variants": [{"variant_id": int(r["variant_id"]), "make": r["make"], "model": r["model"],
                                            "variant": r["variant"]} for r in unpriced]},
        "sanity": {"table": sanity, "failures": failures},
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

    print(f"left out {len(unpriced)} variant(s) with no price: "
          + (", ".join(sorted({f"{r['make']} {r['model']}" for r in unpriced})) or "none"))
    print(f"wrote {len(rows)} rows -> {csv_path} (sha256 {meta['catalogue_sha256']})")
    print(f"wrote {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
