# Recommendation evaluation

One command runs everything, no network, no LLM:

    .venv/bin/python eval/run_eval.py --engine current --out eval/results/<name>.json
    .venv/bin/python eval/run_eval.py --engine v3 ...        # needs services/recsys/api.py (recommend(query))
    .venv/bin/python eval/run_eval.py --check-labels         # labels vs catalogue, engine not run

## Files

- `queries.jsonl` : 209 queries, one JSON object per line: `id`, `query`, `category`, `expect`, optional `paraphrase_group`.
  Categories: plain_english 40, hinglish 34, budget_phrasing 20, negations 25, numeric_bounds 15, named_make_model 15,
  over_constrained 15, vague 10, unsupported_brand 5, paraphrase 30 (10 groups of 3, one Hinglish wording each).
- `shortlist_sheet.csv` + `SHORTLIST_INSTRUCTIONS.md` : 40 queries the owner labels by hand (five cars each).
- `results/` : JSON output of runs (`baseline_current.json` is the engine before any change).
- `run_eval.py` : the runner.

## Label format (`expect`)

`expect` holds only what the query itself states, written from the meaning of the query, not copied from the parser.
A key that is absent means the query says nothing about it. Vocabulary is the catalogue's.

| key | meaning |
|---|---|
| `budget_min`, `budget_max` | rupees, ex-showroom price bounds |
| `budget_around` | rupees; "around 10 lakh". Checked as +/-20%; the parser must give a band that brackets it |
| `fuel_include`, `fuel_exclude` | from petrol, diesel, cng, electric, hybrid |
| `body_include`, `body_exclude` | from suv, hatchback, sedan, mpv, van, pickup |
| `transmission_family` | `automatic` or `manual` ("not automatic" is labelled `manual`) |
| `transmission_include`, `transmission_exclude` | types: manual, imt, amt, dct, cvt, e_cvt, torque_converter, single_speed_ev |
| `seats_min` | minimum seats |
| `required_features`, `excluded_features` | from sunroof, adas, camera_360, ventilated_seats, cruise_control, wireless_charging, heads_up_display, android_auto, apple_carplay |
| `makes_include`, `makes_exclude`, `models_include` | catalogue spelling ("Maruti Suzuki", "Scorpio-N") |
| `reference_models` | "like X": X must not be returned; X is not a filter |
| `numeric_min`, `numeric_max` | maps from airbags, safety_stars_adult, ev_range_km, ground_clearance_mm, boot_space_litres, mileage_kmpl, mileage_km_per_kg to a number |
| `expect_empty` | true: nothing in the catalogue satisfies the query (verified by `--check-labels`) |
| `vague` | true: no usable constraint at all |
| `unsupported_brand` | brand names (as the parser spells them) that the catalogue does not carry |

## Metrics

- **a. Constraint satisfaction.** For every returned car the runner looks up its catalogue row and checks every hard
  constraint in `expect`. A violation is a KNOWN value that breaks the constraint (a feature known absent for a
  required one, known present for an excluded one, a number on the wrong side of a bound). Unknown values never
  count as violations (the engine keeps them and flags them). A CNG row's `mileage_kmpl` is treated as unknown (it holds km/kg).
  Reported: share of queries (among those that returned cars) with zero violations, by constraint kind, and every violation.
  Cars explicitly marked relaxed (`relaxed`, `broken_constraints`, ...) are not counted.
- **b. Parse accuracy.** `intent_to_label()` is the one function that maps the parser's intent object to the label
  form above (hard constraints only; soft preferences and "assumed" guesses are not mapped). Per field, over all
  queries, an unstated field counts as an empty expectation, so a guessed field the user never stated is a false positive.
  Reported: precision (of what the parser produced, how much was right), recall (of what the query states, how much was
  found), and exact-match rate over queries where the field is stated or produced.
- **c. Empty handling.** For `expect_empty` queries: no cars (with or without relaxation hints), cars marked relaxed, or
  cars returned unmarked (the bad case). Also lists satisfiable queries that came back empty.
- **d. Vague / unsupported brand.** How many returned cars; whether the response carries `vague: true`; whether the
  message names an unsupported brand.
- **e. Paraphrase consistency.** For each group, mean pairwise Jaccard overlap of the top-5 model sets across the three
  wordings; reported as the mean over groups.
- **f. Unknown-handling probe.** For 10 feature queries (5 hard-required, 5 soft wishes) the runner copies the catalogue,
  blanks the feature column(s) on the top result's variant, re-runs, and reports where that car lands and whether a car
  known to LACK the feature is now ranked above it ("unknown scored as no"). With a hard-required feature the known-lacking
  cars are filtered out, so only the soft cases can show the defect. Current engine only.
