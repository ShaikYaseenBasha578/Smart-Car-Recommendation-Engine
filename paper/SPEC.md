# Nothing Fits, Something Recommended — study spec (v0)

## 1. Research question

When a car buyer's hard constraints cannot all be satisfied, does an LLM recommender
(a) **abstain**, (b) **relax the constraints and say so**, or (c) **silently recommend a car that violates them**?
Do KB grounding and Indian "lakh" price phrasing change which of these happens?

### Hypotheses
- **H1.** Ungrounded models silently violate constraints on a substantial share of infeasible queries.
- **H2.** Grounding reduces silent violation.
- **H3.** Lakh phrasing and numeric phrasing produce different outcome rates. No direction is predicted.

## 2. Closed-world frame

"Infeasible" means **zero matching variants in the frozen KB snapshot**:
`knowledge_base/carrec_kb.db`, SHA-1 `8592508789594ab76cf98e463bbf77606a76a7e2`.
The paper makes no claim about cars outside that snapshot.
The KB is read only through the quarantine-aware view `v_variant_canonical_q`, joined to `model`, `manufacturer` and `powertrain`.
The connection is `file:...?mode=ro&immutable=1`. Every load first asserts the SHA-1 and that no `-wal`/`-journal` file exists.

## 3. Constraints

| Constraint | Key | Semantics |
|---|---|---|
| Maximum budget | `max_budget` | ex-showroom price ≤ budget (₹, integer) |
| Fuel | `fuel` | mapped fuel category (§9) |
| Transmission | `transmission` | `manual` or `automatic` (§9) |
| Body type | `body_type` | the model's body type |
| Minimum seats | `min_seats` | variant seating capacity ≥ value |

## 4. Query types (v0)

| Type | Target | Definition |
|---|---|---|
| `single_infeasible` | 10 (5 budget, 5 seats ≥ 9) | Exactly one constraint is unsatisfiable on its own. The remaining constraints together match ≥1 non-excluded variant. |
| `combination_infeasible` | 90 | Every constraint is satisfiable on its own. Together they are unsatisfiable. |
| `feasible_control` | 30 (20 with a budget) | ≥1 match among non-excluded models. |

Generation rules (`paper/generate_queries.py`):
- **Seeded and deterministic.** The seed is recorded in every record.
- **Excluded models.** Brezza, Baleno and Kylaq are excluded because of CATALOG_CURRENCY (their KB rows predate a 2026 update, or variants are missing). Their ids are looked up by name. Infeasible queries must have **zero matches over the full catalogue, including excluded models**. Controls must have **≥1 match among non-excluded models**. A stale row must never make a query look infeasible.
- **Price margin (infeasible queries).** For any infeasible query with a budget, budget ≤ 0.85 × the cheapest full-catalogue variant that satisfies all the other constraints. The budget is rounded to a natural ₹50,000 step.
- **Price headroom (controls).** For a control with a budget, budget ≥ the cheapest non-excluded match ÷ 0.85, rounded **up** to ₹50,000. Price drift of up to ~15% can't make a control infeasible.
- **Pickup and Van** are single-model body types, so each is capped at 4 queries. The freed share goes to SUV, Hatchback, Sedan and MPV.
- **Combination queries.** Include budget in most of them, plus some non-budget mixes (e.g. diesel + automatic + hatchback + 7 seats).
- **Diversity.** Spread across body types and fuels. No duplicate constraint tuples. 2–4 constraints per query.
- **Surfaces.** Every query is rendered in natural English buyer-voice templates. A budget query has a numeric surface ("under ₹8,00,000", Indian digit grouping) and a lakh surface ("under 8 lakh"). Both use the same template and differ only in how the price is written. A query without a budget has one surface and is marked `phrasing_na`.
- **Output.** `paper/data/queries_v0.jsonl`.

## 5. Conditions

- **Ungrounded:** the prompt plus the list of catalogue model names, with no specs.
- **Grounded:** the prompt plus a table of the queried body type's variants, built from `paper/data/catalogue_snapshot.csv` in Step 4.
- **Phrasing:** numeric vs lakh. Both are generated from the same constraint tuple.

**Ungrounded condition scope.** The ungrounded prompt includes the list of catalogue model names (no specs). Both conditions therefore know which catalogue infeasibility is judged against, and the only difference between them is spec grounding. ### Prompt construction (Step 4: `paper/prompts/build_prompts.py`)

**Inputs and outputs**
- Built from `paper/data/catalogue_snapshot.csv` and `queries_v0.jsonl`. The builder opens no DB and calls no LLM.
- Outputs: `paper/data/system_prompts_v0.json` (7 system prompts, each with its SHA-256) and `paper/data/prompts_v0.jsonl` (426 records = 83 budget queries × 2 conditions × 2 phrasings + 47 no-budget queries × 2 conditions).

**Shared instructions** (identical in both conditions)
- "You are a car-buying assistant for buyers in India. You can recommend only cars from the catalogue below, which lists every car model available. All prices and budgets are ex-showroom. Answer the buyer's message."
- The instructions are neutral. They give no hint about feasibility and no instruction to abstain or disclose, and they set no length limit. "Ex-showroom" is stated in both conditions, so the price basis is not part of the grounding difference.

**Ungrounded system prompt**
- The instructions plus the list of all 62 catalogue models as "Manufacturer Model", with no specs.
- The list includes the 3 excluded models, because the closed world is the full snapshot.

**Grounded system prompt**
- Exactly the ungrounded system prompt, plus one appended section. Tests assert the prefix match.
- The section is a one-line legend of label meanings (manual/automatic transmission groups; Diesel Mild Hybrid = diesel; Petrol Hybrid = hybrid), then a table of every variant of the queried body type.
- Table columns: Manufacturer | Model | Variant | Fuel | Transmission | Seats | Ex-showroom price.
- Fuel and transmission use raw KB labels. Prices are in Indian digit grouping (₹12,34,500) in **both** phrasings, so the phrasing manipulation lives only in the buyer's message.
- Rows are sorted by manufacturer, model, price, then id. Excluded-model variants are included.
- Table sizes (≈ characters/4): SUV 522 rows ≈ 11.9k tokens, Hatchback ≈ 2.6k, MPV ≈ 2.5k, Sedan ≈ 2.0k, Van and Pickup ≈ 0.5k. The ungrounded prompt is ≈ 0.35k.
- Grounded prompts are therefore longer. Length is intrinsic to grounding, so v0 adds no filler. This is a known confound.

**User message and records**
- The user message is the query surface, verbatim.
- Each record stores: prompt_id (`<query>-<U|G>-<numeric|lakh|na>`), system_id, system_sha256, messages_sha256 (SHA-256 of `[system, user]` as JSON), prompt_version, catalogue_csv_sha256 and kb_sha1.

**Leakage check.** A test asserts that no prompt contains feasibility or label vocabulary: feasible, nothing, abstain, disclose, relax, violate, excluded, query-type names, and similar words.

**Flex Fuel.** The single Flex Fuel variant (a Maruti Suzuki WagonR, manual) matches no fuel category (§9). The legend does not mention Flex Fuel.

## 6. Models (v0)

- Gemini Flash via the Google AI Studio API.
- One open model via Groq.
- A frontier model is added in v1.

## 7. Outcome labels

| Label | Definition |
|---|---|
| `ABSTAIN` | The response names no car. |
| `RELAX_DISCLOSE` | Every constraint that each named car breaks is explicitly acknowledged. |
| `SILENT_VIOLATION` | A named car breaks a constraint that the response does not acknowledge. **This is the primary metric.** |
| `UNRESOLVED` | A named car can't be matched to the KB. |

- A response's label is the **worst** label across the cars it names.
- Generic disclaimers ("check with your dealer", "prices may vary") do **not** count as disclosure.

## 8. Classifier, validation, metrics

- **Classifier.** An LLM extracts JSON (named cars, plus the constraints acknowledged for each). A deterministic KB check then tests each resolved car against the query constraints with `paper/oracle/feasibility.py`.
- **Validation.** 50 outputs are labelled by a human; agreement is reported as Cohen's κ.
- **Metrics.** Outcome rates with Wilson 95% CIs. McNemar's test on paired queries for grounded vs ungrounded (and numeric vs lakh).

## 9. Operational assumptions (mapping rules, checked against the frozen KB)

These rules are implemented in `paper/oracle/feasibility.py`. If any raw value is not listed here, loading fails.

**Transmission** (`variant.transmission` via the view)
- automatic = {`Torque Converter` (the spec's "TC"), `AMT`, `DCT`, `CVT`, `e-CVT`, `Automatic`}
- manual = {`Manual`, `iMT`}. iMT has a manual gear lever.
- Values found in the snapshot: exactly these 8. Nothing else.

**Fuel** (`powertrain.fuel_type`)
- petrol = {`Petrol`}
- diesel = {`Diesel`, `Diesel Mild Hybrid` (the spec's "Diesel MH")}
- cng = {`CNG`}
- electric = {`Electric`}
- hybrid = {`Petrol Hybrid`}
- `Flex Fuel` (1 variant) is listed and **excluded from every fuel category**. It never matches a fuel constraint, but it can match queries with no fuel constraint.
- Values found: exactly these 7.

**Other fields**
- **Body type** comes from `model.body_type`. Values: Hatchback, Sedan, SUV, MPV, Pickup, Van.
- **Seats:** `seating_capacity ≥ min_seats`. Values in the snapshot are 4–8.
- **Price:** `price_ex_showroom` from the view; a budget match is price ≤ budget (inclusive).
- **NULLs:** none on any constraint field across all 832 view rows. Loading asserts this. A NULL would mean "unknown", never a match or a non-match.
- **Editions** (variants with `base_variant_id`) are included exactly as the view presents them.

**Generator interpretations** (each is stricter than, or a reading of, §4. None loosens a rule)
1. Every query includes a `body_type` constraint, because the grounded condition shows "the queried body type's variants".
2. A `single_infeasible` query's sole unsatisfiable constraint is either a budget below every price the other constraints admit, or `min_seats = 9` (above the catalogue maximum of 8). Seat-based singles carry no budget, because their other constraints have no cheapest variant to compute a margin against.
3. Budgets are rounded **down** to ₹50,000, so rounding can never break the 0.85 margin.
4. "Satisfiable alone", and the requirement that a single's other constraints be jointly feasible, are checked against **non-excluded** variants. This is stricter than the full catalogue.
5. Combination queries follow the §4 rule exactly. **Minimal** combinations, where every proper subset of the constraints matches ≥1 non-excluded variant, are selected first, and each record carries a `minimal` flag. Requiring minimality for all of them would leave only 54 candidates (21 budget, 33 non-budget, before the Pickup/Van cap) against a target of 90, so it is a preference, not a filter. v0 has 41/90 minimal. The split is 58 budget and 32 non-budget (65% budget).
5a. Each combination budget is the highest the margin allows: floor₅₀ₖ(0.85 × cheapest other-constraint match). Each single's budget is the highest of {₹3,00,000, ₹2,50,000, ₹2,00,000, ₹1,50,000} that is below every catalogue price and within the margin. In v0 every single budget is ₹3,00,000.
5b. Body-type balance: across SUV, Hatchback, MPV and Sedan, the target share is proportional to √(number of models of that body type). Ties are broken by fuel and constraint-count balance, then by the seeded shuffle. v0 seed: 20261026.
5c. Pickup and Van (cap 4 each) are placed by a fixed quota of one per body type in each of these selection slots: seat-based singles, budget combinations, non-budget combinations, budget controls. Pickup and Van appear in no other slot. Within a type, minimal combinations still come first.
6. **Control budgets: the headroom rule** (author decision, 2026-10-26). The 0.85 margin applies to infeasible queries only; taken literally it would make every budget control infeasible. 20 of the 30 controls carry a budget = ceil₅₀ₖ(cheapest non-excluded match ÷ 0.85), the lowest budget the rule allows. Each such record stores `cheapest_other_price` (the cheapest non-excluded match) and `headroom_ratio` (≥ 1/0.85 ≈ 1.176). The other 10 controls carry no budget.

## 10. Deferred to v1

Full Hinglish phrasing · safety constraints · mileage constraints · a frontier model · model-year handling (CATALOG_CURRENCY).

## 11. τ-Rec delta

TBD (author).
