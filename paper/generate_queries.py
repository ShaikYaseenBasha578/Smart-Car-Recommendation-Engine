"""Generate the v0 query set (paper/SPEC.md §4, §9) from the frozen KB. Seeded and deterministic; no LLM calls.

Usage: python3 paper/generate_queries.py [--seed N]   -> paper/data/queries_v0.jsonl
"""
import argparse
import itertools
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oracle.feasibility import (BODY_TYPES, FROZEN_SHA1, FUELS, TRANSMISSIONS,  # noqa: E402
                                find_matches, load_catalogue)

SEED = 20261026
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "queries_v0.jsonl")
TARGETS = {"single_infeasible": 30, "combination_infeasible": 70, "feasible_control": 30}
COMBO_BUDGET_SHARE = 0.65  # "prefer mixes that include budget"
MARGIN = 0.85
BUDGET_STEP = 50_000
SINGLE_BUDGETS = (150_000, 200_000, 250_000, 300_000)  # below every catalogue price (min ₹3,49,900)
SEAT_OPTIONS = (5, 6, 7, 8)
INFEASIBLE_SEATS = 9  # catalogue maximum is 8
KEY_ORDER = ("body_type", "fuel", "transmission", "min_seats", "max_budget")
# Body-type balance: target share proportional to sqrt(models of that body type), so small classes still appear.
BODY_WEIGHT = {"SUV": math.sqrt(33), "Hatchback": math.sqrt(10), "MPV": math.sqrt(9), "Sedan": math.sqrt(8),
               "Pickup": 1.0, "Van": 1.0}


# ---------------------------------------------------------------- oracle helpers

def n_all(c, cat):
    return len(find_matches(c, cat))


def n_live(c, cat):
    return len(find_matches(c, cat, include_excluded=False))


def cheapest(c, cat):
    hits = find_matches(c, cat)
    return hits[0][1] if hits else None


def margin_budget(cheapest_price):
    return int(math.floor(MARGIN * cheapest_price / BUDGET_STEP) * BUDGET_STEP)


def key(c):
    return tuple((k, c[k]) for k in KEY_ORDER if k in c)


def proper_subsets(c):
    keys = list(c)
    for r in range(1, len(keys)):
        for sub in itertools.combinations(keys, r):
            yield {k: c[k] for k in sub}


def base_sets(max_extra):
    """body_type plus 0..max_extra of {fuel, transmission, min_seats}."""
    dims = (("fuel", FUELS), ("transmission", TRANSMISSIONS), ("min_seats", SEAT_OPTIONS))
    for body in BODY_TYPES:
        for r in range(0, max_extra + 1):
            for chosen in itertools.combinations(dims, r):
                for values in itertools.product(*(vals for _, vals in chosen)):
                    c = {"body_type": body}
                    c.update({name: v for (name, _), v in zip(chosen, values)})
                    yield c


# ---------------------------------------------------------------- candidates

def single_candidates(cat):
    out = []
    for base in base_sets(2):
        if n_live(base, cat) < 1:
            continue  # the other constraints must be jointly feasible
        low = cheapest(base, cat)
        for b in sorted(SINGLE_BUDGETS, reverse=True):  # one budget per base: the highest that qualifies
            c = dict(base, max_budget=b)
            if (len(c) <= 4 and b <= MARGIN * low and n_all({"max_budget": b}, cat) == 0
                    and n_all(c, cat) == 0):
                out.append({"constraints": c, "infeasible_constraint": "max_budget", "cheapest_other_price": low})
                break
        if "min_seats" not in base and len(base) + 1 <= 3:
            c = dict(base, min_seats=INFEASIBLE_SEATS)
            if n_all({"min_seats": INFEASIBLE_SEATS}, cat) == 0 and n_all(c, cat) == 0:
                out.append({"constraints": c, "infeasible_constraint": "min_seats", "cheapest_other_price": None})
    return out


def combination_ok(c, cat):
    """Each constraint alone matches >=1 non-excluded variant; together they match 0 over the full catalogue."""
    return n_all(c, cat) == 0 and all(n_live({k: v}, cat) >= 1 for k, v in c.items())


def is_minimal(c, cat):
    """Every proper subset matches >=1 non-excluded variant: the infeasibility needs every stated constraint."""
    return all(n_live(sub, cat) >= 1 for sub in proper_subsets(c))


def combination_candidates(cat):
    budget, nonbudget = [], []
    for base in base_sets(3):
        if len(base) >= 2 and combination_ok(base, cat):
            nonbudget.append({"constraints": base, "minimal": is_minimal(base, cat)})
        if len(base) <= 3 and n_live(base, cat) >= 1:
            b = margin_budget(cheapest(base, cat))
            c = dict(base, max_budget=b)
            if b > 0 and combination_ok(c, cat):
                budget.append({"constraints": c, "minimal": is_minimal(c, cat)})
    return budget, nonbudget


def select_preferring_minimal(cands, n, rng, taken):
    minimal = [c for c in cands if c["minimal"]]
    picked = select(minimal, min(n, len(minimal)), rng, taken)
    rest = [c for c in cands if not c["minimal"]]
    return picked + (select(rest, n - len(picked), rng, taken) if len(picked) < n else [])


def control_candidates(cat):
    # No budget: the literal margin rule makes any budget query infeasible (SPEC §9, interpretation 6).
    return [{"constraints": base} for base in base_sets(3) if len(base) >= 2 and n_live(base, cat) >= 1]


# ---------------------------------------------------------------- balanced selection

def select(cands, n, rng, taken):
    pool = [c for c in cands if key(c["constraints"]) not in taken]
    rng.shuffle(pool)
    total_w = sum(BODY_WEIGHT.values())
    body_n, fuel_n, size_n, picked = {}, {}, {}, []
    while len(picked) < n and pool:
        k = len(picked) + 1

        def score(cand):
            c = cand["constraints"]
            deficit = BODY_WEIGHT[c["body_type"]] / total_w * k - body_n.get(c["body_type"], 0)
            return (-deficit, fuel_n.get(c.get("fuel", "any"), 0), size_n.get(len(c), 0))

        best = min(range(len(pool)), key=lambda i: score(pool[i]))
        cand = pool.pop(best)
        c = cand["constraints"]
        picked.append(cand)
        taken.add(key(c))
        body_n[c["body_type"]] = body_n.get(c["body_type"], 0) + 1
        fuel_n[c.get("fuel", "any")] = fuel_n.get(c.get("fuel", "any"), 0) + 1
        size_n[len(c)] = size_n.get(len(c), 0) + 1
    if len(picked) < n:
        raise SystemExit(f"STOP: only {len(picked)} candidates for a target of {n}; rules not loosened")
    return picked


# ---------------------------------------------------------------- surfaces

FUEL_WORD = {"petrol": "petrol", "diesel": "diesel", "cng": "CNG", "electric": "electric", "hybrid": "hybrid"}
BODY_WORD = {"Hatchback": "hatchback", "Sedan": "sedan", "SUV": "SUV", "MPV": "MPV", "Pickup": "pickup",
             "Van": "van"}
AN_WORDS = {"electric", "automatic", "SUV", "MPV"}
PRICE = "<<PRICE>>"
TEMPLATES = {
    "T1": "I need {art} {desc}{budget}{seats}. What should I buy?",
    "T2": "Looking for {art} {desc}{seats}{budget}. Which car would you recommend?",
    "T3": "Can you suggest {art} {desc}{seats}{budget}? I want to buy one soon.",
    "T4": "My budget is " + PRICE + ". I want {art} {desc}{seats}. What are my options?",  # budget queries only
}


def indian_digits(n):
    s = str(int(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    groups.insert(0, head)
    return ",".join(groups + [tail])


def numeric_price(n):
    return "₹" + indian_digits(n)


def lakh_price(n):
    lakh = n / 100_000
    return f"{lakh:g} lakh"


def render(c, template_id):
    words = [FUEL_WORD[c["fuel"]]] if "fuel" in c else []
    words += [c["transmission"]] if "transmission" in c else []
    words.append(BODY_WORD[c["body_type"]])
    desc = " ".join(words)
    art = "an" if words[0] in AN_WORDS else "a"
    seats = f" that seats {c['min_seats']}" if "min_seats" in c else ""
    budget = f" under {PRICE}" if "max_budget" in c and template_id != "T4" else ""
    return TEMPLATES[template_id].format(art=art, desc=desc, seats=seats, budget=budget)


def surfaces(c, rng):
    if "max_budget" in c:
        tid = rng.choice(sorted(TEMPLATES))
        text = render(c, tid)
        return tid, text.replace(PRICE, numeric_price(c["max_budget"])), text.replace(PRICE, lakh_price(c["max_budget"]))
    tid = rng.choice(["T1", "T2", "T3"])
    return tid, render(c, tid), None


# ---------------------------------------------------------------- main

def generate(seed=SEED, cat=None):
    cat = cat if cat is not None else load_catalogue()
    rng = random.Random(seed)
    taken = set()
    singles = select(single_candidates(cat), TARGETS["single_infeasible"], rng, taken)
    budget_c, nonbudget_c = combination_candidates(cat)
    n_budget = round(TARGETS["combination_infeasible"] * COMBO_BUDGET_SHARE)
    combos = (select_preferring_minimal(budget_c, n_budget, rng, taken)
              + select_preferring_minimal(nonbudget_c, TARGETS["combination_infeasible"] - n_budget, rng, taken))
    controls = select(control_candidates(cat), TARGETS["feasible_control"], rng, taken)

    records = []
    for qtype, prefix, group in (("single_infeasible", "S", singles), ("combination_infeasible", "C", combos),
                                 ("feasible_control", "F", controls)):
        for i, cand in enumerate(group, 1):
            c = {k: cand["constraints"][k] for k in KEY_ORDER if k in cand["constraints"]}
            hits = find_matches(c, cat)
            live = find_matches(c, cat, include_excluded=False)
            tid, s_num, s_lakh = surfaces(c, rng)
            rec = {
                "query_id": f"{prefix}{i:03d}",
                "type": qtype,
                "constraints": c,
                "n_constraints": len(c),
                "surface_numeric": s_num,
                "surface_lakh": s_lakh,
                "phrasing_na": "max_budget" not in c,
                "template_id": tid,
                "oracle_match_count": len(hits),
                "oracle_match_count_nonexcluded": len(live),
                "oracle_match_ids": [h[0] for h in hits] if qtype == "feasible_control" else None,
                "cheapest_other_price": None,
                "margin_ratio": None,
                "kb_sha1": FROZEN_SHA1,
                "generator_seed": seed,
            }
            if qtype == "single_infeasible":
                rec["infeasible_constraint"] = cand["infeasible_constraint"]
            if qtype == "combination_infeasible":
                rec["minimal"] = cand["minimal"]
            if "max_budget" in c:
                low = cheapest({k: v for k, v in c.items() if k != "max_budget"}, cat)
                rec["cheapest_other_price"] = int(low)
                rec["margin_ratio"] = round(c["max_budget"] / low, 4)
            records.append(rec)
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    records = generate(args.seed)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} queries to {OUT} (seed {args.seed})")


if __name__ == "__main__":
    main()
