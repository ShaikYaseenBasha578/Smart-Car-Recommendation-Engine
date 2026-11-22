"""Side-by-side comparison of up to four catalogue variants: GET /compare?ids=1,2,3.

Read-only. Every spec cell goes through car_detail.spec_item, so a value the car page would call "Not verified" (blank,
or listed in the row's unverified_fields) reads the same here, and nothing is shown that the car page would not show.
Nothing here ranks or filters: it only lays the chosen variants next to each other.
"""

from __future__ import annotations

from urllib.parse import quote

from services.car_detail import FUEL_LABELS, _blank, mileage_display, spec_item
from services.catalogue import get_catalogue
from services.images import find_car_image, image_attribution
from services.new_car_service import TRANSMISSION_LABELS, data_as_of, safe_slug, safety_summary

MAX_COMPARE = 4
NOT_VERIFIED = "Not verified"
NO_RATING_LABEL = "No crash-test rating on record"   # same wording as the result card and the car page

# values this close to the best count as tied for "Best" (same idea as TIE in static/script.js)
TOLERANCE = {"price": 10000, "kmpl": 0.1, "kmkg": 0.1, "range": 5, "boot": 5, "airbags": 0, "stars": 0, "rating": 0.05}
UNIT_KEY = {"kmpl": "kmpl", "km/kg": "kmkg", "km": "range"}


def parse_ids(raw: str) -> list[int]:
    """'3,x,3,-1,0,7' -> [3, 7]: positive integers only, first occurrence kept, at most MAX_COMPARE."""
    out: list[int] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part.isdigit() or int(part) <= 0 or int(part) in out:
            continue
        out.append(int(part))
        if len(out) == MAX_COMPARE:
            break
    return out


def format_price(value: float) -> str:
    """Same wording as formatPrice in static/script.js: 849000 -> '₹8.49 lakh', 10200000 -> '₹1.02 crore'."""
    if value >= 1e7:
        return f"₹{round(value / 1e7, 2):g} crore"
    if value >= 1e5:
        return f"₹{round(value / 1e5, 2):g} lakh"
    return f"₹{round(value):,}"


def _cell(display: str, status: str = "ok", best: bool = False) -> dict:
    return {"display": display, "status": status, "best": best}


def _spec_cell(row, col: str, label: str, kind: str) -> tuple[dict, object]:
    """(cell, raw value or None) for a spec column, exactly as the car page decides it."""
    item = spec_item(row, col, label, kind)
    if item["status"] == "ok":
        return _cell(item["value_display"]), row[col]
    return _cell(NOT_VERIFIED, item["status"]), None


def mark_best(values: list, higher_is_better: bool, tol: float, groups: list | None = None) -> list[bool]:
    """Which cells win. At least 2 known values (within a group, when groups are given); the winners are the known values
    within `tol` of the best one; when every known value ties nobody wins."""
    flags = [False] * len(values)
    for g in set(groups) if groups is not None else [None]:
        idx = [i for i, v in enumerate(values) if v is not None and (groups is None or groups[i] == g)]
        if len(idx) < 2:
            continue
        vals = [values[i] for i in idx]
        best = max(vals) if higher_is_better else min(vals)
        winners = [i for i in idx if abs(values[i] - best) <= tol + 1e-9]
        if len(winners) < len(idx):
            for i in winners:
                flags[i] = True
    return flags


def _slugs(row) -> tuple[str, str]:
    return safe_slug(row["make"]), safe_slug(row["model"])


def _car(row, app_root_path: str) -> dict:
    make_slug, model_slug = _slugs(row)
    vid = int(row["variant_id"])
    return {
        "variant_id": vid, "make": row["make"], "model": row["model"], "variant": row["variant"],
        "make_slug": make_slug, "model_slug": model_slug,
        "image": find_car_image(app_root_path, row["make"], row["model"], row["body_type"]),
        "image_attribution": image_attribution(app_root_path, row["make"], row["model"]),
        "url": f"/car/{quote(make_slug)}/{quote(model_slug)}?variant_id={vid}",
    }


def _safety_text(summary: dict) -> str:
    n = summary["stars_adult"]
    text = f"{n} star{'' if n == 1 else 's'} adult"
    if summary["stars_child"] is not None:
        text += f", {summary['stars_child']} child"
    tail = " ".join(str(x) for x in (summary["testing_body"], summary["year"]) if x)
    return f"{text} · {tail}" if tail else text


def _mileage_cell(row) -> tuple[dict, float | None, str | None]:
    col = {"electric": "ev_range_km", "cng": "mileage_km_per_kg"}.get(row["fuel_type"], "mileage_kmpl")
    item = spec_item(row, col, "Mileage", "")   # the car page's verdict on this cell (unverified, not applicable)
    shown = mileage_display(row)
    if item["status"] != "ok" or shown["value"] is None:
        return _cell(NOT_VERIFIED, item["status"] if item["status"] != "ok" else "unverified"), None, None
    return _cell(shown["value"]), float(row[col]), UNIT_KEY[shown["unit"]]


def _reviewers_cell(model: str, evidence) -> tuple[dict, float | None]:
    from services.recsys.explain import expert_standing
    st = expert_standing(model, evidence)
    if not st or st.get("score") is None or st.get("scale_max") is None:
        return _cell("No review score", "none"), None
    return _cell(f"{round(float(st['score']), 1):g}/{float(st['scale_max']):g} ({st['source']})"), float(st["score"])


def _owners_cell(model: str, evidence) -> tuple[dict, float | None]:
    from services.recsys.explain import owner_standing
    st = owner_standing(model, evidence)
    if not st or st.get("rating") is None:
        return _cell("No owner ratings", "none"), None
    text = f"{round(float(st['rating']), 1):g}/{float(st['scale_max']):g}"
    n = st.get("rating_count")
    low = st.get("band") == "low_confidence"
    if n is not None:
        text += f" from {'only ' if low else ''}{n:,} rating{'' if n == 1 else 's'}"
    return _cell(text), None if low else float(st["rating"])   # a thin sample is shown but never wins


def differing_rows(rows: list[dict]) -> list[dict]:
    """The rows whose cells do not all show the same text ("Show differences only"). Display only: nothing is re-ranked."""
    return [r for r in rows if len({c["display"] for c in r["cells"]}) > 1]


def get_compare(ids: list[int], app_root_path: str = ".", diff: bool = False) -> dict:
    from services.recsys.evidence import get_evidence

    cat = get_catalogue()
    rows = [cat.loc[i] for i in ids if i in cat.index]
    missing = len(ids) - len(rows)
    cars = [_car(r, app_root_path) for r in rows]
    n = len(rows)
    out_rows: list[dict] = []

    def add(label: str, cells: list[dict], flags: list[bool] | None = None) -> None:
        if flags:
            for c, f in zip(cells, flags):
                c["best"] = bool(f) and c["status"] == "ok"
        out_rows.append({"label": label, "cells": cells})

    if n:
        evidence = get_evidence()
        prices = [None if _blank(r["price_ex_showroom"]) else float(r["price_ex_showroom"]) for r in rows]
        add("Price (ex-showroom)", [_cell(format_price(p)) if p is not None else _cell("Price not listed", "none") for p in prices],
            mark_best(prices, False, TOLERANCE["price"]))

        add("Gearbox", [_spec_cell(r, "transmission_type", "Gearbox", "transmission")[0] for r in rows])
        add("Fuel", [_spec_cell(r, "fuel_type", "Fuel", "fuel")[0] for r in rows])

        mil = [_mileage_cell(r) for r in rows]
        units = [m[2] for m in mil]
        flags = [False] * n
        for unit in {u for u in units if u}:   # only cars sharing a unit are ranked, so petrol never meets EV
            same = [m[1] if m[2] == unit else None for m in mil]
            for i, f in enumerate(mark_best(same, True, TOLERANCE[unit])):
                flags[i] = flags[i] or f
        add("Mileage / range", [m[0] for m in mil], flags)

        add("Seats", [_spec_cell(r, "seats", "Seats", "")[0] for r in rows])
        boot = [_spec_cell(r, "boot_space_litres", "Boot space", " litres") for r in rows]
        add("Boot space", [b[0] for b in boot],
            mark_best([None if b[1] is None else float(b[1]) for b in boot], True, TOLERANCE["boot"]))

        safety = [safety_summary(r) for r in rows]
        add("Safety rating", [_cell(_safety_text(s)) if s else _cell(NO_RATING_LABEL, "none") for s in safety],
            mark_best([None if s is None else float(s["stars_adult"]) for s in safety], True, TOLERANCE["stars"]))

        bags = [_spec_cell(r, "airbags", "Airbags", "") for r in rows]
        add("Airbags", [b[0] for b in bags],
            mark_best([None if b[1] is None or _blank(b[1]) else float(b[1]) for b in bags], True, TOLERANCE["airbags"]))

        add("ADAS", [_spec_cell(r, "adas_available", "ADAS", "bool")[0] for r in rows])
        add("Sunroof", [_spec_cell(r, "sunroof", "Sunroof", "bool")[0] for r in rows])

        rev = [_reviewers_cell(r["model"], evidence) for r in rows]
        add("Reviewers", [x[0] for x in rev], mark_best([x[1] for x in rev], True, TOLERANCE["rating"]))
        own = [_owners_cell(r["model"], evidence) for r in rows]
        add("Owners", [x[0] for x in own], mark_best([x[1] for x in own], True, TOLERANCE["rating"]))

    total = len(out_rows)
    if diff:
        out_rows = differing_rows(out_rows)
    return {"cars": cars, "rows": out_rows, "missing": missing, "data_as_of": data_as_of(),
            "diff": diff, "all_equal": bool(diff and total and not out_rows)}
