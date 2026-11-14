# Recommendation evaluation

One command runs everything, no network, no LLM:

    .venv/bin/python eval/run_eval.py --engine current --out eval/results/<name>.json
    .venv/bin/python eval/run_eval.py --engine v3 ...        # services/recsys/api.py recommend(query)
    .venv/bin/python eval/run_eval.py --queries eval/other.jsonl ...   # another query file (default eval/queries.jsonl)
    .venv/bin/python eval/run_eval.py --compare a.json b.json          # side-by-side table of the summary metrics
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

- **a. Constraint satisfaction.** For every returned car the runner looks up its catalogue row (by `variant_id` when the
  response carries it, else model + variant) and checks every hard constraint in `expect`. A violation is a KNOWN value
  that breaks the constraint (a feature known absent for a required one, known present for an excluded one, a number on
  the wrong side of a bound). Unknown values never count as violations. A CNG row's `mileage_kmpl` is treated as unknown
  (it holds km/kg). Reported: share of queries (among those that returned cars) with zero violations, by constraint
  kind, and every violation. **Only non-relaxed responses are counted** (see a2); the number is reported for both engines.
- **a2. Relaxed results and label truthfulness.** A response with a top-level `relaxation` and per-car `violations` (v3)
  is a deliberately relaxed result. Its cars are not counted as violations. Instead, for every car, the constraints it
  really breaks (the same catalogue check) must all be named in that car's `violations`, and nothing else may be named
  ("like X" size bands cannot be checked from a label and are ignored on both sides). Names are compared after mapping
  both sides to one vocabulary (budget, fuel, body, make, gearbox, transmission_family, seats, feature:x,
  exclude_feature:x, min:col, max:col). Reported: relaxed responses, truthful vs mislabelled, and every mislabelled case.
- **b. Parse accuracy.** `intent_to_label()` is the one function that maps the parser's intent object to the label
  form above (hard constraints only; soft preferences and "assumed" guesses are not mapped). Per field, over all
  queries, an unstated field counts as an empty expectation, so a guessed field the user never stated is a false positive.
  Reported: precision (of what the parser produced, how much was right), recall (of what the query states, how much was
  found), and exact-match rate over queries where the field is stated or produced.
- **c. Over-constrained handling.** For `expect_empty` queries, one of: `empty` (no cars, with or without relaxation
  hints); `relaxed_truthfully_labelled`; `relaxed_but_mislabelled` (also: cars marked relaxed in a form the runner cannot
  check); `cars_returned_unmarked` (the bad case). Also lists satisfiable queries that came back empty.
- **d. Vague / unsupported brand.** How many returned cars; whether the response carries `vague: true`; whether it is
  labelled not personalised (v3: `personalised: false`); whether the message names an unsupported brand.
- **e. Paraphrase consistency.** For each group of three wordings, over all pairs: mean Jaccard of the top-5 model sets,
  top-1 agreement (same first model), and rank-biased overlap (extrapolated RBO, p = 0.9) of the top-8 model lists.
  Each is reported for all groups and separately for groups whose three wordings parsed to an IDENTICAL intent
  (hard constraints, use case, soft preferences, assumed guesses) versus groups that parsed differently, so a perfect
  score from identical parses is distinguishable from a ranking that is robust to different parses.
- **f. Unknown-handling probe (both engines).** For 15 feature queries (7 with a hard-required feature, 8 soft wishes)
  the runner takes the top FIVE returned models; for each it copies the catalogue, blanks the requested feature
  column(s) on ALL variants of that model (one model at a time), re-runs the same engine on the modified catalogue (v3:
  `recommend(catalogue=...)`; current: patched `services.new_car_service.get_catalogue`), and records (i) whether the
  model is still returned (in the engine's top list), (ii) its rank change, (iii) whether any car KNOWN to lack the
  feature now ranks above it, and whether it was already above before the blanking ("newly above" is the defect signal).
  With a hard-required feature the known-lacking cars are filtered out, so only the soft cases can show the defect.
  A model that falls out of the list after blanking has dropped below the list limit; it is not filtered out.
- **g. Shortlist agreement.** If `shortlist_sheet.csv` has filled rows (`car_1`..`car_5` as "Make Model"), recall@8 and
  mean reciprocal rank of the engine's top 8 against them (make + model, case-insensitive); otherwise the runner prints
  "no shortlists filled in yet". The sheet is filled by the owner, never by the runner.
