# Plan: the three #60 follow-ups (PR K), 26 Nov 2026

One small PR, cut from the latest main. A Sonnet subagent builds it, and Opus reviews it and reruns every proof.

## 1. "What we understood" chips for the other upper limits
**Today:** the parser already sets five upper limits, and the filter applies them, but the "What we understood" line shows nothing for them:

| Field | Example |
|---|---|
| `max_boot_space_litres` | "boot under 300 litres" |
| `max_ground_clearance_mm` | "ground clearance below 170 mm" |
| `max_ev_range_km` | "EV range under 300 km" |
| `max_mileage_kmpl` | "mileage up to 15 kmpl" |
| `max_mileage_km_per_kg` | a km/kg upper limit |

The same five also print without a unit in the requirement and relaxation lines (`MAX_UNITS` only covers length).

**Change:**
- Add chips to `MAX_LABELS` in `static/script.js`, worded like the existing min chips:
  - "boot up to 300 L";
  - "ground clearance up to 170 mm";
  - "up to 300 km range";
  - "up to 15 kmpl";
  - "up to N km/kg".
- Add the units to `MAX_UNITS` in `filter_v2.py`: " L", " mm", " km", " kmpl", " km/kg".
- This changes display text only, for queries that set these limits. Results do not change.

## 2. "CVT nahi" no longer means "automatics only"
**Today:**
- "kuch bhi chalega bas CVT nahi, 12 lakh tak" ("anything is fine, just not CVT") excludes CVT and also sets the family to automatic, which removes every manual. "no DCT please" does the same.
- #60 fixed this for AMT only. CVT was left because of hard query hq-020, but hq-020's label expects only `transmission_exclude: [cvt]`, so the label agrees with this fix.

**Change:** in `intent_v2._parse_transmission`, a negated gearbox type (CVT, DCT, torque converter, AMT) only excludes that type. It no longer sets a family.
- "automatic but no CVT" keeps the automatic family, from the word "automatic".
- "no manual" still means automatic, as today.

**Expected effect:** more cars for these queries, because manuals are allowed again. I'll list every changed parse and every eval query whose result changes. If more than 20 eval parses change, a blind review runs first, as in PR 4.

## 3. The AI parser keeps the ground-clearance preference
**Today:** `services/recsys/llm_parse.py:733` rebuilds the soft-preference list from `iv.SOFT_PREFERENCES` whenever the AI parser adds one. That silently drops the rule-only `ground_clearance` preference. The AI parser is off on Render, so nothing breaks today.

**Change:** keep the rule-only preferences when the list is rebuilt. The AI parser's prompt stays byte-identical, and a test pins this.

## Proof
- **Parse dump:** the 391 entries (`$S/parse_dump.py`), before and after. Every change must come from item 2 or item 1.
- **Eval:**
  - main: zero-violation and verified counts must not drop (193/193 and 182);
  - held-out: the same (105/107 and 91);
  - the hard queries are reported, but they are not a gate.
- **Tests:** full pytest, the UI gates, and new tests for each item.
- **Screenshots:** before and after of a query with an upper limit, at 1280 and 375, light and dark.

## Not in this PR
The owner-side items (hard-query labels, price review, RAG timeout, brochures, photos, worktree clean-up) and the KB backlog.

## Owner decision (26 Nov)
Approved as written.
