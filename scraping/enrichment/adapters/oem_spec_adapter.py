"""Curated official-spec adapter for shared model and powertrain facts."""

from __future__ import annotations

import re
from typing import Any

from scraping.enrichment.adapters.base import SourceAdapter
from scraping.schemas.enrichment_schema import candidate_value


TARGET_FIELDS = (
    "boot_space_litres",
    "ground_clearance_mm",
    "kerb_weight_kg",
    "turning_radius_metres",
    "fuel_tank_capacity_litres",
    "drivetrain",
    "cylinders",
    "turbocharged",
    "gearbox_speeds",
    "length_mm",
    "width_mm",
    "height_mm",
    "wheelbase_mm",
)


MODEL_SPECS: dict[tuple[str, str], dict[str, Any]] = {
    ("Tata", "Nexon"): {
        "source_url": "https://cars.tatamotors.com/nexon/ice/specifications.html",
        "source_type": "official_model_spec",
        "values": {
            "length_mm": 3995,
            "width_mm": 1804,
            "height_mm": 1620,
            "wheelbase_mm": 2498,
            "ground_clearance_mm": 208,
            "turning_radius_metres": 5.1,
        },
        "evidence": "Tata Nexon official specifications: dimensions, ground clearance, turning circle.",
    },
    ("Hyundai", "Creta"): {
        "source_url": "https://www.hyundai.com/in/en/find-a-car/creta/specification",
        "source_type": "official_model_spec",
        "values": {
            "length_mm": 4330,
            "width_mm": 1790,
            "height_mm": 1635,
            "wheelbase_mm": 2610,
            "ground_clearance_mm": 190,
            "turning_radius_metres": 5.4,
        },
        "evidence": "Hyundai Creta official/model specification table and brochure-compatible model dimensions.",
    },
    ("Maruti Suzuki", "Swift"): {
        "source_url": "https://www.marutisuzuki.com/swift/specifications",
        "source_type": "official_model_spec",
        "values": {
            "length_mm": 3860,
            "width_mm": 1735,
            "height_mm": 1520,
            "wheelbase_mm": 2450,
            "ground_clearance_mm": 163,
            "turning_radius_metres": 4.8,
        },
        "evidence": "Maruti Suzuki Swift official specifications: dimensions, ground clearance, turning radius.",
    },
    ("MG", "Windsor EV"): {
        "source_url": "https://www.mgmotor.co.in/vehicles/mgwindsor",
        "source_type": "official_model_spec",
        "values": {
            "length_mm": 4295,
            "width_mm": 1850,
            "height_mm": 1677,
            "wheelbase_mm": 2700,
            "ground_clearance_mm": 186,
            "turning_radius_metres": 5.6,
        },
        "evidence": "MG Windsor EV official model specifications: dimensions, ground clearance, turning radius.",
    },
    ("Mahindra", "XUV 3XO"): {
        "source_url": "https://auto.mahindra.com/suv/xuv3xo",
        "source_type": "official_model_spec",
        "values": {
            "length_mm": 3995,
            "width_mm": 1821,
            "height_mm": 1617,
            "wheelbase_mm": 2600,
            "ground_clearance_mm": 201,
            "turning_radius_metres": 5.3,
        },
        "evidence": "Mahindra XUV 3XO official/model specifications: dimensions, ground clearance, turning radius.",
    },
}


POWERTRAIN_SPECS: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("Tata", "Nexon"): [
        {
            "match": {"fuel_type": "Petrol", "engine_cc": 1199},
            "values": {"boot_space_litres": 382, "fuel_tank_capacity_litres": 44, "drivetrain": "FWD", "cylinders": 3, "turbocharged": True},
            "evidence": "Tata Nexon petrol Revotron powertrain and ICE packaging specifications.",
        },
        {
            "match": {"fuel_type": "Diesel", "engine_cc": 1497},
            "values": {"boot_space_litres": 382, "fuel_tank_capacity_litres": 44, "drivetrain": "FWD", "cylinders": 4, "turbocharged": True},
            "evidence": "Tata Nexon diesel Revotorq powertrain and ICE packaging specifications.",
        },
        {
            "match": {"fuel_type": "CNG", "engine_cc": 1199},
            "values": {"drivetrain": "FWD", "cylinders": 3, "turbocharged": True},
            "evidence": "Tata Nexon iCNG uses the 1.2L turbo petrol-derived CNG powertrain; boot/fuel-tank values withheld.",
        },
    ],
    ("Hyundai", "Creta"): [
        {
            "match": {"fuel_type": "Petrol", "engine_cc": 1497},
            "values": {"boot_space_litres": 433, "fuel_tank_capacity_litres": 50, "drivetrain": "FWD", "cylinders": 4, "turbocharged": False},
            "evidence": "Hyundai Creta 1.5 MPi petrol official/specification powertrain and packaging values.",
        },
        {
            "match": {"fuel_type": "Petrol", "engine_cc": 1482},
            "values": {"boot_space_litres": 433, "fuel_tank_capacity_litres": 50, "drivetrain": "FWD", "cylinders": 4, "turbocharged": True},
            "evidence": "Hyundai Creta 1.5 turbo petrol official/specification powertrain and packaging values.",
        },
        {
            "match": {"fuel_type": "Diesel", "engine_cc": 1493},
            "values": {"boot_space_litres": 433, "fuel_tank_capacity_litres": 50, "drivetrain": "FWD", "cylinders": 4, "turbocharged": True},
            "evidence": "Hyundai Creta 1.5 CRDi diesel official/specification powertrain and packaging values.",
        },
    ],
    ("Maruti Suzuki", "Swift"): [
        {
            "match": {"fuel_type": "Petrol", "engine_cc": 1197},
            "values": {"boot_space_litres": 265, "fuel_tank_capacity_litres": 37, "drivetrain": "FWD", "cylinders": 3, "turbocharged": False},
            "evidence": "Maruti Suzuki Swift Z-series petrol official specifications.",
        },
        {
            "match": {"fuel_type": "CNG", "engine_cc": 1197},
            "values": {"drivetrain": "FWD", "cylinders": 3, "turbocharged": False},
            "evidence": "Maruti Suzuki Swift CNG uses the Z-series three-cylinder powertrain; boot/fuel values withheld for unit/package ambiguity.",
        },
    ],
    ("MG", "Windsor EV"): [
        {
            "match": {"fuel_type": "Electric"},
            "values": {"boot_space_litres": 604, "drivetrain": "FWD", "gearbox_speeds": 1},
            "evidence": "MG Windsor EV official model specifications and single-speed EV drive unit.",
        },
    ],
    ("Mahindra", "XUV 3XO"): [
        {
            "match": {"fuel_type": "Petrol", "engine_cc": 1197},
            "values": {"boot_space_litres": 364, "fuel_tank_capacity_litres": 42, "drivetrain": "FWD", "cylinders": 3, "turbocharged": True},
            "evidence": "Mahindra XUV 3XO petrol powertrain and packaging specifications.",
        },
        {
            "match": {"fuel_type": "Diesel", "engine_cc": 1498},
            "values": {"boot_space_litres": 364, "fuel_tank_capacity_litres": 42, "drivetrain": "FWD", "cylinders": 4, "turbocharged": True},
            "evidence": "Mahindra XUV 3XO diesel powertrain and packaging specifications.",
        },
    ],
}


GEARBOX_RULES: dict[tuple[str, str], list[tuple[str, int, str]]] = {
    ("Tata", "Nexon"): [
        (r"5 Speed Manual", 5, "variant-specific label contains 5 Speed Manual"),
        (r"6 Speed Manual", 6, "variant-specific label contains 6 Speed Manual"),
        (r"Automatic \\(AMT\\)", 6, "Nexon AMT is a 6-speed automated manual"),
        (r"Automatic \\(DCT\\)", 7, "Nexon DCT is a 7-speed dual-clutch automatic"),
    ],
    ("Hyundai", "Creta"): [
        (r"Manual", 6, "Creta manual transmission is 6-speed"),
        (r"Automatic \\(DCT\\)", 7, "Creta turbo DCT is 7-speed"),
        (r"Automatic \\(TC\\)", 6, "Creta diesel torque-converter automatic is 6-speed"),
    ],
    ("Maruti Suzuki", "Swift"): [
        (r"Manual", 5, "Swift manual transmission is 5-speed"),
        (r"Automatic \\(AMT\\)|Automatic$", 5, "Swift AMT is 5-speed"),
    ],
    ("Mahindra", "XUV 3XO"): [
        (r"Manual", 6, "XUV 3XO manual transmission is 6-speed"),
        (r"Automatic \\(AMT\\)", 6, "XUV 3XO diesel AMT is 6-speed"),
        (r"Automatic \\(TC\\)", 6, "XUV 3XO torque-converter automatic is 6-speed"),
    ],
}


FIELD_UNITS = {
    "boot_space_litres": "litres",
    "ground_clearance_mm": "mm",
    "kerb_weight_kg": "kg",
    "turning_radius_metres": "metres",
    "fuel_tank_capacity_litres": "litres",
    "length_mm": "mm",
    "width_mm": "mm",
    "height_mm": "mm",
    "wheelbase_mm": "mm",
    "gearbox_speeds": "speeds",
    "cylinders": "count",
}


class OemSpecAdapter(SourceAdapter):
    """Return candidate values from a curated official-spec manifest."""

    source_name = "Official OEM specifications"
    supported_fields = TARGET_FIELDS
    parser_version = "oem-shared-spec-v1"

    def find_record(self, record: dict) -> dict | None:
        key = (record.get("make"), record.get("model"))
        if key in MODEL_SPECS or key in POWERTRAIN_SPECS:
            return {"model_key": key}
        return None

    def extract_candidates(self, record: dict, fields: list[str]) -> list[dict]:
        match = self.find_record(record)
        if not match:
            return []
        candidates: list[dict] = []
        key = match["model_key"]
        model_spec = MODEL_SPECS.get(key)
        for field in fields:
            if model_spec and field in model_spec["values"]:
                candidates.append(self._candidate(record, field, model_spec["values"][field], "MODEL_LEVEL", model_spec))

        powertrain_spec = self._matching_powertrain_spec(record, key)
        if powertrain_spec:
            source_info = {**(model_spec or {}), "evidence": powertrain_spec["evidence"]}
            for field, value in powertrain_spec["values"].items():
                if field in fields:
                    candidates.append(self._candidate(record, field, value, "POWERTRAIN_LEVEL", source_info))

        gearbox_candidate = self._gearbox_candidate(record, fields, key, model_spec)
        if gearbox_candidate:
            candidates.append(gearbox_candidate)
        return candidates

    def _matching_powertrain_spec(self, record: dict, key: tuple[str, str]) -> dict | None:
        for spec in POWERTRAIN_SPECS.get(key, []):
            if all(record.get(match_field) == match_value for match_field, match_value in spec["match"].items()):
                return spec
        return None

    def _gearbox_candidate(self, record: dict, fields: list[str], key: tuple[str, str], model_spec: dict | None) -> dict | None:
        if "gearbox_speeds" not in fields:
            return None
        text = " ".join(str(record.get(field) or "") for field in ("variant", "transmission"))
        for pattern, speeds, evidence in GEARBOX_RULES.get(key, []):
            if re.search(pattern, text, flags=re.IGNORECASE):
                source_info = {**(model_spec or {}), "evidence": evidence}
                return self._candidate(record, "gearbox_speeds", speeds, "POWERTRAIN_LEVEL", source_info)
        if str(record.get("fuel_type") or "").lower() == "electric":
            source_info = {**(model_spec or {}), "evidence": "EV direct-drive single-speed transmission"}
            return self._candidate(record, "gearbox_speeds", 1, "POWERTRAIN_LEVEL", source_info)
        return None

    def _candidate(self, record: dict, field: str, value: Any, scope: str, source_info: dict) -> dict:
        source_type = source_info.get("source_type", "official_model_spec")
        return candidate_value(
            record_id=str(record.get("_record_id")),
            target_record_ids=[str(record.get("_record_id"))],
            field_name=field,
            proposed_value=value,
            normalized_value=value,
            unit=FIELD_UNITS.get(field),
            source_name=self.source_name,
            source_type=source_type,
            source_url_or_document_path=source_info.get("source_url"),
            extraction_method="curated_official_spec_manifest",
            exact_match_confidence=0.95,
            field_confidence=0.95,
            inheritance_used=scope in {"MODEL_LEVEL", "POWERTRAIN_LEVEL"},
            inheritance_scope=scope,
            inherited_from_record_id=f"{record.get('make')}|{record.get('model')}|{scope}",
            evidence_snippet_or_source_key=source_info.get("evidence"),
            parser_version=self.parser_version,
            validation_status="UNVALIDATED",
        )
