# Shortlist sheet: what to fill in

File: `eval/shortlist_sheet.csv` (40 queries). Do not look at what the engine returns first.

1. For each row, read the query and imagine you are the friend asked for advice.
2. Write the cars you would suggest in `car_1` to `car_5`, best first.
3. Each entry is make + model, for example `Hyundai Creta` or `Maruti Suzuki Brezza`. No variants.
4. Fewer than five is fine. Leave the rest blank. Only suggest what you would really stand behind.
5. Use the catalogue's model names where you can (see `data/catalogue.csv`); do not suggest cars it does not have.
6. Respect the query: budget, fuel, body type and so on are hard limits.
7. `notes` is optional: one line on anything odd (for example "needs a budget to answer well").
8. Save as CSV in the same place. Do not rename columns.
9. The score will be the overlap between your list and the engine's top five, per query.
10. If a query is unanswerable in the catalogue, write `none` in `car_1`.
