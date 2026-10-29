"""Prompt build checks: conditions differ only by the grounding table; phrasings differ only by the price."""
import json
import os
import re

import pytest

import generate_queries as gq
from oracle.feasibility import load_catalogue
from prompts import build_prompts as bp

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FORBIDDEN = re.compile(r"feasib|nothing|no car|abstain|disclos|relax|violat|exclud|minimal|control|"
                       r"single_|combination|oracle|unsatisf|impossible|doesn't exist|does not exist", re.IGNORECASE)


@pytest.fixture(scope="module")
def built():
    return bp.build()


@pytest.fixture(scope="module")
def on_disk():
    with open(os.path.join(DATA, "system_prompts_v0.json"), encoding="utf-8") as f:
        systems = json.load(f)
    with open(os.path.join(DATA, "prompts_v0.jsonl"), encoding="utf-8") as f:
        prompts = [json.loads(line) for line in f]
    return systems, prompts


@pytest.fixture(scope="module")
def queries():
    with open(os.path.join(DATA, "queries_v0.jsonl"), encoding="utf-8") as f:
        return {q["query_id"]: q for q in map(json.loads, f)}


def test_files_match_a_fresh_build(built, on_disk):
    assert built == on_disk


def test_catalogue_csv_matches_the_frozen_kb():
    kb = {r["variant_id"]: r for r in load_catalogue()}
    rows = bp.load_catalogue_csv()
    assert len(rows) == len(kb)
    for r in rows:
        k = kb[int(r["variant_id"])]
        assert (r["model"], r["variant_name"], r["body_type"], r["fuel_raw"], r["transmission_raw"]) == \
            (k["model"], k["variant_name"], k["body_type"], k["fuel_raw"], k["transmission_raw"])
        assert int(r["seats"]) == k["seats"] and int(r["price"]) == k["price"]
        assert r["model_excluded"] == str(int(k["model_excluded"]))


def test_grounded_is_ungrounded_plus_table_only(on_disk):
    systems, _ = on_disk
    u = systems["U"]["text"]
    for sid, s in systems.items():
        if sid == "U":
            continue
        assert s["text"].startswith(u + "\n\n"), sid
        extra = s["text"][len(u):]
        assert "Catalogue models:" not in extra and bp.INSTRUCTIONS not in extra


def test_ungrounded_lists_every_model_and_no_specs(on_disk):
    systems, _ = on_disk
    u = systems["U"]["text"]
    rows = bp.load_catalogue_csv()
    for mfr, model in {(r["manufacturer"], r["model"]) for r in rows}:
        assert f"- {mfr} {model}\n" in u + "\n"
    assert u.count("\n- ") == 62
    assert "₹" not in u and "|" not in u and "lakh" not in u.lower()


def test_grounded_table_covers_exactly_the_body_types_configurations(on_disk):
    systems, _ = on_disk
    rows = bp.load_catalogue_csv()
    for sid, s in systems.items():
        if sid == "U":
            continue
        body_rows = [r for r in rows if r["body_type"] == s["body_type"]]
        assert s["table_variant_ids"] == sorted(int(r["variant_id"]) for r in body_rows)
        configs = {}
        for r in body_rows:
            configs.setdefault((r["manufacturer"], r["model"], r["fuel_raw"], r["transmission_raw"], r["seats"]),
                               []).append(int(r["price"]))
        table_lines = [ln for ln in s["text"].splitlines() if ln.startswith("| ") and "Manufacturer" not in ln]
        assert len(table_lines) == len(configs) == s["table_rows"], sid
        for (mfr, model, fuel, trans, seats), prices in configs.items():
            lo, hi = bp.indian_rupees(min(prices)), bp.indian_rupees(max(prices))
            rng = lo if lo == hi else f"{lo} – {hi}"
            line = f"| {mfr} | {model} | {fuel} | {trans} | {seats} | {len(prices)} | {rng} |"
            assert line in table_lines, (sid, line)


def test_compact_table_preserves_every_query_verdict(on_disk, queries):
    """A configuration row admits a query iff some variant in it matches, so the table loses no feasibility fact."""
    from oracle.feasibility import FUEL_MAP, TRANSMISSION_MAP, find_matches, load_catalogue
    cat = load_catalogue()
    rows = bp.load_catalogue_csv()
    for q in queries.values():
        c = q["constraints"]
        ok_rows = [g for g in bp.configurations(rows, c["body_type"])
                   if ("fuel" not in c or FUEL_MAP[g["key"][2]] == c["fuel"])
                   and ("transmission" not in c or TRANSMISSION_MAP[g["key"][3]] == c["transmission"])
                   and ("min_seats" not in c or int(g["key"][4]) >= c["min_seats"])
                   and ("max_budget" not in c or g["min_price"] <= c["max_budget"])]
        assert bool(ok_rows) == bool(find_matches(c, cat)), q["query_id"]


def test_prompt_records_cover_every_query_once_per_cell(on_disk, queries):
    _, prompts = on_disk
    assert len({p["prompt_id"] for p in prompts}) == len(prompts)
    per_q = {}
    for p in prompts:
        per_q.setdefault(p["query_id"], set()).add((p["condition"], p["phrasing"]))
    assert set(per_q) == set(queries)
    for qid, cells in per_q.items():
        phr = {"na"} if queries[qid]["phrasing_na"] else {"numeric", "lakh"}
        assert cells == {(c, ph) for c in ("ungrounded", "grounded") for ph in phr}


def test_user_text_is_the_query_surface_and_phrasings_differ_only_in_price(on_disk, queries):
    systems, prompts = on_disk
    by = {(p["query_id"], p["condition"], p["phrasing"]): p for p in prompts}
    for p in prompts:
        q = queries[p["query_id"]]
        assert p["user"] == (q["surface_lakh"] if p["phrasing"] == "lakh" else q["surface_numeric"])
        assert p["system_id"] == ("U" if p["condition"] == "ungrounded" else f"G-{q['constraints']['body_type']}")
        assert p["system_sha256"] == systems[p["system_id"]]["sha256"] == bp.sha256(systems[p["system_id"]]["text"])
        assert p["messages_sha256"] == bp.sha256(json.dumps([systems[p["system_id"]]["text"], p["user"]],
                                                             ensure_ascii=False))
        if p["phrasing"] == "numeric":
            lakh = by[(p["query_id"], p["condition"], "lakh")]
            assert lakh["system_id"] == p["system_id"]
            b = q["constraints"]["max_budget"]
            assert p["user"].replace(gq.numeric_price(b), gq.lakh_price(b)) == lakh["user"]


def test_no_feasibility_or_label_leakage(on_disk):
    systems, prompts = on_disk
    for sid, s in systems.items():
        assert not FORBIDDEN.search(s["text"]), (sid, FORBIDDEN.search(s["text"]).group())
    for p in prompts:
        assert not FORBIDDEN.search(p["user"]), p["prompt_id"]
