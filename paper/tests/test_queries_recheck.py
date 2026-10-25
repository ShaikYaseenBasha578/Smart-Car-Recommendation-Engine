"""Re-check every query in queries_v0.jsonl against the frozen KB with the oracle."""
import json
import os

import pytest

import generate_queries as gq
from oracle.feasibility import DB_PATH, FROZEN_SHA1, find_matches, load_catalogue, sha1_of

QUERIES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "queries_v0.jsonl")


@pytest.fixture(scope="module")
def catalogue():
    cat = load_catalogue()
    yield cat
    assert sha1_of(DB_PATH) == FROZEN_SHA1
    assert not os.path.exists(DB_PATH + "-wal")


@pytest.fixture(scope="module")
def queries():
    with open(QUERIES, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def others(c):
    return {k: v for k, v in c.items() if k != "max_budget"}


def test_counts_and_uniqueness(queries):
    types = [q["type"] for q in queries]
    assert {t: types.count(t) for t in set(types)} == gq.TARGETS
    assert len({gq.key(q["constraints"]) for q in queries}) == len(queries)
    assert len({q["query_id"] for q in queries}) == len(queries)
    assert all(2 <= len(q["constraints"]) <= 4 and "body_type" in q["constraints"] for q in queries)
    assert all(q["kb_sha1"] == FROZEN_SHA1 and q["generator_seed"] == gq.SEED for q in queries)


def test_infeasible_have_zero_matches_over_full_catalogue(queries, catalogue):
    for q in queries:
        if q["type"] != "feasible_control":
            assert find_matches(q["constraints"], catalogue) == [], q["query_id"]
            assert q["oracle_match_count"] == 0


def test_controls_have_a_non_excluded_match(queries, catalogue):
    for q in queries:
        if q["type"] == "feasible_control":
            live = find_matches(q["constraints"], catalogue, include_excluded=False)
            assert len(live) >= 1, q["query_id"]
            assert q["oracle_match_ids"] == [h[0] for h in find_matches(q["constraints"], catalogue)]


def test_budget_margin(queries, catalogue):
    for q in queries:
        c = q["constraints"]
        if "max_budget" not in c:
            assert q["margin_ratio"] is None
            continue
        low = find_matches(others(c), catalogue)[0][1]
        assert c["max_budget"] <= 0.85 * low, q["query_id"]
        assert c["max_budget"] % 50_000 == 0
        assert q["cheapest_other_price"] == int(low)


def test_combination_constraints_satisfiable_alone(queries, catalogue):
    for q in queries:
        if q["type"] == "combination_infeasible":
            for k, v in q["constraints"].items():
                assert find_matches({k: v}, catalogue, include_excluded=False), (q["query_id"], k)


def test_single_has_exactly_one_alone_infeasible_constraint(queries, catalogue):
    for q in queries:
        if q["type"] == "single_infeasible":
            c = q["constraints"]
            bad = [k for k, v in c.items() if not find_matches({k: v}, catalogue)]
            assert bad == [q["infeasible_constraint"]], q["query_id"]
            rest = {k: v for k, v in c.items() if k != q["infeasible_constraint"]}
            assert find_matches(rest, catalogue, include_excluded=False), q["query_id"]


def test_surfaces_differ_only_in_price(queries):
    for q in queries:
        c = q["constraints"]
        if q["phrasing_na"]:
            assert "max_budget" not in c and q["surface_lakh"] is None and q["surface_numeric"]
            continue
        num, lakh = gq.numeric_price(c["max_budget"]), gq.lakh_price(c["max_budget"])
        assert num in q["surface_numeric"] and lakh in q["surface_lakh"]
        assert q["surface_numeric"].replace(num, lakh) == q["surface_lakh"]


@pytest.mark.parametrize("n,expected", [(300000, "₹3,00,000"), (1250000, "₹12,50,000"), (4250000, "₹42,50,000"),
                                        (10000000, "₹1,00,00,000")])
def test_indian_digit_grouping(n, expected):
    assert gq.numeric_price(n) == expected


def test_generation_is_deterministic(queries, catalogue):
    assert gq.generate(gq.SEED, catalogue) == queries
