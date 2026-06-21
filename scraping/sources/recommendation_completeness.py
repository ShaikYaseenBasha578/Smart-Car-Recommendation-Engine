"""Recommendation-focused completeness scoring for canonical processed records."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from scraping.schemas.new_car_schema import NEW_CAR_COLUMNS
from scraping.schemas.null_reasons import field_null_reason


ROOT = Path(__file__).resolve().parents[2]
READY_DATASET = ROOT / "datasets/processed/carrec_canonical_recommendation_ready.json"
POLICY_PATH = ROOT / "scraping/config/field_enrichment_policy.json"
REPORT_JSON = ROOT / "scraping/outputs/recommendation_completeness_report.json"
REPORT_MD = ROOT / "scraping/outputs/recommendation_completeness_report.md"


CATEGORY_WEIGHTS = {
    "CORE_REQUIRED": 5,
    "HIGH_VALUE": 3,
    "SPECIALIST": 2,
    "OPTIONAL": 1,
    "SUBJECTIVE_OR_DERIVED": 0,
    "DEFER_OR_REMOVE": 0,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(wrapper: dict[str, Any]) -> dict[str, Any]:
    return wrapper.get("canonical_record") if isinstance(wrapper.get("canonical_record"), dict) else wrapper


def populated(value: Any) -> bool:
    return value not in (None, "", [], {})


def weighted_completeness_for_record(record: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    weighted_total = 0
    weighted_populated = 0
    missing_weight_by_field = {}
    category_scores = defaultdict(lambda: {"total": 0, "populated": 0})
    for field in NEW_CAR_COLUMNS:
        if field_null_reason(field, record, policy) == "NOT_APPLICABLE":
            continue
        category = policy[field]["category"]
        weight = CATEGORY_WEIGHTS.get(category, 0)
        if weight <= 0:
            continue
        weighted_total += weight
        category_scores[category]["total"] += weight
        if populated(record.get(field)):
            weighted_populated += weight
            category_scores[category]["populated"] += weight
        else:
            missing_weight_by_field[field] = weight
    score = round(weighted_populated / weighted_total * 100, 2) if weighted_total else 100.0
    return {
        "score": score,
        "weighted_total": weighted_total,
        "weighted_populated": weighted_populated,
        "missing_weight_by_field": missing_weight_by_field,
        "category_scores": {
            category: {
                **values,
                "score": round(values["populated"] / values["total"] * 100, 2) if values["total"] else 100.0,
            }
            for category, values in category_scores.items()
        },
    }


def readiness_label(record: dict[str, Any], weighted: dict[str, Any], policy: dict[str, Any]) -> str:
    missing_core = [
        field
        for field in NEW_CAR_COLUMNS
        if policy[field]["category"] == "CORE_REQUIRED"
        and field_null_reason(field, record, policy) != "NOT_APPLICABLE"
        and not populated(record.get(field))
    ]
    if missing_core:
        return "BASIC_READY"
    if weighted["score"] >= 90:
        return "SPECIALIST_READY"
    if weighted["score"] >= 78:
        return "STRONG_RECOMMENDATION_READY"
    if weighted["score"] >= 60:
        return "PARTIALLY_ENRICHED"
    return "BASIC_READY"


def summarize(records: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    per_record = []
    missing_weight_counter = Counter()
    by_model = defaultdict(list)
    by_fuel = defaultdict(list)
    by_body = defaultdict(list)
    by_transmission = defaultdict(list)
    tier_counter = Counter()

    for wrapper in records:
        record = canonical(wrapper)
        weighted = weighted_completeness_for_record(record, policy)
        label = readiness_label(record, weighted, policy)
        tier_counter[label] += 1
        for field, weight in weighted["missing_weight_by_field"].items():
            missing_weight_counter[field] += weight
        row = {
            "record_id": str(wrapper.get("version_id") or record.get("full_name")),
            "make": record.get("make"),
            "model": record.get("model"),
            "variant": record.get("variant"),
            "fuel_type": record.get("fuel_type"),
            "transmission": record.get("transmission"),
            "body_type": record.get("body_type"),
            "weighted_score": weighted["score"],
            "readiness_label": label,
            "missing_weight_by_field": weighted["missing_weight_by_field"],
            "category_scores": weighted["category_scores"],
        }
        per_record.append(row)
        by_model[record.get("model") or "UNKNOWN"].append(weighted["score"])
        by_fuel[record.get("fuel_type") or "UNKNOWN"].append(weighted["score"])
        by_body[record.get("body_type") or "UNKNOWN"].append(weighted["score"])
        by_transmission[record.get("transmission") or "UNKNOWN"].append(weighted["score"])

    def score_summary(groups: dict[str, list[float]]) -> dict[str, Any]:
        return {
            key: {
                "records": len(values),
                "average_score": round(mean(values), 2),
                "minimum_score": round(min(values), 2),
                "maximum_score": round(max(values), 2),
            }
            for key, values in sorted(groups.items())
        }

    return {
        "records_audited": len(records),
        "average_weighted_score": round(mean(row["weighted_score"] for row in per_record), 2) if per_record else 0.0,
        "minimum_weighted_score": round(min(row["weighted_score"] for row in per_record), 2) if per_record else 0.0,
        "maximum_weighted_score": round(max(row["weighted_score"] for row in per_record), 2) if per_record else 0.0,
        "readiness_tiers": dict(tier_counter),
        "score_by_model": score_summary(by_model),
        "score_by_fuel_type": score_summary(by_fuel),
        "score_by_body_type": score_summary(by_body),
        "score_by_transmission": score_summary(by_transmission),
        "largest_information_loss_fields": [
            {
                "field": field,
                "missing_weight": weight,
                "category": policy[field]["category"],
                "preferred_source": policy[field]["preferred_source"],
            }
            for field, weight in missing_weight_counter.most_common(25)
        ],
        "per_record": per_record,
    }


def write_markdown(report: dict[str, Any], report_md: Path = REPORT_MD) -> None:
    lines = [
        "# Recommendation Completeness Report",
        "",
        f"- Records audited: {report['records_audited']}",
        f"- Average weighted recommendation completeness: {report['average_weighted_score']}%",
        f"- Minimum weighted score: {report['minimum_weighted_score']}%",
        f"- Maximum weighted score: {report['maximum_weighted_score']}%",
        "",
        "## Readiness Tiers",
        "",
        "| Tier | Records |",
        "|---|---:|",
    ]
    for tier, count in sorted(report["readiness_tiers"].items()):
        lines.append(f"| {tier} | {count} |")
    lines.extend(["", "## Largest Information Loss Fields", "", "| Field | Missing weight | Category | Preferred source |", "|---|---:|---|---|"])
    for item in report["largest_information_loss_fields"]:
        lines.append(f"| `{item['field']}` | {item['missing_weight']} | {item['category']} | {item['preferred_source']} |")
    lines.extend(["", "## Score By Model", "", "| Model | Records | Average score |", "|---|---:|---:|"])
    for model, values in report["score_by_model"].items():
        lines.append(f"| {model} | {values['records']} | {values['average_score']}% |")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score canonical records for recommendation completeness.")
    parser.add_argument("--input", default=str(READY_DATASET), help="Canonical wrapper JSON to score.")
    parser.add_argument("--report-json", default=str(REPORT_JSON), help="Path to write JSON report.")
    parser.add_argument("--report-md", default=str(REPORT_MD), help="Path to write Markdown report.")
    args = parser.parse_args()

    records = load_json(Path(args.input))
    policy = load_json(POLICY_PATH)
    report = summarize(records, policy)
    Path(args.report_json).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(report, Path(args.report_md))
    print(json.dumps({key: report[key] for key in ("records_audited", "average_weighted_score", "readiness_tiers")}, indent=2))


if __name__ == "__main__":
    main()
