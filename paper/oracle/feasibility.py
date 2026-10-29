"""Feasibility oracle over the frozen CarRec KB snapshot.

Reads the KB only through the quarantine-aware view v_variant_canonical_q (joined to model, manufacturer and
powertrain), on an immutable read-only connection, after asserting the frozen SHA-1. Mapping rules: paper/SPEC.md §9.

    catalogue = load_catalogue()
    find_matches({"body_type": "SUV", "fuel": "diesel", "max_budget": 800000}, catalogue)
    -> [(variant_id, price), ...] sorted by price, then id
"""
import hashlib
import os
import sqlite3

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(REPO_ROOT, "knowledge_base", "carrec_kb.db")
FROZEN_SHA1 = "8592508789594ab76cf98e463bbf77606a76a7e2"

TRANSMISSION_MAP = {
    "Torque Converter": "automatic",
    "AMT": "automatic",
    "DCT": "automatic",
    "CVT": "automatic",
    "e-CVT": "automatic",
    "Automatic": "automatic",
    "Manual": "manual",
    "iMT": "manual",  # manual gear lever
}
FUEL_MAP = {
    "Petrol": "petrol",
    "Diesel": "diesel",
    "Diesel Mild Hybrid": "diesel",
    "CNG": "cng",
    "Electric": "electric",
    "Petrol Hybrid": "hybrid",
    "Flex Fuel": "petrol",  # author decision 2026-10-29; no v0 query changes (SPEC §9)
}
BODY_TYPES = ("Hatchback", "Sedan", "SUV", "MPV", "Pickup", "Van")
FUELS = ("petrol", "diesel", "cng", "electric", "hybrid")
TRANSMISSIONS = ("manual", "automatic")
EXCLUDED_MODEL_NAMES = ("Brezza", "Baleno", "Kylaq")  # CATALOG_CURRENCY
CONSTRAINT_KEYS = ("max_budget", "fuel", "transmission", "body_type", "min_seats")

CATALOGUE_SQL = """
SELECT v.id, mf.name, m.id, m.name, v.name, v.full_name, m.body_type, pt.fuel_type, v.transmission,
       v.seating_capacity, v.price_ex_showroom
FROM v_variant_canonical_q v
JOIN model m ON m.id = v.model_id
JOIN manufacturer mf ON mf.id = m.manufacturer_id
JOIN powertrain pt ON pt.id = v.powertrain_id
ORDER BY v.id
"""
RAW_FIELDS = ("variant_id", "manufacturer", "model_id", "model", "variant_name", "full_name", "body_type",
              "fuel_raw", "transmission_raw", "seats", "price")


class FrozenKBError(RuntimeError):
    pass


class UnmappedValueError(ValueError):
    pass


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_frozen_db(path=DB_PATH):
    for suffix in ("-wal", "-journal"):
        if os.path.exists(path + suffix):
            raise FrozenKBError(f"{path}{suffix} exists; the frozen snapshot is not the file alone")
    digest = sha1_of(path)
    if digest != FROZEN_SHA1:
        raise FrozenKBError(f"KB SHA-1 {digest} != frozen {FROZEN_SHA1}")
    return digest


def build_row(raw, excluded_model_ids=frozenset()):
    """Map one raw view row (dict with RAW_FIELDS) to an oracle row. Raises on NULLs or unmapped values."""
    for key in ("body_type", "fuel_raw", "transmission_raw", "seats", "price"):
        if raw[key] is None:
            raise UnmappedValueError(f"variant {raw['variant_id']}: NULL {key}")
    if raw["transmission_raw"] not in TRANSMISSION_MAP:
        raise UnmappedValueError(f"variant {raw['variant_id']}: unmapped transmission {raw['transmission_raw']!r}")
    if raw["fuel_raw"] not in FUEL_MAP:
        raise UnmappedValueError(f"variant {raw['variant_id']}: unmapped fuel {raw['fuel_raw']!r}")
    if raw["body_type"] not in BODY_TYPES:
        raise UnmappedValueError(f"variant {raw['variant_id']}: unmapped body type {raw['body_type']!r}")
    row = dict(raw)
    row["fuel"] = FUEL_MAP[raw["fuel_raw"]]
    row["transmission"] = TRANSMISSION_MAP[raw["transmission_raw"]]
    row["seats"] = int(raw["seats"])
    row["price"] = float(raw["price"])
    row["model_excluded"] = raw["model_id"] in excluded_model_ids
    return row


def load_catalogue(path=DB_PATH):
    verify_frozen_db(path)
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        raws = [dict(zip(RAW_FIELDS, r)) for r in con.execute(CATALOGUE_SQL)]
    finally:
        con.close()
    excluded = {r["model_id"] for r in raws if r["model"] in EXCLUDED_MODEL_NAMES}
    found = {r["model"] for r in raws if r["model_id"] in excluded}
    if found != set(EXCLUDED_MODEL_NAMES):
        raise FrozenKBError(f"excluded models not all found by name: {sorted(found)}")
    catalogue = [build_row(r, frozenset(excluded)) for r in raws]
    verify_frozen_db(path)
    return catalogue


def validate_constraints(constraints):
    unknown = set(constraints) - set(CONSTRAINT_KEYS)
    if unknown:
        raise ValueError(f"unknown constraint keys {sorted(unknown)}")
    if "fuel" in constraints and constraints["fuel"] not in FUELS:
        raise ValueError(f"fuel {constraints['fuel']!r} not in {FUELS}")
    if "transmission" in constraints and constraints["transmission"] not in TRANSMISSIONS:
        raise ValueError(f"transmission {constraints['transmission']!r} not in {TRANSMISSIONS}")
    if "body_type" in constraints and constraints["body_type"] not in BODY_TYPES:
        raise ValueError(f"body_type {constraints['body_type']!r} not in {BODY_TYPES}")


def satisfies(row, constraints):
    c = constraints
    if "max_budget" in c and not row["price"] <= c["max_budget"]:
        return False
    if "fuel" in c and row["fuel"] != c["fuel"]:
        return False
    if "transmission" in c and row["transmission"] != c["transmission"]:
        return False
    if "body_type" in c and row["body_type"] != c["body_type"]:
        return False
    if "min_seats" in c and not row["seats"] >= c["min_seats"]:
        return False
    return True


def find_matches(constraints, catalogue, include_excluded=True):
    """Matching (variant_id, price) pairs, sorted by price then id. Full catalogue unless include_excluded=False."""
    validate_constraints(constraints)
    hits = [(r["variant_id"], r["price"]) for r in catalogue
            if (include_excluded or not r["model_excluded"]) and satisfies(r, constraints)]
    return sorted(hits, key=lambda h: (h[1], h[0]))
